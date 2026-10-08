"""Auditoria dos arquivos CSV brutos disponibilizados pela ANP."""

import csv
import hashlib
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
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


def parse_br_date(value: str):
    """Converte uma data brasileira para um objeto date."""

    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


def parse_br_decimal(value: str):
    """Converte um número com vírgula decimal para Decimal."""

    if not value:
        return None

    normalized = value.strip()

    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


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
    """Audita um CSV em streaming, sem carregá-lo inteiro na memória."""

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
    states: Counter[str] = Counter()
    products: Counter[str] = Counter()
    units: Counter[str] = Counter()
    observed_rows: set[str] = set()

    row_count = 0
    duplicate_rows = 0

    invalid_date_rows = 0
    date_min = None
    date_max = None

    invalid_sale_price_rows = 0
    non_positive_sale_price_rows = 0
    sale_price_min = None
    sale_price_max = None

    with path.open(encoding=encoding, newline="") as file:
        reader = csv.DictReader(file, delimiter=separator)

        for row in reader:
            row_count += 1

            values = tuple(
                (row.get(column) or "").strip()
                for column in columns
            )

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

            state = (row.get("Estado - Sigla") or "").strip()
            product = (row.get("Produto") or "").strip()
            unit = (row.get("Unidade de Medida") or "").strip()

            if state:
                states[state] += 1
            if product:
                products[product] += 1
            if unit:
                units[unit] += 1

            raw_date = (row.get("Data da Coleta") or "").strip()
            parsed_date = parse_br_date(raw_date)

            if raw_date and parsed_date is None:
                invalid_date_rows += 1
            elif parsed_date is not None:
                date_min = (
                    parsed_date
                    if date_min is None
                    else min(date_min, parsed_date)
                )
                date_max = (
                    parsed_date
                    if date_max is None
                    else max(date_max, parsed_date)
                )

            raw_price = (row.get("Valor de Venda") or "").strip()
            parsed_price = parse_br_decimal(raw_price)

            if raw_price and parsed_price is None:
                invalid_sale_price_rows += 1
            elif parsed_price is not None:
                if parsed_price <= 0:
                    non_positive_sale_price_rows += 1

                sale_price_min = (
                    parsed_price
                    if sale_price_min is None
                    else min(sale_price_min, parsed_price)
                )
                sale_price_max = (
                    parsed_price
                    if sale_price_max is None
                    else max(sale_price_max, parsed_price)
                )

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
        "date_min": date_min.isoformat() if date_min else None,
        "date_max": date_max.isoformat() if date_max else None,
        "invalid_date_rows": invalid_date_rows,
        "sale_price_min": float(sale_price_min) if sale_price_min is not None else None,
        "sale_price_max": float(sale_price_max) if sale_price_max is not None else None,
        "invalid_sale_price_rows": invalid_sale_price_rows,
        "non_positive_sale_price_rows": non_positive_sale_price_rows,
        "states": dict(states),
        "products": dict(products),
        "units": dict(units),
    }