"""Static site builder: plain HTML and one CSS file, from the result tables and figures.

No template engine, one small script (``script``) that only makes reading easier (every page
works without it) and two self-hosted open fonts (``fonts``). The navigation (``NAV_GROUPS``) follows the argument: the
national picture from DGT and INE with three supporting analyses, the Catalan and Barcelona crash
records, the two severity models and their external validation, and the sources and methods.
Every sentence that carries a number computes it from a committed result table at build time, so
the prose cannot drift from the tables; full tables are copied into ``site/tables`` and linked as
CSV rather than printed.

One module per page: ``overview``, ``trends``, ``long_run``, ``seasons``, ``drivers``,
``vehicles``, ``speed``, ``factors``, the supporting ``severity`` and ``policy``,
``regional`` (Catalonia and Barcelona), ``models``, ``validation``, ``sources`` and ``data``. The
shared furniture is in ``components``, the stylesheet in ``style``, the script in ``script``, the result tables several
pages quote in ``numbers`` and the helpers of the regional, model and validation pages in
``regional_common``.

Two kinds of old URL are kept alive. A renamed page (``MOVED_PAGES``) refreshes to its successor.
A withdrawn analysis (``WITHDRAWN_PAGES``: the speed-law simulator and the distraction,
alcohol-and-drugs and enforcement models, whose results came from coefficients published in
external studies, and the monthly deaths forecast, which did worse than last year's count on the
years it had not seen) is replaced by a short notice that says why and links to the pages that hold
the repository's own results on the subject; it is not a redirect, and no live page links to it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, TABLES_DIR
from dgt_stats.site.components import (
    ALL_PAGES,
    MOVED_PAGES,
    NAV_GROUPS,
    PAGES,
    PROFILE_URL,
    REPO_URL,
    SUPPORTING_PAGES,
    WITHDRAWN_LEADS,
    WITHDRAWN_PAGES,
    WITHDRAWN_REASON,
    WITHDRAWN_TITLES,
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
    "MOVED_PAGES",
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
    "page_moved",
    "page_withdrawn",
    "read_captions",
    "table",
]


SITE_DIR = PROJECT_ROOT / "site"
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
# The crash-severity calculator: its arithmetic, its page script and the model it reads.
CALCULATOR_ASSETS = (ASSETS_DIR / "severity-engine.js", ASSETS_DIR / "severity-calculator.js")
CALCULATOR_MODEL = PROJECT_ROOT / "reports" / "models" / "severity_model.json"


PAGE_BUILDERS = {
    "index": page_index,
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


def page_moved(old: str, new: str) -> str:
    """A pointer page for a slug that was renamed, refreshing to its successor."""
    title = dict(ALL_PAGES)[new]
    return render_page(
        old,
        "This page has moved",
        f"What was on this page is now on the page {title}.",
        f'<p><a href="{new}.html">Continue to {esc(title)}</a>.</p>',
        head=f'\n<meta http-equiv="refresh" content="0; url={new}.html">'
        f'\n<link rel="canonical" href="{new}.html">',
    )


# The live pages that hold what the repository's own data say on each withdrawn page's subject.
WITHDRAWN_SUCCESSORS = {
    "long-run": "the long-run trend in deaths and how far recent years depart from it",
    "trends": "deaths in the latest year against the base year, as counts and as rates",
    "speed": "deaths per crash where the police recorded speed, and the speed record itself",
    "factors": "how often the police record alcohol, distraction and other factors in crashes",
}
WITHDRAWN_RELATED = {
    "forecast": ("long-run", "trends"),
    "simulator": ("speed",),
    "distraction": ("factors",),
    "alcohol-drugs": ("factors",),
    "enforcement": ("speed", "factors"),
}


def page_withdrawn(slug: str) -> str:
    """A short notice for a withdrawn analysis: why it went, and where the data-only work is.

    Not a redirect: a reader who arrives from an old link is told what the page was and why it is
    gone, rather than sent on silently to a page that says something else.
    """
    if slug in dict(ALL_PAGES) or slug in MOVED_PAGES:
        raise ValueError(f"withdrawn page {slug!r} is also a live or moved page")
    titles = dict(ALL_PAGES)
    links = "; ".join(
        f'<a href="{target}.html">{esc(titles[target])}</a>, {esc(WITHDRAWN_SUCCESSORS[target])}'
        for target in WITHDRAWN_RELATED[slug]
    )
    body = (
        f"<p>{esc(WITHDRAWN_PAGES[slug])}</p>"
        f"<p>What the repository's own data show on this subject is on these pages: {links}. "
        'The <a href="data.html">methodology</a> explains how the results on the site are '
        "produced.</p>"
    )
    return render_page(
        slug,
        WITHDRAWN_TITLES[slug],
        WITHDRAWN_LEADS.get(slug, WITHDRAWN_REASON),
        body,
        head='\n<meta name="robots" content="noindex">',
    )


def build(site_dir: Path = SITE_DIR) -> list[Path]:
    """Write every page, the stylesheet, the figures and the downloadable tables into ``site_dir``."""
    captions = read_captions()
    site_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source, name, pattern in (
        (FIGURES_DIR, "figures", "*.svg"),
        (TABLES_DIR, "tables", "*.csv"),
        # The web fonts and their licences.
        (FONTS_DIR, "fonts", "*.*"),
    ):
        target_dir = site_dir / name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir()
        for path in sorted(source.glob(pattern)):
            target = target_dir / path.name
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
    style = site_dir / "style.css"
    style.write_text(STYLE.strip() + "\n", encoding="utf-8")
    script = site_dir / "site.js"
    script.write_text(SCRIPT.strip() + "\n", encoding="utf-8")
    written.extend([style, script])
    for slug, builder in PAGE_BUILDERS.items():
        target = site_dir / f"{slug}.html"
        target.write_text(builder(captions), encoding="utf-8")
        written.append(target)
    for old, new in MOVED_PAGES.items():
        target = site_dir / f"{old}.html"
        target.write_text(page_moved(old, new), encoding="utf-8")
        written.append(target)
    for slug in WITHDRAWN_PAGES:
        target = site_dir / f"{slug}.html"
        target.write_text(page_withdrawn(slug), encoding="utf-8")
        written.append(target)
    # A page no builder wrote any more is dead: remove it rather than leave it published.
    for stale in set(site_dir.glob("*.html")) - set(written):
        stale.unlink()
    return written
