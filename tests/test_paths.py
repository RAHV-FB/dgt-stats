import csv
import hashlib

import pytest

from dgt_stats.paths import (
    CENSUS_AGE_YEARS,
    CENSUS_TABLE_YEARS,
    CENSUS_YEARS,
    DATA_DIR,
    DICTIONARY_PATH,
    DRIVING_ACTIVITY_PATH,
    MANIFEST,
    MICRODATA_YEARS,
    MOVILIA_2006_PATH,
    POPULATION_PATH,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    REPORTS_DIR,
    TABLE_CHAPTER_YEARS,
    TABLE_CHAPTERS,
    TABLE_YEARS,
    census_age_raw_path,
    census_raw_path,
    census_tables_raw_path,
    microdata_raw_path,
    tables_raw_path,
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
    for year in CENSUS_AGE_YEARS:
        assert census_age_raw_path(year).is_file(), year
    for year in CENSUS_TABLE_YEARS:
        assert census_tables_raw_path(year).is_file(), year
    for path in (POPULATION_PATH, DRIVING_ACTIVITY_PATH, MOVILIA_2006_PATH):
        assert path.is_file(), path


def test_yearly_tables_exist_for_every_year() -> None:
    for year in TABLE_YEARS:
        if year in TABLE_CHAPTER_YEARS:
            for chapter in TABLE_CHAPTERS:
                assert tables_raw_path(year, chapter).is_file(), (year, chapter)
        else:
            assert tables_raw_path(year).is_file(), year


def test_chapter_years_require_a_chapter() -> None:
    with pytest.raises(ValueError):
        tables_raw_path(2016)
    assert tables_raw_path(2014, 4).suffix == ".xls"
    assert tables_raw_path(2015, 4).suffix == ".xlsx"
    assert tables_raw_path(2024, 4) == tables_raw_path(2024)
