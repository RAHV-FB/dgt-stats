import re
from pathlib import Path

import pandas as pd
import pytest

from dgt_stats import site, summaries
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR

# The analysis pages in navigation order: everything in the main row but the overview and data.
ANALYSIS_PAGES = tuple(slug for slug, _ in site.PAGES if slug not in ("index", "data"))

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
    for slug, _ in site.ALL_PAGES:
        page = built / f"{slug}.html"
        assert page.exists(), slug
        text = page.read_text(encoding="utf-8")
        assert text.count("<h1>") == 1, slug
        assert "<script" not in text, slug
        assert 'lang="en"' in text
        assert f'href="{slug}.html" aria-current="page"' in text
    # Seven analyses, the overview and the data in the main navigation; two supporting analyses
    # in a second row; and a pointer for each page that was renamed, and nothing else.
    assert len(site.PAGES) == 9 and len(site.SUPPORTING_PAGES) == 2
    expected = {slug for slug, _ in site.ALL_PAGES} | set(site.MOVED_PAGES)
    assert expected == {p.stem for p in built.glob("*.html")}


def test_moved_pages_point_to_their_successors(built: Path) -> None:
    for old, new in site.MOVED_PAGES.items():
        text = (built / f"{old}.html").read_text(encoding="utf-8")
        assert f'content="0; url={new}.html"' in text
        assert f'href="{new}.html">' in text
    # No live page links to a moved slug: the pointers are for old bookmarks, not navigation.
    for slug, _ in site.ALL_PAGES:
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        for moved in site.MOVED_PAGES:
            assert f'href="{moved}.html"' not in text, (slug, moved)


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
    for slug in ANALYSIS_PAGES + ("severity", "policy"):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        assert 'href="tables/' in text, slug


def test_figures_are_copied_and_captioned(built: Path) -> None:
    svgs = sorted(p.name for p in (built / "figures").glob("*.svg"))
    assert svgs == sorted(p.name for p in FIGURES_DIR.glob("*.svg"))
    captions = site.read_captions()
    for name in captions:
        assert (built / "figures" / f"{name}.svg").exists(), name
    text = (built / "long-run.html").read_text(encoding="utf-8")
    assert site.mark_spanish(site.esc(captions["l1_trend_projection"])) in text


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
    assert "It says nothing about how often crashes happen" in text
    # Mechanisms are labelled as proposals and cited to original research.
    assert "mechanisms the literature proposes, not results this analysis demonstrates" in text
    for _, url in site.LITERATURE.values():
        assert url in text
    assert "doi.org" in text
    # The full coefficient table is linked, not printed.
    assert 'href="tables/q3_model_coefficients.csv"' in text
    assert text.count("<table>") <= 3


def test_drivers_page_separates_the_two_questions(built: Path) -> None:
    text = (built / "drivers.html").read_text(encoding="utf-8")
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
    # Sex: the fatality ratio once involved is quoted with its interval, and the travel proxy is
    # named as what it is.
    ratios = pd.read_csv(TABLES_DIR / "drivers_sex_ratios.csv").set_index(
        ["scope", "band", "measure"]
    )
    fatality_men = ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    assert f"{fatality_men.ratio:.2f}× ({fatality_men.low:.2f}–{fatality_men.high:.2f})" in text
    assert "MOVILIA" in text and "passengers" in text
    assert 'src="figures/a3_sex_ratios.svg"' in text


def test_policy_page_reports_the_falsification_not_the_headline(built: Path) -> None:
    text = (built / "policy.html").read_text(encoding="utf-8")
    sensitivity = pd.read_csv(TABLES_DIR / "q8_points_sensitivity.csv").set_index("variant")
    main = float(sensitivity.loc["main", "level_change"])
    linear = float(sensitivity.loc["linear_trend", "level_change"])
    # Signed percentages are typeset with a real minus sign, not a hyphen.
    signed = lambda v: f"{v * 100:+.0f}%".replace("-", "\u2212")  # noqa: E731
    assert signed(main) in text and signed(linear) in text
    assert "-7%" not in text and "-12%" not in text
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


def test_speed_page_carries_severity_and_the_recording_discontinuity(built: Path) -> None:
    text = (built / "speed.html").read_text(encoding="utf-8")
    pooled = pd.read_csv(TABLES_DIR / "speed_severity_pooled.csv").set_index("road_type")
    adjusted = pooled.loc["adjusted"]
    assert (
        f"{adjusted.rate_ratio:.2f}× ({adjusted.ratio_low:.2f}–{adjusted.ratio_high:.2f})" in text
    )
    assert f"{adjusted.crude_ratio:.2f}×" in text  # the unadjusted ratio is shown beside it
    # The two biases are named, and no causal count is claimed.
    assert "inflates the ratio" in text and "deflates it" in text
    assert "not an estimate of how many deaths speed caused" in text
    shares = pd.read_csv(TABLES_DIR / "q9_infraction_shares.csv")
    all_roads = shares[shares.zone == "all"].set_index("year")
    for year in (2014, 2016, int(all_roads.index.max())):
        assert f"{all_roads.loc[year, 'share_unknown'] * 100:.0f}%" in text
    assert 'src="figures/c3_speed_status.svg"' in text
    assert "point in opposite directions" in text
    # The transcribed speed report is not republished on the site: no table of the report's
    # breakdowns by limit, vehicle, licence class or hour survives anywhere.
    for page in built.glob("*.html"):
        page_text = page.read_text(encoding="utf-8")
        assert "by the road's speed limit" not in page_text, page.name
        assert "licence class" not in page_text, page.name


