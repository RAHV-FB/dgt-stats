"""The trends and rates explorer: Spain's annual road-safety series as counts and as rates, for a
period the reader chooses, with the change between its two ends.

Question: how road deaths, hospital admissions and injury crashes in Spain have changed, as counts
and against residents, registered vehicles, road fuel sold or measured kilometres. Unit: the
calendar year. Sources: DGT's yearbook series (``risk_annual_panel``: deaths within 30 and 24
hours, people admitted to hospital, injury crashes, the registered fleet; INE residents; CORES road
fuel) and the Ministerio de Transportes' measured vehicle-kilometres on interurban roads with the
interurban deaths (``longrun_km_panel``). Each indicator is published only for the years both its
numerator and its denominator exist; nothing is interpolated. Results are observed counts and
ratios of observed counts; the notes say what each one covers.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import risk_trends
from dgt_stats.site.components import read_table
from dgt_stats.site.tool_frame import tool_page

# Each indicator: id, label, unit sentence, the numerator and denominator columns, the scale the
# ratio is multiplied by, the decimals it is shown with, and a note on what it covers.
INDICATORS = (
    ("deaths_30d", "Deaths within 30 days", "deaths", "deaths_30d", None, 1, 0),
    ("deaths_24h", "Deaths within 24 hours", "deaths", "deaths_24h", None, 1, 0),
    (
        "hospitalised_30d",
        "People admitted to hospital",
        "people admitted to hospital",
        "hospitalised_30d",
        None,
        1,
        0,
    ),
    ("crashes", "Injury crashes", "injury crashes", "crashes", None, 1, 0),
    (
        "crashes_interurban",
        "Injury crashes on interurban roads",
        "injury crashes on interurban roads",
        "crashes_interurban",
        None,
        1,
        0,
    ),
    (
        "crashes_urban",
        "Injury crashes in urban areas",
        "injury crashes in urban areas",
        "crashes_urban",
        None,
        1,
        0,
    ),
    (
        "deaths_per_million_residents",
        "Deaths per million residents",
        "deaths within 30 days per million residents",
        "deaths_30d",
        "residents",
        1_000_000,
        1,
    ),
    (
        "deaths_per_100k_vehicles",
        "Deaths per 100,000 registered vehicles",
        "deaths within 30 days per 100,000 registered vehicles",
        "deaths_30d",
        "vehicle_fleet",
        100_000,
        2,
    ),
    (
        "deaths_per_100k_tonnes_fuel",
        "Deaths per 100,000 tonnes of road fuel sold",
        "deaths within 30 days per 100,000 tonnes of road fuel sold",
        "deaths_30d",
        "road_fuel_tonnes",
        100_000,
        2,
    ),
    (
        "deaths_per_100_crashes",
        "Deaths per 100 injury crashes",
        "deaths within 30 days per 100 injury crashes",
        "deaths_30d",
        "crashes",
        100,
        2,
    ),
    (
        "interurban_deaths_per_bn_km",
        "Interurban deaths per billion vehicle-km",
        "deaths on interurban roads per billion vehicle-kilometres measured on them",
        "deaths_interurban",
        "vehicle_km",
        1_000_000_000,
        2,
    ),
)


def _notes() -> dict[str, str]:
    counted_from = risk_trends.DEATHS_30D_COUNTED_FROM
    deaths_30d = (
        "Deaths within 30 days of the crash. Up to "
        f"{counted_from - 1} DGT estimated them from deaths within 24 hours with correction "
        f"factors; from {counted_from} it counts them by matching crash records with the register "
        "of deaths."
    )
    return {
        "deaths_30d": deaths_30d,
        "deaths_24h": "Deaths within 24 hours of the crash, counted by the police in every year.",
        "hospitalised_30d": "Injured people admitted to hospital, counted within 30 days of the "
        "crash (DGT yearbook).",
        "crashes": "Crashes with at least one person killed or injured, as recorded by the "
        "police. Crashes with no injury are not counted.",
        "crashes_interurban": "Injury crashes on roads outside towns.",
        "crashes_urban": "Injury crashes on urban streets and roads within towns.",
        "deaths_per_million_residents": deaths_30d + " Residents: INE population on 1 July.",
        "deaths_per_100k_vehicles": deaths_30d + " Vehicles: DGT's registered fleet, which "
        "includes vehicles that are seldom driven.",
        "deaths_per_100k_tonnes_fuel": deaths_30d + " Road fuel (petrol and diesel sold for road "
        "use, CORES) stands in for traffic on all roads; it is not a measure of distance.",
        "deaths_per_100_crashes": deaths_30d + " The ratio says how deadly recorded injury "
        "crashes were, not how often they happened.",
        "interurban_deaths_per_bn_km": "Deaths within 30 days on interurban roads against the "
        "vehicle-kilometres the Ministerio de Transportes measures on the State, regional and "
        "provincial networks, which cover nearly the same roads. Only the years whose kilometres "
        "are comparable are shown; the latest year is partly estimated in the source.",
    }


def _series() -> pd.DataFrame:
    panel = read_table("risk_annual_panel").set_index("year")
    km = read_table("longrun_km_panel").set_index("year")
    km = km[km.comparable.astype(bool)]
    return panel.join(km[["deaths_interurban", "vehicle_km"]], how="left")


def indicators() -> list[dict[str, object]]:
    """Every indicator with the years it exists and its value in each, computed from the tables."""
    series = _series()
    notes = _notes()
    out = []
    for key, label, unit, numerator, denominator, scale, decimals in INDICATORS:
        values = series[numerator].astype(float)
        if denominator is not None:
            values = values / series[denominator].astype(float) * scale
        values = values.dropna()
        if values.empty:
            raise ValueError(f"trends explorer: {key} has no year with data")
        years = [int(year) for year in values.index]
        if years != list(range(years[0], years[-1] + 1)):
            raise ValueError(f"trends explorer: {key} has a gap in its years")
        out.append(
            {
                "id": key,
                "label": label,
                "unit": unit,
                "decimals": decimals,
                "first": years[0],
                "values": [round(float(v), 6) for v in values],
                "note": notes[key],
                "rate": denominator is not None,
            }
        )
    return out


def describe() -> dict[str, str]:
    found = indicators()
    first = min(int(item["first"]) for item in found)
    last = max(int(item["first"]) + len(item["values"]) - 1 for item in found)
    return {
        "title": "Trends and rates explorer",
        "what": "Road deaths, hospital admissions and injury crashes year by year, as counts or "
        "as rates per resident, registered vehicle, tonne of fuel or measured kilometre, with the "
        "change over the period you choose.",
        "coverage": f"Spain, {first}–{last} (each rate for the years its denominator exists)",
        "kind": "Observed counts and rates",
    }


def data_files() -> dict[str, object]:
    return {"trends-explorer.json": {"indicators": indicators()}}


def _controls() -> str:
    return (
        '<div class="tool-layout">'
        '<form class="tool-controls" data-controls>'
        '<fieldset><legend>Indicator</legend><div class="tool-fields">'
        '<div class="tool-field"><label for="trends-indicator">Show</label>'
        '<select id="trends-indicator" name="indicator"></select></div>'
        '<div class="tool-field"><label for="trends-compare">Compare with</label>'
        '<select id="trends-compare" name="compare"></select></div>'
        "</div></fieldset>"
        '<fieldset><legend>Period</legend><div class="tool-fields">'
        '<div class="tool-field"><label for="trends-from">From</label>'
        '<select id="trends-from" name="from"></select></div>'
        '<div class="tool-field"><label for="trends-to">To</label>'
        '<select id="trends-to" name="to"></select></div>'
        "</div></fieldset>"
        '<div class="tool-actions"><button type="button" data-reset>Reset</button></div>'
        "</form>"
        '<div class="tool-result" data-result>'
        '<p class="tool-headline" data-headline></p>'
        '<p class="tool-meaning" data-change></p>'
        '<div class="tool-chart" data-chart></div>'
        '<p class="tool-note" data-note></p>'
        '<details class="tool-table"><summary>Figures by year</summary>'
        '<div class="table-wrap"><table data-table></table></div></details>'
        "</div></div>"
        '<p class="visually-hidden" role="status" aria-live="polite" data-status></p>'
    )


def page_trends_explorer(captions: dict[str, str]) -> str:
    del captions
    tool = (
        '<section class="tool" data-tool="trends-explorer" data-src="tools/trends-explorer.json" '
        'aria-label="Trends and rates explorer" hidden>' + _controls() + "</section>"
    )
    notes = (
        "<p>Every figure is a count or a ratio of counts published by DGT, INE, CORES and the "
        "Ministerio de Transportes; a rate is shown only for the years its denominator exists, "
        "and no year is filled in. Comparing two indicators shows each as an index, the first "
        "year of the period being 100.</p>"
        '<p>The long-run trend and how far recent years depart from it are on the <a href="long-'
        'run.html">long-run trends</a> page; definitions are on the <a href="data.html#rates">'
        "methodology</a> page.</p>"
    )
    return tool_page(
        "trends-explorer",
        "Trends and rates explorer",
        "Spain's road deaths, hospital admissions and injury crashes year by year, as counts or "
        "as rates, for the period you choose.",
        tool,
        notes,
        ("tools/trends-explorer.js",),
    )
