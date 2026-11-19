"""The built site in a real browser: the explorers, the keyboard, a phone's width, no sideways scroll.

These tests serve ``site/`` (built by ``scripts/build_site.py``) over HTTP and drive it with
Playwright's Chromium. They need the optional browser dependency
(``pip install -e .[browser]``) and a Chromium build; they skip otherwise. Set
``PLAYWRIGHT_CHROMIUM`` to use a Chromium executable that Playwright did not install itself, and
``REQUIRE_BROWSER`` to fail rather than skip when no browser can be launched (as CI does).

What they check:

* the crash explorer shows what its table holds, names the caveats that apply, and every control
  is reachable and operable from the keyboard;
* at a phone's width no page scrolls sideways;
* at a phone's width every figure loads the chart drawn for a phone, fits its column without
  scrolling and shows its smallest text at 11 px or more, while a desktop loads the full chart.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import re
import threading
from pathlib import Path

import pytest

from dgt_stats.paths import PROJECT_ROOT, REPORTS_DIR
from dgt_stats.site.components import FIGURE_SCALE

# With REQUIRE_BROWSER set (as in CI), a missing browser library or an unbuilt site is an error,
# not a reason to skip.
REQUIRED = bool(os.environ.get("REQUIRE_BROWSER"))
if REQUIRED:
    from playwright import sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

SITE = PROJECT_ROOT / "site"
PHONE = {"width": 390, "height": 844}
LAPTOP = {"width": 1280, "height": 760}

if not (SITE / "crash-explorer.html").exists():
    if REQUIRED:
        raise RuntimeError("REQUIRE_BROWSER is set but the site is not built: run build_site.py")
    pytest.skip("run scripts/build_site.py first", allow_module_level=True)


def _executable() -> str | None:
    if os.environ.get("PLAYWRIGHT_CHROMIUM"):
        return os.environ["PLAYWRIGHT_CHROMIUM"]
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    for pattern in (
        "chromium_headless_shell-*/chrome-linux/headless_shell",
        "chromium-*/chrome-linux/chrome",
    ):
        found = sorted(root.glob(pattern))
        if found:
            return str(found[-1])
    return None


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    handler.log_message = lambda *args: None  # type: ignore[method-assign]
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(
                executable_path=_executable(), args=["--no-sandbox"]
            )
        except Exception as error:  # no Chromium build available
            if os.environ.get("REQUIRE_BROWSER"):
                raise
            pytest.skip(f"Chromium could not be launched: {error}")
        yield launched
        launched.close()


PAGES = sorted(path.stem for path in SITE.glob("*.html"))
CONTRAST = """() => {
  const rgb = (value) => value.match(/[0-9.]+/g).slice(0, 3).map(Number);
  const luminance = ([r, g, b]) => {
    const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const body = getComputedStyle(document.body);
  let background = body.backgroundColor;
  if (background === "rgba(0, 0, 0, 0)") background = getComputedStyle(document.documentElement).backgroundColor;
  const a = luminance(rgb(body.color)), b = luminance(rgb(background));
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("slug", PAGES)
def test_every_page_loads_cleanly_on_a_phone(browser, server, slug: str, scheme: str) -> None:
    """No script error, no sideways scrolling at a phone's width, and body text that meets the
    WCAG AA contrast ratio, in the light and the dark theme."""
    page = browser.new_page(viewport=PHONE, color_scheme=scheme)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console", lambda message: errors.append(message.text) if message.type == "error" else None
    )
    page.goto(f"{server}/{slug}.html", wait_until="networkidle")
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    contrast = page.evaluate(CONTRAST)
    page.close()
    assert errors == [], (slug, scheme, errors)
    assert overflow <= 1, (slug, scheme, overflow)
    assert contrast >= 4.5, (slug, scheme, contrast)


FIGURE_PAGES = sorted(
    path.stem
    for path in SITE.glob("*.html")
    if 'class="figure-wide" src="figures/' in path.read_text(encoding="utf-8")
)
assert FIGURE_PAGES
# Every figure on the page, brought into view so that the drawing it shows loads, then measured:
# the drawing shown (wide or narrow), how many are shown, and every figure the page fetched.
FIGURES = r"""async () => {
  const out = [];
  for (const figure of document.querySelectorAll('main figure')) {
    const shown = [...figure.querySelectorAll('img')].filter(
      (img) => getComputedStyle(img).display !== 'none');
    const img = shown[0];
    const media = figure.querySelector('.figure-media');
    figure.scrollIntoView();
    if (!img.complete || !img.naturalWidth) {
      await Promise.race([
        new Promise((done) => {
          img.addEventListener('load', done, { once: true });
          img.addEventListener('error', done, { once: true });
        }),
        new Promise((done) => setTimeout(done, 5000)),
      ]);
    }
    const box = img.getBoundingClientRect();
    out.push({
      name: img.getAttribute('src').replace(/^figures\/(narrow\/)?/, '').replace('.svg', ''),
      shown: shown.length,
      source: img.currentSrc,
      loaded: img.complete && img.naturalWidth > 0,
      width: box.width,
      right: box.right,
      column: figure.getBoundingClientRect().width,
      columnRight: figure.getBoundingClientRect().right,
      scrolls: media.scrollWidth - media.clientWidth,
    });
  }
  const fetched = performance.getEntriesByType('resource').map((entry) => entry.name)
    .filter((url) => url.includes('/figures/'));
  return { figures: out, fetched };
}"""


def _svg_text(path: Path) -> tuple[float, float]:
    """A chart's viewBox width and its smallest text, in the same units."""
    text = path.read_text(encoding="utf-8")
    width = float(re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ', text).group(1))
    return width, min(float(size) for size in re.findall(r"font-size: ([\d.]+)px", text))


def _measure(browser, server, slug: str, size: dict, scheme: str = "light") -> list[dict]:
    """The figures of a page at one size, with the check that each shows one drawing and that
    the page fetched only the drawings it shows."""
    page = browser.new_page(viewport=size, color_scheme=scheme)
    page.goto(f"{server}/{slug}.html", wait_until="networkidle")
    measured = page.evaluate(FIGURES)
    page.close()
    figures = measured["figures"]
    assert figures, slug
    for figure in figures:
        assert figure["shown"] == 1 and figure["loaded"], (slug, size, scheme, figure)
    names = [re.sub(r"^.*/figures/(narrow/)?", "", url) for url in measured["fetched"]]
    assert len(names) == len(set(names)), (slug, size, scheme, sorted(names))
    return figures


def _legible(figure: dict, slug: str, size: dict, scheme: str) -> None:
    """No wider than its column, no sideways scrolling, and its smallest text at 11 px or more."""
    name = figure["name"]
    folder = SITE / "figures" / ("narrow" if "/figures/narrow/" in figure["source"] else "")
    width, smallest = _svg_text(folder / f"{name}.svg")
    assert figure["width"] <= figure["column"] + 0.5, (slug, size, scheme, figure)
    assert figure["right"] <= figure["columnRight"] + 0.5, (slug, size, scheme, figure)
    assert figure["scrolls"] <= 1, (slug, size, scheme, figure)
    assert smallest * figure["width"] / width >= 11, (slug, size, scheme, name, figure["width"])


@pytest.mark.parametrize("width", [320, 390])
@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("slug", FIGURE_PAGES)
def test_every_figure_fits_a_phone_column(browser, server, slug: str, scheme: str, width) -> None:
    """On the narrowest phone served and a common one, every figure shows the chart drawn for a
    phone's column, no wider than the column and without scrolling, its text at 11 px or more."""
    size = {"width": width, "height": 844}
    for figure in _measure(browser, server, slug, size, scheme):
        assert figure["source"].endswith(f"/figures/narrow/{figure['name']}.svg"), figure
        _legible(figure, slug, size, scheme)


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("slug", FIGURE_PAGES)
def test_every_figure_is_legible_on_tablets_and_laptops(
    browser, server, slug: str, scheme: str
) -> None:
    """Between a phone and a wide screen, each figure shows whichever drawing keeps its text at
    11 px or more in the column it has (the wide one where it fits), and nothing scrolls."""
    for width in (700, 820, 960, 1152):
        size = {"width": width, "height": 900}
        for figure in _measure(browser, server, slug, size, scheme):
            _legible(figure, slug, size, scheme)


@pytest.mark.parametrize("size", [{"width": 360, "height": 740}, {"width": 768, "height": 1024}])
@pytest.mark.parametrize("slug", FIGURE_PAGES)
def test_the_dark_frame_shrinks_no_figure(browser, server, slug: str, size: dict) -> None:
    """The dark frame costs no figure its fit: on a phone and a tablet, where it goes, every
    figure is as wide in dark as in light and scrolls sideways in dark only if it does in light."""
    shown = {}
    for scheme in ("light", "dark"):
        figures = _measure(browser, server, slug, size, scheme)
        shown[scheme] = {figure["name"]: figure for figure in figures}
    assert shown["light"].keys() == shown["dark"].keys(), slug
    for name, light in shown["light"].items():
        dark = shown["dark"][name]
        assert abs(dark["width"] - light["width"]) <= 0.5, (slug, size, name)
        assert dark["scrolls"] <= max(light["scrolls"], 1), (slug, size, name)


def test_a_desktop_loads_the_full_figures(browser, server) -> None:
    figures = _measure(browser, server, "seasons", {"width": 1280, "height": 900})
    for figure in figures:
        name = figure["name"]
        assert figure["source"].endswith(f"/figures/{name}.svg"), figure
        assert figure["scrolls"] <= 1 and figure["width"] <= figure["column"] + 0.5, figure
        # Shown at the site's fixed scale of the chart's own size, as before phones had their own.
        width, _ = _svg_text(SITE / "figures" / f"{name}.svg")
        assert abs(figure["width"] - round(width * FIGURE_SCALE)) <= 1, figure


def test_the_theme_switch_overrides_the_system_and_is_remembered(browser, server) -> None:
    page = browser.new_page(color_scheme="light")
    page.goto(f"{server}/index.html", wait_until="networkidle")
    switch = page.locator("[data-theme-toggle], button.theme-toggle").first
    switch.click()
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
    page.goto(f"{server}/drivers.html", wait_until="networkidle")
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
    page.close()


# ------------------------------------------------------------- the crash statistics explorer

EXPLORER = "crash-explorer.html"
CRASH_TABLE = REPORTS_DIR / "tables" / "explore_dgt_crashes.csv"
CRASH_COUNTS = [
    "injury_crashes",
    "fatal_crashes",
    "deaths_30d",
    "deaths_pedestrians",
    "deaths_cyclists",
    "deaths_moped_riders",
    "deaths_motorcyclists",
    "deaths_car_occupants",
    "deaths_van_light_truck",
    "deaths_heavy_vehicle",
    "deaths_other",
]


def _explorer_data() -> dict:
    return json.loads((SITE / "tools" / "crash-explorer.json").read_text(encoding="utf-8"))


def _open_explorer(browser, server, size: dict | None = None, scheme: str = "light"):
    page = browser.new_page(viewport=size or LAPTOP, color_scheme=scheme)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console", lambda message: errors.append(message.text) if message.type == "error" else None
    )
    page.goto(f"{server}/{EXPLORER}", wait_until="networkidle")
    page.wait_for_selector('[data-tool="crash-explorer"]:not([hidden])')
    return page, errors


@pytest.fixture()
def explorer(browser, server):
    page, errors = _open_explorer(browser, server)
    yield page
    assert errors == []
    page.close()


def _explorer_result(page) -> str:
    return re.sub(r"\s+", " ", page.text_content(".tool-result"))


def _value(text: str) -> float | None:
    text = text.strip().replace(",", "").replace("−", "-")
    return None if text in ("", "–") else float(text)


def _explorer_rows(page) -> list[list[str]]:
    return [
        [cell.text_content() for cell in row.query_selector_all("th, td")]
        for row in page.query_selector_all("[data-table] tbody tr")
    ]


def test_the_crash_explorer_loads_and_every_control_changes_the_result(explorer) -> None:
    data = _explorer_data()
    changes = [
        ("from", "2"),
        ("to", str(len(data["years"]) - 2)),
        ("region", str(data["catalonia"])),
        ("road", "0"),
        ("type", "0"),
        ("outcome", "fatal_share"),
        ("outcome", "user"),
        ("user", "3"),
        ("by", "type"),
    ]
    assert explorer.is_hidden('[data-field="user"]')
    for name, value in changes:
        before = _explorer_result(explorer)
        explorer.select_option(f'[name="{name}"]', value)
        assert _explorer_result(explorer) != before, name
    # The road-user menu shows only with the outcome that needs it, and the breakdown's own
    # filter shows every level instead of one.
    assert explorer.is_visible('[data-field="user"]')
    assert explorer.is_disabled('[name="type"]')
    assert explorer.input_value('[name="type"]') == "each"
    explorer.select_option('[name="by"]', "year")
    assert explorer.input_value('[name="type"]') == "0" and explorer.is_enabled('[name="type"]')
    # A start year after the end year moves the end year with it.
    explorer.select_option('[name="from"]', str(len(data["years"]) - 1))
    assert explorer.input_value('[name="to"]') == str(len(data["years"]) - 1)


def test_the_crash_explorer_names_the_caveats_that_apply(explorer) -> None:
    def caveats() -> str:
        return explorer.text_content("[data-caveats]")

    assert "recorded by the police" in caveats()
    assert "30 days" not in caveats() and "coding breaks" not in caveats()
    explorer.select_option('[name="outcome"]', "fatal_share")
    assert "30 days" in caveats() and "not rates per person" in caveats()
    explorer.select_option('[name="road"]', "0")
    assert "Catalonia's records" in caveats()
    assert explorer.query_selector('[data-caveats] a[href="data.html#coding-breaks"]')
    # A region other than Catalonia leaves Catalonia's coding out of it.
    madrid = _explorer_data()["regions"].index("Madrid")
    explorer.select_option('[name="region"]', str(madrid))
    assert "Catalonia's records" not in caveats()
    # Small cells are flagged in the table and named once below it.
    explorer.select_option('[name="by"]', "type")
    flagged = [row for row in _explorer_rows(explorer) if "low support" in row[0]]
    assert flagged and all(0 < _value(row[1]) < _explorer_data()["minSupport"] for row in flagged)
    assert caveats().count("low support") == 1


def test_the_crash_explorer_says_when_nothing_was_recorded(explorer) -> None:
    data = _explorer_data()
    explorer.select_option('[name="region"]', str(data["regions"].index("Ceuta")))
    explorer.select_option('[name="road"]', str(data["roads"].index("Motorways")))
    text = _explorer_result(explorer)
    assert "No recorded crashes for this selection" in text
    assert f"The records cover {data['years'][0]}–{data['years'][-1]}" in text
    assert _explorer_rows(explorer) == [] and explorer.query_selector("[data-chart] svg") is None


def _expected(table, data: dict, choice: dict):
    """The selection added up in pandas from the committed table, by the breakdown's level."""
    years = data["years"]
    rows = table[
        (table.year >= years[int(choice["from"])]) & (table.year <= years[int(choice["to"])])
    ]
    columns = {
        "region": ("community", "regions"),
        "road": ("road_type", "roads"),
        "type": ("crash_type", "types"),
    }
    for name, (column, labels) in columns.items():
        if choice[name] != "all" and choice["by"] != name:
            rows = rows[rows[column] == data[labels][int(choice[name])]]
    by = {"year": "year", **{name: column for name, (column, _) in columns.items()}}
    grouped = rows.groupby(by[choice["by"]])[CRASH_COUNTS].sum()
    if choice["by"] == "year":
        grouped.index = grouped.index.astype(str)
    return grouped, rows[CRASH_COUNTS].sum()


def _outcome(sums, choice: dict) -> tuple[float | None, tuple[float, float] | None]:
    from dgt_stats import rates

    crashes = sums["injury_crashes"]
    outcome = choice["outcome"]
    if outcome in ("crashes", "fatal", "deaths", "user"):
        column = {"crashes": "injury_crashes", "fatal": "fatal_crashes", "deaths": "deaths_30d"}
        name = column.get(outcome) or CRASH_COUNTS[3 + int(choice["user"])]
        return float(sums[name]), None
    if not crashes:
        return None, None
    if outcome == "deaths_rate":
        return 100 * sums["deaths_30d"] / crashes, None
    low, high = rates.wilson_interval(sums["fatal_crashes"] / crashes, crashes)
    return 100 * sums["fatal_crashes"] / crashes, (100 * low, 100 * high)


def _close(shown: float | None, expected: float | None) -> bool:
    if expected is None:
        return shown is None
    # Shares are shown to two decimals, counts exactly.
    return shown is not None and abs(shown - expected) <= 0.005 + 1e-9


def test_crash_explorer_selections_match_the_table(explorer) -> None:
    import numpy as np
    import pandas as pd

    table = pd.read_csv(CRASH_TABLE)
    data = _explorer_data()
    rng = np.random.default_rng(16)
    outcomes = ["crashes", "fatal", "deaths", "fatal_share", "deaths_rate", "user"]
    for _ in range(20):
        first = int(rng.integers(len(data["years"])))
        choice = {
            "from": str(first),
            "to": str(int(rng.integers(first, len(data["years"])))),
            "outcome": str(rng.choice(outcomes)),
            "user": str(int(rng.integers(len(data["users"])))),
            "by": str(rng.choice(["year", "region", "road", "type"])),
        }
        for name, labels in (("region", "regions"), ("road", "roads"), ("type", "types")):
            pick = int(rng.integers(-4, len(data[labels])))
            choice[name] = "all" if pick < 0 else str(pick)
        explorer.select_option('[name="by"]', "year")
        for name in ("from", "to", "region", "road", "type", "outcome", "user", "by"):
            if name != "user" or choice["outcome"] == "user":
                explorer.select_option(f'[name="{name}"]', choice[name])
        assert explorer.input_value('[name="from"]') == choice["from"], choice
        grouped, total = _expected(table, data, choice)
        if not total["injury_crashes"]:
            assert "No recorded crashes" in _explorer_result(explorer), choice
            continue
        value, interval = _outcome(total, choice)
        headline = explorer.text_content("[data-headline] strong")
        assert _close(_value(headline), value), (choice, headline, value)
        if interval:
            shown = re.search(r"95% interval ([\d.]+)–([\d.]+)", _explorer_result(explorer))
            assert _close(float(shown.group(1)), interval[0]), choice
            assert _close(float(shown.group(2)), interval[1]), choice
        rows = _explorer_rows(explorer)
        assert {row[0].replace(" low support", "") for row in rows} >= set(grouped.index), choice
        for row in rows:
            label = row[0].replace(" low support", "")
            sums = grouped.loc[label] if label in grouped.index else total * 0
            assert _value(row[1]) == sums["injury_crashes"], (choice, row)
            assert ("low support" in row[0]) == (0 < sums["injury_crashes"] < data["minSupport"])
            if choice["outcome"] != "crashes":
                value, interval = _outcome(sums, choice)
                assert _close(_value(row[2]), value), (choice, row, value)
                if interval:
                    low, high = (_value(part) for part in row[3].split("–"))
                    assert _close(low, interval[0]) and _close(high, interval[1]), (choice, row)


def test_crash_explorer_wilson_interval_equals_pythons(explorer) -> None:
    from dgt_stats import rates

    z = _explorer_data()["z"]
    for fatal, crashes in ((0, 1), (0, 19), (3, 19), (7, 244), (1435, 875013), (19, 19)):
        shown = explorer.evaluate("([k, n, z]) => Tools.wilson(k, n, z)", [fatal, crashes, z])
        low, high = rates.wilson_interval(fatal / crashes, crashes)
        assert shown["low"] == pytest.approx(low, abs=1e-12), (fatal, crashes)
        assert shown["high"] == pytest.approx(high, abs=1e-12), (fatal, crashes)


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [320, 768, 1280])
def test_crash_explorer_fits_every_width(browser, server, width: int, scheme: str) -> None:
    page, errors = _open_explorer(browser, server, {"width": width, "height": 900}, scheme)
    for by, outcome in (("year", "crashes"), ("type", "fatal_share"), ("region", "user")):
        page.select_option('[name="outcome"]', outcome)
        page.select_option('[name="by"]', by)
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 1, (width, scheme, by, overflow)
        chart = page.evaluate(
            "(() => { const c = document.querySelector('[data-chart]');"
            " const s = c.querySelector('svg'); return [c.clientWidth,"
            " s ? s.getBoundingClientRect().width : 0]; })()"
        )
        assert 0 < chart[1] <= chart[0] + 0.5, (width, scheme, by, chart)
        # The figures fit the column: no sideways scrolling inside the table either.
        table = page.evaluate(
            "(() => { const w = document.querySelector('[data-table]');"
            " return w.scrollWidth - w.clientWidth; })()"
        )
        assert table <= 1, (width, scheme, by, table)
    page.close()
    assert errors == []


