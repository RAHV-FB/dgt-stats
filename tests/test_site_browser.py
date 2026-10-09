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
* the description of the crash sets the model's crash type, road users and number involved;
  the conditions offer only what the rules allow, adjust what they must and say so, and leave an
  ambiguous lighting to the reader;
* the comparison of scenarios A and B matches :func:`compare_exported`, and reset restores the
  defaults;
* every control is reachable and operable from the keyboard, and results are announced;
* random sequences of changes never pass a scenario the rules refuse to the engine;
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

# With REQUIRE_BROWSER set (as in CI), a missing browser library or an unbuilt site is an error,
# not a reason to skip.
REQUIRED = bool(os.environ.get("REQUIRE_BROWSER"))
if REQUIRED:
    from playwright import sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

SITE = PROJECT_ROOT / "site"
MODEL = REPORTS_DIR / "models" / "severity_model.json"
PAGE = "calculator.html"
PHONE = {"width": 390, "height": 844}

if not (SITE / PAGE).exists() or not (SITE / "models" / "severity_model.json").exists():
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
    """The two reference crashes, every one-input change of them (some of which the conditions
    rules refuse), and random scenarios the rules allow."""
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
        if not set(sm.check_scenario(scenario)) & sm.ERRORS:
            out.append(scenario)
    return out


def _percent(value: float) -> str:
    return f"{100 * value:.1f}%"


def _range(low: float, high: float) -> str:
    """An interval with the unit once, as the site writes it: '9.2–12.8%'."""
    return f"{100 * low:.1f}–{_percent(high)}"


def _shown(page) -> str:
    return re.sub(r"\s+", " ", page.text_content("[data-output]"))


def _text(page, selector: str) -> str:
    return re.sub(r"\s+", " ", page.text_content(selector) or "").strip()


def _disabled(page, control: str) -> set[str]:
    """The values of the options of ``calc-<control>`` the form does not offer now."""
    return set(
        page.eval_on_selector(
            f"#calc-{control}",
            "(s) => [...s.options].filter((o) => o.disabled && o.value).map((o) => o.value)",
        )
    )


def _described(crash: dict) -> dict:
    """The reference crash with a crash type, road users and number involved of its own."""
    users = {user: int(user in crash.get("users", ())) for user in sm.USERS}
    return sm.REFERENCE_SCENARIO | users | {k: v for k, v in crash.items() if k != "users"}


def _shows_estimate(page, scenario: dict) -> None:
    expected = sm.predict_exported(_model(), scenario)
    text = _shown(page)
    assert text.startswith(_percent(expected["probability"])), (scenario, text)
    assert f"95% confidence interval: {_range(expected['low'], expected['high'])}" in text


def test_reference_crashes_match_python(calculator) -> None:
    model = _model()
    # The calculator opens on the worked examples' reference crash.
    _shows_estimate(calculator, sm.REFERENCE_SCENARIO)
    text = _shown(calculator)
    # What the estimate is: a share among crashes already recorded with a death or serious
    # injury (a death within 24 hours), not a chance per crash or per journey.
    assert "within 24 hours" in text
    assert "among crashes like this one with a death or serious injury in Catalonia" in text
    assert "a share of crashes already recorded" in text
    assert "not the chance of a crash or of a death on a journey" in text
    # What the interval leaves out, said once in the notes below the calculator.
    notes = re.sub(r"\s+", " ", calculator.text_content(".tool-notes"))
    assert "only the uncertainty in the model's coefficients" in notes
    assert "not the differences between places and years" in notes
    left_out = f"{model['training']['excluded_owner_not_recorded']:,}"
    assert f"leave out the {left_out} on conventional roads whose owning network" in notes
    # The model's version, its years and a link to the method, in one line.
    first, last = model["training"]["years"]
    meta = _text(calculator, ".calc-meta")
    assert model["model_id"] in meta and f"{first}–{last}" in meta
    assert calculator.get_attribute(".calc-meta a", "href") == "severity-models.html"
    calculator.select_option("#calc-road", "urban_street")
    _shows_estimate(calculator, sm.URBAN_REFERENCE)
    key = f"urban|{sm.REFERENCE_SCENARIO['province']}"
    shown = _shown(calculator)
    assert f"{_percent(model['zone_average'][key])} of those on urban streets in the" in shown
    # The averages are over the crashes the model was fitted on, with their count.
    crashes, fatal, _, _ = model["zone_counts"][key]
    assert f"({fatal:,} of {crashes:,})" in shown
    assert "of the crashes the model was fitted on" in shown


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


