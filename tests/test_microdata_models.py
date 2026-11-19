"""The Catalan feature table: known statuses, no leakage, real ids and provenance."""

import pytest

from dgt_stats.microdata.ml import features

TABLE = features.CATALONIA_TABLE

needs_features = pytest.mark.skipif(
    not TABLE.path.exists(), reason="run `python scripts/microdata.py features` first"
)


def test_every_catalogue_column_has_a_known_status_and_kind() -> None:
    for feature in TABLE.catalogue:
        assert feature.status in ("safe", "questionable", "direct_leakage", "excluded")
        assert feature.kind in ("numeric", "categorical", "binary")
        if feature.status in ("direct_leakage", "excluded"):
            assert not feature.sets, f"{feature.column} is in a feature set"


def test_the_feature_table_holds_no_leakage_column_or_the_target() -> None:
    leaks = {f.column for f in TABLE.catalogue if f.status == "direct_leakage"}
    columns = set(TABLE.candidate_columns())
    assert columns
    assert not columns & leaks
    assert TABLE.target not in columns and TABLE.id_column not in columns


def test_known_leakage_columns_are_classified_as_such() -> None:
    status = {f.column: f.status for f in TABLE.catalogue}
    for column in ("F_MORTS", "D_GRAVETAT", "F_VICTIMES", "F_FERITS_GREUS"):
        assert status[column] == "direct_leakage"


@needs_features
def test_feature_table_has_unique_ids_targets_and_provenance() -> None:
    from dgt_stats.microdata.common import read_provenance

    frame = features.read()
    assert frame[TABLE.id_column].is_unique
    assert set(frame[TABLE.target].unique()) <= {0, 1}
    leaks = {f.column for f in TABLE.catalogue if f.status == "direct_leakage"}
    assert not (leaks - {TABLE.target}) & set(frame.columns)
    provenance = read_provenance(TABLE.path)
    assert provenance["sources"] and provenance["id_column"] == TABLE.id_column
