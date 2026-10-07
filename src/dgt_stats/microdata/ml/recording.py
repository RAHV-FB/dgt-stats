"""Is a field's "not specified" level a circumstance, or a trace of how fully a crash was recorded?

A crash with a death is investigated and documented more fully than one with a serious injury.
Where a field's placeholder ("Sense especificar", or an unexplained "NA") is much rarer among fatal
crashes, the placeholder carries the outcome back into the features: a model can learn "this
record is incomplete, so the crash was not fatal". This module measures that for every categorical
field of the Catalonia file, three ways:

* by **outcome**: the placeholder rate among fatal crashes against serious ones;
* by **year**: whether the rate drifts (a change in recording practice);
* by **geography**: Barcelona municipality against the rest of Catalonia, and by demarcation.

A placeholder that a structural condition explains ("NA" for the road owner on urban streets, "NA"
for the junction type away from junctions) is not a recording artefact. A field is classed as
*outcome-dependent* when its placeholder covers at least :data:`MIN_RATE` of crashes, is not
structurally explained, and its rate among fatal crashes differs from the rate among serious
crashes by a factor of :data:`RATIO_LIMIT` or more. Those fields stay out of the primary model and
enter only the retrospective administrative model; ``tests/test_microdata_models.py`` checks that
the catalogue agrees with this verdict.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgt_stats.microdata import catalonia
from dgt_stats.microdata.ml import features

PLACEHOLDERS = ("NA", "Sense especificar", "Sense Especificar")
MIN_RATE = 0.01
RATIO_LIMIT = 1.5
STRUCTURAL_COVERAGE = 0.9

# Placeholder levels with a structural meaning, and the condition that explains them.
STRUCTURAL: dict[tuple[str, str], tuple[str, str, str]] = {
    ("D_TITULARITAT_VIA", "NA"): ("zona", "Zona urbana", "urban street (no road owner recorded)"),
    ("D_TRACAT_ALTIMETRIC", "NA"): ("zona", "Zona urbana", "urban street"),
    ("D_SUBTIPUS_TRAM", "NA"): ("D_INTER_SECCIO", "En secció", "not at a junction"),
    ("D_REGULACIO_PRIORITAT", "NA"): ("D_INTER_SECCIO", "En secció", "not at a junction"),
}


def categorical_fields() -> list[str]:
    return [
        f.column
        for f in features.CATALONIA_TABLE.catalogue
        if f.kind == "categorical"
        and f.status in ("safe", "questionable")
        and f.sets
        and f.column.startswith("D_")
    ]


def audit(frame: pd.DataFrame | None = None, rows: np.ndarray | None = None) -> pd.DataFrame:
    """One row per field and placeholder level with its rates by outcome, year and place."""
    frame = catalonia.read() if frame is None else frame
    if rows is not None:
        frame = frame.iloc[rows]
    fatal = frame["fatal"].eq(1)
    bcn = frame["municipality"].eq("Barcelona")
    out = []
    for column in categorical_fields():
        values = frame[column].astype(str).str.strip()
        for level in PLACEHOLDERS:
            mask = values.eq(level)
            if mask.sum() == 0:
                continue
            by_year = mask.groupby(frame["year"]).mean()
            by_demarcation = mask.groupby(frame["demarcation"]).mean()
            structural = STRUCTURAL.get((column, level))
            coverage = (
                float(frame.loc[mask, structural[0]].eq(structural[1]).mean())
                if structural
                else float("nan")
            )
            rate_fatal = float(mask[fatal].mean())
            rate_serious = float(mask[~fatal].mean())
            ratio = rate_fatal / rate_serious if rate_serious > 0 else float("nan")
            out.append(
                {
                    "column": column,
                    "level": level,
                    "rows": int(mask.sum()),
                    "rate": float(mask.mean()),
                    "rate_fatal": rate_fatal,
                    "rate_serious": rate_serious,
                    "ratio_fatal_to_serious": ratio,
                    "rate_first_year": float(by_year.iloc[0]),
                    "rate_last_year": float(by_year.iloc[-1]),
                    "rate_min_year": float(by_year.min()),
                    "rate_max_year": float(by_year.max()),
                    "rate_barcelona_municipality": float(mask[bcn].mean()),
                    "rate_rest_of_catalonia": float(mask[~bcn].mean()),
                    "rate_min_demarcation": float(by_demarcation.min()),
                    "rate_max_demarcation": float(by_demarcation.max()),
                    "structural_explanation": structural[2] if structural else "",
                    "structural_coverage": coverage,
                }
            )
    result = pd.DataFrame(out)
    result["verdict"] = [verdict(row) for row in result.itertuples()]
    return result


def verdict(row) -> str:
    if row.structural_explanation and row.structural_coverage >= STRUCTURAL_COVERAGE:
        return "structural"
    if row.rate < MIN_RATE:
        return "too rare to matter"
    ratio = row.ratio_fatal_to_serious
    if ratio <= 1 / RATIO_LIMIT or ratio >= RATIO_LIMIT:
        return "outcome-dependent recording"
    return "no strong outcome dependence"


def outcome_dependent_fields(result: pd.DataFrame) -> set[str]:
    return set(result.loc[result.verdict.eq("outcome-dependent recording"), "column"])
