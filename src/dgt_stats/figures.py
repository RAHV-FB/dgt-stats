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

import pandas as pd

from dgt_stats import agebands, driver_risk, factors, plots, policy, summaries
from dgt_stats.microdata import charts as microdata_charts
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR

CAPTIONS_PATH = FIGURES_DIR / "captions.json"
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

# Panel titles for the four-denominator contrast, short enough to sit over a panel.
CONTRAST_PANELS = {
    "residents": "Per resident",
    "b_permit_holders": "Per B-permit holder",
    "drivers_involved": "Per driver involved",
    "kilometres": "Per km of cars\nof owners this age",
}

SPEED_STATUS_LABELS = {
    "speed_infraction": "Speed infraction recorded",
    "too_slow": "Driving too slowly",
    "none": "No speed infraction recorded",
    "unknown": "No speed status recorded",
}


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


def build_all(
    figures_dir: Path = FIGURES_DIR, frames: dict[str, pd.DataFrame] | None = None
) -> dict[str, str]:
    """Write every figure as SVG and return ``{figure name: caption}``; also saves captions.json.

    ``frames`` are the summaries by registry name; when omitted they are computed here.
    """
    frames = frames if frames is not None else {}

    def summary(name: str) -> pd.DataFrame:
        if name not in frames:
            frames[name] = summaries.SUMMARIES[name]()
        return frames[name].copy()

    figures_dir.mkdir(parents=True, exist_ok=True)
    captions: dict[str, str] = {}
    _trend_figures(figures_dir, captions, summary)
    _long_run_figures(figures_dir, captions, summary)
    _season_figures(figures_dir, captions, summary)
    _forecast_figures(figures_dir, captions, summary)
    _sex_figures(figures_dir, captions, summary)
    _factor_figures(figures_dir, captions, summary)
    _speed_status_figure(figures_dir, captions, summary)
    if summaries.model_tables_present():
        _severity_figures(figures_dir, captions)
    else:
        log.warning("model tables missing: run scripts/model.py to get the severity figures")
    _age_figures(figures_dir, captions, summary)
    _vehicle_figures(figures_dir, captions, summary)
    _policy_figures(figures_dir, captions, summary)
    _data_figures(figures_dir, captions)
    # The regional crash-record figures (Catalonia, Barcelona, models, generalisability); skipped
    # when the microdata tables are not built.
    microdata_charts.build(figures_dir, captions)

    target = figures_dir / CAPTIONS_PATH.name
    target.write_text(json.dumps(captions, indent=2, ensure_ascii=False), encoding="utf-8")
    stale = sorted(path.name for path in figures_dir.glob("*.svg") if path.stem not in captions)
    for name in stale:
        (figures_dir / name).unlink()
        log.info("removed stale figure %s", name)
    return captions


# --------------------------------------------------------------------------- context


def _speed_status_figure(figures_dir: Path, captions: dict[str, str], summary) -> None:
    shares = summary("q9_infraction_shares")
    block = shares[shares.zone == "all"]
    long = block.melt(
        id_vars="year",
        value_vars=list(SPEED_STATUS_LABELS),
        var_name="status",
        value_name="drivers",
    )
    long["status"] = long.status.map(SPEED_STATUS_LABELS)
    plots.bar_shares(
        long,
        "year",
        "status",
        "drivers",
        figures_dir / "c3_speed_status.svg",
        "Drivers in injury crashes by recorded speed status, all roads",
        order=list(SPEED_STATUS_LABELS.values()),
    )
    captions["c3_speed_status"] = _caption(
        "Drivers involved in injury crashes by the police record of a speed infraction, Spain, "
        f"all roads, {int(block.year.min())}–{int(block.year.max())}; the share with no speed "
        "status recorded changes in 2016, which shifts every share below it",
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
    )
    captions["r1_risk_change"] = _caption(
        f"Each outcome's {last} rate as a ratio to its {base} rate, under every denominator it "
        "can be paired with, Spain, all roads, with 95% intervals that allow for ordinary "
        "year-to-year variation; road fuel sold stands in for distance driven",
        f"{SERIES_SOURCE}; {POPULATION_SOURCE}; {CENSUS_SOURCE}; {VEHICLE_FLEET_SOURCE}; "
        f"{FUEL_SOURCE}",
    )


