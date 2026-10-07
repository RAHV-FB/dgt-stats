"""The furniture every page shares: navigation, number formats, tables, figures, the page frame."""

from __future__ import annotations

import html
import json
import re

import pandas as pd

from dgt_stats.paths import FIGURES_DIR, TABLES_DIR

REPO_URL = "https://github.com/RAHV-FB/dgt-stats"


PROFILE_URL = "https://github.com/RAHV-FB"


DOCS_URL = f"{REPO_URL}/blob/main/docs"


# The navigation follows the argument rather than the repository: the national picture from DGT
# and INE (with three supporting analyses), the regional crash records, the two severity models and
# their external validation, and the sources and methods.
OVERVIEW = "Overview"
SPAIN = "Spain"
SUPPORTING = "Supporting analyses"
REGIONAL = "Regional data"
MODELS = "Models"
METHODS = "Methods"
NAV_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (OVERVIEW, (("index", "Overview"),)),
    (
        SPAIN,
        (
            ("trends", "Trends since 2019"),
            ("long-run", "Long-run trends"),
            ("seasons", "Seasons"),
            ("drivers", "Drivers"),
            ("vehicles", "Vehicles"),
            ("speed", "Speed"),
            ("factors", "Recorded factors"),
        ),
    ),
    (
        SUPPORTING,
        (
            ("severity", "Crash circumstances"),
            ("forecast", "Monthly deaths forecast"),
            ("policy", "The 2006 points licence"),
        ),
    ),
    (REGIONAL, (("catalonia", "Catalonia"), ("barcelona", "Barcelona"))),
    (MODELS, (("severity-models", "Severity models"), ("validation", "External validation"))),
    (METHODS, (("sources", "Data sources and scope"), ("data", "Methodology"))),
)
# A group drawn inside another in the navigation: the supporting analyses belong to Spain.
NAV_PARENT = {SUPPORTING: SPAIN}
# The line above a page's title: the part of the argument the page belongs to.
EYEBROWS = {
    SPAIN: "Spain",
    SUPPORTING: "Spain · supporting analysis",
    REGIONAL: "Regional data",
    MODELS: "Models",
    METHODS: "Methods",
}


# The main pages, and the supporting analyses outside the central argument.
PAGES: tuple[tuple[str, str], ...] = tuple(
    page for group, pages in NAV_GROUPS if group != SUPPORTING for page in pages
)
SUPPORTING_PAGES: tuple[tuple[str, str], ...] = dict(NAV_GROUPS)[SUPPORTING]
SPAIN_PAGES: tuple[tuple[str, str], ...] = dict(NAV_GROUPS)[SPAIN]


ALL_PAGES = PAGES + SUPPORTING_PAGES
# Every page in reading order, as the navigation lists them; the pager follows it.
READING_ORDER: tuple[str, ...] = tuple(slug for _, pages in NAV_GROUPS for slug, _ in pages)


# Pages that existed under another name, kept as pointers so old links still arrive somewhere.
MOVED_PAGES = {"older-drivers": "drivers", "context": "long-run", "transport": "validation"}


# Pages whose analysis was withdrawn, each with the reason. Their URLs stay alive as short notices
# (not redirects): every result on them came from coefficients published in external studies, not
# from rows of the files in this repository, which the project no longer accepts.
WITHDRAWN_REASON = (
    "This analysis was withdrawn because its results came from coefficients published in "
    "external studies rather than from data in this repository."
)
WITHDRAWN_PAGES = {
    "simulator": (
        "This page simulated what new speed limits, and drivers keeping to them, would do to "
        "deaths and injuries. Its results came from speeds measured in other countries and from "
        "published estimates of how casualties respond to speed. The Spanish crash records carry "
        "no speeds, so none of those links could be estimated or checked here."
    ),
    "distraction": (
        "This page estimated how many deaths a year distraction causes, by combining the share "
        "of fatal crashes in which the police recorded distraction with a crash risk measured "
        "in a driving study in the United States. The repository holds no Spanish data on how "
        "much distraction raises the risk of a crash."
    ),
    "alcohol-drugs": (
        "This page estimated how many deaths a year alcohol and drugs cause, by applying "
        "relative risks from a European study to the share of fatal crashes in which the police "
        "recorded alcohol. The repository holds no Spanish data on how much alcohol or drugs "
        "raise the risk of a crash."
    ),
    "enforcement": (
        "This page ranked enforcement against speeding, drink- and drug-driving and distraction "
        "by the deaths each would avoid, combining the three withdrawn models with evaluations "
        "from other countries. The repository holds no data on the effect of enforcement in "
        "Spain."
    ),
}


