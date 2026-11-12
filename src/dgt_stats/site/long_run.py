"""Road deaths since the first year of the series: the segmented trends, the recent years against
the pre-pandemic projection, deaths per measured interurban kilometre, the last year against 2019,
the fall in deaths per tonne of fuel and why the records cannot split it into crash frequency and
severity, and the road types the measured kilometres separate. How the trends were fitted, the
projection under other choices and the interurban series in detail are technical notes on the
methodology page (``technical_notes``)."""

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
from dgt_stats.site.numbers import _long_run_numbers, _risk_numbers

MEASURE_SHORT = {
    "count": "Deaths",
    "road_fuel": "Deaths per tonne of fuel",
}
# The prose says a coverage gap of this size moves the comparison by less than this.
COVERAGE_TOLERANCE = 0.01
# A projected year this close to its trend is described as on it.
ON_TREND = 0.01
# A year inside its range by less than this is described as at the edge of it.
EDGE = 0.01
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
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


def _beyond(row: pd.Series) -> bool:
    """Whether a change lies outside the interval of an ordinary year."""
    return float(row.ratio_low_yty) > 1 or float(row.ratio_high_yty) < 1


def _size(ratio: float, decimals: int = 1) -> str:
    """How far a ratio lies from 1, as an unsigned percentage."""
    return _fmt_pct(abs(float(ratio) - 1), decimals)


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the tables, with the checks
    that the sentences built on them still hold."""
    numbers = _long_run_numbers()
    series, segments, projected = numbers["series"], numbers["segments"], numbers["projected"]
    efficiency, last = numbers["efficiency"], numbers["last"]
    sensitivity = read_table("longrun_projection_sensitivity").set_index(
        ["measure", "variant", "year"]
    )
    panel = read_table("risk_annual_panel").set_index("year")
    first = int(series.year.min())
    fit_end = int(series[series.period == "fitted"].year.max())
    pandemic = int(projected.index.get_level_values("year").min())
    after = range(pandemic, last + 1)
    peak = int(panel.deaths_30d.idxmax())
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
    fuel = {year: projected.loc[("road_fuel", year)] for year in after}
    second = pandemic + 1
    recent = (last - 1, last)

    count_out = [year for year in after if bool(count[year].outside_interval)]
    fuel_out = [year for year in after if bool(fuel[year].outside_interval)]
    count_back = min(
        year
        for year in after
        if not any(bool(count[later].outside_interval) for later in range(year, last + 1))
    )
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
    count_observed = series[series.measure == "count"].set_index("year").observed

    # The per-fuel projection keeps falling after the fit ends; how far it fell by the last year.
    refit_slope = float(projection["road_fuel"].projection_annual_change)
    trend_fall = 1 - (1 + refit_slope) ** (last - fit_end)

    # The last year against the base year, as counts and as rates, with an ordinary year's
    # variation measured around the count's last pre-pandemic segment.
    risk = _risk_numbers()
    latest, base_year = risk["latest"], risk["base"]
    scatter = read_table("risk_dispersion").set_index("outcome")
    scatter_first = int(scatter.loc["deaths_30d", "first_year"])
    scatter_last = int(scatter.loc["deaths_30d", "last_year"])
    deaths = latest.xs("deaths_30d", level="outcome")
    hosp = latest.xs("hospitalised_30d", level="outcome")
    df_resid = int(scatter.loc["deaths_30d", "df_resid"])
    ratio = {key: float(deaths.loc[key, "ratio_to_base"]) for key in deaths.index}
    # The only rise beyond ordinary variation is in admissions per tonne of fuel: the extra
    # yearly growth in kilometres per tonne that would bring its lower bound to no change.
    hosp_drift = float(hosp.loc["road_fuel", "ratio_low_yty"]) ** (1 / (last - base_year)) - 1
    per_fuel_index = deaths.loc["road_fuel"]
    index = risk["index"].set_index(["outcome", "denominator", "year"])

    def rate(outcome: str, key: str, year: int) -> float:
        """The rate of ``outcome`` under denominator ``key`` in ``year`` (the count for ``count``)."""
        return float(index.loc[(outcome, key, year), "rate"])

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
    roads_last = roads[roads.year == road_year].set_index("road_class")
    conventional, motorway = roads_last.loc["conventional"], roads_last.loc["motorway"]
    road_deaths = float(conventional.deaths_per_bn_km / motorway.deaths_per_bn_km)
    road_crashes = float(conventional.injury_crashes_per_bn_km / motorway.injury_crashes_per_bn_km)
    road_deadly = road_deaths / road_crashes
    # Kilometres are taken as exact; the interval allows for Poisson error in the two death counts.
    road_log_se = math.sqrt(1 / float(conventional.deaths) + 1 / float(motorway.deaths))
    road_low = road_deaths * math.exp(-risk_trends.NORMAL_QUANTILE * road_log_se)
    road_high = road_deaths * math.exp(risk_trends.NORMAL_QUANTILE * road_log_se)
    all_roads = roads.pivot(index="year", columns="road_class", values="deaths_per_bn_km")
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
        "per fuel inside in the pandemic years and outside, above, in the last two": fuel_out
        == list(recent)
        and all(float(fuel[y].ratio) > 1 for y in recent)
        and last - 2 > pandemic,
        "per fuel projected from the count's last turning point: above trend, last year inside": (
            all(float(row.ratio) > 1 for row in fuel_later)
            and not bool(fuel_later[1].outside_interval)
            and int(fuel_later[0].segment_start) == plateau_start > fuel_start
        ),
        "per fuel fell more slowly from the count's last turning point": -0.02 < later_slope < 0
        and later_slope > float(fuel_flat.annual_change),
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
        "plateau flat as a count": float(last_segments["count"].low)
        < 0
        < float(last_segments["count"].high),
        "the count refitted alone rises without a clear trend": float(count_alone.annual_change) > 0
        and float(count_alone.annual_change_low) < 0 < float(count_alone.annual_change_high),
        "per fuel last segment falls": float(last_segments["road_fuel"].high) < 0,
        "the steep segment is the steepest and the count fell in it": float(steep.annual_change)
        == float(count_segments.annual_change.min())
        and float(steep.high) < 0
        and float(steep.annual_change) < -0.08,
        "most of the count's fall to the plateau came in the steep segment": float(
            panel.loc[int(steep.start), "deaths_30d"]
        )
        - float(panel.loc[plateau_start, "deaths_30d"])
        > float(panel.loc[peak, "deaths_30d"]) - float(panel.loc[int(steep.start), "deaths_30d"])
        and peak < int(steep.start),
        "the two measures place their turning points close together": gap <= 3,
        "the first segment is a slower fall for both measures": max(opening.values()) < 0
        and max(middle) < min(opening.values()),
        "the plateau is the count's last segment": plateau_start
        == int(last_segments["count"].start),
        "each segment of the count's fall ends where the next starts": int(steep.end)
        == plateau_start,
        "deaths fell by about three quarters": 0.7 < 1 - per_fuel < 0.8,
        "by injury crashes most of the fall is severity": severity < frequency < 1,
        "by admissions all of the fall is frequency": admitted < per_fuel and per_admission > 1,
        "deaths and road fuel both fell in the first pandemic year": float(
            panel.loc[pandemic, "deaths_30d"]
        )
        < float(panel.loc[fit_end, "deaths_30d"])
        and float(panel.loc[pandemic, "road_fuel_tonnes"])
        < float(panel.loc[fit_end, "road_fuel_tonnes"]),
        "the table's counts are the annual counts": all(
            float(count_observed.loc[y]) == float(panel.loc[y, "deaths_30d"])
            for y in range(plateau_start, last + 1)
        ),
        "kilometre trend starts at the first comparable year": km_first == km_comparable,
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
        "interurban km per tonne grew, and faster after the fit than before": 0
        < drift_before
        < drift_after,
        "the road-type comparison uses the last year of measured kilometres": road_year == km_last,
        "conventional roads have more crashes per km, more of them deadly, crashes the larger "
        "factor": road_crashes > road_deadly > 1,
        # The answer to 'has it got worse?' on the last year against the base year.
        "the base year is the fit's last year and the index runs to the last year": (
            base_year == fit_end and risk["last"] == last
        ),
        "the count's projection uses the same scatter as an ordinary year": math.isclose(
            float(projection["count"].projection_dispersion),
            float(scatter.loc["deaths_30d", "dispersion"]),
            rel_tol=1e-9,
        )
        and int(projection["count"].projection_start) == scatter_first,
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
        "per fuel within ordinary variation of its own base year": float(
            per_fuel_index.ratio_low_yty
        )
        <= 1
        <= float(per_fuel_index.ratio_high_yty)
        and float(per_fuel_index.ratio_to_base) > 1,
        "no change in deaths lies beyond an ordinary year": not any(
            _beyond(deaths.loc[key]) for key in deaths.index
        ),
        "deaths rose as a count, fell per resident and rose per tonne of fuel": (
            ratio["count"] > 1 and ratio["residents"] < 1 and ratio["road_fuel"] > 1
        ),
        "admissions rise beyond ordinary variation only per tonne of fuel, and a small drift in "
        "kilometres per tonne would bring that within it": (
            [key for key in hosp.index if _beyond(hosp.loc[key])] == ["road_fuel"]
            and float(hosp.loc["road_fuel", "ratio_low_yty"]) > 1
            and 0 < hosp_drift < 0.01
        ),
        "annual counts scatter more than Poisson chance": all(
            float(scatter.loc[o, "dispersion"]) > 1 for o in ("deaths_30d", "hospitalised_30d")
        ),
        "the scatter window is the count's last segment before the pandemic": (
            scatter_first == plateau_start and scatter_last == fit_end
        ),
        "a smaller extra drift clears the later year's excess than the earlier year's": 0
        < needed(last)
        < needed(last - 1),
        "measured interurban km per tonne grew faster after the fit by more than the earlier "
        "year's excess needs, as printed": km_last == last - 1
        and drift_extra > needed(km_last)
        and float(f"{drift_extra * 100:.1f}") > float(_points_up(needed(km_last))),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"long-run page: the tables no longer support: {failed}")
    return SimpleNamespace(**locals())


def _since_2019(f: SimpleNamespace) -> str:
    """The last year against the base year: deaths as a count, per resident and per tonne of road
    fuel, and hospital admissions per tonne, with an ordinary year's variation."""
    base, last = f.base_year, f.last
    deaths, hosp = f.deaths, f.hosp

    def size(frame: pd.DataFrame, key: str) -> str:
        return _size(float(frame.loc[key, "ratio_to_base"]))

    rows = []
    for label, outcome, frame, key, decimals in (
        ("Deaths", "deaths_30d", deaths, "count", 0),
        ("Deaths per 100,000 residents", "deaths_30d", deaths, "residents", 2),
        ("Deaths per million tonnes of road fuel", "deaths_30d", deaths, "road_fuel", 1),
        (
            "Hospital admissions per million tonnes of road fuel",
            "hospitalised_30d",
            hosp,
            "road_fuel",
            0,
        ),
    ):
        row = frame.loc[key]

        def value(v: float, d: int = decimals) -> str:
            return _fmt_int(v) if d == 0 else _fmt_dec(v, d)

        rows.append(
            {
                "Measure": label,
                str(base): value(f.rate(outcome, key, base)),
                str(last): value(f.rate(outcome, key, last)),
                "Change": _change(float(row.ratio_to_base)),
                "95% interval for an ordinary year": (
                    f"{_change(float(row.ratio_low_yty))} to {_change(float(row.ratio_high_yty))}"
                ),
            }
        )
    body = (
        f'<h2 id="since-{base}">Against {base}, deaths in {last} changed within ordinary '
        "variation under every denominator</h2>"
        f"<p>Spain recorded {_fmt_int(deaths.loc['count', 'count'])} road deaths in {last}, "
        f"{size(deaths, 'count')} more than in {base}. Per resident they fell "
        f"{size(deaths, 'residents')} and per tonne of road fuel sold they rose "
        f"{size(deaths, 'road_fuel')}, because the population grew while fuel sales fell. People "
        f"admitted to hospital after a crash rose {size(hosp, 'road_fuel')} per tonne of road "
        "fuel, beyond ordinary variation, an excess that would vanish had kilometres per tonne "
        f"of fuel grown {_fmt_pct(f.hosp_drift)} a year faster.</p>"
    )
    body += table(
        pd.DataFrame(rows),
        f"Deaths and hospital admissions in {last} against {base}. The interval covers "
        f"ordinary year-to-year variation around the {f.scatter_first}–{f.scatter_last} trend.",
    )
    body += (
        "<p>An ordinary year's variation is how far each annual count moved around its trend "
        f"over {f.scatter_first}–{f.scatter_last}, the last segment of the count's trend before "
        f"the pandemic: the variance of deaths was {_fmt_dec(f.scatter.loc['deaths_30d', 'dispersion'])} "
        "times what pure chance gives, and that of admissions "
        f"{_fmt_dec(f.scatter.loc['hospitalised_30d', 'dispersion'])} times. The intervals "
        "allow for that scatter, with Student's t for the trend fit's "
        f"{WORDS[f.df_resid]} residual degrees of freedom, and treat every denominator as "
        "exact.</p>"
    )
    return body


