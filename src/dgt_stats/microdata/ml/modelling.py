"""Severity models trained on the microdata feature tables, with honest evaluation.

Three tasks, each on real rows of a feature table (:mod:`features`):

* Catalonia: among crashes with a death or serious injury, was the crash fatal? One row per crash.
  Temporal design: train on the early years, choose the model on the next two, test on the last.
* Barcelona people: was a person recorded with a serious or fatal injury? One row per person
  record. Rows of one crash never straddle a split: cross-validation is grouped by
  ``Numero_expedient`` and the test set is the last three months, whose crashes are disjoint
  from the training months by construction (both are checked).
* Barcelona crashes: did a crash record a serious or fatal injury? One row per crash; a
  ``context`` model and a ``retrospective`` model that adds the police's recorded causes.

For each task: a prior-only baseline, a regularised logistic regression and gradient-boosted
trees, each with a two-point grid; the choice is made on validation data, never on the test set.
Metrics suited to rare outcomes are reported with N and prevalence: ROC-AUC, PR-AUC, Brier score
and its skill over the prevalence, balanced accuracy, precision, recall, F1 and the confusion
matrix at a threshold chosen on validation data, calibration intercept and slope. Importance is
permutation importance on the test set: how much the test ROC-AUC falls when a feature is
shuffled, a measure of what the model uses, not of cause.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from dgt_stats.microdata.ml import features as feature_tables
from dgt_stats.microdata.ml.features import FeatureTable

log = logging.getLogger(__name__)

SEED = 20251
N_FOLDS = 5
N_BOOT = 1000
N_PERMUTATIONS = 30
BARCELONA_TEST_MONTHS = 3
CATALONIA_VALIDATION_YEARS = 2
ROLLING_YEARS = 5

GRID: dict[str, tuple[dict, ...]] = {
    "logistic": ({"C": 0.05}, {"C": 0.5}),
    "boosted_trees": (
        {
            "learning_rate": 0.05,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 40,
            "l2_regularization": 1.0,
            "max_iter": 250,
        },
        {
            "learning_rate": 0.1,
            "max_leaf_nodes": 31,
            "min_samples_leaf": 20,
            "l2_regularization": 0.0,
            "max_iter": 150,
        },
    ),
}
ESTIMATOR_LABELS = {
    "baseline_prior": "baseline (training prevalence)",
    "logistic": "logistic regression (L2)",
    "boosted_trees": "gradient-boosted trees",
}

# Pre-declared rule for showing probabilities as estimates rather than as a ranking.
CALIBRATION_SLOPE_RANGE = (0.8, 1.25)
CALIBRATION_LARGE_TOLERANCE = 0.25  # |mean predicted - observed| as a share of the prevalence


# ----------------------------------------------------------------------------- pipelines
def make_model(
    table: FeatureTable,
    feature_set: str,
    geography: str,
    estimator: str,
    params: dict | None = None,
) -> Pipeline:
    feats = table.features(feature_set, geography)
    numeric = [f.column for f in feats if f.kind == "numeric"]
    binary = [f.column for f in feats if f.kind == "binary"]
    categorical = [f.column for f in feats if f.kind == "categorical"]
    params = params or {}
    if estimator == "baseline_prior":
        prep = ColumnTransformer(
            [("all", "drop", numeric + binary + categorical)], remainder="drop"
        )
        return Pipeline([("prep", prep), ("model", DummyClassifier(strategy="prior"))])
    if estimator == "logistic":
        prep = ColumnTransformer(
            [
                (
                    "num",
                    Pipeline(
                        [
                            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                            ("scale", StandardScaler()),
                        ]
                    ),
                    numeric,
                ),
                ("bin", SimpleImputer(strategy="most_frequent"), binary),
                (
                    "cat",
                    OneHotEncoder(
                        handle_unknown="infrequent_if_exist", min_frequency=20, sparse_output=False
                    ),
                    categorical,
                ),
            ]
        )
        model = LogisticRegression(max_iter=5000, **params)
        return Pipeline([("prep", prep), ("model", model)])
    if estimator == "boosted_trees":
        prep = ColumnTransformer(
            [
                ("num", "passthrough", numeric),
                ("bin", "passthrough", binary),
                (
                    "cat",
                    OrdinalEncoder(
                        handle_unknown="use_encoded_value",
                        unknown_value=np.nan,
                        encoded_missing_value=np.nan,
                        min_frequency=20,
                        max_categories=250,
                    ),
                    categorical,
                ),
            ]
        )
        mask = [False] * (len(numeric) + len(binary)) + [True] * len(categorical)
        model = HistGradientBoostingClassifier(
            categorical_features=mask, early_stopping=False, random_state=SEED, **params
        )
        return Pipeline([("prep", prep), ("model", model)])
    raise ValueError(estimator)


def predict(model: Pipeline, frame: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(frame)[:, 1]


# ----------------------------------------------------------------------------- metrics
def calibration_fit(y: np.ndarray, p: np.ndarray) -> dict:
    """Calibration intercept (in the large) and slope from a logistic recalibration."""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p))
    try:
        slope_fit = sm.GLM(y, sm.add_constant(logit), family=sm.families.Binomial()).fit()
        slope, slope_se = float(slope_fit.params[1]), float(slope_fit.bse[1])
        large_fit = sm.GLM(
            y, np.ones((len(y), 1)), family=sm.families.Binomial(), offset=logit
        ).fit()
        intercept = float(large_fit.params[0])
    except Exception:  # noqa: BLE001 - a degenerate test set cannot be recalibrated
        slope, slope_se, intercept = math.nan, math.nan, math.nan
    return {
        "calibration_intercept": intercept,
        "calibration_slope": slope,
        "calibration_slope_low": slope - 1.96 * slope_se,
        "calibration_slope_high": slope + 1.96 * slope_se,
    }


def best_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """The probability cut that maximises F1 on the data given (validation data only)."""
    candidates = np.unique(np.quantile(p, np.linspace(0.5, 0.999, 200)))
    scores = [f1_score(y, p >= t, zero_division=0) for t in candidates]
    return float(candidates[int(np.argmax(scores))]) if len(candidates) else 0.5


def metrics(y: np.ndarray, p: np.ndarray, threshold: float | None = None) -> dict:
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    prevalence = float(y.mean())
    out = {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "prevalence": prevalence,
        "roc_auc": float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else math.nan,
        "pr_auc": float(average_precision_score(y, p)) if y.sum() else math.nan,
        "brier": float(brier_score_loss(y, p)),
        "brier_skill": float(1 - brier_score_loss(y, p) / (prevalence * (1 - prevalence)))
        if 0 < prevalence < 1
        else math.nan,
        "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1])),
        "mean_predicted": float(p.mean()),
    }
    if threshold is not None:
        pred = p >= threshold
        tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
        out.update(
            threshold=float(threshold),
            precision=float(precision_score(y, pred, zero_division=0)),
            recall=float(recall_score(y, pred, zero_division=0)),
            f1=float(f1_score(y, pred, zero_division=0)),
            balanced_accuracy=float(balanced_accuracy_score(y, pred)),
            tn=int(tn),
            fp=int(fp),
            fn=int(fn),
            tp=int(tp),
        )
    return out


def resamples(n_rows: int, groups: np.ndarray | None, n: int, seed: int = SEED) -> list[np.ndarray]:
    """Bootstrap row indices; whole crashes are drawn when rows share one (``groups``)."""
    rng = np.random.default_rng(seed)
    if groups is None:
        return [rng.integers(0, n_rows, n_rows) for _ in range(n)]
    codes, uniques = pd.factorize(groups)
    members = [np.flatnonzero(codes == k) for k in range(len(uniques))]
    return [
        np.concatenate([members[k] for k in rng.integers(0, len(members), len(members))])
        for _ in range(n)
    ]


def paired_difference(
    y: np.ndarray,
    first: np.ndarray,
    second: np.ndarray,
    groups: np.ndarray | None = None,
    n: int = N_BOOT,
) -> dict:
    """ROC-AUC and PR-AUC of ``first`` minus ``second``, two scores of the same rows, with paired
    percentile intervals (both scores are recomputed on each resample)."""
    y, first, second = np.asarray(y), np.asarray(first), np.asarray(second)
    auc, ap = [], []
    for idx in resamples(len(y), groups, n):
        yy = y[idx]
        if 0 < yy.sum() < len(yy):
            auc.append(roc_auc_score(yy, first[idx]) - roc_auc_score(yy, second[idx]))
            ap.append(
                average_precision_score(yy, first[idx]) - average_precision_score(yy, second[idx])
            )
    return {
        "roc_auc_difference": float(roc_auc_score(y, first) - roc_auc_score(y, second)),
        "roc_auc_difference_low": float(np.percentile(auc, 2.5)),
        "roc_auc_difference_high": float(np.percentile(auc, 97.5)),
        "pr_auc_difference": float(
            average_precision_score(y, first) - average_precision_score(y, second)
        ),
        "pr_auc_difference_low": float(np.percentile(ap, 2.5)),
        "pr_auc_difference_high": float(np.percentile(ap, 97.5)),
    }


def bootstrap_ci(y: np.ndarray, p: np.ndarray, groups: np.ndarray | None, n: int = N_BOOT) -> dict:
    """Percentile intervals for ROC-AUC and PR-AUC, resampling crashes when rows share one."""
    y, p = np.asarray(y), np.asarray(p)
    index_sets = resamples(len(y), groups, n)
    aucs, aps = [], []
    for idx in index_sets:
        yy, pp = y[idx], p[idx]
        if 0 < yy.sum() < len(yy):
            aucs.append(roc_auc_score(yy, pp))
            aps.append(average_precision_score(yy, pp))
    return {
        "roc_auc_low": float(np.percentile(aucs, 2.5)),
        "roc_auc_high": float(np.percentile(aucs, 97.5)),
        "pr_auc_low": float(np.percentile(aps, 2.5)),
        "pr_auc_high": float(np.percentile(aps, 97.5)),
    }


def calibration_curve(y: np.ndarray, p: np.ndarray, bins: int) -> pd.DataFrame:
    frame = pd.DataFrame({"y": y, "p": p})
    frame["bin"] = pd.qcut(frame.p.rank(method="first"), bins, labels=False)
    out = frame.groupby("bin").agg(
        n=("y", "size"),
        observed=("y", "mean"),
        mean_predicted=("p", "mean"),
        positives=("y", "sum"),
    )
    return out.reset_index()


def probabilities_reliable(calibration: dict, prevalence: float, mean_predicted: float) -> bool:
    low, high = CALIBRATION_SLOPE_RANGE
    slope_ok = low <= calibration["calibration_slope"] <= high
    large_ok = abs(mean_predicted - prevalence) <= CALIBRATION_LARGE_TOLERANCE * prevalence
    return bool(slope_ok and large_ok)


# ----------------------------------------------------------------------------- splits
@dataclass
class Split:
    """Training, validation and test rows, and how validation is done."""

    design: str
    train: np.ndarray
    test: np.ndarray
    validation: np.ndarray | None = None  # a held-out block (temporal design)
    folds: list[tuple[np.ndarray, np.ndarray]] = field(default_factory=list)  # CV within train
    description: str = ""


def temporal_split(frame: pd.DataFrame, table: FeatureTable) -> Split:
    years = sorted(frame[table.time_column].dropna().unique())
    test_years = years[-1:]
    validation_years = years[-1 - CATALONIA_VALIDATION_YEARS : -1]
    train_years = years[: -1 - CATALONIA_VALIDATION_YEARS]
    year = frame[table.time_column]
    return Split(
        design="temporal",
        train=np.flatnonzero(year.isin(train_years)),
        validation=np.flatnonzero(year.isin(validation_years)),
        test=np.flatnonzero(year.isin(test_years)),
        description=(
            f"train {int(train_years[0])}-{int(train_years[-1])}, choose on "
            f"{int(validation_years[0])}-{int(validation_years[-1])}, test {int(test_years[0])}"
        ),
    )


def grouped_month_split(frame: pd.DataFrame, table: FeatureTable) -> Split:
    months = sorted(frame[table.time_column].astype(float).dropna().unique())
    test_months = months[-BARCELONA_TEST_MONTHS:]
    month = frame[table.time_column].astype(float)
    train = np.flatnonzero(~month.isin(test_months))
    test = np.flatnonzero(month.isin(test_months))
    groups = frame[table.group_column or table.id_column].to_numpy()
    y = frame[table.target].to_numpy()
    splitter = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    folds = [(train[a], train[b]) for a, b in splitter.split(train, y[train], groups[train])]
    return Split(
        design="grouped",
        train=train,
        test=test,
        folds=folds,
        description=(
            f"train months {int(months[0])}-{int(test_months[0]) - 1} with {N_FOLDS}-fold "
            f"cross-validation grouped by crash; test months {int(test_months[0])}-"
            f"{int(test_months[-1])}"
        ),
    )


def make_split(frame: pd.DataFrame, table: FeatureTable) -> Split:
    return (
        temporal_split(frame, table)
        if table.time_column == "year"
        else grouped_month_split(frame, table)
    )


def check_isolation(frame: pd.DataFrame, table: FeatureTable, split: Split) -> dict:
    """Ids and crashes shared between training and test rows (both must be zero)."""
    ids = frame[table.id_column].to_numpy()
    groups = frame[table.group_column or table.id_column].to_numpy()
    out = {
        "train_rows": len(split.train),
        "test_rows": len(split.test),
        "shared_ids": len(set(ids[split.train]) & set(ids[split.test])),
        "shared_groups": len(set(groups[split.train]) & set(groups[split.test])),
        "fold_shared_groups": sum(len(set(groups[a]) & set(groups[b])) for a, b in split.folds),
    }
    if split.validation is not None:
        out["validation_rows"] = len(split.validation)
        out["shared_groups_validation"] = len(
            set(groups[split.validation]) & (set(groups[split.train]) | set(groups[split.test]))
        )
    return out


# ----------------------------------------------------------------------------- fitting
def validation_predictions(
    frame: pd.DataFrame,
    table: FeatureTable,
    split: Split,
    feature_set: str,
    geography: str,
    estimator: str,
    params: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Out-of-sample predictions on validation data, and their row positions."""
    y = frame[table.target].to_numpy()
    if split.validation is not None:
        model = make_model(table, feature_set, geography, estimator, params)
        model.fit(frame.iloc[split.train], y[split.train])
        return predict(model, frame.iloc[split.validation]), split.validation
    preds, rows = [], []
    for a, b in split.folds:
        model = make_model(table, feature_set, geography, estimator, params)
        model.fit(frame.iloc[a], y[a])
        preds.append(predict(model, frame.iloc[b]))
        rows.append(b)
    return np.concatenate(preds), np.concatenate(rows)