# House style for numbers: a typographic minus rather than a hyphen, so a negative figure in a
# table or in a sentence is not mistaken for a range or a dash.
MINUS = "\u2212"


def _minus(text: str) -> str:
    return text.replace("-", MINUS)


def _fmt_int(value: object) -> str:
    return "" if pd.isna(value) else _minus(f"{float(value):,.0f}")


def _fmt_pct(value: object, decimals: int = 1) -> str:
    # Adding 0.0 turns a value that rounds to -0 into 0, so no zero carries a minus sign.
    return (
        ""
        if pd.isna(value)
        else _minus(f"{round(float(value) * 100, decimals) + 0.0:.{decimals}f}%")
    )


def _fmt_dec(value: object, decimals: int = 1) -> str:
    return "" if pd.isna(value) else _minus(f"{round(float(value), decimals) + 0.0:,.{decimals}f}")


def _signed_pct(value: float, decimals: int = 0) -> str:
    """A signed percentage, so a fall reads as −7% and a rise as +7%; zero carries no sign."""
    if round(value * 100, decimals) == 0:
        return f"{0:.{decimals}f}%"
    return _minus(f"{value * 100:+.{decimals}f}%")


def _join(items: list[str]) -> str:
    """'a', 'a and b', 'a, b and c'."""
    if len(items) < 2:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " and " + items[-1]


def _times(value: float) -> str:
    return f"{value:.2f}×"


def esc(text: object) -> str:
    return html.escape(str(text))


def read_table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


def read_captions() -> dict[str, str]:
    with (FIGURES_DIR / "captions.json").open(encoding="utf-8") as handle:
        return json.load(handle)


_SVG_SIZE = re.compile(r'<svg[^>]*?\swidth="([\d.]+)pt"[^>]*?\sheight="([\d.]+)pt"')


_SVG_VIEWBOX = re.compile(r'<svg[^>]*?\sviewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"')


def _svg_dimensions(name: str) -> str:
    """``width`` and ``height`` attributes for the image, so the space is reserved before it loads."""
    path = FIGURES_DIR / f"{name}.svg"
    if not path.exists():
        return ""
    head = path.read_text(encoding="utf-8")[:2000]
    match = _SVG_SIZE.search(head) or _SVG_VIEWBOX.search(head)
    if not match:
        return ""
    return f' width="{float(match.group(1)):.0f}" height="{float(match.group(2)):.0f}"'


# The Spanish titles and terms the pages quote inside English sentences. Organisations, places and
# publication names are proper names, which WCAG 2.1 SC 3.1.2 exempts, so they are not listed here.
SPANISH_RUNS: tuple[str, ...] = (
    "Series históricas del Anuario de Accidentes 2024",
    "Ficheros de microdatos de accidentes con víctimas 2016–2024",
    "Accidentes con víctimas, tablas estadísticas 2014–2024",
    "Kilómetros recorridos estimados a partir de la ITV 2022",
    "Kilómetros anualizados recorridos por el parque móvil 2024",
    "Estadística Continua de Población",
    "Censo de conductores 2014–2025",
    "Informe temático Factor Velocidad",
    "parque circulante",
)


def mark_spanish(text: str) -> str:
    """Mark the Spanish runs of an already escaped English string with ``lang="es"``."""
    for run in SPANISH_RUNS:
        text = text.replace(run, f'<span lang="es">{run}</span>')
    return text


def figure(name: str, alt: str, captions: dict[str, str]) -> str:
    # The image links to its SVG, so a reader on a small screen can open the chart full size.
    return (
        f'<figure><div class="figure-wrap" role="region" tabindex="0" aria-label="{esc(alt)}">'
        f'<a href="figures/{name}.svg"><img src="figures/{name}.svg" alt="{esc(alt)}"'
        f'{_svg_dimensions(name)} loading="lazy"></a></div>'
        f"<figcaption>{mark_spanish(esc(captions.get(name, '')))}</figcaption></figure>"
    )


