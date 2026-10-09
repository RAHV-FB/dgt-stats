"""The frame every interactive tool page shares (see ``explore``)."""

from __future__ import annotations

from dgt_stats.site.components import esc, render_page, technical

# What every tool states about itself, in this order (the ``about`` of each tool module).
ABOUT_TERMS = (
    ("question", "Question"),
    ("population", "Population"),
    ("unit", "Unit"),
    ("source", "Source"),
    ("variables", "What you can choose"),
    ("outcome", "Outcome"),
    ("denominator", "Denominator"),
    ("result", "Kind of result"),
    ("limitations", "Limitations"),
    ("validation", "How it is checked"),
)


def about_block(about: dict[str, str]) -> str:
    """The tool's definition, as a list a reader can open: what it answers, for whom, from what,
    and how far its numbers can be taken."""
    if set(about) != {key for key, _ in ABOUT_TERMS}:
        raise ValueError(f"a tool's description needs exactly {[k for k, _ in ABOUT_TERMS]}")
    items = "".join(f"<dt>{label}</dt><dd>{about[key]}</dd>" for key, label in ABOUT_TERMS)
    return technical("About this tool", f'<dl class="tool-about">{items}</dl>', anchor="about")


def tool_page(
    slug: str,
    title: str,
    lead: str,
    tool: str,
    notes: str,
    scripts: tuple[str, ...],
    fallback: str = "",
    about: dict[str, str] | None = None,
) -> str:
    """A tool page: one sentence on what it computes, the tool itself (hidden until its data load),
    a line shown instead when scripting is off or the data cannot load, and short notes on what
    the numbers are, with the links to the method and, where given, the tool's definition."""
    fallback = fallback or (
        '<p class="tool-fallback" data-tool-fallback>This tool needs JavaScript. The results it '
        "draws on are on the pages linked below.</p>"
    )
    body = (
        f"{tool}{fallback}"
        f'<section class="tool-notes" aria-label="About these numbers">{notes}'
        + (about_block(about) if about else "")
        + "</section>"
    )
    head = '\n<script src="tools/tools.js" defer></script>' + "".join(
        f'\n<script src="{esc(path)}" defer></script>' for path in scripts
    )
    return render_page(slug, title, lead, body, head=head)
