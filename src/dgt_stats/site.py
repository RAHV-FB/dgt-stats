"""Static site builder: plain HTML and one CSS file rendered from the result tables and figures.

No template engine and no JavaScript. Pages are assembled from small string helpers so the output is
easy to read in the repository and to serve from GitHub Pages.
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

import pandas as pd

from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, TABLES_DIR

SITE_DIR = PROJECT_ROOT / "site"
REPO_URL = "https://github.com/RAHV-FB/dgt-stats"

PAGES: tuple[tuple[str, str], ...] = (
    ("index", "Overview"),
    ("trends", "Trends"),
    ("timing", "Timing"),
    ("road-users", "Road users"),
    ("data", "Data and checks"),
)

STYLE = """
:root {
  --surface: #fcfcfb;
  --surface-2: #f3f2ef;
  --text: #0b0b0b;
  --text-2: #52514e;
  --line: #e6e5e1;
  --accent: #2a78d6;
  --measure: 76ch;
}
* { box-sizing: border-box; }
html { background: var(--surface); }
body {
  margin: 0;
  color: var(--text);
  background: var(--surface);
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 17px;
  line-height: 1.55;
}
header, main, footer { max-width: 1040px; margin: 0 auto; padding: 0 16px; }
header { padding-top: 20px; }
header .brand { font-weight: 700; text-decoration: none; color: var(--text); font-size: 1.05rem; }
header .brand span { color: var(--text-2); font-weight: 400; }
nav { margin: 12px 0 0; border-bottom: 1px solid var(--line); }
nav ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 4px 20px; }
nav a { display: inline-block; padding: 8px 0 10px; color: var(--text-2); text-decoration: none; }
nav a[aria-current="page"] { color: var(--text); border-bottom: 2px solid var(--accent); }
main { padding-top: 24px; padding-bottom: 48px; }
h1 { font-size: 1.9rem; line-height: 1.2; margin: 0 0 12px; }
h2 { font-size: 1.35rem; margin: 40px 0 8px; }
h3 { font-size: 1.05rem; margin: 28px 0 6px; }
p, li { max-width: var(--measure); }
p.lead { font-size: 1.15rem; color: var(--text-2); }
a { color: var(--accent); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 20px 0 8px; }
.tile { background: var(--surface-2); border-radius: 8px; padding: 14px 16px; }
.tile .label { color: var(--text-2); font-size: 0.9rem; }
.tile .value { font-size: 2rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.15; margin: 4px 0; }
.tile .note { color: var(--text-2); font-size: 0.85rem; }
figure { margin: 20px 0 28px; }
figure img { width: 100%; height: auto; display: block; background: var(--surface); }
figcaption { color: var(--text-2); font-size: 0.85rem; margin-top: 6px; max-width: var(--measure); }
.table-wrap { overflow-x: auto; margin: 12px 0 24px; }
table { border-collapse: collapse; font-size: 0.9rem; font-variant-numeric: tabular-nums; min-width: 480px; }
th, td { padding: 6px 10px; border-bottom: 1px solid var(--line); text-align: right; white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
thead th { color: var(--text-2); font-weight: 600; border-bottom: 2px solid var(--line); }
caption { caption-side: top; text-align: left; color: var(--text-2); font-size: 0.85rem; padding: 0 0 6px; }
.note { background: var(--surface-2); border-left: 3px solid var(--accent); padding: 10px 14px; border-radius: 0 6px 6px 0; max-width: var(--measure); }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 16px; }
.card { border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; }
.card h3 { margin: 0 0 6px; }
.card p { margin: 0; color: var(--text-2); font-size: 0.95rem; }
footer { border-top: 1px solid var(--line); padding-top: 16px; padding-bottom: 32px; color: var(--text-2); font-size: 0.85rem; }
@media print { nav, footer { display: none; } figure { break-inside: avoid; } }
"""


def _fmt_int(value: object) -> str:
    return "" if pd.isna(value) else f"{float(value):,.0f}"


def _fmt_pct(value: object, decimals: int = 1) -> str:
    return "" if pd.isna(value) else f"{float(value) * 100:.{decimals}f}%"


def _fmt_dec(value: object, decimals: int = 1) -> str:
    return "" if pd.isna(value) else f"{float(value):,.{decimals}f}"


def esc(text: object) -> str:
    return html.escape(str(text))


def read_table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


def read_captions() -> dict[str, str]:
    with (FIGURES_DIR / "captions.json").open(encoding="utf-8") as handle:
        return json.load(handle)


# --------------------------------------------------------------------------- components


def figure(name: str, alt: str, captions: dict[str, str]) -> str:
    return (
        f'<figure><img src="figures/{name}.svg" alt="{esc(alt)}" loading="lazy">'
        f"<figcaption>{esc(captions.get(name, ''))}</figcaption></figure>"
    )


def table(frame: pd.DataFrame, caption: str, formats: dict[str, str] | None = None) -> str:
    """Render a frame as an HTML table. ``formats`` maps column -> 'int' | 'pct' | 'pct2' | 'dec'."""
    formats = formats or {}
    formatters = {
        "year": lambda v: "" if pd.isna(v) else str(int(v)),
        "int": _fmt_int,
        "pct": _fmt_pct,
        "pct2": lambda v: _fmt_pct(v, 2),
        "dec": _fmt_dec,
        "dec2": lambda v: _fmt_dec(v, 2),
    }
    rows = []
    for _, row in frame.iterrows():
        cells = []
        for column in frame.columns:
            value = row[column]
            kind = formats.get(column)
            text = formatters[kind](value) if kind else ("" if pd.isna(value) else str(value))
            cells.append(f"<td>{esc(text)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    head = "".join(f"<th>{esc(column)}</th>" for column in frame.columns)
    return (
        f'<div class="table-wrap"><table><caption>{esc(caption)}</caption>'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def tiles(items: list[tuple[str, str, str]]) -> str:
    cards = "".join(
        f'<div class="tile"><div class="label">{esc(label)}</div>'
        f'<div class="value">{esc(value)}</div><div class="note">{esc(note)}</div></div>'
        for label, value, note in items
    )
    return f'<div class="tiles">{cards}</div>'


def cards(items: list[tuple[str, str, str]]) -> str:
    return (
        '<div class="cards">'
        + "".join(
            f'<div class="card"><h3><a href="{esc(href)}">{esc(title)}</a></h3><p>{esc(text)}</p></div>'
            for href, title, text in items
        )
        + "</div>"
    )


def note(text: str) -> str:
    return f'<p class="note">{text}</p>'


def render_page(slug: str, title: str, lead: str, body: str) -> str:
    nav_items = ""
    for s, name in PAGES:
        current = ' aria-current="page"' if s == slug else ""
        nav_items += f'<li><a href="{s}.html"{current}>{esc(name)}</a></li>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Road safety in Spain</title>
<meta name="description" content="{esc(lead)}">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
<a class="brand" href="index.html">Road safety in Spain <span>· DGT crash data, 1993–2024</span></a>
<nav aria-label="Sections"><ul>{nav_items}</ul></nav>
</header>
<main>
<h1>{esc(title)}</h1>
<p class="lead">{esc(lead)}</p>
{body}
</main>
<footer>
<p>Built from the Dirección General de Tráfico (DGT) open data: crash microdata 2016–2024, the historical
series of the Anuario de Accidentes 2024, the 2024 statistical tables and the driver census. Every number
is reproducible from the <a href="{REPO_URL}">repository</a>; see the data page for the checks.</p>
</footer>
</body>
</html>
"""


