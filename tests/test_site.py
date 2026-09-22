import re
from pathlib import Path

import pandas as pd
import pytest

from dgt_stats import site, summaries
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR

pytestmark = pytest.mark.skipif(
    not (FIGURES_DIR / "captions.json").exists()
    or not (TABLES_DIR / "q1_annual_headline.csv").exists()
    or not summaries.model_tables_present(),
    reason="run `python scripts/model.py` and `python scripts/analyse.py all` first",
)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("site")
    site.build(target)
    return target


def test_every_page_is_written_with_one_heading(built: Path) -> None:
    for slug, _ in site.PAGES:
        page = built / f"{slug}.html"
        assert page.exists(), slug
        text = page.read_text(encoding="utf-8")
        assert text.count("<h1>") == 1, slug
        assert "<script" not in text, slug
        assert 'lang="en"' in text
        assert f'href="{slug}.html" aria-current="page"' in text
    # Six pages and no more: the four analyses, their context and the data behind them.
    assert len(site.PAGES) == 7
    assert {slug for slug, _ in site.PAGES} == {p.stem for p in built.glob("*.html")}


def test_referenced_assets_exist(built: Path) -> None:
    for page in built.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        for src in re.findall(r'src="([^"]+)"', text):
            assert (built / src).exists(), (page.name, src)
        for href in re.findall(r'href="([^"]+\.(?:css|csv))"', text):
            assert (built / href).exists(), (page.name, href)
        for href in re.findall(r'href="([a-z-]+\.html)"', text):
            assert (built / href).exists(), (page.name, href)


def test_full_result_tables_are_published_as_csv(built: Path) -> None:
    published = {p.name for p in (built / "tables").glob("*.csv")}
    assert {f"{name}.csv" for name in summaries.SUMMARIES} <= published
    assert {f"{name}.csv" for name in summaries.MODEL_TABLES} <= published
    assert "validation.csv" in published
    # Every page that shows a headline number also links the table it came from.
    for slug in ("severity", "older-drivers", "vehicles", "policy", "context"):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        assert 'href="tables/' in text, slug


def test_figures_are_copied_and_captioned(built: Path) -> None:
    svgs = sorted(p.name for p in (built / "figures").glob("*.svg"))
    assert svgs == sorted(p.name for p in FIGURES_DIR.glob("*.svg"))
    captions = site.read_captions()
    for name in captions:
        assert (built / "figures" / f"{name}.svg").exists(), name
    text = (built / "context.html").read_text(encoding="utf-8")
    assert site.mark_spanish(site.esc(captions["c1_deaths_per_year"])) in text


def test_table_formats_numbers() -> None:
    frame = pd.DataFrame({"Year": [2024], "Crashes": [101996], "Share": [0.1234]})
    out = site.table(frame, "Caption", {"Crashes": "int", "Share": "pct"})
    assert "<td>101,996</td>" in out
    assert "<td>12.3%</td>" in out
    assert "<caption>Caption</caption>" in out


def test_severity_page_leads_with_the_adverse_finding(built: Path) -> None:
    text = (built / "severity.html").read_text(encoding="utf-8")
    adverse = pd.read_csv(TABLES_DIR / "q3_adverse_conditions.csv")
    fatal = adverse[adverse.outcome == "fatal"].set_index(["variant", "level"])
    wet_alone = float(fatal.loc[("no_weather", "wet"), "odds_ratio"])
    # The headline number is computed from the table, not typed.
    assert f"{wet_alone:.2f}×" in text
    assert "Odds ratios for the adverse conditions under every model variant" in text
    assert 'src="figures/s2_adverse_conditions.svg"' in text
    assert 'src="figures/s1_forest_fatal.svg"' in text
    # The distinction the finding depends on is made explicitly.
    assert "given an injury crash" in text
    assert "not about whether a crash happens" in text
    # Mechanisms are labelled as proposals and cited to original research.
    assert "mechanisms the literature proposes, not results this analysis demonstrates" in text
    for _, url in site.LITERATURE.values():
        assert url in text
    assert "doi.org" in text
    # The full coefficient table is linked, not printed.
    assert 'href="tables/q3_model_coefficients.csv"' in text
    assert text.count("<table>") <= 3


def test_older_drivers_page_separates_the_two_questions(built: Path) -> None:
    text = (built / "older-drivers.html").read_text(encoding="utf-8")
    ratios = pd.read_csv(TABLES_DIR / "q7_km_ratio.csv").set_index(["measure", "band"])
    involved = ratios.loc[("involved_per_bn_km", "75+")]
    fatality = ratios.loc[("deaths_per_1000_involved", "75+")]
    assert f"{involved.ratio:.2f}× ({involved.low:.2f}–{involved.high:.2f})" in text
    assert f"{fatality.ratio:.2f}× ({fatality.low:.2f}–{fatality.high:.2f})" in text
    # The exposure is kilometres and the page says whose age it is.
    assert "kilometres" in text and "owner" in text.lower()
    assert "travel-weighted" not in text  # the synthetic denominator is gone
    contrast = pd.read_csv(TABLES_DIR / "q7_denominator_contrast.csv")
    assert set(contrast.denominator) == {
        "residents",
        "licence_holders",
        "drivers_involved",
        "kilometres",
    }
    assert 'src="figures/a1_km_risk_by_age.svg"' in text
    company = pd.read_csv(TABLES_DIR / "q7_company_km.csv").set_index(["allocation", "band"])
    working = float(company.loc[("to_working_age", "75+"), "ratio_to_reference"])
    assert f"{working:.2f}" in text  # the company-car sensitivity is quoted, not hidden


