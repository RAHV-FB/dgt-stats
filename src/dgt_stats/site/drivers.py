"""Age and sex: car drivers in injury crashes, and the share of them killed."""

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

# What every per-km rate on this page divides by, said in full once and then shortened.
OWNER_KM = "kilometres driven by cars registered to owners of the same age"


def _range(low: float, high: float) -> str:
    """A per-km ratio as the range from the transfer scenario to the published ratio."""
    return f"{low:.2f}–{high:.2f}×"


def _sex_section(captions: dict[str, str]) -> tuple[str, dict[str, pd.Series]]:
    numbers = _sex_numbers()
    ratios, rates_table = numbers["ratios"], numbers["rates"]
    involved = ratios.loc[("car", "18+", "involved_per_1000_licences")]
    killed = ratios.loc[("car", "18+", "deaths_per_million_licences")]
    fatality = ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    motor_fatality = ratios.loc[("motor", "18+", "deaths_per_1000_involved")]
    motor_killed = ratios.loc[("motor", "18+", "deaths_per_million_licences")]
    years = str(rates_table.years.iloc[0]).replace("-", "–")
    # The paragraphs say men's rates are higher on every measure and the motor-vehicle gaps wider.
    if not (
        min(float(involved.low), float(fatality.low), float(killed.low)) > 1
        and float(motor_killed.ratio) > float(killed.ratio)
        and float(motor_fatality.ratio) > float(fatality.ratio)
    ):
        raise ValueError("drivers page: the sex ratios no longer read as described")

    section = "<h2>Men and women: per licence holder and per driver involved</h2>"
    section += (
        "<p>No file in this repository measures kilometres driven by sex, so men and women are "
        "compared per licence holder and per driver involved. In "
        f"{years}, male car drivers were involved in injury crashes "
        f"{_ratio_ci(float(involved.ratio), float(involved.low), float(involved.high))} as often "
        "as female ones per licence holder; once involved they were killed "
        f"{_ratio_ci(float(fatality.ratio), float(fatality.low), float(fatality.high))} as often; "
        f"together, {_ratio_ci(float(killed.ratio), float(killed.low), float(killed.high))} the "
        "deaths per licence holder. Involvement per licence holder mixes how much each sex drives "
        "with how often they crash for the distance driven, and the data cannot separate the "
        "two. Deaths per driver involved start from drivers already in a crash, so they need no "
        "measure of driving; they say how often a recorded crash ended in the driver's death, "
        "not why.</p>"
    )
    section += figure(
        "a3_sex_ratios",
        "Men against women, car drivers, by age: involvement and deaths per licence holder, and "
        "deaths per driver involved",
        captions,
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
        f"Drivers aged 18 and over, {years} pooled; licence holders of any class. Sources: DGT "
        "driver tables 4.1.1 and 4.2, Censo de conductores 2014–2025",
        {
            "Involved per 1,000 licence holders": "dec2",
            "Killed per million licence holders": "dec",
            "Killed per 1,000 involved": "dec2",
            "Drivers killed": "int",
        },
    )
    section += (
        "<p>Across all motor-vehicle drivers, which adds the riders of motorcycles and mopeds and "
        "the drivers of vans, trucks and buses to the car drivers, the gaps are wider: "
        f"{_times(float(motor_killed.ratio))} per licence holder and "
        f"{_times(float(motor_fatality.ratio))} per driver involved. Cyclists and "
        "personal-mobility-vehicle riders are left out of both, since they need no licence. The "
        "licence holders are holders of a licence of any class; the census files give B-permit "
        "holders by sex only from 2021, so the 2014–2024 comparison cannot use them.</p>"
    )
    section += downloads(
        [
            ("drivers_sex_rates", "rates by sex and age"),
            ("drivers_sex_ratios", "men against women"),
            ("drivers_sex_trend", "by year, 2014–2024"),
        ]
    )
    return section, {"involved": involved, "fatality": fatality, "killed": killed}


