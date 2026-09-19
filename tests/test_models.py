import numpy as np
import pandas as pd
import pytest

from dgt_stats import features, models

RNG = np.random.default_rng(7)


def _synthetic(n: int = 40_000) -> pd.DataFrame:
    """Two predictors with known effects: level b doubles the odds, level c halves them."""
    x1 = RNG.choice(["a", "b", "c"], size=n, p=[0.5, 0.3, 0.2])
    x2 = RNG.choice(["p", "q"], size=n)
    log_odds = -2.5 + np.log(2) * (x1 == "b") + np.log(0.5) * (x1 == "c") + 0.4 * (x2 == "q")
    y = RNG.random(n) < 1 / (1 + np.exp(-log_odds))
    return pd.DataFrame(
        {
            "year": RNG.choice([2016, 2017, 2023, 2024], size=n),
            "province": RNG.choice([str(i) for i in range(1, 11)], size=n),
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
        {"x1": {"source": "x1"}, "x2": {"source": "x2"}, "year": {"source": "year"}},
    )
    monkeypatch.setattr(features, "PREDICTOR_LABELS", {"x1": "X1", "x2": "X2", "year": "Year"})
    calibration, summary = models.holdout_check(frame, "fatal", (2023, 2024))
    assert calibration.crashes.sum() == (frame.year >= 2023).sum()
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
    assert list(frame.weather) == ["clear", "rain", "not specified"]
    assert list(frame.surface) == ["dry", "wet", "not specified"]
    assert list(frame.alignment) == ["not applicable", "curve", "not specified"]
    assert list(frame.vehicles) == ["2 vehicles", "1 vehicle", "3 or more vehicles"]
    assert list(frame.year) == ["2019", "2020", "2024"]
    assert frame.year.cat.categories[0] == "2019"
    groupings = features.grouping_table()
    assert groupings.groupby("predictor").reference.any().all()
    codes_by_predictor = groupings.groupby("predictor").code.count()
    assert codes_by_predictor["Crash type"] == 20


def test_every_predictor_level_list_starts_with_its_reference() -> None:
    for name, spec in features.PREDICTORS.items():
        first = list(spec["levels"])[0]
        assert first in set(spec["map"].values()), name
        assert features.levels(name)[0] == first
