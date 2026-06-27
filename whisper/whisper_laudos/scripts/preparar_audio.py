from __future__ import annotations

import argparse
import ast
import logging
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
DEFAULT_EXTENSIONS = {".mp4", ".m4a", ".mp3", ".wav", ".flac"}


@dataclass(frozen=True)
class AudioPrepConfig:
    ffmpeg_exe: Path
    input_dir: Path
    output_dir: Path
    logs_dir: Path
    extensions: set[str]
    output_format: str
    overwrite: bool
    recursive: bool


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
        if "." in value:
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
        line = raw_line.rstrip()
        stripped = line.strip()
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


def resolve_project_path(value: str | Path, base_dir: Path = PROJECT_ROOT) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


def setup_logging(logs_dir: Path) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logger = logging.getLogger("preparar_audio")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = logging.FileHandler(logs_dir / "preparar_audio.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def build_config(args: argparse.Namespace) -> AudioPrepConfig:
    raw_config = load_simple_yaml(CONFIG_PATH)
    caminhos = raw_config.get("caminhos", {})
    monitoramento = raw_config.get("monitoramento", {})

    ffmpeg_value = (
        args.ffmpeg
        or os.environ.get("FFMPEG_EXE")
        or caminhos.get("ffmpeg_exe")
        or "ffmpeg"
    )
    input_value = args.input or caminhos.get("dados_originais") or "dados_treinamento/originais"
    output_value = args.output or caminhos.get("dados_convertidos") or "dados_treinamento/convertidos"
    logs_value = caminhos.get("pasta_logs") or "logs"
    extensions = {
        str(ext).lower()
        for ext in (args.extensions or monitoramento.get("extensoes_aceitas") or DEFAULT_EXTENSIONS)
    }

    output_format = args.format.lower().lstrip(".")
    if output_format not in {"wav", "flac"}:
        raise ValueError("Formato de saida invalido. Use wav ou flac.")

    return AudioPrepConfig(
        ffmpeg_exe=Path(ffmpeg_value),
        input_dir=resolve_project_path(input_value),
        output_dir=resolve_project_path(output_value),
        logs_dir=resolve_project_path(logs_value),
        extensions=extensions,
        output_format=output_format,
        overwrite=args.overwrite,
        recursive=args.recursive,
    )


def validate_ffmpeg(ffmpeg_exe: Path) -> None:
    try:
        subprocess.run(
            [str(ffmpeg_exe), "-version"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"FFmpeg nao encontrado: {ffmpeg_exe}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg falhou ao iniciar: {exc.stderr}") from exc


def iter_audio_files(input_dir: Path, extensions: set[str], recursive: bool) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    files = [
        path
        for path in input_dir.glob(pattern)
        if path.is_file() and path.suffix.lower() in extensions
    ]
    return sorted(files, key=lambda item: str(item).lower())


def null_output_path() -> str:
    return "NUL" if platform.system().lower() == "windows" else "/dev/null"


def run_ffmpeg(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def validate_audio(ffmpeg_exe: Path, source: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {source}")
    if source.stat().st_size == 0:
        raise ValueError(f"Arquivo vazio: {source}")

    command = [
        str(ffmpeg_exe),
        "-hide_banner",
        "-v",
        "error",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-f",
        "null",
        null_output_path(),
    ]
    result = run_ffmpeg(command)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"Audio invalido ou corrompido: {source}. {detail}")


def conversion_args(output_format: str) -> list[str]:
    if output_format == "wav":
        return ["-c:a", "pcm_s16le"]
    return ["-c:a", "flac", "-compression_level", "5"]


def convert_audio(ffmpeg_exe: Path, source: Path, destination: Path, output_format: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_name(
        f"{destination.stem}.{int(time.time() * 1000)}.tmp{destination.suffix}"
    )

    command = [
        str(ffmpeg_exe),
        "-hide_banner",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        *conversion_args(output_format),
        str(temp_destination),
    ]

    result = run_ffmpeg(command)
    if result.returncode != 0:
        temp_destination.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Falha ao converter {source}: {detail}")

    if not temp_destination.exists() or temp_destination.stat().st_size == 0:
        temp_destination.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg gerou arquivo vazio: {temp_destination}")

    temp_destination.replace(destination)


def output_path_for(source: Path, input_dir: Path, output_dir: Path, output_format: str) -> Path:
    relative = source.relative_to(input_dir)
    return (output_dir / relative).with_suffix(f".{output_format}")


def process_files(config: AudioPrepConfig, logger: logging.Logger) -> int:
    config.input_dir.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    files = iter_audio_files(config.input_dir, config.extensions, config.recursive)
    if not files:
        logger.warning("Nenhum arquivo de audio encontrado em %s", config.input_dir)
        return 0

    logger.info("Arquivos encontrados: %s", len(files))
    converted = 0
    failed = 0

    for index, source in enumerate(files, start=1):
        destination = output_path_for(
            source, config.input_dir, config.output_dir, config.output_format
        )
        logger.info("[%s/%s] Preparando: %s", index, len(files), source)

        if destination.exists() and not config.overwrite:
            logger.info("Ignorado porque ja existe: %s", destination)
            continue

        try:
            validate_audio(config.ffmpeg_exe, source)
            convert_audio(config.ffmpeg_exe, source, destination, config.output_format)
            validate_audio(config.ffmpeg_exe, destination)
            logger.info("Convertido: %s", destination)
            converted += 1
        except Exception:
            failed += 1
            logger.exception("Falha ao processar: %s", source)

    logger.info("Resumo: %s convertido(s), %s falha(s).", converted, failed)
    return 1 if failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Converte audios para mono 16 kHz usando FFmpeg."
    )
    parser.add_argument("--input", help="Pasta de entrada. Padrao: config.yaml dados_originais.")
    parser.add_argument("--output", help="Pasta de saida. Padrao: config.yaml dados_convertidos.")
    parser.add_argument("--ffmpeg", help="Caminho do ffmpeg.exe. Tambem aceita FFMPEG_EXE.")
    parser.add_argument(
        "--format",
        default="wav",
        choices=["wav", "flac"],
        help="Formato de saida. Padrao: wav.",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        help="Extensoes aceitas. Exemplo: --extensions .mp4 .wav .flac",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Procura arquivos em subpastas da entrada.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recria arquivos convertidos ja existentes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = build_config(args)
        logger = setup_logging(config.logs_dir)
        logger.info("Entrada: %s", config.input_dir)
        logger.info("Saida: %s", config.output_dir)
        logger.info("FFmpeg: %s", config.ffmpeg_exe)
        validate_ffmpeg(config.ffmpeg_exe)
        return process_files(config, logger)
    except Exception as exc:
        logger = logging.getLogger("preparar_audio")
        if logger.handlers:
            logger.exception("Erro fatal: %s", exc)
        else:
            print(f"Erro fatal: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
