"""Road deaths since the first year of the series: segmented trends, the split of deaths per tonne of
fuel into crash frequency and severity, the pandemic years against their projection, and the trend
re-run on measured interurban kilometres, with the road types those kilometres separate."""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import risk_trends
from dgt_stats.site.components import (
    ALL_PAGES,
    _change,
    _fmt_dec,
    _fmt_int,
    _fmt_pct,
    _join,
    _signed_pct,
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
# A year inside its range by less than this is described as at the edge of it.
EDGE = 0.01
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}
TITLES = dict(ALL_PAGES)


def _years(values: list[int]) -> str:
    """A single year when every value is the same, otherwise the range of years."""
    low, high = min(values), max(values)
    return str(low) if low == high else f"{low}–{high}"


def _year_list(years: list[int]) -> str:
    """Years in words, joined by commas and a final 'and'."""
    return _join([str(year) for year in years])


def _off(ratio: float) -> str:
    """How far a ratio to trend lies from 1, as an unsigned percentage."""
    return _fmt_pct(abs(float(ratio) - 1), 0)


def _against(ratio: float, what: str = "the trend") -> str:
    """A ratio to trend in words: so many per cent below or above the trend, or on the trend."""
    if round((float(ratio) - 1) * 100) == 0:
        return f"on {what}"
    return f"{_off(ratio)} {'above' if float(ratio) > 1 else 'below'} {what}"


def _where(row: pd.Series) -> str:
    """Where a projected year lies against the trend's range, in words."""
    if bool(row.outside_interval):
        return "outside the range"
    margin = min(float(row.range_high) - float(row.ratio), float(row.ratio) - float(row.range_low))
    return "at the edge of the range" if margin < EDGE else "within the range"


def _cell(row: pd.Series) -> str:
    """A projected year in a table cell: its difference from trend, flagged when outside."""
    flag = ""
    if bool(row.outside_interval):
        flag = " (above)" if float(row.ratio) > 1 else " (below)"
    return f"{_change(float(row.ratio), 0)}{flag}"


