"""The built site in a real browser: the calculator, the keyboard, a phone's width, no scripting.

These tests serve ``site/`` (built by ``scripts/build_site.py``) over HTTP and drive it with
Playwright's Chromium. They need the optional browser dependency
(``pip install -e .[browser]``) and a Chromium build; they skip otherwise. Set
``PLAYWRIGHT_CHROMIUM`` to use a Chromium executable that Playwright did not install itself, and
``REQUIRE_BROWSER`` to fail rather than skip when no browser can be launched (as CI does).

What they check:

* the calculator loads its model and shows, for the reference crashes, the probability and
  interval that :func:`dgt_stats.severity_model.predict_exported` computes in Python, and the
  engine running in the page agrees with Python to 1e-10 on many scenarios;
* the two-scenario comparison matches :func:`compare_exported`;
* every control is reachable and operable from the keyboard, and results are announced;
* an impossible combination is refused with the rule's own words;
* at a phone's width no page scrolls sideways;
* at a phone's width every figure loads the chart drawn for a phone, fits its column without
  scrolling and shows its smallest text at 11 px or more, while a desktop loads the full chart;
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
from dgt_stats.site.components import FIGURE_SCALE

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
            if os.environ.get("REQUIRE_BROWSER"):
                raise
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


def _range(low: float, high: float) -> str:
    """An interval with the unit once, as the site writes it: '9.2–12.8%'."""
    return f"{100 * low:.1f}–{_percent(high)}"


def _shown(page) -> str:
    return re.sub(r"\s+", " ", page.text_content("[data-output]"))


def test_reference_crashes_match_python(calculator) -> None:
    model = _model()
    # The calculator opens on the worked examples' reference crash.
    regional = sm.predict_exported(model, sm.REFERENCE_SCENARIO)
    text = _shown(calculator)
    assert text.startswith(_percent(regional["probability"]))
    assert f"95% confidence interval: {_range(regional['low'], regional['high'])}" in text
    assert "within 24 hours" in text
    # Beside the interval, what it leaves out.
    assert "only the uncertainty in the model's coefficients" in text
    assert "not the differences between places and years" in text
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
    # The kept crash is named by what differs from the crash on the form.
    kept = sm.predict_exported(model, sm.REFERENCE_SCENARIO)
    assert f"({_percent(kept['probability'])}, {_range(kept['low'], kept['high'])})" in text
    assert "differs from this one in road users involved (A car or van)" in text
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
    # The kept crash is still named, by the inputs to change back.
    assert "The kept crash differs from this one in" in baseline
    assert "type of crash (Side or angle collision)" in baseline


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
    # Locators poll without evaluating strings, which the pages' security policy forbids.
    calculator.locator("[data-status]", has_text="Crash kept for comparison.").wait_for(
        state="attached"
    )
    assert calculator.get_attribute("[data-status]", "aria-live") == "polite"
    for control in calculator.query_selector_all("#calculator select"):
        label = calculator.evaluate(
            "(el) => document.querySelector(`label[for='${el.id}']`)?.textContent", control
        )
        assert label, control.get_attribute("id")


LAPTOP = {"width": 1280, "height": 760}


def _box(page, selector: str) -> dict:
    return page.evaluate(
        "(s) => { const b = document.querySelector(s).getBoundingClientRect();"
        " return {top: b.top, bottom: b.bottom, left: b.left, right: b.right}; }",
        selector,
    )


def test_on_a_laptop_the_estimate_stays_beside_the_form(browser, server) -> None:
    """Changing an input anywhere in the form leaves the estimate on the screen."""
    page = browser.new_page(viewport=LAPTOP)
    page.goto(f"{server}/{PAGE}", wait_until="networkidle")
    page.wait_for_selector("#calculator:not([hidden])")
    form, panel = _box(page, ".calc-layout > form"), _box(page, ".calc-panel")
    assert panel["left"] >= form["right"]
    assert abs(panel["top"] - form["top"]) < 2
    # The last input of the form: once it is on screen and changed, the new estimate is too.
    last = 'input[name="users"][value="heavy_vehicle"]'
    page.locator(last).scroll_into_view_if_needed()
    page.check(last)
    value = _box(page, ".calc-value")
    assert 0 <= value["top"] and value["bottom"] <= LAPTOP["height"], value
    expected = sm.predict_exported(_model(), sm.REFERENCE_SCENARIO | {"heavy_vehicle": 1})
    assert page.text_content(".calc-value") == _percent(expected["probability"])
    page.close()


def test_on_a_phone_the_estimate_follows_the_form_and_is_announced(browser, server) -> None:
    page = browser.new_page(viewport=PHONE)
    page.goto(f"{server}/{PAGE}", wait_until="networkidle")
    page.wait_for_selector("#calculator:not([hidden])")
    form, panel = _box(page, ".calc-layout > form"), _box(page, ".calc-panel")
    assert panel["top"] >= form["bottom"] - 1
    page.select_option("#calc-lighting", "night_unlit")
    expected = sm.predict_exported(_model(), sm.REFERENCE_SCENARIO | {"lighting": "night_unlit"})
    announced = f"Estimate {_percent(expected['probability'])}, interval"
    page.locator("[data-status]", has_text=announced).wait_for(state="attached")
    page.close()


def test_an_impossible_crash_is_refused(calculator) -> None:
    calculator.select_option("#calc-crash_type", "pedestrian_struck")
    text = _shown(calculator)
    rule = next(r for r in _model()["rules"] if r["id"] == "pedestrian_struck_needs_pedestrian")
    assert "No estimate" in text and rule["text"] in text
    assert calculator.is_disabled("[data-keep]")
    calculator.check('input[name="users"][value="pedestrian"]')
    assert not calculator.is_disabled("[data-keep]")


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
    if '<img src="figures/' in path.read_text(encoding="utf-8")
)
# Every figure on the page, brought into view so that its lazy image loads, then measured.
FIGURES = """async () => {
  const out = [];
  for (const figure of document.querySelectorAll('main figure')) {
    const img = figure.querySelector('img');
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
      name: img.getAttribute('src').replace('figures/', '').replace('.svg', ''),
      source: img.currentSrc,
      loaded: img.complete && img.naturalWidth > 0,
      width: box.width,
      right: box.right,
      column: figure.getBoundingClientRect().width,
      columnRight: figure.getBoundingClientRect().right,
      scrolls: media.scrollWidth - media.clientWidth,
    });
  }
  return out;
}"""


def _svg_text(path: Path) -> tuple[float, float]:
    """A chart's viewBox width and its smallest text, in the same units."""
    text = path.read_text(encoding="utf-8")
    width = float(re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ', text).group(1))
    return width, min(float(size) for size in re.findall(r"font-size: ([\d.]+)px", text))


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("slug", FIGURE_PAGES)
def test_every_figure_fits_a_phone_column(browser, server, slug: str, scheme: str) -> None:
    """At 390 px every figure loads the chart drawn for a phone's column, is no wider than its
    column, does not scroll sideways, and shows its smallest text at 11 px or more."""
    page = browser.new_page(viewport=PHONE, color_scheme=scheme)
    page.goto(f"{server}/{slug}.html", wait_until="networkidle")
    figures = page.evaluate(FIGURES)
    page.close()
    assert figures, slug
    for figure in figures:
        name = figure["name"]
        assert figure["loaded"], (slug, scheme, name)
        assert figure["source"].endswith(f"/figures/narrow/{name}.svg"), (slug, scheme, figure)
        assert figure["width"] <= figure["column"] + 0.5, (slug, scheme, figure)
        assert figure["right"] <= figure["columnRight"] + 0.5, (slug, scheme, figure)
        assert figure["scrolls"] <= 1, (slug, scheme, figure)
        width, smallest = _svg_text(SITE / "figures" / "narrow" / f"{name}.svg")
        assert smallest * figure["width"] / width >= 11, (slug, scheme, name)


def test_a_desktop_loads_the_full_figures(browser, server) -> None:
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(f"{server}/seasons.html", wait_until="networkidle")
    figures = page.evaluate(FIGURES)
    page.close()
    assert figures
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
    page.locator("#calculator-fallback", has_text="could not load").wait_for(state="attached")
    assert not page.is_visible("#calculator")
    page.close()


def test_without_scripting_the_fallback_is_shown(browser, server) -> None:
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(f"{server}/{PAGE}", wait_until="load")
    assert not page.is_visible("#calculator")
    assert page.is_visible("#calculator-fallback")
    context.close()
