"""The microdata source files: column names are normalised, values are not, and every table the
pipeline reads is a registered raw file."""

import pandas as pd
import pytest

from dgt_stats.microdata import sources

CAUSE_HEADER = "\ufeffNúmero_expedient,Nk_Any,Causa conductor\n"


def test_column_names_are_normalised_but_values_are_not(tmp_path) -> None:
    assert sources.normalise_column_name("Número_expedient") == "Numero_expedient"
    assert sources.normalise_column_name("NK_ Any") == "NK_Any"
    assert sources.normalise_column_name("Mes_ any") == "Mes_any"
    assert sources.normalise_column_name("Nk_Any") == "NK_Any"
    assert sources.normalise_column_name("Num_postal ") == "Num_postal"
    assert sources.normalise_column_name("Causa conductor") == "Causa_conductor"
    path = tmp_path / "c.csv"
    path.write_text(CAUSE_HEADER + "2025S000001,2025,Manca d'atenció\n", encoding="utf-8")
    frame = sources.read_raw(path)
    assert list(frame.columns) == ["source_row", "Numero_expedient", "NK_Any", "Causa_conductor"]
    assert frame.Causa_conductor.iloc[0] == "Manca d'atenció"


def test_every_regional_source_is_a_registered_raw_file() -> None:
    listed = {row["path"]: row for row in sources.read_manifest()}
    for source in sources.SOURCES.values():
        assert source.relative in listed, source.name
        assert source.path.exists(), source.path


def test_the_manifest_records_a_source_url_for_every_regional_file() -> None:
    listed = pd.read_csv(sources.MANIFEST, dtype=str)
    regional = listed[listed.path.str.startswith(("barcelona/", "catalonia/"))]
    assert not regional.empty
    assert regional.source_url.str.startswith("https://").all()
    assert not regional.source_url.str.contains("not recorded").any()


def test_every_regional_source_file_is_readable_and_keyed_as_declared() -> None:
    for source in sources.SOURCES.values():
        if not source.path.exists():
            pytest.skip("no regional microdata under data/raw")
        frame = sources.read_raw(source.path)
        assert len(frame) > 0
        if source.name.startswith("bcn_"):
            assert sources.BCN_ID in frame.columns, source.name
