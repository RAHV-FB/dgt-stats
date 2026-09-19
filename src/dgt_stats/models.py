"""Crash-severity logistic models: fitting, tidy odds ratios, marginal effects and diagnostics.

The design is main effects only, built by hand from the ordered categoricals of
:mod:`dgt_stats.features` (reference level dropped), fitted with a binomial GLM and cluster-robust
covariance by province. The fits are slow enough (a few minutes for everything) to live behind
``scripts/model.py``, which writes the result tables the site reads.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import brier_score_loss, roc_auc_score

from dgt_stats import features

log = logging.getLogger(__name__)

HOLDOUT_YEARS = (2023, 2024)
STABILITY_TERMS = 10
PROFILE_YEAR = "2024"

# Named crash profiles for the predicted-probability table; unspecified predictors sit at reference.
PROFILES: dict[str, dict[str, str]] = {
    "Urban street, side collision, daylight, two vehicles": {},
    "Urban street, pedestrian struck, dark with lighting": {
        "crash_type": "pedestrian struck",
        "lighting": "dark, street lighting",
    },
    "Conventional road, head-on collision, daylight, two vehicles": {
        "zone": "interurban road",
        "road": "conventional",
        "crash_type": "head-on collision",
        "alignment": "straight",
    },
    "Conventional road, run-off in a curve, dark without lighting, one vehicle": {
        "zone": "interurban road",
        "road": "conventional",
        "crash_type": "run-off or overturn",
        "alignment": "curve",
        "lighting": "dark, no lighting",
        "vehicles": "1 vehicle",
        "hour_band": "00-06",
    },
    "Motorway, rear-end collision, daylight, two vehicles": {
        "zone": "interurban road",
        "road": "motorway",
        "crash_type": "rear-end or chain collision",
        "alignment": "straight",
    },
    "Dual carriageway, run-off, night, one vehicle, weekend": {
        "zone": "interurban road",
        "road": "dual carriageway",
        "crash_type": "run-off or overturn",
        "alignment": "straight",
        "lighting": "dark, no lighting",
        "vehicles": "1 vehicle",
        "weekend": "weekend",
        "hour_band": "00-06",
    },
}


@dataclass
class Fit:
    outcome: str
    predictors: tuple[str, ...]
    columns: list[str]  # design columns after the intercept, "predictor=level"
    params: pd.Series
    cov: pd.DataFrame
    n: int
    events: int


def design_matrix(frame: pd.DataFrame, predictors: tuple[str, ...]) -> pd.DataFrame:
    """Intercept plus one 0/1 column per non-reference level, named ``predictor=level``."""
    blocks = [pd.Series(1.0, index=frame.index, name="intercept")]
    for name in predictors:
        column = frame[name]
        for level in column.cat.categories[1:]:
            blocks.append((column == level).astype(float).rename(f"{name}={level}"))
    return pd.concat(blocks, axis=1)


def fit_severity(
    frame: pd.DataFrame,
    outcome: str,
    predictors: tuple[str, ...] | None = None,
    cluster: str | None = "province",
) -> Fit:
    """Binomial GLM (logit link) with cluster-robust covariance; returns the parameters and cov."""
    predictors = predictors or tuple(features.PREDICTORS)
    design = design_matrix(frame, predictors)
    y = frame[outcome].astype(float).to_numpy()
    model = sm.GLM(y, design.to_numpy(), family=sm.families.Binomial())
    if cluster is not None:
        groups = pd.factorize(frame[cluster])[0]
        result = model.fit(cov_type="cluster", cov_kwds={"groups": groups})
    else:
        result = model.fit()
    params = pd.Series(result.params, index=design.columns)
    cov = pd.DataFrame(result.cov_params(), index=design.columns, columns=design.columns)
    return Fit(
        outcome=outcome,
        predictors=predictors,
        columns=list(design.columns[1:]),
        params=params,
        cov=cov,
        n=len(frame),
        events=int(y.sum()),
    )


def odds_ratios(fit: Fit, alpha: float = 0.05) -> pd.DataFrame:
    """Tidy table: predictor, level, reference, odds ratio with interval, p-value, and the
    reference rows themselves (odds ratio 1) so forest plots show every level."""
    from scipy import stats

    z = stats.norm.ppf(1 - alpha / 2)
    records = []
    for name in fit.predictors:
        spec_levels = None
        for column in fit.columns:
            if not column.startswith(f"{name}="):
                continue
            level = column.split("=", 1)[1]
            estimate = float(fit.params[column])
            se = float(np.sqrt(fit.cov.loc[column, column]))
            records.append(
                {
                    "outcome": fit.outcome,
                    "predictor": name,
                    "predictor_label": features.PREDICTOR_LABELS.get(name, name),
                    "level": level,
                    "is_reference": False,
                    "log_odds": estimate,
                    "se": se,
                    "odds_ratio": float(np.exp(estimate)),
                    "or_low": float(np.exp(estimate - z * se)),
                    "or_high": float(np.exp(estimate + z * se)),
                    "p_value": float(2 * stats.norm.sf(abs(estimate / se))) if se > 0 else np.nan,
                }
            )
            spec_levels = spec_levels or True
    out = pd.DataFrame.from_records(records)
    return out


def _reference_rows(frame: pd.DataFrame, fit: Fit) -> pd.DataFrame:
    records = []
    for name in fit.predictors:
        reference = str(frame[name].cat.categories[0])
        records.append(
            {
                "outcome": fit.outcome,
                "predictor": name,
                "predictor_label": features.PREDICTOR_LABELS.get(name, name),
                "level": reference,
                "is_reference": True,
                "log_odds": 0.0,
                "se": 0.0,
                "odds_ratio": 1.0,
                "or_low": 1.0,
                "or_high": 1.0,
                "p_value": np.nan,
            }
        )
    return pd.DataFrame.from_records(records)


def coefficient_table(frame: pd.DataFrame, fit: Fit) -> pd.DataFrame:
    """Odds ratios plus the reference rows, in predictor and level order, with level counts."""
    table = pd.concat([_reference_rows(frame, fit), odds_ratios(fit)], ignore_index=True)
    counts = []
    shares = []
    for row in table.itertuples():
        mask = frame[row.predictor] == row.level
        counts.append(int(mask.sum()))
        shares.append(float(frame.loc[mask, fit.outcome].mean()) if mask.any() else np.nan)
    table["crashes"] = counts
    table["observed_share"] = shares
    order = {name: i for i, name in enumerate(fit.predictors)}
    level_order = {
        (name, level): i
        for name in fit.predictors
        for i, level in enumerate(frame[name].cat.categories)
    }
    table["_p"] = table.predictor.map(order)
    table["_l"] = [level_order[(p, lv)] for p, lv in zip(table.predictor, table.level)]
    table = table.sort_values(["_p", "_l"]).drop(columns=["_p", "_l"]).reset_index(drop=True)
    table["n"] = fit.n
    table["events"] = fit.events
    return table


def predict(fit: Fit, design: pd.DataFrame) -> np.ndarray:
    linear = design[fit.params.index].to_numpy() @ fit.params.to_numpy()
    return 1 / (1 + np.exp(-linear))


def marginal_effects(frame: pd.DataFrame, fit: Fit) -> pd.DataFrame:
    """Average marginal effect of each level against its reference, in probability points.

    For each predictor and level, every crash is set to that level (all else as observed) and the
    mean predicted probability is compared with the mean when every crash is set to the reference.
    """
    design = design_matrix(frame, fit.predictors)
    records = []
    for name in fit.predictors:
        level_columns = [c for c in fit.columns if c.startswith(f"{name}=")]
        base = design.copy()
        base[level_columns] = 0.0
        p_reference = predict(fit, base).mean()
        records.append(
            {
                "outcome": fit.outcome,
                "predictor": name,
                "predictor_label": features.PREDICTOR_LABELS.get(name, name),
                "level": str(frame[name].cat.categories[0]),
                "is_reference": True,
                "probability": float(p_reference),
                "effect": 0.0,
            }
        )
        for column in level_columns:
            counterfactual = base.copy()
            counterfactual[column] = 1.0
            p_level = predict(fit, counterfactual).mean()
            records.append(
                {
                    "outcome": fit.outcome,
                    "predictor": name,
                    "predictor_label": features.PREDICTOR_LABELS.get(name, name),
                    "level": column.split("=", 1)[1],
                    "is_reference": False,
                    "probability": float(p_level),
                    "effect": float(p_level - p_reference),
                }
            )
    return pd.DataFrame.from_records(records)


def holdout_check(
    frame: pd.DataFrame, outcome: str, holdout_years: tuple[int, ...] = HOLDOUT_YEARS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit on the years before ``holdout_years``, score the held-out years.

    Returns (calibration by decile, summary with Brier score, AUC and base rates). The year
    predictor is excluded from the holdout fit, so the model has to carry across years unaided.
    """
    predictors = tuple(name for name in features.PREDICTORS if name != "year")
    train = frame[~frame.year.isin(holdout_years)]
    test = frame[frame.year.isin(holdout_years)]
    fit = fit_severity(train, outcome, predictors, cluster=None)
    scores = predict(fit, design_matrix(test, predictors))
    y = test[outcome].astype(int).to_numpy()
    deciles = pd.qcut(scores, 10, labels=False, duplicates="drop")
    calibration = (
        pd.DataFrame({"decile": deciles + 1, "predicted": scores, "observed": y})
        .groupby("decile")
        .agg(
            crashes=("observed", "size"),
            predicted=("predicted", "mean"),
            observed=("observed", "mean"),
        )
        .reset_index()
    )
    calibration["outcome"] = outcome
    summary = pd.DataFrame(
        [
            {
                "outcome": outcome,
                "train_years": f"{train.year.min()}–{train.year.max()}",
                "test_years": f"{test.year.min()}–{test.year.max()}",
                "train_crashes": len(train),
                "test_crashes": len(test),
                "test_events": int(y.sum()),
                "base_rate_train": float(train[outcome].mean()),
                "base_rate_test": float(y.mean()),
                "mean_predicted": float(scores.mean()),
                "brier": float(brier_score_loss(y, scores)),
                "brier_base_rate": float(brier_score_loss(y, np.full_like(scores, y.mean()))),
                "auc": float(roc_auc_score(y, scores)),
            }
        ]
    )
    return calibration, summary


