"""Discovery and traceable download of raw ANP fuel-price files."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_SOURCE_PAGE = (
    "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
    "serie-historica-de-precos-de-combustiveis"
)
USER_AGENT = "fuel-price-intelligence-rj/1.0 (educational data project)"
TARGET_FUEL_TERMS = ("gasolina", "etanol")


def discover_csv_links(page_url: str, html: str) -> list[str]:
    """Return unique absolute CSV links found in an HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        absolute_url = urljoin(page_url, href)
        path = unquote(urlparse(absolute_url).path).lower()

        if path.endswith(".csv"):
            links.add(absolute_url)

    return sorted(links)


def select_links_by_year(
    links: Iterable[str],
    start_year: int,
    end_year: int,
    required_terms: Iterable[str] = (),
) -> list[str]:
    """Keep URLs from the requested years that contain a target term."""
    if start_year > end_year:
        raise ValueError("start_year cannot be greater than end_year")

    years = {str(year) for year in range(start_year, end_year + 1)}
    terms = tuple(term.casefold() for term in required_terms)

    selected = []

    for link in links:
        normalized = unquote(link).casefold()
        matches_year = any(year in normalized for year in years)
        matches_term = not terms or any(term in normalized for term in terms)

        if matches_year and matches_term:
            selected.append(link)

    return sorted(selected)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate a file SHA-256 without loading the whole file into memory."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(chunk_size), b""):
            digest.update(chunk)

    return digest.hexdigest()


def fetch_source_page(
    page_url: str = DEFAULT_SOURCE_PAGE,
    timeout: int = 30,
) -> str:
    """Fetch the official source page and return its HTML."""
    response = requests.get(
        page_url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()

    return response.text


def build_destination_filename(url: str) -> str:
    """Build a unique filename while preserving the source year."""
    decoded_path = unquote(urlparse(url).path)
    filename = Path(decoded_path).name

    if not filename:
        raise ValueError(f"Could not derive a filename from URL: {url}")

    years = re.findall(r"(?<!\d)(20\d{2})(?!\d)", decoded_path)

    if not years:
        return filename

    year = years[0]

    if re.search(rf"(?<!\d){year}(?!\d)", filename):
        return filename

    return f"{year}-{filename}"


def download_file(
    url: str,
    destination_dir: Path,
    timeout: int = 120,
    max_attempts: int = 4,
) -> dict[str, object]:
    """Download one file or reuse an existing local copy."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    destination_dir.mkdir(parents=True, exist_ok=True)

    filename = build_destination_filename(url)
    destination = destination_dir / filename

    if destination.exists():
        file_stats = destination.stat()

        return {
            "filename": filename,
            "source_url": url,
            "downloaded_at_utc": datetime.fromtimestamp(
                file_stats.st_mtime,
                tz=timezone.utc,
            ).isoformat(),
            "size_bytes": file_stats.st_size,
            "sha256": sha256_file(destination),
            "reused_existing": True,
        }

    temporary = destination.with_suffix(destination.suffix + ".part")

    for attempt in range(1, max_attempts + 1):
        try:
            if temporary.exists():
                temporary.unlink()

            with requests.get(
                url,
                stream=True,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
            ) as response:
                response.raise_for_status()

                with temporary.open("wb") as file:
                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024,
                    ):
                        if chunk:
                            file.write(chunk)

            temporary.replace(destination)
            break

        except requests.RequestException:
            if temporary.exists():
                temporary.unlink()

            if attempt == max_attempts:
                raise

            wait_seconds = 2**attempt
            print(
                f"Download interrupted for {filename}. "
                f"Retry {attempt + 1}/{max_attempts} "
                f"in {wait_seconds}s..."
            )
            time.sleep(wait_seconds)

    return {
        "filename": filename,
        "source_url": url,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "size_bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "reused_existing": False,
    }


def update_manifest(
    manifest_path: Path,
    records: Iterable[dict[str, object]],
    replace_existing: bool = False,
) -> None:
    """Write provenance records, optionally replacing an earlier run."""
    existing: list[dict[str, object]] = []

    if manifest_path.exists() and not replace_existing:
        existing = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )

    indexed = {
        str(record["source_url"]): record
        for record in existing
    }

    for record in records:
        indexed[str(record["source_url"])] = record

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            sorted(
                indexed.values(),
                key=lambda item: str(item["source_url"]),
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def run_ingestion(
    output_dir: Path,
    start_year: int = 2024,
    end_year: int = 2026,
    page_url: str = DEFAULT_SOURCE_PAGE,
) -> list[dict[str, object]]:
    """Download monthly gasoline and ethanol CSVs and update the manifest."""
    html = fetch_source_page(page_url)
    discovered = discover_csv_links(page_url, html)
    selected = select_links_by_year(
        discovered,
        start_year,
        end_year,
        required_terms=TARGET_FUEL_TERMS,
    )

    if not selected:
        raise RuntimeError(
            "No monthly gasoline/ethanol CSV links matched the "
            "requested years. The ANP page structure may have changed."
        )

    print(
        f"Found {len(selected)} monthly gasoline/ethanol file(s)."
    )

    records = [
        download_file(url, output_dir)
        for url in selected
    ]

    update_manifest(
        output_dir / "manifest.json",
        records,
        replace_existing=False,
    )

    return records