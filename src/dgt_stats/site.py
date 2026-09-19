"""Static site builder: plain HTML and one CSS file rendered from the result tables and figures.

No template engine and no JavaScript. Pages are assembled from small string helpers so the output is
easy to read in the repository and to serve from GitHub Pages.
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from dgt_stats import agebands
from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, TABLES_DIR
from dgt_stats.summaries import BASE_YEAR, read_model_table

SITE_DIR = PROJECT_ROOT / "site"
REPO_URL = "https://github.com/RAHV-FB/dgt-stats"

PAGES: tuple[tuple[str, str], ...] = (
    ("index", "Overview"),
    ("trends", "Trends"),
    ("timing", "Timing"),
    ("road-users", "Road users"),
    ("geography", "Geography"),
    ("older-drivers", "Older drivers"),
    ("severity", "Severity"),
    ("vehicles", "Vehicles per km"),
    ("policy", "Policy"),
    ("speed", "Speed"),
    ("data", "Data and checks"),
)

DENOMINATOR_LABELS = {
    "residents": "Residents of the age band",
    "licence_holders": "Licence holders",
    "travel_weighted": "Travel-weighted drivers (estimate)",
    "drivers_involved": "Drivers involved in injury crashes",
}

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
        "dec4": lambda v: _fmt_dec(v, 4),
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
<title>{"Road safety in Spain · DGT crash data, 1993–2024" if slug == "index" else esc(title) + " · Road safety in Spain"}</title>
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


def _digest() -> str:
    """One computed line per page, in navigation order, for a reader who stops at the front page."""
    headline = read_table("q1_annual_headline").set_index("year")
    first, latest = int(headline.index.min()), int(headline.index.max())
    deaths_change = headline.deaths_30d[latest] / headline.deaths_30d[first] - 1
    night = read_table("q2_night_share")
    night_latest = night[night.year == night.year.max()].set_index("zone")
    vulnerable = read_table("q5_vulnerable_share")
    vulnerable_latest = vulnerable[vulnerable.year == vulnerable.year.max()].set_index("zone")
    provinces = read_table("q4_province_rates")
    provinces = provinces[~provinces.is_total].sort_values("deaths_per_100k")
    lowest, highest = provinces.iloc[0], provinces.iloc[-1]
    ratios = read_table("q7_ladder_ratio")
    older = ratios[(ratios.year == ratios.year.max()) & (ratios.band == "75+")].set_index(
        "denominator"
    )
    holdout = read_model_table("q3_holdout_summary").set_index("outcome")
    coefficients = read_model_table("q3_model_coefficients")
    fatal = coefficients[(coefficients.outcome == "fatal") & ~coefficients.is_reference]
    strongest = fatal.sort_values("odds_ratio", ascending=False).iloc[0]
    vehicles = read_table("q6_summary_2022").set_index("group")
    per_vehicle = (
        vehicles.loc["heavy_truck", "fatal_involvement_per_100k_vehicles"]
        / vehicles.loc["car", "fatal_involvement_per_100k_vehicles"]
    )
    per_km = (
        vehicles.loc["heavy_truck", "fatal_involvement_per_bn_km"]
        / vehicles.loc["car", "fatal_involvement_per_bn_km"]
    )
    points = read_table("q8_points_sensitivity").iloc[0]
    placebo = read_table("q8_points_placebo")
    rank = int(placebo[placebo.is_true]["rank"].iloc[0])
    speed_placebo = read_table("q8_speed_placebo")
    speed_placebo["break_date"] = pd.to_datetime(speed_placebo.break_date)
    fake_2018 = speed_placebo[speed_placebo.break_date == "2018-01-01"].iloc[0]
    infractions = read_table("q9_infraction_shares")
    unknown = infractions[
        (infractions.zone == "all") & (infractions.year == infractions.year.max())
    ]
    factors = read_table("q9_report_factors")
    speed_factor = factors[
        (factors.factor == "Inappropriate speed")
        & (factors.zone == "all")
        & (factors.year == factors.year.max())
    ].iloc[0]
    items = [
        (
            "trends.html",
            "Trends",
            f"{_fmt_int(headline.deaths_30d[latest])} deaths in {latest}, "
            f"{abs(deaths_change) * 100:.0f}% fewer than in {first}; the fall stopped around 2013.",
        ),
        (
            "timing.html",
            "Timing",
            f"Night hours hold {_fmt_pct(night_latest.loc['interurban', 'night_crash_share'], 0)} of "
            f"interurban crashes but {_fmt_pct(night_latest.loc['interurban', 'night_death_share'], 0)} "
            f"of interurban deaths ({int(night.year.max())}).",
        ),
        (
            "road-users.html",
            "Road users",
            f"Pedestrians, cyclists, moped, motorcycle and scooter users are "
            f"{_fmt_pct(vulnerable_latest.loc['urban', 'vulnerable_share'], 0)} of urban deaths and "
            f"{_fmt_pct(vulnerable_latest.loc['interurban', 'vulnerable_share'], 0)} of interurban ones "
            f"({int(vulnerable.year.max())}).",
        ),
        (
            "geography.html",
            "Geography",
            f"Deaths per 100,000 residents run from {_fmt_dec(lowest.deaths_per_100k, 1)} in "
            f"{lowest.province} to {_fmt_dec(highest.deaths_per_100k, 1)} in {highest.province} "
            f"({int(provinces.year.max())}), with intervals wide enough that most provinces overlap.",
        ),
        (
            "older-drivers.html",
            "Older drivers",
            f"Drivers aged 75 and over die {older.loc['residents', 'ratio']:.2f} times as often as "
            f"drivers aged 35–64 per resident, {older.loc['licence_holders', 'ratio']:.2f} times per "
            f"licence holder and {older.loc['drivers_involved', 'ratio']:.1f} times per driver "
            "involved in a crash: the denominator decides the answer.",
        ),
        (
            "severity.html",
            "Severity",
            f"Given an injury crash, the crash type '{strongest.level}' carries "
            f"{strongest.odds_ratio:.1f} times the odds of a death of the reference type; a model "
            f"fitted to 2016–2022 scores 2023–2024 with an area under the curve of "
            f"{holdout.loc['fatal', 'auc']:.2f}.",
        ),
        (
            "vehicles.html",
            "Vehicles per km",
            f"A heavy truck is in a fatal crash {per_vehicle:.0f} times as often as a car per "
            f"registered vehicle but {per_km:.1f} times per kilometre driven (2022); most of the "
            "people killed are outside the truck.",
        ),
        (
            "policy.html",
            "Policy",
            f"The July 2006 points licence coincided with a {abs(points.level_change) * 100:.0f}% drop "
            f"in monthly deaths beyond the trend, larger than any of the {int(placebo.n_fits.iloc[0]) - 1} "
            f"placebo breaks (rank {rank}); the 2019 speed limit shows a change a placebo break in "
            f"January 2018 reproduces ({_pct_change(fake_2018.level_change)}), so no claim is made.",
        ),
        (
            "speed.html",
            "Speed",
            f"DGT's report records inappropriate speed in "
            f"{_fmt_pct(speed_factor.share_of_crashes, 0)} of injury crashes ({int(speed_factor.year)}, "
            "without Cataluña and País Vasco); in the yearbook's driver tables "
            f"{_fmt_pct(unknown.share_unknown.iloc[0], 0)} of drivers have no speed record at all.",
        ),
    ]
    return (
        "<ul>"
        + "".join(
            f'<li><strong><a href="{esc(href)}">{esc(title)}</a></strong>: {esc(text)}</li>'
            for href, title, text in items
        )
        + "</ul>"
    )


def page_index(captions: dict[str, str]) -> str:
    headline = read_table("q1_annual_headline").set_index("year")
    latest, base = int(headline.index.max()), BASE_YEAR
    y24, y19 = headline.loc[latest], headline.loc[base]

    def change(metric: str) -> str:
        delta = (y24[metric] / y19[metric] - 1) * 100
        return f"{delta:+.1f}% vs {base}"

    validation = pd.read_csv(TABLES_DIR / "validation.csv")
    body = tiles(
        [
            (f"Injury crashes, {latest}", _fmt_int(y24.crashes), change("crashes")),
            (f"Deaths within 30 days, {latest}", _fmt_int(y24.deaths_30d), change("deaths_30d")),
            (f"Hospitalised, {latest}", _fmt_int(y24.hospitalised_30d), change("hospitalised_30d")),
            (
                f"Deaths per 100 crashes, {latest}",
                _fmt_dec(y24.deaths_per_100_crashes, 2),
                f"{_fmt_dec(y19.deaths_per_100_crashes, 2)} in {base}",
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
                "geography.html",
                "Geography",
                "Deaths and crashes by province per resident and per licence holder, with intervals, and Spain's rates since 2002.",
            ),
            (
                "older-drivers.html",
                "Older drivers",
                "The same driver deaths against four denominators: residents, licence holders, travel-weighted drivers and drivers involved in crashes.",
            ),
            (
                "severity.html",
                "Severity",
                "Given that a crash happened, which circumstances make it fatal or serious: two logistic models with odds ratios, marginal effects, calibration and stability.",
            ),
            (
                "vehicles.html",
                "Vehicles per km",
                "Motorcycles, cars, vans, heavy trucks and buses in 2022: vehicles in injury and fatal crashes and occupants killed, per registered vehicle and per kilometre driven.",
            ),
            (
                "policy.html",
                "Policy",
                "Did the 2006 points-based licence and the 2019 conventional-road speed limit coincide with a break in monthly deaths: two interrupted time series with placebo checks.",
            ),
            (
                "speed.html",
                "Speed",
                "What the sources record about speed: drivers with a recorded speed infraction since 2014, with the unknown share in view, and the profile of speed-factor crashes from DGT's report.",
            ),
            (
                "data.html",
                "Data and checks",
                f"Sources, definitions, the {len(validation)} reconciliation checks against DGT's published totals, and what is missing.",
            ),
        ]
    )
    body += "<h2>What the data say</h2>" + _digest()
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
    grid = read_table("q2_hour_weekday")
    n_crashes = int(grid.crashes.sum())
    by_zone = read_table("q1_annual_by_zone")
    first_year, last_year = int(by_zone.year.min()), int(by_zone.year.max())
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
        "the share of crashes that kill someone is lowest in the daytime and peaks between two and five in "
        "the morning on every day of the week, when traffic is light and speeds are higher. The very "
        "highest cells are weekday nights, not weekends.</p>"
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
        f"from {_fmt_int(n_crashes)} injury crashes recorded between {first_year} and {last_year}.",
        body,
    )


def page_road_users(captions: dict[str, str]) -> str:
    users = read_table("q5_deaths_by_road_user")
    totals = (
        users.groupby(["year", "road_user"], observed=True)
        .deaths_30d.sum(min_count=1)
        .reset_index()
    )
    wide = totals.pivot(index="road_user", columns="year", values="deaths_30d")
    first, latest = int(wide.columns.min()), int(wide.columns.max())
    compare = pd.DataFrame(
        {
            "Road user": wide.index,
            f"Deaths {first}": wide[first].to_numpy(),
            f"Deaths {BASE_YEAR}": wide[BASE_YEAR].to_numpy(),
            f"Deaths {latest}": wide[latest].to_numpy(),
            f"Share {latest}": (wide[latest] / wide[latest].sum()).to_numpy(),
        }
    ).sort_values(f"Deaths {latest}", ascending=False)
    compare_formats = {
        "Road user": None,
        f"Deaths {first}": "int",
        f"Deaths {BASE_YEAR}": "int",
        f"Deaths {latest}": "int",
        f"Share {latest}": "pct",
    }
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
        "Deaths within 30 days by road-user type (microdata; personal mobility vehicles are counted "
        "separately only from 2020, earlier deaths sit under other vehicles)",
        compare_formats,
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
    drivers = read_table("q5_driver_deaths_series")
    cars = drivers[drivers.vehicle_type_label == "Cars"].set_index("year").deaths_30d
    motorcycles = drivers[drivers.vehicle_type_label == "Motorcycles"].set_index("year").deaths_30d
    last_year = int(cars.index.max())
    body += (
        f"<p>Car-driver deaths fell by {abs(cars[2013] / cars[1993] - 1) * 100:.0f}% between 1993 and "
        f"2013 and have been flat since ({_fmt_int(cars[last_year])} in {last_year}). Motorcyclist "
        "deaths did not follow: they rose through the 2000s, dipped, and are back at "
        f"{_fmt_int(motorcycles[last_year])} in {last_year}, "
        f"{'above' if motorcycles[last_year] > motorcycles.loc[1997:1999].mean() else 'near'} their "
        f"1997–1999 average of {_fmt_int(motorcycles.loc[1997:1999].mean())} and close to the number "
        "of car drivers killed.</p>"
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


def _interval(row: pd.Series, name: str, decimals: int = 1) -> str:
    return (
        f"{_fmt_dec(row[name], decimals)} "
        f"({_fmt_dec(row[f'{name}_low'], decimals)}–{_fmt_dec(row[f'{name}_high'], decimals)})"
    )


def page_geography(captions: dict[str, str]) -> str:
    provinces = read_table("q4_province_rates")
    year = int(provinces.year.iloc[0])
    national = provinces[provinces.is_total].iloc[0]
    ranked = provinces[~provinces.is_total].sort_values("deaths_per_100k", ascending=False)
    top, bottom = ranked.iloc[0], ranked.iloc[-1]
    listing = pd.DataFrame(
        {
            "Province": ranked.province,
            "Deaths": ranked.deaths_30d,
            "Residents": ranked.population,
            "Deaths per 100,000 residents (95% interval)": [
                _interval(row, "deaths_per_100k") for _, row in ranked.iterrows()
            ],
            "Injury crashes per 100,000 residents": ranked.crashes_per_100k,
            "Licence holders": ranked.licence_holders,
            "Deaths per 100,000 licence holders": ranked.deaths_per_100k_licence,
        }
    )
    national_rates = read_table("q4_national_rates")
    recent = national_rates[national_rates.year >= 2014]
    recent_table = pd.DataFrame(
        {
            "Year": recent.year,
            "Deaths (30 d)": recent.deaths_30d,
            "Residents (1 July)": recent.population,
            "Licence holders": recent.licence_holders,
            "Deaths per 100,000 residents": recent.deaths_per_100k_residents,
            "Deaths per 100,000 licence holders": recent.deaths_per_100k_licence,
        }
    )
    body = tiles(
        [
            (
                f"Spain, {year}",
                _fmt_dec(national.deaths_per_100k, 1),
                "deaths per 100,000 residents",
            ),
            (
                f"Highest: {top.province}",
                _fmt_dec(top.deaths_per_100k, 1),
                f"{_fmt_int(top.deaths_30d)} deaths, {_fmt_int(top.population)} residents",
            ),
            (
                f"Lowest: {bottom.province}",
                _fmt_dec(bottom.deaths_per_100k, 1),
                f"{_fmt_int(bottom.deaths_30d)} deaths, {_fmt_int(bottom.population)} residents",
            ),
            (
                f"Per licence holder, {year}",
                _fmt_dec(national.deaths_per_100k_licence, 1),
                "deaths per 100,000 licence holders",
            ),
        ]
    )
    body += "<h2>Provinces</h2>"
    body += figure(
        "q4_province_deaths", f"Road deaths per 100,000 residents by province, {year}", captions
    )
    body += (
        "<p>The rate is deaths in crashes that happened in the province divided by the people who "
        "live there, so provinces crossed by long-distance traffic (Zamora, Soria, Cuenca, Huesca) "
        "rank high partly because many of the dead were passing through, and dense urban provinces "
        "rank low because most travel there is slow and short. The intervals are wide for the small "
        "provinces: one crash more or less moves Soria or Teruel by several places, so the ranking "
        "should be read in groups, not position by position.</p>"
    )
    body += table(
        listing,
        f"Deaths and crashes by province, {year}, ranked by deaths per 100,000 residents "
        "(residents on 1 July; licence holders at the census date)",
        {
            "Province": None,
            "Deaths": "int",
            "Residents": "int",
            "Deaths per 100,000 residents (95% interval)": None,
            "Injury crashes per 100,000 residents": "dec",
            "Licence holders": "int",
            "Deaths per 100,000 licence holders": "dec",
        },
    )
    body += "<h2>Spain over time</h2>"
    body += figure(
        "q4_national_rates", "Road deaths per 100,000 residents and licence holders", captions
    )
    body += (
        "<p>Per resident, deaths fell by almost three quarters between 2002 and 2013 and have been "
        "flat since. Per licence holder the line is flat too: the census has grown by about the same "
        "share as the population, so neither denominator changes the story of the last decade.</p>"
    )
    body += table(
        recent_table,
        "National rates, 2014–2024",
        {
            "Year": "year",
            "Deaths (30 d)": "int",
            "Residents (1 July)": "int",
            "Licence holders": "int",
            "Deaths per 100,000 residents": "dec2",
            "Deaths per 100,000 licence holders": "dec2",
        },
    )
    return render_page(
        "geography",
        "Geography",
        f"Road deaths and crashes by province in {year}, per resident and per licence holder, with "
        "intervals that show how much of the ranking is chance.",
        body,
    )


def _compare(ratio: float) -> str:
    """Wording for a rate ratio: 'less often than', 'about as often as' or 'more often than'."""
    if ratio < 0.95:
        return "less often than"
    if ratio > 1.05:
        return "more often than"
    return "about as often as"


def page_older_drivers(captions: dict[str, str]) -> str:
    ladder = read_table("q7_driver_ladder")
    ratios = read_table("q7_ladder_ratio")
    latest_year = int(ladder.year.max())
    latest = ladder[ladder.year == latest_year].set_index("band")
    latest_ratios = ratios[ratios.year == latest_year]

    def ratio_row(band: str, denominator: str) -> pd.Series:
        return latest_ratios[
            (latest_ratios.band == band) & (latest_ratios.denominator == denominator)
        ].iloc[0]

    def ratio_cell(band: str, denominator: str) -> str:
        return _interval(ratio_row(band, denominator), "ratio", 2)

    def ratio_value(band: str, denominator: str) -> float:
        return float(ratio_row(band, denominator).ratio)

    ladder_table = pd.DataFrame(
        {
            "Denominator": [DENOMINATOR_LABELS[d] for d in DENOMINATOR_LABELS],
            "65–74 vs 35–64": [ratio_cell("65-74", d) for d in DENOMINATOR_LABELS],
            "75 and over vs 35–64": [ratio_cell("75+", d) for d in DENOMINATOR_LABELS],
            "65 and over vs 35–64": [ratio_cell("65+", d) for d in DENOMINATOR_LABELS],
        }
    )
    involvement = latest_ratios[latest_ratios.denominator == "involvement_per_licence"]
    involvement_75 = involvement[involvement.band == "75+"].iloc[0]

    bands = list(agebands.ANALYSIS_BANDS)
    shares = pd.DataFrame(
        {
            "Age band": [agebands.band_label(b) for b in bands],
            "Residents": [latest.loc[b, "residents"] for b in bands],
            "Hold a licence": [latest.loc[b, "licence_share"] for b in bands],
            "Travel-weighted driver share (estimate)": [
                latest.loc[b, "travel_share"] for b in bands
            ],
            "Driver deaths": [latest.loc[b, "driver_deaths"] for b in bands],
            "Per million residents": [latest.loc[b, "deaths_per_million_residents"] for b in bands],
            "Per 100,000 licence holders": [
                latest.loc[b, "deaths_per_100k_licence"] for b in bands
            ],
            "Per 100,000 travel-weighted drivers": [
                latest.loc[b, "deaths_per_100k_travel"] for b in bands
            ],
        }
    )
    licence_share = read_table("q7_licence_share")
    latest_share = licence_share[licence_share.year == latest_year]
    by_sex = latest_share.pivot(index="band", columns="sex", values="licence_share").reindex(bands)
    by_sex_table = pd.DataFrame(
        {
            "Age band": [agebands.band_label(b) for b in bands],
            "Men": by_sex.male.to_numpy(),
            "Women": by_sex.female.to_numpy(),
            "All": by_sex.total.to_numpy(),
        }
    )
    older_75 = latest.loc["75+"]

    body = tiles(
        [
            (
                f"Licence holders aged 75+, {latest_year}",
                _fmt_pct(older_75.licence_share, 0),
                f"of residents 75 and over; {_fmt_pct(latest.loc['45-54', 'licence_share'], 0)} at 45–54",
            ),
            (
                "Driver deaths per resident, 75+ vs 35–64",
                f"{ratio_value('75+', 'residents'):.2f}×",
                "the ratio DGT's per-inhabitant figures imply",
            ),
            (
                "Per licence holder",
                f"{ratio_value('75+', 'licence_holders'):.2f}×",
                "same deaths, licence holders as the denominator",
            ),
            (
                "Per travel-weighted driver",
                f"{ratio_value('75+', 'travel_weighted'):.2f}×",
                "same deaths, drivers weighted by how much they travel by car",
            ),
        ]
    )
    body += "<h2>The same deaths, four denominators</h2>"
    body += (
        "<p>DGT reports deaths of people aged 65 and over per million inhabitants of that age. That "
        "answers how often an older resident dies on the road, not how risky it is for an older person "
        "to drive: fewer older people hold a licence, and those who do drive less. The ladder below "
        "keeps the numerator fixed (drivers killed within 30 days, interurban and urban roads, all "
        "vehicle types) and changes only the denominator.</p>"
    )
    body += figure("q7_ladder_ratio", "Driver death rate, 65 and over relative to 35–64", captions)
    body += table(
        ladder_table,
        f"Driver death rate ratio against drivers aged 35–64, {latest_year} (95% intervals from the "
        "death counts only; the travel-weighted denominator has its own survey band, shown in the "
        "rates table below)",
        {
            "Denominator": None,
            "65–74 vs 35–64": None,
            "75 and over vs 35–64": None,
            "65 and over vs 35–64": None,
        },
    )
    per_resident = ratio_value("75+", "residents")
    body += (
        f"<p>Per resident, drivers aged 75 and over die {_compare(per_resident)} drivers aged 35–64 "
        f"({per_resident:.2f}×). Per licence holder the ratio is "
        f"{ratio_value('75+', 'licence_holders'):.2f}×. Weighted by how much each age travels by "
        f"car it is {ratio_value('75+', 'travel_weighted'):.2f}×, and per driver actually involved "
        f"in an injury crash it is {ratio_value('75+', 'drivers_involved'):.2f}×: when an older "
        "driver crashes, the crash is far more likely to kill them. The conclusion changes with the "
        "denominator, which is why the denominator has to be stated every time.</p>"
    )
    body += "<h2>Why the ratio climbs: exposure and fragility</h2>"
    body += figure(
        "q7_involvement_fragility",
        "Crash involvement per licence holder and deaths per driver involved, by age band",
        captions,
    )
    body += (
        f"<p>Two things happen at once. Licence holders aged 75 and over are involved in injury crashes "
        f"about {_fmt_pct(involvement_75.ratio, 0)} as often as licence holders aged 35–64 (left panel), "
        "which mostly reflects how much less they drive. But when they are involved, the crash kills "
        f"them {ratio_value('75+', 'drivers_involved'):.1f} times as often (right panel): age brings "
        "fragility, and older drivers are "
        "over-represented in the crash types that kill, such as side collisions at junctions on "
        "conventional roads. The per-licence rate hides the second effect behind the first.</p>"
    )
    body += "<h2>Who holds a licence, who drives</h2>"
    body += figure(
        "q7_licence_travel_share",
        f"Share of residents with a licence and travel-weighted driver share, {latest_year}",
        captions,
    )
    body += table(
        shares,
        f"Residents, licence holders, driver deaths and rates by age band, {latest_year}",
        {
            "Age band": None,
            "Residents": "int",
            "Hold a licence": "pct",
            "Travel-weighted driver share (estimate)": "pct",
            "Driver deaths": "int",
            "Per million residents": "dec",
            "Per 100,000 licence holders": "dec2",
            "Per 100,000 travel-weighted drivers": "dec2",
        },
    )
    body += table(
        by_sex_table,
        f"Share of residents holding a licence by sex, {latest_year}",
        {"Age band": None, "Men": "pct", "Women": "pct", "All": "pct"},
    )
    body += (
        "<p>The licence gap between men and women widens with age: among people aged 75 and over, "
        f"{_fmt_pct(by_sex.male.iloc[-1], 0)} of men hold a licence but only "
        f"{_fmt_pct(by_sex.female.iloc[-1], 0)} of women, so the older driving population is mostly "
        "male and the per-resident rates for women 75+ describe passengers and pedestrians far more "
        "than drivers.</p>"
    )
    body += note(
        "<strong>What the travel-weighted estimate is, and is not.</strong> No Spanish source says what "
        "share of people of each age actually drive. ESRA, the European road-user survey in which DGT "
        "takes part, gives a national figure only (80% of adults drove a car at least a few days a "
        "month in 2018, 76% in 2023), and MOVILIA 2006, the last national travel survey, reports car "
        "trips per person by age without separating drivers from passengers. The estimate spreads the "
        "ESRA share across ages in proportion to MOVILIA car trips per resident and caps it at the "
        "licence share; it is therefore an exposure weight, not a head count. Because MOVILIA counts "
        "passengers too, it overstates older people's driving and so understates their per-driver "
        "rate. The true per-driver ratio lies at or above the travel-weighted one. An age split of the "
        "ESRA question would replace the estimate directly."
    )
    body += "<h2>Rates by age band over time</h2>"
    body += figure(
        "q7_death_rates_by_band",
        "Driver deaths per 100,000 licence holders and per 100,000 travel-weighted drivers",
        captions,
    )
    body += (
        f"<p>Per licence holder, the 75-and-over rate fell from "
        f"{_fmt_dec(ladder[(ladder.year == 2014) & (ladder.band == '75+')].deaths_per_100k_licence.iloc[0], 1)} "
        f"in 2014 to {_fmt_dec(older_75.deaths_per_100k_licence, 1)} in {latest_year}, faster than any "
        "other band, as the cohort reaching 75 became one where almost every man and many more women "
        "had driven all their lives. Per travel-weighted driver the older bands stay well above the "
        "rest throughout.</p>"
    )
    body += "<h2>The long view, all road users</h2>"
    body += figure("q7_victims_by_age", "Road deaths per million residents by age band", captions)
    body += (
        "<p>Counting everyone killed, not only drivers, the youngest adults went from the highest "
        "death rate in 2002 to the pack by 2013, while the rate for people aged 65 and over fell least "
        "and has been the highest of any band since 2011. Most of that is pedestrians and, on "
        "interurban roads, car occupants; the driver ladder above isolates the driving part.</p>"
    )
    return render_page(
        "older-drivers",
        "Older drivers",
        "How the risk of driving changes with age once the denominator is the people who hold a "
        "licence and travel by car, not the whole population of that age.",
        body,
    )


def _or_cell(row: pd.Series) -> str:
    if bool(row.is_reference):
        return "1 (reference)"
    return f"{row.odds_ratio:.2f} ({row.or_low:.2f}–{row.or_high:.2f})"


def page_severity(captions: dict[str, str]) -> str:
    coefficients = read_model_table("q3_model_coefficients")
    effects = read_model_table("q3_marginal_effects")
    holdout = read_model_table("q3_holdout_summary").set_index("outcome")
    stability = read_model_table("q3_year_stability")
    profiles = read_model_table("q3_profiles")
    groupings = read_model_table("q3_groupings")
    n_crashes = int(coefficients.n.iloc[0])
    fatal = coefficients[coefficients.outcome == "fatal"]
    serious = coefficients[coefficients.outcome == "serious"]
    base_fatal = fatal.events.iloc[0] / n_crashes
    base_serious = serious.events.iloc[0] / n_crashes

    def effect_table(outcome: str) -> pd.DataFrame:
        table = coefficients[(coefficients.outcome == outcome) & (coefficients.predictor != "year")]
        points = effects[effects.outcome == outcome].set_index(["predictor", "level"]).effect
        return pd.DataFrame(
            {
                "Circumstance": table.predictor_label.to_numpy(),
                "Level": table.level.to_numpy(),
                "Crashes": table.crashes.to_numpy(),
                "Observed share": table.observed_share.to_numpy(),
                "Odds ratio (95% interval)": [_or_cell(row) for _, row in table.iterrows()],
                "Change in probability, points": [
                    points.get((p, lv), 0.0) * 100 for p, lv in zip(table.predictor, table.level)
                ],
            }
        )

    formats = {
        "Circumstance": None,
        "Level": None,
        "Crashes": "int",
        "Observed share": "pct",
        "Odds ratio (95% interval)": None,
        "Change in probability, points": "dec2",
    }
    year_rows = coefficients[coefficients.predictor == "year"]
    year_table = pd.DataFrame(
        {
            "Year": year_rows[year_rows.outcome == "fatal"].level.to_numpy(),
            "Fatal, odds ratio": [
                _or_cell(row) for _, row in year_rows[year_rows.outcome == "fatal"].iterrows()
            ],
            "Serious, odds ratio": [
                _or_cell(row) for _, row in year_rows[year_rows.outcome == "serious"].iterrows()
            ],
        }
    ).sort_values("Year")
    profile_table = profiles.rename(
        columns={"profile": "Crash profile", "fatal": "Fatal", "serious": "Serious"}
    )
    holdout_table = pd.DataFrame(
        {
            "Outcome": ["Fatal", "Serious"],
            "Test crashes": [holdout.loc[o, "test_crashes"] for o in ("fatal", "serious")],
            "Observed share": [holdout.loc[o, "base_rate_test"] for o in ("fatal", "serious")],
            "Mean predicted": [holdout.loc[o, "mean_predicted"] for o in ("fatal", "serious")],
            "Area under the ROC curve": [holdout.loc[o, "auc"] for o in ("fatal", "serious")],
            "Brier score": [holdout.loc[o, "brier"] for o in ("fatal", "serious")],
            "Brier score of the base rate": [
                holdout.loc[o, "brier_base_rate"] for o in ("fatal", "serious")
            ],
        }
    )
    fatal_stability = stability[stability.outcome == "fatal"]
    unstable = fatal_stability[~fatal_stability.within_full_interval]
    if unstable.empty:
        unstable_text = "every per-year estimate lies within the interval of the full model"
    else:
        by_year = unstable.groupby("year").size().sort_values(ascending=False)
        worst_year = int(by_year.index[0])
        worst_terms = unstable[unstable.year == worst_year]
        unstable_text = (
            f"{len(unstable)} of the {len(fatal_stability)} year-by-term estimates fall outside the "
            f"interval of the full model; {worst_year} alone accounts for {int(by_year.iloc[0])} "
            f"of them ({', '.join(worst_terms.level)})"
        )
        unstable_text += (
            ". The yardstick is strict: the full model's intervals are narrow because they pool "
            "nine years, while a single year of fatal crashes gives wide ones"
        )
    latest_year = int(fatal_stability.year.max())
    road_latest = fatal_stability[
        (fatal_stability.year == latest_year) & (fatal_stability.predictor == "road")
    ]
    zone_latest = fatal_stability[
        (fatal_stability.year == latest_year) & (fatal_stability.predictor == "zone")
    ]
    road_collapses = (
        not road_latest.empty
        and (road_latest.odds_ratio < road_latest.full_model_or_low).all()
        and (road_latest.odds_ratio.between(0.67, 1.5)).all()
    )
    zone_rises = (
        not zone_latest.empty and (zone_latest.odds_ratio > zone_latest.full_model_odds_ratio).all()
    )
    if latest_year == 2024 and road_collapses and zone_rises:
        unstable_text += (
            ". One pattern is not noise: in 2024 every road-type effect collapses towards 1 while "
            "every zone effect rises above its full-model estimate, which matches the change in "
            "how road type is coded that year "
            "(the share of crashes coded to other road types rose sharply; see the data page). "
            "Road type and zone should be read together, not separately"
        )
    grouping_table = groupings.rename(
        columns={
            "predictor": "Circumstance",
            "source": "Source field",
            "code": "Code",
            "level": "Model level",
            "reference": "Reference",
        }
    )
    grouping_table["Reference"] = grouping_table.Reference.map({True: "yes", False: ""})

    body = tiles(
        [
            ("Injury crashes modelled", _fmt_int(n_crashes), "2016–2024, none dropped"),
            ("Fatal", _fmt_pct(base_fatal, 2), "share with at least one death within 30 days"),
            ("Serious", _fmt_pct(base_serious, 1), "share with a death or a hospitalised victim"),
            (
                "Holdout discrimination, fatal",
                f"{holdout.loc['fatal', 'auc']:.2f}",
                "area under the ROC curve, 2023–2024 scored by a 2016–2022 fit",
            ),
        ]
    )
    body += "<h2>What the models are</h2>"
    body += (
        "<p>Two logistic regressions on every injury crash of 2016–2024: one for a fatal outcome, one "
        "for a serious outcome (death or hospitalisation). The predictors are the circumstances the "
        "police record for the crash itself: zone, road type, crash type, junction, lighting, weather, "
        "surface, alignment, time of day, weekend, number of vehicles and year. Missing states are "
        "kept as their own level and no crash is dropped; the only exception is a level with fewer "
        "than 500 crashes, which is merged into the reference (the grouping table at the end says "
        "which). Intervals are clustered by province.</p>"
    )
    body += note(
        "<strong>What they are not.</strong> The microdata carry no driver, vehicle or person "
        "fields, so nothing here says who was driving, how fast, or whether alcohol was involved; "
        "the alcohol × speed interaction in the project's methodology note cannot be estimated from "
        "this file. And a model of recorded crashes describes which recorded crashes turn out badly, "
        "not the risk of crashing in the first place."
    )
    body += "<h2>Fatal outcome</h2>"
    body += figure("q3_forest_fatal", "Odds of a fatal outcome by crash circumstance", captions)
    body += table(
        effect_table("fatal"),
        "Fatal outcome: odds ratio against the reference level and the average change in the "
        "probability of a death, in percentage points, when a crash is moved to that level",
        formats,
    )
    body += "<h2>Serious outcome</h2>"
    body += figure("q3_forest_serious", "Odds of a serious outcome by crash circumstance", captions)
    body += table(
        effect_table("serious"),
        "Serious outcome (death or hospitalisation): odds ratio against the reference level and the "
        "average change in probability in percentage points",
        formats,
    )
    body += "<h2>What the two models say together</h2>"
    body += figure(
        "q3_predicted_grid",
        "Predicted probability of a fatal crash by road type and lighting",
        captions,
    )
    body += table(
        profile_table,
        "Predicted probability of each outcome for named crash profiles (year 2024; circumstances "
        "not named are at their reference level)",
        {"Crash profile": None, "Fatal": "pct2", "Serious": "pct"},
    )
    body += "<h2>Year</h2>"
    body += table(
        year_table,
        "Year effects against 2019, all other circumstances held constant",
        {"Year": None, "Fatal, odds ratio": None, "Serious, odds ratio": None},
    )
    body += "<h2>Does it hold up?</h2>"
    body += figure("q3_calibration", "Calibration on the held-out years", captions)
    body += table(
        holdout_table,
        "Fit on 2016–2022 scored on 2023–2024 (the year predictor is left out of this fit)",
        {
            "Outcome": None,
            "Test crashes": "int",
            "Observed share": "pct2",
            "Mean predicted": "pct2",
            "Area under the ROC curve": "dec2",
            "Brier score": "dec4",
            "Brier score of the base rate": "dec4",
        },
    )
    body += figure("q3_year_stability", "Odds ratios refitted year by year", captions)
    body += f"<p>Refitting the fatal model one year at a time, {unstable_text}.</p>"
    body += "<h2>How the codes were grouped</h2>"
    body += table(
        grouping_table,
        "Every original DGT code and the model level it maps to, including the missing markers and "
        "the levels merged into the reference for having fewer than 500 crashes; values no crash "
        "takes are marked as such",
        {
            "Circumstance": None,
            "Source field": None,
            "Code": None,
            "Model level": None,
            "Reference": None,
        },
    )
    return render_page(
        "severity",
        "Severity",
        "Given that an injury crash happened, which recorded circumstances make it fatal or serious, "
        "from logistic models of every crash since 2016.",
        body,
    )


def page_vehicles(captions: dict[str, str]) -> str:
    summary = read_table("q6_summary_2022").set_index("group")
    long = read_table("q6_rates_2022")
    km = read_table("q6_vehicle_km_2022")
    by_year = read_table("q6_involvement_by_year")
    groups = read_table("q6_vehicle_groups")
    fleet = read_table("q1_annual_rates").set_index("year").vehicle_fleet
    year = int(long.year.iloc[0])
    all_roads = long[long.zone == "all"]

    def row(group: str, measure: str) -> pd.Series:
        return all_roads[(all_roads.group == group) & (all_roads.measure == measure)].iloc[0]

    def per_km(group: str, measure: str = "fatal_involvement") -> float:
        return float(row(group, measure).per_billion_km)

    def per_vehicle(group: str, measure: str = "fatal_involvement") -> float:
        return float(row(group, measure).per_100k_vehicles)

    latest = by_year[by_year.year == year].set_index("group")
    heavy = summary.loc["heavy_truck"]
    km_total = km[km.group == "total"].iloc[0]
    coverage = km_total.n_vehicles / fleet.loc[year]
    order = list(summary.index)
    labels_by_group = summary.label.to_dict()

    rate_table = pd.DataFrame(
        {
            "Vehicle type": [labels_by_group[g] for g in order],
            "Registered": [summary.loc[g, "n_vehicles"] for g in order],
            "Km per vehicle": [summary.loc[g, "km_per_vehicle"] for g in order],
            "Billion km": [summary.loc[g, "vehicle_km_bn"] for g in order],
            "In injury crashes": [summary.loc[g, "injury_involvement"] for g in order],
            "per bn km": [
                _interval(row(g, "injury_involvement"), "per_billion_km", 0) for g in order
            ],
            "In fatal crashes": [summary.loc[g, "fatal_involvement"] for g in order],
            "per bn km ": [
                _interval(row(g, "fatal_involvement"), "per_billion_km", 1) for g in order
            ],
            "Occupants killed": [summary.loc[g, "occupant_deaths"] for g in order],
            "per bn km  ": [
                _interval(row(g, "occupant_deaths"), "per_billion_km", 1) for g in order
            ],
        }
    )
    ranking = pd.DataFrame(
        {
            "Vehicle type": [labels_by_group[g] for g in order],
            "In fatal crashes per 100,000 vehicles": [
                _interval(row(g, "fatal_involvement"), "per_100k_vehicles", 1) for g in order
            ],
            "Rank": [summary.loc[g, "rank_fatal_per_100k_vehicles"] for g in order],
            "In fatal crashes per billion km": [
                _interval(row(g, "fatal_involvement"), "per_billion_km", 1) for g in order
            ],
            "Rank ": [summary.loc[g, "rank_fatal_per_bn_km"] for g in order],
        }
    )
    share_table = pd.DataFrame(
        {
            "Vehicle type": [labels_by_group[g] for g in order],
            "In fatal crashes": [summary.loc[g, "fatal_involvement"] for g in order],
            "Own occupants killed": [summary.loc[g, "occupant_deaths"] for g in order],
            "Occupants killed per fatal crash involved in": [
                summary.loc[g, "occupant_deaths_per_fatal_involvement"] for g in order
            ],
        }
    )
    km_table = km.rename(
        columns={
            "label": "Vehicle type",
            "n_vehicles": "Registered",
            "vehicle_km": "Vehicle-km",
            "km_per_vehicle": "Km per vehicle",
            "fleet_share": "Share of fleet",
            "km_share": "Share of km",
        }
    ).drop(columns="group")
    km_table["Vehicle-km"] = (km_table["Vehicle-km"] / 1e9).round(1)
    km_table = km_table.rename(columns={"Vehicle-km": "Billion km"})
    years_table = by_year.pivot(index="label", columns="year", values="fatal_involvement")
    years_table = years_table.reindex(
        [labels_by_group[g] for g in order]
        + [g for g in years_table.index if g not in labels_by_group.values()]
    )
    years_table.columns = [str(c) for c in years_table.columns]
    years_table = (
        years_table.rename_axis(None, axis=1)
        .reset_index()
        .rename(columns={"label": "Vehicle type"})
    )
    mapping = groups.rename(
        columns={
            "label": "Group",
            "yearbook_unit_types": "Yearbook unit types (tables 2.2 and 2.3)",
            "km_table_type": "Kilometre table type",
            "series_column": "Series column",
            "has_km_denominator": "Has a km denominator",
            "note": "Note",
        }
    ).drop(columns=["group", "microdata_column"])
    mapping["Has a km denominator"] = mapping["Has a km denominator"].map({True: "yes", False: ""})
    split = read_table("q6_van_light_truck_split").set_index("group")
    split_table = pd.DataFrame(
        {
            "Vehicle type": split.label.values,
            "Registered": split.n_vehicles.values,
            "In injury crashes": split.injury_involvement.values,
            "per bn km": split.injury_involvement_per_bn_km.values,
            "In fatal crashes": split.fatal_involvement.values,
            "per bn km ": split.fatal_involvement_per_bn_km.values,
            "per 100,000 vehicles": split.fatal_involvement_per_100k_vehicles.values,
        }
    )
    split_ratio = (
        split.loc["light_truck", "fatal_involvement_per_bn_km"]
        / split.loc["van", "fatal_involvement_per_bn_km"]
    )

    by_age = read_table("q6_km_by_age_2022")
    heavy_age = by_age[by_age.group == "heavy_truck"].set_index("age_band").mean_km_year
    heavy_new_km, heavy_old_km = heavy_age["0-4 years"], heavy_age["20 years and over"]
    ratio_vehicle = per_vehicle("heavy_truck") / per_vehicle("car")
    ratio_km = per_km("heavy_truck") / per_km("car")
    moto_ratio = per_km("motorcycle") / per_km("car")
    fatal_share_rate_groups = latest.loc[order, "fatal_involvement_share_of_vehicles"].sum()
    heavy_fatal_share = latest.loc["heavy_truck", "fatal_involvement_share_of_vehicles"]

    def occupant_ratio(group: str) -> float:
        return per_km(group, "occupant_deaths") / per_km("car", "occupant_deaths")

    def times(ratio: float) -> str:
        if ratio < 0.95:
            return "less often"
        if ratio > 1.05:
            return f"{ratio:.1f} times as often"
        return "about as often"

    bus_deaths = row("bus", "occupant_deaths")

    body = tiles(
        [
            (
                f"Trucks over 3,500 kg, {year}",
                _fmt_pct(heavy.n_vehicles / km_total.n_vehicles, 1),
                f"of the seven-type fleet; {_fmt_pct(heavy.vehicle_km_bn * 1e9 / km_total.vehicle_km, 1)} "
                f"of its kilometres; {_fmt_pct(heavy_fatal_share, 1)} of the vehicles in fatal "
                "crashes",
            ),
            (
                "Heavy trucks vs cars, per vehicle",
                f"{ratio_vehicle:.1f}×",
                "as often in a fatal crash per registered vehicle",
            ),
            (
                "Heavy trucks vs cars, per kilometre",
                f"{ratio_km:.1f}×",
                "as often in a fatal crash per kilometre driven",
            ),
            (
                "Motorcycles vs cars, per kilometre",
                f"{moto_ratio:.0f}×",
                "as often in a fatal crash per kilometre driven",
            ),
        ]
    )
    body += "<h2>Three rates, one denominator</h2>"
    body += (
        f"<p>For {year}, and only for {year}, DGT publishes an estimate of how far each type of "
        "vehicle is driven: the registered fleet by type and age multiplied by the mean annual "
        "kilometres modelled from roadworthiness-inspection odometer readings. The same year's "
        "yearbook tables count the vehicles of each type involved in injury crashes and in fatal "
        "crashes, and the drivers and passengers of each type who died. Dividing the counts by the "
        f"kilometres gives the three rates below for the six vehicle groups the two sources share "
        f"({_fmt_pct(fatal_share_rate_groups, 0)} of the vehicles in fatal crashes, pedestrians "
        "not counted; bicycles, personal mobility vehicles, machinery and unknown vehicles have no "
        "kilometre denominator).</p>"
    )
    body += figure("q6_rates_per_km", "Vehicles per billion kilometres driven, 2022", captions)
    body += table(
        rate_table,
        f"Vehicles, kilometres, involvement and occupant deaths by vehicle type, {year} (95% "
        "intervals in brackets; kilometres are the national estimate, so interurban and urban "
        "rows are not separable)",
        {
            "Vehicle type": None,
            "Registered": "int",
            "Km per vehicle": "int",
            "Billion km": "dec",
            "In injury crashes": "int",
            "per bn km": None,
            "In fatal crashes": "int",
            "per bn km ": None,
            "Occupants killed": "int",
            "per bn km  ": None,
        },
    )
    body += (
        f"<p>Per kilometre, motorcycles are in a fatal crash {moto_ratio:.0f} times as often as "
        f"cars ({per_km('motorcycle'):.1f} against {per_km('car'):.1f} per billion km) and their "
        f"riders die "
        f"{per_km('motorcycle', 'occupant_deaths') / per_km('car', 'occupant_deaths'):.0f} times as "
        f"often ({per_km('motorcycle', 'occupant_deaths'):.1f} against "
        f"{per_km('car', 'occupant_deaths'):.1f}). Mopeds sit close behind on both. Heavy trucks "
        f"({per_km('heavy_truck'):.1f}) and buses ({per_km('bus'):.1f}) are in fatal crashes "
        f"{ratio_km:.1f} and {per_km('bus') / per_km('car'):.1f} times as often as cars per "
        f"kilometre. Heavy-truck occupants die {times(occupant_ratio('heavy_truck'))} per kilometre "
        f"than car occupants ({per_km('heavy_truck', 'occupant_deaths'):.1f} against "
        f"{per_km('car', 'occupant_deaths'):.1f}); bus occupants "
        f"{times(occupant_ratio('bus'))} ({per_km('bus', 'occupant_deaths'):.1f}, but on "
        f"{int(bus_deaths['count'])} deaths, so the interval runs from "
        f"{bus_deaths.per_billion_km_low:.1f} to {bus_deaths.per_billion_km_high:.1f}). Vans and "
        f"trucks up to 3,500 kg ({per_km('van_light_truck'):.1f}) match cars on the fatal measures "
        f"and are in injury crashes less often per kilometre "
        f"({per_km('van_light_truck', 'injury_involvement'):.0f} against "
        f"{per_km('car', 'injury_involvement'):.0f}).</p>"
    )
    body += "<h2>Per vehicle or per kilometre</h2>"
    body += figure(
        "q6_per_vehicle_vs_per_km",
        "Vehicles in fatal crashes: ranking per registered vehicle and per kilometre",
        captions,
    )
    body += table(
        ranking,
        f"Vehicles involved in fatal crashes under the two denominators, {year}",
        {
            "Vehicle type": None,
            "In fatal crashes per 100,000 vehicles": None,
            "Rank": "int",
            "In fatal crashes per billion km": None,
            "Rank ": "int",
        },
    )
    body += (
        f"<p>Per registered vehicle, buses and heavy trucks lead by a wide margin: a heavy truck is in "
        f"a fatal crash {ratio_vehicle:.0f} times as often as a car ({per_vehicle('heavy_truck'):.1f} "
        f"against {per_vehicle('car'):.1f} per 100,000). Most of that gap is distance. A heavy truck "
        f"covers about {heavy.km_per_vehicle / summary.loc['car', 'km_per_vehicle']:.0f} times the "
        f"kilometres of a car in a year ({_fmt_int(heavy.km_per_vehicle)} against "
        f"{_fmt_int(summary.loc['car', 'km_per_vehicle'])}), so per kilometre the ratio falls to "
        f"{ratio_km:.1f}. Motorcycles and mopeds move the other way: they are driven little, so a "
        "modest rate per vehicle becomes the highest rate per kilometre. Which denominator is right "
        "depends on the question: per vehicle answers what a fleet of that size costs in fatal "
        "crashes, per kilometre what a trip of a given length costs.</p>"
    )
    body += "<h2>Who dies in the crash</h2>"
    body += table(
        share_table,
        f"Own occupants killed per vehicle involved in a fatal crash, {year}, all roads",
        {
            "Vehicle type": None,
            "In fatal crashes": "int",
            "Own occupants killed": "int",
            "Occupants killed per fatal crash involved in": "dec2",
        },
    )
    body += (
        f"<p>The two measures separate because of who dies. When a motorcycle or a moped is in a "
        f"fatal crash the dead are almost always its own riders "
        f"({summary.loc['motorcycle', 'occupant_deaths_per_fatal_involvement']:.2f} and "
        f"{summary.loc['moped', 'occupant_deaths_per_fatal_involvement']:.2f} occupant deaths per "
        f"fatal involvement). For cars the figure is "
        f"{summary.loc['car', 'occupant_deaths_per_fatal_involvement']:.2f}, for buses "
        f"{summary.loc['bus', 'occupant_deaths_per_fatal_involvement']:.2f} and for heavy trucks "
        f"{heavy.occupant_deaths_per_fatal_involvement:.2f}: in more than four of every five fatal "
        "crashes with a heavy truck, the people killed were in the other vehicle or on foot. A "
        "heavy truck's danger per kilometre is therefore mostly a danger to others, which a rate of "
        "its own occupants' deaths, the only per-type measure the microdata can give, would miss "
        "entirely.</p>"
    )
    body += "<h2>Where the kilometres are</h2>"
    body += figure(
        "q6_km_by_age", "Mean annual kilometres per vehicle by type and vehicle age", captions
    )
    body += table(
        km_table,
        f"Registered vehicles and estimated kilometres by type, {year}",
        {
            "Vehicle type": None,
            "Registered": "int",
            "Billion km": "dec",
            "Km per vehicle": "int",
            "Share of fleet": "pct",
            "Share of km": "pct",
        },
    )
    body += (
        f"<p>The seven types in the kilometre table add up to {_fmt_int(km_total.n_vehicles)} "
        f"vehicles, {_fmt_pct(coverage, 0)} of the {_fmt_int(fleet.loc[year])} registered in {year}; "
        "the rest are tractors, trailers, quadricycles and other vehicles without an estimate. "
        "Distance falls steeply with vehicle age for every type, and most steeply for heavy trucks: "
        f"a truck under five years old covers {_fmt_int(heavy_new_km)} km a year, one over twenty "
        f"{_fmt_int(heavy_old_km)}. "
        "Any rate per registered vehicle therefore depends on how old the fleet is, which a rate per "
        "kilometre does not.</p>"
    )
    body += "<h2>Occupant deaths since 1993</h2>"
    body += figure(
        "q6_occupant_deaths", "Drivers and passengers killed by vehicle type, 1993–2024", captions
    )
    body += table(
        years_table,
        "Vehicles involved in fatal crashes by type, 2020–2024, all roads (counts; kilometres exist "
        "only for 2022)",
        {"Vehicle type": None, **{c: "int" for c in years_table.columns if c != "Vehicle type"}},
    )
    occupants = read_table("q6_occupant_deaths_series")
    last_year = int(occupants.year.max())
    car_series = occupants[occupants.group == "car"].set_index("year").deaths_30d
    moto_series = occupants[occupants.group == "motorcycle"].set_index("year").deaths_30d
    ranking = occupants[occupants.year == last_year].sort_values("deaths_30d", ascending=False)
    moto_rank = int(list(ranking.group).index("motorcycle")) + 1
    ordinal = {1: "largest", 2: "second-largest", 3: "third-largest"}.get(
        moto_rank, f"{moto_rank}th"
    )
    body += (
        f"<p>Deaths of car occupants fell by {abs(car_series[2013] / car_series[2003] - 1) * 100:.0f}% "
        "between 2003 and 2013 and have been flat since; heavy-truck and bus occupant deaths fell in "
        "step with them. Motorcyclist deaths did not: after the drop to 2013 they climbed back to "
        f"{_fmt_int(moto_series[last_year])} in {last_year}, against an average of "
        f"{_fmt_int(moto_series.loc[1997:1999].mean())} a year in 1997–1999, and they were the "
        f"{ordinal} group in {last_year}. The per-kilometre rates above describe a single year; "
        "without kilometre estimates for other years there is no way to say whether the motorcycle "
        "rate has risen or whether more kilometres are being ridden.</p>"
    )
    body += "<h2>Limits</h2>"
    body += note(
        "<strong>Three things to keep in mind.</strong> First, involvement by vehicle type exists "
        "only in the yearbook tables (type × zone × severity), never in the crash microdata, so "
        "nothing finer, such as involvement by hour, road type or crash type, is possible. Second, the "
        "kilometres are modelled, not measured: DGT annualises the odometer readings taken at "
        "roadworthiness inspections and imputes them to the registered fleet; its methodology note "
        "reports that the model explains between 19% and 45% of the variance across individual "
        "vehicles and that the estimates are valid for aggregates only. The intervals on this page "
        "come from the crash counts alone and treat the kilometres as known. Third, the groups "
        "must mean the same thing on both sides of the division. Vans and trucks up to 3,500 kg are "
        "one group because the crash record codes most light commercial vehicles as vans while the "
        "register splits them: taken separately (table below), trucks up to 3,500 kg would be in "
        f"fatal crashes {_fmt_pct(split_ratio, 0)} as often as vans per kilometre, a gap with no "
        "plausible cause but the coding. Heavy trucks include tractor units and articulated vehicles "
        "because the kilometre table's heavy category is, per DGT's methodology note, the union of "
        "trucks over 3,500 kg (272,157 vehicles, 6.9 billion km) and industrial tractors (222,594 "
        "vehicles, 19.7 billion km)."
    )
    body += table(
        split_table,
        f"Vans and trucks up to 3,500 kg taken separately, {year}: the gap that motivates merging them",
        {
            "Vehicle type": None,
            "Registered": "int",
            "In injury crashes": "int",
            "per bn km": "dec",
            "In fatal crashes": "int",
            "per bn km ": "dec",
            "per 100,000 vehicles": "dec",
        },
    )
    body += table(
        mapping,
        "How the 22 yearbook unit types, the 7 kilometre-table types and the 9 series columns map "
        "to the groups on this page",
        {
            "Group": None,
            "Yearbook unit types (tables 2.2 and 2.3)": None,
            "Kilometre table type": None,
            "Series column": None,
            "Has a km denominator": None,
            "Note": None,
        },
    )
    return render_page(
        "vehicles",
        "Vehicles per kilometre",
        f"How often each type of vehicle is in an injury crash or a fatal crash, and how often its "
        f"occupants die, per registered vehicle and per kilometre driven, for {year}, the one year "
        "with a distance estimate.",
        body,
    )


def _pct_change(value: float, decimals: int = 0) -> str:
    return f"{value * 100:+.{decimals}f}%"


def _change_cell(
    row: pd.Series, name: str = "level_change", low: str = "level_low", high: str = "level_high"
) -> str:
    if pd.isna(row[name]):
        return ""
    return (
        f"{_pct_change(row[name], 1)} ({_pct_change(row[low], 1)} to {_pct_change(row[high], 1)})"
    )


def page_policy(captions: dict[str, str]) -> str:
    points_fit = read_table("q8_points_fit").set_index("term")
    points_series = read_table("q8_points_series")
    points_series["period"] = pd.to_datetime(points_series.period)
    points_placebo = read_table("q8_points_placebo")
    points_sens = read_table("q8_points_sensitivity")
    speed_placebo = read_table("q8_speed_placebo")
    speed_placebo["break_date"] = pd.to_datetime(speed_placebo.break_date)
    speed_sens = read_table("q8_speed_sensitivity")

    main = points_sens.iloc[0]
    trend_month = float(points_fit.loc["t", "estimate"])
    trend_year = float(np.expm1(12 * trend_month))
    true_row = points_placebo[points_placebo.is_true].iloc[0]
    rank, n_fits = int(true_row["rank"]), int(true_row.n_fits)
    others = points_placebo[~points_placebo.is_true]
    post = points_series[points_series.post & (points_series.period <= "2007-11-01")]
    avoided = float((post.counterfactual_main - post.deaths).sum())
    after = points_series[points_series.period.between("2006-07-01", "2007-06-01")].deaths.sum()
    before = points_series[points_series.period.between("2005-07-01", "2006-06-01")].deaths.sum()
    raw_change = after / before - 1
    long_row = points_sens[points_sens.variant == "long"].iloc[0]
    urban_row = points_sens[points_sens.variant == "urban"].iloc[0]
    from_1993 = points_sens[points_sens.variant == "from_1993"].iloc[0]

    speed_main = speed_sens.iloc[0]
    placebo_2018 = speed_placebo[speed_placebo.break_date == "2018-01-01"].iloc[0]
    placebo_2017 = speed_placebo[speed_placebo.break_date == "2017-01-01"].iloc[0]
    placebo_2018_significant = placebo_2018.high < 0
    long_speed = speed_sens[speed_sens.variant == "long"].iloc[0]

    sensitivity_table = pd.DataFrame(
        {
            "Variant": points_sens.label,
            "Window": points_sens.window,
            "Level change (95% interval)": [_change_cell(r) for _, r in points_sens.iterrows()],
            "Slope change per year": [
                "" if pd.isna(v) else _pct_change(v, 1) for v in points_sens.slope_change_annual
            ],
            "Dispersion": points_sens.dispersion,
        }
    )
    speed_table = pd.DataFrame(
        {
            "Variant": speed_sens.label,
            "Window": speed_sens.window,
            "Conventional roads, own change (95% interval)": [
                _change_cell(r) for _, r in speed_sens.iterrows()
            ],
            "Control roads, change": [_pct_change(v, 1) for v in speed_sens.control_change],
            "Dispersion": speed_sens.dispersion,
        }
    )
    placebo_table = pd.DataFrame(
        {
            "Break placed at": speed_placebo.break_date.dt.strftime("%B %Y"),
            "Conventional roads, own change (95% interval)": [
                _change_cell(r, "level_change", "low", "high") for _, r in speed_placebo.iterrows()
            ],
            "Control roads, change (95% interval)": [
                _change_cell(r, "control_change", "control_low", "control_high")
                for _, r in speed_placebo.iterrows()
            ],
            "Real intervention": speed_placebo.is_true.map({True: "yes", False: "placebo"}),
        }
    )
    timeline = pd.DataFrame(
        {
            "Date": [
                "2005–2008",
                "1 July 2006",
                "2 December 2007",
                "2008–2009",
                "29 January 2019",
                "March 2020",
            ],
            "Change": [
                "Road-safety plan: automatic speed cameras rolled out on the main network",
                "Points-based driving licence in force (Ley 17/2005)",
                "Penal Code reform: speeding and drink-driving thresholds become offences (LO 15/2007)",
                "Recession; traffic and freight fall",
                "Speed limit on conventional roads cut from 100 to 90 km/h (RD 1514/2018)",
                "Pandemic lockdown, then restrictions to the end of 2021",
            ],
            "Used as": [
                "not modelled; confounds the 2006 estimate",
                "intervention 1",
                "end of the clean post-period; second break in the long fit",
                "not modelled; the fleet offset is the only exposure control",
                "intervention 2",
                "end of the clean post-period; period terms in the long fit",
            ],
        }
    )

    body = tiles(
        [
            (
                "Points licence, July 2006",
                _pct_change(main.level_change),
                f"level change in monthly deaths, {_pct_change(main.level_low)} to "
                f"{_pct_change(main.level_high)}; placebo rank {rank} of {n_fits}",
            ),
            (
                "Deaths below the trend, Jul 2006 – Nov 2007",
                _fmt_int(avoided),
                "fitted counterfactual minus observed over the 17 clean months",
            ),
            (
                "90 km/h limit, January 2019",
                _pct_change(speed_main.level_change),
                f"conventional roads relative to motorways, {_pct_change(speed_main.level_low)} to "
                f"{_pct_change(speed_main.level_high)}",
            ),
            (
                "Same design, break placed in January 2018",
                _pct_change(placebo_2018.level_change),
                f"{_pct_change(placebo_2018.low)} to {_pct_change(placebo_2018.high)}: "
                + (
                    "a false break gives the same result"
                    if placebo_2018_significant
                    else "no effect, as it should"
                ),
            ),
        ]
    )
    body += "<h2>What an interrupted series can and cannot show</h2>"
    body += (
        "<p>An interrupted time series fits the months before a change, projects that pattern "
        "forward, and asks whether the months after sit below it. It needs a stable pre-trend, a "
        "post-period free of other changes, and a way to tell a real break from the ordinary "
        "wobble of the series. The last point is handled here with placebos: the same model is "
        "refitted with the intervention placed at every other admissible month, and a real effect "
        "should sit in the tail of that distribution. The wording follows the result: "
        "<em>coincided with</em> unless the pre-trend, the placebos and the sensitivity fits all "
        "agree.</p>"
    )
    body += table(
        timeline,
        "The changes around the two interventions and how each is handled",
        {"Date": None, "Change": None, "Used as": None},
    )
    body += "<h2>The points-based licence, 1 July 2006</h2>"
    body += figure(
        "q8_points_series", "Monthly road deaths around the points-based licence", captions
    )
    body += (
        f"<p>Deaths were already falling before July 2006: the fitted trend over January 2000 to "
        f"June 2006 is {_pct_change(trend_year, 1)} a year. Against that trend and the seasonal "
        f"pattern, the level of the series shifts by {_pct_change(main.level_change, 1)} at July "
        f"2006 ({_pct_change(main.level_low, 1)} to {_pct_change(main.level_high, 1)}), and the "
        f"slope afterwards is {_pct_change(main.slope_change_annual, 1)} a year relative to the "
        "pre-trend, not distinguishable from no change. Over the seventeen months to November 2007 "
        f"the fitted counterfactual exceeds the observed deaths by {_fmt_int(avoided)}. The raw "
        f"comparison points the same way: the twelve months from July 2006 had {_fmt_int(after)} "
        f"deaths against {_fmt_int(before)} in the twelve months before ({_pct_change(raw_change, 1)}), "
        "of which the pre-trend alone explains about "
        f"{_pct_change(trend_year, 1)}.</p>"
    )
    body += figure(
        "q8_points_placebo",
        "Estimated level change with the break placed at every other month",
        captions,
    )
    placebo_dates = pd.to_datetime(others.break_date)
    body += (
        f"<p>With the break placed at any of the {n_fits - 1} other months from "
        f"{placebo_dates.min():%B %Y} to {placebo_dates.max():%B %Y}, the estimated level change "
        f"runs from {_pct_change(others.level_change.min(), 1)} to "
        f"{_pct_change(others.level_change.max(), 1)}; the July 2006 estimate ranks {rank} of "
        f"{n_fits}. The placebos are not noise around zero: the 2004 breaks all come out negative "
        "because the decline steepened that year, which is the pre-trend problem in another form. "
        + (
            "The July 2006 drop is larger than any of them.</p>"
            if rank == 1
            else f"{rank - 1} of the placebo drops are larger than the July 2006 one.</p>"
        )
    )
    body += table(
        sensitivity_table,
        "The same estimate under other choices",
        {
            "Variant": None,
            "Window": None,
            "Level change (95% interval)": None,
            "Slope change per year": None,
            "Dispersion": "dec2",
        },
    )
    body += figure(
        "q8_points_series_long",
        "The same series to December 2009 with the December 2007 reform as a second break",
        captions,
    )
    body += (
        "<p>The estimate survives the 24-hour definition, the interurban series, the fleet offset "
        "and a negative-binomial fit. It does not survive two things, and the page says which. "
        f"On urban streets alone the change is {_pct_change(urban_row.level_change, 1)} with an "
        "interval that includes zero: the drop is an interurban one. Extending the window to "
        f"December 2009 with a second break at the Penal Code reform, the July 2006 level change "
        f"falls to {_pct_change(long_row.level_change, 1)} ({_pct_change(long_row.level_low, 1)} to "
        f"{_pct_change(long_row.level_high, 1)}) and the December 2007 break takes "
        f"{_pct_change(long_row.second_break_change, 1)}: the two changes share the decline, and "
        "the recession of 2008 is not in the model at all. Starting the pre-period in 1993 gives "
        f"{_pct_change(from_1993.level_change, 1)}, but that fit is misspecified (the series is "
        "flat to 2003 and then falls, so one line does not describe it) and its dispersion of "
        f"{from_1993.dispersion:.1f} says so.</p>"
    )
    body += note(
        "<strong>Reading.</strong> July 2006 coincided with a drop of about "
        f"{abs(main.level_change) * 100:.0f}% in monthly road deaths that no other month of 2002 to "
        "2005 reproduces and that holds under most alternative specifications. Whether the "
        "licence caused it cannot be settled on this series: the speed-camera programme arrived in "
        "the same two years, the Penal Code reform seventeen months later, and the recession after "
        "that. What the series supports is that the decline from mid-2006 was a step, not the "
        "continuation of the pre-trend."
    )
    body += "<h2>The 90 km/h limit on conventional roads, 29 January 2019</h2>"
    body += figure(
        "q8_speed_series",
        "Monthly deaths on conventional roads and on motorways and dual carriageways",
        captions,
    )
    body += (
        "<p>Here the series cannot isolate conventional roads, but the microdata can, and "
        "motorways and dual carriageways, which kept their limits, serve as a control for weather, "
        "traffic and everything else the two share. In one model of both groups, conventional "
        f"roads show a change of {_pct_change(speed_main.level_change, 1)} "
        f"({_pct_change(speed_main.level_low, 1)} to {_pct_change(speed_main.level_high, 1)}) at "
        f"February 2019 over and above the control roads, whose own change is "
        f"{_pct_change(speed_main.control_change, 1)}.</p>"
    )
    body += table(
        placebo_table,
        "The same model with the break placed in January 2017 and January 2018",
        {
            "Break placed at": None,
            "Conventional roads, own change (95% interval)": None,
            "Control roads, change (95% interval)": None,
            "Real intervention": None,
        },
    )
    if placebo_2018_significant:
        body += (
            f"<p>The design fails its own check. A break placed in January 2018, a year before the "
            f"limit changed, gives {_pct_change(placebo_2018.level_change, 1)} "
            f"({_pct_change(placebo_2018.low, 1)} to {_pct_change(placebo_2018.high, 1)}), as large "
            "as the real one: deaths on conventional roads were already falling relative to the "
            "control roads through 2018, so the 2019 estimate is the continuation of a divergence "
            "that predates the limit. The January 2017 placebo is "
            f"{_pct_change(placebo_2017.level_change, 1)}, as it should be.</p>"
        )
    else:
        body += (
            f"<p>Both placebos are near zero ({_pct_change(placebo_2017.level_change, 1)} and "
            f"{_pct_change(placebo_2018.level_change, 1)}), so the 2019 change stands out from the "
            "years before it.</p>"
        )
    body += table(
        speed_table,
        "The 2019 estimate under other choices",
        {
            "Variant": None,
            "Window": None,
            "Conventional roads, own change (95% interval)": None,
            "Control roads, change": None,
            "Dispersion": "dec2",
        },
    )
    body += figure("q8_speed_series_long", "The same two series to December 2024", captions)
    body += (
        f"<p>Extended through the pandemic with period terms, the conventional-road change turns "
        f"to {_pct_change(long_speed.level_change, 1)} ({_pct_change(long_speed.level_low, 1)} to "
        f"{_pct_change(long_speed.level_high, 1)}): from 2021 deaths on conventional roads "
        "recovered to their 2016–2018 level while deaths on motorways and dual carriageways did "
        "not, so relative to the control the 90 km/h limit is followed, years later, by more "
        "deaths rather than fewer. Nothing in these data separates the limit from the pandemic's "
        "different effects on the two kinds of road.</p>"
    )
    if placebo_2018_significant:
        body += note(
            "<strong>Reading.</strong> The clean-window estimate for the 90 km/h limit, "
            f"{_pct_change(speed_main.level_change)}, is not distinguishable from a change that "
            "had already begun in 2018 and is reversed once the series runs through the pandemic. "
            "No claim about the limit's effect can be made from these data; a road-section series "
            "with speeds and traffic volumes would be needed."
        )
    else:
        body += note(
            "<strong>Reading.</strong> The clean-window estimate for the 90 km/h limit, "
            f"{_pct_change(speed_main.level_change)}, passes its placebo checks but is reversed "
            "once the series runs through the pandemic, so it describes thirteen months and no "
            "more. A road-section series with speeds and traffic volumes would be needed to say "
            "whether the limit itself lowered deaths."
        )
    body += "<h2>Limits</h2>"
    body += note(
        "Monthly deaths are counts with overdispersion (the Pearson dispersion of the main 2006 fit "
        f"is {main.dispersion:.1f}) and serial correlation; the standard errors are Newey–West with "
        "twelve lags (within each road group in the 2019 panel) and the negative-binomial variant "
        "is in each table. The 2006 model has no "
        "exposure series but the annual fleet, interpolated to months. The 2019 model treats the "
        "road type recorded at the crash as fixed, but the microdata note a change in road-type "
        "coding in 2024 (see the data page); the clean window ends in February 2020 and is not "
        "affected. Neither design can attribute a change to one measure when several arrived "
        "together, which is why the page says coincided."
    )
    return render_page(
        "policy",
        "Policy",
        "Two interrupted time series on monthly road deaths: the points-based licence of July 2006 "
        "and the 90 km/h limit on conventional roads of January 2019, each with placebo checks "
        "and the changes that confound it.",
        body,
    )


def page_speed(captions: dict[str, str]) -> str:
    shares = read_table("q9_infraction_shares")
    by_vehicle = read_table("q9_infractions_by_vehicle")
    others = read_table("q9_other_infractions")
    factors = read_table("q9_report_factors")
    roads = read_table("q9_report_road_type")
    limits = read_table("q9_report_speed_limit")
    vehicle = read_table("q9_report_vehicle")
    age = read_table("q9_report_age")
    licence = read_table("q9_report_licence")
    day_hour = read_table("q9_report_day_hour")

    latest_year = int(shares.year.max())
    first_year = int(shares.year.min())
    report_year = int(roads.year.max())
    all_roads = shares[shares.zone == "all"].set_index("year")
    inter = shares[shares.zone == "interurban"].set_index("year")
    urban = shares[shares.zone == "urban"].set_index("year")
    latest = all_roads.loc[latest_year]
    first = all_roads.loc[first_year]
    jump_year = int(all_roads[all_roads.share_unknown > 0.4].index.min())

    vehicles_latest = by_vehicle[(by_vehicle.zone == "all") & (by_vehicle.vehicle_group != "total")]
    vehicles_latest = vehicles_latest[vehicles_latest.vehicle_group != "unknown"].set_index(
        "vehicle_group"
    )
    others_all = others[others.zone == "all"].reset_index(drop=True)
    speed_rank = int(others_all.index[others_all["item"] == "speed_infraction"][0]) + 1

    factor_latest = factors[(factors.zone == "all") & (factors.year == report_year)].set_index(
        "factor"
    )
    speed_by_zone = factors[
        (factors.factor == "Inappropriate speed") & (factors.year == report_year)
    ].set_index("zone")
    speed_2014 = factors[
        (factors.factor == "Inappropriate speed") & (factors.year == int(factors.year.min()))
    ].set_index("zone")
    roads_latest = roads[roads.year == report_year].set_index("label")
    limits_latest = limits[(limits.year == report_year) & (limits.category != "Total")]
    limits_latest = limits_latest[limits_latest.limit_km_h.notna()].set_index("label")
    vehicle_latest = vehicle[vehicle.year == report_year].set_index("label")
    age_latest = age[(age.year == report_year) & (age.sex == "all")].set_index("age_band")
    licence_latest = licence[licence.year == report_year].set_index("licence_class")
    first_report_year = int(limits.year.min())
    limits_first = limits[(limits.year == first_report_year) & (limits.category != "Total")]
    limits_last = limits[(limits.year == report_year) & (limits.category != "Total")]

    def unknown_limit_share(block: pd.DataFrame) -> float:
        return float(block[block.label == "Unknown"].crashes.sum() / block.crashes.sum())

    def known_30_share(block: pd.DataFrame) -> float:
        known = block[block.limit_km_h.notna()]
        return float(known[known.label == "30 km/h"].crashes.sum() / known.crashes.sum())

    unknown_limit_first = unknown_limit_share(limits_first)
    unknown_limit_latest = unknown_limit_share(limits_last)
    known_30_first, known_30_latest = known_30_share(limits_first), known_30_share(limits_last)
    weekend = (
        day_hour[day_hour.weekday.isin(["Saturday", "Sunday"])].crashes.sum()
        / day_hour.crashes.sum()
    )
    top_cell = day_hour.sort_values("crashes", ascending=False).iloc[0]
    provinces = read_table("q4_province_rates")
    provinces = provinces[~provinces.is_total]
    excluded_codes = {8, 17, 25, 43, 1, 20, 48}  # Cataluña and País Vasco
    excluded_share = (
        provinces[provinces.province_code.astype(int).isin(excluded_codes)].crashes.sum()
        / provinces.crashes.sum()
    )
    ordinals = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}

    status_table = pd.DataFrame(
        {
            "Year": all_roads.index,
            "Drivers involved": all_roads.total.values,
            "Speed infraction": all_roads.speed_infraction.values,
            "No speed infraction": all_roads.none.values,
            "Unknown": all_roads.unknown.values,
            "Infraction, share of all drivers": all_roads.share_speed_infraction.values,
            "Unknown, share of all drivers": all_roads.share_unknown.values,
            "Infraction, share of drivers with a record": [
                f"{_fmt_pct(r.share_among_known, 1)} ({_fmt_pct(r.share_among_known_low, 1)}–{_fmt_pct(r.share_among_known_high, 1)})"
                for _, r in all_roads.reset_index().iterrows()
            ],
        }
    )
    vehicle_table = pd.DataFrame(
        {
            "Vehicle": vehicles_latest.vehicle_label.values,
            "Drivers involved": vehicles_latest.total.values,
            "With a record": vehicles_latest.known.values,
            "Speed infraction": vehicles_latest.speed_infraction.values,
            "Unknown, share of drivers": vehicles_latest.share_unknown.values,
            "Infraction, share of drivers with a record": [
                f"{_fmt_pct(r.share_among_known, 1)} ({_fmt_pct(r.share_among_known_low, 1)}–{_fmt_pct(r.share_among_known_high, 1)})"
                for _, r in vehicles_latest.iterrows()
            ],
        }
    )
    others_table = pd.DataFrame(
        {
            "Infraction recorded": others_all.label.values,
            "Drivers": others_all.drivers_with_infraction.values,
            "Share of drivers with a record in that block": others_all.share_of_known.values,
        }
    )
    factors_table = pd.DataFrame(
        {
            "Factor": factor_latest.index,
            "Injury crashes": factor_latest.crashes.values,
            "Share of all injury crashes": factor_latest.share_of_crashes.values,
        }
    ).sort_values("Injury crashes", ascending=False)
    roads_table = pd.DataFrame(
        {
            "Road type": roads_latest.index,
            "Injury crashes": roads_latest.crashes.values,
            "Share": roads_latest.share_of_crashes.values,
            "Deaths": roads_latest.deaths.values,
            "Share ": roads_latest.share_of_deaths.values,
        }
    )
    limits_table = pd.DataFrame(
        {
            "Speed limit": limits_latest.index,
            "Injury crashes": limits_latest.crashes.values,
            "Share": limits_latest.share_of_crashes.values,
            "Deaths": limits_latest.deaths.values,
            "Share ": limits_latest.share_of_deaths.values,
        }
    )
    vehicle_report_table = pd.DataFrame(
        {
            "Means of transport": vehicle_latest.index,
            "Injury crashes": vehicle_latest.crashes.values,
            "Deaths": vehicle_latest.deaths.values,
            "Share of deaths": vehicle_latest.share_of_deaths.values,
        }
    )
    age_table = pd.DataFrame(
        {
            "Driver age": age_latest.index,
            "Injury crashes": age_latest.crashes.values,
            "Share": age_latest.share_of_crashes.values,
            "Drivers killed": age_latest.driver_deaths.values,
        }
    )
    age_table = age_table[~age_table["Driver age"].isin(["65+ (all)"])]
    licence_table = pd.DataFrame(
        {
            "Licence class": licence_latest.index,
            "Injury crashes": licence_latest.crashes.values,
            "Share": licence_latest.share_of_crashes.values,
            "Drivers killed": licence_latest.driver_deaths.values,
            "Share ": licence_latest.share_of_driver_deaths.values,
        }
    )

    body = tiles(
        [
            (
                f"Drivers with a speed infraction, {latest_year}",
                _fmt_pct(latest.share_speed_infraction, 1),
                f"of {_fmt_int(latest.total)} drivers involved in injury crashes; "
                f"{_fmt_pct(latest.share_among_known, 1)} of those with a record",
            ),
            (
                f"Drivers with no record, {latest_year}",
                _fmt_pct(latest.share_unknown, 0),
                f"{_fmt_pct(first.share_unknown, 0)} in {first_year}; the jump came in {jump_year}",
            ),
            (
                f"Crashes with the speed factor, {report_year}",
                _fmt_pct(speed_by_zone.loc["all", "share_of_crashes"], 0),
                f"of injury crashes in DGT's report; {_fmt_pct(speed_by_zone.loc['interurban', 'share_of_crashes'], 0)} "
                f"interurban, {_fmt_pct(speed_by_zone.loc['urban', 'share_of_crashes'], 0)} urban "
                "(without Cataluña and País Vasco)",
            ),
            (
                f"Deaths in speed-factor crashes, {report_year}",
                _fmt_int(roads_latest.loc["Total", "deaths"]),
                f"{_fmt_pct(roads_latest.loc['Other interurban roads', 'share_of_deaths'], 0)} of them on "
                "conventional and other interurban roads",
            ),
        ]
    )
    body += "<h2>What the sources record</h2>"
    body += (
        "<p>Nothing in the open data measures speed. Two sources record a judgement about it. The "
        "yearbook's driver tables say, for each driver involved in an injury crash, whether the "
        "police recorded a speed infraction, no speed infraction, or nothing at all. DGT's thematic "
        "report on the speed factor counts crashes in which inappropriate speed was recorded as a "
        "concurrent factor for any road user, and it covers fifteen of the seventeen regions: "
        "Cataluña and País Vasco, which run their own police forces, are excluded. The two count "
        "different things over different territories, so this page never adds them together.</p>"
    )
    body += "<h2>Drivers with a recorded speed infraction</h2>"
    body += figure(
        "q9_speed_status_interurban",
        "Drivers involved in injury crashes by recorded speed status, interurban roads",
        captions,
    )
    body += figure(
        "q9_speed_status_urban",
        "Drivers involved in injury crashes by recorded speed status, urban streets",
        captions,
    )
    body += (
        f"<p>The first thing the tables show is not about speed. In {first_year}, "
        f"{_fmt_pct(first.share_unknown, 0)} of drivers had no speed record; in {jump_year} the share "
        f"jumped to {_fmt_pct(all_roads.loc[jump_year, 'share_unknown'], 0)} and it has stayed there "
        f"({_fmt_pct(latest.share_unknown, 0)} in {latest_year}; "
        f"{_fmt_pct(urban.loc[latest_year, 'share_unknown'], 0)} on urban streets, "
        f"{_fmt_pct(inter.loc[latest_year, 'share_unknown'], 0)} on interurban roads). A share of "
        "drivers with an infraction over all drivers therefore fell for reasons that have nothing to "
        f"do with driving: {_fmt_pct(first.share_speed_infraction, 1)} in {first_year} to "
        f"{_fmt_pct(latest.share_speed_infraction, 1)} in {latest_year}. Among drivers who do have a "
        f"record the share went the other way, from {_fmt_pct(first.share_among_known, 1)} to "
        f"{_fmt_pct(all_roads.loc[jump_year, 'share_among_known'], 1)} in {jump_year} and "
        f"{_fmt_pct(latest.share_among_known, 1)} in {latest_year}, which says as much about which "
        "drivers get a record as about speed. Interurban roads carry the higher rate throughout: "
        f"{_fmt_pct(inter.loc[latest_year, 'share_among_known'], 1)} of interurban drivers with a "
        f"record against {_fmt_pct(urban.loc[latest_year, 'share_among_known'], 1)} of urban ones in "
        f"{latest_year}.</p>"
    )
    body += table(
        status_table,
        f"Drivers involved in injury crashes by recorded speed status, all roads, {first_year}–{latest_year}",
        {
            "Year": "year",
            "Drivers involved": "int",
            "Speed infraction": "int",
            "No speed infraction": "int",
            "Unknown": "int",
            "Infraction, share of all drivers": "pct",
            "Unknown, share of all drivers": "pct",
            "Infraction, share of drivers with a record": None,
        },
    )
    body += figure(
        "q9_speed_by_vehicle",
        "Share of drivers with a recorded speed infraction, among those with a record, by vehicle",
        captions,
    )
    body += table(
        vehicle_table,
        f"Speed status by vehicle, all roads, {latest_year}",
        {
            "Vehicle": None,
            "Drivers involved": "int",
            "With a record": "int",
            "Speed infraction": "int",
            "Unknown, share of drivers": "pct",
            "Infraction, share of drivers with a record": None,
        },
    )
    body += (
        f"<p>Among drivers with a record, motorcyclists carry the highest share "
        f"({_fmt_pct(vehicles_latest.loc['motorcycle', 'share_among_known'], 1)}), then cars "
        f"({_fmt_pct(vehicles_latest.loc['car', 'share_among_known'], 1)}); bus drivers the lowest "
        f"({_fmt_pct(vehicles_latest.loc['bus', 'share_among_known'], 1)}). The unknown share is "
        "similar for every vehicle, between "
        f"{_fmt_pct(vehicles_latest.share_unknown.min(), 0)} and "
        f"{_fmt_pct(vehicles_latest.share_unknown.max(), 0)}, so the ranking is not an artefact of "
        "who gets recorded, though the level might be.</p>"
    )
    body += table(
        others_table,
        f"The speed and driver infractions the tables record, all roads, {latest_year}, ranked",
        {
            "Infraction recorded": None,
            "Drivers": "int",
            "Share of drivers with a record in that block": "pct",
        },
    )
    body += (
        f"<p>Speed ranks {ordinals.get(speed_rank, str(speed_rank))} among the infractions "
        "recorded: priority infractions "
        f"({_fmt_pct(others_all.share_of_known.iloc[0], 1)} of drivers with a record) and not "
        f"keeping a safe distance ({_fmt_pct(others_all.share_of_known.iloc[1], 1)}) come first. "
        "The two blocks are recorded separately, so a driver can appear in both.</p>"
    )
    body += "<h2>The speed factor in DGT's report</h2>"
    body += figure(
        "q9_report_speed_share",
        "Share of injury crashes with inappropriate speed as a factor",
        captions,
    )
    body += table(
        factors_table,
        f"Injury crashes with each concurrent factor, all roads, {report_year} (without Cataluña and País Vasco)",
        {"Factor": None, "Injury crashes": "int", "Share of all injury crashes": "pct"},
    )
    body += (
        f"<p>In the report's territory, inappropriate speed was recorded in "
        f"{_fmt_int(speed_by_zone.loc['all', 'crashes'])} injury crashes in {report_year}, "
        f"{_fmt_pct(speed_by_zone.loc['all', 'share_of_crashes'], 0)} of the total, down from "
        f"{_fmt_pct(speed_2014.loc['all', 'share_of_crashes'], 0)} in {int(factors.year.min())}. The "
        f"factor is an interurban one: {_fmt_pct(speed_by_zone.loc['interurban', 'share_of_crashes'], 0)} "
        f"of interurban injury crashes against {_fmt_pct(speed_by_zone.loc['urban', 'share_of_crashes'], 0)} "
        "of urban ones. Distraction and illegal manoeuvres are recorded far more often, as on the "
        "driver tables above. The report's shares are rounded to whole percentages.</p>"
    )
    body += table(
        roads_table,
        f"Crashes and deaths with the speed factor by road type, {report_year}",
        {
            "Road type": None,
            "Injury crashes": "int",
            "Share": "pct",
            "Deaths": "int",
            "Share ": "pct",
        },
    )
    body += figure(
        "q9_report_speed_limit",
        "Crashes and deaths with the speed factor by the road's speed limit",
        captions,
    )
    body += table(
        limits_table,
        f"Crashes and deaths with the speed factor by the road's speed limit, {report_year}",
        {
            "Speed limit": None,
            "Injury crashes": "int",
            "Share": "pct",
            "Deaths": "int",
            "Share ": "pct",
        },
    )
    body += (
        f"<p>Conventional and other interurban roads take "
        f"{_fmt_pct(roads_latest.loc['Other interurban roads', 'share_of_crashes'], 0)} of the "
        f"speed-factor crashes and {_fmt_pct(roads_latest.loc['Other interurban roads', 'share_of_deaths'], 0)} "
        "of the deaths. By posted limit the crashes split between the 30 km/h streets "
        f"({_fmt_pct(limits_latest.loc['30 km/h', 'share_of_crashes'], 0)}) and the 90 km/h roads "
        f"({_fmt_pct(limits_latest.loc['90 km/h', 'share_of_crashes'], 0)}), but the deaths do not: "
        f"{_fmt_pct(limits_latest.loc['90 km/h', 'share_of_deaths'], 0)} of them are on 90 km/h roads, "
        f"{_fmt_pct(limits_latest.loc['30 km/h', 'share_of_deaths'], 0)} on 30 km/h streets. The "
        f"limit itself was unknown for {_fmt_pct(unknown_limit_first, 0)} of the speed-factor "
        f"crashes in {first_report_year} and for {_fmt_pct(unknown_limit_latest, 1)} in "
        f"{report_year}, so the earlier years cannot be compared row by row; among crashes with a "
        f"known limit, the 30 km/h share went from {_fmt_pct(known_30_first, 0)} to "
        f"{_fmt_pct(known_30_latest, 0)}, as cities extended the limit from 2021 and the "
        "unknowns were filled in.</p>"
    )
    body += table(
        vehicle_report_table,
        f"Crashes and deaths with the speed factor by means of transport, {report_year} (a crash "
        "with two vehicle types counts under both, so the crash total exceeds the number of crashes)",
        {
            "Means of transport": None,
            "Injury crashes": "int",
            "Deaths": "int",
            "Share of deaths": "pct",
        },
    )
    body += table(
        age_table,
        f"Speed-factor crashes by the age of the drivers involved, and drivers killed, {report_year} "
        "(a crash counts once per age band of its drivers)",
        {"Driver age": None, "Injury crashes": "int", "Share": "pct", "Drivers killed": "int"},
    )
    body += table(
        licence_table,
        f"Speed-factor crashes and drivers killed by the driver's licence class, {report_year}",
        {
            "Licence class": None,
            "Injury crashes": "int",
            "Share": "pct",
            "Drivers killed": "int",
            "Share ": "pct",
        },
    )
    body += (
        f"<p>Cars are in {_fmt_int(vehicle_latest.loc['Cars', 'crashes'])} of the speed-factor crashes "
        f"and motorcycles in {_fmt_int(vehicle_latest.loc['Motorcycles', 'crashes'])}, but motorcycle "
        f"users are {_fmt_pct(vehicle_latest.loc['Motorcycles', 'share_of_deaths'], 0)} of the deaths "
        f"against {_fmt_pct(vehicle_latest.loc['Cars', 'share_of_deaths'], 0)} for car occupants. Drivers "
        f"aged 15 to 34 account for {_fmt_pct(age_latest.loc['15-24', 'share_of_crashes'] + age_latest.loc['25-34', 'share_of_crashes'], 0)} "
        "of the driver-by-age entries the report counts (a crash counts once per age band of its "
        "drivers), and class A (motorcycle) licence holders are "
        f"{_fmt_pct(licence_latest.loc['A', 'share_of_driver_deaths'], 0)} of the drivers killed while "
        f"being {_fmt_pct(licence_latest.loc['A', 'share_of_crashes'], 0)} of the driver-by-licence "
        "entries.</p>"
    )
    body += figure(
        "q9_report_day_hour", "Injury crashes with the speed factor by weekday and hour", captions
    )
    body += (
        f"<p>Pooled over ten years, {_fmt_pct(weekend, 0)} of the speed-factor crashes fall on "
        f"Saturdays and Sundays, and the single busiest cell is {top_cell.weekday} at "
        f"{int(top_cell.hour_start):02d}:00 ({_fmt_int(top_cell.crashes)} crashes). This is the "
        "weekend-daytime pattern of leisure riding and driving on interurban roads, not the "
        "commuting peaks of the timing page.</p>"
    )
    body += "<h2>Where speed already appears on this site</h2>"
    body += (
        '<p>The <a href="policy.html">policy page</a> tests the 2019 cut of the conventional-road '
        "limit and finds nothing it can attribute to it. The "
        '<a href="severity.html">severity models</a> have no speed term, because the microdata have '
        'none; road type and darkness stand in for it. The <a href="timing.html">timing page</a> '
        "shows the hour and weekday pattern of all crashes, which the speed-factor grid above "
        "departs from.</p>"
    )
    body += "<h2>Limits</h2>"
    body += note(
        "<strong>Five things to keep in mind.</strong> First, both sources record a judgement, not "
        "a measurement: no speed, no limit exceeded by how much. Second, the report excludes "
        f"Cataluña and País Vasco, {_fmt_pct(excluded_share, 0)} of Spain's injury crashes in "
        f"{int(provinces.year.max())}, and its shares are rounded. Third, about half of the drivers "
        f"in the yearbook tables have no speed record since {jump_year}, and the half that does is not "
        "a random sample: an infraction is more likely to be written down than its absence, so the "
        "shares among recorded drivers probably overstate the true share, by an amount nothing here "
        "can measure. Fourth, the driver tables count drivers and the report "
        "counts crashes; a crash with two drivers appears twice in one and once in the other. Fifth, "
        "nothing here is a rate: without knowing how many drivers speed without crashing, none of "
        "these shares says how dangerous speeding is, only how often it is recorded when a crash "
        "has happened."
    )
    return render_page(
        "speed",
        "Speed",
        "What the two sources that mention speed record, for drivers since 2014 and for crashes in "
        "DGT's speed-factor report, and where the recorded speed factor concentrates.",
        body,
    )


def page_data(captions: dict[str, str]) -> str:
    validation = pd.read_csv(TABLES_DIR / "validation.csv")
    grid = read_table("q2_hour_weekday")
    n_crashes = int(grid.crashes.sum())
    by_zone = read_table("q1_annual_by_zone")
    first_year, last_year = int(by_zone.year.min()), int(by_zone.year.max())
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
        "driver_deaths": "Driver deaths in the yearly tables 4.1.1 equal the yearbook series, every year 2014–2024 and zone",
        "census_age_2023": "The 2023 driver census by age (text file) is within 2% of the published age table, band by band",
        "table_2_3_vehicles": "Vehicles involved in the yearly tables 2.3 are within 0.1% of the microdata vehicle count, 2020–2024",
        "table_2_2_deaths": "Deaths by means of transport in the yearly tables 2.2 equal the microdata death columns for every vehicle group, 2020–2024",
        "table_6_1_drivers": "The driver-infraction tables 6.1 have one total across their blocks, within 1.5% of the drivers involved in table 4.2, every year 2014–2024 and zone",
    }
    summary["What is checked"] = summary.check.map(descriptions)
    summary = summary[["What is checked", "checks", "passed"]].rename(
        columns={"checks": "Checks", "passed": "Passed"}
    )
    body = "<h2>Sources</h2>"
    body += (
        "<ul>"
        f"<li><strong>Crash microdata {first_year}–{last_year}</strong>: one row per injury crash, "
        f"{_fmt_int(n_crashes)} rows, from "
        "DGT en Cifras (Registro Nacional de Víctimas de Accidentes de Tráfico). Location, time, road type, "
        "crash type, victim counts and conditions; no driver, vehicle or coordinate fields.</li>"
        "<li><strong>Historical series 1993–2024</strong>: the Anuario de Accidentes 2024 series workbook, "
        "used for the long-run trends and as the reference for reconciliation.</li>"
        "<li><strong>Statistical tables 2014–2024</strong>: province, month and involvement tables "
        "for 2024; vehicles involved and victims by means of transport for 2020–2024; driver victims "
        "and drivers involved by age, sex and vehicle type for every year (chapter workbooks up to "
        "2019, one workbook per year from 2020).</li>"
        "<li><strong>Driver census 2014–2025</strong>: licence holders by age band and sex from the "
        "published class-by-age tables (2014–2023) and the province-by-age text files (2024–2025).</li>"
        "<li><strong>ITV kilometre estimates 2022</strong>: registered fleet and mean annual km by "
        "vehicle type and age, modelled by DGT from annualised odometer readings at roadworthiness "
        "inspections; valid for aggregates only.</li>"
        "<li><strong>DGT speed-factor report</strong> (Observatorio Nacional de Seguridad Vial, "
        "March 2025): its 61 annex tables transcribed from the PDF, 2014–2023, for Spain without "
        "Cataluña and País Vasco; never added to the yearbook figures.</li>"
        "<li><strong>INE resident population</strong> (Estadística Continua de Población, table 56947): "
        "province by five-year age group and sex, 1 January and 1 July, 2002–2025.</li>"
        "<li><strong>Driving activity</strong>: ESRA 2018 and 2023 national shares of adults who drive "
        "(Spain), MOVILIA 2006 trips by mode, sex and age. No Spanish source gives the share of people "
        "who drive by age.</li>"
        "</ul>"
    )
    body += (
        "<p>All of these are published as open data by DGT (DGT en Cifras) and INE under their own "
        "reuse terms, which this site preserves: figures are quoted with attribution, aggregated, and "
        "never combined with anything that could identify a person.</p>"
    )
    body += "<h2>Definitions</h2>"
    body += (
        "<ul>"
        "<li><strong>Injury crash</strong>: at least one person killed or injured.</li>"
        "<li><strong>Death</strong>: within 30 days of the crash (DGT's consolidated definition). Where "
        "a 24-hour count is used, the chart says so.</li>"
        "<li><strong>Hospitalised</strong>: admitted for more than 24 hours.</li>"
        "<li><strong>Zone</strong>: interurban roads versus urban streets and crossings, as DGT groups them.</li>"
        "<li><strong>Rates</strong>: counts are treated as Poisson with a known denominator; intervals "
        "are exact 95% intervals. Residents are INE's estimate on 1 July of the year; licence holders "
        "are DGT's census (people holding a driving permit or a moped or agricultural licence). "
        "Drivers with unknown age (about 3% of those involved, 0.4% of those killed) are excluded from "
        "the age-band rates.</li>"
        "<li><strong>Interrupted time series</strong> (policy page): Poisson regressions of monthly "
        "deaths on a linear trend, month-of-year terms and a level (and slope) change at the "
        "intervention, with Newey–West standard errors (12 lags); the 2019 design adds a control "
        "group of roads and estimates the treated group's own change.</li>"
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
        f'<p>Everything on this site is generated by Python scripts in the <a href="{REPO_URL}">repository</a>, '
        "run from its root in this order. Times are for a laptop-class machine.</p>"
        "<ol>"
        "<li><code>python scripts/ingest.py all</code>: reads every raw file into Parquet, transcribes the "
        "speed report and runs the reconciliation checks (about six minutes, most of it the nine "
        "microdata workbooks).</li>"
        "<li><code>python scripts/build_tables.py</code>: adds the derived fields and English labels to "
        "the crash table (seconds).</li>"
        "<li><code>python scripts/model.py</code>: fits the two severity models and their checks (about "
        "half a minute).</li>"
        "<li><code>python scripts/analyse.py all</code>: writes every result table and figure, including "
        "the rates, the interrupted time series and the speed summaries (under a minute).</li>"
        "<li><code>python scripts/build_site.py</code>: renders these pages from the committed tables "
        "and figures (seconds). The GitHub Pages workflow runs only this step, so the site never "
        "depends on a rebuild of the data.</li>"
        "</ol>"
        "<p><code>pytest</code> runs the data-contract and code tests; the reconciliation checks above "
        "are among them.</p>"
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
    "geography": page_geography,
    "older-drivers": page_older_drivers,
    "severity": page_severity,
    "vehicles": page_vehicles,
    "policy": page_policy,
    "speed": page_speed,
    "data": page_data,
}


def build(site_dir: Path = SITE_DIR) -> list[Path]:
    """Write every page, the stylesheet and the figures into ``site_dir``."""
    captions = read_captions()
    site_dir.mkdir(parents=True, exist_ok=True)
    figures_out = site_dir / "figures"
    if figures_out.exists():
        shutil.rmtree(figures_out)
    figures_out.mkdir()
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
