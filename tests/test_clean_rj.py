from __future__ import annotations

import pandas as pd

from src.processing.clean_rj import (
    clean_chunk,
    process_raw_dataset,
)

import json
from pathlib import Path

def test_clean_chunk_filters_scope_and_converts_types() -> None:
    raw = pd.DataFrame(
        {
            "Estado - Sigla": [" RJ ", "RJ", "SP"],
            "Municipio": ["RIO DE JANEIRO", "NITEROI", "CAMPINAS"],
            "CNPJ da Revenda": [
                "12.345.678/0001-90",
                "98.765.432/0001-10",
                "11.222.333/0001-44",
            ],
            "Produto": [
                "GASOLINA",
                "ETANOL",
                "GASOLINA",
            ],
            "Data da Coleta": [
                "01/01/2024",
                "02/01/2024",
                "03/01/2024",
            ],
            "Valor de Venda": ["5,99", "4,29", "5,79"],
            "Unidade de Medida": [
                "R$ / litro",
                "R$ / litro",
                "R$ / litro",
            ],
        }
    )

    cleaned, rejected = clean_chunk(raw, source_file="sample.csv")

    assert len(cleaned) == 2
    assert rejected.empty
    assert cleaned["state"].tolist() == ["RJ", "RJ"]
    assert cleaned["product"].tolist() == ["GASOLINA", "ETANOL"]
    assert cleaned["sale_price"].tolist() == [5.99, 4.29]
    assert cleaned["source_file"].tolist() == [
        "sample.csv",
        "sample.csv",
    ]
    assert pd.api.types.is_datetime64_any_dtype(
        cleaned["collection_date"]
    )


def test_clean_chunk_rejects_invalid_business_values() -> None:
    raw = pd.DataFrame(
        {
            "Estado - Sigla": ["RJ", "RJ", "RJ"],
            "Municipio": ["RIO DE JANEIRO"] * 3,
            "CNPJ da Revenda": ["12.345.678/0001-90"] * 3,
            "Produto": ["GASOLINA", "ETANOL", "GASOLINA ADITIVADA"],
            "Data da Coleta": [
                "31/02/2024",
                "02/01/2024",
                "03/01/2024",
            ],
            "Valor de Venda": ["5,99", "-1,00", "6,49"],
            "Unidade de Medida": ["R$ / litro"] * 3,
        }
    )

    cleaned, rejected = clean_chunk(raw, source_file="sample.csv")

    assert cleaned.empty
    assert len(rejected) == 2
    assert set(rejected["rejection_reason"]) == {
        "invalid_collection_date",
        "non_positive_sale_price",
    }

def test_process_raw_dataset_creates_deduplicated_outputs(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw"
    processed_path = tmp_path / "processed" / "rj_fuel_prices.parquet"
    rejected_path = tmp_path / "rejected" / "rj_fuel_prices.parquet"
    report_path = tmp_path / "reports" / "cleaning_report.json"

    raw_dir.mkdir()

    first_file = raw_dir / "first.csv"
    second_file = raw_dir / "second.csv"

    header = (
        "Estado - Sigla;Municipio;CNPJ da Revenda;Produto;"
        "Data da Coleta;Valor de Venda;Unidade de Medida\n"
    )
    valid_row = (
        "RJ;RIO DE JANEIRO;12.345.678/0001-90;GASOLINA;"
        "01/01/2024;5,99;R$ / litro\n"
    )

    first_file.write_text(
        header
        + valid_row
        + (
            "RJ;RIO DE JANEIRO;12.345.678/0001-90;"
            "GASOLINA ADITIVADA;01/01/2024;6,49;"
            "R$ / litro\n"
        ),
        encoding="utf-8",
    )

    second_file.write_text(
        header
        + valid_row
        + (
            "RJ;NITEROI;98.765.432/0001-10;ETANOL;"
            "31/02/2024;4,29;R$ / litro\n"
        )
        + (
            "RJ;NITEROI;98.765.432/0001-10;ETANOL;"
            "02/01/2024;-1,00;R$ / litro\n"
        ),
        encoding="utf-8",
    )

    manifest = [
        {
            "filename": first_file.name,
            "source_url": "https://example.gov.br/first.csv",
        },
        {
            "filename": second_file.name,
            "source_url": "https://example.gov.br/second.csv",
        },
    ]
    (raw_dir / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    report = process_raw_dataset(
        raw_dir=raw_dir,
        processed_path=processed_path,
        rejected_path=rejected_path,
        report_path=report_path,
        chunksize=2,
    )

    processed = pd.read_parquet(processed_path)
    rejected = pd.read_parquet(rejected_path)

    assert len(processed) == 1
    assert len(rejected) == 2
    assert report["duplicate_rows_removed"] == 1
    assert report["processed_rows"] == 1
    assert report["rejected_rows"] == 2
    assert report_path.exists()