# A text column whose longest cell is longer than this wraps instead of widening the table.
WRAP_COLUMN_CHARS = 24


def table(
    frame: pd.DataFrame,
    caption: str,
    formats: dict[str, str] | None = None,
    spanish_columns: tuple[str, ...] = (),
) -> str:
    """Render a frame as an HTML table.

    ``formats`` maps column -> 'int' | 'pct' | 'pct0' | 'pct2' | 'dec' | 'dec2' | 'dec4' | 'year'.
    """
    formats = formats or {}
    assert not frame.columns.duplicated().any(), list(frame.columns)
    formatters = {
        "year": lambda v: "" if pd.isna(v) else str(int(v)),
        "int": _fmt_int,
        "pct": _fmt_pct,
        "pct0": lambda v: _fmt_pct(v, 0),
        "pct2": lambda v: _fmt_pct(v, 2),
        "dec": _fmt_dec,
        "dec0": lambda v: _fmt_dec(v, 0),
        "dec2": lambda v: _fmt_dec(v, 2),
        "dec4": lambda v: _fmt_dec(v, 4),
    }
    wrap = {
        column
        for column in frame.columns
        if not formats.get(column)
        and frame[column].map(lambda v: len("" if pd.isna(v) else str(v))).max() > WRAP_COLUMN_CHARS
    }
    rows = []
    for _, row in frame.iterrows():
        cells = []
        for position, column in enumerate(frame.columns):
            value = row[column]
            kind = formats.get(column)
            text = formatters[kind](value) if kind else ("" if pd.isna(value) else str(value))
            content = esc(text)
            if content and column in spanish_columns:
                content = f'<span lang="es">{content}</span>'
            cls = ' class="wrap"' if column in wrap else ""
            if position == 0:
                cells.append(f'<th scope="row"{cls}>{content}</th>')
            else:
                cells.append(f"<td{cls}>{content}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    head = "".join(
        f'<th scope="col"{" class=" + chr(34) + "wrap" + chr(34) if column in wrap else ""}>'
        f"{esc(column)}</th>"
        for column in frame.columns
    )
    return (
        f'<div class="table-wrap" role="region" tabindex="0" aria-label="{esc(caption)}">'
        f"<table><caption>{mark_spanish(esc(caption))}</caption>"
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def downloads(items: list[tuple[str, str]], method: tuple[str, str] | None = None) -> str:
    """The result tables behind a page, as CSV links, and optionally where its method is set out.

    ``method`` is ``(href, label)``, for example ``("data.html#rates", "how rates are built")``.
    """
    links = ", ".join(f'<a href="tables/{name}.csv">{esc(label)}</a>' for name, label in items)
    text = f"Result tables (CSV): {links}."
    if method:
        text += f' Method: <a href="{method[0]}">{esc(method[1])}</a>.'
    return f'<p class="downloads">{text}</p>'


def note(text: str) -> str:
    return f'<div class="note"><p>{text}</p></div>'


def conclusion(text: str) -> str:
    """The flat statement of what the page has established, at the foot of the argument."""
    return f'<div class="conclusion"><p>{text}</p></div>'


def summary(text: str) -> str:
    """The opening paragraph of a page: its principal result, stated plainly."""
    return f'<p class="summary">{text}</p>'


def limitation(text: str) -> str:
    """A short methodological limitation, used only where a page needs one beyond the methodology."""
    return f'<p class="limit"><strong>Limitations.</strong> {text}</p>'


def technical(label: str, body: str) -> str:
    """Technical detail a reader can open: full metrics, specifications, diagnostics."""
    return f'<details class="technical"><summary>{esc(label)}</summary>{body}</details>'


def _nav_list(group: str, pages: tuple[tuple[str, str], ...], slug: str, index: int) -> str:
    current = ' aria-current="page"'
    return "".join(
        f'<li><a href="{s}.html"{current if s == slug else ""}>{esc(name)}</a></li>'
        for s, name in pages
    )


def _nav(slug: str) -> str:
    """The navigation: each section a small label over its links, so a label never reads as a page.

    A group with a parent (the supporting analyses) is drawn as a labelled list inside its parent's.
    """
    children: dict[str, list[tuple[int, str, tuple[tuple[str, str], ...]]]] = {}
    for index, (label, pages) in enumerate(NAV_GROUPS):
        if label in NAV_PARENT:
            children.setdefault(NAV_PARENT[label], []).append((index, label, pages))
    groups = []
    for index, (label, pages) in enumerate(NAV_GROUPS):
        if label in NAV_PARENT:
            continue
        links = _nav_list(label, pages, slug, index)
        for child_index, child, child_pages in children.get(label, []):
            links += (
                f'<li class="navsub"><span class="navlabel" id="nav-{child_index}">'
                f"{esc(child)}</span>"
                f'<ul aria-labelledby="nav-{child_index}">'
                f"{_nav_list(child, child_pages, slug, child_index)}</ul></li>"
            )
        if label == OVERVIEW:
            groups.append(f'<div class="navgroup"><ul>{links}</ul></div>')
            continue
        wide = " navwide" if label in children else ""
        groups.append(
            f'<div class="navgroup{wide}"><span class="navlabel" id="nav-{index}">{esc(label)}'
            f'</span><ul aria-labelledby="nav-{index}">{links}</ul></div>'
        )
    return f'<nav aria-label="Sections">{"".join(groups)}</nav>'


def _place(slug: str) -> tuple[str, str]:
    """Where a page sits: its section above the title, and the pages either side in reading order."""
    titles = dict(ALL_PAGES)
    if slug not in READING_ORDER or slug == "index":
        return "", ""
    group = next(label for label, pages in NAV_GROUPS if slug in dict(pages))
    eyebrow = f'<p class="eyebrow">{esc(EYEBROWS[group])}</p>'
    position = READING_ORDER.index(slug)
    links = []
    if position > 0:
        before = READING_ORDER[position - 1]
        links.append(f'<a href="{before}.html" rel="prev">← {esc(titles[before])}</a>')
    if position < len(READING_ORDER) - 1:
        after = READING_ORDER[position + 1]
        links.append(f'<a href="{after}.html" rel="next">{esc(titles[after])} →</a>')
    return eyebrow, f'<nav class="pager" aria-label="Reading order">{"".join(links)}</nav>'


SITE_TITLE = "Road safety in Spain"


def render_page(slug: str, title: str, lead: str, body: str, head: str = "") -> str:
    eyebrow, pager = _place(slug)
    page_title = SITE_TITLE if slug == "index" else esc(title) + " · " + SITE_TITLE
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<meta name="description" content="{esc(lead)}">
<link rel="stylesheet" href="style.css">{head}
</head>
<body>
<header>
<div class="masthead">
<a href="index.html">{SITE_TITLE}</a>
<span class="strap">An independent analysis of official crash data</span>
</div>
{_nav(slug)}
</header>
<main>
{eyebrow}<h1>{esc(title)}</h1>
<p class="lead">{esc(lead)}</p>
{body}
{pager}</main>
<footer>
<p>{SITE_TITLE}, an independent analysis by <a href="{PROFILE_URL}">Russell Howard (RAHV-FB)</a>.
Data from the Dirección General de Tráfico, INE, the Ministerio de Transportes, CORES, the Servei
Català de Trànsit and the Ajuntament de Barcelona. All results are computed from the published
files by the code in the repository.</p>
<p><a href="sources.html">Data sources</a> · <a href="data.html">Methodology</a> ·
<a href="{REPO_URL}">Repository</a></p>
</footer>
</body>
</html>
"""


def _ratio_ci(ratio: float, low: float, high: float) -> str:
    return f"{ratio:.2f}× ({low:.2f}–{high:.2f})"


def _change(ratio: float, decimals: int = 1) -> str:
    """A ratio to a base as a signed percentage change: 1.035 reads +3.5%."""
    return _signed_pct(float(ratio) - 1, decimals)


def _ordinal(value: int) -> str:
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth"}
    return words.get(value, f"{value}th")
