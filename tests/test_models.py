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
    assert not table.is_nuisance.any()  # no level here stands for a missing value
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
    assert summary.brier.iloc[0] <= summary.brier_train_rate.iloc[0] + 1e-6
    assert summary.brier_skill.iloc[0] == pytest.approx(
        1 - summary.brier.iloc[0] / summary.brier_train_rate.iloc[0]
    )
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
            "TIPO_VIA": [9, 5, 999],
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
    # Code 5, a conventional road with two carriageways, is a conventional road: DGT recoded most
    # of its crashes as code 6 in 2021, and one level keeps that recoding inside it.
    assert list(frame.road) == ["urban street", "conventional", "not specified"]
    assert features.PREDICTORS["road"]["map"][5] == features.PREDICTORS["road"]["map"][6]
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
    assert set(crash_type.code.tail(3)) == {"999", "998", features.FALLBACK_CODE}
    # A count and the year are not coded fields, so they carry no 999 or 998 row.
    vehicles = groupings[groupings.predictor == "Vehicles involved"]
    assert list(vehicles.code) == ["0", "1", "2", features.FALLBACK_CODE]
    assert list(groupings[groupings.predictor == "Year"].code) == [
        *(str(year) for year in range(2016, 2025)),
        features.FALLBACK_CODE,
    ]
    merged = features.grouping_table(frame)
    assert merged.columns.tolist() == groupings.columns.tolist()


def test_a_repeated_column_is_dropped_and_reported() -> None:
    """Two levels that mark the same crashes make the design singular; the later one is dropped."""
    frame = _synthetic(5_000)
    frame = frame.assign(
        x3=pd.Categorical(
            np.where(frame.x1 == "c", "same", "base"), categories=["base", "same"], ordered=True
        )
    )
    fit = models.fit_severity(frame, "fatal", ("x1", "x3"), cluster=None)
    assert fit.aliased == ["x3=same"]
    assert "x3=same" not in fit.params.index
    table = models.coefficient_table(frame, fit)
    left_out = table[table.level == "same"].iloc[0]
    assert np.isnan(left_out.odds_ratio) and np.isnan(left_out.or_low)
    effects = models.marginal_effects(frame, fit).set_index(["predictor", "level"])
    # A level the fit left out carries NaN in the marginal effects, not a zero effect.
    assert np.isnan(effects.loc[("x3", "same"), "effect"])
    assert models.odds_ratios(fit).set_index("level").loc["c", "odds_ratio"] == pytest.approx(
        0.5, rel=0.3
    )


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
            "TIPO_VIA": [9] * n,
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
        merged.level
        == "side collision (merged: the not specified level's 10 crashes, fewer than 500)"
        and merged.reference
    )
    # No crash reaches the fallback row, so it says so instead of repeating the merged count.
    fallback = groupings.loc[("Crash type", features.FALLBACK_CODE)]
    assert fallback.level == (
        "side collision (the not specified level was merged; no crash takes this code)"
    )
    absent = groupings.loc[("Crash type", "1")]
    assert absent.level == "head-on collision (no crash takes this value)" and not absent.reference
    assert groupings.loc[("Crash type", "2")].level == "side collision"


def test_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _synthetic()
    fit = models.fit_severity(frame, "fatal", ("x1", "x2"))
    monkeypatch.setattr(models, "PROFILES", {"ref": {}, "b": {"x1": "b"}})
    out = models.profiles(frame, {"fatal": fit})
    reference = 1 / (1 + np.exp(-fit.params["intercept"]))
    assert out.set_index("profile").fatal["ref"] == pytest.approx(reference, rel=1e-6)
    assert out.fatal.between(0, 1).all()


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