def test_keyboard_alone_operates_the_crash_explorer(explorer) -> None:
    explorer.focus("#ce-from")
    order = []
    for _ in range(6):
        order.append(explorer.evaluate("document.activeElement.id"))
        explorer.keyboard.press("Tab")
    # The road-user menu is skipped while it is hidden.
    assert order == ["ce-from", "ce-to", "ce-region", "ce-road", "ce-type", "ce-outcome"]
    assert explorer.evaluate("document.activeElement.id") == "ce-by"
    explorer.focus("#ce-from")
    for keys in ("ArrowDown", "Tab ArrowUp", "Tab ArrowDown", "Tab ArrowDown", "Tab ArrowDown"):
        before = _explorer_result(explorer)
        for key in keys.split():
            explorer.keyboard.press(key)
        assert _explorer_result(explorer) != before, keys
    explorer.keyboard.press("Tab")
    explorer.keyboard.press("End")
    assert explorer.input_value("#ce-outcome") == "user"
    explorer.keyboard.press("Tab")
    assert explorer.evaluate("document.activeElement.id") == "ce-user"
    explorer.locator("[data-status]", has_text="deaths within 30 days").wait_for(state="attached")
    assert explorer.get_attribute("[data-status]", "aria-live") == "polite"
    for control in explorer.query_selector_all(".tool select"):
        label = explorer.evaluate(
            "(el) => document.querySelector(`label[for='${el.id}']`)?.textContent", control
        )
        assert label, control.get_attribute("id")