def _long_run_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    series = summary("longrun_series")
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
        last_fitted=2019,
        order=order,
        ylabel="Deaths (30 days)",
    )
    zoom = series[series.year >= 2010].assign(
        ratio_low=lambda f: f.observed / f.high, ratio_high=lambda f: f.observed / f.low
    )
    plots.line_series(
        zoom,
        "year",
        "ratio",
        figures_dir / "l2_observed_over_trend.svg",
        "Observed deaths as a share of the pre-pandemic trend, 2010–2024",
        series="measure_label",
        ylabel="Observed ÷ trend",
        zero_based=False,
        reference=1.0,
        band=("ratio_low", "ratio_high"),
        end_labels=False,
    )
    sources = f"{SERIES_SOURCE}; {VEHICLE_FLEET_SOURCE}; {FUEL_SOURCE}"
    captions["l2_observed_over_trend"] = _caption(
        "Observed deaths within 30 days as a ratio to the pre-pandemic trend of each measure "
        "(fitted to 2019, projected from 2020), with the range allowed by the trend's 95% "
        f"prediction interval shaded, Spain, {int(zoom.year.min())}–{int(zoom.year.max())}; "
        "1 means on trend",
        sources,
    )
    fuel = series[series.measure == "road_fuel"]
    fuel_note = f" (road fuel from {int(fuel.year.min())})" if not fuel.empty else ""
    captions["l1_trend_projection"] = _caption(
        f"Deaths within 30 days, Spain, {int(series.year.min())}–{int(series.year.max())}"
        f"{fuel_note}, against segmented trends fitted up to 2019 and projected from 2020 under "
        "three measures, with 95% prediction intervals; the trends of the two rates are "
        "converted back into deaths",
        sources,
    )

    check = summary("longrun_km_check")
    fit_first = int(check.year.min())
    coverage = summary("longrun_km_coverage")
    outside = (
        f"{coverage.outside_share.min() * 100:.1f}% to {coverage.outside_share.max() * 100:.1f}%"
    )
    covered = f"{int(coverage.year.min())}–{int(coverage.year.max())}"
    check = check[check.year >= 2010].assign(
        ratio_low=lambda f: f.observed / f.high, ratio_high=lambda f: f.observed / f.low
    )
    plots.line_series(
        check,
        "year",
        "ratio",
        figures_dir / "l4_km_against_fuel.svg",
        "Interurban deaths against the pre-pandemic trend: per measured kilometre, and over "
        "national road fuel as a check",
        series="measure_label",
        ylabel="Observed ÷ trend",
        zero_based=False,
        reference=1.0,
        band=("ratio_low", "ratio_high"),
        end_labels=False,
    )
    captions["l4_km_against_fuel"] = _caption(
        f"Interurban deaths within 30 days as a ratio to a trend fitted to {fit_first}–2019 and "
        "projected from 2020, per measured vehicle-kilometre and, as a check, over national "
        "road fuel sold, with 95% prediction intervals shaded, Spain, "
        f"{int(check.year.min())}–{int(check.year.max())}; the kilometres leave out roads run "
        f"by municipalities and other bodies, which account for {outside} of interurban deaths "
        f"({covered})",
        f"{SERIES_SOURCE}; {FUEL_SOURCE}; {ROAD_TRAFFIC_SOURCE}",
    )

    split = summary("risk_frequency_severity")
    labels = {
        "deaths_per_fuel_index": "Deaths per tonne of fuel",
        "frequency_index": "Injury crashes per tonne of fuel (how often)",
        "severity_index": "Deaths per injury crash (how deadly)",
    }
    long = split.melt(
        id_vars="year", value_vars=list(labels), var_name="measure", value_name="index"
    ).assign(measure_label=lambda f: f.measure.map(labels))
    base = int(split.year.min())
    plots.line_series(
        long,
        "year",
        "index",
        figures_dir / "l3_frequency_severity.svg",
        f"Deaths per unit of traffic, split into how often and how deadly ({base} = 100)",
        series="measure_label",
        ylabel=f"Index, {base} = 100",
        reference=100,
        end_labels=False,
    )
    captions["l3_frequency_severity"] = _caption(
        "Deaths within 30 days per tonne of road fuel sold (petrol plus diesel) and its two "
        "factors, injury crashes per tonne and deaths per injury crash, indexed to "
        f"{base} = 100, Spain, all roads, {base}–{int(split.year.max())}; how completely slight "
        "injuries are recorded moves the split between the two factors but not their product",
        f"{SERIES_SOURCE}; {FUEL_SOURCE}",
    )


