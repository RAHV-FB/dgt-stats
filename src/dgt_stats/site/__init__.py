"""Static site builder: plain HTML, one CSS file and one script, from the result tables and figures.

No template engine. The site answers one question, what changes when road risk is measured rather
than counted, in seven analysis pages, a simulator of speed laws, an overview and a data page, with
two supporting analyses (the severity model and the 2006 break) kept apart; the navigation shows
them in labelled groups (``NAV_GROUPS``).
Every sentence that carries a number computes it from a committed result table at build time, so
the prose cannot drift from the tables; full tables are copied into ``site/tables`` and linked as
CSV rather than printed. The one script, ``simulator.js``, is a port of
:mod:`dgt_stats.simulator`, and only the simulator page loads it.

One module per page (``overview``, ``trends``, ``long_run``, ``seasons``, ``drivers``,
``vehicles``, ``speed``, ``factors``, ``simulator``, ``data``, and the supporting ``severity`` and
``policy``), with the shared furniture in ``components``, the stylesheet in ``style`` and the
result tables several pages quote in ``numbers``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, SIMULATOR_EVIDENCE_PATH, TABLES_DIR
from dgt_stats.site.components import (
    ALL_PAGES,
    MOVED_PAGES,
    NAV_GROUPS,
    PAGES,
    PROFILE_URL,
    REPO_URL,
    SUPPORTING_PAGES,
    _signed_int,
    _signed_pct,
    esc,
    mark_spanish,
    read_captions,
    render_page,
    table,
)
from dgt_stats.site.data import page_data
from dgt_stats.site.drivers import page_drivers
from dgt_stats.site.factors import page_factors
from dgt_stats.site.long_run import page_long_run
from dgt_stats.site.overview import page_index
from dgt_stats.site.policy import page_policy
from dgt_stats.site.seasons import page_seasons
from dgt_stats.site.severity import LITERATURE, page_severity
from dgt_stats.site.simulator import page_simulator
from dgt_stats.site.speed import page_speed
from dgt_stats.site.style import STYLE
from dgt_stats.site.trends import page_trends
from dgt_stats.site.vehicles import page_vehicles

__all__ = [
    "ALL_PAGES",
    "LITERATURE",
    "MOVED_PAGES",
    "NAV_GROUPS",
    "PAGES",
    "PAGE_BUILDERS",
    "PROFILE_URL",
    "REPO_URL",
    "SITE_DIR",
    "SUPPORTING_PAGES",
    "_signed_int",
    "_signed_pct",
    "build",
    "esc",
    "mark_spanish",
    "read_captions",
    "table",
]


SITE_DIR = PROJECT_ROOT / "site"


# The one script on the site: the simulator's arithmetic, a port of ``simulator.py``.
SIMULATOR_SCRIPT = Path(__file__).parents[1] / "assets" / "simulator.js"


PAGE_BUILDERS = {
    "index": page_index,
    "trends": page_trends,
    "long-run": page_long_run,
    "seasons": page_seasons,
    "drivers": page_drivers,
    "vehicles": page_vehicles,
    "speed": page_speed,
    "factors": page_factors,
    "simulator": page_simulator,
    "data": page_data,
    "severity": page_severity,
    "policy": page_policy,
}


def page_moved(old: str, new: str) -> str:
    """A pointer page for a slug that was renamed, refreshing to its successor."""
    title = dict(ALL_PAGES)[new]
    return render_page(
        old,
        "This page has moved",
        f"This page is now {title}; the site was reorganised around measuring road risk.",
        f'<p>Its content is now on <a href="{new}.html">{esc(title)}</a>.</p>',
        head=f'\n<meta http-equiv="refresh" content="0; url={new}.html">'
        f'\n<link rel="canonical" href="{new}.html">',
    )


def build(site_dir: Path = SITE_DIR) -> list[Path]:
    """Write every page, the stylesheet, the figures and the downloadable tables into ``site_dir``."""
    captions = read_captions()
    site_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source, name in ((FIGURES_DIR, "figures"), (TABLES_DIR, "tables")):
        target_dir = site_dir / name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir()
        for path in sorted(source.glob("*.svg" if name == "figures" else "*.csv")):
            target = target_dir / path.name
            shutil.copyfile(path, target)
            written.append(target)
    style = site_dir / "style.css"
    style.write_text(STYLE.strip() + "\n", encoding="utf-8")
    written.append(style)
    script = site_dir / SIMULATOR_SCRIPT.name
    shutil.copyfile(SIMULATOR_SCRIPT, script)
    written.append(script)
    evidence = site_dir / "tables" / "simulator_evidence.csv"
    shutil.copyfile(SIMULATOR_EVIDENCE_PATH, evidence)
    written.append(evidence)
    for slug, builder in PAGE_BUILDERS.items():
        target = site_dir / f"{slug}.html"
        target.write_text(builder(captions), encoding="utf-8")
        written.append(target)
    for old, new in MOVED_PAGES.items():
        target = site_dir / f"{old}.html"
        target.write_text(page_moved(old, new), encoding="utf-8")
        written.append(target)
    return written
