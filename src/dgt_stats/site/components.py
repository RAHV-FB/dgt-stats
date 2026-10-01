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


PAGES: tuple[tuple[str, str], ...] = (
    ("index", "Overview"),
    ("trends", "2019–2024"),
    ("long-run", "Long run"),
    ("seasons", "Seasons"),
    ("drivers", "Age and sex"),
    ("vehicles", "Vehicles"),
    ("speed", "Speed"),
    ("factors", "Factors"),
    ("simulator", "Simulator"),
    ("data", "Data"),
)


# Careful analyses outside the central question, linked from a second, quieter row.
SUPPORTING_PAGES: tuple[tuple[str, str], ...] = (
    ("severity", "Severity model"),
    ("policy", "The 2006 break"),
)


ALL_PAGES = PAGES + SUPPORTING_PAGES


SUPPORTING_NOTES = {
    "severity": (
        "<strong>Supporting analysis.</strong> This model explains the outcome of a crash from "
        "where, when and how it happened. It is kept because it is careful and because it shows "
        "which recorded circumstances go with a fatal outcome, but a multivariate model of crash "
        "causation is not "
        "what these data are best at: they have no driver, vehicle or speed records. The central "
        'question of the site is on the <a href="index.html">overview</a>.'
    ),
    "policy": (
        "<strong>Supporting analysis.</strong> A dated policy change is the only kind of "
        "intervention the monthly series can test, and this page shows how weak even that test "
        "is: the headline effect did not survive its falsification checks. The site makes no "
        "causal claim about policies or campaigns. For what the pandemic and traffic did to the "
        'same series, see the <a href="long-run.html">long-run page</a>.'
    ),
}


# Pages that existed under another name, kept as pointers so old links still arrive somewhere.
MOVED_PAGES = {"older-drivers": "drivers", "context": "long-run"}


# House style for numbers: a typographic minus rather than a hyphen, so a negative figure in a
# table or in a sentence is not mistaken for a range or a dash.
MINUS = "\u2212"


def _minus(text: str) -> str:
    return text.replace("-", MINUS)


def _fmt_int(value: object) -> str:
    return "" if pd.isna(value) else _minus(f"{float(value):,.0f}")


def _fmt_pct(value: object, decimals: int = 1) -> str:
    return "" if pd.isna(value) else _minus(f"{float(value) * 100:.{decimals}f}%")


def _fmt_dec(value: object, decimals: int = 1) -> str:
    return "" if pd.isna(value) else _minus(f"{float(value):,.{decimals}f}")


def _signed_pct(value: float, decimals: int = 0) -> str:
    """A signed percentage, so a fall reads as −7% and a rise as +7%; zero carries no sign."""
    if round(value * 100, decimals) == 0:
        return f"{0:.{decimals}f}%"
    return _minus(f"{value * 100:+.{decimals}f}%")


def _chance(power: float) -> str:
    """A chance of detection in words: '45% of the time', or 'almost every time' from 99%."""
    power = float(power)
    return "almost every time" if power >= 0.99 else f"{_fmt_pct(power, 0)} of the time"


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
    return (
        f'<figure><div class="figure-wrap" role="region" tabindex="0" aria-label="{esc(alt)}">'
        f'<img src="figures/{name}.svg" alt="{esc(alt)}"'
        f'{_svg_dimensions(name)} loading="lazy"></div>'
        f"<figcaption>{mark_spanish(esc(captions.get(name, '')))}</figcaption></figure>"
    )


# A text column whose longest cell is longer than this wraps instead of scrolling.
WRAP_COLUMN_CHARS = 40


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


def downloads(items: list[tuple[str, str]]) -> str:
    """A one-line list of the full result tables behind a section, as CSV links."""
    links = ", ".join(f'<a href="tables/{name}.csv">{esc(label)}</a>' for name, label in items)
    return f'<p class="downloads">Full results: {links} (CSV).</p>'


def key_figures(items: list[tuple[str, str, str]]) -> str:
    """The indicator strip at the head of a page: label, figure, one line of gloss."""
    cells = "".join(
        f'<div class="keyfig"><div class="label">{esc(label)}</div>'
        f'<div class="value">{esc(value)}</div><div class="gloss">{esc(gloss)}</div></div>'
        for label, value, gloss in items
    )
    return f'<div class="figures">{cells}</div>'


def finding(number: int, href: str, heading: str, text: str, method: str) -> str:
    """One numbered finding on the front page."""
    return (
        f'<div class="finding"><h3><span class="num">Finding {number}</span>'
        f'<a href="{esc(href)}">{esc(heading)}</a></h3>'
        f'<p>{esc(text)}</p><p class="method">{esc(method)}</p></div>'
    )


def note(text: str) -> str:
    return f'<div class="note"><p>{text}</p></div>'


def conclusion(text: str) -> str:
    """The flat statement of what the page has established, at the foot of the argument."""
    return f'<div class="conclusion"><p>{text}</p></div>'


def limits(text: str) -> str:
    return f'<p class="limit"><strong>Limits.</strong> {text}</p>'


def render_page(slug: str, title: str, lead: str, body: str, head: str = "") -> str:
    def items(pages: tuple[tuple[str, str], ...]) -> str:
        out = ""
        for s, name in pages:
            current = ' aria-current="page"' if s == slug else ""
            out += f'<li><a href="{s}.html"{current}>{esc(name)}</a></li>'
        return out

    nav_items = items(PAGES)
    supporting_items = "<li>Supporting analyses</li>" + items(SUPPORTING_PAGES)
    page_title = (
        "Road safety in Spain · measuring risk, not counting crashes"
        if slug == "index"
        else esc(title) + " · Road safety in Spain"
    )
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
<a href="index.html">Road safety in Spain</a>
<span class="strap">Measuring risk, not counting crashes</span>
</div>
<nav aria-label="Sections"><ul>{nav_items}</ul><ul class="supporting">{supporting_items}</ul></nav>
</header>
<main>
<h1>{esc(title)}</h1>
<p class="lead">{esc(lead)}</p>
{body}
</main>
<footer>
<p>An independent analysis by <a href="{PROFILE_URL}">RAHV-FB</a> (Russell Howard) from Dirección
General de Tráfico open data, INE resident population and the Ministerio de Transportes and CORES
traffic series. Sources, definitions and checks are on the <a href="data.html">data page</a>; every
number is regenerated from the raw files by the code in the
<a href="{REPO_URL}">repository</a>.</p>
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
