"""Static site builder: plain HTML and one CSS file, from the result tables and figures.

No template engine and no scripts. The navigation (``NAV_GROUPS``) follows the source hierarchy
of ``dgt_stats.layers``: Spain from DGT and INE (seven findings and two supporting analyses), the
Catalan crash records, the Barcelona crash and person records, the models that beat a descriptive
table, how far they generalise, and the sources and methods. Descriptive, predictive and
transportability findings sit on separate pages.
Every sentence that carries a number computes it from a committed result table at build time, so
the prose cannot drift from the tables; full tables are copied into ``site/tables`` and linked as
CSV rather than printed.

One module per national page (``overview``, ``trends``, ``long_run``, ``seasons``, ``drivers``,
``vehicles``, ``speed``, ``factors``, ``forecast``, ``data``, and the supporting ``severity`` and
``policy``), the regional, model, generalisability and sources pages in ``microdata_pages``, with
the shared furniture in ``components``, the stylesheet in ``style`` and the result tables several
pages quote in ``numbers``.

Two kinds of old URL are kept alive. A renamed page (``MOVED_PAGES``) refreshes to its successor.
A withdrawn analysis (``WITHDRAWN_PAGES``: the speed-law simulator and the distraction,
alcohol-and-drugs and enforcement models, whose results came from coefficients published in
external studies) is replaced by a short notice that says why and links to the data page; it is
not a redirect, and no live page links to it.
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
    WITHDRAWN_PAGES,
    WITHDRAWN_REASON,
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
from dgt_stats.site.forecast import page_forecast
from dgt_stats.site.long_run import page_long_run
from dgt_stats.site.microdata_pages import (
    page_barcelona,
    page_catalonia,
    page_severity_models,
    page_sources,
    page_transport,
)
from dgt_stats.site.overview import page_index
from dgt_stats.site.policy import page_policy
from dgt_stats.site.seasons import page_seasons
from dgt_stats.site.severity import page_severity
from dgt_stats.site.speed import page_speed
from dgt_stats.site.style import STYLE
from dgt_stats.site.trends import page_trends
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
    "forecast": page_forecast,
    "transport": page_transport,
    "sources": page_sources,
    "data": page_data,
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


# The live pages that hold what the repository's own data say on each withdrawn page's subject.
WITHDRAWN_SUCCESSORS = {
    "forecast": "the model of monthly deaths, fitted only to the repository's series",
    "speed": "deaths per crash where the police recorded speed, and the speed record itself",
    "factors": "the recorded concurrent factors, alcohol and distraction among them",
}
WITHDRAWN_RELATED = {
    "simulator": ("forecast", "speed"),
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
        "<p>The project now keeps only results computed from rows and columns of the files in "
        "the repository; studies published elsewhere may explain a definition or a method, but "
        "they do not supply an observation, a coefficient or a relative risk. What the "
        f"repository's own data show on these subjects is on these pages: {links}. The sources "
        'and methods are on the <a href="data.html">data page</a>.</p>'
    )
    return render_page(
        slug,
        "This analysis was withdrawn",
        WITHDRAWN_REASON,
        body,
        head='\n<meta name="robots" content="noindex">',
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
    # The site runs no script: remove any left from the withdrawn simulator and factor models.
    for stale in site_dir.glob("*.js"):
        stale.unlink()
    style = site_dir / "style.css"
    style.write_text(STYLE.strip() + "\n", encoding="utf-8")
    written.append(style)
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
