import re
from pathlib import Path

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
