from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import logging
import math
import os
import platform
import re
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
SUPPORTED_EXTENSIONS = {".wav", ".flac"}


@dataclass(frozen=True)
class SegmentConfig:
    ffmpeg_exe: Path
    input_dir: Path
    output_dir: Path
    manifest_dir: Path
    logs_dir: Path
    min_duration: float
    max_duration: float
    target_duration: float
    silence_db: float
    silence_min_seconds: float
    overwrite: bool
    limit: int | None


@dataclass(frozen=True)
class AudioInfo:
    duration: float
    sample_rate: int | None
    channels: int | None


@dataclass(frozen=True)
class Segment:
    index: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def parse_scalar(value: str) -> Any:
    value = value.split("#", 1)[0].strip()
    if not value:
        return ""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return [item.strip().strip("\"'") for item in value[1:-1].split(",") if item.strip()]
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        if any(marker in value.lower() for marker in [".", "e"]):
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_simple_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    data: dict[str, Any] = {}
    current_section: str | None = None

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not raw_line.startswith((" ", "\t")) and stripped.endswith(":"):
            current_section = stripped[:-1]
            data.setdefault(current_section, {})
            continue
        if current_section and ":" in stripped:
            key, value = stripped.split(":", 1)
            data[current_section][key.strip()] = parse_scalar(value)

    return data


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def setup_logging(logs_dir: Path) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logger = logging.getLogger("segmentar_dataset")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = logging.FileHandler(logs_dir / "segmentar_dataset.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def build_config(args: argparse.Namespace) -> SegmentConfig:
    raw_config = load_simple_yaml(CONFIG_PATH)
    caminhos = raw_config.get("caminhos", {})
    segmentacao = raw_config.get("segmentacao", {})

    ffmpeg_value = (
        args.ffmpeg
        or os.environ.get("FFMPEG_EXE")
        or caminhos.get("ffmpeg_exe")
        or "ffmpeg"
    )

    silence_min_ms = float(segmentacao.get("silencio_min_ms", 300))

    return SegmentConfig(
        ffmpeg_exe=Path(ffmpeg_value),
        input_dir=resolve_project_path(args.input or caminhos.get("dados_convertidos", "")),
        output_dir=resolve_project_path(args.output or caminhos.get("dados_segmentos", "")),
        manifest_dir=resolve_project_path(args.manifest_dir or caminhos.get("dados_manifestos", "")),
        logs_dir=resolve_project_path(caminhos.get("pasta_logs", "logs")),
        min_duration=float(args.min_duration or segmentacao.get("duracao_minima", 5.0)),
        max_duration=float(args.max_duration or segmentacao.get("duracao_maxima", 30.0)),
        target_duration=float(args.target_duration or segmentacao.get("duracao_alvo", 20.0)),
        silence_db=float(args.silence_db or segmentacao.get("silencio_db", -40)),
        silence_min_seconds=float(args.silence_min_seconds or silence_min_ms / 1000.0),
        overwrite=args.overwrite,
        limit=args.limit,
    )


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def ffprobe_exe(ffmpeg_exe: Path) -> Path:
    if ffmpeg_exe.name.lower() in {"ffmpeg.exe", "ffmpeg"}:
        candidate = ffmpeg_exe.with_name("ffprobe.exe" if platform.system() == "Windows" else "ffprobe")
        if candidate.exists():
            return candidate
    return Path("ffprobe")


def validate_tools(ffmpeg_exe: Path) -> Path:
    result = run_command([str(ffmpeg_exe), "-version"])
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg nao esta acessivel: {ffmpeg_exe}")

    probe = ffprobe_exe(ffmpeg_exe)
    probe_result = run_command([str(probe), "-version"])
    if probe_result.returncode != 0:
        raise RuntimeError(f"ffprobe nao esta acessivel: {probe}")
    return probe


def get_audio_info(ffprobe: Path, audio_path: Path) -> AudioInfo:
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate,channels:format=duration",
        "-of",
        "json",
        str(audio_path),
    ]
    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())

    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    stream = streams[0] if streams else {}
    duration = float(payload.get("format", {}).get("duration") or 0.0)
    sample_rate = stream.get("sample_rate")
    channels = stream.get("channels")

    return AudioInfo(
        duration=duration,
        sample_rate=int(sample_rate) if sample_rate else None,
        channels=int(channels) if channels else None,
    )


