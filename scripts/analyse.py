"""Produce the descriptive result tables and figures.

Usage:
    python scripts/analyse.py tables     # reports/tables/q*.csv
    python scripts/analyse.py figures    # reports/figures/*.svg and captions.json
    python scripts/analyse.py all
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from dgt_stats import figures, summaries  # noqa: E402
from dgt_stats.paths import TABLES_DIR  # noqa: E402

log = logging.getLogger("analyse")


def run_tables() -> dict[str, pd.DataFrame]:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frames = {}
    for name, builder in summaries.SUMMARIES.items():
        frame = builder()
        target = TABLES_DIR / f"{name}.csv"
        frame.to_csv(target, index=False)
        frames[name] = frame
        log.info("table %-28s %6d rows -> %s", name, len(frame), target.name)
    return frames


def run_figures(frames: dict[str, pd.DataFrame] | None = None) -> None:
    captions = figures.build_all(frames=frames)
    for name in captions:
        log.info("figure %s.svg", name)
    log.info("wrote %d figures and captions.json", len(captions))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("tables", "figures", "all"))
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    started = time.perf_counter()
    frames = None
    if args.step in ("tables", "all"):
        frames = run_tables()
    if args.step in ("figures", "all"):
        run_figures(frames)
    log.info("done in %.1f s", time.perf_counter() - started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
