"""Render the static site into site/ from reports/tables and reports/figures.

Usage:
    python scripts/build_site.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dgt_stats import site  # noqa: E402

log = logging.getLogger("build_site")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    written = site.build()
    pages = [path.name for path in written if path.suffix == ".html"]
    log.info("wrote %d files to %s (pages: %s)", len(written), site.SITE_DIR, ", ".join(pages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
