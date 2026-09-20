import numpy as np
import pandas as pd
import pytest

from dgt_stats import features, models


def _synthetic(n: int = 40_000, seed: int = 7) -> pd.DataFrame:
    """Two predictors with known effects: level b doubles the odds, level c halves them.

    Seeded per call, so a test's data do not depend on which tests ran before it.
    """
    rng = np.random.default_rng(seed)
    x1 = rng.choice(["a", "b", "c"], size=n, p=[0.5, 0.3, 0.2])
    x2 = rng.choice(["p", "q"], size=n)
    log_odds = -2.5 + np.log(2) * (x1 == "b") + np.log(0.5) * (x1 == "c") + 0.4 * (x2 == "q")
    y = rng.random(n) < 1 / (1 + np.exp(-log_odds))
    return pd.DataFrame(
        {
            "crash_year": rng.choice([2016, 2017, 2023, 2024], size=n),
            "province": rng.choice([str(i) for i in range(1, 11)], size=n),
            "fatal": y,
            "serious": y,
            "x1": pd.Categorical(x1, categories=["a", "b", "c"], ordered=True),
            "x2": pd.Categorical(x2, categories=["p", "q"], ordered=True),
        }
    )


def test_fit_recovers_known_odds_ratios() -> None:
    frame = _synthetic()
    fit = models.fit_severity(frame, "fatal", ("x1", "x2"))
    table = models.odds_ratios(fit).set_index("level")
    assert table.loc["b", "odds_ratio"] == pytest.approx(2.0, rel=0.15)
    assert table.loc["c", "odds_ratio"] == pytest.approx(0.5, rel=0.2)
    assert (table.or_low < table.odds_ratio).all() and (table.odds_ratio < table.or_high).all()
    assert fit.events == int(frame.fatal.sum())


def test_coefficient_table_marginal_effects_and_predictions() -> None:
    frame = _synthetic(20_000)
    fit = models.fit_severity(frame, "fatal", ("x1", "x2"), cluster=None)
    table = models.coefficient_table(frame, fit)
    assert table.is_reference.sum() == 2 and len(table) == 5
    assert table.crashes.sum() == 2 * len(frame)
    effects = models.marginal_effects(frame, fit)
    b = effects[(effects.predictor == "x1") & (effects.level == "b")].iloc[0]
    assert b.effect > 0 and abs(b.effect) < 0.2
    design = models.design_matrix(frame, ("x1", "x2"))
    assert list(design.columns) == ["intercept", "x1=b", "x1=c", "x2=q"]
    probabilities = models.predict(fit, design)
    assert probabilities.mean() == pytest.approx(frame.fatal.mean(), abs=0.005)


