import numpy as np
import pandas as pd
import pytest

from dgt_stats import rates


def test_poisson_interval_matches_garwood_tables() -> None:
    low, high = rates.poisson_interval(10)
    assert abs(low - 4.795) < 0.01 and abs(high - 18.39) < 0.01
    assert rates.poisson_interval(0) == (0.0, pytest.approx(3.689, abs=0.01))


def test_rate_scales_the_interval() -> None:
    value, low, high = rates.rate(10, 1_000, per=100_000)
    assert value == 1_000
    assert abs(low - 479.5) < 1 and abs(high - 1_839) < 1
    assert all(np.isnan(v) for v in rates.rate(10, 0))


def test_add_rate_columns() -> None:
    frame = pd.DataFrame({"deaths": [10, 0, 5], "people": [1000, 500, np.nan]})
    out = rates.add_rate(frame, "deaths", "people", "per_100k")
    assert list(out.columns[-3:]) == ["per_100k", "per_100k_low", "per_100k_high"]
    assert out.per_100k.tolist()[:2] == [1000.0, 0.0]
    assert np.isnan(out.per_100k.iloc[2])


def test_rate_ratio_interval() -> None:
    ratio, low, high = rates.rate_ratio(20, 1000, 10, 1000)
    assert ratio == 2.0 and low < 2.0 < high
    assert abs(low - 2 * np.exp(-1.96 * np.sqrt(0.15))) < 0.01
    assert np.isnan(rates.rate_ratio(0, 1000, 10, 1000)[1])


def test_wilson_interval_bounds() -> None:
    low, high = rates.wilson_interval(0.759, 935)
    assert 0.73 < low < 0.759 < high < 0.79
    assert rates.wilson_interval(0.0, 10)[0] == 0.0


def test_interpolate_share_between_and_outside_waves() -> None:
    waves = pd.DataFrame({"wave": [2018, 2023], "share": [0.8, 0.7], "n": [900, 900]})
    assert rates.interpolate_share(2018, waves)[0] == pytest.approx(0.8)
    assert rates.interpolate_share(2020, waves)[0] == pytest.approx(0.76)
    assert rates.interpolate_share(2014, waves)[0] == pytest.approx(0.8)
    assert rates.interpolate_share(2025, waves)[0] == pytest.approx(0.7)
    value, low, high = rates.interpolate_share(2021, waves)
    assert low < value < high


def test_travel_weighted_share_spreads_and_caps() -> None:
    waves = pd.DataFrame({"wave": [2023], "share": [0.75], "n": [900]})
    profile = pd.Series({"25-34": 1.2, "75+": 0.4})
    licence = pd.Series({"25-34": 0.95, "75+": 0.25})
    out = rates.travel_weighted_share(2023, waves, profile, licence)
    young = out[out.band == "25-34"].iloc[0]
    old = out[out.band == "75+"].iloc[0]
    assert young.share == pytest.approx(0.9) and not young.capped
    assert old.share == pytest.approx(0.25) and old.capped
    assert young.share_low < young.share < young.share_high