def year_stability(frame: pd.DataFrame, full: Fit, terms: int = STABILITY_TERMS) -> pd.DataFrame:
    """Refit per year (without the year predictor) for the largest effects of the full model."""
    ranked = odds_ratios(full)
    ranked = ranked[ranked.predictor != "year"]
    ranked = ranked.reindex(ranked.log_odds.abs().sort_values(ascending=False).index)
    keep = ranked.head(terms)
    predictors = tuple(name for name in full.predictors if name != "year")
    records = []
    for year, group in frame.groupby("year"):
        fit = fit_severity(group, full.outcome, predictors, cluster=None)
        table = odds_ratios(fit).set_index(["predictor", "level"])
        for row in keep.itertuples():
            key = (row.predictor, row.level)
            if key not in table.index:
                continue
            got = table.loc[key]
            records.append(
                {
                    "outcome": full.outcome,
                    "year": int(year),
                    "predictor": row.predictor,
                    "predictor_label": row.predictor_label,
                    "level": row.level,
                    "odds_ratio": float(got.odds_ratio),
                    "or_low": float(got.or_low),
                    "or_high": float(got.or_high),
                    "full_model_odds_ratio": float(row.odds_ratio),
                    "full_model_or_low": float(row.or_low),
                    "full_model_or_high": float(row.or_high),
                }
            )
    out = pd.DataFrame.from_records(records)
    out["within_full_interval"] = (out.odds_ratio >= out.full_model_or_low) & (
        out.odds_ratio <= out.full_model_or_high
    )
    return out


