"""Crash involvement per kilometre by driver age: calendar, numerators, exposure, rates and ranges.

These guard the errors the per-kilometre comparison is most exposed to: counting a holiday as a
working day, a numerator and a denominator that cover different drivers, an age group whose
population is double counted, shares that do not add up, a 65-74/75+ split that changes the
measured 65-and-over total, a ratio that does not follow from its rates, and a range that does
not contain the estimate it surrounds. They need the DGT table layer
(``python scripts/ingest.py``); without it the module is skipped.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from dgt_stats import edm2018, io_tables
from dgt_stats.exposure_risk import barcelona, calendar, coverage, national, ranges
from dgt_stats.paths import STAGING_DATA_DIR

pytestmark = pytest.mark.skipif(
    not (STAGING_DATA_DIR / "dgt").exists(),
    reason="run `python scripts/ingest.py` first: the DGT table layer is missing",
)


@pytest.fixture(scope="module")
def older_split_table() -> pd.DataFrame:
    return national.older_split()


@pytest.fixture(scope="module")
def rates_table() -> pd.DataFrame:
    return national.rates()


@pytest.fixture(scope="module")
def ranges_table(rates_table, older_split_table) -> pd.DataFrame:
    return ranges.ranges(rates_table, older_split_table, national.sex_per_km())


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


def test_older_split_keeps_the_measured_65_plus_kilometres(older_split_table) -> None:
    split = older_split_table
    assert set(split.profile) == {national.CENTRAL_METHOD, national.BARCELONA_METHOD}
    rates = national.rates()
    for profile, table in split.groupby("profile"):
        assert set(table.assumption) == set(national.SPLITS)
        over_65 = rates[(rates.method == profile) & (rates.group == "65+")].iloc[0]
        for _, part in table.groupby("assumption"):
            assert part.billion_km.sum() == pytest.approx(over_65.billion_km)
            assert part.share_of_65_plus_km.sum() == pytest.approx(1.0)


def test_the_central_profile_averages_the_barcelona_and_madrid_shares() -> None:
    # Each age group's share of the kilometres is the mean of its shares under the two surveys,
    # the Barcelona survey's 65+ kilometres first put on Spain's older population.
    def shares(profile: dict) -> pd.Series:
        km, _ = national.national_km(profile)
        return km / km.sum()

    central = shares(national.average_profile())
    mean = (shares(national.emef_profile()) + shares(national.edm_profile())) / 2
    assert central.sum() == pytest.approx(1.0)
    assert np.allclose(central, mean, atol=0.001)


def test_barcelona_numerator_and_denominators() -> None:
    drivers = barcelona.involved_drivers()
    assert set(drivers.day_type) <= set(calendar.DAY_TYPES)
    cars = drivers[drivers.vehicle == "car"]
    # Ride-hailing cars (trip motive "Taxi" on an ordinary car) count as taxis, as nationally.
    assert not cars[barcelona.MOTIVE].eq(barcelona.TAXI).any()
    rates = barcelona.rates()
    central = rates[rates.numerator == barcelona.NUMERATORS[0]]
    km = central.pivot(index="age4", columns="denominator", values="billion_km")
    assert (km[barcelona.DENOMINATORS[0]] < km[barcelona.DENOMINATORS[1]]).all()
    assert (km[barcelona.DENOMINATORS[1]] < km[barcelona.DENOMINATORS[2]]).all()
    reference = rates[rates.age4 == barcelona.REFERENCE]
    assert np.allclose(reference.ratio_to_45_64, 1.0)
    assert list(rates.numerator.unique()) == list(barcelona.NUMERATORS)
    # Leaving out the drivers on duty removes drivers and never adds any.
    counts = rates.groupby("numerator", sort=False).drivers_involved.sum()
    assert counts.is_monotonic_decreasing


def test_licence_calibration_scales_by_prevalence_only() -> None:
    profile = national.emef_profile()
    calibrated = national.licence_calibrated(profile)
    spain = national.licence_prevalence().set_index(["sex", "group"]).prevalence
    province = national.licence_prevalence("08").set_index(["sex", "group"]).prevalence
    for key, (point, _) in profile.items():
        assert calibrated[key][0] == pytest.approx(point * spain[key] / province[key])


def test_spanish_calendar_and_non_working_shares() -> None:
    # 2024: 262 weekdays less the fourteen public holidays the law allows; 366 days.
    assert national.working_days(2024) == (248, 118)
    assert national.NON_WORKING_RATIOS == (0.6, 1.0)


def test_coverage_components_add_up_to_dgt_total() -> None:
    parts = coverage.components().set_index("component")
    total = national.dgt_car_km()
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
    # The replicates behind the joint interval centre on the point estimates.
    replicates = edm2018.older_ratio_replicates()
    for sex in ("male", "female"):
        for measure in ("per_resident", "per_licence_holder"):
            point, reps = replicates[sex][measure]
            assert len(reps) == edm2018.N_REPLICATES
            assert abs(np.median(reps) / point - 1) < 0.1, (sex, measure)
        assert replicates[sex]["per_resident"][0] == pytest.approx(
            split.loc[sex, "ratio_75_plus_to_65_74"]
        )
    # Per registered licence holder, Madrid's men aged 75 and over drive less than those aged
    # 65-74 even at the top of the interval; its women's interval includes 1.
    like = edm2018.like_for_like_per_holder(national.older_prevalence_ratio("28")).set_index("sex")
    assert like.loc["male", "ratio_high"] < 1
    assert like.loc["female", "ratio_low"] < 1 < like.loc["female", "ratio_high"]


def test_older_split_joint_interval(older_split_table) -> None:
    split = older_split_table.set_index(["profile", "assumption", "group"]).sort_index()
    barcelona = split.loc[(national.BARCELONA_METHOD, national.REFERENCE_SPLIT)]
    central = split.loc[(national.CENTRAL_METHOD, national.REFERENCE_SPLIT)]
    assert barcelona.loc["75+", "ratio_to_45_64"] == pytest.approx(2.055, abs=0.001)
    assert barcelona.loc["65-74", "ratio_to_45_64"] == pytest.approx(0.939, abs=0.001)
    # The Madrid profile has fewer kilometres at 65 and over, so the average raises both.
    assert central.loc["75+", "ratio_to_45_64"] == pytest.approx(2.427, abs=0.001)
    assert central.loc["65-74", "ratio_to_45_64"] == pytest.approx(1.108, abs=0.001)
    for _, row in split.iterrows():
        assert row.ratio_low <= row.ratio_to_45_64 <= row.ratio_high
        # The Monte Carlo error of each end is real but small against the interval's width.
        assert 0 < row.mc_se_low < 0.05 * (row.ratio_high - row.ratio_low)
        assert 0 < row.mc_se_high < 0.06 * (row.ratio_high - row.ratio_low)
    for reference in (barcelona, central):
        assert reference.loc["75+", "ratio_low"] > 1
        # Another set of replicates would not bring the interval down to the 45-64 rate.
        assert reference.loc["75+", "ratio_low"] - 3 * reference.loc["75+", "mc_se_low"] > 1


def test_interval_monte_carlo_error_respects_crossed_replicates() -> None:
    # Draws that share row and column effects, as the crossed EMEF x EDM cells do. The standard
    # error of a percentile is measured directly over independent sets of draws, and the
    # pigeonhole estimate from one set must match it; a batch estimate over blocks that share
    # rows and columns came out several times too small.
    rng = np.random.default_rng(1)

    def crossed(n: int = 60) -> np.ndarray:
        return rng.normal(0, 1.0, (n, 1)) + rng.normal(0, 0.7, (1, n)) + rng.normal(0, 0.3, (n, n))

    direct = np.std([np.percentile(crossed(), [2.5, 97.5]) for _ in range(300)], axis=0, ddof=1)
    estimated = np.mean(
        [
            [national._interval(d, 100)[k] for k in ("mc_se_low", "mc_se_high")]
            for d in (crossed() for _ in range(20))
        ],
        axis=0,
    )
    assert np.all(estimated / direct > 0.7) and np.all(estimated / direct < 1.5)
    # A fixed split: the rows carry the profile and the columns only the count draws.
    profile_only = rng.normal(0, 1.0, (60, 1)) + rng.normal(0, 0.3, (60, 60))
    assert national._interval(profile_only, 100)["mc_se_low"] > 0
    # Paired draws are one-dimensional.
    paired = national._interval(rng.normal(0, 1.0, 300), 100)
    assert 0.05 < paired["mc_se_low"] < 0.4


def test_madrid_profile_is_standardised_to_spain() -> None:
    # The Madrid profile's 65+ cell is its exact-age km per resident at 65-74 and 75 and over,
    # weighted by Spain's residents of those ages, replicate by replicate, not Madrid's own 65+
    # mean (Madrid's 65+ residents are younger than Spain's).
    profile = national.edm_profile()
    spain = national.population_by_group().set_index(["sex", "group"]).population
    frame = edm2018.person_day()
    for sex in national.SEXES:
        young, old = spain[(sex, "65-74")], spain[(sex, "75+")]
        for index in (0, 1):
            expected = (
                profile[(sex, "65-74")][index] * young + profile[(sex, "75+")][index] * old
            ) / (young + old)
            assert np.allclose(profile[(sex, "65+")][index], expected)
        older = frame[(frame.sex == sex) & (frame.EDAD_FIN >= 65)]
        madrid_mean = float(np.average(older.car_km, weights=older.weight))
        assert profile[(sex, "65+")][0] < madrid_mean
    # Under the Madrid split the 65+ km come apart into the survey's own exact-age cells times
    # Spain's residents; an EMEF profile is still taken apart with the province's population.
    km = national._split_older_by_sex(profile, national._older_ratios()[national.REFERENCE_SPLIT])
    for sex in national.SEXES:
        for group in national.OLDER:
            assert km[(sex, group)] == pytest.approx(profile[(sex, group)][0] * spain[(sex, group)])
    emef = national.emef_profile()
    assert national._older_mean_population(emef).equals(
        national.barcelona_older_population().set_index(["sex", "group"]).population
    )


def test_licence_split_counts_licence_holders_one_way() -> None:
    # Madrid's km per DGT licence holder carried to Spain's DGT licence holders: the survey's
    # ratio per resident times Spain's licence gradient over the province of Madrid's.
    ratios = national._older_ratios()
    survey = edm2018.older_ratio_replicates()
    spain = national.older_prevalence_ratio()
    madrid = national.older_prevalence_ratio(national.MADRID_PROVINCE)
    like = edm2018.like_for_like_per_holder(madrid).set_index("sex")
    replicates = national._split_replicates(national.LICENCE_SPLIT)
    for sex in national.SEXES:
        transfer = spain[sex] / madrid[sex]
        assert ratios[national.LICENCE_SPLIT][sex] == pytest.approx(
            survey[sex]["per_resident"][0] * transfer
        )
        assert np.allclose(replicates[sex], survey[sex]["per_resident"][1] * transfer)
        # Per DGT licence holder the split is Madrid's own ratio.
        assert ratios[national.LICENCE_SPLIT][sex] / spain[sex] == pytest.approx(
            like.loc[sex, "ratio_per_dgt_holder"]
        )


def test_rate_intervals_cross_count_draws_with_the_replicates() -> None:
    rates = national.rates()
    central = rates[rates.method == national.CENTRAL_METHOD].set_index("group")
    others = central.drop(index=national.REFERENCE)
    for measure in ("involved", "killed"):
        for column in (f"{measure}_ratio", f"{measure}_per_bn_km"):
            for end in ("low", "high"):
                assert (central[f"{column}_mc_se_{end}"] >= 0).all()
        # Several count draws per replicate: the death ratios' ends move by a few hundredths at
        # most, against up to 0.07 with one draw per replicate.
        assert others[f"{measure}_ratio_mc_se_high"].max() < 0.035
        assert (others[f"{measure}_ratio_low"] <= others[f"{measure}_ratio"]).all()
        assert (others[f"{measure}_ratio"] <= others[f"{measure}_ratio_high"]).all()
    rng = np.random.default_rng(1)
    assert national._count_draws(rng, 10, 7).shape == (7, national.COUNT_DRAWS)
    sex = national.sex_per_km()
    assert {"mc_se_low", "mc_se_high"} <= set(sex.columns)
    assert (sex.ratio_low <= sex.ratio_men_to_women).all()
    city = barcelona.rates()
    assert (city.mc_se_low >= 0).all() and (city.mc_se_high >= 0).all()
    severity = national.severity_and_licences().set_index("group")
    assert severity.killed_per_1000_involved_mc_se_high.max() < 0.05


# ----------------------------------------------------------------------------- age mixes and ranges


def test_structure_shares_keep_the_working_day_mix_unless_told_otherwise() -> None:
    km, _ = national.national_km(national.average_profile())
    base = km / km.sum()
    same = coverage.structure_shares(base)
    assert np.allclose(same, base)
    # A weekend mix shifts shares towards the groups that drive more at weekends, and every mix
    # gives shares that add up to one.
    for non_working in coverage.NON_WORKING_MIXES:
        for remainder in coverage.REMAINDER_MIXES:
            shares = coverage.structure_shares(base, non_working, remainder)
            assert shares.sum() == pytest.approx(1.0)
            assert (shares > 0).all()
    weights = national.movilia_weekend_weights()
    weekend = coverage.structure_shares(base, national.MOVILIA_WEEKEND)
    expected = weights.reindex(base.index) * base
    mixed = coverage.scenario_weights()
    manual = (mixed["covered"] + mixed["professional"] + mixed["remainder"]) * base + mixed[
        "non_working"
    ] * expected / expected.sum()
    assert np.allclose(weekend, manual)
    # The array form (replicates along the second axis) agrees with the Series form.
    array = coverage.structure_shares(
        np.tile(base.to_numpy()[:, None], 3), national.MOVILIA_WEEKEND
    )
    assert np.allclose(array[:, 0], weekend)


def test_ranges_surround_the_published_estimate(
    ranges_table, rates_table, older_split_table
) -> None:
    table = ranges_table
    involved = table[table.measure == "involved per km"].set_index("group")
    assert set(involved.index) == {"16-29", "30-44", "45-64", "65+", "65-74", "75+", "men to women"}
    assert (involved.range_min <= involved.ratio + 1e-9).all()
    assert (involved.ratio <= involved.range_max + 1e-9).all()
    assert (involved.ratio_low <= involved.ratio).all()
    assert (involved.ratio <= involved.ratio_high).all()
    # The central rows are the published ones.
    central = rates_table[rates_table.method == national.CENTRAL_METHOD].set_index("group")
    for group in national.GROUPS:
        assert involved.loc[group, "ratio"] == central.loc[group, "involved_ratio"]
    split = older_split_table[
        (older_split_table.profile == national.CENTRAL_METHOD)
        & (older_split_table.assumption == national.REFERENCE_SPLIT)
    ].set_index("group")
    for group in national.OLDER:
        assert involved.loc[group, "ratio"] == split.loc[group, "ratio_to_45_64"]
    assert involved.loc["45-64", ["range_min", "range_max"]].tolist() == [1.0, 1.0]
    # The reference group, the youngest and the oldest: the direction the pages state.
    assert involved.loc["16-29", "range_min"] > 1.2
    assert involved.loc["75+", "range_min"] < 1.2 < involved.loc["75+", "range_max"]
    killed = table[table.measure == "killed per km"].set_index("group")
    assert {"16-29", "30-44", "45-64", "65+", "men to women"} == set(killed.index)


def test_the_grid_of_alternatives_contains_the_central_combination_once() -> None:
    grid = ranges.alternatives()
    assert (grid.label == "central").sum() == 2  # involved and killed
    assert set(grid.how) == {"combination", "unrecorded age"}
    # Three splits, three weekend mixes and four remainder mixes for each of eight profiles.
    combos = grid[(grid.how == "combination") & (grid.measure == "involved per km")]
    assert len(combos) == 8 * len(national.SPLITS) * 3 * 4
    # Assigning all unrecorded ages to a group raises that group's ratio and leaves the others'.
    unrecorded = grid[(grid.how == "unrecorded age") & (grid.measure == "involved per km")]
    assert len(unrecorded) == len(national.GROUPS)
    young = unrecorded[unrecorded.label.str.endswith("18-29")].iloc[0]
    centre = grid[(grid.label == "central") & (grid.measure == "involved per km")].iloc[0]
    assert young["16-29"] > centre["16-29"]
    assert young["65+"] == pytest.approx(centre["65+"])
    older = unrecorded[unrecorded.label.str.endswith("65+")].iloc[0]
    assert older["65+"] > centre["65+"] and older["75+"] > centre["75+"]
