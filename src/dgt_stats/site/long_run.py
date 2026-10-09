"""Road deaths since the first year of the series: the segmented trends, the fall in deaths per
tonne of fuel and why the records cannot split it into crash frequency and severity, the recent
years against the pre-pandemic projection, deaths per measured interurban kilometre and the road
types those kilometres separate. How the trends were fitted, the projection under other choices
and the interurban series in detail are technical notes on the methodology page
(``technical_notes``)."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pandas as pd

from dgt_stats import risk_trends
from dgt_stats.site.components import (
    ALL_PAGES,
    DOCS_URL,
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
# The section of the methodology page that holds this page's technical notes.
NOTES = "long-run-method"


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


def _points_up(rate: float) -> str:
    """A rate in percentage points, rounded up to one decimal, so that the stated drift is always
    enough."""
    return f"{math.ceil(rate * 1000) / 10:.1f}"


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the tables, with the checks
    that the sentences built on them still hold."""
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
    dispersions = {
        measure: float(frame.dispersion.iloc[0]) for measure, frame in by_measure.items()
    }

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

    # The trends page reads the same per-fuel rate against its base year, with an ordinary
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
    cov_first, cov_last = int(coverage.index.min()), int(coverage.index.max())
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
    dgt_first, dgt_last = int(crosscheck.year.iloc[0]), int(dgt_km_end.year)

    # The page and the notes state each of these; stop if the tables stop supporting them.
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
        "most of the count's fall to the plateau came in the steep segment": float(
            headline.loc[int(steep.start), "deaths_30d"]
        )
        - float(headline.loc[plateau_start, "deaths_30d"])
        > float(headline.loc[peak, "deaths_30d"])
        - float(headline.loc[int(steep.start), "deaths_30d"])
        and peak < int(steep.start),
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
        "year's excess needs, as printed": km_last == last - 1
        and drift_extra > needed(km_last)
        and float(f"{drift_extra * 100:.1f}") > float(_points_up(needed(km_last))),
        "deaths per tonne of fuel fell by about three quarters": 0.7 < 1 - per_fuel < 0.8,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"long-run page: the tables no longer support: {failed}")
    return SimpleNamespace(**locals())


