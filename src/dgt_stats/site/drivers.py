"""Age and sex: crashing, and dying once it happens."""

from __future__ import annotations

import pandas as pd

from dgt_stats import driver_risk
from dgt_stats.site.components import (
    _fmt_pct,
    _join,
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

    section = "<h2>Men and women: the same chain per licence holder</h2>"
    section += (
        "<p>No Spanish source measures kilometres by sex, so the chain for men and women runs per "
        f"licence holder. In {years}, male car drivers were involved in injury crashes "
        f"{_ratio_ci(float(involved.ratio), float(involved.low), float(involved.high))} as often "
        "as female ones per licence holder; once involved they were killed "
        f"{_ratio_ci(float(fatality.ratio), float(fatality.low), float(fatality.high))} as often; "
        f"together, {_ratio_ci(float(killed.ratio), float(killed.low), float(killed.high))} the "
        "deaths per licence holder. The first factor includes how much each sex drives; the "
        "second does not depend on driving at all, because it starts from drivers already in a "
        "crash.</p>"
    )
    section += figure(
        "a3_sex_ratios",
        "Men against women, car drivers, by age: involvement and deaths per licence holder, and "
        "deaths once involved",
        captions,
    )
    section += (
        "<p>How much of the crash gap is driving? The national travel survey MOVILIA (2006) "
        "counts trips by car or motorcycle, as "
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
        f"could produce. The deaths gap is not: per trip, deaths still run "
        f"{under_65.deaths_ratio_per_trip.min():.1f} to "
        f"{under_65.deaths_ratio_per_trip.max():.1f} times.</p>"
    )
    section += (
        "<p>The deaths per crash mean something different here than for age. Frailty does not "
        "explain the men's excess: in comparable crashes women are, if anything, more likely to "
        "be seriously injured "
        '(<a href="https://doi.org/10.2105/AJPH.2011.300275">Bose, Segui-Gomez &amp; Crandall '
        "2011</a>, US data). So the men's higher deaths per crash point to the crashes "
        "themselves and to behaviour within them: the roads, hours and speeds at which men crash, "
        "and belt use, which these tables cannot separate.</p>"
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
    return section, {"involved": involved, "fatality": fatality, "killed": killed}


def _chain_table(rates: pd.DataFrame, ratios: pd.DataFrame, year: int) -> str:
    """The chain by age band: crashes per km times deaths per crash is deaths per km."""

    def cell(measure: str, band: str) -> str:
        row = ratios.loc[(measure, band)]
        if band == driver_risk.REFERENCE_BAND:
            return "1 (reference)"
        return f"{row.ratio:.2f}× ({row.low:.2f}–{row.high:.2f})"

    rows = []
    for band, row in rates.iterrows():
        rows.append(
            {
                "Age of driver (and of car owner)": row.band_label,
                "Drivers in an injury crash, per billion km": f"{row.involved_per_bn_km:,.0f}",
                "× drivers killed per 1,000 in a crash": f"{row.deaths_per_1000_involved:.1f}",
                "= drivers killed per billion km": f"{row.deaths_per_bn_km:.2f}",
                "Crashes per km, against 35–54": cell("involved_per_bn_km", band),
                "Deaths per crash, against 35–54": cell("deaths_per_1000_involved", band),
                "Deaths per km, against 35–54": cell("deaths_per_bn_km", band),
            }
        )
    return table(
        pd.DataFrame(rows),
        f"Car drivers by age, {year}: how often they are in an injury crash for the distance "
        "they drive, how often that crash kills them, and the product, deaths per kilometre "
        "(involved per billion km × killed per 1,000 involved ÷ 1,000); ratios with 95% "
        f"intervals. Sources: DGT driver tables 4.1.1 and 4.2 (car rows) and Kilómetros "
        f"anualizados recorridos por el parque móvil {year}",
    )


def page_drivers(captions: dict[str, str]) -> str:
    numbers = _age_numbers()
    ratios, rates, contrast, company = (
        numbers["ratios"],
        numbers["rates"],
        numbers["contrast"],
        numbers["company"],
    )
    older = read_table("q7_km_ratio_65_74").set_index(["measure", "band"])
    km = read_table("q7_km_by_owner_age").set_index("band")
    year = driver_risk.KM_YEAR

    def ratio_text(measure: str, band: str, table: pd.DataFrame = ratios) -> str:
        row = table.loc[(measure, band)]
        return f"{row.ratio:.2f}× ({row.low:.2f}–{row.high:.2f})"

    def times(measure: str, band: str) -> str:
        return _times(float(ratios.loc[(measure, band), "ratio"]))

    deaths_75 = ratios.loc[("deaths_per_bn_km", "75+")]
    sex_section, sex = _sex_section(captions)
    men_involved, men_fatality, men_killed = sex["involved"], sex["fatality"], sex["killed"]
    trough = [b for b in ("55-64", "65-74")]
    trough_values = [float(ratios.loc[("involved_per_bn_km", b), "ratio"]) for b in trough]
    fatality_by_age = [
        float(ratios.loc[("deaths_per_1000_involved", b), "ratio"]) for b in rates.index
    ]
    # The paragraphs below describe a U-shaped crash rate per km and a death rate per crash that
    # rises with every band; stop if the tables no longer say so.
    involvement = [float(ratios.loc[("involved_per_bn_km", b), "ratio"]) for b in rates.index]
    if not (
        max(trough_values) < 1 < float(ratios.loc[("involved_per_bn_km", "75+"), "ratio"])
        and involvement[0] == max(involvement)
        and fatality_by_age[1:] == sorted(fatality_by_age[1:])
        and float(older.loc[("involved_per_bn_km", "75+"), "low"]) > 1
    ):
        raise ValueError("drivers page: the age pattern no longer reads as described")

    body = key_figures(
        [
            (
                "Killed per km, 75 and over",
                times("deaths_per_bn_km", "75+"),
                f"against 35–54: {times('involved_per_bn_km', '75+')} the crashes per km × "
                f"{times('deaths_per_1000_involved', '75+')} the deaths per crash",
            ),
            (
                "Killed per km, 18–34",
                times("deaths_per_bn_km", "18-34"),
                f"against 35–54: {times('involved_per_bn_km', '18-34')} the crashes per km × "
                f"{times('deaths_per_1000_involved', '18-34')} the deaths per crash",
            ),
            (
                "Crashes per km, 75+ against 65–74",
                _times(float(older.loc[("involved_per_bn_km", "75+"), "ratio"])),
                "the crash rate per km is lowest at 55–74 and rises again after 75",
            ),
            (
                "Killed per licence, men",
                _times(float(men_killed.ratio)),
                f"against women: {_times(float(men_involved.ratio))} the crashes × "
                f"{_times(float(men_fatality.ratio))} the deaths per crash",
            ),
        ]
    )

    body += (
        '<p class="answer">A driver\'s risk of being killed for each kilometre driven is how '
        "often they crash per kilometre times how often a crash kills them. Split that way, the "
        "two ends of the age range are dangerous for opposite reasons. Car drivers aged 75 and "
        f"over are killed {ratio_text('deaths_per_bn_km', '75+')} as often per kilometre as "
        f"drivers aged 35 to 54: they are in injury crashes {times('involved_per_bn_km', '75+')} "
        f"as often per kilometre, and a crash kills them {times('deaths_per_1000_involved', '75+')} "
        "as often. Drivers aged 18 to 34 are killed "
        f"{ratio_text('deaths_per_bn_km', '18-34')} as often per kilometre: they crash "
        f"{times('involved_per_bn_km', '18-34')} as often, and a crash kills them no more often: "
        f"{ratio_text('deaths_per_1000_involved', '18-34')}. Men are killed "
        f"{_times(float(men_killed.ratio))} as often per licence holder as women: "
        f"{_times(float(men_involved.ratio))} the crashes and {_times(float(men_fatality.ratio))} "
        "the deaths per crash.</p>"
    )

    body += _chain_table(rates, ratios, year)
    body += figure(
        "a1_km_risk_by_age",
        "Car drivers by age: involvement per billion km, deaths per 1,000 involved, deaths per "
        "billion km",
        captions,
    )

    body += "<h2>Crashes per kilometre: lowest at 55–74, not flat</h2>"
    body += (
        "<p>Against drivers aged 35 to 54, those 75 and over crash "
        f"{ratio_text('involved_per_bn_km', '75+')} as often per kilometre, which on its own "
        "reads as no difference. The comparison hides the shape of the curve. The crash rate per "
        "kilometre falls from its peak at 18–34 to a low at 55–64 and 65–74 "
        f"({trough_values[0]:.2f}× and {trough_values[1]:.2f}× the 35–54 rate) and rises again "
        "after 75. Against the drivers just younger than them, aged 65 to 74, drivers of 75 and "
        f"over crash {ratio_text('involved_per_bn_km', '75+', older)} as often per kilometre and "
        f"are killed {ratio_text('deaths_per_1000_involved', '75+', older)} as often per crash, "
        f"{ratio_text('deaths_per_bn_km', '75+', older)} per kilometre in all.</p>"
    )
    body += (
        "<p>Part of that rise may be how little they drive rather than their age. Drivers who "
        "cover few kilometres crash more per kilometre at any age, because more of their "
        "driving is short trips in towns, with more junctions per kilometre "
        '(<a href="https://doi.org/10.1016/j.aap.2005.12.002">Langford, Methorst &amp; '
        "Hakamies-Blomqvist 2006</a>). A car whose owner is 75 or over covers "
        f"{rates.loc['75+', 'mean_km_per_car']:,.0f} km a year against "
        f"{rates.loc['35-54', 'mean_km_per_car']:,.0f} for owners aged 35 to 54. These tables "
        "cannot separate mileage from age.</p>"
    )

    body += "<h2>Deaths per crash: what a crash does to the driver</h2>"
    after = [b for b in rates.index if b not in ("18-34", driver_risk.REFERENCE_BAND)]
    fatality_text = _join(
        [
            f"{ratios.loc[('deaths_per_1000_involved', b), 'ratio']:.2f}× at "
            f"{rates.loc[b, 'band_label']}"
            for b in after
        ]
    )
    body += (
        "<p>Against drivers aged 35 to 54, the share of drivers in an injury crash who are "
        f"killed rises with every band after it: {fatality_text}; drivers aged 18 to 34 are at "
        f"{times('deaths_per_1000_involved', '18-34')}. That is what physical frailty predicts: "
        "the same crash does more harm to an older body. US data show the same split "
        '(<a href="https://doi.org/10.1016/S0001-4575(01)00107-5">Li, Braver &amp; Chen '
        "2003</a>): the high death rate per mile of older drivers came mainly from their "
        "fragility, much less from crashing more. The measure counts only the driver's own "
        "death; DGT's tables do not say how often the other people in those crashes die.</p>"
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
        "<p>The same driver deaths give a different answer under each denominator. DGT reports "
        "road deaths of people 65 and over per million inhabitants of that age. On that "
        f"denominator drivers 75 and over die {residents_75.ratio:.2f} times as often as drivers "
        "aged 35 to 54, barely more, because most people over 75 do not drive at all. Per "
        f"licence holder the ratio is {licence_75.ratio:.2f}, because holding a licence is not "
        f"the same as driving. Per driver in a crash it is {involved_75_contrast.ratio:.2f} and "
        f"per kilometre {deaths_75.ratio:.2f}: the last two agree because crashes per kilometre "
        "are about the same at the two ages. Only the kilometre compares like with like, "
        "distance with distance.</p>"
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
            ("q7_km_ratio_65_74", "ratios to the 65–74 band"),
            ("q7_denominator_contrast", "the four denominators"),
            ("q7_km_by_owner_age", "kilometres by owner age"),
            ("q7_company_km", "company-car sensitivity"),
            ("q7_licence_share", "licence holding by age and sex"),
        ]
    )

    body += "<h2>Whose kilometres</h2>"
    company_share = float(km.loc[driver_risk.COMPANY_BAND, "share_of_km"])
    working = company.loc[("to_working_age", "75+")]
    young_case = float(
        read_table("q7_owner_age_check").ratio_75_if_young_drive_like_baseline.iloc[0]
    )
    body += (
        f"<p>DGT's {year} kilometre release estimates how far the whole circulating fleet is "
        "driven, by the age band of the registered owner: the same source, year and construction "
        "for every band. It is the <em>owner's</em> age, not the driver's, and the biases this "
        "brings pull both ways. Drivers aged 18 to 34 own far fewer cars per licence than anyone "
        "else, so part of their driving is registered to their parents in the 35–54 baseline; "
        "that inflates the baseline's kilometres and overstates the older bands against it. In "
        "the extreme case, with the young driving as far per licence as the baseline, the 75-and-"
        f"over crash ratio per kilometre would be {young_case:.2f} rather than "
        f"{float(ratios.loc[('involved_per_bn_km', '75+'), 'ratio']):.2f}. The other way, a car "
        "registered to a person of 75 may be driven by a relative, and a car registered to a "
        f"company has no age at all: company cars are {company_share:.0%} of car kilometres, "
        "mostly driven by people of working age, and they leave the denominator while their "
        "drivers stay in the numerator. Spreading them over the bands from 18 to 64 would raise "
        f"the 75-and-over deaths-per-kilometre ratio from {deaths_75.ratio:.2f} to "
        f"{float(working.ratio_to_reference):.2f}. Neither moves the main result: for drivers "
        "of 75 and over the deaths per crash, which need no kilometres, carry the excess.</p>"
    )
    body += sex_section
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Age and sex raise the risk of dying at the wheel through different factors. For drivers "
        "75 and over it is mostly what a crash does to them: "
        f"{times('deaths_per_1000_involved', '75+')} the deaths per crash of drivers aged 35 to "
        f"54, with crashes per kilometre at {times('involved_per_bn_km', '75+')} that rate, "
        "though "
        f"{_times(float(older.loc[('involved_per_bn_km', '75+'), 'ratio']))} the rate of drivers "
        "aged 65 to 74. For drivers 18 to 34 it is all how often they crash: "
        f"{times('involved_per_bn_km', '18-34')} the crashes per kilometre, with no more deaths "
        "per crash. For men it is mostly deaths per crash, "
        f"{_times(float(men_fatality.ratio))}, beside {_times(float(men_involved.ratio))} the "
        "crashes per licence holder, about what their extra travel produces. The split says "
        "where the excess sits, not what would remove it: for older drivers it points at what a "
        "crash does, which speed and the vehicle govern, more than at how often they crash, and "
        "for young drivers the reverse."
    )

    body += limits(
        "Owner age is a proxy for driver age, and the two diverge most in the households where a "
        "car is shared. The kilometres are modelled from roadworthiness-inspection odometer "
        "readings and are valid for aggregates only; the intervals here come from the crash "
        "counts and treat them as known. The numerator counts drivers of cars on Spanish roads, "
        "including foreign-registered ones, while the denominator covers Spanish-registered cars "
        f"only. The kilometre comparison is one year, {year}. Deaths per crash count the driver "
        "only. No source measures kilometres by sex, so the sex comparison uses licences and a "
        "2006 travel survey that counts passengers; only the deaths per crash are free of that "
        "limit."
    )
    return render_page(
        "drivers",
        "Age and sex: how often drivers crash, and how often a crash kills them",
        "Are older drivers, or male drivers, more dangerous? Deaths per kilometre driven are "
        "crashes per kilometre times deaths per crash; splitting the two shows which one makes "
        "the difference for each group.",
        body,
    )
