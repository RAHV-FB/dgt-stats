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
from dgt_stats.emef import older_routing
from dgt_stats.exposure_risk import barcelona, calendar, coverage, national


@pytest.fixture(scope="module")
def older_table() -> pd.DataFrame:
    """Every 65-74 and 75+ combination (about two minutes to compute, so computed once)."""
    return national.older_sensitivity()


@pytest.fixture(scope="module")
def older_split_table() -> pd.DataFrame:
    return national.older_split()


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
    # Every central ratio lies inside its sensitivity range.
    rates = national.rates()
    central_rates = rates[rates.method == national.CENTRAL_METHOD].set_index("group")
    spread = national.sensitivity().groupby("group").involved_ratio.agg(["min", "max"])
    for group in national.GROUPS:
        value = central_rates.loc[group, "involved_ratio"]
        assert spread.loc[group, "min"] <= value <= spread.loc[group, "max"], group


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


def test_older_ranges_cover_the_central_split(older_table, older_split_table) -> None:
    split = older_split_table.set_index(["assumption", "group"]).ratio_to_45_64
    ranges = older_table
    assert set(ranges.assumption) == set(national.SPLITS)
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
        if s["profile"] == national.BARCELONA_METHOD
        and s["non_working_mix"] == s["remainder_mix"] == coverage.WORKING_DAY_MIX
    )
    _, professional = coverage._daily_km()
    w = coverage.scenario_weights()["professional"]
    expected = (1 - w) * base + w * professional / professional.sum()
    assert np.allclose(scenario["shares"], expected)
    for s in coverage.scenario_km():
        assert s["shares"].sum() == pytest.approx(1.0)
        assert all(0 < q < 1 for q in s["share_75_plus_of_65_plus"].values())


def test_sensitivity_carries_credible_coverage_scenarios_only(older_table) -> None:
    table = national.sensitivity()
    assert {national.COVERAGE_SOURCE, national.COVERAGE_PROFILE_SOURCE} <= set(table.source)
    coverage_rows = table[
        table.source.isin([national.COVERAGE_SOURCE, national.COVERAGE_PROFILE_SOURCE])
    ]
    assert not coverage_rows.variant.str.contains("(bound)", regex=False).any()
    older = older_table
    assert {national.COVERAGE_SOURCE, national.COVERAGE_PROFILE_SOURCE} <= set(older.source)
    older_coverage = older[
        older.source.isin([national.COVERAGE_SOURCE, national.COVERAGE_PROFILE_SOURCE])
    ]
    assert not older_coverage.variant.str.contains("(bound)", regex=False).any()
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


# ----------------------------------------------------------------------------- ages 75 and over


def test_older_split_joint_interval(older_split_table) -> None:
    split = older_split_table.set_index(["profile", "assumption", "group"])
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
    # A regression check, not an invariant: adding the Madrid survey's sampling error widens
    # the interval of the two Madrid splits.
    for profile in (national.BARCELONA_METHOD, national.CENTRAL_METHOD):
        for assumption in national.EDM_SPLITS:
            row = split.loc[(profile, assumption, "75+")]
            joint = np.log(row.ratio_high / row.ratio_low) / 2
            fixed = np.log(row.ratio_high_split_fixed / row.ratio_low_split_fixed) / 2
            assert joint >= fixed - 0.02
            assert "EDM2018" in row.sampling_sources
    # The central average carries both surveys' sampling error under every split.
    for (_, _, _), row in split.loc[[national.CENTRAL_METHOD]].iterrows():
        assert "EMEF" in row.sampling_sources and "EDM2018" in row.sampling_sources
    assert (
        "RACC constant"
        in split.loc[(national.BARCELONA_METHOD, national.RACC_SPLIT, "75+"), "sampling_sources"]
    )


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


def test_racc_limit_derivation() -> None:
    assert national.racc_men_limit() == pytest.approx(0.677, abs=0.005)
    for midpoints in ((0.5, 2.5, 4.5, 6.0), (1.5, 2.5, 4.5, 6.5), (1.0, 2.5, 4.5, 6.5)):
        assert 0.66 <= national.racc_men_limit(midpoints) <= 0.69
    # Both sexes' interviews add up to the survey's 3,003 holders.
    assert sum(sum(ages.values()) for ages in national.RACC_INTERVIEWS.values()) == 3003


