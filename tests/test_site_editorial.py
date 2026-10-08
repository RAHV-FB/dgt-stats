"""The public site reads as one piece of research, not as the machinery that built it.

These checks keep the site from drifting back to the old presentation: the page names and
navigation built around the repository's layers, the "Layer: … Unit: …" lines and source blocks
on every page, numbered findings on the front page, raw database field names in the prose, and
headings phrased as questions.
"""

import re
from html.parser import HTMLParser

import pytest

from dgt_stats import site, summaries
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR
from dgt_stats.site import components

pytestmark = pytest.mark.skipif(
    not (FIGURES_DIR / "captions.json").exists()
    or not (TABLES_DIR / "q1_annual_headline.csv").exists()
    or not (TABLES_DIR / "ml_model_decisions.csv").exists()
    or not summaries.model_tables_present(),
    reason="run `python scripts/model.py`, `python scripts/analyse.py all` and "
    "`python scripts/microdata.py all` first",
)

LIVE = tuple(slug for slug, _ in site.ALL_PAGES)
# The methodology page documents the data dictionary, so it may name a source field.
METHODOLOGY = "data"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    target = tmp_path_factory.mktemp("site")
    site.build(target)
    return {page.stem: page.read_text(encoding="utf-8") for page in target.glob("*.html")}


