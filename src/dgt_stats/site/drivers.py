"""Driver age and sex: how often car drivers are involved in crashes for the distance they drive,
and how often a crash kills the driver.

The page leads with involvement per kilometre driven by drivers of each age, estimated from the
EMEF working-day survey's age profile, Spain's population and DGT's car kilometres
(``scripts/exposure_risk.py``; ``docs/research/DRIVER_AGE_EXPOSURE.md``). That section sets out
how much of DGT's kilometres the survey covers, what the rest is made of and how other age mixes
for it move the ratios, and closes with a short note on the former owner-age figure. It then
gives deaths once involved, the check in Barcelona on working days, the oldest drivers (counted
deaths once involved and involvement per licence holder, a conditional estimate per kilometre
beside the sensitivity range, and what moves it), and the comparison of men and women. Every number is read from the ``risk_*`` and ``drivers_sex_*``
tables, and every qualitative sentence is checked against them before the page is written.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgt_stats import edm2018
from dgt_stats import figures as figures_module
from dgt_stats.emef import exposure, publication
from dgt_stats.emef import variables as emef_variables
from dgt_stats.exposure_risk import barcelona as city_design
from dgt_stats.exposure_risk import calendar as day_calendar
from dgt_stats.exposure_risk import coverage as coverage_design
from dgt_stats.exposure_risk import national
from dgt_stats.site.components import (
    _fmt_dec,
    _fmt_pct,
    downloads,
    evidence_note,
    figure,
    figure_ref,
    limitation,
    read_table,
    render_page,
    summary,
    table,
    technical,
)
from dgt_stats.site.numbers import (
    FAIL,
    INTERMEDIATE,
    PASS,
    _driver_numbers,
    _older_numbers,
    _sex_numbers,
)

REFERENCE = "45-64"
YEAR = national.YEAR
CITY_YEAR = city_design.YEAR
SURVEY_YEARS = f"{min(exposure.CONTEMPORARY_YEARS)}–{max(exposure.CONTEMPORARY_YEARS)}"
CENTRAL_KM = "less taxi and ride-hailing"
GROUPS = ("18-29", "30-44", "45-64", "65+")
LABELS = {
    "18-29": "18–29",
    "30-44": "30–44",
    "45-64": "45–64",
    "65+": "65 and over",
    "65-74": "65–74",
    "75+": "75 and over",
}
CRTM_URL = "https://www.crtm.es"
EXPOSURE_DOC = "https://github.com/RAHV-FB/dgt-stats/blob/main/docs/research/DRIVER_AGE_EXPOSURE.md"


def _check(holds: bool, claim: str) -> None:
    if not holds:
        raise ValueError(f"drivers page: the tables no longer support: {claim}")


def _ci(row: pd.Series, column: str) -> str:
    return f"{float(row[f'{column}_low']):.2f}–{float(row[f'{column}_high']):.2f}"


def _span(values: pd.Series) -> str:
    return f"{float(values.min()):.2f}–{float(values.max()):.2f}"


def _rates_table(central: pd.DataFrame, ranges: pd.DataFrame, level: pd.Series, year: int) -> str:
    rows = []
    for group in GROUPS:
        row = central.loc[group]
        reference = group == REFERENCE
        rows.append(
            {
                "Age": LABELS[group],
                "Drivers involved": row.involved,
                "Kilometres (billion)": row.billion_km,
                "Involved per billion km (95% sampling interval)": (
                    f"{row.involved_per_bn_km:,.0f} "
                    f"({row.involved_per_bn_km_low:,.0f}–{row.involved_per_bn_km_high:,.0f})"
                ),
                "Ratio to 45–64 (95% sampling interval)": "1 (reference)"
                if reference
                else f"{row.involved_ratio:.2f} ({_ci(row, 'involved_ratio')})",
                "Sensitivity range of the ratio": ""
                if reference
                else f"{ranges.loc[group, 'min']:.2f}–{ranges.loc[group, 'max']:.2f}",
            }
        )
    # A reader reproducing the table needs the rows of the published CSV it comes from.
    method, km_total = str(central.method.iloc[0]), str(central.km_total.iloc[0])
    return table(
        pd.DataFrame(rows),
        f"Car drivers involved in injury crashes per kilometre driven, by age, Spain, {year}. "
        "Kilometres by age from the EMEF's working-day profile applied to Spain's population "
        "and scaled to DGT's car kilometres less taxis and ride-hailing cars. The 95% sampling "
        "intervals combine a bootstrap of the survey with Poisson error in the crash counts; the "
        "bootstrap replicates are not published. The sensitivity range spans every alternative in the "
        "table of sources below. Data: the rows of the CSV of involvement and deaths per km by "
        f"age with method “{method}” and kilometre total “{km_total}”; its other kilometre "
        f"totals change the rates (from {float(level.min()):,.0f} to {float(level.max()):,.0f} "
        "per billion km at 65 and over) but not the ratios.",
        {"Drivers involved": "int", "Kilometres (billion)": "dec"},
    )


SOURCE_LABELS = {
    "regional profile": (
        f"Another region's age profile (four parts of the province; Madrid {edm2018.SURVEY_YEAR})"
    ),
    "licence-calibrated transfer": "Driving per licence holder, not per resident, carried to Spain",
    "distance": "Other treatments of trip distances",
    "survey years": "Other survey years",
    "professionals' work driving": "Professional drivers' unrecorded work driving",
    "older sample": (
        "Survey's older respondents: employed share set to the census, or too few aged 75 and "
        "over (bound)"
    ),
    "non-working days": "A different age mix on weekends and holidays",
    national.COVERAGE_SOURCE: "Other age mixes for the kilometres the survey does not cover",
    national.COVERAGE_PROFILE_SOURCE: "Another region's profile together with those age mixes",
}


def _sources_table(by_source: pd.DataFrame) -> str:
    rows = []
    for source, label in SOURCE_LABELS.items():
        row = {"What changes": label}
        for group in ("18-29", "30-44", "65+"):
            low, high = by_source.loc[(source, group)]
            row[LABELS[group]] = (
                f"{low:.2f}" if abs(high - low) < 0.005 else f"{low:.2f}–{high:.2f}"
            )
        rows.append(row)
    return table(
        pd.DataFrame(rows),
        "Ratio of each age group's involvement per kilometre to that of drivers aged 45–64 under "
        "each alternative choice, Spain. Each cell spans the variants of one choice in the CSV "
        "of ratios under every alternative; the sensitivity range in the table above is the "
        "span of all of them.",
    )


PROFESSIONAL_PART = "professionals' work driving"
COVERAGE_LABELS = {
    "working days": ("Working days, as the survey measures them", "survey's working days"),
    PROFESSIONAL_PART: (
        "Work trips of people who drive for a living, counted but not described by the survey",
        "professionals' work trips",
    ),
    "regional level": (
        "More driving per resident in Spain than in the province",
        "survey's working days",
    ),
    "non-working days": (
        "Weekends and public holidays",
        "survey's working days; two weekend mixes tested",
    ),
    "months outside the fieldwork": (
        "Months outside the survey's fieldwork",
        "survey's working days",
    ),
    "remainder (not explained)": (
        "Not explained by any part above",
        "survey's working days; four other measured mixes and two bounds tested",
    ),
    "cars registered to companies": (
        "Cars registered to companies (overlaps the parts above)",
        "no age recorded",
    ),
    "car hire without driver": ("Hire cars (overlaps the parts above)", "no age recorded"),
}


def _between(low: float, high: float, fmt) -> str:
    """One value, or 'a to b' from the lower to the higher (either may be negative)."""
    low, high = sorted((float(low), float(high)))
    return fmt(low) if fmt(low) == fmt(high) else f"{fmt(low)} to {fmt(high)}"


def _coverage_table(parts: pd.DataFrame) -> str:
    rows = []
    for component, (label, mix) in COVERAGE_LABELS.items():
        row = parts.loc[component]
        rows.append(
            {
                "Part of DGT's car kilometres": label,
                "Billion km": _between(
                    row.bn_km_least_explained, row.bn_km_most_explained, _fmt_dec
                ),
                "Share of DGT's total": _between(
                    row.share_least_explained,
                    row.share_most_explained,
                    lambda v: _fmt_pct(v, 0),
                ),
                "Age mix in the central estimate": mix,
            }
        )
    total = float(parts.dgt_total_bn_km.iloc[0])
    return table(
        pd.DataFrame(rows),
        f"What the {YEAR} DGT car kilometres less taxis and ride-hailing cars "
        f"({_fmt_dec(total)} billion) are made of, as far as the data show. Each part is given at "
        "the setting that explains least and the one that explains most, and the parts are "
        "added in the order shown; the last two rows overlap them and are not added. Data: the "
        "CSV of the coverage of DGT's kilometres and the CSV of the evidence behind it.",
    )


def _barcelona_table(barcelona: pd.DataFrame) -> str:
    rows = []
    for group in GROUPS:
        part = barcelona[barcelona.age4 == group].set_index("denominator")
        row = {"Age": LABELS[group], "Drivers involved": int(part.drivers_involved.iloc[0])}
        for denominator, column in (
            ("internal trips only", "Inside-city trips only"),
            (
                "crossing trips at an internal trip's length",
                "Crossing trips at a city trip's length",
            ),
            ("crossing trips in full", "Crossing trips in full"),
        ):
            value = part.loc[denominator]
            row[column] = (
                "1 (reference)"
                if group == REFERENCE
                else f"{value.ratio_to_45_64:.2f} ({value.ratio_low:.2f}–{value.ratio_high:.2f})"
            )
        rows.append(row)
    return table(
        pd.DataFrame(rows),
        "Car drivers involved in injury crashes per kilometre driven inside Barcelona on working "
        f"days, {CITY_YEAR}, as ratios to drivers aged 45–64 under three versions of the "
        f"kilometres, with 95% intervals. The kilometres are EMEF {SURVEY_YEARS} car-driver trips "
        "inside the city by residents of the survey area, with trips that cross the city boundary "
        "counted not at all, at the length of a trip inside the city, or in full. Taxis and "
        "ride-hailing cars are left out.",
        {"Drivers involved": "int"},
    )


def _older_table(older: pd.DataFrame, variants: pd.DataFrame, full: str, madrid: str) -> str:
    labels = national.public_split_labels()
    rows = []
    for split in national.SPLITS:
        part = older[older.assumption == split].set_index("group")
        spread = variants[variants.assumption == split].ratio_75_plus
        rows.append(
            {
                "Split of the 65-and-over kilometres": labels[split],
                "75 and over: ratio to 45–64 (95% sampling interval)": (
                    f"{part.loc['75+', 'ratio_to_45_64']:.2f} ({_ci(part.loc['75+'], 'ratio')})"
                ),
                "75 and over: sensitivity range under this split": _span(spread),
                "65–74: ratio (95% sampling interval)": (
                    f"{part.loc['65-74', 'ratio_to_45_64']:.2f} ({_ci(part.loc['65-74'], 'ratio')})"
                ),
                "Implied km per licence holder, men 75 and over against 65–74": float(
                    part.loc["75+", "men_km_per_holder_75_vs_65_74"]
                ),
            }
        )
    return table(
        pd.DataFrame(rows),
        f"Car drivers involved in injury crashes per kilometre at 75 and over and at 65–74, Spain, "
        f"{YEAR}, as ratios to drivers aged 45–64, under each split of the 65-and-over "
        "kilometres, with every other choice as in the central estimate; the sensitivity range "
        f"over all four splits and every other choice is {full} at 75 and over. The first two "
        "rows' intervals include the Madrid survey's sampling error; the last two include only "
        "the Barcelona-area survey's and the crash counts', and the RACC figure is held fixed. "
        f"{madrid}",
        {"Implied km per licence holder, men 75 and over against 65–74": "dec2"},
    )


def _sex_rates_table(rates_table: pd.DataFrame, years: str) -> str:
    rows = []
    for scope, scope_label in (
        ("car", "Private-car drivers"),
        ("motor", "All motor-vehicle drivers"),
    ):
        for sex, sex_label in (("male", "Men"), ("female", "Women")):
            row = rates_table.loc[(scope, "18+", sex)]
            rows.append(
                {
                    "Drivers": scope_label,
                    "Sex": sex_label,
                    "Involved per 1,000 licence holders a year": row.involved_per_1000_licences,
                    "Killed per million licence holders a year": row.deaths_per_million_licences,
                    "Killed per 1,000 involved": row.deaths_per_1000_involved,
                    "Drivers killed": row.driver_deaths,
                }
            )
    return table(
        pd.DataFrame(rows),
        f"Drivers aged 18 and over by sex, {years} pooled. Licence holders include every type "
        "of licence; private cars exclude taxis and ride-hailing cars.",
        {
            "Involved per 1,000 licence holders a year": "dec2",
            "Killed per million licence holders a year": "dec",
            "Killed per 1,000 involved": "dec",
            "Drivers killed": "int",
        },
    )


def _fmt_span(low: float, high: float, digits: int = 2) -> str:
    return f"{low:.{digits}f}–{high:.{digits}f}"


def page_drivers(captions: dict[str, str]) -> str:
    numbers = _driver_numbers()
    central, licence = numbers["central"], numbers["licence"]
    ranges, by_source = numbers["ranges"], numbers["by_source"]
    year = YEAR
    all_rates = read_table("risk_national_rates")
    central_rows = all_rates[all_rates.method == central.method.iloc[0]]
    level = central_rows[central_rows.group == "65+"].set_index("km_total").involved_per_bn_km
    city = numbers["city"]
    city_all = numbers["city_all"]
    older = numbers["older"]
    older_range = numbers["older_range"]
    city_split = numbers["city_older"]
    severity = numbers["severity"]
    comparison = read_table("risk_owner_age_comparison")
    numerator = read_table("risk_national_numerator").set_index("group")
    shares = read_table("risk_national_shares")
    unknown_bounds = read_table("risk_unknown_age_bounds")
    city_unknown = read_table("risk_barcelona_unknown_age_bounds")
    employment = read_table("emef_employment_benchmark")
    prevalence = read_table("risk_licence_prevalence")
    sex_km = read_table("risk_sex_per_km").set_index("measure")
    b_licence = read_table("drivers_sex_b_licence").set_index("denominator")
    sex_numbers = _sex_numbers()
    sex_ratios, sex_rates = sex_numbers["ratios"], sex_numbers["rates"]
    sex_years = str(sex_rates.years.iloc[0]).replace("-", "–")
    trend = read_table("drivers_sex_trend")
    trend_years = f"{int(trend.year.min())}–{int(trend.year.max())}"
    parts = read_table("risk_coverage").set_index("component")
    proof = read_table("risk_coverage_evidence").set_index("measure").value
    scenarios = read_table("risk_coverage_scenarios")
    oldest_numbers = _older_numbers()
    older_variants = oldest_numbers["older"]
    unmarked = oldest_numbers["unmarked"]
    tier = oldest_numbers["tier"]
    conditional = oldest_numbers["conditional"]
    cond_75, cond_65 = conditional.loc["75+"], conditional.loc["65-74"]
    clear = oldest_numbers["clear"]
    lowest_clear = oldest_numbers["lowest_clear"]
    checks = read_table("risk_older_reference_checks")
    decomposition = read_table("risk_older_decomposition")
    madrid_year = edm2018.SURVEY_YEAR

    young, older_all = central.loc["18-29"], central.loc["65+"]
    by_older = older.set_index(["assumption", "group"])
    old_65 = older[older.group == "65-74"].ratio_to_45_64
    city_older = city[city.age4 == "65+"].set_index("denominator").ratio_to_45_64
    city_young = city[city.age4 == "18-29"].ratio_to_45_64
    on_duty = city_all[
        (city_all.numerator == city_design.NUMERATORS[1]) & (city_all.age4 == "65+")
    ].set_index("denominator")
    city_75 = city_split[city_split.age == "75+"].ratio_to_45_64
    owner = comparison[comparison.denominator.str.endswith("(former figure)")].set_index("group")
    owner_same = comparison[comparison.denominator.str.endswith("same age groups")].set_index(
        "group"
    )
    killed = {g: float(severity.loc[g, "killed_per_1000_involved"]) for g in severity.index}
    a_share = shares[shares.method.str.startswith("A:")].set_index("group")
    unknown_share = float(numerator.unknown_share.iloc[0])
    madrid = by_older.loc[national.REFERENCE_SPLIT]
    variants = numbers["sensitivity"]
    sensitivity = variants.set_index(["source", "variant", "group"]).involved_ratio
    composition_older = float(
        sensitivity.loc[("older sample", national.COMPOSITION_VARIANT, "65+")]
    )
    employed_survey = employment[employment.source.str.startswith("EMEF")].set_index("year")
    employed_census = float(
        employment[employment.source.str.startswith("census")].employed_share.iloc[0]
    )
    early_years = [y for y in employed_survey.index if y < min(exposure.CONTEMPORARY_YEARS)]
    late_years = list(exposure.CONTEMPORARY_YEARS)
    employed_reweighted = float(
        sensitivity.loc[("older sample", national.EMPLOYMENT_VARIANT, "65+")]
    )
    professional = by_source.loc[("professionals' work driving", "65+")]
    weekend = by_source.loc[("non-working days", "65+")]
    regional_young = by_source.loc[("regional profile", "18-29")]
    regional_old = by_source.loc[("regional profile", "65+")]
    distance_old = by_source.loc[("distance", "65+")]
    unknown_young = float(
        unknown_bounds[
            (unknown_bounds.unknown_age_assigned_to == "18-29") & (unknown_bounds.group == "18-29")
        ].involved_ratio.iloc[0]
    )
    city_unknown_old = (
        city_unknown[city_unknown.age4 == "65+"].set_index("unknown_age_assigned_to").ratio_to_45_64
    )
    city_unknown_share = float(
        city.drivers_age_not_recorded.iloc[0]
        / (
            city.drivers_age_not_recorded.iloc[0]
            + city[city.denominator == city.denominator.iloc[0]].drivers_involved.sum()
        )
    )

    killed_range = variants.groupby("group").killed_ratio.agg(["min", "max"]).loc["65+"]
    km_total = read_table("risk_national_km_total").set_index("variant").km
    working, non_working = national.working_days(year)
    survey_cover = float(parts.loc["working days", "share_least_explained"])
    _check(
        abs(
            float(a_share.workday_km_per_day_millions.sum()) * 1e6 * working
            - float(parts.loc["working days", "bn_km_least_explained"]) * 1e9
        )
        < 1e6
        and abs(float(parts.dgt_total_bn_km.iloc[0]) * 1e9 - float(km_total[CENTRAL_KM])) < 1e6
        and 0.45 < survey_cover < 0.55,
        "the survey's working days, carried to Spain, cover about half of DGT's car kilometres",
    )

    def part(component: str) -> tuple[float, float]:
        row = parts.loc[component]
        return tuple(sorted((float(row.share_least_explained), float(row.share_most_explained))))

    def share_span(component: str) -> str:
        return _between(*part(component), lambda v: _fmt_pct(v, 0))

    regional = proof[proof.index.str.startswith("car or motorcycle trips per resident, week (")]
    dgt_regional = proof[proof.index.str.startswith("car km per resident aged 15 and over, Spain")]
    seasonal = proof[proof.index.str.contains("mean day of")]
    weekend_trips = float(
        proof[proof.index.str.startswith("car or motorcycle trips on an average weekend day")].iloc[
            0
        ]
    )
    weekend_minutes = float(proof[proof.index.str.startswith("mean trip duration")].iloc[0])
    remainder = part("remainder (not explained)")
    _check(
        part("non-working days")[0] > part("regional level")[0]
        and part("non-working days")[1] > part("professionals' work driving")[1]
        and remainder[0] < 0 < 0.2 < remainder[1]
        and float(regional.iloc[0]) < float(dgt_regional.min())
        and float(seasonal.min()) < 1 < float(seasonal.max())
        and abs(float(seasonal.max()) - 1) < 0.05
        and abs(float(seasonal.min()) - 1) < 0.05
        and weekend_trips < 1 < weekend_minutes,
        "weekends are the largest measured part; the measured parts can explain all of the gap "
        "or leave over a fifth; MOVILIA's regional level is below DGT's; the months outside the "
        "fieldwork change the total by a few per cent either way; weekend days have fewer car "
        "trips and longer trips",
    )
    credible = scenarios[scenarios.credible]
    alone = credible[credible.profile == national.CENTRAL_METHOD]
    bounds = scenarios[~scenarios.credible & (scenarios.profile == national.CENTRAL_METHOD)]
    others = variants[
        ~variants.source.isin([national.COVERAGE_SOURCE, national.COVERAGE_PROFILE_SOURCE])
    ]
    other_ranges = others.groupby("group").involved_ratio.agg(["min", "max"])
    licence_bound = bounds[bounds.remainder_mix == coverage_design.LICENCE_MIX]
    under_65_bound = bounds[bounds.remainder_mix == coverage_design.UNDER_65_MIX]
    for group, column in (("18-29", "ratio_18_29"), ("65+", "ratio_65_plus")):
        _check(
            float(other_ranges.loc[group, "min"]) <= float(alone[column].min())
            and float(alone[column].max()) <= float(other_ranges.loc[group, "max"])
            and float(ranges.loc[group, "min"]) < float(other_ranges.loc[group, "min"])
            and np.isclose(float(credible[column].min()), float(ranges.loc[group, "min"]))
            and np.isclose(float(credible[column].max()), float(ranges.loc[group, "max"])),
            f"for {group}, the uncovered kilometres alone stay inside the other tests' range, and "
            "with another region's profile they set both ends of the sensitivity range",
        )
    _check(
        float(ranges.loc["65+", "min"]) <= float(licence_bound.ratio_65_plus.min())
        and float(licence_bound.ratio_65_plus.max()) <= float(ranges.loc["65+", "max"])
        and float(under_65_bound.ratio_65_plus.max()) > float(ranges.loc["65+", "max"]),
        "the licence-holder bound lies inside the 65+ range and the under-65 bound above it",
    )
    # Ages 75 and over: the marking rule, the ends of the range and what sets them.
    weekend_mixes = (national.EMEF_WEEKEND_PROXY, national.MOVILIA_WEEKEND)
    marked = older_variants[older_variants.at_odds_with_mens_driving]
    lowest_75 = older_variants.loc[older_variants.ratio_75_plus.idxmin()]
    highest_75 = older_variants.loc[older_variants.ratio_75_plus.idxmax()]
    lowest_clear_row = unmarked.loc[unmarked.ratio_75_plus.idxmin()]
    _check(
        set(marked.assumption) == {national.EQUAL_SPLIT}
        and len(marked) == int((older_variants.assumption == national.EQUAL_SPLIT).sum())
        and len(older_variants)
        == len(national.SPLITS) * len(older_variants.drop_duplicates(["source", "variant"])),
        "exactly the equal-split rows are marked, as a property of the split, and no row is "
        "dropped",
    )
    _check(
        bool(lowest_75.at_odds_with_mens_driving)
        and "Barcelona city" in str(lowest_75.profile)
        and str(lowest_clear_row.assumption) == national.RACC_SPLIT
        and "Barcelona city" in str(lowest_clear_row.profile)
        and str(lowest_clear_row.non_working_mix) in weekend_mixes
        and str(lowest_clear_row.remainder_mix) in weekend_mixes
        and clear["75+"][0] > older_range["75+"][0]
        and np.isclose(clear["75+"][1], older_range["75+"][1])
        and not bool(highest_75.at_odds_with_mens_driving)
        and clear["65-74"][1] < older_range["65-74"][1],
        "the lowest combination is marked; the lowest unmarked one combines Barcelona city's "
        "profile, weekend mixes for the km outside the working days and the RACC limit; marked "
        "rows alone reach the bottom of the 75+ range and the top of the 65-74 range",
    )
    _check(
        older_range["75+"][0] <= 1 < older_range["75+"][1]
        and float(cond_75.ratio_low) > 1
        and float(cond_75.ratio_low) <= float(cond_75.ratio_to_45_64) <= float(cond_75.ratio_high)
        and older_range["75+"][0] <= float(cond_75.ratio_to_45_64) <= older_range["75+"][1]
        and str(lowest_clear.assumption) == national.RACC_SPLIT
        and (
            (tier == INTERMEDIATE and float(lowest_clear.ratio_low) <= 1 < clear["75+"][0])
            or (tier == PASS and float(lowest_clear.ratio_low) > 1)
            or (tier == FAIL and clear["75+"][0] <= 1)
        ),
        "the 75+ sensitivity range reaches the 45-64 rate; the conditional estimate's interval "
        "lies above it; the wording chosen matches the lowest unmarked combination and its "
        "sampling interval",
    )
    bands = read_table("emef_km_by_band")
    # Trips of 100 km or more and trips with no band, together: one minus the shorter bands, so
    # that a band suppressed under the survey's publication rule (fewer than 20 sample trips, as
    # at 16-29) is never read; the combined cell itself must rest on 20 sample trips or more.
    long_bands = bands.band.isin(["100 km or more", "no band"])
    shorter = bands[~long_bands]
    _check(
        bool(shorter[["share_of_trips", "share_of_km"]].notna().all().all()),
        "every band under 100 km is published in every age group",
    )
    long_trips = 1 - shorter.groupby("age4")[["share_of_trips", "share_of_km"]].sum()
    long_sample = bands[long_bands].groupby("age4").sample_trips.sum()
    _check(
        bool((long_sample >= publication.MIN_SAMPLE_OBSERVATIONS).all()),
        "the long and unbanded trips of every age group rest on enough sample trips to publish",
    )
    _check(
        long_trips.share_of_km.idxmax() == "65+"
        and float(long_trips.loc["65+", "share_of_km"])
        > 2 * float(long_trips.loc[REFERENCE, "share_of_km"]),
        "the 65+ kilometres depend most on long and unbanded trips",
    )
    unknown_old = unknown_bounds[unknown_bounds.group == "65+"].involved_ratio
    _check(
        float(unknown_old.min()) < float(older_all.involved_ratio) < float(unknown_old.max()),
        "the 65+ ratio under the unknown-age bounds brackets the central figure",
    )
    # Involvement per km: young drivers above the middle-aged on every assumption, and the
    # highest of the four groups centrally; drivers aged 65 and over above them on the central
    # estimate, with a sensitivity range on both sides of 1, so no direction is claimed.
    _check(
        float(young.involved_ratio_low) > 2
        and float(ranges.loc["18-29", "min"]) > 1.2
        and central.involved_ratio.idxmax() == "18-29",
        "drivers aged 18-29 are involved more often per km than 45-64 on every assumption, and "
        "most often of the four groups centrally",
    )
    _check(
        1 < float(older_all.involved_ratio) < 1.35
        and float(older_all.involved_ratio_low) > 0.95
        and float(ranges.loc["65+", "min"]) < 1 < float(ranges.loc["65+", "max"]),
        "drivers aged 65 and over above 45-64 on the central estimate, but on either side of it "
        "under the alternatives, so the direction is not established",
    )
    # The kilometre total sets the level of the rates, never their ratios.
    _check(
        bool(
            central_rows.groupby("group")
            .involved_ratio.agg(lambda r: r.max() - r.min())
            .lt(1e-9)
            .all()
        ),
        "the other DGT kilometre totals change the rates but not the ratios",
    )
    # The sources of the sensitivity range, as the text describes them.
    profiles = variants[(variants.source == "regional profile") & (variants.group == "65+")]
    profiles = profiles.set_index("variant").involved_ratio
    distances = variants[(variants.source == "distance") & (variants.group == "65+")]
    distances = distances.set_index("variant").involved_ratio
    youngest = prevalence[prevalence.group == prevalence.group.min()]
    spain = youngest[youngest.place == "Spain"].set_index("sex").prevalence
    province = youngest[youngest.place != "Spain"].set_index("sex").prevalence
    _check(
        bool((province < spain.reindex(province.index)).all())
        and float(licence.loc["18-29", "involved_ratio"]) < float(young.involved_ratio),
        "young people in the province of Barcelona hold car licences less often than in Spain, "
        "so the licence-calibrated transfer lowers the young drivers' ratio",
    )
    _check(
        "Barcelona city" in profiles.idxmin() and "Madrid" in profiles.idxmax(),
        "for 65 and over the regional profiles run from Barcelona city's to the Madrid survey's",
    )
    _check(
        "unbanded trips left out" in distances.idxmax(),
        "for 65 and over, leaving out the trips with no distance band raises the ratio most",
    )
    _check(
        float(weekend["max"]) < float(older_all.involved_ratio),
        "a different age mix on weekends lowers the 65-and-over ratio",
    )
    _check(
        all(
            float(employed_survey.loc[y, "employed_share"]) < 1.2 * employed_census
            for y in early_years
        )
        and all(
            float(employed_survey.loc[y, "employed_share"]) > 1.3 * employed_census
            for y in late_years
        ),
        "the survey's employed share at 65+ matched the census in the earlier editions and "
        "exceeds it in the recent ones",
    )
    _check(
        employed_reweighted > float(older_all.involved_ratio)
        and float(professional["min"]) > float(older_all.involved_ratio)
        and float(older_all.involved_ratio) < composition_older <= float(ranges.loc["65+", "max"]),
        "the corrections for the survey's older respondents, and the bound on too few aged 75 "
        "and over in its sample, raise the 65-and-over ratio inside its range",
    )
    _check(
        float(weekend["max"]) < float(older_all.involved_ratio)
        and float(regional_old["min"]) < float(older_all.involved_ratio),
        "the weekend age mix and Barcelona city's profile lower the 65-and-over ratio",
    )
    _check(
        float(owner_same.loc["18-29", "ratio_to_reference"]) > float(young.involved_ratio) + 1
        and float(owner_same.loc["65+", "ratio_to_reference"]) < float(older_all.involved_ratio),
        "on the same age groups the owner kilometres put the young higher and 65+ lower",
    )
    # Deaths once involved: highest at 75 and over, and above 45-64 at both older ages.
    _check(
        float(severity.loc["75+", "killed_per_1000_involved_low"])
        > float(severity.loc[REFERENCE, "killed_per_1000_involved_high"])
        and float(severity.loc["65-74", "killed_per_1000_involved_low"])
        > float(severity.loc[REFERENCE, "killed_per_1000_involved_high"])
        and severity.killed_per_1000_involved.idxmax() == "75+",
        "drivers aged 65-74 and 75 and over die more often once involved than drivers aged "
        "45-64, and 75 and over most often",
    )
    killed_ratio_old = float(older_all.killed_ratio)
    _check(
        killed_ratio_old > 2 * float(older_all.involved_ratio)
        and float(killed_range["min"]) > float(ranges.loc["65+", "max"]),
        "older drivers' higher deaths per km come mainly from severity once involved, under "
        "every alternative",
    )
    # The clearest difference at older ages is the outcome once involved: the deaths-once-involved
    # ratio exceeds every involvement-per-km ratio at 65-74 and at 75 and over.
    _check(
        killed["75+"] / killed[REFERENCE] > older_range["75+"][1]
        and killed["65-74"] / killed[REFERENCE] > older_range["65-74"][1],
        "deaths once involved separate the older groups from 45-64 more than involvement per km",
    )
    # Barcelona's working-day check.
    _check(
        bool((city[city.age4 == "65+"].ratio_low < 1).all())
        and bool((city[city.age4 == "65+"].ratio_high > 1).all())
        and bool((city_young > 1.8).all()),
        "in Barcelona on working days, 65+ at about the 45-64 rate (every interval includes 1) "
        "and the young at about twice it or more",
    )
    _check(
        bool((on_duty.ratio_to_45_64 > city_older.reindex(on_duty.index)).all()),
        "leaving out the drivers recorded as on duty raises the older drivers' ratio in Barcelona",
    )
    # Ages 75 and over without kilometres: involvement per licence holder, below the 45-64 rate
    # even allowing for chance in the counts, and below every per-km ratio, so that every
    # assumption gives licence holders aged 75 and over fewer km than those aged 45-64.
    check = checks.set_index(["check", "subject"])
    per_holder = {
        group: float(
            check.loc[
                (national.CHECK_PER_HOLDER, group),
                "value",
            ]
        )
        for group in ("75+", "65-74", REFERENCE)
    }
    holder_ratio = check.loc[
        (
            national.CHECK_HOLDER_RATIO,
            "count-only 95% interval",
        )
    ]
    _check(
        float(holder_ratio.value) < 1
        and float(holder_ratio.high) < 1
        and older_range["75+"][0] > float(holder_ratio.value)
        and np.isclose(per_holder["75+"] / per_holder[REFERENCE], float(holder_ratio.value)),
        "drivers aged 75 and over are involved less often per licence holder than drivers aged "
        "45-64, and every per-km ratio is above that ratio",
    )
    # What supports the Madrid pattern, and what does not.
    prevalence_ratio = check.xs(national.CHECK_PREVALENCE, level="check").value
    places = ("province of Madrid", "province of Barcelona", "Spain")
    licence_fall = {
        sex: [float(prevalence_ratio[f"{place}, {sex}"]) for place in places]
        for sex in national.SEXES
    }
    transfer = check.xs(national.CHECK_TRANSFER, level="check").value
    like_for_like = check.xs(national.CHECK_MADRID_PER_HOLDER, level="check")
    men_madrid = like_for_like.loc["male"]
    women_madrid = like_for_like.loc["female"]
    trend_key = national.CHECK_LICENCE_TREND
    licence_trend = check.xs(trend_key, level="check").value
    composition_75 = older_variants[
        (older_variants.variant == national.COMPOSITION_VARIANT)
        & (older_variants.assumption == national.REFERENCE_SPLIT)
    ].ratio_75_plus.iloc[0]
    racc_limit = float(
        older_variants[
            older_variants.assumption == national.RACC_SPLIT
        ].men_km_per_holder_75_vs_65_74.iloc[0]
    )
    _check(
        all(max(v) - min(v) < 0.05 for v in licence_fall.values())
        and float(transfer[national.MADRID_METHOD]) < float(transfer[national.CENTRAL_METHOD])
        and float(men_madrid.high) < 1 < float(women_madrid.high)
        and float(women_madrid.low) < 1
        and bool((licence_trend > 1).all())
        and float(composition_75) > float(cond_75.ratio_to_45_64)
        and older_range["75+"][0] <= float(composition_75) <= older_range["75+"][1]
        and float(cond_75.men_km_per_holder_75_vs_65_74) < racc_limit < 1,
        "licence holding falls alike from 65-74 to 75+ in the three places while Madrid's older "
        "residents drive less than the transfer implies; Madrid's men drive less per licence "
        "holder at 75+ and its women's interval includes 1; licence holding at 75+ has risen "
        "since the Madrid survey; the composition bound raises the figure inside the range; the "
        "Madrid split's men's ratio is below the RACC limit, which is below 1",
    )
    # Barcelona's working-day check of the splits, with the counts behind it.
    city_split_75 = city_split[city_split.age == "75+"]
    city_madrid = city_split_75[city_split_75.assumption == national.REFERENCE_SPLIT]
    _check(
        float(city_75.min()) < 1 < float(city_75.max())
        and float(city_madrid.ratio_low.min()) < 1
        and set(city_split.assumption) == set(national.SPLITS)
        and int(city_split_75.drivers_involved.iloc[0]) < 200,
        "in Barcelona the four splits put 75 and over on both sides of the 45-64 rate, and the "
        "Madrid split's intervals reach below it, with few drivers aged 75 and over",
    )
    # The top of the range against the owner kilometres (a tension, not a test).
    _check(
        float(highest_75.driver_over_owner_km_75_plus)
        < float(highest_75.driver_over_owner_km_45_64),
        "at the top of the range drivers aged 75 and over drive a smaller share of their owner "
        "km than drivers aged 45-64",
    )
    _check(
        float(old_65.min()) > 0.8 and float(old_65.max()) < 1.2,
        "65-74 at about the 45-64 rate under the four splits",
    )

    men_involved = sex_ratios.loc[("car", "18+", "involved_per_1000_licences")]
    men_fatality = sex_ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    men_killed = sex_ratios.loc[("car", "18+", "deaths_per_million_licences")]
    motor_killed = sex_ratios.loc[("motor", "18+", "deaths_per_million_licences")]
    motor_fatality = sex_ratios.loc[("motor", "18+", "deaths_per_1000_involved")]
    car_bands = sex_ratios.xs("car", level="scope").drop(index="18+", level="band")
    per_km_involved = sex_km.loc["involved per km"]
    per_km_killed = sex_km.loc["killed per km"]
    _check(
        min(float(men_involved.low), float(men_fatality.low), float(men_killed.low)) > 1
        and float(men_fatality.ratio) > float(men_involved.ratio)
        and float(motor_killed.ratio) > float(men_killed.ratio)
        and float(motor_fatality.ratio) > float(men_fatality.ratio)
        and bool((car_bands.low > 1).all()),
        "men are higher than women per licence holder and once involved, on every measure in "
        "every band",
    )
    _check(
        float(per_km_involved.range_low) < 1 < float(per_km_involved.range_high)
        and float(per_km_involved.ratio_high) < float(men_involved.low)
        and float(per_km_involved.ratio_men_to_women) < 1
        and float(per_km_killed.range_low) > 1.5,
        "per km, neither sex is shown to be involved more often (the profiles span 1), while men "
        "are killed far more often; under the central profile men's higher involvement per "
        "licence holder comes from driving further",
    )
    _check(
        float(b_licence.loc["B-licence holders", "ratio"])
        > float(b_licence.loc["licence holders of any class", "ratio"]),
        "counting only car-licence holders makes the men's excess slightly larger",
    )

    def ci(row: pd.Series) -> str:
        return f"{float(row.low):.2f}–{float(row.high):.2f}"

    def spread(group: str) -> str:
        return _fmt_span(float(ranges.loc[group, "min"]), float(ranges.loc[group, "max"]))

    older_75 = _fmt_span(*older_range["75+"])
    full_75 = f"{older_range['75+'][0]:.2f} to {older_range['75+'][1]:.2f}"
    madrid_pattern = (
        "if people aged 75 and over drive as much less than those aged 65–74 as in Madrid in "
        f"{madrid_year}"
    )
    direction = {
        PASS: "Among the combinations tested, every one consistent with Spanish surveys of men's "
        "driving puts them above that rate, even allowing for sampling error, so the evidence "
        "points to more involvement per kilometre at 75 and over; how much more is not "
        "established.",
        INTERMEDIATE: "Among the combinations tested, every one consistent with Spanish surveys "
        "of men's driving puts them above that rate, but at the lowest of these sampling error "
        "alone could bring them down to it, so a higher rate per kilometre is not established "
        "under every assumption, and how much higher is not established.",
        FAIL: "Some combinations consistent with Spanish surveys of men's driving put them at or "
        "below that rate, so whether they are involved more or less often per kilometre is not "
        "established.",
    }[tier]
    body = summary(
        "No national source records how far drivers of each age drive, so involvement in "
        "crashes per kilometre is an estimate, built from a Barcelona-area survey of working "
        f"days that accounts for {_fmt_pct(survey_cover, 0)} of DGT's car kilometres. On that "
        f"estimate, car drivers aged 18–29 were involved in injury crashes in Spain in {year} "
        f"{float(young.involved_ratio):.2f} times as often per kilometre driven as drivers aged "
        f"45–64 (95% sampling interval {_ci(young, 'involved_ratio')}; sensitivity range, the "
        f"span across the assumptions tested, {spread('18-29')}), and more often under every "
        "assumption tested. Drivers aged 65 and over were involved "
        f"{float(older_all.involved_ratio):.2f} times as often (95% sampling interval "
        f"{_ci(older_all, 'involved_ratio')}; sensitivity range {spread('65+')}), so whether "
        "they are involved more or less often per kilometre is not established. For drivers "
        "aged 75 and over, whose kilometres no Spanish source separates from those at 65–74, the "
        f"sensitivity range is {full_75} times the 45–64 rate. {direction} "
        f"{madrid_pattern[:1].upper()}{madrid_pattern[1:]}, with the other assumptions as in the "
        "central estimate, they were involved about "
        f"{float(cond_75.ratio_to_45_64):.1f} times as often (95% sampling interval "
        f"{float(cond_75.ratio_low):.1f}–{float(cond_75.ratio_high):.1f}). What is counted "
        f"directly is the outcome once a crash happens: {killed['75+']:.1f} of every 1,000 car "
        "drivers aged 75 "
        "and over involved in an injury crash died within 30 days, against "
        f"{killed[REFERENCE]:.1f} at 45–64. Involvement counts every driver in a crash, "
        "whoever caused it, and the death rate only the driver's own death: no rate here shows "
        "who caused a crash or whether older drivers' crashes are more dangerous to others."
    )

    # ------------------------------------------------------------------- per kilometre
    body += (
        '<h2 id="involvement-in-crashes-per-kilometre-driven">'
        "Crashes per kilometre: above the 45–64 rate at 18–29; at 65 and over it depends on "
        "assumptions</h2>"
    )
    body += (
        "<p>No national source counts kilometres by the age of the driver, so they are estimated, "
        "and the ratios per kilometre are estimates with ranges, not measurements; the method "
        f'and its checks are set out in <a href="{EXPOSURE_DOC}">the exposure study</a>. The '
        "EMEF, the working-day mobility survey of the province of Barcelona, records the car "
        "trips its respondents drove on one working day, with each trip's duration and, from "
        f"{emef_variables.DISTANCE_FROM}, its straight-line distance in bands, from which each "
        f"trip's kilometres are estimated. Its {SURVEY_YEARS} editions give each age group's "
        "car-driver kilometres per resident, by sex. Applied to the population of Spain and "
        f"scaled to DGT's {YEAR} car kilometres from inspection odometer readings, less taxis and "
        "ride-hailing cars (whose drivers are outside both counts), they put "
        f"{_fmt_pct(float(a_share.loc['18-29', 'share_of_km']))} of car kilometres with drivers "
        f"aged 18–29, {_fmt_pct(float(a_share.loc['45-64', 'share_of_km']))} with 45–64 and "
        f"{_fmt_pct(float(a_share.loc['65+', 'share_of_km']))} with 65 and over. Over the "
        f"{working} working days of {year} (weekdays less public holidays), the survey's "
        f"driving comes to {_fmt_pct(survey_cover, 0)} of those kilometres. The central "
        "estimate gives the rest the same age mix; the tests below measure what the rest is made "
        "of and give it other age mixes. The drivers involved are DGT's count of private-car "
        f"drivers in injury crashes in {year}.</p>"
    )

    def to(low: float, high: float) -> str:
        return f"{low:.2f} to {high:.2f}"

    def alt_row(group: str) -> str:
        row = central.loc[group]
        return (
            f"{LABELS[group]}: {int(row.involved):,} involved; "
            f"{float(row.involved_ratio):.2f} times the 45–64 rate (95% sampling interval "
            f"{to(float(row.involved_ratio_low), float(row.involved_ratio_high))}; sensitivity "
            f"range {to(float(ranges.loc[group, 'min']), float(ranges.loc[group, 'max']))})"
        )

    body += figure(
        "dr1_involved_per_km",
        f"Dot chart of car drivers involved in injury crashes per kilometre in {year}, as ratios "
        "to drivers aged 45–64, on a log scale, with the number of drivers involved under each "
        f"age. {alt_row('18-29')}. {alt_row('30-44')}. 45–64: "
        f"{int(central.loc[REFERENCE, 'involved']):,} involved. {alt_row('65+')}. Of these, "
        f"65–74: {int(severity.loc['65-74', 'involved']):,} involved; "
        f"{float(cond_65.ratio_to_45_64):.2f} times the 45–64 rate per kilometre "
        f"{madrid_pattern.replace('those aged 65–74', '65–74s')} (95% sampling interval "
        f"{to(float(cond_65.ratio_low), float(cond_65.ratio_high))}); sensitivity range "
        f"{to(*older_range['65-74'])}, above about {clear['65-74'][1]:.2f} only with equal "
        "kilometres per licence holder at 65–74 and 75 and over. 75 and over: "
        f"{int(severity.loc['75+', 'involved']):,} involved; "
        f"{float(cond_75.ratio_to_45_64):.2f} times on the same assumption (95% sampling "
        f"interval {to(float(cond_75.ratio_low), float(cond_75.ratio_high))}); sensitivity "
        f"range {to(*older_range['75+'])}, below about {clear['75+'][0]:.1f} only with equal "
        "kilometres per licence holder.",
        captions,
    )
    body += _rates_table(central, ranges, level, year)
    body += (
        "<p>The 95% sampling interval reflects only sampling error in the survey and chance "
        "variation in "
        "the crash counts, and is probably too narrow, because its resampling of survey "
        "respondents does not reproduce every stage of the survey's sampling and weighting; the "
        "sensitivity range adds the other choices, set out in the table below. For drivers aged 18–29 the largest is which region's age profile stands in for "
        "Spain's "
        f"({_fmt_span(float(regional_young['min']), float(regional_young['max']))}). Carrying "
        "the survey's driving per licence holder rather than per resident to Spain gives "
        f"{float(licence.loc['18-29', 'involved_ratio']):.2f}, because young people in the "
        "province of Barcelona hold car licences less often than in Spain as a whole. For 65 "
        "and over the treatments of trip distances give "
        f"{_fmt_span(float(distance_old['min']), float(distance_old['max']))}, leaving out the "
        "long trips that have no distance band raising it most. This group is the most "
        "sensitive to them: trips of 100 km or more and trips with no distance band are "
        f"{_fmt_pct(float(long_trips.loc['65+', 'share_of_trips']))} of its trips but carry "
        f"{_fmt_pct(float(long_trips.loc['65+', 'share_of_km']), 0)} of its kilometres, against "
        f"{_fmt_pct(float(long_trips.loc[REFERENCE, 'share_of_km']), 0)} at 45–64. A different "
        "age mix on weekends "
        f"lowers it to {_fmt_span(float(weekend['min']), float(weekend['max']))}; and the "
        "regional profiles give "
        f"{_fmt_span(float(regional_old['min']), float(regional_old['max']))}, from Barcelona "
        "city's to the Madrid survey's.</p>"
    )
    dgt_low, dgt_high = float(dgt_regional.min()), float(dgt_regional.max())
    body += (
        "<p>The other half of DGT's kilometres is not measured by age, but most of it can be "
        "sized from the sources this site uses; the table below gives each part. Weekends and "
        f"public holidays, {non_working} days in {year}, add {share_span('non-working days')} "
        f"of DGT's total if each carries {_fmt_pct(national.NON_WORKING_RATIOS[0], 0)} to "
        f"{_fmt_pct(national.NON_WORKING_RATIOS[1], 0)} of a working day's driving; "
        f"{coverage_design.MOVILIA_DAILY} counted {weekend_trips:.2f} times as many car trips, "
        "drivers and passengers together, on an average weekend day as on a working day, and "
        f"weekend trips of all modes lasted {weekend_minutes:.2f} times as long. Spain drives "
        "more per resident than the province of Barcelona: "
        f"{float(regional.iloc[0]):.2f} times as many car trips per resident in "
        f"{coverage_design.MOVILIA_DAILY}, and {dgt_low:.2f} to {dgt_high:.2f} times "
        f"Catalonia's car kilometres per resident in DGT's {year} figures, which adds "
        f"{share_span('regional level')}. The work trips of people who drive for a living, "
        "which the survey counts but does not describe, add "
        f"{share_span(PROFESSIONAL_PART)}. Judged by fuel sales and toll-motorway traffic, the "
        "months outside the survey's fieldwork change the total by "
        f"{share_span('months outside the fieldwork')}. At their lowest these parts leave "
        f"{_fmt_pct(remainder[1], 0)} of DGT's total unexplained; at their highest they exceed "
        f"it by {_fmt_pct(-remainder[0], 0)}. Cars registered to companies "
        f"({_fmt_pct(part('cars registered to companies')[0], 0)} of the total) and hire cars "
        f"({_fmt_pct(part('car hire without driver')[0], 0)}) are driven within these parts, "
        "not beside them; hire cars also bound the driving that visitors from abroad do in "
        "Spanish cars.</p>"
    )
    body += technical("What DGT's kilometres are made of", _coverage_table(parts))
    body += (
        "<p>The central estimate gives all of these parts the survey's working-day age mix. To "
        "test that, the non-working days and the unexplained part, taken at its largest "
        f"({_fmt_pct(remainder[1], 0)} of the total), were given age mixes measured elsewhere: "
        "DGT's kilometres by the age of a car's private owner, car journeys over 50 km per "
        f"resident in {coverage_design.MOVILIA_LONG}, and the two weekend mixes. With the "
        f"survey's profile for the rest, these give {_span(alone.ratio_18_29)} at 18–29 and "
        f"{_span(alone.ratio_65_plus)} at 65 and over, inside the ranges of the other tests. "
        "Combined with another region's profile, the two largest uncertainties together, they "
        f"give {spread('18-29')} and {spread('65+')}, and the sensitivity range includes these "
        "combinations. Two allocations that no source supports are reported but left out of "
        "the range: the same kilometres per licence holder at every age "
        f"({_span(licence_bound.ratio_65_plus)} at 65 and over) and no driving at 65 and over "
        "in the unexplained part (up to "
        f"{float(under_65_bound.ratio_65_plus.max()):.2f}).</p>"
    )
    body += technical("Sources of the sensitivity range", _sources_table(by_source))
    body += (
        "<p>Further choices raise the 65-and-over ratio. The share of the survey's older "
        f"respondents in work was about {_fmt_pct(float(employed_survey.loc[early_years, 'employed_share'].mean()))} "
        f"in {min(early_years)}–{max(early_years)}, the same as the census for Catalonia, but "
        f"{_fmt_pct(float(employed_survey.loc[late_years, 'employed_share'].min()))} to "
        f"{_fmt_pct(float(employed_survey.loc[late_years, 'employed_share'].max()))} in "
        f"{SURVEY_YEARS}; setting it back to the census share moves the 65-and-over ratio from "
        f"{float(older_all.involved_ratio):.2f} to {employed_reweighted:.2f}. And the survey "
        "does not record the work trips of people who drive for a living, most of them under "
        "65: counting a quarter or a half of those trips as car trips raises the ratio to "
        f"{_fmt_span(float(professional['min']), float(professional['max']))}. If the "
        "survey's 65-and-over sample holds too few people aged 75 and over, who drive less, its "
        "65-and-over kilometres per resident are too high; at the bound described in the "
        f"section on ages 75 and over, the ratio rises to {composition_older:.2f}. The weekend "
        "age mix and Barcelona city's profile point the other way, so the evidence does not say "
        "in which direction the central figure errs.</p>"
    )
    # The former figure, compared like with like: change history, kept short.
    body += (
        "<p>Earlier versions of this page divided the same drivers, taxi and ride-hailing "
        "drivers included, by DGT's kilometres of cars registered to owners of each age, the "
        "only kilometres by age that DGT publishes. On the age groups used here, those owner "
        "kilometres put drivers aged 18–29 at "
        f"{float(owner_same.loc['18-29', 'ratio_to_reference']):.2f} times the 45–64 rate and "
        f"drivers aged 65 and over at {float(owner_same.loc['65+', 'ratio_to_reference']):.2f}, "
        f"against {float(young.involved_ratio):.2f} and {float(older_all.involved_ratio):.2f} "
        "here; the figure the page used to give, "
        f"{float(owner.loc['18-24', 'ratio_to_reference']):.2f}, compared drivers aged 18–24 "
        "with 35–54. A car's owner is often not its driver: young people drive cars registered "
        "to their parents, and older owners' cars are partly driven by others, so the owner "
        "kilometres credited too little driving to the young and too much to the old.</p>"
    )

    # ------------------------------------------------------------------- deaths once involved
    body += (
        '<h2 id="deaths-once-a-crash-has-happened">'
        "Deaths once a crash has happened: highest at 75 and over</h2>"
    )
    body += (
        "<p>This rate divides the car drivers killed within 30 days by all car drivers involved "
        "in injury crashes, injured or not, of the same age and year, so no measure of driving "
        "enters it. It counts only the driver's own death: DGT's tables do not say how often "
        f"other people in the same crashes died. In {year} it was {killed['18-29']:.1f} per "
        f"1,000 at 18–29, {killed['30-44']:.1f} at 30–44, {killed[REFERENCE]:.1f} at 45–64, "
        f"{killed['65-74']:.1f} at 65–74 and {killed['75+']:.1f} at 75 and over, about "
        f"{killed['75+'] / killed[REFERENCE]:.1f} times the 45–64 rate.</p>"
    )
    body += figure(
        "dr2_killed_per_involved",
        f"Dot chart of private-car drivers killed per 1,000 involved in an injury crash in {year}, "
        f"by age, with 95% intervals. The rate is {killed['18-29']:.1f} at 18–29, "
        f"{killed[REFERENCE]:.1f} at 45–64, {killed['65-74']:.1f} at 65–74 and "
        f"{killed['75+']:.1f} at 75 and over.",
        captions,
    )
    body += (
        "<p>Deaths per kilometre combine the two measures, so they carry the estimate of "
        "kilometres. On the central estimate, drivers aged 65 and over were killed "
        f"{killed_ratio_old:.2f} times as often per kilometre driven as drivers aged 45–64 (95% "
        f"sampling interval {_ci(older_all, 'killed_ratio')}; sensitivity range "
        f"{_fmt_span(float(killed_range['min']), float(killed_range['max']))}), while their "
        f"involvement per kilometre was {float(older_all.involved_ratio):.2f} times (sensitivity "
        f"range {spread('65+')}). Under every assumption tested the first ratio is above the "
        "second, so most of the excess in deaths per kilometre comes from how often a crash "
        "kills an older driver, not from how often older drivers are in crashes.</p>"
    )

    # ------------------------------------------------------------------- Barcelona
    city_span = _fmt_span(float(city_older.min()), float(city_older.max()))
    body += (
        '<h2 id="a-check-in-barcelona-city-on-working-days">'
        "Barcelona on working days: 65 and over at about the 45–64 rate</h2>"
    )
    body += (
        "<p>Inside Barcelona on working days, involvement per kilometre can be compared without "
        "carrying the survey to Spain or assuming anything about weekends. The Guàrdia Urbana's "
        f"{CITY_YEAR} records give the age of {_fmt_pct(1 - city_unknown_share)} of the car "
        "drivers involved in injury crashes in the city on working days, uninjured drivers "
        "included; the EMEF gives the kilometres the survey area's residents drove inside the "
        f"city on a working day in {SURVEY_YEARS}, counted over the "
        f"{day_calendar.days_in_year(CITY_YEAR)[day_calendar.WORKING_DAY]} working days of "
        f"{CITY_YEAR} (weekdays less the Catalan and Barcelona public holidays). The part of a "
        "trip into or out of the city that lies inside it cannot be measured, so the table "
        "gives three versions of the kilometres, and only the ratios between ages are read.</p>"
    )
    body += _barcelona_table(city)
    body += (
        "<p>Across the three versions, drivers aged 65 and over were involved at "
        f"{city_span} times the rate of drivers aged 45–64, each with a 95% interval that "
        f"includes 1, and drivers aged 18–29 at {_span(city_young)} times it. The crashes "
        "include drivers whose kilometres the survey does not count: people living outside the "
        "survey area, traffic passing through the city, and people driving ordinary cars for "
        "work. They are mostly of working age, so the older drivers' ratio is more likely "
        "biased down than up; leaving out the drivers recorded as on duty raises it to "
        f"{_span(on_duty.ratio_to_45_64)}. The ratios assume that the drivers with no recorded "
        "age follow the recorded mix; if all were aged 65 or over, the ratio for trips inside "
        f"the city would be {float(city_unknown_old.loc['65+']):.2f}.</p>"
    )

    # ------------------------------------------------------------------- 75 and over
    body += (
        '<h2 id="ages-75-and-over">75 and over: deaths once involved are counted; crashes per '
        "kilometre depend on how much less they drive</h2>"
    )
    body += evidence_note(
        "No source for Spain measures how far drivers aged 75 and over drive apart from those "
        "aged 65–74. The rates per kilometre below rest on an assumption about how the "
        "65-and-over kilometres divide between the two ages: one is given as a conditional "
        "estimate, the others in the sensitivity range. The counts, the rates per licence holder "
        "and the deaths once involved need no kilometres."
    )
    oldest_counts = severity.loc["75+"]
    body += (
        f"<p><strong>Counted.</strong> In {year}, "
        f"{int(oldest_counts.involved):,} car drivers aged 75 and over and "
        f"{int(severity.loc['65-74', 'involved']):,} aged 65–74 were involved in injury crashes "
        f"in Spain, and {int(oldest_counts.killed):,} and "
        f"{int(severity.loc['65-74', 'killed']):,} of them died within 30 days: "
        f"{killed['75+']:.1f} and {killed['65-74']:.1f} per 1,000 involved, against "
        f"{killed[REFERENCE]:.1f} at 45–64 (Figure {figure_ref('dr2_killed_per_involved')}). "
        "These figures say how often a crash kills the driver. They do not say how often "
        "drivers of these ages are in crashes for the distance they drive, or who caused the "
        f"crashes. Per 1,000 holders of a car licence, {per_holder['75+']:.2f} drivers aged 75 "
        f"and over were involved, against {per_holder['65-74']:.2f} at 65–74 and "
        f"{per_holder[REFERENCE]:.2f} at 45–64. Many licence holders aged 75 and over drive "
        "little or not at all, so these are not rates per driver. Every estimate per kilometre "
        f"below is higher than the ratio of these rates, {float(holder_ratio.value):.2f}, "
        "because under every assumption tested licence holders aged 75 and over drive fewer "
        "kilometres than those aged 45–64.</p>"
    )
    body += (
        "<p><strong>Conditional estimate.</strong> The EMEF's public files group everyone aged "
        "65 and over, although the survey sampled 65–74 and 75 and over separately until "
        f"{emef_variables.OLDER_STRATA_LAST}. Madrid's {madrid_year} household travel survey "
        "records exact ages: there, residents aged 75 and over drove "
        f"{float(madrid.loc['75+', 'ratio_75_to_65_74_male']):.2f} times the car distance per "
        "resident of those aged 65–74 if men and "
        f"{float(madrid.loc['75+', 'ratio_75_to_65_74_female']):.2f} times if women. If people "
        f"aged 75 and over in Spain in {year} drive as much less as in Madrid, with the other "
        "assumptions as in the central estimate, drivers aged 75 and over were involved in injury "
        "crashes "
        f"{float(cond_75.ratio_to_45_64):.2f} times as often per kilometre as drivers aged 45–64 "
        f"(95% sampling interval {_ci(cond_75, 'ratio')}), and drivers aged 65–74 "
        f"{float(cond_65.ratio_to_45_64):.2f} times ({_ci(cond_65, 'ratio')}). The interval "
        "allows for sampling error in both surveys and chance in the crash counts, and may be "
        "too narrow or too wide because neither survey's resampling reproduces every stage of "
        "its design; it holds the assumption fixed. Under the other assumptions tested the "
        f"figure for 75 and over runs from {full_75} (the sensitivity range, below).</p>"
    )
    places_text = {
        sex: ", ".join(f"{v:.2f}" for v in values) for sex, values in licence_fall.items()
    }
    body += technical(
        "Why this assumption, and what could move it",
        "<ul>"
        "<li>It is the only split that uses kilometres measured by exact age without a bridge "
        "between two definitions of a licence holder.</li>"
        "<li>Car-licence holding falls about equally from 65–74 to 75 and over in the province "
        "of Madrid, the province of Barcelona and Spain (holders per resident at 75 and over "
        f"against 65–74, DGT, {year}: men {places_text['male']}; women "
        f"{places_text['female']}). That is consistent with the assumption but does not test "
        "it: Madrid's residents aged 65 and over drive much less, relative to those aged 45–64, "
        "than the Barcelona-area survey's "
        f"({float(transfer[national.MADRID_METHOD]):.2f} against "
        f"{float(transfer[national.CENTRAL_METHOD]):.2f} times as far per resident on working days).</li>"
        "<li>Some evidence points lower: licence holding at 75 and over has risen since "
        f"{madrid_year}, and surveys in other European countries show a gentler fall in driving "
        f'after 75 (see <a href="{EXPOSURE_DOC}">the exposure study</a>).</li>'
        "<li>Some points higher: the Barcelona-area survey's weighting does not separate 75 and "
        "over within 65 and over, so its 65-and-over sample may hold too few people aged 75 and "
        f"over; at the most this would raise the figure to about {float(composition_75):.2f}, a "
        "case included in the sensitivity range.</li>"
        "<li>Which way the figure errs is not known.</li>"
        "</ul>",
    )
    body += (
        "<p><strong>Across the assumptions.</strong> Four splits of the 65-and-over kilometres "
        "were tested: Madrid's, used for the estimate; Madrid's kilometres per licence holder "
        "applied to Spain's licence holders; an upper limit for men from the number of days "
        "they drive, with women driving as far per licence holder at 75 and over as at 65–74; "
        "and equal kilometres per licence holder at 65–74 and 75 and over. Combined with every "
        "alternative for the 65-and-over kilometres (other regions' age profiles, trip "
        "distances, survey years, work driving, the older respondents' employment and age mix, "
        "weekend mixes and the age mixes of the kilometres the survey does not cover), they give "
        f"a sensitivity range of {full_75} at 75 and over and "
        f"{to(*older_range['65-74'])} at 65–74. A sensitivity range is not an interval: it "
        "carries no probability, and it is not a limit, because choices varied here one at a "
        "time are not combined with each other, which would move both ends. The split with "
        "equal kilometres per licence holder stays in the range, unlike the two allocations of "
        "the uncovered kilometres described above that no source supports: it was part of the "
        "range as first published, women's driving does not rule it out, and the evidence "
        "against it for men comes from regional or dated surveys rather than a national measure "
        "of kilometres.</p>"
    )
    body += _older_table(
        older,
        older_variants,
        older_75,
        f"In Madrid in {madrid_year} men aged 75 and over drove {float(men_madrid.value):.2f} "
        f"times ({float(men_madrid.low):.2f}–{float(men_madrid.high):.2f}) as far per "
        "car-licence holder as men aged 65–74.",
    )
    whole = decomposition[decomposition.kind == "all"].iloc[0]
    shown = decomposition[decomposition.kind == "factor"].head(figures_module.DR3_FACTORS)
    bars = "; ".join(
        f"{row.short_label.lower()} {to(float(row.low), float(row.high))}"
        for row in shown.itertuples()
    )
    body += figure(
        "dr3_older_range_sources",
        "Bar chart, on a log scale, of the ratio of involvement per kilometre at 75 and over to "
        "45–64 when one choice at a time changes, the others as in the Madrid-pattern estimate "
        f"({float(whole.estimate):.2f}). All combinations tested: {to(whole.low, whole.high)}, "
        f"the part below {float(whole.clear_low):.2f} reached only with equal kilometres per "
        f"licence holder. One choice changed: {bars}.",
        captions,
    )
    _check(
        np.isclose(float(whole.low), older_range["75+"][0])
        and np.isclose(float(whole.high), older_range["75+"][1])
        and np.isclose(float(whole.clear_low), clear["75+"][0])
        and np.isclose(float(whole.estimate), float(cond_75.ratio_to_45_64)),
        "Figure 3's top bar is the sensitivity range and its line the conditional estimate",
    )
    racc = older_variants[older_variants.assumption == national.RACC_SPLIT]
    if tier == INTERMEDIATE:
        sampling = (
            f"Its 95% sampling interval, {float(lowest_clear.ratio_low):.2f}–"
            f"{float(lowest_clear.ratio_high):.2f}, reaches the 45–64 rate, so a higher rate per "
            "kilometre at 75 and over is not established under every assumption, and how much "
            "higher is not established."
        )
    elif tier == PASS:
        sampling = (
            f"Its 95% sampling interval, {float(lowest_clear.ratio_low):.2f}–"
            f"{float(lowest_clear.ratio_high):.2f}, stays above the 45–64 rate, so among the "
            "combinations tested the evidence points to more involvement per kilometre at 75 and "
            "over; how much more is not established."
        )
    else:
        sampling = (
            "It is at or below the 45–64 rate, so whether drivers aged 75 and over are involved "
            "more or less often per kilometre is not established."
        )
    body += (
        f"<p>Below about {clear['75+'][0]:.1f} the sensitivity range is reached only with "
        "equal kilometres per licence holder at 65–74 and 75 and over, which assumes men aged "
        "75 and over with a car licence drive as far as men aged 65–74 with one. Spanish "
        f"surveys of men's driving show them driving less: in Madrid in {madrid_year}, "
        f"{float(men_madrid.value):.2f} times as far per licence holder (95% sampling interval "
        f"{float(men_madrid.low):.2f}–{float(men_madrid.high):.2f}); in RACC's survey of "
        f"licence holders aged 65 and over, published in {national.RACC_YEAR}, on at most about "
        f"{racc_limit:.2f} times as many days. Surveys of women's driving are too uncertain to "
        "say the same for them. These combinations stay in the sensitivity range and are "
        f"hatched in Figures {figure_ref('dr1_involved_per_km')} and "
        f"{figure_ref('dr3_older_range_sources')}. Among the other combinations tested, the "
        f"lowest, about {clear['75+'][0]:.1f}, combines Barcelona city's age profile, weekend "
        "age mixes for the kilometres outside the survey's working days and the RACC limit; "
        f"this edge is set by that limit. {sampling} At the top, {older_range['75+'][1]:.2f}, "
        "drivers aged 75 and over would drive "
        f"{_fmt_pct(float(highest_75.driver_over_owner_km_75_plus), 0)} of the kilometres DGT "
        "records for cars registered to owners of that age, against "
        f"{_fmt_pct(float(highest_75.driver_over_owner_km_45_64), 0)} at 45–64; owner figures "
        "cannot say who drove, so this is noted, not counted against it.</p>"
    )
    _check(
        float(racc.ratio_75_plus.min()) == clear["75+"][0]
        or np.isclose(float(racc.ratio_75_plus.min()), clear["75+"][0]),
        "the lowest unmarked combination uses the RACC limit",
    )
    madrid_intervals = ", ".join(
        f"{float(row.ratio_low):.2f}–{float(row.ratio_high):.2f}"
        for row in city_madrid.itertuples()
    )
    body += (
        "<p>In Barcelona's working-day check, with no transfer to Spain (the 65-and-over "
        "kilometres are still divided by each split), the four splits give "
        f"{_span(city_75)} at 75 and over across the three ways of counting trips that cross "
        f"the city boundary. With {int(city_split_75.drivers_involved.iloc[0])} drivers aged 75 "
        "and over, each figure has a wide 95% sampling interval (for the Madrid split, "
        f"{madrid_intervals}), so the check neither confirms nor rules out a rate above the "
        "45–64 rate.</p>"
    )
    body += (
        "<p>Drivers who drive few kilometres, at any age, tend to have more crashes per "
        "kilometre, partly because more of their driving is on streets with junctions and less "
        "on motorways, so a higher rate per kilometre at 75 and over would not by itself show "
        "that age makes driving less safe. These rates are averages over everyone of an age who "
        "drives and say nothing about any one driver. They count involvement in injury crashes, "
        "whoever caused them; responsibility is not measured. The higher deaths once involved "
        "are counted and do not depend on any of these assumptions. The Madrid survey data are "
        "reused under the open-data licence of the Consorcio Regional de Transportes de Madrid. "
        f'<a href="{CRTM_URL}">Powered by CRTM</a>.</p>'
    )
    previous = older[older.assumption == national.REFERENCE_SPLIT].set_index("group").loc["75+"]
    body += (
        f"<p>Changed in {national.OLDER_ESTIMATE_CHANGED}: this section previously said "
        "involvement per kilometre at 75 and over was not established and gave no figure; it "
        "now gives a conditional estimate beside the sensitivity range. The Madrid-split "
        f"interval, previously {float(previous.ratio_low_split_fixed):.2f}–"
        f"{float(previous.ratio_high_split_fixed):.2f}, now includes the Madrid survey's own "
        f"sampling error ({_ci(previous, 'ratio')}). A fourth split and the hatching of "
        "combinations at odds with men's driving were added.</p>"
    )

    # ------------------------------------------------------------------- men and women
    body += (
        '<h2 id="men-and-women">'
        "Men and women: no clear difference in crashes per kilometre, more deaths among men</h2>"
    )
    body += (
        "<p>The survey's kilometres can be split by sex and carried to Spain in the same way as "
        f"by age. On that estimate men drove {_fmt_pct(float(per_km_involved.men_share_of_km))} "
        f"of car kilometres in {year}. Per kilometre, male private-car drivers aged 18 and over "
        f"were involved in injury crashes {float(per_km_involved.ratio_men_to_women):.2f} times "
        f"as often as female drivers (95% sampling interval {ci_km(per_km_involved)}), but across the "
        "regional profiles that ratio runs from "
        f"{_fmt_span(float(per_km_involved.range_low), float(per_km_involved.range_high)).replace('–', ' to ')}, "
        "so neither sex is shown to be involved more often per kilometre. Men were killed "
        f"{float(per_km_killed.ratio_men_to_women):.2f} times as often (95% sampling interval "
        f"{ci_km(per_km_killed)}; sensitivity range "
        f"{_fmt_span(float(per_km_killed.range_low), float(per_km_killed.range_high))}). Per "
        f"licence holder, pooling {sex_years}, men were involved "
        f"{float(men_involved.ratio):.2f} times as often as women (95% interval "
        f"{ci(men_involved)}) and, once involved, died {float(men_fatality.ratio):.2f} times as "
        f"often ({ci(men_fatality)}); combined, they died at the wheel "
        f"{float(men_killed.ratio):.2f} times as often ({ci(men_killed)}). Under the central "
        "profile, men's higher involvement per licence holder comes from their driving further; "
        "their higher death rate holds per kilometre under every profile and, in every age band, "
        "once a crash has happened.</p>"
    )
    body += figure(
        "a3_sex_ratios",
        f"Ratios of men's to women's rates for private-car drivers, {sex_years}, overall and by "
        "age band: involvement in injury crashes per licence holder, deaths per licence holder, "
        "and deaths per driver involved. Men's rates are above women's on all three measures "
        f"in every age band; at 18 and over men were involved {float(men_involved.ratio):.2f} "
        f"times as often, killed {float(men_killed.ratio):.2f} times as often per licence "
        f"holder and {float(men_fatality.ratio):.2f} times as often once involved.",
        captions,
    )
    body += (
        "<p>Across all motor-vehicle drivers, which adds motorcyclists, moped riders, the drivers "
        "of vans, trucks and buses and other motor vehicles, the gaps are wider: men died "
        f"{float(motor_killed.ratio):.2f} times as often as women per licence holder and "
        f"{float(motor_fatality.ratio):.2f} times as often once involved. The licence holders "
        "are holders of any class of licence. The census gives car-licence holders by sex and "
        f"age for {str(b_licence.years.iloc[0]).replace('-', '–')} only; counting only them "
        "raises the ratio of men's to women's deaths per licence holder in those years from "
        f"{float(b_licence.loc['licence holders of any class', 'ratio']):.2f} to "
        f"{float(b_licence.loc['B-licence holders', 'ratio']):.2f}.</p>"
    )
    body += technical("Detailed counts by sex", _sex_rates_table(sex_rates, sex_years))

    body += limitation(
        "The kilometres by age and sex are estimates transferred from one region's working-day "
        "survey; DGT describes its kilometre totals as valid only in aggregate. The crash counts "
        "include foreign and unlicensed drivers. Drivers whose age the tables do not record "
        f"({_fmt_pct(unknown_share)} of those involved) are left out of every rate, which lowers "
        "each absolute rate by that share; the ratios assume their ages follow the recorded mix "
        f"(if all were aged 18–29, the young drivers' ratio would be {unknown_young:.2f}; "
        "assigned to any one age group, they would put the ratio for 65 and over between "
        f"{_fmt_span(float(unknown_old.min()), float(unknown_old.max())).replace('–', ' and ')})."
    )
    body += downloads(
        [
            (
                "risk_national_rates",
                "involvement and deaths per km by age, every method and kilometre total",
            ),
            ("risk_national_sensitivity", "the ratios under every alternative choice"),
            ("risk_national_shares", "share of car kilometres by age, every method"),
            ("risk_national_numerator", "drivers involved and killed by age"),
            ("risk_weekend_sensitivity", "the ratios under other weekend and holiday age mixes"),
            ("risk_coverage", "the coverage of DGT's kilometres: what they are made of"),
            ("risk_coverage_evidence", "the evidence behind the coverage of DGT's kilometres"),
            ("risk_coverage_mixes", "age mixes for the kilometres the survey does not cover"),
            (
                "risk_coverage_scenarios",
                "the ratios under every age mix for those kilometres, with each profile",
            ),
            ("risk_licence_prevalence", "car-licence holders per resident, Spain and province"),
            ("emef_employment_benchmark", "survey's employed share at 65 and over"),
            ("risk_owner_age_comparison", "owner-age against driver-age kilometres"),
            ("q7_km_by_owner_age", "DGT kilometres by owner age"),
            ("risk_severity_and_licences", "deaths once involved, by age"),
            ("risk_barcelona_rates", "Barcelona working days, three versions of the kilometres"),
            ("risk_barcelona_day_type", "Barcelona crashes by type of day"),
            ("risk_older_split", "65–74 and 75 and over under the four splits"),
            (
                "risk_older_sensitivity",
                "65–74 and 75 and over under every alternative, with what each row implies",
            ),
            ("risk_older_extremes", "sampling intervals at the ends of the 75+ range"),
            ("risk_older_decomposition", "what moves the 75+ figure, one choice at a time"),
            ("risk_older_reference_checks", "the checks the 75+ estimate is read against"),
            ("emef_routing_older", "the survey's 65+ sample: share identified as aged 75+"),
            ("risk_barcelona_older", "65–74 and 75 and over in Barcelona"),
            ("edm_older_split", "Madrid survey: driving at 65–74 and at 75 and over"),
            ("risk_sex_per_km", "men against women per km"),
            ("drivers_sex_ratios", "men against women per licence holder and once involved"),
            ("drivers_sex_rates", "rates by sex and age"),
            ("drivers_sex_b_licence", "men against women per car-licence holder"),
            ("drivers_sex_trend", f"rates by sex and year, {trend_years}"),
        ],
        method=(EXPOSURE_DOC, "how the kilometres by age were estimated"),
    )
    return render_page(
        "drivers",
        "Driver age and sex",
        "How often car drivers of each age are involved in injury crashes for the distance they "
        "drive, how often a crash kills them, and how men and women compare.",
        body,
    )


def ci_km(row: pd.Series) -> str:
    return f"{float(row.ratio_low):.2f}–{float(row.ratio_high):.2f}"
