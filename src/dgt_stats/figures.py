"""Figure recipes: which summary feeds which chart, with the caption each figure carries.

Eleven figures, one per idea. A figure earns its place by showing something a sentence cannot:
a ranking that reverses, a distribution a single estimate has to be read against, a discontinuity
in the data themselves. Tables that a figure already says are not drawn twice; they are written
to ``reports/tables`` and linked from the page as CSV.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from dgt_stats import agebands, plots, policy, summaries
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
TRAFFIC_SOURCE = (
    "CORES, consumo de productos petrolíferos; Ministerio de Transportes y Movilidad Sostenible, "
    "tráfico en autopistas estatales de peaje"
)
THIRTY_DAY = "deaths within 30 days of the crash"

# The three rates the older-driver page separates, in the order they are read.
AGE_RATE_PANELS = {
    "involved_per_bn_km": "Involved per billion km",
    "deaths_per_1000_involved": "Killed per 1,000 involved",
    "deaths_per_bn_km": "Killed per billion km",
}

SPEED_STATUS_LABELS = {
    "speed_infraction": "Speed infraction recorded",
    "too_slow": "Driving too slowly",
    "none": "No speed infraction recorded",
    "unknown": "No speed status recorded",
}


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
    captions["c3_speed_status"] = plots.caption(
        TABLES_SOURCE,
        "2014–2024",
        "drivers involved in injury crashes by the police's record of a speed infraction "
        "(yearbook tables 6.1); the top band is the share for which no judgement was recorded at "
        "all, which changes in 2016 and changes the meaning of every share below it",
        f"{int(block.total.sum()):,} drivers",
    )


# --------------------------------------------------------------------------- counts and risk


SHORT_DENOMINATORS = {
    "count": "Count",
    "residents": "Per resident",
    "licence_holders": "Per licence holder",
    "vehicles": "Per registered vehicle",
    "road_fuel": "Per unit of road fuel",
}


def _trend_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    index = summary("risk_index")
    last = int(index.year.max())
    latest = index[index.year == last].assign(
        denominator_short=lambda f: f.denominator.map(SHORT_DENOMINATORS)
    )
    plots.dot_interval_panels(
        latest,
        "outcome_label",
        "denominator_short",
        "ratio_to_base",
        "ratio_low",
        "ratio_high",
        figures_dir / "r1_risk_change.svg",
        f"{last} against 2019: the same outcomes under five denominators",
        order=list(SHORT_DENOMINATORS.values()),
        panel_order=list(dict.fromkeys(latest.outcome_label)),
        xlabel=f"Ratio, {last} to 2019 (dotted line: no change)",
        reference=1.0,
        from_zero=False,
    )
    captions["r1_risk_change"] = plots.caption(
        f"{SERIES_SOURCE}; {POPULATION_SOURCE} (1 July); {CENSUS_SOURCE}; DGT registered "
        f"vehicle fleet; {FUEL_SOURCE}",
        f"2019 and {last}, all roads",
        "each outcome divided by each denominator in turn, as the ratio of the "
        f"{last} rate to the 2019 rate, with 95% log-normal intervals that treat both counts as "
        "Poisson and the denominators as known; count is the outcome with no denominator; road "
        "fuel is automotive petrol plus diesel in tonnes, a proxy for vehicle-kilometres; each "
        "panel has its own scale",
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
    segments = summary("longrun_segments")
    breaks = {
        label: ", ".join(str(int(v)) for v in group.start.iloc[1:])
        for label, group in segments.groupby("measure_label", sort=False)
    }
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
    captions["l2_observed_over_trend"] = plots.caption(
        f"{SERIES_SOURCE}; DGT registered vehicle fleet; {FUEL_SOURCE}",
        "2010–2024",
        "30-day deaths divided by the fitted (to 2019) or projected (from 2020) trend of each "
        "measure; 1 means on trend; shaded: the range of the ratio that the trend's 95% "
        "prediction interval allows, which is narrow where the trend was fitted and widens as "
        "the projection runs on",
    )
    captions["l1_trend_projection"] = plots.caption(
        f"{SERIES_SOURCE}; DGT registered vehicle fleet; {FUEL_SOURCE}",
        "1993–2024 (road fuel from 1996)",
        "segmented log-linear (joinpoint) quasi-Poisson trends fitted to 30-day deaths up to 2019, "
        "turning points chosen by QBIC ("
        + "; ".join(f"{label.lower()}: {years}" for label, years in breaks.items())
        + "); the per-vehicle and per-fuel trends are multiplied back by each year's fleet or "
        "fuel so that all three panels are in deaths; shaded: 95% prediction interval of the "
        "projection",
    )


def _season_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    profile = summary("season_profile_long")
    plots.month_lines(
        profile,
        "series_label",
        "index",
        figures_dir / "m1_season_profile.svg",
        "Deaths and three measures of traffic by month (average month = 100)",
        order=list(dict.fromkeys(profile.series_label)),
        reference=100,
    )
    years = "2014–2019 and 2022–2024"
    captions["m1_season_profile"] = plots.caption(
        f"{SERIES_SOURCE}; {TRAFFIC_SOURCE}",
        f"{years} (2020 and 2021 left out)",
        "each month's 30-day deaths, road fuel (petrol plus diesel), petrol alone and toll-motorway "
        "average daily traffic per kilometre, divided by the mean month of the same year and "
        "averaged across years",
    )

    effects = summary("season_month_effects")
    short = {
        "none": "Raw deaths",
        "road_fuel_tonnes": "Per road fuel",
        "petrol_tonnes": "Per petrol",
        "toll_intensity": "Per toll traffic",
    }
    effects = effects.assign(panel=effects.exposure.map(short))
    plots.dot_interval_panels(
        effects,
        "panel",
        "month_label",
        "rate_ratio",
        "low",
        "high",
        figures_dir / "m2_month_effects.svg",
        "How much riskier is each month, before and after allowing for traffic",
        order=list(dict.fromkeys(effects.month_label)),
        panel_order=list(short.values()),
        xlabel="Deaths against the average month (dotted line: the same)",
        reference=1.0,
        from_zero=False,
    )
    captions["m2_month_effects"] = plots.caption(
        f"{SERIES_SOURCE}; {TRAFFIC_SOURCE}",
        f"{years}",
        "month effects from quasi-Poisson models of monthly 30-day deaths with year effects; the "
        "first panel has no exposure, the others take the log of one traffic series as an offset, "
        "so their month effects are deaths per unit of that traffic against the average month; "
        "whiskers are 95% intervals on the overdispersed scale",
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
    captions["m3_lockdown"] = plots.caption(
        f"{SERIES_SOURCE}; {TRAFFIC_SOURCE}",
        "2020 against the 2017–2019 mean of each month",
        "proportional change in 30-day deaths and in each traffic series; the state of alarm "
        "began on 14 March 2020 and the strictest restrictions ran to early May",
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
    captions["a3_sex_ratios"] = plots.caption(
        f"{TABLES_SOURCE}; {CENSUS_SOURCE}",
        "2022–2024 pooled",
        "car drivers involved in injury crashes and killed within 30 days (DGT tables 4.2 and "
        "4.1.1, car rows), against licence-holder-years from the driver census and against the "
        "drivers involved; each row is the male rate divided by the female rate, with 95% "
        "log-normal intervals; drivers of unknown sex or age left out",
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
    captions["f1_speed_severity"] = plots.caption(
        f"{SPEED_REPORT_SOURCE}; {MICRODATA_SOURCE}",
        "2016–2023 pooled, Spain without Cataluña and País Vasco",
        "deaths within 30 days per 100 injury crashes in which the police recorded inappropriate "
        "speed as a concurrent factor, divided by the same ratio for the other injury crashes of "
        "the same road type and scope (totals from the microdata restricted to the report's "
        "provinces); 95% log-normal intervals; the adjusted row is a quasi-Poisson model with road "
        "type and year",
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
        "Share of injury crashes with each factor recorded; gaps are recording breaks",
        order=[
            "Alcohol",
            "Inappropriate speed",
            "Distraction or inattention",
            "Illegal manoeuvres",
            "Drugs",
        ],
        series_order=["Interurban roads", "Urban streets"],
    )
    captions["f2_factor_shares"] = plots.caption(
        SPEED_REPORT_SOURCE,
        "2014–2023, Spain without Cataluña and País Vasco",
        "injury crashes in which the police recorded each concurrent factor, as a share of all "
        "injury crashes in the zone; a line is broken wherever the share jumps or falls by more "
        "than 25% in one year (a recording break), so each unbroken run can be compared within "
        "itself; each panel has its own scale",
    )


# --------------------------------------------------------------------------- severity


def _severity_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    coefficients = summaries.read_model_table("q3_model_coefficients")
    n_model = int(coefficients.n.iloc[0])
    table = coefficients[(coefficients.outcome == "fatal") & (coefficients.predictor != "year")]
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
            f"; {named} {'have' if plural else 'has'} no crash of this outcome, so "
            f"{'they' if plural else 'it'} cannot be estimated and "
            f"{'are' if plural else 'is'} left out of the plot"
        )
    captions["s1_forest_fatal"] = plots.caption(
        MICRODATA_SOURCE,
        "2016–2024",
        "logistic regression of at least one death on the circumstances shown plus year; odds "
        "ratios against the reference level (hollow marker) with 95% intervals clustered by "
        "province" + note,
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
        "Adverse conditions and a fatal outcome: the same odds ratio under eight models",
        order=list(dict.fromkeys(fatal.variant_label)),
        panel_order=[
            level.capitalize()
            for level in ("wet", "rain", "hail or snow", "at a junction")
            if level.capitalize() in set(fatal.level.map(str.capitalize))
        ],
        xlabel="Odds ratio against the reference level (dotted line: no difference)",
        reference=1.0,
    )
    captions["s2_adverse_conditions"] = plots.caption(
        MICRODATA_SOURCE,
        "2016–2024",
        "odds of at least one death, given an injury crash, at each level against its reference; "
        "the first row is the full model and the others drop a correlated predictor or fit one "
        "kind of road on its own; a missing row is a level the variant does not contain; 95% "
        "intervals clustered by province; each panel has its own horizontal scale from zero",
        f"{n_model:,} crashes",
    )


# --------------------------------------------------------------------------- older drivers


def _age_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    rates = summary("q7_km_rates")
    long = pd.concat(
        [
            rates.assign(
                panel=AGE_RATE_PANELS[measure],
                value=rates[measure],
                low=rates[f"{measure}_low"],
                high=rates[f"{measure}_high"],
            )[["band_label", "panel", "value", "low", "high"]]
            for measure in AGE_RATE_PANELS
        ],
        ignore_index=True,
    )
    plots.dot_interval_panels(
        long,
        "panel",
        "band_label",
        "value",
        "low",
        "high",
        figures_dir / "a1_km_risk_by_age.svg",
        "Car drivers by age: crashing per kilometre, and dying once the crash happens (2024)",
        order=[agebands.band_label(band) for band in rates.band],
        panel_order=list(AGE_RATE_PANELS.values()),
    )
    captions["a1_km_risk_by_age"] = plots.caption(
        f"{TABLES_SOURCE}; {KM_2024_SOURCE}",
        "2024",
        "car drivers involved in injury crashes and killed within 30 days (DGT tables 4.1.1 and "
        "4.2, car rows only), against the kilometres driven in 2024 by cars whose registered "
        "owner is in the band; whiskers are exact 95% Poisson intervals on the counts, with the "
        "kilometres treated as known; each panel has its own horizontal scale from zero",
        f"{int(rates.drivers_involved.sum()):,} drivers involved",
    )

    contrast = summary("q7_denominator_contrast")
    plots.dot_interval_panels(
        contrast.assign(panel=contrast.denominator_label),
        "panel",
        "band_label",
        "ratio",
        "low",
        "high",
        figures_dir / "a2_denominator_contrast.svg",
        "The same car-driver deaths, four denominators: each band against 35–54 (2024)",
        order=[agebands.band_label(band) for band in dict.fromkeys(contrast.band)],
        panel_order=list(dict.fromkeys(contrast.denominator_label)),
        xlabel="Rate ratio against drivers aged 35–54 (dotted line: the same rate)",
        reference=1.0,
    )
    captions["a2_denominator_contrast"] = plots.caption(
        f"{TABLES_SOURCE}; {KM_2024_SOURCE}; INE, Estadística Continua de Población; "
        "DGT, Censo de conductores",
        "2024",
        "car-driver deaths within 30 days divided by each denominator in turn and expressed as a "
        "ratio to the 35–54 band, with 95% log-normal intervals; the numerator is the same in "
        "every panel, so the movement between panels is the denominator and nothing else",
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
    captions["v1_per_vehicle_vs_per_km"] = plots.caption(
        f"{TABLES_SOURCE}; {KM_SOURCE}",
        "2022",
        "vehicles of each type involved in 30-day fatal crashes per 100,000 circulating vehicles "
        "(left) and per billion vehicle-km (right); the lines show how each type's rank moves "
        "when distance driven replaces fleet size as the denominator",
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
    trend = summary("q8_points_trend_choice")
    chosen = trend[trend.chosen].iloc[0]
    captions["p1_points_series"] = plots.caption(
        SERIES_SOURCE,
        "January 2000 to November 2007, all roads",
        f"{THIRTY_DAY}; fitted = Poisson regression with month-of-year terms, a level and slope "
        f"change at July 2006 and a pre-trend with a {chosen.label} chosen by AIC on the months "
        "before the break; the dashed line is that model with the change set to zero and the "
        "dotted line the same counterfactual under one straight pre-trend, the specification "
        "that gives the larger drop",
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
    captions["p2_july_placebos"] = plots.caption(
        SERIES_SOURCE,
        "July of every year with a clean window, 1993–2024",
        "the same segmented regression with the break placed at 1 July of each year, on a window "
        "of the same shape every time (60 months before, 17 after); the filled marker is July "
        "2006 and the hollow ones are Julys the points licence cannot have affected; years whose "
        "window would contain July 2006 or the pandemic are left out",
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
    captions["d1_missingness"] = plots.caption(
        MICRODATA_SOURCE,
        "2016–2024",
        "observed = not empty, not 999 (not specified), not 998 (not applicable) and not an "
        "explicit unknown code. The fields that carry no code list count their placeholder values "
        "as not observed too: KM 9999 (and 1000 in 2019, the year DGT used it), CARRETERA 'No "
        "inventariada' and COD_MUNICIPIO 00000",
        f"{int(profile.groupby('year').rows.first().sum()):,} crashes",
    )