def page_long_run(captions: dict[str, str]) -> str:
    f = _facts()
    last, plateau_start, fit_end = f.last, f.plateau_start, f.fit_end
    steep, fuel, count = f.steep, f.fuel, f.count
    notes_link = f'<a href="data.html#{NOTES}">technical notes</a>'

    body = summary(
        f"Road deaths in Spain fell {_fmt_pct(-float(steep.annual_change))} a year from "
        f"{int(steep.start)} to {int(steep.end)} and have shown no clear rise or fall since: "
        f"{_fmt_int(f.count_observed.loc[plateau_start])} people died in {plateau_start} and "
        f"{_fmt_int(f.count_observed.loc[last])} in {last}. Deaths per tonne of road fuel sold, "
        f"which stands in for traffic, were {_off(fuel[last - 1].ratio)} and "
        f"{_off(fuel[last].ratio)} above their pre-pandemic trend in {last - 1} and {last}, an "
        "excess that depends on where the trend starts and on the kilometres a tonne of fuel "
        "represents; per measured interurban kilometre, deaths stayed within their trend's range."
    )

    headline = f.panel.deaths_30d
    body += (
        f'<h2 id="trend">Deaths fell steeply from {int(steep.start)} to {int(steep.end)} and '
        "have levelled off since</h2>"
        f"<p>Between {f.peak} and {plateau_start} the annual count of deaths fell "
        f"{_fmt_pct(1 - float(headline.loc[plateau_start]) / float(headline.loc[f.peak]), 0)}, "
        f"from {_fmt_int(headline.loc[f.peak])} to {_fmt_int(headline.loc[plateau_start])}, "
        f"most of it after {int(steep.start)}. Since {plateau_start} the count has no clear "
        f"trend: fitted alone, the count of {plateau_start}–{fit_end} rises "
        f"{_fmt_pct(float(f.count_alone.annual_change))} a year "
        f"(95% interval {_signed_pct(float(f.count_alone.annual_change_low), 1)} to "
        f"{_signed_pct(float(f.count_alone.annual_change_high), 1)}).</p>"
    )
    body += figure(
        "l1_trend_projection",
        f"Two panels of annual road deaths since {f.first}: all deaths against the trend of the "
        "count, and all deaths against the trend per tonne of road fuel. Each "
        f"trend is fitted to {fit_end} and projected forward with a shaded range. Deaths fell "
        f"steeply to {int(steep.end)} and then levelled off; the count lies below its range in "
        f"{_year_list(f.count_out)} and within it afterwards, and deaths per tonne of fuel lie "
        f"above their range in {_year_list(f.fuel_out)}.",
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
        f"{last}, {_points_up(f.needed(last))} points would be enough. The projections under "
        f"other choices are in the {notes_link}.</p>"
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
    )
    body += (
        '<h2 id="road-fuel">Road fuel stands in for kilometres driven, which no source counts '
        "on all roads</h2>"
        "<p>The kilometres a tonne of fuel represents can change with fuel economy, electric "
        "driving, the mix of freight and private travel, and fuel bought in Spain but burnt "
        "elsewhere, so a change per tonne cannot be read as a change per kilometre. Divided by "
        "national road fuel instead, as a check on road fuel as a measure of traffic, the "
        "interurban deaths were "
        f"{_against(f.fuel_km_row.ratio, 'their trend')} in {f.km_last}, outside its range.</p>"
        "<p>The measures part because measured kilometres per tonne of fuel grew "
        f"{f.drift_extra * 100:.1f} percentage points a year faster after {fit_end} than "
        f"before; had kilometres per tonne grown that much faster on all roads, the {f.km_last} "
        "excess in deaths per tonne of fuel would fall within its range. Whether they did is "
        "unknown, so the excess of deaths per tonne of fuel stays unresolved.</p>"
    )

    body += _since_2019(f)

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
            ("longrun_projection_sensitivity", "the projection under other choices"),
            ("longrun_efficiency", "hypothetical fuel drifts"),
            ("longrun_km_check", "trend per measured kilometre, with the fuel check"),
            ("risk_index", f"{f.base_year} to {last} under each denominator"),
            ("risk_dispersion", "the year-to-year scatter of each count"),
            ("risk_frequency_severity", "crash frequency and severity"),
            ("road_class_risk", "road types per measured kilometre"),
        ],
        method=(f"data.html#{NOTES}", "how the trends were fitted, projected and checked"),
    )
    return render_page(
        "long-run",
        f"Long-run trends in road deaths, {f.first}–{last}",
        f"Road deaths in Spain since {f.first} as a count, per tonne of road fuel and, on "
        f"interurban roads, per measured kilometre, with trends fitted up to {fit_end} and "
        f"projected forward, and {last} against {f.base_year}.",
        body,
    )


