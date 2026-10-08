"""The independent model review and the crash-severity calculator.

Usage:
    python scripts/severity_calculator.py review       # reports/tables/review_*.csv
    python scripts/severity_calculator.py calculator   # reports/tables/sev_*.csv and
                                                      # reports/models/severity_model.json
    python scripts/severity_calculator.py all

Both read the feature tables written by ``scripts/microdata.py features`` and, for the forecast
diagnosis, the national layer built by ``scripts/ingest.py``. ``calculator`` takes about
twenty minutes (the nested choices refit the model a few hundred times), ``review`` about ten.
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


def _subsets(rolling: pd.DataFrame) -> dict[str, pd.Series]:
    """The pooled years, each year, each zone, Barcelona city, each province, and each zone of
    each province."""
    urban = rolling.zone == "urban"
    first, last = severity_model.ROLLING_TEST_YEARS[0], severity_model.ROLLING_TEST_YEARS[-1]
    subsets = {f"{first}-{last}": rolling.year > 0}
    subsets |= {str(year): rolling.year == year for year in severity_model.ROLLING_TEST_YEARS}
    subsets |= {f"zone: {zone}": rolling.zone == zone for zone in severity_model.ZONES}
    subsets["Barcelona city, urban streets"] = urban & rolling.barcelona_city
    subsets["urban streets outside Barcelona city"] = urban & ~rolling.barcelona_city
    subsets |= {
        f"province: {province}": rolling.province == province
        for province in severity_model.PROVINCES
    }
    subsets |= {
        f"province and zone: {province}|{zone}": (rolling.province == province)
        & (rolling.zone == zone)
        for province in severity_model.PROVINCES
        for zone in severity_model.ZONES
    }
    return subsets


def _scores(rolling: pd.DataFrame, estimators: list[str]) -> pd.DataFrame:
    rows = []
    for subset, mask in _subsets(rolling).items():
        part = rolling[mask]
        y = part.fatal.to_numpy()
        low, high = model_review.wilson(y.sum(), len(y))
        for name in estimators:
            rows.append(
                {"subset": subset, "estimator": name}
                | model_review.scores(y, part[name].to_numpy())
                | {"observed_low": low, "observed_high": high}
            )
    return pd.DataFrame(rows)


def _steps(rolling: pd.DataFrame) -> pd.DataFrame:
    """From the previous design to the nested one, one choice at a time: pooled, by year and by
    zone, each step's ROC-AUC gain over the table with a paired bootstrap interval (pooled)."""
    y = rolling.fatal.to_numpy()
    steps = list(severity_model.STEPS)
    bootstrap = model_review.bootstrap_intervals(
        y,
        {name: rolling[name].to_numpy() for name in [*steps, "road_x_crash_table"]},
        reference="road_x_crash_table",
    ).set_index(["estimator", "metric"])
    scores = _scores(rolling, [*steps, "road_x_crash_table"])
    table = scores[scores.estimator == "road_x_crash_table"].set_index("subset").roc_auc
    out = scores[scores.estimator.isin(steps)].copy()
    out = out[~out.subset.str.startswith(("province", "Barcelona city", "urban streets"))]
    out.insert(1, "step", out.estimator.map({s: i for i, s in enumerate(steps)}))
    out.insert(2, "description", out.estimator.map(severity_model.STEPS))
    out["table_roc_auc"] = out.subset.map(table)
    out["roc_auc_gain"] = out.roc_auc - out.table_roc_auc
    pooled = out.subset == _pooled_label()
    for bound, column in (("low", "roc_auc_gain_low"), ("high", "roc_auc_gain_high")):
        out[column] = np.nan
        out.loc[pooled, column] = out[pooled].estimator.map(
            lambda name: float(bootstrap.loc[(name, "roc_auc_minus_road_x_crash_table"), bound])
        )
    return out.sort_values(["step", "subset"], kind="stable").reset_index(drop=True)


def _pooled_label() -> str:
    years = severity_model.ROLLING_TEST_YEARS
    return f"{years[0]}-{years[-1]}"


