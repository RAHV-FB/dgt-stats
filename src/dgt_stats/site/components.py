"""The furniture every page shares: navigation, number formats, tables, figures, the page frame."""

from __future__ import annotations

import html
import json
import re

import pandas as pd

from dgt_stats.paths import FIGURES_DIR, TABLES_DIR
from dgt_stats.risk_trends import BASE_YEAR
from dgt_stats.site.script import CONTENT_SECURITY_POLICY, JS_FLAG

REPO_URL = "https://github.com/RAHV-FB/dgt-stats"


PROFILE_URL = "https://github.com/RAHV-FB"


DOCS_URL = f"{REPO_URL}/blob/main/docs"


# The navigation follows the questions a reader brings: how deaths have changed over time, which
# drivers, vehicles and recorded circumstances go with crashes and deaths, how deadly a crash is
# once it has happened (in Spain's records, in Catalonia's and Barcelona's, and in the model built
# on Catalonia's), and where the data and methods come from. The home page lists the same groups.
OVERVIEW = "Overview"
OVER_TIME = "Over time"
WHO = "Drivers, vehicles and factors"
SEVERITY = "Crash severity"
METHODS = "Data and methods"
NAV_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (OVERVIEW, (("index", "Overview"),)),
    (
        OVER_TIME,
        (
            ("long-run", "Long-run trends"),
            ("trends", f"Since {BASE_YEAR}"),
            ("seasons", "Seasons"),
            ("policy", "The 2006 points licence"),
        ),
    ),
    (
        WHO,
        (
            ("drivers", "Drivers"),
            ("vehicles", "Vehicles"),
            ("speed", "Speed"),
            ("factors", "Recorded factors"),
        ),
    ),
    (
        SEVERITY,
        (
            ("severity", "Crash circumstances in Spain"),
            ("catalonia", "Catalonia"),
            ("barcelona", "Barcelona"),
            ("severity-models", "Severity model and calculator"),
            ("validation", "External validation"),
        ),
    ),
    (METHODS, (("sources", "Data sources and scope"), ("data", "Methodology"))),
)
# The line above a page's title: the group it belongs to.
EYEBROWS = {group: group for group, _ in NAV_GROUPS}
# What each page answers, one line each, for the home page's list of pages.
PAGE_QUESTIONS = {
    "long-run": "How road deaths have changed since 1993, against vehicles, fuel sold and "
    "kilometres driven.",
    "trends": f"Deaths, hospital admissions and injury crashes in 2024 against {BASE_YEAR}.",
    "seasons": "Which months are deadliest, and how the 2020 lockdown changed them.",
    "policy": "Whether the points-based licence of July 2006 changed monthly deaths.",
    "drivers": "How often drivers of each age and sex are in crashes per kilometre, and how "
    "often a crash kills them.",
    "vehicles": "Crashes and deaths by type of vehicle, per vehicle and per kilometre.",
    "speed": "Crashes in which the police recorded inappropriate speed, and their deaths.",
    "factors": "The other circumstances the police record, and how their shares have moved.",
    "severity": "Which recorded circumstances go with a death in Spain's injury crashes.",
    "catalonia": "Crashes with a death or serious injury in Catalonia, 2010–2023.",
    "barcelona": "Every crash the Guàrdia Urbana attended in Barcelona in 2025.",
    "severity-models": "A model of which severe crashes in Catalonia were fatal, and a "
    "calculator to try it.",
    "validation": "How the Catalan models held up on other years, places and records.",
    "sources": "Where every figure comes from, what it covers and what it cannot show.",
    "data": "How the results are produced, the checks they pass and the assumptions tested.",
}