def test_the_description_sets_the_models_inputs(calculator) -> None:
    """The kind of crash and its questions set the crash type, the road users and the number
    involved, and the page says which."""
    derived = "[data-derived]"
    assert _text(calculator, derived) == (
        "In the model: side or angle collision; road users: a car or van; number involved: two."
    )
    # A pedestrian struck: the pedestrian is involved.
    calculator.select_option("#calc-what", "pedestrian")
    assert "pedestrian struck; road users: a pedestrian and a car or van; number involved: two" in (
        _text(calculator, derived)
    )
    _shows_estimate(
        calculator,
        _described({"crash_type": "pedestrian_struck", "users": ("pedestrian", "light_vehicle")}),
    )
    # A car and a motorcycle in a collision: both, two involved.
    calculator.select_option("#calc-what", "collision")
    calculator.select_option("#calc-second", "motorcycle")
    assert "road users: a motorcycle and a car or van; number involved: two" in (
        _text(calculator, derived)
    )
    _shows_estimate(calculator, _described({"users": ("motorcycle", "light_vehicle")}))
    # A collision never has fewer than two involved, whatever its type.
    calculator.select_option("#calc-collision", "head_on")
    assert calculator.eval_on_selector(
        "#calc-vehicles", "(s) => [...s.options].map((o) => o.value)"
    ) == ["2", "3", "4+"]
    # A third kind of vehicle is asked only when there are three or more.
    assert not calculator.is_visible("#calc-collision-another")
    calculator.select_option("#calc-vehicles", "3")
    calculator.select_option("#calc-collision-another", "heavy_vehicle")
    _shows_estimate(
        calculator,
        _described(
            {
                "crash_type": "head_on",
                "units": "3",
                "users": ("motorcycle", "light_vehicle", "heavy_vehicle"),
            }
        ),
    )
    # A motorcyclist's fall: the motorcycle alone, one involved.
    calculator.select_option("#calc-what", "single")
    calculator.select_option("#calc-mishap", "fall")
    calculator.select_option("#calc-single-vehicle", "motorcycle")
    assert "road users: a motorcycle; number involved: one" in _text(calculator, derived)
    _shows_estimate(
        calculator, _described({"crash_type": "fall", "units": "1", "users": ("motorcycle",)})
    )
    assert not calculator.is_visible("#calc-collision")


def test_heavy_rain_leaves_no_dry_surface(calculator) -> None:
    calculator.select_option("#calc-weather", "heavy_rain_snow")
    assert calculator.input_value("#calc-surface") == "wet"
    assert _disabled(calculator, "surface") == {"dry"}
    note = _text(calculator, "[data-adjusted]")
    assert calculator.is_visible("[data-adjusted]") and "road surface set to wet" in note
    _shows_estimate(
        calculator, sm.REFERENCE_SCENARIO | {"weather": "heavy_rain_snow", "surface": "wet"}
    )
    calculator.select_option("#calc-surface", "slippery")
    assert not calculator.is_visible("[data-adjusted]")
    # Without heavy rain, a dry surface is offered again; nothing changes by itself.
    calculator.select_option("#calc-weather", "fine")
    assert _disabled(calculator, "surface") == set()
    assert calculator.input_value("#calc-surface") == "slippery"