def _rate_table(rates: pd.DataFrame, ratios: pd.DataFrame, owner: pd.DataFrame, year: int) -> str:
    """Deaths per driver involved first, then the two per-km rates with their ranges."""

    def fatality(band: str) -> str:
        if band == driver_risk.REFERENCE_BAND:
            return "1 (reference)"
        row = ratios.loc[("deaths_per_1000_involved", band)]
        return _ratio_ci(float(row.ratio), float(row.low), float(row.high))

    def km_range(measure: str, band: str) -> str:
        if band == driver_risk.REFERENCE_BAND:
            return "1 (reference)"
        row = owner.loc[band]
        return _range(float(row[f"{measure}_range_low"]), float(row[f"{measure}_range_high"]))

    rows = []
    for band, row in rates.iterrows():
        rows.append(
            {
                "Age band": row.band_label,
                "Drivers killed per 1,000 involved": f"{row.deaths_per_1000_involved:.1f}",
                "Killed per involved, against 35–54": fatality(band),
                "Involved per billion owner-age km": f"{row.involved_per_bn_km:,.0f}",
                "Involved per km, against 35–54": km_range("involved_per_bn_km", band),
                "Killed per billion owner-age km": f"{row.deaths_per_bn_km:.2f}",
                "Killed per km, against 35–54": km_range("deaths_per_bn_km", band),
            }
        )
    return table(
        pd.DataFrame(rows),
        f"Car drivers by age, {year}: drivers killed within 30 days per 1,000 drivers involved in "
        f"an injury crash, and drivers involved and killed per billion {OWNER_KM} (owner-age km; "
        "involved per billion km × killed per 1,000 involved ÷ 1,000 = killed per billion km). "
        "Ratios to 35–54 with 95% intervals; each per-km range runs from the transfer scenario to "
        "the published ratio. Sources: DGT driver tables 4.1.1 and 4.2 (car rows) and "
        f"Kilómetros anualizados recorridos por el parque móvil {year}",
    )


