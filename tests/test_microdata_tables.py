"""The canonical Barcelona and Catalonia tables: keys, cardinality, semantics and cleaning rules."""

import numpy as np
import pandas as pd
import pytest

from dgt_stats.microdata import barcelona, catalonia, coordinates, sources
from dgt_stats.microdata.ml import recording

needs_barcelona = pytest.mark.skipif(
    not barcelona.PROCESSED_ACCIDENTS.exists(),
    reason="run `python scripts/microdata.py build` first",
)
needs_catalonia = pytest.mark.skipif(
    not catalonia.PROCESSED.exists(), reason="run `python scripts/microdata.py build` first"
)
KEY = barcelona.KEY


# ----------------------------------------------------------------------------- synthetic rules
def test_catalan_hours_are_hours_and_minutes() -> None:
    parsed = catalonia.parse_hour(pd.Series(["18,3", "9,05", "17", "0,45", "23,59", "25"]))
    assert parsed.hour.tolist()[:5] == [18, 9, 17, 0, 23]
    assert parsed.minute.tolist()[:5] == [30, 5, 0, 45, 59]
    assert pd.isna(parsed.hour.iloc[5])


def test_a_generic_limit_is_never_read_as_a_speed() -> None:
    raw = pd.Series(["100", "100", "50", "999", "NA", "99"])
    kind = pd.Series(
        [
            "Genérica via",
            "Senyal velocitat",
            "Senyal velocitat",
            "Genérica via",
            "Genérica via",
            "Senyal velocitat",
        ]
    )
    out = catalonia.speed_limit(raw, kind)
    assert out.speed_limit_kmh.isna().tolist() == [True, False, False, True, True, True]
    assert out.speed_limit_category.iloc[0].startswith("generic limit")
    assert out.speed_limit_category.iloc[5] == "posted, implausible value"


def test_swapped_utm_labels_are_detected_by_magnitude() -> None:
    frame = pd.DataFrame(
        {
            coordinates.X_LABEL: ["4582445.169", "429920.025"],
            coordinates.Y_LABEL: ["427206.997", "4579485.471"],
        }
    )
    out = coordinates.corrected_utm(frame, "test")
    assert out.utm_labels_swapped_in_source.tolist() == [True, False]
    assert out.utm_x_ed50.tolist() == [427206.997, 429920.025]
    assert out.utm_y_ed50.tolist() == [4582445.169, 4579485.471]


def test_projection_has_the_properties_of_utm_zone_31() -> None:
    # The central meridian of zone 31 (3 degrees east) maps to the 500 km false easting, the
    # equator to northing 0, and points either side of the meridian mirror each other.
    east, north = coordinates.utm_from_wgs84(np.array([3.0, 2.0, 4.0]), np.array([0.0, 41.4, 41.4]))
    assert east[0] == pytest.approx(500_000) and north[0] == pytest.approx(0, abs=1e-6)
    assert east[1] - 500_000 == pytest.approx(500_000 - east[2])
    assert north[1] == pytest.approx(north[2])


def test_cause_aggregation_keeps_one_row_per_crash_and_reads_blank_as_not_recorded() -> None:
    mediate = pd.DataFrame(
        {
            KEY: ["A", "B", "B", "C"],
            "Descripcio_causa_mediata": [
                "",
                "Alcoholèmia",
                "Excés de velocitat o inadequada",
                "Drogues o medicaments",
            ],
        }
    )
    out = barcelona.aggregate_mediate(mediate).set_index(KEY)
    assert len(out) == 3
    assert out.loc["A", "mediate_cause_status"] == "none_recorded"
    assert not out.loc["A", "mediate_alcohol_recorded"]
    assert out.loc["B", "n_mediate_causes"] == 2
    assert out.loc["B", "mediate_speed_recorded"] and out.loc["B", "mediate_alcohol_recorded"]
    driver = pd.DataFrame(
        {
            KEY: ["A", "B", "B", "C"],
            "Causa_conductor": ["No determinada", "Desobeir semàfor", "No determinada", ""],
        }
    )
    status = barcelona.aggregate_driver_causes(driver).set_index(KEY).driver_cause_status
    assert status.to_dict() == {"A": "not_determined", "B": "recorded", "C": "blank"}


def test_vehicle_type_presence_does_not_depend_on_repeated_rows() -> None:
    vehicles = pd.DataFrame(
        {KEY: ["A", "A", "B"], "Descripcio_tipus_vehicle": ["Motocicleta", "Turisme", "Turisme"]}
    )
    doubled = pd.concat([vehicles, vehicles.iloc[[0]]], ignore_index=True)
    once = barcelona.vehicle_type_presence(vehicles).drop(columns="vehicle_table_rows")
    twice = barcelona.vehicle_type_presence(doubled).drop(columns="vehicle_table_rows")
    pd.testing.assert_frame_equal(once, twice)


