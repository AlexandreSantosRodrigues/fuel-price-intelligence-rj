"""Executa a auditoria de qualidade dos arquivos brutos da ANP."""

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.quality.raw_audit import audit_csv


def audit_raw_directory(raw_dir: Path) -> dict[str, Any]:
    """Audita os arquivos registrados no manifesto da coleta."""

    manifest_path = raw_dir / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifesto não encontrado: {manifest_path}"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    audited_files = []
    errors = []
    aggregate_nulls: Counter[str] = Counter()

    for position, item in enumerate(manifest, start=1):
        filename = item["filename"]
        path = raw_dir / filename

        print(f"[{position:02d}/{len(manifest):02d}] Auditando {filename}")

        try:
            result = audit_csv(path)
            audited_files.append(result)
            aggregate_nulls.update(result["null_counts"])
        except Exception as exc:
            errors.append(
                {
                    "filename": filename,
                    "error": str(exc),
                }
            )

    summary = {
        "expected_files": len(manifest),
        "audited_files": len(audited_files),
        "failed_files": len(errors),
        "total_rows": sum(
            item["row_count"] for item in audited_files
        ),
        "total_duplicate_rows": sum(
            item["duplicate_rows"] for item in audited_files
        ),
        "invalid_schema_files": sum(
            not item["schema_valid"] for item in audited_files
        ),
        "null_counts": dict(aggregate_nulls),
    }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_directory": str(raw_dir),
        "summary": summary,
        "files": audited_files,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audita os arquivos CSV brutos da ANP."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Diretório que contém os CSVs e o manifesto.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/data_quality/raw_audit.json"),
        help="Caminho do relatório JSON.",
    )
    args = parser.parse_args()

    report = audit_raw_directory(args.raw_dir)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = report["summary"]

    print("\nAuditoria concluída")
    print(f"Arquivos esperados: {summary['expected_files']}")
    print(f"Arquivos auditados: {summary['audited_files']}")
    print(f"Arquivos com erro: {summary['failed_files']}")
    print(f"Registros encontrados: {summary['total_rows']:,}")
    print(f"Duplicidades: {summary['total_duplicate_rows']:,}")
    print(
        "Esquemas inválidos:",
        summary["invalid_schema_files"],
    )
    print(f"Relatório salvo em: {args.output}")


if __name__ == "__main__":
    main()