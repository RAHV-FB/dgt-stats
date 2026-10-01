import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import integrate, stats

from dgt_stats import simulator
from dgt_stats.paths import PROCESSED_DATA_DIR, TABLES_DIR

JS = Path(simulator.__file__).parent / "assets" / "simulator.js"


def test_every_published_value_carries_its_source() -> None:
    rows = simulator.evidence()
    for column in ("source", "location", "url"):
        assert rows[column].notna().all(), column
    assert rows.url.str.startswith("http").all()
    # Every value the browser reads is in the register exactly once.
    for outcome in simulator.OUTCOMES:
        for environment in ("rural", "urban"):
            low, value, high = (
                simulator.parameter(f"exponent_{outcome}", environment, bound)
                for bound in ("low", "value", "high")
            )
            assert low <= value <= high
    for site in simulator.SITES:
        for name in ("limit", "mean_speed", "v85", "share_within_limit"):
            simulator.parameter(name, site)
    # More severe outcomes respond more strongly to speed, as the evidence says.
    for environment in ("rural", "urban"):
        order = [
            simulator.exponent(o, environment)
            for o in ("deaths", "seriously_injured", "slightly_injured")
        ]
        assert order == sorted(order, reverse=True)


def test_typical_response_is_partial_and_stays_inside_the_evidence() -> None:
    assert simulator.typical_response(0) == 0
    changes = np.arange(-30, 21, 5)
    responses = [simulator.typical_response(float(c)) for c in changes]
    assert np.all(np.diff(responses) > 0)
    # Drivers move by less than the limit: about 8 km/h for a cut of 20, says the handbook.
    assert -9 < simulator.typical_response(-20) < -6
    for change in changes[changes != 0]:
        assert abs(simulator.typical_response(float(change))) < abs(change)
    with pytest.raises(ValueError):
        simulator.typical_response(-40)


@pytest.mark.parametrize("site", list(simulator.SITES))
def test_the_speed_distribution_reproduces_what_was_measured(site: str) -> None:
    d = simulator.speed_distribution(site)
    lognormal = stats.lognorm(s=d.sigma, scale=math.exp(d.mu))
    assert lognormal.cdf(d.limit) == pytest.approx(d.share_within_limit, abs=1e-9)
    assert lognormal.ppf(0.85) == pytest.approx(d.v85, abs=1e-9)
    # The third measured statistic, the mean, is not used to fit and is reproduced closely.
    assert d.implied_mean == pytest.approx(d.mean, abs=1.0)
    # The closed form of the excess over the limit agrees with numerical integration.
    numeric, _ = integrate.quad(lambda v: (v - d.limit) * lognormal.pdf(v), d.limit, np.inf)
    assert d.excess(d.limit) == pytest.approx(numeric, rel=1e-6)


def test_full_compliance_caps_every_speed_at_the_limit() -> None:
    d = simulator.speed_distribution("conventional")
    lognormal = stats.lognorm(s=d.sigma, scale=math.exp(d.mu))
    capped, _ = integrate.quad(lambda v: min(v, d.limit) * lognormal.pdf(v), 0, np.inf)
    v1 = simulator.new_mean_speed("conventional", compliance=1.0)
    # The measured mean minus the excess equals the mean of min(v, limit) up to the small gap
    # between the measured and the fitted mean.
    assert v1 == pytest.approx(d.mean - (d.implied_mean - capped), abs=1e-6)
    assert v1 < d.limit


def test_the_power_model_moves_outcomes_in_the_right_order() -> None:
    nothing = simulator.site_effects(simulator.PRESETS[0])
    ratio_columns = [
        c for c in nothing.columns if c.endswith(("_ratio", "_ratio_low", "_ratio_high"))
    ]
    assert np.allclose(nothing[ratio_columns].to_numpy(dtype=float), 1.0)
    slower = simulator.site_effects(simulator.Scenario("t", "t", {"conventional": 80})).set_index(
        "site"
    )
    row = slower.loc["conventional"]
    assert row.new_mean_speed < row.mean_speed
    assert row.deaths_ratio < row.seriously_injured_ratio < row.slightly_injured_ratio < 1
    assert row.deaths_ratio_low <= row.deaths_ratio <= row.deaths_ratio_high
    faster = simulator.site_effects(simulator.Scenario("t", "t", {"motorway": 130})).set_index(
        "site"
    )
    assert faster.loc["motorway", "deaths_ratio"] > 1
    # A set response of the full limit change moves the mean by exactly the change.
    full = simulator.new_mean_speed("motorway", 110, response_share=1.0)
    assert full == pytest.approx(simulator.speed_distribution("motorway").mean - 10)


