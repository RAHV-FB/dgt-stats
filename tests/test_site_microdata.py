"""The microdata pages: numbers come from the result tables, never from the page code."""

import re

import pandas as pd
import pytest

from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, TABLES_DIR
from dgt_stats.site.components import _fmt_int, _fmt_pct

PAGES = ("catalonia", "barcelona", "severity-models", "sources")
# The modules that write the pages, and the helpers they share. Two are left out: components,
# whose navigation labels and publication titles carry years, and data, which cites a law by its
# number.
MODULES = tuple(
    path.stem
    for path in sorted((PROJECT_ROOT / "src/dgt_stats/site").glob("*.py"))
    if path.stem not in {"components", "data", "script", "style"}
)
NEEDED = (
    "cat_fatal_share",
    "bcn_person_severity_share",
    "sev_tests",
    "sev_rolling_scores",
    "source_comparison",
)

pytestmark = pytest.mark.skipif(
    not all((TABLES_DIR / f"{name}.csv").exists() for name in NEEDED)
    or not (FIGURES_DIR / "captions.json").exists(),
    reason="run `python scripts/microdata.py all` and `python scripts/analyse.py all` first",
)


@pytest.fixture(scope="module")
def pages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    from dgt_stats import site

    target = tmp_path_factory.mktemp("site")
    site.build(target)
    # The methodology page too, which holds the regional pages' technical notes.
    return {
        slug: (target / f"{slug}.html").read_text(encoding="utf-8") for slug in (*PAGES, "data")
    }


def _table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


def _notes(data: str, anchor: str) -> str:
    """One page's technical notes on the methodology page: its section, up to the next one."""
    start = data.index(f'<h2 id="{anchor}">')
    return data[start : data.index("<h2", start + 1)]


def test_page_code_types_no_year_and_no_result() -> None:
    source = "\n".join(
        (PROJECT_ROOT / f"src/dgt_stats/site/{name}.py").read_text(encoding="utf-8")
        for name in MODULES
    )
    strings = re.findall(r'"[^"\n]*"', source)
    years = [s for s in strings if re.search(r"\b(19|20)\d\d\b", s)]
    assert not years, years
    # Percentages other than the 95% of an interval would be results typed into the page.
    shares = [s for s in strings if re.search(r"\b(?!95%)\d+(\.\d+)?%", s)]
    assert not shares, shares


def test_microdata_pages_open_with_a_summary_and_link_their_tables(pages: dict[str, str]) -> None:
    for slug, text in pages.items():
        if slug == "data":
            continue
        # The old furniture is gone: no source block, no layer line. (A model's description
        # may say in prose what one row is; the old per-page "unit" block is what is banned.)
        assert '<details class="about">' not in text, slug
        assert '<p class="level">' not in text and "Layer:" not in text, slug
        assert text.count('<p class="summary">') == 1, slug
        assert 'href="tables/' in text, slug
    # Each regional page links its technical notes on the methodology page, and the notes link
    # the methodology's account of how police crash records are read.
    for slug in ("catalonia", "barcelona"):
        assert f'href="data.html#{slug}-method"' in pages[slug], slug
        assert 'href="#records"' in _notes(pages["data"], f"{slug}-method"), slug


def test_catalonia_headline_numbers_come_from_the_tables(pages: dict[str, str]) -> None:
    shares = _table("cat_fatal_share")
    overall = shares[(shares.dimension == "unit type involved") & (shares.level == "all")].iloc[0]
    text = pages["catalonia"]
    assert _fmt_int(overall.n) in text
    assert _fmt_pct(overall.share) in text
    comparison = _table("cat_vs_dgt_province_year")
    assert bool((comparison.ratio_fatal_24h == 1).all())
    assert f"in all {len(comparison)} province-years" in text


def _summary(text: str) -> str:
    return re.search(r'<p class="summary">(.*?)</p>', text, re.S).group(1)


def _headings(text: str) -> list[str]:
    main = text[text.find("<main>") : text.find("</main>")]
    return re.findall(r"<h2[^>]*>(.*?)</h2>", main, re.S)


def test_regional_pages_state_their_population_and_link_the_other_two(
    pages: dict[str, str],
) -> None:
    # Spain's, Catalonia's and Barcelona's pages answer related questions for different crashes
    # and definitions: each says so in its first paragraph and links the other two once.
    others = {"catalonia": ("severity", "barcelona"), "barcelona": ("severity", "catalonia")}
    for slug, linked in others.items():
        opening = _summary(pages[slug])
        for other in linked:
            assert opening.count(f'href="{other}.html"') == 1, (slug, other)
        assert "within 30 days" in opening and "within 24 hours" in opening, slug
        assert '<p class="scope">' not in pages[slug], slug


