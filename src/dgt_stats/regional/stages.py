"""The regional section's pipeline stages, run by ``scripts/run.py regional``.

In order: ``build`` stages the Barcelona and Catalonia files and writes their canonical tables;
``quality`` writes the data-quality report, the Barcelona vehicle audit and the tables behind
them; ``analyse`` writes the descriptive tables and the comparison with DGT and INE at province
and year. ``organise`` files loose downloads under ``data/raw/<source>/`` and is run by hand.
"""

from __future__ import annotations

import logging

from dgt_stats.regional import barcelona, catalonia, crosssource, descriptive, files, quality

log = logging.getLogger(__name__)


def organise() -> None:
    """File loose downloads under ``data/raw/<source>/`` and register them in the manifest."""
    result = files.organise()
    for old, new in result.moved:
        log.info("moved %s -> %s", old.name, new)
    for path, original in result.duplicates:
        log.warning("duplicate copy left in place, not processed: %s (= raw/%s)", path, original)
    for path, reason in result.skipped:
        log.warning("skipped %s: %s", path, reason)
    log.info("registered %d files in the manifest", len(result.registered))


def build(force: bool = False) -> None:
    """Staging and the canonical tables of both sources; restaged when a raw file changes."""
    barcelona.build(force=force)
    catalonia.build(force=force)


def run_quality() -> None:
    """The data-quality report and the Barcelona vehicle audit."""
    quality.build()
    log.info("wrote %s and %s", quality.REPORT.name, "barcelona_vehicle_audit.md")


def analyse() -> None:
    """The descriptive tables and the aggregate comparison with the national data."""
    descriptive.write()
    crosssource.write()
