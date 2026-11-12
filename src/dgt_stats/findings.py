"""The study's conclusions in one short document, ``docs/FINDINGS.md``.

For each research question the document gives the answer, the evidence, how strong it is and the
main limit. Every number is formatted from the committed result tables with the helpers and
facts of the site's pages (``dgt_stats.site``), so the document and the site cannot disagree,
and every qualitative claim is checked against the tables first: if a table no longer supports a
sentence, :func:`render` raises instead of writing it. ``scripts/build_site.py`` writes the
document after the pages, and a test holds the committed file to the build.

Strength labels: *Strong* (counted, or an interval far from no effect, and robust to the checks
run), *Moderate* (clear on the central assumptions, open to a stated alternative), *Weak*
(suggestive), *Not established* (the data cannot tell).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from dgt_stats.exposure_risk import national as national_rates
from dgt_stats.paths import PROJECT_ROOT
from dgt_stats.site import (
    drivers,
    factors,
    long_run,
    models,
    policy,
    regional,
    seasons,
    severity,
    vehicles,
)
from dgt_stats.site.components import _fmt_int, _fmt_pct, _join, read_table
from dgt_stats.site.numbers import per_km_ratio

DOCUMENT = PROJECT_ROOT / "docs" / "FINDINGS.md"
SITE_URL = "https://rahv-fb.github.io/dgt-stats"
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September")


def _require(section: str, checks: dict[str, bool]) -> None:
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"findings ({section}): the tables no longer support: {failed}")


def _times(value: float, decimals: int = 1) -> str:
    return f"{float(value):.{decimals}f}"


def _ci(low: float, high: float, decimals: int = 1) -> str:
    return f"{float(low):.{decimals}f}–{float(high):.{decimals}f}"


def _pct_ci(low: float, high: float, decimals: int = 1) -> str:
    return f"{_fmt_pct(low, decimals)} to {_fmt_pct(high, decimals)}"


def _dash(text: object) -> str:
    return str(text).replace("-", "–")


def _signed(value: float, decimals: int = 1) -> str:
    return f"{value * 100:+.{decimals}f}%".replace("-", "−")


def _claim(strength: str, text: str) -> str:
    return f"- **{strength}.** {text}"


def _section(number: int, question: str, answer: str, claims: list[str], limit: str) -> list[str]:
    return [
        f"## {number}. {question}",
        "",
        answer,
        "",
        *claims,
        "",
        f"Main limit: {limit}",
        "",
    ]


# ----------------------------------------------------------------------------- 1. long run
def _long_run() -> list[str]:
    f = long_run._facts()
    deaths = f.panel.deaths_30d
    first, end, last = int(f.first), int(f.steep.end), int(f.last)
    fall = 1 - float(deaths.loc[end]) / float(deaths.loc[first])
    per_tonne_fall = 1 - float(f.per_fuel)
    crash_gain = 1 - float(f.frequency)
    count_ratio = f.deaths.loc["count"]
    fuel_years = list(f.recent)
    later = {int(year): row for year, row in zip(f.recent, f.fuel_later)}
    km = f.km_row
    alone, hosp_fuel = f.count_alone, f.hosp.loc["road_fuel"]
    _require(
        "long run",
        {
            "the count's last segment refitted alone has no clear trend": float(
                alone.annual_change_low
            )
            < 0
            < float(alone.annual_change_high),
            "admissions per tonne of fuel are above ordinary year-to-year variation": float(
                hosp_fuel.ratio_to_base
            )
            > 1
            and float(hosp_fuel.ratio_low_yty) > 1,
            "deaths fell by about three quarters to the end of the steep fall": 0.7 < fall < 0.8,
            "the steepest fall is the fall to the last segment": int(f.steep.end)
            == int(f.flat.start),
            "the last segment has no clear trend": float(f.flat.low) < 0 < float(f.flat.high),
            "per tonne of fuel, deaths fell by more than half": per_tonne_fall > 0.5,
            "per injury crash the fall is mostly severity": float(f.severity)
            < float(f.frequency)
            < 1,
            "per admission the fall is all frequency": float(f.admitted) < float(f.per_fuel)
            and float(f.per_admission) > 1,
            "per fuel is above the 2011-based trend in the last two years, outside its range": all(
                bool(f.fuel[year].outside_interval) and float(f.fuel[year].ratio) > 1
                for year in fuel_years
            ),
            "per fuel is inside the range of a trend started at the last turning point": not bool(
                later[last].outside_interval
            )
            and float(later[last].ratio) > 1,
            "per measured km is inside its trend range": not bool(km.outside_interval),
            "the count in the last year is within an ordinary year's variation of 2019": float(
                count_ratio.ratio_low_yty
            )
            <= 1
            <= float(count_ratio.ratio_high_yty),
        },
    )
    claims = [
        _claim(
            "Strong",
            f"Deaths within 30 days fell by about three quarters between {first} and {end}, "
            f"from {_fmt_int(deaths.loc[first])} to {_fmt_int(deaths.loc[end])}. The steepest "
            f"fall was {f.steep.start}–{end}, {_signed(f.steep.annual_change)} a year "
            f"(95% interval {_signed(f.steep.low)} to {_signed(f.steep.high)}).",
        ),
        _claim(
            "Strong",
            f"There is no clear trend after {end}: fitted alone, the change for {f.flat.start}–"
            f"{f.flat.end} is {_signed(alone.annual_change)} a year "
            f"({_signed(alone.annual_change_low)} to {_signed(alone.annual_change_high)}), and "
            f"{last} had {_fmt_int(deaths.loc[last])} deaths.",
        ),
        _claim(
            "Moderate",
            f"Deaths per tonne of road fuel sold fell by {_fmt_pct(per_tonne_fall, 0)} between "
            f"{f.split_first} and {f.split_last}. Whether crashes became rarer or less deadly "
            "depends on the denominator: per injury crash the fall is mostly in deaths per "
            f"crash (crashes per tonne fell {_fmt_pct(crash_gain, 0)}); per person admitted to "
            f"hospital, admissions per tonne fell to {_fmt_pct(f.admitted, 0)} while deaths per "
            "admission did not fall.",
        ),
        _claim(
            "Not established",
            f"A post-pandemic rise in risk. Per tonne of fuel, {fuel_years[0]} and {fuel_years[1]} "
            f"are {_fmt_pct(f.fuel[fuel_years[0]].ratio - 1, 0)} and "
            f"{_fmt_pct(f.fuel[fuel_years[1]].ratio - 1, 0)} above the trend of "
            f"{f.fuel_start}–{f.fit_end}, outside its range, but {_fmt_pct(later[last].ratio - 1, 0)} "
            f"above a trend started in {f.plateau_start} and inside its range. Deaths per "
            f"measured interurban kilometre in {f.km_last} are {_fmt_pct(km.ratio - 1, 0)} above "
            "trend, inside its range.",
        ),
        _claim(
            "Weak",
            f"Hospital admissions per tonne of road fuel in {last} are "
            f"{_fmt_pct(hosp_fuel.ratio_to_base - 1, 0)} above {f.base_year}, beyond ordinary "
            f"year-to-year variation (interval {_signed(hosp_fuel.ratio_low_yty - 1)} to "
            f"{_signed(hosp_fuel.ratio_high_yty - 1)}). This depends on how completely "
            "admissions are recorded, and fuel sold is not kilometres driven.",
        ),
        _claim(
            "Not established",
            f"A change since {f.base_year}. Deaths in {last} are "
            f"{_fmt_pct(count_ratio.ratio_to_base - 1, 1)} above {f.base_year}, within the "
            f"variation between ordinary years ({_ci(count_ratio.ratio_low_yty, count_ratio.ratio_high_yty, 2)} "
            "as a ratio).",
        ),
    ]
    return _section(
        1,
        "How have road deaths changed since 1993?",
        "Deaths fell steeply to 2013 and have not clearly changed since.",
        claims,
        "traffic is measured by fuel sold and, from 2008, by kilometres on the measured "
        "interurban roads; neither measures all travel.",
    )


# ----------------------------------------------------------------------------- 2. road classes
def _road_classes() -> list[str]:
    f = long_run._facts()
    ratios = f.road_years
    first, last = int(ratios.index.min()), int(ratios.index.max())
    _require(
        "road classes",
        {
            "conventional roads have three to four times the deaths per km of motorways in "
            "every year": 3 <= float(ratios.min()) and float(ratios.max()) < 4.5,
            "the last year's interval excludes equal rates": float(f.road_low) > 1,
        },
    )
    claims = [
        _claim(
            "Strong",
            f"Per measured kilometre, deaths on conventional interurban roads were "
            f"{_times(ratios.min(), 2)} to {_times(ratios.max(), 2)} times those on motorways "
            f"in each year of {first}–{last}; in {f.road_year}, {_times(f.road_deaths, 2)} times "
            f"(95% interval {_ci(f.road_low, f.road_high, 2)}).",
        ),
    ]
    return _section(
        2,
        "Which roads are deadliest per kilometre?",
        "Conventional roads, single and dual carriageway, much more than motorways.",
        claims,
        "the measured network covers the state and regional interurban roads only, so urban "
        "streets and local roads are not compared.",
    )


# ----------------------------------------------------------------------------- seasons
def _seasons() -> list[str]:
    f = seasons._facts()
    july, august = f.july_fuel, f.august_fuel
    _require(
        "seasons",
        {
            "July to September deaths exceed the average month per tonne of fuel": f.above
            == [7, 8, 9],
            "the lockdown fall in deaths exceeds the fall in road fuel": abs(f.deaths_fall)
            > abs(f.fuel_fall),
        },
    )
    claims = [
        _claim(
            "Moderate",
            f"Deaths in {_join([MONTHS[m - 1] for m in f.above])} exceed the average month even "
            f"per tonne of road fuel sold: {MONTHS[6]} {_times(july.rate_ratio, 2)} times "
            f"(95% interval {_ci(july.low, july.high, 2)}), {MONTHS[7]} "
            f"{_times(august.rate_ratio, 2)} ({_ci(august.low, august.high, 2)}).",
        ),
        _claim(
            "Moderate",
            f"In April {f.lockdown_year}, deaths fell {_fmt_pct(-f.deaths_fall, 0)} against the "
            f"{f.baseline} average for the month and road fuel sold fell "
            f"{_fmt_pct(-f.fuel_fall, 0)}.",
        ),
    ]
    return _section(
        3,
        "When in the year are deaths highest?",
        "In summer, and not only because more fuel is sold then.",
        claims,
        "road fuel sold is the only traffic series available by month, so whether summer is "
        "riskier per kilometre driven cannot be told.",
    )


# ----------------------------------------------------------------------------- 3. policy
def _policy() -> list[str]:
    f = policy._facts()
    main, cal, calibration = f.main, f.true_calendar, f.calibration
    linear, straight = f.linear, f.straight
    _require(
        "points licence",
        {
            "the straight-line trend gives a larger step than the preferred one": float(
                linear.level_change
            )
            < float(main.level_change)
            < 0,
            "the straight-line trend gives a lasting fall": float(linear.mean_high) < 0,
            "the straight-line trend fits the earlier months worse by between 4 and 10 QAIC": 4
            < float(straight.delta_qaic)
            < 10,
            "the placebos and the calibration are for the straight-line step": abs(
                float(cal.level_change) - float(calibration.level_change)
            )
            < 1e-9,
            "the model finds a step down at July 2006": float(main.level_high) < 0,
            "July 2006 has the largest step of the placebo Julys": int(cal["rank"]) == 1,
            "several placebo Julys also exclude zero": int(calibration.n_excluding_zero) >= 3,
            "the calibrated interval includes no change": float(calibration.calibrated_low)
            < 0
            < float(calibration.calibrated_high),
        },
    )
    claims = [
        _claim(
            "Weak",
            f"Under the preferred trend, which bends once, the model puts a step at "
            f"{f.break_month} at {_signed(main.level_change)} "
            f"(95% interval {_signed(main.level_low)} to {_signed(main.level_high)}); averaged "
            f"over the {main.post_months} months from it the change is "
            f"{_signed(main.mean_change)} ({_signed(main.mean_low)} to {_signed(main.mean_high)}).",
        ),
        _claim(
            "Weak",
            f"A straight-line trend gives a larger step, {_signed(linear.level_change, 0)}, and a "
            f"lasting fall, {_signed(linear.mean_change)} on average ({_signed(linear.mean_low)} "
            f"to {_signed(linear.mean_high)}), but fits the earlier months worse, by about "
            f"{float(straight.delta_qaic):.0f} points of QAIC.",
        ),
        _claim(
            "Not established",
            f"That the licence caused the fall. The placebo count and the recalibrated interval "
            f"are for the straight-line specification, whose July {f.it.date.year} step is "
            f"{_signed(cal.level_change)}: {int(calibration.n_excluding_zero)} of "
            f"{int(calibration.n_placebos)} placebo Julys with no policy change also have an "
            "interval that excludes zero, so the model's intervals are too narrow; the interval "
            f"recalibrated on the placebos runs from {_signed(calibration.calibrated_low)} to "
            f"{_signed(calibration.calibrated_high)}, which includes no change.",
        ),
    ]
    return _section(
        4,
        "Did the 2006 points licence cut deaths?",
        "Deaths fell around its introduction, but the series cannot show that the licence caused "
        "the fall or that it lasted.",
        claims,
        "one national monthly series, a long downward trend and no comparison group.",
    )


# ----------------------------------------------------------------------------- 4. drivers
def _drivers() -> list[str]:
    f = drivers._facts()
    numbers = f.numbers
    oldest = f.severity.loc["75+"]
    young = per_km_ratio(numbers, "18-29")
    middle = per_km_ratio(numbers, "30-44")
    ranges = numbers["involved_ranges"]
    older = f.older.loc["65-74"]
    b_licence = (
        read_table("drivers_sex_b_licence").set_index("denominator").loc["B-licence holders"]
    )
    per_km = read_table("risk_sex_per_km").set_index("measure")
    involved_sex, killed_sex = per_km.loc["involved per km"], per_km.loc["killed per km"]
    _require(
        "drivers",
        {
            "drivers aged 75 and over die clearly more often once involved": float(
                oldest.killed_ratio_low
            )
            > 2,
            "drivers aged 75 and over have the highest ratio of deaths once involved": float(
                oldest.killed_ratio_to_45_64
            )
            == float(f.severity.killed_ratio_to_45_64.max()),
            "drivers aged 18-29 are involved clearly more often per km on every assumption": float(
                ranges.loc["18-29", "range_min"]
            )
            > 1,
            "drivers aged 30-44 are above 45-64 on every assumption": float(
                ranges.loc["30-44", "range_min"]
            )
            > 1,
            "65-74 cannot be told apart from 45-64": float(older.ratio_low)
            <= 1
            <= float(older.ratio_high)
            and float(ranges.loc["65-74", "range_min"])
            < 1
            < float(ranges.loc["65-74", "range_max"]),
            "75 and over: the range includes no difference": float(ranges.loc["75+", "range_min"])
            < 1,
            "men die clearly more often per B-licence holder": float(b_licence.low) > 1,
            "per km men are not shown to be involved more often": float(involved_sex.range_low)
            < 1
            < float(involved_sex.range_high),
            "per km men are killed clearly more often on every assumption": float(
                killed_sex.range_low
            )
            > 1,
        },
    )
    claims = [
        _claim(
            "Strong",
            f"Once in an injury crash, car drivers aged 75 and over died "
            f"{_times(oldest.killed_ratio_to_45_64)} times as often as drivers aged 45–64 in "
            f"{national_rates.YEAR} "
            f"(95% interval {_ci(oldest.killed_ratio_low, oldest.killed_ratio_high)}). This is "
            "counted, not estimated.",
        ),
        _claim(
            "Moderate",
            f"Per kilometre driven, drivers aged 18–29 were involved in injury crashes about "
            f"{young['ratio']} times as often as drivers aged 45–64 (sampling interval "
            f"{young['interval']}; range across assumptions {young['range']}). Drivers aged "
            f"30–44 were modestly above (about {middle['ratio']} times; range {middle['range']}).",
        ),
        _claim(
            "Not established",
            f"Drivers aged 65–74 cannot be told apart from 45–64 per kilometre (about "
            f"{per_km_ratio(numbers, '65-74')['ratio']} times; range "
            f"{per_km_ratio(numbers, '65-74')['range']}), and the result for 75 and over "
            f"(range {per_km_ratio(numbers, '75+')['range']}) rests on a split of the survey's "
            "65-and-over group that the data cannot check.",
        ),
        _claim(
            "Strong",
            f"Men were killed {_times(b_licence.ratio)} times as often as women per B-licence "
            f"holder ({_dash(b_licence.years)}; 95% interval {_ci(b_licence.low, b_licence.high)}).",
        ),
        _claim(
            "Moderate",
            f"Per kilometre, men are not shown to be involved in injury crashes more often "
            f"({_times(involved_sex.ratio_men_to_women, 2)} times women's; range "
            f"{_ci(involved_sex.range_low, involved_sex.range_high, 2)}), but are killed "
            f"{_times(killed_sex.ratio_men_to_women)} times as often (range "
            f"{_ci(killed_sex.range_low, killed_sex.range_high)}).",
        ),
    ]
    return _section(
        5,
        "Which drivers are at higher risk?",
        "Older drivers are the most likely to die once in a crash. Per kilometre, drivers aged "
        "18–29 are clearly more often in one than drivers aged 45–64; the comparison with "
        "drivers aged 75 and over is not established.",
        claims,
        "no national source counts kilometres by the driver's age, so the kilometres are "
        "estimated from regional surveys (the EMEF in the Barcelona area and Madrid's 2018 "
        "survey) and the per-kilometre results rest on them.",
    )


# ----------------------------------------------------------------------------- 5. vehicles
def _vehicles() -> list[str]:
    f = vehicles._facts()
    bike = f.intervals.loc[("fatal_involvement", "motorcycle")]
    car = f.intervals.loc[("fatal_involvement", "car")]
    _require(
        "vehicles",
        {
            "motorcycles lead per kilometre by far": f.bike_per_km > 5
            and float(bike.per_billion_km_low) > float(car.per_billion_km_high),
            "heavy trucks are in fewer injury crashes per km but more of them are fatal": (
                f.truck_crashes < 1 and f.truck_fatal_share > 2
            ),
            "most deaths in heavy-truck fatal crashes are outside the truck": f.truck_occupants
            < 0.5,
        },
    )
    claims = [
        _claim(
            "Strong",
            f"Per kilometre in {f.year}, motorcycles were in fatal crashes "
            f"{_times(f.bike_per_km)} times as often as cars ({_ci(bike.per_billion_km_low, bike.per_billion_km_high)} "
            f"against {_ci(car.per_billion_km_low, car.per_billion_km_high)} per billion km, "
            "95% intervals; the intervals cover the crash counts only, and the rate rests on DGT's "
            "modelled kilometres), mostly because they are in more crashes.",
        ),
        _claim(
            "Moderate",
            f"Heavy trucks are in fewer injury crashes per kilometre than cars "
            f"({_times(f.truck_crashes, 2)} times), but the share that are fatal is "
            f"{_times(f.truck_fatal_share)} times a car's. Deaths per vehicle in a fatal crash "
            f"average {_times(f.truck_occupants, 2)} for a truck's own occupants, so most of "
            "those killed were outside the truck.",
        ),
    ]
    return _section(
        6,
        "Which vehicles are in the most fatal crashes?",
        "Per kilometre, motorcycles; per vehicle on the road, buses and heavy trucks.",
        claims,
        "the kilometres are DGT's modelled estimates for one year, valid for groups of "
        "vehicles, and the intervals cover the crash counts only.",
    )


# ----------------------------------------------------------------------------- 6. factors
def _factors() -> list[str]:
    f = factors._facts()
    pooled = read_table("speed_severity_pooled").set_index("road_type")
    adjusted = pooled.loc["adjusted"]
    types = pooled.drop(index="adjusted")
    low, high = types.loc[types.rate_ratio.idxmin()], types.loc[types.rate_ratio.idxmax()]
    _require(
        "factors",
        {
            "every road type has more deaths per crash where speed is recorded": bool(
                (types.ratio_low > 1).all()
            ),
            "the adjusted ratio lies between the road types'": float(low.rate_ratio)
            < float(adjusted.rate_ratio)
            < float(high.rate_ratio),
            "the interurban speed share is flat to 2020, then lower": f.flat_to == 2020
            and abs(f.inter_flat) < 0.05
            and f.inter_late_fall < -0.2,
            "the all-roads share fell, and by more than the same mix of crashes would give": (
                float(f.speed_all.share_last) < float(f.speed_all.share_first)
                and f.speed_all_fall > f.speed_same_mix_fall > 0
            ),
        },
    )
    claims = [
        _claim(
            "Moderate",
            f"Crashes in which the police recorded inappropriate speed had "
            f"{_times(adjusted.rate_ratio)} times the deaths per crash of other crashes on the "
            f"same kind of road ({_dash(adjusted.year)}; 95% interval {_ci(adjusted.ratio_low, adjusted.ratio_high)}), "
            f"from {_times(low.rate_ratio)} times on {low.road_type_label.lower()} to "
            f"{_times(high.rate_ratio)} times on {high.road_type_label.lower()}.",
        ),
        _claim(
            "Weak",
            f"On interurban roads the share of crashes with inappropriate speed recorded was flat "
            f"to {f.flat_to} ({_fmt_pct(f.inter_series.loc[f.first])} in {f.first}, "
            f"{_fmt_pct(f.inter_series.loc[f.flat_to])} in {f.flat_to}) and fell to "
            f"{_fmt_pct(f.inter_series.loc[f.fall_to])} in {f.fall_to}. On all roads it fell "
            f"from {_fmt_pct(f.speed_all.share_first)} in {f.speed_all.first_year} to "
            f"{_fmt_pct(f.speed_all.share_last)} in {f.speed_all.last_year}, partly because "
            "crashes shifted to urban streets, where speed is rarely recorded. A change in "
            "recording practice is not excluded, so the series is not read as a change in "
            "behaviour.",
        ),
    ]
    return _section(
        7,
        "How do speed and the other recorded factors relate to deaths?",
        "Crashes recorded with inappropriate speed are deadlier.",
        claims,
        "the factor is the police's judgement, recorded more or less often over time and by "
        "place, so the association is open to recording bias; the report excludes Catalonia "
        "and the Basque Country.",
    )


# ----------------------------------------------------------------------------- 7. circumstances
def _circumstances() -> list[str]:
    f = severity._facts()
    place = f.strongest_location
    _require(
        "circumstances",
        {
            "a pedestrian struck raises the odds of a death clearly": float(f.pedestrian.or_low)
            > 1,
            "a head-on collision raises the odds of a death clearly": float(f.head_on.or_low) > 1,
            "interurban and urban-crossing locations raise the odds against urban streets": float(
                place.or_low
            )
            > 1,
        },
    )
    claims = [
        _claim(
            "Moderate",
            f"Crash type and place dominate whether an injury crash is fatal. Against the "
            f"reference crash, a pedestrian struck has odds {_times(f.pedestrian.odds_ratio)} "
            f"times as high (95% interval {_ci(f.pedestrian.or_low, f.pedestrian.or_high)}), a "
            f"head-on collision {_times(f.head_on.odds_ratio)} ({_ci(f.head_on.or_low, f.head_on.or_high)}). "
            f"By place, the highest contrast with an urban street is an {place.zone} on a "
            f"{place.road} road, {_times(place.odds_ratio)} ({_ci(place.or_low, place.or_high)}).",
        ),
    ]
    return _section(
        8,
        "What goes with a death in Spain's injury crashes?",
        "The kind of crash and where it happens, much more than the weather or the light.",
        claims,
        "the records hold only crashes with victims and the circumstances the police code, so "
        "the odds ratios are associations conditional on a crash, with recording that differs "
        "by region.",
    )


# ----------------------------------------------------------------------------- 8. Catalonia
def _catalonia() -> list[str]:
    c = regional._catalonia_facts()
    m = models._facts()
    heavy_ratio = m.heavy
    gap = m.gap
    through_model = float(m.zone["through_town"].roc_auc)
    through_table = float(m.zone_table["through_town"].roc_auc)
    pooled = m.pooled
    _require(
        "Catalonia",
        {
            "the fatal share is higher with a heavy vehicle than on average": float(c.heavy.share)
            > float(c.overall.events) / float(c.overall.n),
            "the model's heavy-vehicle ratio is clearly above 1": float(heavy_ratio.ratio_low) > 1,
            "interurban roads have a higher fatal share than urban streets": float(
                c.interurban.share
            )
            > float(c.urban.share),
            "the Catalan fatal crashes equal DGT's in every province-year": c.equal_fatal_24h
            == len(c.dgt),
            "the model ranks better than the road-by-crash-type table": float(gap.high) < 0,
            "on roads through towns the model ranks no better than the table": through_model
            <= through_table,
        },
    )
    claims = [
        _claim(
            "Strong",
            f"Of {_fmt_int(c.overall.n)} crashes with a death or serious injury in Catalonia "
            f"({c.period}), {_fmt_pct(c.overall.events / c.overall.n)} were fatal. The fatal "
            f"share was {_fmt_pct(c.interurban.share)} on interurban roads and "
            f"{_fmt_pct(c.urban.share)} on urban streets, and {_fmt_pct(c.heavy.share)} with a "
            "heavy vehicle involved.",
        ),
        _claim(
            "Moderate",
            f"With the other recorded circumstances held equal, the model puts the fatal share "
            f"{_times(heavy_ratio.ratio)} times as high with a heavy vehicle involved "
            f"(95% interval {_ci(heavy_ratio.ratio_low, heavy_ratio.ratio_high)}). The interval "
            "covers coefficient uncertainty only, and the model was tested only within "
            "Catalonia.",
        ),
        _claim(
            "Strong",
            f"The Catalan file's fatal crashes equal DGT's crashes with a death within 24 hours "
            f"in all {len(c.dgt)} province-years of {c.overlap}.",
        ),
        _claim(
            "Moderate",
            f"On the crashes of {_dash(m.span)}, each predicted from earlier years, the model ranks "
            f"fatal crashes better than a table of fatal shares by road and crash type "
            f"(ROC-AUC {_times(pooled.loc['model'].roc_auc, 2)} against "
            f"{_times(pooled.loc['road_x_crash_table'].roc_auc, 2)}), but not on roads through "
            f"towns ({_times(through_model, 2)} against {_times(through_table, 2)}).",
        ),
    ]
    return _section(
        9,
        "Which severe crashes in Catalonia were fatal?",
        "Those on interurban roads, involving heavy vehicles and in head-on collisions.",
        claims,
        "the model was tested only within Catalonia; its inputs are recorded in no other "
        "source, and a fatal crash there means a death within 24 hours.",
    )


# ----------------------------------------------------------------------------- 9. Barcelona
def _barcelona() -> list[str]:
    b = regional._barcelona_facts()
    ages = b.ages[~b.ages.small_n.astype(bool)]
    _require(
        "Barcelona",
        {
            "pedestrians are far more often seriously hurt or killed than car drivers": float(
                b.pedestrian.ci_low
            )
            > float(b.car_driver.ci_high),
            "motorcyclists are far more often seriously hurt or killed than car drivers": float(
                b.motorcycle.ci_low
            )
            > float(b.car_driver.ci_high),
            "people aged 75 and over are the age group with the highest share": float(
                b.oldest.share
            )
            == float(ages.share.max()),
        },
    )
    claims = [
        _claim(
            "Strong",
            f"Of {_fmt_int(b.labelled)} people with a recorded outcome in {b.year}, "
            f"{_fmt_pct(b.severe_people / b.labelled)} were seriously injured or killed. "
            f"Pedestrians ({_fmt_pct(b.pedestrian.share)}) and motorcyclists "
            f"({_fmt_pct(b.motorcycle.share)}) were far more often so than car drivers "
            f"({_fmt_int(b.car_driver.events)} of {_fmt_int(b.car_driver.n)}, "
            f"{_fmt_pct(b.car_driver.share, 2)}).",
        ),
        _claim(
            "Moderate",
            f"People aged 75 and over had the highest share by age ({_fmt_pct(b.oldest.share)}, "
            f"95% interval {_pct_ci(b.oldest.ci_low, b.oldest.ci_high)}).",
        ),
    ]
    return _section(
        10,
        f"Who is seriously hurt in Barcelona's crashes ({b.year})?",
        "Pedestrians, motorcyclists and the oldest.",
        claims,
        "one year, shares of people in the crashes the city police attended, not rates per "
        "journey or per kilometre.",
    )


# ----------------------------------------------------------------------------- 10. the data
def _data() -> list[str]:
    validation = read_table("validation")
    _require("data", {"every reconciliation check passes": bool(validation.passed.all())})
    claims = [
        _claim(
            "Strong",
            f"The national files reconcile with DGT's published totals: all "
            f"{_fmt_int(len(validation))} reconciliation checks pass.",
        ),
    ]
    return _section(
        11,
        "How far can the data be trusted?",
        "As counts, well; as measures of causes or of kilometres by age, only as far as the "
        "limits above allow.",
        claims,
        "the police records code circumstances unevenly across years and regions (the "
        "[methodology](methodology.md) lists the coding breaks). The study would gain most from "
        "kilometres driven by age on a national basis, from a measure of exposure for the "
        "regional records and from exact age above 65 in the EMEF.",
    )


def _wrap(line: str) -> str:
    """A paragraph or list item wrapped at 100 columns; headings and blank lines as they are."""
    if not line or line.startswith("#"):
        return line
    indent = "  " if line.startswith("- ") else ""
    return textwrap.fill(
        line,
        width=100,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def render() -> str:
    """The document as text."""
    lines = [
        "# Findings",
        "",
        "This study covers road deaths and injuries in Spain from 1993 to 2024, police crash "
        "records for Catalonia (2010–2023) and Barcelona (2025), and the kilometres driven by "
        "drivers of each age. Every result is descriptive or an association in recorded data, "
        f"not a causal effect. The pages with the full evidence are on the [site]({SITE_URL}/); "
        f"definitions, checks and technical notes are in the [methodology]({SITE_URL}/data.html).",
        "",
        "Strength: **Strong** is counted, or an interval far from no effect that survives the "
        "checks run. **Moderate** is clear on the central assumptions and open to a stated "
        "alternative. **Weak** is suggestive. **Not established** means the data cannot tell.",
        "",
    ]
    for section in (
        _long_run,
        _road_classes,
        _seasons,
        _policy,
        _drivers,
        _vehicles,
        _factors,
        _circumstances,
        _catalonia,
        _barcelona,
        _data,
    ):
        lines += section()
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(_wrap(line) for line in lines) + "\n"


def write(path: Path = DOCUMENT) -> Path:
    """Write the document to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(), encoding="utf-8")
    return path