def test_a_profile_is_a_valid_design_and_rejects_unknown_levels() -> None:
    frame = _road_frame()
    fit = models.fit_severity(frame, "fatal", ("road", "zone", "lighting"), cluster=None)
    motorway = models._profile_design(
        frame, fit, {"road": "motorway", "lighting": "daylight", "zone": "interurban road"}
    )
    urban = models._profile_design(frame, fit, {"road": "urban street", "lighting": "daylight"})
    for design in (motorway, urban):
        assert 0 < float(models.predict(fit, design)[0]) < 1
    with pytest.raises(ValueError):
        models._profile_design(frame, fit, {"road": "no such road"})


def _adverse_frame(n: int = 60_000, seed: int = 11) -> pd.DataFrame:
    """Weather and surface that partly measure the same thing, with a known joint effect.

    Rain drives the surface wet nine times in ten, and only the *wet conditions* state lowers the
    odds. A model carrying both predictors has to split one effect; dropping either must recover
    it. That is the sensitivity the severity page reports, so it is tested on data whose answer
    is known.
    """
    rng = np.random.default_rng(seed)
    rain = rng.random(n) < 0.15
    wet = rain & (rng.random(n) < 0.9) | (~rain & (rng.random(n) < 0.02))
    zone = rng.choice(["street", "interurban road"], size=n)
    log_odds = -3.0 + np.log(0.5) * wet + 0.5 * (zone == "interurban road")
    y = rng.random(n) < 1 / (1 + np.exp(-log_odds))
    return pd.DataFrame(
        {
            "crash_year": rng.choice([2016, 2024], size=n),
            "province": rng.choice([str(i) for i in range(1, 11)], size=n),
            "fatal": y,
            "serious": y,
            "weather": pd.Categorical(
                np.where(rain, "rain", "clear"), categories=["clear", "rain"], ordered=True
            ),
            "surface": pd.Categorical(
                np.where(wet, "wet", "dry"), categories=["dry", "wet"], ordered=True
            ),
            "zone": pd.Categorical(zone, categories=["street", "interurban road"], ordered=True),
        }
    )


def test_adverse_conditions_separates_two_collinear_predictors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = _adverse_frame()
    monkeypatch.setattr(
        features, "PREDICTORS", {"weather": {}, "surface": {}, "zone": {}}, raising=False
    )
    monkeypatch.setattr(
        features,
        "PREDICTOR_LABELS",
        {"weather": "Weather", "surface": "Road surface", "zone": "Zone"},
        raising=False,
    )
    monkeypatch.setattr(
        models,
        "ADVERSE_LEVELS",
        (("weather", "rain"), ("surface", "wet")),
        raising=False,
    )
    monkeypatch.setattr(
        models,
        "ADVERSE_VARIANTS",
        {
            "full": {"label": "Full model", "drop": (), "subset": None},
            "no_surface": {"label": "Without road surface", "drop": ("surface",), "subset": None},
            "no_weather": {"label": "Without weather", "drop": ("weather",), "subset": None},
            "interurban": {
                "label": "Interurban roads only",
                "drop": ("zone",),
                "subset": ("zone", "interurban road"),
            },
        },
        raising=False,
    )
    out = models.adverse_conditions(frame, "fatal").set_index(["variant", "level"])
    # With both predictors in, the rain coefficient is pulled towards no effect, because the
    # surface column is carrying what rain does; on its own rain recovers the true effect.
    assert out.loc[("full", "rain"), "odds_ratio"] > out.loc[("no_surface", "rain"), "odds_ratio"]
    # Dropping either predictor recovers roughly the whole 0.5.
    assert out.loc[("no_weather", "wet"), "odds_ratio"] == pytest.approx(0.5, abs=0.08)
    assert out.loc[("no_surface", "rain"), "odds_ratio"] == pytest.approx(0.5, abs=0.08)
    # A level a variant does not contain is absent rather than silently reported.
    assert ("no_weather", "rain") not in out.index
    assert ("no_surface", "wet") not in out.index
    # A stratified fit uses only its own rows.
    assert out.loc[("interurban", "wet"), "n_crashes"] < len(frame)


