"""Figure recipes: which summary feeds which chart, with the caption each figure carries.

One figure per idea, drawn where it shows something a sentence cannot: a ranking that reverses,
a distribution a single estimate has to be read against, a discontinuity in the data themselves.
Tables that a figure already says are not drawn twice; they are written to ``reports/tables``
and linked from the page as CSV. A caption says what is shown, for which population and period,
with at most one short clause the reader needs to read the chart; model specifications belong
on the pages and in the methodology.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from dgt_stats import codes, factors, plots, policy, summaries
from dgt_stats.microdata import charts as microdata_charts
from dgt_stats.paths import FIGURES_DIR, NARROW_FIGURES_DIR, TABLES_DIR

CAPTIONS_PATH = FIGURES_DIR / "captions.json"
# The title the page prints above each figure; the SVGs carry none (``plots.TITLES``).
TITLES_PATH = FIGURES_DIR / "titles.json"
log = logging.getLogger(__name__)

SERIES_SOURCE = "DGT, Series históricas del Anuario de Accidentes 2024"
MICRODATA_SOURCE = "DGT, Ficheros de microdatos de accidentes con víctimas 2016–2024"
TABLES_SOURCE = "DGT, Accidentes con víctimas, tablas estadísticas 2014–2024"
KM_SOURCE = "DGT, Kilómetros recorridos estimados a partir de la ITV 2022"
KM_2024_SOURCE = "DGT, Kilómetros anualizados recorridos por el parque móvil 2024"
SPEED_REPORT_SOURCE = "DGT, Informe temático Factor Velocidad 2014–2023"
POPULATION_SOURCE = "INE, Estadística Continua de Población"
CENSUS_SOURCE = "DGT, Censo de conductores 2014–2025"
FUEL_SOURCE = "CORES, consumo de productos petrolíferos"
ROAD_TRAFFIC_SOURCE = "Ministerio de Transportes y Movilidad Sostenible, Anuario Estadístico 2023"
TRAFFIC_SOURCE = (
    "CORES, consumo de productos petrolíferos; Ministerio de Transportes y Movilidad Sostenible, "
    "tráfico en autopistas estatales de peaje"
)
VEHICLE_FLEET_SOURCE = "DGT registered vehicle fleet"

SPEED_STATUS_LABELS = {
    "speed_infraction": "Speed infraction recorded",
    "none": "No speed infraction recorded",
    "unknown": "No speed status recorded",
}
# Drivers recorded as driving too slowly count in each year's total but are not drawn: they are
# below this share of drivers in every year, too few to see.
TOO_SLOW = "too_slow"
TOO_SLOW_MAX_SHARE = 0.001


def _caption(shown: str, source: str, n: str | int | None = None) -> str:
    """A figure caption: what is shown (population and period included, and at most one short
    clause a reader needs to read the chart), then the source and the count."""
    text = f"{shown}. Source: {source}."
    if n is not None:
        text += f" n = {n:,}." if isinstance(n, int) else f" n = {n}."
    return text


def _ranges(text: str) -> str:
    """A range written with a hyphen between numbers (hours 10-13) with an en dash."""
    return re.sub(r"(?<=\d)-(?=\d)", "–", text)


def _year_runs(years: list[int]) -> list[str]:
    """Years as runs of consecutive years: [2005, 2007, 2008, 2009] gives 2005 and 2007–2009."""
    runs: list[list[int]] = []
    for year in sorted(years):
        if runs and year == runs[-1][-1] + 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    return [str(run[0]) if len(run) == 1 else f"{run[0]}–{run[-1]}" for run in runs]


def _join_words(items: list[str]) -> str:
    """'a', 'a and b', 'a, b and c'."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def build_all(
    figures_dir: Path = FIGURES_DIR, frames: dict[str, pd.DataFrame] | None = None
) -> dict[str, str]:
    """Write every figure as SVG and return ``{figure name: caption}``; also saves captions.json
    and titles.json, the title the page prints above each figure.

    Every figure is drawn twice from the same data: for a desktop column, and into ``narrow/``
    for a phone's (``plots.narrow``). The build fails if the two passes disagree on the figures,
    their captions or their titles, or if a narrow figure comes out too wide for a phone.

    ``frames`` are the summaries by registry name; when omitted they are computed here.
    """
    frames = frames if frames is not None else {}

    def summary(name: str) -> pd.DataFrame:
        if name not in frames:
            frames[name] = summaries.SUMMARIES[name]()
        return frames[name].copy()

    figures_dir.mkdir(parents=True, exist_ok=True)
    captions: dict[str, str] = {}
    plots.TITLES.clear()
    _draw_all(figures_dir, captions, summary)
    titles = dict(plots.TITLES)
    narrow_dir = figures_dir / NARROW_FIGURES_DIR.name
    narrow_captions: dict[str, str] = {}
    with plots.narrow():
        _draw_all(narrow_dir, narrow_captions, summary)
    if narrow_captions != captions or plots.TITLES != titles:
        raise ValueError("the narrow figures differ from the wide ones")
    widths = {name: svg_width(narrow_dir / f"{name}.svg") for name in captions}
    too_wide = {name: width for name, width in widths.items() if width > plots.NARROW_MAX_POINTS}
    if too_wide:
        raise ValueError(f"narrow figures wider than a phone's column (points): {too_wide}")

    target = figures_dir / CAPTIONS_PATH.name
    target.write_text(json.dumps(captions, indent=2, ensure_ascii=False), encoding="utf-8")
    missing = sorted(set(captions) - set(titles))
    if missing:
        raise ValueError(f"figures drawn without a title: {missing}")
    (figures_dir / TITLES_PATH.name).write_text(
        json.dumps({name: titles[name] for name in captions}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    for directory in (figures_dir, narrow_dir):
        for path in sorted(directory.glob("*.svg")):
            if path.stem not in captions:
                path.unlink()
                log.info("removed stale figure %s", path.relative_to(figures_dir))
    return captions


_SVG_WIDTH = re.compile(r'<svg[^>]*?\swidth="([\d.]+)pt"')


def svg_width(path: Path) -> float:
    """A chart's width in points, from its SVG."""
    match = _SVG_WIDTH.search(path.read_text(encoding="utf-8")[:2000])
    if not match:
        raise ValueError(f"no width in {path}")
    return float(match.group(1))


def _draw_all(figures_dir: Path, captions: dict[str, str], summary) -> None:
    """Every figure, into ``figures_dir``, with its caption added to ``captions``."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    _trend_figures(figures_dir, captions, summary)
    _long_run_figures(figures_dir, captions, summary)
    _season_figures(figures_dir, captions, summary)
    _sex_figures(figures_dir, captions, summary)
    _factor_figures(figures_dir, captions, summary)
    _speed_status_figure(figures_dir, captions, summary)
    if summaries.model_tables_present():
        _severity_figures(figures_dir, captions)
    else:
        log.warning("model tables missing: run scripts/model.py to get the severity figures")
    _driver_exposure_figures(figures_dir, captions)
    _vehicle_figures(figures_dir, captions, summary)
    _policy_figures(figures_dir, captions, summary)
    _data_figures(figures_dir, captions)
    # The regional crash-record figures (Catalonia, Barcelona, models, generalisability); skipped
    # when the microdata tables are not built.
    microdata_charts.build(figures_dir, captions)
    _severity_calculator_figures(figures_dir, captions)


# --------------------------------------------------------------------------- context


def _speed_status_figure(figures_dir: Path, captions: dict[str, str], summary) -> None:
    shares = summary("q9_infraction_shares")
    block = shares[shares.zone == "all"]
    too_slow = block[TOO_SLOW] / block[[*SPEED_STATUS_LABELS, TOO_SLOW]].sum(axis=1)
    if not (too_slow < TOO_SLOW_MAX_SHARE).all():
        raise ValueError("c3: drivers recorded as too slow are now too many to leave undrawn")
    long = block.melt(
        id_vars="year",
        value_vars=[*SPEED_STATUS_LABELS, TOO_SLOW],
        var_name="status",
        value_name="drivers",
    )
    long["status"] = long.status.map({**SPEED_STATUS_LABELS, TOO_SLOW: TOO_SLOW})
    plots.bar_shares(
        long,
        "year",
        "status",
        "drivers",
        figures_dir / "c3_speed_status.svg",
        "Drivers in injury crashes by recorded speed status, all roads",
        order=list(SPEED_STATUS_LABELS.values()),
        colors=[plots.ACCENT, "#d4d4cf", "#8f8f8a"],
        hidden=(TOO_SLOW,),
    )
    captions["c3_speed_status"] = _caption(
        "Drivers involved in injury crashes by the police record of a speed infraction, Spain, "
        f"all roads, {int(block.year.min())}–{int(block.year.max())}; the share with no speed "
        "status recorded changes in 2016, which shifts every share below it. Drivers recorded "
        f"as driving too slowly, under {TOO_SLOW_MAX_SHARE:.1%} in every year, are not drawn",
        TABLES_SOURCE,
        f"{int(block.total.sum()):,} drivers",
    )


# --------------------------------------------------------------------------- counts and risk


SHORT_DENOMINATORS = {
    "count": "Count",
    "residents": "Per resident",
    "licence_holders": "Drivers per licence holder",
    "vehicles": "Occupants per registered vehicle",
    "road_fuel": "Per tonne of road fuel",
}


def _trend_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    index = summary("risk_index")
    base, last = int(index.year.min()), int(index.year.max())
    latest = index[index.year == last].assign(
        denominator_short=lambda f: f.denominator.map(SHORT_DENOMINATORS)
    )
    plots.dot_interval_panels(
        latest,
        "outcome_label",
        "denominator_short",
        "ratio_to_base",
        "ratio_low_yty",
        "ratio_high_yty",
        figures_dir / "r1_risk_change.svg",
        f"{last} against {base}: each outcome under the denominators it can be paired with",
        order=list(SHORT_DENOMINATORS.values()),
        panel_order=list(dict.fromkeys(latest.outcome_label)),
        xlabel=f"Ratio, {last} to {base} (dotted line: no change)",
        reference=1.0,
        from_zero=False,
        shared=True,
    )
    captions["r1_risk_change"] = _caption(
        f"Each outcome's {last} rate as a ratio to its {base} rate, under every denominator it "
        "can be paired with, Spain, all roads, with 95% intervals that allow for ordinary "
        "year-to-year variation; road fuel sold stands in for distance driven",
        f"{SERIES_SOURCE}; {POPULATION_SOURCE}; {CENSUS_SOURCE}; {VEHICLE_FLEET_SOURCE}; "
        f"{FUEL_SOURCE}",
    )


# Panel titles of the trend chart. Every panel plots a count of deaths a year, the middle one only
# the occupant deaths of the vehicles in the fleet; what differs is the measure the trend was
# fitted to, so each title names what is counted and that measure.
LONG_RUN_PANELS = {
    "Deaths": "All deaths a year; trend fitted to the count",
    "Vehicle occupant deaths per registered vehicle": (
        "Vehicle occupant deaths a year; trend fitted per registered vehicle"
    ),
    "Deaths per tonne of road fuel": "All deaths a year; trend fitted per tonne of road fuel",
}
# The same measures in the ratio chart, where every panel is a ratio.
LONG_RUN_RATIO_PANELS = {
    "Deaths": "Deaths",
    "Vehicle occupant deaths per registered vehicle": "Occupant deaths per vehicle",
    "Deaths per tonne of road fuel": "Deaths per tonne of fuel",
}
# The zoom of the ratio charts: the decade before the pandemic and every year after it.
RATIO_ZOOM_YEARS = 10
# Panel titles of the kilometre check, by measure; the caption says why the fuel panel is only a
# check.
LONG_RUN_KM_PANELS = {
    "per_km": "Per measured interurban vehicle-km",
    "per_fuel": "Over national road fuel (check)",
}


def _long_run_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    raw = summary("longrun_series")
    # Each panel title says what the panel counts, so every measure needs one, and each panel
    # must plot a count of deaths (the rates' trends converted back into deaths).
    untitled = set(raw.measure_label) - set(LONG_RUN_PANELS)
    if untitled or not set(raw.numerator) <= {"deaths_30d", "occupants_deaths_30d"}:
        raise ValueError(f"l1 panel titles: untitled {untitled} or a panel that is not a count")
    fit_end = int(raw[raw.period == "fitted"].year.max())
    first_projected = fit_end + 1
    series = raw.assign(measure_label=raw.measure_label.replace(LONG_RUN_PANELS))
    order = list(dict.fromkeys(series.measure_label))
    plots.trend_projection(
        series,
        "measure_label",
        "year",
        "observed",
        "expected",
        "low",
        "high",
        figures_dir / "l1_trend_projection.svg",
        "Road deaths against the pre-pandemic trend, under three measures",
        last_fitted=fit_end,
        order=order,
        ylabel="Deaths within 30 days, a year",
    )
    zoom_first = fit_end - RATIO_ZOOM_YEARS + 1
    zoom = raw[raw.year >= zoom_first].assign(
        measure_label=lambda f: f.measure_label.replace(LONG_RUN_RATIO_PANELS)
    )
    plots.ratio_panels(
        zoom,
        "measure_label",
        "year",
        "ratio",
        "range_low",
        "range_high",
        figures_dir / "l2_observed_over_trend.svg",
        f"Observed deaths as a share of the pre-pandemic trend, {zoom_first}–{int(zoom.year.max())}",
        last_fitted=fit_end,
        order=list(dict.fromkeys(zoom.measure_label)),
        ylabel="Observed ÷ trend",
    )
    sources = f"{SERIES_SOURCE}; {VEHICLE_FLEET_SOURCE}; {FUEL_SOURCE}"
    captions["l2_observed_over_trend"] = _caption(
        "Observed deaths within 30 days as a ratio to the pre-pandemic trend of each measure "
        f"(up to {fit_end} the fitted segmented trend; from {first_projected} its last segment, "
        f"refitted on that segment's years and projected), with the trend's 95% "
        f"prediction range shaded from {first_projected}, Spain, "
        f"{zoom_first}–{int(zoom.year.max())}; a year outside the shading is outside the "
        "trend's range",
        sources,
    )
    fuel = raw[raw.measure == "road_fuel"]
    fuel_note = f" (road fuel from {int(fuel.year.min())})" if not fuel.empty else ""
    captions["l1_trend_projection"] = _caption(
        f"Deaths within 30 days, Spain, {int(raw.year.min())}–{int(raw.year.max())}"
        f"{fuel_note}, against segmented trends fitted up to {fit_end} and projected from "
        f"{first_projected} with 95% prediction intervals; the middle panel counts the "
        "occupant deaths of motorcycles, cars, vans, trucks and buses, and the trends of the "
        "two rates are converted back into deaths",
        sources,
    )

    check = summary("longrun_km_check")
    fit_first = int(check.year.min())
    coverage = summary("longrun_km_coverage")
    outside = (
        f"{coverage.outside_share.min() * 100:.1f}% to {coverage.outside_share.max() * 100:.1f}%"
    )
    covered = f"{int(coverage.year.min())}–{int(coverage.year.max())}"
    check = check[check.year >= zoom_first]
    untitled = set(check.measure) - set(LONG_RUN_KM_PANELS)
    if untitled:
        raise ValueError(f"l4 panel titles: no title for {sorted(untitled)}")
    check = check.assign(measure_label=check.measure.map(LONG_RUN_KM_PANELS))
    plots.ratio_panels(
        check,
        "measure_label",
        "year",
        "ratio",
        "range_low",
        "range_high",
        figures_dir / "l4_km_against_fuel.svg",
        "Interurban deaths against the pre-pandemic trend: per measured kilometre, and over "
        "national road fuel as a check",
        last_fitted=fit_end,
        order=list(dict.fromkeys(check.measure_label)),
        ylabel="Observed ÷ trend",
    )
    captions["l4_km_against_fuel"] = _caption(
        f"Interurban deaths within 30 days as a ratio to a trend fitted to {fit_first}–{fit_end} "
        f"and projected from {first_projected}, per measured vehicle-kilometre and, as a check "
        "on fuel as a measure of traffic, over the road fuel sold for every road in Spain, towns "
        "included, with the trend's 95% prediction range shaded, Spain, "
        f"{int(check.year.min())}–{int(check.year.max())}; the kilometres leave out roads run "
        f"by municipalities and other bodies, which account for {outside} of interurban deaths "
        f"({covered})",
        f"{SERIES_SOURCE}; {FUEL_SOURCE}; {ROAD_TRAFFIC_SOURCE}",
    )

    split = summary("risk_frequency_severity")
    per_fuel = "Deaths per tonne of fuel"
    panels = {
        "Split by injury crashes": {
            "deaths_per_fuel_index": per_fuel,
            "frequency_index": "Injury crashes per tonne",
            "severity_index": "Deaths per injury crash",
        },
        "Split by people admitted to hospital": {
            "deaths_per_fuel_index": per_fuel,
            "hospitalised_per_fuel_index": "Admissions per tonne",
            "deaths_per_hospitalised_index": "Deaths per admission",
        },
    }
    long = pd.concat(
        [
            split.melt(
                id_vars="year", value_vars=list(labels), var_name="measure", value_name="index"
            ).assign(measure_label=lambda f, labels=labels: f.measure.map(labels), panel=panel)
            for panel, labels in panels.items()
        ],
        ignore_index=True,
    )
    base = int(split.year.min())
    plots.line_panels(
        long,
        "panel",
        "year",
        "index",
        "measure_label",
        figures_dir / "l3_frequency_severity.svg",
        f"Deaths per tonne of road fuel, split two ways into how often and how deadly ({base} = 100)",
        order=list(panels),
        focal=per_fuel,
        reference=100,
        ylabel=f"Index, {base} = 100",
    )
    captions["l3_frequency_severity"] = _caption(
        "Deaths within 30 days per tonne of road fuel sold (petrol plus diesel), split into "
        "injury crashes per tonne and deaths per injury crash (top) and into people admitted to "
        "hospital per tonne and deaths per admission (bottom), indexed to "
        f"{base} = 100, Spain, all roads, {base}–{int(split.year.max())}; each pair multiplies "
        "to deaths per tonne, and the two pairs divide its fall differently",
        f"{SERIES_SOURCE}; {FUEL_SOURCE}",
    )


# --------------------------------------------------------------------------- forecasts


# The three measures of road use drawn beside deaths on the seasons page, the same in both of its
# line charts. Greys alone left them hard to tell apart, so each has its own colour (near-black,
# orange, purple: every pair, and each with the accent of deaths, stays apart under red-green and
# blue-yellow colour-vision deficiency on the charts' white ground), its own marker shape and its
# own dash.
SEASON_STYLES = {
    "Road fuel sold (petrol + diesel)": {
        "color": "#2b2b2b",
        "linestyle": (0, (5, 2)),
        "marker": "s",
        "markersize": 3.2,
    },
    "Petrol sold only": {
        "color": plots.CATEGORICAL[1],
        "linestyle": (0, (5, 2, 1, 2)),
        "marker": "^",
        "markersize": 3.8,
    },
    "Toll-motorway traffic per km": {
        "color": plots.CATEGORICAL[2],
        "linestyle": (0, (1, 1.6)),
        "marker": "D",
        "markersize": 3.2,
    },
}


def _season_styles(frame: pd.DataFrame) -> dict[str, dict[str, object]]:
    """The fixed look of each road-use series; the build fails on a series without one."""
    names = list(dict.fromkeys(frame.series_label))[1:]
    unstyled = set(names) - set(SEASON_STYLES)
    if unstyled:
        raise ValueError(f"season charts: no style for {sorted(unstyled)}")
    return {name: SEASON_STYLES[name] for name in names}


def _season_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    profile = summary("season_profile_long")
    plots.month_lines(
        profile,
        "series_label",
        "index",
        figures_dir / "m1_season_profile.svg",
        "Deaths and three measures of road use by month (average month = 100)",
        order=list(dict.fromkeys(profile.series_label)),
        reference=100,
        focal=profile.series_label.iloc[0],
        styles=_season_styles(profile),
    )
    effects = summary("season_month_effects")
    pooled = [int(year) for year in str(effects.years.iloc[0]).split()]
    left_out = sorted(set(range(min(pooled), max(pooled) + 1)) - set(pooled))
    years = f"{min(pooled)}–{max(pooled)} ({', '.join(str(y) for y in left_out)} left out)"
    captions["m1_season_profile"] = _caption(
        "Deaths within 30 days, road fuel sold (petrol plus diesel), petrol sold and "
        "toll-motorway traffic per kilometre by month, each divided by its year's mean month "
        f"and averaged over {years}, Spain; petrol and toll motorways cover only part of all "
        "traffic, and toll traffic is a daily average where the other series are monthly totals",
        f"{SERIES_SOURCE}; {TRAFFIC_SOURCE}",
    )

    short = {"none": "Raw deaths", "road_fuel_tonnes": "Per tonne of road fuel sold"}
    effects = effects.assign(panel=effects.exposure.map(short))
    plots.dot_interval_panels(
        effects,
        "panel",
        "month_label",
        "rate_ratio",
        "low",
        "high",
        figures_dir / "m2_month_effects.svg",
        "Deaths by month against the average month, raw and per tonne of road fuel",
        order=list(dict.fromkeys(effects.month_label)),
        panel_order=list(short.values()),
        xlabel="Deaths against the average month (dotted line: the same)",
        reference=1.0,
        from_zero=False,
        shared=True,
    )
    captions["m2_month_effects"] = _caption(
        "Deaths within 30 days in each month against the average month of the same year, raw "
        f"and per tonne of road fuel sold, Spain, {years}, with 95% intervals; the raw panel "
        "compares monthly totals, not adjusted for the number of days in a month",
        f"{SERIES_SOURCE}; {FUEL_SOURCE}",
    )

    lockdown = summary("season_lockdown_long")
    plots.month_lines(
        lockdown,
        "series_label",
        "change",
        figures_dir / "m3_lockdown.svg",
        "2020 against the same month of 2017–2019: deaths and traffic",
        order=list(dict.fromkeys(lockdown.series_label)),
        reference=0,
        percent=True,
        focal=lockdown.series_label.iloc[0],
        styles=_season_styles(lockdown),
    )
    captions["m3_lockdown"] = _caption(
        "Change in deaths within 30 days and in three measures of road use (road fuel sold, petrol "
        "sold, toll-motorway traffic per kilometre) in each month of 2020 against the mean of "
        "the same month in 2017–2019, Spain; the state of alarm began on 14 March 2020",
        f"{SERIES_SOURCE}; {TRAFFIC_SOURCE}",
    )


def _sex_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    ratios = summary("drivers_sex_ratios")
    short = {
        "involved_per_1000_licences": "Involved, per licence holder",
        "deaths_per_million_licences": "Killed, per licence holder",
        "deaths_per_1000_involved": "Killed, once involved",
    }
    cars = ratios[ratios.scope == "car"].assign(panel=lambda f: f.measure.map(short))
    plots.dot_interval_panels(
        cars,
        "panel",
        "band_label",
        "ratio",
        "low",
        "high",
        figures_dir / "a3_sex_ratios.svg",
        "Men against women, private-car drivers: crashing, and dying (2022–2024)",
        order=list(dict.fromkeys(cars.band_label)),
        panel_order=list(short.values()),
        # Ratios on a log scale, where a ratio of 2 and one of 1/2 are the same distance from 1.
        xlabel="Ratio, men to women, log scale (dotted line: the same rate)",
        reference=1.0,
        from_zero=False,
        shared=True,
        log=True,
    )
    rates_table = summary("drivers_sex_rates")
    adults = rates_table[(rates_table.scope == "car") & (rates_table.band == "18+")]
    captions["a3_sex_ratios"] = _caption(
        "Men's rates divided by women's among private-car drivers (taxis and ride-hailing cars "
        "excluded), by age: involvement in injury crashes and death within 30 days per licence "
        "holder, and death per driver involved, Spain, 2022–2024 pooled, with 95% intervals. "
        "The estimates per kilometre are given in the text",
        f"{TABLES_SOURCE}; {CENSUS_SOURCE}",
        f"{int(adults.drivers_involved.sum()):,} drivers involved",
    )


def _factor_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    pooled = summary("speed_severity_pooled")
    adjusted = pooled.road_type == "adjusted"
    shown = pooled.assign(
        label=pooled.road_type_label.where(~adjusted, "Adjusted for road type and year"),
        block=np.where(adjusted, "All roads", "By road type"),
        kind=np.where(adjusted, "summary", "focal"),
    )
    shown = pd.concat([shown[~adjusted], shown[adjusted]])
    plots.dot_interval(
        shown,
        "label",
        "rate_ratio",
        "ratio_low",
        "ratio_high",
        figures_dir / "f1_speed_severity.svg",
        "Deaths per crash when speed is recorded, against other crashes",
        xlabel="Ratio of deaths per 100 crashes, log scale (dotted line: the same)",
        reference=1.0,
        style="kind",
        group="block",
        log=True,
    )
    captions["f1_speed_severity"] = _caption(
        "Deaths within 30 days per 100 injury crashes in which the police recorded "
        "inappropriate speed, as a ratio to the same rate in the other injury crashes on the "
        "same type of road, Spain outside Catalonia and the Basque Country, 2016–2023 pooled, "
        "with 95% intervals that allow for year-to-year variation (for the adjusted ratio, also "
        "for the differences between road types)",
        f"{SPEED_REPORT_SOURCE}; {MICRODATA_SOURCE}",
        f"{int(pooled.speed_crashes.sum()):,} crashes with inappropriate speed recorded",
    )

    shares = summary("factor_shares")
    shares = shares[shares.zone != "all"]
    # A series that breaks at every year is drawn as unjoined points; the caption names the
    # factors whose series do so on both kinds of road, and the build stops on any other.
    runs = shares.groupby(["factor", "zone"]).agg(
        years=("year", "size"), runs=("segment", "nunique")
    )
    every_year = (runs.years == runs.runs).groupby(level="factor").agg(["all", "any"])
    unjoined = list(every_year.index[every_year["all"]])
    if len(unjoined) != 1 or every_year["any"].sum() != len(unjoined):
        raise ValueError(f"f2 caption: series that break at every year: {every_year}")
    plots.segmented_small_multiples(
        shares,
        "factor",
        "year",
        "share",
        "zone_label",
        "segment",
        figures_dir / "f2_factor_shares.svg",
        "Share of injury crashes with each factor recorded; gaps are breaks in comparability",
        order=[
            "Alcohol",
            "Inappropriate speed",
            "Distraction or inattention",
            "Illegal manoeuvres",
            "Drugs",
        ],
        series_order=["Interurban roads", "Urban streets"],
    )
    captions["f2_factor_shares"] = _caption(
        "Injury crashes in which the police recorded each factor, as a share of all "
        "injury crashes on interurban roads and on urban streets, Spain outside Catalonia and "
        "the Basque Country, 2014–2023; a line breaks, at a short vertical mark, where the share "
        f"rises by more than {factors.BREAK_RATIO - 1:.0%} or falls by more than "
        f"{1 - 1 / factors.BREAK_RATIO:.0%} in a year, or a year has fewer than "
        f"{factors.MIN_CRASHES} crashes. The {unjoined[0].lower()} series breaks at every year "
        "on both kinds of road, so its points are not joined and are not comparable from year "
        "to year",
        SPEED_REPORT_SOURCE,
    )


# --------------------------------------------------------------------------- severity


# The model table keeps DGT's Spanish name for a road type; the figure uses the English one that
# the crash-circumstances page and its tables use.
FOREST_LEVELS = {"autovía": "dual carriageway"}


def _severity_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    coefficients = summaries.read_model_table("q3_model_coefficients")
    n_model = int(coefficients.n.iloc[0])
    fatal_rows = coefficients[
        (coefficients.outcome == "fatal") & (coefficients.predictor != "year")
    ]
    # The levels that stand for a missing value record how the form was filled in, not what
    # happened (``is_nuisance``); they stay in the table and are left out of the figure.
    nuisance = fatal_rows[fatal_rows.is_nuisance.astype(bool)]
    table = fatal_rows[~fatal_rows.is_nuisance.astype(bool)].assign(
        level=lambda f: f.level.astype(str).replace(FOREST_LEVELS).map(_ranges)
    )
    spanish = sorted(set(table.level[table.level.str.contains("[áéíóúñ]")]))
    if spanish:
        raise ValueError(f"s1 forest plot: levels without an English label: {spanish}")
    plots.forest(
        table,
        "predictor_label",
        "level",
        "odds_ratio",
        "or_low",
        "or_high",
        figures_dir / "s1_forest_fatal.svg",
        "Odds of at least one death, by crash circumstance",
        reference_flag="is_reference",
    )
    # A level with no crash of the modelled outcome has no odds ratio, so the forest plot leaves
    # its row out; name it here rather than letting the reader wonder, and derive the sentence
    # from the table so that it follows the data on a refit.
    separated = table[table.odds_ratio.isna() & ~table.is_reference.astype(bool)]
    note = ""
    if not separated.empty:
        named = ", ".join(
            f"{row.predictor_label.lower()} '{row.level}' ({row.crashes:,} crashes)"
            for row in separated.itertuples()
        )
        plural = len(separated) > 1
        note = (
            f"; {named} {'have' if plural else 'has'} no fatal crash and "
            f"{'are' if plural else 'is'} not drawn"
        )
    years = coefficients[coefficients.predictor == "year"].level.astype(int)
    captions["s1_forest_fatal"] = _caption(
        "Odds ratios for at least one death in an injury crash, by crash circumstance, from a "
        "logistic regression that also includes the year, against reference levels (hollow "
        f"markers), with 95% intervals, Spain, {years.min()}–{years.max()}; zone and road "
        "type describe one location between them and are read together"
        + note
        + (
            "; levels that record a missing value are in the model but not drawn"
            if len(nuisance)
            else ""
        ),
        MICRODATA_SOURCE,
        f"{n_model:,} crashes",
    )

    adverse = summaries.read_model_table("q3_adverse_conditions")
    fatal = adverse[adverse.outcome == "fatal"].copy()
    plots.dot_interval_panels(
        fatal.assign(panel=fatal.level.map(str.capitalize)),
        "panel",
        "variant_label",
        "odds_ratio",
        "or_low",
        "or_high",
        figures_dir / "s2_adverse_conditions.svg",
        "Adverse conditions and a fatal outcome: the same odds ratio under "
        f"{fatal.variant.nunique()} models",
        order=list(dict.fromkeys(fatal.variant_label)),
        panel_order=[
            level.capitalize()
            for level in ("wet", "rain", "hail or snow", "at a junction")
            if level.capitalize() in set(fatal.level.map(str.capitalize))
        ],
        xlabel="Odds ratio against the reference level, log scale (dotted line: no difference)",
        reference=1.0,
        from_zero=False,
        shared=True,
        log=True,
    )
    captions["s2_adverse_conditions"] = _caption(
        "Odds ratios for at least one death in an injury crash under each adverse condition "
        f"shown, against its reference level, in the full model and {fatal.variant.nunique() - 1} "
        "variants that drop a correlated variable or fit one kind of road alone, Spain, "
        f"{years.min()}–{years.max()}, with 95% intervals; a missing row is a level the variant "
        "does not contain",
        MICRODATA_SOURCE,
        f"{n_model:,} crashes",
    )


# --------------------------------------------------------------------------- older drivers


# --------------------------------------------------------------------------- driver age per km

EMEF_SOURCE = "ATM, Idescat and Institut Metròpoli, Enquesta de mobilitat en dia feiner 2022–2024"
EDM_SOURCE = "CRTM, Encuesta Domiciliaria de Movilidad 2018 (Powered by CRTM)"
GROUP_LABELS = {
    "18-29": "18–29",
    "30-44": "30–44",
    "45-64": "45–64",
    "65+": "65 and over",
    "65-74": "65–74",
    "75+": "75 and over",
}


def _driver_exposure_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    """Involvement per kilometre by driver age, and deaths once involved, from the committed
    ``risk_*`` tables (``scripts/exposure_risk.py``)."""
    path = TABLES_DIR / "risk_national_rates.csv"
    if not path.exists():
        log.warning("risk_national_rates.csv missing: run scripts/exposure_risk.py national")
        return
    rates = pd.read_csv(path)
    rates = rates[rates.km_total == "less taxi and ride-hailing"]
    central = rates[rates.method.str.startswith("A:")].set_index("group")
    sensitivity = pd.read_csv(TABLES_DIR / "risk_national_sensitivity.csv")
    spread = sensitivity.groupby("group").involved_ratio.agg(["min", "max"])
    older = pd.read_csv(TABLES_DIR / "risk_older_sensitivity.csv")
    older_spread = {"65-74": older.ratio_65_74, "75+": older.ratio_75_plus}
    rows = []
    for group in ("18-29", "30-44", "45-64", "65+"):
        rows.append(
            {
                "label": GROUP_LABELS[group],
                "reference_row": group == "45-64",
                "value": float(central.loc[group, "involved_ratio"]),
                "low": float(central.loc[group, "involved_ratio_low"]),
                "high": float(central.loc[group, "involved_ratio_high"]),
                "range_low": float(spread.loc[group, "min"]),
                "range_high": float(spread.loc[group, "max"]),
            }
        )
    for group in ("65-74", "75+"):
        rows.append(
            {
                "label": f"{GROUP_LABELS[group]} (model-dependent)",
                "reference_row": False,
                "value": np.nan,
                "low": np.nan,
                "high": np.nan,
                "range_low": float(older_spread[group].min()),
                "range_high": float(older_spread[group].max()),
            }
        )
    plots.estimate_and_range(
        pd.DataFrame(rows),
        figures_dir / "dr1_involved_per_km.svg",
        "Car drivers involved in injury crashes per kilometre driven, against drivers aged "
        "45–64 (2024)",
        xlabel="Rate ratio per km against drivers aged 45–64 (log scale)",
        reference_label="45–64 rate",
        # The caption says what the estimate rests on and what the ranges cover.
        estimate_label="Estimate with 95% interval",
        range_label="Sensitivity range (see caption)",
    )
    captions["dr1_involved_per_km"] = _caption(
        "Car drivers involved in injury crashes in Spain in 2024 per kilometre driven by drivers "
        "of the same age, as ratios to drivers aged 45–64 (hollow marker); kilometres by age "
        "from the EMEF's working-day profile applied to Spain's population and scaled to DGT's "
        "car kilometres. "
        "The grey bands are sensitivity ranges, not intervals: other regional profiles, the "
        "licence-calibrated transfer, other treatments of trip distances, other survey years, "
        "professionals' work driving, the older sample's employment and the age mix of "
        "non-working days. The rows for 65–74 and 75 and over rest on assumptions splitting the "
        "65+ kilometres (Madrid survey ratios or licence holding) and carry no point estimate",
        f"{TABLES_SOURCE}; {EMEF_SOURCE}; {EDM_SOURCE}; {KM_2024_SOURCE}; {POPULATION_SOURCE}",
        f"{int(central.involved.sum()):,} drivers involved",
    )

    severity = pd.read_csv(TABLES_DIR / "risk_severity_and_licences.csv")
    severity = severity[severity.group != "65+"].assign(label=lambda f: f.group.map(GROUP_LABELS))
    plots.dot_interval(
        severity,
        "label",
        "killed_per_1000_involved",
        "killed_per_1000_involved_low",
        "killed_per_1000_involved_high",
        figures_dir / "dr2_killed_per_involved.svg",
        "Car drivers killed per 1,000 involved in an injury crash, by age (2024)",
        xlabel="Drivers killed within 30 days per 1,000 drivers involved",
        reference=float(severity.set_index("group").loc["45-64", "killed_per_1000_involved"]),
        reference_label="45–64 rate",
        keep_order=True,
        reference_row="45–64",
    )
    captions["dr2_killed_per_involved"] = _caption(
        "Private-car drivers who died within 30 days per 1,000 involved in an injury crash, by "
        "age, Spain, 2024, with 95% intervals; no measure of driving enters the rate",
        TABLES_SOURCE,
        f"{int(severity.involved.sum()):,} drivers involved",
    )


# --------------------------------------------------------------------------- vehicles


def _vehicle_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    rates = summary("q6_rates_2022")
    rates = rates[rates.zone == "all"]
    # Unrounded rates in the group order of the rates table, so the printed values round like the
    # page's table.
    slope_frame = rates[rates.measure == "fatal_involvement"][
        ["label", "per_100k_vehicles", "per_billion_km"]
    ]
    plots.slope(
        slope_frame,
        "label",
        "per_100k_vehicles",
        "per_billion_km",
        figures_dir / "v1_per_vehicle_vs_per_km.svg",
        "Vehicles in fatal crashes: the ranking per vehicle and per kilometre, 2022",
        "per 100,000 vehicles",
        "per billion km",
        highlight=["Motorcycles", "Trucks over 3,500 kg"],
    )
    # The caption says that only the top rank per kilometre is clear of the intervals below it.
    per_km = rates[rates.measure == "fatal_involvement"].sort_values(
        "per_billion_km", ascending=False
    )
    top, rest = per_km.iloc[0], per_km.iloc[1:]
    neighbours_overlap = (
        rest.per_billion_km_high.to_numpy()[1:] >= rest.per_billion_km_low.to_numpy()[:-1]
    )
    if not (top.per_billion_km_low > rest.per_billion_km_high.max() and neighbours_overlap.any()):
        raise ValueError("v1 caption: the per-km ranking no longer has one clear leader")
    captions["v1_per_vehicle_vs_per_km"] = _caption(
        "Vehicles of each type involved in fatal crashes (deaths within 30 days) per 100,000 "
        "circulating vehicles (left) and per billion vehicle-kilometres (right), Spain, 2022. "
        "The vertical position shows the rank only; each rate is printed beside its point. Per "
        f"kilometre only the lead of {str(top.label).lower()} is clear of the 95% intervals of "
        "the types below, some of which overlap (intervals and counts by type in the rates "
        "table)",
        f"{TABLES_SOURCE}; {KM_SOURCE}",
        f"{int(per_km['count'].sum()):,} vehicles in fatal crashes",
    )


# --------------------------------------------------------------------------- policy


def _policy_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    points = policy.INTERVENTIONS["points_licence"]
    series = summary("q8_points_series")
    series["period"] = pd.to_datetime(series.period)
    # The lower panel enlarges the months around the change, from the January of the year before.
    zoom_from = pd.Timestamp(year=points.date.year - 1, month=1, day=1)
    after = series[series.period >= points.date]
    if not (after.counterfactual_linear > after.counterfactual_main).all():
        raise ValueError("p1 caption: the straight-line projection no longer gives the larger drop")
    break_label = f"{points.date.day} {points.date:%B %Y}"
    plots.intervention(
        series,
        "period",
        "deaths",
        "fitted_main",
        "counterfactual_main",
        figures_dir / "p1_points_series.svg",
        "Monthly road deaths around the points-based licence, "
        f"{series.period.min().year}–{series.period.max().year}",
        points.date,
        break_label,
        ylabel="Deaths (30 days)",
        # One name for each line, the same in the legend, the caption and the page.
        names={
            "observed": "Observed deaths",
            "fitted": "Fitted model",
            "counterfactual": "Projection without the change, preferred pre-trend",
        },
        alternative=(
            "counterfactual_linear",
            "Projection without the change, straight-line pre-trend",
        ),
        zero_based=False,
        zoom_from=zoom_from,
    )
    captions["p1_points_series"] = _caption(
        "Monthly road deaths within 30 days, Spain, "
        f"{series.period.min():%B %Y} to {series.period.max():%B %Y} (top) and enlarged from "
        f"{zoom_from:%B %Y} (bottom), with the fitted model, a segmented regression, and from "
        f"{break_label} two projections without the change: the preferred pre-trend (dashed) "
        "and a straight-line pre-trend (dotted), which gives the larger drop. The value axes do "
        "not start at zero. The projections are drawn without intervals; the intervals of the "
        "step and of the average change are given in the text and in the table of every "
        "specification",
        SERIES_SOURCE,
        f"{int(series.deaths.sum()):,} deaths",
    )

    placebo = summary("q8_points_calendar_placebo")
    placebo["label"] = pd.to_datetime(placebo.break_date).dt.strftime("%Y")
    # The Julys whose windows hold the change are left out of the placebos; a note row stands in
    # each run of them, so the axis does not read as consecutive years.
    years = pd.to_datetime(placebo.break_date).dt.year
    pre, post = policy.CALENDAR_PRE_MONTHS, points.post_months
    missing = sorted(set(range(years.min(), years.max() + 1)) - set(years))
    holds_change = [
        pd.Timestamp(year=year, month=7, day=1) - pd.DateOffset(months=pre)
        <= points.date
        < pd.Timestamp(year=year, month=7, day=1) + pd.DateOffset(months=post)
        for year in missing
    ]
    if not missing or not all(holds_change):
        raise ValueError("p2: the Julys left out are no longer those whose window holds the change")
    left_out = _year_runs(missing)
    notes = pd.DataFrame(
        {
            "label": [f"{run}: left out" for run in left_out],
            "year": [int(run[:4]) for run in left_out],
            "is_true": False,
        }
    )
    placebo = (
        pd.concat([placebo.assign(year=years), notes], ignore_index=True)
        .sort_values("year", kind="stable")
        .reset_index(drop=True)
    )
    plots.dot_interval(
        placebo,
        "label",
        "level_change",
        "low",
        "high",
        figures_dir / "p2_july_placebos.svg",
        "The July break estimated at every July the licence cannot explain",
        xlabel="Estimated level change at 1 July (95% interval)",
        percent=True,
        reference=0.0,
        highlight="is_true",
        keep_order=True,
    )
    captions["p2_july_placebos"] = _caption(
        "Estimated change in the level of monthly deaths at 1 July 2006 and at every other "
        f"July of {years.min()}–{years.max()} whose window avoids July 2006 and the pandemic, "
        f"each from the same segmented regression on {pre} months before and {post} after, Spain, "
        "with model-based 95% intervals, which these placebos show to be too narrow; the "
        f"filled marker is July 2006. The Julys of {_join_words(left_out)} are left out because "
        "their windows include July 2006",
        SERIES_SOURCE,
        f"{int(placebo.n_fits.dropna().iloc[0])} fits",
    )


# --------------------------------------------------------------------------- data


# The fields of DGT's crash records in the missing-values chart, in English; the table of missing
# values keeps DGT's field names. The right-of-way flags (``codes.PRIORI_COLUMNS``) share one row.
MISSINGNESS_FIELDS = {
    "DIA_SEMANA": "Day of the week",
    "COD_PROVINCIA": "Province",
    "COD_MUNICIPIO": "Municipality",
    "ISLA": "Island",
    "ZONA": "Zone",
    "ZONA_AGRUPADA": "Interurban or urban",
    "CARRETERA": "Road number",
    "KM": "Kilometre post",
    "CARRETERA_CRUCE": "Crossing road",
    "SENTIDO_1F": "Direction of travel",
    "TITULARIDAD_VIA": "Road owner",
    "TIPO_VIA": "Road type",
    "TIPO_ACCIDENTE": "Crash type",
    "NUDO": "At a junction or not",
    "NUDO_INFO": "Junction type",
    "CONDICION_NIVEL_CIRCULA": "Traffic level",
    "CONDICION_FIRME": "Road surface",
    "CONDICION_ILUMINACION": "Lighting",
    "CONDICION_METEO": "Weather",
    "CONDICION_NIEBLA": "Fog",
    "CONDICION_VIENTO": "Strong wind",
    "VISIB_RESTRINGIDA_POR": "Restricted visibility",
    "ACERA": "Pavement",
    "TRAZADO_PLANTA": "Road alignment",
}
# The right-of-way flags are drawn as one row only while their shares stay this close together.
PRIORITY_SPREAD = 0.01
# Optional fields whose empty cells DGT's dictionary does not define, named in the caption as
# fields where an empty cell may also mean there was nothing to record; each is empty in most
# crashes.
OPTIONAL_FIELDS = ("CONDICION_NIEBLA", "KM", "NUDO_INFO")


def empty_means(column: str) -> str | None:
    """What DGT's dictionary says an empty cell of ``column`` means: ``"not applicable"`` where
    it labels an empty cell "No aplica" (the island field), ``"no"`` where it codes absence as
    '.' (the strong-wind field, whose files leave that cell empty), otherwise None."""
    labels = codes.load_dictionary().get(column, {})
    if labels.get("", "").strip().lower() == "no aplica":
        return "not applicable"
    if "." in labels:
        return "no"
    return None


def priority_row(count: int) -> str:
    return f"Right of way, {count} flags"


def recorded_where_applicable(profile: pd.DataFrame) -> pd.DataFrame:
    """Field × year share of crashes with a value recorded, among the crashes the field applies
    to, from the missing-values table (``missingness_by_year``), as the chart draws it.

    A value is not applicable, and is left out, when it is coded 998, when it is a non-coded
    field's own "not applicable" placeholder (both in ``share_not_applicable``), or when the cell
    is empty in a field whose dictionary defines an empty cell as not applicable. An empty cell
    in a field whose dictionary codes absence as '.' is the recorded "no". Every other empty
    cell, 999, an explicit unknown code and the placeholders count as missing. The right-of-way
    flags are one row, their mean, and the rows run from the most completely recorded down.
    """
    meaning = profile.column.map(empty_means)
    not_applicable = profile.share_not_applicable + profile.share_empty.where(
        meaning.eq("not applicable"), 0.0
    )
    recorded = profile.share_observed + profile.share_empty.where(meaning.eq("no"), 0.0)
    applies = 1 - not_applicable
    shares = profile.assign(share=(recorded / applies).where(applies > 0))
    matrix = shares.pivot(index="column", columns="year", values="share")
    priority = matrix[matrix.index.isin(codes.PRIORI_COLUMNS)]
    unnamed = set(matrix.index) - set(MISSINGNESS_FIELDS) - set(priority.index)
    if unnamed:
        raise ValueError(f"d1: no English name for the fields {sorted(unnamed)}")
    if len(priority):
        if ((priority.max() - priority.min()) >= PRIORITY_SPREAD).any():
            raise ValueError("d1: the right-of-way flags are no longer recorded together")
        matrix = matrix.drop(index=priority.index)
        matrix.loc[priority_row(len(priority))] = priority.mean()
    matrix = matrix.rename(index=MISSINGNESS_FIELDS)
    means = matrix.mean(axis=1).round(6)
    return matrix.loc[sorted(matrix.index, key=lambda row: (-means[row], row))]


def _data_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    profile = pd.read_csv(TABLES_DIR / "missingness_by_year.csv")
    matrix = recorded_where_applicable(profile)
    plots.missingness_heatmap(
        matrix,
        figures_dir / "d1_missingness.svg",
        "Share of crashes with a value recorded where the field applies, by field and year",
    )
    columns = sorted(set(profile.column))
    meaning = {column: empty_means(column) for column in columns}
    empty_na = [MISSINGNESS_FIELDS[c].lower() for c in columns if meaning[c] == "not applicable"]
    empty_no = [MISSINGNESS_FIELDS[c].lower() for c in columns if meaning[c] == "no"]
    optional = profile[profile.column.isin(OPTIONAL_FIELDS)].groupby("column").share_empty.mean()
    if (
        len(empty_na) != 1
        or len(empty_no) != 1
        or len(optional) != len(OPTIONAL_FIELDS)
        or not (optional > 0.5).all()
        or any(meaning[c] for c in OPTIONAL_FIELDS)
    ):
        raise ValueError("d1 caption: the fields whose empty cells it describes have changed")
    priority = profile[profile.column.isin(codes.PRIORI_COLUMNS)].column.nunique()
    optional_names = _join_words([MISSINGNESS_FIELDS[c].lower() for c in OPTIONAL_FIELDS])
    captions["d1_missingness"] = _caption(
        "Share of crashes with a value recorded in each field of the DGT crash records, among "
        f"the crashes the field applies to, by year, Spain, {int(profile.year.min())}–"
        f"{int(profile.year.max())}. A value is not applicable, and is left out, when it is 998 "
        "(not applicable), when the road is 'No inventariada' (no road number), or when the "
        f"{empty_na[0]} field is empty, which DGT's dictionary defines as not applicable. An "
        f"empty cell in the {empty_no[0]} field is the dictionary's code for no {empty_no[0]} "
        "and counts as recorded. A value is missing when it is 999 (not specified), an "
        "explicit unknown code, a placeholder (kilometre post 9999, and 1000 in 2019; "
        "municipality 00000) or any other empty cell, although in optional fields "
        f"({optional_names}) an empty cell may also mean there was nothing to record. The "
        f"{priority} right-of-way flags, recorded together, share one row",
        MICRODATA_SOURCE,
        f"{int(profile.groupby('year').rows.first().sum()):,} crashes",
    )


# --------------------------------------------------------------------------- severity calculator


def _severity_calculator_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    """Predicted against observed for the Catalan severity model, the published model behind the
    calculator, on years it was not fitted on."""
    path = TABLES_DIR / "sev_calibration.csv"
    if not path.exists():
        log.warning("sev_calibration.csv missing: run scripts/severity_calculator.py calculator")
        return
    groups = pd.read_csv(path)
    groups = groups[groups.estimator.isin(["calculator", "road_x_crash_table"])]
    plots.calibration_comparison(
        groups,
        figures_dir / "sev1_predicted_observed.svg",
        "Predicted and observed: the share of severe crashes that were fatal",
        {"calculator": "the model", "road_x_crash_table": "a table by road and crash type"},
        xlabel="Predicted chance that the crash was fatal (average in the group)",
        ylabel="Share of the crashes that were fatal",
    )
    model = groups[groups.estimator == "calculator"]
    captions["sev1_predicted_observed"] = _caption(
        "Crashes in Catalonia in which someone was killed or seriously injured, 2016–2023, on "
        "the roads the calculator offers. Each year was predicted by a model fitted only on the "
        "years before it. The crashes are split into ten equal groups by the model's prediction "
        f"(about {int(model.n.median()):,} crashes each), and separately by the table's. Each dot "
        "is the share of a group's crashes that were fatal (someone died within 24 hours), with "
        "its 95% interval, against the group's average prediction",
        "Servei Català de Trànsit, crashes with a death or serious injury",
        int(model.n.sum()),
    )
