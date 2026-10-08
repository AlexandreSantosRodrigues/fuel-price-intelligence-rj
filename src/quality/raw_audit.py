"""Auditoria dos arquivos CSV brutos disponibilizados pela ANP."""

import csv
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_COLUMNS = (
    "Regiao - Sigla",
    "Estado - Sigla",
    "Municipio",
    "Revenda",
    "CNPJ da Revenda",
    "Nome da Rua",
    "Numero Rua",
    "Complemento",
    "Bairro",
    "Cep",
    "Produto",
    "Data da Coleta",
    "Valor de Venda",
    "Valor de Compra",
    "Unidade de Medida",
    "Bandeira",
)


def detect_encoding(raw: bytes) -> str:
    """Detecta a codificação entre os formatos conhecidos da fonte."""

    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"

    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def detect_csv_format(path: Path) -> dict[str, Any]:
    """Identifica codificação, separador e cabeçalho de um CSV."""

    raw = path.read_bytes()[:100_000]
    encoding = detect_encoding(raw)
    text = raw.decode(encoding)

    sample = "\n".join(text.splitlines()[:10])
    dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t")

    with path.open(encoding=encoding, newline="") as file:
        reader = csv.reader(file, delimiter=dialect.delimiter)
        header = next(reader)

    return {
        "encoding": encoding,
        "separator": dialect.delimiter,
        "column_count": len(header),
        "columns": header,
    }


def audit_csv(path: Path) -> dict[str, Any]:
    """Audita um CSV em streaming, sem carregar todo o arquivo na memória."""

    file_format = detect_csv_format(path)
    encoding = file_format["encoding"]
    separator = file_format["separator"]
    columns = file_format["columns"]

    missing_columns = [
        column for column in EXPECTED_COLUMNS if column not in columns
    ]
    unexpected_columns = [
        column for column in columns if column not in EXPECTED_COLUMNS
    ]

    null_counts = Counter({column: 0 for column in columns})
    observed_rows: set[str] = set()

    row_count = 0
    duplicate_rows = 0

    with path.open(encoding=encoding, newline="") as file:
        reader = csv.DictReader(file, delimiter=separator)

        for row in reader:
            row_count += 1

            values = tuple((row.get(column) or "").strip() for column in columns)

            for column, value in zip(columns, values):
                if not value:
                    null_counts[column] += 1

            row_hash = hashlib.sha256(
                "\x1f".join(values).encode("utf-8")
            ).hexdigest()

            if row_hash in observed_rows:
                duplicate_rows += 1
            else:
                observed_rows.add(row_hash)

    return {
        "filename": path.name,
        "encoding": encoding,
        "separator": separator,
        "column_count": len(columns),
        "columns": columns,
        "schema_valid": tuple(columns) == EXPECTED_COLUMNS,
        "missing_columns": missing_columns,
        "unexpected_columns": unexpected_columns,
        "row_count": row_count,
        "duplicate_rows": duplicate_rows,
        "null_counts": dict(null_counts),
    }