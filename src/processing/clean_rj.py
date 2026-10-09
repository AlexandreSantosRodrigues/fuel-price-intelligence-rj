"""Cleaning rules for the Rio de Janeiro fuel-price analytical layer."""

from __future__ import annotations

import re

import pandas as pd

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

TARGET_STATE = "RJ"
TARGET_PRODUCTS = {"GASOLINA", "ETANOL"}

COLUMN_MAPPING = {
    "Regiao - Sigla": "region",
    "Estado - Sigla": "state",
    "Municipio": "municipality",
    "Revenda": "station_name",
    "CNPJ da Revenda": "station_cnpj",
    "Nome da Rua": "street",
    "Numero Rua": "street_number",
    "Complemento": "address_complement",
    "Bairro": "neighborhood",
    "Cep": "postal_code",
    "Produto": "product",
    "Data da Coleta": "collection_date",
    "Valor de Venda": "sale_price",
    "Unidade de Medida": "unit",
    "Bandeira": "brand",
}

OUTPUT_COLUMNS = [
    "region",
    "state",
    "municipality",
    "station_name",
    "station_cnpj",
    "street",
    "street_number",
    "address_complement",
    "neighborhood",
    "postal_code",
    "product",
    "collection_date",
    "sale_price",
    "unit",
    "brand",
    "source_file",
]


def normalize_text(
    series: pd.Series,
    *,
    uppercase: bool = False,
) -> pd.Series:
    """Trim text, collapse repeated spaces and preserve missing values."""
    normalized = (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .replace("", pd.NA)
    )

    if uppercase:
        normalized = normalized.str.upper()

    return normalized


def normalize_digits(series: pd.Series) -> pd.Series:
    """Keep only digits while preserving null values."""
    normalized = normalize_text(series)
    normalized = normalized.str.replace(r"\D", "", regex=True)

    return normalized.replace("", pd.NA)


def parse_sale_price(series: pd.Series) -> pd.Series:
    """Parse Brazilian decimal strings and already numeric values."""
    text = normalize_text(series)
    uses_decimal_comma = text.str.contains(",", regex=False, na=False)

    normalized = text.where(
        ~uses_decimal_comma,
        text.str.replace(".", "", regex=False).str.replace(
            ",",
            ".",
            regex=False,
        ),
    )

    return pd.to_numeric(normalized, errors="coerce")


def empty_processed_frame() -> pd.DataFrame:
    """Return an empty frame with the processed-layer columns."""
    frame = pd.DataFrame(columns=OUTPUT_COLUMNS)
    frame["collection_date"] = pd.to_datetime(
        frame["collection_date"]
    )
    frame["sale_price"] = pd.to_numeric(
        frame["sale_price"]
    )

    return frame