def detect_silence(ffmpeg_exe: Path, audio_path: Path, silence_db: float, silence_min: float) -> list[float]:
    command = [
        str(ffmpeg_exe),
        "-hide_banner",
        "-nostats",
        "-i",
        str(audio_path),
        "-af",
        f"silencedetect=noise={silence_db}dB:d={silence_min}",
        "-f",
        "null",
        "NUL" if platform.system() == "Windows" else "/dev/null",
    ]
    result = run_command(command)
    output = "\n".join([result.stdout, result.stderr])
    if result.returncode != 0 and "silencedetect" not in output:
        raise RuntimeError(output.strip())

    boundaries: list[float] = []
    for match in re.finditer(r"silence_end:\s*([0-9.]+)", output):
        boundaries.append(float(match.group(1)))
    return sorted(set(boundaries))


def choose_boundary(candidates: list[float], earliest: float, target: float, latest: float) -> float | None:
    valid = [item for item in candidates if earliest <= item <= latest]
    if not valid:
        return None
    return min(valid, key=lambda item: abs(item - target))


def build_segments(duration: float, silence_points: list[float], config: SegmentConfig) -> list[Segment]:
    segments: list[Segment] = []
    start = 0.0
    index = 1

    while duration - start > config.max_duration:
        earliest = start + config.min_duration
        target = min(start + config.target_duration, duration)
        latest = min(start + config.max_duration, duration)
        boundary = choose_boundary(silence_points, earliest, target, latest)
        end = boundary if boundary is not None else latest

        if end <= start:
            end = min(start + config.max_duration, duration)

        segments.append(Segment(index=index, start=start, end=end))
        index += 1
        start = end

    if duration - start > 0.25:
        if segments and duration - start < config.min_duration:
            previous = segments[-1]
            needed = config.min_duration - (duration - start)
            if previous.duration - needed >= config.min_duration:
                adjusted_end = previous.end - needed
                segments[-1] = Segment(previous.index, previous.start, adjusted_end)
                segments.append(Segment(index=index, start=adjusted_end, end=duration))
            else:
                segments.append(Segment(index=index, start=start, end=duration))
        else:
            segments.append(Segment(index=index, start=start, end=duration))

    return segments


def safe_stem(path: Path) -> str:
    normalized = unicodedata.normalize("NFKD", path.stem)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_text).strip("_")
    digest = hashlib.sha1(path.name.encode("utf-8", errors="replace")).hexdigest()[:8]
    if not text:
        text = "audio"
    return f"{text}_{digest}"


def cut_segment(ffmpeg_exe: Path, source: Path, destination: Path, segment: Segment) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f"{destination.stem}.{int(time.time() * 1000)}.tmp.wav")
    command = [
        str(ffmpeg_exe),
        "-hide_banner",
        "-y",
        "-ss",
        f"{segment.start:.3f}",
        "-t",
        f"{segment.duration:.3f}",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(temp_path),
    ]
    result = run_command(command)
    if result.returncode != 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError((result.stderr or result.stdout).strip())
    if not temp_path.exists() or temp_path.stat().st_size == 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Segmento vazio gerado: {temp_path}")
    temp_path.replace(destination)


def iter_audio_files(input_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ],
        key=lambda item: str(item).lower(),
    )


