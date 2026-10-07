"""Road deaths since the first year of the series: segmented trends, the split of deaths per tonne of
fuel into crash frequency and severity, the pandemic years against their projection, and the trend
re-run on measured interurban kilometres, with the road types those kilometres separate."""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import risk_trends
from dgt_stats.site.components import (
    _change,
    _fmt_dec,
    _fmt_int,
    _fmt_pct,
    _signed_pct,
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
from dgt_stats.site.numbers import _long_run_numbers

MEASURE_SHORT = {
    "count": "Deaths",
    "occupants_per_vehicle": "Occupant deaths per vehicle",
    "road_fuel": "Deaths per tonne of fuel",
}
# The prose says a coverage gap of this size moves the comparison by less than this.
COVERAGE_TOLERANCE = 0.01
# A projected year this close to its trend is described as on it.
ON_TREND = 0.01
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def _years(values: list[int]) -> str:
    """A single year when every value is the same, otherwise the range of years."""
    low, high = min(values), max(values)
    return str(low) if low == high else f"{low}–{high}"


def _off(ratio: float) -> str:
    """How far a ratio to trend lies from 1, as an unsigned percentage."""
    return _fmt_pct(abs(float(ratio) - 1), 0)


def _against(ratio: float, what: str = "the trend") -> str:
    """A ratio to trend in words: so many per cent below or above the trend, or on the trend."""
    if round((float(ratio) - 1) * 100) == 0:
        return f"on {what}"
    return f"{_off(ratio)} {'above' if float(ratio) > 1 else 'below'} {what}"


def page_long_run(captions: dict[str, str]) -> str:
    numbers = _long_run_numbers()
    series, segments, projected = numbers["series"], numbers["segments"], numbers["projected"]
    efficiency, last = numbers["efficiency"], numbers["last"]
    headline = read_table("q1_annual_headline").set_index("year")
    panel = read_table("risk_annual_panel").set_index("year")
    first = int(series.year.min())
    fit_end = int(series[series.period == "fitted"].year.max())
    pandemic = int(projected.index.get_level_values("year").min())
    after = range(pandemic, last + 1)
    peak = int(headline.deaths_30d.idxmax())
    by_measure = {
        measure: segments[segments.measure == measure].reset_index(drop=True)
        for measure in MEASURE_SHORT
    }
    if any(len(frame) != 3 for frame in by_measure.values()):
        raise ValueError("long-run page: a measure no longer has three segments")
    count_segments, fuel_segments = by_measure["count"], by_measure["road_fuel"]
    steep, flat = count_segments.iloc[1], count_segments.iloc[2]
    fuel_flat = fuel_segments.iloc[-1]
    fuel_first = int(fuel_segments.start.iloc[0])
    fuel_start = int(fuel_flat.start)
    first_breaks = [int(frame.start.iloc[1]) for frame in by_measure.values()]
    second_breaks = [int(frame.start.iloc[2]) for frame in by_measure.values()]
    middle = [float(frame.annual_change.iloc[1]) for frame in by_measure.values()]
    decade = [b - a for a, b in zip(first_breaks, second_breaks)]
    gap = max(max(first_breaks) - min(first_breaks), max(second_breaks) - min(second_breaks))
    last_segments = {measure: frame.iloc[-1] for measure, frame in by_measure.items()}
    plateau_start = int(flat.start)

    count_first = projected.loc[("count", pandemic)]
    occupants = {year: projected.loc[("occupants_per_vehicle", year)] for year in after}
    fuel = {year: projected.loc[("road_fuel", year)] for year in after}

    def back_from(measures: tuple[str, ...]) -> int:
        """The first year from which every one of ``measures`` stays inside its interval."""
        return min(
            year
            for year in after
            if not any(
                bool(projected.loc[(measure, later), "outside_interval"])
                for measure in measures
                for later in range(year, last + 1)
            )
        )

    count_back = back_from(("count",))

    # Deaths per tonne of road fuel split into injury crashes per tonne and deaths per crash.
    split = read_table("risk_frequency_severity").set_index("year")
    split_first, split_last = int(split.index.min()), int(split.index.max())
    frequency = float(split.loc[split_last, "frequency_index"]) / 100
    severity = float(split.loc[split_last, "severity_index"]) / 100
    per_fuel = float(split.loc[split_last, "deaths_per_fuel_index"]) / 100

    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_panel = read_table("longrun_km_panel").set_index("year")
    coverage = read_table("longrun_km_coverage").set_index("year")
    km_last = int(km_panel.index.max())
    km_first = int(km_check.index.get_level_values("year").min())
    km_comparable = int(km_panel[km_panel.comparable.astype(bool)].index.min())
    km_row = km_check.loc[("per_km", km_last)]
    km_pandemic = km_check.loc[("per_km", pandemic)]
    km_low, km_high = (
        float(km_row.observed) / float(km_row.high),
        float(km_row.observed) / float(km_row.low),
    )
    fuel_km_row = km_check.loc[("per_fuel", km_last)]
    km_base = int(km_row.last_segment_start)
    share = coverage.outside_share
    share_shift = (1 - float(share.loc[km_last])) / (1 - float(share.loc[fit_end])) - 1
    per_tonne = km_panel.km_per_tonne
    vehicle_km = km_panel.vehicle_km
    km_fall = 1 - float(vehicle_km.loc[pandemic]) / float(vehicle_km.loc[fit_end])

    def drift(a: int, b: int) -> float:
        """Average annual growth of measured interurban km per tonne of national fuel."""
        return (float(per_tonne.loc[b]) / float(per_tonne.loc[a])) ** (1 / (b - a)) - 1

    drift_before, drift_after = drift(fuel_start, fit_end), drift(fit_end, km_last)

    # Conventional roads against motorways and dual carriageways, per measured kilometre.
    roads = read_table("road_class_risk")
    road_year = int(roads.year.max())
    roads = roads[roads.year == road_year].set_index("road_class")
    conventional, motorway = roads.loc["conventional"], roads.loc["motorway"]
    road_deaths = float(conventional.deaths_per_bn_km / motorway.deaths_per_bn_km)
    road_crashes = float(conventional.injury_crashes_per_bn_km / motorway.injury_crashes_per_bn_km)
    road_deadly = road_deaths / road_crashes

    # The prose below states each of these; stop if the tables stop supporting them.
    checks = {
        "the projection starts the year after the fit ends": pandemic == fit_end + 1,
        "count first pandemic year below its interval": bool(count_first.outside_interval)
        and float(count_first.ratio) < 1,
        "count inside again from a later year": count_back > pandemic,
        "per fuel first pandemic year inside": not bool(fuel[pandemic].outside_interval),
        "deaths and road fuel both fell in the first pandemic year": float(
            panel.loc[pandemic, "deaths_30d"]
        )
        < float(panel.loc[fit_end, "deaths_30d"])
        and float(panel.loc[pandemic, "road_fuel_tonnes"])
        < float(panel.loc[fit_end, "road_fuel_tonnes"]),
        "per fuel inside until two years before the last": not any(
            bool(fuel[y].outside_interval) for y in range(pandemic, last - 1)
        )
        and last - 2 > pandemic,
        "per fuel last two years above": all(
            bool(fuel[y].outside_interval) and float(fuel[y].ratio) > 1 for y in (last - 1, last)
        ),
        "occupants first two pandemic years below": all(
            bool(occupants[y].outside_interval) and float(occupants[y].ratio) < 1
            for y in (pandemic, pandemic + 1)
        ),
        "fleet grew in the first pandemic year": float(panel.loc[pandemic, "vehicle_fleet"])
        > float(panel.loc[fit_end, "vehicle_fleet"]),
        "plateau flat as a count and per vehicle": all(
            float(last_segments[m].low) < 0 < float(last_segments[m].high)
            for m in ("count", "occupants_per_vehicle")
        ),
        "per fuel last segment falls": float(last_segments["road_fuel"].high) < 0,
        "the first count segment is slow beside the steep one": -0.03
        < float(count_segments.annual_change.iloc[0])
        and float(steep.annual_change) < -0.08,
        "the steep segment is the steepest": float(steep.annual_change)
        == float(count_segments.annual_change.min()),
        "the three measures place their turning points close together": gap <= 3,
        "deaths per tonne of fuel is the product of its two factors": math.isclose(
            frequency * severity, per_fuel, rel_tol=1e-6
        ),
        "both factors fell, deaths per crash much more than crashes per tonne": severity
        < frequency
        < 1
        and math.log(severity) < 2 * math.log(frequency),
        "per km last year inside and above trend": not bool(km_row.outside_interval)
        and float(km_row.ratio) > 1,
        "per km on trend in the first pandemic year while kilometres fell": abs(
            float(km_pandemic.ratio) - 1
        )
        < ON_TREND
        and km_fall > 0,
        "interurban deaths over national fuel above their interval": bool(
            fuel_km_row.outside_interval
        )
        and float(fuel_km_row.ratio) > 1,
        "microdata reproduce the interurban series": bool(
            (coverage.deaths_microdata == coverage.deaths_series).all()
        ),
        "coverage shift under the tolerance": abs(share_shift) < COVERAGE_TOLERANCE,
        "kilometre trend starts at the first comparable year": km_first == km_comparable,
        "interurban km per tonne grew, and faster after the fit than before": 0
        < drift_before
        < drift_after,
        "the road-type comparison uses the last year of measured kilometres": road_year == km_last,
        "conventional roads have more crashes per km, more of them deadly, crashes the larger "
        "factor": road_crashes > road_deadly > 1,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"long-run page: the tables no longer support: {failed}")

    body = summary(
        f"Road deaths in Spain fell slowly until {int(steep.start)}, steeply for the next "
        f"{int(steep.end) - int(steep.start)} years, and have not fallen since {plateau_start}. "
        f"Between {split_first} and {split_last} deaths per tonne of road fuel sold fell "
        f"{_fmt_pct(1 - per_fuel, 0)}, mostly through deaths per injury crash, which fell "
        f"{_fmt_pct(1 - severity, 0)}; injury crashes per tonne fell only "
        f"{_fmt_pct(1 - frequency, 0)}. Set against the trend fitted up to {fit_end} and "
        f"projected forward, the count of deaths in {pandemic} was {_off(count_first.ratio)} "
        "lower, outside the trend's range, while deaths per tonne of road fuel stayed within "
        "their own range: over the year as a whole, deaths fell roughly in line with fuel "
        f"sales. In {last - 1} and {last} deaths per tonne of fuel were "
        f"{_off(fuel[last - 1].ratio)} and "
        f"{_off(fuel[last].ratio)} above their trend, beyond its range, but on interurban roads "
        f"deaths per measured kilometre in {km_last} were "
        f"{_against(km_row.ratio, 'their pre-pandemic trend')}, within its range."
    )
    body += figure(
        "l1_trend_projection",
        f"Three panels of annual road deaths since {first}: as a count, as occupant deaths per "
        "registered vehicle and per tonne of road fuel. Each shows its segmented trend fitted "
        f"to {fit_end} and projected forward, with a shaded range around the projection.",
        captions,
    )

    body += (
        f"<h2>The trend from {first} to {fit_end}</h2>"
        "<p>Each series is described by a trend that changes by a constant percentage each "
        f"year, with up to {WORDS[risk_trends.MAX_BREAKS]} turning points placed where the data "
        "put them. The turning points describe the series; the model attaches no cause to "
        f"them. Each trend is fitted up to {fit_end} and projected forward on the assumption "
        "that its last segment continued, with a 95% prediction interval: the range within "
        "which a year would be expected to fall if the trend had continued with its ordinary "
        "scatter.</p>"
    )
    shown = segments.assign(
        Measure=segments.measure.map(MEASURE_SHORT),
        Years=[f"{int(a)}–{int(b)}" for a, b in zip(segments.start, segments.end)],
        Change=[_signed_pct(float(v), 1) for v in segments.annual_change],
        Interval=[
            f"{_signed_pct(float(lo), 1)} to {_signed_pct(float(hi), 1)}"
            for lo, hi in zip(segments.low, segments.high)
        ],
    )[["Measure", "Years", "Change", "Interval"]].rename(
        columns={"Change": "Annual change", "Interval": "95% interval"}
    )
    body += table(
        shown,
        f"Annual change in each segment of the trends fitted to {first}–{fit_end} (deaths per "
        f"tonne of fuel from {fuel_first}). Occupant deaths are those of motorcycles, cars, "
        "vans, trucks and buses.",
    )
    body += (
        "<p>The three measures describe the same history, with turning points that fall within "
        f"{gap} years of each other: a slow decline to {_years(first_breaks)}, then a fall of "
        f"between {_fmt_pct(-max(middle))} and {_fmt_pct(-min(middle))} a year over the next "
        f"{_years(decade)} years. Between {peak} and {plateau_start} the annual count fell "
        f"{_fmt_pct(1 - float(headline.loc[plateau_start, 'deaths_30d']) / float(headline.loc[peak, 'deaths_30d']), 0)}, "
        f"from {_fmt_int(headline.loc[peak, 'deaths_30d'])} deaths to "
        f"{_fmt_int(headline.loc[plateau_start, 'deaths_30d'])}. In the last segment the count "
        "and occupant deaths per registered vehicle no longer fall (both intervals include no "
        "change), while deaths per tonne of road fuel still fall "
        f"{_fmt_pct(-float(fuel_flat.annual_change))} a year.</p>"
    )
    dispersions = {
        measure: float(frame.dispersion.iloc[0]) for measure, frame in by_measure.items()
    }
    body += technical(
        "Trend specification",
        "<p>Each series is a segmented log-linear Poisson regression (a joinpoint model) with "
        "quasi-likelihood errors: the variance is the mean multiplied by a dispersion factor "
        "estimated from the data and never set below 1. Occupant deaths per registered vehicle "
        "and deaths per tonne of road fuel are fitted as death counts with the logarithm of the "
        "fleet or of fuel as an offset, and the figure multiplies their trends back by each "
        "year's fleet or fuel. For each number of turning points from none to "
        f"{WORDS[risk_trends.MAX_BREAKS]}, every placement that leaves segments at least "
        f"{WORDS[risk_trends.MIN_SEGMENT_YEARS]} years long is fitted and the best kept. The "
        "number of turning points is chosen by QBIC, a Bayesian information criterion in which "
        "the Poisson log-likelihood is divided by the dispersion of the largest model, taking "
        f"the simplest model within {_fmt_dec(risk_trends.QBIC_TOLERANCE, 0)} points of the "
        "lowest. The dispersion factors of the chosen models are "
        f"{_fmt_dec(dispersions['count'])} for the count, "
        f"{_fmt_dec(dispersions['occupants_per_vehicle'])} per registered vehicle and "
        f"{_fmt_dec(dispersions['road_fuel'])} per tonne of fuel. Segment intervals are 95% "
        "confidence intervals for the annual change. The 95% prediction interval of a "
        "projected year combines the uncertainty of the fitted trend with the overdispersed "
        "scatter of a single year around it.</p>",
    )

    body += (
        f"<h2>Crash frequency and severity, {split_first}–{split_last}</h2>"
        "<p>Deaths per tonne of road fuel are the product of two factors that can move "
        "separately: injury crashes per tonne, which measure how often crashes happen for a "
        "given amount of traffic, and deaths per injury crash, which measure how deadly a crash "
        f"is once it has happened. Between {split_first} and {split_last} the first fell "
        f"{_fmt_pct(1 - frequency, 0)} and the second {_fmt_pct(1 - severity, 0)}, so most of "
        f"the {_fmt_pct(1 - per_fuel, 0)} fall in deaths per tonne lies in how deadly crashes "
        "are.</p>"
    )
    body += figure(
        "l3_frequency_severity",
        f"Three lines indexed to {split_first} = 100: deaths per tonne of road fuel, injury "
        f"crashes per tonne and deaths per injury crash. By {split_last} injury crashes per tonne "
        f"stand at {frequency * 100:.0f}, deaths per injury crash at {severity * 100:.0f} and "
        f"deaths per tonne at {per_fuel * 100:.0f}.",
        captions,
    )
    body += (
        "<p>The split depends on how completely crashes with only slight injuries are recorded: "
        "if fewer of them are recorded, crashes per tonne fall and deaths per crash rise by the "
        "same factor, leaving their product unchanged. The fall in deaths per tonne is therefore "
        "the firmer result, and its division between frequency and severity the more fragile "
        "one.</p>"
    )

    body += f"<h2>{pandemic}–{last} against the pre-pandemic trends</h2>"
    body += figure(
        "l2_observed_over_trend",
        "Observed deaths as a ratio to each measure's pre-pandemic trend, for the count, "
        "occupant deaths per registered vehicle and deaths per tonne of road fuel. The count "
        f"and the per-vehicle measure fall below the shaded range in {pandemic}; deaths "
        f"per tonne of fuel rise above it in {last - 1} and {last}.",
        captions,
    )
    rows = []
    for year in after:
        record = {"Year": year}
        for measure, label in MEASURE_SHORT.items():
            row = projected.loc[(measure, year)]
            flag = ""
            if bool(row.outside_interval):
                flag = " (above)" if float(row.ratio) > 1 else " (below)"
            record[label] = f"{_change(float(row.ratio), 0)}{flag}"
        rows.append(record)
    body += table(
        pd.DataFrame(rows),
        f"Observed deaths against each pre-pandemic trend, {pandemic}–{last}, as a percentage "
        "difference from the trend. Above or below: outside the trend's 95% prediction "
        "interval.",
        {"Year": "year"},
    )

    gains = sorted(
        float(g) for g in efficiency.hypothetical_extra_annual_gain.unique() if float(g) > 0
    )
    if len(gains) != 2:
        raise ValueError(f"long-run page: the hypothetical drifts are no longer two: {gains}")
    at_pace = efficiency[efficiency.hypothetical_extra_annual_gain == 0].set_index("year")

    def needed(year: int) -> float:
        return float(at_pace.loc[year, "ratio_low"]) ** (1 / (year - fit_end)) - 1

    def excess(gain: float, with_years: bool) -> str:
        """The per-fuel excess in the last two years under a hypothetical extra drift."""
        rows = efficiency[efficiency.hypothetical_extra_annual_gain == gain].set_index("year")
        pair = [rows.loc[year] for year in (last - 1, last)]
        if not all(float(row.ratio) > 1 for row in pair):
            raise ValueError("long-run page: a hypothetical drift no longer leaves an excess")
        outside = [float(row.ratio_low) > 1 for row in pair]
        sizes = [_off(row.ratio) for row in pair]
        if outside[0] == outside[1]:
            where = "outside" if outside[0] else "inside"
            years = f" in {last - 1} and {last}" if with_years else ""
            return f"{sizes[0]} and {sizes[1]} above{years}, both {where} the range"
        return (
            f"{sizes[0]} above the trend in {last - 1}, "
            f"{'still outside the range' if outside[0] else 'inside the range'}, and {sizes[1]} "
            f"above it in {last}, {'outside it' if outside[1] else 'inside it'}"
        )

    body += (
        f"<p>The count of deaths has been back within its range since {count_back}. Occupant "
        f"deaths per registered vehicle stayed below their range in {pandemic} and "
        f"{pandemic + 1}: the "
        "fleet counts vehicles whether they are used or not, and it grew in "
        f"{pandemic} while deaths fell.</p>"
        f"<p>The excess of deaths per tonne of fuel in {last - 1} and {last} rests on the "
        "projection's assumption that the kilometres a tonne of fuel represents "
        f'(see <a href="trends.html#road-fuel">road fuel as a measure of traffic</a>) kept '
        f"changing after {fit_end} at their {fuel_start}–{fit_end} pace, an assumption no "
        "series can check on all roads. In a hypothetical case where kilometres per tonne "
        f"grew an extra {_fmt_pct(gains[0], 0)} a year from {pandemic}, deaths per tonne of "
        f"fuel would be {excess(gains[0], True)}; with an extra {_fmt_pct(gains[1], 0)} a year, "
        f"{excess(gains[1], False)}. The {last - 1} excess would fall within the range with an "
        f"extra {needed(last - 1) * 100:.1f} percentage points a year, and the {last} excess "
        f"with {needed(last) * 100:.1f}. These growth rates are illustrative assumptions.</p>"
    )

    body += "<h2>Interurban roads: deaths per measured kilometre</h2>"
    cov_first, cov_last = int(coverage.index.min()), int(coverage.index.max())
    body += (
        "<p>The Ministerio de Transportes measures, by traffic counts, the vehicle-kilometres "
        "travelled each year on the interurban roads of the State, the regions and the "
        "provincial councils. Divided into interurban deaths, they give the only available "
        "series whose numerator and denominator cover nearly the same roads. The kilometres "
        "leave out roads run by municipalities and other bodies, which DGT's crash records "
        f"identify: between {_fmt_pct(float(share.min()))} and {_fmt_pct(float(share.max()))} "
        f"of interurban deaths each year from {cov_first} to {cov_last} occurred on them, "
        f"{_fmt_pct(float(share.loc[fit_end]))} in {fit_end} and "
        f"{_fmt_pct(float(share.loc[km_last]))} in {km_last}. The rate's level is therefore "
        "too high by about that share, but the comparison between "
        f"{fit_end} and {km_last} moves by less than {_fmt_pct(COVERAGE_TOLERANCE, 0)}. Before "
        f"{cov_first} the share cannot be measured.</p>"
        "<p>The same trend model, applied to interurban deaths per measured kilometre over "
        f"{km_first}–{fit_end} (the kilometre series is comparable only from {km_comparable}), "
        f"places the last turning point in {km_base} and finds a fall of "
        f"{_fmt_pct(-float(km_row.last_segment_annual_change))} a year after it. Projected "
        f"forward with each year's kilometres, {km_last} comes out at "
        f"{_change(float(km_row.ratio), 0)} against the trend, within its range of "
        f"{_change(km_low, 0)} to {_change(km_high, 0)}. In {pandemic}, when measured "
        f"kilometres fell {_fmt_pct(km_fall, 0)}, deaths per kilometre were on trend "
        f"({_times(float(km_pandemic.ratio))}).</p>"
        "<p>Divided instead by national road fuel, with a trend fitted the same way, the same "
        f"deaths were {_against(fuel_km_row.ratio, 'their trend')} in {km_last}, beyond its "
        "range. Fuel is sold for every road, towns included, so this ratio serves only as a "
        "check on road fuel as a measure of traffic, and it shows the two measures parting: "
        "measured interurban kilometres per tonne of national road fuel grew "
        f"{_fmt_pct(drift_before)} a year over {fuel_start}–{fit_end} and "
        f"{_fmt_pct(drift_after)} a year over {fit_end}–{km_last} (from "
        f"{_fmt_int(per_tonne.loc[fit_end])} to {_fmt_int(per_tonne.loc[km_last])}).</p>"
    )
    body += figure(
        "l4_km_against_fuel",
        "Interurban deaths as a ratio to their pre-pandemic trend. The line per measured "
        "kilometre stays within the shaded range; the line over national road fuel, shown as "
        f"a check on fuel as a measure of traffic, rises above it in {km_last}.",
        captions,
    )
    body += (
        "<p>The measured kilometres also separate road types. Counting only deaths and injury "
        f"crashes on the networks whose traffic is measured, conventional roads in {road_year} "
        f"had {_fmt_dec(conventional.deaths_per_bn_km)} deaths per billion vehicle-kilometres "
        f"and motorways and dual carriageways {_fmt_dec(motorway.deaths_per_bn_km)}: "
        f"{_times(road_deaths)} as many on conventional roads. That ratio combines "
        f"{_times(road_crashes)} as many injury crashes per kilometre with "
        f"{_times(road_deadly)} as many deaths per injury crash, so more of the difference lies "
        "in how often crashes happen than in how deadly they are.</p>"
    )

    body += f"<h2>Fuel and kilometres after {fit_end}</h2>"
    body += (
        f"<p>From {pandemic} the two measures that relate deaths to traffic disagree. Measured "
        "kilometres are the better denominator, but they cover only the interurban networks "
        f"and end in {km_last}. Fuel covers every road, but its projection rests on an "
        "assumption about kilometres per tonne that cannot be checked, and on interurban roads "
        f"kilometres per tonne of fuel grew faster after {fit_end} than before. If they did so "
        "on all roads, part of the excess in deaths per tonne of fuel would reflect more "
        f"driving per tonne. Up to {km_last}, interurban deaths per kilometre show no rise "
        "beyond their trend's range; on all roads, deaths per kilometre are not measured.</p>"
    )
    body += limitation(
        f"The 30-day death series is used as DGT publishes it for every year since {first}; "
        "whether its definition changed over that period has not been checked."
    )
    body += downloads(
        [
            ("longrun_series", "deaths against trend"),
            ("longrun_segments", "trend segments"),
            ("longrun_model_choice", "choice of turning points"),
            ("risk_frequency_severity", "crash frequency and severity"),
            ("longrun_efficiency", "hypothetical fuel drifts"),
            ("longrun_km_panel", "interurban deaths, kilometres and fuel"),
            ("longrun_km_check", "trend per measured kilometre, with the fuel check"),
            ("longrun_km_coverage", "interurban deaths by road owner"),
            ("road_class_risk", "road types per measured kilometre"),
        ],
        method=("data.html#rates", "rates and denominators"),
    )
    return render_page(
        "long-run",
        f"Long-run trends in road deaths, {first}–{last}",
        f"Road deaths in Spain since {first} as a count, per registered vehicle, per tonne of "
        "road fuel and, on interurban roads, per measured kilometre, with trends fitted up to "
        f"{fit_end} and projected forward.",
        body,
    )