def clean_chunk(
    raw: pd.DataFrame,
    *,
    source_file: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean one raw chunk and return accepted and rejected rows."""
    required = {
        "Estado - Sigla",
        "Produto",
        "Data da Coleta",
        "Valor de Venda",
    }
    missing = required.difference(raw.columns)

    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(
            f"Missing required raw columns: {missing_list}"
        )

    working = raw.copy()

    working["Estado - Sigla"] = normalize_text(
        working["Estado - Sigla"],
        uppercase=True,
    )
    working["Produto"] = normalize_text(
        working["Produto"],
        uppercase=True,
    )

    scope_mask = (
        working["Estado - Sigla"].eq(TARGET_STATE)
        & working["Produto"].isin(TARGET_PRODUCTS)
    )
    working = working.loc[scope_mask].copy()

    if working.empty:
        empty = empty_processed_frame()

        return empty, empty.assign(
            rejection_reason=pd.Series(dtype="string")
        )

    working = working.rename(columns=COLUMN_MAPPING)

    for column in OUTPUT_COLUMNS:
        if column not in working.columns:
            working[column] = pd.NA

    working["source_file"] = source_file

    uppercase_columns = [
        "region",
        "state",
        "municipality",
        "product",
        "unit",
        "brand",
    ]
    text_columns = [
        "station_name",
        "street",
        "street_number",
        "address_complement",
        "neighborhood",
    ]

    for column in uppercase_columns:
        working[column] = normalize_text(
            working[column],
            uppercase=True,
        )

    for column in text_columns:
        working[column] = normalize_text(
            working[column]
        )

    working["station_cnpj"] = normalize_digits(
        working["station_cnpj"]
    )
    working["postal_code"] = normalize_digits(
        working["postal_code"]
    )

    working["collection_date"] = pd.to_datetime(
        normalize_text(working["collection_date"]),
        format="%d/%m/%Y",
        errors="coerce",
    )
    working["sale_price"] = parse_sale_price(
        working["sale_price"]
    )

    invalid_date = working["collection_date"].isna()
    invalid_price = working["sale_price"].isna()
    non_positive_price = working["sale_price"].le(0).fillna(
        False
    )

    rejected_mask = (
        invalid_date
        | invalid_price
        | non_positive_price
    )

    rejected = working.loc[
        rejected_mask,
        OUTPUT_COLUMNS,
    ].copy()

    rejected["rejection_reason"] = pd.Series(
        pd.NA,
        index=rejected.index,
        dtype="string",
    )
    rejected.loc[
        invalid_date.loc[rejected.index],
        "rejection_reason",
    ] = "invalid_collection_date"
    rejected.loc[
        invalid_price.loc[rejected.index]
        & rejected["rejection_reason"].isna(),
        "rejection_reason",
    ] = "invalid_sale_price"
    rejected.loc[
        non_positive_price.loc[rejected.index]
        & rejected["rejection_reason"].isna(),
        "rejection_reason",
    ] = "non_positive_sale_price"

    cleaned = working.loc[
        ~rejected_mask,
        OUTPUT_COLUMNS,
    ].copy()

    return (
        cleaned.reset_index(drop=True),
        rejected.reset_index(drop=True),
    )

def detect_csv_format(path: Path) -> tuple[str, str]:
    """Detect a supported text encoding and delimiter."""
    sample = path.read_bytes()[:65536]

    encoding = "latin-1"
    decoded = ""

    for candidate in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            decoded = sample.decode(candidate)
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue

    first_line = decoded.splitlines()[0]
    candidates = (";", ",", "\t", "|")
    separator = max(candidates, key=first_line.count)

    if first_line.count(separator) == 0:
        raise ValueError(
            f"Could not detect CSV separator for {path.name}"
        )

    return encoding, separator


def iter_raw_chunks(
    path: Path,
    *,
    chunksize: int,
) -> Iterator[pd.DataFrame]:
    """Read a raw CSV in memory-efficient chunks."""
    encoding, separator = detect_csv_format(path)

    yield from pd.read_csv(
        path,
        sep=separator,
        encoding=encoding,
        dtype="string",
        chunksize=chunksize,
        low_memory=False,
    )


def count_values(series: pd.Series) -> dict[str, int]:
    """Return JSON-serializable value counts."""
    counts = series.value_counts(dropna=False)

    return {
        str(key): int(value)
        for key, value in counts.items()
    }

def portable_path(path: Path) -> str:
    """Use relative project paths, with a safe absolute fallback."""
    resolved_path = path.resolve()
    project_root = Path.cwd().resolve()

    try:
        return resolved_path.relative_to(
            project_root
        ).as_posix()
    except ValueError:
        return resolved_path.as_posix()



def process_raw_dataset(
    *,
    raw_dir: Path,
    processed_path: Path,
    rejected_path: Path,
    report_path: Path,
    chunksize: int = 100_000,
) -> dict[str, object]:
    """Create the cleaned RJ analytical layer from the raw manifest."""
    if chunksize < 1:
        raise ValueError("chunksize must be at least 1")

    manifest_path = raw_dir / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Raw manifest not found: {manifest_path}"
        )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    if not isinstance(manifest, list) or not manifest:
        raise ValueError("Raw manifest must contain at least one file")

    accepted_chunks: list[pd.DataFrame] = []
    rejected_chunks: list[pd.DataFrame] = []

    raw_rows_read = 0
    rows_in_scope = 0

    for record in manifest:
        filename = str(record["filename"])
        source_path = raw_dir / filename

        if not source_path.exists():
            raise FileNotFoundError(
                f"Manifest file not found: {source_path}"
            )

        for raw_chunk in iter_raw_chunks(
            source_path,
            chunksize=chunksize,
        ):
            raw_rows_read += len(raw_chunk)

            cleaned, rejected = clean_chunk(
                raw_chunk,
                source_file=filename,
            )
            rows_in_scope += len(cleaned) + len(rejected)

            if not cleaned.empty:
                accepted_chunks.append(cleaned)

            if not rejected.empty:
                rejected_chunks.append(rejected)

    if accepted_chunks:
        processed = pd.concat(
            accepted_chunks,
            ignore_index=True,
        )
    else:
        processed = empty_processed_frame()

    if rejected_chunks:
        rejected = pd.concat(
            rejected_chunks,
            ignore_index=True,
        )
    else:
        rejected = empty_processed_frame().assign(
            rejection_reason=pd.Series(dtype="string")
        )

    accepted_before_deduplication = len(processed)

    duplicate_subset = [
        column
        for column in OUTPUT_COLUMNS
        if column != "source_file"
    ]
    duplicate_mask = processed.duplicated(
        subset=duplicate_subset,
        keep="first",
    )
    duplicate_rows_removed = int(duplicate_mask.sum())

    processed = (
        processed.loc[~duplicate_mask]
        .sort_values(
            by=[
                "collection_date",
                "municipality",
                "product",
                "station_cnpj",
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )

    processed_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    rejected_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    processed.to_parquet(
        processed_path,
        index=False,
        engine="pyarrow",
    )
    rejected.to_parquet(
        rejected_path,
        index=False,
        engine="pyarrow",
    )

    date_min = None
    date_max = None
    sale_price_min = None
    sale_price_max = None

    if not processed.empty:
        date_min = processed["collection_date"].min().date().isoformat()
        date_max = processed["collection_date"].max().date().isoformat()
        sale_price_min = float(processed["sale_price"].min())
        sale_price_max = float(processed["sale_price"].max())

    report: dict[str, object] = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "input_files": len(manifest),
        "raw_rows_read": int(raw_rows_read),
        "rows_in_scope": int(rows_in_scope),
        "rows_out_of_scope": int(
            raw_rows_read - rows_in_scope
        ),
        "accepted_rows_before_deduplication": int(
            accepted_before_deduplication
        ),
        "duplicate_rows_removed": duplicate_rows_removed,
        "processed_rows": int(len(processed)),
        "rejected_rows": int(len(rejected)),
        "date_min": date_min,
        "date_max": date_max,
        "sale_price_min": sale_price_min,
        "sale_price_max": sale_price_max,
        "products": count_values(processed["product"]),
        "municipality_count": int(
            processed["municipality"].nunique()
        ),
        "rejection_reasons": count_values(
            rejected["rejection_reason"]
        ),
       "processed_path": portable_path(processed_path),
       "rejected_path": portable_path(rejected_path),
    }

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return report