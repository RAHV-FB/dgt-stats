"""Does a model add anything over a descriptive table?

For each source model the simplest honest competitor is a lookup table: the outcome share of each
group in the training rows, read off for each test row. The grouping is declared here, before
looking at the test rows, as the one a descriptive analysis would lead with:

* Catalonia: crash subtype x zone detail (how and where the crash happened);
* Barcelona people: road user (role x vehicle type on the record);
* Barcelona crashes: accident type.

Shares are smoothed toward the training prevalence with :data:`PSEUDO_COUNT` pseudo-rows, so a
group seen a handful of times does not score 0 or 1, and a group never seen in training gets the
prevalence. Both the model and the rule are scored on the same test rows; the difference in
ROC-AUC and PR-AUC gets a paired bootstrap interval (crashes resampled where people share one).

The verdict rule, declared in advance: a model **adds signal over the table** when its ROC-AUC
exceeds the rule's by at least :data:`MIN_GAIN` and the 95% interval of the difference excludes 0.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from dgt_stats.microdata.ml import features, modelling

PSEUDO_COUNT = 20
MIN_GAIN = 0.02
N_BOOT = 1000

RULES: dict[str, tuple[str, ...]] = {
    "catalonia_crash_severity": ("D_SUBTIPUS_ACCIDENT", "D_SUBZONA"),
    "barcelona_person_severity": ("person_role", "associated_vehicle_group"),
    "barcelona_crash_severity": ("accident_type",),
}


def fit_rule(train: pd.DataFrame, target: str, columns: tuple[str, ...]) -> tuple[pd.Series, float]:
    prevalence = float(train[target].mean())
    key = train[list(columns)].astype(str).agg(" | ".join, axis=1)
    stats = train.groupby(key)[target].agg(["sum", "size"])
    shares = (stats["sum"] + PSEUDO_COUNT * prevalence) / (stats["size"] + PSEUDO_COUNT)
    return shares, prevalence


def apply_rule(
    frame: pd.DataFrame, shares: pd.Series, prevalence: float, columns: tuple[str, ...]
) -> np.ndarray:
    key = frame[list(columns)].astype(str).agg(" | ".join, axis=1)
    return key.map(shares).fillna(prevalence).to_numpy(dtype=float)


def compare(task: modelling.TaskResult) -> dict:
    table = task.table
    columns = RULES[table.name]
    frame = features.read(table.name).reset_index(drop=True)
    train = frame.iloc[modelling.refit_rows(task.split)]
    test = frame.iloc[task.split.test]
    shares, prevalence = fit_rule(train, table.target, columns)
    rule = apply_rule(test, shares, prevalence, columns)
    chosen = task.detailed[table.primary_set]["chosen"]
    model = chosen.test_pred
    y = test[table.target].to_numpy()
    groups = test[table.group_column].to_numpy() if table.group_column else None
    diff = modelling.paired_difference(y, model, rule, groups, n=N_BOOT)
    auc_model, auc_rule = roc_auc_score(y, model), roc_auc_score(y, rule)
    low, high = diff["roc_auc_difference_low"], diff["roc_auc_difference_high"]
    gain = auc_model - auc_rule
    adds = bool(gain >= MIN_GAIN and low > 0)
    return {
        "model": table.name,
        "rule": " x ".join(columns),
        "rule_groups_in_training": int(len(shares)),
        "test_n": int(len(y)),
        "test_positives": int(y.sum()),
        "model_estimator": chosen.estimator,
        "model_roc_auc": float(auc_model),
        "rule_roc_auc": float(auc_rule),
        "roc_auc_gain": float(gain),
        "roc_auc_gain_low": float(low),
        "roc_auc_gain_high": float(high),
        "model_pr_auc": float(average_precision_score(y, model)),
        "rule_pr_auc": float(average_precision_score(y, rule)),
        "pr_auc_gain_low": diff["pr_auc_difference_low"],
        "pr_auc_gain_high": diff["pr_auc_difference_high"],
        "model_adds_signal_over_table": adds,
    }


def run(results: list[modelling.TaskResult]) -> pd.DataFrame:
    return pd.DataFrame([compare(task) for task in results if task.table.name in RULES])