def test_the_time_of_day_limits_the_lighting(calculator) -> None:
    # Late morning: daylight only.
    assert _disabled(calculator, "lighting") == set(sm.LIGHTING) - {"day", "overcast"}
    calculator.select_option("#calc-hour", "18-21")
    assert _disabled(calculator, "lighting") == set()
    calculator.select_option("#calc-lighting", "night_lit")
    for hour in ("00-05", "22-23"):
        calculator.select_option("#calc-hour", hour)
        assert _disabled(calculator, "lighting") == {"day", "overcast"}, hour
        assert calculator.input_value("#calc-lighting") == "night_lit"
    _shows_estimate(calculator, sm.REFERENCE_SCENARIO | {"hour": "22-23", "lighting": "night_lit"})
    # Back to late morning, only daylight remains: it is chosen, and the page says so.
    calculator.select_option("#calc-hour", "10-13")
    assert calculator.input_value("#calc-lighting") == "day"
    assert "it is daylight all year: lighting set to daylight" in _text(
        calculator, "[data-adjusted]"
    )
    _shows_estimate(calculator, sm.REFERENCE_SCENARIO)


def test_an_ambiguous_lighting_is_left_to_the_reader(calculator) -> None:
    calculator.select_option("#calc-hour", "00-05")
    # Dawn or night with lit, poorly lit or unlit streets: the reader chooses.
    assert calculator.input_value("#calc-lighting") == ""
    assert "Choose the lighting" in _text(calculator, "#calc-lighting option:checked")
    assert _shown(calculator).strip() == "Choose the lighting to see the estimate."
    assert _text(calculator, "[data-sticky]") == "Choose the lighting to see the estimate."
    assert calculator.is_disabled("[data-save]")
    calculator.select_option("#calc-lighting", "night_unlit")
    _shows_estimate(
        calculator, sm.REFERENCE_SCENARIO | {"hour": "00-05", "lighting": "night_unlit"}
    )
    assert not calculator.is_disabled("[data-save]")


def test_scenarios_a_and_b_match_python(calculator) -> None:
    model = _model()
    assert calculator.is_hidden("[data-clear]")
    calculator.click("[data-save]")
    calculator.locator("[data-status]", has_text="Scenario A saved").wait_for(state="attached")
    calculator.select_option("#calc-second", "heavy_vehicle")
    a = sm.REFERENCE_SCENARIO
    b = sm.REFERENCE_SCENARIO | {"heavy_vehicle": 1}
    pa, pb = sm.predict_exported(model, a), sm.predict_exported(model, b)
    compared = sm.compare_exported(model, b, a)
    rows = calculator.eval_on_selector_all(
        ".calc-ab tbody tr", "(rows) => rows.map((r) => [...r.cells].map((c) => c.textContent))"
    )

    def points(value: float) -> str:
        shown = f"{100 * value:.1f}"
        return ("+" if value > 0 else "") + shown.replace("-", "−")

    assert rows == [
        ["Scenario A", _percent(pa["probability"]), _range(pa["low"], pa["high"])],
        ["Scenario B", _percent(pb["probability"]), _range(pb["low"], pb["high"])],
        [
            "Difference, B − A",
            f"{points(compared['difference'])} points",
            f"{points(compared['difference_low'])} to {points(compared['difference_high'])}",
        ],
        [
            "Ratio, B ÷ A",
            f"{compared['ratio']:.2f}",
            f"{compared['ratio_low']:.2f}–{compared['ratio_high']:.2f}",
        ],
    ]
    baseline = _text(calculator, "[data-baseline]")
    assert "Scenario A differs from B in road users involved (a car or van)." in baseline
    assert "an association between recorded crashes" in baseline
    assert "not the effect of changing" in baseline
    assert f"B − A {points(compared['difference'])} percentage points" in _text(
        calculator, "[data-sticky]"
    )
    # While scenario B has no estimate, A stays named and no difference is shown.
    calculator.select_option("#calc-hour", "00-05")
    baseline = _text(calculator, "[data-baseline]")
    assert "No comparison until scenario B has an estimate." in baseline
    assert f"Scenario A: {_percent(pa['probability'])}" in baseline
    assert "time of day (10:00–13:59)" in baseline
    assert not calculator.query_selector(".calc-ab")
    calculator.click("[data-clear]")
    assert calculator.is_hidden("[data-clear]") and _text(calculator, "[data-baseline]") == ""
    calculator.select_option("#calc-lighting", "night_unlit")
    assert "save this one as scenario A" in _text(calculator, "[data-baseline]")


