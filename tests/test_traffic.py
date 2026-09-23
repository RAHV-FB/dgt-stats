import pandas as pd
import pytest

from dgt_stats import io_traffic
from dgt_stats.paths import CORES_FUEL_PATH, TOLL_TRAFFIC_PATH

pytestmark = pytest.mark.skipif(
    not (CORES_FUEL_PATH.exists() and TOLL_TRAFFIC_PATH.exists()),
    reason="the monthly traffic sources are not in data/raw",
)


def test_cores_fuel_is_a_complete_monthly_series_from_1996() -> None:
    fuel = io_traffic.read_cores_fuel()
    assert fuel.period.iloc[0] == pd.Timestamp("1996-01-01")
    assert fuel.period.is_monotonic_increasing and fuel.period.is_unique
    expected = pd.date_range(fuel.period.min(), fuel.period.max(), freq="MS")
    assert list(fuel.period) == list(expected)
    assert (fuel.road_fuel_tonnes == fuel.petrol_tonnes + fuel.diesel_tonnes).all()
    assert (fuel.road_fuel_tonnes > 0).all()
    # Road diesel overtook petrol in Spain during the 2000s; the series has to show it.
    assert fuel[fuel.year == 1996].diesel_tonnes.sum() > fuel[fuel.year == 1996].petrol_tonnes.sum()
    assert (
        fuel[fuel.year == 2006].diesel_tonnes.sum()
        > 3 * fuel[fuel.year == 2006].petrol_tonnes.sum()
    )
    # Summer is the peak of road-fuel consumption, which is what makes it a seasonality control.
    monthly = fuel[fuel.year.between(2000, 2007)].groupby("month").road_fuel_tonnes.mean()
    assert monthly.idxmax() in (7, 8)


def test_toll_traffic_is_a_complete_monthly_series_from_1990() -> None:
    toll = io_traffic.read_toll_traffic()
    assert toll.period.iloc[0] == pd.Timestamp("1990-01-01")
    expected = pd.date_range(toll.period.min(), toll.period.max(), freq="MS")
    assert list(toll.period) == list(expected)
    assert (toll.veh_km_millions > 0).all() and (toll.imd > 0).all()
    assert (toll.network_km > 0).all()
    # August is the peak on a holiday-heavy network, every year.
    peaks = (
        toll[toll.year.between(2000, 2007)]
        .groupby("year")
        .apply(
            lambda block: int(block.loc[block.veh_km_millions.idxmax(), "month"]),
            include_groups=False,
        )
    )
    assert set(peaks) <= {7, 8}
    # April 2020 is the lockdown floor of the whole series.
    assert toll.loc[toll.veh_km_millions.idxmin(), "period"] == pd.Timestamp("2020-04-01")


def test_the_two_series_agree_on_the_shape_of_a_spanish_year() -> None:
    fuel = io_traffic.read_cores_fuel()
    toll = io_traffic.read_toll_traffic()
    window = slice("2000-01-01", "2007-11-01")
    a = fuel.set_index("period").road_fuel_tonnes.loc[window]
    b = toll.set_index("period").veh_km_millions.loc[window]
    assert len(a) == len(b) == 95
    seasonal_fuel = a.groupby(a.index.month).mean() / a.mean()
    seasonal_toll = b.groupby(b.index.month).mean() / b.mean()
    assert seasonal_fuel.corr(seasonal_toll) > 0.7
    assert seasonal_fuel.idxmax() == 7 and seasonal_toll.idxmax() == 8
    # The toll network is holiday traffic and swings far harder than national fuel sales, which
    # is why the policy page treats the two as different measurements rather than one exposure.
    assert seasonal_toll.max() - seasonal_toll.min() > 3 * (
        seasonal_fuel.max() - seasonal_fuel.min()
    )
