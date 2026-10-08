"""The EMEF ingestion, harmonisation, distance model and exposure estimator.

These read the raw files under ``data/raw/emef`` (committed), so they run everywhere. They guard
against the errors the exposure analysis is most exposed to: a year missing, a respondent counted
twice, a passenger counted as a driver, the wrong weight, an age group mislabelled, people without
trips left out of a denominator, and a distance outside its band.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dgt_stats.emef import distance, exposure, ingest
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


def test_truncated_mean_stays_inside_its_band() -> None:
    rng = np.random.default_rng(1)
    mu = rng.normal(1.5, 1.5, 2000)
    sigma = rng.uniform(0.2, 1.5, 2000)
    for low, high in v.DISTANCE_BANDS.values():
        mean = distance.truncated_lognormal_mean(
            mu, sigma, np.full_like(mu, low), np.full_like(mu, high)
        )
        assert (mean >= low).all() and (mean <= high).all()


def test_distance_model_reproduces_the_report_for_driving() -> None:
    table = distance.validate_against_report().set_index("measure")
    driving = table.loc["mean straight-line km per trip: driving"]
    assert abs(driving.relative_difference) < 0.02
    for age in ("16-29", "30-64", "65+"):
        assert abs(table.loc[f"daily road km per mobile person: {age}"].relative_difference) < 0.1


def test_rates_use_every_respondent_as_denominator() -> None:
    frame = pd.DataFrame(
        {
            "year": [2024] * 4,
            "stratum": ["a"] * 4,
            "age4": ["65+"] * 4,
            "weight": [1.0, 1.0, 1.0, 1.0],
            "drove": [True, False, False, False],
            "car_trips": [2.0, 0.0, 0.0, 0.0],
            "car_km": [40.0, 0.0, 0.0, 0.0],
            "car_minutes": [60.0, 0.0, 0.0, 0.0],
        }
    )
    row = exposure.estimates(frame, ["age4"], np.ones((4, 5))).iloc[0]
    assert row.share_driving == pytest.approx(0.25)
    assert row.km_per_resident == pytest.approx(10.0)
    assert row.km_per_driver == pytest.approx(40.0)
    assert row.km_per_trip == pytest.approx(20.0)


def test_pooled_years_count_each_year_once() -> None:
    frame = pd.DataFrame(
        {
            "year": [2022, 2022, 2023, 2023],
            "stratum": ["a", "a", "b", "b"],
            "age4": ["65+"] * 4,
            "weight": [100.0, 100.0, 100.0, 100.0],
            "drove": [True, False, True, True],
            "car_trips": [1.0, 0.0, 1.0, 1.0],
            "car_km": [10.0, 0.0, 10.0, 10.0],
            "car_minutes": [10.0, 0.0, 10.0, 10.0],
        }
    )
    row = exposure.estimates(frame, ["age4"], np.ones((4, 3)), pooled=True).iloc[0]
    # 200 residents in each year: the pooled population is 200, not 400.
    assert row.residents == pytest.approx(200.0)
    assert row.share_driving == pytest.approx(0.75)


def test_bounded_road_distance_stays_between_straight_line_and_ratio() -> None:
    straight = np.array([1.0, 20.0, 150.0, 150.0])
    duration = np.array([5.0, 20.0, 60.0, np.nan])
    road = exposure.bounded_road_km(straight, duration, 1.5, 100.0)
    assert (road >= straight).all() and (road <= 1.5 * straight).all()
    # 150 km in a straight line in an hour: bounded at 100 km/h, so the straight line itself.
    assert road[2] == pytest.approx(150.0)
    assert road[3] == pytest.approx(225.0)


def test_bounded_ratio_reproduces_the_report_mean() -> None:
    ratio = exposure.bounded_road_ratio(100.0)
    assert exposure.ROAD_RATIO < ratio < 1.6


def test_band_table_shares_sum_to_one() -> None:
    table = exposure.km_by_band()
    sums = table.groupby("age4")[["share_of_trips", "share_of_km"]].sum()
    assert np.allclose(sums, 1.0)


def test_bounded_imputation_is_closest_to_the_band_based_distance() -> None:
    table = exposure.imputation_check().set_index("subset")
    pooled = table.loc["2021-2024 all"]
    assert abs(pooled.bounded_relative - 1) < 0.05
    assert abs(pooled.bounded_relative - 1) < abs(pooled.truncated_relative - 1)
    by_year = table[table.index.str.match(r"^\d{4} ")]
    assert (by_year.bounded_relative.sub(1).abs() < 0.10).all()
