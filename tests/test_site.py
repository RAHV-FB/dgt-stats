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


def test_referenced_assets_exist(built: Path) -> None:
    for page in built.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        for src in re.findall(r'src="([^"]+)"', text):
            assert (built / src).exists(), (page.name, src)
        for href in re.findall(r'href="([^"]+\.css)"', text):
            assert (built / href).exists(), (page.name, href)
        for href in re.findall(r'href="([a-z-]+\.html)"', text):
            assert (built / href).exists(), (page.name, href)


def test_index_shows_the_validated_headline_numbers(built: Path) -> None:
    text = (built / "index.html").read_text(encoding="utf-8")
    assert "101,996" in text
    assert "1,785" in text
    assert "9,561" in text


def test_figures_are_copied_and_captioned(built: Path) -> None:
    svgs = sorted(p.name for p in (built / "figures").glob("*.svg"))
    assert svgs == sorted(p.name for p in FIGURES_DIR.glob("*.svg"))
    captions = site.read_captions()
    for name in captions:
        assert (built / "figures" / f"{name}.svg").exists(), name
    text = (built / "trends.html").read_text(encoding="utf-8")
    assert site.mark_spanish(site.esc(captions["q1_deaths_30d"])) in text


def test_table_formats_numbers() -> None:
    frame = pd.DataFrame({"Year": [2024], "Crashes": [101996], "Share": [0.1234]})
    out = site.table(frame, "Caption", {"Crashes": "int", "Share": "pct"})
    assert "<td>101,996</td>" in out
    assert "<td>12.3%</td>" in out
    assert "<caption>Caption</caption>" in out


def test_severity_page_reports_the_models(built: Path) -> None:
    text = (built / "severity.html").read_text(encoding="utf-8")
    assert "Odds ratio (95% interval)" in text
    assert "1 (reference)" in text
    assert "Area under the ROC curve" in text
    assert 'href="figures/q3_forest_fatal.svg"' not in text  # figures are images, not links
    assert 'src="figures/q3_forest_fatal.svg"' in text


def test_vehicles_page_reports_the_rates(built: Path) -> None:
    text = (built / "vehicles.html").read_text(encoding="utf-8")
    assert "per billion km" in text
    assert "Heavy trucks vs cars, per kilometre" in text
    assert 'src="figures/q6_rates_per_km.svg"' in text
    assert "Trucks over 3,500 kg" in text and "Vans and trucks up to 3,500 kg" in text
    assert "1993" in text and "Has a km denominator" in text
    summary = pd.read_csv(TABLES_DIR / "q6_summary_2022.csv").set_index("group")
    ratio = (
        summary.loc["heavy_truck", "fatal_involvement_per_bn_km"]
        / summary.loc["car", "fatal_involvement_per_bn_km"]
    )
    assert f"{ratio:.1f}×" in text  # the per-kilometre tile is computed, not typed
    assert "yet their occupants die less often" not in text
    index = (built / "index.html").read_text(encoding="utf-8")
    assert 'href="vehicles.html"' in index
    data = (built / "data.html").read_text(encoding="utf-8")
    assert "yearly tables 2.3" in data and "yearly tables 2.2" in data


def test_policy_page_reports_both_interventions(built: Path) -> None:
    text = (built / "policy.html").read_text(encoding="utf-8")
    assert 'src="figures/q8_points_series.svg"' in text
    assert 'src="figures/q8_speed_series.svg"' in text
    sensitivity = pd.read_csv(TABLES_DIR / "q8_points_sensitivity.csv")
    level = sensitivity.level_change.iloc[0]
    assert f"{level * 100:+.1f}%" in text  # the 2006 estimate is computed, not typed
    placebo = pd.read_csv(TABLES_DIR / "q8_points_placebo.csv")
    rank = int(placebo[placebo.is_true]["rank"].iloc[0])
    assert f"placebo rank {rank} of {len(placebo)}" in text
    assert "coincided" in text and "Penal Code" in text
    speed = pd.read_csv(TABLES_DIR / "q8_speed_placebo.csv")
    fakes = speed[~speed.is_true]
    # Both placebo estimates are quoted on the page, whichever branch its wording takes, and the
    # design is said to fail when a placebo interval excludes zero in either direction.
    for value in fakes.level_change:
        assert f"{value * 100:+.1f}%" in text
    fails = bool(((fakes.low > 0) | (fakes.high < 0)).any())
    assert ("The design fails its own check" in text) == fails
    # The 2006 sensitivity list follows the sign of each variant's upper bound.
    phrases = {
        "24h": "the 24-hour definition",
        "interurban": "the interurban series",
        "fleet_offset": "the fleet offset",
        "negative_binomial": "a negative-binomial fit",
    }
    for row in sensitivity.itertuples():
        if row.variant in phrases:
            assert (phrases[row.variant] in text) == bool(row.level_high < 0)
    index = (built / "index.html").read_text(encoding="utf-8")
    assert 'href="policy.html"' in index


def test_speed_page_keeps_the_two_sources_apart(built: Path) -> None:
    text = (built / "speed.html").read_text(encoding="utf-8")
    assert 'src="figures/q9_speed_status_interurban.svg"' in text
    assert 'src="figures/q9_report_day_hour.svg"' in text
    shares = pd.read_csv(TABLES_DIR / "q9_infraction_shares.csv")
    latest = shares[(shares.zone == "all") & (shares.year == shares.year.max())].iloc[0]
    assert f"{latest.share_unknown * 100:.0f}%" in text  # the unknown share is computed
    assert "without Cataluña and País Vasco" in text
    assert "never adds them together" in text
    index = (built / "index.html").read_text(encoding="utf-8")
    assert 'href="speed.html"' in index
    data = (built / "data.html").read_text(encoding="utf-8")
    assert "speed-factor report" in data and "tables 6.1" in data


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
                # A fragment must name a built page and an id on it, on this page or another.
                host = target or page.name
                assert host in ids, (page.name, href)
                assert anchor in ids[host], (page.name, href)


def test_every_page_has_a_description_and_every_image_an_alt(built: Path) -> None:
    for page in sorted(built.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        description = re.search(r'<meta name="description" content="([^"]*)"', text)
        assert description and len(description.group(1)) > 40, page.name
        if page.name == "index.html":
            assert "<title>Road safety in Spain · DGT crash data" in text
        else:
            assert re.search(r"<title>[^<]+ · Road safety in Spain</title>", text), page.name
        images = re.findall(r"<img[^>]*>", text)
        for image in images:
            alt = re.search(r'alt="([^"]*)"', image)
            assert alt and alt.group(1).strip(), (page.name, image[:80])
        assert "<script" not in text


def test_front_page_leads_with_three_analyses_and_links_the_rest(built: Path) -> None:
    index = (built / "index.html").read_text(encoding="utf-8")
    body = index[index.find("<main>") : index.find("</main>")]
    # The three featured analyses are set out in full; every other page is linked from the list.
    assert body.count('<section class="feature">') == len(site.FEATURED) == 3
    for href, (title, method) in site.FEATURED.items():
        assert f'<h3><a href="{href}">{site.esc(title)}</a></h3>' in body
        assert site.esc(method) in body
    for slug, _ in site.PAGES:
        if slug == "index":
            continue
        assert f'href="{slug}.html"' in body, slug
    # The front page carries a byline and says what the project is.
    assert "About this project" in body and site.PROFILE_URL in index