def test_reset_restores_the_defaults(calculator) -> None:
    defaults = calculator.eval_on_selector_all(
        "#calculator select", "(all) => all.map((s) => [s.id, s.value])"
    )
    calculator.click("[data-save]")
    calculator.select_option("#calc-what", "single")
    calculator.select_option("#calc-province", "Lleida")
    calculator.select_option("#calc-weather", "heavy_rain_snow")
    calculator.select_option("#calc-hour", "00-05")
    calculator.click('button[type="reset"]')
    calculator.locator("[data-status]", has_text="Inputs reset.").wait_for(state="attached")
    assert (
        calculator.eval_on_selector_all(
            "#calculator select", "(all) => all.map((s) => [s.id, s.value])"
        )
        == defaults
    )
    _shows_estimate(calculator, sm.REFERENCE_SCENARIO)
    assert _disabled(calculator, "surface") == set()
    assert not calculator.is_visible("[data-adjusted]")
    assert calculator.is_visible("#calc-collision") and not calculator.is_visible("#calc-mishap")
    # Scenario A is kept until it is cleared: the form is compared with it again.
    assert calculator.query_selector(".calc-ab")


def test_roads_through_towns_follow_the_published_choice(calculator) -> None:
    """Where the published choice gives roads through towns the average, the page shows it with
    its count and 95% interval; otherwise it gives the model's estimate."""
    model = _model()
    calculator.select_option("#calc-road", "through_town")
    calculator.select_option("#calc-province", "Lleida")
    text = _shown(calculator)
    if model["through_town"] != "average":
        scenario = sm.REFERENCE_SCENARIO | {"road": "through_town", "province": "Lleida"}
        assert text.startswith(_percent(sm.predict_exported(model, scenario)["probability"]))
        return
    assert text.startswith(_percent(model["zone_average"]["through_town|Lleida"]))
    assert "in the province of Lleida" in text
    crashes, fatal, low, high = model["zone_counts"]["through_town|Lleida"]
    assert f"({fatal:,} of {crashes:,}, 95% interval {_range(low, high)})" in text
    rule = next(r for r in model["rules"] if r["id"] == "through_town")
    assert rule["text"] in text
    assert calculator.is_disabled("[data-save]")


def test_a_rarely_recorded_level_on_the_chosen_road_is_flagged(calculator) -> None:
    calculator.select_option("#calc-road", "conventional_local")
    calculator.select_option("#calc-speed_limit", "100_120")
    warnings = calculator.eval_on_selector_all(
        ".calc-warnings li", "(items) => items.map((li) => li.textContent)"
    )
    assert any("Fewer than" in w and "posted speed limit" in w for w in warnings), warnings


