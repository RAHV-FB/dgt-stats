"""Build the interim data layer from the raw DGT files and run the validation checks.

Usage:
    python scripts/ingest.py all
    python scripts/ingest.py microdata --years 2020 2024
    python scripts/ingest.py validate

Each sub-command is idempotent. Existing outputs are skipped unless --force is given.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dgt_stats import io_exposure, io_microdata, io_reports, io_tables, validate  # noqa: E402
from dgt_stats.paths import MICRODATA_YEARS  # noqa: E402

log = logging.getLogger("ingest")

STEPS = ("microdata", "tables", "exposure", "reports", "validate")


def run_microdata(years: tuple[int, ...], force: bool) -> None:
    io_microdata.build_all(years, force=force)


def run_tables(force: bool) -> None:
    io_tables.build_tables(force=force)


def run_exposure(force: bool) -> None:
    io_exposure.build_exposure(force=force)


def run_reports(force: bool) -> None:
    io_reports.build_reports(force=force)


def run_validate() -> int:
    """Run the reconciliation checks; returns how many failed, so the CLI can stop the pipeline."""
    results, _ = validate.run_all()
    return int((~results.passed).sum())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "step", choices=(*STEPS, "all"), help="which layer to build, or all of them"
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=list(MICRODATA_YEARS),
        help="microdata years to process (default: every available year)",
    )
    parser.add_argument("--force", action="store_true", help="rebuild outputs that already exist")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug-level logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    started = time.perf_counter()
    steps = STEPS if args.step == "all" else (args.step,)
    failed = 0
    for step in steps:
        if step == "microdata":
            run_microdata(tuple(args.years), args.force)
        elif step == "tables":
            run_tables(args.force)
        elif step == "exposure":
            run_exposure(args.force)
        elif step == "reports":
            run_reports(args.force)
        elif step == "validate":
            failed = run_validate()
    log.info("done in %.1f s", time.perf_counter() - started)
    if failed:
        log.error(
            "validation failed: %d reconciliation checks did not pass; see %s",
            failed,
            validate.VALIDATION_PATH,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