@pytest.mark.skipif(
    not (PROCESSED_DATA_DIR / "accidentes.parquet").exists(),
    reason="run `python scripts/build_tables.py` first",
)
def test_a_total_range_uses_one_exponent_end_on_every_road() -> None:
    # Motorway deaths rise and conventional deaths fall: the total's ends are the sums at the low
    # and at the high exponent, which lie inside the sum of each road's own sorted ends.
    mixed = simulator.Scenario("m", "m", {"motorway": 130, "conventional": 80})
    effects = simulator.interurban_effects(mixed).set_index("road_class")
    assert (
        effects.loc["motorway", "deaths_change"] > 0 > effects.loc["conventional", "deaths_change"]
    )
    total = simulator.totals(effects)
    at_ends = sorted(
        [
            effects.deaths_change_at_low_exponent.sum(),
            effects.deaths_change_at_high_exponent.sum(),
        ]
    )
    assert [total.deaths_change_low, total.deaths_change_high] == pytest.approx(at_ends)
    assert total.deaths_change_low >= effects.deaths_change_low.sum()
    assert total.deaths_change_high <= effects.deaths_change_high.sum()


processed = pytest.mark.skipif(
    not (PROCESSED_DATA_DIR / "accidentes.parquet").exists(),
    reason="run `python scripts/build_tables.py` first",
)


@processed
def test_the_baseline_reconciles_with_the_yearbook() -> None:
    from dgt_stats import io_tables

    base = simulator.baseline()
    annual = io_tables.read_table("series_annual")
    annual = annual[(annual.zone == "all") & annual.year.isin(simulator.BASELINE_YEARS)]
    yearbook = annual.pivot_table(index="year", columns="metric", values="value").mean()
    assert base.deaths.sum() == pytest.approx(yearbook["deaths_30d"])
    assert base.seriously_injured.sum() == pytest.approx(yearbook["hospitalised_30d"])
    assert base.injury_crashes.sum() == pytest.approx(yearbook["crashes"])


@processed
def test_conventional_roads_carry_the_most_risk_per_kilometre() -> None:
    risk = simulator.class_risk().pivot(
        index="year", columns="road_class", values="deaths_per_bn_km"
    )
    assert ((risk.conventional / risk.motorway) > 2.5).all()


def _browser_parameters() -> dict:
    names = ("simulator_baseline", "simulator_speed_sites", "forecast_detectability")
    tables = {name: pd.read_csv(TABLES_DIR / f"{name}.csv") for name in names}
    return simulator.browser_parameters(tables)


tables = pytest.mark.skipif(
    not (TABLES_DIR / "simulator_baseline.csv").exists(),
    reason="run `python scripts/analyse.py tables` first",
)


@processed
@tables
@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_browser_computes_exactly_what_the_python_computes(tmp_path: Path) -> None:
    parameters = _browser_parameters()
    scenarios = [*simulator.PRESETS]
    scenarios += [
        simulator.Scenario("a", "a", {"motorway": 100, "conventional": 70}, 0.4, 0.3),
        simulator.Scenario("b", "b", {"motorway": 140, "urban_50": 40}, None, 0.8),
        simulator.Scenario("c", "c", {"conventional": 100}, 1.0, 0.0),
    ]
    payload = [
        {"limits": s.limits, "responseShare": s.response_share, "compliance": s.compliance}
        for s in scenarios
    ]
    (tmp_path / "p.json").write_text(json.dumps(parameters))
    (tmp_path / "s.json").write_text(json.dumps(payload))
    script = (
        f"const S = require({json.dumps(str(JS))});"
        f"const P = require({json.dumps(str(tmp_path / 'p.json'))});"
        f"const scenarios = require({json.dumps(str(tmp_path / 's.json'))});"
        "console.log(JSON.stringify(scenarios.map((s) => S.simulate(P, s))));"
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    browser = json.loads(result.stdout)
    columns = [
        "new_mean_speed",
        "deaths_change",
        "deaths_change_low",
        "deaths_change_high",
        "seriously_injured_change",
        "slightly_injured_change",
        "injury_crashes_change",
        "value_euros",
        "value_euros_low",
        "value_euros_high",
        "vehicle_hours_change",
    ]
    for scenario, computed in zip(scenarios, browser):
        python = simulator.interurban_effects(scenario).set_index("road_class")
        for row in computed["interurban"]:
            for column in columns:
                assert row[column] == pytest.approx(
                    float(python.loc[row["road_class"], column]), rel=1e-6, abs=1e-6
                ), (scenario.key, row["road_class"], column)
        urban = simulator.urban_effects(scenario).set_index("site")
        for row in computed["urban"]:
            for column in ("new_mean_speed", "deaths_change", "seriously_injured_change"):
                assert row[column] == pytest.approx(
                    float(urban.loc[row["site"], column]), rel=1e-6, abs=1e-9
                ), (scenario.key, row["site"], column)
        total = simulator.totals(simulator.interurban_effects(scenario))
        for column in (
            "deaths_change",
            "deaths_change_low",
            "deaths_change_high",
            "value_euros_low",
        ):
            assert computed["total"][column] == pytest.approx(
                float(total[column]), rel=1e-6, abs=1e-6
            ), (scenario.key, "total", column)
        presets = {p.key for p in simulator.PRESETS}
        if scenario.key in presets:
            published = pd.read_csv(TABLES_DIR / "simulator_presets.csv").set_index("scenario")
            total = computed["total"]
            assert total["deaths_change"] == pytest.approx(
                float(published.loc[scenario.key, "deaths_change"]), rel=1e-6, abs=1e-6
            )
            assert total["visible_in_one_year"] == bool(
                published.loc[scenario.key, "visible_in_one_year"]
            )
