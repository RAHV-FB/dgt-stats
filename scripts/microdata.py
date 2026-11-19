"""Build the regional crash microdata layers and the tables behind the Catalonia and Barcelona pages.

Usage:
    python scripts/microdata.py build       # data/staging/{barcelona,catalonia}, data/processed/*
    python scripts/microdata.py quality     # mq_bcn_structure, mq_bcn_count_semantics, mq_cat_checks
    python scripts/microdata.py features    # data/features/catalonia_crash_severity.parquet and
                                            # ml_recording_artefacts
    python scripts/microdata.py analyse     # descriptive tables, the Catalan-DGT reconciliation
                                            # and the DGT coding tables (dgt_audit_*)
    python scripts/microdata.py sources     # source_comparison.csv
    python scripts/microdata.py all         # all of the above, in this order

The Catalan file is the crash-microdata layer the severity model is trained on
(``scripts/severity_model.py``); the Barcelona files are described, not modelled. Every step reads
only the files the previous steps wrote; the raw files are never modified.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dgt_stats import dgt_coding, source_profile
from dgt_stats.microdata import barcelona, catalonia, crosssource, descriptive, quality
from dgt_stats.microdata.ml import features, recording

log = logging.getLogger("microdata")

STEPS = ("build", "quality", "features", "analyse", "sources")


def run(step: str, force: bool) -> None:
    if step == "build":
        barcelona.build(force=force)
        catalonia.build(force=force)
    elif step == "quality":
        for name, frame in quality.build().items():
            log.info("wrote %s: %d rows", name, len(frame))
    elif step == "features":
        frame = features.build()
        log.info("feature table: %s rows, %d columns", f"{len(frame):,}", frame.shape[1])
        log.info("ml_recording_artefacts: %d rows", len(recording.write()))
    elif step == "analyse":
        descriptive.write()
        crosssource.write()
        dgt_coding.write()
    elif step == "sources":
        source_profile.write()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("step", choices=(*STEPS, "all"))
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
