"""The trends explorer and the driver risk comparison in Chromium: they load, every control
changes the result, the numbers shown are the tables', and they fit a phone.

Needs the optional ``browser`` dependencies and a built site; with REQUIRE_BROWSER set (as in CI)
a missing library or an unbuilt site is an error rather than a reason to skip.
"""

from __future__ import annotations

import functools
import http.server
import os
import random
import re
import threading
from pathlib import Path

import pandas as pd
import pytest

from dgt_stats.paths import PROJECT_ROOT, TABLES_DIR
from dgt_stats.site import tool_driver_risk, tool_trends

REQUIRED = bool(os.environ.get("REQUIRE_BROWSER"))
if REQUIRED:
    from playwright import sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

SITE = PROJECT_ROOT / "site"
PHONE = {"width": 390, "height": 844}
LAPTOP = {"width": 1280, "height": 900}
SMALL = {"width": 320, "height": 640}

if not (SITE / "tools" / "trends-explorer.json").exists():
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
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(
                executable_path=_executable(), args=["--no-sandbox"]
            )
        except Exception as error:
            if REQUIRED:
                raise
            pytest.skip(f"Chromium could not be launched: {error}")
        yield launched
        launched.close()


def _open(browser, server, slug: str, size=LAPTOP, scheme: str = "light"):
    page = browser.new_page(viewport=size, color_scheme=scheme)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console", lambda message: errors.append(message.text) if message.type == "error" else None
    )
    page.goto(f"{server}/{slug}.html", wait_until="networkidle")
    page.wait_for_selector(f'[data-tool="{slug}"]:not([hidden])')
    return page, errors


def _text(page, selector: str) -> str:
    return re.sub(r"\s+", " ", page.text_content(selector) or "").strip()


def _pct(value: float) -> str:
    text = f"{abs(value) * 100:,.1f}%"
    sign = "+" if value > 0 and text.strip("0.%") else ("−" if value < 0 else "")
    return sign + text


# --------------------------------------------------------------------------- trends explorer


def test_the_trends_explorer_shows_each_indicator_and_its_change(browser, server) -> None:
    page, errors = _open(browser, server, "trends-explorer")
    indicators = tool_trends.indicators()
    rng = random.Random(20261009)
    for item in indicators:
        first, last = item["first"], item["first"] + len(item["values"]) - 1
        start = rng.randint(first, last - 1)
        end = rng.randint(start + 1, last)
        page.select_option("[name='indicator']", item["id"])
        page.select_option("[name='from']", str(start))
        page.select_option("[name='to']", str(end))
        a, b = item["values"][start - first], item["values"][end - first]
        headline = _text(page, "[data-headline]")
        assert headline == f"{item['label']} in {end}: {b:,.{item['decimals']}f}", item["id"]
        change = _text(page, "[data-change]")
        annual = (b / a) ** (1 / (end - start)) - 1
        assert change.startswith(f"{_pct(b / a - 1)} since {start} ({a:,.{item['decimals']}f})")
        assert f"{_pct(annual)} a year on average" in change, item["id"]
        # The chart and the table cover exactly the chosen years.
        rows = page.locator("[data-table] tbody tr")
        assert rows.count() == end - start + 1
        assert _text(page, "[data-table] caption") == f"{item['label']}, {start}–{end}"
        assert page.locator("[data-chart] svg").count() == 1
    assert not errors
    page.close()


def test_the_trends_explorer_offers_only_years_an_indicator_has(browser, server) -> None:
    page, _ = _open(browser, server, "trends-explorer")
    for item in tool_trends.indicators():
        page.select_option("[name='indicator']", item["id"])
        years = page.eval_on_selector_all(
            "[name='from'] option", "options => options.map(o => Number(o.value))"
        )
        assert min(years) >= item["first"], item["id"]
        last = item["first"] + len(item["values"]) - 1
        ends = page.eval_on_selector_all(
            "[name='to'] option", "options => options.map(o => Number(o.value))"
        )
        assert max(ends) <= last, item["id"]
    page.close()


def test_comparing_two_indicators_shows_indices_and_reset_restores(browser, server) -> None:
    page, _ = _open(browser, server, "trends-explorer")
    page.select_option("[name='indicator']", "deaths_30d")
    page.select_option("[name='compare']", "crashes")
    assert "Index" in _text(page, "[data-chart]")
    panel = pd.read_csv(TABLES_DIR / "risk_annual_panel.csv").set_index("year")
    start, end = int(page.input_value("[name='from']")), int(page.input_value("[name='to']"))
    crashes = panel.crashes.loc[end] / panel.crashes.loc[start] - 1
    assert f"Injury crashes: {_pct(crashes)} over the same years" in _text(page, "[data-change]")
    page.click("[data-reset]")
    assert page.input_value("[name='compare']") == ""
    assert page.input_value("[name='indicator']") == "deaths_30d"
    page.close()


# --------------------------------------------------------------------------- driver risk


