"""Driver age and sex: how often car drivers are involved in crashes for the distance they drive,
and how often a crash kills the driver.

The page states the results in the order of how firmly they are known. Deaths once involved, by
age, are counted from the crash records and need no estimate of distance. Involvement per
kilometre by age is an estimate: the direction is robust but the size depends on assumptions, so
every ratio is printed with its 95% sampling interval and the range across the alternative
assumptions tested (``risk_national_ranges``). Men against women comes last. ``technical_notes``
gives the methodology page the rest: what is measured, how the kilometres by age were estimated
from the EMEF working-day survey and the Madrid household survey (``scripts/exposure_risk.py``;
``docs/DRIVER_AGE_EXPOSURE.md``), what DGT's kilometres are made of, what the ranges span, the
check in Barcelona and the caveat on drivers aged 75 and over.

Every number is read from the ``risk_*``, ``emef_*`` and ``drivers_sex_*`` tables, and every
sentence of the page and its notes is checked against them (``_facts``) before either is written.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from dgt_stats import edm2018
from dgt_stats.emef import exposure
from dgt_stats.exposure_risk import barcelona as city_design
from dgt_stats.exposure_risk import calendar as day_calendar
from dgt_stats.exposure_risk import national
from dgt_stats.site.components import (
    _fmt_dec,
    _fmt_pct,
    definition_link,
    downloads,
    figure,
    figure_ref,
    limitation,
    read_table,
    render_page,
    summary,
    table,
)
from dgt_stats.site.numbers import _driver_numbers, _sex_numbers, per_km_ratio

REFERENCE = "45-64"
YEAR = national.YEAR
CITY_YEAR = city_design.YEAR
SURVEY_YEARS = f"{min(exposure.CONTEMPORARY_YEARS)}–{max(exposure.CONTEMPORARY_YEARS)}"
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
EXPOSURE_DOC = "https://github.com/RAHV-FB/dgt-stats/blob/main/docs/DRIVER_AGE_EXPOSURE.md"
# The sections of the methodology page that hold this page's technical notes.
NOTES_ANCHOR = "drivers-per-km"
OLDER_NOTES_ANCHOR = "drivers-75-and-over"


def _check(holds: bool, claim: str) -> None:
    if not holds:
        raise ValueError(f"drivers page: the tables no longer support: {claim}")


def _pair(low: float, high: float, digits: int = 1) -> str:
    return f"{float(low):.{digits}f}–{float(high):.{digits}f}"


def _detail(estimate: dict, long: bool = False) -> str:
    """'(95% sampling interval 2.5–2.9; range 1.5–3.6)', the interval and the range beside a
    ratio; ``long`` names the range as the one under other assumptions."""
    name = "range under other assumptions" if long else "range"
    return f"(95% sampling interval {estimate['interval']}; {name} {estimate['range']})"


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the tables, with the checks
    that the sentences built on them still hold."""
    numbers = _driver_numbers()
    central, older, severity = numbers["central"], numbers["older"], numbers["severity"]
    involved, city, city_all = numbers["involved_ranges"], numbers["city"], numbers["city_all"]
    killed_ranges = numbers["ranges"][numbers["ranges"].measure == "killed per km"].set_index(
        "group"
    )
    per_km = {g: per_km_ratio(numbers, g) for g in (*GROUPS, "65-74", "75+")}
    numerator = read_table("risk_national_numerator").set_index("group")
    shares = read_table("risk_national_shares")
    parts = read_table("risk_coverage").set_index("component")
    employment = read_table("emef_employment_benchmark")
    emef_choices = read_table("emef_sensitivity").set_index("variant")
    sex = _sex_numbers()
    sex_ratios, sex_rates = sex["ratios"], sex["rates"]
    b_licence = read_table("drivers_sex_b_licence").set_index("denominator")
    # Men against women per km: the same ranges table, one row each.
    sex_per_km = numbers["ranges"][numbers["ranges"].group == "men to women"].set_index("measure")
    sex_years = str(sex_rates.years.iloc[0]).replace("-", "–")
    men_share = float(read_table("risk_sex_per_km").men_share_of_km.iloc[0])
    killed = {g: float(severity.loc[g, "killed_per_1000_involved"]) for g in severity.index}
    unknown_share = float(numerator.unknown_share.iloc[0])
    working, non_working = national.working_days(YEAR)

    # What the opening and the section on involvement per km claim about each age group.
    _check(
        float(central.loc["18-29", "involved_ratio_low"]) > 2
        and float(involved.loc["18-29", "range_min"]) > 1.2,
        "drivers aged 18-29 are involved more often per km than 45-64, clearly: the sampling "
        "interval is above 2 and every alternative above 1.2",
    )
    _check(
        float(central.loc["30-44", "involved_ratio_low"]) > 1
        and float(involved.loc["30-44", "range_min"]) > 1
        and float(central.loc["30-44", "involved_ratio"])
        < float(central.loc["18-29", "involved_ratio_low"]),
        "drivers aged 30-44 are modestly above 45-64, and below 18-29, under every alternative",
    )
    _check(
        float(older.loc["65-74", "ratio_low"]) < 1.05
        and float(involved.loc["65-74", "range_min"])
        < 1
        < float(involved.loc["65-74", "range_max"]),
        "drivers aged 65-74 cannot be told apart from 45-64: the sampling interval reaches 1 and "
        "the range is on both sides of it",
    )
    _check(
        float(involved.loc["75+", "range_min"]) < 1 < float(involved.loc["75+", "range_max"])
        and float(involved.loc["75+", "range_max"]) > 2 * float(involved.loc["75+", "range_min"]),
        "for drivers aged 75 and over the range spans 1 and is wide, so no direction is "
        "established",
    )
    _check(
        float(involved.loc["65+", "range_min"]) < 1 < float(central.loc["65+", "involved_ratio"]),
        "the range for 65 and over includes 1 although the estimate is above it",
    )
    # Deaths once involved: the older groups above 45-64, 75 and over most.
    _check(
        float(severity.loc["75+", "killed_ratio_low"]) > 1
        and float(severity.loc["65-74", "killed_ratio_low"]) > 1
        and severity.killed_per_1000_involved.idxmax() == "75+",
        "drivers aged 65-74 and 75 and over die more often once involved than drivers aged "
        "45-64, and 75 and over most often",
    )
    _check(
        float(killed_ranges.loc["65+", "range_min"]) > float(involved.loc["65+", "range_max"]),
        "under every alternative the 65-and-over ratio of deaths per km is above that of "
        "involvement per km",
    )
    _check(
        float(severity.loc["75+", "killed_ratio_to_45_64"])
        > float(involved.loc["75+", "range_max"]),
        "deaths once involved separate drivers aged 75 and over from 45-64 more than any "
        "involvement-per-km ratio does",
    )
    # Men and women.
    car = sex_ratios.xs("car", level="scope")
    adult = car.xs("18+", level="band")
    involved_sex = sex_per_km.loc["involved per km"]
    killed_sex = sex_per_km.loc["killed per km"]
    _check(
        float(adult.low.min()) > 1
        and bool((car.drop(index="18+", level="band").low > 1).all())
        and float(involved_sex.range_min) < 1 < float(involved_sex.range_max)
        and float(killed_sex.range_min) > 1.5,
        "men are higher than women per licence holder and once involved in every age band; per "
        "km the range for involvement spans 1 while men are killed far more often",
    )
    # The kilometres the survey covers, and the employed share of its older respondents.
    covered = float(parts.loc["working days", "share_least_explained"])
    _check(0.45 < covered < 0.55, "the survey's working days cover about half of DGT's km")
    survey = employment[employment.source.str.startswith("EMEF")].set_index("year")
    census = float(employment[employment.source.str.startswith("census")].employed_share.iloc[0])
    recent = survey.loc[list(exposure.CONTEMPORARY_YEARS), "employed_share"]
    _check(
        bool((recent > 1.3 * census).all()),
        "the survey's employed share at 65+ exceeds the census share in 2022-2024",
    )
    level_65 = "km_per_resident_65+"
    employment_effect = 1 - float(
        emef_choices.loc["older sample", level_65] / emef_choices.loc["central", level_65]
    )
    # Barcelona's working-day check.
    city_65 = city[city.age4 == "65+"]
    on_duty = city_all[
        (city_all.numerator == city_design.NUMERATORS[1]) & (city_all.age4 == "65+")
    ].set_index("denominator")
    _check(
        bool((city_65.ratio_low < 1).all())
        and bool((city_65.ratio_high > 1).all())
        and bool((city[city.age4 == "18-29"].ratio_to_45_64 > 1.8).all()),
        "in Barcelona on working days, 65+ at about the 45-64 rate (every interval includes 1) "
        "and the young at about twice it or more",
    )
    _check(
        bool(
            (
                on_duty.ratio_to_45_64
                > city_65.set_index("denominator").ratio_to_45_64.reindex(on_duty.index)
            ).all()
        ),
        "leaving out the drivers recorded as on duty raises the older drivers' ratio in Barcelona",
    )
    return SimpleNamespace(**locals())


