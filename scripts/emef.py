"""The EMEF working-day mobility survey: ingestion and car-driving exposure.

Usage:
    python scripts/emef.py build      # data/processed/emef_{persons,trips}.parquet, after every
                                     # check passes
    python scripts/emef.py exposure   # emef_exposure_contemporary, emef_sensitivity and the 65+
                                     # employment benchmark
    python scripts/emef.py all

The checks themselves (the harmonisation checks of ``ingest.validate``, the published 2024
figures, the distance report's benchmarks and the duration-only distance check) are asserted by
``tests/test_emef.py`` and write no tables. ``build`` takes about a minute; ``exposure`` about
five.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# The distance model's fit sums a log-likelihood over tens of thousands of trips, so where the
# optimiser stops depends on the order of floating-point sums, which the BLAS thread count
# changes. One thread makes the committed tables reproducible on any machine.
for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from dgt_stats.emef import exposure, ingest  # noqa: E402
from dgt_stats.paths import TABLES_DIR  # noqa: E402

log = logging.getLogger("emef")


def write(frame: pd.DataFrame, name: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.10g")
    log.info("%s: %d rows", name, len(frame))


def run_build() -> None:
    people, trips = ingest.build()
    log.info("persons %d, trips %d", len(people), len(trips))


def run_exposure() -> None:
    write(exposure.contemporary(), "emef_exposure_contemporary")
    write(exposure.sensitivity(), "emef_sensitivity")
    write(exposure.employment_benchmark(), "emef_employment_benchmark")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=("build", "exposure", "all"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = time.time()
    if args.step in ("build", "all"):
        run_build()
    if args.step in ("exposure", "all"):
        run_exposure()
    log.info("done in %.1f s", time.time() - start)


if __name__ == "__main__":
    main()
