"""The EMEF ingestion and harmonisation.

These read the raw files under ``data/raw/emef`` (committed), so they run everywhere. They guard
against the errors the exposure analysis is most exposed to: a year missing, a respondent counted
twice, a passenger counted as a driver, the wrong weight, an age group mislabelled and people without
trips left out.
"""

from __future__ import annotations

import pandas as pd
import pytest

from dgt_stats.emef import ingest
from dgt_stats.emef import variables as v


@pytest.fixture(scope="module")
def people() -> pd.DataFrame:
    return ingest.persons()


@pytest.fixture(scope="module")
def trips() -> pd.DataFrame:
    return ingest.trips()


def test_every_check_passes() -> None:
    checks = ingest.validate()
    assert set(checks.year) == set(v.YEARS)
    failed = checks[~checks.passed]
    assert failed.empty, failed.to_string()


def test_every_year_is_present_with_both_files(people: pd.DataFrame, trips: pd.DataFrame) -> None:
    assert sorted(people.year.unique()) == list(v.YEARS)
    assert sorted(trips.year.unique()) == list(v.YEARS)
    for year in v.YEARS:
        assert ingest.raw_path(year, "dictionary").exists()


def test_respondents_and_trips_are_unique(people: pd.DataFrame, trips: pd.DataFrame) -> None:
    assert not people.duplicated(["year", "person_id"]).any()
    assert not trips.duplicated(["year", "person_id", "trip_order"]).any()


def test_people_without_trips_are_kept(people: pd.DataFrame) -> None:
    for year, group in people.groupby("year"):
        assert (group.n_trips == 0).sum() > 500, year
        assert not group.loc[group.n_trips == 0, "drove_car"].any()


def test_published_2024_figures_are_reproduced() -> None:
    table = ingest.reproduce_2024()
    assert (table.difference.abs() <= 0.1).all(), table.to_string()


@pytest.mark.parametrize("year", v.YEARS)
def test_car_driver_is_code_12_in_every_dictionary(year: int) -> None:
    labels = pd.read_excel(
        ingest.raw_path(year, "dictionary"), sheet_name="Valors de variable_DESP", header=None
    ).iloc[1:]
    labels[0] = labels[0].ffill()
    modes = labels[labels[0].astype(str).str.strip() == "V03G"]
    label = {int(float(k)): str(t) for k, t in zip(modes[1], modes[2]) if str(k) != "nan"}
    assert label[v.MODE_CAR_DRIVER].lower().startswith("cotxe com a conductor")
    assert label[v.MODE_CAR_PASSENGER].lower().startswith("cotxe com a acompanyant")


def test_passengers_are_not_drivers(trips: pd.DataFrame) -> None:
    passenger_only = trips.car_passenger & ~trips.car_driver
    assert passenger_only.sum() > 10_000
    stages = trips.loc[passenger_only, ["mode1", "mode2", "mode3"]]
    assert not stages.eq(v.MODE_CAR_DRIVER).any(axis=None)


def test_age_groups_are_harmonised_without_splitting(people: pd.DataFrame) -> None:
    early = people[people.year < v.AGE4_FROM]
    late = people[people.year >= v.AGE4_FROM]
    assert set(early.age3) == {"16-29", "30-64", "65+"}
    assert early.age4.isna().all()
    assert set(late.age4) == {"16-29", "30-44", "45-64", "65+"}
    collapsed = late.age4.replace({"30-44": "30-64", "45-64": "30-64"})
    assert (collapsed == late.age3).all()
    # Nothing finer than 65 and over exists in any public file.
    assert not any("75" in str(label) for label in people.age_group.unique())


def test_2024_renamed_respondent_columns_match_the_trip_file() -> None:
    raw_people = ingest.read_raw(2024, "persons").set_index("ID")
    raw_trips = ingest.read_raw(2024, "trips").drop_duplicates("ID").set_index("ID")
    common = raw_trips.index
    assert (raw_people.loc[common, "S02"] == raw_trips["S02_R3"]).all()
    assert (raw_people.loc[common, "COMARCA"] == raw_trips["COMARCA"]).all()
    assert (raw_people.loc[common, "V01A"] == raw_trips["V01D1"]).all()


def test_weights_are_respondent_expansion_factors(people: pd.DataFrame) -> None:
    totals = people.groupby("year").weight.sum()
    for year, (population, _) in v.UNIVERSE.items():
        assert abs(totals[year] - population) < 1
