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
    questions = {"q1", "q2", "q4", "q5", "q6", "q7"}
    assert all(name.split("_")[0] in questions for name in summaries.SUMMARIES)


def test_province_rates_cover_every_province() -> None:
    provinces = summaries.province_rates()
    assert len(provinces) == 53 and provinces.is_total.sum() == 1
    total = provinces[provinces.is_total].iloc[0]
    assert total.deaths_30d == 1_785 and total.crashes == 101_996
    rest = provinces[~provinces.is_total]
    assert rest.deaths_30d.sum() == total.deaths_30d
    assert rest.population.sum() == total.population
    assert rest.licence_holders.sum() == total.licence_holders
    assert (rest.deaths_per_100k_low <= rest.deaths_per_100k).all()
    assert rest.deaths_rank.min() == 1 and rest.deaths_rank.max() <= 52


def test_national_rates_by_year() -> None:
    national = summaries.national_rates_by_year()
    assert national.year.min() == 2002 and national.year.max() == 2024
    row = national[national.year == 2024].iloc[0]
    assert 3.0 < row.deaths_per_100k_residents < 4.0
    assert row.licence_holders == 28_142_470
    assert national[national.year < 2014].deaths_per_100k_licence.isna().all()


def test_driver_ladder_is_complete_and_ordered() -> None:
    ladder = summaries.driver_ladder()
    assert sorted(ladder.year.unique()) == list(summaries.LADDER_YEARS)
    assert set(ladder.band.unique()) == set(summaries.agebands.ANALYSIS_BANDS)
    assert ladder.driver_deaths.notna().all() and ladder.licence_holders.notna().all()
    assert ((ladder.licence_share > 0) & (ladder.licence_share < 1)).all()
    assert ((ladder.travel_share > 0) & (ladder.travel_share <= ladder.licence_share + 1e-9)).all()
    assert (ladder.travel_share_low <= ladder.travel_share).all()
    assert (ladder.deaths_per_100k_travel >= ladder.deaths_per_100k_licence - 1e-9).all()
    deaths_2024 = ladder[ladder.year == 2024].driver_deaths.sum()
    assert deaths_2024 < 1_186 and deaths_2024 > 1_150  # drivers with unknown age excluded


def test_ladder_ratio_rises_with_the_denominator() -> None:
    ratios = summaries.ladder_ratio()
    assert set(ratios.denominator.unique()) == set(summaries.LADDER_DENOMINATORS)
    latest = ratios[(ratios.year == 2024) & (ratios.band == "75+")].set_index("denominator").ratio
    assert latest["residents"] < latest["licence_holders"] < latest["travel_weighted"]


def test_licence_share_victims_and_movilia() -> None:
    share = summaries.licence_share_by_age()
    assert set(share.sex.unique()) == {"total", "male", "female"}
    older = share[(share.year == 2024) & (share.sex == "female") & (share.band == "75+")].iloc[0]
    assert older.licence_share < 0.4
    victims = summaries.victims_by_age_rates()
    assert set(victims.band.unique()) == set(summaries.VICTIM_BANDS)
    assert victims[victims.year == 2024].deaths_30d.sum() == 1_785 - 29 - 12
    travel = summaries.movilia_car_travel()
    assert travel.car_share_of_trips.between(0, 1).all()


def test_registry_covers_phases_2_to_5() -> None:
    questions = {name.split("_")[0] for name in summaries.SUMMARIES}
    assert questions == {"q1", "q2", "q4", "q5", "q6", "q7"}
