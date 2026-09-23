"""Static site builder: plain HTML and one CSS file rendered from the result tables and figures.

No template engine and no JavaScript. The site answers one question, what changes when road risk
is measured rather than counted, in seven analysis pages (2019–2024, the long run, seasons, age
and sex, vehicles, speed, other factors), an overview and a data page, with two supporting
analyses (the severity model and the 2006 break) kept outside the main navigation. Every sentence
that carries a number computes it from a committed result table at build time, so the prose cannot
drift from the tables; full tables are copied into ``site/tables`` and linked as CSV rather than
printed.
"""

from __future__ import annotations

import html
import json
import math
import re
import shutil
from pathlib import Path

import pandas as pd

from dgt_stats import driver_risk
from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, TABLES_DIR

SITE_DIR = PROJECT_ROOT / "site"
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

STYLE = """
/* A statistical bulletin, not a dashboard: serif for reading, sans for furniture and figures,
   hairline rules instead of boxes, and a text column narrower than the charts so that a figure
   or a table always breaks out of the prose. The paper colour is the same one the SVGs are drawn
   on, so a chart sits on the page with no visible edge. */
:root {
  --paper: #fcfcfb;
  --ink: #191817;
  --ink-2: #57544e;
  --rule: #ddd9d1;
  --rule-strong: #b4afa4;
  --accent: #1b5fae;
  --wash: #f4f2ec;
  --serif: Charter, "Bitstream Charter", "Sitka Text", Cambria, "Source Serif 4", Georgia, serif;
  --sans: "Helvetica Neue", Helvetica, Arial, system-ui, sans-serif;
  --measure: 34rem;
  --wide: 52rem;
}
* { box-sizing: border-box; }
html { background: var(--paper); }
body {
  margin: 0;
  color: var(--ink);
  background: var(--paper);
  font-family: var(--serif);
  font-size: 19px;
  line-height: 1.62;
  -webkit-font-smoothing: antialiased;
}
header, main, footer { max-width: var(--wide); margin: 0 auto; padding: 0 24px; }

/* Masthead */
header { padding-top: 28px; }
.masthead { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }
.masthead a { color: var(--ink); text-decoration: none; font-weight: 600; font-size: 1.05rem; letter-spacing: 0.01em; }
.masthead .strap { font-family: var(--sans); font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-2); }
nav { margin: 14px 0 0; border-top: 1px solid var(--ink); border-bottom: 1px solid var(--rule); }
nav ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0 22px; }
nav a {
  display: inline-block; padding: 9px 0 8px; color: var(--ink-2); text-decoration: none;
  font-family: var(--sans); font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase;
}
nav a:hover { color: var(--ink); }
nav a[aria-current="page"] { color: var(--ink); box-shadow: inset 0 -2px 0 var(--accent); }
nav ul.supporting { border-top: 1px solid var(--rule); }
nav ul.supporting li:first-child { font-family: var(--sans); font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-2); padding: 8px 0; }

main { padding-top: 34px; padding-bottom: 56px; }
h1 { font-size: 2.35rem; line-height: 1.12; margin: 0 0 14px; letter-spacing: -0.012em; font-weight: 600; max-width: var(--measure); }
h2 {
  font-size: 1.28rem; font-weight: 600; margin: 46px 0 10px; padding-top: 12px;
  border-top: 1px solid var(--rule); max-width: var(--wide); letter-spacing: -0.005em;
}
h3 { font-size: 1.05rem; font-weight: 600; margin: 30px 0 6px; max-width: var(--measure); }
p, li { max-width: var(--measure); }
p { margin: 0 0 1em; }
p.lead { font-size: 1.12rem; color: var(--ink-2); line-height: 1.5; margin-bottom: 26px; }
p.answer { font-size: 1.18rem; line-height: 1.5; margin: 0 0 1.2em; }
p.answer strong, p.answer em { font-weight: 600; font-style: normal; }
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }

/* Key figures: a bulletin's indicator strip, ruled rather than boxed. */
.figures + h2, .figures + p + h2 { border-top: 0; padding-top: 0; margin-top: 34px; }
.figures { display: flex; flex-wrap: wrap; margin: 0 0 32px; border-top: 2px solid var(--ink); border-bottom: 1px solid var(--rule); }
.keyfig { flex: 1 1 11rem; padding: 12px 18px 13px 0; margin-right: 18px; border-right: 1px solid var(--rule); }
.keyfig:last-child { border-right: 0; margin-right: 0; }
.keyfig .label {
  font-family: var(--sans); font-size: 0.7rem; letter-spacing: 0.07em; text-transform: uppercase;
  color: var(--ink-2); line-height: 1.35; min-height: 2.7em;
}
.keyfig .value { font-size: 1.95rem; font-weight: 600; font-variant-numeric: tabular-nums lining-nums; line-height: 1.1; margin: 5px 0 3px; letter-spacing: -0.02em; }
.keyfig .gloss { font-family: var(--sans); font-size: 0.76rem; line-height: 1.35; color: var(--ink-2); }

/* Findings: a numbered editorial list on the front page. */
.finding { max-width: var(--measure); margin: 0 0 30px; }
.finding h3 { margin: 0 0 6px; font-size: 1.12rem; line-height: 1.3; }
.finding h3 .num { font-family: var(--sans); font-size: 0.72rem; letter-spacing: 0.08em; color: var(--accent); display: block; margin-bottom: 3px; }
.finding h3 a { color: var(--ink); text-decoration: none; box-shadow: inset 0 -1px 0 var(--rule-strong); }
.finding h3 a:hover { box-shadow: inset 0 -2px 0 var(--accent); }
.finding p { margin: 0 0 6px; }
.finding p.method { font-family: var(--sans); font-size: 0.81rem; line-height: 1.45; color: var(--ink-2); }

/* Figures and tables break out of the text column. */
figure { margin: 26px 0 30px; max-width: var(--wide); }
.figure-wrap { overflow-x: auto; }
figure img { width: 100%; min-width: 660px; height: auto; display: block; background: var(--paper); }
figcaption {
  font-family: var(--sans); font-size: 0.78rem; line-height: 1.5; color: var(--ink-2);
  margin-top: 8px; padding-top: 7px; border-top: 1px solid var(--rule); max-width: 46rem;
}
.table-wrap { overflow-x: auto; margin: 24px 0 8px; max-width: var(--wide); }
table {
  border-collapse: collapse; font-family: var(--sans); font-size: 0.82rem;
  font-variant-numeric: tabular-nums lining-nums; min-width: 460px;
}
caption {
  caption-side: top; text-align: left; font-family: var(--sans); font-size: 0.78rem;
  line-height: 1.5; color: var(--ink-2); padding: 0 0 9px; max-width: 46rem;
}
thead th {
  font-weight: 600; color: var(--ink); text-align: right; vertical-align: bottom;
  padding: 0 14px 6px 0; border-bottom: 1px solid var(--ink);
  border-top: 2px solid var(--ink);
  font-size: 0.74rem; letter-spacing: 0.03em;
}
thead th:first-child { text-align: left; }
tbody th, tbody td { padding: 5px 14px 5px 0; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--rule); }
tbody th { font-weight: 400; text-align: left; }
tbody tr:last-child th, tbody tr:last-child td { border-bottom: 1px solid var(--rule-strong); }
th.wrap, td.wrap { white-space: normal; min-width: 22ch; max-width: 40ch; text-align: left; }
.table-wrap:focus-visible, .figure-wrap:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }

.downloads { font-family: var(--sans); font-size: 0.78rem; color: var(--ink-2); margin: 0 0 30px; max-width: 46rem; }
.note { background: var(--wash); padding: 14px 18px; margin: 22px 0; max-width: var(--measure); }
.note p { margin: 0; }
.limit {
  font-family: var(--sans); font-size: 0.83rem; line-height: 1.55; color: var(--ink-2);
  max-width: 44rem; margin: 26px 0 0; padding-top: 12px; border-top: 1px solid var(--rule);
}
.limit strong { color: var(--ink); }
.conclusion { max-width: var(--measure); margin: 26px 0 0; padding-left: 16px; border-left: 3px solid var(--accent); }
.conclusion p { margin: 0; }

footer {
  border-top: 1px solid var(--rule); margin-top: 20px; padding-top: 18px; padding-bottom: 40px;
  font-family: var(--sans); font-size: 0.78rem; line-height: 1.55; color: var(--ink-2);
}
footer p { max-width: 46rem; }

@media (max-width: 640px) {
  body { font-size: 18px; }
  h1 { font-size: 1.85rem; }
  .keyfig { flex-basis: 100%; border-right: 0; border-bottom: 1px solid var(--rule); margin-right: 0; padding-right: 0; }
  .keyfig:last-child { border-bottom: 0; }
}
@media print {
  nav, .downloads { display: none; }
  body { font-size: 11pt; }
  figure, .figure-wrap, .table-wrap { break-inside: avoid; overflow: visible; }
  figure img { min-width: 0; }
  table { min-width: 0; font-size: 8pt; }
  th, td { white-space: normal; }
  a[href^="http"]::after { content: " (" attr(href) ")"; }
}
"""


# --------------------------------------------------------------------------- formatting


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
    """A signed percentage, so a fall reads as −7% and a rise as +7%."""
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


# --------------------------------------------------------------------------- components


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


# --------------------------------------------------------------------------- shared numbers


def _severity_numbers() -> dict[str, object]:
    holdout = read_table("q3_holdout_summary").set_index("outcome")
    coefficients = read_table("q3_model_coefficients")
    fatal = coefficients[coefficients.outcome == "fatal"]
    adverse = read_table("q3_adverse_conditions")
    fatal_adverse = adverse[adverse.outcome == "fatal"].set_index(["variant", "level"])
    return {
        "n": int(fatal.n.iloc[0]),
        "fatal_share": float(fatal.events.iloc[0]) / float(fatal.n.iloc[0]),
        "auc_fatal": float(holdout.loc["fatal", "auc"]),
        "auc_serious": float(holdout.loc["serious", "auc"]),
        "adverse": fatal_adverse,
        "coefficients": coefficients,
    }


def _age_numbers() -> dict[str, object]:
    ratios = read_table("q7_km_ratio").set_index(["measure", "band"])
    rates = read_table("q7_km_rates").set_index("band")
    contrast = read_table("q7_denominator_contrast").set_index(["denominator", "band"])
    company = read_table("q7_company_km").set_index(["allocation", "band"])
    return {"ratios": ratios, "rates": rates, "contrast": contrast, "company": company}


def _policy_numbers() -> dict[str, object]:
    sensitivity = read_table("q8_points_sensitivity").set_index("variant")
    calendar = read_table("q8_points_calendar_placebo")
    forecast = read_table("q8_points_forecast")
    transitions = read_table("q8_points_transitions")
    trend = read_table("q8_points_trend_choice")
    return {
        "sensitivity": sensitivity,
        "calendar": calendar,
        "forecast": forecast,
        "transitions": transitions,
        "trend": trend,
        "main": sensitivity.loc["main"],
        "linear": sensitivity.loc["linear_trend"],
        "true_calendar": calendar[calendar.is_true].iloc[0],
        "true_forecast": forecast[forecast.is_true].iloc[0],
    }


# --------------------------------------------------------------------------- shared numbers


def _ratio_ci(ratio: float, low: float, high: float) -> str:
    return f"{ratio:.2f}× ({low:.2f}–{high:.2f})"


def _change(ratio: float, decimals: int = 1) -> str:
    """A ratio to a base as a signed percentage change: 1.035 reads +3.5%."""
    return _signed_pct(float(ratio) - 1, decimals)


def _risk_numbers() -> dict[str, object]:
    index = read_table("risk_index")
    last = int(index.year.max())
    latest = index[index.year == last].set_index(["outcome", "denominator"])
    return {"index": index, "last": last, "latest": latest}


def _long_run_numbers() -> dict[str, object]:
    series = read_table("longrun_series")
    segments = read_table("longrun_segments")
    efficiency = read_table("longrun_efficiency")
    projected = series[series.period == "projected"].set_index(["measure", "year"])
    return {
        "series": series,
        "segments": segments,
        "efficiency": efficiency,
        "projected": projected,
        "last": int(series.year.max()),
    }


def _season_numbers() -> dict[str, object]:
    effects = read_table("season_month_effects").set_index(["exposure", "month"])
    lockdown = read_table("season_lockdown").set_index("month")
    return {"effects": effects, "lockdown": lockdown}


def _sex_numbers() -> dict[str, object]:
    ratios = read_table("drivers_sex_ratios").set_index(["scope", "band", "measure"])
    rates = read_table("drivers_sex_rates").set_index(["scope", "band", "sex"])
    travel = read_table("drivers_sex_travel").set_index("band")
    return {"ratios": ratios, "rates": rates, "travel": travel}


def _speed_numbers() -> dict[str, object]:
    pooled = read_table("speed_severity_pooled").set_index("road_type")
    yearly = read_table("speed_severity")
    all_roads = yearly[yearly.road_type == "all"].set_index("year")
    return {"pooled": pooled, "yearly": yearly, "all_roads": all_roads}


def _factor_numbers() -> dict[str, object]:
    windows = read_table("factor_windows")
    changes = read_table("factor_changes")
    shares = read_table("factor_shares").set_index(["zone", "factor", "year"])
    return {"windows": windows, "changes": changes, "shares": shares}


def _window(windows: pd.DataFrame, zone: str, factor: str, year: int) -> pd.Series:
    """The comparable window of ``factor`` in ``zone`` that contains ``year``."""
    match = windows[
        (windows.zone == zone)
        & (windows.factor == factor)
        & (windows.first_year <= year)
        & (windows.last_year >= year)
    ]
    return match.iloc[0]


# --------------------------------------------------------------------------- overview