def test_keyboard_alone_operates_the_calculator(calculator) -> None:
    calculator.focus("#calc-what")
    before = _shown(calculator)
    # Choose another kind of crash with the arrow keys, as a keyboard user would.
    calculator.keyboard.press("ArrowDown")
    assert calculator.input_value("#calc-what") == "pedestrian"
    assert calculator.is_visible("#calc-struck-by") and _shown(calculator) != before
    # Tab reaches every control in order, then the buttons; Enter saves scenario A.
    calculator.focus("#calc-surface")
    calculator.keyboard.press("Tab")
    assert calculator.evaluate("document.activeElement.hasAttribute('data-save')")
    calculator.keyboard.press("Enter")
    # Locators poll without evaluating strings, which the pages' security policy forbids.
    calculator.locator("[data-status]", has_text="Scenario A saved").wait_for(state="attached")
    assert calculator.get_attribute("[data-status]", "aria-live") == "polite"
    assert calculator.get_attribute("[data-status]", "role") == "status"
    for control in calculator.query_selector_all("#calculator select"):
        label = calculator.evaluate(
            "(el) => document.querySelector(`label[for='${el.id}']`)?.textContent", control
        )
        assert label, control.get_attribute("id")
    legends = calculator.eval_on_selector_all(
        "#calculator fieldset", "(sets) => sets.map((f) => f.querySelector('legend')?.textContent)"
    )
    assert legends == ["What happened?", "Where did it happen?", "Under what conditions?"]


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
    page.locator("#calc-surface").scroll_into_view_if_needed()
    page.select_option("#calc-surface", "wet")
    value = _box(page, ".calc-value")
    assert 0 <= value["top"] and value["bottom"] <= LAPTOP["height"], value
    expected = sm.predict_exported(_model(), sm.REFERENCE_SCENARIO | {"surface": "wet"})
    assert page.text_content(".calc-value") == _percent(expected["probability"])
    page.close()


def test_on_a_phone_the_estimate_follows_the_form_and_is_announced(browser, server) -> None:
    page = browser.new_page(viewport=PHONE)
    page.goto(f"{server}/{PAGE}", wait_until="networkidle")
    page.wait_for_selector("#calculator:not([hidden])")
    form, panel = _box(page, ".calc-layout > form"), _box(page, ".calc-panel")
    assert panel["top"] >= form["bottom"] - 1
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1
    page.select_option("#calc-lighting", "overcast")
    expected = sm.predict_exported(_model(), sm.REFERENCE_SCENARIO | {"lighting": "overcast"})
    announced = f"Estimate {_percent(expected['probability'])}, interval"
    page.locator("[data-status]", has_text=announced).wait_for(state="attached")
    assert page.text_content("[data-sticky]").startswith(
        f"Estimate {_percent(expected['probability'])} fatal"
    )
    # Scenarios A and B fit the phone's column.
    page.click("[data-save]")
    page.select_option("#calc-what", "pedestrian")
    table, column = _box(page, ".calc-ab"), _box(page, ".calc-panel")
    assert table["right"] <= column["right"] + 0.5
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1
    page.close()


@pytest.mark.parametrize(
    "size",
    [
        {"width": 320, "height": 640},
        {"width": 360, "height": 560},
        PHONE,
        {"width": 768, "height": 1024},
    ],
)
def test_the_pinned_estimate_never_covers_the_focused_control(browser, server, size) -> None:
    """On a narrow screen the estimate is pinned to the foot of the screen; a control reached
    with the keyboard is scrolled clear of it (WCAG 2.2, focus not obscured)."""
    page = browser.new_page(viewport=size, reduced_motion="reduce")
    page.goto(f"{server}/{PAGE}", wait_until="networkidle")
    page.wait_for_selector("[data-sticky]:not(:empty)")
    # With scenario A saved, every button is shown.
    page.click("[data-save]")
    controls = page.evaluate(
        "() => [...document.querySelectorAll('.calc-layout form select, .calc-layout form button')]"
        ".filter((el) => el.getClientRects().length).length"
    )
    page.focus("#calc-what")
    reached = 1
    for _ in range(40):
        page.keyboard.press("Tab")
        state = page.evaluate(
            """() => {
              const focused = document.activeElement;
              if (!focused || !focused.closest('.calc-layout form')) return null;
              const line = document.querySelector('[data-sticky]');
              const box = focused.getBoundingClientRect();
              return {name: focused.name || focused.textContent, top: box.top,
                      bottom: box.bottom, line: line.getBoundingClientRect().top,
                      shown: getComputedStyle(line).display !== 'none'};
            }"""
        )
        if state is None:
            break
        reached += 1
        assert state["shown"], size
        assert 0 <= state["top"] and state["bottom"] <= state["line"] + 0.5, (size, state)
    assert reached == controls >= 15, (reached, controls)
    page.close()


