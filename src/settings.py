"""Centralized project paths.

All paths are resolved from the repository root so modules can run from
notebooks, tests, GitHub Codespaces, or GitHub Actions.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REJECTED_DATA_DIR = DATA_DIR / "rejected"

MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
CONFIG_DIR = PROJECT_ROOT / "configs"


def create_project_directories() -> None:
    """Create directories used by generated data and model artifacts."""
    for directory in (
        RAW_DATA_DIR,
        INTERIM_DATA_DIR,
        PROCESSED_DATA_DIR,
        REJECTED_DATA_DIR,
        MODELS_DIR,
        FIGURES_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
