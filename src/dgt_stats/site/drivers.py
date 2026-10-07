"""Driver age and sex: how often car drivers are in crashes, and how often a crash kills the driver.

The page leads with deaths per driver involved, the one comparison that needs no estimate of
kilometres, and then compares involvement in crashes with DGT's kilometres by the registered
owner's age, which are not kilometres by the driver's age. Every number is read from the ``q7_*`` and ``drivers_sex_*`` tables,
and every qualitative sentence is checked against them before the page is written.
"""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import agebands, driver_risk
from dgt_stats.site.components import (
    _fmt_pct,
    _ratio_ci,
    _times,
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
from dgt_stats.site.numbers import _age_numbers, _sex_numbers

YOUNG = driver_risk.TRANSFER_BANDS
REFERENCE = driver_risk.REFERENCE_BAND
OLDEST = "75+"
# The bands between the reference and the oldest, which the scenario does not touch.
MIDDLE = ("55-64", "65-74")


def _label(band: str) -> str:
    """A band key as printed in prose: '18-24' as 18–24, '75+' as 75 and over."""
    return "75 and over" if band == OLDEST else band.replace("-", "–")


def _range(low: float, high: float) -> str:
    """A per-km ratio as the range from the reallocation scenario to the published figure."""
    return f"{low:.2f}–{high:.2f}×"


def _check(holds: bool, claim: str) -> None:
    if not holds:
        raise ValueError(f"drivers page: the tables no longer support: {claim}")


def _licence_shares() -> tuple[int, pd.DataFrame]:
    """The latest year of licence holding by age band and sex, indexed by (band, sex)."""
    licence = read_table("q7_licence_share")
    year = int(licence.year.max())
    return year, licence[licence.year == year].set_index(["band", "sex"])


def _ratio_table(ratios: pd.DataFrame, owner: pd.DataFrame, rates: pd.DataFrame, year: int) -> str:
    """Ratios to 35–54: involvement per km × deaths per driver involved = deaths per km."""

    def per_involved(band: str) -> str:
        if band == REFERENCE:
            return "1 (reference)"
        row = ratios.loc[("deaths_per_1000_involved", band)]
        return _ratio_ci(float(row.ratio), float(row.low), float(row.high))

    def per_km(measure: str, band: str) -> str:
        if band == REFERENCE:
            return "1 (reference)"
        row = owner.loc[band]
        return _range(float(row[f"{measure}_range_low"]), float(row[f"{measure}_range_high"]))

    rows = [
        {
            "Age band": rates.loc[band, "band_label"],
            "Involved in an injury crash, per km": per_km("involved_per_bn_km", band),
            "Killed once involved": per_involved(band),
            "Killed, per km": per_km("deaths_per_bn_km", band),
        }
        for band in rates.index
    ]
    return table(
        pd.DataFrame(rows),
        f"Car drivers by age, {year}, as ratios to drivers aged 35–54. Each per-kilometre ratio "
        "runs from the scenario to the published owner-age kilometres; deaths once involved need "
        "no kilometres and carry a 95% interval. At either end of a range, involvement per km × "
        "deaths once involved = deaths per km.",
    )


def _rates_table(rates: pd.DataFrame, year: int) -> str:
    frame = pd.DataFrame(
        {
            "Age band": rates.band_label,
            "Drivers involved": rates.drivers_involved,
            "Drivers killed": rates.driver_deaths,
            "Killed per 1,000 involved": rates.deaths_per_1000_involved,
            "Kilometres (billion)": rates.billion_km,
            "Involved per billion km": rates.involved_per_bn_km,
            "Killed per billion km": rates.deaths_per_bn_km,
        }
    )
    return table(
        frame,
        f"Car drivers by age, {year}: drivers involved in injury crashes and killed within 30 "
        "days, and DGT's published kilometres of cars registered to owners in each band. Involved "
        "per billion km × killed per 1,000 involved ÷ 1,000 = killed per billion km.",
        {
            "Drivers involved": "int",
            "Drivers killed": "int",
            "Killed per 1,000 involved": "dec",
            "Kilometres (billion)": "dec",
            "Involved per billion km": "dec0",
            "Killed per billion km": "dec2",
        },
        reference_rows=(agebands.band_label(REFERENCE),),
    )


def _breakeven_table(breakeven: pd.DataFrame, year: int) -> str:
    """For each band, the km per licence holder needed to match the 35–54 rate per km."""
    rows = []
    for (reference, kilometres, band), row in breakeven.iterrows():
        if reference != REFERENCE or kilometres != "published":
            continue
        rows.append(
            {
                "Age band": row.band_label,
                "Credited to cars of owners this age": row.credited_km_per_b_permit,
                "Needed to match drivers aged 35–54": (
                    f"{row.needed_km_per_b_permit:,.0f} "
                    f"({row.needed_low:,.0f}–{row.needed_high:,.0f})"
                ),
                "Needed ÷ credited": f"{row.needed_over_credited:.2f}",
            }
        )
    return table(
        pd.DataFrame(rows),
        f"Kilometres a year per B-licence holder, car drivers by age, {year}. The distance "
        "needed is the one at which the band's drivers would be involved in injury crashes no "
        "more often per kilometre than drivers aged 35–54, with a 95% interval from the crash "
        "counts; needed ÷ credited equals the ratio of involvement per kilometre on the "
        "published owner-age kilometres.",
        {"Credited to cars of owners this age": "dec0"},
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
    numbers = _age_numbers()
    ratios, rates, contrast = numbers["ratios"], numbers["rates"], numbers["contrast"]
    company, owner, older = numbers["company"], numbers["owner"], numbers["older"]
    km_table = read_table("q7_km_by_owner_age").set_index("band")
    year = driver_risk.KM_YEAR
    sex_numbers = _sex_numbers()
    sex_ratios, sex_rates = sex_numbers["ratios"], sex_numbers["rates"]
    sex_years = str(sex_rates.years.iloc[0]).replace("-", "–")
    trend = read_table("drivers_sex_trend")
    trend_years = f"{int(trend.year.min())}–{int(trend.year.max())}"
    licence_year, licence = _licence_shares()

    def ratio(measure: str, band: str, frame: pd.DataFrame = ratios) -> pd.Series:
        return frame.loc[(measure, band)]

    def ci(row: pd.Series) -> str:
        return f"{float(row.low):.2f}–{float(row.high):.2f}"

    def rate(band: str) -> float:
        return float(rates.loc[band, "deaths_per_1000_involved"])

    def end(measure: str, band: str, which: str) -> float:
        return float(owner.loc[band, f"{measure}_range_{which}"])

    def published(measure: str, band: str) -> float:
        return float(owner.loc[band, f"{measure}_ratio"])

    def scenario(measure: str, band: str) -> float:
        return float(owner.loc[band, f"{measure}_ratio_transfer"])

    bands = list(rates.index)
    others = [b for b in bands if b != REFERENCE]
    fatality = {b: ratio("deaths_per_1000_involved", b) for b in others}
    base, oldest = owner.loc[REFERENCE], owner.loc[OLDEST]
    moved = -float(base.transfer_bn_km)
    pooled_km = float(owner.loc[YOUNG[0], "billion_km_transfer"]) / float(
        owner.loc[YOUNG[0], "b_permit_holders"]
    )
    peers_involved = ratio("involved_per_bn_km", OLDEST, older)
    peers_fatality = ratio("deaths_per_1000_involved", OLDEST, older)
    working = company.loc[("to_working_age", OLDEST)]
    spread = company.loc["to_all_bands"].ratio_to_reference
    left_out = company.loc["excluded"].ratio_to_reference
    men_involved = sex_ratios.loc[("car", "18+", "involved_per_1000_licences")]
    men_fatality = sex_ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    men_killed = sex_ratios.loc[("car", "18+", "deaths_per_million_licences")]
    motor_killed = sex_ratios.loc[("motor", "18+", "deaths_per_million_licences")]
    motor_fatality = sex_ratios.loc[("motor", "18+", "deaths_per_1000_involved")]
    by_band_fatality = sex_ratios.xs(
        ("car", "deaths_per_1000_involved"), level=["scope", "measure"]
    )
    by_band_fatality = by_band_fatality.drop(index="18+")
    residents_75 = contrast.loc[("residents", OLDEST)]
    permit_75 = contrast.loc[("b_permit_holders", OLDEST)]
    involved_75 = contrast.loc[("drivers_involved", OLDEST)]
    km_75 = contrast.loc[("kilometres", OLDEST)]
    reference_census = ("35-44", "45-54")

    def chain_holds(band: str, which: str) -> bool:
        return math.isclose(
            end("involved_per_bn_km", band, which) * float(fatality[band].ratio),
            end("deaths_per_bn_km", band, which),
            rel_tol=1e-6,
        )

    # Deaths once involved: the oldest band far above the reference, a rise with every band
    # after it, and no difference at either young band.
    after = [rate(b) for b in bands[bands.index(REFERENCE) :]]
    _check(float(fatality[OLDEST].low) > 1, "drivers aged 75 and over die more once involved")
    _check(after == sorted(after), "deaths once involved rise with every band after 35-54")
    _check(
        all(float(fatality[b].low) <= 1 <= float(fatality[b].high) for b in YOUNG),
        "neither young band differs from 35-54 once involved",
    )
    # The owner's age stands poorly for the driver's at the young end and at 75 and over.
    _check(
        all(
            float(owner.loc[b, "cars_per_b_permit"]) < float(base.cars_per_b_permit)
            and float(owner.loc[b, "km_per_b_permit"]) < float(base.km_per_b_permit)
            for b in YOUNG
        )
        and float(owner.loc[YOUNG[0], "km_per_b_permit"])
        < float(owner.loc[YOUNG[1], "km_per_b_permit"]),
        "young licence holders have fewer cars and kilometres registered to them, the youngest "
        "fewest",
    )
    _check(
        float(oldest.cars_per_b_permit) > 1
        and all(float(owner.loc[b, "cars_per_b_permit"]) < 1 for b in bands if b != OLDEST),
        "75 and over is the only band with more cars than licence holders",
    )
    # The scenario adds kilometres to the young bands only, and lowers every ratio.
    _check(
        all(float(owner.loc[b, "transfer_bn_km"]) > 0 for b in YOUNG)
        and all(float(owner.loc[b, "transfer_bn_km"]) == 0 for b in (*MIDDLE, OLDEST))
        and all(
            scenario(m, b) < published(m, b)
            for m in ("involved_per_bn_km", "deaths_per_bn_km")
            for b in others
        ),
        "the scenario moves kilometres to the young bands only and lowers every ratio",
    )
    _check(
        all(chain_holds(b, which) for b in others for which in ("low", "high")),
        "involvement per km times deaths once involved equals deaths per km",
    )
    # Frequency: the young above the reference at both ends, 55-74 below at both ends, the
    # oldest about level; deaths per km above the reference for the young and the oldest.
    _check(
        all(end("involved_per_bn_km", b, "low") > 1 for b in YOUNG)
        and end("involved_per_bn_km", YOUNG[0], "low")
        > end("involved_per_bn_km", YOUNG[1], "high"),
        "both young bands are involved more often per km, 18-24 most",
    )
    _check(
        all(end("involved_per_bn_km", b, "high") < 1 for b in MIDDLE),
        "55-64 and 65-74 are involved less often per km at both ends",
    )
    _check(
        0.85 < end("involved_per_bn_km", OLDEST, "low")
        and end("involved_per_bn_km", OLDEST, "high") < 1.15,
        "drivers aged 75 and over are involved about as often per km as 35-54",
    )
    _check(
        all(end("deaths_per_bn_km", b, "low") > 1 for b in (*YOUNG, OLDEST))
        and all(
            abs(math.log(end("involved_per_bn_km", OLDEST, which)))
            < 0.5 * math.log(end("deaths_per_bn_km", OLDEST, which))
            for which in ("low", "high")
        ),
        "the young and the oldest die more per km; the oldest mainly through severity",
    )
    _check(
        float(peers_involved.low) > 1 and float(peers_fatality.low) > 1,
        "against 65-74, drivers aged 75 and over are higher on both factors",
    )
    _check(
        all(math.isclose(float(spread[b]), float(left_out[b]), rel_tol=1e-6) for b in spread.index)
        and float(working.ratio_to_reference) > published("deaths_per_bn_km", OLDEST),
        "company kilometres spread in proportion change no ratio; over 18-64 they raise 75+",
    )
    # The four denominators for the oldest band, each step larger than the one before.
    _check(
        math.isclose(float(km_75.ratio), published("deaths_per_bn_km", OLDEST), rel_tol=1e-6)
        and float(residents_75.ratio) < float(permit_75.ratio) < float(km_75.ratio)
        and all(
            float(licence.loc[(OLDEST, "total"), "licence_share"])
            < float(licence.loc[(b, "total"), "licence_share"])
            for b in reference_census
        ),
        "per resident, per B-permit holder and per km rise in turn for 75 and over",
    )
    # Men against women: higher on every measure, more so once involved, in every age band.
    _check(
        min(float(men_involved.low), float(men_fatality.low), float(men_killed.low)) > 1
        and float(men_fatality.ratio) > float(men_involved.ratio)
        and float(motor_killed.ratio) > float(men_killed.ratio)
        and float(motor_fatality.ratio) > float(men_fatality.ratio)
        and bool((by_band_fatality.low > 1).all()),
        "men are higher than women on every measure, most of all once involved, in every band",
    )

    young_high = {b: end("involved_per_bn_km", b, "high") for b in YOUNG}

    # How far each band would have to drive to match the 35–54 (or 65–74) rate per kilometre.
    breakeven = read_table("q7_breakeven_km").set_index(["reference_band", "kilometres", "band"])

    def needed(band: str, reference: str = REFERENCE, kilometres: str = "published") -> pd.Series:
        return breakeven.loc[(reference, kilometres, band)]

    youngest_need, young_need = needed(YOUNG[0]), needed(YOUNG[1])
    youngest_scenario = needed(YOUNG[0], kilometres="scenario")
    oldest_need, oldest_peer_need = needed(OLDEST), needed(OLDEST, reference="65-74")
    highest_km = float(youngest_need.highest_credited_km)
    highest_band = str(youngest_need.highest_credited_band)
    middle_need = {b: needed(b) for b in MIDDLE}
    km_per_car = owner.billion_km * 1e9 / owner.cars
    _check(
        float(youngest_need.needed_low) > 1.5 * highest_km
        and float(youngest_scenario.needed_low) > highest_km,
        "18-24 drivers would need far more km per holder than any owner band is credited with",
    )
    _check(
        float(young_need.needed_low) > highest_km,
        "25-34 drivers would need more km per holder than any owner band is credited with",
    )
    _check(
        all(float(middle_need[b].needed_over_credited_high) < 1 for b in MIDDLE),
        "55-64 and 65-74 would match 35-54 only by driving less than their cars are credited",
    )
    _check(
        float(oldest_need.needed_over_credited_low)
        < 1
        < float(oldest_need.needed_over_credited_high),
        "against 35-54, the 75+ break-even distance is what their cars are credited with",
    )
    _check(
        float(oldest_peer_need.needed_low) > highest_km
        and float(km_per_car[OLDEST]) == float(km_per_car.min()),
        "against 65-74, 75+ would need more km than any band is credited, and their cars are "
        "driven least",
    )

    def km(value: float) -> str:
        return f"{float(value):,.0f}"

    def round_km(value: float) -> str:
        return f"{round(float(value), -2):,.0f}"

    body = summary(
        "Once they are in an injury crash, car drivers aged 75 and over die far more often than "
        f"middle-aged drivers: in {year}, {rate(OLDEST):.1f} of every 1,000 involved died within "
        f"30 days, against {rate(REFERENCE):.1f} per 1,000 at 35–54. That comparison uses only "
        "crash records. How often each age group is involved in crashes for the distance it "
        "drives is less certain, because DGT counts kilometres by the age of a car's registered "
        "owner, not its driver. On those kilometres, drivers aged 18–24 were involved in "
        f"{young_high[YOUNG[0]]:.2f} times as many injury crashes per kilometre as drivers aged "
        "35–54; for them to be involved no more often, each would have to drive about twice as "
        "far as the licence holders of any owner age group are credited with. Drivers aged 75 "
        "and over were involved about as often per kilometre as drivers aged 35–54, and "
        f"{float(peers_involved.ratio):.2f} times as often as drivers aged 65–74. Per licence "
        f"holder, men died at the wheel of a car {float(men_killed.ratio):.2f} times as often as "
        f"women in {sex_years}."
    )

    # ------------------------------------------------------------------- deaths once involved
    body += "<h2>Deaths once a crash has happened</h2>"
    body += key_result(
        f"{float(fatality[OLDEST].ratio):.2f}×",
        "Car drivers aged 75 and over who were involved in an injury crash died within 30 days "
        f"{float(fatality[OLDEST].ratio):.2f} times as often as drivers aged 35–54 "
        f"({rate(OLDEST):.1f} against {rate(REFERENCE):.1f} per 1,000 drivers involved, {year}; "
        f"95% interval {ci(fatality[OLDEST])}).",
    )
    body += (
        "<p>This rate divides the car drivers killed within 30 days by all car drivers involved "
        "in injury crashes, injured or not, of the same age in the same year. Both counts come "
        "from DGT's tables of drivers involved in crashes, so no measure of driving enters it. "
        f"It rises with every band after 35–54: {rate(MIDDLE[0]):.1f} deaths per 1,000 drivers "
        f"involved at 55–64, {rate(MIDDLE[1]):.1f} at 65–74 and {rate(OLDEST):.1f} at 75 and "
        f"over. Drivers aged 18–24 ({rate(YOUNG[0]):.1f}) and 25–34 ({rate(YOUNG[1]):.1f}) "
        f"cannot be distinguished from those aged 35–54 ({rate(REFERENCE):.1f}): the 95% "
        f"intervals of their ratios to 35–54, {ci(fatality[YOUNG[0]])} and "
        f"{ci(fatality[YOUNG[1]])}, both include 1.</p>"
    )
    body += figure(
        "a1_killed_per_involved",
        f"Dot chart of car drivers killed per 1,000 involved in an injury crash in {year}, by age "
        "band, with 95% intervals. The rate is level from 18 to 54 and rises with each older "
        "band, to about four times the 35–54 rate at 75 and over.",
        captions,
    )
    body += (
        "<p>The rate counts only the driver's own death. The tables do not say how often other "
        "people in the same crashes died, so the measure cannot show whether older drivers' "
        "crashes are more dangerous to others.</p>"
    )

    # ------------------------------------------------------------------- crashes per kilometre
    young_km = owner.loc[list(YOUNG)]
    body += "<h2>Crashes relative to kilometres by owner age</h2>"
    body += evidence_note(
        "The rates in this section rest on kilometres counted by the age of a car's registered "
        "owner, not its driver, so they are less certain than the deaths once involved above."
    )
    body += (
        f"<p>DGT estimates the kilometres driven by cars in {year} from odometer readings taken "
        "at roadworthiness (ITV) inspections, and publishes them by the age of each car's "
        "registered owner. No source gives kilometres by the driver's age. The rates per "
        "kilometre on this page therefore divide the drivers of each age involved in injury "
        "crashes by the kilometres of cars registered to owners of the same age. On those "
        "kilometres, drivers aged 18–24 were involved in "
        f"{float(rates.loc[YOUNG[0], 'involved_per_bn_km']):,.0f} injury crashes per billion km "
        f"and drivers aged 25–34 in {float(rates.loc[YOUNG[1], 'involved_per_bn_km']):,.0f}, "
        f"against {float(rates.loc[REFERENCE, 'involved_per_bn_km']):,.0f} at 35–54, "
        f"{float(rates.loc[MIDDLE[0], 'involved_per_bn_km']):,.0f} at 55–64, "
        f"{float(rates.loc[MIDDLE[1], 'involved_per_bn_km']):,.0f} at 65–74 and "
        f"{float(rates.loc[OLDEST, 'involved_per_bn_km']):,.0f} at 75 and over.</p>"
    )
    body += figure(
        "a4_involved_per_km",
        f"Dot chart of car drivers involved in injury crashes per billion kilometres in {year}, "
        "by age band, on a log scale. On the published owner-age kilometres the rate is highest "
        "at 18–24, falls to 35–54, is lowest at 55–74 and returns to about the 35–54 level at 75 "
        "and over; moving kilometres to the young bands narrows their excess but leaves it above "
        "35–54.",
        captions,
    )
    body += (
        "<p>Few cars are registered to young owners. For every holder of a B (car) licence, "
        "there are "
        f"{float(young_km.loc[YOUNG[0], 'cars_per_b_permit']):.2f} cars and "
        f"{float(young_km.loc[YOUNG[0], 'km_per_b_permit']):,.0f} km a year registered to "
        f"owners aged 18–24, {float(young_km.loc[YOUNG[1], 'cars_per_b_permit']):.2f} cars and "
        f"{float(young_km.loc[YOUNG[1], 'km_per_b_permit']):,.0f} km at 25–34, and "
        f"{float(base.cars_per_b_permit):.2f} cars and {float(base.km_per_b_permit):,.0f} km at "
        "35–54. The gap can reflect less driving by young licence holders, their use of cars "
        "registered to older people or to companies, or a combination of these. The source "
        "cannot separate them. Kilometres that young people drive in cars registered to others "
        "are counted in another band, which makes their published rates per kilometre too "
        "high.</p>"
    )
    body += (
        "<p>A sensitivity scenario, the grey band in the chart, shows how much this could change "
        "the result. It moves kilometres from the 35–54 band to the two young bands until all "
        f"three have the same kilometres per licence holder ({pooled_km * 1e9:,.0f} a year), as "
        "if the whole gap were young people driving cars registered to owners aged 35–54. The "
        f"reassignment is deliberately extreme: {moved:.1f} billion km, "
        f"{_fmt_pct(moved / float(base.billion_km))} of the 35–54 kilometres. Under it, drivers "
        "aged 18–24 were involved in injury crashes "
        f"{scenario('involved_per_bn_km', YOUNG[0]):.2f} times as often per kilometre as drivers "
        f"aged 35–54, against {published('involved_per_bn_km', YOUNG[0]):.2f} times on the "
        "published owner-age kilometres; for drivers aged 25–34 the figures are "
        f"{scenario('involved_per_bn_km', YOUNG[1]):.2f} and "
        f"{published('involved_per_bn_km', YOUNG[1]):.2f}. The two values form a sensitivity "
        "range, not a confidence interval: the data do not show how many kilometres should be "
        "reassigned between age groups, so the true ratio need not lie between them.</p>"
    )

    body += "<h3>The distance each age group would have to drive</h3>"
    body += (
        "<p>The owner-age kilometres cannot be corrected without knowing who drives each car, "
        "and the data do not say: DGT publishes drivers' recorded infractions by vehicle type, "
        "not by age, and its national crash file has no records of drivers. The question can be "
        "turned round. The table gives, for each age group, the distance each B-licence holder "
        "would have to drive in a year for the group to be involved in injury crashes no more "
        "often per kilometre than drivers aged 35–54, beside the kilometres per licence holder "
        "credited to cars of owners that age.</p>"
    )
    body += _breakeven_table(breakeven, year)
    body += (
        f"<p>Drivers aged 18–24 would each have to drive about "
        f"{round_km(youngest_need.needed_km_per_b_permit)} km a year (95% interval "
        f"{round_km(youngest_need.needed_low)}–{round_km(youngest_need.needed_high)}): "
        f"{float(youngest_need.needed_over_credited):.2f} times the kilometres credited to cars "
        "of owners their age, and about twice the most credited per licence holder to any "
        f"owner age group ({km(highest_km)} at {highest_band.replace('-', '–')}). Even after "
        "the scenario moves kilometres to them, they would need "
        f"{round_km(youngest_scenario.needed_km_per_b_permit)}. Their higher involvement per "
        "kilometre therefore does not depend on the owner-age kilometres being right. Drivers "
        f"aged 25–34 would need about {round_km(young_need.needed_km_per_b_permit)} km, "
        f"{float(young_need.needed_km_per_b_permit) / highest_km:.2f} times the most credited to "
        "any owner age group, so their higher involvement is likely but less clear-cut. Drivers "
        "aged 55–64 and 65–74 would be involved as often per kilometre as drivers aged 35–54 if "
        "they drove about "
        f"{_fmt_pct(1 - float(middle_need[MIDDLE[0]].needed_over_credited), 0)} and "
        f"{_fmt_pct(1 - float(middle_need[MIDDLE[1]].needed_over_credited), 0)} less than the "
        "kilometres credited to their cars. The data cannot rule that out, so their lower "
        "involvement per kilometre is less firmly established than the young drivers' higher "
        "one.</p>"
    )
    body += (
        "<p>For drivers aged 75 and over the distance needed to match drivers aged 35–54, about "
        f"{round_km(oldest_need.needed_km_per_b_permit)} km, is almost exactly what is credited "
        f"to cars of owners their age ({km(oldest_need.credited_km_per_b_permit)}), so that "
        "comparison turns on whether they drive more or less than their own cars' kilometres. "
        "Owners aged 75 and over also have "
        f"{float(oldest.cars_per_b_permit):.2f} cars per licence holder, the only band with more "
        "cars than licence holders, which shows again that owner age cannot be treated as "
        "driver age; the data do not identify who drives those cars. Drivers aged 65–74 give a "
        "closer comparison. Against them, on the published owner-age kilometres, drivers aged 75 "
        f"and over were involved in injury crashes {float(peers_involved.ratio):.2f} times as "
        f"often per kilometre ({ci(peers_involved)}) and died "
        f"{float(peers_fatality.ratio):.2f} times as often once involved "
        f"({ci(peers_fatality)}). To be involved no more often per kilometre than drivers aged "
        "65–74, they would each need to drive about "
        f"{round_km(oldest_peer_need.needed_km_per_b_permit)} km a year (95% interval "
        f"{round_km(oldest_peer_need.needed_low)}–{round_km(oldest_peer_need.needed_high)}), "
        "more than is "
        "credited per licence holder to any owner age group. The data give no sign that they "
        "do: cars registered to owners aged 75 and over are driven fewer kilometres a year "
        f"({km(km_per_car[OLDEST])} per car) than the cars of any other owner age group.</p>"
    )
    body += _ratio_table(ratios, owner, rates, year)
    body += (
        "<p>The columns of this table separate crash frequency from severity. At both ends of "
        "the range, drivers aged 18–24 and 25–34 have higher death rates per kilometre than "
        "drivers aged 35–54 because they are involved in more crashes per kilometre; once "
        "involved, their death rates cannot be distinguished from the 35–54 rate. Drivers aged "
        "75 and over are involved about as often per kilometre as drivers aged 35–54 but die "
        "far more often once involved, so their higher death rate per kilometre "
        f"({_range(end('deaths_per_bn_km', OLDEST, 'low'), end('deaths_per_bn_km', OLDEST, 'high'))}) "
        "comes mainly from severity. The scenario takes kilometres from the reference band, so it "
        "lowers the oldest band's ratios too, which is why they are also ranges.</p>"
    )

    # ------------------------------------------------------------------- men and women
    body += "<h2>Men and women</h2>"
    body += (
        "<p>No source records kilometres driven by sex, so men and women are compared per "
        f"licence holder and per driver involved, pooling {sex_years}. Male car drivers were "
        f"involved in injury crashes {float(men_involved.ratio):.2f} times as often as female "
        f"drivers per licence holder ({ci(men_involved)}) and, once involved, died "
        f"{float(men_fatality.ratio):.2f} times as often ({ci(men_fatality)}). Combined, per "
        f"licence holder, men died at the wheel {float(men_killed.ratio):.2f} times as often as "
        f"women ({ci(men_killed)}). The gap once involved holds in every age band. Involvement "
        "per licence holder combines how far men and women drive with how often they crash per "
        "kilometre, and no source separates the two.</p>"
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
        f"{float(motor_fatality.ratio):.2f} times as often once involved.</p>"
    )

    # ------------------------------------------------------------------- technical detail
    licence_share = float(licence.loc[(OLDEST, "total"), "licence_share"])
    reference_shares = [float(licence.loc[(b, "total"), "licence_share"]) for b in reference_census]
    body += technical(
        "The same deaths under four denominators",
        "<p>Against drivers aged 35–54, car drivers aged 75 and over died "
        f"{_times(float(residents_75.ratio))} as often per resident, "
        f"{_times(float(permit_75.ratio))} per holder of a B permit, "
        f"{_times(float(km_75.ratio))} per kilometre on the published owner-age kilometres and "
        f"{_times(float(involved_75.ratio))} per driver involved. The deaths are the same in "
        "each case; only the denominator changes. Dividing by licence holders allows for how "
        f"many people in each band hold a licence: in {licence_year}, "
        f"{_fmt_pct(licence_share)} of residents aged 75 and over held one, against "
        f"{_fmt_pct(min(reference_shares))}–{_fmt_pct(max(reference_shares))} at 35–54. "
        "Dividing by kilometres allows for distance driven only as far as the kilometres of "
        "cars registered to owners of each age reflect it. Dividing by drivers involved removes "
        "crash frequency and leaves severity. Drivers aged 18–24 are missing from this comparison "
        "because INE's resident counts are grouped as 15–19 and 20–24.</p>"
        + figure(
            "a2_denominator_contrast",
            f"Car-driver deaths in {year} by age band, as ratios to drivers aged 35–54, divided in "
            "turn by residents, B-permit holders, drivers involved in injury crashes and "
            "kilometres of cars registered to owners of each age",
            captions,
        ),
    )
    company_share = float(km_table.loc[driver_risk.COMPANY_BAND, "share_of_km"])
    body += technical(
        "Company cars and the kilometre denominator",
        f"<p>Cars registered to companies, {_fmt_pct(company_share)} of car kilometres, have no "
        "owner age, so their kilometres drop out of the denominator while their drivers stay in "
        "the numerator. Spreading those kilometres over every band in proportion changes no "
        "ratio. Spreading them over the bands from 18 to 64 raises the ratio of deaths per "
        f"kilometre at 75 and over from {_times(published('deaths_per_bn_km', OLDEST))} to "
        f"{_times(float(working.ratio_to_reference))}. Deaths once involved are unaffected.</p>",
    )
    body += technical(
        "Detailed counts, kilometres and rates",
        _rates_table(rates, year) + _sex_rates_table(sex_rates, sex_years),
    )

    body += limitation(
        "DGT describes its kilometre estimates as valid only in aggregate, and the intervals "
        "treat them as exact. The crash counts include foreign-registered cars and unlicensed "
        "drivers; the kilometres cover Spanish-registered cars only. Drivers whose age or sex "
        "the tables do not record are left out."
    )
    body += downloads(
        [
            ("q7_km_rates", "rates by age band"),
            ("q7_km_ratio", "ratios to drivers aged 35–54"),
            ("q7_km_ratio_65_74", "ratios to drivers aged 65–74"),
            ("q7_owner_age_check", "owner-age check and scenario"),
            ("q7_breakeven_km", "distance needed to match drivers aged 35–54 and 65–74"),
            ("q7_company_km", "company-car scenarios"),
            ("q7_denominator_contrast", "the four denominators"),
            ("q7_km_by_owner_age", "kilometres by owner age"),
            ("q7_licence_share", "licence holding by age and sex"),
            ("drivers_sex_rates", "rates by sex and age"),
            ("drivers_sex_ratios", "men against women"),
            ("drivers_sex_trend", f"by sex and year, {trend_years}"),
        ],
        method=("data.html#rates", "rates and denominators"),
    )
    return render_page(
        "drivers",
        "Driver age and sex",
        "Car drivers compared by age and by sex, using DGT's counts of drivers involved in "
        "injury crashes and killed, set against the measures of driving available for each "
        "group.",
        body,
    )
