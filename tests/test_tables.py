import pytest

from dgt_stats import vehicles
from dgt_stats import io_tables as tables


@pytest.fixture(scope="module")
def annual():
    return tables.read_series_annual()


def test_series_annual_headline_totals(annual) -> None:
    def value(year: int, metric: str, zone: str = "all") -> float:
        row = annual[(annual.year == year) & (annual.metric == metric) & (annual.zone == zone)]
        assert len(row) == 1, (year, metric, zone)
        return float(row.value.iloc[0])

    assert value(2024, "crashes") == 101_996
    assert value(2024, "crashes", "interurban") == 35_772
    assert value(2024, "crashes", "urban") == 66_224
    assert value(2024, "deaths_30d") == 1_785
    assert value(1993, "deaths_30d") == 6_378
    assert value(2020, "crashes") == 72_959
    assert value(2024, "vehicle_fleet") == 36_241_784
    assert annual.year.min() == 1993 and annual.year.max() == 2024


def test_series_monthly_sums_match_annual_totals(annual) -> None:
    monthly = tables.read_series_monthly()
    deaths = monthly[(monthly.metric == "deaths_30d") & (monthly.zone == "all")]
    sums = deaths.groupby("year").value.sum()
    totals = deaths.groupby("year").annual_total.first()
    assert (sums == totals).all()
    expected = annual[(annual.metric == "deaths_30d")].set_index("year").value
    assert (sums == expected.loc[sums.index]).all()
    assert set(monthly.metric.unique()) == {
        "deaths_30d",
        "hospitalised_30d",
        "non_hospitalised_30d",
        "victims_30d",
        "deaths_24h",
    }


def test_series_province_totals() -> None:
    province = tables.read_series_province()
    total = province[province.is_total & (province.metric == "crashes") & (province.zone == "all")]
    assert float(total[total.year == 2024].value.iloc[0]) == 101_996
    by_province = province[
        ~province.is_total
        & (province.metric == "deaths_30d")
        & (province.zone == "all")
        & (province.year == 2024)
    ]
    assert len(by_province) == 52
    assert by_province.value.sum() == 1_785


def test_series_age_sex_and_road_users() -> None:
    age = tables.read_series_age()
    row = age[
        (age.year == 2024)
        & (age.severity == "deaths_30d")
        & (age.age_band == "65 y más")
        & (age.zone == "all")
    ]
    assert float(row.value.iloc[0]) == 486

    sex = tables.read_series_sex()
    row = sex[
        (sex.year == 2024)
        & (sex.severity == "deaths_30d")
        & (sex.sex == "Hombre")
        & (sex.zone == "all")
    ]
    assert float(row.value.iloc[0]) == 1_422

    users = tables.read_series_road_users()
    row = users[
        (users.year == 2024)
        & (users.population == "drivers")
        & (users.severity == "deaths_30d")
        & (users.zone == "all")
        & (users.vehicle_type == "Motocicletas")
    ]
    assert float(row.value.iloc[0]) == 415
    vmp_1993 = users[(users.year == 1993) & (users.vehicle_type == "VMP") & (users.zone == "all")]
    assert vmp_1993.value.isna().all()


def test_series_pedestrians() -> None:
    ped = tables.read_series_pedestrians()
    row = ped[
        (ped.year == 2024)
        & (ped.breakdown == "severity")
        & (ped.category == "deaths_30d")
        & (ped.zone == "all")
    ]
    assert float(row.value.iloc[0]) == 320


def test_tables_2024_province_and_month() -> None:
    province = tables.read_table_1_1()
    total = province[province.is_total & (province.zone == "all")].set_index("metric").value
    assert total["crashes"] == 101_996
    assert total["deaths_30d"] == 1_785
    assert total["hospitalised_30d"] == 9_561
    provinces = province[
        ~province.is_total & (province.zone == "all") & (province.metric == "crashes")
    ]
    assert len(provinces) == 52
    assert provinces.value.sum() == 101_996

    month = tables.read_table_3_1()
    total = month[month.is_total & (month.zone == "all")].set_index("metric").value
    assert total["crashes"] == 101_996
    assert total["deaths_30d"] == 1_785
    months = month[~month.is_total & (month.zone == "all") & (month.metric == "deaths_30d")]
    assert list(months.month) == list(range(1, 13))
    assert months.value.sum() == 1_785


