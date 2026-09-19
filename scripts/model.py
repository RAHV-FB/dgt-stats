"""Fit the crash-severity models and write their result tables.

Usage:
    python scripts/model.py            # reports/tables/q3_*.csv (a few minutes)

The site build never refits: scripts/analyse.py and scripts/build_site.py read these tables.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from dgt_stats import features, models  # noqa: E402
from dgt_stats.paths import TABLES_DIR  # noqa: E402

log = logging.getLogger("model")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    started = time.perf_counter()
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frame = features.model_frame()
    log.info("model frame: %s crashes, %d predictors", f"{len(frame):,}", len(features.PREDICTORS))

    fits: dict[str, models.Fit] = {}
    coefficients, effects, calibrations, summaries, stability = [], [], [], [], []
    for outcome in features.OUTCOMES:
        fit = models.fit_severity(frame, outcome)
        fits[outcome] = fit
        log.info("%s: fitted on %s crashes, %s events", outcome, f"{fit.n:,}", f"{fit.events:,}")
        coefficients.append(models.coefficient_table(frame, fit))
        effects.append(models.marginal_effects(frame, fit))
        calibration, summary = models.holdout_check(frame, outcome)
        calibrations.append(calibration)
        summaries.append(summary)
        log.info(
            "%s: holdout AUC %.3f, Brier %.4f", outcome, summary.auc.iloc[0], summary.brier.iloc[0]
        )
        stability.append(models.year_stability(frame, fit))

    outputs = {
        "q3_model_coefficients": pd.concat(coefficients, ignore_index=True),
        "q3_marginal_effects": pd.concat(effects, ignore_index=True),
        "q3_calibration": pd.concat(calibrations, ignore_index=True),
        "q3_holdout_summary": pd.concat(summaries, ignore_index=True),
        "q3_year_stability": pd.concat(stability, ignore_index=True),
        "q3_profiles": models.profiles(frame, fits),
        "q3_predicted_grid": models.predicted_grid(frame, fits["fatal"]),
        "q3_groupings": features.grouping_table(frame),
    }
    for name, table in outputs.items():
        target = TABLES_DIR / f"{name}.csv"
        table.to_csv(target, index=False, float_format="%.6g")
        log.info("table %-24s %5d rows -> %s", name, len(table), target.name)
    log.info("done in %.1f s", time.perf_counter() - started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
