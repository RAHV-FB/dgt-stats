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
TRAFFIC_SOURCE = (
    "CORES, consumo de productos petrolíferos; Ministerio de Transportes y Movilidad Sostenible, "
    "tráfico en autopistas estatales de peaje"
)
THIRTY_DAY = "deaths within 30 days of the crash"

# Twelve road-user death columns folded to eight series (the fixed categorical limit).
ROAD_USER_FOLD = {
    "Pedestrians": "Pedestrians",
    "Cyclists": "Cyclists",
    "Moped riders": "Moped riders",
    "Motorcyclists": "Motorcyclists",
    "Personal mobility vehicles": "Personal mobility vehicles",
    "Car occupants": "Car occupants",
    "Van occupants": "Van occupants",
    "Light truck occupants (≤3.5 t)": "Trucks, buses and other",
    "Heavy truck occupants (>3.5 t)": "Trucks, buses and other",
    "Bus occupants": "Trucks, buses and other",
    "Other vehicles": "Trucks, buses and other",
    "Unspecified vehicle": "Trucks, buses and other",
}
ROAD_USER_ORDER = [
    "Pedestrians",
    "Cyclists",
    "Moped riders",
    "Motorcyclists",
    "Personal mobility vehicles",
    "Car occupants",
    "Van occupants",
    "Trucks, buses and other",
]

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
    _context_figures(figures_dir, captions, summary)
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


def _context_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    headline = summary("q1_annual_headline")
    plots.line_series(
        headline,
        "year",
        "deaths_30d",
        figures_dir / "c1_deaths_per_year.svg",
        "Road deaths per year, Spain 1993–2024",
        ylabel="Deaths (30 days)",
    )
    captions["c1_deaths_per_year"] = plots.caption(
        SERIES_SOURCE, "1993–2024, all roads", THIRTY_DAY
    )

    users = summary("q5_deaths_by_road_user")
    users["group"] = users.road_user.map(ROAD_USER_FOLD)
    folded = users.groupby(["year", "group"], observed=True).deaths_30d.sum().reset_index()
    plots.bar_shares(
        folded,
        "year",
        "group",
        "deaths_30d",
        figures_dir / "c2_road_user_shares.svg",
        "Share of road deaths by type of road user",
        order=ROAD_USER_ORDER,
    )
    captions["c2_road_user_shares"] = plots.caption(
        MICRODATA_SOURCE,
        "2016–2024, all roads",
        "each year's 30-day deaths as shares by the vehicle the person was using, stacked to "
        "100%; trucks, buses, other and unspecified folded together; personal mobility vehicles "
        "counted separately only from 2020",
        f"{int(folded.deaths_30d.sum()):,} deaths",
    )

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
