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
        "Explore",
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
    assert links == [slug for _, pages in site.NAV_GROUPS for slug, _ in pages]
    # Each page names its group above the title and links to its neighbours in reading order.
    assert '<p class="eyebrow">Drivers, vehicles and factors</p>' in built["speed"]
    assert 'href="vehicles.html" rel="prev"' in built["speed"]
    assert 'href="factors.html" rel="next"' in built["speed"]
    assert '<p class="eyebrow">Over time</p>' in built["policy"]
    assert '<p class="eyebrow">Explore</p>' in built["calculator"]
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
    # Every figure, and its drawing for a phone's column in narrow/; the missing-values figure
    # names DGT's fields in English too.
    for path in sorted(FIGURES_DIR.rglob("*.svg")):
        labels = re.findall(r"<text[^>]*>([^<]+)</text>", path.read_text(encoding="utf-8"))
        found = sorted({m for label in labels for m in RAW_FIELD.findall(label)})
        assert not found, (path.name, found)
        assert not any("-&gt;" in label or "->" in label for label in labels), path.name


def test_headings_and_leads_are_statements(built: dict[str, str]) -> None:
    for slug in LIVE:
        text = built[slug]
        for heading in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", text, re.S):
            assert "?" not in re.sub(r"<[^>]+>", "", heading), (slug, heading)
        # The page's one-sentence description: its search description, shown under the title
        # only on the home page and the tool pages (a page with a summary does not open twice).
        lead = re.search(r'<meta name="description" content="([^"]*)">', text).group(1)
        assert "?" not in lead, slug
        opens_with_lead = slug in ("index", "explore", *components.TOOL_SLUGS)
        assert ('<p class="lead">' in text) == opens_with_lead, slug
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
    # The interactive tools are reached from the top of the page, before the findings.
    assert main.find('<p class="summary">') < main.find('href="explore.html"') < main.find("<h2")
    # The modelling is described in plain words, with the model that lost to its table named as
    # such, and the supporting association analysis is not presented as a model.
    visible = _visible(built["index"])
    assert "tested only within Catalonia" in visible
    assert "Association analysis of DGT crash records" not in visible


def test_the_models_page_leads_with_predicted_against_observed(built: dict[str, str]) -> None:
    visible = _visible(built["severity-models"])
    main = _main(built["severity-models"])
    # Predicted against observed, what the model shows and where it was tested; how it was
    # built and the scores are on the Model method and tests page. The headings say what each
    # finds.
    headings = re.findall(r"<h2[^>]*>(.*?)</h2>", main, re.S)
    assert headings[:3] == [
        "The estimates matched later years overall, but not in every province",
        "Crashes involving a heavy vehicle: about twice the fatal share",
        "Tested only within Catalonia",
    ]
    assert main.find("sev1_predicted_observed") < main.find('id="calculator"')
    assert 'href="validation.html#later-years"' in main
    assert 'id="later-years"' in built["validation"]
    # One name for the published model; ranking skill is described by the fatal shares of the
    # fifths, and ROC-AUC is left to the Model method and tests page.
    assert "the Catalan severity model" in visible
    assert "times in 100" not in visible
    assert "ROC-AUC" not in visible
    # The calculator has its own page; the model page links to it at the old anchor.
    assert '<p id="calculator">' in main and 'href="calculator.html"' in main
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
    # The figure titles and captions, written with the charts, use the same names.
    for old in ("calculator's model", "Catalonia model", "Catalonia crash-severity", "trained"):
        assert old not in visible, old
    assert visible.count("the share of pairs in which the fatal one gets the higher") == 1
    # No pair of headline numbers without intervals.
    assert 'class="compare"' not in built["validation"]


# The regional crash-record pages and the methodology section that holds each one's technical
# notes.
RECORD_PAGES = {"catalonia": "catalonia-method", "barcelona": "barcelona-method"}