def test_tables_2024_units_and_vehicles_involved() -> None:
    units = tables.read_table_2_3()
    total = units[units.is_total & (units.zone == "all")].set_index("metric").value
    assert total["crashes"] == 190_508
    pedestrians = units[
        (units.unit_type == "Peatón") & (units.zone == "all") & (units.metric == "crashes")
    ]
    assert float(pedestrians.value.iloc[0]) == 14_110
    assert set(units.year) == {2024}

    involved = tables.read_table_8_1_1()
    one = involved[(involved.vehicles_involved == "Un vehículo") & (involved.zone == "all")]
    assert float(one[one.metric == "crashes"].value.iloc[0]) == 38_810


DRIVER_DEATHS_INTERURBAN = {2014: 836, 2015: 884, 2020: 701, 2024: 935}


def test_driver_victims_every_year_reconciles_with_the_series() -> None:
    victims = tables.read_driver_victims_all()
    assert sorted(victims.year.unique()) == list(tables.TABLE_YEARS)
    assert set(victims.sex.unique()) == {"male", "female", "unknown"}
    assert set(victims.severity.unique()) == set(tables.DRIVER_SEVERITIES)
    deaths = victims[victims.is_total & (victims.severity == "deaths_30d")]
    by_year = deaths[deaths.zone == "interurban"].groupby("year").value.sum()
    for year, expected in DRIVER_DEATHS_INTERURBAN.items():
        assert by_year[year] == expected, year
    series = tables.read_series_road_users()
    expected = (
        series[
            (series.population == "drivers") & (series.severity == "deaths_30d") & series.is_total
        ]
        .set_index(["year", "zone"])
        .value
    )
    actual = deaths.groupby(["year", "zone"]).value.sum()
    for (year, zone), value in actual.items():
        assert value == expected[(year, zone)], (year, zone)
    bands = set(victims.band.unique())
    assert bands == {*tables.agebands.DGT_BANDS, tables.CHILD_BAND, tables.agebands.UNKNOWN}


def test_drivers_involved_every_year() -> None:
    involved = tables.read_drivers_involved_all()
    assert sorted(involved.year.unique()) == list(tables.TABLE_YEARS)
    totals = involved[involved.is_total].groupby(["year", "zone"]).value.sum()
    assert totals[(2024, "interurban")] == 61_428
    assert totals[(2014, "urban")] == 95_943
    assert (involved.value >= 0).all()
    assert not involved.is_total.all()


def test_vehicle_tables_2020_to_2024_and_both_2_2_layouts() -> None:
    units = tables.read_units_by_type_all()
    assert sorted(units.year.unique()) == list(tables.VEHICLE_TABLE_YEARS)
    total_2022 = units[(units.year == 2022) & units.is_total & (units.zone == "all")]
    assert total_2022.set_index("metric").value["crashes"] == 183_078
    assert total_2022.set_index("metric").value["fatal_crashes"] == 2_940
    labels = set(units.unit_type) - {"Total"}
    assert labels == set(vehicles.UNIT_TO_GROUP), labels ^ set(vehicles.UNIT_TO_GROUP)

    single = tables.read_table_2_2(2022)  # one sheet, interurban and urban side by side
    split = tables.read_table_2_2(2024)  # 2.2.I and 2.2.U
    assert set(single.zone) == set(split.zone) == {"interurban", "urban"}
    assert set(single.source_sheet) == {"TABLA 2.2"}
    assert set(split.source_sheet) == {"TABLA 2.2.I", "TABLA 2.2.U"}
    deaths = single[single.is_total & (single.metric == "deaths_30d") & (single.role == "total")]
    assert deaths.set_index("zone").value.to_dict() == {"interurban": 1_273.0, "urban": 473.0}
    roles = single[single.metric == "deaths_30d"].pivot_table(
        index=["zone", "unit_type"], columns="role", values="value", aggfunc="sum"
    )
    assert (roles.driver + roles.passenger + roles.pedestrian == roles.total).all()
    assert set(single.unit_type) - {"Total"} == set(vehicles.UNIT_TO_GROUP)

    victims = tables.read_victims_by_mode_all()
    assert sorted(victims.year.unique()) == list(tables.VEHICLE_TABLE_YEARS)
    totals = (
        victims[victims.is_total & (victims.metric == "deaths_30d") & (victims.role == "total")]
        .set_index(["year", "zone"])
        .value.to_dict()
    )
    assert totals == {
        (2020, "interurban"): 975.0,
        (2020, "urban"): 395.0,
        (2021, "interurban"): 1_116.0,
        (2021, "urban"): 417.0,
        (2022, "interurban"): 1_273.0,
        (2022, "urban"): 473.0,
        (2023, "interurban"): 1_288.0,
        (2023, "urban"): 518.0,
        (2024, "interurban"): 1_291.0,
        (2024, "urban"): 494.0,
    }


