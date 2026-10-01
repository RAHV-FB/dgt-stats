"""Age and sex: crashing, and dying once it happens."""

from __future__ import annotations

import pandas as pd

from dgt_stats import driver_risk
from dgt_stats.site.components import (
    _fmt_pct,
    _ratio_ci,
    _times,
    conclusion,
    downloads,
    figure,
    key_figures,
    limits,
    read_table,
    render_page,
    table,
)
from dgt_stats.site.numbers import _age_numbers, _sex_numbers


def _sex_section(captions: dict[str, str]) -> tuple[str, dict[str, pd.Series]]:
    numbers = _sex_numbers()
    ratios, rates_table, travel = numbers["ratios"], numbers["rates"], numbers["travel"]
    involved = ratios.loc[("car", "18+", "involved_per_1000_licences")]
    killed = ratios.loc[("car", "18+", "deaths_per_million_licences")]
    fatality = ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    motor_fatality = ratios.loc[("motor", "18+", "deaths_per_1000_involved")]
    motor_killed = ratios.loc[("motor", "18+", "deaths_per_million_licences")]
    years = str(rates_table.years.iloc[0]).replace("-", "–")
    under_65 = travel.loc[["15-29", "30-39", "40-49", "50-64"]]

    section = "<h2>Men and women</h2>"
    section += (
        f"<p>Per licence holder, in {years}, male car drivers were involved in injury crashes "
        f"{_ratio_ci(float(involved.ratio), float(involved.low), float(involved.high))} as often "
        "as female ones and killed "
        f"{_ratio_ci(float(killed.ratio), float(killed.low), float(killed.high))} as often. The "
        "first ratio includes how much each group drives; the census counts licences, not "
        "kilometres. The second divides into two parts that exposure affects very differently. "
        "Once involved in a crash, a male car driver was killed "
        f"{_ratio_ci(float(fatality.ratio), float(fatality.low), float(fatality.high))} as often "
        "as a female one, a ratio that needs no measure of driving at all.</p>"
    )
    section += figure(
        "a3_sex_ratios",
        "Men against women, car drivers, by age: involvement and deaths per licence holder, and "
        "deaths once involved",
        captions,
    )
    section += (
        "<p>How much of the involvement gap is driving? No Spanish source measures kilometres "
        "by sex. The national travel survey MOVILIA (2006) counts trips by car or motorcycle, as "
        "driver or passenger, by sex and age. Under 65, men made "
        f"{under_65.trip_ratio_2006.min():.1f} to {under_65.trip_ratio_2006.max():.1f} times as "
        "many such trips per head as women; car-driver involvement per head in "
        f"{years} runs "
        f"{under_65.involved_ratio_per_resident.min():.1f} to "
        f"{under_65.involved_ratio_per_resident.max():.1f} times. Per trip, that leaves "
        f"{under_65.involved_ratio_per_trip.min():.1f} to "
        f"{under_65.involved_ratio_per_trip.max():.1f}: about equal. The survey is old and counts "
        "passengers, who are more often women, so it understates the driving gap; the "
        "conclusion it supports is only that the involvement gap is of the size a travel gap "
        f"could produce. The fatality gap is not: per trip, deaths still run "
        f"{under_65.deaths_ratio_per_trip.min():.1f} to "
        f"{under_65.deaths_ratio_per_trip.max():.1f} times.</p>"
    )
    rows = []
    for scope, label in (("car", "Car drivers"), ("motor", "All motor-vehicle drivers")):
        for sex, sex_label in (("male", "Men"), ("female", "Women")):
            row = rates_table.loc[(scope, "18+", sex)]
            rows.append(
                {
                    "Drivers": label,
                    "Sex": sex_label,
                    "Involved per 1,000 licence holders": row.involved_per_1000_licences,
                    "Killed per million licence holders": row.deaths_per_million_licences,
                    "Killed per 1,000 involved": row.deaths_per_1000_involved,
                    "Drivers killed": row.driver_deaths,
                }
            )
    section += table(
        pd.DataFrame(rows),
        f"Drivers aged 18 and over, {years} pooled. Sources: DGT driver tables 4.1.1 and 4.2, "
        "Censo de conductores 2014–2025",
        {
            "Involved per 1,000 licence holders": "dec2",
            "Killed per million licence holders": "dec",
            "Killed per 1,000 involved": "dec2",
            "Drivers killed": "int",
        },
    )
    section += (
        "<p>Across all motor vehicles the gaps are wider, "
        f"{_times(float(motor_killed.ratio))} per licence holder and "
        f"{_times(float(motor_fatality.ratio))} once involved, because men ride most of the "
        "motorcycles. Cyclists and personal-mobility-vehicle riders are left out of both, since "
        "they need no licence.</p>"
    )
    section += downloads(
        [
            ("drivers_sex_rates", "rates by sex and age"),
            ("drivers_sex_ratios", "men against women"),
            ("drivers_sex_trend", "by year, 2014–2024"),
            ("drivers_sex_travel", "the MOVILIA travel bracket"),
        ]
    )
    return section, {"involved": involved, "fatality": fatality}