@pytest.mark.parametrize("size", [PHONE, LAPTOP])
def test_an_old_link_to_the_calculator_lands_on_its_page(browser, server, size) -> None:
    """The calculator moved from the model page to its own page: an old link to it arrives
    there."""
    page = browser.new_page(viewport=size, reduced_motion="reduce")
    page.goto(f"{server}/severity-models.html#calculator", wait_until="networkidle")
    page.wait_for_url(f"{server}/{PAGE}")
    page.wait_for_selector("#calculator:not([hidden])")
    page.close()


# Wrap the engine's predict and compare before the page creates it, to record any scenario the
# rules refuse that the page passes to them.
WATCH_ENGINE = """
(() => {
  let engine;
  window.__refused = [];
  window.__computed = 0;
  Object.defineProperty(window, 'SeverityEngine', {
    configurable: true,
    get() { return engine; },
    set(value) {
      engine = Object.assign({}, value, {
        create(model) {
          const made = value.create(model);
          const watch = (name) => {
            const original = made[name];
            made[name] = (...scenarios) => {
              for (const s of scenarios) {
                const errors = made.check(s).errors;
                if (errors.length) window.__refused.push({ call: name, scenario: s, errors });
              }
              window.__computed += 1;
              return original(...scenarios);
            };
          };
          watch('predict');
          watch('compare');
          return made;
        },
      });
    },
  });
})();
"""
# Random changes as a reader could make them: an offered option of a shown select, or a button.
# After each, the form and the result must agree: no select shows an option it does not offer,
# and the lighting is unchosen exactly when the page asks for it.
FUZZ = """
async ([seed, steps]) => {
  let state = seed;
  const random = () => { state = (state * 16807) % 2147483647; return state / 2147483647; };
  const form = document.querySelector('#calculator form');
  const shown = (el) => el.getClientRects().length > 0;
  const problems = [];
  for (let i = 0; i < steps; i++) {
    const r = random();
    const save = document.querySelector('[data-save]');
    const clear = document.querySelector('[data-clear]');
    if (r < 0.05 && !save.disabled) save.click();
    else if (r < 0.07 && !clear.hidden) clear.click();
    else if (r < 0.09) form.reset();
    else {
      const selects = [...form.querySelectorAll('select')].filter(shown);
      const select = selects[Math.floor(random() * selects.length)];
      const options = [...select.options].filter((o) => !o.disabled);
      select.value = options[Math.floor(random() * options.length)].value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }
    await new Promise((done) => setTimeout(done, 0));
    const output = document.querySelector('[data-output]').getAttribute('data-state');
    for (const select of form.querySelectorAll('select')) {
      const chosen = select.selectedOptions[0];
      if (chosen.disabled && chosen.value) problems.push([i, select.id, chosen.value]);
    }
    const unchosen = form.elements.lighting.value === '';
    if (unchosen !== (output === 'pending')) problems.push([i, 'lighting', output]);
    if (['ok', 'average', 'pending'].indexOf(output) < 0) problems.push([i, 'state', output]);
  }
  return { problems, refused: window.__refused, computed: window.__computed };
}
"""


@pytest.mark.parametrize("seed", [7, 2026, 90210])
def test_random_changes_never_pass_a_refused_scenario_to_the_engine(browser, server, seed) -> None:
    page = browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script(WATCH_ENGINE)
    page.goto(f"{server}/{PAGE}", wait_until="networkidle")
    page.wait_for_selector("#calculator:not([hidden])")
    result = page.evaluate(FUZZ, [seed, 400])
    page.close()
    assert errors == []
    assert result["refused"] == [], result["refused"][:3]
    assert result["problems"] == [], result["problems"][:5]
    assert result["computed"] > 100


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