def test_record_pages_are_short_and_keep_their_detail_on_the_methodology_page(
    built: dict[str, str],
) -> None:
    import pandas as pd

    from dgt_stats.site.regional_common import _year_label

    for slug, notes in RECORD_PAGES.items():
        main = _main(built[slug])
        opening = re.sub(r"<[^>]+>", " ", re.search(r'<p class="summary">(.*?)</p>', main).group(1))
        assert 40 <= len(opening.split()) <= 90, (slug, len(opening.split()))
        # No paragraph of the argument runs long, and one to three figures and tables carry it.
        for block in _blocks(built[slug], "p"):
            assert len(block.split()) <= 100, (slug, block[:80])
        shown = main.count("<figure") + main.count('<div class="table-block">')
        assert 1 <= shown <= 3, (slug, shown)
        # The detail is not folded away on the page: it is a section of the methodology page,
        # which the page links to.
        assert '<details class="technical"' not in main, slug
        assert f'href="data.html#{notes}"' in main, slug
        assert f'<h2 id="{notes}">' in built["data"], slug
    # Catalonia's fatal shares by circumstance lead to the calculator built on the same file.
    assert 'href="calculator.html"' in _main(built["catalonia"])
    # Barcelona's records are one city's in one year, named in the opening, and the models
    # fitted on them give no probability.
    year = _year_label(pd.read_csv(TABLES_DIR / "bcn_person_severity_share.csv"))
    opening = re.search(r'<p class="summary">(.*?)</p>', built["barcelona"]).group(1)
    assert f"crashes in {year}:" in opening
    visible = " ".join(_visible(built["barcelona"]).split())
    assert "one year in one city" in visible
    assert "neither gives probabilities" in visible and "kept for research only" in visible


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
        if slug not in ("explore", *components.TOOL_SLUGS):
            assert main.count('<p class="summary">') == 1, slug


# The pages on deaths over time and the methodology section that holds each one's technical notes.
TIME_PAGES = {
    "long-run": "long-run-method",
    "trends": "trends-method",
    "seasons": "seasons-method",
    "policy": "policy-method",
}


def test_time_pages_are_short_and_keep_their_detail_on_the_methodology_page(
    built: dict[str, str],
) -> None:
    for slug, notes in TIME_PAGES.items():
        main = _main(built[slug])
        opening = re.sub(r"<[^>]+>", " ", re.search(r'<p class="summary">(.*?)</p>', main).group(1))
        assert 40 <= len(opening.split()) <= 90, (slug, len(opening.split()))
        # No paragraph of the argument runs long, and one to three figures and tables carry it.
        for block in _blocks(built[slug], "p"):
            assert len(block.split()) <= 100, (slug, block[:80])
        shown = main.count("<figure") + main.count('<div class="table-block">')
        assert 1 <= shown <= 3, (slug, shown)
        # The detail is not folded away on the page: it is a section of the methodology page,
        # which the page links to.
        assert '<details class="technical"' not in main, slug
        assert f'href="data.html#{notes}"' in main, slug
        assert f'<h2 id="{notes}">' in built["data"], slug
    # The yearly series can be explored from the pages that read them.
    for slug in ("long-run", "trends"):
        assert 'href="trends-explorer.html"' in _main(built[slug]), slug


# The pages that quote the figures for drivers aged 75 and over.
OLDER_PAGES = ("drivers", "index", "data")


def _blocks(text: str, tag: str) -> list[str]:
    """The plain text of every ``tag`` element in a page's <main>."""
    found = re.findall(rf"<{tag}\b[^>]*>(.*?)</{tag}>", _main(text), re.S)
    return [" ".join(components.html.unescape(re.sub(r"<[^>]+>", " ", f)).split()) for f in found]