# --------------------------------------------------------------------------- pages


def page_index(captions: dict[str, str]) -> str:
    headline = read_table("q1_annual_headline").set_index("year")
    y24, y19 = headline.loc[2024], headline.loc[2019]

    def change(metric: str) -> str:
        delta = (y24[metric] / y19[metric] - 1) * 100
        return f"{delta:+.1f}% vs 2019"

    validation = pd.read_csv(TABLES_DIR / "validation.csv")
    body = tiles(
        [
            ("Injury crashes, 2024", _fmt_int(y24.crashes), change("crashes")),
            ("Deaths within 30 days, 2024", _fmt_int(y24.deaths_30d), change("deaths_30d")),
            ("Hospitalised, 2024", _fmt_int(y24.hospitalised_30d), change("hospitalised_30d")),
            (
                "Deaths per 100 crashes, 2024",
                _fmt_dec(y24.deaths_per_100_crashes, 2),
                f"{_fmt_dec(y19.deaths_per_100_crashes, 2)} in 2019",
            ),
        ]
    )
    body += figure("q1_indexed_trend", "Injury crashes and victims indexed to 2019", captions)
    body += "<h2>What is here</h2>" + cards(
        [
            (
                "trends.html",
                "Trends",
                "Crashes and victims since 1993, rates per vehicle and per inhabitant, the 2020 dip, urban versus interurban.",
            ),
            (
                "timing.html",
                "Timing",
                "When crashes happen and when they turn fatal: hour, weekday, month, darkness, road type.",
            ),
            (
                "road-users.html",
                "Road users",
                "Who dies on the road: pedestrians, cyclists, motorcyclists, car occupants and others, and how that mix is changing.",
            ),
            (
                "data.html",
                "Data and checks",
                f"Sources, definitions, the {len(validation)} reconciliation checks against DGT's published totals, and what is missing.",
            ),
        ]
    )
    body += "<h2>How to read the numbers</h2>" + note(
        "Counts are DGT's consolidated figures: an injury crash is one with at least one person killed or "
        "injured, and deaths are counted within 30 days of the crash unless a chart says otherwise. Crash "
        "counts describe what the police recorded, not the risk of travelling; rates on the trends page "
        "divide by the vehicle fleet or the population."
    )
    return render_page(
        "index",
        "Road safety in Spain",
        "Injury crashes, deaths and injuries on Spanish roads, from DGT's open data, with every figure "
        "reconciled against the published yearbook.",
        body,
    )


