"""The crash statistics explorer: Spain's police-recorded injury crashes, fatal crashes and deaths
within 30 days, by year, region, road type and crash type.

It reads ``reports/tables/explore_dgt_crashes.csv`` (:mod:`dgt_stats.crash_cells`), whose rows
are the non-empty cells of year x autonomous community x road type x crash type, and publishes it
compactly as ``tools/crash-explorer.json``: one label list per dimension and each row as the
positions of its labels followed by its counts. The page script (``assets/crash-explorer.js``)
adds up the rows the reader selects; the interval of a fatal share is the Wilson interval of
``Tools.wilson`` with the normal quantile published here. The years of the Catalan coding breaks
it names come from the tables that document them on the methodology page.
"""

from __future__ import annotations

from scipy import stats

from dgt_stats import crash_cells, regions
from dgt_stats.site.components import DOCS_URL, esc, read_table
from dgt_stats.site.tool_frame import tool_page

DATA_FILE = "crash-explorer.json"
TABLE = f"{crash_cells.NAME}.csv"
# A cell with fewer injury crashes than this is flagged as resting on little data.
MIN_SUPPORT = 20
# The outcomes the reader can choose: key, label in the menu.
OUTCOMES = (
    ("crashes", "Injury crashes"),
    ("fatal", "Fatal crashes"),
    ("deaths", "Deaths within 30 days"),
    ("fatal_share", "Fatal crashes per 100 crashes"),
    ("deaths_rate", "Deaths per 100 crashes"),
    ("user", "Deaths of one road-user group"),
)
BREAKDOWNS = (
    ("year", "Year"),
    ("region", "Region"),
    ("road", "Road type"),
    ("type", "Crash type"),
)


def _table():
    return read_table(crash_cells.NAME)


def _years(table) -> tuple[int, int]:
    return int(table.year.min()), int(table.year.max())


def _levels(values, order) -> list[str]:
    present = set(values)
    return [level for level in order if level in present]


def _coding_breaks() -> dict[str, object]:
    """The years of the Catalan coding breaks the data page describes (``data._coding_breaks``)."""
    coding = read_table("gen_coding_by_region")
    catalonia = coding[coding.region == "Catalonia"].set_index("year")
    switch = int(catalonia[catalonia.road_type_5_dual_carriageway.eq(0)].index.min())
    other = read_table("q2_other_road_by_period")
    junctions = read_table("dgt_audit_junction_coding")
    inverted = sorted(
        int(year) for year in junctions[junctions.junction_flag_inverted.astype(bool)].year.unique()
    )
    return {
        "dualUntil": switch - 1,
        "otherFrom": int(other.period.iloc[-1]),
        "junction": [inverted[0], inverted[-1]],
    }


def describe() -> dict[str, str]:
    first, last = _years(_table())
    return {
        "title": "Crash statistics explorer",
        "what": "Recorded injury crashes, fatal crashes and deaths by year, region, road type and "
        "crash type, with fatal shares and their intervals.",
        "coverage": f"Spain, crashes recorded in {first}–{last}",
        "kind": "Observed counts and shares",
    }


def data_files() -> dict[str, object]:
    table = _table()
    dimensions = {
        "years": sorted(int(year) for year in table.year.unique()),
        "regions": _levels(table.community, regions.COMMUNITIES),
        "roads": _levels(
            table.road_type, [*crash_cells.ROAD_TYPES.values(), crash_cells.NOT_RECORDED]
        ),
        "types": _levels(table.crash_type, [*crash_cells.CRASH_TYPES, crash_cells.NOT_RECORDED]),
    }
    position = {
        "year": {year: i for i, year in enumerate(dimensions["years"])},
        "community": {name: i for i, name in enumerate(dimensions["regions"])},
        "road_type": {name: i for i, name in enumerate(dimensions["roads"])},
        "crash_type": {name: i for i, name in enumerate(dimensions["types"])},
    }
    rows = [
        [position[column][value] for column, value in zip(crash_cells.DIMENSIONS, row[:4])]
        + [int(count) for count in row[4:]]
        for row in table[[*crash_cells.DIMENSIONS, *crash_cells.COUNTS]].itertuples(
            index=False, name=None
        )
    ]
    return {
        DATA_FILE: {
            **dimensions,
            "users": [label for label, _ in crash_cells.ROAD_USERS.values()],
            "notRecorded": crash_cells.NOT_RECORDED,
            "catalonia": dimensions["regions"].index("Catalonia"),
            "breaks": _coding_breaks(),
            "minSupport": MIN_SUPPORT,
            "z": float(stats.norm.ppf(0.975)),
            "rows": rows,
        }
    }


