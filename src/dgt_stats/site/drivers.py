"""Driver age and sex: how often car drivers are involved in crashes for the distance they drive,
and how often a crash kills the driver.

The page leads with involvement per kilometre driven by drivers of each age, estimated from the
EMEF working-day survey's age profile, Spain's population and DGT's car kilometres
(``scripts/exposure_risk.py``; ``docs/research/DRIVER_AGE_EXPOSURE.md``). It then checks the
result in Barcelona on working days, gives the model-dependent range for 65–74 and 75 and over,
deaths once involved, the former figure on owner-age kilometres and the comparison of men and
women. Every number is read from the ``risk_*`` and ``drivers_sex_*`` tables, and every
qualitative sentence is checked against them before the page is written.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import edm2018
from dgt_stats.emef import exposure
from dgt_stats.emef import variables as emef_variables
from dgt_stats.exposure_risk import barcelona as city_design
from dgt_stats.exposure_risk import calendar as day_calendar
from dgt_stats.exposure_risk import national
from dgt_stats.site.components import (
    _fmt_pct,
    downloads,
    evidence_note,
    figure,
    key_result,
    limitation,
    read_table,
    render_page,
    summary,
    table,
    technical,
)
from dgt_stats.site.numbers import _driver_numbers, _sex_numbers

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


def _rates_table(
    central: pd.DataFrame, licence: pd.DataFrame, ranges: pd.DataFrame, year: int
) -> str:
    rows = []
    for group in GROUPS:
        row = central.loc[group]
        reference = group == REFERENCE
        rows.append(
            {
                "Age": LABELS[group],
                "Drivers involved": row.involved,
                "Kilometres (billion)": row.billion_km,
                "Involved per billion km (95% interval)": (
                    f"{row.involved_per_bn_km:,.0f} "
                    f"({row.involved_per_bn_km_low:,.0f}–{row.involved_per_bn_km_high:,.0f})"
                ),
                "Ratio to 45–64 (95% interval)": "1 (reference)"
                if reference
                else f"{row.involved_ratio:.2f} ({_ci(row, 'involved_ratio')})",
                "Ratio, licence-calibrated transfer": ""
                if reference
                else f"{licence.loc[group, 'involved_ratio']:.2f}",
                "Sensitivity range of the ratio": ""
                if reference
                else f"{ranges.loc[group, 'min']:.2f}–{ranges.loc[group, 'max']:.2f}",
            }
        )
    return table(
        pd.DataFrame(rows),
        f"Car drivers involved in injury crashes per kilometre driven, by age, Spain, {year}. "
        "Kilometres by age from the EMEF's working-day profile applied to Spain's population, "
        "scaled to DGT's car kilometres less taxis and ride-hailing cars; the interval combines "
        "sampling error in the profile with Poisson error in the counts, and the sensitivity "
        "range covers every alternative in the table of sources below.",
        {"Drivers involved": "int", "Kilometres (billion)": "dec"},
    )


SOURCE_LABELS = {
    "regional profile": (
        "Another region's age profile (four parts of the province; Madrid "
        f"{edm2018.SURVEY_YEAR})"
    ),
    "licence-calibrated transfer": "Driving per licence holder, not per resident, carried to Spain",
    "distance": "Other treatments of trip distances",
    "survey years": "Other survey years",
    "professionals' work driving": "Professional drivers' unrecorded work driving",
    "older sample": "Survey's employed share at 65 and over set to the census",
    "non-working days": "A different age mix on weekends and holidays",
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
        "each alternative choice, Spain. The sensitivity range in the table above is the span "
        "of all of them.",
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


def _older_table(older: pd.DataFrame) -> str:
    rows = []
    for assumption, part in older.groupby("assumption", sort=False):
        part = part.set_index("group")
        rows.append(
            {
                "Assumption": assumption[:1].upper() + assumption[1:],
                "75 and over: share of the 65+ km": float(part.loc["75+", "share_of_65_plus_km"]),
                "65–74: ratio to 45–64": (
                    f"{part.loc['65-74', 'ratio_to_45_64']:.2f} ({_ci(part.loc['65-74'], 'ratio')})"
                ),
                "75 and over: ratio to 45–64": (
                    f"{part.loc['75+', 'ratio_to_45_64']:.2f} ({_ci(part.loc['75+'], 'ratio')})"
                ),
            }
        )
    return table(
        pd.DataFrame(rows),
        f"Model-dependent split of the 65-and-over kilometres, Spain, {YEAR}: car drivers involved "
        "in injury crashes per kilometre at 65–74 and at 75 and over, as ratios to drivers aged "
        "45–64, with 95% intervals, under three assumptions. None is a measurement; the "
        "65-and-over total is the central estimate's under each.",
        {"75 and over: share of the 65+ km": "pct0"},
    )


def _owner_table(comparison: pd.DataFrame) -> str:
    old = comparison[comparison.denominator.str.endswith("(former figure)")]
    rows = [
        {
            "Age (owner bands)": band.replace("-", "–").replace("75+", "75 and over"),
            "Involved per billion km": rate,
            "Ratio to 35–54": f"{ratio:.2f}",
        }
        for band, rate, ratio in zip(old.group, old.involved_per_bn_km, old.ratio_to_reference)
    ]
    return table(
        pd.DataFrame(rows),
        "The former figure: car drivers (taxi and ride-hailing drivers included) involved in "
        "injury crashes per kilometre driven by cars registered to owners of the same age, "
        f"Spain, {YEAR}, as ratios to 35–54.",
        {"Involved per billion km": "dec0"},
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
    level = all_rates[all_rates.method.str.startswith("A:") & (all_rates.group == "65+")]
    level = level.set_index("km_total").involved_per_bn_km
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
    sex_km = read_table("risk_sex_per_km").set_index("measure")
    b_licence = read_table("drivers_sex_b_licence").set_index("denominator")
    sex_numbers = _sex_numbers()
    sex_ratios, sex_rates = sex_numbers["ratios"], sex_numbers["rates"]
    sex_years = str(sex_rates.years.iloc[0]).replace("-", "–")
    trend = read_table("drivers_sex_trend")
    trend_years = f"{int(trend.year.min())}–{int(trend.year.max())}"

    young, older_all = central.loc["18-29"], central.loc["65+"]
    by_older = older.set_index(["assumption", "group"])
    old_75 = older[older.group == "75+"].ratio_to_45_64
    old_65 = older[older.group == "65-74"].ratio_to_45_64
    city_older = city[city.age4 == "65+"]
    city_young = city[city.age4 == "18-29"].ratio_to_45_64
    on_duty = city_all[
        (city_all.numerator == city_design.NUMERATORS[1]) & (city_all.age4 == "65+")
    ].ratio_to_45_64
    city_75 = city_split[city_split.age == "75+"].ratio_to_45_64
    owner = comparison[comparison.denominator.str.endswith("(former figure)")].set_index("group")
    owner_same = comparison[comparison.denominator.str.endswith("same age groups")].set_index(
        "group"
    )
    killed = {g: float(severity.loc[g, "killed_per_1000_involved"]) for g in severity.index}
    a_share = shares[shares.method.str.startswith("A:")].set_index("group")
    unknown_share = float(numerator.unknown_share.iloc[0])
    madrid = by_older.loc["Madrid survey: km per resident"]
    sensitivity = numbers["sensitivity"].set_index(["source", "variant", "group"]).involved_ratio
    employed_survey = employment[employment.source.str.startswith("EMEF")].set_index("year")
    employed_census = float(
        employment[employment.source.str.startswith("census")].employed_share.iloc[0]
    )
    early_years = [y for y in employed_survey.index if y < min(exposure.CONTEMPORARY_YEARS)]
    late_years = list(exposure.CONTEMPORARY_YEARS)
    employed_reweighted = float(
        sensitivity.loc[("older sample", "65+ employed share set to the census", "65+")]
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

    # Involvement per km: young drivers well above the middle-aged on every assumption; drivers
    # aged 65 and over slightly above them centrally, with a range that reaches 1.
    _check(
        float(young.involved_ratio_low) > 2 and float(ranges.loc["18-29", "min"]) > 1.5,
        "drivers aged 18-29 are clearly involved more often per km than 45-64 on every assumption",
    )
    _check(
        1 < float(older_all.involved_ratio) < 1.35
        and float(older_all.involved_ratio_low) > 0.95
        and 0.9 < float(ranges.loc["65+", "min"]) < 1.05
        and float(ranges.loc["65+", "max"]) < 2,
        "drivers aged 65 and over slightly more often than 45-64 centrally, about level to "
        "modestly more under the alternatives",
    )
    _check(
        bool((city_older.ratio_low < 1).all() and (city_older.ratio_high > 1).all())
        and bool((city_young > 1.8).all()),
        "in Barcelona on working days, 65+ at about the 45-64 rate (every interval includes 1) "
        "and the young at about twice it or more",
    )
    _check(
        older_range["75+"][0] > 1 and float(city_75.min()) < 1 < float(city_75.max()),
        "75 and over above the middle-aged rate per km nationally on every assumption, but not "
        "clearly in Barcelona",
    )
    _check(
        float(old_65.min()) > 0.8 and float(old_65.max()) < 1.2,
        "65-74 at about the middle-aged rate under the three split assumptions",
    )
    _check(
        float(severity.loc["75+", "killed_per_1000_involved_low"])
        > float(severity.loc[REFERENCE, "killed_per_1000_involved_high"])
        and float(severity.loc["65-74", "killed_per_1000_involved_low"])
        > float(severity.loc[REFERENCE, "killed_per_1000_involved_high"]),
        "drivers aged 65-74 and 75 and over die more often once involved than drivers aged 45-64",
    )
    _check(
        float(owner_same.loc["18-29", "ratio_to_reference"]) > float(young.involved_ratio) + 1
        and float(owner_same.loc["65+", "ratio_to_reference"]) < float(older_all.involved_ratio),
        "on the same age groups the owner kilometres put the young higher and 65+ lower",
    )
    killed_ratio_old = float(older_all.killed_ratio)
    _check(
        killed_ratio_old > 2 * float(older_all.involved_ratio),
        "older drivers' higher deaths per km come mainly from severity once involved",
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

    men_involved = sex_ratios.loc[("car", "18+", "involved_per_1000_licences")]
    men_fatality = sex_ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    men_killed = sex_ratios.loc[("car", "18+", "deaths_per_million_licences")]
    motor_killed = sex_ratios.loc[("motor", "18+", "deaths_per_million_licences")]
    motor_fatality = sex_ratios.loc[("motor", "18+", "deaths_per_1000_involved")]
    by_band_fatality = sex_ratios.xs(
        ("car", "deaths_per_1000_involved"), level=["scope", "measure"]
    ).drop(index="18+")
    per_km_involved = sex_km.loc["involved per km"]
    per_km_killed = sex_km.loc["killed per km"]
    _check(
        min(float(men_involved.low), float(men_fatality.low), float(men_killed.low)) > 1
        and float(men_fatality.ratio) > float(men_involved.ratio)
        and float(motor_killed.ratio) > float(men_killed.ratio)
        and float(motor_fatality.ratio) > float(men_fatality.ratio)
        and bool((by_band_fatality.low > 1).all()),
        "men are higher than women per licence holder and once involved, in every band",
    )
    _check(
        float(per_km_involved.ratio_high) < 1 and float(per_km_killed.ratio_low) > 2,
        "per km, men are involved slightly less often than women and killed far more often",
    )
    _check(
        float(b_licence.loc["B-licence holders", "ratio"])
        > float(b_licence.loc["licence holders of any class", "ratio"]),
        "counting only car-licence holders makes the men's excess slightly larger",
    )

    def ci(row: pd.Series) -> str:
        return f"{float(row.low):.2f}–{float(row.high):.2f}"

    young_span = (
        f"{float(ranges.loc['18-29', 'min']):.1f} to {float(ranges.loc['18-29', 'max']):.1f}"
    )
    old_span = _fmt_span(float(ranges.loc["65+", "min"]), float(ranges.loc["65+", "max"]))
    city_span = _fmt_span(
        float(city_older.ratio_to_45_64.min()), float(city_older.ratio_to_45_64.max())
    )
    body = summary(
        "Per kilometre driven, car drivers aged 18–29 were involved in injury crashes in Spain in "
        f"{year} about {float(young.involved_ratio):.1f} times as often as drivers aged 45–64 "
        f"(95% interval {_ci(young, 'involved_ratio')}). The kilometres by age are estimated from "
        "a Barcelona-area travel survey, and other defensible assumptions about them put the "
        f"ratio anywhere from {young_span}: young drivers are clearly involved more often, but "
        "by how much is uncertain. Drivers aged 65 and over were involved slightly more often "
        f"than the middle-aged, {float(older_all.involved_ratio):.2f} times "
        f"({_ci(older_all, 'involved_ratio')}; {old_span} under the other assumptions), and in "
        "Barcelona on working days, a separate check, at about the same rate "
        f"({city_span}, every interval including 1). For drivers aged 75 and over the estimate "
        "depends on how the 65-and-over kilometres are split: "
        f"{older_range['75+'][0]:.1f} to {older_range['75+'][1]:.1f} times the middle-aged rate "
        "nationally, and not clearly above it in Barcelona. What sets older drivers apart is the "
        f"outcome once a crash happens: {killed['75+']:.1f} of every 1,000 car drivers aged 75 "
        "and over involved in an injury crash died within 30 days, against "
        f"{killed[REFERENCE]:.1f} at 45–64."
    )

    # ------------------------------------------------------------------- per kilometre
    body += "<h2>Involvement in crashes per kilometre driven</h2>"
    body += key_result(
        f"{float(young.involved_ratio):.2f}×",
        "Car drivers aged 18–29 were involved in injury crashes "
        f"{float(young.involved_ratio):.2f} times as often per kilometre driven as drivers aged "
        f"45–64 (Spain, {year}; 95% interval {_ci(young, 'involved_ratio')}; sensitivity range "
        f"{_fmt_span(float(ranges.loc['18-29', 'min']), float(ranges.loc['18-29', 'max']))}).",
    )
    body += (
        "<p>No national source counts kilometres by the age of the driver, so they are estimated. "
        "The EMEF, the working-day mobility survey of the province of Barcelona, records the car "
        "trips its respondents drove on one working day, with each trip's duration and, from "
        f"{emef_variables.DISTANCE_FROM}, its straight-line distance in bands; each trip's "
        "kilometres are estimated from "
        f"those. From its {SURVEY_YEARS} editions come each age group's car-driver kilometres "
        f"per resident, by sex. Applied to the population of Spain and scaled to DGT's {YEAR} car "
        "kilometres from inspection odometer readings (less taxis and ride-hailing cars, whose "
        f"drivers are outside both counts), they put "
        f"{_fmt_pct(float(a_share.loc['18-29', 'share_of_km']))} of car kilometres with drivers "
        f"aged 18–29, {_fmt_pct(float(a_share.loc['45-64', 'share_of_km']))} with 45–64 and "
        f"{_fmt_pct(float(a_share.loc['65+', 'share_of_km']))} with 65 and over. The numerator is "
        f"DGT's count of private-car drivers involved in injury crashes in {year}, whoever "
        "caused the crash.</p>"
    )
    rows_alt = {group: f"{float(central.loc[group, 'involved_ratio']):.2f}" for group in GROUPS}
    body += figure(
        "dr1_involved_per_km",
        f"Dot chart of car drivers involved in injury crashes per kilometre in {year}, as ratios "
        "to drivers aged 45–64, on a log scale. Drivers aged 18–29 are at "
        f"{rows_alt['18-29']} times the reference and 30–44 at {rows_alt['30-44']}; drivers aged "
        f"65 and over are at {rows_alt['65+']}. Grey bands show sensitivity ranges; the "
        "model-dependent rows for 65–74 and 75 and over show only a band, from "
        f"{older_range['65-74'][0]:.1f} to {older_range['65-74'][1]:.1f} for 65–74 and from "
        f"{older_range['75+'][0]:.1f} to {older_range['75+'][1]:.1f} for 75 and over.",
        captions,
    )
    body += _rates_table(central, licence, ranges, year)
    body += (
        "<p>The interval and the sensitivity range answer different questions. The interval is "
        "sampling and count error. The range is how far the ratio moves under other defensible "
        "choices, set out in the table below. For drivers aged 18–29 the largest is which "
        "region's age profile stands in for Spain's "
        f"({_fmt_span(float(regional_young['min']), float(regional_young['max']))}). Carrying "
        "the survey's driving per licence holder rather than per resident to Spain gives "
        f"{float(licence.loc['18-29', 'involved_ratio']):.2f}, because young people in the "
        "province of Barcelona hold car licences less often than in Spain as a whole. For 65 "
        "and over the treatments of trip distances give "
        f"{_fmt_span(float(distance_old['min']), float(distance_old['max']))}, leaving out the "
        "long trips that have no distance band raising it most; a different age mix on weekends "
        f"lowers it to {_fmt_span(float(weekend['min']), float(weekend['max']))}; and the "
        "regional profiles give "
        f"{_fmt_span(float(regional_old['min']), float(regional_old['max']))}, from Barcelona "
        "city's to the Madrid survey's. "
        "The level of the rates also depends on DGT's kilometre total "
        f"(from {float(level.min()):,.0f} to {float(level.max()):,.0f} per billion km for the "
        "65-and-over group across the variants), but their ratios do not.</p>"
    )
    body += technical("Sources of the sensitivity range", _sources_table(by_source))
    body += (
        "<p>Two of those choices concern the survey's older respondents. The share of them in "
        f"work was about {_fmt_pct(float(employed_survey.loc[early_years, 'employed_share'].mean()))} "
        f"in {min(early_years)}–{max(early_years)}, the same as the census for Catalonia, but "
        f"{_fmt_pct(float(employed_survey.loc[late_years, 'employed_share'].min()))} to "
        f"{_fmt_pct(float(employed_survey.loc[late_years, 'employed_share'].max()))} in "
        f"{SURVEY_YEARS}; setting it back to the census share moves the 65-and-over ratio from "
        f"{float(older_all.involved_ratio):.2f} to {employed_reweighted:.2f}. And the survey "
        "does not record the work trips of people who drive for a living, most of them under "
        "65: counting a quarter or a half of those trips as car trips raises the ratio to "
        f"{_fmt_span(float(professional['min']), float(professional['max']))}. Both point the "
        "same way, so the central figure for 65 and over is more likely too low than too "
        "high.</p>"
    )
    body += evidence_note(
        "The kilometres by age rest on one region's survey transferred to Spain, so the ratios "
        "are estimates with ranges, not measurements. The method, its checks and every "
        f'sensitivity analysis are set out in <a href="{EXPOSURE_DOC}">the exposure study</a>.'
    )

    # ------------------------------------------------------------------- Barcelona
    body += "<h2>A check in Barcelona city on working days</h2>"
    body += (
        "<p>In Barcelona the comparison can be made inside one city on working days, without "
        "the transfer to Spain or an assumption about weekends. The Guàrdia Urbana's "
        f"{CITY_YEAR} records give the age of {_fmt_pct(1 - city_unknown_share)} of the car "
        "drivers involved in injury crashes in the city on working days, uninjured drivers "
        f"included; the EMEF gives the kilometres the survey area's residents drove inside the "
        f"city on a working day in {SURVEY_YEARS}. The "
        f"{day_calendar.days_in_year(CITY_YEAR)[day_calendar.WORKING_DAY]} working days "
        f"of {CITY_YEAR} (weekdays less the Catalan and Barcelona public holidays) are counted. "
        "The part of a trip into or out of the city that lies inside it cannot be measured, so "
        "the table gives three versions of the kilometres, and only the ratios between ages are "
        "read.</p>"
    )
    body += _barcelona_table(city)
    body += (
        "<p>Drivers aged 65 and over were involved at about the rate of drivers aged 45–64 "
        f"({city_span}; every interval includes 1), and drivers aged 18–29 at about "
        f"{float(city_young.median()):.1f} times it ({_span(city_young)}). The crashes include "
        "drivers whose kilometres the survey does not count: people living outside the survey "
        "area, traffic passing through the city, and people driving ordinary cars for work. "
        "They are mostly of working age, so the older drivers' ratio is more likely biased "
        "down than up; leaving out the drivers recorded as on duty raises it to "
        f"{_span(on_duty)}. The drivers with no recorded age are almost all records with no "
        "age, sex or injury, probably drivers who were never identified; the ratios assume "
        "their ages follow the recorded mix (if all were 65 or over, the ratio inside the city "
        f"would be {float(city_unknown_old.loc['65+']):.2f}).</p>"
    )

    # ------------------------------------------------------------------- 75 and over
    body += "<h2>Ages 75 and over</h2>"
    body += evidence_note(
        "No source available to this study measures driving at 75 and over separately from "
        "65–74; the figures in this section depend on an assumption and are labelled "
        "model-dependent."
    )
    body += (
        "<p>The EMEF's public files group everyone aged 65 and over, although the survey "
        f"sampled 65–74 and 75 and over separately until {emef_variables.OLDER_STRATA_LAST}; a "
        "request for the split has been prepared. The Madrid household travel survey of "
        f"{edm2018.SURVEY_YEAR} records exact ages: there, "
        "residents aged 75 and over drove "
        f"{float(madrid.loc['75+', 'ratio_75_to_65_74_male']):.2f} times the distance per "
        "resident of those aged 65–74 if men and "
        f"{float(madrid.loc['75+', 'ratio_75_to_65_74_female']):.2f} times if women. Dividing "
        "the 65-and-over kilometres with those ratios, or with two alternatives based on "
        "licence holding, gives the table below.</p>"
    )
    body += _older_table(older)
    body += (
        "<p>Under these assumptions drivers aged 65–74 are involved in injury crashes at about "
        f"the middle-aged rate per kilometre ({_span(old_65)}) and drivers aged 75 and over "
        f"above it ({_span(old_75)}). Repeating the split under every alternative for the "
        "65-and-over kilometres widens the range for 75 and over to "
        f"{older_range['75+'][0]:.2f}–{older_range['75+'][1]:.2f}. In Barcelona's working-day "
        f"check the same splits give {_span(city_75)}, so there the direction is not "
        "established. The national evidence supports a higher rate at 75 and over but not a "
        "single figure, so none is given. The Madrid survey data are reused under the "
        "open-data licence of the Consorcio Regional de Transportes de Madrid. "
        f'<a href="{CRTM_URL}">Powered by CRTM</a>.</p>'
    )

    # ------------------------------------------------------------------- deaths once involved
    body += "<h2>Deaths once a crash has happened</h2>"
    body += key_result(
        f"{killed['75+'] / killed[REFERENCE]:.1f}×",
        "Car drivers aged 75 and over who were involved in an injury crash died within 30 days "
        f"{killed['75+'] / killed[REFERENCE]:.1f} times as often as drivers aged 45–64 "
        f"({killed['75+']:.1f} against {killed[REFERENCE]:.1f} per 1,000 drivers involved, "
        f"{year}).",
    )
    body += (
        "<p>This rate divides the car drivers killed within 30 days by all car drivers involved "
        "in injury crashes, injured or not, of the same age and year, so no measure of driving "
        f"enters it. It is {killed['18-29']:.1f} per 1,000 at 18–29, {killed['30-44']:.1f} at "
        f"30–44, {killed[REFERENCE]:.1f} at 45–64, {killed['65-74']:.1f} at 65–74 and "
        f"{killed['75+']:.1f} at 75 and over. Combined with involvement per kilometre, it means "
        "that drivers aged 65 and over were killed "
        f"{killed_ratio_old:.1f} times as often per kilometre driven as drivers aged 45–64 "
        f"({_ci(older_all, 'killed_ratio')}), although they were involved in crashes only "
        f"{float(older_all.involved_ratio):.1f} times as often: their excess deaths come mainly "
        "from the outcome once involved, not from being involved in more crashes.</p>"
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
        "<p>The rate counts only the driver's own death. DGT's tables do not say how often "
        "other people in the same crashes died, so it cannot show whether older drivers' "
        "crashes are more dangerous to others; and involvement counts every driver in an injury "
        "crash, so neither rate says who caused it.</p>"
    )

    # ------------------------------------------------------------------- former figure
    body += "<h2>Why the former figure differed</h2>"
    body += (
        "<p>This page used to divide the same drivers, taxi and ride-hailing drivers included, "
        "by DGT's kilometres of cars registered to owners of each age, the only kilometres by "
        "age that DGT publishes. With the age groups and reference used now, those owner "
        "kilometres put drivers aged 18–29 at "
        f"{float(owner_same.loc['18-29', 'ratio_to_reference']):.2f} times the 45–64 rate and "
        f"drivers aged 65 and over at {float(owner_same.loc['65+', 'ratio_to_reference']):.2f}; "
        f"the driver-age kilometres give {float(young.involved_ratio):.2f} and "
        f"{float(older_all.involved_ratio):.2f}. (The figure the page used to show, "
        f"{float(owner.loc['18-24', 'ratio_to_reference']):.2f}, compared drivers aged 18–24 "
        "with 35–54.) A car's owner is often not its driver: young people drive cars registered "
        "to their parents, and older owners' cars are partly driven by others. The owner "
        "kilometres therefore credited too little driving to the young and too much to the "
        "old.</p>"
    )
    body += technical("The former owner-age figures", _owner_table(comparison))

    # ------------------------------------------------------------------- men and women
    body += "<h2>Men and women</h2>"
    body += (
        "<p>The survey's kilometres can be split by sex and carried to Spain in the same way as "
        f"by age. On that estimate men drove {_fmt_pct(float(per_km_involved.men_share_of_km))} "
        f"of car kilometres in {year}, and per kilometre male private-car drivers aged 18 and "
        f"over were involved in injury crashes slightly less often than female drivers "
        f"({float(per_km_involved.ratio_men_to_women):.2f} times; {ci_km(per_km_involved)}) but "
        f"killed {float(per_km_killed.ratio_men_to_women):.1f} times as often "
        f"({ci_km(per_km_killed)}). Per licence holder, pooling {sex_years}, men were involved "
        f"{float(men_involved.ratio):.2f} times as often as women ({ci(men_involved)}) and, once "
        f"involved, died {float(men_fatality.ratio):.2f} times as often ({ci(men_fatality)}); "
        f"combined, they died at the wheel {float(men_killed.ratio):.2f} times as often "
        f"({ci(men_killed)}). So men's higher involvement per licence holder comes from driving "
        "further, while their higher death rate holds per kilometre and once a crash has "
        "happened. The gap once involved holds in every age band.</p>"
    )
    body += figure(
        "a3_sex_ratios",
        f"Ratios of men's to women's rates for private-car drivers, {sex_years}, overall and by "
        "age band: involvement in injury crashes per licence holder, deaths per licence holder, "
        "and deaths per driver involved",
        captions,
    )
    body += (
        "<p>Across all motor-vehicle drivers, which adds motorcyclists, moped riders, the drivers "
        "of vans, trucks and buses and other motor vehicles, the gaps are wider: men died "
        f"{float(motor_killed.ratio):.2f} times as often as women per licence holder and "
        f"{float(motor_fatality.ratio):.2f} times as often once involved. The licence holders "
        "are holders of any class of licence; counting only car-licence holders, which the "
        "census gives by sex and age for "
        f"{str(b_licence.years.iloc[0]).replace('-', '–')} only, raises the men's excess in "
        f"deaths per licence holder from {float(b_licence.loc['licence holders of any class', 'ratio']):.2f} "
        f"to {float(b_licence.loc['B-licence holders', 'ratio']):.2f} in those years.</p>"
    )
    body += technical("Detailed counts by sex", _sex_rates_table(sex_rates, sex_years))

    body += limitation(
        "The kilometres by age and sex are estimates transferred from one region's working-day "
        "survey; DGT describes its kilometre totals as valid only in aggregate. The crash counts "
        "include foreign and unlicensed drivers. Drivers whose age the tables do not record "
        f"({_fmt_pct(unknown_share)} of those involved) are left out of every rate, which lowers "
        "each absolute rate by that share; the ratios assume their ages follow the recorded mix "
        "(if all were aged 18–29, the young drivers' ratio would be "
        f"{unknown_young:.2f})."
    )
    body += downloads(
        [
            ("risk_national_rates", "involvement and deaths per km by age, every method"),
            ("risk_national_sensitivity", "the ratios under every alternative choice"),
            ("risk_national_shares", "kilometres by age, every method"),
            ("risk_national_numerator", "drivers involved and killed by age"),
            ("risk_weekend_sensitivity", "weekend and holiday sensitivity"),
            ("risk_licence_prevalence", "car-licence holders per resident, Spain and province"),
            ("emef_employment_benchmark", "survey's employed share at 65 and over"),
            ("risk_barcelona_rates", "Barcelona working days, three denominators"),
            ("risk_barcelona_day_type", "Barcelona crashes by type of day"),
            ("risk_older_split", "65–74 and 75 and over, model-dependent"),
            ("risk_older_sensitivity", "65–74 and 75 and over under every alternative"),
            ("risk_barcelona_older", "65–74 and 75 and over in Barcelona"),
            ("edm_older_split", "Madrid survey: driving above 65"),
            ("risk_severity_and_licences", "deaths once involved and per licence holder"),
            ("risk_owner_age_comparison", "the former owner-age figures"),
            ("q7_km_by_owner_age", "DGT kilometres by owner age"),
            ("risk_sex_per_km", "men against women per km"),
            ("drivers_sex_rates", "rates by sex and age"),
            ("drivers_sex_ratios", "men against women"),
            ("drivers_sex_b_licence", "men against women per car-licence holder"),
            ("drivers_sex_trend", f"by sex and year, {trend_years}"),
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