def page_trends(captions: dict[str, str]) -> str:
    headline = read_table("q1_annual_headline")
    recent = headline[headline.year >= 2013][
        [
            "year",
            "crashes",
            "deaths_30d",
            "hospitalised_30d",
            "non_hospitalised_30d",
            "deaths_per_100_crashes",
        ]
    ].rename(
        columns={
            "year": "Year",
            "crashes": "Injury crashes",
            "deaths_30d": "Deaths (30 d)",
            "hospitalised_30d": "Hospitalised",
            "non_hospitalised_30d": "Non-hospitalised",
            "deaths_per_100_crashes": "Deaths per 100 crashes",
        }
    )
    by_zone = read_table("q1_annual_by_zone")
    zone_wide = by_zone.pivot(index="year", columns="zone", values="deaths_30d").reset_index()
    zone_wide = zone_wide.rename(
        columns={"year": "Year", "interurban": "Interurban deaths", "urban": "Urban deaths"}
    )
    body = "<h2>Thirty years of decline, then a plateau</h2>"
    body += figure("q1_deaths_30d", "Road deaths per year, 1993 to 2024", captions)
    body += (
        "<p>Deaths fell from 6,378 in 1993 to 1,680 in 2013 and have moved between 1,500 and 1,850 "
        "since, apart from the 2020 lockdown year. Injury crashes, by contrast, are back at their late "
        "2010s level, so the deaths-per-crash ratio keeps falling.</p>"
    )
    body += figure("q1_indexed_trend", "Injury crashes and victims, index 2019 = 100", captions)
    body += table(
        recent,
        "Injury crashes and victims per year, 2013–2024 (30-day definitions)",
        {
            "Year": "year",
            "Injury crashes": "int",
            "Deaths (30 d)": "int",
            "Hospitalised": "int",
            "Non-hospitalised": "int",
            "Deaths per 100 crashes": "dec2",
        },
    )
    body += "<h2>Relative to the fleet and the population</h2>"
    body += figure("q1_rates", "Crashes and deaths per vehicle and per inhabitant", captions)
    body += "<h2>Urban and interurban roads</h2>"
    body += figure("q1_deaths_by_zone", "Road deaths by zone, 2016 to 2024", captions)
    body += table(
        zone_wide,
        "Deaths within 30 days by zone (microdata, 2016–2024)",
        {"Year": "year", "Interurban deaths": "int", "Urban deaths": "int"},
    )
    body += "<h2>Seasonality</h2>"
    body += figure("q1_monthly_heatmap", "Share of each year's road deaths by month", captions)
    body += "<p>July and August carry the most deaths in almost every year; the pattern is stable across "
    body += "three decades even as the totals fell by three quarters.</p>"
    return render_page(
        "trends",
        "Trends",
        "How injury crashes, deaths and injuries have evolved since 1993, and how the picture differs "
        "between urban streets and interurban roads.",
        body,
    )


