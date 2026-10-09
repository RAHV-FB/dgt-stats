"""Driver age and sex: how often car drivers are involved in crashes for the distance they drive,
and how often a crash kills the driver.

The page states the results and the qualification each needs: involvement per kilometre by age,
an estimate printed with its sampling interval and sensitivity range; for drivers aged 75 and
over, the sensitivity range beside the conditional estimate and the assumption it rests on;
deaths once involved, which need no kilometres; and men against women. ``technical_notes`` gives
the methodology page the rest: how the kilometres by age were estimated from the EMEF working-day
survey, Spain's population and DGT's car kilometres (``scripts/exposure_risk.py``;
``docs/research/DRIVER_AGE_EXPOSURE.md``), what DGT's kilometres are made of and what the
sensitivity range spans, deaths per kilometre, the check in Barcelona on working days, men and
women per licence holder, the former owner-age figure, and the split at 75 and what moves it.

Every number is read from the ``risk_*`` and ``drivers_sex_*`` tables, and every sentence of the
page and its notes is checked against them (``_facts``) before either is written.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from dgt_stats import edm2018
from dgt_stats.emef import exposure, publication
from dgt_stats.emef import variables as emef_variables
from dgt_stats.exposure_risk import barcelona as city_design
from dgt_stats.exposure_risk import calendar as day_calendar
from dgt_stats.exposure_risk import coverage as coverage_design
from dgt_stats.exposure_risk import national
from dgt_stats.site.components import (
    DOCS_URL,
    _fmt_dec,
    _fmt_pct,
    _join,
    definition_link,
    downloads,
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
    MC_MARGIN,
    OLDER_CONCLUSION,
    PASS,
    _driver_numbers,
    _older_numbers,
    _sex_numbers,
    joint_interval,
    mc_digits,
    mc_interval,
    rate_interval,
    side_of_one_shown,
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
# The sections of the methodology page that hold this page's technical notes.
NOTES_ANCHOR = "drivers-per-km"
OLDER_NOTES_ANCHOR = "drivers-75-and-over"

# The opening's one clause on the older groups, in the words each wording tier allows; the section
# on ages 75 and over gives the tier's full wording (``OLDER_CONCLUSION``) beside the range.
SUMMARY_OLDER = {
    PASS: "for drivers aged 65 and over a difference is not established, while at 75 and over "
    "every combination tested that agrees with surveys of men's driving puts them above the "
    "45–64 rate",
    INTERMEDIATE: "for drivers aged 65 and over, and 75 and over, a higher rate is not established",
    FAIL: "for drivers aged 65 and over, and 75 and over, a higher or lower rate is not "
    "established",
}


def _check(holds: bool, claim: str) -> None:
    if not holds:
        raise ValueError(f"drivers page: the tables no longer support: {claim}")


def _ci(row: pd.Series, column: str, sep: str = "–") -> str:
    """A ratio's sampling interval from ``risk_national_rates``, at the precision its Monte Carlo
    error supports."""
    return rate_interval(row, column, sep)


# The closed sections of the technical notes that their text sends readers to, with their ids.
SOURCES_TITLE, SOURCES_ANCHOR = (
    "Sources of the sensitivity range",
    "sources-of-the-sensitivity-range",
)
COVERAGE_TITLE, COVERAGE_ANCHOR = "What DGT's kilometres are made of", "what-dgts-kilometres"


NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")


def _words(number: int) -> str:
    """A count under ten in words, as in running prose."""
    return NUMBER_WORDS[number] if 0 <= number < len(NUMBER_WORDS) else f"{number:,}"


def _open_link(anchor: str, label: str) -> str:
    """A pointer to a closed section of technical detail further down the notes."""
    return f'open “<a href="#{anchor}">{label}</a>” below'


def _span(values: pd.Series) -> str:
    return f"{float(values.min()):.2f}–{float(values.max()):.2f}"


def _to(low: float, high: float) -> str:
    return f"{low:.2f} to {high:.2f}"


def _ci95(row: pd.Series) -> str:
    """A 95% interval of a ratio of men's to women's rates per licence holder (a formula's)."""
    return f"{float(row.low):.2f}–{float(row.high):.2f}"


RATE_COARSEST = -2  # rates per billion km may be rounded to tens, never to thousands
DIGIT_WORDS = {2: "two decimals", 1: "one decimal", 0: "whole numbers", -1: "tens"}


def _mc_errors(rows: pd.DataFrame, column: str) -> float:
    """The largest Monte Carlo standard error of the interval ends of ``column`` in ``rows``."""
    return float(rows[[f"{column}_mc_se_low", f"{column}_mc_se_high"]].max().max())


def _precision_rule(central: pd.DataFrame) -> str:
    """The one statement of how the sampling intervals are printed, with the Monte Carlo errors
    of the ratios and rates of the table of rates and of the death ratios quoted with them."""
    shown = central.loc[[group for group in GROUPS if group != REFERENCE]]
    involved = _mc_errors(shown, "involved_ratio")
    killed = _mc_errors(shown, "killed_ratio")
    rate_digits = sorted(
        {
            mc_digits(
                row.involved_per_bn_km_mc_se_low,
                row.involved_per_bn_km_mc_se_high,
                coarsest=RATE_COARSEST,
            )
            for row in central.itertuples()
        },
        reverse=True,
    )
    each = sorted(
        {
            mc_digits(getattr(row, f"{c}_mc_se_low"), getattr(row, f"{c}_mc_se_high"))
            for row in shown.itertuples()
            for c in ("involved_ratio", "killed_ratio")
        },
        reverse=True,
    )
    _check(
        0 < involved < 0.05 and 0 < killed < 0.05 and min(each) >= 1,
        "the ratios' interval ends move by less than 0.05 between resamples, so they keep one "
        "decimal at least",
    )
    rates = " or ".join(DIGIT_WORDS[d] for d in rate_digits)
    return (
        "How every sampling interval of driver age is printed: it comes from resampling the "
        "surveys and the crash counts, and another set of resamples would move its ends "
        "slightly, so both ends are printed to the last digit that the larger of their Monte "
        "Carlo standard errors supports, a unit at least twice that error. Here the ratios' ends "
        f"carry errors of up to {involved:.3f} for involvement and {killed:.3f} for deaths per "
        f"kilometre, so the ratios' intervals are given to "
        f"{' or '.join(DIGIT_WORDS[d] for d in each)}, as each row's error allows; the "
        f"rates' ends carry errors of up to {_mc_errors(central, 'involved_per_bn_km'):.1f} per "
        f"billion km, so they are given to {rates}, as each row's error allows. One exception: "
        "an interval that lies wholly on one side of 1 but would print as reaching it, with its "
        f"nearer end {_words(MC_MARGIN)} Monte Carlo errors clear of 1, gets a second decimal, "
        "so that it is not read as touching 1. No sentence on "
        "the drivers page or here rests on which side of 1 an end lies unless the printed end "
        f"shows it and stands {_words(MC_MARGIN)} Monte Carlo errors clear of 1. The 95% "
        "intervals of men against women per licence holder come from a formula, not from "
        "resampling."
    )


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
                    f"({rate_interval(row, 'involved_per_bn_km', coarsest=RATE_COARSEST)})"
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
        "intervals combine a bootstrap of the survey (the bootstrap replicates are not "
        "published) with Poisson error in the crash counts, "
        f"{national.COUNT_DRAWS} draws of each count for every replicate. "
        f"{_precision_rule(central)} The sensitivity range spans "
        f"every alternative in the closed section “{SOURCES_TITLE}” below. Data: "
        "the rows of the CSV of involvement and deaths per km by "
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
        "of ratios under every alternative; the sensitivity range in the table of rates above is "
        "the span of all of them.",
    )


