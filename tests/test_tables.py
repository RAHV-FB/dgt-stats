import pytest

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

    involved = tables.read_table_8_1_1()
    one = involved[(involved.vehicles_involved == "Un vehículo") & (involved.zone == "all")]
    assert float(one[one.metric == "crashes"].value.iloc[0]) == 38_810