def test_holdout_and_stability_on_synthetic_years(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _synthetic(30_000)
    monkeypatch.setattr(
        features,
        "PREDICTORS",
        {"x1": {"source": "x1"}, "x2": {"source": "x2"}, "year": {"source": "crash_year"}},
    )
    monkeypatch.setattr(features, "PREDICTOR_LABELS", {"x1": "X1", "x2": "X2", "year": "Year"})
    calibration, summary = models.holdout_check(frame, "fatal", (2023, 2024))
    assert calibration.crashes.sum() == (frame.crash_year >= 2023).sum()
    assert 0.5 < summary.auc.iloc[0] < 1.0
    assert summary.brier.iloc[0] <= summary.brier_base_rate.iloc[0] + 1e-6
    full = models.fit_severity(frame, "fatal", ("x1", "x2"), cluster=None)
    stability = models.year_stability(frame, full, terms=3)
    assert set(stability.year.unique()) == {2016, 2017, 2023, 2024}
    assert stability.within_full_interval.mean() > 0.5


def test_model_frame_levels_and_groupings() -> None:
    raw = pd.DataFrame(
        {
            "ANYO": [2019, 2020, 2024],
            "COD_PROVINCIA": [28, 8, 46],
            "fatal": [False, True, False],
            "serious": [True, True, False],
            "ZONA": [3, 1, 999],
            "road_group": ["urban_street", "conventional", pd.NA],
            "TIPO_ACCIDENTE": [2, 13, 7],
            "NUDO": [2, 1, pd.NA],
            "CONDICION_ILUMINACION": [1, 6, 999],
            "CONDICION_METEO": [1, 4, 7],
            "CONDICION_FIRME": [1, 3, 9],
            "TRAZADO_PLANTA": [998, 2, 4],
            "hour_band": ["10-13", "00-06", "20-23"],
            "weekend": [False, True, False],
            "TOTAL_VEHICULOS": [2, 1, 5],
        }
    )
    frame = features.model_frame(raw)
    assert list(frame.zone) == ["street", "interurban road", "not specified"]
    assert list(frame.road) == ["urban street", "conventional", "not specified"]
    assert list(frame.crash_type) == ["side collision", "run-off or overturn", "pedestrian struck"]
    assert list(frame.junction) == ["not at a junction", "at a junction", "not specified"]
    assert list(frame.lighting) == ["daylight", "dark, no lighting", "not specified"]
    # Each field's explicit unknown code (7, 9, 4) is a level of its own, apart from 999.
    assert list(frame.weather) == ["clear", "rain", "unknown"]
    assert list(frame.surface) == ["dry", "wet", "unknown"]
    assert list(frame.alignment) == ["straight", "curve", "unknown"]  # 998 folds to reference
    assert list(frame.vehicles) == ["2 vehicles", "1 vehicle", "3 or more vehicles"]
    assert list(frame.year) == ["2019", "2020", "2024"]
    assert frame.year.cat.categories[0] == "2019"
    groupings = features.grouping_table()
    assert groupings.groupby("predictor").reference.any().all()
    crash_type = groupings[groupings.predictor == "Crash type"]
    assert len(crash_type) == 23  # 20 dictionary codes, 999, 998 and the fallback row
    assert set(crash_type.code.tail(3)) == {"999", "998", "any other value or empty"}
    merged = features.grouping_table(frame)
    assert merged.columns.tolist() == groupings.columns.tolist()


def test_every_predictor_level_list_starts_with_its_reference() -> None:
    for name, spec in features.PREDICTORS.items():
        first = list(spec["levels"])[0]
        assert first in set(spec["map"].values()), name
        assert features.levels(name)[0] == first


def test_small_levels_merge_into_the_reference() -> None:
    n = 2_000
    raw = pd.DataFrame(
        {
            "ANYO": [2019] * n,
            "COD_PROVINCIA": [28] * n,
            "fatal": [False] * n,
            "serious": [False] * n,
            "ZONA": [3] * n,
            "road_group": ["urban_street"] * n,
            "TIPO_ACCIDENTE": [2] * (n - 10) + [999] * 10,
            "NUDO": [2] * n,
            "CONDICION_ILUMINACION": [1] * n,
            "CONDICION_METEO": [1] * n,
            "CONDICION_FIRME": [1] * n,
            "TRAZADO_PLANTA": [998] * n,
            "hour_band": ["10-13"] * n,
            "weekend": [False] * n,
            "TOTAL_VEHICULOS": [2] * n,
        }
    )
    frame = features.model_frame(raw)
    assert list(frame.crash_type.cat.categories) == ["side collision"]
    assert list(frame.alignment.cat.categories) == ["straight"]
    assert frame.attrs["merged_levels"] == {"crash_type": {"not specified": 10}}
    groupings = features.grouping_table(frame).set_index(["predictor", "code"])
    merged = groupings.loc[("Crash type", "999")]
    assert (
        merged.level == "side collision (merged: 10 crashes, fewer than 500)" and merged.reference
    )
    absent = groupings.loc[("Crash type", "1")]
    assert absent.level == "head-on collision (no crash takes this value)" and not absent.reference
    assert groupings.loc[("Crash type", "2")].level == "side collision"


def test_profiles_and_predicted_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _synthetic()
    fit = models.fit_severity(frame, "fatal", ("x1", "x2"))
    monkeypatch.setattr(models, "PROFILES", {"ref": {}, "b": {"x1": "b"}})
    out = models.profiles(frame, {"fatal": fit})
    reference = 1 / (1 + np.exp(-fit.params["intercept"]))
    assert out.set_index("profile").fatal["ref"] == pytest.approx(reference, rel=1e-6)
    assert out.fatal.between(0, 1).all()
    grid = models.predicted_grid(frame, fit, rows="x1", columns="x2")
    assert len(grid) == 3 * 2 and grid.probability.between(0, 1).all()


def _road_frame(n: int = 20_000) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    road = rng.choice(["urban street", "conventional", "motorway"], size=n)
    zone = rng.choice(["urban street", "interurban road"], size=n)
    lighting = rng.choice(["daylight", "dark, no lighting"], size=n)
    log_odds = -2.5 + 0.5 * (road == "conventional") + 0.3 * (lighting == "dark, no lighting")
    y = rng.random(n) < 1 / (1 + np.exp(-log_odds))
    return pd.DataFrame(
        {
            "province": rng.choice([str(i) for i in range(1, 11)], size=n),
            "fatal": y,
            "road": pd.Categorical(
                road, categories=["urban street", "conventional", "motorway"], ordered=True
            ),
            "zone": pd.Categorical(
                zone, categories=["urban street", "interurban road"], ordered=True
            ),
            "lighting": pd.Categorical(
                lighting, categories=["daylight", "dark, no lighting"], ordered=True
            ),
        }
    )


def test_predicted_grid_pins_zone_to_the_road_type() -> None:
    frame = _road_frame()
    fit = models.fit_severity(frame, "fatal", ("road", "zone", "lighting"), cluster=None)
    grid = models.predicted_grid(frame, fit)
    assert len(grid) == 3 * 2 and grid.probability.between(0, 1).all()
    got = grid.set_index(["road", "lighting"]).probability
    coupled = models._profile_design(
        frame, fit, {"road": "motorway", "lighting": "daylight", "zone": "interurban road"}
    )
    assert got[("motorway", "daylight")] == pytest.approx(float(models.predict(fit, coupled)[0]))
    urban = models._profile_design(frame, fit, {"road": "urban street", "lighting": "daylight"})
    assert got[("urban street", "daylight")] == pytest.approx(float(models.predict(fit, urban)[0]))
    with pytest.raises(ValueError):
        models._profile_design(frame, fit, {"road": "no such road"})