def test_racc_split_between(older_table) -> None:
    """An empirical check, not a construction: the RACC split gives 75 and over less driving
    than the equal split and more than the Madrid split per resident in every structure. (Its
    women's ratio per resident, 0.262, is below Madrid's 0.282, so the ordering is not
    guaranteed by the inputs.)"""
    ratios = national._older_ratios()
    assert ratios[national.RACC_SPLIT]["female"] < ratios[national.REFERENCE_SPLIT]["female"]
    wide = older_table.pivot_table(
        index=["source", "variant"], columns="assumption", values="ratio_75_plus"
    )
    assert (wide[national.EQUAL_SPLIT] < wide[national.RACC_SPLIT]).all()
    assert (wide[national.RACC_SPLIT] < wide[national.REFERENCE_SPLIT]).all()


def test_marking_rule(older_table) -> None:
    table = older_table
    # Nothing is filtered: every structure under every split. 115 structures: 31 one at a time
    # and 7 profiles x 3 non-working-day mixes x 4 credible remainder mixes.
    structures = table.drop_duplicates(["source", "variant"])
    assert len(table) == len(national.SPLITS) * len(structures) == 460
    # The men's ratio recomputed from the km allocation and DGT's holders matches the column,
    # and is a property of the split.
    holders = national.older_licence_prevalence().set_index(["sex", "group"]).b_licence_holders
    for split, part in table.groupby("assumption"):
        km = national._split_older_by_sex(national.emef_profile(), national._older_ratios()[split])
        men = (km[("male", "75+")] / holders[("male", "75+")]) / (
            km[("male", "65-74")] / holders[("male", "65-74")]
        )
        assert np.allclose(part.men_km_per_holder_75_vs_65_74, men)
    # The licence split carries Madrid's km per DGT licence holder, so it implies Madrid's own
    # men's ratio per DGT licence holder (0.48, like the Madrid split), not the 0.45 it gave
    # when it divided by the survey's self-reported licence holding.
    expected = {
        national.REFERENCE_SPLIT: 0.48,
        national.LICENCE_SPLIT: 0.48,
        national.RACC_SPLIT: 0.677,
        national.EQUAL_SPLIT: 1.0,
    }
    by_split = table.groupby("assumption").men_km_per_holder_75_vs_65_74
    for split, value in expected.items():
        assert by_split.min()[split] == pytest.approx(value, abs=0.005)
        assert by_split.max()[split] == pytest.approx(value, abs=0.005)
    marked = table.at_odds_with_mens_driving
    assert marked.equals(table.assumption == national.EQUAL_SPLIT)
    for threshold in (0.7, 0.9, 1.0):
        assert (table.men_km_per_holder_75_vs_65_74 >= threshold - 1e-9).equals(marked)
    # The full range is over all rows; the lowest row is marked; the lowest unmarked one is the
    # RACC split at Barcelona city's profile with MOVILIA's weekend mix for the km outside the
    # working days.
    assert table.loc[table.ratio_75_plus.idxmin(), "at_odds_with_mens_driving"]
    unmarked = table[~marked]
    lowest = unmarked.loc[unmarked.ratio_75_plus.idxmin()]
    assert lowest.ratio_75_plus == pytest.approx(1.214, abs=0.002)
    assert lowest.assumption == national.RACC_SPLIT
    assert lowest.profile == "C: EMEF, Barcelona city"
    assert lowest.non_working_mix == lowest.remainder_mix == national.MOVILIA_WEEKEND