def refit_rows(split: Split) -> np.ndarray:
    """Training rows for the final fit: training plus validation for the temporal design."""
    if split.validation is None:
        return split.train
    return np.sort(np.concatenate([split.train, split.validation]))


@dataclass
class VariantResult:
    table: str
    feature_set: str
    geography: str
    estimator: str
    params: dict
    validation: dict
    train_fit: dict
    test: dict
    threshold: float
    model: Pipeline | None = None
    test_pred: np.ndarray | None = None


def evaluate_variant(
    frame: pd.DataFrame, table: FeatureTable, split: Split, feature_set: str, geography: str
) -> list[VariantResult]:
    """Every estimator of one variant: best grid point on validation, then refit and test."""
    y = frame[table.target].to_numpy()
    results = []
    for estimator in ("baseline_prior", "logistic", "boosted_trees"):
        best = None
        for params in GRID.get(estimator, ({},)):
            p_val, rows = validation_predictions(
                frame, table, split, feature_set, geography, estimator, params
            )
            score = metrics(y[rows], p_val)
            if best is None or (score["roc_auc"] or 0) > (best[1]["roc_auc"] or 0):
                best = (params, score, p_val, rows)
        params, score, p_val, rows = best
        threshold = best_threshold(y[rows], p_val)
        score = metrics(y[rows], p_val, threshold)
        final_rows = refit_rows(split)
        model = make_model(table, feature_set, geography, estimator, params)
        model.fit(frame.iloc[final_rows], y[final_rows])
        p_train = predict(model, frame.iloc[final_rows])
        p_test = predict(model, frame.iloc[split.test])
        results.append(
            VariantResult(
                table=table.name,
                feature_set=feature_set,
                geography=geography,
                estimator=estimator,
                params=params,
                validation=score,
                train_fit=metrics(y[final_rows], p_train),
                test=metrics(y[split.test], p_test, threshold),
                threshold=threshold,
                model=model,
                test_pred=p_test,
            )
        )
    return results


