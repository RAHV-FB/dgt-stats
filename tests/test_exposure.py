from dgt_stats import io_exposure as exposure

CENSUS_TOTALS = {2023: 27_914_572, 2024: 28_142_470, 2025: 28_472_636}


def test_census_years_match_audit_totals() -> None:
    for year, expected in CENSUS_TOTALS.items():
        frame = exposure.read_census_year(year)
        assert frame.n_drivers.sum() == expected, year
        assert frame.province_code.nunique() == 52
        assert set(frame.sex.unique()) == {"male", "female"}
        assert not frame.duplicated(
            ["province_code", "sex_code", "licence_class", "licence_year"]
        ).any()
        assert (frame.licence_class.str.len() > 0).all()


def test_census_province_table_total_matches_text_file() -> None:
    table = exposure.read_census_province_totals_2025()
    total = table[table.is_total]
    assert len(total) == 1
    assert int(total.total.iloc[0]) == CENSUS_TOTALS[2025]
    provinces = table[~table.is_total]
    assert len(provinces) == 52
    assert provinces.total.sum() == int(total.total.iloc[0])
    assert (provinces.men + provinces.women == provinces.total).all()


def test_km_mean_table_has_35_strata() -> None:
    km = exposure.read_km_mean_2022()
    assert len(km) == 35
    assert set(km.vehicle_type) == set(exposure.KM_VEHICLE_TYPES)
    cars = km[(km.vehicle_type == "Turismo") & (km.age_band == "De 0 a 4 años")].iloc[0]
    assert cars.n_vehicles == 4_807_569
    assert abs(cars.mean_km_year - 21_646.36) < 1e-6
    assert km.vehicle_km.sum() > 0


def test_km_estimated_table_stacks_six_sheets() -> None:
    km = exposure.read_km_estimated_2022()
    assert km.source_sheet.nunique() == 6
    assert km.payload.isna().sum() > 0
    assert (km.year == 2022).all()
    assert km.km_year.min() > 0


def test_census_by_age_text_files_match_census_totals() -> None:
    for year, expected in CENSUS_TOTALS.items():
        frame = exposure.read_census_age_year(year)
        assert frame.n_drivers.sum() == expected, year
        assert frame.province_code.nunique() == 52
        assert set(frame.sex.unique()) == {"male", "female"}
        assert set(frame.band.unique()) == {*exposure.agebands.DGT_BANDS, exposure.agebands.UNKNOWN}
        assert (frame.province_code.str.len() == 2).all()


def test_census_age_tables_cover_2014_to_2023() -> None:
    tables = exposure.read_census_age_tables_all()
    assert sorted(tables.census_year.unique()) == list(exposure.CENSUS_AGE_TABLE_YEARS)
    assert set(tables.sex.unique()) == {"total", "male", "female"}
    totals = tables[tables.sex == "total"].groupby("census_year").n_drivers.sum()
    assert totals[2014] == 26_217_202
    assert totals[2023] == CENSUS_TOTALS[2023]
    by_sex = tables[tables.sex != "total"].groupby("census_year").n_drivers.sum()
    assert (by_sex == totals).all()


def test_census_2023_workbook_and_text_file_agree_within_two_percent() -> None:
    tables = exposure.read_census_age_tables(2023)
    text = exposure.read_census_age_year(2023)
    assert tables[tables.sex == "total"].n_drivers.sum() == text.n_drivers.sum()
    text_sum = text.groupby(["sex", "band"]).n_drivers.sum()
    for row in tables[(tables.sex != "total") & (tables.band != "unknown")].itertuples():
        gap = abs(text_sum[(row.sex, row.band)] - row.n_drivers) / row.n_drivers
        assert gap < 0.02, (row.sex, row.band, gap)


def test_licence_holders_by_age_series() -> None:
    series = exposure.licence_holders_by_age()
    assert sorted(series.year.unique()) == list(range(2014, 2026))
    assert (series[series.year <= 2023].source == "census_tables").all()
    assert (series[series.year >= 2024].source == "census_text").all()
    assert set(series.sex.unique()) == {"total", "male", "female"}
    totals = series[series.sex == "total"].groupby("year").n_drivers.sum()
    assert totals[2025] == CENSUS_TOTALS[2025]
    older = series[(series.sex == "total") & (series.band == "75+")].set_index("year").n_drivers
    assert older[2014] == 1_206_810 and older[2023] == 1_789_835
