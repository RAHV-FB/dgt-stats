"""The driver risk comparison: two groups of car drivers side by side, from the driver-age tables."""

from __future__ import annotations

from dgt_stats.site.tool_frame import tool_page


def describe() -> dict[str, str]:
    return {
        "title": "Driver risk comparison",
        "what": "Crash involvement and deaths of car drivers of two age groups or sexes, side by side.",
        "coverage": "Spain",
        "kind": "Observed rates and assumption-dependent estimates",
    }


def data_files() -> dict[str, object]:
    return {}


def page_driver_risk(captions: dict[str, str]) -> str:
    del captions
    return tool_page(
        "driver-risk",
        "Driver risk comparison",
        "Crash involvement and deaths of car drivers of two groups, side by side.",
        '<div class="tool" data-tool="driver-risk" hidden></div>',
        "<p>This tool is being built.</p>",
        ("tools/driver-risk.js",),
    )
