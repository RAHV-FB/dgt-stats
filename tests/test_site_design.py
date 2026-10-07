"""The site's structure and presentation: one design system, applied the same way on every page.

These checks are about the markup a reader, a keyboard or a screen reader meets, not about pixels:
titles and headings, links that resolve, tables and figures that carry their own labels, the
navigation and contents lists, and a stylesheet built from one set of tokens.
"""

import re
from pathlib import Path

import pytest

from dgt_stats import site, summaries
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR
from dgt_stats.site import components
from dgt_stats.site.style import STYLE

pytestmark = pytest.mark.skipif(
    not (FIGURES_DIR / "captions.json").exists()
    or not (TABLES_DIR / "q1_annual_headline.csv").exists()
    or not summaries.model_tables_present(),
    reason="run `python scripts/model.py` and `python scripts/analyse.py all` first",
)

LIVE = tuple(slug for slug, _ in site.ALL_PAGES)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("site")
    site.build(target)
    return target


@pytest.fixture(scope="module")
def pages(built: Path) -> dict[str, str]:
    return {page.stem: page.read_text(encoding="utf-8") for page in built.glob("*.html")}


def _main(text: str) -> str:
    return text[text.find("<main>") : text.find("</main>")]


def _plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment)).strip()


def test_every_page_has_a_viewport_one_title_and_one_heading(pages: dict[str, str]) -> None:
    for slug, text in pages.items():
        assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in text
        assert text.count("<h1>") == 1 and text.count("<title>") == 1, slug
        h1 = _plain(re.search(r"<h1>(.*?)</h1>", text, re.S).group(1))
        title = re.search(r"<title>(.*?)</title>", text, re.S).group(1)
        expected = site.esc(h1) if slug == "index" else f"{site.esc(h1)} · Road safety in Spain"
        assert title == expected, slug


def test_headings_descend_one_level_at_a_time(pages: dict[str, str]) -> None:
    for slug in LIVE:
        levels = [int(level) for level in re.findall(r"<h([1-6])[ >]", _main(pages[slug]))]
        assert levels[0] == 1, slug
        for before, after in zip(levels, levels[1:]):
            assert after <= before + 1, (slug, before, after)


def test_internal_links_and_anchors_resolve(built: Path, pages: dict[str, str]) -> None:
    ids = {slug: set(re.findall(r'\bid="([^"]+)"', text)) for slug, text in pages.items()}
    for slug, text in pages.items():
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, anchor = href.partition("#")
            target = path[: -len(".html")] if path.endswith(".html") else slug
            if path and not path.endswith(".html"):
                assert (built / path).exists(), (slug, href)
                continue
            assert target in pages, (slug, href)
            if anchor:
                assert anchor in ids[target], (slug, href)
        # Every id on a page is unique.
        found = re.findall(r'\bid="([^"]+)"', text)
        assert len(found) == len(set(found)), slug


def test_the_skip_link_reaches_the_page_opening(pages: dict[str, str]) -> None:
    for slug, text in pages.items():
        assert '<a class="skip-link" href="#content">Skip to content</a>' in text, slug
        assert '<header class="page-header" id="content">' in text, slug


def test_the_navigation_holds_only_live_pages_and_marks_the_current_one(
    pages: dict[str, str],
) -> None:
    hidden = set(site.WITHDRAWN_PAGES) | set(site.MOVED_PAGES)
    for slug in LIVE:
        nav = re.search(r'<nav aria-label="Sections">(.*?)</nav>', pages[slug], re.S).group(1)
        linked = re.findall(r'href="([a-z-]+)\.html"', nav)
        assert linked == list(components.READING_ORDER), slug
        assert not hidden & set(linked), slug
        assert nav.count('aria-current="page"') == 1, slug
        assert f'href="{slug}.html" aria-current="page"' in nav, slug
    for slug in site.WITHDRAWN_PAGES:
        assert '<meta name="robots" content="noindex">' in pages[slug], slug


def test_every_table_has_a_caption_and_header_cells(pages: dict[str, str]) -> None:
    for slug in LIVE:
        main = _main(pages[slug])
        blocks = re.findall(r'<div class="table-block">.*?</table></div></div>', main, re.S)
        assert len(blocks) == len(re.findall(r"<table[ >]", main)), slug
        for block in blocks:
            # The title is outside the box that scrolls, and the caption repeats it unseen.
            title = re.search(r'<p class="table-title" aria-hidden="true">([^<]+)</p>', block)
            assert title and not title.group(1).endswith("."), slug
            assert block.index(title.group(0)) < block.index('<div class="table-wrap"'), slug
            caption = re.search(r'<caption class="visually-hidden">(.*?)</caption>', block, re.S)
            assert caption and caption.group(1).startswith(site.esc(title.group(1))[:20]), slug
            head = re.search(r"<thead>(.*?)</thead>", block, re.S).group(1)
            assert head.count("<th") == head.count('scope="col"') > 1, slug
            for row in re.findall(r"<tbody>.*?</tbody>", block, re.S)[0].split("</tr>")[:-1]:
                assert '<th scope="row"' in row, slug
            # Wide tables scroll inside their own region, with a note shown only when they do.
            assert '<p class="table-tools" hidden>' in block, slug


