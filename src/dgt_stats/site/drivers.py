"""Driver age and sex: how often car drivers are in crashes, and how often a crash kills the driver.

The page leads with deaths per driver involved, the one comparison that needs no estimate of
kilometres, and then compares involvement in crashes with DGT's kilometres by the registered
owner's age, which are not kilometres by the driver's age. Every number is read from the ``q7_*`` and ``drivers_sex_*`` tables,
and every qualitative sentence is checked against them before the page is written.
"""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import driver_risk
from dgt_stats.site.components import (
    _fmt_pct,
    _ratio_ci,
    _times,
    downloads,
    figure,
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
    km = read_table("q7_km_by_owner_age").set_index("band")
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

    young_low = {b: end("involved_per_bn_km", b, "low") for b in YOUNG}
    young_high = {b: end("involved_per_bn_km", b, "high") for b in YOUNG}
    body = summary(
        "Once they are in an injury crash, car drivers aged 75 and over die far more often than "
        f"middle-aged drivers. In {year}, {rate(OLDEST):.1f} of every 1,000 drivers aged 75 and "
        f"over involved in an injury crash died within 30 days, against {rate(REFERENCE):.1f} "
        f"per 1,000 at 35–54: {float(fatality[OLDEST].ratio):.2f} times as often (95% interval "
        f"{ci(fatality[OLDEST])}). This comparison uses only crash records, so it needs no "
        "estimate of kilometres. Once involved, drivers aged 18–24 and 25–34 died about as often "
        "as drivers aged 35–54. Measured against the kilometres of cars registered to owners of "
        "their age, they were involved in injury crashes more often: "
        f"{young_high[YOUNG[0]]:.2f} times the 35–54 rate at 18–24 and "
        f"{young_high[YOUNG[1]]:.2f} times at 25–34. Because those kilometres follow the owner's "
        "age, not the driver's, the page also tests a deliberately extreme reassignment of "
        "kilometres to the young owner bands: the ratios fall to "
        f"{young_low[YOUNG[0]]:.2f} and {young_low[YOUNG[1]]:.2f} but stay above 1. Per licence "
        "holder, men died at the wheel of a car "
        f"{float(men_killed.ratio):.2f} times as often as women in {sex_years}."
    )

    # ------------------------------------------------------------------- deaths once involved
    body += "<h2>Deaths once a crash has happened</h2>"
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
    body += (
        f"<p>DGT estimates the kilometres driven by cars in {year} from odometer readings taken "
        "at roadworthiness (ITV) inspections, and publishes them by the age of each car's "
        "registered owner. No source gives kilometres by the driver's age. The rates per "
        "kilometre on this page therefore divide the drivers of each age involved in injury "
        "crashes by the kilometres of cars registered to owners of the same age.</p>"
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
        "<p>A sensitivity scenario shows how much this could change the result. It moves "
        "kilometres from the 35–54 band to the two young bands until all three have the same "
        f"kilometres per licence holder ({pooled_km * 1e9:,.0f} a year), as if the whole gap "
        "were young people driving cars registered to owners aged 35–54. The reassignment is "
        f"deliberately extreme: {moved:.1f} billion km, "
        f"{_fmt_pct(moved / float(base.billion_km))} of the 35–54 kilometres. Under it, drivers "
        "aged 18–24 were involved in injury crashes "
        f"{scenario('involved_per_bn_km', YOUNG[0]):.2f} times as often per kilometre as drivers "
        f"aged 35–54, against {published('involved_per_bn_km', YOUNG[0]):.2f} times on the "
        "published owner-age kilometres; for drivers aged 25–34 the figures are "
        f"{scenario('involved_per_bn_km', YOUNG[1]):.2f} and "
        f"{published('involved_per_bn_km', YOUNG[1]):.2f}. Each per-kilometre ratio in the "
        "table runs between these two values. The two values form a sensitivity range, not a "
        "confidence interval: the data do not show how many kilometres should be reassigned "
        "between age groups, so the true ratio need not lie between them.</p>"
    )
    body += _ratio_table(ratios, owner, rates, year)
    body += (
        "<p>The columns separate crash frequency from severity. At both ends of the range, "
        "drivers aged 18–24 and 25–34 have higher death rates per kilometre than drivers aged "
        "35–54 because they are involved in more crashes per kilometre; once involved, their "
        "death rates cannot be distinguished from the 35–54 rate. Drivers aged 55–64 and 65–74 "
        "are involved less often per kilometre at both ends of the range. Drivers aged 75 and "
        "over are involved about as often per kilometre as "
        "drivers aged 35–54 but die far more often once involved, so their higher death rate "
        f"per kilometre ({_range(end('deaths_per_bn_km', OLDEST, 'low'), end('deaths_per_bn_km', OLDEST, 'high'))}) "
        "comes mainly from severity.</p>"
    )
    body += (
        "<p>The scenario takes kilometres from the reference band, so it lowers the oldest "
        "band's ratios too, which is why they are also ranges. Owners aged 75 and over have "
        f"{float(oldest.cars_per_b_permit):.2f} cars per licence holder, the only band with more "
        "cars than licence holders. This shows again that owner age cannot be treated as driver "
        "age. The data do not identify who drives those cars. Drivers aged 65–74 give a "
        "comparison that the scenario does not touch. Against them, on the published owner-age "
        "kilometres, drivers aged 75 and over were involved in injury crashes "
        f"{float(peers_involved.ratio):.2f} times as often per kilometre "
        f"({ci(peers_involved)}) and died {float(peers_fatality.ratio):.2f} times as often once "
        f"involved ({ci(peers_fatality)}).</p>"
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
    company_share = float(km.loc[driver_risk.COMPANY_BAND, "share_of_km"])
    body += technical(
        "Company cars",
        f"<p>Cars registered to companies, {_fmt_pct(company_share)} of car kilometres, have no "
        "owner age, so their kilometres drop out of the denominator while their drivers stay in "
        "the numerator. Spreading those kilometres over every band in proportion changes no "
        "ratio. Spreading them over the bands from 18 to 64 raises the ratio of deaths per "
        f"kilometre at 75 and over from {_times(published('deaths_per_bn_km', OLDEST))} to "
        f"{_times(float(working.ratio_to_reference))}. Deaths once involved are unaffected.</p>",
    )
    body += technical(
        "Counts, kilometres and rates",
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
