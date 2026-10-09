"""Static site builder: plain HTML and one CSS file, from the result tables and figures.

No template engine, one small script (``script``) that only makes reading easier (every page
works without it) and two self-hosted open fonts (``fonts``). The navigation (``NAV_GROUPS``) follows the argument: the
national picture from DGT and INE with three supporting analyses, the Catalan and Barcelona crash
records, the two severity models and their external validation, and the sources and methods.
Every sentence that carries a number computes it from a committed result table at build time, so
the prose cannot drift from the tables; full tables are linked as CSV rather than printed. Only
the tables a page links are copied into ``site/tables``, and only the figures a page shows into
``site/figures``, with their drawings for a phone's column in ``site/figures/narrow``; the other
result tables stay in the repository, unpublished.

One module per page: ``overview``, ``trends``, ``long_run``, ``seasons``, ``drivers``,
``vehicles``, ``speed``, ``factors``, the supporting ``severity`` and ``policy``,
``regional`` (Catalonia and Barcelona), ``models``, ``validation``, ``sources`` and ``data``. The
shared furniture is in ``components``, the stylesheet in ``style``, the script in ``script``, the result tables several
pages quote in ``numbers`` and the helpers of the regional, model and validation pages in
``regional_common``.

The interactive tools (``explore`` and the ``tool_*`` modules) are pages like the others; their
scripts and the data they read are published in ``site/tools``, and the calculator's engine and
model in ``site/models``. Pages that no builder writes any more, such as the notices of withdrawn
analyses, are removed from ``site``.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, TABLES_DIR
from dgt_stats.site import explore
from dgt_stats.site.components import (
    ALL_PAGES,
    NAV_GROUPS,
    PAGES,
    PROFILE_URL,
    REPO_URL,
    SUPPORTING_PAGES,
    _signed_pct,
    esc,
    mark_spanish,
    read_captions,
    table,
)
from dgt_stats.site.data import page_data
from dgt_stats.site.drivers import page_drivers
from dgt_stats.site.factors import page_factors
from dgt_stats.site.long_run import page_long_run
from dgt_stats.site.models import page_severity_models
from dgt_stats.site.overview import page_index
from dgt_stats.site.policy import page_policy
from dgt_stats.site.regional import page_barcelona, page_catalonia
from dgt_stats.site.script import SCRIPT
from dgt_stats.site.seasons import page_seasons
from dgt_stats.site.severity import page_severity
from dgt_stats.site.sources import page_sources
from dgt_stats.site.speed import page_speed
from dgt_stats.site.style import STYLE
from dgt_stats.site.trends import page_trends
from dgt_stats.site.validation import page_validation
from dgt_stats.site.vehicles import page_vehicles

__all__ = [
    "ALL_PAGES",
    "NAV_GROUPS",
    "PAGES",
    "PAGE_BUILDERS",
    "PROFILE_URL",
    "REPO_URL",
    "SITE_DIR",
    "SUPPORTING_PAGES",
    "WITHDRAWN_PAGES",
    "_signed_pct",
    "build",
    "esc",
    "mark_spanish",
    "publish_tables",
    "read_captions",
    "table",
]


SITE_DIR = PROJECT_ROOT / "site"
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
# The crash-severity calculator: its arithmetic, its page script and the model it reads.
CALCULATOR_ASSETS = (ASSETS_DIR / "severity-engine.js", ASSETS_DIR / "severity-calculator.js")
CALCULATOR_MODEL = PROJECT_ROOT / "reports" / "models" / "severity_model.json"
# The other tools' scripts: the shared helpers and one per tool, published in ``site/tools``.
TOOL_ASSETS = tuple(
    ASSETS_DIR / f"{name}.js"
    for name in ("tools", *(slug for slug, _ in explore.TOOLS if slug != "calculator"))
)


PAGE_BUILDERS = {
    "index": page_index,
    "explore": explore.page_explore,
    "calculator": explore.tool_calculator.page_calculator,
    "driver-risk": explore.tool_driver_risk.page_driver_risk,
    "crash-explorer": explore.tool_crashes.page_crash_explorer,
    "trends-explorer": explore.tool_trends.page_trends_explorer,
    "trends": page_trends,
    "long-run": page_long_run,
    "seasons": page_seasons,
    "drivers": page_drivers,
    "vehicles": page_vehicles,
    "speed": page_speed,
    "factors": page_factors,
    "severity": page_severity,
    "policy": page_policy,
    "catalonia": page_catalonia,
    "barcelona": page_barcelona,
    "severity-models": page_severity_models,
    "validation": page_validation,
    "sources": page_sources,
    "data": page_data,
}


def build(site_dir: Path = SITE_DIR) -> list[Path]:
    """Write every page, the stylesheet, the figures and the downloadable tables into ``site_dir``."""
    captions = read_captions()
    site_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    # The web fonts and their licences.
    fonts_dir = site_dir / "fonts"
    if fonts_dir.exists():
        shutil.rmtree(fonts_dir)
    fonts_dir.mkdir()
    for path in sorted(FONTS_DIR.glob("*.*")):
        target = fonts_dir / path.name
        shutil.copyfile(path, target)
        written.append(target)
    # The one site-wide script is the site's own; any other, such as those of the withdrawn
    # simulator and factor models, is removed. The calculator's engine, its page script and the
    # exported model it reads live apart, in ``models/``, and only its page loads them.
    for stale in site_dir.glob("*.js"):
        stale.unlink()
    models_dir = site_dir / "models"
    if models_dir.exists():
        shutil.rmtree(models_dir)
    models_dir.mkdir()
    for source in (*CALCULATOR_ASSETS, CALCULATOR_MODEL):
        target = models_dir / source.name
        shutil.copyfile(source, target)
        written.append(target)
    # The other tools' scripts and the data each computes from the result tables.
    tools_dir = site_dir / "tools"
    if tools_dir.exists():
        shutil.rmtree(tools_dir)
    tools_dir.mkdir()
    for source in TOOL_ASSETS:
        target = tools_dir / source.name
        shutil.copyfile(source, target)
        written.append(target)
    for _, module in explore.TOOLS:
        for name, payload in module.data_files().items():
            target = tools_dir / name
            target.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            written.append(target)
    style = site_dir / "style.css"
    style.write_text(STYLE.strip() + "\n", encoding="utf-8")
    script = site_dir / "site.js"
    script.write_text(SCRIPT.strip() + "\n", encoding="utf-8")
    written.extend([style, script])
    for slug, builder in PAGE_BUILDERS.items():
        target = site_dir / f"{slug}.html"
        target.write_text(builder(captions), encoding="utf-8")
        written.append(target)
    pages = [path for path in written if path.suffix == ".html"]
    written.extend(publish_figures(site_dir, pages))
    written.extend(publish_tables(site_dir, pages))
    # A page no builder wrote any more is dead: remove it rather than leave it published.
    for stale in set(site_dir.glob("*.html")) - set(written):
        stale.unlink()
    return written


# A result table as a page links it for download.
TABLE_REFERENCE = re.compile(r'href="tables/([^"/]+\.csv)"')


def publish_tables(site_dir: Path, pages: list[Path], source_dir: Path = TABLES_DIR) -> list[Path]:
    """Copy into ``site_dir/tables`` the result tables that ``pages`` link, and nothing else: a
    table no page links (a withdrawn analysis's record, a check behind a generated document) stays
    in the repository and is not published. A page that links a table the reports do not hold
    fails the build."""
    target_dir = site_dir / "tables"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)
    linked = {
        name for page in pages for name in TABLE_REFERENCE.findall(page.read_text(encoding="utf-8"))
    }
    written = []
    for name in sorted(linked):
        source = source_dir / name
        if not source.exists():
            raise FileNotFoundError(f"a page links tables/{name}, which no step wrote")
        target = target_dir / name
        shutil.copyfile(source, target)
        written.append(target)
    return written


# A figure as a page refers to it: the chart, its full-size link and the drawing a phone loads.
FIGURE_REFERENCE = re.compile(r'(?:src|srcset|href)="figures/((?:narrow/)?[^"/]+\.svg)"')


def publish_figures(site_dir: Path, pages: list[Path]) -> list[Path]:
    """Copy into ``site_dir/figures`` the figures that ``pages`` show, with the narrow drawings
    they serve to phones, and nothing else: a figure drawn but shown on no page is not published.
    A page that shows a figure the reports do not hold fails the build."""
    target_dir = site_dir / "figures"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir()
    shown = {
        reference
        for page in pages
        for reference in FIGURE_REFERENCE.findall(page.read_text(encoding="utf-8"))
    }
    written = []
    for reference in sorted(shown):
        source = FIGURES_DIR / reference
        if not source.exists():
            raise FileNotFoundError(f"a page shows figures/{reference}, which was not drawn")
        target = target_dir / reference
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, target)
        written.append(target)
    return written