def test_the_conditional_75_plus_estimate_is_never_read_alone(built: dict[str, str]) -> None:
    import pandas as pd

    from dgt_stats.exposure_risk import national

    split = pd.read_csv(TABLES_DIR / "risk_older_split.csv")
    madrid = split[(split.assumption == national.REFERENCE_SPLIT) & (split.group == "75+")].iloc[0]
    older = pd.read_csv(TABLES_DIR / "risk_older_sensitivity.csv").ratio_75_plus
    low, high = float(older.min()), float(older.max())
    ranges = (f"{low:.2f}–{high:.2f}", f"{low:.2f} to {high:.2f}")
    values = [f"{madrid.ratio_to_45_64:.2f}", f"{madrid.ratio_to_45_64:.1f}"]
    # The value as a quoted figure, not as one end of another interval or range printed at one
    # decimal ("2.1–3.4"); the conditional estimate's own interval is checked under (b).
    value = re.compile(
        r"(?<![\d.–])(" + "|".join(re.escape(v) for v in values) + r")(?![\d–]| to \d)"
    )
    intervals = [
        f"{madrid.ratio_low:.2f}–{madrid.ratio_high:.2f}",
        f"{madrid.ratio_low:.1f}–{madrid.ratio_high:.1f}",
    ]
    for slug in OLDER_PAGES:
        prose = _blocks(built[slug], "p") + _blocks(built[slug], "li")
        prose += _blocks(built[slug], "figcaption")
        for block in prose:
            for sentence in re.split(r"(?<=[.;:])\s+(?=[A-Z])", block):
                if value.search(sentence):
                    # (a) in a sentence naming Madrid, in a block with the full range.
                    assert "Madrid" in sentence, (slug, sentence)
                    assert any(r in block for r in ranges), (slug, block[:120])
            for match in value.finditer(block):
                # (e) the word "reference" never stands near the conditional value.
                near = block[max(0, match.start() - 40) : match.end() + 40]
                assert "reference" not in near, (slug, near)
            for interval in intervals:
                # (b) every printed interval of the conditional value is called a sampling one.
                for match in re.finditer(re.escape(interval), block):
                    before = block[max(0, match.start() - 60) : match.start()]
                    assert "sampling" in before, (slug, before)
        for row in re.findall(r"<tr>(.*?)</tr>", _main(built[slug]), re.S):
            plain = " ".join(re.sub(r"<[^>]+>", " ", row).split())
            if value.search(plain) and "75" in plain:
                table = _main(built[slug])
                caption = table[: table.find(row)].rsplit("<caption", 1)[-1]
                assert "Madrid" in plain, (slug, plain)
                assert any(r in plain or r in caption for r in ranges), (slug, plain)


def test_older_driver_wording_carries_no_probability_or_ranking(built: dict[str, str]) -> None:
    banned = (
        r"\b\d+ of (the )?\d+ combinations",
        r"most combinations",
        r"best estimate",
        r"most likely",
        r"can only be estimated by borrowing",
        r"the rate for 75 and over",
    )
    for slug in OLDER_PAGES:
        visible = " ".join(_visible(built[slug]).split())
        for pattern in banned:
            assert not re.search(pattern, visible, re.I), (slug, pattern)
        # (c) no loaded comparison near the oldest drivers.
        for match in re.finditer(r"75", visible):
            near = visible[max(0, match.start() - 80) : match.end() + 80].lower()
            for word in ("twice", "double", "riskier", "more dangerous drivers"):
                assert word not in near, (slug, word, near)
        # (d) a range or a count of combinations is never a probability; (g) nor a percentage.
        for match in re.finditer(r"combination|range|scenario", visible):
            near = visible[max(0, match.start() - 80) : match.end() + 80]
            near = near.replace("probably too narrow", "").replace("no probability", "")
            assert "probab" not in near.lower(), (slug, near)
        for match in re.finditer(r"combinations", visible):
            near = visible[max(0, match.start() - 60) : match.end() + 60]
            assert "%" not in near, (slug, near)


# The pages on recorded factors and crash circumstances, and the methodology section that holds
# each one's technical notes.
FACTOR_PAGES = {
    "speed": "speed-method",
    "factors": "factors-method",
    "severity": "severity-method",
}


def test_factor_pages_are_short_and_keep_their_detail_on_the_methodology_page(
    built: dict[str, str],
) -> None:
    for slug, notes in FACTOR_PAGES.items():
        main = _main(built[slug])
        opening = re.sub(r"<[^>]+>", " ", re.search(r'<p class="summary">(.*?)</p>', main).group(1))
        assert 40 <= len(opening.split()) <= 90, (slug, len(opening.split()))
        # No paragraph of the argument runs long, and one to three figures and tables carry it.
        for block in _blocks(built[slug], "p"):
            assert len(block.split()) <= 100, (slug, block[:80])
        shown = main.count("<figure") + main.count('<div class="table-block">')
        assert 1 <= shown <= 3, (slug, shown)
        # The detail is not folded away on the page: it is a section of the methodology page,
        # which the page links to.
        assert '<details class="technical"' not in main, slug
        assert f'href="data.html#{notes}"' in main, slug
        assert f'<h2 id="{notes}">' in built["data"], slug
    # A recorded factor is never read as a cause.
    assert "not estimates of what speed causes" in _visible(built["speed"])
    assert "not a finding that the factor caused it" in _visible(built["factors"])
    # The crash records behind the speed and severity pages can be explored by road type.
    for slug in ("speed", "severity"):
        assert 'href="crash-explorer.html"' in _main(built[slug]), slug