# --------------------------------------------------------------------------- forecasts


def _forecast_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    backtest = summary("forecast_backtest")
    national = backtest[backtest.outcome == "deaths_all"]
    labels = {
        "observed": "Deaths",
        "model": "Model forecast",
        "naive_last_year": "Last year's count",
    }
    long = national.melt(
        id_vars="year", value_vars=list(labels), var_name="series", value_name="deaths"
    ).assign(series_label=lambda f: f.series.map(labels))
    first, last = int(national.year.min()), int(national.year.max())
    plots.line_series(
        long,
        "year",
        "deaths",
        figures_dir / "k1_forecast_check.svg",
        "Each year's deaths against two forecasts made before it",
        series="series_label",
        ylabel="Deaths (30 days), all roads",
        zero_based=True,
        end_labels=False,
    )
    captions["k1_forecast_check"] = _caption(
        f"Road deaths within 30 days in each year, Spain, {first}–{last}, against two "
        "forecasts made from the four years before it: a regression of monthly deaths on "
        "season, trend, road fuel and weekend days, and the previous year's count; the model "
        "was chosen on the forecasts of 2006–2015 alone",
        f"{SERIES_SOURCE}; {FUEL_SOURCE}",
    )
    detect = summary("forecast_detectability")
    plots.line_series(
        detect.assign(mde_pct=lambda f: f.mde),
        "horizon",
        "mde_pct",
        figures_dir / "k2_detectability.svg",
        "The fall in deaths a comparison detects four times in five, by years summed",
        series="outcome_label",
        ylabel="Fall detected 4 times in 5",
        percent=True,
        end_labels=True,
    )
    captions["k2_detectability"] = _caption(
        "The fall in deaths, summed over the years after a change (horizontal axis), that a "
        "comparison with the model's forecast detects four times in five (80% power at the 5% "
        "level), Spain, by zone; it allows for chance and for the forecast's own error, "
        "measured on 2006–2024 without the pandemic years",
        f"{SERIES_SOURCE}; {FUEL_SOURCE}",
    )


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
    )
    effects = summary("season_month_effects")
    pooled = [int(year) for year in str(effects.years.iloc[0]).split()]
    left_out = sorted(set(range(min(pooled), max(pooled) + 1)) - set(pooled))
    years = f"{min(pooled)}–{max(pooled)} ({', '.join(str(y) for y in left_out)} left out)"
    captions["m1_season_profile"] = _caption(
        "Deaths within 30 days, road fuel sold (petrol plus diesel), petrol sold and "
        "toll-motorway traffic per kilometre by month, each divided by its year's mean month "
        f"and averaged over {years}, Spain; petrol and toll motorways cover only part of all "
        "traffic",
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
    )
    captions["m2_month_effects"] = _caption(
        "Deaths within 30 days in each month against the average month of the same year, raw "
        f"and per tonne of road fuel sold, Spain, {years}, with 95% intervals",
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
        "Men against women, car drivers: crashing, and dying (2022–2024)",
        order=list(dict.fromkeys(cars.band_label)),
        panel_order=list(short.values()),
        xlabel="Ratio, men to women (dotted line: the same rate)",
        reference=1.0,
    )
    rates_table = summary("drivers_sex_rates")
    adults = rates_table[(rates_table.scope == "car") & (rates_table.band == "18+")]
    captions["a3_sex_ratios"] = _caption(
        "Men's rates divided by women's among car drivers, by age: involvement in injury "
        "crashes and death within 30 days per licence holder, and death per driver involved, "
        "Spain, 2022–2024 pooled, with 95% intervals; no source records kilometres by sex",
        f"{TABLES_SOURCE}; {CENSUS_SOURCE}",
        f"{int(adults.drivers_involved.sum()):,} drivers involved",
    )


