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