# The two analyses that support the national argument rather than answer one of its questions.
SUPPORTING_SLUGS = ("severity", "policy")
PAGES: tuple[tuple[str, str], ...] = tuple(
    page for _, pages in NAV_GROUPS for page in pages if page[0] not in SUPPORTING_SLUGS
)
SUPPORTING_PAGES: tuple[tuple[str, str], ...] = tuple(
    page for _, pages in NAV_GROUPS for page in pages if page[0] in SUPPORTING_SLUGS
)
SPAIN_PAGES: tuple[tuple[str, str], ...] = tuple(
    page
    for group, pages in NAV_GROUPS
    if group in (OVER_TIME, WHO)
    for page in pages
    if page[0] not in SUPPORTING_SLUGS
)


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
# A withdrawn page whose reason differs from ``WITHDRAWN_REASON``. The lead states the reason; the
# notice's body says only what the page published and where the data-only work is.
WITHDRAWN_LEADS = {
    "forecast": (
        "This analysis was withdrawn because the model forecast a year's deaths less accurately "
        "than last year's count."
    ),
}
# What each withdrawn page was, as its notice names it.
WITHDRAWN_TITLES = {
    "forecast": "Monthly deaths forecast",
    "simulator": "Speed-limit simulator",
    "distraction": "Deaths attributed to distraction",
    "alcohol-drugs": "Deaths attributed to alcohol and drugs",
    "enforcement": "Ranking of enforcement measures",
}
# What each withdrawn page published. The reason is in its lead and is not repeated here.
WITHDRAWN_PAGES = {
    "forecast": (
        "This page published a model of Spain's monthly road deaths and, from its forecast "
        "errors, the smallest change in a year's deaths that the counts could reveal. Both are "
        "withdrawn."
    ),
    "simulator": (
        "This page simulated what new speed limits, and drivers keeping to them, would do to "
        "deaths and injuries. It started from free-flow speeds measured in Spain for the EU "
        "Baseline project, and took from studies in other countries both how speeds follow a "
        "new limit and how casualties respond to speed."
    ),
    "distraction": (
        "This page estimated how many deaths a year distraction causes, by combining the share "
        "of fatal crashes in which the police recorded distraction with a crash risk measured "
        "in a driving study in the United States."
    ),
    "alcohol-drugs": (
        "This page estimated how many deaths a year alcohol and drugs cause, by applying "
        "relative risks from a European study to the share of fatal crashes in which the police "
        "recorded alcohol."
    ),
    "enforcement": (
        "This page ranked enforcement against speeding, drink- and drug-driving and distraction "
        "by the deaths each would avoid, combining the three withdrawn models with published "
        "evaluations of enforcement, all from other countries but one study of Barcelona's "
        "fixed speed cameras."
    ),
}


def withdrawn_detail(slug: str) -> str:
    """A further paragraph for a withdrawn page whose reason rests on a result table (HTML)."""
    if slug != "forecast":
        return ""
    review = read_table("review_forecast")
    held_out = review[review.set.eq("holdout")]
    model = held_out[held_out.method.str.contains("published model")].sort_values("window")
    naive = held_out[held_out.method.str.startswith("naive")]
    model_error, naive_error = float(model.rmse.iloc[0]), float(naive.rmse.iloc[0])
    if not (len(naive) == 1 and model_error > naive_error):
        raise ValueError("forecast notice: the model no longer loses to last year's count")
    return (
        "<p>The model predicted each month's deaths from the month of the year, a linear trend, "
        "the number of Fridays, Saturdays and Sundays, and the road fuel sold in that same "
        "month. Fuel sales are known only once the month is over, so the model could not "
        "forecast ahead: it estimated the deaths that a month's traffic would have brought. "
        "Even so, in the ordinary years held back from its choice its error in a year's deaths "
        f"was {_fmt_pct(model_error)}, against {_fmt_pct(naive_error)} for repeating the same "
        "months of the year before. The re-evaluation is in the "
        f'<a href="{DOCS_URL}/research/ML_MODEL_REVIEW.md">model review</a>.</p>'
    )


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


_TITLES: dict[str, str] = {}


def read_titles() -> dict[str, str]:
    """The title printed above each figure (``reports/figures/titles.json``)."""
    if not _TITLES:
        path = FIGURES_DIR / "titles.json"
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                _TITLES.update(json.load(handle))
    return _TITLES


_SVG_SIZE = re.compile(r'<svg[^>]*?\swidth="([\d.]+)pt"[^>]*?\sheight="([\d.]+)pt"')


_SVG_VIEWBOX = re.compile(r'<svg[^>]*?\sviewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"')