def test_level_composition_and_exclusions_describe_where_a_level_is() -> None:
    frame = _adverse_frame()
    frame["road"] = frame.zone  # the composition helper looks at province, zone and road
    frame.loc[frame.index[:1_000], "province"] = "99"
    composition = models.level_composition(frame, "surface", "wet", top=3)
    assert set(composition.dimension) == {"province", "zone", "road"}
    assert composition.share_of_level.between(0, 1).all()
    assert composition.attrs["n_level"] == int((frame.surface == "wet").sum())


def test_missing_state_levels_are_flagged_as_nuisance() -> None:
    for level in features.MISSING_LEVELS:
        assert features.is_nuisance(level)
    assert not features.is_nuisance("wet") and not features.is_nuisance("curve")
    frame = _synthetic(20_000)
    frame["x2"] = pd.Categorical(
        np.where(frame.x2 == "q", features.UNKNOWN, "p"),
        categories=["p", features.UNKNOWN],
        ordered=True,
    )
    fit = models.fit_severity(frame, "fatal", ("x1", "x2"), cluster=None)
    table = models.coefficient_table(frame, fit).set_index("level")
    assert bool(table.loc[features.UNKNOWN, "is_nuisance"]) and not table.loc["b", "is_nuisance"]
    effects = models.marginal_effects(frame, fit).set_index("level")
    assert bool(effects.loc[features.UNKNOWN, "is_nuisance"])


def test_holdout_merges_are_decided_on_the_training_years() -> None:
    frame = _synthetic(6_000)
    # Level "c" of x1 is common in the held-out years and rare in the training years: merged into
    # the reference on the training counts alone, in both parts.
    late = frame.crash_year >= 2023
    values = frame.x1.astype(str).to_numpy()
    values = np.where(~late & (values == "c") & (frame.index >= 100), "a", values)
    frame["x1"] = pd.Categorical(values, categories=["a", "b", "c"], ordered=True)
    train, test = frame[~late], frame[late]
    assert (train.x1 == "c").sum() < features.MIN_LEVEL_CRASHES <= (test.x1 == "c").sum()
    new_train, new_test, merged = models._merge_small_levels(train, test, ("x1", "x2"))
    assert merged == {"x1": ["c"]}
    assert list(new_test.x1.cat.categories) == ["a", "b"]
    assert (new_test.x1 == "a").sum() == (test.x1.isin(["a", "c"])).sum()
    assert len(new_train) == len(train) and len(new_test) == len(test)


def test_recording_regime_and_the_refit_without_some_provinces() -> None:
    frame = _synthetic(30_000)
    inside = frame.province.isin(["1", "2"])
    rng = np.random.default_rng(5)
    unknown = inside & (rng.random(len(frame)) < 0.4)
    frame["x2"] = pd.Categorical(
        np.where(unknown, features.UNKNOWN, frame.x2.astype(str)),
        categories=["p", "q", features.UNKNOWN],
        ordered=True,
    )
    regime = models.recording_regime(frame, ("1", "2"), ("x1", "x2")).set_index("level")
    row = regime.loc[features.UNKNOWN]
    assert row.crashes == int(unknown.sum()) and row.catalan_share_of_level == 1.0
    assert row.share_of_catalan_crashes == pytest.approx(unknown.sum() / inside.sum())
    assert row.share_of_other_crashes == 0
    fit = models.fit_severity(frame, "fatal", ("x1", "x2"))
    out = models.regime_sensitivity(frame, {"fatal": fit}, provinces=("1", "2"))
    out = out.set_index(["predictor", "level"])
    assert int(out.n_without.iloc[0]) == int((~inside).sum())
    # The level that exists only inside the dropped provinces cannot be refitted.
    assert np.isnan(out.loc[("x2", features.UNKNOWN), "odds_ratio_without"])
    assert bool(out.loc[("x2", features.UNKNOWN), "is_nuisance"])
    # The true effect of level b is the same everywhere, so it survives the refit.
    assert bool(out.loc[("x1", "b"), "within_full_interval"])
