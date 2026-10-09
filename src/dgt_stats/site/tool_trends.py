"""The trends and rates explorer: Spain's annual series, from the national tables."""

from __future__ import annotations

from dgt_stats.site.tool_frame import tool_page


def describe() -> dict[str, str]:
    return {
        "title": "Trends and rates explorer",
        "what": "Road deaths, hospital admissions and injury crashes over time, as counts or rates.",
        "coverage": "Spain",
        "kind": "Observed counts and rates",
    }


def data_files() -> dict[str, object]:
    return {}


def page_trends_explorer(captions: dict[str, str]) -> str:
    del captions
    return tool_page(
        "trends-explorer",
        "Trends and rates explorer",
        "Road deaths, injuries and crashes over time, as counts or as rates.",
        '<div class="tool" data-tool="trends-explorer" hidden></div>',
        "<p>This tool is being built.</p>",
        ("tools/trends-explorer.js",),
    )