def test_factors_page_reads_trends_only_within_comparable_runs(built: Path) -> None:
    text = (built / "factors.html").read_text(encoding="utf-8")
    windows = pd.read_csv(TABLES_DIR / "factor_windows.csv")
    alcohol = windows[(windows.zone == "interurban") & (windows.factor == "Alcohol")]
    assert len(alcohol) == 1  # no recording break in the interurban alcohol series
    assert f"{alcohol.share_first.iloc[0] * 100:.1f}%" in text
    assert f"{alcohol.share_last.iloc[0] * 100:.1f}%" in text
    assert 'src="figures/f2_factor_shares.svg"' in text
    assert "recording break" in text and "Drugs" in text


def test_trend_pages_show_every_denominator_and_the_projection(built: Path) -> None:
    trends = (built / "trends.html").read_text(encoding="utf-8")
    index = pd.read_csv(TABLES_DIR / "risk_index.csv")
    for label in index.denominator_label.unique():
        assert site.esc(label) in trends, label
    assert 'src="figures/r1_risk_change.svg"' in trends
    long_run = (built / "long-run.html").read_text(encoding="utf-8")
    assert 'src="figures/l2_observed_over_trend.svg"' in long_run
    series = pd.read_csv(TABLES_DIR / "longrun_series.csv")
    fuel = series[(series.measure == "road_fuel") & (series.period == "projected")]
    last = fuel[fuel.year == fuel.year.max()].iloc[0]
    assert site._signed_pct(float(last.ratio) - 1, 0) in long_run
    seasons = (built / "seasons.html").read_text(encoding="utf-8")
    for name in ("m1_season_profile", "m2_month_effects", "m3_lockdown"):
        assert f'src="figures/{name}.svg"' in seasons


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
            assert "<title>Road safety in Spain · measuring risk, not counting crashes" in text
        else:
            assert re.search(r"<title>[^<]+ · Road safety in Spain</title>", text), page.name
        for image in re.findall(r"<img[^>]*>", text):
            alt = re.search(r'alt="([^"]*)"', image)
            assert alt and alt.group(1).strip(), (page.name, image[:80])
        assert "<script" not in text


def test_front_page_leads_with_the_central_question(built: Path) -> None:
    index = (built / "index.html").read_text(encoding="utf-8")
    body = index[index.find("<main>") : index.find("</main>")]
    # One finding per analysis page, in navigation order, and four key figures.
    assert body.count('<div class="finding">') == len(ANALYSIS_PAGES)
    assert body.count('<div class="keyfig">') == 4
    positions = [body.find(f'href="{slug}.html"') for slug in ANALYSIS_PAGES]
    assert all(p > 0 for p in positions) and positions == sorted(positions)
    # The supporting analyses are linked from a paragraph that says why they are not central.
    assert "does not claim" in body
    for slug in ("severity", "policy"):
        assert f'href="{slug}.html"' in body
    assert site.PROFILE_URL in index and "Russell Howard" in index
    assert len(body) < 10_000


def test_every_analysis_page_ends_on_a_stated_conclusion(built: Path) -> None:
    for slug in ANALYSIS_PAGES + ("severity", "policy"):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        assert text.count('<div class="conclusion">') == 1, slug
        body = text[text.find("<main>") : text.find("</main>")]
        # The conclusion is the last thing in the argument, not a box in the middle of it.
        assert body.rfind('<div class="conclusion">') > body.rfind("<table>"), slug


def test_supporting_pages_say_they_are_supporting(built: Path) -> None:
    for slug in ("severity", "policy"):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        body = text[text.find("<main>") : text.find("</main>")]
        assert body.find("Supporting analysis.") < body.find("<h2>"), slug


def test_no_page_uses_an_em_dash(built: Path) -> None:
    # House style: colons, commas, brackets and full stops instead. Checked on the rendered
    # pages because the prose is assembled from many fragments.
    for page in sorted(built.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        assert "\u2014" not in text, page.name
        assert "&mdash;" not in text, page.name


def test_the_development_note_is_professional_and_present(built: Path) -> None:
    data = (built / "data.html").read_text(encoding="utf-8")
    assert "reproducible, source-driven workflow" in data
    assert "AI coding assistants were used during implementation" in data
    assert "are the author's" in data
    for page in built.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        if page.name != "data.html":
            assert "Claude Code" not in text
