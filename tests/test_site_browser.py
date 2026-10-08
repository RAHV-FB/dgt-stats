"""The built site in a real browser: the calculator, the keyboard, a phone's width, no scripting.

These tests serve ``site/`` (built by ``scripts/build_site.py``) over HTTP and drive it with
Playwright's Chromium. They need the optional browser dependency
(``pip install -e .[browser]``) and a Chromium build; they skip otherwise. Set
``PLAYWRIGHT_CHROMIUM`` to use a Chromium executable that Playwright did not install itself.

What they check:

* the calculator loads its model and shows, for the reference crashes, the probability and
  interval that :func:`dgt_stats.severity_model.predict_exported` computes in Python, and the
  engine running in the page agrees with Python to 1e-10 on many scenarios;
* the two-scenario comparison matches :func:`compare_exported`;
* every control is reachable and operable from the keyboard, and results are announced;
* an impossible combination is refused with the rule's own words;
* at a phone's width no page scrolls sideways;
* without scripting the calculator stays hidden and its fallback is shown.
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

from dgt_stats import severity_model as sm
from dgt_stats.paths import PROJECT_ROOT, REPORTS_DIR

sync_api = pytest.importorskip("playwright.sync_api")

SITE = PROJECT_ROOT / "site"
MODEL = REPORTS_DIR / "models" / "severity_model.json"
PAGE = "severity-models.html"
PHONE = {"width": 390, "height": 844}

if not (SITE / PAGE).exists() or not (SITE / "models" / "severity_model.json").exists():
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
            pytest.skip(f"Chromium could not be launched: {error}")
        yield launched
        launched.close()


@pytest.fixture()
def calculator(browser, server):
    page = browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console", lambda message: errors.append(message.text) if message.type == "error" else None
    )
    page.goto(f"{server}/{PAGE}", wait_until="networkidle")
    page.wait_for_selector("#calculator:not([hidden])")
    yield page
    assert errors == []
    page.close()


def _model() -> dict:
    return json.loads(MODEL.read_text())


def _scenarios(n: int) -> list[dict]:
    """The two reference crashes, every one-input change of them, and random scenarios."""
    import numpy as np

    out = [sm.REFERENCE_SCENARIO, sm.URBAN_REFERENCE]
    for base in (sm.REFERENCE_SCENARIO, sm.URBAN_REFERENCE):
        out += [scenario for _, _, scenario in sm._variants(base)]
    rng = np.random.default_rng(11)
    roads = [r for r in sm.ROADS if r != "through_town"]
    while len(out) < n:
        scenario = {"road": str(rng.choice(roads)), "province": str(rng.choice(list(sm.PROVINCES)))}
        for name, levels in sm.CATEGORICAL.items():
            scenario[name] = str(rng.choice(list(levels)))
        for user in sm.USERS:
            scenario[user] = int(rng.random() < 0.3)
        out.append(scenario)
    return out


def _percent(value: float) -> str:
    return f"{100 * value:.1f}%"


def _shown(page) -> str:
    return re.sub(r"\s+", " ", page.text_content("[data-output]"))


def test_reference_crashes_match_python(calculator) -> None:
    model = _model()
    # The calculator opens on the worked examples' reference crash.
    regional = sm.predict_exported(model, sm.REFERENCE_SCENARIO)
    text = _shown(calculator)
    assert text.startswith(_percent(regional["probability"]))
    assert f"{_percent(regional['low'])}–{_percent(regional['high'])}" in text
    assert "95% confidence interval" in text and "within 24 hours" in text
    calculator.select_option("#calc-road", "urban_street")
    urban = sm.predict_exported(model, sm.URBAN_REFERENCE)
    assert _shown(calculator).startswith(_percent(urban["probability"]))
    urban_here = model["zone_average"][f"urban|{sm.REFERENCE_SCENARIO['province']}"]
    assert f"{_percent(urban_here)} of those on urban streets in the province of" in _shown(
        calculator
    )


def test_the_engine_in_the_page_matches_python(calculator) -> None:
    model = _model()
    scenarios = _scenarios(120)
    results = calculator.evaluate(
        """async (scenarios) => {
            const model = await (await fetch('models/severity_model.json')).json();
            const engine = SeverityEngine.create(model);
            return scenarios.map(s => engine.check(s).errors.length ? null : engine.predict(s));
        }""",
        scenarios,
    )
    checked = 0
    for scenario, result in zip(scenarios, results):
        if result is None:
            continue
        expected = sm.predict_exported(model, scenario)
        for key in ("probability", "low", "high"):
            assert abs(result[key] - expected[key]) < 1e-10, (scenario, key)
        checked += 1
    assert checked > 100


def test_comparison_matches_python(calculator) -> None:
    model = _model()
    calculator.click("[data-keep]")
    calculator.check('input[name="users"][value="heavy_vehicle"]')
    expected = sm.compare_exported(
        model, sm.REFERENCE_SCENARIO | {"heavy_vehicle": 1}, sm.REFERENCE_SCENARIO
    )
    text = re.sub(r"\s+", " ", calculator.text_content("[data-baseline]"))
    assert f"{expected['ratio']:.2f} times the share" in text
    assert f"{expected['ratio_low']:.2f}–{expected['ratio_high']:.2f}" in text
    assert "percentage points" in text and "not the effect of changing" in text
    calculator.click("[data-clear]")
    assert "Keep this crash" in calculator.text_content("[data-baseline]")


def test_a_refused_crash_shows_no_comparison(calculator) -> None:
    """Once the current inputs are refused, no ratio from an earlier state stays on screen."""
    calculator.click("[data-keep]")
    calculator.check('input[name="users"][value="heavy_vehicle"]')
    assert "times the share" in calculator.text_content("[data-baseline]")
    calculator.select_option("#calc-crash_type", "pedestrian_struck")
    assert "No estimate" in _shown(calculator)
    baseline = calculator.text_content("[data-baseline]")
    assert "times the share" not in baseline and "No comparison" in baseline
    assert "Kept crash:" in baseline


def test_roads_through_towns_show_their_average(calculator) -> None:
    model = _model()
    calculator.select_option("#calc-road", "through_town")
    calculator.select_option("#calc-province", "Tarragona")
    text = _shown(calculator)
    assert text.startswith(_percent(model["zone_average"]["through_town|Tarragona"]))
    assert "in the province of Tarragona" in text
    assert "cannot tell more and less deadly crashes apart" in text
    assert calculator.is_disabled("[data-keep]")


def test_a_rarely_recorded_level_on_the_chosen_road_is_flagged(calculator) -> None:
    calculator.select_option("#calc-road", "conventional_local")
    calculator.select_option("#calc-speed_limit", "100_120")
    assert "Fewer than" in _shown(calculator) and "posted speed limit" in _shown(calculator)


def test_keyboard_alone_operates_the_calculator(calculator) -> None:
    calculator.focus("#calc-road")
    before = _shown(calculator)
    # Choose another road with the arrow keys, as a keyboard user would.
    calculator.keyboard.press("ArrowDown")
    assert calculator.input_value("#calc-road") != sm.REFERENCE_SCENARIO["road"]
    assert _shown(calculator) != before
    # Tab reaches every control in order, and the keep button works from the keyboard.
    calculator.focus('input[name="users"][value="other_unit"]')
    calculator.keyboard.press("Tab")
    assert calculator.evaluate("document.activeElement.hasAttribute('data-keep')")
    calculator.keyboard.press("Enter")
    calculator.wait_for_function(
        "document.querySelector('[data-status]').textContent === 'Crash kept for comparison.'"
    )
    assert calculator.get_attribute("[data-status]", "aria-live") == "polite"
    for control in calculator.query_selector_all("#calculator select"):
        label = calculator.evaluate(
            "(el) => document.querySelector(`label[for='${el.id}']`)?.textContent", control
        )
        assert label, control.get_attribute("id")


def test_an_impossible_crash_is_refused(calculator) -> None:
    calculator.select_option("#calc-crash_type", "pedestrian_struck")
    text = _shown(calculator)
    rule = next(r for r in _model()["rules"] if r["id"] == "pedestrian_struck_needs_pedestrian")
    assert "No estimate" in text and rule["text"] in text
    assert calculator.is_disabled("[data-keep]")
    calculator.check('input[name="users"][value="pedestrian"]')
    assert not calculator.is_disabled("[data-keep]")


@pytest.mark.parametrize("slug", ["index", "drivers", "severity-models", "validation", "data"])
def test_no_page_scrolls_sideways_on_a_phone(browser, server, slug: str) -> None:
    page = browser.new_page(viewport=PHONE)
    page.goto(f"{server}/{slug}.html", wait_until="networkidle")
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    page.close()
    assert overflow <= 1, (slug, overflow)


@pytest.mark.parametrize("broken", ["missing", "mismatched"])
def test_a_model_that_fails_to_load_leaves_the_fallback(browser, server, broken: str) -> None:
    page = browser.new_page()
    if broken == "missing":
        page.route("**/models/severity_model.json*", lambda route: route.fulfill(status=404))
    else:
        mismatched = json.dumps(_model() | {"model_id": "another-build"})
        page.route(
            "**/models/severity_model.json*",
            lambda route: route.fulfill(
                status=200, body=mismatched, content_type="application/json"
            ),
        )
    page.goto(f"{server}/{PAGE}", wait_until="networkidle")
    page.wait_for_function(
        "document.getElementById('calculator-fallback').textContent.includes('could not load')"
    )
    assert not page.is_visible("#calculator")
    page.close()


def test_without_scripting_the_fallback_is_shown(browser, server) -> None:
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(f"{server}/{PAGE}", wait_until="load")
    assert not page.is_visible("#calculator")
    assert page.is_visible("#calculator-fallback")
    context.close()
