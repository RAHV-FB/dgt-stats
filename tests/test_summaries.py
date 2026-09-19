import pytest

from dgt_stats import summaries

pytestmark = pytest.mark.skipif(
    not summaries.PROCESSED_CRASHES.exists(),
    reason="run `python scripts/build_tables.py` first",
)


def test_annual_headline_matches_yearbook() -> None:
    headline = summaries.annual_headline()
    row = headline[headline.year == 2024].iloc[0]
    assert row.crashes == 101_996
    assert row.deaths_30d == 1_785
    assert row.hospitalised_30d == 9_561
    base = headline[headline.year == summaries.BASE_YEAR].iloc[0]
    assert base.crashes_index == 100.0 and base.deaths_30d_index == 100.0
    assert headline.year.min() == 1993 and len(headline) == 32


def test_annual_by_zone_sums_to_yearbook() -> None:
    by_zone = summaries.annual_by_zone()
    year = by_zone[by_zone.year == 2024].set_index("zone")
    assert year.loc["interurban", "crashes"] == 35_772
    assert year.loc["urban", "crashes"] == 66_224
    assert year.loc["interurban", "deaths_30d"] + year.loc["urban", "deaths_30d"] == 1_785


def test_monthly_deaths_shares_sum_to_one() -> None:
    monthly = summaries.monthly_deaths()
    shares = monthly.groupby("year").share_of_year.sum()
    assert ((shares - 1).abs() < 0.001).all()
    assert monthly[(monthly.year == 2024)].deaths_30d.sum() == 1_785


def test_hour_weekday_covers_the_grid_and_totals() -> None:
    grid = summaries.hour_weekday()
    assert len(grid) == 7 * 24
    assert grid.crashes.sum() == 875_013
    assert grid.deaths_30d.sum() == 15_441
    assert ((grid.fatal_share >= 0) & (grid.fatal_share <= 1)).all()


def test_night_share_and_hour_band_road_group() -> None:
    night = summaries.night_share_by_year_zone()
    assert set(night.zone) == {"interurban", "urban"}
    assert ((night.night_crash_share > 0) & (night.night_crash_share < 1)).all()
    bands = summaries.hour_band_by_road_group()
    assert set(bands.road_group) == {
        "motorway",
        "dual_carriageway",
        "conventional",
        "urban_street",
        "other",
    }
    assert set(bands.hour_band) == {"00-06", "07-09", "10-13", "14-16", "17-19", "20-23"}


def test_deaths_by_road_user_reconciles() -> None:
    users = summaries.deaths_by_road_user()
    total_2024 = users[users.year == 2024].deaths_30d.sum()
    assert total_2024 == 1_785
    shares = users.groupby(["year", "zone"]).share.sum()
    assert ((shares - 1).abs() < 0.001).all()
    vulnerable = summaries.vulnerable_share_by_year()
    assert ((vulnerable.vulnerable_share > 0.2) & (vulnerable.vulnerable_share < 0.9)).all()


def test_series_based_summaries() -> None:
    drivers = summaries.driver_deaths_series()
    assert drivers.vehicle_type_label.notna().all()
    assert (
        drivers[(drivers.year == 2024) & (drivers.vehicle_type == "Motocicletas")].deaths_30d.iloc[
            0
        ]
        == 415
    )
    pedestrians = summaries.pedestrian_series()
    assert {"deaths_30d", "hospitalised_30d", "non_hospitalised_30d"} <= set(pedestrians.columns)
    row = pedestrians[(pedestrians.year == 2024) & (pedestrians.zone == "all")].iloc[0]
    assert row.deaths_30d == 320


def test_registry_names_are_prefixed_by_question() -> None:
    assert all(name.split("_")[0] in {"q1", "q2", "q5"} for name in summaries.SUMMARIES)
