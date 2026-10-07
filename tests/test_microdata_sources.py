"""The microdata source registry: files found by their columns, copies processed once."""

import datetime as dt

import pandas as pd
import pytest

from dgt_stats.microdata import sources

CRASH_HEADER = (
    "﻿Numero_expedient,NK_Any,Numero_morts,Numero_lesionats_lleus,Numero_lesionats_greus,"
    "Numero_victimes,Numero_vehicles_implicats\n"
)
CAUSE_HEADER = "﻿Número_expedient,Nk_Any,Causa conductor\n"


def _write(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "".join(rows), encoding="utf-8")
    return path


def test_column_names_are_normalised_but_values_are_not(tmp_path) -> None:
    assert sources.normalise_column_name("Número_expedient") == "Numero_expedient"
    assert sources.normalise_column_name("NK_ Any") == "NK_Any"
    assert sources.normalise_column_name("Mes_ any") == "Mes_any"
    assert sources.normalise_column_name("Nk_Any") == "NK_Any"
    assert sources.normalise_column_name("Num_postal ") == "Num_postal"
    assert sources.normalise_column_name("Causa conductor") == "Causa_conductor"
    path = _write(tmp_path / "c.csv", CAUSE_HEADER, ["2025S000001,2025,Manca d'atenció\n"])
    frame = sources.read_raw(path)
    assert list(frame.columns) == ["source_row", "Numero_expedient", "NK_Any", "Causa_conductor"]
    assert frame.Causa_conductor.iloc[0] == "Manca d'atenció"


def test_files_are_identified_by_columns_not_names(tmp_path) -> None:
    crash = _write(tmp_path / "download(7).csv", CRASH_HEADER, ["2025S1,2025,,1,,1,2\n"])
    cause = _write(tmp_path / "export.csv", CAUSE_HEADER, ["2025S1,2025,Altres\n"])
    assert sources.identify(sources.header(crash)).name == "bcn_accidents"
    assert sources.identify(sources.header(cause)).name == "bcn_driver_causes"
    assert sources.identify(["a", "b"]) is None


def test_a_byte_identical_copy_is_processed_once(tmp_path) -> None:
    rows = ["2025S1,2025,,1,,1,2\n", "2025S2,2025,1,,,1,1\n"]
    _write(tmp_path / "bcn" / "a.csv", CRASH_HEADER, rows)
    _write(tmp_path / "bcn" / "b.csv", CRASH_HEADER, rows)
    found = sources.discover(roots=(tmp_path / "bcn",))
    assert len(found) == 2
    assert sum(item.duplicate_of is not None for item in found) == 1
    assert len(sources.resolve("bcn_accidents", found)) == 1


def test_same_rows_in_another_order_count_as_a_copy(tmp_path) -> None:
    _write(
        tmp_path / "bcn" / "a.csv", CRASH_HEADER, ["2025S1,2025,,1,,1,2\n", "2025S2,2025,1,,,1,1\n"]
    )
    _write(
        tmp_path / "bcn" / "b.csv", CRASH_HEADER, ["2025S2,2025,1,,,1,1\n", "2025S1,2025,,1,,1,2\n"]
    )
    found = sources.discover(roots=(tmp_path / "bcn",))
    assert all(item.duplicate_of is None for item in found)
    chosen = sources.resolve("bcn_accidents", found)
    assert len(chosen) == 1


def test_two_different_files_for_one_role_and_year_stop_the_pipeline(tmp_path) -> None:
    _write(tmp_path / "bcn" / "a.csv", CRASH_HEADER, ["2025S1,2025,,1,,1,2\n"])
    _write(tmp_path / "bcn" / "b.csv", CRASH_HEADER, ["2025S1,2025,1,,,1,2\n"])
    found = sources.discover(roots=(tmp_path / "bcn",))
    with pytest.raises(sources.SourceConflict):
        sources.resolve("bcn_accidents", found)


def test_organise_files_a_new_download_and_leaves_a_duplicate_in_place(tmp_path) -> None:
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    manifest = raw / "manifest.csv"
    sources.write_manifest([], manifest)
    rows = ["2025S1,2025,,1,,1,2\n"]
    new = _write(tmp_path / "data" / "download.csv", CRASH_HEADER, rows)
    result = sources.organise(raw_dir=raw, manifest=manifest, today=dt.date(2026, 1, 1))
    target = raw / "barcelona" / "2025" / "accidents_gu_bcn_2025.csv"
    assert result.moved == [(new, target)] and target.exists()
    listed = pd.read_csv(manifest, dtype=str)
    assert listed.downloaded_as.tolist() == ["download.csv"]
    copy = _write(tmp_path / "data" / "download(1).csv", CRASH_HEADER, rows)
    again = sources.organise(raw_dir=raw, manifest=manifest, today=dt.date(2026, 1, 1))
    assert again.duplicates == [(copy, "barcelona/2025/accidents_gu_bcn_2025.csv")]
    assert copy.exists() and len(pd.read_csv(manifest)) == 1


def test_every_registered_raw_microdata_file_is_readable_and_recognised() -> None:
    found = sources.discover()
    if not found:
        pytest.skip("no regional microdata under data/raw")
    roles = {item.role.name for item in found if item.duplicate_of is None}
    assert roles == {role.name for role in sources.ROLES}
    for item in found:
        assert len(sources.read_raw(item.path)) > 0
