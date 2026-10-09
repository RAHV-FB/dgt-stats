"""The interactive tools: a landing page that lists them, and the frame every tool page shares.

Each tool is a module of its own (``tool_calculator``, ``tool_driver_risk``, ``tool_crashes``,
``tool_trends``) with a ``describe()`` for the landing page, a page builder, and the data it
publishes as JSON (``data_files()``), computed at build time from the committed result tables or
the exported model. The tools' scripts are in ``assets``: ``tools.js`` holds what they share
(number formats, the two charts), and each tool has one script of its own. The browser only reads
and arranges the published numbers; no statistic is typed into a script.
"""

from __future__ import annotations

from dgt_stats.site import tool_calculator, tool_crashes, tool_driver_risk, tool_trends
from dgt_stats.site.components import esc, render_page

# The tools in the order the landing page lists them: slug, module.
TOOLS = (
    ("calculator", tool_calculator),
    ("driver-risk", tool_driver_risk),
    ("crash-explorer", tool_crashes),
    ("trends-explorer", tool_trends),
)


def page_explore(captions: dict[str, str]) -> str:
    """The landing page: each tool with what it computes, the area and years it covers, and the
    kind of result it gives."""
    del captions
    items = []
    for slug, module in TOOLS:
        about = module.describe()
        items.append(
            '<li class="tool-card">'
            f'<h2><a href="{slug}.html">{esc(about["title"])}</a></h2>'
            f"<p>{esc(about['what'])}</p>"
            '<dl class="tool-facts">'
            f"<div><dt>Covers</dt><dd>{esc(about['coverage'])}</dd></div>"
            f"<div><dt>Result</dt><dd>{esc(about['kind'])}</dd></div>"
            "</dl></li>"
        )
    body = (
        '<ul class="tool-list">' + "".join(items) + "</ul>"
        '<p class="tool-landing-note">Each tool computes from the same published tables and model '
        'as the analysis pages; how they were produced is on the <a href="data.html">methodology'
        "</a> page.</p>"
    )
    return render_page(
        "explore",
        "Interactive tools",
        "Calculators and explorers that compute results from the site's data for the cases and "
        "periods you choose.",
        body,
    )
