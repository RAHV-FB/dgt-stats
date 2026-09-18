from dgt_stats.paths import DATA_DIR, PROJECT_ROOT, REPORTS_DIR


def test_project_directories_exist() -> None:
    assert (PROJECT_ROOT / "README.md").is_file()
    assert DATA_DIR.is_dir()
    assert REPORTS_DIR.is_dir()