def _svg_size(name: str) -> tuple[float, float] | None:
    """A chart's own width and height, in points, from its SVG."""
    path = FIGURES_DIR / f"{name}.svg"
    if not path.exists():
        return None
    head = path.read_text(encoding="utf-8")[:2000]
    match = _SVG_SIZE.search(head) or _SVG_VIEWBOX.search(head)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


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


# Charts are shown at one fixed multiple of their own size, so that their text is the same size on
# every chart, and never wider than the column. They shrink with the column down to a smaller
# multiple that keeps their text near 11px, and below that scroll sideways inside the figure
# rather than shrinking further; a phone shows them at that multiple.
FIGURE_SCALE = 1.45
SMALL_SCALE = 1.2


def _split_source(caption: str) -> tuple[str, str]:
    """A caption's description and its 'Source: …' line."""
    marker = " Source: "
    if marker in caption:
        shown, source = caption.split(marker, 1)
        return shown, "Source: " + source
    return caption, ""


def figure(name: str, alt: str, captions: dict[str, str], title: str | None = None) -> str:
    """A figure in three parts: a title stating what is shown, the chart, and a caption giving
    the denominator, period, interval and source. The chart links to its SVG at full size."""
    heading = title or read_titles().get(name, "")
    shown, source = _split_source(captions.get(name, ""))
    size = _svg_size(name)
    dims = ""
    if size:
        width, height = size
        dims = (
            f' width="{width:.0f}" height="{height:.0f}"'
            f' style="--w: {width * FIGURE_SCALE:.0f}px; --w-small: {width * SMALL_SCALE:.0f}px"'
        )
    title_html = (
        f'<p class="figure-title" id="figure-{name}">{mark_spanish(esc(heading))}</p>'
        if heading
        else ""
    )
    labelled = f' aria-labelledby="figure-{name}"' if heading else ""
    source_html = f'<p class="figure-source">{mark_spanish(esc(source))}</p>' if source else ""
    return (
        f"<figure{labelled}>{title_html}"
        '<p class="figure-tools">Scroll sideways to see the whole chart, or '
        f'<a href="figures/{name}.svg">open it at full size</a>.</p>'
        f'<div class="figure-media" role="region" tabindex="0" aria-label="Chart: {esc(heading or alt)}">'
        f'<a href="figures/{name}.svg"><img src="figures/{name}.svg" alt="{esc(alt)}"{dims}'
        ' loading="lazy" decoding="async"></a></div>'
        f"<figcaption><p>{mark_spanish(esc(shown))}</p>{source_html}</figcaption></figure>"
    )


# A text column whose longest cell is longer than this wraps instead of widening the table.
WRAP_COLUMN_CHARS = 24

# A cell that reads as a number: a value, a range or a value with its interval in brackets, with
# an optional sign, percentage or multiplication sign ("1,234", "−7%", "2.02–6.75×",
# "−6.0% to +10.1%", "0.79 (0.76–0.82)", "1 (reference)").
_NUMBER = re.compile(
    r"[−\-+]?\d[\d.,]*\s?[%×]?(?:\s?(?:[–\-]|to)\s?[−\-+]?\d[\d.,]*\s?[%×]?)?(?:\s*\(.*\))?"
)


def _numeric(values: pd.Series) -> bool:
    cells = [str(v).strip() for v in values if not pd.isna(v) and str(v).strip()]
    return bool(cells) and sum(bool(_NUMBER.fullmatch(c)) for c in cells) >= 0.8 * len(cells)


def _caption_parts(caption: str) -> tuple[str, str]:
    """A table caption's first sentence, shown as the table's title, and the rest as its note."""
    match = re.match(r"(.+?[.:])\s+(?=[A-Z0-9“\"(])(.+)$", caption, re.S)
    if not match:
        return caption, ""
    return match.group(1), match.group(2)