def test_composition_bound(older_table, older_split_table) -> None:
    shares = national.composition_shares()
    for sample, population in shares.values():
        assert 0 < sample < population < 1
    routing = older_routing.routing_share().set_index("sex")
    assert (routing.respondents_flagged >= 20).all()
    assert (routing.routing_share_75_plus < routing.ine_share_75_plus).all()
    # In 2014, when the routing identified the 75+ correctly, it matches the population share.
    early = older_routing.routing_share((2014,)).set_index("sex")
    assert np.allclose(early.routing_share_75_plus, early.ine_share_75_plus, atol=0.02)
    table = older_table
    bound = table[table.variant == national.COMPOSITION_VARIANT].set_index("assumption")
    assert set(bound.index) == set(national.SPLITS)
    split = older_split_table[older_split_table.profile == national.BARCELONA_METHOD]
    split = split.set_index(["assumption", "group"]).ratio_to_45_64
    for assumption, row in bound.iterrows():
        rise = row.ratio_75_plus / split[(assumption, "75+")] - 1
        assert 0.04 < rise < 0.13, (assumption, rise)
    # The bound moves neither end of the range.
    others = table[table.variant != national.COMPOSITION_VARIANT]
    assert others.ratio_75_plus.min() == table.ratio_75_plus.min()
    assert others.ratio_75_plus.max() == table.ratio_75_plus.max()
    # And it has its own 65+ row in the national sensitivity table.
    national_table = national.sensitivity()
    assert (
        (national_table.variant == national.COMPOSITION_VARIANT) & (national_table.group == "65+")
    ).sum() == 1


def test_older_extremes(older_table) -> None:
    extremes = national.older_extremes(older_table)
    assert set(zip(extremes.group, extremes.end)) == {
        (group, end) for group in ("75+", "65-74") for end, _, _ in national.EXTREMES
    }
    assert (extremes.ratio_low <= extremes.value).all()
    assert (extremes.value <= extremes.ratio_high).all()
    for row in extremes.itertuples():
        if row.profile == national.MADRID_METHOD and row.assumption in national.EDM_SPLITS:
            assert row.replicates.startswith("paired")
        assert "counts" in row.sampling_sources
    assert extremes.set_index(["group", "end"]).loc[("75+", "full minimum"), "value"] == (
        pytest.approx(older_table.ratio_75_plus.min())
    )
    fixed = extremes.set_index(["group", "end"]).loc[("75+", "lowest unmarked")]
    assert "fixed:" in fixed.sampling_sources and "RACC constant" in fixed.sampling_sources


def test_decomposition_table(older_table, older_split_table) -> None:
    table = national.older_decomposition(older_table, older_split_table)
    assert "sampling" not in set(table.kind)
    whole = table[table.kind == "all"].iloc[0]
    unmarked = older_table[~older_table.at_odds_with_mens_driving].ratio_75_plus
    assert whole.low == older_table.ratio_75_plus.min()
    assert whole.high == older_table.ratio_75_plus.max()
    assert whole.clear_low == unmarked.min() and whole.clear_high == unmarked.max()
    factors = table[table.kind == "factor"].set_index("factor")
    estimate = float(whole.estimate)
    reference = older_table[older_table.assumption == national.REFERENCE_SPLIT]
    for source in ("regional profile", "distance", "non-working days", "survey years"):
        values = list(reference[reference.source == source].ratio_75_plus) + [estimate]
        assert factors.loc[source, "low"] == pytest.approx(min(values))
        assert factors.loc[source, "high"] == pytest.approx(max(values))
    assert factors.loc["split", "low"] == pytest.approx(
        older_split_table.query("group == '75+'").ratio_to_45_64.min()
    )
    assert factors.loc["split", "hatched_high"] == pytest.approx(factors.loc["split", "clear_low"])
    # The remainder alone, with every other part at the working-day mix, reproduces the
    # estimate when the remainder takes the working-day mix too.
    remainder = national._remainder_only()
    assert remainder[coverage.WORKING_DAY_MIX] == pytest.approx(estimate, abs=1e-9)
    assert (table.low <= table.high).all() and (table.low > 0).all()
    assert list(factors.log_width) == sorted(factors.log_width, reverse=True)


def test_decomposition_labels_keep_their_subject() -> None:
    # Each chart label names the same assumption as its long label: the remainder is the
    # unexplained km, never "outside working days", which would also hold the weekends of the
    # separate weekend bar.
    subjects = {
        "regional profile": "region",
        "split": "split",
        "remainder": "unexplained",
        "distance": "conversion",
        "non-working days": "weekend",
        "professionals' work driving": "professional",
        "composition": "share",
        "licence-calibrated transfer": "per licence holder",
        "employment": "share in work",
        "survey years": "survey years",
    }
    assert set(subjects) == set(national.DECOMPOSITION_FACTORS)
    for factor, (label, short) in national.DECOMPOSITION_FACTORS.items():
        assert subjects[factor] in label.lower() and subjects[factor] in short.lower(), factor
        assert "working days" not in short.lower(), factor
    shorts = [short for _, short in national.DECOMPOSITION_FACTORS.values()]
    assert len(set(shorts)) == len(shorts)


