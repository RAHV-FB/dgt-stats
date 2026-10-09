"""The crash-severity calculator: its inputs, its rules and Python/JavaScript parity.

The page computes every prediction in the browser from ``reports/models/severity_model.json``
(``src/dgt_stats/site/assets/severity-engine.js``). These tests run that script under Node on
several hundred scenarios (random valid ones and edge cases) and require the same design vector,
probability and interval as :func:`dgt_stats.severity_model.predict_exported`, the same as an
independent computation written here from the exported column names, coefficients and covariance
alone, and the same rule checks as :func:`dgt_stats.severity_model.check_scenario`. They also
require the exported model to be the one the published choices give, and the page and the
calculator to say that the estimate is a share among crashes already recorded with a death or
serious injury, not the chance of a crash or of a death on a journey.

The page's own script (``assets/severity-calculator.js``) turns the reader's description of a
crash into the model's inputs and keeps the conditions possible; under Node it exports that
mapping (``SeverityBuilder``), and every description the form can give, and every combination of
conditions, is run through it here and must pass the rules.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from dgt_stats import severity_model as sm
from dgt_stats.paths import PROJECT_ROOT, REPORTS_DIR
from dgt_stats.site import tool_calculator

MODEL = REPORTS_DIR / "models" / "severity_model.json"
ENGINE = PROJECT_ROOT / "src" / "dgt_stats" / "site" / "assets" / "severity-engine.js"
BUILDER = ENGINE.parent / "severity-calculator.js"
NODE = shutil.which("node")

needs_model = pytest.mark.skipif(not MODEL.exists(), reason="run scripts/severity_calculator.py")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is not installed")


def _model() -> dict:
    return json.loads(MODEL.read_text())


def _random_scenario(rng: np.random.Generator) -> dict:
    scenario = {
        "road": str(rng.choice(list(sm.ROADS))),
        "province": str(rng.choice(list(sm.PROVINCES))),
    }
    for name, levels in sm.CATEGORICAL.items():
        scenario[name] = str(rng.choice(list(levels)))
    for user in sm.USERS:
        scenario[user] = int(rng.random() < 0.3)
    return scenario


def _edge_cases() -> list[dict]:
    """Every road in every province, every input at every level, and the boundaries of the
    rules: no user, every user, units at the number of kinds of user and one below it."""
    base = sm.REFERENCE_SCENARIO
    out = [base | {"road": road, "province": p} for road in sm.ROADS for p in sm.PROVINCES]
    for name, levels in sm.CATEGORICAL.items():
        for level in levels:
            for road in ("urban_street", "through_town", "motorway"):
                out.append(base | {"road": road, name: level})
    everyone = {user: 1 for user in sm.USERS}
    out += [
        base | {"light_vehicle": 0},  # no road user: refused
        base | everyone | {"units": "4+", "crash_type": "pedestrian_struck"},
        base | everyone | {"units": "3"},  # fewer units than kinds of user: refused
        base | {"crash_type": "pedestrian_struck"},  # no pedestrian ticked: refused
        base | {"light_vehicle": 0, "pedestrian": 1, "crash_type": "pedestrian_struck"},
        base | {"units": "1", "crash_type": "head_on"},  # a collision with one unit: a warning
        base | {"units": "1", "crash_type": "run_off_road", "road": "rural_track"},
        base | {"road": "conventional_local", "speed_limit": "100_120"},
    ]
    # The conditions rules: each broken, and the nearest combinations that keep them.
    out += [
        base | {"weather": "heavy_rain_snow", "surface": "dry"},  # refused
        base | {"weather": "heavy_rain_snow", "surface": "wet"},
        base | {"weather": "heavy_rain_snow", "surface": "slippery"},
        base | {"weather": "light_rain", "surface": "dry"},
    ]
    for hour in sm.HOURS:
        for lighting in sm.LIGHTING:
            out.append(base | {"hour": hour, "lighting": lighting, "road": "urban_street"})
    return out


def _scenarios(n_random: int = 300) -> list[dict]:
    """The reference crashes, every one-input change of them, edge cases and ``n_random``
    random valid scenarios."""
    out = [sm.REFERENCE_SCENARIO, sm.URBAN_REFERENCE]
    for base in (sm.REFERENCE_SCENARIO, sm.URBAN_REFERENCE):
        out += [scenario for _, _, scenario in sm._variants(base)]
    out += _edge_cases()
    rng = np.random.default_rng(7)
    valid = 0
    while valid < n_random:
        scenario = _random_scenario(rng)
        if not set(sm.check_scenario(scenario)) & sm.ERRORS:
            out.append(scenario)
            valid += 1
    return out


def _independent(model: dict, scenario: dict) -> dict[str, float]:
    """The estimate and its 95% interval computed from the exported file alone, without the
    package's design code: a column is 1 when its name matches the scenario."""
    zone = {lv["value"]: lv["zone"] for lv in model["inputs"]["road"]["levels"]}[scenario["road"]]
    ones = []
    for j, column in enumerate(model["columns"]):
        if column.startswith("zone="):
            hit = column == f"zone={zone}"
        elif column.startswith("zone_province="):
            hit = column == f"zone_province={zone}|{scenario['province']}"
        elif column.startswith("road="):
            hit = column == f"road={scenario['road']}"
        else:
            scope, term = column.split(":", 1)
            applies = scope in ("all", zone)
            if "=" in term:
                name, level = term.split("=", 1)
                hit = applies and str(scenario[name]) == level
            else:
                hit = applies and bool(scenario.get(term))
        if hit:
            ones.append(j)
    k = len(model["columns"])
    covariance = np.zeros((k, k))
    covariance[np.tril_indices(k)] = model["covariance_lower"]
    covariance = covariance + np.tril(covariance, -1).T
    logit = sum(model["coefficients"][j] for j in ones)
    se = float(np.sqrt(covariance[np.ix_(ones, ones)].sum()))
    expit = lambda z: 1 / (1 + np.exp(-z))  # noqa: E731
    return {
        "design": ones,
        "probability": expit(logit),
        "low": expit(logit - 1.959964 * se),
        "high": expit(logit + 1.959964 * se),
    }


