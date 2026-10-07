"""Build the regional crash microdata layers and test the models built on them.

Usage:
    python scripts/microdata.py organise    # file loose downloads under data/raw/<source>/
    python scripts/microdata.py inventory   # reports/tables/data_inventory.csv, docs/RAW_FILE_INVENTORY.md
    python scripts/microdata.py build       # data/staging/{barcelona,catalonia}, data/processed/*
    python scripts/microdata.py quality     # docs/DATA_QUALITY_MICRODATA.md, vehicle audit, mq_*.csv
    python scripts/microdata.py features    # data/features/*.parquet
    python scripts/microdata.py analyse     # descriptive tables and the Catalan-DGT reconciliation
    python scripts/microdata.py models      # source models: ml_*.csv, rule baselines, leakage audit
    python scripts/microdata.py validate    # transfer tests, Barcelona diagnosis, DGT audit,
                                            # representativeness, outward path, model decisions,
                                            # model cards, docs/GENERALISABILITY.md
    python scripts/microdata.py documents   # re-render the validation documents from saved tables
    python scripts/microdata.py sources     # docs/SOURCE_COMPARISON.md (data-generating processes)
    python scripts/microdata.py all         # everything except organise (about 30 minutes)

The layers (dgt_stats.layers): DGT and INE are the national context; the Catalan file is the
crash-microdata layer the severity model is trained on; the Barcelona files are the rich
microdata layer; validation tests models across them and never merges their records. Every step
reads only the files the previous steps wrote; the raw files are never modified.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dgt_stats import source_profile
from dgt_stats.microdata import (
    barcelona,
    catalonia,
    crosssource,
    descriptive,
    inventory,
    quality,
    sources,
)
from dgt_stats.microdata.ml import features, reporting
from dgt_stats.microdata.validation import pipeline

log = logging.getLogger("microdata")

STEPS = ("inventory", "build", "quality", "features", "analyse", "models", "validate", "sources")


def run(step: str, force: bool) -> None:
    if step == "organise":
        result = sources.organise()
        for old, new in result.moved:
            log.info("moved %s -> %s", old.name, new)
        for path, original in result.duplicates:
            log.warning(
                "duplicate copy left in place, not processed: %s (= raw/%s)", path, original
            )
        for path, reason in result.skipped:
            log.warning("skipped %s: %s", path, reason)
        log.info("registered %d files in the manifest", len(result.registered))
    elif step == "inventory":
        frame = inventory.write()
        log.info(
            "inventory: %d files, %d duplicates",
            len(frame),
            int((frame.duplicate_status != "unique").sum()),
        )
    elif step == "build":
        barcelona.build(force=force)
        catalonia.build(force=force)
    elif step == "quality":
        quality.build()
        log.info("wrote %s and %s", quality.REPORT.name, "BARCELONA_VEHICLE_AUDIT.md")
    elif step == "features":
        for name, frame in features.build_all().items():
            log.info(
                "feature table %s: %s rows, %d columns", name, f"{len(frame):,}", frame.shape[1]
            )
    elif step == "models":
        tables = reporting.run()
        selected = tables["ml_selected"]
        for row in selected.itertuples():
            log.info(
                "%s / %s: %s, test ROC-AUC %.3f (n=%d, positives=%d)",
                row.model,
                row.feature_set,
                row.estimator,
                row.roc_auc,
                row.n,
                row.positives,
            )
    elif step == "validate":
        tables = pipeline.run()
        for row in tables["ml_model_decisions"].itertuples():
            log.info("decision %s: %s", row.model, row.keep)
    elif step == "documents":
        pipeline.documents()
    elif step == "sources":
        source_profile.write()
    elif step == "analyse":
        descriptive.write()
        crosssource.write()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("step", choices=("organise", "documents", *STEPS, "all"))
    parser.add_argument("--force", action="store_true", help="rebuild staged files")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    started = time.perf_counter()
    for step in STEPS if args.step == "all" else (args.step,):
        run(step, args.force)
    log.info("done in %.1f s", time.perf_counter() - started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
