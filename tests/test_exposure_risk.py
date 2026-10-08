"""Crash involvement per kilometre by driver age: calendar, numerators, exposure and rates.

These guard the errors the per-kilometre comparison is most exposed to: counting a holiday as a
working day, a numerator and a denominator that cover different drivers, an age group whose
population is double counted, shares that do not add up, a 65-74/75+ split that changes the
measured 65-and-over total, and a ratio that does not follow from its rates.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from dgt_stats import edm2018, io_tables
from dgt_stats.exposure_risk import barcelona, calendar, national


def test_barcelona_2025_calendar() -> None:
    assert calendar.days_in_year(2025) == {
        "working day": 248,
        "Saturday": 50,
        "Sunday or holiday": 67,
    }
    days = pd.Series(pd.to_datetime(["2025-09-24", "2025-06-09", "2025-09-17", "2025-11-01"]))
    assert calendar.day_type(days).tolist() == [
        "Sunday or holiday",
        "Sunday or holiday",
        "working day",
        "Sunday or holiday",
    ]
    assert all(day.year == 2025 for day in calendar.HOLIDAYS_BARCELONA_2025)
    assert dt.date(2025, 10, 12) not in calendar.HOLIDAYS_BARCELONA_2025  # a Sunday in 2025


def test_single_age_population_has_no_overlapping_aggregates() -> None:
    people = national.single_age_population()
    assert not people.duplicated(["age", "sex"]).any()
    assert 48.5e6 < people.population.sum() < 49.5e6
    groups = national.population_by_group().set_index(["sex", "group"]).population
    for sex in national.SEXES:
        assert groups[(sex, "65+")] == pytest.approx(groups[(sex, "65-74")] + groups[(sex, "75+")])


def test_numerator_covers_every_private_car_driver_once() -> None:
    counts = national.drivers_involved().set_index("group")
    table = io_tables.read_table("tables_drivers_involved")
    cars = table[(table.year == national.YEAR) & table.vehicle_type.isin(national.PRIVATE_CARS)]
    under_15 = cars[cars.band == "0-14"].value.sum()
    covered = counts.loc[[*national.GROUPS, "15-17", "unknown"], "involved"].sum()
    assert covered + under_15 == pytest.approx(cars.value.sum())
    assert (
        counts.loc["65+", "involved"]
        == counts.loc["65-74", "involved"] + counts.loc["75+", "involved"]
    )


def test_shares_add_up_and_rates_follow_from_them() -> None:
    shares = national.shares()
    by_method = shares.groupby("method").share_of_km.sum()
    assert np.allclose(by_method, 1.0)
    rates = national.rates()
    for _, method in rates.groupby("method"):
        method = method.set_index("group")
        assert method.loc[national.REFERENCE, "involved_ratio"] == pytest.approx(1.0)
        assert np.allclose(method.involved_per_bn_km * method.billion_km, method.involved)
        reference = method.loc[national.REFERENCE]
        expected = (method.involved / reference.involved) / (
            method.share_of_km / reference.share_of_km
        )
        assert np.allclose(method.involved_ratio, expected)
        assert (method.involved_ratio_low <= method.involved_ratio + 1e-9).all()
        assert (method.involved_ratio_high >= method.involved_ratio - 1e-9).all()


def test_older_split_keeps_the_measured_65_plus_kilometres() -> None:
    split = national.older_split()
    rates = national.rates().query("method.str.startswith('A:') and group == '65+'").iloc[0]
    for _, part in split.groupby("assumption"):
        assert part.billion_km.sum() == pytest.approx(rates.billion_km)
        assert part.share_of_65_plus_km.sum() == pytest.approx(1.0)


def test_uniform_weekend_mix_reproduces_the_central_ratios() -> None:
    weekend = national.weekend_sensitivity()
    uniform = weekend[weekend.non_working_age_mix.str.startswith("same")]
    central = national.rates().query("method.str.startswith('A:')").set_index("group")
    for _, row in uniform.iterrows():
        assert row.ratio_to_45_64 == pytest.approx(central.loc[row.group, "involved_ratio"])


def test_barcelona_numerator_and_denominators() -> None:
    drivers = barcelona.involved_drivers()
    assert set(drivers.day_type) <= set(calendar.DAY_TYPES)
    days = barcelona.counts_by_day_type()
    cars = drivers[drivers.vehicle == "car"]
    assert days.query(
        "age in ['16-29', '30-44', '45-64', '65+', 'not recorded']"
    ).drivers.sum() == (len(cars) - int(((cars.age < 16) & cars.age.notna()).sum()))
    # Ride-hailing cars (trip motive "Taxi" on an ordinary car) count as taxis, as nationally.
    assert not cars[barcelona.MOTIVE].eq(barcelona.TAXI).any()
    rates = barcelona.rates()
    central = rates[rates.numerator == barcelona.NUMERATORS[0]]
    km = central.pivot(index="age4", columns="denominator", values="billion_km")
    assert (km[barcelona.DENOMINATORS[0]] < km[barcelona.DENOMINATORS[1]]).all()
    assert (km[barcelona.DENOMINATORS[1]] < km[barcelona.DENOMINATORS[2]]).all()
    reference = rates[rates.age4 == barcelona.REFERENCE]
    assert np.allclose(reference.ratio_to_45_64, 1.0)
    # Each further exclusion removes drivers and never adds any.
    counts = rates.groupby("numerator", sort=False).drivers_involved.sum()
    assert counts.is_monotonic_decreasing


def test_sensitivity_holds_the_central_estimate_and_every_source() -> None:
    table = national.sensitivity()
    central = table[table.source == "central"].set_index("group").involved_ratio
    rates = national.rates().query("method.str.startswith('A:')").set_index("group")
    assert np.allclose(central, rates.involved_ratio.reindex(central.index))
    assert {
        "regional profile",
        "licence-calibrated transfer",
        "distance",
        "survey years",
        "professionals' work driving",
        "older sample",
        "non-working days",
    } <= set(table.source)
    assert np.allclose(table[table.group == national.REFERENCE].involved_ratio, 1.0)
    # Professionals' work driving adds kilometres mostly at working ages, so it raises 65+.
    professional = table[(table.source == "professionals' work driving") & (table.group == "65+")]
    assert (professional.involved_ratio > central["65+"]).all()


def test_licence_calibration_scales_by_prevalence_only() -> None:
    profile = national.emef_profile()
    calibrated = national.licence_calibrated(profile)
    spain = national.licence_prevalence().set_index(["sex", "group"]).prevalence
    province = national.licence_prevalence("08").set_index(["sex", "group"]).prevalence
    for key, (point, _) in profile.items():
        assert calibrated[key][0] == pytest.approx(point * spain[key] / province[key])


def test_older_ranges_cover_the_central_split() -> None:
    split = national.older_split().set_index(["assumption", "group"]).ratio_to_45_64
    ranges = national.older_sensitivity()
    assert ranges.ratio_75_plus.min() <= split.xs("75+", level="group").min() + 1e-9
    assert ranges.ratio_75_plus.max() >= split.xs("75+", level="group").max() - 1e-9
    assert "registered owners' split of the 65+ km" not in set(ranges.assumption)


def test_madrid_survey_reading() -> None:
    people = edm2018.person_day()
    # No car-driver day is longer than the distance limit allows trip by trip.
    trips = pd.read_csv(edm2018.EDM_DIR / "edm2018_viajes_conductor.csv")
    longest = trips.groupby(["ID_HOGAR", "ID_IND"]).size().max()
    assert people.car_km.max() <= longest * edm2018.DISTANCE_LIMIT_KM
    assert len(people) == 74_945
    assert (people.weight > 0).all()
    assert people.EDAD_FIN.min() >= 16
    split = edm2018.older_split().set_index("sex")
    for column in ("share_of_residents_75_plus", "share_of_km_75_plus"):
        assert ((split[column] > 0) & (split[column] < 1)).all()
    assert (split.ratio_low <= split.ratio_75_plus_to_65_74).all()
