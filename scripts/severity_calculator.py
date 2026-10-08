"""The independent model review and the crash-severity calculator.

Usage:
    python scripts/severity_calculator.py review       # reports/tables/review_*.csv
    python scripts/severity_calculator.py calculator   # reports/tables/sev_*.csv and
                                                      # reports/models/severity_model.json
    python scripts/severity_calculator.py all

Both read the feature tables written by ``scripts/microdata.py features`` and, for the forecast
diagnosis, the national layer built by ``scripts/ingest.py``. ``calculator`` takes about two
minutes, ``review`` about ten.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from dgt_stats import model_review, severity_model  # noqa: E402
from dgt_stats.paths import REPORTS_DIR, TABLES_DIR  # noqa: E402

log = logging.getLogger("severity_calculator")
MODELS_DIR = REPORTS_DIR / "models"
MODEL_PATH = MODELS_DIR / "severity_model.json"


def write(frame: pd.DataFrame, name: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.10g")
    log.info("%s: %d rows", name, len(frame))


def run_review() -> None:
    single = model_review.catalonia_single_split()
    write(single, "review_catalonia_2023")
    rolling = model_review.catalonia_rolling()
    estimators = [
        c for c in rolling.predictions.columns if c not in ("cat_crash_id", "year", "fatal")
    ]
    y = rolling.predictions.fatal.to_numpy()
    pooled = pd.DataFrame(
        [
            {"year": "2016-2023", "estimator": name}
            | model_review.scores(y, rolling.predictions[name].to_numpy())
            for name in estimators
        ]
    )
    write(pd.concat([pooled, rolling.by_year], ignore_index=True), "review_catalonia_rolling")
    barcelona = pd.concat(
        [
            model_review.barcelona_split_scores("barcelona_person_severity"),
            model_review.barcelona_split_scores("barcelona_crash_severity"),
        ],
        ignore_index=True,
    )
    write(barcelona, "review_barcelona")
    write(model_review.forecast_diagnosis(), "review_forecast")


def run_calculator() -> None:
    grid = severity_model.choose_penalty()
    write(grid, "sev_penalty")
    c = float(grid[grid.chosen].iloc[0].c)

    rolling = severity_model.rolling_predictions(c)
    estimators = ["calculator", "boosted_trees", "road_x_crash_table"]
    rows = []
    urban = rolling.zone == "urban"
    subsets = {"2016-2023": rolling.year > 0}
    subsets |= {str(year): rolling.year == year for year in severity_model.ROLLING_TEST_YEARS}
    subsets |= {f"zone: {zone}": rolling.zone == zone for zone in severity_model.ZONES}
    subsets["Barcelona city, urban streets"] = urban & rolling.barcelona_city
    subsets["urban streets outside Barcelona city"] = urban & ~rolling.barcelona_city
    for subset, mask in subsets.items():
        part = rolling[mask]
        for name in estimators:
            rows.append(
                {"subset": subset, "estimator": name}
                | model_review.scores(part.fatal.to_numpy(), part[name].to_numpy())
            )
    write(pd.DataFrame(rows), "sev_rolling_scores")
    y = rolling.fatal.to_numpy()
    comparison = model_review.bootstrap_intervals(
        y, {name: rolling[name].to_numpy() for name in estimators}, reference="calculator"
    )
    write(comparison, "sev_comparison")
    calibration = []
    for name in estimators:
        table = model_review.calibration_groups(y, rolling[name].to_numpy())
        table.insert(0, "estimator", name)
        calibration.append(table)
    write(pd.concat(calibration, ignore_index=True), "sev_calibration")
    write(severity_model.geography(c), "sev_geography")
    write(severity_model.specification_check(c), "sev_specification")

    fitted, x = severity_model.final_fit(c)
    frame, _, y_all = severity_model.load()
    draws = severity_model.bootstrap_draws(x, y_all, c)
    covariance = np.cov(draws, rowvar=False)
    contrasts = pd.concat(
        [
            severity_model.scenario_contrasts(fitted, covariance, base).assign(base=label)
            for label, base in (
                ("interurban", severity_model.REFERENCE_SCENARIO),
                ("urban", severity_model.URBAN_REFERENCE),
            )
        ],
        ignore_index=True,
    )
    write(contrasts, "sev_contrasts")
    write(severity_model.marginal_and_adjusted(fitted, draws), "sev_marginal_adjusted")
    write(severity_model.stability(c), "sev_stability")
    coefficients = pd.DataFrame(
        {
            "column": fitted.columns,
            "group": [severity_model.column_group(col) for col in fitted.columns],
            "coefficient": fitted.coef,
            "bootstrap_se": np.sqrt(np.diag(covariance)),
        }
    )
    write(coefficients, "sev_coefficients")

    pooled = (
        pd.read_csv(TABLES_DIR / "sev_rolling_scores.csv")
        .query("subset == '2016-2023' and estimator == 'calculator'")
        .iloc[0]
    )
    evaluation = {
        "design": "each year 2016-2023 predicted by a model fitted on the years before it",
        "crashes": int(pooled.n),
        "fatal": int(pooled.positives),
        "roc_auc": round(float(pooled.roc_auc), 4),
        "brier_skill": round(float(pooled.brier_skill), 4),
        "calibration_slope": round(float(pooled.calibration_slope), 4),
        "mean_predicted": round(float(pooled.mean_predicted), 4),
        "observed": round(float(pooled.prevalence), 4),
    }
    scenarios = severity_model.scenarios_from_records(frame)
    excluded = len(severity_model.load_all()) - len(frame)
    exported = severity_model.export(fitted, covariance, scenarios, y_all, evaluation, excluded)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(exported, ensure_ascii=False, separators=(",", ":")) + "\n")
    log.info("model: %s (%.0f kB)", MODEL_PATH, MODEL_PATH.stat().st_size / 1024)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=("review", "calculator", "all"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = time.time()
    if args.step in ("calculator", "all"):
        run_calculator()
    if args.step in ("review", "all"):
        run_review()
    log.info("done in %.1f s", time.time() - start)


if __name__ == "__main__":
    main()