def select(results: list[VariantResult]) -> VariantResult:
    """The fitted estimator with the best validation ROC-AUC (ties go to the simpler)."""
    order = {"logistic": 0, "boosted_trees": 1}
    candidates = [r for r in results if r.estimator != "baseline_prior"]
    return max(candidates, key=lambda r: (round(r.validation["roc_auc"], 3), -order[r.estimator]))


def rolling_origin(frame: pd.DataFrame, table: FeatureTable, chosen: VariantResult) -> pd.DataFrame:
    """Train on every earlier year, test on one year, for the last few years (temporal design)."""
    y = frame[table.target].to_numpy()
    years = sorted(frame[table.time_column].unique())
    rows = []
    for year in years[-ROLLING_YEARS:]:
        train = np.flatnonzero(frame[table.time_column] < year)
        test = np.flatnonzero(frame[table.time_column] == year)
        model = make_model(
            table, chosen.feature_set, chosen.geography, chosen.estimator, chosen.params
        )
        model.fit(frame.iloc[train], y[train])
        rows.append(
            {
                "evaluation": "rolling origin",
                "test_block": str(int(year)),
                **metrics(y[test], predict(model, frame.iloc[test])),
            }
        )
    return pd.DataFrame(rows)


def random_cv(frame: pd.DataFrame, table: FeatureTable, chosen: VariantResult) -> pd.DataFrame:
    """K-fold cross-validation over all rows: by row (random) and, where rows share a crash,
    grouped by crash. The random version is shown only as a contrast to the honest designs."""
    y = frame[table.target].to_numpy()
    rows = []
    designs = [
        (
            "random rows (stratified)",
            StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED),
            None,
        )
    ]
    if table.group_column:
        designs = [
            (
                "grouped by crash",
                StratifiedGroupKFold(N_FOLDS, shuffle=True, random_state=SEED),
                frame[table.group_column].to_numpy(),
            )
        ] + designs
    for name, splitter, groups in designs:
        for k, (a, b) in enumerate(splitter.split(frame, y, groups)):
            model = make_model(
                table, chosen.feature_set, chosen.geography, chosen.estimator, chosen.params
            )
            model.fit(frame.iloc[a], y[a])
            rows.append(
                {
                    "evaluation": f"{N_FOLDS}-fold CV, {name}",
                    "test_block": f"fold {k + 1}",
                    **metrics(y[b], predict(model, frame.iloc[b])),
                }
            )
    return pd.DataFrame(rows)