def page_drivers(captions: dict[str, str]) -> str:
    numbers = _age_numbers()
    ratios, rates, contrast, company, owner, older = (
        numbers["ratios"],
        numbers["rates"],
        numbers["contrast"],
        numbers["company"],
        numbers["owner"],
        numbers["older"],
    )
    km = read_table("q7_km_by_owner_age").set_index("band")
    year = driver_risk.KM_YEAR
    reference = driver_risk.REFERENCE_BAND

    def ratio_text(measure: str, band: str, frame: pd.DataFrame = ratios) -> str:
        row = frame.loc[(measure, band)]
        return _ratio_ci(float(row.ratio), float(row.low), float(row.high))

    def km_range(measure: str, band: str) -> str:
        row = owner.loc[band]
        return _range(float(row[f"{measure}_range_low"]), float(row[f"{measure}_range_high"]))

    def published(measure: str, band: str) -> float:
        return float(owner.loc[band, f"{measure}_ratio"])

    def transfer(measure: str, band: str) -> float:
        return float(owner.loc[band, f"{measure}_ratio_transfer"])

    sex_section, sex = _sex_section(captions)
    men_involved, men_fatality, men_killed = sex["involved"], sex["fatality"], sex["killed"]
    young, base, oldest = owner.loc["18-34"], owner.loc[reference], owner.loc["75+"]
    shortfall = float(young.transfer_bn_km)
    fatality_young = ratios.loc[("deaths_per_1000_involved", "18-34")]
    fatality_by_age = [
        float(ratios.loc[("deaths_per_1000_involved", b), "ratio"])
        for b in rates.index
        if b != "18-34"
    ]
    middle = ("55-64", "65-74")
    licence = read_table("q7_licence_share")
    year_licence = int(licence.year.max())
    latest_licence = licence[licence.year == year_licence].set_index(["band", "sex"])
    # Every qualitative statement below, checked against the tables it rests on.
    if not (
        fatality_by_age == sorted(fatality_by_age)
        and float(fatality_young.low) <= 1 <= float(fatality_young.high)
        and float(young.cars_per_b_permit) < float(base.cars_per_b_permit)
        and float(young.km_per_b_permit) < float(base.km_per_b_permit)
        and float(oldest.cars_per_b_permit) > 1
        and shortfall > 0
        and all(float(owner.loc[b, "involved_per_bn_km_range_high"]) < 1 for b in middle)
        and float(owner.loc["65-74", "transfer_bn_km"]) == 0
        and float(owner.loc["75+", "transfer_bn_km"]) == 0
        and float(latest_licence.loc[("75+", "total"), "licence_share"]) < 0.5
        and float(latest_licence.loc[("75+", "female"), "licence_share"]) < 0.5
    ):
        raise ValueError("drivers page: the age tables no longer read as described")

    body = key_figures(
        [
            (
                "Killed per driver involved, 75+",
                _times(float(ratios.loc[("deaths_per_1000_involved", "75+"), "ratio"])),
                "against drivers aged 35–54 in injury crashes, 2024; needs no kilometres",
            ),
            (
                "Killed per owner-age km, 75+",
                km_range("deaths_per_bn_km", "75+"),
                "against 35–54, per km of cars registered to owners of each age: transfer "
                "scenario to published ratio",
            ),
            (
                "Involved per owner-age km, 18–34",
                km_range("involved_per_bn_km", "18-34"),
                "against 35–54: transfer scenario to published ratio",
            ),
            (
                "Killed per licence holder, men",
                _times(float(men_killed.ratio)),
                f"against women: {_times(float(men_involved.ratio))} the involvement × "
                f"{_times(float(men_fatality.ratio))} the deaths per driver involved",
            ),
        ]
    )

    body += (
        '<p class="answer">Among car drivers in injury crashes in 2024, the share killed within '
        "30 days rose with each age band after 35–54: drivers aged 75 and over were killed "
        f"{ratio_text('deaths_per_1000_involved', '75+')} as often per driver involved as "
        "drivers aged 35 to 54, and drivers aged 18 to 34 were killed "
        f"{ratio_text('deaths_per_1000_involved', '18-34')} as often. That ratio compares the "
        "same drivers, by the same age, in the same tables, and needs no exposure. For distance "
        "the repository holds only the kilometres driven by cars registered to owners in each "
        "age band, not the kilometres driven by the drivers in it, so every per-km ratio is a "
        "range, from a scenario that moves young drivers' kilometres out of the "
        "35–54 band to the published ratio. On that denominator drivers aged 75 and over were "
        f"killed {km_range('deaths_per_bn_km', '75+')} as often as drivers aged 35 to 54, and "
        "drivers aged 18 to 34 were involved in injury crashes "
        f"{km_range('involved_per_bn_km', '18-34')} as often. Male car drivers were killed "
        f"{_times(float(men_killed.ratio))} as often per licence holder as female ones: "
        f"{_times(float(men_involved.ratio))} the involvement and "
        f"{_times(float(men_fatality.ratio))} the deaths per driver involved.</p>"
    )

    body += _rate_table(rates, ratios, owner, year)
    body += figure(
        "a1_km_risk_by_age",
        "Car drivers by age: deaths per 1,000 involved, and involvement and deaths per billion km "
        "driven by cars registered to owners of each age",
        captions,
    )

    body += "<h2>Deaths per driver involved: the measure that needs no kilometres</h2>"
    after = [b for b in rates.index if b not in ("18-34", reference)]
    fatality_text = _join(
        [
            f"{ratios.loc[('deaths_per_1000_involved', b), 'ratio']:.2f}× at "
            f"{rates.loc[b, 'band_label']}"
            for b in after
        ]
    )
    body += (
        "<p>Against drivers aged 35 to 54, the share of car drivers in an injury crash who were "
        f"killed rises with every band after it: {fatality_text}. Drivers aged 18 to 34 are at "
        f"{ratio_text('deaths_per_1000_involved', '18-34')}, an interval that includes no "
        "difference. Numerator and denominator are the same drivers, counted by the same age "
        "band in DGT's tables 4.1.1 and 4.2, so the kilometres and their owner-age problem do "
        "not enter. The measure counts only the driver's own death; DGT's tables do not say how "
        "often the other people in those crashes died, and they do not say why the share rises "
        "with age.</p>"
    )

    body += "<h2>Per kilometre: kilometres by the owner's age, not the driver's</h2>"
    company_share = float(km.loc[driver_risk.COMPANY_BAND, "share_of_km"])
    working = company.loc[("to_working_age", "75+")]
    body += (
        f"<p>DGT's {year} kilometre release estimates how far the circulating fleet is driven, by "
        "the age band of the registered owner. The repository's own tables show where owner and "
        "driver part. Per holder of a B permit, the car licence, the 18–34 band has "
        f"{float(young.cars_per_b_permit):.2f} cars registered to it and "
        f"{float(young.km_per_b_permit):,.0f} km a year, against "
        f"{float(base.cars_per_b_permit):.2f} cars and {float(base.km_per_b_permit):,.0f} km at "
        "35–54: either young licence holders drive less, or part of their driving is in cars "
        "registered to older owners, and the data cannot tell which. The 75-and-over band has "
        f"{float(oldest.cars_per_b_permit):.2f} cars per B-permit holder, more cars than people "
        "of that age licensed to drive them: either some of those cars are driven by others, "
        "or some drivers have more than one, and again the data cannot tell which.</p>"
    )
    body += (
        "<p>A transfer scenario puts a number on the first gap: kilometres move from the 35–54 "
        "band to 18–34 until both drive the same distance per B-permit holder, as if the whole "
        "gap were young drivers' driving registered to owners aged 35 to 54: "
        f"{shortfall:.1f} billion km, {shortfall / float(base.billion_km):.0%} of the 35–54 "
        "kilometres. It is arithmetic on the published table, not an estimate: the data say "
        "neither how much of the gap is young drivers' driving nor which older band holds it. "
        "Under it, involvement per km at 18–34 falls from "
        f"{published('involved_per_bn_km', '18-34'):.2f}× to "
        f"{transfer('involved_per_bn_km', '18-34'):.2f}× the 35–54 rate and deaths per km from "
        f"{published('deaths_per_bn_km', '18-34'):.2f}× to "
        f"{transfer('deaths_per_bn_km', '18-34'):.2f}×; at 75 and over, involvement per km goes "
        f"from {published('involved_per_bn_km', '75+'):.2f}× to "
        f"{transfer('involved_per_bn_km', '75+'):.2f}× and deaths per km from "
        f"{published('deaths_per_bn_km', '75+'):.2f}× to "
        f"{transfer('deaths_per_bn_km', '75+'):.2f}×. The second gap, if it is cars driven by "
        "others, pulls the other way: kilometres credited to owners of 75 and over but driven "
        "by younger people make that band's published per-km rates too low, by an amount the "
        "data do not give. Cars "
        f"registered to companies, {company_share:.0%} of car kilometres, have no owner age: "
        "their kilometres leave the denominator while their drivers stay in the numerator. "
        "Spreading them over every band in proportion changes no ratio; a scenario that spreads "
        "them over the bands from 18 to 64 raises the 75-and-over deaths-per-km ratio from "
        f"{published('deaths_per_bn_km', '75+'):.2f}× to "
        f"{float(working.ratio_to_reference):.2f}×. None of this moves deaths per driver "
        "involved.</p>"
    )
    middle_text = _join(
        [f"{km_range('involved_per_bn_km', b)} at {rates.loc[b, 'band_label']}" for b in middle]
    )
    body += (
        "<p>No band can serve as a reference where owner and driver are known to coincide. Cars "
        f"per B-permit holder are {float(owner.loc['55-64', 'cars_per_b_permit']):.2f} at 55–64 "
        f"and {float(owner.loc['65-74', 'cars_per_b_permit']):.2f} at 65–74, but owning a car "
        "per licence does not show that the owner drives it, so the page keeps 35–54 as the "
        "reference and gives each per-km ratio as a range. Against that reference, involvement "
        f"per owner-age km is lower at 55–64 and 65–74 under both readings: {middle_text}. "
        "Against 65–74, whose "
        "kilometres the transfer scenario does not move, drivers aged 75 and over were involved "
        f"{ratio_text('involved_per_bn_km', '75+', older)} as often per owner-age km and killed "
        f"{ratio_text('deaths_per_bn_km', '75+', older)} as often, with "
        f"{ratio_text('deaths_per_1000_involved', '75+', older)} the deaths per driver "
        "involved.</p>"
    )

    body += "<h2>Residents, B-permit holders, drivers involved, kilometres</h2>"
    body += figure(
        "a2_denominator_contrast",
        "The same car-driver deaths under four denominators, as ratios to drivers aged 35–54",
        captions,
    )
    residents_75 = contrast.loc[("residents", "75+")]
    permit_75 = contrast.loc[("b_permit_holders", "75+")]
    involved_75 = contrast.loc[("drivers_involved", "75+")]
    km_75 = contrast.loc[("kilometres", "75+")]
    body += (
        "<p>The same driver deaths give a different ratio under each denominator. Against "
        f"drivers aged 35 to 54, car drivers aged 75 and over died {residents_75.ratio:.2f} times "
        f"as often per resident, {permit_75.ratio:.2f} times per B-permit holder, "
        f"{involved_75.ratio:.2f} times per driver involved and {km_75.ratio:.2f} times per km "
        "of cars registered to owners of the same age (the published end of the range above). "
        "Residents and permit holders count "
        "people, not driving. In "
        f"{year_licence}, "
        f"{_fmt_pct(float(latest_licence.loc[('75+', 'total'), 'licence_share']), 0)} of "
        "residents aged 75 and over held a licence of any class against "
        f"{_fmt_pct(float(latest_licence.loc[('45-54', 'total'), 'licence_share']), 0)} of "
        "those aged 45–54, and the gap between the sexes widens with age: "
        f"{_fmt_pct(float(latest_licence.loc[('75+', 'male'), 'licence_share']), 0)} of men "
        "over 74 held one and "
        f"{_fmt_pct(float(latest_licence.loc[('75+', 'female'), 'licence_share']), 0)} of "
        f"women. Of licence holders aged 75 and over, {_fmt_pct(float(oldest.b_permit_share), 0)} "
        "held a B permit. The licence counts include moped and motorcycle permits and the "
        "agricultural licence. A per-resident rate for older women divides by a population "
        "most of whom hold no licence at all.</p>"
    )
    body += downloads(
        [
            ("q7_km_rates", "rates by band"),
            ("q7_km_ratio", "ratios to the 35–54 baseline"),
            ("q7_km_ratio_65_74", "ratios to the 65–74 band"),
            ("q7_owner_age_check", "owner-age check and the transfer scenario, every band"),
            ("q7_company_km", "company-car scenarios"),
            ("q7_denominator_contrast", "the four denominators"),
            ("q7_km_by_owner_age", "kilometres by owner age"),
            ("q7_licence_share", "licence holding by age and sex"),
        ]
    )

    body += sex_section
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Recorded in DGT's 2024 car-driver tables: the share of drivers in an injury crash who "
        "were killed rose with age after 35–54, to "
        f"{_times(float(ratios.loc[('deaths_per_1000_involved', '75+'), 'ratio']))} at 75 and "
        "over, a ratio that needs no exposure. Per kilometre the repository holds only "
        f"{OWNER_KM}; on that denominator drivers aged 75 and over were killed "
        f"{km_range('deaths_per_bn_km', '75+')} as often as drivers aged 35 to 54, and drivers "
        f"aged 18 to 34 were involved in injury crashes {km_range('involved_per_bn_km', '18-34')} "
        "as often, with a share killed once involved not distinguishable from 35–54 "
        f"({_times(float(fatality_young.ratio))}). In 2022–2024 male car drivers were killed "
        f"{_times(float(men_killed.ratio))} as often per licence holder as female ones, with "
        f"{_times(float(men_involved.ratio))} the involvement and "
        f"{_times(float(men_fatality.ratio))} the deaths per driver involved. These are "
        "associations in recorded counts; the tables do not say what produces them."
    )

    body += limits(
        "The per-km denominator is the kilometres driven by cars registered to owners of the "
        "driver's age band: owner age stands in for driver age, company cars have no owner "
        "age, and the transfer and company-car scenarios are "
        "arithmetic on the published table, not estimates of who drives. The kilometres are "
        "modelled from roadworthiness-inspection odometer readings and are valid for aggregates "
        "only; the intervals come from the crash counts and treat them as known. The numerator "
        "counts drivers of cars on Spanish roads, including foreign-registered cars and "
        "unlicensed drivers, while the kilometres cover Spanish-registered cars only. Drivers "
        "whose age or sex the tables do not record are left out. The kilometre comparison is "
        f"one year, {year}. Deaths per driver involved count the driver only. No file in the "
        "repository measures kilometres by sex, so the sex comparison is per licence holder of "
        "any class and per driver involved."
    )
    return render_page(
        "drivers",
        "Age and sex: car drivers in injury crashes, and the share killed",
        "Are older drivers, or male drivers, more often killed at the wheel? Deaths per driver "
        "involved need no exposure; per kilometre the repository holds only kilometres by the "
        "age of the car's registered owner, so those ratios are given as ranges.",
        body,
    )
