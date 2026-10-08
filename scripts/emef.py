"""The EMEF working-day mobility survey: ingestion and checks.

Usage:
    python scripts/emef.py build      # data/processed/emef_{persons,trips}.parquet, after every
                                     # check passes; reports/tables/emef_checks.csv, emef_inventory
    python scripts/emef.py validate   # emef_reproduction (published 2024 figures)
    python scripts/emef.py all

``build`` takes about a minute.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from dgt_stats.emef import ingest  # noqa: E402
from dgt_stats.paths import TABLES_DIR  # noqa: E402

log = logging.getLogger("emef")


def write(frame: pd.DataFrame, name: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.10g")
    log.info("%s: %d rows", name, len(frame))


def run_build() -> None:
    checks = ingest.validate()
    write(checks, "emef_checks")
    people, trips = ingest.build()
    log.info("persons %d, trips %d", len(people), len(trips))
    write(ingest.inventory(), "emef_inventory")


def run_validate() -> None:
    write(ingest.reproduce_2024(), "emef_reproduction")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=("build", "validate", "all"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = time.time()
    if args.step in ("build", "all"):
        run_build()
    if args.step in ("validate", "all"):
        run_validate()
    log.info("done in %.1f s", time.time() - start)


if __name__ == "__main__":
    main()