def test_the_driver_comparison_opens_on_the_75_plus_estimate_with_its_condition(
    browser, server
) -> None:
    page, errors = _open(browser, server, "driver-risk")
    headline = _text(page, "[data-headline]")
    assert (
        "drivers aged 75 and over were involved in injury crashes 2.06 times as often" in headline
    )
    detail = _text(page, "[data-detail]")
    assert "95% sampling interval 1.6–2.6; sensitivity range 0.97–3.20" in detail
    condition = _text(page, "[data-condition]")
    assert "holds only if people aged 75 and over drive as much less" in condition
    assert "0.97 to 3.20 times the 45–64 rate" in condition
    assert not errors
    page.close()


def test_changing_the_split_changes_only_the_older_estimates(browser, server) -> None:
    page, _ = _open(browser, server, "driver-risk")
    data = tool_driver_risk.driver_data()
    groups = next(m for m in data["age"] if m["id"] == "involved_per_km")["groups"]
    for split in data["splits"]:
        page.select_option("[name='split']", split["value"])
        shown = groups["75+"]["by_split"][split["value"]]
        assert f"{shown['value']:.2f} times as often" in _text(page, "[data-headline]")
        assert shown["interval"] in _text(page, "[data-detail]")
        odds = "at odds with surveys of men's driving" in _text(page, "[data-condition]")
        assert odds == shown["at_odds"], split["value"]
    # The age profile applies to the younger groups, not to the split at 75.
    page.select_option("[name='a']", "18-29")
    for profile in data["profiles"]:
        page.select_option("[name='profile']", profile["value"])
        shown = groups["18-29"]["by_profile"][profile["value"]]
        assert f"{shown['value']:.2f} times as often" in _text(page, "[data-headline]")
    page.close()


def test_observed_measures_compare_two_groups_with_an_interval(browser, server) -> None:
    page, _ = _open(browser, server, "driver-risk")
    data = tool_driver_risk.driver_data()
    killed = next(m for m in data["age"] if m["id"] == "killed_per_involved")
    page.select_option("[name='measure']", "killed_per_involved")
    page.select_option("[name='a']", "75+")
    page.select_option("[name='b']", "45-64")
    ratio = killed["pairs"]["75+|45-64"]
    detail = _text(page, "[data-detail]")
    assert f"{ratio[0]:.2f} times (95% interval {ratio[1]:.2f}–{ratio[2]:.2f})" in detail
    assert "15.9 per 1,000 drivers involved" in _text(page, "[data-headline]")
    # The same group on both sides is not a comparison.
    page.select_option("[name='b']", "75+")
    assert "Choose two different groups" in _text(page, "[data-detail]")
    page.close()


def test_men_and_women_side_by_side(browser, server) -> None:
    page, _ = _open(browser, server, "driver-risk")
    data = tool_driver_risk.driver_data()
    page.select_option("[name='mode']", "sex")
    assert page.is_hidden("[data-field='a']") and page.is_hidden("[data-field='b']")
    km = data["sex"]["per_km"]["involved_per_km"]
    assert (
        f"men were involved in injury crashes {km['ratio']:.2f} times as often as women"
        in _text(page, "[data-headline]")
    )
    page.select_option("[name='measure']", "killed_per_involved")
    assert page.is_visible("[data-field='band']")
    band = data["sex"]["observed"]["killed_per_involved"]["75+"]
    page.select_option("[name='band']", "75+")
    assert f"{band['ratio'][0]:.2f} times" in _text(page, "[data-detail]")
    page.close()


# --------------------------------------------------------------------------- both


@pytest.mark.parametrize("slug", ["trends-explorer", "driver-risk"])
@pytest.mark.parametrize("size", [SMALL, PHONE, LAPTOP])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_tools_fit_their_page_and_load_cleanly(browser, server, slug, size, scheme) -> None:
    page, errors = _open(browser, server, slug, size, scheme)
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0, (slug, size, overflow)
    # The chart's text is drawn at its reading size: 13 px or more.
    sizes = page.eval_on_selector_all(
        "[data-chart] svg text", "nodes => nodes.map(n => parseFloat(getComputedStyle(n).fontSize))"
    )
    assert sizes and min(sizes) >= 13, (slug, size)
    assert not errors, (slug, errors)
    page.close()


@pytest.mark.parametrize("slug", ["trends-explorer", "driver-risk"])
def test_the_tools_work_from_the_keyboard(browser, server, slug) -> None:
    page, _ = _open(browser, server, slug, PHONE)
    before = _text(page, "[data-headline]")
    first = page.locator("[data-controls] select").first
    first.focus()
    # A select changes with the arrow keys, and the result follows at once.
    for _ in range(3):
        page.keyboard.press("ArrowDown")
        if _text(page, "[data-headline]") != before:
            break
    assert _text(page, "[data-headline]") != before, slug
    # Screen readers hear the new result once, from the polite status line.
    page.wait_for_function("document.querySelector('[data-status]').textContent.length > 0")
    page.close()


@pytest.mark.parametrize("slug", ["trends-explorer", "driver-risk"])
def test_a_tool_says_so_when_its_data_cannot_load(browser, server, slug) -> None:
    page = browser.new_page(viewport=PHONE)
    page.route(f"**/tools/{slug}.json", lambda route: route.fulfill(status=404, body=""))
    page.goto(f"{server}/{slug}.html", wait_until="networkidle")
    assert page.is_hidden(f'[data-tool="{slug}"]')
    assert "could not load its data" in _text(page, "[data-tool-fallback]")
    page.close()