def importance(
    frame: pd.DataFrame, table: FeatureTable, split: Split, chosen: VariantResult
) -> pd.DataFrame:
    y = frame[table.target].to_numpy()
    columns = table.columns(chosen.feature_set, chosen.geography)
    test = frame.iloc[split.test]
    result = permutation_importance(
        chosen.model,
        test[columns],
        y[split.test],
        scoring="roc_auc",
        n_repeats=N_PERMUTATIONS,
        random_state=SEED,
    )
    kinds = {f.column: f for f in table.catalogue}
    out = pd.DataFrame(
        {
            "feature": columns,
            "kind": [kinds[c].kind for c in columns],
            "status": [kinds[c].status for c in columns],
            "auc_drop_mean": result.importances_mean,
            "auc_drop_std": result.importances_std,
        }
    )
    return out.sort_values("auc_drop_mean", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------------- driver
@dataclass
class TaskResult:
    table: FeatureTable
    split: Split
    isolation: dict
    variants: list[VariantResult]
    detailed: dict[str, dict]  # feature_set -> outputs for the primary geography
    stability: pd.DataFrame


def run_task(name: str) -> TaskResult:
    table = feature_tables.table_by_name(name)
    frame = feature_tables.read(name).reset_index(drop=True)
    split = make_split(frame, table)
    isolation = check_isolation(frame, table, split)
    if isolation["shared_groups"] or isolation["fold_shared_groups"]:
        raise AssertionError(f"{name}: a crash appears on both sides of a split: {isolation}")
    y = frame[table.target].to_numpy()
    groups = frame[table.group_column].to_numpy() if table.group_column else None
    variants: list[VariantResult] = []
    detailed: dict[str, dict] = {}
    for feature_set in table.feature_sets:
        for geography in table.geography_variants:
            log.info("%s: %s / %s", name, feature_set, geography)
            results = evaluate_variant(frame, table, split, feature_set, geography)
            variants.extend(results)
            if geography != table.primary_geography:
                continue
            chosen = select(results)
            p = chosen.test_pred
            yt = y[split.test]
            cal = calibration_fit(yt, p)
            bins = 10 if yt.sum() >= 150 else 5
            detailed[feature_set] = {
                "chosen": chosen,
                "baseline": next(r for r in results if r.estimator == "baseline_prior"),
                "all": results,
                "test_ci": bootstrap_ci(yt, p, groups[split.test] if groups is not None else None),
                "calibration": cal,
                "calibration_curve": calibration_curve(yt, p, bins),
                "reliable_probabilities": probabilities_reliable(
                    cal, chosen.test["prevalence"], chosen.test["mean_predicted"]
                ),
                "importance": importance(frame, table, split, chosen),
            }
    primary = detailed[table.primary_set]["chosen"]
    stability = (
        rolling_origin(frame, table, primary) if split.design == "temporal" else pd.DataFrame()
    )
    stability = pd.concat([stability, random_cv(frame, table, primary)], ignore_index=True)
    return TaskResult(table, split, isolation, variants, detailed, stability)


# ----------------------------------------------------------------------------- tables
def variant_table(results: list[TaskResult]) -> pd.DataFrame:
    rows = []
    for task in results:
        for v in task.variants:
            base = {
                "model": task.table.name,
                "feature_set": v.feature_set,
                "geography": v.geography,
                "estimator": v.estimator,
                "params": ", ".join(f"{k}={val}" for k, val in v.params.items()),
            }
            for stage, values in (
                ("validation", v.validation),
                ("training fit", v.train_fit),
                ("test", v.test),
            ):
                rows.append({**base, "evaluated_on": stage, **values})
    return pd.DataFrame(rows)


def selected_table(results: list[TaskResult]) -> pd.DataFrame:
    rows = []
    for task in results:
        for feature_set, d in task.detailed.items():
            chosen, baseline = d["chosen"], d["baseline"]
            rows.append(
                {
                    "model": task.table.name,
                    "feature_set": feature_set,
                    "geography": task.table.primary_geography,
                    "primary": feature_set == task.table.primary_set,
                    "estimator": chosen.estimator,
                    "params": ", ".join(f"{k}={val}" for k, val in chosen.params.items()),
                    "design": task.split.description,
                    "validation_roc_auc": chosen.validation["roc_auc"],
                    "baseline_test_roc_auc": baseline.test["roc_auc"],
                    "baseline_test_brier": baseline.test["brier"],
                    **{k: v for k, v in chosen.test.items()},
                    **d["test_ci"],
                    **d["calibration"],
                    "probabilities_shown_as_estimates": d["reliable_probabilities"],
                    "train_rows": task.isolation["train_rows"]
                    + task.isolation.get("validation_rows", 0),
                    "train_positives": int(chosen.train_fit["positives"]),
                }
            )
    return pd.DataFrame(rows)


def calibration_table(results: list[TaskResult]) -> pd.DataFrame:
    frames = []
    for task in results:
        for feature_set, d in task.detailed.items():
            frames.append(
                d["calibration_curve"].assign(model=task.table.name, feature_set=feature_set)
            )
    return pd.concat(frames, ignore_index=True)


def importance_table(results: list[TaskResult]) -> pd.DataFrame:
    frames = []
    for task in results:
        for feature_set, d in task.detailed.items():
            frames.append(
                d["importance"].assign(
                    model=task.table.name, feature_set=feature_set, estimator=d["chosen"].estimator
                )
            )
    return pd.concat(frames, ignore_index=True)


def stability_table(results: list[TaskResult]) -> pd.DataFrame:
    return pd.concat([t.stability.assign(model=t.table.name) for t in results], ignore_index=True)


def isolation_table(results: list[TaskResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"model": t.table.name, "design": t.split.description, **t.isolation} for t in results]
    )


def geography_table(results: list[TaskResult]) -> pd.DataFrame:
    rows = []
    for task in results:
        for v in task.variants:
            if v.estimator == "baseline_prior":
                continue
            rows.append(
                {
                    "model": task.table.name,
                    "feature_set": v.feature_set,
                    "geography": v.geography,
                    "estimator": v.estimator,
                    "training_fit_roc_auc": v.train_fit["roc_auc"],
                    "validation_roc_auc": v.validation["roc_auc"],
                    "test_roc_auc": v.test["roc_auc"],
                    "gap_training_minus_test": v.train_fit["roc_auc"] - v.test["roc_auc"],
                }
            )
    return pd.DataFrame(rows)
