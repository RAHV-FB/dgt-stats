"""Scores for a probability forecast of a yes/no outcome: ranking, calibration, bootstrap and
Wilson intervals. Used to evaluate the Catalan severity model (:mod:`dgt_stats.severity_model`)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

from dgt_stats.microdata.common import wilson as _wilson

SEED = 20261007
N_BOOT = 1000


def calibration_fit(y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    """Calibration slope and intercept: logistic regression of the outcome on logit(p)."""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p))
    if np.ptp(logit) == 0:  # a constant prediction has no slope
        return (np.nan, np.nan)
    design = np.column_stack([np.ones_like(logit), logit])
    fit = sm.GLM(y, design, family=sm.families.Binomial()).fit()
    return float(fit.params[1]), float(fit.params[0])


def calibration_in_the_large(y: np.ndarray, p: np.ndarray) -> float:
    """Intercept with the slope fixed at 1 (offset logit p): 0 means mean predictions are right."""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p))
    fit = sm.GLM(y, np.ones((len(y), 1)), family=sm.families.Binomial(), offset=logit).fit()
    return float(fit.params[0])


def scores(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    slope, intercept = calibration_fit(y, p)
    prevalence = y.mean()
    brier = brier_score_loss(y, p)
    return {
        "n": len(y),
        "positives": int(y.sum()),
        "prevalence": float(prevalence),
        "mean_predicted": float(p.mean()),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "brier": float(brier),
        "brier_skill": float(1 - brier / (prevalence * (1 - prevalence))),
        "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "calibration_in_the_large": calibration_in_the_large(y, p),
    }


def bootstrap_intervals(
    y: np.ndarray,
    predictions: dict[str, np.ndarray],
    reference: str | None = None,
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> pd.DataFrame:
    """95% percentile intervals of ROC-AUC, Brier score and log loss, and of each estimator's
    difference from ``reference`` on the same resampled rows (paired)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    draws: dict[tuple[str, str], list[float]] = {}
    for _ in range(n_boot):
        index = rng.integers(0, n, n)
        yb = y[index]
        if yb.min() == yb.max():
            continue
        values = {}
        for name, p in predictions.items():
            pb = p[index]
            values[name] = {
                "roc_auc": roc_auc_score(yb, pb),
                "brier": brier_score_loss(yb, pb),
                "log_loss": log_loss(yb, np.clip(pb, 1e-6, 1 - 1e-6)),
            }
        for name, metrics in values.items():
            for metric, value in metrics.items():
                draws.setdefault((name, metric), []).append(value)
                if reference and name != reference:
                    draws.setdefault((name, f"{metric}_minus_{reference}"), []).append(
                        value - values[reference][metric]
                    )
    rows = [
        {
            "estimator": name,
            "metric": metric,
            "low": float(np.percentile(values, 2.5)),
            "high": float(np.percentile(values, 97.5)),
        }
        for (name, metric), values in draws.items()
    ]
    return pd.DataFrame(rows)


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% interval of a share, as two floats."""
    low, high = _wilson(k, n, z)
    return float(low), float(high)


def calibration_groups(y: np.ndarray, p: np.ndarray, n_groups: int = 10) -> pd.DataFrame:
    """Predicted against observed in ``n_groups`` equal-sized groups of predicted probability
    (tenths by default), with Wilson 95% intervals for the observed share."""
    order = np.argsort(p, kind="stable")
    group = np.empty(len(p), dtype=int)
    group[order] = np.arange(len(p)) * n_groups // len(p)
    frame = pd.DataFrame({"y": y, "p": p, "group": group + 1})
    out = frame.groupby("group").agg(
        n=("y", "size"),
        positives=("y", "sum"),
        mean_predicted=("p", "mean"),
        predicted_low=("p", "min"),
        predicted_high=("p", "max"),
    )
    out["observed"] = out.positives / out.n
    limits = [wilson(k, n) for k, n in zip(out.positives, out.n)]
    out["observed_low"] = [low for low, _ in limits]
    out["observed_high"] = [high for _, high in limits]
    return out.reset_index()


# --------------------------------------------------------------------------- Catalonia