def page_long_run(captions: dict[str, str]) -> str:
    f = _facts()
    last, plateau_start, fit_end = f.last, f.plateau_start, f.fit_end
    steep, fuel, count = f.steep, f.fuel, f.count
    trends_link = f'<a href="trends.html">{TITLES["trends"]}</a>'
    notes_link = f'<a href="data.html#{NOTES}">technical notes</a>'
    explorer = f'<a href="trends-explorer.html">{TITLES["trends-explorer"].lower()}</a>'

    body = summary(
        f"Road deaths in Spain fell {_fmt_pct(-float(steep.annual_change))} a year from "
        f"{int(steep.start)} to {int(steep.end)} and have shown no clear rise or fall since: "
        f"{_fmt_int(f.count_observed.loc[plateau_start])} people died in {plateau_start} and "
        f"{_fmt_int(f.count_observed.loc[last])} in {last}. Deaths per tonne of road fuel sold, "
        f"which stands in for traffic, fell {_fmt_pct(1 - f.per_fuel, 0)} between "
        f"{f.split_first} and {f.split_last}. In {last - 1} and {last} they were "
        f"{_off(fuel[last - 1].ratio)} and {_off(fuel[last].ratio)} above their pre-pandemic "
        "trend, an excess that depends on where the trend starts and on the kilometres a tonne "
        "of fuel represents."
    )

    headline = f.headline.deaths_30d
    body += (
        f'<h2 id="trend">Deaths fell steeply from {int(steep.start)} to {int(steep.end)} and '
        "have levelled off since</h2>"
        f"<p>Between {f.peak} and {plateau_start} the annual count of deaths fell "
        f"{_fmt_pct(1 - float(headline.loc[plateau_start]) / float(headline.loc[f.peak]), 0)}, "
        f"from {_fmt_int(headline.loc[f.peak])} to {_fmt_int(headline.loc[plateau_start])}, "
        f"most of it after {int(steep.start)}. Since {plateau_start} neither the count nor "
        "occupant deaths per registered vehicle has a clear trend: fitted alone, the count of "
        f"{plateau_start}–{fit_end} rises {_fmt_pct(float(f.count_alone.annual_change))} a year "
        f"(95% interval {_signed_pct(float(f.count_alone.annual_change_low), 1)} to "
        f"{_signed_pct(float(f.count_alone.annual_change_high), 1)}).</p>"
    )
    body += figure(
        "l1_trend_projection",
        f"Three panels of annual road deaths since {f.first}: all deaths against the trend of the "
        "count, occupant deaths of motorcycles, cars, vans, trucks and buses against the trend "
        "per registered vehicle, and all deaths against the trend per tonne of road fuel. Each "
        f"trend is fitted to {fit_end} and projected forward with a shaded range. Deaths fell "
        f"steeply to {int(steep.end)} and then levelled off; the count lies below its range in "
        f"{_year_list(f.count_out)} and within it afterwards, and deaths per tonne of fuel lie "
        f"above their range in {_year_list(f.fuel_out)}.",
        captions,
    )
    body += f"<p>Explore the yearly counts and rates in the {explorer}.</p>"

    body += (
        '<h2 id="frequency-and-severity">Deaths per tonne of fuel fell by three quarters, but '
        "the records cannot tell fewer crashes from less deadly ones</h2>"
        f"<p>Deaths per tonne of road fuel fell {_fmt_pct(1 - f.per_fuel, 0)} between "
        f"{f.split_first} and {f.split_last}. Split by injury crashes, crashes per tonne fell "
        f"{_fmt_pct(1 - f.frequency, 0)} and deaths per crash {_fmt_pct(1 - f.severity, 0)}; "
        "split by people admitted to hospital, admissions per tonne fell "
        f"{_fmt_pct(1 - f.admitted, 0)} and deaths per admission rose "
        f"{_fmt_pct(f.per_admission - 1, 0)}. Each split depends on how completely the lesser "
        "casualties are recorded, so how the fall divides between how often crashes happen and "
        "how deadly they are cannot be told from these series.</p>"
    )
    body += figure(
        "l3_frequency_severity",
        f"Two panels of lines indexed to {f.split_first} = 100, each with deaths per tonne of road "
        f"fuel, which stand at {f.per_fuel * 100:.0f} by {f.split_last}. In the first, injury "
        f"crashes per tonne end at {f.frequency * 100:.0f} and deaths per injury crash at "
        f"{f.severity * 100:.0f}. In the second, admissions to hospital per tonne end at "
        f"{f.admitted * 100:.0f} and deaths per admission at {f.per_admission * 100:.0f}.",
        captions,
    )

    body += (
        f'<h2 id="recent-years">In {last - 1} and {last} deaths per tonne of fuel were above '
        "their pre-pandemic trend, while the count was within its range</h2>"
        f"<p>Each trend fitted up to {fit_end} is projected forward with a 95% prediction "
        "interval, its range: where a year would be expected to fall had the trend's last "
        "segment gone on with its ordinary scatter. The count was below its range in "
        f"{_year_list(f.count_out)} and has been within "
        f"it since {f.count_back}. Deaths per tonne of fuel stayed within range in those years, "
        f"because fuel sales fell too, and were {_off(fuel[last - 1].ratio)} and "
        f"{_off(fuel[last].ratio)} above the trend in {last - 1} and {last}, outside its "
        "range.</p>"
    )
    yearly = []
    for year in range(plateau_start, last + 1):
        projected_year = year >= f.pandemic
        row = count.get(year)
        yearly.append(
            {
                "Year": year,
                "Deaths": _fmt_int(f.count_observed.loc[year]),
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
        f"Road deaths within 30 days, {plateau_start}–{last}, and from {f.pandemic} against the "
        f"pre-pandemic trends. The trend continues the count's {plateau_start}–{fit_end} trend. "
        "The last column sets deaths per tonne of road fuel against their own "
        f"{f.fuel_start}–{fit_end} trend. Above or below: outside the trend's range.",
        {"Year": "year"},
    )
    body += (
        f"<p>Started in {plateau_start}, where the count turned, instead of {f.fuel_start}, the "
        f"trend leaves smaller excesses: {_off(f.fuel_later[0].ratio)} and "
        f"{_off(f.fuel_later[1].ratio)}, {_where(f.fuel_later[0])} in {last - 1} and "
        f"{_where(f.fuel_later[1])} in {last}. Had the kilometres a tonne of fuel represents "
        f"grown {_points_up(f.needed(last - 1))} percentage points a year faster from "
        f"{f.pandemic} than before, the {last - 1} excess would also fall within the range; for "
        f"{last}, {_points_up(f.needed(last))} points would be enough.</p>"
        f"<p>Against {f.base_year} itself, deaths per tonne of fuel in {last} were "
        f"{_fmt_pct(float(f.per_fuel_index.ratio_to_base) - 1)} higher, within ordinary "
        f"year-to-year variation ({trends_link}); the two readings differ because the trend "
        f"kept falling after {fit_end}. The projections under other choices are in the "
        f"{notes_link}.</p>"
    )

    body += (
        '<h2 id="interurban">On interurban roads, deaths per measured kilometre stayed within '
        "their trend's range</h2>"
        "<p>The Ministerio de Transportes measures the vehicle-kilometres driven on State, "
        "regional and provincial interurban roads. Per measured kilometre, interurban deaths in "
        f"{f.km_last} were {_against(f.km_row.ratio)}, inside its range of "
        f"±{_off(f.km_row.range_high)}. Roads run by municipalities and other bodies, where "
        f"{_fmt_pct(float(f.share.min()))} to {_fmt_pct(float(f.share.max()))} of interurban "
        f"deaths occurred each year from {f.cov_first} to {f.cov_last}, are not measured; that "
        f"moves the comparison by less than {_fmt_pct(COVERAGE_TOLERANCE, 0)}.</p>"
        "<p>Divided by national road fuel instead, as a check on road fuel as a measure of "
        f"traffic, the same deaths were {_against(f.fuel_km_row.ratio, 'their trend')} in "
        f"{f.km_last}, outside its range. The measures part because measured kilometres per "
        f"tonne of fuel grew {f.drift_extra * 100:.1f} percentage points a year faster after "
        f"{fit_end} than before; had kilometres per tonne grown that much faster on all roads, the "
        f"{f.km_last} excess in deaths per tonne of fuel would fall within its range.</p>"
    )
    body += (
        f'<h2 id="road-types">Conventional roads have {f.road_years.min():.0f} to '
        f"{f.road_years.max():.0f} times the deaths per kilometre of motorways</h2>"
        "<p>On the networks whose traffic is measured, conventional roads, single and dual "
        f"carriageway, had {_fmt_dec(f.conventional.deaths_per_bn_km, 2)} deaths per billion "
        f"vehicle-kilometres in {f.road_year} and motorways (autopistas and autovías) "
        f"{_fmt_dec(f.motorway.deaths_per_bn_km, 2)}: {f.road_deaths:.2f} times as many (95% "
        f"interval {f.road_low:.2f}–{f.road_high:.2f}). Over "
        f"{int(f.road_years.index.min())}–{int(f.road_years.index.max())} the ratio ran from "
        f"{f.road_years.min():.2f} to {f.road_years.max():.2f}.</p>"
    )

    body += limitation(
        f"DGT estimated the 30-day deaths of {f.first} to "
        f"{risk_trends.DEATHS_30D_COUNTED_FROM - 1} from deaths within 24 hours, with correction "
        f"factors; since {risk_trends.DEATHS_30D_COUNTED_FROM} it has counted them. Refitted on "
        "deaths within 24 hours, which the police count directly throughout, the trends turn in "
        "the same years."
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
        method=(f"data.html#{NOTES}", "how the trends were fitted, projected and checked"),
    )
    return render_page(
        "long-run",
        f"Long-run trends in road deaths, {f.first}–{last}",
        f"Road deaths in Spain since {f.first} as a count, per registered vehicle, per tonne of "
        "road fuel and, on interurban roads, per measured kilometre, with trends fitted up to "
        f"{fit_end} and projected forward.",
        body,
    )


def technical_notes(captions: dict[str, str]) -> str:
    """How the long-run trends were fitted, the projection under other choices, the interurban
    series and the recording questions behind the page: one section for the methodology page."""
    f = _facts()
    last, plateau_start, fit_end, first = f.last, f.plateau_start, f.fit_end, f.first
    pandemic, second = f.pandemic, f.second
    count, occupants, fuel, projection = f.count, f.occupants, f.fuel, f.projection
    trends_link = f'<a href="trends.html">{TITLES["trends"]}</a>'
    fuel_link = '<a href="trends.html#road-fuel">road fuel as a measure of traffic</a>'
    document = f'<a href="{DOCS_URL}/methodology.md">methods document</a>'

    body = (
        f'<h2 id="{NOTES}">{TITLES["long-run"]}: fitting, projections and checks</h2>'
        f'<p>These notes support <a href="long-run.html">{TITLES["long-run"]}</a>; the '
        f"{document} gives the full account, in its section on the long run and the "
        "pandemic.</p>"
    )

    body += '<h3 id="long-run-fit">How the trends were fitted</h3>'
    body += (
        "<p>Each trend changes by a constant percentage a year between up to "
        f"{WORDS[risk_trends.MAX_BREAKS]} turning points placed where the data put them; the "
        "turning points describe the series and say nothing about causes. The count, occupant "
        "deaths per registered vehicle and deaths per tonne of fuel turn within "
        f"{f.gap} years of each other.</p><p>All three show a slower decline to "
        f"{_years(f.first_breaks)} ({_fmt_pct(-f.opening['count'])} a year as a count, "
        f"{_fmt_pct(-max(f.rate_opening))} to {_fmt_pct(-min(f.rate_opening))} a year as "
        f"rates), then a fall of between {_fmt_pct(-max(f.middle))} and "
        f"{_fmt_pct(-min(f.middle))} a year over the next {_years(f.decade)} years. In their "
        "last segment the count and deaths per vehicle show no clear trend (both intervals "
        "include no change), while deaths per tonne of fuel kept falling, "
        f"{_fmt_pct(-float(f.fuel_flat.annual_change))} a year from {f.fuel_start} to {fit_end} "
        f"({_fmt_pct(-f.later_slope)} a year over {plateau_start}–{fit_end}). The intervals in "
        "the table take the turning points as known.</p>"
    )
    segments = f.segments
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
        f"Annual change in each segment of the long-run trends fitted to {first}–{fit_end} "
        f"(deaths per tonne of fuel from {f.fuel_first}). Occupant deaths are those of "
        "motorcycles, cars, vans, trucks and buses.",
    )
    body += (
        "<p>Each series is a segmented log-linear Poisson regression (a joinpoint model) with "
        "quasi-likelihood errors: the variance is the mean multiplied by a dispersion factor "
        "estimated from the data and never set below 1. Occupant deaths per registered vehicle "
        "and deaths per tonne of road fuel are fitted as death counts with the logarithm of the "
        "fleet or of fuel as an offset; the long-run page's first figure multiplies their trends "
        "back by each year's fleet or fuel.</p>"
        "<p>For each number of turning points from none to "
        f"{WORDS[risk_trends.MAX_BREAKS]}, every placement that leaves segments at least "
        f"{WORDS[risk_trends.MIN_SEGMENT_YEARS]} years long is fitted and the best kept. The "
        "number of turning points is then chosen by QBIC, a Bayesian information criterion in "
        "which the Poisson log-likelihood is divided by the dispersion of the largest model. "
        f"The simplest model within {_fmt_dec(risk_trends.QBIC_TOLERANCE, 0)} points of the "
        "lowest QBIC is taken.</p>"
        "<p>The dispersion factors of the chosen models are "
        f"{_fmt_dec(f.dispersions['count'])} for the count, "
        f"{_fmt_dec(f.dispersions['occupants_per_vehicle'])} per registered vehicle and "
        f"{_fmt_dec(f.dispersions['road_fuel'])} per tonne of fuel. Segment intervals are 95% "
        "confidence intervals for the annual change, from Student's t with the fit's residual "
        "degrees of freedom.</p>"
        "<p>The projection continues the last segment: the trend of the years from the last "
        f"turning point to {fit_end}, refitted on those years alone. Its scatter is that of "
        "those years: "
        f"{_fmt_dec(float(projection['count'].projection_dispersion))} for the count (the "
        f"factor that {trends_link} uses for an ordinary year's variation in deaths), "
        f"{_fmt_dec(float(projection['occupants_per_vehicle'].projection_dispersion))} per "
        "registered vehicle and "
        f"{_fmt_dec(float(projection['road_fuel'].projection_dispersion))} per tonne of fuel; "
        "the whole fit's factors also carry the poorer fit of the early years.</p>"
        "<p>The 95% prediction interval of a projected year, called its range, combines the "
        "uncertainty of the refitted trend with the scatter of a single year around it, with "
        "Student's t quantiles for the "
        f"{WORDS[int(projection['count'].projection_df)]}, "
        f"{WORDS[int(projection['occupants_per_vehicle'].projection_df)]} and "
        f"{WORDS[int(projection['road_fuel'].projection_df)]} residual degrees of freedom of "
        "the three refits.</p>"
    )

    body += '<h3 id="long-run-projections">The pre-pandemic projections under other choices</h3>'
    body += (
        f"<p>The count of deaths was {_off(count[pandemic].ratio)} below its trend in {pandemic} "
        f"and {_off(count[second].ratio)} below in {second}, outside the range, and has been "
        f"within it since {f.count_back}; in {last} it was {_against(count[last].ratio)}. "
        f"Occupant deaths per registered vehicle were {_off(occupants[pandemic].ratio)} below "
        f"their trend in {pandemic}, outside its range, and {_off(occupants[second].ratio)} "
        f"below in {second}, within it. Their range is wider because occupant deaths are fewer "
        f"and scatter more around their {plateau_start}–{fit_end} trend.</p>"
        "<p>Whether a year this far below trend lies outside the range depends mostly on the "
        "scatter it is read against: "
        f"with the continuous trend and the scatter of the whole {first}–{fit_end} fit, which "
        f"the poorer fit of the early years inflates, the count in {second} lies within its "
        "range and the per-vehicle measure outside it.</p>"
    )
    body += figure(
        "l2_observed_over_trend",
        "Three panels of observed deaths as a ratio to each measure's pre-pandemic trend, with "
        f"the trend's range shaded from {pandemic}: the count, occupant deaths per registered "
        f"vehicle and deaths per tonne of road fuel. The count lies below its range in "
        f"{_year_list(f.count_out)} and the per-vehicle measure in "
        f"{_year_list(f.occupants_out)}; deaths per tonne of fuel lie above their range in "
        f"{_year_list(f.fuel_out)}.",
        captions,
    )
    body += (
        f"<p>Deaths per tonne of fuel stayed within their range in {pandemic} and {second}, "
        f"because fuel sales fell too, and were {_off(fuel[last - 1].ratio)} and "
        f"{_off(fuel[last].ratio)} above the trend in {last - 1} and {last}. Against "
        f"{f.base_year} itself, deaths per tonne of fuel in {last} were "
        f"{_fmt_pct(float(f.per_fuel_index.ratio_to_base) - 1)} higher, within the variation of "
        f"an ordinary year. The two readings differ because the trend kept falling after "
        f"{fit_end}, about {_fmt_pct(-f.refit_slope, 0)} a year and "
        f"{_fmt_pct(f.trend_fall, 0)} in all by {last}: the trend asks whether the decline of "
        f"{f.fuel_start}–{fit_end} went on, the comparison with {f.base_year} whether the rate "
        "rose.</p>"
        f"<p>The search puts the last turning point of deaths per tonne of fuel in "
        f"{f.fuel_start}. They fell {_fmt_pct(f.early_fall, 0)} from {f.fuel_start} to "
        f"{plateau_start} and then {_fmt_pct(-f.later_slope)} a year over "
        f"{plateau_start}–{fit_end}, so a trend started in {plateau_start} leaves smaller "
        "excesses (table below). Refitted on deaths within 24 hours, which the police count "
        f"directly, the search finds the same turning points, and {last - 1} and {last} still "
        "lie above the range.</p>"
        "<p>The excess also assumes that the kilometres a tonne of fuel represents kept "
        f"changing after {fit_end} at their pace of {f.fuel_start}–{fit_end}. No series can "
        f"check this on all roads ({fuel_link}). Had kilometres per tonne grown faster by "
        f"{_points_up(f.needed(last - 1))} percentage points a year from {pandemic}, the "
        f"{last - 1} excess would fall within the range; for {last}, "
        f"{_points_up(f.needed(last))} points would be enough.</p>"
    )
    variants = [
        ("main", "Last segment refitted, as on the page"),
        (f.other_start, f"Last segment from {plateau_start} for every measure"),
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
            if variant == f.other_start and measure != "road_fuel":
                key = (measure, "main", year)
            record[heading] = _cell(f.sensitivity.loc[key]) if key in f.sensitivity.index else "–"
        sensitivity_rows.append(record)
    body += table(
        pd.DataFrame(sensitivity_rows),
        "Observed deaths against the pre-pandemic trend under other projections, as a "
        "percentage difference from the trend. Above or below: outside the trend's 95% "
        "prediction interval. Occupant deaths are not published within 24 hours.",
    )

    body += '<h3 id="long-run-interurban">Interurban deaths per measured kilometre</h3>'
    body += (
        "<p>The Ministerio de Transportes measures, by traffic counts, the vehicle-kilometres "
        "travelled each year on the interurban roads of the State, the regions and the "
        "provincial councils. Dividing interurban deaths by them gives the only available "
        "series whose numerator and denominator cover nearly the same roads. Fitted to "
        f"interurban deaths per kilometre over {f.km_first}–{fit_end} (the kilometre series is "
        f"comparable only from {f.km_comparable}), the same trend model places the last turning "
        f"point in {f.km_base}, and the trend refitted to {f.km_base}–{fit_end} falls "
        f"{_fmt_pct(-float(f.km_row.projection_annual_change))} a year.</p>"
        f"<p>The latest year, {f.km_last}, is partly estimated: the yearbook keeps the regional "
        "and provincial networks' lengths of the year before and takes the State network's "
        "traffic as the reference for all networks. Projected forward with each year's "
        f"kilometres, {f.km_last} comes out {_against(f.km_row.ratio)}, inside its range of "
        f"±{_off(f.km_row.range_high)}. In {pandemic}, when measured kilometres fell "
        f"{_fmt_pct(f.km_fall, 0)}, deaths per kilometre were on trend (a ratio of "
        f"{float(f.km_pandemic.ratio):.2f}).</p>"
        "<p>The kilometres leave out roads run by municipalities and other bodies, which DGT's "
        f"crash records identify: between {_fmt_pct(float(f.share.min()))} and "
        f"{_fmt_pct(float(f.share.max()))} of interurban deaths each year from {f.cov_first} to "
        f"{f.cov_last} occurred on them, {_fmt_pct(float(f.share.loc[fit_end]))} in {fit_end} "
        f"and {_fmt_pct(float(f.share.loc[f.km_last]))} in {f.km_last}. The rate's level is "
        f"therefore too high by about that share, but the comparison between {fit_end} and "
        f"{f.km_last} moves by less than {_fmt_pct(COVERAGE_TOLERANCE, 0)}. Before "
        f"{f.cov_first} the share cannot be measured.</p>"
        "<p>Divided instead by national road fuel, with a trend fitted the same way, the same "
        f"deaths were {_against(f.fuel_km_row.ratio, 'their trend')} in {f.km_last}, against "
        f"a range of ±{_off(f.fuel_km_row.range_high)}. Fuel is sold for every road, towns "
        "included, so this ratio serves only as a check on road fuel as a measure of traffic.</p>"
        "<p>The check shows the two measures parting: measured interurban kilometres per tonne of "
        f"national road fuel grew {_fmt_pct(f.drift_before)} a year over "
        f"{f.fuel_start}–{fit_end} and {_fmt_pct(f.drift_after)} a year over "
        f"{fit_end}–{f.km_last} (from {_fmt_int(f.per_tonne.loc[fit_end])} to "
        f"{_fmt_int(f.per_tonne.loc[f.km_last])}), {f.drift_extra * 100:.1f} percentage points "
        "a year faster. Had kilometres per tonne grown that much faster on all roads, the "
        f"{f.km_last} excess in deaths per tonne of fuel would fall within its range.</p>"
        "<p>The other source of kilometres points the other way: DGT's inspection-based "
        f"kilometres, which start in {f.dgt_first}, put kilometres per tonne of fuel "
        f"{_fmt_pct(abs(f.dgt_per_tonne))} {'lower' if f.dgt_per_tonne < 0 else 'higher'} in "
        f"{f.dgt_last} than in {f.dgt_first} ({fuel_link}). On all roads, deaths per kilometre "
        "are not measured.</p>"
    )
    body += figure(
        "l4_km_against_fuel",
        "Two panels of interurban deaths as a ratio to their pre-pandemic trend, with the "
        f"trend's range shaded from {pandemic}. Per measured kilometre the ratio stays within "
        "the range every year; over national road fuel, shown as a check on fuel as a measure "
        f"of traffic, it rises above the range in {f.km_last}.",
        captions,
    )

    body += '<h3 id="long-run-recording">Recording behind the long-run series</h3>'
    body += (
        "<p>By injury crashes most of the fall in deaths per tonne of fuel is in how deadly a "
        "crash is; by admissions to hospital all of it is in how often people are seriously "
        "hurt. Each split depends on how completely the lesser "
        "casualties are recorded: if fewer of them are recorded, the frequency falls and the "
        "deaths per casualty rise by the same factor, leaving their product unchanged. The "
        "injury-crash series has two steps inside the split's years: injury crashes rose "
        f"{_fmt_pct(f.step_all, 0)} from {f.step_year - 1} to {f.step_year} "
        f"({_fmt_pct(f.step_interurban, 0)} on interurban roads), and urban injury crashes rose "
        f"{_fmt_pct(f.urban_step, 0)} between {f.urban_from} and {f.urban_to} while interurban "
        f"ones fell {_fmt_pct(-f.interurban_then, 0)}.</p>"
        f"<p>On the measured networks in {f.road_year}, conventional roads had "
        f"{f.road_crashes:.2f} times the injury crashes per kilometre of motorways and "
        f"{f.road_deadly:.2f} times the deaths per injury crash; that split too depends on how "
        "completely injury crashes are recorded on each kind of road. The interval of the ratio "
        "of deaths per kilometre allows for Poisson error in the two death counts and takes the "
        "kilometres as exact.</p>"
        f"<p>DGT estimated the 30-day deaths of {first} to "
        f"{risk_trends.DEATHS_30D_COUNTED_FROM - 1} from deaths within 24 hours, with "
        "correction factors drawn from following a sample of people admitted to hospital. Since "
        f"{risk_trends.DEATHS_30D_COUNTED_FROM} it has counted them by matching crash records "
        "with the register of deaths (DGT's accident yearbook, annex on the revised method). "
        "The trends refitted on deaths within 24 hours, which the police count directly "
        "throughout, place the turning points of the count and of deaths per tonne of fuel in "
        'the same years (<a href="#assumptions-tested">assumptions tested</a>).</p>'
    )
    return body
