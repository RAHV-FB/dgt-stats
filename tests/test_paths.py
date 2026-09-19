import csv
import hashlib

import pytest

from dgt_stats.paths import (
    CENSUS_YEARS,
    DATA_DIR,
    DICTIONARY_PATH,
    MANIFEST,
    MICRODATA_YEARS,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    REPORTS_DIR,
    census_raw_path,
    microdata_raw_path,
)


def _manifest_rows() -> list[dict[str, str]]:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_project_directories_exist() -> None:
    assert (PROJECT_ROOT / "README.md").is_file()
    assert DATA_DIR.is_dir()
    assert REPORTS_DIR.is_dir()


def test_manifest_lists_every_raw_file() -> None:
    listed = {row["path"] for row in _manifest_rows()}
    on_disk = {
        str(path.relative_to(RAW_DATA_DIR))
        for path in RAW_DATA_DIR.rglob("*")
        if path.is_file() and path.name != "manifest.csv"
    }
    assert listed == on_disk


def test_manifest_sizes_match() -> None:
    for row in _manifest_rows():
        path = RAW_DATA_DIR / row["path"]
        assert path.stat().st_size == int(row["bytes"]), row["path"]


@pytest.mark.slow
def test_manifest_checksums_match() -> None:
    for row in _manifest_rows():
        digest = hashlib.sha256((RAW_DATA_DIR / row["path"]).read_bytes()).hexdigest()
        assert digest == row["sha256"], row["path"]


def test_expected_source_files_exist() -> None:
    assert DICTIONARY_PATH.is_file()
    for year in MICRODATA_YEARS:
        assert microdata_raw_path(year).is_file(), year
    for year in CENSUS_YEARS:
        assert census_raw_path(year).is_file(), year