def test_every_figure_has_a_title_alt_text_caption_and_source(
    built: Path, pages: dict[str, str]
) -> None:
    for slug in LIVE:
        for html in re.findall(r"<figure.*?</figure>", _main(pages[slug]), re.S):
            name = re.search(r'src="figures/([^"]+)\.svg"', html).group(1)
            assert (built / "figures" / f"{name}.svg").exists(), (slug, name)
            assert f'<p class="figure-title" id="figure-{name}">' in html, (slug, name)
            assert f'aria-labelledby="figure-{name}"' in html, (slug, name)
            alt = re.search(r'alt="([^"]*)"', html).group(1)
            assert len(alt) > 30, (slug, name)
            assert re.search(r'width="\d+" height="\d+"', html), (slug, name)
            assert '<p class="figure-source">Source: ' in html, (slug, name)
            caption = re.search(r"<figcaption><p>(.*?)</p>", html, re.S).group(1)
            assert len(_plain(caption)) > 40, (slug, name)


def test_long_pages_have_contents_and_short_pages_do_not(pages: dict[str, str]) -> None:
    for slug in LIVE:
        text = pages[slug]
        rail = re.search(r'<aside class="toc-rail">(.*?)</aside>', text, re.S)
        inline = re.search(r'<details class="toc-inline">(.*?)</details>', text, re.S)
        assert bool(rail) == bool(inline), slug
        if not rail:
            continue
        sections = re.findall(r'<h2 id="([^"]+)"', _main(text))
        listed = re.findall(r'href="#([^"]+)"', rail.group(1))
        # The contents list every section of the argument, in order, but not the closing
        # 'Data and method' block.
        assert listed == [anchor for anchor in sections if anchor != "data-and-method"], slug
        assert re.findall(r'href="#([^"]+)"', inline.group(1)) == listed, slug
    assert '<aside class="toc-rail">' not in pages["index"]
    # The inline contents follow the opening summary, and any headline number set right after it.
    for slug in LIVE:
        main = _main(pages[slug])
        if '<details class="toc-inline">' not in main:
            continue
        before = main[: main.index('<details class="toc-inline">')]
        between = before[before.index('<p class="summary">') :].split("</p>", 1)[1]
        assert "<h2" not in between and "<p>" not in between, slug
        assert between == "" or re.fullmatch(
            r'<div class="(compare|key-result)">.*</div>', between, re.S
        ), slug


def test_technical_details_and_limitations_use_one_form(pages: dict[str, str]) -> None:
    for slug in LIVE:
        main = _main(pages[slug])
        # Every disclosure is either the contents list or a technical block with a specific label.
        details = re.findall(r'<details class="([^"]+)">', main)
        assert set(details) <= {"toc-inline", "technical"}, slug
        labels = re.findall(r'<details class="technical"><summary>([^<]+)</summary>', main)
        assert len(labels) == len(set(labels)), slug
        for label in labels:
            assert len(label) > 10 and label.lower() not in {"details", "more", "technical"}
        for note in re.findall(r'<aside class="limit"[^>]*>(.*?)</aside>', main, re.S):
            assert '<span class="limit-label">Limitation' in note, slug
        # Every page closes on the same block: its tables, its method (the methodology page is
        # its own) and its sources.
        if slug != "index":
            block = re.search(r'<section class="data-method".*?</section>', main, re.S).group(0)
            terms = ["Result tables (CSV)", "Source documentation"]
            if slug != "data":
                terms.append("Method")
            for term in terms:
                assert f"<dt>{term}</dt>" in block, (slug, term)


def test_only_figure_sizes_are_set_inline(pages: dict[str, str]) -> None:
    for slug, text in pages.items():
        for style in re.findall(r'style="([^"]*)"', text):
            assert re.fullmatch(r"--w: \d+px; --w-small: \d+px", style), (slug, style)
        assert "<style" not in text, slug


def test_the_stylesheet_is_one_token_system() -> None:
    root = re.search(r":root \{(.*?)\}", STYLE, re.S).group(1)
    for token in (
        "--bg",
        "--text",
        "--text-muted",
        "--rule",
        "--surface",
        "--accent",
        "--measure",
        "--wide",
        "--radius",
        "--space-1",
        "--text-base",
    ):
        assert f"{token}:" in root, token
    # Colours are set once, as tokens, and redefined only for dark mode and for print.
    rules = re.sub(r":root \{.*?\}", "", STYLE, flags=re.S)
    colours = re.findall(r"#[0-9a-fA-F]{3,6}\b", rules)
    assert not colours, colours
    # A system font stack, no web fonts, gradients or animation beyond reduced-motion-aware
    # scrolling, and print and dark-mode rules.
    assert "@import" not in STYLE and "@font-face" not in STYLE and "url(" not in STYLE
    assert "gradient" not in STYLE and "@keyframes" not in STYLE
    assert "system-ui" in STYLE
    for media in ("prefers-color-scheme: dark", "prefers-reduced-motion", "@media print"):
        assert media in STYLE, media
    assert ":focus-visible" in STYLE
    assert "font-variant-numeric: tabular-nums" in STYLE