def write_manifest(rows: list[dict[str, Any]], manifest_dir: Path) -> None:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = manifest_dir / "segmentos_sem_transcricao.jsonl"
    csv_path = manifest_dir / "segmentos_sem_transcricao.csv"

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    fields = [
        "audio",
        "text_path",
        "source_id",
        "segment_id",
        "start",
        "end",
        "duration",
        "needs_transcription",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def process_dataset(config: SegmentConfig, logger: logging.Logger) -> int:
    ffprobe = validate_tools(config.ffmpeg_exe)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    files = iter_audio_files(config.input_dir)
    if config.limit:
        files = files[: config.limit]

    if not files:
        logger.warning("Nenhum WAV/FLAC encontrado em %s", config.input_dir)
        return 0

    logger.info("Arquivos para segmentar: %s", len(files))
    rows: list[dict[str, Any]] = []
    failures = 0
    total_segments = 0

    for file_index, audio_path in enumerate(files, start=1):
        source_id = safe_stem(audio_path)
        logger.info("[%s/%s] Analisando: %s", file_index, len(files), audio_path.name)
        try:
            info = get_audio_info(ffprobe, audio_path)
            if info.duration <= 0:
                raise ValueError("Duracao invalida")

            silence_points = detect_silence(
                config.ffmpeg_exe, audio_path, config.silence_db, config.silence_min_seconds
            )
            segments = build_segments(info.duration, silence_points, config)
            logger.info(
                "%s segmento(s), duracao %.1fs, pausas detectadas %s",
                len(segments),
                info.duration,
                len(silence_points),
            )

            for segment in segments:
                segment_id = f"{source_id}_seg_{segment.index:04d}"
                destination = config.output_dir / f"{segment_id}.wav"
                text_path = PROJECT_ROOT / "dados_treinamento" / "transcricoes" / f"{segment_id}.txt"

                if destination.exists() and not config.overwrite:
                    logger.info("Ignorado porque ja existe: %s", destination.name)
                else:
                    cut_segment(config.ffmpeg_exe, audio_path, destination, segment)

                rows.append(
                    {
                        "audio": str(destination.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                        "text_path": str(text_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                        "source_id": source_id,
                        "segment_id": segment_id,
                        "start": round(segment.start, 3),
                        "end": round(segment.end, 3),
                        "duration": round(segment.duration, 3),
                        "needs_transcription": True,
                    }
                )
                total_segments += 1
        except Exception:
            failures += 1
            logger.exception("Falha ao segmentar %s", audio_path)

    write_manifest(rows, config.manifest_dir)
    logger.info("Segmentos registrados: %s", total_segments)
    logger.info("Falhas: %s", failures)
    logger.info("Manifestos: %s", config.manifest_dir)
    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Segmenta WAV/FLAC em trechos curtos para revisao e transcricao humana."
    )
    parser.add_argument("--input", help="Pasta com WAV/FLAC convertidos.")
    parser.add_argument("--output", help="Pasta de saida dos segmentos.")
    parser.add_argument("--manifest-dir", help="Pasta dos manifestos gerados.")
    parser.add_argument("--ffmpeg", help="Caminho do ffmpeg.exe. Tambem aceita FFMPEG_EXE.")
    parser.add_argument("--min-duration", type=float, help="Duracao minima desejada por segmento.")
    parser.add_argument("--target-duration", type=float, help="Duracao alvo por segmento.")
    parser.add_argument("--max-duration", type=float, help="Duracao maxima desejada por segmento.")
    parser.add_argument("--silence-db", type=float, help="Limiar de silencio em dB.")
    parser.add_argument("--silence-min-seconds", type=float, help="Duracao minima de pausa.")
    parser.add_argument("--overwrite", action="store_true", help="Recria segmentos existentes.")
    parser.add_argument("--limit", type=int, help="Processa somente os N primeiros arquivos.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = build_config(args)
        logger = setup_logging(config.logs_dir)
        logger.info("Entrada: %s", config.input_dir)
        logger.info("Saida: %s", config.output_dir)
        logger.info("Duracoes min/alvo/max: %.1f/%.1f/%.1fs", config.min_duration, config.target_duration, config.max_duration)
        return process_dataset(config, logger)
    except Exception as exc:
        logger = logging.getLogger("segmentar_dataset")
        if logger.handlers:
            logger.exception("Erro fatal: %s", exc)
        else:
            print(f"Erro fatal: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
