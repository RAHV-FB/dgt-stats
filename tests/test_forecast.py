import numpy as np
import pandas as pd
import pytest
from scipy import stats

from dgt_stats import forecast, io_tables
from dgt_stats.paths import CORES_FUEL_PATH


def _synthetic_panel(elasticity: float, saturday: float, seed: int = 5) -> pd.DataFrame:
    """Twelve years of monthly deaths built from known month, trend, traffic and Saturday effects."""
    rng = np.random.default_rng(seed)
    rows = []
    for year in range(2008, 2020):
        for month in range(1, 13):
            rows.append({"year": year, "month": month})
    panel = pd.DataFrame(rows)
    panel["t"] = panel.year + (panel.month - 0.5) / 12
    season = 1 + 0.25 * np.sin((panel.month - 4) / 12 * 2 * np.pi)
    traffic = 2e6 * season * rng.lognormal(0, 0.25, len(panel))
    panel["log_fuel"] = np.log(traffic)
    for column, weekday in (("fridays", 4), ("saturdays", 5), ("sundays", 6)):
        panel[column] = [
            forecast._weekday_count(y, m, weekday) for y, m in zip(panel.year, panel.month)
        ]
    log_mu = (
        np.log(150)
        + 0.15 * np.cos(panel.month)
        - 0.02 * (panel.t - 2008)
        + elasticity * (panel.log_fuel - np.log(2e6))
        + np.log(saturday) * (panel.saturdays - 4)
    )
    panel["deaths_all"] = rng.poisson(np.exp(log_mu)).astype(float)
    return panel


def test_the_model_recovers_a_known_traffic_elasticity_and_weekday_effect() -> None:
    panel = _synthetic_panel(elasticity=1.0, saturday=1.10)
    result = forecast.fit(panel, "deaths_all")
    assert result.params["log_fuel"] == pytest.approx(1.0, abs=0.15)
    assert np.exp(result.params["saturdays"]) == pytest.approx(1.10, abs=0.04)
    low, high = result.conf_int().loc["log_fuel"]
    assert low < 1.0 < high


def test_the_model_forecast_follows_traffic_where_last_year_cannot() -> None:
    # A year whose traffic falls by a third: the model, given that year's traffic, predicts the
    # fall; the same months of last year cannot.
    panel = _synthetic_panel(elasticity=1.0, saturday=1.0, seed=9)
    shock = panel.year == 2019
    panel.loc[shock, "log_fuel"] += np.log(2 / 3)
    rng = np.random.default_rng(1)
    panel.loc[shock, "deaths_all"] = rng.poisson(panel.loc[shock, "deaths_all"] * 2 / 3)
    observed = panel.loc[shock, "deaths_all"].sum()
    model = forecast.predict_year(panel, "deaths_all", 2019, forecast.CHOSEN).sum()
    naive = forecast.predict_year(panel, "deaths_all", 2019, "last_year").sum()
    assert abs(np.log(observed / model)) < 0.06
    assert np.log(observed / naive) < -0.25


def test_detection_power_counts_only_the_right_direction_and_is_the_power_at_the_mde() -> None:
    tau, expected = 0.05, 1200.0
    fall = forecast.minimum_detectable_effect(expected, tau) * expected
    rise = forecast.minimum_detectable_rise(expected, tau) * expected
    # With nothing to find, a two-sided test flags a change in a given direction half its size.
    assert forecast.detection_power(0.0, expected, tau) == pytest.approx(forecast.ALPHA / 2)
    assert forecast.detection_power(-fall, expected, tau) == pytest.approx(forecast.POWER)
    assert forecast.detection_power(rise, expected, tau) == pytest.approx(forecast.POWER)
    # On the log scale a rise has to be larger than a fall to be seen as often.
    assert rise > fall
    powers = [forecast.detection_power(-change, expected, tau) for change in (50, 100, 200, 400)]
    assert powers == sorted(powers)


