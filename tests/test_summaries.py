import pytest

from dgt_stats import io_exposure, io_tables, summaries

pytestmark = pytest.mark.skipif(
    not (
        summaries.PROCESSED_CRASHES.exists()
        and io_tables.interim_path("series_annual").exists()
        and io_exposure.interim_path("conductores_por_edad").exists()
        and io_exposure.interim_path("censo_edad").exists()
    ),
    reason="run `python scripts/ingest.py tables exposure` and `python scripts/build_tables.py` first",
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


def test_monthly_deaths_peak_in_summer_and_sum_to_the_yearbook() -> None:
    monthly = summaries.monthly_deaths()
    assert monthly[monthly.year == 2024].sort_values("share_of_year").iloc[-1].month in (7, 8)
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
    # The road-user split of each year and zone adds up to the zone table, not just to itself.
    zone_totals = summaries.annual_by_zone().set_index(["year", "zone"]).deaths_30d
    assert users.groupby(["year", "zone"]).deaths_30d.sum().eq(zone_totals).all()
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
    assert (ladder.travel_share > 0).all()
    assert (ladder.travel_share_low <= ladder.travel_share).all()
    # The travel share is capped at the licence share; it binds in the younger bands only.
    assert ladder[ladder.travel_capped].band.isin({"15-24", "25-34", "35-44", "45-54"}).all()
    assert ladder[ladder.year == 2024].travel_capped.tolist() == [
        True,
        True,
        True,
        False,
        False,
        False,
        False,
    ]
    oldest = ladder[(ladder.year == 2024) & (ladder.band == "75+")].iloc[0]
    assert oldest.deaths_per_100k_travel == pytest.approx(11.64, abs=0.01)
    deaths_2024 = ladder[ladder.year == 2024].driver_deaths.sum()
    published = io_tables.read_series_road_users()
    total = published[
        (published.year == 2024)
        & (published.population == "drivers")
        & (published.severity == "deaths_30d")
        & (published.zone == "all")
        & published.is_total
    ].value.iloc[0]
    # 3 drivers of unknown age and 1 driver aged 10-14 fall outside the 15+ analysis bands
    assert deaths_2024 == total - 3 - 1


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


def test_other_road_by_period_splits_the_pooled_row() -> None:
    other = summaries.other_road_by_period().set_index("period")
    assert list(other.index) == ["2016-2023", "2024"]
    pooled = summaries.hour_band_by_road_group()
    assert other.crashes.sum() == pooled[pooled.road_group == "other"].crashes.sum()
    assert (
        other.crashes.sum() == summaries.read_crashes(["road_group"]).road_group.eq("other").sum()
    )
    assert other.share_of_row.sum() == pytest.approx(1, abs=1e-3)
    assert other.loc["2024", "share_of_row"] == pytest.approx(0.3945, abs=5e-4)
    assert other.loc["2024", "street_share"] > 0.8 > other.loc["2016-2023", "street_share"]
    # the 2024 "other" row is mostly urban street and much less deadly than the 2016-2023 one
    assert other.loc["2016-2023", "fatal_share"] > 2 * other.loc["2024", "fatal_share"]
    assert (other.fatal_share == (other.fatal_crashes / other.crashes).round(4)).all()


def test_registry_covers_every_question_except_the_models() -> None:
    # Q3 is the severity model; its tables are written by scripts/model.py, not the registry.
    questions = {name.split("_")[0] for name in summaries.SUMMARIES}
    assert questions == {"q1", "q2", "q4", "q5", "q6", "q7", "q8", "q9"}


def test_annual_rates_and_month_zone() -> None:
    rates = summaries.annual_rates()
    assert len(rates) == 32 and rates.year.min() == 1993 and rates.year.max() == 2024
    fleet = rates.set_index("year").vehicle_fleet
    assert fleet.loc[2022] == 35_668_443  # the register total behind the vehicles page
    assert fleet.loc[2024] == 36_241_784

    mz = summaries.month_zone()  # pooled 2016–2024
    assert set(mz.zone) == {"interurban", "urban"}
    assert len(mz) == 24 and (mz.groupby("zone", observed=True).size() == 12).all()
    assert mz.crashes.sum() == 875_013 and mz.deaths_30d.sum() == 15_441