def test_policy_page_reports_the_falsification_not_the_headline(built: Path) -> None:
    text = (built / "policy.html").read_text(encoding="utf-8")
    sensitivity = pd.read_csv(TABLES_DIR / "q8_points_sensitivity.csv").set_index("variant")
    main = float(sensitivity.loc["main", "level_change"])
    linear = float(sensitivity.loc["linear_trend", "level_change"])
    assert f"{main * 100:+.0f}%" in text and f"{linear * 100:+.0f}%" in text
    assert main > linear  # the preferred specification gives the smaller drop
    calendar = pd.read_csv(TABLES_DIR / "q8_points_calendar_placebo.csv")
    true = calendar[calendar.is_true].iloc[0]
    assert f"{int(true['rank'])} of {int(true.n_fits)}" in text
    forecast = pd.read_csv(TABLES_DIR / "q8_points_forecast.csv")
    true_forecast = forecast[forecast.is_true].iloc[0]
    assert f"{int(true_forecast['rank'])} of {int(true_forecast.n_fits)}" in text
    assert 'src="figures/p2_july_placebos.svg"' in text
    # The two claims are kept apart, and the 2019 study is a paragraph, not a section.
    assert "That the points licence caused it" in text
    assert "2019" in text and 'src="figures/q8_speed_series.svg"' not in text
    # The exposure series are named and their effect reported.
    assert "CORES" in text and "toll" in text


def test_context_page_carries_the_recording_discontinuity(built: Path) -> None:
    text = (built / "context.html").read_text(encoding="utf-8")
    shares = pd.read_csv(TABLES_DIR / "q9_infraction_shares.csv")
    all_roads = shares[shares.zone == "all"].set_index("year")
    for year in (2014, 2016, int(all_roads.index.max())):
        assert f"{all_roads.loc[year, 'share_unknown'] * 100:.0f}%" in text
    assert 'src="figures/c3_speed_status.svg"' in text
    assert "point in opposite directions" in text
    # The transcribed speed report is not republished on the site: no table of the report's
    # breakdowns by limit, vehicle, licence class or hour survives anywhere.
    for page in built.parent.glob("site*/*.html"):
        page_text = page.read_text(encoding="utf-8")
        assert "by the road's speed limit" not in page_text, page.name
        assert "licence class" not in page_text, page.name
    assert "fifteen of seventeen regions" in text


def test_every_internal_link_and_anchor_resolves(built: Path) -> None:
    pages = {p.name for p in built.glob("*.html")}
    ids = {
        p.name: set(re.findall(r'\sid="([^"]+)"', p.read_text(encoding="utf-8")))
        for p in built.glob("*.html")
    }
    for page in sorted(built.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            target, _, anchor = href.partition("#")
            if target:
                assert target in pages or (built / target).exists(), (page.name, href)
            if anchor:
                host = target or page.name
                assert host in ids, (page.name, href)
                assert anchor in ids[host], (page.name, href)


def test_every_page_has_a_description_and_every_image_an_alt(built: Path) -> None:
    for page in sorted(built.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        description = re.search(r'<meta name="description" content="([^"]*)"', text)
        assert description and len(description.group(1)) > 40, page.name
        if page.name == "index.html":
            assert "<title>Road safety in Spain · four analyses" in text
        else:
            assert re.search(r"<title>[^<]+ · Road safety in Spain</title>", text), page.name
        for image in re.findall(r"<img[^>]*>", text):
            alt = re.search(r'alt="([^"]*)"', image)
            assert alt and alt.group(1).strip(), (page.name, image[:80])
        assert "<script" not in text


def test_front_page_leads_with_the_four_analyses(built: Path) -> None:
    index = (built / "index.html").read_text(encoding="utf-8")
    body = index[index.find("<main>") : index.find("</main>")]
    assert body.count('<div class="feature">') == 4
    for slug in ("severity", "older-drivers", "vehicles", "policy"):
        assert f'href="{slug}.html"' in body, slug
    assert site.PROFILE_URL in index and "Russell Howard" in index
    # The front page is short: one screen of tiles, four findings and two short notes.
    assert len(body) < 7_000


def test_the_development_note_is_professional_and_present(built: Path) -> None:
    data = (built / "data.html").read_text(encoding="utf-8")
    assert "reproducible, source-driven workflow" in data
    assert "AI coding assistants were used during implementation" in data
    assert "are the author's" in data
    for page in built.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        if page.name != "data.html":
            assert "Claude Code" not in text