def test_reference_checks_licence_trend() -> None:
    checks = national.reference_checks().set_index(["check", "subject"])
    gradient = checks.xs(national.CHECK_LICENCE_GRADIENT_TREND, level="check").value
    level = checks.xs(national.CHECK_LICENCE_TREND, level="check").value
    # Licence holding at 75 and over rose against 65-74 for both sexes, by less than at 75 and
    # over alone, and the cohort update lowers the conditional estimate.
    assert (gradient > 1).all() and (gradient < level).all()
    cohort = float(checks.loc[(national.CHECK_COHORT_UPDATE, "both sexes"), "value"])
    split = national.older_split()
    split = split[split.profile == national.BARCELONA_METHOD].set_index(["assumption", "group"])
    assert 1 < cohort < float(split.loc[(national.REFERENCE_SPLIT, "75+"), "ratio_to_45_64"])


def test_attribution_shares(older_table) -> None:
    shares = national.older_attribution(older_table)
    for column in ("share_all_splits", "share_without_equal_split"):
        assert shares[column].sum() == pytest.approx(1.0, abs=1e-9)
        assert (shares[column] >= -1e-12).all()


def test_barcelona_older() -> None:
    table = barcelona.older_ratios()
    assert set(table.assumption) == set(national.SPLITS)
    assert (table.ratio_low <= table.ratio_to_45_64).all()
    assert (table.ratio_to_45_64 <= table.ratio_high).all()
    # Each end carries its Monte Carlo error, so the pages can print it to a supported precision.
    assert (table.mc_se_low > 0).all() and (table.mc_se_high > 0).all()
    assert (table.mc_se_high < 0.1 * (table.ratio_high - table.ratio_low)).all()


# ----------------------------------------------------------------------------- October 2026 review


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
    implied = national.implied_km_per_holder(ratios[national.LICENCE_SPLIT])
    replicates = national._split_replicates(national.LICENCE_SPLIT)
    for sex in national.SEXES:
        transfer = spain[sex] / madrid[sex]
        assert ratios[national.LICENCE_SPLIT][sex] == pytest.approx(
            survey[sex]["per_resident"][0] * transfer
        )
        assert np.allclose(replicates[sex], survey[sex]["per_resident"][1] * transfer)
        assert implied[sex] == pytest.approx(like.loc[sex, "ratio_per_dgt_holder"])
    assert "DGT licence prevalence" in national._sampling_sources(national.LICENCE_SPLIT)


def test_owner_age_mix_is_a_bound_with_the_scenarios_own_split() -> None:
    assert coverage.OWNER_MIX in coverage.BOUNDS and "bound" in coverage.OWNER_MIX
    km, _ = national.national_km(national.emef_profile())
    _, own = coverage.mix_shares(coverage.OWNER_MIX, km / km.sum())
    assert own is None
    mixes = coverage.mixes().drop_duplicates("mix").set_index("mix")
    assert not mixes.loc[coverage.OWNER_MIX, "credible"]
    assert mixes.loc[coverage.OWNER_MIX, "status"].startswith("bound")
    assert np.isnan(mixes.loc[coverage.OWNER_MIX, "share_75_plus_of_65_plus"])
    # With no split of its own, the owner-age remainder keeps each scenario's 75+ share, as the
    # working-day remainder does.
    keyed = {
        (s["profile"], s["non_working_mix"], s["remainder_mix"]): s for s in coverage.scenario_km()
    }
    for (profile, non_working, remainder), scenario in keyed.items():
        if remainder != coverage.OWNER_MIX:
            continue
        assert not scenario["credible"]
        same = keyed[(profile, non_working, coverage.WORKING_DAY_MIX)]
        for split, share in scenario["share_75_plus_of_65_plus"].items():
            assert share == pytest.approx(same["share_75_plus_of_65_plus"][split])
    # It is in no published range.
    assert not national.sensitivity().variant.str.contains("owner", regex=False).any()


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
