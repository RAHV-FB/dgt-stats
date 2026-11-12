import numpy as np
import pandas as pd
import pytest

from dgt_stats import io_tables, seasonality
from dgt_stats.paths import CORES_FUEL_PATH, TOLL_TRAFFIC_PATH

pytestmark = pytest.mark.skipif(
    not (
        io_tables.staging_path("series_monthly").exists()
        and CORES_FUEL_PATH.exists()
        and TOLL_TRAFFIC_PATH.exists()
    ),
    reason="run `python scripts/ingest.py tables` first",
)


def test_monthly_panel_lines_up_deaths_and_traffic() -> None:
    panel = seasonality.monthly_panel()
    recent = panel[panel.year.isin(seasonality.PROFILE_YEARS)]
    assert len(recent) == 12 * len(seasonality.PROFILE_YEARS)
    columns = ["deaths_all", *seasonality.TRAFFIC_SERIES]
    assert recent[columns].notna().all().all()
    # Zones add up to the national series.
    assert (recent.deaths_interurban + recent.deaths_urban == recent.deaths_all).all()


def test_seasonal_indices_average_to_one_hundred() -> None:
    profile = seasonality.seasonal_profile()
    for column in ["deaths_all", *seasonality.TRAFFIC_SERIES]:
        assert profile[column].mean() == pytest.approx(100.0, abs=1e-9)
    # Deaths are divided only by the series whose scope matches them: road fuel.
    assert [c for c in profile.columns if c.startswith("deaths_per_")] == [
        "deaths_per_road_fuel_tonnes"
    ]
    # The raw summer peak is there to be explained.
    assert profile.set_index("month").deaths_all.loc[[7, 8]].min() > 110


def test_an_offset_equal_to_the_outcome_removes_all_seasonality(monkeypatch) -> None:
    # If deaths were exactly proportional to traffic, every month effect per unit of traffic
    # would be 1: the model has to find that, and find the raw season without the offset.
    rng = np.random.default_rng(11)
    months = np.tile(np.arange(1, 13), 4)
    years = np.repeat([2016, 2017, 2018, 2019], 12)
    traffic = 10_000 * (1 + 0.3 * np.sin((months - 4) / 12 * 2 * np.pi))
    panel = pd.DataFrame(
        {
            "year": years,
            "month": months,
            "deaths_all": rng.poisson(traffic).astype(float),
            "road_fuel_tonnes": traffic,
            "petrol_tonnes": traffic,
            "toll_intensity": traffic,
        }
    )
    monkeypatch.setattr(seasonality, "monthly_panel", lambda: panel)
    effects = seasonality.month_effects(years=(2016, 2017, 2018, 2019))
    assert set(effects.exposure) == {"none", "road_fuel_tonnes"}
    per_traffic = effects[effects.exposure == "road_fuel_tonnes"]
    assert per_traffic.rate_ratio.to_numpy() == pytest.approx(np.ones(12), abs=0.03)
    raw = effects[effects.exposure == "none"].set_index("month").rate_ratio
    assert raw.loc[7] > 1.2 and raw.loc[1] < 0.8


def test_lockdown_compares_each_month_with_the_same_month_before() -> None:
    lockdown = seasonality.lockdown_months().set_index("month")
    assert lockdown.loc[4, "deaths_change"] < -0.5  # April 2020
    assert lockdown.loc[4, "road_fuel_tonnes_change"] < -0.5
    change = (1 + lockdown.deaths_change) / (1 + lockdown.road_fuel_tonnes_change) - 1
    assert change.to_numpy() == pytest.approx(
        lockdown.deaths_per_road_fuel_tonnes_change.to_numpy()
    )
    # Road fuel is the only traffic comparator of the lockdown months.
    assert not [c for c in lockdown.columns if "petrol" in c or "toll" in c]


def test_raw_month_effects_allow_for_the_length_of_the_month(monkeypatch) -> None:
    # Deaths proportional to the days in the month, with no other seasonality: per day, every
    # month is the same, and February is not low just for being short.
    months = np.tile(np.arange(1, 13), 4)
    years = np.repeat([2015, 2017, 2018, 2019], 12)
    days = np.array([[31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1] for m in months])
    panel = pd.DataFrame(
        {
            "year": years,
            "month": months,
            "deaths_all": 10 * days.astype(float),
            "road_fuel_tonnes": 1e6 * days.astype(float),
        }
    )
    monkeypatch.setattr(seasonality, "monthly_panel", lambda: panel)
    effects = seasonality.month_effects(years=(2015, 2017, 2018, 2019))
    raw = effects[effects.exposure == "none"].rate_ratio
    assert raw.to_numpy() == pytest.approx(np.ones(12), abs=1e-6)
