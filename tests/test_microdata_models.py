"""Feature tables and model matrices: real ids, no leakage, crashes never split across a test."""

import numpy as np
import pandas as pd
import pytest

from dgt_stats.microdata.ml import features, modelling
from dgt_stats.microdata.validation import harmonise

TABLES = features.TABLES


def _built(table) -> bool:
    return table.path.exists()


needs_features = pytest.mark.skipif(
    not all(_built(t) for t in TABLES), reason="run `python scripts/microdata.py features` first"
)


def test_every_catalogue_column_has_a_known_status_and_kind() -> None:
    for table in TABLES:
        for feature in table.catalogue:
            assert feature.status in ("safe", "questionable", "direct_leakage", "excluded")
            assert feature.kind in ("numeric", "categorical", "binary")
            if feature.status in ("direct_leakage", "excluded"):
                assert not feature.sets, f"{table.name}: {feature.column} is in a feature set"


def test_no_model_matrix_contains_a_leakage_column_or_the_target() -> None:
    for table in TABLES:
        leaks = {f.column for f in table.catalogue if f.status == "direct_leakage"}
        for feature_set in table.feature_sets:
            for geography in table.geography_variants:
                columns = set(table.columns(feature_set, geography))
                assert columns, (table.name, feature_set, geography)
                assert not columns & leaks, (table.name, feature_set, columns & leaks)
                assert table.target not in columns
                assert table.id_column not in columns
                if table.group_column:
                    assert table.group_column not in columns


def test_the_primary_sets_hold_no_questionable_feature() -> None:
    for table in TABLES:
        statuses = {f.status for f in table.features(table.primary_set, table.primary_geography)}
        assert statuses == {"safe"}, (table.name, statuses)


def test_known_leakage_columns_are_classified_as_such() -> None:
    catalonia = {f.column: f.status for f in features.CATALONIA_TABLE.catalogue}
    for column in ("F_MORTS", "D_GRAVETAT", "F_VICTIMES", "F_FERITS_GREUS"):
        assert catalonia[column] == "direct_leakage"
    person = {f.column: f.status for f in features.BARCELONA_PERSON_TABLE.catalogue}
    for column in (
        "Descripcio_victimitzacio",
        "injury_severity",
        "n_serious_injuries",
        "serious_or_fatal_crash",
    ):
        assert person[column] == "direct_leakage"


def test_crash_level_causes_are_never_person_features_in_the_primary_model() -> None:
    person = features.BARCELONA_PERSON_TABLE
    primary = set(person.columns(person.primary_set, person.primary_geography))
    assert not any(c.startswith(("mediate_", "driver_cause_")) for c in primary)


def test_cross_source_models_use_only_validated_or_exact_fields() -> None:
    for field in harmonise.DGT_FIELDS + harmonise.BCN_FIELDS:
        assert field.status in ("exact", "defensible", "approximate", "unusable")
    for table in features.common_tables():
        for feature in table.catalogue:
            name = feature.column.split("_", 1)[1]
            fields = (
                harmonise.DGT_FIELDS if feature.column.startswith("dgt_") else harmonise.BCN_FIELDS
            )
            assert next(f for f in fields if f.name == name).status in harmonise.USABLE


@needs_features
def test_feature_tables_have_unique_ids_targets_and_provenance() -> None:
    from dgt_stats.microdata.common import read_provenance

    for table in TABLES:
        frame = features.read(table.name)
        assert frame[table.id_column].is_unique
        assert set(frame[table.target].unique()) <= {0, 1}
        leaks = {f.column for f in table.catalogue if f.status == "direct_leakage"}
        assert not (leaks - {table.target}) & set(frame.columns)
        provenance = read_provenance(table.path)
        assert provenance["sources"] and provenance["id_column"] == table.id_column


@needs_features
def test_person_rows_of_one_crash_never_straddle_a_split() -> None:
    table = features.BARCELONA_PERSON_TABLE
    frame = features.read(table.name).reset_index(drop=True)
    split = modelling.make_split(frame, table)
    crash = frame[table.group_column].to_numpy()
    assert not set(crash[split.train]) & set(crash[split.test])
    for train, held in split.folds:
        assert not set(crash[train]) & set(crash[held])
    assert modelling.check_isolation(frame, table, split)["shared_groups"] == 0


@needs_features
def test_catalonia_test_year_is_later_than_every_training_year() -> None:
    table = features.CATALONIA_TABLE
    frame = features.read(table.name).reset_index(drop=True)
    split = modelling.make_split(frame, table)
    years = frame.year.to_numpy()
    assert years[split.train].max() < years[split.validation].min()
    assert years[split.validation].max() < years[split.test].min()


def test_isolation_check_detects_a_shared_crash() -> None:
    table = features.BARCELONA_PERSON_TABLE
    frame = pd.DataFrame(
        {table.id_column: ["a", "b", "c", "d"], table.group_column: ["X", "X", "Y", "Z"]}
    )
    split = modelling.Split(design="grouped", train=np.array([0, 2]), test=np.array([1, 3]))
    assert modelling.check_isolation(frame, table, split)["shared_groups"] == 1


def test_metrics_report_prevalence_and_do_not_reward_the_majority_class() -> None:
    y = np.array([0] * 99 + [1])
    p = np.zeros(100)
    out = modelling.metrics(y, p, threshold=0.5)
    assert out["prevalence"] == pytest.approx(0.01)
    assert out["balanced_accuracy"] == pytest.approx(0.5)
    assert out["recall"] == 0 and out["roc_auc"] == pytest.approx(0.5)