def page_index(captions: dict[str, str]) -> str:
    risk = _risk_numbers()
    latest, last = risk["latest"], risk["last"]
    long_run = _long_run_numbers()
    projected = long_run["projected"]
    season = _season_numbers()
    effects = season["effects"]
    sex = _sex_numbers()
    age = _age_numbers()
    speed = _speed_numbers()
    factor = _factor_numbers()
    vehicles = read_table("q6_summary_2022").set_index("group")
    truck, car = vehicles.loc["heavy_truck"], vehicles.loc["car"]

    deaths_count = latest.loc[("deaths_30d", "count")]
    deaths_fuel = latest.loc[("deaths_30d", "road_fuel")]
    deaths_vehicle = latest.loc[("deaths_30d", "vehicles")]
    deaths_resident = latest.loc[("deaths_30d", "residents")]
    hosp = latest.xs("hospitalised_30d", level="outcome")
    fuel_last = projected.loc[("road_fuel", last)]
    fuel_prev = projected.loc[("road_fuel", last - 1)]
    count_2020 = projected.loc[("count", 2020)]
    fuel_2020 = projected.loc[("road_fuel", 2020)]
    fuel_segment = long_run["segments"][long_run["segments"].measure == "road_fuel"].iloc[-1]
    july_raw = effects.loc[("none", 7)]
    july_petrol = effects.loc[("petrol_tonnes", 7)]
    august_raw = effects.loc[("none", 8)]
    august_petrol = effects.loc[("petrol_tonnes", 8)]
    april = season["lockdown"].loc[4]
    ratios_sex = sex["ratios"]
    men_involved = ratios_sex.loc[("car", "18+", "involved_per_1000_licences")]
    men_fatality = ratios_sex.loc[("car", "18+", "deaths_per_1000_involved")]
    involved_75 = age["ratios"].loc[("involved_per_bn_km", "75+")]
    fatality_75 = age["ratios"].loc[("deaths_per_1000_involved", "75+")]
    adjusted = speed["pooled"].loc["adjusted"]
    per_vehicle = float(
        truck.fatal_involvement_per_100k_vehicles / car.fatal_involvement_per_100k_vehicles
    )
    per_km = float(truck.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
    windows = factor["windows"]
    alcohol = _window(windows, "interurban", "Alcohol", 2014)
    speed_share = _window(windows, "all", "Inappropriate speed", 2014)

    body = key_figures(
        [
            (
                "Deaths per unit of traffic",
                _change(float(fuel_last.ratio), 0),
                f"per tonne of fuel, above the pre-2020 trend in {last}; the count is on trend",
            ),
            (
                "August peak, per unit of traffic",
                _times(float(august_petrol.rate_ratio)),
                f"the average month; {_times(float(august_raw.rate_ratio))} as a raw count",
            ),
            (
                "Killed once in a crash",
                _times(float(men_fatality.ratio)),
                "male against female car drivers",
            ),
            (
                "Deaths per crash with speed",
                _times(float(adjusted.rate_ratio)),
                "against other crashes on the same kind of road",
            ),
        ]
    )
    body += (
        '<p class="answer">A count of crashes or deaths says how many. It does not say how '
        "dangerous the roads were, because it moves with how much people drove, who was driving "
        "and in what. This site divides the same DGT counts by residents, licence holders, "
        "vehicles, kilometres and road fuel, and asks what changes. On every question below the "
        "answer changes size, and on several it changes sign.</p>"
    )

    findings = [
        (
            "trends.html",
            "Since 2019, whether death risk rose or fell depends on the denominator",
            f"Deaths in {last} were {_change(float(deaths_count.ratio_to_base))} on 2019 as a "
            f"count, {_change(float(deaths_resident.ratio_to_base))} per resident, "
            f"{_change(float(deaths_vehicle.ratio_to_base))} per registered vehicle and "
            f"{_change(float(deaths_fuel.ratio_to_base))} per tonne of road fuel, none of it "
            "beyond chance. Injury crashes fell per person and per vehicle but not per unit of "
            "traffic, and people admitted to hospital rose under every denominator, by "
            f"{_change(float(hosp.ratio_to_base.min()))} to "
            f"{_change(float(hosp.ratio_to_base.max()))}.",
            "Annual DGT totals over INE residents, the driver census, the registered fleet and "
            "CORES road-fuel consumption, each indexed to 2019 with Poisson intervals.",
        ),
        (
            "long-run.html",
            "The pandemic dip was less driving; the plateau since is worse than it looks",
            f"As a count, 2020 deaths were {_change(float(count_2020.ratio), 0)} against the "
            "pre-pandemic trend and were back on it by 2022. Per tonne of road fuel, 2020 was on "
            f"trend ({_times(float(fuel_2020.ratio))}): the fall was the traffic. And per tonne of "
            f"fuel, {last - 1} and {last} ran {_change(float(fuel_prev.ratio), 0)} and "
            f"{_change(float(fuel_last.ratio), 0)} above where the {int(fuel_segment.start)}–"
            f"{int(fuel_segment.end)} trend was heading, unless fuel economy improved much "
            "faster after 2020 than before.",
            "Segmented (joinpoint) quasi-Poisson trends fitted to 1993–2019 with turning points "
            "chosen by QBIC, projected through 2020–2024 with prediction intervals, and a "
            "sensitivity for faster fuel-economy gains.",
        ),
        (
            "seasons.html",
            "The summer peak is mostly traffic; the autumn excess is not",
            f"Raw deaths in July are {_times(float(july_raw.rate_ratio))} and in August "
            f"{_times(float(august_raw.rate_ratio))} the average month. Per unit of petrol, the "
            f"car fuel, they are {_times(float(july_petrol.rate_ratio))} and "
            f"{_times(float(august_petrol.rate_ratio))}. In the April 2020 lockdown deaths fell "
            f"{_fmt_pct(-float(april.deaths_change), 0)} and petrol sales "
            f"{_fmt_pct(-float(april.petrol_tonnes_change), 0)}: fewer deaths, not safer roads.",
            "Monthly deaths since 2014 against monthly road fuel, petrol and toll-motorway "
            "traffic, in quasi-Poisson models with year and month effects.",
        ),
        (
            "drivers.html",
            "Older and male drivers crash little more for their driving; they die more when they do",
            f"Per kilometre, car drivers aged 75 and over are involved in injury crashes "
            f"{_times(float(involved_75.ratio))} as often as those aged 35 to 54, but are killed "
            f"{_times(float(fatality_75.ratio))} as often once involved. Male car drivers are "
            f"involved {_times(float(men_involved.ratio))} as often as women per licence holder, "
            "about what the only Spanish travel survey by sex implies, and killed "
            f"{_times(float(men_fatality.ratio))} as often once involved.",
            "DGT driver tables over the driver census and DGT's 2024 kilometres by owner age; "
            "MOVILIA trips by sex as a bounded travel proxy.",
        ),
        (
            "vehicles.html",
            "A heavy truck is ten times a car, or two and a half times, depending on the divisor",
            f"Per circulating vehicle a heavy truck is in a fatal crash {per_vehicle:.1f} times as "
            f"often as a car. Per kilometre driven it is {per_km:.1f} times. For every fatal crash "
            f"a truck is in, {float(truck.occupant_deaths_per_fatal_involvement):.2f} of its own "
            "occupants die, so most of the danger a truck carries is to other people.",
            "DGT's 2022 kilometre estimates divided into the same year's involvement counts, "
            "with exact Poisson intervals.",
        ),
        (
            "speed.html",
            "Where speed is recorded, a crash is twice as likely to kill",
            "Injury crashes in which the police recorded inappropriate speed kill "
            f"{_times(float(adjusted.crude_ratio))} as many people per crash as the rest, and "
            f"{_times(float(adjusted.rate_ratio))} once the comparison is made on the same kind "
            "of road in the same year. That is an association: the record is written after the "
            "fact, and is likelier to be written when someone has died.",
            "DGT's speed-factor report against totals from the microdata for the same provinces, "
            "which reproduce the report's own totals exactly.",
        ),
        (
            "factors.html",
            "Alcohol is rising on interurban roads; distraction cannot be trended in towns",
            "Recorded alcohol went from "
            f"{_fmt_pct(float(alcohol.share_first))} to {_fmt_pct(float(alcohol.share_last))} of "
            f"interurban injury crashes between {int(alcohol.first_year)} and "
            f"{int(alcohol.last_year)}, and inappropriate speed from "
            f"{_fmt_pct(float(speed_share.share_first))} to "
            f"{_fmt_pct(float(speed_share.share_last))} of all of them, both on a consistent "
            "record. Urban distraction jumps and falls by half in single years, and drugs are too "
            "few to compare.",
            "DGT's concurrent-factor tables, with a recording-break rule applied to every "
            "year-to-year change before any trend is read.",
        ),
    ]
    body += "".join(
        finding(index, href, heading, text, method)
        for index, (href, heading, text, method) in enumerate(findings, start=1)
    )

    body += "<h2>What this site does not claim</h2>"
    body += (
        "<p>It attributes no cause. The public microdata have one row per crash and no driver, "
        "vehicle or person records, so every factor here is an association, and a policy or "
        "campaign effect is never read off a time series. Two analyses built earlier in the "
        "project are kept as supporting material because they are careful but outside this "
        'question: a <a href="severity.html">model of crash severity</a> and a '
        '<a href="policy.html">test of the 2006 points licence</a> whose headline did not '
        "survive its own falsification tests. Road design and municipal hotspots are not "
        "analysed: the files carry no road geometry, traffic volume or coordinates.</p>"
    )
    body += "<h2>How to read the numbers</h2>"
    body += (
        "<p>Counts are DGT's consolidated figures. An injury crash is one with at least one "
        "person killed or injured, and deaths are counted within 30 days. Every rate names its "
        "denominator, because the denominator is usually where the answer comes from. Sources, "
        "definitions and the reconciliation checks are on the "
        '<a href="data.html">data page</a>.</p>'
    )
    return render_page(
        "index",
        "Road safety in Spain",
        "What changes when you stop counting crashes and start measuring road risk: seven "
        "questions answered from DGT data, each with the denominator that decides it.",
        body,
    )


# --------------------------------------------------------------------------- 2019 to 2024


DENOMINATOR_NOTES = {
    "count": "The outcome itself.",
    "residents": "Everyone living in Spain, most of whom are not driving at any moment.",
    "licence_holders": "Everyone allowed to drive, including those who rarely do.",
    "vehicles": "Every registered vehicle, including the many that are rarely used.",
    "road_fuel": "Petrol and diesel sold for road use: the closest annual measure of traffic.",
}


def page_trends(captions: dict[str, str]) -> str:
    risk = _risk_numbers()
    latest, last = risk["latest"], risk["last"]
    efficiency = read_table("risk_fuel_efficiency")
    crosscheck = read_table("risk_km_crosscheck").set_index("measure")
    deaths = latest.xs("deaths_30d", level="outcome")
    hosp = latest.xs("hospitalised_30d", level="outcome")
    crashes = latest.xs("crashes", level="outcome")

    body = key_figures(
        [
            (
                f"Deaths, {last} against 2019",
                _change(float(deaths.loc["count", "ratio_to_base"])),
                "as a count",
            ),
            (
                "Per registered vehicle",
                _change(float(deaths.loc["vehicles", "ratio_to_base"])),
                "the same deaths",
            ),
            (
                "Per tonne of road fuel",
                _change(float(deaths.loc["road_fuel", "ratio_to_base"])),
                "the same deaths",
            ),
            (
                "Hospitalised, as a count",
                _change(float(hosp.loc["count", "ratio_to_base"])),
                "up under every denominator",
            ),
        ]
    )
    body += (
        '<p class="answer">Whether Spain\'s roads became more or less dangerous after 2019 '
        f"depends on what the deaths are divided by. In {last} there were "
        f"{_fmt_int(deaths.loc['count', 'count'])} deaths, "
        f"{_change(float(deaths.loc['count', 'ratio_to_base']))} on 2019. Per resident that is "
        f"{_change(float(deaths.loc['residents', 'ratio_to_base']))}, per licence holder "
        f"{_change(float(deaths.loc['licence_holders', 'ratio_to_base']))}, per registered "
        f"vehicle {_change(float(deaths.loc['vehicles', 'ratio_to_base']))} and per tonne of "
        f"road fuel {_change(float(deaths.loc['road_fuel', 'ratio_to_base']))}. The population "
        "and the fleet grew faster than the deaths; traffic did not. None of the five changes "
        "in deaths is distinguishable from chance. The two larger counts are: injury crashes "
        "fell per person and per vehicle and held level per unit of traffic, and the number of "
        "people injured and admitted to hospital rose under every denominator, by "
        f"{_change(float(hosp.ratio_to_base.min()))} to "
        f"{_change(float(hosp.ratio_to_base.max()))}.</p>"
    )
    body += figure(
        "r1_risk_change",
        f"Deaths, hospitalised and injury crashes in {last} against 2019 under five denominators",
        captions,
    )

    rows = []
    for key, note_text in DENOMINATOR_NOTES.items():
        for outcome_frame, name in ((deaths, "Deaths"), (hosp, "Hospitalised")):
            row = outcome_frame.loc[key]
            rows.append(
                {
                    "Denominator": row.denominator_label,
                    "Outcome": name,
                    f"Change {last} on 2019": _change(float(row.ratio_to_base)),
                    "95% interval": f"{_change(float(row.ratio_low))} to "
                    f"{_change(float(row.ratio_high))}",
                    "What it counts": note_text,
                }
            )
    body += table(
        pd.DataFrame(rows),
        f"Deaths and hospitalised injured, {last} against 2019, under each denominator",
    )
    body += (
        "<p>Injury crashes, a count large enough to show small changes, moved "
        f"{_change(float(crashes.loc['count', 'ratio_to_base']))} as a count, "
        f"{_change(float(crashes.loc['residents', 'ratio_to_base']))} per resident, "
        f"{_change(float(crashes.loc['vehicles', 'ratio_to_base']))} per vehicle and "
        f"{_change(float(crashes.loc['road_fuel', 'ratio_to_base']))} per tonne of fuel: fewer "
        "crashes for each person and each vehicle, the same number for the traffic. Together "
        "with the rise in hospital admissions that means more people admitted per crash, "
        "which is either more serious crashes or more complete tracing of admissions. "
        "Against 2019 alone, the per-fuel rise in deaths is within chance. Against the "
        'direction the pre-2020 trend was taking, it is not; the <a href="long-run.html">long-run '
        "page</a> sets that out.</p>"
    )

    body += "<h2>Fuel is a proxy for kilometres, and it drifts</h2>"
    last_rows = efficiency[(efficiency.year == last) & (efficiency.outcome == "deaths_30d")]
    by_gain = last_rows.set_index("annual_efficiency_gain")
    body += (
        "<p>No Spanish source counts vehicle-kilometres every year. Road fuel is the closest "
        "substitute, and it is biased in one known direction: a fleet that burns less per "
        "kilometre each year, and a growing share of electric kilometres that burn none, drive "
        "further per tonne. If kilometres per tonne improved by 1% a year after 2019, deaths per "
        f"kilometre moved {_change(float(by_gain.loc[0.01, 'ratio_to_base']))} rather than "
        f"{_change(float(by_gain.loc[0.0, 'ratio_to_base']))}; at 2% a year, "
        f"{_change(float(by_gain.loc[0.02, 'ratio_to_base']))}. So per kilometre, deaths were "
        "roughly flat between 2019 and "
        f"{last}, while the population and the fleet both grew.</p>"
    )
    all_types = crosscheck.loc["All vehicle types"]
    cars_row = crosscheck.loc["Cars"]
    body += (
        "<p>DGT has published two estimates of vehicle-kilometres, for 2022 and for 2024. They "
        "cannot replace fuel as a series: they are built differently, and between them the "
        f"total moves {_change(float(all_types.km_ratio_2024_to_2022))} (cars "
        f"{_change(float(cars_row.km_ratio_2024_to_2022))}) while road fuel moves "
        f"{_change(float(all_types.fuel_ratio_2024_to_2022))}. They are used where a single "
        'year is enough: <a href="vehicles.html">vehicle types</a> and '
        '<a href="drivers.html">driver age</a>.</p>'
    )
    body += downloads(
        [
            ("risk_index", "every outcome, denominator and year"),
            ("risk_annual_panel", "outcomes and denominators, 1993 onwards"),
            ("risk_fuel_efficiency", "fuel-economy sensitivity"),
            ("risk_km_crosscheck", "DGT kilometre estimates against fuel"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        f"Measured as a count, road deaths in {last} were slightly above 2019. Measured per "
        "resident, per licence holder or per vehicle they were slightly below; measured per "
        "unit of traffic, slightly above, or flat once better fuel economy is allowed for. None "
        "of those differences is larger than a year's chance variation, so the honest summary "
        "is that death risk did not measurably change against 2019. Crash risk fell per person "
        "and per vehicle and held level per unit of traffic. Serious injury rose: more people "
        f"were admitted to hospital after a crash in {last} than in 2019 under every "
        "denominator."
    )
    body += limits(
        "The denominators are totals for Spain and treat every resident, licence, vehicle and "
        "tonne of fuel alike. Fuel sold is not fuel burnt on Spanish roads, and it mixes freight "
        "with private travel. The intervals cover the chance variation in the counts only. The "
        "hospitalised count depends on how completely admissions are traced back to crashes, and "
        "a change in that tracing would move the series without any change on the road; these "
        "tables cannot tell the two apart."
    )
    return render_page(
        "trends",
        "2019 to 2024: counts against risk",
        "Did the roads get safer or more dangerous after the pandemic? For deaths the count "
        "and four denominators disagree, within chance; for crashes and serious injuries they "
        "do not.",
        body,
    )


# --------------------------------------------------------------------------- long run


MEASURE_SHORT = {
    "count": "Deaths",
    "vehicles": "Deaths per vehicle",
    "road_fuel": "Deaths per tonne of fuel",
}


def page_long_run(captions: dict[str, str]) -> str:
    numbers = _long_run_numbers()
    segments, projected = numbers["segments"], numbers["projected"]
    efficiency, last = numbers["efficiency"], numbers["last"]
    headline = read_table("q1_annual_headline").set_index("year")
    peak = int(headline.deaths_30d.idxmax())
    count_segments = segments[segments.measure == "count"].reset_index(drop=True)
    fuel_segments = segments[segments.measure == "road_fuel"].reset_index(drop=True)
    steep, flat = count_segments.iloc[1], count_segments.iloc[2]
    fuel_flat = fuel_segments.iloc[-1]
    count_2020 = projected.loc[("count", 2020)]
    fuel_2020 = projected.loc[("road_fuel", 2020)]
    fuel_last = projected.loc[("road_fuel", last)]
    fuel_prev = projected.loc[("road_fuel", last - 1)]
    count_last = projected.loc[("count", last)]
    plateau_start = int(flat.start)

    body = key_figures(
        [
            (
                f"Deaths, {peak} to {plateau_start}",
                _fmt_pct(
                    1
                    - float(headline.loc[plateau_start, "deaths_30d"])
                    / float(headline.loc[peak, "deaths_30d"]),
                    0,
                ),
                "fewer",
            ),
            (
                f"Annual change, {int(steep.start)}–{int(steep.end)}",
                _signed_pct(float(steep.annual_change), 1),
                "deaths per year, the steep segment",
            ),
            (
                f"Annual change, {int(flat.start)}–{int(flat.end)}",
                _signed_pct(float(flat.annual_change), 1),
                "the plateau",
            ),
            (
                f"Per unit of fuel, {last}",
                _change(float(fuel_last.ratio), 0),
                "above the pre-2020 trend",
            ),
        ]
    )
    body += (
        '<p class="answer">Spain\'s road deaths fell slowly until '
        f"{int(steep.start)}, steeply for a decade, and have not fallen since "
        f"{plateau_start}. The pandemic looks like a dip in that plateau and a recovery. Measured "
        "against traffic it was neither: per tonne of road fuel, 2020 and 2021 were on the "
        "pre-pandemic trend, so the fall in deaths was the fall in driving. The recovery is the "
        f"part that changed. By {last - 1} and {last}, deaths per tonne of fuel were "
        f"{_change(float(fuel_prev.ratio), 0)} and {_change(float(fuel_last.ratio), 0)} above "
        "where the pre-2020 decline was heading, outside the trend's prediction interval.</p>"
    )
    body += figure(
        "l1_trend_projection",
        "Deaths, 1993–2024, against segmented trends fitted to 2019 and projected on",
        captions,
    )
    shown = segments.assign(
        Measure=segments.measure.map(MEASURE_SHORT),
        Years=[f"{int(a)}–{int(b)}" for a, b in zip(segments.start, segments.end)],
        Change=[_signed_pct(float(v), 1) for v in segments.annual_change],
        Interval=[
            f"{_signed_pct(float(lo), 1)} to {_signed_pct(float(hi), 1)}"
            for lo, hi in zip(segments.low, segments.high)
        ],
    )[["Measure", "Years", "Change", "Interval"]].rename(
        columns={"Change": "Annual change", "Interval": "95% interval"}
    )
    body += table(
        shown,
        "Segments of the 1993–2019 trend, turning points chosen by the data. Sources: DGT "
        "yearbook series, registered fleet and CORES road fuel",
    )
    body += (
        "<p>The three measures find the same history. The turning points are placed by the data "
        "(every combination of up to three is fitted and the simplest adequate model kept), and "
        "they land within two years of each other: a slow decline to about 2003, a fall of "
        "around a tenth a year for a decade, then a halt. Per vehicle and per tonne of fuel the "
        "last segment still slopes down "
        f"({_signed_pct(float(fuel_flat.annual_change), 1)} a year per tonne of fuel), because "
        "traffic kept growing while deaths held steady.</p>"
    )

    body += "<h2>2020 to 2024: distortion or trend?</h2>"
    body += figure(
        "l2_observed_over_trend",
        "Observed deaths divided by each measure's pre-pandemic trend, 2010–2024",
        captions,
    )
    rows = []
    for year in range(2020, last + 1):
        record = {"Year": year}
        for measure, label in MEASURE_SHORT.items():
            row = projected.loc[(measure, year)]
            flag = " (outside)" if bool(row.outside_interval) else ""
            record[label] = f"{float(row.ratio):.2f}{flag}"
        rows.append(record)
    body += table(
        pd.DataFrame(rows),
        "Observed deaths as a multiple of each projected trend; outside: beyond the 95% "
        "prediction interval",
        {"Year": "year"},
    )

    def excess(gain: float) -> str:
        rows = efficiency[
            (efficiency.extra_annual_efficiency_gain == gain) & (efficiency.year >= last - 1)
        ].set_index("year")
        parts = []
        for year in (last - 1, last):
            row = rows.loc[year]
            where = "outside" if float(row.ratio_low) > 1 else "inside"
            parts.append(f"{_change(float(row.ratio), 0)} in {year} ({where} the interval)")
        return _join(parts)

    body += (
        f"<p>As a count, 2020 was {_change(float(count_2020.ratio), 0)} against trend and "
        f"{last} {_change(float(count_last.ratio), 0)}: a dip and a return. Per tonne of fuel, "
        f"2020 was {_change(float(fuel_2020.ratio), 0)}, inside the interval. The per-fuel trend "
        "already carries the fuel-economy gains of 1996–2019, so projecting it assumes they "
        "continued at that pace. If kilometres per tonne improved an extra 1% a year from 2020, "
        f"the excess is {excess(0.01)}; at an extra 2% a year it is {excess(0.02)}. So the "
        "excess is clear if fuel economy kept its pre-2020 pace, and within the trend's "
        "uncertainty only if it improved about two points a year faster than before.</p>"
    )
    body += downloads(
        [
            ("longrun_series", "observed against trend, every year"),
            ("longrun_segments", "segments and annual changes"),
            ("longrun_model_choice", "the turning-point search"),
            ("longrun_efficiency", "fuel-economy sensitivity"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "The large structural change in Spanish road deaths happened between about 2003 and "
        f"{plateau_start} and has not resumed. The pandemic did not interrupt it: 2020 and 2021 "
        "deaths fell in line with traffic, so they are a distortion of the count, not of the "
        "risk. What the count hides is that since 2022 deaths per unit of traffic have run "
        "above the pre-pandemic decline, and in the last two years beyond its prediction "
        "interval unless fuel economy improved much faster than before: the plateau in deaths "
        "is a plateau at a level of risk the trend had been leaving behind."
    )
    body += limits(
        "The trends are statistical descriptions, not explanations, and a projection assumes "
        "the last segment would have continued. Road fuel is a proxy for traffic whose "
        "relation to kilometres drifts, bounded above by a sensitivity. The registered fleet "
        "counts idle vehicles and grows as the fleet ages. The 30-day death series is taken as "
        "DGT publishes it for every year since 1993."
    )
    return render_page(
        "long-run",
        "1993 to 2024: structural change and the pandemic",
        "Which changes in thirty years of road deaths are structural, and which are the "
        "pandemic? Fit the trend before 2020, project it, and measure against traffic.",
        body,
    )


# --------------------------------------------------------------------------- seasons


def page_seasons(captions: dict[str, str]) -> str:
    numbers = _season_numbers()
    effects, lockdown = numbers["effects"], numbers["lockdown"]
    profile = read_table("season_profile").set_index("month")
    night = read_table("q2_night_share")
    night_year = int(night.year.max())
    night_inter = night[(night.year == night_year) & (night.zone == "interurban")].iloc[0]

    def effect(exposure: str, month: int) -> pd.Series:
        return effects.loc[(exposure, month)]

    july, august = effect("none", 7), effect("none", 8)
    july_petrol, august_petrol = effect("petrol_tonnes", 7), effect("petrol_tonnes", 8)
    july_fuel, august_fuel = effect("road_fuel_tonnes", 7), effect("road_fuel_tonnes", 8)
    august_toll = effect("toll_intensity", 8)
    april = lockdown.loc[4]
    exposures = ("road_fuel_tonnes", "petrol_tonnes", "toll_intensity")
    spring = [float(effect(e, m).rate_ratio) for e in exposures for m in (4, 5)]
    dark = [
        month
        for month in (1, 9, 10, 11, 12)
        if sum(float(effect(e, month).low) > 1 for e in exposures) >= 2
    ]
    month_names = {1: "January", 9: "September", 10: "October", 11: "November", 12: "December"}

    body = key_figures(
        [
            ("July deaths", _times(float(july.rate_ratio)), "the average month, as a count"),
            (
                "July, per unit of petrol",
                _times(float(july_petrol.rate_ratio)),
                "the average month",
            ),
            (
                "August, per unit of petrol",
                _times(float(august_petrol.rate_ratio)),
                f"{_times(float(august.rate_ratio))} as a count",
            ),
            (
                "Deaths, April 2020",
                _fmt_pct(float(april.deaths_change), 0),
                f"petrol {_fmt_pct(float(april.petrol_tonnes_change), 0)}",
            ),
        ]
    )
    body += (
        '<p class="answer">The summer rise in road deaths is mostly more driving. Deaths in July '
        f"and August run {_times(float(july.rate_ratio))} and {_times(float(august.rate_ratio))} "
        "the average month. Per unit of petrol, which in Spain is burnt mostly by private cars "
        f"and motorcycles, they are {_times(float(july_petrol.rate_ratio))} and "
        f"{_times(float(august_petrol.rate_ratio))}: August's excess disappears and July's "
        "shrinks to a few per cent. What survives the allowance for traffic is elsewhere in the "
        "year: spring has fewer deaths per unit of traffic under every measure, and "
        + _join([month_names[m] for m in dark])
        + " more under at least two of the three.</p>"
    )
    body += figure(
        "m1_season_profile",
        "Deaths and three traffic series by month, average month = 100",
        captions,
    )
    body += (
        "<p>No series counts kilometres on all Spanish roads month by month, so three stand in "
        "for it, each wrong in a known direction. Road fuel includes freight diesel, which slows "
        f"in the August industrial holiday, so it rises only to {float(profile.loc[8, 'road_fuel_tonnes']):.0f} "
        "in August. Traffic on the state toll motorways, mostly long-distance holiday routes, "
        f"rises to {float(profile.loc[8, 'toll_intensity']):.0f}. Petrol sits between them at "
        f"{float(profile.loc[8, 'petrol_tonnes']):.0f}. The truth for the whole network lies "
        "somewhere in that range, which is why the answer is given under all three.</p>"
    )
    body += figure(
        "m2_month_effects",
        "Month effects on deaths with no exposure and per unit of each traffic series",
        captions,
    )
    body += (
        "<p>With year effects taking out the trend, July's deaths are "
        f"{_times(float(july.rate_ratio))} the average month as a count, "
        f"{_times(float(july_fuel.rate_ratio))} per unit of road fuel and "
        f"{_times(float(july_petrol.rate_ratio))} per unit of petrol; August's are "
        f"{_times(float(august.rate_ratio))}, {_times(float(august_fuel.rate_ratio))} and "
        f"{_times(float(august_petrol.rate_ratio))}, and per unit of toll-motorway traffic "
        f"{_times(float(august_toll.rate_ratio))}. April and May run between "
        f"{min(spring):.2f} and {max(spring):.2f} under every proxy. "
        + _join([month_names[m] for m in dark])
        + " carry more deaths per unit of traffic under at least two of the three, and the "
        "winter months under some. That is consistent with longer hours of darkness: in the "
        f"microdata for {night_year}, darkness holds "
        f"{_fmt_pct(float(night_inter.night_crash_share), 0)} of interurban injury crashes but "
        f"{_fmt_pct(float(night_inter.night_death_share), 0)} of interurban deaths. These series "
        "do not show darkness to be the cause.</p>"
    )

    body += "<h2>The lockdown as a natural experiment</h2>"
    body += figure(
        "m3_lockdown", "2020 against 2017–2019, month by month: deaths and traffic", captions
    )
    body += (
        f"<p>In April 2020, the one full month of the strictest lockdown, deaths fell "
        f"{_fmt_pct(-float(april.deaths_change), 0)} on the 2017–2019 average. Road fuel fell "
        f"{_fmt_pct(-float(april.road_fuel_tonnes_change), 0)}, petrol "
        f"{_fmt_pct(-float(april.petrol_tonnes_change), 0)} and toll-motorway traffic "
        f"{_fmt_pct(-float(april.toll_intensity_change), 0)}. The fall in deaths was the size of "
        "the fall in traffic. Whether each remaining kilometre became more or less dangerous "
        "depends on which proxy is believed: per unit of road fuel deaths fell "
        f"{_fmt_pct(-float(april.risk_change_road_fuel_tonnes), 0)}, per unit of petrol they "
        f"rose {_fmt_pct(float(april.risk_change_petrol_tonnes), 0)}. The data cannot settle "
        "it, and this page does not claim either.</p>"
    )
    body += downloads(
        [
            ("season_profile", "monthly indices"),
            ("season_month_effects", "month effects under each exposure"),
            ("season_lockdown", "2020 month by month"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Most of the summer peak in road deaths is a peak in driving: per unit of private-car "
        "fuel, August is an ordinary month and July only slightly worse. The seasonal pattern "
        "that is not explained by volume runs the other way from the headlines: spring is "
        "safer per unit of traffic and autumn riskier. The 2020 collapse in "
        "deaths was a collapse in traffic, and is not evidence that the roads became safer."
    )
    body += limits(
        "The traffic series are proxies: fuel sales by month, not fuel burnt, and toll traffic "
        "on a network that shrank as concessions expired, which is why intensity per kilometre "
        "is used rather than vehicle-kilometres. Monthly deaths are small counts, about 100 to "
        "200, so single months carry wide intervals; the month effects pool nine years."
    )
    return render_page(
        "seasons",
        "Seasonality and mobility",
        "Is the summer peak in road deaths a peak in danger, or in driving? Divide each month by "
        "three measures of traffic and see what is left.",
        body,
    )


# --------------------------------------------------------------------------- drivers: sex


def _sex_section(captions: dict[str, str]) -> tuple[str, dict[str, pd.Series]]:
    numbers = _sex_numbers()
    ratios, rates_table, travel = numbers["ratios"], numbers["rates"], numbers["travel"]
    involved = ratios.loc[("car", "18+", "involved_per_1000_licences")]
    killed = ratios.loc[("car", "18+", "deaths_per_million_licences")]
    fatality = ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    motor_fatality = ratios.loc[("motor", "18+", "deaths_per_1000_involved")]
    motor_killed = ratios.loc[("motor", "18+", "deaths_per_million_licences")]
    years = str(rates_table.years.iloc[0]).replace("-", "–")
    under_65 = travel.loc[["15-29", "30-39", "40-49", "50-64"]]

    section = "<h2>Men and women</h2>"
    section += (
        f"<p>Per licence holder, in {years}, male car drivers were involved in injury crashes "
        f"{_ratio_ci(float(involved.ratio), float(involved.low), float(involved.high))} as often "
        "as female ones and killed "
        f"{_ratio_ci(float(killed.ratio), float(killed.low), float(killed.high))} as often. The "
        "first ratio includes how much each group drives; the census counts licences, not "
        "kilometres. The second divides into two parts that exposure affects very differently. "
        "Once involved in a crash, a male car driver was killed "
        f"{_ratio_ci(float(fatality.ratio), float(fatality.low), float(fatality.high))} as often "
        "as a female one, a ratio that needs no measure of driving at all.</p>"
    )
    section += figure(
        "a3_sex_ratios",
        "Men against women, car drivers, by age: involvement and deaths per licence holder, and "
        "deaths once involved",
        captions,
    )
    section += (
        "<p>How much of the involvement gap is driving? No Spanish source measures kilometres "
        "by sex. The national travel survey MOVILIA (2006) counts trips by car or motorcycle, as "
        "driver or passenger, by sex and age. Under 65, men made "
        f"{under_65.trip_ratio_2006.min():.1f} to {under_65.trip_ratio_2006.max():.1f} times as "
        "many such trips per head as women; car-driver involvement per head in "
        f"{years} runs "
        f"{under_65.involved_ratio_per_resident.min():.1f} to "
        f"{under_65.involved_ratio_per_resident.max():.1f} times. Per trip, that leaves "
        f"{under_65.involved_ratio_per_trip.min():.1f} to "
        f"{under_65.involved_ratio_per_trip.max():.1f}: about equal. The survey is old and counts "
        "passengers, who are more often women, so it understates the driving gap; the "
        "conclusion it supports is only that the involvement gap is of the size a travel gap "
        f"could produce. The fatality gap is not: per trip, deaths still run "
        f"{under_65.deaths_ratio_per_trip.min():.1f} to "
        f"{under_65.deaths_ratio_per_trip.max():.1f} times.</p>"
    )
    rows = []
    for scope, label in (("car", "Car drivers"), ("motor", "All motor-vehicle drivers")):
        for sex, sex_label in (("male", "Men"), ("female", "Women")):
            row = rates_table.loc[(scope, "18+", sex)]
            rows.append(
                {
                    "Drivers": label,
                    "Sex": sex_label,
                    "Involved per 1,000 licence holders": row.involved_per_1000_licences,
                    "Killed per million licence holders": row.deaths_per_million_licences,
                    "Killed per 1,000 involved": row.deaths_per_1000_involved,
                    "Drivers killed": row.driver_deaths,
                }
            )
    section += table(
        pd.DataFrame(rows),
        f"Drivers aged 18 and over, {years} pooled. Sources: DGT driver tables 4.1.1 and 4.2, "
        "Censo de conductores 2014–2025",
        {
            "Involved per 1,000 licence holders": "dec2",
            "Killed per million licence holders": "dec",
            "Killed per 1,000 involved": "dec2",
            "Drivers killed": "int",
        },
    )
    section += (
        "<p>Across all motor vehicles the gaps are wider, "
        f"{_times(float(motor_killed.ratio))} per licence holder and "
        f"{_times(float(motor_fatality.ratio))} once involved, because men ride most of the "
        "motorcycles. Cyclists and personal-mobility-vehicle riders are left out of both, since "
        "they need no licence.</p>"
    )
    section += downloads(
        [
            ("drivers_sex_rates", "rates by sex and age"),
            ("drivers_sex_ratios", "men against women"),
            ("drivers_sex_trend", "by year, 2014–2024"),
            ("drivers_sex_travel", "the MOVILIA travel bracket"),
        ]
    )
    return section, {"involved": involved, "fatality": fatality}


# --------------------------------------------------------------------------- speed


def page_speed(captions: dict[str, str]) -> str:
    numbers = _speed_numbers()
    pooled, all_roads = numbers["pooled"], numbers["all_roads"]
    adjusted = pooled.loc["adjusted"]
    last = int(all_roads.index.max())
    latest = all_roads.loc[last]
    shares = read_table("q9_infraction_shares")
    status = shares[shares.zone == "all"].set_index("year")
    first_status, last_status = int(status.index.min()), int(status.index.max())

    body = key_figures(
        [
            (
                f"Share of crashes, {last}",
                _fmt_pct(float(latest.share_of_crashes), 0),
                "with inappropriate speed recorded",
            ),
            (
                f"Share of deaths, {last}",
                _fmt_pct(float(latest.share_of_deaths), 0),
                "in those crashes",
            ),
            (
                "Deaths per crash, same road",
                _times(float(adjusted.rate_ratio)),
                f"{_times(float(adjusted.crude_ratio))} before road type is allowed for",
            ),
            (
                "Drivers with no speed record",
                _fmt_pct(float(status.loc[last_status, "share_unknown"]), 0),
                f"{_fmt_pct(float(status.loc[first_status, 'share_unknown']), 0)} in "
                f"{first_status}",
            ),
        ]
    )
    urban = pooled.loc["urban"]
    other = pooled.loc["other_interurban"]
    dual = pooled.loc["dual_carriageway"]
    body += (
        '<p class="answer">Crashes in which the police recorded inappropriate speed are a small '
        f"share of injury crashes, {_fmt_pct(float(latest.share_of_crashes), 0)} in {last}, and "
        f"a large share of deaths, {_fmt_pct(float(latest.share_of_deaths), 0)}. Per crash they "
        f"kill {_times(float(adjusted.crude_ratio))} as many people as the rest. About half of "
        "that is where they happen: speed crashes concentrate on conventional interurban roads, "
        "where every crash is more often fatal. Compared on the same kind of road in the same "
        f"year the ratio is {_ratio_ci(float(adjusted.rate_ratio), float(adjusted.ratio_low), float(adjusted.ratio_high))}.</p>"
    )
    body += figure(
        "f1_speed_severity",
        "Ratio of deaths per 100 injury crashes, speed recorded against not, by road type",
        captions,
    )
    rows = []
    for key in ("urban", "motorway", "dual_carriageway", "other_interurban"):
        row = pooled.loc[key]
        rows.append(
            {
                "Road type": row.road_type_label,
                "Speed crashes": row.speed_crashes,
                "Deaths per 100, speed recorded": row.speed_deaths_per_100,
                "Deaths per 100, other crashes": row.other_deaths_per_100,
                "Ratio": _ratio_ci(
                    float(row.rate_ratio), float(row.ratio_low), float(row.ratio_high)
                ),
            }
        )
    body += table(
        pd.DataFrame(rows),
        "Injury crashes 2016–2023 in Spain without Cataluña and País Vasco. Sources: DGT "
        "Informe temático Factor Velocidad and crash microdata for the same provinces",
        {
            "Speed crashes": "int",
            "Deaths per 100, speed recorded": "dec2",
            "Deaths per 100, other crashes": "dec2",
        },
    )
    body += (
        "<p>The ratio is not the same everywhere. On urban streets, where an ordinary injury "
        "crash rarely kills, a crash with speed recorded kills "
        f"{_times(float(urban.rate_ratio))} as often; on conventional interurban roads "
        f"{_times(float(other.rate_ratio))}; on dual carriageways "
        f"{_times(float(dual.rate_ratio))}. The single adjusted ratio averages over that "
        "variation, and the page leads with it only because it is the fairest one-number "
        "answer.</p>"
    )

    body += "<h2>What the ratio can and cannot mean</h2>"
    body += (
        "<p>Speed here is a concurrent factor written by a police officer after the crash, not a "
        "measured speed. Two biases pull on the ratio in opposite directions. A fatal crash is "
        "investigated more thoroughly, so speed is more likely to be found and recorded when "
        "someone has died: that inflates the ratio. Speed that was present but not recorded "
        "sits in the comparison group: that deflates it. Neither can be measured from these "
        "tables. What the data do support is the direction and rough size: where speed is "
        "judged to have played a part, a crash is about twice as likely to kill, on the same "
        "kind of road. That is consistent with what the physics of impact energy predicts. It is "
        "not an estimate of how many deaths speed caused.</p>"
    )
    body += (
        "<p>The report covers Spain without Cataluña and País Vasco, which keep their own "
        "records. Its totals for that scope are reproduced exactly by the crash microdata "
        "restricted to the same provinces, every year from 2016 to 2023; that check is what "
        "allows the report's speed-related crashes to be set against microdata totals for road "
        "types the report does not total.</p>"
    )

    body += "<h2>A published series that changes meaning in 2016</h2>"
    body += figure(
        "c3_speed_status",
        f"Drivers in injury crashes by recorded speed status, {first_status}–{last_status}",
        captions,
    )
    known_first = float(status.loc[first_status, "share_among_known"])
    known_last = float(status.loc[last_status, "share_among_known"])
    all_first = float(status.loc[first_status, "share_speed_infraction"])
    all_last = float(status.loc[last_status, "share_speed_infraction"])
    body += (
        "<p>DGT's driver tables record, for each driver in an injury crash, whether the police "
        f"noted a speed infraction. In {first_status}, "
        f"{_fmt_pct(status.loc[first_status, 'share_unknown'], 0)} of drivers had no speed "
        f"status recorded. In 2016 that jumped to {_fmt_pct(status.loc[2016, 'share_unknown'], 0)} "
        "and it has stayed there. The two obvious readings of the table now point in opposite "
        "directions: the share of <em>all</em> drivers with a speed infraction fell from "
        f"{_fmt_pct(all_first)} to {_fmt_pct(all_last)}, while the share among drivers with a "
        f"record <em>rose</em> from {_fmt_pct(known_first)} to {_fmt_pct(known_last)}. Neither is "
        "a trend in speeding. The report's concurrent-factor series, used above, shows no break "
        'of that kind; the <a href="factors.html">factors page</a> tests it.</p>'
    )
    body += downloads(
        [
            ("speed_severity", "by year and road type"),
            ("speed_severity_pooled", "pooled 2016–2023 and adjusted"),
            ("q9_infraction_shares", "speed status in the driver tables"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Speed is recorded in a small share of injury crashes and a large share of deaths. On "
        "the same kind of road in the same year, a crash with speed recorded kills about twice "
        "as often as one without, and on urban streets far more. The data support speed as a "
        "severity factor of that order. They do not support a count of deaths caused by speed, "
        "because the record is a judgement made after the fact, and they do not support a "
        "trend in speeding from DGT's driver tables, which change meaning in 2016."
    )
    body += limits(
        "The concurrent-factor record is the police's judgement, may name several factors for "
        "one crash, and is not a measured speed. The report excludes Cataluña and País Vasco. "
        "The road-type comparison starts in 2016, where the microdata start, and the adjusted "
        "ratio is overdispersed because the urban ratio is so different from the rest."
    )
    return render_page(
        "speed",
        "Speed as a severity factor",
        "How much deadlier is a crash when speed is involved, on the same kind of road? About "
        "twice, with two biases the data cannot measure pulling in opposite directions.",
        body,
    )


# --------------------------------------------------------------------------- factors


FACTOR_ORDER = (
    "Alcohol",
    "Inappropriate speed",
    "Distraction or inattention",
    "Illegal manoeuvres",
    "Drugs",
)


def page_factors(captions: dict[str, str]) -> str:
    numbers = _factor_numbers()
    windows, changes = numbers["windows"], numbers["changes"]
    alcohol_inter = _window(windows, "interurban", "Alcohol", 2023)
    alcohol_urban = _window(windows, "urban", "Alcohol", 2023)
    speed_all = _window(windows, "all", "Inappropriate speed", 2023)
    distraction_inter = _window(windows, "interurban", "Distraction or inattention", 2023)
    urban_distraction = changes[
        (changes.zone == "urban") & (changes.factor == "Distraction or inattention") & changes.jump
    ]
    manoeuvres = _window(windows, "interurban", "Illegal manoeuvres", 2023)
    n_breaks = int(changes.is_break.sum())
    drugs = numbers["shares"].xs(("all", "Drugs"), level=["zone", "factor"]).crashes
    drugs_peak_year = int(drugs.idxmax())
    drugs_multiple = float(drugs.max() / drugs.loc[drugs.index.min()])

    body = key_figures(
        [
            (
                "Alcohol, interurban",
                f"{_fmt_pct(float(alcohol_inter.share_first))} → "
                f"{_fmt_pct(float(alcohol_inter.share_last))}",
                f"of injury crashes, {int(alcohol_inter.first_year)}–"
                f"{int(alcohol_inter.last_year)}, no break",
            ),
            (
                "Inappropriate speed, all roads",
                f"{_fmt_pct(float(speed_all.share_first))} → "
                f"{_fmt_pct(float(speed_all.share_last))}",
                f"{int(speed_all.first_year)}–{int(speed_all.last_year)}, no break",
            ),
            (
                "Urban distraction",
                f"{len(urban_distraction)} breaks",
                "in "
                + _join([str(int(year)) for year in urban_distraction.to_year])
                + ": not comparable across",
            ),
            ("Drugs", "not comparable", "too few crashes and a collapse in 2020"),
        ]
    )
    body += (
        '<p class="answer">DGT publishes, for each year, how many injury crashes had each of '
        "five concurrent factors recorded by the police. Before any trend is read, every "
        "year-to-year change in each factor's share is tested for a recording break: a jump or "
        "fall of more than a quarter in a single year, which no change in behaviour produces "
        f"across tens of thousands of crashes. {n_breaks} of the "
        f"{len(changes)} year-to-year changes fail that test or are too small to test. Within "
        "the runs that pass, two trends are clear. Recorded alcohol rose on interurban roads, "
        f"from {_fmt_pct(float(alcohol_inter.share_first))} to "
        f"{_fmt_pct(float(alcohol_inter.share_last))} of crashes between "
        f"{int(alcohol_inter.first_year)} and {int(alcohol_inter.last_year)}, and recorded "
        f"inappropriate speed fell, from {_fmt_pct(float(speed_all.share_first))} to "
        f"{_fmt_pct(float(speed_all.share_last))} of all injury crashes.</p>"
    )
    body += figure(
        "f2_factor_shares",
        "Share of injury crashes with each factor recorded, broken at recording breaks",
        captions,
    )
    shown = windows[(windows.zone != "all") & (windows.n_years >= 3)].copy()
    shown["order"] = shown.factor.map({name: i for i, name in enumerate(FACTOR_ORDER)})
    shown = shown.sort_values(["order", "zone", "first_year"])
    rows = [
        {
            "Factor": row.factor,
            "Zone": row.zone_label,
            "Comparable years": f"{int(row.first_year)}–{int(row.last_year)}",
            "Share, first year": row.share_first,
            "Share, last year": row.share_last,
            "Change in share": _signed_pct(float(row.change_in_share), 0),
        }
        for row in shown.itertuples(index=False)
    ]
    body += table(
        pd.DataFrame(rows),
        "Runs of three or more comparable years, by factor and zone. Source: DGT Informe "
        "temático Factor Velocidad, Spain without Cataluña and País Vasco",
        {"Share, first year": "pct", "Share, last year": "pct"},
    )
    body += (
        "<p>The alcohol rise on interurban roads runs across the whole decade without a break, "
        "and the urban series rises too once its own 2016 break is set aside, from "
        f"{_fmt_pct(float(alcohol_urban.share_first))} in {int(alcohol_urban.first_year)} to "
        f"{_fmt_pct(float(alcohol_urban.share_last))}. More recorded alcohol can mean more "
        "drinking drivers or more testing after a crash; DGT's enforcement statistics, which "
        "would tell the two apart, are not in these files. Interurban distraction is stable at "
        f"about {_fmt_pct(float(distraction_inter.share_last), 0)} of crashes. Illegal "
        "manoeuvres, a composite of priority, distance, overtaking and negligent driving, rose "
        f"on interurban roads from {_fmt_pct(float(manoeuvres.share_first), 0)} to "
        f"{_fmt_pct(float(manoeuvres.share_last), 0)}, most of it before 2018, which passes "
        "the rule but is the kind of drift a gradual change in recording also produces.</p>"
    )
    body += (
        "<p>Three series fail. Urban distraction jumps by two thirds in 2016 and falls by more "
        "than half in 2019, while the interurban series barely moves: those are changes in how "
        "town police forces recorded it. Urban alcohol has the same 2016 jump. Drugs are "
        f"recorded in at most {_fmt_int(drugs.max())} crashes a year, climb "
        f"{drugs_multiple:.0f}-fold from {int(drugs.index.min())} to {drugs_peak_year} and "
        "collapse in 2020: nothing about drug-driving can be read from them. 2016 is also the year the "
        "driver tables stop recording a speed status for half of all drivers, which is why it "
        "keeps appearing.</p>"
    )
    body += downloads(
        [
            ("factor_shares", "shares by year, zone and factor"),
            ("factor_changes", "every year-to-year change and the break test"),
            ("factor_windows", "comparable runs"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Of DGT's five recorded factors, three can be compared across years once recording "
        "breaks are taken out: recorded alcohol has risen on interurban roads, recorded "
        "inappropriate speed has fallen, and interurban distraction has held steady. Urban "
        "distraction and urban alcohol can only be compared within their own runs of years, and "
        "drugs cannot be compared at all. None of these shares is a measure of how often "
        "drivers drink, speed or look at a phone; each is how often the police recorded it in a "
        "crash that injured someone."
    )
    body += limits(
        "A crash can have several factors recorded, so the shares do not add up. The rule for "
        "a break is a threshold, not a test with a known error rate; every change is published "
        "so another threshold can be applied. The report covers Spain without Cataluña and País "
        "Vasco and ends in 2023. It gives crashes by factor but not deaths, so the severity of "
        "alcohol or distraction crashes cannot be compared the way speed is."
    )
    return render_page(
        "factors",
        "Alcohol, distraction and other recorded factors",
        "Which of DGT's recorded crash factors can be compared from year to year, and what do "
        "the comparable ones show?",
        body,
    )


def _ordinal(value: int) -> str:
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth"}
    return words.get(value, f"{value}th")


# --------------------------------------------------------------------------- severity

# Original research behind the mechanisms box. Peer-reviewed papers only, cited so a reader can
# check them; none of them is evidence about Spain, and the page says so.
LITERATURE = {
    "theofilatos": (
        "Theofilatos & Yannis (2014), “A review of the effect of traffic and weather "
        "characteristics on road safety”, <i>Accident Analysis &amp; Prevention</i> 72, 244–256",
        "https://doi.org/10.1016/j.aap.2014.06.017",
    ),
    "ahmed": (
        "Ahmed &amp; Ghasemzadeh (2018), “The impacts of heavy rain on speed and headway "
        "behaviors”, <i>Transportation Research Part C</i> 91, 371–384",
        "https://doi.org/10.1016/j.trc.2018.04.012",
    ),
    "kilpelainen": (
        "Kilpeläinen &amp; Summala (2007), “Effects of weather and weather forecasts on driver "
        "behaviour”, <i>Transportation Research Part F</i> 10(4), 288–299",
        "https://doi.org/10.1016/j.trf.2006.11.002",
    ),
    "elvik": (
        "Elvik, Vadeby, Hels &amp; van Schagen (2019), “Updated estimates of the relationship "
        "between speed and road safety”, <i>Accident Analysis &amp; Prevention</i> 123, 114–122",
        "https://doi.org/10.1016/j.aap.2018.11.014",
    ),
    "rosen": (
        "Rosén &amp; Sander (2009), “Pedestrian fatality risk as a function of car impact speed”, "
        "<i>Accident Analysis &amp; Prevention</i> 41, 536–542",
        "https://doi.org/10.1016/j.aap.2009.02.002",
    ),
}


def _cite(key: str) -> str:
    text, url = LITERATURE[key]
    return f'<a href="{url}">{text}</a>'


def page_severity(captions: dict[str, str]) -> str:
    numbers = _severity_numbers()
    adverse = numbers["adverse"]
    coefficients = numbers["coefficients"]
    fatal = coefficients[coefficients.outcome == "fatal"].set_index(["predictor", "level"])
    serious_adverse = read_table("q3_adverse_conditions")
    serious_adverse = serious_adverse[serious_adverse.outcome == "serious"].set_index(
        ["variant", "level"]
    )

    def orr(variant: str, level: str, frame=adverse) -> str:
        row = frame.loc[(variant, level)]
        return f"{row.odds_ratio:.2f} ({row.or_low:.2f}–{row.or_high:.2f})"

    wet_alone = float(adverse.loc[("no_weather", "wet"), "odds_ratio"])
    junction_full = float(adverse.loc[("full", "at a junction"), "odds_ratio"])

    body = key_figures(
        [
            ("Injury crashes modelled", f"{numbers['n']:,}", "2016–2024, none dropped"),
            ("Fatal", _fmt_pct(numbers["fatal_share"], 2), "at least one death within 30 days"),
            (
                "Wet road, fatal odds",
                f"{wet_alone:.2f}×",
                "against a dry road, everything else held constant",
            ),
            (
                "Holdout discrimination",
                f"{numbers['auc_fatal']:.2f}",
                "area under the ROC curve, 2023–2024 scored by a 2016–2022 fit",
            ),
        ]
    )

    body += (
        '<p class="answer">Once an injury crash has happened, the conditions a driver would '
        "call dangerous go with a <em>lower</em> chance that someone dies. A wet road carries "
        f"{wet_alone:.2f} times the odds of a death of a dry one, a junction {junction_full:.2f} "
        "times the odds of a stretch away from one. Rain and a wet surface are one effect counted "
        "twice, worth about "
        f"{wet_alone:.2f} on its own. All of this concerns how badly a crash ends, given that one "
        "has happened. It says nothing about how often crashes happen.</p>"
    )

    body += "<h2>Testing the finding</h2>"
    body += (
        "<p>The models are two logistic regressions on every injury crash of 2016 to 2024, "
        "one for a death and one for a death or a hospitalisation. The predictors are the "
        "circumstances the police record: zone, road type, crash type, junction, lighting, "
        "weather, surface, alignment, time of day, weekend, number of vehicles and year.</p>"
        "<p>The first objection is that weather and road surface measure much the same thing, so "
        "a model carrying both splits one effect between two columns. That is what happens. With "
        f"surface dropped, rain moves from {orr('full', 'rain')} to {orr('no_surface', 'rain')}. "
        f"With weather dropped, a wet surface moves from {orr('full', 'wet')} to "
        f"{orr('no_weather', 'wet')}. The right reading is a single wet-conditions effect of "
        f"about {wet_alone:.2f}.</p>"
    )
    body += (
        "<p>The second objection is that adverse weather falls in particular places. Fitting "
        "interurban roads and urban streets separately holds the road context fixed instead of "
        f"adjusting for it. The wet-surface effect stays: {orr('interurban', 'wet')} on interurban "
        f"roads and {orr('street', 'wet')} on urban streets. The junction effect, "
        f"{orr('full', 'at a junction')} overall, is present in every stratum too. Hail and snow "
        f"behave differently. They give {orr('full', 'hail or snow')} in the full model but "
        f"{orr('conventional', 'hail or snow')} on conventional roads alone, where the interval "
        "covers no effect at all.</p>"
    )
    body += figure(
        "s2_adverse_conditions",
        "Odds ratios for wet, rain, hail or snow and junctions under eight model variants",
        captions,
    )

    variants = read_table("q3_adverse_conditions")
    shown = variants[variants.outcome.isin(["fatal", "serious"])].copy()
    shown["ci"] = shown.apply(
        lambda r: f"{r.odds_ratio:.2f} ({r.or_low:.2f}–{r.or_high:.2f})", axis=1
    )
    wide = shown.pivot_table(
        index=["variant_label", "level"], columns="outcome", values="ci", aggfunc="first"
    ).reset_index()
    wide = wide.rename(
        columns={
            "variant_label": "Model",
            "level": "Condition",
            "fatal": "Fatal (95% interval)",
            "serious": "Serious (95% interval)",
        }
    )
    order = list(dict.fromkeys(variants.variant_label))
    conditions = ["wet", "rain", "hail or snow", "at a junction"]
    wide["_model"] = wide.Model.map({label: i for i, label in enumerate(order)})
    wide["_condition"] = wide.Condition.map({name: i for i, name in enumerate(conditions)})
    wide = wide.sort_values(["_condition", "_model"]).drop(columns=["_model", "_condition"])
    body += table(
        wide,
        "Odds ratios for the adverse conditions under every model variant, both outcomes. A blank "
        "cell is a level the variant does not contain",
    )
    body += downloads(
        [
            ("q3_adverse_conditions", "sensitivity fits"),
            ("q3_adverse_composition", "where hail and snow crashes happen"),
            ("q3_adverse_exclusions", "hail and snow with the top provinces removed"),
        ]
    )

    composition = read_table("q3_adverse_composition")
    snow = composition[(composition.level == "hail or snow") & (composition.dimension == "zone")]
    interurban_share = float(snow[snow.category == "interurban road"].share_of_level.iloc[0])
    exclusions = read_table("q3_adverse_exclusions")
    widest = exclusions.iloc[-1]
    body += (
        f"<p>Hail and snow are only "
        f"{int(adverse.loc[('full', 'hail or snow'), 'n_level']):,} crashes, and "
        f"{interurban_share:.0%} of them are on interurban roads, so it is fair to suspect a few "
        "mountain provinces. That is not the explanation. Dropping the three provinces that "
        f"record most of them moves the odds ratio only to {widest.odds_ratio:.2f} "
        f"({widest.or_low:.2f}–{widest.or_high:.2f}). The road type is what moves it, and on "
        "conventional roads alone the effect disappears.</p>"
    )

    body += "<h2>Why might visibly dangerous conditions produce less severe crashes?</h2>"
    body += note(
        "These are mechanisms the literature proposes, not results this analysis demonstrates. "
        "The DGT microdata carry no speed, no driver and no vehicle information, so nothing here "
        "can show which of them is at work."
    )
    body += (
        "<p>Drivers appear to compensate when the risk is visible. Naturalistic-driving data show "
        f"lower speeds and longer headways in heavy rain ({_cite('ahmed')}); survey work finds "
        "drivers also postpone or re-route trips, avoid overtaking and drive more cautiously when "
        f"the weather is bad or forecast to be ({_cite('kilpelainen')}). A modest speed reduction "
        "matters more than it sounds, because the relationship between speed and fatal outcomes "
        f"is steeply non-linear ({_cite('elvik')}; for pedestrians, {_cite('rosen')}). At "
        "junctions the plausible mechanisms are similar and more mundane: approach speeds are "
        "lower, conflict points are expected and signalled, and drivers are more often already "
        "braking when the impact happens.</p>"
    )
    body += (
        "<p>Compensation is not the only candidate. Which trips are made changes with the "
        "weather, and so does who makes them. Traffic is denser and slower. The mix of vehicles "
        "and of road types differs. A police officer's judgement of the conditions is recorded "
        "after the event. The review literature on weather and road safety treats all of these as "
        f"open ({_cite('theofilatos')}).</p>"
    )

    body += "<h2>The other coefficients</h2>"
    body += figure(
        "s1_forest_fatal",
        "Odds ratios for a fatal outcome by crash circumstance, with 95% intervals",
        captions,
    )
    head_on = fatal.loc[("crash_type", "head-on collision")]
    pedestrian = fatal.loc[("crash_type", "pedestrian struck")]
    body += (
        "<p>The large effects are the expected ones. A head-on collision carries "
        f"{head_on.odds_ratio:.1f} times the odds of a death of a side collision, and a pedestrian "
        f"struck {pedestrian.odds_ratio:.1f} times, against {junction_full:.2f} for a junction and "
        f"{wet_alone:.2f} for a wet road. Fitted on 2016 to 2022 and scored on 2023 and 2024, the "
        f"fatal model reaches an area under the ROC curve of {numbers['auc_fatal']:.2f} and the "
        f"serious model {numbers['auc_serious']:.2f}.</p>"
    )
    profiles = read_table("q3_profiles").rename(
        columns={"profile": "Crash profile", "fatal": "Fatal", "serious": "Serious"}
    )
    body += table(
        profiles,
        "Predicted probability of each outcome for named crash profiles (2024; circumstances not "
        "named are at their reference level)",
        {"Fatal": "pct2", "Serious": "pct"},
    )
    body += downloads(
        [
            ("q3_model_coefficients", "all coefficients"),
            ("q3_marginal_effects", "average marginal effects"),
            ("q3_calibration", "holdout calibration"),
            ("q3_year_stability", "year-by-year refits"),
            ("q3_groupings", "how DGT's codes map to model levels"),
        ]
    )

    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Wet conditions and junctions are associated with materially lower odds that an injury "
        f"crash kills someone: about {wet_alone:.2f} and {junction_full:.2f} times the reference "
        "odds, holding the other recorded circumstances constant. Both survive every sensitivity "
        "fit run here, so treat them as established associations. The hail and snow result does "
        "not survive, so treat it as unresolved. None of this identifies a mechanism, and none of "
        "it says anything about how likely a crash is in the first place."
    )

    stability = read_table("q3_year_stability")
    outside = int(
        (~stability[stability.outcome == "fatal"].within_full_interval.astype(bool)).sum()
    )
    total = int(len(stability[stability.outcome == "fatal"]))
    body += limits(
        "The microdata are one row per crash with no driver, vehicle or person fields, so nothing "
        "here says who was driving, how fast or whether alcohol was involved, and the factor "
        "interactions this project was first framed around cannot be estimated. A model of "
        "recorded crashes describes which recorded crashes end badly, not the risk of crashing. "
        f"Refitting one year at a time, {outside} of the {total} year-by-term estimates fall "
        "outside the full model's interval, mostly in 2024, when DGT changed how urban road types "
        'are coded (see the <a href="data.html">data page</a>); road type and zone have to be read '
        "together. Four levels that stand for a missing value track which force recorded the "
        "crash rather than what the road was like, and are marked as such in the full coefficient "
        "table."
    )
    return render_page(
        "severity",
        "Crash severity",
        "Which recorded circumstances make an injury crash fatal, and why the "
        "dangerous-looking ones point the wrong way.",
        note(SUPPORTING_NOTES["severity"]) + body,
    )


# --------------------------------------------------------------------------- older drivers


def page_drivers(captions: dict[str, str]) -> str:
    numbers = _age_numbers()
    ratios, rates, contrast, company = (
        numbers["ratios"],
        numbers["rates"],
        numbers["contrast"],
        numbers["company"],
    )
    km = read_table("q7_km_by_owner_age").set_index("band")
    year = driver_risk.KM_YEAR

    def ratio_text(measure: str, band: str) -> str:
        row = ratios.loc[(measure, band)]
        return f"{row.ratio:.2f}× ({row.low:.2f}–{row.high:.2f})"

    deaths_75 = ratios.loc[("deaths_per_bn_km", "75+")]
    involved_75 = ratios.loc[("involved_per_bn_km", "75+")]
    fatality_75 = ratios.loc[("deaths_per_1000_involved", "75+")]
    sex_section, sex = _sex_section(captions)
    men_involved, men_fatality = sex["involved"], sex["fatality"]

    body = key_figures(
        [
            (
                "Crashes per kilometre, 75+",
                _times(float(involved_75.ratio)),
                "involvement rate against drivers aged 35–54",
            ),
            (
                "Deaths per crash, 75+",
                _times(float(fatality_75.ratio)),
                "killed per 1,000 drivers involved, against 35–54",
            ),
            (
                "Crashes per licence, men",
                _times(float(men_involved.ratio)),
                "male against female car drivers",
            ),
            (
                "Deaths per crash, men",
                _times(float(men_fatality.ratio)),
                "killed once involved, against women",
            ),
        ]
    )

    body += (
        '<p class="answer">Older drivers are not crashing more often for the distance they '
        "drive. Per kilometre, car drivers aged 75 and over are involved in injury crashes "
        f"{ratio_text('involved_per_bn_km', '75+')} as often as drivers aged 35 to 54, which is "
        "to say about as often. The difference is in the consequence. Once involved, they are "
        f"killed {ratio_text('deaths_per_1000_involved', '75+')} as often. Young drivers are the "
        f"mirror image, with {ratio_text('involved_per_bn_km', '18-34')} the involvement rate per "
        f"kilometre and {ratio_text('deaths_per_1000_involved', '18-34')} the chance of dying "
        "once involved. Sex splits the same way: male car drivers are in injury crashes "
        f"{_times(float(men_involved.ratio))} as often as women per licence holder, a gap of the "
        "size a difference in driving could produce, and are killed "
        f"{_times(float(men_fatality.ratio))} as often once they are.</p>"
    )

    body += figure(
        "a1_km_risk_by_age",
        "Car drivers by age: involvement per billion km, deaths per 1,000 involved, deaths per "
        "billion km",
        captions,
    )

    shown = rates.reset_index()[
        [
            "band_label",
            "n_cars",
            "billion_km",
            "mean_km_per_car",
            "drivers_involved",
            "involved_per_bn_km",
            "driver_deaths",
            "deaths_per_1000_involved",
            "deaths_per_bn_km",
        ]
    ].rename(
        columns={
            "band_label": "Age of driver (and of car owner)",
            "n_cars": "Cars owned",
            "billion_km": "Billion km",
            "mean_km_per_car": "Km per car",
            "drivers_involved": "Drivers involved",
            "involved_per_bn_km": "Involved per bn km",
            "driver_deaths": "Drivers killed",
            "deaths_per_1000_involved": "Killed per 1,000 involved",
            "deaths_per_bn_km": "Killed per bn km",
        }
    )
    body += table(
        shown,
        f"Car drivers and car kilometres by age band, {year}. Sources: DGT driver tables 4.1.1 and "
        f"4.2 (car rows) and Kilómetros anualizados recorridos por el parque móvil {year}",
        {
            "Cars owned": "int",
            "Billion km": "dec",
            "Km per car": "int",
            "Drivers involved": "int",
            "Involved per bn km": "dec0",
            "Drivers killed": "int",
            "Killed per 1,000 involved": "dec",
            "Killed per bn km": "dec2",
        },
    )

    body += "<h2>Residents, licences, crashes, kilometres</h2>"
    body += figure(
        "a2_denominator_contrast",
        "The same car-driver deaths under four denominators, as ratios to drivers aged 35–54",
        captions,
    )
    residents_75 = contrast.loc[("residents", "75+")]
    licence_75 = contrast.loc[("licence_holders", "75+")]
    involved_75_contrast = contrast.loc[("drivers_involved", "75+")]
    body += (
        "<p>DGT reports road deaths of people 65 and over per million inhabitants of that age. "
        f"On that denominator drivers 75 and over die {residents_75.ratio:.2f} times as often as "
        "drivers aged 35 to 54, barely more, because most people over 75 do not drive at all. Per "
        f"licence holder the ratio is {licence_75.ratio:.2f}, because holding a licence is not "
        "the same as driving. "
        f"Per driver already in a crash it is {involved_75_contrast.ratio:.2f} and per kilometre "
        f"{deaths_75.ratio:.2f}. The numerator is identical in all four; the denominator is the "
        "entire difference, which is why it has to be named every time. The last two agree because "
        "involvement per kilometre is about the same at both ages. That is the finding above, "
        "seen from the other side.</p>"
    )
    licence = read_table("q7_licence_share")
    latest_licence = licence[licence.year == licence.year.max()].set_index(["band", "sex"])
    year_licence = int(licence.year.max())
    body += (
        f"<p>That is also why the per-resident rate says so little about driving. In "
        f"{year_licence}, {_fmt_pct(float(latest_licence.loc[('75+', 'total'), 'licence_share']), 0)} "
        f"of residents aged 75 and over held a licence against "
        f"{_fmt_pct(float(latest_licence.loc[('45-54', 'total'), 'licence_share']), 0)} of those "
        f"aged 45–54, and the gap between the sexes widens with age: "
        f"{_fmt_pct(float(latest_licence.loc[('75+', 'male'), 'licence_share']), 0)} of men over 74 "
        f"hold one and {_fmt_pct(float(latest_licence.loc[('75+', 'female'), 'licence_share']), 0)} "
        "of women. A per-resident rate for older women is describing passengers and pedestrians "
        "far more than drivers.</p>"
    )
    body += downloads(
        [
            ("q7_km_rates", "rates by band"),
            ("q7_km_ratio", "ratios to the 35–54 baseline"),
            ("q7_denominator_contrast", "the four denominators"),
            ("q7_km_by_owner_age", "kilometres by owner age"),
            ("q7_company_km", "company-car sensitivity"),
            ("q7_licence_share", "licence holding by age and sex"),
        ]
    )

    body += "<h2>What the denominator measures</h2>"
    company_share = float(km.loc[driver_risk.COMPANY_BAND, "share_of_km"])
    working = company.loc[("to_working_age", "75+")]
    body += (
        f"<p>DGT's {year} kilometre release estimates, for the whole circulating fleet, how far "
        "each vehicle category is driven, and breaks it down by the age band of the registered "
        "owner. That is what makes this comparison possible and what makes the middle-aged "
        "baseline and the older groups directly comparable: the same source, the same year, the "
        "same construction. It is the <em>owner's</em> age, not the driver's. A car registered to "
        "a person of 75 may be driven by a relative, and a car registered to a company has no age "
        f"at all: those are {company_share:.0%} of all car kilometres and they leave the "
        "denominator while their drivers stay in the numerator. Since company cars are mostly "
        "driven by people of working age, leaving them out understates middle-aged exposure and "
        "so understates this comparison: spreading those kilometres over the bands from 18 to 64 "
        f"would raise the 75-and-over ratio from {deaths_75.ratio:.2f} to "
        f"{float(working.ratio_to_reference):.2f}.</p>"
    )
    body += sex_section
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Splitting the question in two changes the answer, for age and for sex alike. Older car "
        "drivers are not more likely to crash for the distance they cover; drivers aged 75 and "
        f"over are involved {ratio_text('involved_per_bn_km', '75+')} as often per kilometre as "
        f"drivers aged 35 to 54, and are {ratio_text('deaths_per_1000_involved', '75+')} as "
        "likely to be killed once involved. Men crash somewhat more often per licence, by about "
        "as much as the one travel survey by sex suggests they drive more, and are killed "
        f"{_times(float(men_fatality.ratio))} as often once in a crash. In both cases the excess "
        "in deaths comes from what a crash does to the driver, not from how often the driver "
        "crashes. The data show that split, not its causes: physical frailty for older drivers, "
        "and for men the roads, hours and speeds at which they crash, are candidate "
        "explanations these tables cannot separate."
    )

    body += limits(
        "Owner age is a proxy for driver age, and the two diverge most in the households where a "
        "car is shared. The kilometres are modelled from roadworthiness-inspection odometer "
        "readings and are valid for aggregates only; the intervals here come from the crash "
        "counts and treat them as known. The numerator counts drivers of cars on Spanish roads, "
        "including foreign-registered ones, while the denominator covers Spanish-registered cars "
        f"only. The kilometre comparison is one year, {year}. No source measures kilometres by "
        "sex, so the sex comparison uses licences and a 2006 travel survey that counts "
        "passengers; only the fatality ratio once involved is free of that limit."
    )
    return render_page(
        "drivers",
        "Age and sex: crashing, and dying once it happens",
        "Are older drivers, or male drivers, more dangerous? Split the question into crashing "
        "for the driving done and dying once the crash happens, and the halves disagree.",
        body,
    )


# --------------------------------------------------------------------------- vehicles


def page_vehicles(captions: dict[str, str]) -> str:
    summary = read_table("q6_summary_2022").set_index("group")
    split = read_table("q6_van_light_truck_split").set_index("group")
    car, truck, bike = summary.loc["car"], summary.loc["heavy_truck"], summary.loc["motorcycle"]
    per_vehicle = float(
        truck.fatal_involvement_per_100k_vehicles / car.fatal_involvement_per_100k_vehicles
    )
    per_km = float(truck.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
    bike_per_km = float(bike.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)

    body = key_figures(
        [
            ("Heavy truck vs car, per vehicle", f"{per_vehicle:.1f}×", "in a fatal crash, 2022"),
            (
                "Heavy truck vs car, per kilometre",
                f"{per_km:.1f}×",
                "the same crashes, distance as the divisor",
            ),
            ("Motorcycle vs car, per kilometre", f"{bike_per_km:.0f}×", "in a fatal crash"),
            (
                "Truck occupants killed",
                f"{float(truck.occupant_deaths_per_fatal_involvement):.2f}",
                "per fatal crash a heavy truck is in; 0.93 for a motorcycle",
            ),
        ]
    )
    body += (
        f'<p class="answer">A heavy truck is in a fatal crash {per_vehicle:.1f} times as often as '
        f"a car per vehicle on the road, and {per_km:.1f} times as often per kilometre driven. "
        "The gap between those two numbers is the difference between blaming the vehicle and "
        "describing how much it is used. Motorcycles move the other way. "
        f"They are driven little, so a modest rate per vehicle becomes {bike_per_km:.0f} times a "
        "car's rate once distance is the divisor.</p>"
    )
    body += figure(
        "v1_per_vehicle_vs_per_km",
        "Ranking of vehicle types in fatal crashes per vehicle and per kilometre",
        captions,
    )

    shown = summary.reset_index()[
        [
            "label",
            "n_vehicles",
            "km_per_vehicle",
            "vehicle_km_bn",
            "fatal_involvement_per_100k_vehicles",
            "fatal_involvement_per_bn_km",
            "occupant_deaths_per_bn_km",
            "occupant_deaths_per_fatal_involvement",
        ]
    ].rename(
        columns={
            "label": "Vehicle type",
            "n_vehicles": "Circulating",
            "km_per_vehicle": "Km per vehicle",
            "vehicle_km_bn": "Billion km",
            "fatal_involvement_per_100k_vehicles": "In fatal crashes per 100,000 vehicles",
            "fatal_involvement_per_bn_km": "In fatal crashes per bn km",
            "occupant_deaths_per_bn_km": "Own occupants killed per bn km",
            "occupant_deaths_per_fatal_involvement": "Own occupants killed per fatal crash",
        }
    )
    shown = shown.sort_values("In fatal crashes per bn km", ascending=False)
    body += table(
        shown,
        "Fleet, kilometres and fatal-crash rates by vehicle type, 2022. Sources: DGT statistical "
        "tables 2022; DGT, Kilómetros recorridos estimados a partir de la ITV 2022",
        {
            "Circulating": "int",
            "Km per vehicle": "int",
            "Billion km": "dec",
            "In fatal crashes per 100,000 vehicles": "dec",
            "In fatal crashes per bn km": "dec",
            "Own occupants killed per bn km": "dec",
            "Own occupants killed per fatal crash": "dec2",
        },
    )
    body += downloads(
        [
            ("q6_summary_2022", "rates by type"),
            ("q6_rates_2022", "rates with intervals, by zone and measure"),
            ("q6_vehicle_km_2022", "fleet and kilometres"),
            ("q6_vehicle_groups", "how the source categories map to these groups"),
            ("q6_van_light_truck_split", "vans and light trucks taken separately"),
        ]
    )

    body += "<h2>Who dies in the crash</h2>"
    body += (
        "<p>The last column of that table is the second half of the finding. When a motorcycle is "
        f"in a fatal crash, {float(bike.occupant_deaths_per_fatal_involvement):.2f} of its own riders "
        f"are killed on average; for a car {float(car.occupant_deaths_per_fatal_involvement):.2f}; for "
        f"a heavy truck {float(truck.occupant_deaths_per_fatal_involvement):.2f}. A fatal crash "
        "kills at least one person, so a figure of 0.18 means that in most fatal crashes involving "
        "a heavy truck the people killed were in the other vehicle or on foot. A truck's risk per "
        "kilometre is mostly a risk to other people, which is exactly what a measure built from "
        "its own occupants' deaths would miss.</p>"
    )
    van_gap = float(
        split.loc["light_truck", "fatal_involvement_per_bn_km"]
        / split.loc["van", "fatal_involvement_per_bn_km"]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Which vehicle looks most dangerous depends entirely on the divisor. Buses and heavy "
        "trucks lead per vehicle on the road; motorcycles and mopeds lead per kilometre driven, "
        "and by a wide margin. Neither ranking is wrong, but they answer different questions: "
        "per vehicle asks what a fleet of that size costs in fatal crashes, per kilometre asks "
        "what a journey of a given length costs. For heavy trucks the two rankings disagree "
        f"by a factor of {per_vehicle / per_km:.1f}, and most of the people killed are outside "
        "the truck."
    )

    body += limits(
        "Kilometres exist for 2022 only, so this is a cross-section, not a trend. They are "
        "modelled from inspection odometer readings, and DGT's own note says they are valid for "
        "aggregates rather than for individual vehicles. They are annualised over readings taken "
        "across 2014 to 2023, so they describe a normal year imputed to the 2022 fleet rather "
        "than 2022 travel. The two sides of the division do not cover quite the same vehicles: the "
        "crash counts include foreign-registered vehicles, and the kilometres include the "
        "distance Spanish vehicles drive abroad. Vans and light trucks are one group because the "
        f"crash record and the register split them differently; taken apart, light trucks would "
        f"show {van_gap:.0%} of a van's rate per kilometre, a gap with no plausible cause but the "
        "coding. The intervals come from the crash counts and treat the kilometres as known."
    )
    return render_page(
        "vehicles",
        "Vehicle risk per kilometre",
        "How different vehicle types look when the divisor is distance driven rather than the "
        "number of vehicles on the road.",
        body,
    )


# --------------------------------------------------------------------------- policy

CONFOUNDERS = [
    ("2003–2004", "The decline in road deaths steepens, before any of the measures below"),
    ("2005–2008", "Road-safety plan: automatic speed cameras rolled out on the main network"),
    ("1 July 2006", "Points-based driving licence in force (Ley 17/2005); the intervention"),
    (
        "2 December 2007",
        "Penal Code reform: speeding and drink-driving thresholds become offences (LO 15/2007)",
    ),
    ("2008–2009", "Recession; traffic and freight fall"),
]


def page_policy(captions: dict[str, str]) -> str:
    numbers = _policy_numbers()
    main, linear = numbers["main"], numbers["linear"]
    calendar, forecast = numbers["calendar"], numbers["forecast"]
    transitions = numbers["transitions"]
    trend = numbers["trend"]
    chosen = trend[trend.chosen].iloc[0]
    straight = trend[trend.label == "one linear trend"].iloc[0]
    true_calendar = numbers["true_calendar"]
    true_forecast = numbers["true_forecast"]
    true_transition = transitions[transitions.year == 2006].iloc[0]

    body = key_figures(
        [
            (
                "Level change at July 2006",
                _signed_pct(float(main.level_change)),
                f"{_signed_pct(float(main.level_low))} to {_signed_pct(float(main.level_high))}, "
                "preferred pre-trend",
            ),
            (
                "Under a straight pre-trend",
                _signed_pct(float(linear.level_change)),
                "the specification the pre-2006 months reject",
            ),
            (
                "Rank among July breaks",
                f"{int(true_calendar['rank'])} of {int(true_calendar.n_fits)}",
                "same model placed at July of other years",
            ),
            (
                "Rank on out-of-sample error",
                f"{int(true_forecast['rank'])} of {int(true_forecast.n_fits)}",
                "how abnormal the months after each July were",
            ),
        ]
    )
    body += (
        '<p class="answer">Something did happen to Spanish road deaths around July 2006, when the '
        "points-based licence came in. It is smaller and less exceptional than a straight-line "
        f"model says. Fitting the pre-trend the earlier months actually prefer cuts the step from "
        f"{_signed_pct(float(linear.level_change))} to {_signed_pct(float(main.level_change))} "
        f"({_signed_pct(float(main.level_low))} to {_signed_pct(float(main.level_high))}), and a "
        "forecast made before each July finds 2006 only the "
        f"{_ordinal(int(true_forecast['rank']))} most abnormal July of "
        f"{int(true_forecast.n_fits)}. What the series supports is a step of roughly seven per "
        "cent that no single measure can be credited with.</p>"
    )

    body += "<h2>How the pre-trend was chosen, and why it matters</h2>"
    body += figure(
        "p1_points_series",
        "Monthly road deaths 2000–2007 with the fitted model and two counterfactuals",
        captions,
    )
    body += (
        "<p>An interrupted time series fits the months before a change, projects them forward and "
        "asks whether the months after sit below. Everything therefore depends on what is "
        "projected. Earlier versions of this study used one straight trend through 2000–2006. "
        "Tested on the pre-intervention months alone, with no post-period involved, that "
        "straight line is worse than a trend with a single kink by "
        f"{float(straight.delta_aic):.0f} points "
        f"of AIC, and the kink the data pick is at {chosen.label.replace('knot at ', '')}, where "
        "the decline steepened. Put that kink in and the estimated step at July 2006 falls by "
        f"about {abs(float(linear.level_change) - float(main.level_change)) * 100:.0f} percentage "
        "points. The dotted line on the chart is the straight-line counterfactual; the gap "
        "between the two counterfactuals is the disagreement.</p>"
    )
    body += table(
        trend.assign(label=lambda f: f.label.str[0].str.upper() + f.label.str[1:])[
            ["label", "aic", "delta_aic"]
        ].rename(columns={"label": "Pre-trend", "aic": "AIC", "delta_aic": "Δ AIC"}),
        "Choosing the pre-trend on the months before July 2006 only: the best candidates, with "
        "the straight line for comparison. Lower AIC is better",
        {"AIC": "dec", "Δ AIC": "dec"},
    )

    body += "<h2>Was July 2006 unusual for a July?</h2>"
    body += (
        "<p>Spanish road deaths peak every July and August. A placebo distribution built by "
        "moving the break to arbitrary months cannot answer whether the summer of 2006 was "
        "unusual, so this one places the break at 1 July of every year with a clean window: the "
        "same model, the same 60 months before and 17 after, at Julys the points licence cannot "
        "explain.</p>"
    )
    body += figure(
        "p2_july_placebos",
        "Estimated level change at 1 July of each year, with July 2006 marked",
        captions,
    )
    others = calendar[~calendar.is_true].sort_values("level_change")
    runner_up = others.iloc[0]
    body += (
        f"<p>July 2006 is the largest fall of the {int(true_calendar.n_fits)}, but only just. "
        f"July {int(runner_up.year)} gives {_signed_pct(float(runner_up.level_change), 1)} and "
        f"July {int(others.iloc[1].year)} {_signed_pct(float(others.iloc[1].level_change), 1)}, "
        f"and the intervals overlap. Rank 1 of {int(true_calendar.n_fits)} is a one-sided "
        f"empirical p-value of about {1 / float(true_calendar.n_fits):.2f}: suggestive, not "
        "decisive.</p>"
    )

    body += "<h2>Two tests without a model</h2>"
    ranked = transitions[transitions["rank"].notna()]
    body += (
        "<p>Take the twelve months from each July and divide by the twelve months before it. Both "
        "sides then contain one of every calendar month, so seasonality cancels exactly and no "
        "model is involved. Across July 2006 that ratio is "
        f"{_signed_pct(math.expm1(float(true_transition.twelve_month_ratio)), 1)}"
        f", a large fall, and the {_ordinal(int(true_transition['rank']))} largest of the "
        f"{int(true_transition.n_ranked)} years that can be measured. Three years in the recession "
        "that followed were larger. The series was falling steeply either side of 2006, which is "
        "the same problem the pre-trend test found, seen without a regression.</p>"
    )
    largest = ranked.nsmallest(8, "twelve_month_ratio")
    show = pd.concat([largest, ranked[ranked.year == 2006]]).drop_duplicates("year")
    show = show.sort_values("twelve_month_ratio")[
        ["year", "jun_to_jul", "jul_to_aug", "aug_to_sep", "twelve_month_ratio", "rank"]
    ].copy()
    # The table carries log changes; the page prints them as percentage changes.
    for column in ("jun_to_jul", "jul_to_aug", "aug_to_sep", "twelve_month_ratio"):
        show[column] = show[column].map(math.expm1)
    show = show.rename(
        columns={
            "year": "Year",
            "jun_to_jul": "June → July",
            "jul_to_aug": "July → August",
            "aug_to_sep": "August → September",
            "twelve_month_ratio": "12 months after ÷ 12 before",
            "rank": "Rank",
        }
    )
    body += table(
        show,
        "The eight largest falls across a July, of the 27 years that can be measured. The last "
        "column has the same twelve calendar months on each side, so seasonality cancels; "
        "2019–2021 are left out because the pandemic breaks the comparison",
        {
            "Year": "year",
            "June → July": "pct0",
            "July → August": "pct0",
            "August → September": "pct0",
            "12 months after ÷ 12 before": "pct",
            "Rank": "int",
        },
    )
    body += (
        "<p>The second test fits the 60 months before each July, with a trend and seasonality "
        "and no intervention term, then forecasts the 17 months after it. The question is how far "
        "the "
        f"observed months fall below that forecast. After July 2006 they fall "
        f"{abs(float(true_forecast.log_ratio)) * 100:.0f}% below, which sounds decisive until the "
        f"same exercise is run at the other Julys: 2006 comes "
        f"{_ordinal(int(true_forecast['rank']))} of {int(true_forecast.n_fits)}. The months after "
        f"July {int(forecast.sort_values('z').iloc[0].year)} were further below their own forecast, "
        "and so were two other years. This is the single clearest reason not to report a twelve "
        "per cent policy effect.</p>"
    )
    body += downloads(
        [
            ("q8_points_calendar_placebo", "July placebos"),
            ("q8_points_forecast", "out-of-sample forecasts"),
            ("q8_points_transitions", "summer transitions"),
            ("q8_points_trend_choice", "pre-trend selection"),
            ("q8_points_sensitivity", "every specification"),
            ("q8_points_placebo", "the older arbitrary-month placebos"),
        ]
    )

    body += "<h2>Exposure, and everything else that changed</h2>"
    fuel = numbers["sensitivity"].loc["fuel"]
    toll = numbers["sensitivity"].loc["toll"]
    body += (
        "<p>A fall in deaths can be a fall in traffic. Two Spanish series are monthly and reach "
        "back past 2006: CORES's national road-fuel consumption, which covers every road, and the "
        "Ministerio de Transportes' vehicle-kilometres on the state toll-motorway network, which "
        "is a direct traffic measurement on a small and changing part of it. Adding either as a "
        f"covariate barely moves the estimate: {_signed_pct(float(fuel.level_change))} with "
        f"fuel and {_signed_pct(float(toll.level_change))} with toll traffic, against "
        f"{_signed_pct(float(main.level_change))} without either. Neither is vehicle-kilometres on all "
        "Spanish roads by month, which does not exist, so they rule out a traffic-volume "
        "explanation rather than measuring exposure properly.</p>"
    )
    body += table(
        pd.DataFrame(CONFOUNDERS, columns=["When", "What changed"]),
        "What else was happening around the intervention",
    )
    sensitivity = numbers["sensitivity"].reset_index()
    shown = sensitivity[
        ["label", "window", "level_change", "level_low", "level_high", "dispersion"]
    ]
    shown = shown.assign(
        interval=shown.apply(
            lambda r: (
                f"{_signed_pct(r.level_change, 1)} ({_signed_pct(r.level_low, 1)} to "
                f"{_signed_pct(r.level_high, 1)})"
            ),
            axis=1,
        )
    )[["label", "window", "interval", "dispersion"]].rename(
        columns={
            "label": "Specification",
            "window": "Window",
            "interval": "Level change (95% interval)",
            "dispersion": "Dispersion",
        }
    )
    body += table(
        shown, "The July 2006 level change under every specification", {"Dispersion": "dec2"}
    )

    body += "<h2>Conclusion</h2>"
    crosses = numbers["sensitivity"][numbers["sensitivity"].level_high > 0]
    body += conclusion(
        "Two different claims have to be kept apart. <strong>That the death series changed "
        f"unusually around July 2006</strong>: partly supported. A step of about "
        f"{abs(float(main.level_change)) * 100:.0f}% survives the specification the pre-period "
        "prefers and the largest of the calendar-matched July placebos, but the out-of-sample "
        "test and the seasonality-free transition both put 2006 inside the range of ordinary "
        "years. <strong>That the points licence caused it</strong>: not supported by this series "
        "at all. The speed-camera programme was rolling out over the same two years, the Penal "
        "Code reform followed seventeen months later, and the recession after that."
    )
    body += (
        f"<p>And the step is fragile. Of the {len(numbers['sensitivity'])} specifications in the "
        f"table above, {len(crosses)} give an interval that includes no change at all"
        + (
            ": " + _join([str(row.label).lower() for row in crosses.itertuples()]) + ". "
            if len(crosses)
            else ". "
        )
        + "Twelve per cent is not what this series supports; seven, with a wide interval, is "
        "about as much as it will carry.</p>"
    )
    body += limits(
        "Monthly deaths are overdispersed and serially correlated; standard errors are Newey–West "
        "with twelve lags and a negative-binomial fit is in the table above. Choosing the "
        "pre-trend by AIC on the pre-period is a selection step, so the table shows the "
        "alternatives: every knot from 2002 to 2005 gives between −6% and −10%, and a knot at "
        "January 2004 gives an interval that includes zero. A separate study of the January 2019 "
        "speed-limit cut on conventional roads is not published here: its control design fails a "
        "placebo break placed in January 2017, which produces a divergence of its own, so no "
        "claim can be made from it. Its fits are kept as evidence of the negative result "
        '(<a href="tables/q8_speed_placebo.csv">placebos</a>, '
        '<a href="tables/q8_speed_sensitivity.csv">specifications</a>).'
    )
    return render_page(
        "policy",
        "The July 2006 break",
        "Monthly road deaths fell around the points-based licence. How much of that was the "
        "policy, how much the trend already under way, and how much July?",
        note(SUPPORTING_NOTES["policy"]) + body,
    )


# --------------------------------------------------------------------------- context


# --------------------------------------------------------------------------- data


def page_data(captions: dict[str, str]) -> str:
    validation = pd.read_csv(TABLES_DIR / "validation.csv")
    passed = int(validation.passed.astype(bool).sum())
    total = int(len(validation))
    coefficients = read_table("q3_model_coefficients")
    n_crashes = int(coefficients.n.iloc[0])
    other = read_table("q2_other_road_by_period").set_index("period")

    body = key_figures(
        [
            ("Injury crashes", f"{n_crashes:,}", "2016–2024 microdata, one row per crash"),
            ("Reconciliation checks", f"{passed} / {total}", "run before any analysis"),
            ("Series", "1993–2024", "the yearbook monthly and annual series"),
            ("Traffic series", "1990–2025", "monthly road fuel and toll-motorway traffic"),
        ]
    )
    body += (
        '<p class="answer">Every number on this site is generated from files published by DGT, '
        "INE, the Ministerio de Transportes and CORES, reconciled against the publishers' own "
        f"totals by {passed} checks before anything is computed. This page is the short version; "
        f'the <a href="{DOCS_URL}/data_sources.md">source register</a>, the '
        f'<a href="{DOCS_URL}/data_inventory.md">data audit</a> and the '
        f'<a href="{DOCS_URL}/methodology.md">methodology</a> in the repository are the long '
        "one.</p>"
    )

    body += "<h2>Sources</h2>"
    sources = pd.DataFrame(
        [
            (
                "Crash microdata 2016–2024",
                "DGT",
                f"{n_crashes:,} injury crashes, one row each: place, time, road, conditions and "
                "victim counts. No driver, vehicle or person records.",
            ),
            (
                "Yearbook series 1993–2024",
                "DGT",
                "Annual, monthly and provincial totals; the reference the microdata are checked "
                "against, and the series the long-run and seasons pages fit.",
            ),
            (
                "Statistical tables 2014–2024",
                "DGT",
                "Drivers involved and killed by age, sex and vehicle; vehicles involved by type; "
                "drivers by recorded infraction.",
            ),
            (
                "Kilometre estimates 2022 and 2024",
                "DGT",
                "Circulating fleet and mean annual kilometres from roadworthiness-inspection "
                "odometer readings; the 2024 release adds a breakdown by the owner's age band.",
            ),
            (
                "Driver census 2014–2025",
                "DGT",
                "Licence holders by province, sex and age band.",
            ),
            (
                "Resident population 2002–2025",
                "INE",
                "Province by five-year age group and sex (CC BY 4.0).",
            ),
            (
                "Monthly traffic and fuel",
                "Ministerio de Transportes; CORES",
                "Traffic on state toll motorways from 1990 and national road-fuel consumption "
                "from 1996: the traffic denominators of the 2019–2024, long-run and seasons pages.",
            ),
            (
                "Speed-factor report 2014–2023",
                "DGT",
                "Injury crashes with each recorded concurrent factor, and deaths in those with "
                "speed, for Spain without Cataluña and País Vasco; used on the speed and factors "
                "pages, never added to national totals.",
            ),
        ],
        columns=["Source", "Published by", "What it carries"],
    )
    body += table(sources, "The sources behind this site")

    body += "<h2>Definitions</h2>"
    body += (
        "<p><strong>Injury crash</strong>: at least one person killed or injured. "
        "<strong>Death</strong>: within 30 days of the crash, DGT's consolidated definition. "
        "<strong>Serious</strong>: a death or a person admitted to hospital for more than 24 "
        "hours. <strong>Zone</strong>: interurban roads against urban streets and crossings, as "
        "DGT groups them. Missing states are kept apart everywhere: “not specified”, “not "
        "applicable” and a field's own unknown code are three different things, and none of them "
        "means no.</p>"
    )

    body += "<h2>Checks, and what they found</h2>"
    body += (
        f"<p>{passed} checks tie the crash microdata, the yearbook tables and the driver census to "
        "DGT's published totals: crashes and victims per year, deaths by province and by month, "
        "driver deaths by zone, vehicles involved by type, the census against its published "
        "tables, every code against the dictionary, and the speed report's own totals against "
        "the microdata restricted to its provinces. All of them pass, and the microdata match "
        "the yearbook exactly, year by year. The kilometre table by owner age reconciles with the "
        "same release's published fleet to within 0.5%, the margin left by owners DGT could not "
        f'classify. The <a href="tables/validation.csv">full list is a CSV</a>.</p>'
    )
    body += figure(
        "d1_missingness", "Share of crashes with a value recorded, by field and year", captions
    )
    body += "<h3>Three coding breaks worth knowing about</h3>"
    later = other.loc["2024"] if "2024" in other.index else other.iloc[-1]
    earlier = other.loc["2016-2023"] if "2016-2023" in other.index else other.iloc[0]
    body += (
        "<p>In 2024 Barcelona begins coding most of its streets as road type “other”: "
        f"{float(later.street_share):.0%} of that year's “other” crashes are urban streets, "
        f"against {float(earlier.street_share):.0%} before, so road-type series must be read year "
        "by year and alongside zone. In 2021 most crashes on double-carriageway conventional "
        "roads are recoded as single-carriageway conventional. From 2023 the junction field "
        "records more crashes at a junction, mostly in Barcelona. All three are why the severity "
        "page reports its year-by-year refits, and why no page draws a road-type trend.</p>"
    )

    body += "<h2>Reuse</h2>"
    body += (
        f'<p>The code is under the <a href="{REPO_URL}/blob/main/LICENSE">MIT licence</a>. The '
        "data are not: each file keeps the terms of the body that publishes it, and DGT's "
        "statistics are reused here as public-sector information under Ley 37/2007 with the "
        "datos.gob.es conditions applied: the source is named, the meaning is not distorted, the "
        "dates are kept and no endorsement is implied. INE population is CC BY 4.0. Every figure "
        "published here is an aggregate and nothing identifies a person. The file-by-file terms, "
        f'with URLs and checksums, are in the <a href="{DOCS_URL}/data_sources.md">source '
        "register</a>.</p>"
    )

    body += "<h2>Reproduce</h2>"
    body += (
        "<p>Five commands from the raw files, which are tracked in the repository with their "
        f'checksums. The sequence is in the <a href="{REPO_URL}#reproduce">README</a>, it runs on '
        "every push through GitHub Actions, and the result tables and figures are committed, so "
        "any number on this site can be traced to the table it came from and the table to the "
        "file it came from.</p>"
    )
    body += (
        "<p>The project was developed through a reproducible, source-driven workflow. The "
        "research questions, the choice of sources, the statistical design, the interpretation "
        "and the decision to publish each result are the author's, and so is responsibility for "
        "them. AI coding assistants were used during implementation, debugging, data-processing "
        "work and review. All published results are generated from the recorded source data and "
        "can be independently reproduced and checked through the repository.</p>"
    )
    return render_page(
        "data",
        "Data and methods",
        "Where the numbers come from, how they are defined, what the checks found and how to "
        "reproduce all of it.",
        body,
    )


# --------------------------------------------------------------------------- build


PAGE_BUILDERS = {
    "index": page_index,
    "trends": page_trends,
    "long-run": page_long_run,
    "seasons": page_seasons,
    "drivers": page_drivers,
    "vehicles": page_vehicles,
    "speed": page_speed,
    "factors": page_factors,
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
    for slug, builder in PAGE_BUILDERS.items():
        target = site_dir / f"{slug}.html"
        target.write_text(builder(captions), encoding="utf-8")
        written.append(target)
    for old, new in MOVED_PAGES.items():
        target = site_dir / f"{old}.html"
        target.write_text(page_moved(old, new), encoding="utf-8")
        written.append(target)
    return written
