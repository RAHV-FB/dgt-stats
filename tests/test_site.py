import re
from pathlib import Path

import pandas as pd
import pytest

from dgt_stats import site
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR

pytestmark = pytest.mark.skipif(
    not (FIGURES_DIR / "captions.json").exists()
    or not (TABLES_DIR / "q1_annual_headline.csv").exists(),
    reason="run `python scripts/analyse.py all` first",
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
    assert captions["q1_deaths_30d"] in text or site.esc(captions["q1_deaths_30d"]) in text


def test_table_formats_numbers() -> None:
    import pandas as pd

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
    fake_2018 = speed[speed.break_date == "2018-01-01"].iloc[0]
    if fake_2018.high < 0:
        assert "The design fails its own check" in text
    else:
        assert "Both placebos are near zero" in text
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