def page_drivers(captions: dict[str, str]) -> str:
    numbers = _age_numbers()
    ratios, rates, contrast, company = (
        numbers["ratios"],
        numbers["rates"],
        numbers["contrast"],
        numbers["company"],
    )
    km = read_table("q7_km_by_owner_age").set_index("band")
    year = driver_risk.KM_YEAR

    def ratio_text(measure: str, band: str) -> str:
        row = ratios.loc[(measure, band)]
        return f"{row.ratio:.2f}× ({row.low:.2f}–{row.high:.2f})"

    deaths_75 = ratios.loc[("deaths_per_bn_km", "75+")]
    involved_75 = ratios.loc[("involved_per_bn_km", "75+")]
    fatality_75 = ratios.loc[("deaths_per_1000_involved", "75+")]
    sex_section, sex = _sex_section(captions)
    men_involved, men_fatality = sex["involved"], sex["fatality"]

    body = key_figures(
        [
            (
                "Crashes per kilometre, 75+",
                _times(float(involved_75.ratio)),
                "involvement rate against drivers aged 35–54",
            ),
            (
                "Deaths per crash, 75+",
                _times(float(fatality_75.ratio)),
                "killed per 1,000 drivers involved, against 35–54",
            ),
            (
                "Crashes per licence, men",
                _times(float(men_involved.ratio)),
                "male against female car drivers",
            ),
            (
                "Deaths per crash, men",
                _times(float(men_fatality.ratio)),
                "killed once involved, against women",
            ),
        ]
    )

    body += (
        '<p class="answer">Older drivers are not crashing more often for the distance they '
        "drive. Per kilometre, car drivers aged 75 and over are involved in injury crashes "
        f"{ratio_text('involved_per_bn_km', '75+')} as often as drivers aged 35 to 54, which is "
        "to say about as often. The difference is in the consequence. Once involved, they are "
        f"killed {ratio_text('deaths_per_1000_involved', '75+')} as often. Young drivers are the "
        f"mirror image, with {ratio_text('involved_per_bn_km', '18-34')} the involvement rate per "
        f"kilometre and {ratio_text('deaths_per_1000_involved', '18-34')} the chance of dying "
        "once involved. Sex splits the same way: male car drivers are in injury crashes "
        f"{_times(float(men_involved.ratio))} as often as women per licence holder, a gap of the "
        "size a difference in driving could produce, and are killed "
        f"{_times(float(men_fatality.ratio))} as often once they are.</p>"
    )

    body += figure(
        "a1_km_risk_by_age",
        "Car drivers by age: involvement per billion km, deaths per 1,000 involved, deaths per "
        "billion km",
        captions,
    )

    shown = rates.reset_index()[
        [
            "band_label",
            "n_cars",
            "billion_km",
            "mean_km_per_car",
            "drivers_involved",
            "involved_per_bn_km",
            "driver_deaths",
            "deaths_per_1000_involved",
            "deaths_per_bn_km",
        ]
    ].rename(
        columns={
            "band_label": "Age of driver (and of car owner)",
            "n_cars": "Cars owned",
            "billion_km": "Billion km",
            "mean_km_per_car": "Km per car",
            "drivers_involved": "Drivers involved",
            "involved_per_bn_km": "Involved per bn km",
            "driver_deaths": "Drivers killed",
            "deaths_per_1000_involved": "Killed per 1,000 involved",
            "deaths_per_bn_km": "Killed per bn km",
        }
    )
    body += table(
        shown,
        f"Car drivers and car kilometres by age band, {year}. Sources: DGT driver tables 4.1.1 and "
        f"4.2 (car rows) and Kilómetros anualizados recorridos por el parque móvil {year}",
        {
            "Cars owned": "int",
            "Billion km": "dec",
            "Km per car": "int",
            "Drivers involved": "int",
            "Involved per bn km": "dec0",
            "Drivers killed": "int",
            "Killed per 1,000 involved": "dec",
            "Killed per bn km": "dec2",
        },
    )

    body += "<h2>Residents, licences, crashes, kilometres</h2>"
    body += figure(
        "a2_denominator_contrast",
        "The same car-driver deaths under four denominators, as ratios to drivers aged 35–54",
        captions,
    )
    residents_75 = contrast.loc[("residents", "75+")]
    licence_75 = contrast.loc[("licence_holders", "75+")]
    involved_75_contrast = contrast.loc[("drivers_involved", "75+")]
    body += (
        "<p>DGT reports road deaths of people 65 and over per million inhabitants of that age. "
        f"On that denominator drivers 75 and over die {residents_75.ratio:.2f} times as often as "
        "drivers aged 35 to 54, barely more, because most people over 75 do not drive at all. Per "
        f"licence holder the ratio is {licence_75.ratio:.2f}, because holding a licence is not "
        "the same as driving. "
        f"Per driver already in a crash it is {involved_75_contrast.ratio:.2f} and per kilometre "
        f"{deaths_75.ratio:.2f}. The numerator is identical in all four; the denominator is the "
        "entire difference, which is why it has to be named every time. The last two agree because "
        "involvement per kilometre is about the same at both ages. That is the finding above, "
        "seen from the other side.</p>"
    )
    licence = read_table("q7_licence_share")
    latest_licence = licence[licence.year == licence.year.max()].set_index(["band", "sex"])
    year_licence = int(licence.year.max())
    body += (
        f"<p>That is also why the per-resident rate says so little about driving. In "
        f"{year_licence}, {_fmt_pct(float(latest_licence.loc[('75+', 'total'), 'licence_share']), 0)} "
        f"of residents aged 75 and over held a licence against "
        f"{_fmt_pct(float(latest_licence.loc[('45-54', 'total'), 'licence_share']), 0)} of those "
        f"aged 45–54, and the gap between the sexes widens with age: "
        f"{_fmt_pct(float(latest_licence.loc[('75+', 'male'), 'licence_share']), 0)} of men over 74 "
        f"hold one and {_fmt_pct(float(latest_licence.loc[('75+', 'female'), 'licence_share']), 0)} "
        "of women. A per-resident rate for older women is describing passengers and pedestrians "
        "far more than drivers.</p>"
    )
    body += downloads(
        [
            ("q7_km_rates", "rates by band"),
            ("q7_km_ratio", "ratios to the 35–54 baseline"),
            ("q7_denominator_contrast", "the four denominators"),
            ("q7_km_by_owner_age", "kilometres by owner age"),
            ("q7_company_km", "company-car sensitivity"),
            ("q7_licence_share", "licence holding by age and sex"),
        ]
    )

    body += "<h2>What the denominator measures</h2>"
    company_share = float(km.loc[driver_risk.COMPANY_BAND, "share_of_km"])
    working = company.loc[("to_working_age", "75+")]
    body += (
        f"<p>DGT's {year} kilometre release estimates, for the whole circulating fleet, how far "
        "each vehicle category is driven, and breaks it down by the age band of the registered "
        "owner. That is what makes this comparison possible and what makes the middle-aged "
        "baseline and the older groups directly comparable: the same source, the same year, the "
        "same construction. It is the <em>owner's</em> age, not the driver's. A car registered to "
        "a person of 75 may be driven by a relative, and a car registered to a company has no age "
        f"at all: those are {company_share:.0%} of all car kilometres and they leave the "
        "denominator while their drivers stay in the numerator. Since company cars are mostly "
        "driven by people of working age, leaving them out understates middle-aged exposure and "
        "so understates this comparison: spreading those kilometres over the bands from 18 to 64 "
        f"would raise the 75-and-over ratio from {deaths_75.ratio:.2f} to "
        f"{float(working.ratio_to_reference):.2f}.</p>"
    )
    body += sex_section
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Splitting the question in two changes the answer, for age and for sex alike. Older car "
        "drivers are not more likely to crash for the distance they cover; drivers aged 75 and "
        f"over are involved {ratio_text('involved_per_bn_km', '75+')} as often per kilometre as "
        f"drivers aged 35 to 54, and are {ratio_text('deaths_per_1000_involved', '75+')} as "
        "likely to be killed once involved. Men crash somewhat more often per licence, by about "
        "as much as the one travel survey by sex suggests they drive more, and are killed "
        f"{_times(float(men_fatality.ratio))} as often once in a crash. In both cases the excess "
        "in deaths comes from what a crash does to the driver, not from how often the driver "
        "crashes. The data show that split, not its causes: physical frailty for older drivers, "
        "and for men the roads, hours and speeds at which they crash, are candidate "
        "explanations these tables cannot separate."
    )

    body += limits(
        "Owner age is a proxy for driver age, and the two diverge most in the households where a "
        "car is shared. The kilometres are modelled from roadworthiness-inspection odometer "
        "readings and are valid for aggregates only; the intervals here come from the crash "
        "counts and treat them as known. The numerator counts drivers of cars on Spanish roads, "
        "including foreign-registered ones, while the denominator covers Spanish-registered cars "
        f"only. The kilometre comparison is one year, {year}. No source measures kilometres by "
        "sex, so the sex comparison uses licences and a 2006 travel survey that counts "
        "passengers; only the fatality ratio once involved is free of that limit."
    )
    return render_page(
        "drivers",
        "Age and sex: crashing, and dying once it happens",
        "Are older drivers, or male drivers, more dangerous? Split the question into crashing "
        "for the driving done and dying once the crash happens, and the halves disagree.",
        body,
    )
