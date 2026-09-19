import numpy as np
import pytest

from dgt_stats import io_reports, io_tables, speed

pytestmark = pytest.mark.skipif(
    not (
        io_tables.interim_path("tables_driver_infractions").exists()
        and io_reports.SPEED_REPORT_INTERIM.exists()
    ),
    reason="run `python scripts/ingest.py tables reports` first",
)


def test_infraction_shares_add_up_and_show_the_unknown_jump() -> None:
    shares = speed.infraction_shares()
    assert sorted(shares.year.unique()) == list(range(2014, 2025))
    assert set(shares.zone) == {"all", "interurban", "urban"}
    parts = shares[["share_speed_infraction", "share_too_slow", "share_none", "share_unknown"]]
    assert np.allclose(parts.sum(axis=1), 1, atol=2e-4)
    assert np.allclose(shares.speed_infraction / shares.known, shares.share_among_known, atol=1e-4)
    assert (shares.share_among_known_low < shares.share_among_known).all()
    assert (shares.share_among_known < shares.share_among_known_high).all()
    both = shares[shares.zone == "all"].set_index("year")
    assert both.loc[2024, "total"] == 61_318 + 108_869
    assert both.loc[2014, "share_unknown"] < 0.2 and both.loc[2016, "share_unknown"] > 0.5
    zones = shares[shares.zone != "all"].groupby("year")[["total", "speed_infraction"]].sum()
    assert (zones.total == both.total.loc[zones.index]).all()
    assert (zones.speed_infraction == both.speed_infraction.loc[zones.index]).all()


def test_infractions_by_vehicle_and_other_infractions() -> None:
    by_vehicle = speed.infractions_by_vehicle()
    latest = by_vehicle[by_vehicle.zone == "all"].set_index("vehicle_group")
    assert latest.loc["total", "total"] == 170_187
    assert latest.loc["motorcycle", "speed_infraction"] == 894 + 680
    assert latest.loc["motorcycle", "share_among_known"] > latest.loc["car", "share_among_known"]
    groups = [g for g in latest.index if g != "total"]
    assert latest.loc[groups, "total"].sum() == latest.loc["total", "total"]
    assert (by_vehicle.share_unknown.between(0, 1)).all()

    others = speed.other_infractions()
    all_roads = others[others.zone == "all"]
    assert all_roads.iloc[0]["item"] == "other_priority"  # the largest infraction group
    assert "speed_infraction" in set(all_roads.item)
    speed_row = all_roads[all_roads.item == "speed_infraction"].iloc[0]
    assert speed_row.drivers_with_infraction == 4_473 + 2_920
    assert speed_row.known == 61_318 + 108_869 - (30_115 + 58_537)


def test_report_tables_carry_the_scope_and_their_own_totals() -> None:
    factors = speed.report_factors()
    assert (factors.region_scope == io_reports.REGION_SCOPE).all()
    row = factors[
        (factors.zone == "all") & (factors.year == 2023) & (factors.factor == "Inappropriate speed")
    ]
    assert row.crashes.iloc[0] == 5_070 and row.share_of_crashes.iloc[0] == pytest.approx(0.07)

    roads = speed.report_road_type()
    latest = roads[roads.year == 2023].set_index("label")
    assert latest.loc["Total", "crashes"] == 5_070 and latest.loc["Total", "deaths"] == 319
    assert latest.drop(index="Total").share_of_crashes.sum() == pytest.approx(1, abs=1e-3)
    assert list(roads[roads.year == 2023].label) == list(speed.ROAD_TYPE_LABELS.values())

    limits = speed.report_speed_limit()
    latest = limits[limits.year == 2023]
    assert list(latest.label[:3]) == ["10 km/h", "20 km/h", "30 km/h"]
    assert latest.label.iloc[-1] == "Total"
    assert latest.set_index("label").loc["90 km/h", "deaths"] == 86

    vehicle = speed.report_vehicle()
    latest = vehicle[vehicle.year == 2023].set_index("label")
    assert latest.loc["Motorcycles", "deaths"] == 117 and np.isnan(latest.loc["Total", "crashes"])
    assert latest.loc["Cars", "share_of_deaths"] == pytest.approx(142 / 319, abs=1e-3)

    age = speed.report_age()
    assert set(age.sex) == {"all", "men", "women"} and set(age.year) == {2014, 2023}
    assert (
        age[(age.sex == "all") & (age.year == 2023) & (age.age_band == "25-34")].crashes.iloc[0]
        == 1_491
    )

    grid = speed.report_day_hour()
    assert len(grid) == 7 * 24 and grid.crashes.sum() == 57_383 and grid.deaths.sum() == 3_220
    assert grid.share_of_crashes.sum() == pytest.approx(1, abs=1e-3)

    licence = speed.report_licence()
    assert licence[(licence.year == 2023) & (licence.licence_class == "B")].crashes.iloc[0] == 3_853