def _per_km_alt(f: SimpleNamespace) -> str:
    """The text of the chart of involvement per kilometre, for a reader who cannot see it."""
    rows = [
        f"{LABELS[g]} {f.per_km[g]['ratio']} (sampling interval {f.per_km[g]['interval']}, "
        f"range {f.per_km[g]['range']})"
        for g in ("18-29", "30-44", "65-74", "75+")
    ]
    return (
        f"Dot chart of car drivers involved in injury crashes per kilometre in {YEAR}, as ratios "
        "to drivers aged 45–64 (the reference, 1), on a log scale, with 95% sampling intervals; "
        "the range across alternative assumptions in brackets: " + "; ".join(rows) + "."
    )


def _ratio_table(f: SimpleNamespace) -> str:
    rows = []
    for group in (*GROUPS, "65-74", "75+"):
        shown = f.per_km[group]
        reference = group == REFERENCE
        count = f.numerator.loc[group, "involved"]
        rows.append(
            {
                "Age": LABELS[group] + (" (measured)" if group == "65+" else ""),
                "Drivers involved": count,
                "Times the 45–64 rate": "1 (reference)" if reference else shown["ratio"],
                "95% sampling interval": "" if reference else shown["interval"],
                "Range under other assumptions": "" if reference else shown["range"],
            }
        )
    return table(
        pd.DataFrame(rows),
        f"Car drivers involved in injury crashes per kilometre driven, by age, Spain, {YEAR}, as "
        "a multiple of the rate of drivers aged 45–64. The kilometres by age are estimated from "
        "two travel surveys; the 65–74 and 75-and-over rows split the 65-and-over kilometres as "
        "Madrid's survey does. The 95% sampling interval allows only for chance in the surveys "
        "and the crash counts. The range is the lowest and highest ratio under the alternative "
        "assumptions listed in the technical notes. Data: the CSV of ranges.",
        {"Drivers involved": "int"},
    )


