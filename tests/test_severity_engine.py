"""The crash-severity calculator: its inputs, its rules and Python/JavaScript parity.

The page computes every prediction in the browser from ``reports/models/severity_model.json``
(``src/dgt_stats/site/assets/severity-engine.js``). These tests run that script under Node on a
fixed set of scenarios and require the same design vector, probability and interval as
:func:`dgt_stats.severity_model.predict_exported`, and the same rule checks as
:func:`dgt_stats.severity_model.check_scenario`.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from dgt_stats import severity_model as sm
from dgt_stats.paths import PROJECT_ROOT, REPORTS_DIR

MODEL = REPORTS_DIR / "models" / "severity_model.json"
ENGINE = PROJECT_ROOT / "src" / "dgt_stats" / "site" / "assets" / "severity-engine.js"
NODE = shutil.which("node")

needs_model = pytest.mark.skipif(not MODEL.exists(), reason="run scripts/severity_calculator.py")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is not installed")


def _model() -> dict:
    return json.loads(MODEL.read_text())


def _scenarios(n_random: int = 300) -> list[dict]:
    """The reference crashes, every one-input change of them, and random valid scenarios."""
    out = [sm.REFERENCE_SCENARIO, sm.URBAN_REFERENCE]
    for base in (sm.REFERENCE_SCENARIO, sm.URBAN_REFERENCE):
        out += [scenario for _, _, scenario in sm._variants(base)]
    rng = np.random.default_rng(7)
    roads = [r for r in sm.ROADS if r not in sm.TRAINING_ONLY_ROADS]
    while len(out) < n_random + 2:
        scenario = {"road": str(rng.choice(roads))}
        for name, levels in sm.CATEGORICAL.items():
            scenario[name] = str(rng.choice(list(levels)))
        for user in sm.USERS:
            scenario[user] = int(rng.random() < 0.3)
        out.append(scenario)
    return out


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
    assert set(scenarios.road) <= set(sm.ROADS)
    for name, levels in sm.CATEGORICAL.items():
        assert set(scenarios[name]) <= set(levels), name


def test_training_only_roads_are_never_offered() -> None:
    offered = {level["value"] for level in sm.input_specification()["inputs"]["road"]["levels"]}
    assert not offered & set(sm.TRAINING_ONLY_ROADS)
    assert offered | set(sm.TRAINING_ONLY_ROADS) == set(sm.ROADS)


def test_hard_rules_hold_in_the_training_records() -> None:
    """The three rules the page enforces are broken by at most one recorded crash each."""
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
    )
    assert broken.value_counts().max() <= 1


@needs_model
def test_exported_coefficients_reproduce_the_fitted_model() -> None:
    if not sm.FEATURES_PATH.exists():
        pytest.skip("run scripts/microdata.py features")
    model = _model()
    fitted, x = sm.final_fit(model["penalty"]["C"], model["penalty"]["deviation_scale"])
    assert fitted.columns == model["columns"]
    exported = np.array(model["coefficients"])
    assert np.abs(fitted.coef - exported).max() < 1e-7
    assert np.abs(sm.expit(x @ fitted.coef) - sm.expit(x @ exported)).max() < 1e-7


@needs_model
@needs_node
def test_javascript_matches_python() -> None:
    model = _model()
    scenarios = _scenarios()
    results = _run_engine(scenarios)
    assert len(results) == len(scenarios)
    columns = model["columns"]
    compared = 0
    for scenario, js in zip(scenarios, results):
        x = sm.design_matrix(sm.scenario_frame(scenario), columns)[0]
        assert js["design"] == [int(i) for i in np.flatnonzero(x)]
        python_rules = set(sm.check_scenario(scenario))
        js_rules = set(js["check"]["errors"]) | set(js["check"]["warnings"])
        assert python_rules == js_rules - {"few_similar", "rare_level"}
        if js["check"]["errors"]:
            continue
        expected = sm.predict_exported(model, scenario)
        for key in ("probability", "low", "high"):
            assert abs(js[key] - expected[key]) < 1e-12, (scenario, key)
        compared += 1
    assert compared >= 100


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
