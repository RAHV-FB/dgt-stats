"""The scoring functions behind the severity model's evaluation.

A constant prediction (a prevalence benchmark) has no calibration slope, and must return one as
missing rather than fail; a perfectly calibrated prediction must score a slope near 1 and an
intercept near 0; the Brier skill of the prevalence itself is 0.
"""

from __future__ import annotations

import numpy as np
import pytest

from dgt_stats import metrics


def test_constant_prediction_has_no_calibration_slope() -> None:
    y = np.array([0, 1, 0, 0, 1, 0, 0, 0])
    slope, intercept = metrics.calibration_fit(y, np.full(len(y), y.mean()))
    assert np.isnan(slope) and np.isnan(intercept)
    scores = metrics.scores(y, np.full(len(y), y.mean()))
    assert scores["brier_skill"] == pytest.approx(0.0)
    assert scores["calibration_in_the_large"] == pytest.approx(0.0, abs=1e-8)


def test_calibrated_prediction_scores_slope_one() -> None:
    rng = np.random.default_rng(3)
    p = rng.uniform(0.02, 0.6, 40_000)
    y = (rng.uniform(size=p.size) < p).astype(int)
    slope, intercept = metrics.calibration_fit(y, p)
    assert slope == pytest.approx(1.0, abs=0.05)
    assert intercept == pytest.approx(0.0, abs=0.05)


def test_wilson_interval_stays_inside_zero_and_one() -> None:
    low, high = metrics.wilson(0, 20)
    assert low == 0.0 and 0 < high < 0.2
    low, high = metrics.wilson(20, 20)
    assert high == 1.0 and 0.8 < low < 1
    assert all(np.isnan(v) for v in metrics.wilson(0, 0))
