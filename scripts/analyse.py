"""Produce the national result tables, every figure and the national model cards.

Usage:
    python scripts/analyse.py tables     # reports/tables/q*.csv and the other national tables
    python scripts/analyse.py figures    # reports/figures/*.svg and captions.json
    python scripts/analyse.py cards      # docs/models/dgt_*.md (needs model.py and the DGT audit)
    python scripts/analyse.py all

Run after scripts/model.py and scripts/microdata.py: the figures include the regional ones, and
the card of the DGT association analysis quotes the DGT microdata audit.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from dgt_stats import figures, model_cards, summaries  # noqa: E402
from dgt_stats.paths import TABLES_DIR  # noqa: E402

log = logging.getLogger("analyse")


def run_tables() -> dict[str, pd.DataFrame]:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frames = {}
    for name, builder in summaries.SUMMARIES.items():
        frame = builder()
        target = TABLES_DIR / f"{name}.csv"
        # Ten significant digits: enough for every number the pages print, and stable across
        # library versions, which differ in the last bits of the fitted coefficients.
        frame.to_csv(target, index=False, float_format="%.10g")
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
    parser.add_argument("step", choices=("tables", "figures", "cards", "all"))
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
    if args.step in ("cards", "all"):
        for path in (model_cards.write_forecast_card(), model_cards.write_severity_card()):
            log.info("model card %s", path.name)
    log.info("done in %.1f s", time.perf_counter() - started)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
