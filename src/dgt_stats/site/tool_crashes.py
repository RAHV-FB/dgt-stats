"""The crash statistics explorer: Spain's recorded injury crashes, from the DGT crash records."""

from __future__ import annotations

from dgt_stats.site.tool_frame import tool_page


def describe() -> dict[str, str]:
    return {
        "title": "Crash statistics explorer",
        "what": "Recorded injury crashes, fatal crashes and deaths by year, region, road type and crash type.",
        "coverage": "Spain",
        "kind": "Observed counts and shares",
    }


def data_files() -> dict[str, object]:
    return {}


def page_crash_explorer(captions: dict[str, str]) -> str:
    del captions
    return tool_page(
        "crash-explorer",
        "Crash statistics explorer",
        "Spain's recorded injury crashes and deaths, by the breakdown you choose.",
        '<div class="tool" data-tool="crash-explorer" hidden></div>',
        "<p>This tool is being built.</p>",
        ("tools/crash-explorer.js",),
    )
