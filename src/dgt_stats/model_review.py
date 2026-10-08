"""An independent re-evaluation of the repository's predictive models.

The models were built and scored by :mod:`dgt_stats.microdata.ml`. This module refits them with its
own code from the feature tables, so that a score reported there is reproduced here or the
difference is explained, and it adds what the original evaluation lacked:

* **rolling-origin predictions for the Catalan model**: every year from 2016 to 2023 is predicted
  by models fitted only on the years before it, so the pooled out-of-sample predictions number
  about 13,000 crashes and 1,600 fatal ones rather than the single 2023 test year (1,732 and 209);
* the same predictions from **three simple competitors**: the training prevalence, the fatal share
  of the crash's type and zone in the training years (the original benchmark), and a logistic
  regression on main effects;
* **calibration** for every model: predicted against observed by probability band, with Wilson
  intervals and counts, the calibration slope and intercept, the Brier score and log loss;
* bootstrap intervals and paired differences for every comparison.

Nothing here selects a model on the years it is tested on: hyperparameters are the ones the
original pipeline chose on 2021–2022, and the rolling origins only ever see earlier years.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder

from dgt_stats.paths import FEATURES_DATA_DIR

SEED = 20261007
N_BOOT = 1000
ROLLING_TEST_YEARS: tuple[int, ...] = tuple(range(2016, 2024))

CATALONIA_FEATURES = FEATURES_DATA_DIR / "catalonia_crash_severity.parquet"
# The original pipeline's primary feature set (context, broad geography).
CATALONIA_NUMERIC = ("year", "n_units")
CATALONIA_BINARY = (
    "single_unit",
    "involves_pedestrian",
    "involves_bicycle",
    "involves_moped",
    "involves_motorcycle",
    "involves_light_vehicle",
    "involves_heavy_vehicle",
    "involves_other_unit",
)
CATALONIA_CATEGORICAL = (
    "month",
    "weekday",
    "hour_band",
    "D_TIPUS_VIA",
    "D_TITULARITAT_VIA",
    "D_SUBZONA",
    "D_FUNC_ESP_VIA",
    "D_INTER_SECCIO",
    "D_SUBTIPUS_TRAM",
    "D_REGULACIO_PRIORITAT",
    "D_SUPERFICIE",
    "D_LLUMINOSITAT",
    "D_CLIMATOLOGIA",
    "D_VENT",
    "D_BOIRA",
    "D_CIRCULACIO_MESURES_ESP",
    "D_SUBTIPUS_ACCIDENT",
    "speed_limit_category",
    "demarcation",
)
# The original benchmark: the fatal share of each crash type x zone in the training years.
CATALONIA_TABLE_KEYS = ("D_SUBTIPUS_ACCIDENT", "D_SUBZONA")
# The hyperparameters the original pipeline chose on 2021-2022 (docs/models/catalonia_*.md).
BOOSTED_PARAMS = {
    "learning_rate": 0.1,
    "max_leaf_nodes": 31,
    "min_samples_leaf": 20,
    "l2_regularization": 0.0,
    "max_iter": 150,
}
LOGISTIC_C = 0.5
PROBABILITY_BANDS: tuple[float, ...] = (0.0, 0.03, 0.06, 0.10, 0.15, 0.20, 0.30, 0.45, 1.0)


# --------------------------------------------------------------------------- estimators


def logistic_pipeline(
    numeric: tuple[str, ...], binary: tuple[str, ...], categorical: tuple[str, ...], c: float
) -> Pipeline:
    prep = ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median"), list(numeric)),
            ("bin", SimpleImputer(strategy="most_frequent"), list(binary)),
            (
                "cat",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist", min_frequency=20, sparse_output=False
                ),
                list(categorical),
            ),
        ]
    )
    model = LogisticRegression(C=c, max_iter=5000)
    return Pipeline([("prep", prep), ("model", model)])


def boosted_pipeline(
    numeric: tuple[str, ...], binary: tuple[str, ...], categorical: tuple[str, ...], params: dict
) -> Pipeline:
    prep = ColumnTransformer(
        [
            ("num", "passthrough", list(numeric) + list(binary)),
            (
                "cat",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value", unknown_value=-1, encoded_missing_value=-1
                ),
                list(categorical),
            ),
        ]
    )
    n_numeric = len(numeric) + len(binary)
    mask = [False] * n_numeric + [True] * len(categorical)
    model = HistGradientBoostingClassifier(categorical_features=mask, random_state=SEED, **params)
    return Pipeline([("prep", prep), ("model", model)])


def table_rates(
    train: pd.DataFrame, target: str, keys: tuple[str, ...], strength: float = 20.0
) -> pd.DataFrame:
    """Outcome share of each group, shrunk towards the overall share by ``strength`` pseudo-rows."""
    prior = train[target].mean()
    groups = train.groupby(list(keys), observed=True)[target].agg(["sum", "size"])
    groups["rate"] = (groups["sum"] + strength * prior) / (groups["size"] + strength)
    return groups[["rate"]].reset_index().assign(prior=prior)


def apply_table(rates: pd.DataFrame, frame: pd.DataFrame, keys: tuple[str, ...]) -> np.ndarray:
    merged = frame[list(keys)].merge(rates, on=list(keys), how="left")
    return merged.rate.fillna(rates.prior.iloc[0]).to_numpy()


# --------------------------------------------------------------------------- metrics


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
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centre - half, centre + half)


def calibration_table(
    y: np.ndarray, p: np.ndarray, bands: tuple[float, ...] = PROBABILITY_BANDS
) -> pd.DataFrame:
    """Predicted against observed by fixed probability band, with Wilson 95% intervals."""
    band = pd.cut(p, bins=list(bands), include_lowest=True, right=False)
    frame = pd.DataFrame({"y": y, "p": p, "band": band})
    out = frame.groupby("band", observed=True).agg(
        n=("y", "size"), positives=("y", "sum"), mean_predicted=("p", "mean")
    )
    out["observed"] = out.positives / out.n
    limits = [wilson(k, n) for k, n in zip(out.positives, out.n)]
    out["observed_low"] = [low for low, _ in limits]
    out["observed_high"] = [high for _, high in limits]
    out = out.reset_index()
    out["band_low"] = [interval.left for interval in out.band]
    out["band_high"] = [interval.right for interval in out.band]
    return out.drop(columns="band")


# --------------------------------------------------------------------------- Catalonia


@dataclass(frozen=True)
class RollingResult:
    predictions: pd.DataFrame  # one row per test crash: year, fatal, and one column per estimator
    by_year: pd.DataFrame


def catalonia_frame() -> pd.DataFrame:
    frame = pd.read_parquet(CATALONIA_FEATURES)
    frame["year"] = frame["year"].astype(int)
    return frame


def catalonia_estimators(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    """Fit every estimator on ``train`` and predict ``test``."""
    y = train.fatal.to_numpy()
    out: dict[str, np.ndarray] = {"prevalence": np.full(len(test), y.mean())}
    rates = table_rates(train, "fatal", CATALONIA_TABLE_KEYS)
    out["type_x_zone_table"] = apply_table(rates, test, CATALONIA_TABLE_KEYS)
    logistic = logistic_pipeline(
        CATALONIA_NUMERIC, CATALONIA_BINARY, CATALONIA_CATEGORICAL, LOGISTIC_C
    )
    logistic.fit(train, y)
    out["logistic_all_features"] = logistic.predict_proba(test)[:, 1]
    boosted = boosted_pipeline(
        CATALONIA_NUMERIC, CATALONIA_BINARY, CATALONIA_CATEGORICAL, BOOSTED_PARAMS
    )
    boosted.fit(train, y)
    out["boosted_trees"] = boosted.predict_proba(test)[:, 1]
    return out


def catalonia_rolling(test_years: tuple[int, ...] = ROLLING_TEST_YEARS) -> RollingResult:
    frame = catalonia_frame()
    pieces = []
    for year in test_years:
        train = frame[frame.year < year]
        test = frame[frame.year == year]
        predictions = catalonia_estimators(train, test)
        pieces.append(
            pd.DataFrame(
                {"cat_crash_id": test.cat_crash_id, "year": year, "fatal": test.fatal} | predictions
            )
        )
    predictions = pd.concat(pieces, ignore_index=True)
    estimators = [c for c in predictions.columns if c not in ("cat_crash_id", "year", "fatal")]
    rows = []
    for year, group in predictions.groupby("year"):
        y = group.fatal.to_numpy()
        for name in estimators:
            rows.append({"year": year, "estimator": name} | scores(y, group[name].to_numpy()))
    return RollingResult(predictions=predictions, by_year=pd.DataFrame(rows))


def catalonia_single_split() -> pd.DataFrame:
    """The original design (train 2010-2020, test 2023), to reproduce the published scores."""
    frame = catalonia_frame()
    train = frame[frame.year <= 2020]
    test = frame[frame.year == 2023]
    predictions = catalonia_estimators(train, test)
    y = test.fatal.to_numpy()
    return pd.DataFrame([{"estimator": name} | scores(y, p) for name, p in predictions.items()])


# --------------------------------------------------------------------------- Barcelona

BARCELONA_TEST_FROM_MONTH = 10  # the original split: months 1-9 train, 10-12 test


def barcelona_split_scores(table_name: str) -> pd.DataFrame:
    """Refit a Barcelona model on months 1-9 and score months 10-12, with its table benchmark.

    Columns come from the original feature catalogue (a definition, not a result); estimators,
    encodings and the benchmark are this module's own. ``estimator`` and its parameters are
    those the original pipeline selected (``reports/tables/ml_selected.csv``).
    """
    from dgt_stats.microdata.ml import features as catalogue
    from dgt_stats.paths import TABLES_DIR

    table = {t.name: t for t in catalogue.TABLES}[table_name]
    frame = pd.read_parquet(table.path)
    month = pd.to_numeric(frame[table.time_column]).astype(int)
    feats = table.features(table.primary_set, table.primary_geography)
    numeric = tuple(f.column for f in feats if f.kind == "numeric")
    binary = tuple(f.column for f in feats if f.kind == "binary")
    categorical = tuple(f.column for f in feats if f.kind == "categorical")
    train = frame[month < BARCELONA_TEST_FROM_MONTH]
    test = frame[month >= BARCELONA_TEST_FROM_MONTH]
    y_train, y_test = train[table.target].to_numpy(), test[table.target].to_numpy()
    selected = pd.read_csv(TABLES_DIR / "ml_selected.csv")
    row = selected[(selected.model == table_name) & selected.primary].iloc[0]
    params = dict(
        (key.strip(), float(value) if "." in value else int(value))
        for key, value in (item.split("=") for item in row.params.split(","))
    )
    predictions: dict[str, np.ndarray] = {"prevalence": np.full(len(test), y_train.mean())}
    keys = {
        "barcelona_person_severity": ("person_role", "associated_vehicle_group"),
        "barcelona_crash_severity": ("accident_type",),
    }[table_name]
    predictions["table"] = apply_table(table_rates(train, table.target, keys), test, keys)
    if row.estimator == "boosted_trees":
        model = boosted_pipeline(numeric, binary, categorical, params)
    else:
        model = logistic_pipeline(numeric, binary, categorical, params["C"])
    model.fit(train, y_train)
    predictions[str(row.estimator)] = model.predict_proba(test)[:, 1]
    return pd.DataFrame(
        [
            {"model": table_name, "estimator": name} | scores(y_test, p)
            for name, p in predictions.items()
        ]
    )


# --------------------------------------------------------------------------- monthly deaths

FORECAST_VARIANTS: dict[str, str] = {
    "month + trend + fuel + calendar (the published model)": "C(month) + t + log_fuel + "
    "fridays + saturdays + sundays",
    "month + fuel + calendar (no trend)": "C(month) + log_fuel + fridays + saturdays + sundays",
    "month + trend": "C(month) + t",
    "month only": "C(month)",
}


def forecast_diagnosis(outcome: str = "deaths_all") -> pd.DataFrame:
    """Why the Poisson forecast loses to last year's count in the ordinary held-out years.

    For each specification and window, and for each kind of year: the root mean squared error of
    the log annual total, its mean (bias), and the mean standard error of the predicted annual
    total that comes only from estimating the coefficients (delta method on the fitted model).
    The Poisson floor is the error a forecast with the exact expected value would still make.
    """
    import patsy

    from dgt_stats import forecast

    panel = forecast.model_panel()
    rows = []
    sets = {"selection": forecast.SELECTION_YEARS, "holdout": forecast.HOLDOUT_YEARS}
    for label, years in sets.items():
        totals = [float(panel.loc[panel.year == y, outcome].sum()) for y in years]
        mean_total = float(np.mean(totals))
        for name, formula in FORECAST_VARIANTS.items():
            for window in (4, 8):
                errors, standard_errors = [], []
                for year in years:
                    train = panel[(panel.year >= year - window) & (panel.year < year)]
                    test = panel[panel.year == year]
                    y, x = patsy.dmatrices(f"{outcome} ~ {formula}", train, return_type="dataframe")
                    fit = sm.GLM(y, x, family=sm.families.Poisson()).fit(scale="X2")
                    xt = patsy.build_design_matrices([x.design_info], test, return_type="dataframe")
                    xt = xt[0].to_numpy()
                    mu = np.exp(xt @ fit.params.to_numpy())
                    gradient = (mu[:, None] * xt).sum(axis=0) / mu.sum()
                    standard_errors.append(
                        float(np.sqrt(gradient @ fit.cov_params().to_numpy() @ gradient))
                    )
                    errors.append(float(np.log(test[outcome].sum() / mu.sum())))
                rows.append(
                    {
                        "set": label,
                        "method": name,
                        "window": window,
                        "years": len(years),
                        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
                        "bias": float(np.mean(errors)),
                        "estimation_se": float(np.mean(standard_errors)),
                        "poisson_floor": 1 / np.sqrt(mean_total),
                    }
                )
        naive = [
            np.log(
                panel.loc[panel.year == y, outcome].sum()
                / panel.loc[panel.year == y - 1, outcome].sum()
            )
            for y in years
        ]
        rows.append(
            {
                "set": label,
                "method": "naive: same months last year",
                "window": 1,
                "years": len(years),
                "rmse": float(np.sqrt(np.mean(np.square(naive)))),
                "bias": float(np.mean(naive)),
                "estimation_se": 0.0,
                "poisson_floor": float(np.sqrt(2 / mean_total)),
            }
        )
    return pd.DataFrame(rows)