PROFESSIONAL_PART = "professionals' work driving"
COVERAGE_LABELS = {
    "working days": ("Working days, as the survey measures them", "survey's working days"),
    PROFESSIONAL_PART: (
        "Work trips of people who drive for a living, counted but not described by the survey",
        "survey's working days; their own age mix tested",
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
        "survey's working days; three other measured mixes tested, three bounds reported",
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
                else f"{value.ratio_to_45_64:.2f} ({joint_interval(value)})"
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


def _older_table(
    older: pd.DataFrame, variants: pd.DataFrame, full: str, madrid: str, like_for_like: float
) -> str:
    labels = national.public_split_labels()
    oldest = older[older.group == "75+"].set_index("assumption")
    men = oldest.men_km_per_holder_75_vs_65_74
    ratio = oldest.ratio_to_45_64
    _check(
        np.isclose(float(men[national.LICENCE_SPLIT]), like_for_like)
        and abs(float(ratio[national.LICENCE_SPLIT]) / float(ratio[national.REFERENCE_SPLIT]) - 1)
        < 0.05
        and float(ratio[national.RACC_SPLIT]) < float(ratio[national.REFERENCE_SPLIT]),
        "the licence split implies Madrid's own men's ratio per DGT licence holder and gives "
        "nearly the Madrid split's figure, and the RACC upper limit on men's km gives a lower "
        "involvement ratio",
    )
    rows = []
    for split in national.SPLITS:
        part = older[older.assumption == split].set_index("group")
        spread = variants[variants.assumption == split].ratio_75_plus
        rows.append(
            {
                "Split of the 65-and-over kilometres": labels[split],
                "75 and over: ratio to 45–64 (95% sampling interval)": (
                    f"{part.loc['75+', 'ratio_to_45_64']:.2f} ({joint_interval(part.loc['75+'])})"
                ),
                "75 and over: sensitivity range under this split": _span(spread),
                "65–74: ratio (95% sampling interval)": (
                    f"{part.loc['65-74', 'ratio_to_45_64']:.2f} "
                    f"({joint_interval(part.loc['65-74'])})"
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
        f"{madrid} The second row carries Madrid's kilometres per licence holder, with holders "
        f"counted on DGT's {YEAR} register in the province of Madrid and in Spain alike, to "
        "Spain's licence holders; licence holding falls about as much from 65–74 to 75 and over "
        "in the province of Madrid as in Spain, so it gives nearly the figures of the first. The "
        "third row's upper limit is on men's kilometres, so it gives a lower ratio of "
        "involvement.",
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


def ci_km(row: pd.Series) -> str:
    """The sampling interval of a ratio of men's to women's rates per km, at the precision its
    Monte Carlo error supports."""
    return joint_interval(row)


def _share_table(share_of_km: dict[str, pd.Series]) -> str:
    """Each age group's share of Spain's car kilometres under each survey and the average."""
    rows = [
        {
            "Age": LABELS[group],
            "Barcelona-area survey": _fmt_pct(float(share_of_km[national.BARCELONA_METHOD][group])),
            "Madrid survey": _fmt_pct(float(share_of_km[national.MADRID_METHOD][group])),
            "Average (used)": _fmt_pct(float(share_of_km[national.CENTRAL_METHOD][group])),
        }
        for group in GROUPS
    ]
    return table(
        pd.DataFrame(rows),
        "Share of car kilometres in Spain by the driver's age, from each survey's profile and "
        "their average, weekdays",
    )


def _moves_table(whole: pd.Series, one_choice: pd.DataFrame) -> str:
    """What moves the 75+ figure: the whole range, then each choice varied on its own."""
    rows = [
        {
            "What changes": str(whole.short_label),
            "Involvement per km at 75 and over, against 45–64": _to(
                float(whole.low), float(whole.high)
            ),
        }
    ]
    rows += [
        {
            "What changes": str(row.short_label),
            "Involvement per km at 75 and over, against 45–64": _to(
                float(row.low), float(row.high)
            ),
        }
        for row in one_choice.itertuples()
    ]
    return table(
        pd.DataFrame(rows),
        "What moves the figure for drivers aged 75 and over: every combination tested, then each "
        "choice changed on its own from the Barcelona profile with Madrid's split "
        f"({float(whole.estimate):.2f}). A row's span depends on which alternatives were tried, "
        "not on how likely they are, and carries no sampling error.",
    )


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the tables, with the checks
    that the sentences built on them still hold."""
    numbers = _driver_numbers()
    # ``central`` is the published estimate (the average of the Barcelona and Madrid profiles);
    # ``barcelona`` is Method A, from which the sensitivity analysis varies one choice at a time.
    central, licence = numbers["central"], numbers["licence"]
    barcelona = numbers["barcelona"]
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
    bcn_75 = oldest_numbers["barcelona_conditional"].loc["75+"]
    clear = oldest_numbers["clear"]
    lowest_clear = oldest_numbers["lowest_clear"]
    checks = read_table("risk_older_reference_checks")
    decomposition = read_table("risk_older_decomposition")
    madrid_year = edm2018.SURVEY_YEAR

    young, older_all = central.loc["18-29"], central.loc["65+"]
    bcn_young, bcn_older_all = barcelona.loc["18-29"], barcelona.loc["65+"]
    share_of_km = {
        method: shares[shares.method == method].set_index("group").share_of_km
        for method in (national.BARCELONA_METHOD, national.MADRID_METHOD, national.CENTRAL_METHOD)
    }
    by_older = older.set_index(["assumption", "group"])
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
    alone = credible[credible.profile == national.BARCELONA_METHOD]
    others = variants[
        ~variants.source.isin([national.COVERAGE_SOURCE, national.COVERAGE_PROFILE_SOURCE])
    ]
    other_ranges = others.groupby("group").involved_ratio.agg(["min", "max"])
    # The bounds with every profile, the basis on which the notes quote all three.
    every_bound = {mix: scenarios[scenarios.remainder_mix == mix] for mix in coverage_design.BOUNDS}
    licence_bound = every_bound[coverage_design.LICENCE_MIX]
    under_65_bound = every_bound[coverage_design.UNDER_65_MIX]
    owner_bound = every_bound[coverage_design.OWNER_MIX]
    measured_mixes = [
        mix
        for mix in coverage_design.REMAINDER_MIXES
        if mix not in coverage_design.BOUNDS and mix != coverage_design.WORKING_DAY_MIX
    ]
    _check(
        not bool(owner_bound.credible.any())
        and set(scenarios[~scenarios.credible].remainder_mix) == set(coverage_design.BOUNDS)
        and len(measured_mixes) == len(coverage_design.BOUNDS) == 3,
        "the owner-age mix is a bound, left out of the range like the two constructed ones: "
        "three measured mixes besides the working day's and three bounds, as the coverage table "
        "says",
    )
    for group, column in (("18-29", "ratio_18_29"), ("65+", "ratio_65_plus")):
        _check(
            float(other_ranges.loc[group, "min"]) <= float(alone[column].min())
            and float(alone[column].max()) <= float(other_ranges.loc[group, "max"])
            and float(ranges.loc[group, "min"]) < float(other_ranges.loc[group, "min"])
            and np.isclose(float(credible[column].min()), float(ranges.loc[group, "min"]))
            and float(credible[column].max()) <= float(ranges.loc[group, "max"]) + 1e-9,
            f"for {group}, the uncovered kilometres alone stay inside the other tests' range, and "
            "with another region's profile they widen it and stay inside the sensitivity range",
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
        1 < float(older_all.involved_ratio_low)
        and float(ranges.loc["65+", "min"]) < 1 < float(ranges.loc["65+", "max"]),
        "drivers aged 65 and over above 45-64 on the central estimate, but on either side of it "
        "under the alternatives, so the direction is not established",
    )
    order = [float(central.loc[g, "involved_ratio"]) for g in ("18-29", "30-44")]
    order += [float(cond_65.ratio_to_45_64), float(cond_75.ratio_to_45_64)]
    _check(
        order[0] == max(order)
        and all(
            float(ranges.loc[g, "min"])
            <= float(central.loc[g, "involved_ratio"])
            <= float(ranges.loc[g, "max"])
            for g in GROUPS
        )
        and all(
            older_range[g][0] <= float(conditional.loc[g, "ratio_to_45_64"]) <= older_range[g][1]
            for g in ("65-74", "75+")
        ),
        "drivers aged 18-29 are involved most often per km of the five age groups on the "
        "central estimate, and every central figure lies inside its sensitivity range",
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
    # The sources of the sensitivity range, as the notes describe them.
    profiles = variants[(variants.source == "regional profile") & (variants.group == "65+")]
    profiles = profiles.set_index("variant").involved_ratio
    distances = variants[(variants.source == "distance") & (variants.group == "65+")]
    distances = distances.set_index("variant").involved_ratio
    youngest = prevalence[prevalence.group == prevalence.group.min()]
    spain = youngest[youngest.place == "Spain"].set_index("sex").prevalence
    province = youngest[youngest.place != "Spain"].set_index("sex").prevalence
    _check(
        bool((province < spain.reindex(province.index)).all())
        and float(licence.loc["18-29", "involved_ratio"]) < float(bcn_young.involved_ratio),
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
        float(weekend["max"]) < float(bcn_older_all.involved_ratio),
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
        employed_reweighted > float(bcn_older_all.involved_ratio)
        and float(professional["min"]) > float(bcn_older_all.involved_ratio)
        and float(bcn_older_all.involved_ratio)
        < composition_older
        <= float(ranges.loc["65+", "max"]),
        "the corrections for the survey's older respondents, and the bound on too few aged 75 "
        "and over in its sample, raise the 65-and-over ratio inside its range",
    )
    _check(
        float(weekend["max"]) < float(bcn_older_all.involved_ratio)
        and float(regional_old["min"]) < float(bcn_older_all.involved_ratio),
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
    city_rows = city[city.age4 == "65+"]
    _check(
        bool((city_rows.ratio_low < 1).all())
        and bool((city_rows.ratio_high > 1).all())
        and all(
            side_of_one_shown(row.ratio_low, row.mc_se_low, row.mc_se_low, row.mc_se_high)
            and side_of_one_shown(row.ratio_high, row.mc_se_high, row.mc_se_low, row.mc_se_high)
            for row in city_rows.itertuples()
        )
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
    within_survey = check.xs(national.CHECK_WITHIN_SURVEY, level="check").value
    like_for_like = check.xs(national.CHECK_MADRID_PER_HOLDER, level="check")
    men_madrid = like_for_like.loc["male"]
    women_madrid = like_for_like.loc["female"]
    men_madrid_ci = mc_interval(
        men_madrid.low, men_madrid.high, men_madrid.mc_se_low, men_madrid.mc_se_high
    )
    _check(
        side_of_one_shown(
            men_madrid.high, men_madrid.mc_se_high, men_madrid.mc_se_low, men_madrid.mc_se_high
        )
        and float(men_madrid.high) < 1
        and abs(
            float(within_survey[national.BARCELONA_METHOD])
            - float(transfer[national.BARCELONA_METHOD])
        )
        < 0.05,
        "Madrid's men drive less per licence holder at 75+ even at the top of the printed "
        "interval; the Barcelona-area survey's own 65+/45-64 ratio is close to its value after "
        "transfer",
    )
    trend_key = national.CHECK_LICENCE_TREND
    licence_trend = check.xs(trend_key, level="check").value
    licence_gradient = check.xs(national.CHECK_LICENCE_GRADIENT_TREND, level="check").value
    cohort_update = check.loc[(national.CHECK_COHORT_UPDATE, "both sexes"), "value"]
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
        and float(transfer[national.MADRID_METHOD]) < float(transfer[national.BARCELONA_METHOD])
        and float(men_madrid.high) < 1 < float(women_madrid.high)
        and float(women_madrid.low) < 1
        and bool((licence_trend > 1).all())
        and bool((licence_gradient > 1).all())
        and float(cohort_update) < float(bcn_75.ratio_to_45_64)
        and float(cond_75.women_km_per_holder_75_vs_65_74) > 1
        and float(composition_75) > float(bcn_75.ratio_to_45_64)
        and older_range["75+"][0] <= float(composition_75) <= older_range["75+"][1]
        and float(cond_75.men_km_per_holder_75_vs_65_74) < racc_limit < 1,
        "licence holding falls alike from 65-74 to 75+ in the three places while Madrid's older "
        "residents drive less than the transfer implies; Madrid's men drive less per licence "
        "holder at 75+ and its women's interval includes 1; licence holding at 75+ has risen "
        "since the Madrid survey, more than at 65-74, which on its own would lower the figure; "
        "the Madrid split has women aged 75+ driving further per licence holder than at 65-74; "
        "the composition bound raises the figure inside the range; the "
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

    # Ages 75 and over in the notes: the licence split, the structure of the range, its ends and
    # Barcelona's check of the splits.
    places_text = {
        sex: ", ".join(f"{v:.2f}" for v in values) for sex, values in licence_fall.items()
    }
    years_after = YEAR - madrid_year
    _check(
        0 < years_after < 10
        and float(transfer[national.MADRID_METHOD]) < float(transfer[national.BARCELONA_METHOD])
        and float(within_survey[national.MADRID_METHOD])
        < float(within_survey[national.BARCELONA_METHOD]),
        "the licence split counts holders some years after the Madrid survey; Madrid's 65+ "
        "residents drive less, against 45-64, than the Barcelona-area survey's, within each "
        "survey and carried to Spain",
    )
    # Which choices the sensitivity table crosses, and which it varies one at a time.
    crossed = older_variants[
        older_variants.source.isin([national.COVERAGE_SOURCE, national.COVERAGE_PROFILE_SOURCE])
    ]
    one_at_a_time = older_variants.drop(crossed.index)
    factorial = [crossed[c].nunique() for c in ("profile", "non_working_mix", "remainder_mix")]
    _check(
        len(crossed) == int(np.prod(factorial)) * len(national.SPLITS)
        and factorial[0] == len(national._profile_methods())
        and set(one_at_a_time.source)
        == {
            "regional profile",
            "licence-calibrated transfer",
            "distance",
            "survey years",
            "professionals' work driving",
            "older sample",
            "non-working days",
        }
        and bool(
            older_variants.groupby(["source", "variant"])
            .assumption.nunique()
            .eq(len(national.SPLITS))
            .all()
        ),
        "every split is combined with every structure; the profiles are crossed with the age "
        "mixes of weekends and of the unexplained km; the other choices vary one at a time",
    )
    bound_75 = {mix: _span(bound.ratio_75_plus) for mix, bound in every_bound.items()}
    whole = decomposition[decomposition.kind == "all"].iloc[0]
    one_choice = decomposition[decomposition.kind == "factor"].sort_values(
        "log_width", ascending=False
    )
    _check(
        np.isclose(float(whole.low), older_range["75+"][0])
        and np.isclose(float(whole.high), older_range["75+"][1])
        and np.isclose(float(whole.clear_low), clear["75+"][0])
        and np.isclose(float(whole.estimate), float(bcn_75.ratio_to_45_64)),
        "the breakdown's first row is the sensitivity range, and it starts from the Barcelona "
        "profile's Madrid-pattern estimate",
    )
    racc = older_variants[older_variants.assumption == national.RACC_SPLIT]
    _check(
        str(highest_75.profile) == national.MADRID_METHOD
        and str(highest_75.remainder_mix) == coverage_design.LONG_DISTANCE_MIX
        and str(highest_75.assumption) == national.LICENCE_SPLIT,
        "the top of the 75+ range combines Madrid's profile, the long-journey mix for the "
        "unexplained km and the licence split",
    )
    _check(
        float(racc.ratio_75_plus.min()) == clear["75+"][0]
        or np.isclose(float(racc.ratio_75_plus.min()), clear["75+"][0]),
        "the lowest unmarked combination uses the RACC limit",
    )
    madrid_intervals = [joint_interval(row) for _, row in city_madrid.iterrows()]
    # Where each interval lies against the 45-64 rate; a lower end within Monte Carlo error of it
    # is said to end at about it, since another set of replicates could put it on either side.
    sides = []
    for _, row in city_madrid.iterrows():
        _check(
            float(row.ratio_high) - 1 > MC_MARGIN * float(row.mc_se_high),
            "in Barcelona every interval of the Madrid split reaches above the 45-64 rate",
        )
        if abs(float(row.ratio_low) - 1) < MC_MARGIN * float(row.mc_se_low):
            sides.append("about")
        else:
            sides.append("above" if float(row.ratio_low) > 1 else "includes")
    _check(
        len(sides) == 3 and "includes" in sides,
        "in Barcelona at least one interval of the Madrid split includes the 45-64 rate",
    )
    # The former figure, which divided the drivers by the kilometres of cars registered to owners
    # of each age (35-54 the reference).
    former_75 = float(owner.loc["75+", "ratio_to_reference"])
    cars_per_holder = check.xs(
        "Cars registered to private owners per B-licence holder", level="check"
    ).value
    _check(
        0.9 < former_75 < 1.1
        and str(owner.reference.iloc[0]) == "35-54"
        and float(cars_per_holder["75+"]) > 1 > float(cars_per_holder["65-74"]),
        "the former figure put drivers aged 75+ at about the 35-54 rate per owner km, and owners "
        "aged 75+ have more cars than car-licence holders",
    )

    def spread(group: str) -> str:
        return _fmt_span(float(ranges.loc[group, "min"]), float(ranges.loc[group, "max"]))

    older_75 = _fmt_span(*older_range["75+"])
    full_75 = _to(*older_range["75+"])
    madrid_pattern = (
        "if people aged 75 and over drive as much less than those aged 65–74 as in Madrid in "
        f"{madrid_year}"
    )
    direction = OLDER_CONCLUSION[tier]
    return SimpleNamespace(**locals())


def _per_km_alt(f: SimpleNamespace) -> str:
    """The text of the chart of involvement per kilometre, for a reader who cannot see it."""
    rows = [
        f"{LABELS[g]} {float(f.central.loc[g, 'involved_ratio']):.2f} "
        f"({_ci(f.central.loc[g], 'involved_ratio', ' to ')})"
        for g in ("18-29", "30-44")
    ]
    rows += [
        f"{label} {float(row.ratio_to_45_64):.2f} ({joint_interval(row, sep=' to ')})"
        for label, row in (("65–74", f.cond_65), ("75 and over", f.cond_75))
    ]
    return (
        f"Dot chart of car drivers involved in injury crashes per kilometre in {f.year}, as ratios "
        "to drivers aged 45–64 (the reference, 1), on a log scale, with 95% sampling intervals: "
        + "; ".join(rows)
        + "."
    )


def page_drivers(captions: dict[str, str]) -> str:
    f = _facts()
    year, killed = f.year, f.killed
    young, central = f.young, f.central
    per_km_involved, per_km_killed = f.per_km_involved, f.per_km_killed
    body = summary(
        f"Per kilometre driven, car drivers aged 18–29 in Spain in {year} were involved in injury "
        f"crashes an estimated {float(young.involved_ratio):.2f} times as often as drivers aged "
        "45–64. Once in a crash, drivers aged 75 and over died "
        f"{killed['75+'] / killed[REFERENCE]:.1f} times as often as those aged 45–64, and men "
        f"{float(f.men_fatality.ratio):.1f} times as often as women. Involvement counts every "
        "driver in a crash, whoever caused it."
    )

    # ------------------------------------------------------------------- per kilometre
    body += (
        '<h2 id="involvement-in-crashes-per-kilometre-driven">'
        "Crashes per kilometre: highest among drivers aged 18–29</h2>"
        "<p>No source counts kilometres by the driver's age in Spain, so they are estimated: "
        "DGT's car kilometres are shared out by age with the average of two travel surveys' age "
        f"profiles, the Barcelona area's ({SURVEY_YEARS}) and Madrid's ({f.madrid_year}) "
        f'(<a href="data.html#{NOTES_ANCHOR}">method</a>).</p>'
        "<p>Per kilometre driven, car drivers aged 18–29 were involved in injury crashes "
        f"{float(young.involved_ratio):.2f} times as often as drivers aged 45–64 "
        f"(95% {definition_link('Sampling interval')} {_ci(young, 'involved_ratio')}), drivers "
        f"aged 30–44 {float(central.loc['30-44', 'involved_ratio']):.2f} times "
        f"({_ci(central.loc['30-44'], 'involved_ratio')}) and drivers aged 65–74 "
        f"{float(f.cond_65.ratio_to_45_64):.2f} times ({joint_interval(f.cond_65)}).</p>"
        '<p id="ages-75-and-over">Drivers aged 75 and over were involved '
        f"{float(f.cond_75.ratio_to_45_64):.2f} times as often (95% sampling interval "
        f"{joint_interval(f.cond_75)}), the least certain of these figures: no survey of the "
        "Barcelona area separates their driving from that of people aged 65–74, so it rests on "
        "Madrid's survey alone, and under other plausible assumptions it runs from "
        f"{f.full_75} times the 45–64 rate{f.direction} "
        f'(<a href="data.html#{OLDER_NOTES_ANCHOR}">why</a>). Madrid survey data: '
        f'<a href="{CRTM_URL}">Powered by CRTM</a>.</p>'
    )
    body += figure("dr1_involved_per_km", _per_km_alt(f), captions)
    body += (
        "<p>Compare any two age groups, or men and women, in the "
        '<a href="driver-risk.html">driver risk comparison</a>.</p>'
    )

    # ------------------------------------------------------------------- deaths once involved
    body += (
        '<h2 id="deaths-once-a-crash-has-happened">'
        "Deaths once a crash has happened: highest at 75 and over</h2>"
        f"<p>Counted directly, with no kilometres, {killed['75+']:.1f} of every 1,000 car drivers "
        f"aged 75 and over involved in an injury crash in {year} died within 30 days, and "
        f"{killed['65-74']:.1f} at 65–74, against {killed[REFERENCE]:.1f} at 45–64. The rate "
        "counts only the driver's own death, so it does not show whether older drivers' crashes "
        "are more dangerous to others; like involvement, it does not show who caused a "
        "crash.</p>"
    )
    body += figure(
        "dr2_killed_per_involved",
        f"Dot chart of private-car drivers killed per 1,000 involved in an injury crash in {year}, "
        f"by age, with 95% intervals. The rate is {killed['18-29']:.1f} at 18–29, "
        f"{killed['30-44']:.1f} at 30–44, {killed[REFERENCE]:.1f} at 45–64, "
        f"{killed['65-74']:.1f} at 65–74 and {killed['75+']:.1f} at 75 and over.",
        captions,
    )

    # ------------------------------------------------------------------- men and women
    body += (
        '<h2 id="men-and-women">Men and women: men die far more often</h2>'
        "<p>Per kilometre, estimated in the same way, male car drivers were involved in injury "
        f"crashes {float(per_km_involved.ratio_men_to_women):.2f} times as often as female "
        f"drivers (95% sampling interval {ci_km(per_km_involved)}), a gap small enough that "
        "other assumptions about who drives how far could reverse it, and they were killed "
        f"{float(per_km_killed.ratio_men_to_women):.2f} times as often "
        f"({ci_km(per_km_killed)}). Per licence holder, pooling {f.sex_years}, men were involved "
        f"{float(f.men_involved.ratio):.2f} times as often as women ({_ci95(f.men_involved)}), "
        "which on the estimated kilometres comes from their driving further; once involved, "
        "they died "
        f"{float(f.men_fatality.ratio):.2f} times as often ({_ci95(f.men_fatality)}), in every "
        f"age band (Figure {figure_ref('a3_sex_ratios')}).</p>"
    )
    body += figure(
        "a3_sex_ratios",
        f"Ratios of men's to women's rates for private-car drivers, {f.sex_years}, overall and by "
        "age band: involvement in injury crashes per licence holder, deaths per licence holder, "
        "and deaths per driver involved. Men's rates are above women's on all three measures "
        f"in every age band; at 18 and over men were involved {float(f.men_involved.ratio):.2f} "
        f"times as often, killed {float(f.men_killed.ratio):.2f} times as often per licence "
        f"holder and {float(f.men_fatality.ratio):.2f} times as often once involved.",
        captions,
    )

    body += limitation(
        "The kilometres by age and sex share out DGT's kilometre totals, which DGT describes as "
        "valid only in aggregate. The crash counts include foreign and unlicensed drivers, and "
        f"drivers whose age is not recorded ({_fmt_pct(f.unknown_share)} of those involved) are "
        "left out of every rate."
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
            ("drivers_sex_trend", f"rates by sex and year, {f.trend_years}"),
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


# ----------------------------------------------------------------------------- technical notes
def _per_km_notes(f: SimpleNamespace) -> str:
    """How the kilometres by age were estimated and what the sensitivity range spans, deaths per
    kilometre, the check in Barcelona, men and women, drivers of unrecorded age and the former
    owner-age figure."""
    year = f.year
    young, older_all, ranges = f.young, f.older_all, f.ranges
    body = (
        f'<h2 id="{NOTES_ANCHOR}">Driver age and sex: kilometres and crashes per kilometre</h2>'
        "<p>These notes give the method and the checks behind the rates per kilometre on the "
        f'<a href="drivers.html">drivers page</a>; <a href="{EXPOSURE_DOC}">the exposure '
        "study</a> gives them in full. No national source "
        "counts kilometres by the age of the driver. The EMEF, the working-day mobility survey of "
        "the province of Barcelona, records the car trips its respondents drove on one working "
        "day, with each trip's duration and, from "
        f"{emef_variables.DISTANCE_FROM}, its straight-line distance in bands, from which each "
        f"trip's kilometres are estimated. Its {SURVEY_YEARS} editions give each age group's "
        "car-driver kilometres per resident, by sex.</p>"
        f"<p>Madrid's {f.madrid_year} household travel survey (the Encuesta Domiciliaria de "
        "Movilidad of the Consorcio Regional de Transportes de Madrid) gives the same measure "
        "for the Madrid region, by exact age. Each survey's kilometres per resident are applied "
        "to the population of Spain, which gives each age group's share of the kilometres. "
        "Neither region stands for Spain, and the two disagree most at 65 and over, so the "
        "estimate uses the average of the two shares, giving each survey equal weight; the "
        "Barcelona-area survey's 65-and-over kilometres are first put on Spain's mix of ages at "
        "65–74 and 75 and over, using Madrid's split between them.</p>"
        + _share_table(f.share_of_km)
        + "<p>These shares divide DGT's "
        f"{YEAR} car kilometres from inspection odometer readings, less taxis and ride-hailing "
        "cars (whose drivers are outside both counts). The drivers involved are DGT's count of "
        f"private-car drivers in injury crashes in {year}.</p>"
        f"<p>Over the {f.working} working days of {year} (weekdays less public holidays), the "
        f"Barcelona-area survey's driving comes to {_fmt_pct(f.survey_cover, 0)} of those "
        "kilometres. Both surveys describe weekdays (Madrid's, Monday to Thursday), so the "
        "estimate gives the rest the same age mix; the tests below measure what the rest is made "
        "of and give it other age mixes.</p>"
    )
    body += _rates_table(f.central, ranges, f.level, year)
    body += (
        "<p>The 95% sampling interval reflects only sampling error in the survey and chance "
        "variation in the crash counts. It is probably too narrow, because the resampling "
        "treats respondents as independent although the survey samples them in clusters. The "
        "sensitivity range adds the other choices (to see them, "
        f"{_open_link(SOURCES_ANCHOR, SOURCES_TITLE)}).</p>"
        "<h3>What the sensitivity range spans</h3>"
        "<p>The sensitivity range spans every alternative tested, each survey's profile alone "
        "among them; the estimate lies inside it for every age group. The alternatives below "
        "vary one choice at a time from the Barcelona-area survey's profile, the starting point "
        "of the analysis before the two profiles were averaged.</p>"
        "<p>For drivers aged 18–29 the largest of these choices is which region's age profile "
        "stands in for Spain's "
        f"({_fmt_span(float(f.regional_young['min']), float(f.regional_young['max']))}). "
        "Carrying the survey's driving per licence holder rather than per resident to Spain "
        f"gives {float(f.licence.loc['18-29', 'involved_ratio']):.2f}, because young people in "
        "the province of Barcelona hold car licences less often than in Spain as a whole.</p>"
        "<p>For 65 and over the treatments of trip distances give "
        f"{_fmt_span(float(f.distance_old['min']), float(f.distance_old['max']))}. Leaving out "
        "the long trips that have no distance band raises the ratio most. This group is the most "
        "sensitive to these treatments: trips of 100 km or more and trips with no distance band "
        f"are {_fmt_pct(float(f.long_trips.loc['65+', 'share_of_trips']))} of its trips but "
        f"carry {_fmt_pct(float(f.long_trips.loc['65+', 'share_of_km']), 0)} of its kilometres, "
        f"against {_fmt_pct(float(f.long_trips.loc[REFERENCE, 'share_of_km']), 0)} at 45–64. A "
        "different age mix on weekends lowers the ratio to "
        f"{_fmt_span(float(f.weekend['min']), float(f.weekend['max']))}. The regional profiles "
        f"give {_fmt_span(float(f.regional_old['min']), float(f.regional_old['max']))}, from "
        "Barcelona city's to the Madrid survey's.</p>"
    )
    share_span, part, remainder = f.share_span, f.part, f.remainder
    dgt_low, dgt_high = float(f.dgt_regional.min()), float(f.dgt_regional.max())
    body += (
        "<p>The other half of DGT's kilometres is not measured by age, but most of it can be "
        "sized from the sources this site uses (for each part, "
        f"{_open_link(COVERAGE_ANCHOR, COVERAGE_TITLE)}):</p>"
        "<ul>"
        f"<li>Weekends and public holidays, {f.non_working} days in {year}, add "
        f"{share_span('non-working days')} of DGT's total if each carries "
        f"{_fmt_pct(national.NON_WORKING_RATIOS[0], 0)} to "
        f"{_fmt_pct(national.NON_WORKING_RATIOS[1], 0)} of a working day's driving. "
        f"{coverage_design.MOVILIA_DAILY} counted {f.weekend_trips:.2f} times as many car trips, "
        "drivers and passengers together, on an average weekend day as on a working day, and "
        f"weekend trips of all modes lasted {f.weekend_minutes:.2f} times as long.</li>"
        "<li>Spain drives more per resident than the province of Barcelona: "
        f"{float(f.regional.iloc[0]):.2f} times as many car trips per resident in "
        f"{coverage_design.MOVILIA_DAILY}, and {dgt_low:.2f} to {dgt_high:.2f} times "
        f"Catalonia's car kilometres per resident in DGT's {year} figures. The difference adds "
        f"{share_span('regional level')}.</li>"
        "<li>The work trips of people who drive for a living, which the survey counts but does "
        f"not describe, add {share_span(PROFESSIONAL_PART)}.</li>"
        "<li>The months outside the survey's fieldwork change the total by "
        f"{share_span('months outside the fieldwork')}, judged by fuel sales and toll-motorway "
        "traffic.</li>"
        "</ul>"
        "<p>At their lowest these parts leave "
        f"{_fmt_pct(remainder[1], 0)} of DGT's total unexplained; at their highest they exceed "
        f"it by {_fmt_pct(-remainder[0], 0)}. Cars registered to companies "
        f"({_fmt_pct(part('cars registered to companies')[0], 0)} of the total) and hire cars "
        f"({_fmt_pct(part('car hire without driver')[0], 0)}) are driven within these parts, "
        "not beside them; hire cars also bound the driving that visitors from abroad do in "
        "Spanish cars.</p>"
    )
    body += technical(COVERAGE_TITLE, _coverage_table(f.parts), COVERAGE_ANCHOR)
    body += (
        "<p>The central estimate gives all of these parts the survey's working-day age mix. To "
        "test that, the non-working days and the unexplained part, taken at its largest "
        f"({_fmt_pct(remainder[1], 0)} of the total), were given age mixes measured elsewhere "
        f"by the traveller's own age: car journeys over 50 km per resident in "
        f"{coverage_design.MOVILIA_LONG}, and the two weekend mixes. With the "
        f"survey's profile for the rest, these give {_span(f.alone.ratio_18_29)} at 18–29 and "
        f"{_span(f.alone.ratio_65_plus)} at 65 and over, inside the ranges of the other tests.</p>"
        "<p>Combined with another region's profile, the two largest uncertainties together, they "
        f"give {_span(f.credible.ratio_18_29)} and {_span(f.credible.ratio_65_plus)}, and the "
        "sensitivity range includes these combinations. Three allocations of the unexplained "
        "part are reported but left out of the range. With each region's profile they would "
        "give:</p>"
        "<ul>"
        "<li>The same kilometres per licence holder at every age, a constructed allocation "
        f"that no source supports: {_span(f.licence_bound.ratio_18_29)} at 18–29 and "
        f"{_span(f.licence_bound.ratio_65_plus)} at 65 and over.</li>"
        "<li>No driving at 65 and over, also constructed and supported by no source: "
        f"{_span(f.under_65_bound.ratio_18_29)} at 18–29 and "
        f"{_span(f.under_65_bound.ratio_65_plus)} at 65 and over.</li>"
        "<li>DGT's kilometres by the age of a car's private owner, which is not the age of its "
        "driver (see the former owner-age figure, at the end of this section): "
        f"{_span(f.owner_bound.ratio_18_29)} at 18–29 and {_span(f.owner_bound.ratio_65_plus)} "
        "at 65 and over.</li>"
        "</ul>"
    )
    body += technical(SOURCES_TITLE, _sources_table(f.by_source), SOURCES_ANCHOR)
    early, late = f.early_years, f.late_years
    employed = f.employed_survey
    body += (
        "<p>Further choices raise the 65-and-over ratio:</p>"
        "<ul>"
        "<li>The share of the survey's older respondents in work was about "
        f"{_fmt_pct(float(employed.loc[early, 'employed_share'].mean()))} in "
        f"{min(early)}–{max(early)}, the same as the census for Catalonia, but "
        f"{_fmt_pct(float(employed.loc[late, 'employed_share'].min()))} to "
        f"{_fmt_pct(float(employed.loc[late, 'employed_share'].max()))} in "
        f"{SURVEY_YEARS}. Setting it back to the census share moves the Barcelona profile's "
        f"65-and-over ratio from {float(f.bcn_older_all.involved_ratio):.2f} to "
        f"{f.employed_reweighted:.2f}.</li>"
        "<li>The survey counts but does not describe the work trips of people who drive for a "
        "living, most of them under 65. Counting a quarter or a half of those trips as car "
        "trips raises the ratio to "
        f"{_fmt_span(float(f.professional['min']), float(f.professional['max']))}.</li>"
        "<li>If the survey's 65-and-over sample holds too few people aged 75 and over, who "
        "drive less, its 65-and-over kilometres per resident are too high. At the bound "
        f'described under <a href="#{OLDER_NOTES_ANCHOR}">drivers aged 75 and over</a>, the '
        f"ratio rises to {f.composition_older:.2f}.</li>"
        "</ul>"
        "<p>The weekend age mix and Barcelona city's profile point the other way, so the "
        "evidence does not say in which direction the estimate errs.</p>"
    )

    # Deaths per kilometre: the two measures combined.
    body += (
        "<h3>Deaths per kilometre</h3>"
        "<p>Deaths per kilometre combine involvement per kilometre with deaths once involved, so "
        "they carry the estimate of kilometres. On the estimate, drivers aged 65 and "
        f"over were killed {f.killed_ratio_old:.2f} times as often per kilometre driven as "
        f"drivers aged 45–64 (95% sampling interval {_ci(older_all, 'killed_ratio')}; "
        "sensitivity range "
        f"{_fmt_span(float(f.killed_range['min']), float(f.killed_range['max']))}), while their "
        f"involvement per kilometre was {float(older_all.involved_ratio):.2f} times "
        f"(sensitivity range {f.spread('65+')}).</p>"
        "<p>Under every assumption tested the first ratio is above the second, so most of the "
        "excess in deaths per kilometre comes from how often a crash kills an older driver, not "
        "from how often older drivers are in crashes.</p>"
    )

    # Barcelona's working-day check.
    city = f.city
    body += (
        "<h3>A check in Barcelona on working days</h3>"
        "<p>Inside Barcelona on working days, involvement per kilometre can be compared without "
        "carrying the survey to Spain or assuming anything about weekends. The Guàrdia Urbana's "
        f"{CITY_YEAR} records give the age of {_fmt_pct(1 - f.city_unknown_share)} of the car "
        "drivers involved in injury crashes in the city on working days, uninjured drivers "
        "included.</p>"
        "<p>The EMEF gives the kilometres the survey area's residents drove inside the city on a "
        f"working day in {SURVEY_YEARS}, counted over the "
        f"{day_calendar.days_in_year(CITY_YEAR)[day_calendar.WORKING_DAY]} working days of "
        f"{CITY_YEAR} (weekdays less the Catalan and Barcelona public holidays). The part of a "
        "trip into or out of the city that lies inside it cannot be measured, so the table "
        "gives three versions of the kilometres, and only the ratios between ages are read.</p>"
    )
    body += _barcelona_table(city)
    body += (
        "<p>Across the three versions, drivers aged 65 and over were involved at "
        f"{_fmt_span(float(f.city_older.min()), float(f.city_older.max()))} times the rate of "
        "drivers aged 45–64, each with a 95% interval that includes 1, and drivers aged 18–29 "
        f"at {_span(f.city_young)} times it.</p>"
        "<p>The crashes include drivers whose kilometres the survey does not count: people "
        "living outside the survey area, traffic passing through the city, and people driving "
        "ordinary cars for work. They are mostly of working age, so the older drivers' ratio is "
        "more likely biased down than up; leaving out the drivers recorded as on duty raises it "
        f"to {_span(f.on_duty.ratio_to_45_64)}. The ratios assume that the drivers with no "
        "recorded age follow the recorded mix; if all were aged 65 or over, the ratio for trips "
        f"inside the city would be {float(f.city_unknown_old.loc['65+']):.2f}.</p>"
    )

    # Men and women.
    b_licence = f.b_licence
    body += (
        "<h3>Men and women</h3>"
        "<p>The survey's kilometres are split by sex and carried to Spain in the same way as by "
        f"age; on that estimate men drove {_fmt_pct(float(f.per_km_involved.men_share_of_km))} "
        f"of car kilometres in {year}. Per licence holder, pooling {f.sex_years}, men died at "
        f"the wheel {float(f.men_killed.ratio):.2f} times as often as women "
        f"({_ci95(f.men_killed)}): {float(f.men_involved.ratio):.2f} times as often involved and, "
        f"once involved, {float(f.men_fatality.ratio):.2f} times as often killed.</p>"
        "<p>Across all motor-vehicle drivers, which adds motorcyclists, moped riders, the drivers "
        "of vans, trucks and buses and other motor vehicles, the gaps are wider: men died "
        f"{float(f.motor_killed.ratio):.2f} times as often as women per licence holder and "
        f"{float(f.motor_fatality.ratio):.2f} times as often once involved. The licence holders "
        "are holders of any class of licence. The census gives car-licence holders by sex and "
        f"age for {str(b_licence.years.iloc[0]).replace('-', '–')} only; counting only them "
        "raises the ratio of men's to women's deaths per licence holder in those years from "
        f"{float(b_licence.loc['licence holders of any class', 'ratio']):.2f} to "
        f"{float(b_licence.loc['B-licence holders', 'ratio']):.2f}.</p>"
    )
    body += technical("Detailed counts by sex", _sex_rates_table(f.sex_rates, f.sex_years))

    # Drivers of unrecorded age, and the former figure.
    owner, owner_same = f.owner, f.owner_same
    body += (
        "<h3>Drivers whose age is not recorded</h3>"
        f"<p>Drivers whose age the tables do not record ({_fmt_pct(f.unknown_share)} of those "
        "involved) are left out of every rate, which lowers each absolute rate by that share. "
        "The ratios assume their ages follow the recorded mix: if all were aged 18–29, the young "
        f"drivers' ratio would be {f.unknown_young:.2f}; assigned to any one age group, they "
        "would put the ratio for 65 and over between "
        f"{_fmt_span(float(f.unknown_old.min()), float(f.unknown_old.max())).replace('–', ' and ')}."
        "</p>"
        "<h3>The former owner-age figure</h3>"
        f"<p>Until {national.OLDER_ESTIMATE_CHANGED} the drivers page divided the same drivers, "
        "taxi and ride-hailing drivers included, by DGT's kilometres of cars registered to "
        "owners of each age, the only kilometres by age that DGT publishes. On those kilometres "
        "it said that drivers aged 75 and over were involved about as often per kilometre as "
        f"drivers aged 35–54 ({f.former_75:.2f} times); the figure it gave for young drivers, "
        f"{float(owner.loc['18-24', 'ratio_to_reference']):.2f}, compared drivers aged 18–24 "
        "with 35–54.</p>"
        "<p>On the age groups used now, those owner kilometres put drivers aged 18–29 at "
        f"{float(owner_same.loc['18-29', 'ratio_to_reference']):.2f} times the 45–64 rate and "
        f"drivers aged 65 and over at {float(owner_same.loc['65+', 'ratio_to_reference']):.2f}, "
        f"against {float(young.involved_ratio):.2f} and {float(older_all.involved_ratio):.2f} "
        "on the estimated kilometres.</p>"
        "<p>A car's owner is often not its driver: young people drive "
        "cars registered to their parents, and owners aged 75 and over have "
        f"{float(f.cars_per_holder['75+']):.2f} cars registered to them for every car-licence "
        "holder of that age, more cars than holders, some of them driven by others. So the "
        "owner kilometres credited too little driving to the young and too much to the old.</p>"
    )
    return body


def _older_notes(f: SimpleNamespace, captions: dict[str, str]) -> str:
    """Drivers aged 75 and over: the counts, the conditional estimate and why it rests on the
    Madrid pattern, the sensitivity range and what sets its ends, Barcelona's check of the
    splits, and the data that would narrow it."""
    year, killed, severity = f.year, f.killed, f.severity
    cond_75, cond_65, madrid = f.cond_75, f.cond_65, f.madrid
    clear, older_range = f.clear, f.older_range
    oldest_counts = severity.loc["75+"]
    body = (
        f'<h2 id="{OLDER_NOTES_ANCHOR}">Drivers aged 75 and over: the conditional estimate and '
        "its range</h2>"
        "<p>No source for Spain measures how far drivers aged 75 and over drive apart from those "
        "aged 65–74, so their rates per kilometre rest on an assumption about how the "
        "65-and-over kilometres divide between the two ages: one gives the conditional "
        "estimate, the others the sensitivity range. The counts, the rates per licence holder "
        "and the deaths once involved need no kilometres.</p>"
        f"<p><strong>Counted.</strong> In {year}, "
        f"{int(oldest_counts.involved):,} car drivers aged 75 and over and "
        f"{int(severity.loc['65-74', 'involved']):,} aged 65–74 were involved in injury crashes "
        f"in Spain, and {int(oldest_counts.killed):,} and "
        f"{int(severity.loc['65-74', 'killed']):,} of them died within 30 days: "
        f"{killed['75+']:.1f} and {killed['65-74']:.1f} per 1,000 involved, against "
        f"{killed[REFERENCE]:.1f} at 45–64 (charted on the "
        '<a href="drivers.html#figure-dr2_killed_per_involved">drivers page</a>). These '
        "figures say how often a crash kills the driver. They do not say "
        "how often drivers of these ages are in crashes for the distance they drive, or who "
        "caused the crashes.</p>"
        f"<p>Per 1,000 holders of a car licence, {f.per_holder['75+']:.2f} drivers aged 75 "
        f"and over were involved, against {f.per_holder['65-74']:.2f} at 65–74 and "
        f"{f.per_holder[REFERENCE]:.2f} at 45–64. Many licence holders aged 75 and over drive "
        "little or not at all, so these are not rates per driver. Every estimate per kilometre "
        f"below is higher than the ratio of these rates, {float(f.holder_ratio.value):.2f}, "
        "because under every assumption tested licence holders aged 75 and over drive fewer "
        "kilometres than those aged 45–64.</p>"
    )
    body += (
        "<p><strong>Conditional estimate.</strong> The EMEF's public files group everyone aged "
        "65 and over, although the survey sampled 65–74 and 75 and over separately until "
        f"{emef_variables.OLDER_STRATA_LAST}. Madrid's {f.madrid_year} household travel survey "
        "records exact ages: there, residents aged 75 and over drove "
        f"{float(madrid.loc['75+', 'ratio_75_to_65_74_male']):.2f} times the car distance per "
        "resident of those aged 65–74 if men and "
        f"{float(madrid.loc['75+', 'ratio_75_to_65_74_female']):.2f} times if women.</p>"
        f"<p>If people aged 75 and over in Spain in {year} drive as much less as in Madrid, with "
        "the kilometres by age from the average of the two surveys' profiles, drivers aged 75 "
        "and over were involved in injury crashes "
        f"{float(cond_75.ratio_to_45_64):.2f} times as often per kilometre as drivers aged 45–64 "
        f"(95% sampling interval {joint_interval(cond_75)}), and drivers aged 65–74 "
        f"{float(cond_65.ratio_to_45_64):.2f} times ({joint_interval(cond_65)}). Under the "
        f"other assumptions tested the figure for 75 and over runs from {f.full_75} (the "
        "sensitivity range, below).</p>"
        "<p>The sampling intervals allow for sampling error in both surveys and chance in the "
        "crash counts, and hold the Madrid assumption fixed. They may be too narrow or too "
        "wide: the Barcelona-area survey's resampling treats respondents as independent "
        "although the survey samples them in clusters, which makes an interval too narrow, and "
        "the Madrid survey's ignores the stratification of its sample, which makes one too "
        "wide.</p>"
        "<p>The Barcelona-area survey's kilometres at 65 and over are a mean over the province "
        "of Barcelona's residents of those ages, a slightly larger share of whom are aged 75 and "
        "over than in Spain. Before the two profiles are averaged they are split at 75 with "
        "Madrid's ratio and put back together with Spain's mix of ages, as the Madrid profile "
        "already is. On the Barcelona profile alone, as in the analysis of the range below, "
        "drivers aged 75 and over were involved "
        f"{float(f.bcn_75.ratio_to_45_64):.2f} times as often ({joint_interval(f.bcn_75)}).</p>"
    )
    transfer, within_survey = f.transfer, f.within_survey
    body += technical(
        "Why this assumption, and what could move it",
        "<ul>"
        "<li>It uses only kilometres measured by exact age; the second split, Madrid's "
        "kilometres per licence holder, also needs DGT's counts of licence holders, taken "
        f"{_words(f.years_after)} years after the survey.</li>"
        "<li>Car-licence holding falls about equally from 65–74 to 75 and over in the province "
        "of Madrid, the province of Barcelona and Spain (holders per resident at 75 and over "
        f"against 65–74, DGT, {year}: men {f.places_text['male']}; women "
        f"{f.places_text['female']}). That is consistent with the assumption but does not test "
        "it.</li>"
        "<li>The Madrid survey has residents aged 65 and over driving much less, relative to "
        "those aged 45–64, than the Barcelona-area survey does. Each survey's profile carried "
        f"to Spain's population gives {float(transfer[national.MADRID_METHOD]):.2f} against "
        f"{float(transfer[national.BARCELONA_METHOD]):.2f} times as far per resident on working "
        "days; among each survey's own residents the figures are "
        f"{float(within_survey[national.MADRID_METHOD]):.2f} and "
        f"{float(within_survey[national.BARCELONA_METHOD]):.2f}. Averaging the two profiles "
        "takes the middle of that disagreement.</li>"
        "<li>Some evidence points lower: licence holding at 75 and over has risen since "
        f"{f.madrid_year}, more than at 65–74, and surveys in other European countries show a "
        f'gentler fall in driving after 75 (see <a href="{EXPOSURE_DOC}">the exposure '
        "study</a>).</li>"
        "<li>Some points higher: the Barcelona-area survey's weighting does not separate 75 and "
        "over within 65 and over, so its 65-and-over sample may hold too few people aged 75 and "
        "over; on the Barcelona profile, at the most this would raise the figure from "
        f"{float(f.bcn_75.ratio_to_45_64):.2f} to about {float(f.composition_75):.2f}, a case "
        "included in the sensitivity range.</li>"
        "<li>Also higher: applied to Spain's licence holders, the "
        "Madrid pattern implies that women aged 75 and over with a car licence drive "
        f"{float(cond_75.women_km_per_holder_75_vs_65_74):.2f} times as far as women aged 65–74 "
        "with one, while Spanish surveys of women's driving, though too uncertain to rule that "
        "out, point to less; less driving by these women would raise the figure.</li>"
        "<li>Which way the figure errs is not known.</li>"
        "</ul>",
    )
    body += (
        "<p><strong>Across the assumptions.</strong> Four splits of the 65-and-over kilometres "
        "were tested:</p>"
        "<ol>"
        "<li>Madrid's split, used for the estimate.</li>"
        "<li>Madrid's kilometres per licence holder, applied to Spain's licence holders.</li>"
        "<li>An upper limit for men from the number of days they drive, with women driving as "
        "far per licence holder at 75 and over as at 65–74.</li>"
        "<li>Equal kilometres per licence holder at 65–74 and 75 and over.</li>"
        "</ol>"
        "<p>Each split was combined with every alternative for the 65-and-over kilometres, and "
        f"together they give a sensitivity range of {f.full_75} at 75 and over and "
        f"{_to(*older_range['65-74'])} at 65–74. Of these alternatives, the region whose age "
        "profile stands in for Spain's (the province of Barcelona's, its four parts, Madrid's, "
        "or the province's carried per licence holder) was crossed with the age mixes for "
        "weekends and holidays and for the kilometres no part explains.</p>"
        "<p>Trip distances, survey years, work driving, the older respondents' employment and "
        "age mix, and a weekend age mix on its own were varied one at a time, each with "
        "everything else as on the Barcelona profile with Madrid's split. A sensitivity range is "
        "not an interval: it "
        "carries no probability, and it is not a limit, because the choices varied one at a "
        "time are not combined with each other or with the crossed ones, which would move both "
        "ends.</p>"
        "<p>The split with equal kilometres per licence holder stays in the range: women's "
        "driving does not rule it out, and the evidence against it for men comes from regional "
        "or dated surveys rather than a national measure of kilometres.</p>"
        "<p>The three allocations "
        "of the unexplained kilometres reported above stay out of it, for the reasons given "
        "there. At 75 and over, across the profiles and splits, they would give "
        f"{f.bound_75[coverage_design.LICENCE_MIX]} with the same kilometres per licence holder "
        f"at every age, {f.bound_75[coverage_design.UNDER_65_MIX]} with no driving at 65 and "
        f"over, and {f.bound_75[coverage_design.OWNER_MIX]} with DGT's kilometres by the "
        "owner's age.</p>"
    )
    men_madrid, men_madrid_ci = f.men_madrid, f.men_madrid_ci
    body += _older_table(
        f.older,
        f.older_variants,
        f.older_75,
        f"In Madrid in {f.madrid_year} men aged 75 and over drove "
        f"{float(men_madrid.value):.2f} times ({men_madrid_ci}) as far per {YEAR} DGT licence "
        "holder as men aged 65–74 (the survey's kilometres per resident over the province's "
        f"licence holding in {YEAR}).",
        float(men_madrid.value),
    )
    body += _moves_table(f.whole, f.one_choice)
    tier, lowest_clear = f.tier, f.lowest_clear
    if tier == INTERMEDIATE:
        sampling = (
            f"Its 95% sampling interval, {joint_interval(lowest_clear)}, includes the 45–64 "
            "rate. So even leaving out equal kilometres per licence holder, one combination "
            "tested is consistent with no difference, and the data do not establish a higher "
            "rate at 75 and over, or its size."
        )
    elif tier == PASS:
        sampling = (
            f"Its 95% sampling interval, {joint_interval(lowest_clear)}, stays above the 45–64 "
            "rate, so among the "
            "combinations tested the evidence points to more involvement per kilometre at 75 and "
            "over; how much more is not established."
        )
    else:
        sampling = (
            "It is at or below the 45–64 rate, so whether drivers aged 75 and over are involved "
            "more or less often per kilometre is not established."
        )
    highest_75 = f.highest_75
    body += (
        f"<p>Below about {clear['75+'][0]:.1f} the sensitivity range is reached only with "
        "equal kilometres per licence holder at 65–74 and 75 and over, which assumes men aged "
        "75 and over with a car licence drive as far as men aged 65–74 with one. Spanish "
        f"surveys of men's driving show them driving less: in Madrid in {f.madrid_year}, "
        f"{float(men_madrid.value):.2f} times as far per {YEAR} DGT licence holder (95% "
        f"sampling interval {men_madrid_ci}); in RACC's survey of "
        f"licence holders aged 65 and over, published in {national.RACC_YEAR}, on about "
        f"{f.racc_limit:.2f} times as many days, an upper limit for their kilometres.</p>"
        "<p>Surveys of women's driving are too uncertain to say the same for them, so these "
        "combinations stay in the sensitivity range.</p>"
        "<p>Among the other combinations tested, the "
        f"lowest, about {clear['75+'][0]:.1f}, combines Barcelona city's age profile, weekend "
        "age mixes for the kilometres outside the survey's working days and the RACC limit; "
        f"this edge is set by that limit. {sampling}</p>"
        f"<p>The top of the sensitivity range, {older_range['75+'][1]:.2f}, "
        "combines Madrid's age profile, the age mix of long car journeys for the kilometres no "
        "part explains and Madrid's kilometres per licence holder, the second split. There "
        "drivers aged 75 and over would drive "
        f"{_fmt_pct(float(highest_75.driver_over_owner_km_75_plus), 0)} of the kilometres DGT "
        "records for cars registered to owners of that age, against "
        f"{_fmt_pct(float(highest_75.driver_over_owner_km_45_64), 0)} at 45–64; owner figures "
        "cannot say who drove, so this is noted, not counted against it.</p>"
    )
    words = ("none", "one", "two", "three")
    clauses = []
    for side, singular, plural in (
        ("includes", "includes the 45–64 rate", "include the 45–64 rate"),
        ("above", "lies above it", "lie above it"),
        (
            "about",
            "ends so close to it that another set of resamples could put its lower end on "
            "either side",
            "end so close to it that another set of resamples could put their lower ends on "
            "either side",
        ),
    ):
        count = f.sides.count(side)
        if count:
            clauses.append(f"{words[count]} {singular if count == 1 else plural}")
    madrid_intervals = f.madrid_intervals
    body += (
        "<p>In Barcelona's working-day check, with no transfer to Spain (the 65-and-over "
        "kilometres are still divided by each split), the four splits give "
        f"{_span(f.city_75)} at 75 and over across the three ways of counting trips that cross "
        "the city boundary, below the 45–64 rate in some combinations and above it in "
        "others.</p>"
        f"<p>With {int(f.city_split_75.drivers_involved.iloc[0])} drivers aged 75 and over, the "
        f"Madrid split's 95% sampling intervals ({', '.join(madrid_intervals[:-1])} and "
        f"{madrid_intervals[-1]}) are wide: {_join(clauses)}. The figures disagree with each "
        "other, so the check neither confirms nor rules out a rate above the 45–64 rate.</p>"
    )
    # What would narrow the range: the owner asked the pages to name the missing data.
    body += (
        "<p>Two kinds of data would narrow this range. The EMEF's own records hold each "
        "respondent's exact age, so its kilometres at 65–74 and at 75 and over, tabulated by "
        "the Institut Metròpoli or the ATM, would replace the transfer of Madrid's pattern; a "
        "request for those tables has been prepared but not sent "
        f'(<a href="{DOCS_URL}/research/EMEF_DATA_REQUEST.md">the data request</a>). A survey '
        "of driving on every day of the week across Spain, by exact age, would replace the "
        "assumptions about weekends and about the kilometres the working-day survey does not "
        "cover.</p>"
        "<p>Drivers who drive few kilometres, at any age, tend to have more crashes per "
        "kilometre, partly because more of their driving is on streets with junctions and less "
        "on motorways, so a higher rate per kilometre at 75 and over would not by itself show "
        "that age makes driving less safe. These rates are averages over everyone of an age who "
        "drives and say nothing about any one driver.</p>"
        "<p>They count involvement in injury crashes, whoever caused them; responsibility is not "
        "measured. The higher deaths once involved are counted and do not depend on any of "
        "these assumptions. The Madrid survey data are reused under the open-data licence of "
        "the Consorcio Regional de Transportes de Madrid. "
        f'<a href="{CRTM_URL}">Powered by CRTM</a>.</p>'
    )
    return body


def technical_notes(captions: dict[str, str]) -> str:
    """The drivers page's method and checks, as two sections of the methodology page: the
    kilometres by age and crashes per kilometre, and drivers aged 75 and over."""
    f = _facts()
    return _per_km_notes(f) + _older_notes(f, captions)
