"""The frame every interactive tool page shares (see ``explore``)."""

from __future__ import annotations

from dgt_stats.site.components import esc, render_page


def tool_page(
    slug: str,
    title: str,
    lead: str,
    tool: str,
    notes: str,
    scripts: tuple[str, ...],
    fallback: str = "",
) -> str:
    """A tool page: one sentence on what it computes, the tool itself (hidden until its data load),
    a line shown instead when scripting is off or the data cannot load, and short notes on what
    the numbers are, with the links to the method."""
    fallback = fallback or (
        '<p class="tool-fallback" data-tool-fallback>This tool needs JavaScript. The results it '
        "draws on are on the pages linked below.</p>"
    )
    body = (
        f"{tool}{fallback}"
        f'<section class="tool-notes" aria-label="About these numbers">{notes}</section>'
    )
    head = '\n<script src="tools/tools.js" defer></script>' + "".join(
        f'\n<script src="{esc(path)}" defer></script>' for path in scripts
    )
    return render_page(slug, title, lead, body, head=head)