def _factor_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    pooled = summary("speed_severity_pooled")
    shown = pooled.assign(
        label=pooled.road_type_label.where(
            pooled.road_type != "adjusted", "All roads, adjusted for road type and year"
        )
    )
    plots.dot_interval(
        shown,
        "label",
        "rate_ratio",
        "ratio_low",
        "ratio_high",
        figures_dir / "f1_speed_severity.svg",
        "Deaths per crash when speed is recorded, against other crashes",
        xlabel="Ratio of deaths per 100 crashes (dotted line: the same)",
        reference=1.0,
        keep_order=True,
    )
    captions["f1_speed_severity"] = _caption(
        "Deaths within 30 days per 100 injury crashes in which the police recorded "
        "inappropriate speed, as a ratio to the same rate in the other injury crashes on the "
        "same type of road, Spain outside Catalonia and the Basque Country, 2016–2023 pooled, "
        "with 95% intervals",
        f"{SPEED_REPORT_SOURCE}; {MICRODATA_SOURCE}",
        f"{int(pooled.speed_crashes.sum()):,} speed-related crashes",
    )

    shares = summary("factor_shares")
    shares = shares[shares.zone != "all"]
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
        "the Basque Country, 2014–2023; a line breaks where the share rises by more than "
        f"{factors.BREAK_RATIO - 1:.0%} or falls by more than {1 - 1 / factors.BREAK_RATIO:.0%} "
        f"in a year, or a year has fewer than {factors.MIN_CRASHES} crashes",
        SPEED_REPORT_SOURCE,
    )


# --------------------------------------------------------------------------- severity


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
        level=lambda f: f.level.astype(str).map(_ranges)
    )
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
        f"markers), with 95% intervals, Spain, {years.min()}–{years.max()}"
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
        xlabel="Odds ratio against the reference level (dotted line: no difference)",
        reference=1.0,
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


def _age_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    rates = summary("q7_km_rates")
    reference = rates[rates.band == driver_risk.REFERENCE_BAND].iloc[0]
    # Deaths per driver involved need no measure of distance, so they are drawn as points with
    # their intervals; the per-km ratios depend on the owner-age kilometres and are given on the
    # page as ranges rather than drawn as points.
    plots.dot_interval(
        rates.assign(label=[agebands.band_label(band) for band in rates.band]),
        "label",
        "deaths_per_1000_involved",
        "deaths_per_1000_involved_low",
        "deaths_per_1000_involved_high",
        figures_dir / "a1_killed_per_involved.svg",
        "Car drivers killed per 1,000 involved in an injury crash, by age (2024)",
        xlabel="Drivers killed within 30 days per 1,000 drivers involved",
        reference=float(reference.deaths_per_1000_involved),
        reference_label=agebands.band_label(driver_risk.REFERENCE_BAND),
        keep_order=True,
    )
    captions["a1_killed_per_involved"] = _caption(
        "Car drivers who died within 30 days per 1,000 car drivers involved in an injury crash, "
        "by age band, Spain, 2024, with 95% intervals; the dotted line is the rate at 35–54, and "
        "no estimate of distance driven enters the rate",
        TABLES_SOURCE,
        f"{int(rates.drivers_involved.sum()):,} drivers involved",
    )

    contrast = summary("q7_denominator_contrast")
    plots.dot_interval_panels(
        contrast.assign(panel=contrast.denominator.map(CONTRAST_PANELS)),
        "panel",
        "band_label",
        "ratio",
        "low",
        "high",
        figures_dir / "a2_denominator_contrast.svg",
        "The same car-driver deaths, four denominators: each band against 35–54 (2024)",
        order=[agebands.band_label(band) for band in dict.fromkeys(contrast.band)],
        panel_order=[CONTRAST_PANELS[key] for key in dict.fromkeys(contrast.denominator)],
        xlabel="Rate ratio against drivers aged 35–54 (dotted line: the same rate)",
        reference=1.0,
    )
    captions["a2_denominator_contrast"] = _caption(
        "Car-driver deaths within 30 days by age band, per resident, per holder of a B (car) "
        "permit, per car driver involved in an injury crash and per kilometre driven by cars "
        "registered to owners of the band, as ratios to drivers aged 35–54, Spain, 2024, with "
        "95% intervals; the numerator is the same in every panel, and 18–24 is left out because "
        "INE groups residents as 15–19 and 20–24",
        f"{TABLES_SOURCE}; {KM_2024_SOURCE}; {POPULATION_SOURCE}; {CENSUS_SOURCE}",
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
    )
    captions["v1_per_vehicle_vs_per_km"] = _caption(
        "Vehicles of each type involved in fatal crashes (deaths within 30 days) per 100,000 "
        "circulating vehicles (left) and per billion vehicle-kilometres (right), Spain, 2022; "
        "the lines show how each type's rank changes with the denominator",
        f"{TABLES_SOURCE}; {KM_SOURCE}",
    )


