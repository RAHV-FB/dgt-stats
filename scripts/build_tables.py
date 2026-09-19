"""Build the processed crash table from the interim layer.

Usage:
    python scripts/build_tables.py [--force]

Reads data/interim/microdata/accidentes_all.parquet, adds the derived fields and English labels
from dgt_stats.derive, and writes data/processed/accidentes.parquet.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dgt_stats import derive, io_microdata  # noqa: E402
from dgt_stats.paths import PROCESSED_DATA_DIR  # noqa: E402

log = logging.getLogger("build_tables")

PROCESSED_CRASHES = PROCESSED_DATA_DIR / "accidentes.parquet"


def build(force: bool = False) -> Path:
    if PROCESSED_CRASHES.exists() and not force:
        log.info("processed crashes: exists, skipping (%s)", PROCESSED_CRASHES.name)
        return PROCESSED_CRASHES
    started = time.perf_counter()
    frame = derive.add_fields(io_microdata.read_all())
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(PROCESSED_CRASHES, index=False)
    log.info(
        "processed crashes: %s rows, %s columns -> %s (%.1f MB, %.1f s)",
        f"{len(frame):,}",
        frame.shape[1],
        PROCESSED_CRASHES.name,
        PROCESSED_CRASHES.stat().st_size / 1e6,
        time.perf_counter() - started,
    )
    return PROCESSED_CRASHES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild even if the output exists")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    build(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