def test_an_unlisted_victimisation_category_stops_the_build() -> None:
    people = pd.DataFrame({KEY: ["A"], "Descripcio_victimitzacio": ["Ferit molt greu"]})
    with pytest.raises(ValueError, match="unlisted victimisation"):
        barcelona.build_people(people)


# ----------------------------------------------------------------------------- Barcelona
@needs_barcelona
def test_canonical_crash_ids_are_unique_and_cover_every_table() -> None:
    crashes = barcelona.read_crashes()
    assert crashes[KEY].is_unique
    ids = set(crashes[KEY])
    for role in barcelona.ROLES:
        assert set(barcelona.load(role)[KEY]) == ids, role


@needs_barcelona
def test_accident_type_is_one_to_one() -> None:
    crashes = barcelona.load("bcn_accidents")
    types = barcelona.load("bcn_accident_types")
    merged = crashes[[KEY]].merge(
        types[[KEY, "Descripcio_tipus_accident"]], on=KEY, validate="one_to_one"
    )
    assert len(merged) == len(crashes)


@needs_barcelona
def test_one_to_many_tables_reach_the_crash_table_only_after_aggregation() -> None:
    crashes = barcelona.read_crashes()
    for role, aggregate in (
        ("bcn_mediate_causes", barcelona.aggregate_mediate),
        ("bcn_driver_causes", barcelona.aggregate_driver_causes),
        ("bcn_vehicles", barcelona.vehicle_type_presence),
    ):
        raw = barcelona.load(role)
        assert raw[KEY].duplicated().any(), f"{role} has no repeated crash to test with"
        with pytest.raises(pd.errors.MergeError):
            crashes[[KEY]].merge(raw[[KEY]], on=KEY, validate="one_to_one")
        joined = crashes[[KEY]].merge(aggregate(raw), on=KEY, validate="one_to_one")
        assert len(joined) == len(crashes)


@needs_barcelona
def test_every_person_row_maps_to_a_crash_and_keeps_its_raw_victimisation() -> None:
    people = barcelona.read_people()
    crashes = barcelona.read_crashes()
    assert set(people[KEY]) <= set(crashes[KEY])
    assert people.person_record_id.is_unique
    joined = people[[KEY]].merge(crashes[[KEY]], on=KEY, validate="many_to_one")
    assert len(joined) == len(people)
    assert "Descripcio_victimitzacio" in people.columns
    excluded = people.injury_severity.isin(["not_recorded", "excluded_natural_death"])
    assert people.loc[excluded, "serious_or_fatal"].isna().all()
    assert people.loc[~excluded, "serious_or_fatal"].notna().all()


@needs_barcelona
def test_blank_counts_are_zeros_by_the_victim_identity() -> None:
    crashes = barcelona.read_crashes()
    assert (
        crashes.n_victims
        == crashes.n_deaths + crashes.n_serious_injuries + crashes.n_minor_injuries
    ).all()
    for column in ("Numero_morts", "Numero_lesionats_greus", "Numero_victimes"):
        assert not crashes[column].astype(str).str.strip().eq("0").any()


@needs_barcelona
def test_only_the_crash_file_has_exchanged_utm_labels() -> None:
    tables = {role: barcelona.load(role) for role in barcelona.ROLES}
    audit = coordinates.audit(tables, KEY, "bcn_people").set_index("table")
    assert audit.loc["bcn_accidents", "rows_x_label_holds_northing"] == len(tables["bcn_accidents"])
    others = audit.drop(index="bcn_accidents")
    assert (others.rows_x_label_holds_northing == 0).all()
    assert (audit.share_matching_reference_after_correction == 1).all()
    assert (audit.offset_spread_max_m < 1).all()


# ----------------------------------------------------------------------------- Catalonia
@needs_catalonia
def test_catalan_crashes_have_unique_surrogate_ids_and_a_consistent_label() -> None:
    crashes = catalonia.read()
    assert crashes.cat_crash_id.is_unique
    assert (crashes.fatal.eq(1) == crashes.n_deaths.gt(0)).all()
    assert crashes.n_serious_injuries.gt(0)[crashes.fatal.eq(0)].all()
    assert crashes.speed_limit_kmh[crashes.D_LIMIT_VELOCITAT.ne("Senyal velocitat")].isna().all()


@needs_catalonia
def test_the_catalan_file_is_processed_once() -> None:
    files = [f for f in sources.discover() if f.role.name == catalonia.ROLE]
    assert len(sources.resolve(catalonia.ROLE, files)) == 1


@needs_catalonia
def test_outcome_dependent_fields_stay_out_of_the_primary_model() -> None:
    from dgt_stats.microdata.ml import features

    crashes = catalonia.read()
    years = sorted(crashes.year.unique())
    training = np.flatnonzero(crashes.year <= years[-1 - 2 - 1])
    flagged = recording.outcome_dependent_fields(recording.audit(crashes, training))
    primary = set(features.CATALONIA_TABLE.columns("context", "broad"))
    assert flagged, "the recording check found nothing: review the thresholds"
    assert not flagged & primary
