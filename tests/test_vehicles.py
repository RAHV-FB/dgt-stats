import numpy as np
import pytest

from dgt_stats import io_exposure, io_tables, vehicles

pytestmark = pytest.mark.skipif(
    not (
        io_tables.interim_path("tables_units_by_type").exists()
        and io_exposure.interim_path("km_medios_2022").exists()
    ),
    reason="run `python scripts/ingest.py tables` and `python scripts/ingest.py exposure` first",
)


def test_vehicle_km_sums_the_age_bands_and_shares_add_up() -> None:
    by_age = vehicles.km_by_age()
    assert len(by_age) == 35 and set(by_age.age_band) == set(vehicles.AGE_BANDS.values())

    km = vehicles.vehicle_km()
    # The age-band shares use the same group kilometres as the group table, not their own total.
    group_km = km.set_index("group").vehicle_km
    assert np.allclose(
        by_age.km_share_within_group, (by_age.vehicle_km / by_age.group.map(group_km)).round(4)
    )
    assert list(km.group) == [*vehicles.KM_GROUPS, "total"]
    total = km[km.group == "total"].iloc[0]
    assert total.n_vehicles == by_age.n_vehicles.sum() == 32_522_330
    assert total.vehicle_km == pytest.approx(by_age.vehicle_km.sum())
    # Shares of the published fleet total, not of a total the table builds from its own rows.
    assert km[km.group != "total"].n_vehicles.sum() == 32_522_330
    assert km[km.group == "car"].fleet_share.iloc[0] == pytest.approx(
        23_173_813 / 32_522_330, abs=5e-5
    )
    heavy = km[km.group == "heavy_truck"].iloc[0]
    assert heavy.km_per_vehicle > 4 * km[km.group == "car"].iloc[0].km_per_vehicle

    merged = vehicles.vehicle_km(by_rate_group=True)
    assert list(merged.group) == [*vehicles.RATE_GROUPS, "total"]
    vans = merged[merged.group == vehicles.MERGED_GROUP].iloc[0]
    assert vans.n_vehicles == km[km.group.isin(["van", "light_truck"])].n_vehicles.sum()


def test_rates_recompute_from_their_columns_and_intervals_hold() -> None:
    long = vehicles.rates_2022()
    assert set(long.measure) == set(vehicles.MEASURES)
    assert set(long.group) == set(vehicles.RATE_GROUPS)
    assert len(long) == len(vehicles.RATE_GROUPS) * 3 * len(vehicles.MEASURES)
    per_km = long["count"] / long.vehicle_km * vehicles.BILLION
    assert np.allclose(per_km, long.per_billion_km)
    per_vehicle = long["count"] / long.n_vehicles * vehicles.PER_VEHICLES
    assert np.allclose(per_vehicle, long.per_100k_vehicles)
    assert (long.per_billion_km_low <= long.per_billion_km).all()
    assert (long.per_billion_km <= long.per_billion_km_high).all()
    # Pinned to the published inputs: TABLA 2.3 2022 car rows and the km table car strata.
    car = long[(long.group == "car") & (long.zone == "all")].set_index("measure")
    car_km = 1.040664e11 + 6.569315e10 + 4.612673e10 + 5.686434e10 + 3.019795e10
    assert car.loc["fatal_involvement", "count"] == 1_290 + 2 + 7
    assert car.loc["fatal_involvement", "per_billion_km"] == pytest.approx(
        1_299 / car_km * vehicles.BILLION, rel=1e-4
    )
    assert car.loc["occupant_deaths", "count"] == 681  # equals TOT_TUR_MU30DF in the microdata
    involvement = long[long.measure != "occupant_deaths"]
    zones = involvement.pivot_table(index=["group", "measure"], columns="zone", values="count")
    assert (zones.interurban + zones.urban == zones["all"]).all()


def test_summary_matches_the_yearbook_and_the_long_table() -> None:
    summary = vehicles.summary_2022().set_index("group")
    assert summary.loc["heavy_truck", "fatal_involvement"] == 83 + 2 + 57 + 142
    assert summary.loc["bus", "occupant_deaths"] == 13
    assert summary.loc["car", "injury_involvement"] == 98_475 + 131 + 1_634
    assert summary.loc["car", "occupant_deaths"] == 681
    assert summary.loc["car", "occupant_deaths_per_fatal_involvement"] == pytest.approx(0.524)
    assert summary.loc["heavy_truck", "occupant_deaths_per_fatal_involvement"] < 0.25
    assert summary.loc["motorcycle", "occupant_deaths_per_fatal_involvement"] > 0.9
    assert sorted(summary.rank_fatal_per_bn_km) == list(range(1, len(summary) + 1))
    long = vehicles.rates_2022()
    row = long[(long.group == "bus") & (long.zone == "all") & (long.measure == "fatal_involvement")]
    assert summary.loc["bus", "fatal_involvement_per_bn_km"] == round(
        float(row.per_billion_km.iloc[0]), 2
    )


def test_involvement_by_year_and_occupant_series() -> None:
    by_year = vehicles.involvement_by_year()
    assert sorted(by_year.year.unique()) == list(io_tables.VEHICLE_TABLE_YEARS)
    assert by_year[by_year.group == "pedestrian"].fatal_involvement_share_of_vehicles.isna().all()
    # Shares of the vehicles involved in fatal crashes, pedestrians excluded: pinned to TABLA 2.3.
    cars_2022 = by_year[(by_year.year == 2022) & (by_year.group == "car")].iloc[0]
    assert cars_2022.fatal_involvement == 1_299
    assert cars_2022.fatal_involvement_share_of_vehicles == pytest.approx(0.5102, abs=5e-5)

    split = vehicles.van_light_truck_split().set_index("group")
    assert list(split.index) == ["van", "light_truck"]
    assert split.loc["van", "fatal_involvement"] == 215
    assert split.loc["light_truck", "fatal_involvement"] == 62 + 1
    assert (
        split.fatal_involvement.sum()
        == vehicles.summary_2022()
        .set_index("group")
        .loc[vehicles.MERGED_GROUP, "fatal_involvement"]
    )
    assert (
        by_year[(by_year.year == 2024) & (by_year.group == "pedestrian")].iloc[0].fatal_involvement
        == 380
    )

    series = vehicles.occupant_deaths_series()
    assert series.year.min() == 1993 and series.year.max() == 2024
    row = series[(series.year == 2022) & (series.group == vehicles.MERGED_GROUP)].iloc[0]
    assert row.deaths_30d == 98 and row.has_km_denominator
    assert series[(series.year == 1993) & (series.group == "vmp")].deaths_30d.isna().all()

    groups = vehicles.vehicle_groups_table()
    assert len(groups) == len(vehicles.VEHICLE_GROUPS)
    assert groups.has_km_denominator.sum() == len(vehicles.KM_GROUPS)
    assert (
        groups[groups.group.isin(["van", "light_truck"])].series_column
        == vehicles.SERIES_MERGED_COLUMN
    ).all()
