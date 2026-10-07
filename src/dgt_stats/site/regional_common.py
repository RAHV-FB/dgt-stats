"""Shared helpers for the regional, model, validation and sources pages.

Every number on those pages is read from a committed table in ``reports/tables`` written by
``scripts/microdata.py``; qualitative sentences are guarded by ``_check``, which stops the build
when the tables no longer support them.
"""

from __future__ import annotations

import re

import pandas as pd

from dgt_stats.site.components import (
    esc,
)

MIN_N = 30
# The names a reader sees. The two featured models are the Catalonia crash-severity model and the
# Barcelona person-severity model; the harmonised models are validation instruments.
MODEL_NAMES = {
    "catalonia_crash_severity": "Catalonia crash-severity model",
    "barcelona_person_severity": "Barcelona person-severity model",
    "barcelona_crash_severity": "Barcelona crash-severity model",
    "catalonia_common_dgt": "Harmonised Catalonia model (variables recorded alike by DGT)",
    "catalonia_common_bcn": "Catalonia model on Barcelona's variables",
    "dgt_crash_severity": "Association analysis of DGT crash records",
    "dgt_monthly_deaths_forecast": "Monthly deaths forecast",
}
CARDS = {
    "catalonia_crash_severity": "models/catalonia_fatal_severity.md",
    "barcelona_person_severity": "models/barcelona_person_severity.md",
    "barcelona_crash_severity": "models/barcelona_crash_severity.md",
}
ESTIMATORS = {
    "baseline_prior": "Baseline (prevalence)",
    "logistic": "Logistic regression",
    "boosted_trees": "Boosted trees",
}


def _year_label(frame: pd.DataFrame) -> str:
    """The year (or years) a Barcelona table covers, from its own dataset label."""
    return re.search(r"\d{4}(-\d{4})?", str(frame.dataset.iloc[0])).group(0).replace("-", "–")


def ca(text: str) -> str:
    return f'<span lang="ca">{esc(text)}</span>'


def _check(condition: bool, page: str, claim: str) -> None:
    if not condition:
        raise ValueError(f"{page} page: '{claim}' no longer reads as described")


def _dimension(frame: pd.DataFrame, dimension: str) -> pd.DataFrame:
    return frame[(frame.dimension == dimension) & (frame.n >= MIN_N)].sort_values(
        "share", ascending=False
    )
