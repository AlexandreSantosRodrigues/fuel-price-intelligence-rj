import hashlib
import json
from pathlib import Path

import pytest

from src.ingestion.anp import (
    discover_csv_links,
    select_links_by_year,
    sha256_file,
    update_manifest,
)


def test_discover_csv_links_resolves_relative_urls_and_removes_duplicates() -> None:
    page_url = "https://example.gov.br/data/index.html"
    html = """
    <html><body>
      <a href="files/prices-2024.csv">2024</a>
      <a href="/data/files/prices-2025.CSV">2025</a>
      <a href="files/prices-2024.csv">duplicate</a>
      <a href="metadata.pdf">metadata</a>
    </body></html>
    """

    assert discover_csv_links(page_url, html) == [
        "https://example.gov.br/data/files/prices-2025.CSV",
        "https://example.gov.br/data/files/prices-2024.csv",
    ]


def test_select_links_by_year() -> None:
    links = [
        "https://example.gov.br/prices-2023.csv",
        "https://example.gov.br/prices-2024-01.csv",
        "https://example.gov.br/prices-2026-02.csv",
        "https://example.gov.br/prices-2027.csv",
    ]

    assert select_links_by_year(links, 2024, 2026) == [
        "https://example.gov.br/prices-2024-01.csv",
        "https://example.gov.br/prices-2026-02.csv",
    ]


def test_select_links_rejects_invalid_interval() -> None:
    with pytest.raises(ValueError):
        select_links_by_year([], 2026, 2024)


def test_sha256_file(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    content = b"city,price\nRio de Janeiro,6.19\n"
    path.write_bytes(content)

    assert sha256_file(path) == hashlib.sha256(content).hexdigest()


def test_update_manifest_replaces_same_source_url(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    update_manifest(
        manifest,
        [
            {
                "filename": "old.csv",
                "source_url": "https://example.gov.br/file.csv",
                "sha256": "old",
            }
        ],
    )
    update_manifest(
        manifest,
        [
            {
                "filename": "new.csv",
                "source_url": "https://example.gov.br/file.csv",
                "sha256": "new",
            },
            {
                "filename": "second.csv",
                "source_url": "https://example.gov.br/second.csv",
                "sha256": "second",
            },
        ],
    )

    records = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(records) == 2
    assert records[0]["filename"] == "new.csv"
