"""Command-line entry point for the RJ fuel-price cleaning pipeline."""

from __future__ import annotations

import json

from src.processing.clean_rj import process_raw_dataset
from src.settings import (
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    REJECTED_DATA_DIR,
    REPORTS_DIR,
)


def main() -> None:
    """Run the raw-to-processed cleaning pipeline."""
    processed_path = (
        PROCESSED_DATA_DIR / "rj_fuel_prices.parquet"
    )
    rejected_path = (
        REJECTED_DATA_DIR
        / "rj_fuel_prices_rejected.parquet"
    )
    report_path = (
        REPORTS_DIR
        / "data_quality"
        / "cleaning_report.json"
    )

    report = process_raw_dataset(
        raw_dir=RAW_DATA_DIR,
        processed_path=processed_path,
        rejected_path=rejected_path,
        report_path=report_path,
    )

    print("RJ fuel-price cleaning completed.")
    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()