def test_minimum_detectable_effect_is_the_power_formula() -> None:
    z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)
    assert forecast.minimum_detectable_effect(1e12, 0.05) == pytest.approx(1 - np.exp(-z * 0.05))
    assert forecast.minimum_detectable_effect(400, 0.0) == pytest.approx(1 - np.exp(-z / 20))
    # More deaths to count, or a steadier counterfactual, both make smaller effects visible.
    assert forecast.minimum_detectable_effect(2000, 0.05) < forecast.minimum_detectable_effect(
        500, 0.05
    )
    assert forecast.minimum_detectable_effect(2000, 0.03) < forecast.minimum_detectable_effect(
        2000, 0.06
    )


data = pytest.mark.skipif(
    not (io_tables.staging_path("series_monthly").exists() and CORES_FUEL_PATH.exists()),
    reason="run `python scripts/ingest.py tables` first",
)


@data
def test_model_panel_is_complete_monthly_and_adds_up() -> None:
    panel = forecast.model_panel()
    assert panel.year.min() == 1996 and panel.month.iloc[0] == 1
    assert len(panel) == 12 * panel.year.nunique()
    assert (panel.deaths_interurban + panel.deaths_urban == panel.deaths_all).all()
    assert panel[["fridays", "saturdays", "sundays"]].isin([4, 5]).all().all()


@data
def test_the_published_choice_is_the_one_the_selection_years_make() -> None:
    selection = forecast.model_selection()
    chosen = selection[selection.chosen]
    model = chosen[chosen.family == "model"]
    assert set(model.method) == {forecast.CHOSEN}
    assert set(model.window) == {forecast.WINDOW_YEARS}
    # The trees were tuned on the same years: every leaf size was scored, and the published one
    # is the best of them there.
    trees = selection[selection.family == "trees"]
    leaves = {f"boosted_trees_leaf_{leaf}" for leaf in forecast.TREE_LEAF_CANDIDATES}
    assert set(trees.method) == leaves
    assert set(chosen[chosen.family == "trees"].method) == {forecast.TREE_METHOD}
    assert set(chosen.family) == {"model", "trees"}
    # The selection and holdout years do not overlap, and the lockdown years are in neither.
    sets = selection.groupby("set").years.max()
    assert sets["selection"] == len(forecast.SELECTION_YEARS)
    assert sets["holdout"] == len(forecast.HOLDOUT_YEARS)


@data
def test_the_model_beats_last_year_when_the_trend_or_traffic_moves() -> None:
    table = forecast.validation().set_index(["outcome", "set", "method"])
    for kind in ("selection", "pandemic"):
        model = table.loc[("deaths_all", kind, forecast.CHOSEN), "rmse"]
        naive = table.loc[("deaths_all", kind, "last_year"), "rmse"]
        assert model < naive / 2
    # In the flat years since 2016 last year's count does slightly better: the page says so, and
    # this holds it.
    model = table.loc[("deaths_all", "holdout", forecast.CHOSEN), "rmse"]
    naive = table.loc[("deaths_all", "holdout", "last_year"), "rmse"]
    assert naive < model < naive + 0.02
    # The tuned trees do worse than the model on every kind of road and in every set of years.
    for outcome in forecast.OUTCOMES:
        for kind in ("selection", "holdout", "pandemic"):
            model = table.loc[(outcome, kind, forecast.CHOSEN), "rmse"]
            assert table.loc[(outcome, kind, forecast.TREE_METHOD), "rmse"] > model


@data
def test_waiting_longer_makes_a_law_harder_to_see() -> None:
    horizons = forecast.detectability()
    for _, group in horizons.groupby("outcome"):
        assert group.sort_values("horizon").mde.is_monotonic_increasing
    one_year = horizons[horizons.horizon == 1].set_index("outcome").mde
    assert 0.08 < one_year["deaths_all"] < 0.25
    assert one_year["deaths_urban"] > one_year["deaths_interurban"]