def _population(rec: severity_model.Records) -> pd.DataFrame:
    """The crashes the model describes against all the file's crashes: the excluded roads are
    those whose owner network is not named, and they change the fatal share."""
    everything = severity_model.load_all()
    roads = severity_model.road_of(everything)
    fatal = everything.fatal.to_numpy().astype(int)
    zone = roads.map({key: zone for key, (_, zone) in severity_model.ROADS.items()})
    zone = zone.fillna("interurban").to_numpy()
    groups = {
        "fitted (named owner network or not a conventional road)": ~roads.isin(
            severity_model.EXCLUDED_ROADS
        ).to_numpy(),
        "excluded: owner recorded as other": (roads == "conventional_owner_other").to_numpy(),
        "excluded: owner blank": (roads == "conventional_owner_blank").to_numpy(),
        "excluded: both": roads.isin(severity_model.EXCLUDED_ROADS).to_numpy(),
        "all crashes in the file": np.ones(len(roads), dtype=bool),
    }
    rows = []
    for label, mask in groups.items():
        for scope, scoped in (
            ("all zones", mask),
            ("interurban roads", mask & (zone == "interurban")),
        ):
            n, k = int(scoped.sum()), int(fatal[scoped].sum())
            low, high = model_review.wilson(k, n)
            rows.append(
                {
                    "population": label,
                    "zone": scope,
                    "crashes": n,
                    "fatal": k,
                    "fatal_share": k / n if n else np.nan,
                    "fatal_share_low": low,
                    "fatal_share_high": high,
                }
            )
    out = pd.DataFrame(rows)
    fitted = out[out.population.str.startswith("fitted")]
    assert int(fitted[fitted.zone == "all zones"].crashes.iloc[0]) == len(rec.y)
    return out


def run_calculator() -> None:
    rec = severity_model.records()
    nested = severity_model.nested_rolling(rec)
    final, final_grid = severity_model.final_choice(rec)
    choices = pd.concat(
        [
            nested.choices,
            pd.DataFrame([severity_model.choice_row(final, final_grid, "published model")]),
        ],
        ignore_index=True,
    )
    write(choices, "sev_choices")
    grid_columns = [
        "fit",
        "specification",
        "c",
        "validation_log_loss",
        "validation_roc_auc",
        "best_for_specification",
        "chosen",
    ]
    write(
        pd.concat([nested.grid[grid_columns], final_grid[grid_columns]], ignore_index=True),
        "sev_penalty",
    )

    rolling = nested.predictions
    estimators = ["calculator", "boosted_trees", "road_x_crash_table"]
    write(_scores(rolling, estimators), "sev_rolling_scores")
    write(_steps(rolling), "sev_nested_steps")
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
    write(severity_model.geography(rec), "sev_geography")
    write(_population(rec), "sev_population")

    fitted, x = severity_model.final_fit(final, rec)
    draws = severity_model.bootstrap_draws(x, rec.y, final.c, fitted.columns)
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
    write(severity_model.marginal_and_adjusted(fitted, draws, rec), "sev_marginal_adjusted")
    write(severity_model.stability(final, rec), "sev_stability")
    coefficients = pd.DataFrame(
        {
            "column": fitted.columns,
            "group": [severity_model.column_group(col) for col in fitted.columns],
            "coefficient": fitted.coef,
            "bootstrap_se": np.sqrt(np.diag(covariance)),
        }
    )
    write(coefficients, "sev_coefficients")

    scores = pd.read_csv(TABLES_DIR / "sev_rolling_scores.csv")
    pooled = scores[(scores.subset == _pooled_label()) & (scores.estimator == "calculator")].iloc[0]
    evaluation = {
        "design": "nested rolling origin: each year "
        f"{_pooled_label()} predicted by a model whose penalty, specification and "
        "through-town rule were chosen, and whose coefficients were fitted, on the years before it",
        "crashes": int(pooled.n),
        "fatal": int(pooled.positives),
        "roc_auc": round(float(pooled.roc_auc), 4),
        "brier_skill": round(float(pooled.brier_skill), 4),
        "calibration_slope": round(float(pooled.calibration_slope), 4),
        "calibration_intercept": round(float(pooled.calibration_intercept), 4),
        "mean_predicted": round(float(pooled.mean_predicted), 4),
        "observed": round(float(pooled.prevalence), 4),
    }
    everything = severity_model.load_all()
    left_out = severity_model.road_of(everything).isin(severity_model.EXCLUDED_ROADS).to_numpy()
    excluded = {"crashes": int(left_out.sum()), "fatal": int(everything.fatal[left_out].sum())}
    years = (int(rec.years.min()), int(rec.years.max()))
    exported = severity_model.export(
        fitted, covariance, rec.scenarios, rec.y, evaluation, excluded, years, final
    )
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
