"""The independent review of the repository's predictive models.

Usage:
    python scripts/severity_calculator.py review       # reports/tables/review_*.csv

It reads the feature tables written by ``scripts/microdata.py features`` and, for the forecast
diagnosis, the national layer built by ``scripts/ingest.py``; it takes about ten minutes.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from dgt_stats import model_review  # noqa: E402
from dgt_stats.paths import TABLES_DIR  # noqa: E402

log = logging.getLogger("severity_calculator")


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=("review",))
    parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = time.time()
    run_review()
    log.info("done in %.1f s", time.time() - start)


if __name__ == "__main__":
    main()
