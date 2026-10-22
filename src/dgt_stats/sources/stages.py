"""The cross-cutting source documents, run by ``scripts/run.py sources``.

``inventory`` profiles every file under ``data/raw``; ``profile`` compares how each source came
to exist.
"""

from __future__ import annotations

import logging

from dgt_stats.sources import inventory as file_inventory
from dgt_stats.sources import profile as source_profile

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