# --------------------------------------------------------------------------- policy


def _policy_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    points = policy.INTERVENTIONS["points_licence"]
    series = summary("q8_points_series")
    series["period"] = pd.to_datetime(series.period)
    plots.intervention(
        series,
        "period",
        "deaths",
        "fitted_main",
        "counterfactual_main",
        figures_dir / "p1_points_series.svg",
        "Monthly road deaths around the points-based licence, 2000–2007",
        points.date,
        "1 July 2006",
        ylabel="Deaths (30 days)",
        alternative=("counterfactual_linear", "Counterfactual, one straight pre-trend"),
    )
    captions["p1_points_series"] = _caption(
        "Monthly road deaths within 30 days, Spain, "
        f"{series.period.min():%B %Y} to {series.period.max():%B %Y}, with a fitted segmented "
        "regression and two counterfactuals without the points-based licence of 1 July 2006: "
        "the fitted model with its change set to zero, and the same with one straight "
        "pre-trend, which gives the larger drop",
        SERIES_SOURCE,
        f"{int(series.deaths.sum()):,} deaths",
    )

    placebo = summary("q8_points_calendar_placebo")
    placebo["label"] = pd.to_datetime(placebo.break_date).dt.strftime("%Y")
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
    july = pd.to_datetime(placebo.break_date).dt.year
    captions["p2_july_placebos"] = _caption(
        "Estimated change in the level of monthly deaths at 1 July 2006 and at every other "
        f"July of {july.min()}–{july.max()} whose window avoids July 2006 and the pandemic, "
        "each from the same segmented regression on 60 months before and 17 after, Spain, "
        "with 95% intervals; the filled marker is July 2006",
        SERIES_SOURCE,
        f"{int(placebo.n_fits.iloc[0])} fits",
    )


# --------------------------------------------------------------------------- data


def _data_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    profile = pd.read_csv(TABLES_DIR / "missingness_by_year.csv")
    plots.missingness_heatmap(
        profile,
        figures_dir / "d1_missingness.svg",
        "Share of crashes with a value recorded, by field and year",
    )
    captions["d1_missingness"] = _caption(
        "Share of crashes with a value recorded in each field of the DGT crash records, by "
        f"year, Spain, {int(profile.year.min())}–{int(profile.year.max())}; a value counts as "
        "missing when it is empty, 999 (not specified), 998 (not applicable), an explicit "
        "unknown code or a placeholder (KM 9999, and 1000 in 2019; CARRETERA 'No "
        "inventariada'; COD_MUNICIPIO 00000)",
        MICRODATA_SOURCE,
        f"{int(profile.groupby('year').rows.first().sum()):,} crashes",
    )