def test_catalonia_leads_with_its_results_and_links_the_model(
    pages: dict[str, str],
) -> None:
    text = pages["catalonia"]
    headings = _headings(text)
    # The checks on the file are technical notes on the methodology page, not sections of the
    # page. The page keeps the agreement with DGT's 24-hour counts, under the anchor the sources
    # page cites; the comparison in full is in the notes.
    assert "Agreement with DGT's national records" not in headings
    assert "Fields recorded unevenly" not in headings
    assert '<details class="technical"' not in text
    main = text[text.find("<main>") : text.find("</main>")]
    assert headings[-1] == "Data and method"
    agreement = re.search(r'<p id="dgt-agreement">(.*?)</p>', main, re.S).group(1)
    comparison = _table("cat_vs_dgt_province_year")
    assert f"in all {len(comparison)} province-years" in agreement
    assert "a death within 24 hours" in agreement
    notes = _notes(pages["data"], "catalonia-method")
    ratio30 = comparison.ratio_fatal_30d
    assert (
        f"{_fmt_pct(ratio30.min(), 0).removesuffix('%')}–{_fmt_pct(ratio30.max(), 0)} of DGT's "
        "count of crashes with a death within 30 days" in notes
    )
    # Where it shows fatal shares by circumstance, the page sends the reader to the model
    # before its first chart.
    first = main.find("<h2")
    model = main.find('href="severity-models.html"')
    assert first < model < main.find("cat1_fatal_by_road")


def test_barcelona_tables_name_each_breakdown_once(pages: dict[str, str]) -> None:
    # The shares of people by road user, age and sex are linked from the Barcelona page's notes.
    text = _notes(pages["data"], "barcelona-method")
    for prefix in ("Road user: ", "Age: ", "Sex: "):
        assert f">{prefix}" not in text, prefix
    # The shares by road user, age and sex are one table, published as CSV.
    assert 'href="tables/bcn_person_severity_share.csv"' in text


def test_barcelona_headline_numbers_come_from_the_tables(pages: dict[str, str]) -> None:
    people = _table("bcn_person_severity_share")
    pedestrian = people[(people.dimension == "road user") & (people.level == "pedestrian")]
    assert _fmt_pct(float(pedestrian.share.iloc[0])) in pages["barcelona"]
    structure = _table("mq_bcn_structure").set_index("table")
    assert _fmt_int(structure.loc["bcn_accidents", "rows"]) in pages["barcelona"]


def test_model_scores_come_from_the_tables(pages: dict[str, str]) -> None:
    text, notes = pages["severity-models"], pages["data"]
    scores = _table("sev_rolling_scores")
    pooled = scores[scores.subset.str.fullmatch(r"\d{4}-\d{4}")].set_index("estimator")
    calc, table = pooled.loc["model"], pooled.loc["road_x_crash_table"]
    trees = pooled.loc["boosted_trees"]
    # Ranking is given as ROC-AUC to two decimals.
    assert f"is {calc.roc_auc:.2f} and the table's {table.roc_auc:.2f}" in text
    assert f"({trees.roc_auc:.2f}) but gives no interval" in notes
    gap = _table("sev_comparison").set_index(["estimator", "metric"])
    lead = gap.loc[("road_x_crash_table", "roc_auc_minus_model")]
    assert f"lead is {-lead.high:.2f}–{-lead.low:.2f} (95% interval)" in text
    assert _fmt_pct(calc.mean_predicted) in text and _fmt_pct(calc.prevalence) in text
    # The contrasts lead, predicted against observed follows the ranking, and no score box.
    body = text[text.find("<main>") : text.find("</main>")]
    assert body.find("sev1_predicted_observed") < body.find("sev2_held_out")
    assert 'class="key-result"' not in body
    calibration = _table("sev_calibration")
    model = calibration[calibration.estimator == "model"].sort_values("group")
    top = model.tail(2).positives.sum() / model.tail(2).n.sum()
    assert f"rated most likely to have been fatal, {_fmt_pct(top, 0)} were" in text


def test_the_held_out_tests_come_from_the_table(pages: dict[str, str]) -> None:
    text = pages["severity-models"]
    tests = _table("sev_tests")
    for row in tests.itertuples():
        assert f"{row.roc_auc:.2f}" in text and f"{row.table_roc_auc:.2f}" in text
        assert _fmt_int(row.test_n) in text
    assert 'href="tables/sev_tests.csv"' in text
    assert "has been tested only on crashes from the same file" in text


def test_the_models_page_names_no_other_model(pages: dict[str, str]) -> None:
    text = pages["severity-models"]
    assert 'href="data.html#how-the-model-was-built"' in text
    assert 'id="how-the-model-was-built"' in pages["data"]


def test_sources_page_describes_the_uneven_recording_of_dgt_fields(pages: dict[str, str]) -> None:
    text = pages["sources"]
    assert 'id="scope"' in text
    # Fields that do not apply are not unrecorded.
    assert "in a crash it applies to" in text
    # The junction flag is described as inverted, not as a new way of marking missing types.
    assert "the junction flag the wrong way round" in text
    assert "instead of leaving it blank" not in text
