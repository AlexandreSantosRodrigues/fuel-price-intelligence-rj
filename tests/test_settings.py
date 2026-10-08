from src.settings import DATA_DIR, PROJECT_ROOT


def test_data_directory_is_inside_project_root() -> None:
    assert DATA_DIR.parent == PROJECT_ROOT


def test_project_root_contains_readme() -> None:
    assert (PROJECT_ROOT / "README.md").exists()
