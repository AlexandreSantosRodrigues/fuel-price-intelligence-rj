"""Command-line entry point for ANP raw-data ingestion."""

from __future__ import annotations

import argparse

from src.ingestion.anp import DEFAULT_SOURCE_PAGE, run_ingestion
from src.settings import RAW_DATA_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download raw ANP fuel-price CSV files with provenance metadata."
    )
    parser.add_argument("--start-year", type=int, default=2024)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--source-page", default=DEFAULT_SOURCE_PAGE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = run_ingestion(
        output_dir=RAW_DATA_DIR,
        start_year=args.start_year,
        end_year=args.end_year,
        page_url=args.source_page,
    )

    print(f"Downloaded {len(records)} raw file(s) to {RAW_DATA_DIR}")
    print(f"Manifest: {RAW_DATA_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
