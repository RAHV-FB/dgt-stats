"""Driver age and sex: how often car drivers crash, and how often a crash kills the driver."""

from __future__ import annotations

import math

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
    limitation,
    read_table,
    render_page,
    summary,
    table,
    technical,
)
from dgt_stats.site.numbers import _age_numbers, _sex_numbers

# The denominator of every per-km rate on the page, said in full once.
OWNER_KM = "kilometres driven by cars registered to owners of the same age"


def _range(low: float, high: float) -> str:
    """A per-km ratio as the range from the reallocation scenario to the published ratio."""
    return f"{low:.2f}–{high:.2f}×"


def _band(band: str) -> str:
    """A band key such as '35-44' as it is printed: '35–44'."""
    return band.replace("-", "–")


def _licence() -> tuple[int, pd.DataFrame]:
    """The latest year of licence holding by age band and sex, indexed by (band, sex)."""
    licence = read_table("q7_licence_share")
    year = int(licence.year.max())
    return year, licence[licence.year == year].set_index(["band", "sex"])


def _sex_section(captions: dict[str, str]) -> tuple[str, dict[str, pd.Series], str, str]:
    numbers = _sex_numbers()
    ratios, rates_table = numbers["ratios"], numbers["rates"]
    involved = ratios.loc[("car", "18+", "involved_per_1000_licences")]
    killed = ratios.loc[("car", "18+", "deaths_per_million_licences")]
    fatality = ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    motor_fatality = ratios.loc[("motor", "18+", "deaths_per_1000_involved")]
    motor_killed = ratios.loc[("motor", "18+", "deaths_per_million_licences")]
    years = str(rates_table.years.iloc[0]).replace("-", "–")
    trend = read_table("drivers_sex_trend")
    trend_years = f"{int(trend.year.min())}–{int(trend.year.max())}"
    _, latest_licence = _licence()
    by_sex = latest_licence.licence_share.unstack("sex")
    sex_gap = (by_sex.male - by_sex.female).loc[["35-44", "45-54", "55-64", "65-74", "75+"]]
    # Men's rates are higher on every measure, higher once involved than in involvement, and the
    # gaps are wider across all motor-vehicle drivers. The gap in licence holding between the
    # sexes widens with every band from 35-44, and most women aged 75 and over hold no licence.
    if not (
        min(float(involved.low), float(fatality.low), float(killed.low)) > 1
        and float(fatality.ratio) > float(involved.ratio)
        and float(motor_killed.ratio) > float(killed.ratio)
        and float(motor_fatality.ratio) > float(fatality.ratio)
        and sex_gap.is_monotonic_increasing
        and float(sex_gap["35-44"]) > 0
        and float(latest_licence.loc[("75+", "female"), "licence_share"]) < 0.5
    ):
        raise ValueError("drivers page: the sex ratios no longer read as described")

    def ci(row: pd.Series) -> str:
        return _ratio_ci(float(row.ratio), float(row.low), float(row.high))

    def share(band: str, sex: str) -> str:
        return _fmt_pct(float(latest_licence.loc[(band, sex), "licence_share"]))

    section = "<h2>Men and women</h2>"
    section += (
        "<p>None of the data sources records kilometres driven by sex, so men and women are "
        f"compared per licence holder and per driver involved, with the years {years} pooled. "
        f"Male car drivers were involved in injury crashes {ci(involved)} as often as female "
        f"drivers per licence holder, and once involved they were killed {ci(fatality)} as "
        "often. Together, per licence holder, men died at the wheel of a car "
        f"{ci(killed)} as often as women. Involvement per licence holder combines how far each "
        "sex drives with how often they crash for the distance driven, and the data do not "
        "separate the two.</p>"
    )
    section += (
        "<p>Licence holding itself differs between the sexes, and more so with age: the gap "
        f"between men and women widens with each band from {_band('35-44')}, and among people "
        f"aged 75 and over, {share('75+', 'male')} of men held a licence against "
        f"{share('75+', 'female')} of women. A rate per resident for older women would "
        "therefore divide by a population most of whom hold no licence.</p>"
    )
    section += figure(
        "a3_sex_ratios",
        f"Ratios of men's to women's rates for car drivers, {years}, overall and by age band: "
        "involvement in injury crashes per licence holder, deaths per licence holder, and "
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
                    "Involved per 1,000 licence holders a year": row.involved_per_1000_licences,
                    "Killed per million licence holders a year": row.deaths_per_million_licences,
                    "Killed per 1,000 involved": row.deaths_per_1000_involved,
                    "Drivers killed": row.driver_deaths,
                }
            )
    section += table(
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
    section += (
        "<p>Across all motor-vehicle drivers, which adds motorcyclists, moped riders and the "
        "drivers of vans, trucks and buses to car drivers, the gaps are wider: men died "
        f"{_times(float(motor_killed.ratio))} as often as women per licence holder and "
        f"{_times(float(motor_fatality.ratio))} as often per driver involved. Cyclists and riders "
        "of personal mobility vehicles need no licence and are left out of both groups. The "
        "licence counts cover every type of licence, since the driver census gives B-permit "
        "holders by sex only for recent years.</p>"
    )
    return (
        section,
        {"involved": involved, "fatality": fatality, "killed": killed},
        years,
        trend_years,
    )


def _ratio_table(ratios: pd.DataFrame, owner: pd.DataFrame, rates: pd.DataFrame, year: int) -> str:
    """Ratios to 35-54: involvement per km × deaths per driver involved = deaths per km."""

    def per_involved(band: str) -> str:
        if band == driver_risk.REFERENCE_BAND:
            return "1 (reference)"
        row = ratios.loc[("deaths_per_1000_involved", band)]
        return _ratio_ci(float(row.ratio), float(row.low), float(row.high))

    def per_km(measure: str, band: str) -> str:
        if band == driver_risk.REFERENCE_BAND:
            return "1 (reference)"
        row = owner.loc[band]
        return _range(float(row[f"{measure}_range_low"]), float(row[f"{measure}_range_high"]))

    rows = [
        {
            "Age band": rates.loc[band, "band_label"],
            "Involved in an injury crash, per km": per_km("involved_per_bn_km", band),
            "Killed, per driver involved": per_involved(band),
            "Killed, per km": per_km("deaths_per_bn_km", band),
        }
        for band in rates.index
    ]
    return table(
        pd.DataFrame(rows),
        f"Car drivers by age, {year}: ratios to drivers aged 35–54. Per-kilometre ratios run "
        "from the reallocation scenario to the published figure; deaths per driver involved are "
        "shown with 95% intervals. At either end of a range, involvement per km × deaths per "
        "driver involved = deaths per km.",
    )


def _rates_table(rates: pd.DataFrame, year: int) -> str:
    frame = pd.DataFrame(
        {
            "Age band": rates.band_label,
            "Drivers involved": rates.drivers_involved,
            "Drivers killed": rates.driver_deaths,
            "Kilometres (billion)": rates.billion_km,
            "Involved per billion km": rates.involved_per_bn_km,
            "Killed per 1,000 involved": rates.deaths_per_1000_involved,
            "Killed per billion km": rates.deaths_per_bn_km,
        }
    )
    return table(
        frame,
        f"Car drivers by age, {year}: drivers involved in injury crashes and killed within 30 "
        "days, and the published kilometres of cars registered to owners in each band. "
        "Involved per billion km × killed per 1,000 involved ÷ 1,000 = killed per billion km.",
        {
            "Drivers involved": "int",
            "Drivers killed": "int",
            "Kilometres (billion)": "dec",
            "Involved per billion km": "dec0",
            "Killed per 1,000 involved": "dec",
            "Killed per billion km": "dec2",
        },
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
    label = rates.band_label

    def ratio_text(measure: str, band: str, frame: pd.DataFrame = ratios) -> str:
        row = frame.loc[(measure, band)]
        return _ratio_ci(float(row.ratio), float(row.low), float(row.high))

    def km_range(measure: str, band: str) -> str:
        row = owner.loc[band]
        return _range(float(row[f"{measure}_range_low"]), float(row[f"{measure}_range_high"]))

    def published(measure: str, band: str) -> float:
        return float(owner.loc[band, f"{measure}_ratio"])

    def reallocated(measure: str, band: str) -> float:
        return float(owner.loc[band, f"{measure}_ratio_transfer"])

    sex_section, sex, sex_years, trend_years = _sex_section(captions)
    men_killed = sex["killed"]
    young, base, oldest = owner.loc["18-34"], owner.loc[reference], owner.loc["75+"]
    shortfall = float(young.transfer_bn_km)
    fatality_young = ratios.loc[("deaths_per_1000_involved", "18-34")]
    fatality_old = ratios.loc[("deaths_per_1000_involved", "75+")]
    others = [b for b in rates.index if b != reference]
    fatality_by_age = [
        float(ratios.loc[("deaths_per_1000_involved", b), "ratio"])
        for b in rates.index
        if b != "18-34"
    ]
    middle = ("55-64", "65-74")
    measures = ("involved_per_bn_km", "deaths_per_bn_km")
    year_licence, latest_licence = _licence()
    reference_bands = ("35-44", "45-54")
    working = company.loc[("to_working_age", "75+")]
    spread = company.loc["to_all_bands"].ratio_to_reference
    left_out = company.loc["excluded"].ratio_to_reference
    peers_involved = older.loc[("involved_per_bn_km", "75+")]
    peers_fatality = older.loc[("deaths_per_1000_involved", "75+")]
    residents_75 = contrast.loc[("residents", "75+")]
    permit_75 = contrast.loc[("b_permit_holders", "75+")]
    involved_75 = contrast.loc[("drivers_involved", "75+")]
    km_75 = contrast.loc[("kilometres", "75+")]

    def chain_holds(band: str, end: str) -> bool:
        return math.isclose(
            float(owner.loc[band, f"involved_per_bn_km_{end}"])
            * float(ratios.loc[("deaths_per_1000_involved", band), "ratio"]),
            float(owner.loc[band, f"deaths_per_bn_km_{end}"]),
            rel_tol=1e-6,
        )

    # Every qualitative statement below, checked against the tables it rests on.
    if not (
        # The share killed once involved rises with every band after 35-54; 18-34 is no different
        # from 35-54; 75 and over is higher, outside its interval.
        fatality_by_age == sorted(fatality_by_age)
        and float(fatality_young.low) <= 1 <= float(fatality_young.high)
        and float(fatality_old.low) > 1
        # Owner and driver diverge: fewer cars and kilometres per B-permit holder at 18-34, more
        # cars than B-permit holders at 75 and over, close to one car each at 55-64 and 65-74.
        and float(young.cars_per_b_permit) < float(base.cars_per_b_permit)
        and float(young.km_per_b_permit) < float(base.km_per_b_permit)
        and float(oldest.cars_per_b_permit) > 1
        and all(abs(float(owner.loc[b, "cars_per_b_permit"]) - 1) < 0.1 for b in middle)
        and float(oldest.km_per_b_permit) < float(base.km_per_b_permit)
        # The reallocation scenario moves kilometres to 18-34 only, and lowers every other band's
        # per-km ratio to 35-54.
        and shortfall > 0
        and float(owner.loc["65-74", "transfer_bn_km"]) == 0
        and float(owner.loc["75+", "transfer_bn_km"]) == 0
        and all(reallocated(m, b) < published(m, b) for m in measures for b in others)
        # Involvement per km x deaths per driver involved = deaths per km, at both ends.
        and all(chain_holds(b, end) for b in others for end in ("range_low", "range_high"))
        # 18-34 crash more per km at either end; 75 and over about as often as 35-54; 55-64 and
        # 65-74 less often at either end.
        and float(owner.loc["18-34", "involved_per_bn_km_range_low"]) > 1
        and 0.85 < float(oldest.involved_per_bn_km_range_low)
        and float(oldest.involved_per_bn_km_range_high) < 1.15
        and all(float(owner.loc[b, "involved_per_bn_km_range_high"]) < 1 for b in middle)
        # Both 18-34 and 75 and over die more per km than 35-54 at either end of the range; at
        # 75 and over, most of the excess (on the log scale) lies in deaths per driver involved.
        and all(float(owner.loc[b, "deaths_per_bn_km_range_low"]) > 1 for b in ("18-34", "75+"))
        and all(
            abs(math.log(float(oldest[f"involved_per_bn_km_{end}"])))
            < 0.5 * math.log(float(oldest[f"deaths_per_bn_km_{end}"]))
            for end in ("range_low", "range_high")
        )
        # Against 65-74, the oldest drivers are higher on both factors.
        and float(peers_involved.low) > 1
        and float(peers_fatality.low) > 1
        # Company kilometres: spread in proportion they change no ratio; spread over 18-64 they
        # raise the 75-and-over ratio.
        and all(
            math.isclose(float(spread[b]), float(left_out[b]), rel_tol=1e-6) for b in spread.index
        )
        and float(working.ratio_to_reference) > published("deaths_per_bn_km", "75+")
        # The kilometre denominator in the contrast is the published end of the range.
        and math.isclose(float(km_75.ratio), published("deaths_per_bn_km", "75+"), rel_tol=1e-6)
        # The denominator steps: fewer licence holders at 75 and over than in either census band
        # of the reference, shorter distances, and each ratio larger than the one before.
        and all(
            float(latest_licence.loc[("75+", "total"), "licence_share"])
            < float(latest_licence.loc[(b, "total"), "licence_share"])
            for b in reference_bands
        )
        and float(residents_75.ratio) < float(permit_75.ratio) < float(km_75.ratio)
    ):
        raise ValueError("drivers page: the age tables no longer read as described")

    body = summary(
        f"In {year}, car drivers aged 75 and over who were involved in an injury crash were "
        f"killed {ratio_text('deaths_per_1000_involved', '75+')} as often as drivers aged 35 to "
        "54, and the share of drivers killed rose with every age band after 35–54. Per "
        "kilometre, with kilometres known only by the age of the car's owner, drivers aged 75 "
        "and over were killed "
        f"{km_range('deaths_per_bn_km', '75+')} as often as drivers aged 35 to 54, and drivers "
        "aged 18 to 34 were involved in injury crashes "
        f"{km_range('involved_per_bn_km', '18-34')} as often. Per licence holder, men died at "
        f"the wheel of a car {_times(float(men_killed.ratio))} as often as women in {sex_years}."
    )

    def licence_share(band: str) -> str:
        return _fmt_pct(float(latest_licence.loc[(band, "total"), "licence_share"]))

    body += "<h2>The same deaths under four denominators</h2>"
    body += (
        "<p>A death rate depends on what it is divided by. Against drivers aged 35 to 54, car "
        f"drivers aged 75 and over died {_times(float(residents_75.ratio))} as often per "
        f"resident, {_times(float(permit_75.ratio))} per holder of a B permit (the ordinary car "
        f"licence), {_times(float(km_75.ratio))} per kilometre (on DGT's published "
        "kilometres, which follow the age of the car's owner) and "
        f"{_times(float(involved_75.ratio))} per driver involved in an injury crash. The deaths "
        "are the same in each case; only the denominator changes, and with it the meaning of "
        "the ratio. Per resident, the ratio combines how many people of that age hold a car "
        "licence, how far they drive, how often they crash for the distance driven and how "
        "often a crash kills them. Each further denominator removes one of these steps: per "
        "B-permit holder, licence holding; per kilometre, distance; per driver involved, crash "
        "frequency, which leaves severity alone.</p>"
    )
    body += figure(
        "a2_denominator_contrast",
        f"Car-driver deaths in {year} by age band, as ratios to drivers aged 35–54, divided in "
        "turn by residents, B-permit holders, drivers involved in injury crashes and kilometres "
        "of cars registered to owners of each age",
        captions,
    )
    body += (
        "<p>Read in that order, the ratios show where the difference between the age groups "
        f"lies. The step from {_times(float(residents_75.ratio))} to "
        f"{_times(float(permit_75.ratio))} is licence holding: in {year_licence}, "
        f"{licence_share('75+')} of residents aged 75 and over held a driving licence of any "
        f"type ({_fmt_pct(float(oldest.b_permit_share))} of them a B permit), against "
        f"{licence_share('35-44')} at {_band('35-44')} and {licence_share('45-54')} at "
        f"{_band('45-54')}, the two bands that make up the reference. The step to {_times(float(km_75.ratio))} is distance: B-permit "
        f"holders aged 75 and over have {float(oldest.km_per_b_permit):,.0f} km a year "
        f"registered to them, against {float(base.km_per_b_permit):,.0f} km at 35–54. The last "
        f"step, to {_times(float(involved_75.ratio))}, changes little, because drivers aged 75 "
        "and over are involved in about as many injury crashes per kilometre as drivers aged 35 "
        "to 54.</p>"
    )

    body += "<h2>Deaths per driver involved</h2>"
    body += (
        "<p>Deaths per driver involved count, among car drivers already in an injury crash, "
        "those who died within 30 days. Numerator and denominator come from the same DGT "
        "tables, by the same age bands, so the measure needs no estimate of how much anyone "
        f"drives. Of every 1,000 drivers aged 35 to 54 involved in an injury crash in {year}, "
        f"{float(rates.loc[reference, 'deaths_per_1000_involved']):.1f} died; among drivers "
        f"aged 75 and over the figure was "
        f"{float(rates.loc['75+', 'deaths_per_1000_involved']):.1f}. Drivers aged 18 to 34 "
        f"are at {ratio_text('deaths_per_1000_involved', '18-34')} the reference rate, an "
        "interval that includes no difference. The measure counts only the driver's own death: the tables do "
        "not say how often the other people in those crashes died.</p>"
    )

    body += "<h2>Kilometres by the owner's age</h2>"
    body += (
        "<p>Crash frequency needs kilometres by the driver's age, and none of the sources "
        f"gives them. The nearest are DGT's estimates for {year}, modelled from odometer "
        "readings taken at roadworthiness inspections and published by the age band of each "
        "car's registered owner. Rates per kilometre therefore divide the drivers of each band "
        f"by the {OWNER_KM}, and a car's owner is not always its driver. Counted per B-permit "
        "holder, the published figures show where owner and driver diverge: the 18–34 band "
        f"has {float(young.cars_per_b_permit):.2f} "
        f"cars registered to it and {float(young.km_per_b_permit):,.0f} km a year, against "
        f"{float(base.cars_per_b_permit):.2f} cars and {float(base.km_per_b_permit):,.0f} km at "
        "35–54. Either young licence holders drive less, or part of their driving is in cars "
        "registered to older owners; the data do not distinguish the two. The band aged 75 and "
        f"over has {float(oldest.cars_per_b_permit):.2f} cars per B-permit holder, more cars than "
        "people of that age licensed to drive them: either some of those cars are driven by "
        "others, or some owners have more than one.</p>"
    )
    body += (
        "<p>A reallocation scenario puts a size on the gap at 18–34. It moves kilometres from the "
        "35–54 band to the 18–34 band until both have the same distance per B-permit holder, as "
        "if the whole difference were young people driving cars registered to owners aged 35 "
        f"to 54. That is {shortfall:.1f} billion km, "
        f"{_fmt_pct(shortfall / float(base.billion_km))} of the 35–54 kilometres. "
        "Which older band, if any, holds young people's driving is unknown. Under the "
        "scenario, involvement per kilometre at 18–34 falls "
        f"from {_times(published('involved_per_bn_km', '18-34'))} to "
        f"{_times(reallocated('involved_per_bn_km', '18-34'))} the 35–54 rate. Taking "
        "kilometres out of the reference band also raises its rates, so every other band's "
        "ratio falls as well: at 75 and over, deaths per kilometre go from "
        f"{_times(published('deaths_per_bn_km', '75+'))} to "
        f"{_times(reallocated('deaths_per_bn_km', '75+'))} the 35–54 rate. Each per-kilometre "
        "ratio is therefore given as a range, from the reallocation scenario to the published "
        "figure.</p>"
    )
    body += (
        "<p>At 75 and over any error runs the other way: if some of the cars registered to "
        "owners of that age are driven by younger people, the band's published rates per "
        "kilometre are too low, by an amount the data do not give.</p>"
    )
    company_share = float(km.loc[driver_risk.COMPANY_BAND, "share_of_km"])
    body += technical(
        "Company cars and the choice of reference band",
        f"<p>Cars registered to companies, {_fmt_pct(company_share)} of car kilometres, have "
        "no owner age: their kilometres drop out of the denominator while their drivers stay in "
        "the numerator. Spreading those kilometres over every band in proportion changes no "
        "ratio; spreading them over the bands from 18 to 64 raises the ratio of deaths per "
        f"kilometre at 75 and over from {_times(published('deaths_per_bn_km', '75+'))} to "
        f"{_times(float(working.ratio_to_reference))}. Neither allocation affects deaths per "
        "driver involved.</p>"
        "<p>Cars per B-permit holder are close to one at 55–64 "
        f"({float(owner.loc['55-64', 'cars_per_b_permit']):.2f}) and 65–74 "
        f"({float(owner.loc['65-74', 'cars_per_b_permit']):.2f}). That does not show that "
        "owners in those bands drive their own cars, so no band offers a reference in which "
        "owner and driver are known to coincide, and 35–54 stays the reference.</p>",
    )

    body += "<h2>Crash frequency and severity by age</h2>"
    body += (
        "<p>A death rate per kilometre is the product of how often drivers are involved in an "
        "injury crash for the distance they drive (crash frequency) and how often such a crash "
        "kills the driver (severity). A group can have a high death rate per kilometre because "
        "it crashes often, because its crashes more often kill the driver, or both.</p>"
    )
    body += _ratio_table(ratios, owner, rates, year)
    middle_text = _join([f"{km_range('involved_per_bn_km', b)} at {label[b]}" for b in middle])
    body += (
        "<p>Against drivers aged 35 to 54, involvement per kilometre is lower at 55–64 and "
        f"65–74 at both ends of the range: {middle_text}. The reallocation scenario moves "
        "neither the 65–74 nor the 75-and-over kilometres, so those two bands can be compared "
        "in a single ratio. Per kilometre, drivers aged 75 and "
        "over were involved in injury crashes "
        f"{ratio_text('involved_per_bn_km', '75+', older)} as often as drivers aged 65 to 74 "
        f"and killed {ratio_text('deaths_per_bn_km', '75+', older)} as often; per driver "
        f"involved they were killed {ratio_text('deaths_per_1000_involved', '75+', older)} as "
        "often.</p>"
    )
    body += figure(
        "a1_km_risk_by_age",
        f"Three panels for car drivers by age band in {year}: drivers involved in injury crashes "
        "per billion kilometres, drivers killed per 1,000 involved, and drivers killed per "
        "billion kilometres, the kilometres being those of cars registered to owners of each age",
        captions,
    )
    body += technical(
        "Counts, kilometres and rates by age band",
        _rates_table(rates, year),
    )

    body += sex_section

    body += "<h2>Frequency at young ages, severity at old ages</h2>"
    body += conclusion(
        "Crash frequency and severity separate the youngest and the oldest drivers from the "
        "middle-aged in different ways. Against drivers aged 35 to 54, drivers aged 18 to 34 "
        "crash more often for the distance they drive and are killed no more often once "
        "involved: their higher death rate per kilometre lies in frequency. Drivers aged 75 and "
        "over crash about as often per kilometre and are killed far more often once involved: "
        "their higher death rate lies in severity. Against drivers aged 65 to 74, whose "
        "kilometres the reallocation leaves untouched, they are higher on both. The two results "
        "also rest on different evidence. The young drivers' excess depends on kilometres "
        "recorded by the owner's age, and holds at both ends of the range. The oldest drivers' excess lies mostly in deaths per driver involved, "
        "which need no kilometres at all. Men differ from women on both counts, and the larger "
        "gap is in deaths per driver involved."
    )

    body += limitation(
        "The kilometre estimates are valid only in aggregate, and the intervals reflect the crash "
        "counts alone, treating the kilometres as known. The crash counts include "
        "foreign-registered cars and unlicensed drivers, while the kilometres cover "
        "Spanish-registered cars only. Drivers whose age or sex the tables do not record are left "
        "out."
    )
    body += downloads(
        [
            ("q7_km_rates", "rates by age band"),
            ("q7_km_ratio", "ratios to drivers aged 35–54"),
            ("q7_km_ratio_65_74", "ratios to drivers aged 65–74"),
            ("q7_owner_age_check", "owner-age check and reallocation scenario"),
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
        "Car drivers in Spain compared by age and by sex, with each group's death rate divided "
        "into how often it crashes and how often a crash kills the driver.",
        body,
    )