def technical_notes(captions: dict[str, str]) -> str:
    """How the long-run trends were fitted, the projection under other choices, the interurban
    series and the recording questions behind the page: one section for the methodology page."""
    f = _facts()
    last, fit_end, first = f.last, f.fit_end, f.first
    pandemic = f.pandemic
    projection = f.projection
    document = f'<a href="{DOCS_URL}/methodology.md">methods document</a>'

    body = (
        f'<h2 id="{NOTES}">{TITLES["long-run"]}: fitting, projections and checks</h2>'
        f'<p>These notes support <a href="long-run.html">{TITLES["long-run"]}</a>; the '
        f"{document} gives the full account.</p>"
        "<p>Each series is a segmented log-linear Poisson regression (a joinpoint model) with "
        "up to "
        f"{WORDS[risk_trends.MAX_BREAKS]} turning points, which describe the series and say "
        "nothing about causes. The variance is the mean times a dispersion factor estimated from "
        f"the data and never below 1 ({_fmt_dec(f.dispersions['count'])} for the count, "
        f"{_fmt_dec(f.dispersions['road_fuel'])} per tonne of fuel); deaths per tonne of road "
        "fuel use the logarithm of fuel as an offset. Segments are at least "
        f"{WORDS[risk_trends.MIN_SEGMENT_YEARS]} years long, and the number of turning points is "
        "chosen by QBIC, taking the simplest model within "
        f"{_fmt_dec(risk_trends.QBIC_TOLERANCE, 0)} points of the lowest. Both measures fall "
        f"slowly to {_years(f.first_breaks)} ({_fmt_pct(-f.opening['count'])} a year as a "
        f"count), then {_fmt_pct(-max(f.middle))} to {_fmt_pct(-min(f.middle))} a year for "
        f"{_years(f.decade)} years; deaths per tonne of fuel then kept falling, "
        f"{_fmt_pct(-float(f.fuel_flat.annual_change))} a year from {f.fuel_start} to "
        f"{fit_end}. Segment intervals use Student's t and take the turning points as known "
        '(<a href="tables/longrun_segments.csv">segments</a>).</p>'
        "<p>The projection continues the last segment, refitted on its own years, so it "
        "carries the scatter of those years: "
        f"{_fmt_dec(float(projection['count'].projection_dispersion))} for the count, the "
        f"factor that sets an ordinary year's variation on the last year against {f.base_year}, "
        f"and {_fmt_dec(float(projection['road_fuel'].projection_dispersion))} per tonne of "
        "fuel. A year's range is the 95% prediction interval, with Student's t for "
        f"{WORDS[int(projection['count'].projection_df)]} and "
        f"{WORDS[int(projection['road_fuel'].projection_df)]} residual degrees of freedom. "
        f"Refitted on deaths within 24 hours, which the police count directly, the search "
        f"finds the same turning points, and {last - 1} and {last} still lie above the range. "
        f"Deaths per tonne of fuel in {last} were "
        f"{_fmt_pct(float(f.per_fuel_index.ratio_to_base) - 1)} above {f.base_year}, within an "
        f"ordinary year's variation, but above a trend that kept falling, about "
        f"{_fmt_pct(-f.refit_slope, 0)} a year and {_fmt_pct(f.trend_fall, 0)} in all by "
        f"{last}.</p>"
    )
    body += figure(
        "l4_km_against_fuel",
        "Two panels of interurban deaths as a ratio to their pre-pandemic trend, with the "
        f"trend's range shaded from {pandemic}. Per measured kilometre the ratio stays within "
        "the range every year; over national road fuel, shown as a check on fuel as a measure "
        f"of traffic, it rises above the range in {f.km_last}.",
        captions,
    )
    body += (
        "<p>The interurban series divides interurban deaths by the vehicle-kilometres the "
        "Ministerio de Transportes measures by traffic counts on State, regional and "
        f"provincial roads. The kilometre series is comparable only from {f.km_comparable}, and "
        f"the latest year, {f.km_last}, is partly estimated. Roads run by municipalities and "
        f"other bodies carry {_fmt_pct(float(f.share.loc[fit_end]))} of interurban deaths in "
        f"{fit_end} and {_fmt_pct(float(f.share.loc[f.km_last]))} in {f.km_last}, so the level "
        f"of the rate is too high by about that share, but its comparison moves by less than "
        f"{_fmt_pct(COVERAGE_TOLERANCE, 0)}. Measured interurban kilometres per tonne of "
        f"national fuel grew {_fmt_pct(f.drift_before)} a year over {f.fuel_start}–{fit_end} "
        f"and {_fmt_pct(f.drift_after)} over {fit_end}–{f.km_last}. DGT's inspection-based "
        f"kilometres, from {f.dgt_first}, put kilometres per tonne "
        f"{_fmt_pct(abs(f.dgt_per_tonne))} {'lower' if f.dgt_per_tonne < 0 else 'higher'} in "
        f"{f.dgt_last} than in {f.dgt_first}.</p>"
        "<p>If fewer lesser casualties are recorded, crashes per tonne fall and deaths per "
        "crash rise by the same factor, leaving deaths per tonne unchanged. The injury-crash "
        f"series has two steps: injury crashes rose {_fmt_pct(f.step_all, 0)} from "
        f"{f.step_year - 1} to {f.step_year}, and urban ones {_fmt_pct(f.urban_step, 0)} between "
        f"{f.urban_from} and {f.urban_to} while interurban ones fell "
        f"{_fmt_pct(-f.interurban_then, 0)}. On the measured networks in {f.road_year}, "
        f"conventional roads had {f.road_crashes:.2f} times the injury crashes per kilometre of "
        f"motorways and {f.road_deadly:.2f} times the deaths per injury crash.</p>"
        f"<p>DGT estimated the 30-day deaths of {first} to "
        f"{risk_trends.DEATHS_30D_COUNTED_FROM - 1} from deaths within 24 hours, with "
        f"correction factors, and has counted them since {risk_trends.DEATHS_30D_COUNTED_FROM} "
        'by matching crash records with the register of deaths (<a href="#assumptions-tested">'
        "assumptions tested</a>).</p>"
    )
    return body
