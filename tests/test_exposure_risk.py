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
from dgt_stats.exposure_risk import barcelona, calendar, coverage, national


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
        national.COVERAGE_SOURCE,
        national.COVERAGE_PROFILE_SOURCE,
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


def test_spanish_calendar_and_non_working_shares() -> None:
    # 2024: 262 weekdays less the fourteen public holidays the law allows; 366 days.
    assert national.working_days(2024) == (248, 118)
    low, high = national.NON_WORKING_SHARES
    assert high == pytest.approx(118 / 366)
    assert low == pytest.approx(118 * 0.6 / (248 + 118 * 0.6))


def test_coverage_components_add_up_to_dgt_total() -> None:
    parts = coverage.components().set_index("component")
    total = national.dgt_car_km()["less taxi and ride-hailing"]
    additive = parts[parts.additive]
    for setting in ("least_explained", "most_explained"):
        assert additive[f"bn_km_{setting}"].sum() * 1e9 == pytest.approx(total)
        assert additive[f"share_{setting}"].sum() == pytest.approx(1.0)
    # The working days are Method A's km per working day times the working days of the year.
    km, _ = national.national_km(national.emef_profile())
    working, _ = national.working_days()
    assert parts.loc["working days", "bn_km_least_explained"] * 1e9 == pytest.approx(
        km.sum() * working
    )
    # The setting that explains least leaves the largest remainder, and each measured part is
    # larger at the setting that explains most (the months outside the fieldwork may be negative).
    remainder = parts.loc["remainder (not explained)"]
    assert remainder.bn_km_least_explained > remainder.bn_km_most_explained
    for name in ("professionals' work driving", "regional level", "non-working days"):
        assert (
            0 < parts.loc[name, "bn_km_least_explained"] < parts.loc[name, "bn_km_most_explained"]
        )
    # Company cars and hire cars overlap the parts and are not added.
    assert not parts.loc[["cars registered to companies", "car hire without driver"]].additive.any()
    low, high = coverage.regional_factors()
    assert 1 < low < high
    low, high = coverage.seasonal_factors()
    assert low < 1 < high


def test_scenario_weights_match_the_components() -> None:
    weights = coverage.scenario_weights()
    parts = coverage.components().set_index("component")
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["remainder"] == pytest.approx(
        parts.loc["remainder (not explained)", "share_least_explained"]
    )
    # Covered, professional and non-working parts carry the regional level and the season.
    measured = parts.loc[
        [
            "working days",
            "professionals' work driving",
            "regional level",
            "non-working days",
            "months outside the fieldwork",
        ],
        "share_least_explained",
    ].sum()
    assert weights["covered"] + weights["professional"] + weights["non_working"] == pytest.approx(
        measured
    )


def test_coverage_mixes_and_scenarios() -> None:
    km, _ = national.national_km(national.emef_profile())
    base = km / km.sum()
    same, older = coverage.mix_shares(coverage.WORKING_DAY_MIX, base)
    assert np.allclose(same, base) and older is None
    # A weekend mix is the same weights on the covered part as in the weekend sensitivity.
    weekend = national.weekend_sensitivity()
    movilia = weekend[weekend.non_working_age_mix == national.MOVILIA_WEEKEND]
    weights = movilia.drop_duplicates("group").set_index("group").weekend_weight
    shares, _ = coverage.mix_shares(national.MOVILIA_WEEKEND, base)
    expected = weights.reindex(base.index) * base
    assert np.allclose(shares, expected / expected.sum())
    # The under-65 bound gives no km at 65 and over; every mix's shares add up to one.
    under, _ = coverage.mix_shares(coverage.UNDER_65_MIX, base)
    assert under["65+"] == 0
    mixes = coverage.mixes()
    assert np.allclose(mixes.groupby("mix").share_of_km.sum(), 1.0)
    assert set(mixes[~mixes.credible].mix) == set(coverage.BOUNDS)
    # With every part at the working-day mix, a scenario differs from the central estimate only
    # through professionals' work driving.
    scenario = next(
        s
        for s in coverage.scenario_km()
        if s["profile"] == national.CENTRAL_METHOD
        and s["non_working_mix"] == s["remainder_mix"] == coverage.WORKING_DAY_MIX
    )
    _, professional = coverage._daily_km()
    w = coverage.scenario_weights()["professional"]
    expected = (1 - w) * base + w * professional / professional.sum()
    assert np.allclose(scenario["shares"], expected)
    for s in coverage.scenario_km():
        assert s["shares"].sum() == pytest.approx(1.0)
        assert all(0 < q < 1 for q in s["share_75_plus_of_65_plus"].values())


def test_sensitivity_carries_credible_coverage_scenarios_only() -> None:
    table = national.sensitivity()
    assert {national.COVERAGE_SOURCE, national.COVERAGE_PROFILE_SOURCE} <= set(table.source)
    assert not table.variant.str.contains("(bound)", regex=False).any()
    older = national.older_sensitivity()
    assert {national.COVERAGE_SOURCE, national.COVERAGE_PROFILE_SOURCE} <= set(older.source)
    assert not older.variant.str.contains("(bound)", regex=False).any()
    # The scenarios table holds the bounds too, flagged as not credible, and the published range
    # is the span of the credible ones and the other alternatives.
    scenarios = coverage.scenarios()
    assert set(scenarios[~scenarios.credible].remainder_mix) == set(coverage.BOUNDS)
    credible = scenarios[scenarios.credible]
    assert older.ratio_75_plus.min() <= credible.ratio_75_plus.min() + 1e-9
    groups = table.groupby("group").involved_ratio
    assert groups.min()["65+"] <= credible.ratio_65_plus.min() + 1e-9
    assert groups.max()["16-29"] >= credible.ratio_18_29.max() - 1e-9


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
