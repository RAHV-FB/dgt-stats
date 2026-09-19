from dgt_stats import agebands, io_population


def test_extract_shape_and_codes() -> None:
    frame = io_population.read_population()
    assert len(frame) == 149_460
    assert frame.province_code.nunique() == 53  # 52 provinces + ES
    assert set(frame.sex.unique()) == {"male", "female", "total"}
    assert frame.year.min() == 2002 and frame.year.max() == 2025


def test_national_65_plus_matches_dgt_report() -> None:
    groups = io_population.population(2023, reference="1 January")
    older = groups[groups.age_low >= 65].population.sum()
    assert older == 9_687_776


def test_provinces_sum_to_national() -> None:
    provinces = io_population.population_by_province(2024)
    national = provinces[provinces.province_code == io_population.NATIONAL_CODE].population.iloc[0]
    assert provinces[provinces.province_code != io_population.NATIONAL_CODE].population.sum() == (
        national
    )
    assert len(provinces) == 53


def test_bands_cover_everyone_from_15() -> None:
    bands = io_population.population_by_band(2024)
    assert bands.band.tolist() == list(agebands.ANALYSIS_BANDS)
    groups = io_population.population(2024)
    assert bands.population.sum() == groups[groups.age_low >= 15].population.sum()
    older_bands = {"65-69": (65, 69), "70-74": (70, 74), "75+": (75, None)}
    older = io_population.population_by_band(2024, older_bands)
    assert older.population.sum() == groups[groups.age_low >= 65].population.sum()


def test_province_band_selection() -> None:
    older = io_population.population_by_province(2024, ages="75+")
    national = older[older.province_code == io_population.NATIONAL_CODE].population.iloc[0]
    groups = io_population.population(2024)
    assert national == groups[groups.age_low >= 75].population.sum()