def page_timing(captions: dict[str, str]) -> str:
    bands = read_table("q2_hour_band_road_group")
    band_table = bands.pivot(
        index="road_group_label", columns="hour_band_label", values="fatal_share"
    )
    band_table = band_table.reset_index().rename(columns={"road_group_label": "Road type"})
    band_formats = {column: "pct" for column in band_table.columns if column != "Road type"}
    night = read_table("q2_night_share")
    night_wide = night.pivot(index="year", columns="zone", values="night_death_share").reset_index()
    night_wide = night_wide.rename(
        columns={"year": "Year", "interurban": "Interurban", "urban": "Urban"}
    )
    body = "<h2>Hour and weekday</h2>"
    body += figure("q2_hour_weekday_crashes", "Injury crashes by weekday and hour", captions)
    body += figure(
        "q2_hour_weekday_fatal_share",
        "Share of crashes with a death, by weekday and hour",
        captions,
    )
    body += (
        "<p>Crashes cluster in the afternoon rush on weekdays. Fatal outcomes follow a different clock: "
        "the share of crashes that kill someone peaks in the small hours, especially on Saturday and "
        "Sunday nights, when traffic is light and speeds are higher.</p>"
    )
    body += "<h2>Road type and time of day</h2>"
    body += figure("q2_hour_band_road_group", "Fatal share by road type and time of day", captions)
    body += table(
        band_table,
        "Share of injury crashes with at least one death, 2016–2024 pooled",
        {"Road type": None, **band_formats},
    )
    body += "<h2>Darkness</h2>"
    body += figure("q2_night_share", "Share of road deaths that occur in darkness", captions)
    body += table(
        night_wide,
        "Share of 30-day deaths in darkness, by zone",
        {"Year": "year", "Interurban": "pct", "Urban": "pct"},
    )
    return render_page(
        "timing",
        "Timing",
        "When crashes happen and when they turn deadly: by hour, weekday, road type and lighting, "
        "from 875,013 injury crashes recorded between 2016 and 2024.",
        body,
    )


def page_road_users(captions: dict[str, str]) -> str:
    users = read_table("q5_deaths_by_road_user")
    totals = users.groupby(["year", "road_user"], observed=True).deaths_30d.sum().reset_index()
    wide = totals.pivot(index="road_user", columns="year", values="deaths_30d")
    compare = pd.DataFrame(
        {
            "Road user": wide.index,
            "Deaths 2016": wide[2016].to_numpy(),
            "Deaths 2019": wide[2019].to_numpy(),
            "Deaths 2024": wide[2024].to_numpy(),
            "Share 2024": (wide[2024] / wide[2024].sum()).to_numpy(),
        }
    ).sort_values("Deaths 2024", ascending=False)
    vulnerable = read_table("q5_vulnerable_share")
    vuln_wide = vulnerable.pivot(
        index="year", columns="zone", values="vulnerable_share"
    ).reset_index()
    vuln_wide = vuln_wide.rename(
        columns={"year": "Year", "interurban": "Interurban", "urban": "Urban"}
    )
    body = "<h2>Who dies on the road</h2>"
    body += figure("q5_road_user_shares", "Road deaths by type of road user", captions)
    body += table(
        compare,
        "Deaths within 30 days by road-user type (microdata)",
        {
            "Road user": None,
            "Deaths 2016": "int",
            "Deaths 2019": "int",
            "Deaths 2024": "int",
            "Share 2024": "pct",
        },
    )
    body += (
        "<p>Pedestrians, cyclists, moped riders, motorcyclists and personal-mobility-vehicle users are "
        "the vulnerable road users: they have no protective shell. Their share of all deaths is far higher "
        "on urban streets than on interurban roads.</p>"
    )
    body += table(
        vuln_wide,
        "Vulnerable road users as a share of 30-day deaths, by zone",
        {"Year": "year", "Interurban": "pct", "Urban": "pct"},
    )
    body += "<h2>Drivers, by vehicle, since 1993</h2>"
    body += figure("q5_driver_deaths", "Driver deaths by vehicle type", captions)
    body += (
        "<p>Car-driver deaths fell by three quarters between 1993 and 2013 and have been flat since. "
        "Motorcyclist deaths did not follow: they rose through the 2000s, dipped, and are now back above "
        "400 a year, close to the number of car drivers killed.</p>"
    )
    body += "<h2>Pedestrians</h2>"
    body += figure("q5_pedestrian_deaths", "Pedestrian deaths by zone", captions)
    return render_page(
        "road-users",
        "Road users",
        "How road deaths are distributed across pedestrians, riders and vehicle occupants, and how that "
        "mix has shifted over three decades.",
        body,
    )