def _profile_design(frame: pd.DataFrame, fit: Fit, settings: dict[str, str]) -> pd.DataFrame:
    row = {"intercept": 1.0}
    for column in fit.columns:
        row[column] = 0.0
    for name in fit.predictors:
        level = settings.get(name)
        if name == "year" and level is None:
            level = PROFILE_YEAR
        if level is None or level == str(frame[name].cat.categories[0]):
            continue
        column = f"{name}={level}"
        if column not in row:
            raise ValueError(f"profile level not in the model: {column}")
        row[column] = 1.0
    return pd.DataFrame([row])


def profiles(frame: pd.DataFrame, fits: dict[str, Fit]) -> pd.DataFrame:
    """Predicted probability of each outcome for the named crash profiles (year 2024)."""
    records = []
    for name, settings in PROFILES.items():
        record: dict[str, object] = {"profile": name}
        for outcome, fit in fits.items():
            record[outcome] = float(predict(fit, _profile_design(frame, fit, settings))[0])
        records.append(record)
    return pd.DataFrame.from_records(records)


def predicted_grid(
    frame: pd.DataFrame, fit: Fit, rows: str = "road", columns: str = "lighting"
) -> pd.DataFrame:
    """Predicted probability over every combination of two predictors, others at reference."""
    records = []
    for row_level in frame[rows].cat.categories:
        for column_level in frame[columns].cat.categories:
            settings = {rows: str(row_level), columns: str(column_level)}
            if rows == "road" and row_level != "urban street":
                settings["zone"] = "interurban road"
            probability = float(predict(fit, _profile_design(frame, fit, settings))[0])
            records.append(
                {
                    "outcome": fit.outcome,
                    rows: str(row_level),
                    columns: str(column_level),
                    "probability": probability,
                }
            )
    return pd.DataFrame.from_records(records)