def table(
    frame: pd.DataFrame,
    caption: str,
    formats: dict[str, str] | None = None,
    spanish_columns: tuple[str, ...] = (),
    reference_rows: tuple[str, ...] = (),
) -> str:
    """Render a frame as an HTML table.

    ``formats`` maps column -> 'int' | 'pct' | 'pct0' | 'pct2' | 'dec' | 'dec2' | 'dec4' | 'year'.
    Numeric columns are right-aligned and the others left-aligned. A row whose first cell is in
    ``reference_rows``, or with a cell marked '(reference)', is lightly shaded as the row the
    others are compared with. The caption's first sentence is set as the table's title.
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
    texts = pd.DataFrame(
        {
            column: [
                formatters[formats[column]](v)
                if formats.get(column)
                else ("" if pd.isna(v) else str(v))
                for v in frame[column]
            ]
            for column in frame.columns
        }
    )
    wrap = {
        column
        for column in frame.columns
        if not formats.get(column) and texts[column].map(len).max() > WRAP_COLUMN_CHARS
    }
    numeric = {
        column
        for position, column in enumerate(frame.columns)
        if position > 0 and (formats.get(column) or _numeric(texts[column]))
    }

    def classes(column: str) -> str:
        names = [n for n, on in (("num", column in numeric), ("wrap", column in wrap)) if on]
        return f' class="{" ".join(names)}"' if names else ""

    # A table of prose alone is set as a list of records on a small screen, each cell under its
    # column's name, rather than scrolling sideways.
    stacked = not numeric and len(frame.columns) >= 3
    rows = []
    for index in range(len(texts)):
        cells = []
        values = texts.iloc[index]
        reference = str(values.iloc[0]) in reference_rows or any(
            "(reference)" in str(v) for v in values
        )
        for position, column in enumerate(frame.columns):
            content = esc(values[column])
            if content and column in spanish_columns:
                content = f'<span lang="es">{content}</span>'
            if position == 0:
                # A row shaded as the reference says so in words too, for screen readers.
                if reference and not any("(reference)" in str(v) for v in values):
                    content += '<span class="visually-hidden"> (reference)</span>'
                cells.append(f'<th scope="row"{classes(column)}>{content}</th>')
            else:
                label = f' data-label="{esc(column)}"' if stacked else ""
                cells.append(f"<td{classes(column)}{label}>{content}</td>")
        row_class = ' class="is-reference"' if reference else ""
        rows.append(f"<tr{row_class}>" + "".join(cells) + "</tr>")
    head = "".join(
        f'<th scope="col"{classes(column)}>{esc(column)}</th>' for column in frame.columns
    )
    # The title and note are set above the table, outside the box that scrolls sideways, so they
    # are never cut off on a small screen; the caption carries the same words for screen readers.
    title, note = _caption_parts(caption)
    title = title.rstrip(".:")
    shown = f'<p class="table-title" aria-hidden="true">{mark_spanish(esc(title))}</p>'
    if note:
        shown += f'<p class="table-note" aria-hidden="true">{mark_spanish(esc(note))}</p>'
    spoken = esc(title) + (f". {esc(note)}" if note else "")
    table_class = ' class="stack"' if stacked else ""
    return (
        f'<div class="table-block">{shown}'
        '<p class="table-tools" hidden>Scroll sideways to see the whole table.</p>'
        f'<div class="table-wrap" role="region" tabindex="0" aria-label="{esc(title)}">'
        f'<table{table_class}><caption class="visually-hidden">{spoken}</caption>'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div></div>"
    )


SOURCE_REGISTER = f"{DOCS_URL}/data_sources.md"


def downloads(items: list[tuple[str, str]], method: tuple[str, str] | None = None) -> str:
    """The page's closing 'Data and method' block: its result tables as CSV files, where its
    method is set out, and where its sources are documented.

    ``method`` is ``(href, label)``, for example ``("data.html#rates", "how rates are built")``.
    """
    links = "".join(
        f'<li><a href="tables/{name}.csv">{esc(label[:1].upper() + label[1:])}</a></li>'
        for name, label in items
    )
    many = ' class="many"' if len(items) > 5 else ""
    rows = f"<dt>Result tables (CSV)</dt><dd><ul{many}>{links}</ul></dd>"
    if method:
        label = method[1][:1].upper() + method[1][1:]
        rows += f'<dt>Method</dt><dd><a href="{method[0]}">{esc(label)}</a></dd>'
    rows += (
        '<dt>Source documentation</dt><dd><a href="sources.html">Data sources and scope</a>'
        f' · <a href="{SOURCE_REGISTER}">Source register</a></dd>'
    )
    return (
        '<section class="data-method" aria-labelledby="data-and-method">'
        '<h2 id="data-and-method">Data and method</h2>'
        f"<dl>{rows}</dl></section>"
    )


def summary(text: str) -> str:
    """The opening paragraph of a page: its principal result, stated plainly."""
    return f'<p class="summary">{text}</p>'


def key_result(value: str, text: str) -> str:
    """One headline number with a sentence saying exactly what it measures. Used sparingly."""
    return (
        f'<div class="key-result"><p class="key-value">{value}</p>'
        f'<p class="key-text">{text}</p></div>'
    )


def compare(items: list[tuple[str, str]], note: str = "") -> str:
    """Two numbers side by side, each with what it measures, and a sentence reading them."""
    cells = "".join(
        f'<div class="compare-item"><p class="compare-value">{value}</p>'
        f'<p class="compare-label">{label}</p></div>'
        for value, label in items
    )
    note_html = f'<p class="compare-note">{note}</p>' if note else ""
    return f'<div class="compare"><div class="compare-items">{cells}</div>{note_html}</div>'


def facts(rows: list[tuple[str, str]], label: str) -> str:
    """A short definition list that can be read in a few seconds (a model's unit, outcome,
    benchmark, score and decision)."""
    items = "".join(f"<div><dt>{esc(term)}</dt><dd>{value}</dd></div>" for term, value in rows)
    return f'<dl class="facts" aria-label="{esc(label)}">{items}</dl>'


def decision_label(text: str) -> str:
    """A model's decision, set after its section heading as a quiet label."""
    return (
        '<span class="decision-label"><span class="visually-hidden">Decision: </span>'
        f"<span>{esc(text)}</span></span>"
    )