def page_data(captions: dict[str, str]) -> str:
    validation = pd.read_csv(TABLES_DIR / "validation.csv")
    summary = (
        validation.groupby("check")
        .agg(checks=("passed", "size"), passed=("passed", "sum"))
        .reset_index()
    )
    descriptions = {
        "row_count": "Crashes per year equal the yearbook total",
        "victim_total": "Deaths, hospitalised and non-hospitalised per year equal the yearbook (30 d and 24 h)",
        "table_1_1_province": "2024 crashes and deaths per province equal statistical table 1.1",
        "table_3_1_month": "2024 crashes and deaths per month equal statistical table 3.1",
        "unique_key": "Crash identifiers are unique within each year",
        "code_domain": "Every code in the 33 coded fields is in the DGT dictionary or a documented missing state",
        "census_2025": "The 2025 driver-census extract equals the published province table",
    }
    summary["What is checked"] = summary.check.map(descriptions)
    summary = summary[["What is checked", "checks", "passed"]].rename(
        columns={"checks": "Checks", "passed": "Passed"}
    )
    body = "<h2>Sources</h2>"
    body += (
        "<ul>"
        "<li><strong>Crash microdata 2016–2024</strong>: one row per injury crash, 875,013 rows, from "
        "DGT en Cifras (Registro Nacional de Víctimas de Accidentes de Tráfico). Location, time, road type, "
        "crash type, victim counts and conditions; no driver, vehicle or coordinate fields.</li>"
        "<li><strong>Historical series 1993–2024</strong>: the Anuario de Accidentes 2024 series workbook, "
        "used for the long-run trends and as the reference for reconciliation.</li>"
        "<li><strong>2024 statistical tables</strong>: province, month, vehicle and involvement tables.</li>"
        "<li><strong>Driver census 2023–2025</strong> and <strong>ITV kilometre estimates 2022</strong>: "
        "exposure denominators for later analysis.</li>"
        "</ul>"
    )
    body += "<h2>Definitions</h2>"
    body += (
        "<ul>"
        "<li><strong>Injury crash</strong>: at least one person killed or injured.</li>"
        "<li><strong>Death</strong>: within 30 days of the crash (DGT's consolidated definition). Where "
        "a 24-hour count is used, the chart says so.</li>"
        "<li><strong>Hospitalised</strong>: admitted for more than 24 hours.</li>"
        "<li><strong>Zone</strong>: interurban roads versus urban streets and crossings, as DGT groups them.</li>"
        "</ul>"
    )
    body += "<h2>Reconciliation checks</h2>"
    body += table(
        summary,
        "Checks run on the interim data layer",
        {"What is checked": None, "Checks": "int", "Passed": "int"},
    )
    body += "<h2>What is missing</h2>"
    body += figure(
        "data_missingness", "Share of crashes with an observed value by field and year", captions
    )
    body += (
        '<p>Empty, "not specified" (999), "not applicable" (998) and explicit unknown codes are kept '
        "apart in every table. Two quirks found by the checks: the island field carries an undocumented "
        'code 0 from 2018 on, treated as "not specified"; and the strong-wind flag is set in about 0.3% '
        "of crashes every year except 2021, where it is set in 24.6%, so it is excluded from comparisons.</p>"
    )
    body += "<h2>Reproduce</h2>"
    body += (
        f'<p>Everything on this site is generated by Python scripts in the <a href="{REPO_URL}">repository</a>: '
        "<code>scripts/ingest.py</code> builds the Parquet layer and runs the checks, "
        "<code>scripts/build_tables.py</code> adds derived fields, <code>scripts/analyse.py</code> writes "
        "the result tables and figures, and <code>scripts/build_site.py</code> renders these pages.</p>"
    )
    return render_page(
        "data",
        "Data and checks",
        "Where the numbers come from, how they are defined, and the checks that tie them to DGT's "
        "published totals.",
        body,
    )


# --------------------------------------------------------------------------- build


PAGE_BUILDERS = {
    "index": page_index,
    "trends": page_trends,
    "timing": page_timing,
    "road-users": page_road_users,
    "data": page_data,
}


def build(site_dir: Path = SITE_DIR) -> list[Path]:
    """Write every page, the stylesheet and the figures into ``site_dir``."""
    captions = read_captions()
    site_dir.mkdir(parents=True, exist_ok=True)
    figures_out = site_dir / "figures"
    figures_out.mkdir(exist_ok=True)
    written: list[Path] = []
    for svg in sorted(FIGURES_DIR.glob("*.svg")):
        target = figures_out / svg.name
        shutil.copyfile(svg, target)
        written.append(target)
    style = site_dir / "style.css"
    style.write_text(STYLE.strip() + "\n", encoding="utf-8")
    written.append(style)
    for slug, builder in PAGE_BUILDERS.items():
        target = site_dir / f"{slug}.html"
        target.write_text(builder(captions), encoding="utf-8")
        written.append(target)
    return written
