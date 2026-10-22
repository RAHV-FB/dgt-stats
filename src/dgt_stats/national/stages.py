"""The national section's pipeline stages, run by ``scripts/run.py national``.

In order: ``ingest`` parses the raw DGT, INE, Ministry and CORES files into ``data/staging/dgt``;
``reconcile`` ties them to DGT's published totals (482 checks, and the pipeline stops if one
fails); ``process`` writes the processed crash table; ``associations`` fits the supporting
association analysis of the DGT crash records and counts the crash explorer's cells; ``results``
writes every other national result table; ``cards`` writes the two national model cards, after
the DGT microdata audit (``models.validate``). ``withdrawn`` rebuilds the withdrawn forecast's
tables on request only.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from dgt_stats.national import (
    associations,
    crash_cells,
    derive,
    features,
    io_exposure,
    io_microdata,
    io_reports,
    io_tables,
    model_cards,
    reconcile,
    summaries,
)
from dgt_stats.paths import (
    DGT_PROCESSED_CRASHES,
    MICRODATA_YEARS,
    PROCESSED_DATA_DIR,
    TABLES_DIR,
)

log = logging.getLogger(__name__)


def ingest(force: bool = False, years: tuple[int, ...] = MICRODATA_YEARS) -> None:
    """The staging layer: the crash microdata, the published tables, the exposure denominators
    and the speed report. Each output that exists is skipped unless ``force``."""
    io_microdata.build_all(years, force=force)
    io_tables.build_tables(force=force)
    io_exposure.build_exposure(force=force)
    io_reports.build_reports(force=force)


def reconcile_checks() -> None:
    """The reconciliation checks; raises if any fails, so that nothing is built on them."""
    results, _ = reconcile.run_all()
    failed = int((~results.passed).sum())
    if failed:
        raise SystemExit(
            f"reconciliation failed: {failed} checks did not pass; see {reconcile.VALIDATION_PATH}"
        )


def process(force: bool = False) -> Path:
    """The processed crash table: the staged crashes with derived fields and English labels."""
    if DGT_PROCESSED_CRASHES.exists() and not force:
        log.info("processed crashes: exists, skipping (%s)", DGT_PROCESSED_CRASHES.name)
        return DGT_PROCESSED_CRASHES
    started = time.perf_counter()
    frame = derive.add_fields(io_microdata.read_all())
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DGT_PROCESSED_CRASHES, index=False)
    log.info(
        "processed crashes: %s rows, %s columns -> %s (%.1f MB, %.1f s)",
        f"{len(frame):,}",
        frame.shape[1],
        DGT_PROCESSED_CRASHES.name,
        DGT_PROCESSED_CRASHES.stat().st_size / 1e6,
        time.perf_counter() - started,
    )
    return DGT_PROCESSED_CRASHES


def run_associations() -> None:
    """The supporting association analysis of DGT's crash records (``q3_*``) and the crash
    explorer's counts, from the same processed records."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    crashes = features.read_crashes()
    frame = features.model_frame(crashes)
    log.info("model frame: %s crashes, %d predictors", f"{len(frame):,}", len(features.PREDICTORS))
    log.info(
        "junction flag read the other way round in %s",
        features.province_years(frame.attrs["junction_inverted"]) or "no province-year",
    )
    fits: dict[str, associations.Fit] = {}
    coefficients, effects, calibrations, holdout, stability = [], [], [], [], []
    periods, locations = [], []
    for outcome in features.OUTCOMES:
        fit = associations.fit_severity(frame, outcome)
        fits[outcome] = fit
        log.info("%s: fitted on %s crashes, %s events", outcome, f"{fit.n:,}", f"{fit.events:,}")
        coefficients.append(associations.coefficient_table(frame, fit))
        effects.append(associations.marginal_effects(frame, fit))
        locations.append(associations.location_contrasts(frame, fit))
        periods.append(associations.period_refits(frame, outcome))
        calibration, summary = associations.holdout_check(frame, outcome)
        calibrations.append(calibration)
        holdout.append(summary)
        log.info(
            "%s: holdout AUC %.3f, Brier %.4f", outcome, summary.auc.iloc[0], summary.brier.iloc[0]
        )
        stability.append(associations.year_stability(frame, fit))
    adverse = pd.concat(
        [associations.adverse_conditions(frame, outcome) for outcome in features.OUTCOMES],
        ignore_index=True,
    )
    log.info("adverse conditions: %d variant estimates", len(adverse))
    composition = pd.concat(
        [
            associations.level_composition(frame, predictor, level)
            for predictor, level in (("weather", "hail or snow"), ("weather", "rain"))
        ],
        ignore_index=True,
    )
    exclusions = associations.level_exclusions(frame, "weather", "hail or snow")
    regime = associations.recording_regime(frame)
    regime_fits = associations.regime_sensitivity(frame, fits)
    log.info("recording regime: refitted without %s", ", ".join(features.CATALAN_PROVINCES))
    junction = associations.junction_sensitivity(crashes)
    log.info("junction: %d treatments refitted", junction.treatment.nunique())
    outputs = {
        "q3_model_coefficients": pd.concat(coefficients, ignore_index=True),
        "q3_marginal_effects": pd.concat(effects, ignore_index=True),
        "q3_calibration": pd.concat(calibrations, ignore_index=True),
        "q3_holdout_summary": pd.concat(holdout, ignore_index=True),
        "q3_year_stability": pd.concat(stability, ignore_index=True),
        "q3_period_refits": pd.concat(periods, ignore_index=True),
        "q3_location_contrasts": pd.concat(locations, ignore_index=True),
        "q3_profiles": associations.profiles(frame, fits),
        "q3_adverse_conditions": adverse,
        "q3_adverse_composition": composition,
        "q3_adverse_exclusions": exclusions,
        "q3_recording_regime": regime,
        "q3_regime_sensitivity": regime_fits,
        "q3_groupings": features.grouping_table(frame),
        "q3_junction_coding": features.junction_coding_table(crashes),
        "q3_junction_sensitivity": junction,
        crash_cells.NAME: crash_cells.crash_cells(),
    }
    for name, table in outputs.items():
        target = TABLES_DIR / f"{name}.csv"
        table.to_csv(target, index=False, float_format="%.6g")
        log.info("table %-24s %5d rows -> %s", name, len(table), target.name)


def write_registry(registry: dict[str, Callable[[], pd.DataFrame]]) -> dict[str, pd.DataFrame]:
    """Build and write every table of a registry of result tables."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frames = {}
    for name, builder in registry.items():
        frame = builder()
        target = TABLES_DIR / f"{name}.csv"
        # Ten significant digits: enough for every number the pages print, and stable across
        # library versions, which differ in the last bits of the fitted coefficients.
        frame.to_csv(target, index=False, float_format="%.10g")
        frames[name] = frame
        log.info("table %-28s %6d rows -> %s", name, len(frame), target.name)
    return frames


def results() -> None:
    """Every other national result table (:data:`summaries.SUMMARIES`)."""
    write_registry(summaries.SUMMARIES)


def withdrawn() -> None:
    """The withdrawn forecast's tables: slow, and read only by its card and the model review."""
    write_registry(summaries.WITHDRAWN_SUMMARIES)


def cards() -> None:
    """The cards of the national association analysis and of the withdrawn forecast."""
    for path in (model_cards.write_forecast_card(), model_cards.write_severity_card()):
        log.info("model card %s", path.name)