class _Visible(HTMLParser):
    """The text a reader sees in <main>: element text plus image alt text."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "main":
            self.depth += 1
        if self.depth and tag == "img":
            self.parts.append(dict(attrs).get("alt") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.parts.append(data)


def _visible(text: str) -> str:
    parser = _Visible()
    parser.feed(text)
    return " ".join(parser.parts)


def _main(text: str) -> str:
    return text[text.find("<main>") : text.find("</main>")]


def test_navigation_follows_the_argument(built: dict[str, str]) -> None:
    assert [group for group, _ in site.NAV_GROUPS] == [
        "Overview",
        "Over time",
        "Drivers, vehicles and factors",
        "Crash severity",
        "Data and methods",
    ]
    groups = dict(site.NAV_GROUPS)
    assert [slug for slug, _ in groups["Crash severity"]][-2:] == ["severity-models", "validation"]
    assert [slug for slug, _ in groups["Crash severity"]][1:3] == ["catalonia", "barcelona"]
    assert [slug for slug, _ in groups["Data and methods"]] == ["sources", "data"]
    assert dict(groups["Data and methods"])["sources"] == "Data sources and scope"
    nav = re.search(r'<nav aria-label="Sections">(.*?)</nav>', built["speed"], re.S).group(1)
    links = re.findall(r'href="([a-z-]+)\.html"', nav)
    assert links == list(components.READING_ORDER)
    # Each page names its group above the title and links to its neighbours in reading order.
    assert '<p class="eyebrow">Drivers, vehicles and factors</p>' in built["speed"]
    assert 'href="vehicles.html" rel="prev"' in built["speed"]
    assert 'href="factors.html" rel="next"' in built["speed"]
    assert '<p class="eyebrow">Over time</p>' in built["policy"]
    assert '<p class="eyebrow">Withdrawn analysis</p>' in built["forecast"]
    assert '<p class="eyebrow">Crash severity</p>' in built["validation"]
    assert '<p class="eyebrow">' not in built["index"]


def test_the_old_page_names_and_framing_are_gone(built: dict[str, str]) -> None:
    obsolete = (
        "Four layers of data",
        "The four layers",
        "How far the results reach",
        "earn their place",
        "earns its place",
        "Four questions",
        "Finding 1",
        "Spain: DGT and INE",
        "Spain: supporting",
        "Rich microdata",
        "Crash microdata: Catalonia",
        "Validation and transportability",
        "outward path",
        "One model or several",
        "What this site does not claim",
        "is the answer",
    )
    for slug in LIVE:
        for phrase in obsolete:
            assert phrase not in built[slug], (slug, phrase)
    # The old address of the validation page points to its successor.
    assert site.MOVED_PAGES["transport"] == "validation"
    assert 'content="0; url=validation.html"' in built["transport"]


def test_no_page_carries_the_old_layer_and_unit_boilerplate(built: dict[str, str]) -> None:
    for slug in LIVE:
        main = _main(built[slug])
        visible = _visible(built[slug])
        for markup in ('class="level"', '<details class="about">', 'class="finding"'):
            assert markup not in main, (slug, markup)
        assert "Source, coverage and unit" not in visible, slug
        assert not re.search(r"\b(Layers?|Units?): ", visible), slug
        # Validation is described in plain words, not in the vocabulary of the pipeline.
        for word in ("native", "in-domain", "transportability", "common-feature"):
            assert not re.search(rf"\b{word}\b", visible, re.I), (slug, word)
        # Decision codes stay in the generated model-decision record, off the pages.
        for code in ("KEEP as", "REPLACE with", "KEEP but"):
            assert code not in visible, (slug, code)


# A source column name (D_SUBZONA, ID_ACCIDENTE, TOTAL_MU24H, Numero_expedient) or a snake_case
# code (person_role, bus_or_coach) in the text a reader sees.
RAW_FIELD = re.compile(r"\b(?:[A-Z][A-Za-z0-9]*_[A-Za-z0-9_]+|[a-z][a-z0-9]*_[a-z0-9_]+)\b")


def test_no_raw_field_names_outside_the_methodology(built: dict[str, str]) -> None:
    for slug in LIVE:
        if slug == METHODOLOGY:
            continue
        found = sorted(set(RAW_FIELD.findall(_visible(built[slug]))))
        assert not found, (slug, found)


def test_no_figure_shows_a_raw_field_name() -> None:
    allowed = {"d1_missingness"}  # the methodology figure documents the source fields
    for path in sorted(FIGURES_DIR.glob("*.svg")):
        if path.stem in allowed:
            continue
        labels = re.findall(r"<text[^>]*>([^<]+)</text>", path.read_text(encoding="utf-8"))
        found = sorted({m for label in labels for m in RAW_FIELD.findall(label)})
        assert not found, (path.name, found)
        assert not any("-&gt;" in label or "->" in label for label in labels), path.name


def test_headings_and_leads_are_statements(built: dict[str, str]) -> None:
    for slug in LIVE:
        text = built[slug]
        for heading in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", text, re.S):
            assert "?" not in re.sub(r"<[^>]+>", "", heading), (slug, heading)
        lead = re.search(r'<p class="lead">(.*?)</p>', text, re.S).group(1)
        assert "?" not in lead, slug
        for opening in re.findall(r'<p class="summary">(.*?)</p>', text, re.S):
            assert "?" not in re.sub(r"<[^>]+>", "", opening), slug


def test_the_footer_is_short_and_shared(built: dict[str, str]) -> None:
    footers = {
        slug: re.search(r"<footer[^>]*>(.*?)</footer>", built[slug], re.S).group(1) for slug in LIVE
    }
    assert len(set(footers.values())) == 1
    footer = footers["index"]
    assert components.PROFILE_URL in footer and "Russell Howard" in footer
    for href in ('href="sources.html"', 'href="data.html"', f'href="{components.REPO_URL}"'):
        assert href in footer, href
    assert len(re.sub(r"<[^>]+>", "", footer)) < 600
    # The statement that every result is computed from the published files is made once, in the
    # footer and on the methodology page, not repeated in each page's own text.
    for slug in LIVE:
        if slug == METHODOLOGY:
            continue
        assert "regenerated from the raw files" not in _main(built[slug]), slug


def test_the_front_page_is_a_research_overview(built: dict[str, str]) -> None:
    main = _main(built["index"])
    assert "Finding" not in _visible(built["index"])
    assert '<div class="finding">' not in main
    assert not re.search(r"<h2>\d+\. ", main)
    for slug in ("trends", "drivers", "vehicles", "catalonia", "barcelona", "severity-models"):
        assert f'href="{slug}.html"' in main, slug
    for slug in ("validation", "data", "sources"):
        assert f'href="{slug}.html' in main, slug
    # The modelling is described in plain words, with the model that lost to its table named as
    # such, and the supporting association analysis is not presented as a model.
    visible = _visible(built["index"])
    assert "tested only within Catalonia" in visible
    assert "Association analysis of DGT crash records" not in visible


def test_the_models_page_leads_with_predicted_against_observed(built: dict[str, str]) -> None:
    visible = _visible(built["severity-models"])
    main = _main(built["severity-models"])
    # Predicted against observed, then the calculator, then what the model shows and a short
    # method; scores tables stay in the research documents. The headings say what each finds.
    headings = re.findall(r"<h2[^>]*>(.*?)</h2>", main, re.S)
    assert headings[:4] == [
        "The estimates matched what happened in later years",
        "Try the model",
        "Crashes involving a heavy vehicle: about twice the fatal share",
        "How the model was built",
    ]
    assert main.find("sev1_predicted_observed") < main.find('id="calculator"')
    # One name for the published model, and one scale for ranking skill, shared with the
    # External validation page: ROC-AUC to two decimals, explained once in plain words.
    assert "the Catalan severity model" in visible
    assert "times in 100" not in visible
    gloss = "given one fatal and one non-fatal crash, the share of pairs in which the fatal one"
    assert visible.count(gloss) == 1
    assert not re.search(r"ROC-AUC[^.]*\b0\.\d{3}\b", visible)
    # The calculator's result and comparison share a panel that sits beside the form when there
    # is room; the interval's scope is said beside the interval, not only in the limitations.
    assert '<div class="calc-layout"><form>' in main and '<div class="calc-panel">' in main
    assert "uncertainty of its coefficients" not in visible
    # What the calculator answers, and what its inputs are not, are said in plain words.
    assert "a posted limit is not a speed" in visible.lower()
    assert "cannot say whether a crash will happen" in visible
    assert "died within 24 hours" in visible
    # No withdrawn page is linked.
    assert 'href="forecast.html"' not in main


def test_the_validation_page_does_not_claim_national_transferability(
    built: dict[str, str],
) -> None:
    import pandas as pd

    path = pd.read_csv(TABLES_DIR / "ml_outward_path.csv")
    visible = _visible(built["validation"])
    if not path.verdict.eq("potentially nationally transferable").any():
        assert "nationally transferable" not in visible
        assert "national use of the models is not established" in visible
    # The two scores of a validation are named in plain words, the published and the retired
    # model each by one name, and ranking skill on the models page's scale.
    assert "fitted on the Catalan file alone" in visible
    assert re.search(r"fitted (in|within) the test population", visible)
    assert "the Catalan severity model" in visible and "original Catalan model (retired)" in visible
    # (Figure captions are written with the charts.)
    prose = re.sub(r"<figcaption>.*?</figcaption>", "", built["validation"], flags=re.S)
    assert "calculator's model" not in _visible(prose)
    assert visible.count("the share of pairs in which the fatal one gets the higher") == 1
    # No pair of headline numbers without intervals.
    assert 'class="compare"' not in built["validation"]


def test_pages_carry_no_template_furniture(built: dict[str, str]) -> None:
    # The opening summary carries a page's result: no indicator strip repeats it, no generic
    # "Conclusion" or "Interpretation" heading closes it, and the supporting analyses say what
    # they are through the line above their title rather than in their prose.
    for slug in LIVE:
        main = _main(built[slug])
        assert 'class="figures"' not in main and 'class="keyfig"' not in main, slug
        for heading in ("Conclusion", "Interpretation", "Limits"):
            assert f"<h2>{heading}</h2>" not in main, (slug, heading)
        prose = main.replace('<p class="eyebrow">Spain · supporting analysis</p>', "")
        assert "upporting analysis" not in prose, slug
        assert main.count('<p class="summary">') == 1, slug
