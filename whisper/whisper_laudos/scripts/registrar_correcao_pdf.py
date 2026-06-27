from __future__ import annotations

import argparse
import ast
import csv
import json
import logging
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
AUDIO_EXTENSIONS = {".mp4"}


@dataclass(frozen=True)
class CycleConfig:
    audios_dir: Path
    whisper_dir: Path
    pdfs_dir: Path
    corrected_texts_dir: Path
    validated_pairs_dir: Path
    rejected_dir: Path
    reports_dir: Path
    pairs_manifest: Path
    logs_dir: Path
    similarity_alert: float


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

    logger = logging.getLogger("registrar_correcao_pdf")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = logging.FileHandler(logs_dir / "registrar_correcao_pdf.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def build_config() -> CycleConfig:
    raw_config = load_simple_yaml(CONFIG_PATH)
    ciclo = raw_config.get("ciclo_tuning", {})
    caminhos = raw_config.get("caminhos", {})

    return CycleConfig(
        audios_dir=resolve_project_path(ciclo.get("audios_recebidos", "ciclo_tuning/audios_recebidos")),
        whisper_dir=resolve_project_path(
            ciclo.get("transcricoes_whisper", "ciclo_tuning/transcricoes_whisper")
        ),
        pdfs_dir=resolve_project_path(ciclo.get("pdfs_corrigidos", "ciclo_tuning/pdfs_corrigidos")),
        corrected_texts_dir=resolve_project_path(
            ciclo.get("textos_corrigidos", "ciclo_tuning/textos_corrigidos")
        ),
        validated_pairs_dir=resolve_project_path(
            ciclo.get("pares_validados", "ciclo_tuning/pares_validados")
        ),
        rejected_dir=resolve_project_path(ciclo.get("rejeitados", "ciclo_tuning/rejeitados")),
        reports_dir=resolve_project_path(ciclo.get("relatorios", "ciclo_tuning/relatorios")),
        pairs_manifest=resolve_project_path(
            ciclo.get("manifesto_pares", "ciclo_tuning/relatorios/pares_ciclo.jsonl")
        ),
        logs_dir=resolve_project_path(caminhos.get("pasta_logs", "logs")),
        similarity_alert=float(ciclo.get("similaridade_minima_alerta", 0.55)),
    )


def ensure_directories(config: CycleConfig) -> None:
    for directory in [
        config.audios_dir,
        config.whisper_dir,
        config.pdfs_dir,
        config.corrected_texts_dir,
        config.validated_pairs_dir,
        config.rejected_dir,
        config.reports_dir,
        config.pairs_manifest.parent,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def normalize_key(path_or_name: str | Path) -> str:
    stem = unicodedata.normalize("NFC", Path(path_or_name).stem).casefold()
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


def find_matching_file(directory: Path, key: str, extensions: set[str]) -> Path | None:
    matches: list[Path] = []
    for path in directory.iterdir():
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        candidate_key = normalize_key(path)
        if candidate_key == key:
            matches.append(path)
    if len(matches) == 1:
        return matches[0]
    return None


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Dependencia ausente: instale PyMuPDF com "
            ".\\venv\\Scripts\\python.exe -m pip install pymupdf"
        ) from exc

    parts: list[str] = []
    with fitz.open(pdf_path) as document:
        for page in document:
            parts.append(page.get_text("text"))
    text = "\n".join(parts)
    return normalize_text_blocks(text)


def normalize_text_blocks(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    compact_lines: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if not previous_blank:
                compact_lines.append("")
            previous_blank = True
            continue
        compact_lines.append(line)
        previous_blank = False
    return "\n".join(compact_lines).strip() + "\n"


def text_for_comparison(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_text_if_exists(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def compute_similarity(whisper_text: str, corrected_text: str) -> float | None:
    whisper_norm = text_for_comparison(whisper_text)
    corrected_norm = text_for_comparison(corrected_text)
    if not whisper_norm or not corrected_norm:
        return None
    return SequenceMatcher(None, whisper_norm, corrected_norm).ratio()


def classify_pair(audio_path: Path | None, whisper_path: Path | None, similarity: float | None, threshold: float) -> str:
    if audio_path is None:
        return "pendente_audio"
    if whisper_path is None:
        return "pendente_transcricao_whisper"
    if similarity is None:
        return "pendente_comparacao"
    if similarity < threshold:
        return "revisar_alinhamento"
    return "pronto_para_validacao_humana"


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def upsert_csv_report(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))

    key = row["case_id"]
    rows = [existing for existing in rows if existing.get("case_id") != key]
    rows.append(row)

    fields = [
        "case_id",
        "status",
        "similarity",
        "audio",
        "whisper_txt",
        "corrected_pdf",
        "corrected_txt",
        "registered_at",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def relative_or_empty(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def register_pdf(pdf_path: Path, case_id: str | None, copy_pdf: bool, config: CycleConfig, logger: logging.Logger) -> dict[str, Any]:
    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"PDF invalido ou inexistente: {pdf_path}")

    resolved_case_id = case_id or pdf_path.stem
    key = normalize_key(resolved_case_id)
    stored_pdf = config.pdfs_dir / f"{resolved_case_id}.pdf"
    if copy_pdf and pdf_path.resolve() != stored_pdf.resolve():
        shutil.copy2(pdf_path, stored_pdf)
    else:
        stored_pdf = pdf_path

    corrected_text = extract_pdf_text(stored_pdf)
    corrected_txt_path = config.corrected_texts_dir / f"{resolved_case_id}.txt"
    corrected_txt_path.write_text(corrected_text, encoding="utf-8", newline="\n")

    audio_path = find_matching_file(config.audios_dir, key, AUDIO_EXTENSIONS)
    whisper_path = find_matching_file(config.whisper_dir, key, {".txt"})
    whisper_text = load_text_if_exists(whisper_path)
    similarity = compute_similarity(whisper_text, corrected_text)
    status = classify_pair(audio_path, whisper_path, similarity, config.similarity_alert)

    row = {
        "case_id": resolved_case_id,
        "status": status,
        "similarity": round(similarity, 4) if similarity is not None else "",
        "audio": relative_or_empty(audio_path),
        "whisper_txt": relative_or_empty(whisper_path),
        "corrected_pdf": relative_or_empty(stored_pdf),
        "corrected_txt": relative_or_empty(corrected_txt_path),
        "registered_at": datetime.now().isoformat(timespec="seconds"),
    }

    append_jsonl(config.pairs_manifest, row)
    upsert_csv_report(config.reports_dir / "pares_ciclo.csv", row)
    logger.info("PDF registrado: %s", stored_pdf)
    logger.info("Status: %s", status)
    if similarity is not None:
        logger.info("Similaridade Whisper vs corrigido: %.4f", similarity)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Registra PDF corrigido, extrai texto e cria par para ciclo mensal de tuning."
    )
    parser.add_argument("pdf", help="Caminho do PDF corrigido.")
    parser.add_argument("--case-id", help="Identificador do caso. Padrao: nome do PDF sem extensao.")
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Nao copia o PDF para ciclo_tuning/pdfs_corrigidos.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = build_config()
        ensure_directories(config)
        logger = setup_logging(config.logs_dir)
        row = register_pdf(Path(args.pdf), args.case_id, not args.no_copy, config, logger)
        print(json.dumps(row, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        logger = logging.getLogger("registrar_correcao_pdf")
        if logger.handlers:
            logger.exception("Erro fatal: %s", exc)
        else:
            print(f"Erro fatal: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
