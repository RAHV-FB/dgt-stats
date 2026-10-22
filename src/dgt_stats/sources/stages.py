"""The cross-cutting source documents, run by ``scripts/run.py sources``.

``inventory`` profiles every file under ``data/raw``; ``profile`` compares how each source came
to exist; ``catalogue`` writes the map of sections, sources and tables (``docs/catalogue.md``) and
an index in each table folder. ``catalogue`` reads the built pages, to say which page publishes
each table, so it runs after the site.
"""

from __future__ import annotations

import logging

from dgt_stats.sources import inventory as file_inventory
from dgt_stats.sources import profile as source_profile
from dgt_stats.sources import provenance

log = logging.getLogger(__name__)


def inventory() -> None:
    """The raw-file inventory: one row per file, and its document."""
    frame = file_inventory.write()
    log.info(
        "inventory: %d files, %d duplicates",
        len(frame),
        int((frame.duplicate_status != "unique").sum()),
    )


def profile() -> None:
    """The source comparison: each source against the same questions."""
    source_profile.write()


def catalogue() -> None:
    """The catalogue written out: docs/catalogue.md and one README per table folder."""
    provenance.write()