def test_vehicle_groups_cover_every_source_once() -> None:
    units = [unit for spec in vehicles.VEHICLE_GROUPS.values() for unit in spec["units"]]
    assert len(units) == len(set(units)) == 22
    columns = [spec["microdata"] for spec in vehicles.VEHICLE_GROUPS.values()]
    assert len(columns) == len(set(columns)) == 12
    assert vehicles.KM_GROUPS == (
        "moped",
        "motorcycle",
        "car",
        "van",
        "light_truck",
        "heavy_truck",
        "bus",
    )
    assert vehicles.group_of("Vehículo articulado") == "heavy_truck"
    with pytest.raises(KeyError):
        vehicles.group_of("Nave espacial")


def test_driver_infractions_every_layout() -> None:
    latest = tables.read_table_6_1(2024, "interurban")
    totals = latest[(latest.item == "total") & (latest.vehicle_group == "total")]
    assert set(totals.block) == set(tables.INFRACTION_BLOCKS)
    assert totals.value.nunique() == 1 and totals.value.iloc[0] == 61_318
    speed = latest[(latest.block == "speed") & (latest.vehicle_group == "total")].set_index("item")
    assert speed.value["speed_infraction"] == 4_473 and speed.value["unknown"] == 30_115
    assert (
        latest[
            (latest.item == "speed_infraction") & (latest.vehicle_group == "motorcycle")
        ].value.iloc[0]
        == 894
    )
    assert "vmp" in set(latest.vehicle_group)

    oldest = tables.read_table_6_1(2014, "interurban")  # .xls, block headings as rows
    assert set(oldest.block) == {"speed", "driver", "door", "lighting", "load", "summary"}
    speed_2014 = oldest[(oldest.block == "speed") & (oldest.vehicle_group == "total")].set_index(
        "item"
    )
    assert speed_2014.value["speed_infraction"] == 7_702 and speed_2014.value["total"] == 58_976
    summary_2014 = oldest[
        (oldest.block == "summary") & (oldest.vehicle_group == "total")
    ].set_index("item")
    assert summary_2014.value["none"] == 25_023 and summary_2014.value["unknown"] == 7_143
    assert "vmp" not in set(oldest.vehicle_group) and "unknown" not in set(oldest.vehicle_group)

    two_columns = tables.read_table_6_1(2015, "urban")  # block in one column, item in the next
    summary_2015 = two_columns[
        (two_columns.block == "summary") & (two_columns.vehicle_group == "total")
    ]
    assert set(summary_2015.item) == {"none", "any", "unknown", "total"}
    prefixed = tables.read_table_6_1(2017, "urban")  # block name prefixed to every label
    driver = prefixed[(prefixed.block == "driver") & (prefixed.vehicle_group == "total")]
    assert set(driver.item) >= {
        "stop_sign",
        "safety_distance",
        "other_infraction",
        "none",
        "unknown",
        "total",
    }

    everything = tables.read_driver_infractions_all()
    assert sorted(everything.year.unique()) == list(tables.TABLE_YEARS)
    per_table = everything[(everything.item == "total") & (everything.vehicle_group == "total")]
    assert per_table.groupby(["year", "zone"]).value.nunique().eq(1).all()
    recent = everything[(everything.year >= 2016) & (everything.vehicle_group == "total")]
    for (year, zone, block), rows in recent.groupby(["year", "zone", "block"]):
        items = rows.set_index("item").value
        expected = items["total"]
        if block == "summary":
            assert items["any"] + items["none"] + items["unknown"] == expected, (year, zone)
        elif block == "speed":
            assert items.drop(index="total").sum() == expected, (year, zone)
        else:
            assert items.drop(index="total").sum() == expected, (year, zone, block)