def page_long_run(captions: dict[str, str]) -> str:
    numbers = _long_run_numbers()
    series, segments, projected = numbers["series"], numbers["segments"], numbers["projected"]
    efficiency, last = numbers["efficiency"], numbers["last"]
    sensitivity = read_table("longrun_projection_sensitivity").set_index(
        ["measure", "variant", "year"]
    )
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
    opening = {measure: float(frame.annual_change.iloc[0]) for measure, frame in by_measure.items()}
    rate_opening = [opening["occupants_per_vehicle"], opening["road_fuel"]]
    middle = [float(frame.annual_change.iloc[1]) for frame in by_measure.values()]
    decade = [b - a for a, b in zip(first_breaks, second_breaks)]
    gap = max(max(first_breaks) - min(first_breaks), max(second_breaks) - min(second_breaks))
    last_segments = {measure: frame.iloc[-1] for measure, frame in by_measure.items()}
    plateau_start = int(flat.start)

    def at(measure: str, year: int, variant: str = "main") -> pd.Series:
        return sensitivity.loc[(measure, variant, year)]

    count = {year: projected.loc[("count", year)] for year in after}
    occupants = {year: projected.loc[("occupants_per_vehicle", year)] for year in after}
    fuel = {year: projected.loc[("road_fuel", year)] for year in after}
    second = pandemic + 1
    recent = (last - 1, last)

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
    count_out = [year for year in after if bool(count[year].outside_interval)]
    occupants_out = [year for year in after if bool(occupants[year].outside_interval)]
    fuel_out = [year for year in after if bool(fuel[year].outside_interval)]
    projection = {
        measure: series[(series.measure == measure) & (series.period == "projected")].iloc[0]
        for measure in MEASURE_SHORT
    }
    other_start = f"start_{plateau_start}"
    fuel_later = [at("road_fuel", year, other_start) for year in recent]
    later_slope = float(fuel_later[0].annual_change)
    per_tonne_rate = panel.deaths_30d / panel.road_fuel_tonnes
    early_fall = 1 - float(per_tonne_rate.loc[plateau_start] / per_tonne_rate.loc[fuel_start])
    count_alone = at("count", pandemic)

    # The trends page reads the same per-fuel rate against its 2019 level, with an ordinary
    # year's variation measured around the count's last pre-pandemic segment.
    index = read_table("risk_index")
    per_fuel_index = index[
        (index.year == last) & (index.outcome == "deaths_30d") & (index.denominator == "road_fuel")
    ].iloc[0]
    base_year = int(index.year.min())
    ordinary_scatter = float(
        read_table("risk_dispersion").set_index("outcome").loc["deaths_30d", "dispersion"]
    )
    # The per-fuel projection keeps falling after the fit ends; how far it fell by the last year.
    refit_slope = float(projection["road_fuel"].projection_annual_change)
    trend_fall = 1 - (1 + refit_slope) ** (last - fit_end)
    # Each year's count, from the start of the count's last segment.
    count_observed = series[series.measure == "count"].set_index("year").observed

    # Deaths per tonne of road fuel split two ways: by injury crashes and by people admitted.
    split = read_table("risk_frequency_severity").set_index("year")
    split_first, split_last = int(split.index.min()), int(split.index.max())
    end = split.loc[split_last]
    frequency = float(end.frequency_index) / 100
    severity = float(end.severity_index) / 100
    per_fuel = float(end.deaths_per_fuel_index) / 100
    admitted = float(end.hospitalised_per_fuel_index) / 100
    per_admission = float(end.deaths_per_hospitalised_index) / 100
    # The two recording steps of the injury-crash series inside the split's years.
    step_year = int(
        (panel.crashes_interurban / panel.crashes_interurban.shift()).loc[split_first:].idxmax()
    )
    step_all = float(panel.loc[step_year, "crashes"] / panel.loc[step_year - 1, "crashes"]) - 1
    step_interurban = (
        float(
            panel.loc[step_year, "crashes_interurban"]
            / panel.loc[step_year - 1, "crashes_interurban"]
        )
        - 1
    )
    urban_from, urban_to = plateau_start, plateau_start + 3
    urban_step = (
        float(panel.loc[urban_to, "crashes_urban"] / panel.loc[urban_from, "crashes_urban"]) - 1
    )
    interurban_then = (
        float(
            panel.loc[urban_to, "crashes_interurban"] / panel.loc[urban_from, "crashes_interurban"]
        )
        - 1
    )

    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_panel = read_table("longrun_km_panel").set_index("year")
    coverage = read_table("longrun_km_coverage").set_index("year")
    km_last = int(km_panel.index.max())
    km_first = int(km_check.index.get_level_values("year").min())
    km_comparable = int(km_panel[km_panel.comparable.astype(bool)].index.min())
    km_row = km_check.loc[("per_km", km_last)]
    km_pandemic = km_check.loc[("per_km", pandemic)]
    km_projected = [km_check.loc[("per_km", year)] for year in range(pandemic, km_last + 1)]
    fuel_km_row = km_check.loc[("per_fuel", km_last)]
    km_base = int(km_row.projection_start)
    share = coverage.outside_share
    share_shift = (1 - float(share.loc[km_last])) / (1 - float(share.loc[fit_end])) - 1
    per_tonne = km_panel.km_per_tonne
    vehicle_km = km_panel.vehicle_km
    km_fall = 1 - float(vehicle_km.loc[pandemic]) / float(vehicle_km.loc[fit_end])

    def drift(a: int, b: int) -> float:
        """Average annual growth of measured interurban km per tonne of national fuel."""
        return (float(per_tonne.loc[b]) / float(per_tonne.loc[a])) ** (1 / (b - a)) - 1

    drift_before, drift_after = drift(fuel_start, fit_end), drift(fit_end, km_last)
    # How much faster a year measured interurban km per tonne grew after the fit than before.
    drift_extra = (1 + drift_after) / (1 + drift_before) - 1

    # The extra annual growth of km per tonne of fuel from the first projected year that would
    # bring a year's per-fuel excess down to the top of the trend's range.
    at_pace = efficiency[efficiency.hypothetical_extra_annual_gain == 0].set_index("year")

    def needed(year: int) -> float:
        return float(at_pace.loc[year, "ratio_low"]) ** (1 / (year - fit_end)) - 1

    def points_up(rate: float) -> str:
        """A rate in percentage points, rounded up to one decimal, so that the stated drift is
        always enough."""
        return f"{math.ceil(rate * 1000) / 10:.1f}"

    # Conventional roads, single and dual carriageway, against autopistas and autovías.
    roads = read_table("road_class_risk")
    road_year = int(roads.year.max())
    roads = roads[roads.year == road_year].set_index("road_class")
    conventional, motorway = roads.loc["conventional"], roads.loc["motorway"]
    road_deaths = float(conventional.deaths_per_bn_km / motorway.deaths_per_bn_km)
    road_crashes = float(conventional.injury_crashes_per_bn_km / motorway.injury_crashes_per_bn_km)
    road_deadly = road_deaths / road_crashes
    # Kilometres are taken as exact; the interval allows for Poisson error in the two death counts.
    road_log_se = math.sqrt(1 / float(conventional.deaths) + 1 / float(motorway.deaths))
    road_low = road_deaths * math.exp(-risk_trends.NORMAL_QUANTILE * road_log_se)
    road_high = road_deaths * math.exp(risk_trends.NORMAL_QUANTILE * road_log_se)
    all_roads = read_table("road_class_risk").pivot(
        index="year", columns="road_class", values="deaths_per_bn_km"
    )
    road_years = all_roads.conventional / all_roads.motorway
    # DGT's inspection-based kilometres, the other source, over their own years.
    crosscheck = read_table("risk_km_crosscheck").dropna(subset=["billion_km_ratio"])
    dgt_km_end = crosscheck.iloc[-1]
    dgt_per_tonne = float(dgt_km_end.billion_km_ratio / dgt_km_end.road_fuel_tonnes_ratio) - 1
    dgt_years = f"{int(crosscheck.year.iloc[0])}–{int(dgt_km_end.year)}"

    # The prose below states each of these; stop if the tables stop supporting them.
    checks = {
        "the projection starts the year after the fit ends": pandemic == fit_end + 1,
        "the count projection continues the last segment of the count": int(
            projection["count"].projection_start
        )
        == plateau_start,
        "count below its range in the first two pandemic years, inside from then on": count_out
        == [pandemic, second]
        and all(float(count[y].ratio) < 1 for y in count_out)
        and count_back == second + 1,
        "per vehicle below its range in the first pandemic year only, below trend in the second": (
            occupants_out == [pandemic]
            and float(occupants[pandemic].ratio) < 1
            and float(occupants[second].ratio) < 1
        ),
        "the count and the per-vehicle measure about as far below trend in the second year": abs(
            float(count[second].ratio) - float(occupants[second].ratio)
        )
        < 0.05,
        "the per-vehicle range is the wider": float(occupants[second].range_high)
        > float(count[second].range_high),
        "with the scatter of the whole fit the second year swaps over": not bool(
            at("count", second, "joinpoint").outside_interval
        )
        and bool(at("occupants_per_vehicle", second, "joinpoint").outside_interval),
        "the whole fit scatters more than the count's last segment": float(
            at("count", second, "joinpoint").dispersion
        )
        > float(count_alone.dispersion),
        "per fuel inside in the pandemic years and outside, above, in the last two": fuel_out
        == list(recent)
        and all(float(fuel[y].ratio) > 1 for y in recent)
        and last - 2 > pandemic,
        "deaths and road fuel both fell in the first pandemic year": float(
            panel.loc[pandemic, "deaths_30d"]
        )
        < float(panel.loc[fit_end, "deaths_30d"])
        and float(panel.loc[pandemic, "road_fuel_tonnes"])
        < float(panel.loc[fit_end, "road_fuel_tonnes"]),
        "per fuel projected from the count's last turning point: above trend, last year inside": (
            all(float(row.ratio) > 1 for row in fuel_later)
            and not bool(fuel_later[1].outside_interval)
            and int(fuel_later[0].segment_start) == plateau_start > fuel_start
        ),
        "per fuel fell more slowly from the count's last turning point": -0.02 < later_slope < 0
        and later_slope > float(fuel_flat.annual_change),
        "per fuel fell faster a year between the two turning points than after": (
            1 - (1 - early_fall) ** (1 / (plateau_start - fuel_start)) > -later_slope > 0
        ),
        "per fuel on deaths within 24 hours: same turning points, last two years above": (
            str(at("road_fuel", last, "deaths_24h").breaks)
            == str(at("road_fuel", last, "main").breaks)
            and all(
                bool(at("road_fuel", y, "deaths_24h").outside_interval)
                and float(at("road_fuel", y, "deaths_24h").ratio) > 1
                for y in recent
            )
        ),
        "the count on deaths within 24 hours: same turning points": str(
            at("count", last, "deaths_24h").breaks
        )
        == str(at("count", last, "main").breaks),
        "per fuel within ordinary variation of its own base year": float(
            per_fuel_index.ratio_low_yty
        )
        <= 1
        <= float(per_fuel_index.ratio_high_yty)
        and float(per_fuel_index.ratio_to_base) > 1,
        "plateau flat as a count and per vehicle": all(
            float(last_segments[m].low) < 0 < float(last_segments[m].high)
            for m in ("count", "occupants_per_vehicle")
        ),
        "the count refitted alone rises without a clear trend": float(count_alone.annual_change) > 0
        and float(count_alone.annual_change_low) < 0 < float(count_alone.annual_change_high),
        "per fuel last segment falls": float(last_segments["road_fuel"].high) < 0,
        "the first count segment is slow beside the steep one": -0.03
        < float(count_segments.annual_change.iloc[0])
        < 0
        and float(steep.annual_change) < -0.08,
        "the rates fell faster than the count in the first segment": max(rate_opening)
        < opening["count"],
        "the steep segment is the steepest": float(steep.annual_change)
        == float(count_segments.annual_change.min()),
        "the three measures place their turning points close together": gap <= 3,
        "each split multiplies to deaths per tonne of fuel": math.isclose(
            frequency * severity, per_fuel, rel_tol=1e-6
        )
        and math.isclose(admitted * per_admission, per_fuel, rel_tol=1e-6),
        "the two splits disagree: by crashes mostly severity, by admissions all frequency": (
            severity < frequency < 1 and admitted < per_fuel < 1 < per_admission
        ),
        "a one-year step in interurban crashes inside the split's years": step_year > split_first
        and step_interurban > 0.15
        and step_all > 0.1,
        "urban crashes stepped up after the count's last turning point, interurban did not": (
            urban_step > 0.2 and interurban_then < 0
        ),
        "per km inside and above trend in the last year, inside in every projected year": (
            not any(bool(row.outside_interval) for row in km_projected) and float(km_row.ratio) > 1
        ),
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
        # The answer to 'has it got worse?' set beside the trends page's.
        "the trends page compares the last year of this page with the fit's last year": (
            base_year == fit_end and int(index.year.max()) == last
        ),
        "the count's projection uses the same scatter as an ordinary year on the trends page": (
            math.isclose(
                float(projection["count"].projection_dispersion), ordinary_scatter, rel_tol=1e-9
            )
        ),
        "the per-fuel projection continues the per-fuel trend's last segment, falling": int(
            projection["road_fuel"].projection_start
        )
        == fuel_start
        and refit_slope < 0,
        "the two readings reconcile: change on the base year over the trend's fall gives the "
        "excess": abs(
            float(per_fuel_index.ratio_to_base) / (1 - trend_fall) / float(fuel[last].ratio) - 1
        )
        < 0.02,
        "the count lies within its range, below the trend, in the last two years": all(
            not bool(count[y].outside_interval) and float(count[y].ratio) < 1 for y in recent
        ),
        "the per-vehicle measure below its range in the first pandemic year, inside in the second": (
            bool(occupants[pandemic].outside_interval)
            and not bool(occupants[second].outside_interval)
        ),
        "per fuel inside its range in the first two pandemic years": not any(
            bool(fuel[y].outside_interval) for y in (pandemic, second)
        ),
        "the table's counts are the annual headline counts": all(
            float(count_observed.loc[y]) == float(headline.loc[y, "deaths_30d"])
            for y in range(plateau_start, last + 1)
        ),
        "a smaller extra drift clears the later year's excess than the earlier year's": 0
        < needed(last)
        < needed(last - 1),
        "measured interurban km per tonne grew faster after the fit by more than the earlier "
        "year's excess needs": km_last == last - 1 and drift_extra > needed(km_last),
        "deaths per tonne of fuel fell by about three quarters": 0.7 < 1 - per_fuel < 0.8,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"long-run page: the tables no longer support: {failed}")

    trends_link = f'<a href="trends.html">{TITLES["trends"]}</a>'
    body = summary(
        f"Road deaths in Spain fell slowly until {int(steep.start)}, then by "
        f"{_fmt_pct(-float(steep.annual_change))} a year to {int(steep.end)}, and have shown no "
        f"clear rise or fall since: {_fmt_int(count_observed.loc[plateau_start])} people died in "
        f"{plateau_start} and {_fmt_int(count_observed.loc[last])} in {last}. Deaths per tonne "
        f"of road fuel sold, which stands in for traffic, fell {_fmt_pct(1 - per_fuel, 0)} "
        f"between {split_first} and {split_last}. Whether the last years are worse depends on "
        f"the comparison. Against {base_year}, deaths per tonne of fuel in {last} were "
        f"{_fmt_pct(float(per_fuel_index.ratio_to_base) - 1)} higher, within ordinary "
        f"year-to-year variation ({trends_link}). Against their {fuel_start}–{fit_end} decline "
        f"projected forward, they were {_off(fuel[last - 1].ratio)} above the trend in "
        f"{last - 1} and {_off(fuel[last].ratio)} in {last}, outside its range, or "
        f"{_off(fuel_later[0].ratio)} and {_off(fuel_later[1].ratio)} if the trend starts in "
        f"{plateau_start}, {_where(fuel_later[0])} in {last - 1} and {_where(fuel_later[1])} in "
        f"{last}. On interurban roads, deaths per measured kilometre in {km_last} were "
        f"{_against(km_row.ratio, 'their trend')}, within its range."
    )
    body += figure(
        "l1_trend_projection",
        f"Three panels of annual road deaths since {first}: all deaths against the trend of the "
        "count, occupant deaths of motorcycles, cars, vans, trucks and buses against the trend "
        "per registered vehicle, and all deaths against the trend per tonne of road fuel. Each "
        f"trend is fitted to {fit_end} and projected forward with a shaded range. Deaths fell "
        f"steeply to {int(steep.end)} and then levelled off; the count lies below its range in "
        f"{_year_list(count_out)} and within it afterwards, and deaths per tonne of fuel lie "
        f"above their range in {_year_list(fuel_out)}.",
        captions,
    )

    body += (
        f'<h2 id="trend">Deaths fell steeply from {int(steep.start)} to {int(steep.end)} and '
        "have levelled off since</h2>"
        "<p>The count of deaths, occupant deaths per registered vehicle and deaths per tonne of "
        f"road fuel turn at about the same time, within {gap} years of each other: a slower "
        f"decline to {_years(first_breaks)} ({_fmt_pct(-opening['count'])} a year as a count, "
        f"{_fmt_pct(-max(rate_opening))} to {_fmt_pct(-min(rate_opening))} a year as rates), "
        f"then a fall of between {_fmt_pct(-max(middle))} and {_fmt_pct(-min(middle))} a year "
        f"over the next {_years(decade)} years. Between {peak} and {plateau_start} the annual "
        "count fell "
        f"{_fmt_pct(1 - float(headline.loc[plateau_start, 'deaths_30d']) / float(headline.loc[peak, 'deaths_30d']), 0)}, "
        f"from {_fmt_int(headline.loc[peak, 'deaths_30d'])} deaths to "
        f"{_fmt_int(headline.loc[plateau_start, 'deaths_30d'])}. Since then neither the count "
        "nor occupant deaths per registered vehicle has a clear trend (both intervals include "
        "no change), while deaths per tonne of road fuel fell "
        f"{_fmt_pct(-float(fuel_flat.annual_change))} a year from {fuel_start} to {fit_end} "
        f"({_fmt_pct(-later_slope)} a year over {plateau_start}–{fit_end}). Fitted on its own, "
        f"the count of {plateau_start}–{fit_end} rises "
        f"{_fmt_pct(float(count_alone.annual_change))} a year (95% interval "
        f"{_signed_pct(float(count_alone.annual_change_low), 1)} to "
        f"{_signed_pct(float(count_alone.annual_change_high), 1)}), so a slight rise since "
        f"{plateau_start} cannot be ruled out.</p>"
        "<p>Each trend changes by a constant percentage a year between up to "
        f"{WORDS[risk_trends.MAX_BREAKS]} turning points placed where the data put them; the "
        "turning points describe the series and say nothing about causes. The intervals in the "
        "table take the turning points as known.</p>"
    )
    shown = segments.assign(
        Measure=segments.measure.map(MEASURE_SHORT),
        Years=[f"{int(a)}–{int(b)}" for a, b in zip(segments.start, segments.end)],
        Change=[
            f"{_signed_pct(float(v), 1)} ({_signed_pct(float(lo), 1)} to "
            f"{_signed_pct(float(hi), 1)})"
            for v, lo, hi in zip(segments.annual_change, segments.low, segments.high)
        ],
    )[["Measure", "Years", "Change"]].rename(columns={"Change": "Annual change (95% interval)"})
    body += table(
        shown,
        f"Annual change in each segment of the trends fitted to {first}–{fit_end} (deaths per "
        f"tonne of fuel from {fuel_first}). Occupant deaths are those of motorcycles, cars, "
        "vans, trucks and buses.",
    )
    dispersions = {
        measure: float(frame.dispersion.iloc[0]) for measure, frame in by_measure.items()
    }
    body += technical(
        "How the trends were fitted",
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
        "confidence intervals for the annual change, from Student's t with the fit's residual "
        "degrees of freedom.</p>"
        "<p>The projection continues the last segment: the trend of the years from the last "
        f"turning point to {fit_end}, refitted on those years alone. Its scatter is that of "
        "those years: "
        f"{_fmt_dec(float(projection['count'].projection_dispersion))} for the count (the "
        f"factor that {trends_link} uses for an ordinary year's variation in deaths), "
        f"{_fmt_dec(float(projection['occupants_per_vehicle'].projection_dispersion))} per "
        "registered vehicle and "
        f"{_fmt_dec(float(projection['road_fuel'].projection_dispersion))} per tonne of fuel, "
        "where the whole fit's factors also carry the poorer fit of the early years. The 95% "
        "prediction interval of a projected year combines the uncertainty of the refitted trend "
        "with the scatter of a single year around it, with Student's t quantiles for the "
        f"{WORDS[int(projection['count'].projection_df)]}, "
        f"{WORDS[int(projection['occupants_per_vehicle'].projection_df)]} and "
        f"{WORDS[int(projection['road_fuel'].projection_df)]} residual degrees of freedom of "
        "the three refits.</p>",
    )

    body += (
        '<h2 id="frequency-and-severity">Deaths per tonne of fuel fell by three quarters, but '
        "the records cannot split the fall between fewer crashes and less deadly ones</h2>"
        "<p>Deaths per tonne of road fuel are the product of two parts that can move "
        "separately: casualties of a given kind per tonne (how often, for a given amount of "
        "traffic) and deaths per such casualty (how deadly). Between "
        f"{split_first} and {split_last} deaths per tonne fell {_fmt_pct(1 - per_fuel, 0)}. "
        f"Counted by injury crashes, crashes per tonne fell {_fmt_pct(1 - frequency, 0)} and "
        f"deaths per injury crash {_fmt_pct(1 - severity, 0)}. Counted by people admitted to "
        f"hospital, admissions per tonne fell {_fmt_pct(1 - admitted, 0)} and deaths per "
        f"admission rose {_fmt_pct(per_admission - 1, 0)}. By the first split most of the fall "
        "is in how deadly a crash is; by the second all of it is in how often people are "
        "seriously hurt.</p>"
    )
    body += figure(
        "l3_frequency_severity",
        f"Two panels of lines indexed to {split_first} = 100, each with deaths per tonne of road "
        f"fuel, which stand at {per_fuel * 100:.0f} by {split_last}. In the first, injury "
        f"crashes per tonne end at {frequency * 100:.0f} and deaths per injury crash at "
        f"{severity * 100:.0f}. In the second, admissions to hospital per tonne end at "
        f"{admitted * 100:.0f} and deaths per admission at {per_admission * 100:.0f}.",
        captions,
    )
    body += (
        "<p>Each split depends on how completely the lesser casualties are recorded: if fewer "
        "of them are recorded, the frequency falls and the deaths per casualty rise by the same "
        "factor, leaving their product unchanged. The injury-crash series has two steps inside "
        f"these years: injury crashes rose {_fmt_pct(step_all, 0)} from {step_year - 1} to "
        f"{step_year} ({_fmt_pct(step_interurban, 0)} on interurban roads), and urban injury "
        f"crashes rose {_fmt_pct(urban_step, 0)} between {urban_from} and {urban_to} while "
        f"interurban ones fell {_fmt_pct(-interurban_then, 0)}.</p>"
    )

    body += (
        f'<h2 id="recent-years">In {last - 1} and {last} deaths per tonne of fuel were above '
        "their pre-pandemic trend, while the count was within its range</h2>"
        f"<p>Each trend is fitted up to {fit_end} and its last segment projected forward with "
        "a 95% prediction interval, called its range here: where a year would be expected to "
        "fall if the last segment had continued with its ordinary scatter. The table gives each "
        f"year's count since {plateau_start}.</p>"
    )
    yearly = []
    for year in range(plateau_start, last + 1):
        projected_year = year >= pandemic
        row = count.get(year)
        yearly.append(
            {
                "Year": year,
                "Deaths": _fmt_int(count_observed.loc[year]),
                "Trend (95% range)": (
                    f"{_fmt_int(row.expected)} ({_fmt_int(row.low)}–{_fmt_int(row.high)})"
                    if projected_year
                    else ""
                ),
                "Against the trend": _cell(row) if projected_year else "",
                "Per tonne of fuel, against its trend": _cell(fuel[year]) if projected_year else "",
            }
        )
    body += table(
        pd.DataFrame(yearly),
        f"Road deaths within 30 days, {plateau_start}–{last}, and from {pandemic} against the "
        f"pre-pandemic trends. The trend continues the count's {plateau_start}–{fit_end} trend. "
        "The last column sets deaths per tonne of road fuel against their own "
        f"{fuel_start}–{fit_end} trend. Above or below: outside the trend's range.",
        {"Year": "year"},
    )
    body += (
        f"<p>The count of deaths was {_off(count[pandemic].ratio)} below its trend in {pandemic} "
        f"and {_off(count[second].ratio)} below in {second}, outside the range, and has been "
        f"within it since {count_back}; in {last} it was {_against(count[last].ratio)}. "
        f"Occupant deaths per registered vehicle were {_off(occupants[pandemic].ratio)} below "
        f"their trend in {pandemic}, outside its range, and {_off(occupants[second].ratio)} "
        f"below in {second}, within it: their range is wider because occupant deaths are fewer "
        f"and scatter more around their {plateau_start}–{fit_end} trend. Whether a year this "
        "far below trend lies outside the range depends mostly on the scatter it is read "
        f"against: with the continuous trend and the scatter of the whole {first}–{fit_end} "
        "fit, which the poorer fit of the early years inflates, the count in "
        f"{second} lies within its range and the per-vehicle measure outside it (table of other "
        "projections below).</p>"
    )
    body += figure(
        "l2_observed_over_trend",
        "Three panels of observed deaths as a ratio to each measure's pre-pandemic trend, with "
        f"the trend's range shaded from {pandemic}: the count, occupant deaths per registered "
        f"vehicle and deaths per tonne of road fuel. The count lies below its range in "
        f"{_year_list(count_out)} and the per-vehicle measure in {_year_list(occupants_out)}; "
        f"deaths per tonne of fuel lie above their range in {_year_list(fuel_out)}.",
        captions,
    )
    body += (
        f"<p>Deaths per tonne of fuel stayed within their range in {pandemic} and {second}, "
        f"because fuel sales fell too, and were {_off(fuel[last - 1].ratio)} and "
        f"{_off(fuel[last].ratio)} above the trend in {last - 1} and {last}, outside its range. "
        f"Against {base_year} itself, deaths per tonne of fuel in {last} were "
        f"{_fmt_pct(float(per_fuel_index.ratio_to_base) - 1)} higher, within the variation of an "
        f"ordinary year ({trends_link}). The two readings differ because the trend kept falling "
        f"after {fit_end}, about {_fmt_pct(-refit_slope, 0)} a year and "
        f"{_fmt_pct(trend_fall, 0)} in all by {last}: the trend asks whether the decline of "
        f"{fuel_start}–{fit_end} went on, the comparison with {base_year} whether the rate "
        "rose.</p>"
        f"<p>The excess in {last - 1} and {last} depends on where the last segment of the "
        f"trend starts. The search puts the last turning point in {fuel_start}; deaths per "
        f"tonne fell {_fmt_pct(early_fall, 0)} from {fuel_start} to {plateau_start} and then "
        f"{_fmt_pct(-later_slope)} a year over {plateau_start}–{fit_end}, so a trend started "
        f"in {plateau_start} leaves smaller excesses (table below). Refitted on deaths within "
        "24 hours, which the police count directly, the search finds the same turning points, "
        f"and {last - 1} and {last} still lie above the range. The excess also assumes that "
        "the kilometres a tonne of fuel represents kept changing after "
        f"{fit_end} at their pace of {fuel_start}–{fit_end}, which no series can check on all "
        'roads (<a href="trends.html#road-fuel">road fuel as a measure of traffic</a>). Had '
        f"they grown faster by {points_up(needed(last - 1))} percentage points a year from "
        f"{pandemic}, the {last - 1} excess would fall within the range; for {last}, "
        f"{points_up(needed(last))} points would be enough. On interurban roads, where "
        "kilometres are measured, kilometres per tonne of national fuel did grow faster by "
        'more than that (<a href="#interurban">below</a>).</p>'
    )
    variants = [
        ("main", "Last segment refitted, as above"),
        (other_start, f"Last segment from {plateau_start} for every measure"),
        ("normal_quantile", "Last segment refitted, normal quantile in place of Student's t"),
        (
            "joinpoint",
            f"Joinpoint trend continued, scatter of the whole {first}–{fit_end} fit, normal quantile",
        ),
        ("deaths_24h", "Deaths within 24 hours, turning points searched again"),
    ]
    columns = [
        ("count", second, f"Deaths, {second}"),
        ("occupants_per_vehicle", second, f"Occupant deaths per vehicle, {second}"),
        ("road_fuel", last - 1, f"Per tonne of fuel, {last - 1}"),
        ("road_fuel", last, f"Per tonne of fuel, {last}"),
    ]
    sensitivity_rows = []
    for variant, label in variants:
        record = {"Projection": label}
        for measure, year, heading in columns:
            key = (measure, variant, year)
            if variant == other_start and measure != "road_fuel":
                key = (measure, "main", year)
            record[heading] = _cell(sensitivity.loc[key]) if key in sensitivity.index else "–"
        sensitivity_rows.append(record)
    body += table(
        pd.DataFrame(sensitivity_rows),
        "Observed deaths against the pre-pandemic trend under other projections, as a "
        "percentage difference from the trend. Above or below: outside the trend's 95% "
        "prediction interval. Occupant deaths are not published within 24 hours.",
    )

    body += (
        '<h2 id="interurban">On interurban roads, deaths per measured kilometre stayed within '
        "their trend's range</h2>"
    )
    cov_first, cov_last = int(coverage.index.min()), int(coverage.index.max())
    body += (
        "<p>The Ministerio de Transportes measures, by traffic counts, the vehicle-kilometres "
        "travelled each year on the interurban roads of the State, the regions and the "
        "provincial councils. Dividing interurban deaths by them gives the only available "
        "series whose numerator and denominator cover nearly the same roads. The latest "
        f"year, {km_last}, is partly estimated: the yearbook keeps the regional and provincial "
        "networks' lengths of the year before and takes the State network's traffic as the "
        "reference for all networks. Over "
        f"{km_first}–{fit_end} (the kilometre series is comparable only from {km_comparable}) "
        f"the same trend model places the last turning point in {km_base}, and the trend "
        f"refitted to {km_base}–{fit_end} falls {_fmt_pct(-float(km_row.projection_annual_change))} "
        f"a year. Projected forward with each year's kilometres, {km_last} comes out "
        f"{_against(km_row.ratio)}, inside its range of ±{_off(km_row.range_high)}. In "
        f"{pandemic}, when measured kilometres fell "
        f"{_fmt_pct(km_fall, 0)}, deaths per kilometre were on trend (a ratio of "
        f"{float(km_pandemic.ratio):.2f}).</p>"
        "<p>The kilometres leave out roads run by municipalities and other bodies, which DGT's "
        f"crash records identify: between {_fmt_pct(float(share.min()))} and "
        f"{_fmt_pct(float(share.max()))} of interurban deaths each year from {cov_first} to "
        f"{cov_last} occurred on them, {_fmt_pct(float(share.loc[fit_end]))} in {fit_end} and "
        f"{_fmt_pct(float(share.loc[km_last]))} in {km_last}. The rate's level is therefore too "
        f"high by about that share, but the comparison between {fit_end} and {km_last} moves "
        f"by less than {_fmt_pct(COVERAGE_TOLERANCE, 0)}. Before {cov_first} the share cannot "
        "be measured.</p>"
        "<p>Divided instead by national road fuel, with a trend fitted the same way, the same "
        f"deaths were {_against(fuel_km_row.ratio, 'their trend')} in {km_last}, against a "
        f"range of ±{_off(fuel_km_row.range_high)}. Fuel is sold for every road, towns "
        "included, so this ratio serves only as a check on road fuel as a measure of traffic, "
        "and it shows the two measures parting: measured interurban kilometres per tonne of "
        f"national road fuel grew {_fmt_pct(drift_before)} a year over {fuel_start}–{fit_end} "
        f"and {_fmt_pct(drift_after)} a year over {fit_end}–{km_last} (from "
        f"{_fmt_int(per_tonne.loc[fit_end])} to {_fmt_int(per_tonne.loc[km_last])}), "
        f"{drift_extra * 100:.1f} percentage points a year faster. Had kilometres per tonne "
        f"grown that much faster on all roads, the {km_last} excess in deaths per tonne of fuel "
        '(<a href="#recent-years">above</a>) would fall within its range. The other source '
        "points the other way: DGT's inspection-based kilometres, which start in "
        f"{dgt_years.split('–')[0]}, put kilometres per tonne of fuel "
        f"{_fmt_pct(abs(dgt_per_tonne))} {'lower' if dgt_per_tonne < 0 else 'higher'} in "
        f"{dgt_years.split('–')[1]} than in {dgt_years.split('–')[0]} "
        '(<a href="trends.html#road-fuel">road fuel as a measure of traffic</a>). On all '
        "roads, deaths per kilometre are not measured.</p>"
    )
    body += figure(
        "l4_km_against_fuel",
        "Two panels of interurban deaths as a ratio to their pre-pandemic trend, with the "
        f"trend's range shaded from {pandemic}. Per measured kilometre the ratio stays within "
        "the range every year; over national road fuel, shown as a check on fuel as a measure "
        f"of traffic, it rises above the range in {km_last}.",
        captions,
    )
    body += (
        f'<h2 id="road-types">Conventional roads have {road_years.min():.0f} to '
        f"{road_years.max():.0f} times the deaths per kilometre of motorways</h2>"
        "<p>The measured kilometres also separate road types. Counting only deaths and injury "
        f"crashes on the networks whose traffic is measured, conventional roads, single and "
        f"dual carriageway, had {_fmt_dec(conventional.deaths_per_bn_km, 2)} deaths per "
        f"billion vehicle-kilometres in {road_year} and motorways (autopistas and autovías) "
        f"{_fmt_dec(motorway.deaths_per_bn_km, 2)}: {road_deaths:.2f} times as many on "
        f"conventional roads (95% interval {road_low:.2f}–{road_high:.2f}). Over "
        f"{int(road_years.index.min())}–{int(road_years.index.max())} the ratio ran from "
        f"{road_years.min():.2f} to {road_years.max():.2f}. In {road_year} it combines "
        f"{road_crashes:.2f} times as many injury crashes per kilometre with "
        f"{road_deadly:.2f} times as many deaths per injury crash; that split depends on how "
        "completely injury crashes are recorded on each kind of road "
        '(<a href="data.html#rates">frequency and severity</a>).</p>'
    )

    body += limitation(
        f"DGT estimated the 30-day deaths of {first} to "
        f"{risk_trends.DEATHS_30D_COUNTED_FROM - 1} from deaths within 24 hours, with "
        "correction factors drawn from following a sample of people admitted to hospital, and "
        f"has counted them since {risk_trends.DEATHS_30D_COUNTED_FROM} by matching crash "
        "records with the register of deaths (DGT's accident yearbook, annex on the revised "
        "method). The trends refitted on deaths within "
        "24 hours, which the police count directly throughout, place the turning points of the "
        "count and of deaths per tonne of fuel in the same years (the table of other projections above)."
    )
    body += downloads(
        [
            ("longrun_series", "deaths against trend"),
            ("longrun_segments", "trend segments"),
            ("longrun_model_choice", "choice of turning points"),
            ("longrun_projection_sensitivity", "the projection under other choices"),
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