def page_drivers(captions: dict[str, str]) -> str:
    f = _facts()
    young, middle = f.per_km["18-29"], f.per_km["30-44"]
    k = f.severity
    old_deaths = (
        f"{float(k.loc['75+', 'killed_ratio_to_45_64']):.1f} times as often as drivers aged 45–64 "
        f"(95% interval {_pair(k.loc['75+', 'killed_ratio_low'], k.loc['75+', 'killed_ratio_high'])})"
    )
    body = summary(
        f"Car drivers aged 75 and over who are in an injury crash die {old_deaths}; this is "
        "counted from the crash records and needs no estimate of distance. Per kilometre driven, "
        f"drivers aged 18–29 are involved in injury crashes {young['ratio']} times as often as "
        f"drivers aged 45–64 {_detail(young, long=True)}, and drivers aged 30–44 {middle['ratio']} times "
        f"as often {_detail(middle)}. Drivers aged 65–74 cannot be told apart from drivers aged "
        f"45–64 ({f.per_km['65-74']['ratio']} times; interval {f.per_km['65-74']['interval']}; "
        f"range {f.per_km['65-74']['range']}), and whether drivers aged 75 and over differ is "
        f"not established ({f.per_km['75+']['ratio']} times; interval "
        f"{f.per_km['75+']['interval']}; range {f.per_km['75+']['range']}). Involvement counts "
        "every driver in a crash, whoever caused it."
    )

    # ------------------------------------------------------------------- per kilometre
    body += (
        '<h2 id="involvement-in-crashes-per-kilometre-driven">'
        "Crashes per kilometre: highest among drivers aged 18–29</h2>"
        "<p>No source counts kilometres by the driver's age in Spain, so they are estimated: "
        "DGT's car kilometres are shared out by age with the average of two travel surveys' age "
        f"profiles, the Barcelona area's ({SURVEY_YEARS}) and Madrid's ({edm2018.SURVEY_YEAR}) "
        f'(<a href="data.html#{NOTES_ANCHOR}">method</a>). The direction of the differences is '
        "robust; their size depends on assumptions, so each ratio is given with its 95% "
        f"{definition_link('Sampling interval')} and the "
        f"{definition_link('Sensitivity range', 'range under other assumptions')}: "
        "the lowest and highest ratio when another region's profile stands for Spain, the "
        "kilometres the survey does not cover are given another age mix, the 65-and-over "
        "kilometres are split another way, or the drivers of unrecorded age are placed in one "
        "age group.</p>"
    )
    body += _ratio_table(f)
    body += (
        "<ul>"
        f"<li><strong>18–29</strong>: clearly above the 45–64 rate, {young['ratio']} times, and "
        f"at least {float(f.involved.loc['18-29', 'range_min']):.1f} times under every "
        "alternative.</li>"
        f"<li><strong>30–44</strong>: modestly above, {middle['ratio']} times, and above 1 "
        "under every alternative.</li>"
        f"<li><strong>65–74</strong>: cannot be told apart from the 45–64 rate "
        f"({f.per_km['65-74']['ratio']} times, with an interval that reaches 1 and a range of "
        f"{f.per_km['65-74']['range']}).</li>"
        f"<li><strong>75 and over</strong>: not established. The estimate, {f.per_km['75+']['ratio']} "
        f"times, rests on the split of the 65-and-over kilometres between 65–74 and 75 and "
        "over in Madrid's survey, which the Barcelona-area survey cannot supply, and the range "
        f"({f.per_km['75+']['range']}) includes 1 "
        f'(<a href="data.html#{OLDER_NOTES_ANCHOR}">why</a>). Madrid survey data: '
        f'<a href="{CRTM_URL}">Powered by CRTM</a>.</li>'
        "</ul>"
    )
    body += figure("dr1_involved_per_km", _per_km_alt(f), captions)
    body += (
        "<p>Compare any two age groups, or men and women, in the "
        '<a href="driver-risk.html">driver risk comparison</a>.</p>'
    )

    # ------------------------------------------------------------------- deaths once involved
    kill = f.killed
    body += (
        '<h2 id="deaths-once-a-crash-has-happened">'
        "Deaths once a crash has happened: highest at 75 and over</h2>"
        f"<p>Counted directly, with no kilometres, {kill['75+']:.1f} of every 1,000 car drivers "
        f"aged 75 and over involved in an injury crash in {YEAR} died within 30 days, and "
        f"{kill['65-74']:.1f} at 65–74, against {kill[REFERENCE]:.1f} at 45–64: "
        f"{float(k.loc['75+', 'killed_ratio_to_45_64']):.1f} times the 45–64 rate at 75 and over "
        f"(95% interval {_pair(k.loc['75+', 'killed_ratio_low'], k.loc['75+', 'killed_ratio_high'])}) "
        f"and {float(k.loc['65-74', 'killed_ratio_to_45_64']):.1f} times at 65–74 "
        f"({_pair(k.loc['65-74', 'killed_ratio_low'], k.loc['65-74', 'killed_ratio_high'])}). "
        "The rate counts only the driver's own death, so it does not show whether older "
        "drivers' crashes are more dangerous to others; like involvement, it does not show who "
        "caused a crash.</p>"
    )
    body += figure(
        "dr2_killed_per_involved",
        f"Dot chart of private-car drivers killed per 1,000 involved in an injury crash in {YEAR}, "
        f"by age, with 95% intervals. The rate is {kill['18-29']:.1f} at 18–29, "
        f"{kill['30-44']:.1f} at 30–44, {kill[REFERENCE]:.1f} at 45–64, "
        f"{kill['65-74']:.1f} at 65–74 and {kill['75+']:.1f} at 75 and over.",
        captions,
    )

    # ------------------------------------------------------------------- men and women
    ratios = f.adult
    involved_sex, killed_sex = f.involved_sex, f.killed_sex
    men_involved = ratios.loc["involved_per_1000_licences"]
    men_fatality = ratios.loc["deaths_per_1000_involved"]
    body += (
        '<h2 id="men-and-women">Men and women: men die far more often</h2>'
        "<p>Per kilometre, estimated in the same way, male car drivers were involved in injury "
        f"crashes {float(involved_sex.ratio):.2f} times as often as female drivers "
        f"(95% sampling interval {_pair(involved_sex.ratio_low, involved_sex.ratio_high, 2)}; "
        f"range {_pair(involved_sex.range_min, involved_sex.range_max, 2)}), so neither sex is "
        "shown to be involved more often for the distance driven, and they were killed "
        f"{float(killed_sex.ratio):.1f} times as often "
        f"({_pair(killed_sex.ratio_low, killed_sex.ratio_high)}; range "
        f"{_pair(killed_sex.range_min, killed_sex.range_max)}). Per licence holder, pooling "
        f"{f.sex_years}, men were involved {float(men_involved.ratio):.2f} times as often as "
        f"women ({_pair(men_involved.low, men_involved.high, 2)}), which on the estimated "
        "kilometres comes from their driving further; once involved, they died "
        f"{float(men_fatality.ratio):.2f} times as often "
        f"({_pair(men_fatality.low, men_fatality.high, 2)}), in every age band "
        f"(Figure {figure_ref('a3_sex_ratios')}).</p>"
    )
    body += figure(
        "a3_sex_ratios",
        f"Ratios of men's to women's rates for private-car drivers, {f.sex_years}, overall and by "
        "age band: involvement in injury crashes per licence holder, deaths per licence holder, "
        "and deaths per driver involved. Men's rates are above women's on all three measures "
        f"in every age band; at 18 and over men were involved {float(men_involved.ratio):.2f} "
        f"times as often, killed "
        f"{float(ratios.loc['deaths_per_million_licences'].ratio):.2f} times as often per "
        f"licence holder and {float(men_fatality.ratio):.2f} times as often once involved.",
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
            ("risk_national_ranges", "involvement and deaths per km by age: ratios and ranges"),
            ("risk_national_rates", "involvement and deaths per km by age, every profile"),
            ("risk_national_shares", "share of car kilometres by age, every profile"),
            ("risk_national_numerator", "drivers involved and killed by age"),
            ("risk_older_split", "65–74 and 75 and over under three splits"),
            ("risk_severity_and_licences", "deaths once involved, by age"),
            ("risk_coverage", "what DGT's car kilometres are made of"),
            ("risk_barcelona_rates", "Barcelona working days, three versions of the kilometres"),
            ("emef_exposure_contemporary", "car-driving kilometres per resident, EMEF"),
            ("emef_employment_benchmark", "the survey's employed share at 65 and over"),
            ("drivers_sex_ratios", "men against women per licence holder and once involved"),
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
def _share_table(f: SimpleNamespace) -> str:
    """Each age group's share of Spain's car kilometres under each survey and the average."""
    shares = f.shares
    by_method = {
        method: shares[shares.method == method].set_index("group").share_of_km
        for method in (national.BARCELONA_METHOD, national.MADRID_METHOD, national.CENTRAL_METHOD)
    }
    rows = [
        {
            "Age": LABELS[group],
            "Barcelona-area survey": _fmt_pct(float(by_method[national.BARCELONA_METHOD][group])),
            "Madrid survey": _fmt_pct(float(by_method[national.MADRID_METHOD][group])),
            "Average (used)": _fmt_pct(float(by_method[national.CENTRAL_METHOD][group])),
        }
        for group in GROUPS
    ]
    return table(
        pd.DataFrame(rows),
        "Share of car kilometres in Spain by the driver's age, from each survey's profile and "
        "their average, weekdays",
    )


COVERAGE_LABELS = {
    "working days": "Working days, as the survey measures them",
    "professionals' work driving": "Work trips of people who drive for a living (counted, not described)",
    "regional level": "More driving per resident in Spain than in the province",
    "non-working days": "Weekends and public holidays",
    "months outside the fieldwork": "Months outside the survey's fieldwork",
    "remainder (not explained)": "Not explained by any part above",
}


def _between(low: float, high: float) -> str:
    low, high = sorted((float(low), float(high)))
    one, two = _fmt_pct(low, 0), _fmt_pct(high, 0)
    return one if one == two else f"{one} to {two}"


def _coverage_table(f: SimpleNamespace) -> str:
    rows = [
        {
            "Part of DGT's car kilometres": label,
            "Billion km": (
                _fmt_dec(f.parts.loc[name, "bn_km_least_explained"])
                if f.parts.loc[name, "bn_km_least_explained"]
                == f.parts.loc[name, "bn_km_most_explained"]
                else f"{_fmt_dec(f.parts.loc[name, 'bn_km_least_explained'])} to "
                f"{_fmt_dec(f.parts.loc[name, 'bn_km_most_explained'])}"
            ),
            "Share of DGT's total": _between(
                f.parts.loc[name, "share_least_explained"],
                f.parts.loc[name, "share_most_explained"],
            ),
        }
        for name, label in COVERAGE_LABELS.items()
    ]
    total = float(f.parts.dgt_total_bn_km.iloc[0])
    return table(
        pd.DataFrame(rows),
        f"What the {YEAR} DGT car kilometres less taxis and ride-hailing cars "
        f"({_fmt_dec(total)} billion) are made of, as far as the data show. Each part is given "
        "at the setting that explains least and the one that explains most, and the parts are "
        "added in the order shown. Data: the CSV of the coverage of DGT's kilometres.",
    )


def _barcelona_table(f: SimpleNamespace) -> str:
    rows = []
    for group in GROUPS:
        part = f.city[f.city.age4 == group].set_index("denominator")
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
                else f"{value.ratio_to_45_64:.1f} ({_pair(value.ratio_low, value.ratio_high)})"
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


def technical_notes(captions: dict[str, str]) -> str:
    f = _facts()
    ranges = f.involved
    sampling = f.per_km
    body = (
        f'<h2 id="{NOTES_ANCHOR}">Driver age and sex: kilometres and crashes per kilometre</h2>'
        "<p>These notes give the method behind the rates per kilometre on the "
        f'<a href="drivers.html">drivers page</a>; <a href="{EXPOSURE_DOC}">the exposure study</a> '
        "gives it in full.</p>"
        "<h3>What is measured</h3>"
        f"<p>The numerator is DGT's count of private-car drivers involved in injury crashes in "
        f"{YEAR} and of those killed within 30 days, by age band; taxi and ride-hailing drivers "
        "are left out. No national source counts kilometres by the age of the driver, so the "
        "denominator is estimated.</p>"
        "<h3>From the surveys to Spain</h3>"
        "<p>The EMEF, the working-day mobility survey of the province of Barcelona, records the "
        "car trips its respondents drove on one working day, with each trip's duration and, from "
        f"2021, its straight-line distance in bands, from which the kilometres are estimated "
        f"(road distance is 1.45 times the straight line). Its {SURVEY_YEARS} editions give each "
        "age group's car-driver kilometres per resident, by sex. Madrid's "
        f"{edm2018.SURVEY_YEAR} household travel survey (Consorcio Regional de Transportes de "
        "Madrid) gives the same measure for the Madrid region by exact age. Each survey's "
        "kilometres per resident are applied to the population of Spain, which gives each age "
        "group's share of the kilometres. Neither region stands for Spain, and the two disagree "
        "most at 65 and over, so the estimate uses the average of the two shares; the "
        "Barcelona-area survey's 65-and-over kilometres are first put on Spain's mix of ages at "
        "65–74 and 75 and over, using Madrid's split between them.</p>"
    )
    body += _share_table(f)
    body += (
        "<h3>What DGT's kilometres are made of</h3>"
        "<p>These shares divide DGT's "
        f"{YEAR} car kilometres from inspection odometer readings, less taxis and ride-hailing "
        f"cars. Over the {f.working} working days of {YEAR} the Barcelona-area survey's driving "
        f"comes to {_fmt_pct(f.covered, 0)} of those kilometres. The rest is weekends and public "
        f"holidays ({f.non_working} days), more driving per resident in Spain than in the "
        "province, the work trips of people who drive for a living, the months outside the "
        "fieldwork, and a remainder that no measured part explains. Both surveys describe "
        "weekdays, so the estimate gives all of it the working-day age mix.</p>"
    )
    body += _coverage_table(f)
    body += (
        "<h3>The ranges</h3>"
        "<p>The range beside each ratio is the lowest and highest value under these alternatives, "
        "each computed around the published estimate: another regional profile (each survey "
        "alone, the Barcelona area carrying driving per licence holder instead of per resident, "
        "or one part of the province alone); another age mix for the weekends and holidays and "
        "for the remainder (the EMEF's weekend stays away, MOVILIA 2006's weekend trips and "
        "MOVILIA 2007's long car journeys); another split of the 65-and-over kilometres at 75; "
        "and all the drivers of unrecorded age placed in one age group. The first three are "
        "combined in every way; the last is tried alone. A range is the spread of the "
        "alternatives tried, not a confidence interval and not a bound: other choices would "
        "widen it. "
        f"At 18–29 the lowest ratio ({float(ranges.loc['18-29', 'range_min']):.1f}) comes "
        f"from: {ranges.loc['18-29', 'range_min_from']}; the highest "
        f"({float(ranges.loc['18-29', 'range_max']):.1f}) from: "
        f"{ranges.loc['18-29', 'range_max_from']}."
        "</p>"
        "<p>The 95% sampling interval reflects only sampling error in the surveys and chance "
        "variation in the crash counts. It is probably too narrow, because the resampling treats "
        "respondents as independent although the surveys sample them in clusters. The EMEF "
        "respondents aged 65 and over were in work more often in "
        f"{SURVEY_YEARS} ({_fmt_pct(float(f.recent.min()))} to {_fmt_pct(float(f.recent.max()))}) "
        f"than the census counts for Catalonia ({_fmt_pct(f.census)}); setting the share to "
        f"the census would lower the 65-and-over kilometres per resident by about "
        f"{_fmt_pct(f.employment_effect, 0)}.</p>"
        "<h3>Deaths per kilometre</h3>"
        "<p>Deaths per kilometre combine involvement per kilometre with deaths once involved, so "
        "they carry the estimate of kilometres. Drivers aged 65 and over were killed "
        f"{float(f.central.loc['65+', 'killed_ratio']):.1f} times as often per kilometre as "
        f"drivers aged 45–64 (95% sampling interval "
        f"{_pair(f.central.loc['65+', 'killed_ratio_low'], f.central.loc['65+', 'killed_ratio_high'])}; "
        f"range {_pair(f.killed_ranges.loc['65+', 'range_min'], f.killed_ranges.loc['65+', 'range_max'])}), "
        f"against {sampling['65+']['ratio']} times for involvement. Under every alternative "
        "the first ratio is above the second, so most of the excess in deaths per kilometre comes "
        "from how often a crash kills an older driver, not from how often older drivers are in "
        "crashes.</p>"
    )

    body += (
        "<h3>A check in Barcelona on working days</h3>"
        "<p>Inside Barcelona on working days, involvement per kilometre can be compared without "
        "carrying the survey to Spain or assuming anything about weekends: the Guàrdia Urbana's "
        f"{CITY_YEAR} records give the age of most of the car drivers involved in injury crashes "
        "in the city, uninjured drivers included, and the EMEF gives the kilometres the survey "
        f"area's residents drove inside the city on a working day, counted over the "
        f"{day_calendar.days_in_year(CITY_YEAR)[day_calendar.WORKING_DAY]} working days of "
        f"{CITY_YEAR}. The part of a trip into or out of the city that lies inside it cannot be "
        "measured, so the table gives three versions of the kilometres, and only the ratios "
        "between ages are read.</p>"
    )
    body += _barcelona_table(f)
    older_city = f.city_65.ratio_to_45_64
    body += (
        "<p>Across the three versions, drivers aged 65 and over were involved at "
        f"{_pair(older_city.min(), older_city.max())} times the rate of drivers aged 45–64, each "
        "with a 95% interval that includes 1, and drivers aged 18–29 at "
        f"{_pair(f.city[f.city.age4 == '18-29'].ratio_to_45_64.min(), f.city[f.city.age4 == '18-29'].ratio_to_45_64.max())} "
        "times it. The crashes include drivers whose kilometres the survey does not count "
        "(people living outside the survey area, traffic passing through, people driving for "
        "work), mostly of working age, so the older drivers' ratio is more likely biased down "
        "than up; leaving out the drivers recorded as on duty raises it to "
        f"{_pair(f.on_duty.ratio_to_45_64.min(), f.on_duty.ratio_to_45_64.max())}.</p>"
        "<h3>Men and women</h3>"
        "<p>The survey's kilometres are split by sex and carried to Spain in the same way as by "
        f"age; on that estimate men drove {_fmt_pct(float(f.men_share))} of car "
        f"kilometres in {YEAR}. Across all motor-vehicle drivers, which adds motorcyclists, "
        "moped riders and the drivers of vans, trucks and buses, the gaps per licence holder "
        "are wider. The licence holders are holders of any class of licence; the census gives "
        f"car-licence holders by sex and age for {str(f.b_licence.years.iloc[0]).replace('-', '–')} "
        "only, and counting only them raises the ratio of men's to women's deaths per licence "
        f"holder in those years from {float(f.b_licence.loc['licence holders of any class', 'ratio']):.2f} "
        f"to {float(f.b_licence.loc['B-licence holders', 'ratio']):.2f}.</p>"
        "<h3>Drivers whose age is not recorded</h3>"
        f"<p>They are {_fmt_pct(f.unknown_share)} of the drivers involved and are left out of "
        "every rate, which lowers each absolute rate by that share. The ratios assume their "
        "ages follow the recorded mix; the ranges include the case where all of them belong to "
        "one age group.</p>"
    )
    body += (
        f'<h3 id="{OLDER_NOTES_ANCHOR}">Drivers aged 75 and over</h3>'
        "<p>The EMEF's public files group everyone aged 65 and over, so the survey measures "
        "their driving as one group. The split between 65–74 and 75 and over comes from Madrid's "
        f"{edm2018.SURVEY_YEAR} survey, which has exact ages: the estimate for 75 and over is a "
        f"{definition_link('Conditional estimate', 'conditional estimate')}, true if drivers aged "
        "75 and over drive as much less than those aged 65–74 in Spain as in Madrid. Two other "
        "splits are tried in the range: Madrid's kilometres per licence holder applied to Spain's "
        "licence holders, and equal kilometres per licence holder at 65–74 and 75 and over. "
        "Licence holding falls from 65–74 to 75 and over about as much in the province of Madrid "
        "as in Spain, so the first changes little; the second gives the lowest ratios. The "
        f"sampling interval of the estimate ({sampling['75+']['interval']}) holds the split "
        "fixed, while the range ("
        f"{sampling['75+']['range']}) includes 1: the data do not establish that drivers aged "
        "75 and over are involved more often per kilometre than drivers aged 45–64, or by how "
        "much. What they do show, with no kilometres, is that a crash is far more often fatal "
        "for them (see the section on deaths once a crash has happened on "
        '<a href="drivers.html#deaths-once-a-crash-has-happened">the drivers page</a>).</p>'
    )
    return body