def evidence_note(text: str) -> str:
    """A note at the head of a section whose evidence is weaker than the page's main result."""
    return f'<div class="evidence-note"><p>{text}</p></div>'


def limitation(text: str) -> str:
    """A short methodological limitation, kept next to the results it qualifies."""
    return (
        '<aside class="limit" aria-label="Limitations">'
        f'<p><span class="limit-label">Limitations</span>{text}</p></aside>'
    )


def technical(label: str, body: str) -> str:
    """Secondary detail a reader can open: full counts, specifications, diagnostics. The label
    says exactly what is inside."""
    return (
        f'<details class="technical"><summary>{esc(label)}</summary>'
        f'<div class="technical-body">{body}</div></details>'
    )


def _slug(text: str) -> str:
    plain = re.sub(r"<[^>]+>", "", text)
    plain = html.unescape(plain).lower()
    plain = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")
    return plain[:60].rstrip("-") or "section"


# A page gets a contents list when it has at least this many sections and this much text.
TOC_MIN_SECTIONS = 3
TOC_MIN_CHARS = 6000


# A model's decision set after its section heading; the contents list leaves it out.
DECISION_LABEL = re.compile(r'<span class="decision-label">.*?</span></span>', re.S)


def _sections(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Give every section heading of a page an id, and list the headings for its contents.

    The closing 'Data and method' block is not a section of the argument and is left out.
    """
    seen: set[str] = set()
    entries: list[tuple[str, str]] = []

    def name(match: re.Match[str]) -> str:
        attributes, text = match.group(1), match.group(2)
        plain = DECISION_LABEL.sub("", text).strip()
        found = re.search(r'id="([^"]+)"', attributes)
        anchor = found.group(1) if found else _slug(plain)
        base, number = anchor, 2
        while anchor in seen:
            anchor, number = f"{base}-{number}", number + 1
        seen.add(anchor)
        if anchor != "data-and-method":
            entries.append((anchor, plain))
        if found:
            return match.group(0)
        return f'<h2 id="{anchor}"{attributes}>{text}</h2>'

    body = re.sub(r"<h2([^>]*)>(.*?)</h2>", name, body, flags=re.S)
    return body, entries


# The switch between the light and dark themes: a half-filled circle, named for screen readers
# and pressed while the dark theme is on. Hidden until the script can work it.
THEME_TOGGLE = (
    '<button class="theme-toggle" type="button" aria-pressed="false" title="Dark mode" hidden>'
    '<span class="visually-hidden">Dark mode</span>'
    '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    '<circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" stroke-width="1.5"/>'
    '<path d="M8 1.75a6.25 6.25 0 0 1 0 12.5z" fill="currentColor"/></svg></button>'
)


def _number(body: str) -> str:
    """Number a page's figures and tables in reading order, as a printed paper does.

    The number goes before each title; a table's hidden caption, which is what a screen reader
    announces for it, carries the same number.
    """
    counts = {"figure": 0, "table": 0}

    def figure_title(match: re.Match[str]) -> str:
        counts["figure"] += 1
        return f'{match.group(0)}<span class="figure-label">Figure {counts["figure"]}.</span> '

    def table_block(match: re.Match[str]) -> str:
        counts["table"] += 1
        label = f"Table {counts['table']}."
        block = match.group(0).replace(
            '<p class="table-title" aria-hidden="true">',
            f'<p class="table-title" aria-hidden="true"><span class="table-label">{label}</span> ',
            1,
        )
        return block.replace(
            '<caption class="visually-hidden">', f'<caption class="visually-hidden">{label} ', 1
        )

    pattern = re.compile(
        r'<p class="figure-title" id="[^"]+">|<div class="table-block">.*?</table></div></div>',
        re.S,
    )
    return pattern.sub(
        lambda m: figure_title(m) if m.group(0).startswith("<p") else table_block(m), body
    )


def _block_end(html_text: str, start: int) -> int:
    """The position just after the <div> that opens at ``start`` and everything nested in it."""
    depth = 0
    for match in re.finditer(r"<(/?)div\b", html_text[start:]):
        depth += -1 if match.group(1) else 1
        if depth == 0:
            return html_text.index(">", start + match.start()) + 1
    raise ValueError("unclosed <div>")


def _toc_lists(entries: list[tuple[str, str]]) -> tuple[str, str]:
    items = "".join(f'<li><a href="#{anchor}">{text}</a></li>' for anchor, text in entries)
    rail = (
        '<aside class="toc-rail"><nav class="toc" aria-label="On this page">'
        f'<p class="toc-title">On this page</p><ol>{items}</ol></nav></aside>'
    )
    inline = (
        f'<details class="toc-inline"><summary>On this page</summary><ol>{items}</ol></details>'
    )
    return rail, inline


def _nav(slug: str) -> str:
    """The site navigation: each section a menu of its pages, the current one marked.

    On a wide screen each section is a button opening its list; on a small screen the whole list
    is shown under a 'Menu' button, sections as labels. Without scripting every list is reachable
    from the keyboard and the small-screen list is shown open.
    """
    groups = []
    for label, pages in NAV_GROUPS:
        if label == OVERVIEW:
            current = ' aria-current="page"' if slug == "index" else ""
            groups.append(
                f'<li class="nav-group"><a class="nav-top" href="index.html"{current}>'
                f"{esc(pages[0][1])}</a></li>"
            )
            continue
        key = _slug(label)
        is_current = slug in dict(pages)
        links = "".join(
            f'<li><a href="{s}.html"{" aria-current=" + chr(34) + "page" + chr(34) if s == slug else ""}>'
            f"{esc(name)}</a></li>"
            for s, name in pages
        )
        marker = '<span class="visually-hidden"> (current section)</span>' if is_current else ""
        groups.append(
            f'<li class="nav-group{" is-current" if is_current else ""}">'
            f'<button class="nav-trigger" type="button" aria-expanded="false" '
            f'aria-controls="menu-{key}">{esc(label)}{marker}</button>'
            f'<span class="nav-label" id="label-{key}">{esc(label)}</span>'
            f'<ul class="nav-menu" id="menu-{key}" aria-labelledby="label-{key}">{links}</ul></li>'
        )
    return f'<nav aria-label="Sections"><ul class="nav-groups">{"".join(groups)}</ul></nav>'


def _place(slug: str) -> tuple[str, str]:
    """Where a page sits: its section above the title, and the pages either side in reading order."""
    titles = dict(ALL_PAGES)
    if slug in WITHDRAWN_PAGES:
        return '<p class="eyebrow">Withdrawn analysis</p>', ""
    if slug not in READING_ORDER or slug == "index":
        return "", ""
    group = next(label for label, pages in NAV_GROUPS if slug in dict(pages))
    eyebrow = f'<p class="eyebrow">{esc(EYEBROWS[group])}</p>'
    position = READING_ORDER.index(slug)
    links = []
    if position > 0:
        before = READING_ORDER[position - 1]
        links.append(
            f'<a href="{before}.html" rel="prev"><span class="pager-label">Previous</span>'
            f'<span class="pager-title">{esc(titles[before])}</span></a>'
        )
    if position < len(READING_ORDER) - 1:
        after = READING_ORDER[position + 1]
        links.append(
            f'<a href="{after}.html" rel="next"><span class="pager-label">Next</span>'
            f'<span class="pager-title">{esc(titles[after])}</span></a>'
        )
    return eyebrow, f'<nav class="pager" aria-label="Reading order">{"".join(links)}</nav>'


SITE_TITLE = "Road safety in Spain"


def render_page(
    slug: str, title: str, lead: str, body: str, head: str = "", scope: str = ""
) -> str:
    """A whole page: the site header and navigation, the page's opening (section, title, one
    sentence and, for a regional page, its source and scope), its argument with a contents list
    when it is long, the reading-order links and the footer."""
    eyebrow, pager = _place(slug)
    page_title = SITE_TITLE if slug == "index" else esc(title) + " · " + SITE_TITLE
    body, entries = _sections(_number(body))
    visible = len(re.sub(r"<[^>]+>", "", body))
    rail = ""
    if len(entries) >= TOC_MIN_SECTIONS and visible >= TOC_MIN_CHARS:
        rail, inline = _toc_lists(entries)
        opening = re.search(r'<p class="summary">.*?</p>', body, re.S)
        cut = opening.end() if opening else 0
        # A headline number that follows the summary stays with it, before the contents.
        if re.match(r'<div class="(compare|key-result)">', body[cut:]):
            cut = _block_end(body, cut)
        body = body[:cut] + inline + body[cut:]
    scope_html = f'<p class="scope">{scope}</p>' if scope else ""
    body_class = ' class="home"' if slug == "index" else ""
    page_class = "page has-toc" if rail else "page"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta http-equiv="Content-Security-Policy" content="{CONTENT_SECURITY_POLICY}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{page_title}</title>
<meta name="description" content="{esc(lead)}">
<link rel="preload" href="fonts/NunitoSans.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="style.css">
{JS_FLAG}
<script src="site.js" defer></script>{head}
</head>
<body{body_class}>
<a class="skip-link" href="#content">Skip to content</a>
<header class="site-header">
<div class="site-header-inner">
<a class="site-title" href="index.html">{SITE_TITLE}</a>
<button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav" hidden>Menu</button>
<div class="site-nav" id="site-nav">
{_nav(slug)}
</div>
{THEME_TOGGLE}
</div>
</header>
<div class="{page_class}">
<main>
<header class="page-header" id="content">
{eyebrow}<h1>{esc(title)}</h1>
<p class="lead">{esc(lead)}</p>{scope_html}
</header>
{body}
{pager}</main>{rail}
</div>
<footer class="site-footer">
<div class="site-footer-inner">
<p>{SITE_TITLE}, an independent analysis by <a href="{PROFILE_URL}">Russell Howard (RAHV-FB)</a>.
Data from the Dirección General de Tráfico, INE, the Ministerio de Transportes, CORES, the Servei
Català de Trànsit, the Ajuntament de Barcelona, the Autoritat del Transport Metropolità (EMEF) and
the Consorcio Regional de Transportes de Madrid (<a href="https://www.crtm.es">Powered by CRTM</a>).
All results are computed from the published files by the code in the repository.</p>
<p><a href="sources.html">Data sources</a> · <a href="data.html">Methodology</a> ·
<a href="data.html#reuse">Reuse and licences</a> ·
<a href="{REPO_URL}">Repository</a></p>
</div>
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