def _select(name: str, label: str, options: tuple[tuple[str, str], ...] = ()) -> str:
    items = "".join(f'<option value="{esc(v)}">{esc(t)}</option>' for v, t in options)
    return (
        f'<div class="tool-field" data-field="{name}"><label for="ce-{name}">{esc(label)}</label>'
        f'<select id="ce-{name}" name="{name}">{items}</select></div>'
    )


def _tool() -> str:
    """The controls, filled with the table's labels by the page script, and the result."""
    crashes = (
        _select("from", "From")
        + _select("to", "To")
        + _select("region", "Region")
        + _select("road", "Road type")
        + _select("type", "Crash type")
    )
    result = (
        _select("outcome", "Show", OUTCOMES)
        + _select("user", "Road user")
        + _select("by", "Break down by", BREAKDOWNS)
    )
    return (
        f'<div class="tool" data-tool="crash-explorer" data-src="tools/{DATA_FILE}" hidden>'
        '<div class="tool-layout">'
        '<form class="tool-controls" aria-label="Choose the crashes and the result">'
        f'<fieldset><legend>Crashes</legend><div class="tool-fields">{crashes}</div></fieldset>'
        f'<fieldset><legend>Result</legend><div class="tool-fields">{result}</div></fieldset>'
        "</form>"
        '<div class="tool-result">'
        '<p class="tool-headline" data-headline></p>'
        '<p class="tool-meaning" data-scope></p>'
        '<div class="tool-chart" data-chart></div>'
        '<div class="tool-table table-wrap" data-table tabindex="0" role="region" '
        'aria-label="The figures behind the chart"></div>'
        '<ul class="tool-caveats" data-caveats></ul>'
        "</div></div>"
        '<p class="visually-hidden" role="status" aria-live="polite" data-status></p>'
        "</div>"
    )


def page_crash_explorer(captions: dict[str, str]) -> str:
    del captions
    first, last = _years(_table())
    notes = (
        "<p>The counts are the injury crashes the police recorded in DGT's crash records, "
        f"{first}–{last}: crashes in which at least one person was killed or injured "
        '(<a href="data.html#definitions">definitions</a>). A fatal crash is one with at least '
        "one death within 30 days. Shares are among recorded injury crashes, not rates per "
        'person, vehicle or kilometre driven; the <a href="long-run.html">long-run trends</a> '
        "set deaths against vehicles and distance driven.</p>"
        "<p>Region is the autonomous community of the province where the crash happened. Road "
        "types group DGT's road codes as the methodology defines road groups, and DGT's "
        "run-off-road crash types (by side and outcome) count as one. Deaths of riders of "
        "personal mobility vehicles count under others and not specified. Changes in how some "
        'records are coded are listed under <a href="data.html#coding-breaks">coding '
        "breaks</a>.</p>"
        f'<p>The <a href="tables/{TABLE}">full table (CSV)</a> has one row per year, region, '
        "road type and crash type with at least one recorded crash. How it is built, and its "
        f'check against DGT\'s published yearly totals: <a href="{DOCS_URL}/methodology.md">'
        "methodology</a>.</p>"
    )
    return tool_page(
        "crash-explorer",
        "Crash statistics explorer",
        "Spain's recorded injury crashes, fatal crashes and deaths, for the years, region, road "
        "type and crash type you choose.",
        _tool(),
        notes,
        ("tools/crash-explorer.js",),
    )
