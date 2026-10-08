"""Driver age and sex: how often car drivers are involved in crashes for the distance they drive,
and how often a crash kills the driver.

The page leads with involvement per kilometre driven by drivers of each age, estimated from the
EMEF working-day survey's age profile, Spain's population and DGT's car kilometres
(``scripts/exposure_risk.py``; ``docs/research/DRIVER_AGE_EXPOSURE.md``). It then checks the
result in Barcelona on working days, gives the model-dependent range for 65–74 and 75 and over,
deaths once involved, the former figure on owner-age kilometres and the comparison of men and
women. Every number is read from the ``risk_*``, ``q7_*`` and ``drivers_sex_*`` tables, and every
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
from dgt_stats.site.numbers import _sex_numbers

REFERENCE = "45-64"
YEAR = national.YEAR
CITY_YEAR = city_design.YEAR
SURVEY_YEARS = f"{min(exposure.CONTEMPORARY_YEARS)}–{max(exposure.CONTEMPORARY_YEARS)}"
CENTRAL_KM = "less taxi and ride-hailing"
GROUPS = ("16-29", "30-44", "45-64", "65+")
LABELS = {
    "16-29": "18–29",
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


def _rates_table(central: pd.DataFrame, ranges: dict[str, str], year: int) -> str:
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
                "Sensitivity range of the ratio": "" if reference else ranges[group],
            }
        )
    return table(
        pd.DataFrame(rows),
        f"Car drivers involved in injury crashes per kilometre driven, by age, Spain, {year}. "
        "Kilometres by age from the EMEF's working-day profile applied to Spain's population, "
        "scaled to DGT's car kilometres less taxis and ride-hailing cars; the interval combines "
        "sampling error in the profile with Poisson error in the counts, and the sensitivity "
        "range covers the other regional profiles and weekend mixes.",
        {"Drivers involved": "int", "Kilometres (billion)": "dec"},
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
        f"days, {CITY_YEAR}, as ratios to drivers aged 45–64 under three denominators, with 95% "
        f"intervals. The kilometres are EMEF {SURVEY_YEARS} car-driver trips inside the city, with "
        "trips that cross the city boundary counted not at all, at the length of a trip inside "
        "the city, or in full.",
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
                "65–74: ratio to 45–64": f"{part.loc['65-74', 'ratio_to_45_64']:.2f}",
                "75 and over: ratio to 45–64": f"{part.loc['75+', 'ratio_to_45_64']:.2f}",
            }
        )
    return table(
        pd.DataFrame(rows),
        f"Model-dependent split of the 65-and-over kilometres, Spain, {YEAR}: car drivers involved "
        "in injury crashes per kilometre at 65–74 and at 75 and over, as ratios to drivers aged "
        "45–64, under four assumptions. None is a measurement; the measured 65-and-over total is "
        "the same under each.",
        {"75 and over: share of the 65+ km": "pct0"},
    )


def _owner_table(comparison: pd.DataFrame) -> str:
    old = comparison[comparison.denominator.str.startswith("km of cars registered")]
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
        "The former figure: car drivers involved in injury crashes per kilometre driven by cars "
        f"registered to owners of the same age, Spain, {YEAR}, as ratios to 35–54.",
        {"Involved per billion km": "dec0"},
    )


def _sex_rates_table(rates_table: pd.DataFrame, years: str) -> str:
    rows = []
    for scope, scope_label in (("car", "Car drivers"), ("motor", "All motor-vehicle drivers")):
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
        "of licence.",
        {
            "Involved per 1,000 licence holders a year": "dec2",
            "Killed per million licence holders a year": "dec",
            "Killed per 1,000 involved": "dec",
            "Drivers killed": "int",
        },
    )


def page_drivers(captions: dict[str, str]) -> str:
    rates = read_table("risk_national_rates")
    year = YEAR
    central_rates = rates[rates.km_total == CENTRAL_KM]
    central = central_rates[central_rates.method.str.startswith("A:")].set_index("group")
    regional = central_rates.groupby("group").involved_ratio
    weekend = read_table("risk_weekend_sensitivity")
    spread = (
        pd.concat(
            [
                central_rates[["group", "involved_ratio"]].rename(
                    columns={"involved_ratio": "ratio"}
                ),
                weekend[["group", "ratio_to_45_64"]].rename(columns={"ratio_to_45_64": "ratio"}),
            ]
        )
        .groupby("group")
        .ratio
    )
    ranges = {group: _span(spread.get_group(group)) for group in GROUPS if group != REFERENCE}
    level = rates.groupby("km_total").apply(
        lambda f: float(
            f[f.method.str.startswith("A:") & (f.group == "65+")].involved_per_bn_km.iloc[0]
        ),
        include_groups=False,
    )
    barcelona = read_table("risk_barcelona_rates")
    older = read_table("risk_older_split")
    severity = read_table("risk_severity_and_licences").set_index("group")
    comparison = read_table("risk_owner_age_comparison")
    numerator = read_table("risk_national_numerator").set_index("group")
    shares = read_table("risk_national_shares")
    sex_numbers = _sex_numbers()
    sex_ratios, sex_rates = sex_numbers["ratios"], sex_numbers["rates"]
    sex_years = str(sex_rates.years.iloc[0]).replace("-", "–")
    trend = read_table("drivers_sex_trend")
    trend_years = f"{int(trend.year.min())}–{int(trend.year.max())}"

    young, older_all = central.loc["16-29"], central.loc["65+"]
    by_older = older.set_index(["assumption", "group"])
    old_75 = older[older.group == "75+"].ratio_to_45_64
    old_65 = older[older.group == "65-74"].ratio_to_45_64
    city_older = barcelona[barcelona.age4 == "65+"].ratio_to_45_64
    city_young = barcelona[barcelona.age4 == "16-29"].ratio_to_45_64
    owner = comparison[comparison.denominator.str.startswith("km of cars")].set_index("group")
    killed = {g: float(severity.loc[g, "killed_per_1000_involved"]) for g in severity.index}
    a_share = shares[shares.method.str.startswith("A:")].set_index("group")
    unknown_share = float(numerator.unknown_share.iloc[0])
    madrid = by_older.loc["Madrid survey: km per resident"]

    # Involvement per km: young drivers well above the middle-aged on every method; drivers aged
    # 65 and over level with them or modestly above, never below the interval's reach.
    _check(
        float(young.involved_ratio_low) > 2 and float(regional.get_group("16-29").min()) > 1.5,
        "drivers aged 18-29 are involved at about two and a half times the 45-64 rate per km",
    )
    _check(
        0.95 < float(older_all.involved_ratio_low)
        and float(older_all.involved_ratio) < 1.3
        and float(spread.get_group("65+").max()) < 2,
        "drivers aged 65 and over are involved about as often per km as 45-64, or modestly more",
    )
    _check(
        bool((city_older < 1.2).all()) and bool((city_young > 1.8).all()),
        "in Barcelona on working days, 65+ at about the 45-64 rate and the young at twice it",
    )
    _check(
        float(old_75.min()) > 1.2 and float(old_65.min()) > 0.8 and float(old_65.max()) < 1.2,
        "75 and over above the middle-aged rate per km on every assumption, 65-74 at it",
    )
    _check(
        float(severity.loc["75+", "killed_per_1000_involved_low"])
        > float(severity.loc[REFERENCE, "killed_per_1000_involved_high"])
        and float(severity.loc["65-74", "killed_per_1000_involved_low"])
        > float(severity.loc[REFERENCE, "killed_per_1000_involved_high"]),
        "drivers aged 65-74 and 75 and over die more often once involved than drivers aged 45-64",
    )
    _check(
        float(owner.loc["18-24", "ratio_to_reference"]) > 5
        and float(owner.loc["65-74", "ratio_to_reference"]) < 0.8,
        "the owner-age figure put the young far higher and 65-74 far lower",
    )
    killed_ratio_old = float(older_all.killed_ratio)
    _check(
        killed_ratio_old > 2 * float(older_all.involved_ratio),
        "older drivers' higher deaths per km come mainly from severity once involved",
    )

    men_involved = sex_ratios.loc[("car", "18+", "involved_per_1000_licences")]
    men_fatality = sex_ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    men_killed = sex_ratios.loc[("car", "18+", "deaths_per_million_licences")]
    motor_killed = sex_ratios.loc[("motor", "18+", "deaths_per_million_licences")]
    motor_fatality = sex_ratios.loc[("motor", "18+", "deaths_per_1000_involved")]
    by_band_fatality = sex_ratios.xs(
        ("car", "deaths_per_1000_involved"), level=["scope", "measure"]
    ).drop(index="18+")
    _check(
        min(float(men_involved.low), float(men_fatality.low), float(men_killed.low)) > 1
        and float(men_fatality.ratio) > float(men_involved.ratio)
        and float(motor_killed.ratio) > float(men_killed.ratio)
        and float(motor_fatality.ratio) > float(men_fatality.ratio)
        and bool((by_band_fatality.low > 1).all()),
        "men are higher than women on every measure, most of all once involved, in every band",
    )

    def ci(row: pd.Series) -> str:
        return f"{float(row.low):.2f}–{float(row.high):.2f}"

    body = summary(
        "Per kilometre driven, car drivers aged 18–29 were involved in injury crashes about "
        f"{float(young.involved_ratio):.1f} times as often as drivers aged 45–64 in {year} "
        f"(95% interval {_ci(young, 'involved_ratio')}). Drivers aged 65 and over were involved "
        f"about as often as the middle-aged, or modestly more ({float(older_all.involved_ratio):.2f}; "
        f"{_ci(older_all, 'involved_ratio')}), and in Barcelona on working days, where the "
        "comparison is matched in place and time, about as often or less. Above 75 the evidence "
        "is model-dependent: per kilometre, drivers aged 75 and over appear to be involved "
        f"{float(old_75.min()):.1f} to {float(old_75.max()):.1f} times as often as the "
        "middle-aged, and drivers aged 65–74 at the middle-aged rate. What sets older drivers "
        f"apart is the outcome once a crash happens: {killed['75+']:.1f} of every 1,000 drivers "
        f"aged 75 and over involved in an injury crash died within 30 days, against "
        f"{killed[REFERENCE]:.1f} at 45–64."
    )

    # ------------------------------------------------------------------- per kilometre
    body += "<h2>Involvement in crashes per kilometre driven</h2>"
    body += key_result(
        f"{float(young.involved_ratio):.2f}×",
        "Car drivers aged 18–29 were involved in injury crashes "
        f"{float(young.involved_ratio):.2f} times as often per kilometre driven as drivers aged "
        f"45–64 (Spain, {year}; 95% interval {_ci(young, 'involved_ratio')}; sensitivity range "
        f"{ranges['16-29']}).",
    )
    body += (
        "<p>No national source counts kilometres by the age of the driver, so the kilometres "
        "are estimated. The EMEF, the annual working-day mobility survey of the province of "
        "Barcelona, records every car trip its respondents drive on one working day; from its "
        f"{SURVEY_YEARS} editions comes each age group's car-driver kilometres per resident, by "
        f"sex. Applied to the population of Spain and scaled to DGT's {YEAR} car kilometres from "
        "inspection odometer readings (less taxis and ride-hailing cars, whose drivers are "
        f"outside both counts), it puts {_fmt_pct(float(a_share.loc['16-29', 'share_of_km']))} of "
        f"car kilometres with drivers aged 18–29, {_fmt_pct(float(a_share.loc['45-64', 'share_of_km']))} "
        f"with 45–64 and {_fmt_pct(float(a_share.loc['65+', 'share_of_km']))} with 65 and over. "
        "The numerator is DGT's count of private-car drivers involved in injury crashes in "
        f"{year}, whoever caused the crash.</p>"
    )
    body += figure(
        "dr1_involved_per_km",
        f"Dot chart of car drivers involved in injury crashes per kilometre in {year}, as ratios "
        "to drivers aged 45–64, on a log scale. Drivers aged 18–29 are at about 2.6 times the "
        "reference and 30–44 at about 1.4; drivers aged 65 and over are at about 1.2, with an "
        "interval reaching 1. Grey bands show sensitivity ranges; the model-dependent rows for "
        "65–74 and 75 and over show only a band, around 1 for 65–74 and from about 1.3 to 2.2 "
        "for 75 and over.",
        captions,
    )
    body += _rates_table(central, ranges, year)
    body += (
        "<p>The interval and the sensitivity range answer different questions. The interval is "
        "sampling and count error. The range is how far the ratio moves under other defensible "
        "choices: the age profile of another part of the province or of the Madrid household "
        f"survey of {edm2018.SURVEY_YEAR} in place of the province's, and a different age mix on weekends and "
        "holidays, which the survey does not cover. The transfer from one region to Spain "
        "matters most for the youngest and oldest groups, whose driving varies most between "
        "city and country. The level of the rates also depends on DGT's kilometre total "
        f"(from {float(level.min()):,.0f} to {float(level.max()):,.0f} per billion km for the "
        "65-and-over group across the variants), but their ratios do not.</p>"
    )
    body += evidence_note(
        "The kilometres by age rest on one region's survey transferred to Spain, so the ratios "
        "are estimates with ranges, not measurements. The method, its checks and every "
        f'sensitivity analysis are set out in <a href="{EXPOSURE_DOC}">the exposure study</a>.'
    )

    # ------------------------------------------------------------------- Barcelona
    body += "<h2>A check matched in place and time: Barcelona on working days</h2>"
    body += (
        "<p>Barcelona allows a comparison that needs neither the transfer to Spain nor an "
        f"assumption about weekends. The Guàrdia Urbana's {CITY_YEAR} records give the exact age of every "
        "driver involved in a crash in the city, uninjured drivers included, and its date; the "
        "EMEF gives the kilometres driven inside the city on a working day. The "
        f"{day_calendar.days_in_year(CITY_YEAR)[day_calendar.WORKING_DAY]} working days "
        f"of {CITY_YEAR} (weekdays less the Catalan and Barcelona public holidays) are matched to them. "
        "The part of a trip into or out of the city that lies inside it cannot be measured, so "
        "three denominators bracket it, and only the ratios between ages are read.</p>"
    )
    body += _barcelona_table(barcelona)
    body += (
        "<p>On every denominator, drivers aged 65 and over were involved at about the rate of "
        f"drivers aged 45–64 or below it ({_span(city_older)}), and drivers aged 18–29 at about "
        f"twice it ({_span(city_young)}). The police do not record where drivers live, so the "
        "numerator includes drivers from outside the province, whose kilometres the survey "
        "does not count.</p>"
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
        "the measured 65-and-over kilometres with those ratios, or with three alternatives, "
        "gives the table below.</p>"
    )
    body += _older_table(older)
    body += (
        "<p>On every assumption, drivers aged 65–74 are involved in injury crashes at about the "
        f"middle-aged rate per kilometre ({_span(old_65)}), and drivers aged 75 and over above "
        f"it ({_span(old_75)}). The evidence supports that direction but not a single rate for "
        "75 and over, so none is given. The Madrid survey data are reused under the open-data "
        "licence of the Consorcio Regional de Transportes de Madrid. "
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
        f"enters it. It is {killed['16-29']:.1f} per 1,000 at 18–29, {killed['30-44']:.1f} at "
        f"30–44, {killed[REFERENCE]:.1f} at 45–64, {killed['65-74']:.1f} at 65–74 and "
        f"{killed['75+']:.1f} at 75 and over. Combined with involvement per kilometre, it means "
        "that drivers aged 65 and over were killed "
        f"{killed_ratio_old:.1f} times as often per kilometre driven as drivers aged 45–64 "
        f"({_ci(older_all, 'killed_ratio')}), although they were involved in crashes only "
        f"{float(older_all.involved_ratio):.1f} times as often: their excess deaths come from "
        "the outcome once involved, not from being involved in more crashes.</p>"
    )
    body += figure(
        "dr2_killed_per_involved",
        f"Dot chart of private-car drivers killed per 1,000 involved in an injury crash in {year}, "
        "by age, with 95% intervals. The rate is about 4 to 5 per 1,000 up to 64, about 8.5 at "
        "65–74 and about 16 at 75 and over.",
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
        "<p>This page used to divide the same drivers by DGT's kilometres of cars registered to "
        "owners of each age, the only kilometres by age that DGT publishes. On that basis drivers "
        f"aged 18–24 were involved {float(owner.loc['18-24', 'ratio_to_reference']):.2f} times "
        "as often per kilometre as drivers aged 35–54, and drivers aged 65–74 "
        f"{float(owner.loc['65-74', 'ratio_to_reference']):.2f} times as often. A car's owner "
        "is often not its driver: young people drive cars registered to their parents, and "
        "older owners' cars are partly driven by others. The owner kilometres therefore credited "
        "too little driving to the young and too much to the old, which inflated the young "
        "drivers' rate and deflated the older drivers'. Measured by the driver's age, the "
        "young drivers' excess is about two and a half times, not nearly seven.</p>"
    )
    body += technical("The former owner-age figures", _owner_table(comparison))

    # ------------------------------------------------------------------- men and women
    body += "<h2>Men and women</h2>"
    body += (
        "<p>No source records kilometres driven by sex, so men and women aged 18 and over are "
        f"compared per licence holder and per driver involved, pooling {sex_years}. Male car "
        f"drivers were involved in injury crashes {float(men_involved.ratio):.2f} times as often "
        f"as female drivers per licence holder ({ci(men_involved)}) and, once involved, died "
        f"{float(men_fatality.ratio):.2f} times as often ({ci(men_fatality)}). Combined, per "
        f"licence holder, men aged 18 and over died at the wheel {float(men_killed.ratio):.2f} "
        f"times as often as women ({ci(men_killed)}). The gap once involved holds in every age "
        "band. Involvement per licence holder combines how far men and women drive with how "
        "often they crash per kilometre, and no source separates the two.</p>"
    )
    body += figure(
        "a3_sex_ratios",
        f"Ratios of men's to women's rates for car drivers, {sex_years}, overall and by age band: "
        "involvement in injury crashes per licence holder, deaths per licence holder, and deaths "
        "per driver involved",
        captions,
    )
    body += (
        "<p>Across all motor-vehicle drivers, which adds motorcyclists, moped riders and the "
        "drivers of vans, trucks and buses, the gaps are wider: men died "
        f"{float(motor_killed.ratio):.2f} times as often as women per licence holder and "
        f"{float(motor_fatality.ratio):.2f} times as often once involved. The licence holders "
        "are holders of any class of licence; counting only car-licence holders, published by "
        "sex for the latest years only, makes the men's excess slightly larger.</p>"
    )
    body += technical("Detailed counts by sex", _sex_rates_table(sex_rates, sex_years))

    body += limitation(
        "The kilometres by age are estimates transferred from one region's working-day survey; "
        "DGT describes its kilometre totals as valid only in aggregate. The crash counts include "
        "foreign and unlicensed drivers. Drivers whose age the tables do not record "
        f"({_fmt_pct(unknown_share)} of those involved) are left out of every rate, which lowers "
        "each absolute rate by that share and leaves the ratios unchanged."
    )
    body += downloads(
        [
            ("risk_national_rates", "involvement and deaths per km by age, every method"),
            ("risk_national_shares", "kilometres by age, every method"),
            ("risk_national_numerator", "drivers involved and killed by age"),
            ("risk_weekend_sensitivity", "weekend and holiday sensitivity"),
            ("risk_barcelona_rates", "Barcelona working days, three denominators"),
            ("risk_barcelona_day_type", "Barcelona crashes by type of day"),
            ("risk_older_split", "65–74 and 75 and over, model-dependent"),
            ("edm_older_split", "Madrid survey: driving above 65"),
            ("risk_severity_and_licences", "deaths once involved and per licence holder"),
            ("risk_owner_age_comparison", "the former owner-age figures"),
            ("q7_km_by_owner_age", "DGT kilometres by owner age"),
            ("drivers_sex_rates", "rates by sex and age"),
            ("drivers_sex_ratios", "men against women"),
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
