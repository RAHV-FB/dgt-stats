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
        "<li><strong>Statistical tables 2014–2024</strong>: province, month, vehicle and involvement "
        "tables for 2024; driver victims and drivers involved by age, sex and vehicle type for every "
        "year (chapter workbooks up to 2019, one workbook per year from 2020).</li>"
        "<li><strong>Driver census 2014–2025</strong>: licence holders by age band and sex from the "
        "published class-by-age tables (2014–2023) and the province-by-age text files (2024–2025); "
        "<strong>ITV kilometre estimates 2022</strong>.</li>"
        "<li><strong>INE resident population</strong> (Estadística Continua de Población, table 56947): "
        "province by five-year age group and sex, 1 January and 1 July, 2002–2025.</li>"
        "<li><strong>Driving activity</strong>: ESRA 2018 and 2023 national shares of adults who drive "
        "(Spain), MOVILIA 2006 trips by mode, sex and age. No Spanish source gives the share of people "
        "who drive by age.</li>"
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
        "<li><strong>Rates</strong>: counts are treated as Poisson with a known denominator; intervals "
        "are exact 95% intervals. Residents are INE's estimate on 1 July of the year; licence holders "
        "are DGT's census (people holding a driving permit or a moped or agricultural licence). "
        "Drivers with unknown age (about 3% of those involved, 0.4% of those killed) are excluded from "
        "the age-band rates.</li>"
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
    "geography": page_geography,
    "older-drivers": page_older_drivers,
    "severity": page_severity,
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
