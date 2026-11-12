"""The severity model on crashes it was not fitted on, all within the Catalan file.

Four kinds of test, each fitted on the other crashes alone with the choices made on those
crashes (:func:`severity_model.select`): the last year from the years before it, each province
left out in turn, and Barcelona city from the rest of Catalonia. Each sits beside the same
choices fitted and cross-validated inside the test population (5 folds), and beside the table of
fatal shares by road and crash type fitted on the same training crashes. A province left out has
no intercept of its own to learn, so those tests use the specification without province
intercepts. The test of Barcelona city keeps the published design with province intercepts, a
choice made on the last two years of all the crashes, the city's included.

No test uses another source: no other file records the model's inputs (DGT's records lack the
road's owning network and the posted limit, and their road-type coding disagrees with the Catalan
file's on the same crashes). The rolling-origin evaluation over 2016-2023 is
:func:`severity_model.nested_rolling`.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

from dgt_stats import severity_model as sev
from dgt_stats.metrics import wilson

log = logging.getLogger(__name__)

SEED = 20251
N_FOLDS = 5
N_BOOT = 500
BARCELONA = "Barcelona municipality"
REST = "rest of Catalonia"


def _bootstrap_ci(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    """Percentile intervals for ROC-AUC and PR-AUC from resampled crashes."""
    rng = np.random.default_rng(SEED)
    aucs, aps = [], []
    for _ in range(N_BOOT):
        index = rng.integers(0, len(y), len(y))
        yy, pp = y[index], p[index]
        if 0 < yy.sum() < len(yy):
            aucs.append(roc_auc_score(yy, pp))
            aps.append(average_precision_score(yy, pp))
    return {
        "roc_auc_low": float(np.percentile(aucs, 2.5)),
        "roc_auc_high": float(np.percentile(aucs, 97.5)),
        "pr_auc_low": float(np.percentile(aps, 2.5)),
        "pr_auc_high": float(np.percentile(aps, 97.5)),
    }


def _calibration(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
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


def held_out_tests(rec: sev.Records, nested: sev.Nested) -> pd.DataFrame:
    """One row per test: the model's ROC-AUC with its interval, the table's, and the ROC-AUC of
    the same choices cross-validated inside the test population (``in_domain_cv_roc_auc``).
    ``nested`` supplies the choices made for the last test year."""
    y, years, frame = rec.y, rec.years, rec.frame
    city = (frame.municipality == "Barcelona").to_numpy()
    first, last = int(years.min()), int(years.max())

    def cross_validated(domain: np.ndarray, choice: sev.Choice) -> np.ndarray:
        index = np.flatnonzero(domain)
        folds = StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED)
        out = np.zeros(len(index))
        for a, b in folds.split(index, y[index]):
            train = np.zeros(len(y), dtype=bool)
            test = np.zeros(len(y), dtype=bool)
            train[index[a]], test[index[b]] = True, True
            out[b] = sev.predict_chosen(rec, choice, train, test)
        return out

    rows = []

    def held_out(experiment, kind, train_desc, test_desc, train, test, provinces, choice=None):
        log.info("severity tests: %s", experiment)
        if choice is None:
            choice, _ = sev.select(rec, train, provinces=provinces, label=experiment)
        p = sev.predict_chosen(rec, choice, train, test)
        table = sev._table(rec.scenarios[train], y[train], rec.scenarios[test])
        reference = cross_validated(test, choice)
        yt = y[test]
        low, high = wilson(yt.sum(), len(yt))
        rows.append(
            {
                "experiment": experiment,
                "evidence_level": kind,
                "train_domain": train_desc,
                "test_domain": test_desc,
                "test_n": int(test.sum()),
                "test_positives": int(yt.sum()),
                "test_prevalence": float(yt.mean()),
                "mean_predicted": float(p.mean()),
                "observed_low": low,
                "observed_high": high,
                "roc_auc": float(roc_auc_score(yt, p)),
                **_bootstrap_ci(yt, p),
                **_calibration(yt, p),
                "table_roc_auc": float(roc_auc_score(yt, table)),
                "in_domain_cv_roc_auc": float(roc_auc_score(yt, reference)),
            }
        )

    choices = nested.choices.set_index("test_year").loc[last]
    chosen = sev.Choice(
        specification=str(choices.specification),
        c=float(choices.c),
        through_town=str(choices.through_town),
        provinces=bool(choices.provinces),
        train_years=tuple(int(v) for v in str(choices.train_years).split("-")),
        validation_years=tuple(int(v) for v in str(choices.validation_years).split("-")),
        c_bracketed=bool(choices.c_bracketed),
    )
    held_out(
        f"temporal holdout: train {first}-{last - 1}, test {last}",
        "2 temporal",
        f"{first}-{last - 1}",
        str(last),
        years < last,
        years == last,
        True,
        chosen,
    )
    for name in sorted(frame.demarcation.astype(str).unique()):
        test = (frame.demarcation.astype(str) == name).to_numpy()
        held_out(
            f"leave out {name} demarcation",
            "3 geographic",
            "the other three demarcations",
            f"{name} demarcation",
            ~test,
            test,
            False,
        )
    held_out(
        "rest of Catalonia -> Barcelona municipality",
        "3 geographic",
        REST,
        BARCELONA,
        ~city,
        city,
        True,
    )
    out = pd.DataFrame(rows)
    out["transfer_gap"] = out.roc_auc - out.in_domain_cv_roc_auc
    return out