def _run_engine(scenarios: list[dict]) -> list[dict]:
    script = f"""
const engine = require({json.dumps(str(ENGINE))});
const model = require({json.dumps(str(MODEL))});
const e = engine.create(model);
const scenarios = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = scenarios.map(s => {{
  const check = e.check(s);
  return Object.assign({{design: e.design(s), check: check}},
                       check.errors.length ? {{}} : e.predict(s));
}});
process.stdout.write(JSON.stringify(out));
"""
    result = subprocess.run(
        [NODE, "-e", script],
        input=json.dumps(scenarios),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_every_source_value_is_recoded() -> None:
    frame = pd.read_parquet(sm.FEATURES_PATH) if sm.FEATURES_PATH.exists() else None
    if frame is None:
        pytest.skip("run scripts/microdata.py features")
    scenarios = sm.scenarios_from_records(frame)
    assert scenarios.notna().all().all()
    assert set(scenarios.road) <= set(sm.ROADS) | set(sm.EXCLUDED_ROADS)
    for name, levels in sm.CATEGORICAL.items():
        assert set(scenarios[name]) <= set(levels), name


def test_the_recording_artefact_roads_are_never_fitted_or_offered() -> None:
    """Crashes on roads whose owner is "other" or blank are excluded from fitting, evaluation and
    the counts shown, and the calculator offers exactly the roads the model was fitted on."""
    offered = {level["value"] for level in sm.input_specification()["inputs"]["road"]["levels"]}
    assert offered == set(sm.ROADS)
    assert not offered & set(sm.EXCLUDED_ROADS)
    if not sm.FEATURES_PATH.exists():
        pytest.skip("run scripts/microdata.py features")
    frame, _, y = sm.load()
    assert not set(sm.scenarios_from_records(frame).road) & set(sm.EXCLUDED_ROADS)
    assert len(sm.load_all()) > len(frame) == len(y)


def test_unknown_input_levels_are_errors_not_the_reference() -> None:
    with pytest.raises(ValueError):
        sm.scenario_frame(sm.REFERENCE_SCENARIO | {"crash_type": "foo"})
    with pytest.raises(ValueError):
        sm.scenario_frame(sm.REFERENCE_SCENARIO | {"road": "conventional_owner_blank"})


def test_four_or_more_units_has_no_upper_bound() -> None:
    five_kinds = sm.REFERENCE_SCENARIO | {
        "units": "4+",
        "pedestrian": 1,
        "bicycle": 1,
        "moped": 1,
        "motorcycle": 1,
        "crash_type": "pedestrian_struck",
    }
    assert "units_cover_users" not in sm.check_scenario(five_kinds)
    assert "units_cover_users" in sm.check_scenario(five_kinds | {"units": "3"})


def test_the_conditions_rules() -> None:
    """Heavy rain, hail or snow never on a dry, clean surface; no daylight at 00:00-05:59 or
    22:00-23:59; nothing but daylight at 10:00-13:59; every lighting in the other bands."""
    base = sm.REFERENCE_SCENARIO
    for weather in sm.WEATHER:
        for surface in sm.SURFACE:
            broken = "heavy_rain_on_dry_surface" in sm.check_scenario(
                base | {"weather": weather, "surface": surface}
            )
            assert broken == (weather == "heavy_rain_snow" and surface == "dry")
    for hour in sm.HOURS:
        refused = {
            lighting
            for lighting in sm.LIGHTING
            if "lighting_outside_hours"
            in sm.check_scenario(base | {"hour": hour, "lighting": lighting})
        }
        if hour in ("00-05", "22-23"):
            assert refused == {"day", "overcast"}, hour
        elif hour == "10-13":
            assert refused == set(sm.LIGHTING) - {"day", "overcast"}, hour
        else:
            assert not refused, hour


def test_hard_rules_hold_in_the_training_records() -> None:
    """The three rules of the crash itself are broken by at most one recorded crash each. The two
    conditions rules are broken by a few records, recording inconsistencies kept in the fit: the
    calculator report gives their counts, and each stays under 2% of the fitted crashes."""
    if not sm.FEATURES_PATH.exists():
        pytest.skip("run scripts/microdata.py features")
    frame, _, _ = sm.load()
    scenarios = sm.scenarios_from_records(frame)
    broken = pd.Series(
        [
            id_
            for record in scenarios.to_dict("records")
            for id_ in sm.check_scenario(record)
            if id_ in sm.ERRORS
        ]
    ).value_counts()
    for rule in sm.CRASH_ERRORS:
        assert broken.get(rule, 0) <= 1, (rule, broken.get(rule, 0))
    report = (PROJECT_ROOT / "docs" / "research" / "SEVERITY_CALCULATOR.md").read_text()
    total = len(scenarios)
    for rule in sm.CONDITION_ERRORS:
        count = int(broken.get(rule, 0))
        assert count < 0.02 * total, (rule, count, total)
        assert f"{count:,} of {total:,}" in " ".join(report.split()), (rule, count)


@needs_model
def test_exported_coefficients_reproduce_the_fitted_model() -> None:
    if not sm.FEATURES_PATH.exists():
        pytest.skip("run scripts/microdata.py features")
    model = _model()
    exported_choice = model["choice"]
    choice = sm.Choice(
        specification=exported_choice["specification"],
        c=exported_choice["C"],
        through_town=exported_choice["through_town"],
        provinces=exported_choice["provinces"],
        train_years=tuple(exported_choice["train_years"]),
        validation_years=tuple(exported_choice["validation_years"]),
        c_bracketed=exported_choice["c_bracketed"],
    )
    fitted, x = sm.final_fit(choice)
    assert fitted.columns == model["columns"] == choice.columns
    assert model["model_id"] == sm.model_id(model["columns"], model["coefficients"])
    assert model["penalty"]["C"] == choice.c and model["through_town"] == choice.through_town
    exported = np.array(model["coefficients"])
    assert np.abs(fitted.coef - exported).max() < 1e-7
    assert np.abs(sm.expit(x @ fitted.coef) - sm.expit(x @ exported)).max() < 1e-7


@needs_model
@needs_node
def test_javascript_matches_python() -> None:
    """At least 200 random valid scenarios and every edge case: the engine's design vector,
    estimate and interval equal the package's and an independent computation from the exported
    file, and its rules equal the package's."""
    model = _model()
    scenarios = _scenarios()
    results = _run_engine(scenarios)
    assert len(results) == len(scenarios)
    columns = model["columns"]
    compared, through_town = 0, 0
    for scenario, js in zip(scenarios, results):
        x = sm.design_matrix(sm.scenario_frame(scenario), columns)[0]
        independent = _independent(model, scenario)
        assert js["design"] == [int(i) for i in np.flatnonzero(x)] == independent["design"]
        python_rules = set(sm.check_scenario(scenario, model["through_town"]))
        js_rules = set(js["check"]["errors"]) | set(js["check"]["warnings"])
        assert python_rules == js_rules - {"few_similar", "rare_level"}
        if js["check"]["errors"]:
            continue
        through_town += "through_town" in js_rules
        expected = sm.predict_exported(model, scenario)
        for key in ("probability", "low", "high"):
            assert abs(js[key] - expected[key]) < 1e-12, (scenario, key)
            assert abs(js[key] - independent[key]) < 1e-10, (scenario, key)
        assert js["low"] < js["probability"] < js["high"]
        compared += 1
    assert compared >= 200
    assert (through_town > 0) == (model["through_town"] == "average")


@needs_model
@needs_node
def test_changing_an_input_changes_the_prediction() -> None:
    """Every input the page offers moves the prediction for at least one reference crash."""
    model = _model()
    results = _run_engine([sm.REFERENCE_SCENARIO, sm.URBAN_REFERENCE])
    base = {r["probability"] for r in results}
    for name in ("road", *sm.CATEGORICAL):
        for base_scenario in (sm.REFERENCE_SCENARIO, sm.URBAN_REFERENCE):
            levels = [lv["value"] for lv in model["inputs"][name]["levels"]]
            changed = [base_scenario | {name: level} for level in levels]
            changed = [s for s in changed if not set(sm.check_scenario(s)) & sm.ERRORS]
            probabilities = {round(r["probability"], 12) for r in _run_engine(changed)}
            if len(probabilities) > 1:
                break
        else:
            pytest.fail(f"{name} never changes the prediction")
    assert len(base) == 2


@needs_model
@needs_node
def test_comparison_matches_python() -> None:
    model = _model()
    scenarios = [s for s in _scenarios(80) if not set(sm.check_scenario(s)) & sm.ERRORS]
    pairs = [(scenarios[i], scenarios[i + 1]) for i in range(0, len(scenarios) - 1, 2)]
    script = f"""
const engine = require({json.dumps(str(ENGINE))});
const e = engine.create(require({json.dumps(str(MODEL))}));
const pairs = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(pairs.map(p => e.compare(p[0], p[1]))));
"""
    result = subprocess.run(
        [NODE, "-e", script], input=json.dumps(pairs), capture_output=True, text=True, check=True
    )
    for (first, second), js in zip(pairs, json.loads(result.stdout)):
        expected = sm.compare_exported(model, first, second)
        for key, value in expected.items():
            assert abs(js[key] - value) < 1e-10, key
        assert expected["ratio_low"] <= expected["ratio"] <= expected["ratio_high"]


@needs_model
def test_worked_examples_use_the_calculators_arithmetic() -> None:
    """The page's table of one-input changes and the calculator give the same intervals."""
    from dgt_stats.paths import TABLES_DIR

    model = _model()
    contrasts = pd.read_csv(TABLES_DIR / "sev_contrasts.csv")
    for base_name, base in (("interurban", sm.REFERENCE_SCENARIO), ("urban", sm.URBAN_REFERENCE)):
        rows = contrasts[contrasts.base == base_name].set_index(["input", "level"])
        for name, level, scenario in sm._variants(base):
            row = rows.loc[(name, level)]
            predicted = sm.predict_exported(model, scenario)
            compared = sm.compare_exported(model, scenario, base)
            assert abs(row.probability_low - predicted["low"]) < 1e-6, (name, level)
            assert abs(row.probability_high - predicted["high"]) < 1e-6, (name, level)
            assert abs(row.ratio_low - compared["ratio_low"]) < 1e-6, (name, level)
            assert abs(row.ratio_high - compared["ratio_high"]) < 1e-6, (name, level)


@needs_model
@needs_node
def test_rare_levels_are_flagged_for_the_chosen_road() -> None:
    """An input level seldom recorded on the chosen road is flagged even when it is common in
    its zone (a posted 100-120 km/h limit on a local road)."""
    model = _model()
    scenario = sm.REFERENCE_SCENARIO | {"road": "conventional_local", "speed_limit": "100_120"}
    count = model["level_support"].get("conventional_local|speed_limit=100_120", 0)
    assert count < sm.SUPPORT_FEW
    (result,) = _run_engine([scenario])
    assert "rare_level" in result["check"]["warnings"]
    assert "speed_limit" in result["check"]["rare"]


@needs_model
def test_roads_through_towns_follow_the_published_choice() -> None:
    """The through-town rule is the published model's nested choice. Where it gives the average,
    the page shows the observed share with its count and 95% interval."""
    model = _model()
    rules = {r["id"]: r for r in model["rules"]}
    assert model["through_town"] == model["choice"]["through_town"]
    assert ("through_town" in rules) == (model["through_town"] == "average")
    if "through_town" in rules:
        assert rules["through_town"]["kind"] == "average"
    for key, share in model["zone_average"].items():
        crashes, fatal, low, high = model["zone_counts"][key]
        assert abs(share - fatal / crashes) < 1e-12, key
        assert low < share < high, key


@needs_model
def test_the_averages_name_the_crashes_left_out() -> None:
    """The calculator's averages are over the fitted crashes, which leave out the conventional
    roads whose owning network is not named; the export says how many."""
    model = _model()
    training = model["training"]
    assert training["excluded_owner_not_recorded"] > 0
    assert 0 < training["excluded_fatal"] < training["excluded_owner_not_recorded"]
    assert abs(model["zone_average"]["all"] - training["fatal"] / training["crashes"]) < 1e-12
    assert "of the crashes the model was fitted on" in _calculator_text()
    assert "of all such crashes in Catalonia" not in _calculator_text()


def _calculator_text() -> str:
    """The calculator script with its string concatenations joined, as one line."""
    script = BUILDER.read_text(encoding="utf-8")
    return " ".join(re.sub(r'"\s*\+\s*"', "", script).split())


def test_the_estimate_is_framed_as_a_conditional_share() -> None:
    """The calculator says its estimate is a share among crashes already recorded with a death
    or serious injury, not the chance of a crash or of a death on a journey."""
    flat = _calculator_text()
    assert "among crashes like this one with a death or serious injury in Catalonia" in flat
    assert "a share of crashes already recorded" in flat
    assert "not the chance of a crash or of a death on a journey" in flat
    for wrong in ("chance of dying", "probability of a crash", "risk of a crash"):
        assert wrong not in flat.lower()
    model = _model() if MODEL.exists() else None
    if model is not None:
        assert model["question"].startswith(
            "Of crashes in Catalonia with a death or a serious injury"
        )


def _run_builder(body: str, payload: object) -> object:
    """Run ``body`` under Node with the page's builder (``builder``), an engine on the exported
    model (``engine``) and ``payload`` (``input``); it writes its JSON result to stdout."""
    script = f"""
const builder = require({json.dumps(str(BUILDER))});
const engine = require({json.dumps(str(ENGINE))}).create(require({json.dumps(str(MODEL))}));
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
{body}
"""
    result = subprocess.run(
        [NODE, "-e", script], input=json.dumps(payload), capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def _from_description(crash: dict) -> dict:
    """The reference crash's place and conditions with a described crash's model inputs."""
    base = {k: v for k, v in sm.REFERENCE_SCENARIO.items() if k not in sm.USERS}
    return (
        base
        | {"crash_type": crash["crash_type"], "units": crash["units"]}
        | {user: int(user in crash["users"]) for user in sm.USERS}
    )


@needs_model
@needs_node
def test_every_crash_the_form_describes_passes_the_rules() -> None:
    """Every description the "What happened?" selects can give becomes a scenario that breaks no
    error rule, in Python and in the engine; together they reach every crash type, every kind of
    road user and every number involved, so no level of the model is lost to the form."""
    choices = tool_calculator.builder_choices()
    described = _run_builder(
        "process.stdout.write(JSON.stringify(input.map(c => builder.crash(c))));", choices
    )
    scenarios = []
    for choice, crash in zip(choices, described, strict=True):
        scenario = _from_description(crash)
        assert not set(sm.check_scenario(scenario)) & sm.ERRORS, (choice, scenario)
        # The vehicles named are involved; collisions and a pedestrian struck have two or more.
        assert choice["vehicle"] in crash["users"], choice
        if choice["what"] == "collision":
            assert choice["second"] in crash["users"] and crash["units"] != "1", choice
        if choice["what"] == "pedestrian":
            assert crash["crash_type"] == "pedestrian_struck" and scenario["pedestrian"], choice
        if choice["what"] == "single":
            assert crash["units"] == "1" and crash["users"] == [choice["vehicle"]], choice
        scenarios.append(scenario)
    assert not [r for r in _run_engine(scenarios) if r["check"]["errors"]]
    assert {s["crash_type"] for s in scenarios} == set(sm.CRASH_TYPES)
    assert {s["units"] for s in scenarios} == set(sm.UNITS)
    assert {user for s in scenarios for user in sm.USERS if s[user]} == set(sm.USERS)
    # Three plain descriptions.
    examples = [
        {"what": "pedestrian", "vehicle": "light_vehicle", "count": "2", "another": ""},
        {
            "what": "collision",
            "type": "head_on",
            "vehicle": "light_vehicle",
            "second": "motorcycle",
            "count": "2",
            "another": "heavy_vehicle",  # not asked with two vehicles: ignored
        },
        {"what": "single", "type": "fall", "vehicle": "motorcycle"},
    ]
    pedestrian, collision, fall = _run_builder(
        "process.stdout.write(JSON.stringify(input.map(c => builder.crash(c))));", examples
    )
    assert pedestrian == {
        "crash_type": "pedestrian_struck",
        "units": "2",
        "users": ["pedestrian", "light_vehicle"],
    }
    assert collision == {
        "crash_type": "head_on",
        "units": "2",
        "users": ["light_vehicle", "motorcycle"],
    }
    assert fall == {"crash_type": "fall", "units": "1", "users": ["motorcycle"]}


@needs_model
@needs_node
def test_the_conditions_the_form_allows_pass_the_rules() -> None:
    """For every time of day, lighting (or none chosen yet), weather and surface, the form offers
    exactly the options the rules allow, changes a selection only when the rules rule it out,
    chooses daylight only when nothing else remains, and otherwise leaves the lighting to the
    reader. Whatever it settles on with a lighting breaks no rule."""
    base = sm.REFERENCE_SCENARIO
    states = [
        base | {"hour": hour, "lighting": lighting, "weather": weather, "surface": surface}
        for hour in sm.HOURS
        for lighting in (*sm.LIGHTING, "")
        for weather in sm.WEATHER
        for surface in sm.SURFACE
    ]
    settled = _run_builder(
        "process.stdout.write(JSON.stringify(input.map(s => builder.settle(engine, s))));", states
    )
    asked = 0
    for before, out in zip(states, settled, strict=True):
        after = out["scenario"]
        lighting = [
            level
            for level in sm.LIGHTING
            if "lighting_outside_hours" not in sm.check_scenario(after | {"lighting": level})
        ]
        surface = [
            level
            for level in sm.SURFACE
            if "heavy_rain_on_dry_surface" not in sm.check_scenario(after | {"surface": level})
        ]
        assert out["lighting"] == lighting and out["surface"] == surface, before
        assert {k for k in before if before[k] != after[k]} <= {"surface", "lighting"}
        if before["surface"] in surface:
            assert after["surface"] == before["surface"]
        else:
            assert after["surface"] == "wet" and "surface" in out["changed"], before
        if before["lighting"] in lighting:
            assert after["lighting"] == before["lighting"]
        elif all(level in sm.DAYLIGHT for level in lighting):
            assert after["lighting"] == "day" and "lighting" in out["changed"], before
        else:
            assert after["lighting"] == "" and "lighting" not in out["changed"], before
        if after["lighting"]:
            assert not set(sm.check_scenario(after)) & sm.ERRORS, after
        else:
            asked += 1
            assert after["hour"] != "10-13"
    assert asked


@needs_model
@needs_node
def test_the_engine_refuses_a_scenario_that_breaks_a_rule() -> None:
    """The engine computes no estimate and no comparison for a scenario the rules refuse."""
    base = sm.REFERENCE_SCENARIO
    refused = [
        base | {"light_vehicle": 0},
        base | {"crash_type": "pedestrian_struck"},
        base | {"weather": "heavy_rain_snow"},
        base | {"lighting": "night_unlit"},
        base | {"hour": "00-05"},
    ]
    messages = _run_builder(
        """
const attempt = (f) => { try { f(); return 'computed'; } catch (error) { return error.message; } };
const base = input[input.length - 1];
process.stdout.write(JSON.stringify(input.slice(0, -1).map(s => [
  attempt(() => engine.predict(s)), attempt(() => engine.compare(s, base))])));""",
        [*refused, base],
    )
    for scenario, (predicted, compared) in zip(refused, messages, strict=True):
        rules = sorted(set(sm.check_scenario(scenario)) & sm.ERRORS)
        assert rules, scenario
        for message in (predicted, compared):
            assert message.startswith("refused scenario: "), message
            assert sorted(message.removeprefix("refused scenario: ").split(", ")) == rules
