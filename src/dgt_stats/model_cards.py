"""Model cards for the national DGT models, written from the committed result tables.

``python -m dgt_stats.model_cards`` rewrites ``docs/models/dgt_monthly_deaths_forecast.md`` from
the ``forecast_*`` tables in ``reports/tables`` and the constants of :mod:`dgt_stats.forecast`, and
``docs/models/dgt_crash_severity.md`` from the ``q3_*`` tables that ``scripts/model.py`` writes and
the predictor definitions of :mod:`dgt_stats.features`, so that no number in either card is typed
by hand; tests check the committed cards against a fresh rendering. The Barcelona and Catalonia
severity models write their own cards (``scripts/microdata.py models``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from dgt_stats import features, forecast, models
from dgt_stats.paths import (
    CORES_FUEL_PATH,
    DGT_PROCESSED_CRASHES,
    DOCS_DIR,
    PROJECT_ROOT,
    RAW_MICRODATA_DIR,
    SERIES_PATH,
    TABLES_DIR,
)

FORECAST_CARD_PATH = DOCS_DIR / "models" / "dgt_monthly_deaths_forecast.md"
SEVERITY_CARD_PATH = DOCS_DIR / "models" / "dgt_crash_severity.md"
SEVERITY_TABLES = (
    "q3_model_coefficients",
    "q3_holdout_summary",
    "q3_calibration",
    "q3_adverse_conditions",
    "q3_adverse_exclusions",
    "q3_year_stability",
    "q3_recording_regime",
    "q3_regime_sensitivity",
)
FORECAST_TABLES = (
    "forecast_selection",
    "forecast_validation",
    "forecast_backtest",
    "forecast_horizons",
    "forecast_detectability",
    "forecast_coefficients",
)
SETS = {
    "selection": "used to choose",
    "holdout": "held back, the test",
    "pandemic": "lockdown, scored apart",
}
ZONES = ("deaths_all", "deaths_interurban", "deaths_urban")


def _pct(value: float, decimals: int = 1) -> str:
    return f"{float(value) * 100:.{decimals}f}%"


def _signed(value: float, decimals: int = 1) -> str:
    return f"{float(value) * 100:+.{decimals}f}%"


def _span(years: list[int]) -> str:
    years = sorted(int(y) for y in years)
    runs: list[list[int]] = []
    for year in years:
        if runs and year == runs[-1][-1] + 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    parts = [str(r[0]) if len(r) == 1 else f"{r[0]}-{r[-1]}" for r in runs]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _markdown(frame: pd.DataFrame) -> str:
    head = "| " + " | ".join(frame.columns) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([head, rule, *rows])


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def read_forecast_tables(tables_dir: Path = TABLES_DIR) -> dict[str, pd.DataFrame]:
    return {name: pd.read_csv(tables_dir / f"{name}.csv") for name in FORECAST_TABLES}


def forecast_card(tables: dict[str, pd.DataFrame] | None = None) -> str:
    """The model card of the monthly deaths forecast, as Markdown."""
    tables = tables if tables is not None else read_forecast_tables()
    selection = tables["forecast_selection"]
    validation = tables["forecast_validation"].set_index(["outcome", "set", "method"])
    backtest = tables["forecast_backtest"]
    horizons = tables["forecast_horizons"].set_index(["outcome", "horizon"])
    detect = tables["forecast_detectability"].set_index(["outcome", "horizon"])
    coefficients = tables["forecast_coefficients"]
    chosen, tree = forecast.CHOSEN, forecast.TREE_METHOD
    labels = forecast.SPECIFICATION_LABELS
    years = {kind: sorted(backtest[backtest.set == kind].year.unique()) for kind in SETS}
    chosen_rows = selection[selection.chosen & (selection.set == "selection")]
    model_row = chosen_rows[chosen_rows.family == "model"].iloc[0]
    tree_row = chosen_rows[chosen_rows.family == "trees"].iloc[0]
    trees = selection[
        (selection.family == "trees") & (selection.outcome == "deaths_all")
    ].pivot_table(index="method", columns="set", values="rmse")
    hindsight = str(trees.drop(index=tree).holdout.idxmin())
    n_specs = selection[selection.family == "model"].method.nunique()
    windows = sorted(selection[selection.family == "model"].window.unique())
    first_fit, last_fit = int(coefficients.first_year.min()), int(coefficients.last_year.max())
    last = int(backtest.year.max())

    def rmse(outcome: str, kind: str, method: str) -> float:
        return float(validation.loc[(outcome, kind, method), "rmse"])

    metric_rows = []
    for zone in ZONES:
        for kind, kind_label in SETS.items():
            metric_rows.append(
                {
                    "roads": forecast.OUTCOMES[zone],
                    "years": f"{_span(years[kind])}, {kind_label}",
                    "model": _pct(rmse(zone, kind, chosen)),
                    "month and trend only": _pct(rmse(zone, kind, "trend")),
                    "tuned trees": _pct(rmse(zone, kind, tree)),
                    "last year's count": _pct(rmse(zone, kind, "last_year")),
                    "mean of last 3 years": _pct(rmse(zone, kind, "mean_3_years")),
                    "model bias": _signed(validation.loc[(zone, kind, chosen), "bias"]),
                }
            )
    detect_rows = []
    for zone in ZONES:
        for horizon in sorted(detect.loc[zone].index):
            row, error = detect.loc[(zone, horizon)], horizons.loc[(zone, horizon)]
            rise = forecast.minimum_detectable_rise(float(row.expected), float(row.tau))
            detect_rows.append(
                {
                    "roads": forecast.OUTCOMES[zone],
                    "years summed": int(horizon),
                    "origins": int(error.origins),
                    "rmse": _pct(error.rmse),
                    "bias": _signed(error.bias),
                    "tau": _pct(row.tau),
                    "expected deaths": f"{float(row.expected):,.0f}",
                    "fall detected 4 in 5": _pct(row.mde, 0),
                    "rise detected 4 in 5": _pct(rise, 0),
                }
            )
    coefficient_rows = [
        {
            "roads": row.outcome_label,
            "term": row.term_label,
            "scale": row.scale,
            "estimate": f"{row.estimate:.3f}",
            "95% interval": f"{row.low:.3f} to {row.high:.3f}",
            "dispersion": f"{row.dispersion:.2f}",
        }
        for row in coefficients.itertuples()
    ]
    one = detect.loc[("deaths_all", 1)]
    five = detect.loc[("deaths_all", 5)]
    rise_one = forecast.minimum_detectable_rise(float(one.expected), float(one.tau))
    urban_trend_better = rmse("deaths_urban", "selection", "trend") < rmse(
        "deaths_urban", "selection", chosen
    )
    holdout_naive_better = rmse("deaths_all", "holdout", "last_year") < rmse(
        "deaths_all", "holdout", chosen
    )
    bias_five = float(horizons.loc[("deaths_all", 5), "bias"])
    checks = {
        "the tuned trees do worse than the model everywhere": all(
            rmse(zone, kind, tree) > rmse(zone, kind, chosen) for zone in ZONES for kind in SETS
        ),
        "the detectable change grows with the years summed": all(
            detect.loc[zone].mde.is_monotonic_increasing for zone in ZONES
        ),
        "the model beats last year's count in the lockdowns": rmse("deaths_all", "pandemic", chosen)
        < rmse("deaths_all", "pandemic", "last_year"),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"forecast model card: the tables no longer support: {failed}")

    lines = [
        "# Model card: DGT monthly deaths forecast",
        "",
        "Generated by `python -m dgt_stats.model_cards` from the committed `reports/tables/"
        "forecast_*.csv` tables and the constants in `src/dgt_stats/forecast.py`; do not edit "
        "by hand. The site page is `forecast.html`.",
        "",
        (
            "**Decision:** REPLACE with the naive forecast (last year's count) for ordinary "
            "years: it does not beat that comparator on the held-back years; kept for its "
            "lockdown-years result and the detectable change ([`MODEL_DECISIONS.md`]"
            "(../MODEL_DECISIONS.md))."
            if holdout_naive_better
            else "**Decision:** KEEP: it beats the naive forecasts on the held-back years "
            "([`MODEL_DECISIONS.md`](../MODEL_DECISIONS.md))."
        ),
        "",
        "## Task",
        "",
        "Forecast the number of people killed within 30 days on Spain's roads in each month of a "
        "year, from the years before it, as the counterfactual a before-and-after comparison of "
        "the death counts needs; and measure how large a change in a year's deaths such a "
        "comparison can detect.",
        "",
        "- **Unit (one row):** one calendar month of Spain. All roads, interurban roads and "
        "urban streets are three separate models.",
        "- **Target:** deaths within 30 days in the month (`deaths_30d` of DGT's monthly "
        "yearbook series, by zone).",
        "- **Predictors:** month of the year (12 levels), a linear time trend, the log of the "
        "month's road fuel (CORES automotive petrol plus diesel, tonnes) and the month's numbers "
        "of Fridays, Saturdays and Sundays. Fuel and calendar are those observed in the month "
        "forecast, so the forecast is a counterfactual given the traffic there was, not an "
        "advance prediction.",
        "- **Model:** Poisson regression (log link) with Pearson dispersion for the standard "
        f"errors: `{forecast.SPECIFICATIONS[chosen]}`.",
        f"- **Source files:** `{_relative(SERIES_PATH)}` (via the staging table "
        f"`series_monthly`) and `{_relative(CORES_FUEL_PATH)}`. No value comes from an external "
        "study.",
        "",
        "## Training, selection and test",
        "",
        f"- **Rolling origin:** each year is forecast from a model fitted on the "
        f"{forecast.WINDOW_YEARS} years before it.",
        f"- **Selection years:** {_span(years['selection'])}. {n_specs} specifications and "
        f"windows of {windows[0]} to {windows[-1]} years were scored on these years alone for "
        f"all roads; the chosen one is `{model_row.method}` ({labels[model_row.method]}) with a "
        f"{int(model_row.window)}-year window.",
        f"- **Held-back (test) years:** {_span(years['holdout'])}, never used to choose.",
        f"- **Lockdown years:** {_span(years['pandemic'])}, scored apart and never used to choose.",
        f"- **Final fit** (the coefficients below): {first_fit}-{last_fit}, a window that "
        f"includes {max(years['pandemic'])}, one of the lockdown years.",
        "",
        "## Metrics",
        "",
        "Root mean square of the log error of each year's total (about the error as a share of "
        "the year's deaths), each year forecast from the four before it. Bias is the mean log "
        "error: positive means more deaths than forecast.",
        "",
        _markdown(pd.DataFrame(metric_rows)),
        "",
        "## Comparators",
        "",
        "- **Naive:** the same months of the previous year; the mean of the previous three years.",
        "- **Gradient-boosted trees** (scikit-learn `HistGradientBoostingRegressor`, Poisson "
        "loss) given the same inputs, with the leaf size tuned on the selection years: "
        f"`{tree_row.method}` ({labels[tree_row.method]}). It does worse than the model in "
        "every zone and every set of years in the table above.",
        f"- **Disclosed, not a candidate:** `{hindsight}` ({labels[hindsight]}) is the best "
        f"forecast of the held-back years ({_pct(trees.loc[hindsight, 'holdout'])} on all "
        "roads), but that leaf size was found by looking at the test years; it scores "
        f"{_pct(trees.loc[hindsight, 'selection'])} on the selection years and "
        f"{_pct(trees.loc[hindsight, 'pandemic'])} in the lockdowns.",
        "",
        "## Horizon error and the detectable change",
        "",
        "For sums of 1 to 5 years, the error of the chosen model's forecast splits into Poisson "
        "chance and a drift of the trend, `tau`. The detectable change is the fall (or rise) "
        f"that a two-sided {forecast.ALPHA:.0%} comparison of the observed count with the "
        f"forecast detects with {forecast.POWER:.0%} probability, at each zone's mean deaths a "
        f"year in {last - 2}-{last} times the years summed.",
        "",
        _markdown(pd.DataFrame(detect_rows)),
        "",
        "## Coefficients of the final fit",
        "",
        "Rate ratios per extra Friday, Saturday or Sunday and per year of trend; the fuel term is "
        "an elasticity. They are associations within four years of months.",
        "",
        _markdown(pd.DataFrame(coefficient_rows)),
        "",
        "## Valid interpretation",
        "",
        "- The forecast is the number of deaths associated with the month's observed traffic and "
        "calendar on the trend of the four years before.",
        f"- One year of deaths on all roads differs from the forecast by more than chance about "
        f"four times in five when the change is a fall of {_pct(one.mde, 0)} or a rise of "
        f"{_pct(rise_one, 0)}; smaller changes are detected less often, not never.",
        f"- Summing more years does not help: over five years the fall detected four times in "
        f"five is {_pct(five.mde, 0)}, because the trend drifts from any extrapolation.",
        "",
        "## Invalid interpretation",
        "",
        "- A difference between the observed deaths and the forecast is not the effect of any "
        "policy, campaign or event: the model says whether deaths differ from the forecast, not "
        "why.",
        "- A change that does not show in a year's count is not evidence that nothing changed.",
        "- The fuel elasticity and the weekday ratios are not effects of traffic or of weekends.",
        "- Fuel is a predictor, not a denominator: the model gives no rate of deaths per unit of "
        "traffic.",
        "- The forecast needs the month's observed fuel, so it is not an advance prediction of "
        "future deaths.",
        "",
        "## Limitations",
        "",
    ]
    if holdout_naive_better:
        lines.append(
            "- In the flat held-back years last year's count does slightly better on all roads "
            f"({_pct(rmse('deaths_all', 'holdout', 'last_year'))} against "
            f"{_pct(rmse('deaths_all', 'holdout', chosen))}). By the project's decision rule "
            "(a model must beat its plain comparator on records it never saw) the forecast is "
            "replaced by last year's count for ordinary years and is not presented as a "
            "predictive model ([`MODEL_DECISIONS.md`](../MODEL_DECISIONS.md)). Separately, it is "
            "far better when traffic moves sharply "
            f"({_pct(rmse('deaths_all', 'pandemic', chosen))} against "
            f"{_pct(rmse('deaths_all', 'pandemic', 'last_year'))} in the lockdown years), and its "
            "error sets the detectable change."
        )
    if urban_trend_better:
        lines.append(
            "- The form was chosen on all roads; on urban streets alone the month-and-trend form "
            f"scored better on the selection years ({_pct(rmse('deaths_urban', 'selection', 'trend'))}"
            f" against {_pct(rmse('deaths_urban', 'selection', chosen))})."
        )
    lines += [
        f"- `tau` is measured on every forecast origin from {years['selection'][0]}, the "
        "selection years included, so it describes the whole period rather than the held-back "
        "years alone.",
        f"- The forecast errors grow with the horizon and lean one way: over five years the "
        f"mean log error on all roads is {_signed(bias_five)} "
        f"({'more' if bias_five > 0 else 'fewer'} deaths than forecast on average).",
        "- Road fuel is national and is observed after any change being judged: for a change "
        "that itself alters how much people drive, the comparison speaks only of deaths for the "
        "traffic there was.",
        f"- The final fit's window includes {max(years['pandemic'])}, whose low-traffic months "
        "weigh on the fuel coefficient; with four years of data the coefficients are imprecise.",
        "- The detectable change assumes the forecast's errors are as large after a change as "
        "before it.",
        "",
    ]
    return "\n".join(lines)


def write_forecast_card(path: Path = FORECAST_CARD_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(forecast_card(), encoding="utf-8")
    return path


def read_severity_tables(tables_dir: Path = TABLES_DIR) -> dict[str, pd.DataFrame]:
    return {name: pd.read_csv(tables_dir / f"{name}.csv") for name in SEVERITY_TABLES}


def _or(odds: float, low: float, high: float) -> str:
    return f"{odds:.2f} ({low:.2f} to {high:.2f})"


def _severity_decision(tables_dir: Path = TABLES_DIR) -> str:
    """The card's decision line, worded from the DGT microdata audit's checks."""
    checks = pd.read_csv(tables_dir / "dgt_audit_checks.csv")
    numbered = checks[checks.check.str.match(r"\d")]
    failed = [c.split(" ", 1)[1] for c in numbered.loc[~numbered.passed, "check"]]
    links = (
        "([`DGT_MICRODATA_AUDIT.md`](../DGT_MICRODATA_AUDIT.md), "
        "[`MODEL_DECISIONS.md`](../MODEL_DECISIONS.md))"
    )
    if not failed:
        return f"**Decision:** the DGT microdata audit passes every check {links}."
    return (
        "**Decision:** KEEP as research/diagnostic model: a supporting association analysis, "
        "not a predictive model. The DGT crash microdata do not train a predictive model: "
        f"their audit fails {', '.join(failed)} {links}."
    )


def severity_card(tables: dict[str, pd.DataFrame] | None = None) -> str:
    """The card of the DGT crash-severity regressions, an association analysis, as Markdown."""
    tables = tables if tables is not None else read_severity_tables()
    coefficients = tables["q3_model_coefficients"]
    holdout = tables["q3_holdout_summary"].set_index("outcome")
    calibration = tables["q3_calibration"]
    adverse = tables["q3_adverse_conditions"]
    adverse = adverse[adverse.outcome == "fatal"].set_index(["variant", "level"])
    exclusions = tables["q3_adverse_exclusions"]
    stability = tables["q3_year_stability"]
    regime = tables["q3_recording_regime"]
    sensitivity = tables["q3_regime_sensitivity"]
    outcomes = list(dict.fromkeys(coefficients.outcome))
    fatal = coefficients[coefficients.outcome == "fatal"]
    years = sorted(int(y) for y in fatal[fatal.predictor == "year"].level)
    n = int(fatal.n.iloc[0])
    events = {o: int(coefficients[coefficients.outcome == o].events.iloc[0]) for o in outcomes}

    feature_rows = []
    for name, spec in features.PREDICTORS.items():
        rows = fatal[fatal.predictor == name]
        reference = rows[rows.is_reference.astype(bool)].level.iloc[0]
        others = [
            f"{level}{' (nuisance)' if nuisance else ''}"
            for level, ref, nuisance in zip(rows.level, rows.is_reference, rows.is_nuisance)
            if not ref
        ]
        feature_rows.append(
            {
                "predictor": features.PREDICTOR_LABELS[name],
                "source column": f"`{spec['source']}`",
                "reference level": reference,
                "other levels": "; ".join(others),
            }
        )
    metric_rows = []
    for outcome in outcomes:
        row = holdout.loc[outcome]
        metric_rows.append(
            {
                "target": outcome,
                "train years": row.train_years.replace("–", "-"),
                "test years": row.test_years.replace("–", "-"),
                "test crashes": f"{int(row.test_crashes):,}",
                "test events": f"{int(row.test_events):,}",
                "training base rate": _pct(row.base_rate_train, 2),
                "AUC": f"{row.auc:.3f}",
                "Brier": f"{row.brier:.5f}",
                "Brier, training base rate": f"{row.brier_train_rate:.5f}",
                "Brier skill": _pct(row.brier_skill),
            }
        )
    top = calibration.sort_values("decile").groupby("outcome").tail(1).set_index("outcome")
    regime_rows = [
        {
            "predictor": row.predictor_label,
            "level": row.level,
            "crashes": f"{int(row.crashes):,}",
            "share of Catalan crashes": _pct(row.share_of_catalan_crashes, 2),
            "share of other crashes": _pct(row.share_of_other_crashes, 2),
            "Catalan share of the level": _pct(row.catalan_share_of_level),
        }
        for row in regime.itertuples()
    ]
    nuisance = fatal[fatal.is_nuisance.astype(bool)]
    nuisance_rows = [
        {
            "level": f"{row.predictor_label}: {row.level}",
            "crashes": f"{int(row.crashes):,}",
            "fatal odds ratio": "not estimated"
            if pd.isna(row.odds_ratio)
            else _or(row.odds_ratio, row.or_low, row.or_high),
        }
        for row in nuisance.itertuples()
    ]
    fatal_sens = sensitivity[sensitivity.outcome == "fatal"]
    kept = fatal_sens[~fatal_sens.is_nuisance.astype(bool)]
    moved = kept.reindex((kept.ratio_without_to_full - 1).abs().sort_values(ascending=False).index)
    sens_rows = [
        {
            "term": f"{row.predictor_label}: {row.level}",
            "full model": _or(row.odds_ratio, row.or_low, row.or_high),
            "without Cataluña": _or(
                row.odds_ratio_without, row.or_low_without, row.or_high_without
            ),
        }
        for row in moved.head(6).itertuples()
    ]
    alignment = regime.set_index(["predictor", "level"]).loc[("alignment", "unknown")]
    excluded = fatal_sens.excluded_provinces.iloc[0]
    wet = adverse.loc[("no_weather", "wet")]
    junction = adverse.loc[("full", "at a junction")]
    fatal_stability = stability[stability.outcome == "fatal"]
    outside = int((~fatal_stability.within_full_interval.astype(bool)).sum())
    ranked = fatal[
        (fatal.predictor != "year") & ~fatal.is_reference.astype(bool) & fatal.odds_ratio.notna()
    ]
    ranked = ranked.reindex(np.log(ranked.odds_ratio).abs().sort_values(ascending=False).index)
    top_nuisance = ranked[ranked.is_nuisance.astype(bool)].iloc[0]
    nuisance_rank = int(list(ranked.index).index(top_nuisance.name)) + 1
    checks = {
        "every outcome has a holdout row": set(outcomes) == set(holdout.index),
        "the models discriminate better than chance": bool((holdout.auc > 0.5).all()),
        "the models beat the training base rate": bool((holdout.brier_skill > 0).all()),
        "a missing-value level is among the strongest terms": nuisance_rank <= 3,
        "wet and junction odds are below 1": float(wet.or_high) < 1 and float(junction.or_high) < 1,
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"severity model card: the tables no longer support: {failed}")

    lines = [
        "# Model card: associations in DGT crash records (crash severity)",
        "",
        "Generated by `python -m dgt_stats.model_cards` from the committed "
        "`reports/tables/q3_*.csv` "
        "tables (written by `python scripts/model.py`) and the predictor definitions in "
        "`src/dgt_stats/features.py`; do not edit by hand. The site page is `severity.html`, a "
        "supporting analysis.",
        "",
        _severity_decision(),
        "",
        "## Task",
        "",
        "Describe which circumstances the police record for an injury crash go with a fatal "
        "outcome, and with a fatal or serious one, holding the other recorded circumstances "
        "constant. It is a supporting association analysis of DGT's records: a description of "
        "severity given that an injury crash happened, not a model of how often crashes happen "
        "or of what causes them, and not the project's predictive model. DGT's file is not used "
        "to train a model that predicts severity: levels that record a missing value are among "
        f"its strongest terms ({top_nuisance.predictor_label.lower()} '{top_nuisance.level}', "
        f"odds ratio {top_nuisance.odds_ratio:.2f}, rank {nuisance_rank} of {len(ranked)} by "
        "size).",
        "",
        "- **Unit (one row):** one DGT injury crash (a crash with at least one person killed or "
        f"injured), {years[0]}-{years[-1]}; {n:,} crashes, none dropped.",
        "- **Targets:** `fatal`, at least one death within 30 days "
        f"({events.get('fatal', 0):,} crashes); `serious`, a death within 30 days or a person "
        f"admitted to hospital for more than 24 hours ({events.get('serious', 0):,} crashes).",
        "- **Model:** logistic regression with main effects only, fitted by iteratively "
        "reweighted least squares, with cluster-robust standard errors by province. Each "
        "predictor is categorical against a reference level, its most common one. A level with "
        "no event of the outcome, or one that repeats another column exactly, is left out of the "
        "fit and reported as not estimated.",
        f"- **Source files:** `{_relative(RAW_MICRODATA_DIR)}/accidentes_<year>.xlsx` through the "
        f"processed table `{_relative(DGT_PROCESSED_CRASHES)}`. No value comes from an external "
        "study.",
        "",
        "## Features",
        "",
        "Every predictor is a circumstance the police record on the crash form. Levels with "
        f"fewer than {features.MIN_LEVEL_CRASHES:,} crashes are merged into the reference: on "
        "all years for the full models, on the training years alone for the holdout check. "
        "Road-type codes 5 and 6 (conventional roads with one or two carriageways) are one "
        "level, because DGT recoded most code-5 crashes as code 6 from 2021.",
        "",
        _markdown(pd.DataFrame(feature_rows)),
        "",
        "## Holdout check",
        "",
        "A check that the associations carry across years, not a measure of a predictive tool: "
        "the regressions are fitted on the training years with every predictor but the year "
        "and scored on the held-out years, which play no part in the fit or in the level "
        "merges. The Brier skill is the improvement on giving every held-out crash the training "
        "years' share of the outcome.",
        "",
        _markdown(pd.DataFrame(metric_rows)),
        "",
        "In the top decile of fitted probability the observed share is "
        + "; ".join(
            f"{outcome} {_pct(top.loc[outcome, 'observed'])} against "
            f"{_pct(top.loc[outcome, 'predicted'])} predicted"
            for outcome in outcomes
            if outcome in top.index
        )
        + " (`q3_calibration`).",
        "",
        "## Nuisance levels",
        "",
        "The missing states (a field's own unknown code, not specified) are levels of their own "
        "so that no crash is dropped. They record how the form was filled in, which differs "
        "between police forces and years, and are flagged `is_nuisance` in "
        "`q3_model_coefficients` and `q3_marginal_effects`. They are not drawn in the forest "
        "figure and never quoted as an effect.",
        "",
        _markdown(pd.DataFrame(nuisance_rows)),
        "",
        f"Where they are (provinces {excluded}, Cataluña, against the rest of Spain):",
        "",
        _markdown(pd.DataFrame(regime_rows)),
        "",
        f"Road alignment unknown is {_pct(alignment.catalan_share_of_level)} Catalan, while "
        f"Cataluña has {_pct(alignment.catalan_share_of_all_crashes)} of all crashes, so it marks "
        "crashes recorded in Cataluña rather than a kind of road.",
        "",
        "## Sensitivity: without Cataluña",
        "",
        f"The fatal model refitted without provinces {excluded}: "
        f"{int(kept.within_full_interval.astype(bool).sum())} of the {len(kept)} odds ratios "
        "that are not nuisance terms stay inside the full model's interval. The six that move "
        "most (`q3_regime_sensitivity`):",
        "",
        _markdown(pd.DataFrame(sens_rows)),
        "",
        "## Other checks",
        "",
        f"- Adverse conditions under {adverse.index.get_level_values('variant').nunique()} model "
        "variants (`q3_adverse_conditions`): wet surface without the weather predictor "
        f"{_or(wet.odds_ratio, wet.or_low, wet.or_high)}, at a junction "
        f"{_or(junction.odds_ratio, junction.or_low, junction.or_high)} (fatal).",
        f"- Hail or snow with the {int(exclusions.n_excluded.max())} provinces that record most "
        f"of it removed: {_or(*exclusions.iloc[-1][['odds_ratio', 'or_low', 'or_high']])} "
        "(`q3_adverse_exclusions`).",
        f"- Year-by-year refits (`q3_year_stability`): {outside} of {len(fatal_stability)} "
        f"estimates of the {models.STABILITY_TERMS} largest non-nuisance terms fall outside the "
        "full model's interval.",
        "",
        "## Valid interpretation",
        "",
        "- Given an injury crash and the other recorded circumstances, a level's odds ratio says "
        "how the odds of the outcome differ from the reference level in the police record.",
        "- The ratios are associations in recorded crashes, comparable across levels of the "
        "same predictor.",
        "",
        "## Invalid interpretation",
        "",
        "- An odds ratio is not the effect of a circumstance: a lower ratio for wet roads does "
        "not say that rain makes crashes safer, and no mechanism can be tested with these data.",
        "- Nothing here is a crash risk: the data hold only crashes that happened, with no "
        "measure of traffic.",
        "- The fitted probabilities are not predictions for new crashes: the regressions "
        "describe associations in recorded crashes and are not a predictive model.",
        "- The nuisance levels are not findings about roads, weather or light.",
        "- Zone and road type overlap and are read together, not one at a time.",
        "",
        "## Limitations",
        "",
        "- DGT's national microdata have one row per crash and no driver, vehicle, person or "
        "speed fields.",
        "- Recording practice differs between forces and years: the missing states concentrate "
        "in some provinces and years, and coding changes (urban road types in 2024, junctions "
        "from 2023, road-type codes 5 and 6 in 2021) move crashes between levels.",
        "- Standard errors are clustered by province; with "
        f"{len(excluded.split(','))} provinces removed the clustering changes too.",
        "- The holdout check scores later years with a model that has no year term, so a "
        "change in recording between the training and test years counts as model error.",
        "",
    ]
    return "\n".join(lines)


def write_severity_card(path: Path = SEVERITY_CARD_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(severity_card(), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write_forecast_card())
    print(write_severity_card())
