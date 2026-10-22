"""The catalogue is the map of the project: it must agree with the files, the pipeline and the docs."""

import re
from pathlib import Path

import pytest

from dgt_stats import catalogue, pipeline
from dgt_stats.paths import PROJECT_ROOT, TABLES_DIR, table_path
from dgt_stats.sources import provenance

INVENTORY = "data_inventory"


def test_every_table_on_disk_is_catalogued_in_its_sections_folder() -> None:
    assert not list(TABLES_DIR.glob("*.csv")), "a table outside every section's folder"
    found = [(path.stem, path.parent.name) for path in TABLES_DIR.glob("*/*.csv")]
    on_disk = dict(found)
    assert len(found) == len(on_disk), "a table in two section folders"
    catalogued = {entry.name: entry.section for entry in catalogue.TABLES}
    assert on_disk == catalogued
    assert len(catalogue.TABLES) == len(catalogue.TABLE_BY_NAME)


def test_folders_are_the_sections() -> None:
    folders = {path.name for path in TABLES_DIR.iterdir() if path.is_dir()}
    assert folders == {section.key for section in catalogue.SECTIONS}


def test_a_table_the_catalogue_does_not_know_has_no_path() -> None:
    with pytest.raises(KeyError, match="not a catalogued result table"):
        table_path("no_such_table")
    assert table_path("reconciliation") == TABLES_DIR / "national" / "reconciliation.csv"


def test_every_entry_names_a_stage_and_known_sources() -> None:
    stages = {stage.key for stage in pipeline.STAGES}
    for entry in catalogue.TABLES:
        assert entry.stage in stages, entry.name
        assert set(entry.sources) <= set(catalogue.SOURCE_BY_KEY), entry.name
        assert 0 < len(entry.description) <= 100, entry.name
        assert not entry.description.endswith("."), entry.name


def test_every_raw_file_belongs_to_exactly_one_source() -> None:
    owned = provenance.files_by_source()
    for source in catalogue.SOURCES:
        if source.files:
            assert owned.get(source.key), f"{source.key} owns no file"
        else:
            assert source.key not in owned


def test_every_source_read_by_an_analysis_feeds_a_table_and_no_other_does() -> None:
    for source in catalogue.SOURCES:
        readers = [t.name for t in catalogue.tables_reading(source.key) if t.name != INVENTORY]
        if source.read:
            assert readers, f"{source.key} is read by no table"
        else:
            assert not readers, f"{source.key} is kept as a record but {readers} read it"


def test_every_site_page_belongs_to_one_section() -> None:
    from dgt_stats import site

    pages = [slug for section in catalogue.SECTIONS for slug in section.pages]
    assert len(pages) == len(set(pages))
    assert set(pages) <= set(site.PAGE_BUILDERS)
    # The home page and the tools' index belong to no single section.
    assert set(site.PAGE_BUILDERS) - set(pages) == {"index", "explore"}


def test_the_committed_catalogue_documents_are_the_ones_the_catalogue_gives() -> None:
    for path, text in provenance.outputs().items():
        assert path.read_text(encoding="utf-8") == text, (
            f"{path.relative_to(PROJECT_ROOT)} is stale: run `python scripts/run.py "
            "sources.catalogue`"
        )


LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)\s]*)?\)")


def _markdown() -> list[Path]:
    skip = {".git", ".venv", "site", "node_modules", ".pytest_cache"}
    return sorted(
        path
        for path in PROJECT_ROOT.rglob("*.md")
        if not skip & set(path.relative_to(PROJECT_ROOT).parts)
    )


def test_every_relative_link_in_the_documents_resolves() -> None:
    broken = []
    for path in _markdown():
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+:", target) or target.startswith("/"):
                continue
            if not (path.parent / target).exists():
                broken.append(f"{path.relative_to(PROJECT_ROOT)}: {target}")
    assert not broken, broken
