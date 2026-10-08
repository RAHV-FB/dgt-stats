"""The EMEF working-day mobility survey: ingestion, checks and car-driving exposure.

Usage:
    python scripts/emef.py build      # data/processed/emef_{persons,trips}.parquet, after every
                                     # check passes; reports/tables/emef_checks.csv, emef_inventory
    python scripts/emef.py validate   # emef_reproduction (published 2024 figures) and
                                     # emef_distance_validation (EMEF 2021 distance report) and
                                     # emef_imputation_check (duration-only distances)
    python scripts/emef.py exposure   # emef_exposure_*, emef_km_by_band, emef_sensitivity and the
                                     # frequency and weekend tables
    python scripts/emef.py all

``build`` takes about a minute; ``exposure`` about five.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from dgt_stats.emef import distance, exposure, ingest  # noqa: E402
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
    write(distance.validate_against_report(), "emef_distance_validation")
    write(exposure.imputation_check(), "emef_imputation_check")


def run_exposure() -> None:
    write(exposure.contemporary(), "emef_exposure_contemporary")
    write(exposure.by_area(), "emef_exposure_area")
    write(exposure.series(), "emef_exposure_series")
    write(exposure.periods(), "emef_exposure_periods")
    write(exposure.km_by_band(), "emef_km_by_band")
    write(exposure.sensitivity(), "emef_sensitivity")
    write(exposure.usual_frequency(), "emef_driving_frequency")
    write(exposure.weekend_away_2023(), "emef_weekend_2023")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=("build", "validate", "exposure", "all"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = time.time()
    if args.step in ("build", "all"):
        run_build()
    if args.step in ("validate", "all"):
        run_validate()
    if args.step in ("exposure", "all"):
        run_exposure()
    log.info("done in %.1f s", time.time() - start)


if __name__ == "__main__":
    main()
