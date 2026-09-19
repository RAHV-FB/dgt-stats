import pandas as pd
import pytest

from dgt_stats import io_tables, policy

pytestmark = pytest.mark.skipif(
    not io_tables.interim_path("series_monthly").exists(),
    reason="run `python scripts/ingest.py tables` first",
)


def test_monthly_series_is_complete_and_matches_the_yearbook() -> None:
    series = policy.monthly_series()
    assert len(series) == 384
    assert series.period.iloc[0] == pd.Timestamp("1993-01-01")
    assert series.period.iloc[-1] == pd.Timestamp("2024-12-01")
    year_2006 = series[series.period.dt.year == 2006].set_index(
        series.period.dt.month[series.period.dt.year == 2006]
    )
    assert year_2006.deaths.loc[7] == 380 and year_2006.deaths.loc[12] == 324
    assert series[series.period.dt.year == 2024].deaths.sum() == 1_785
    interurban = policy.monthly_series(zone="interurban")
    urban = policy.monthly_series(zone="urban")
    gap = interurban.deaths + urban.deaths - series.deaths
    # The yearbook's zone sheets differ from its all-roads sheet by one death in four months of 1995.
    assert (gap.abs() <= 1).all() and (gap != 0).sum() == 4
    assert set(series.period[gap != 0].dt.year) == {1995}
    day = policy.monthly_series(metric="deaths_24h")
    assert (day.deaths <= series.deaths).all()


def test_road_group_panel_covers_every_month_and_sums_to_the_microdata() -> None:
    panel = policy.monthly_by_road_group()
    assert set(panel.group) == {policy.TREATED, policy.CONTROL}
    assert panel.groupby("group").size().eq(9 * 12).all()
    treated = panel[panel.group == policy.TREATED].set_index("period").deaths
    assert treated.loc["2016-01-01"] == 55 and treated.loc["2016-07-01"] == 93
    control = panel[panel.group == policy.CONTROL].set_index("period").deaths
    assert control.loc["2016-01-01"] == 28 + 8
    raw = pd.DataFrame(
        {
            "ANYO": [2016, 2016, 2016, 2016],
            "MES": [1, 1, 2, 3],
            "road_group": ["conventional", "urban_street", "motorway", pd.NA],
            "TOTAL_MU30DF": [2, 5, 1, 3],
        }
    )
    small = policy.monthly_by_road_group(raw)
    assert len(small) == 24 and small.deaths.sum() == 3
    assert (
        small[(small.group == policy.CONTROL) & (small.period == "2016-02-01")].deaths.iloc[0] == 1
    )


def test_intervention_windows_and_fleet_offset() -> None:
    points = policy.INTERVENTIONS["points_licence"]
    assert points.post_months == 17
    assert points.second_break == pd.Timestamp("2007-12-01")
    speed = policy.INTERVENTIONS["speed_limit_90"]
    assert speed.post_months == 13 and speed.design == "did"
    series = policy.monthly_series()
    inside = policy.window(series, points.pre_start, points.post_end)
    assert len(inside) == 78 + 17
    fleet = policy.fleet_offset(inside.period)
    assert fleet.is_monotonic_increasing
    july_2006 = fleet[inside.period == "2006-07-01"].iloc[0]
    annual = io_tables.read_table("series_annual")
    published = annual[
        (annual.metric == "vehicle_fleet") & (annual.zone == "all") & (annual.year == 2006)
    ]
    assert july_2006 == pytest.approx(float(published.value.iloc[0]))
