import pandas as pd
import pytest

from dgt_stats import io_microdata, validate
from dgt_stats.paths import MICRODATA_YEARS, TABLE_YEARS

pytestmark = pytest.mark.skipif(
    not io_microdata.all_years_path().exists(),
    reason="run `python scripts/ingest.py all` first",
)


@pytest.fixture(scope="module")
def results() -> pd.DataFrame:
    return validate.run_checks()


FAMILIES = {
    "census_2025",
    "census_age_2023",
    "code_domain",
    "driver_deaths",
    "row_count",
    "speed_report_scope",
    "table_1_1_province",
    "table_2_2_deaths",
    "table_2_3_vehicles",
    "table_3_1_month",
    "table_6_1_drivers",
    "victim_total",
}


def test_every_check_family_is_present_and_every_check_passes(results: pd.DataFrame) -> None:
    # A family that vanished or came back empty would otherwise pass unnoticed.
    sizes = results.groupby("check").size()
    assert set(sizes.index) == FAMILIES
    assert (sizes > 0).all()
    failed = results[~results.passed]
    assert failed.empty, failed.to_string()


def test_row_counts_cover_every_microdata_year(results: pd.DataFrame) -> None:
    rows = results[results.check == "row_count"]
    assert sorted(rows.year) == list(MICRODATA_YEARS)


def test_census_checks_cover_every_province(results: pd.DataFrame) -> None:
    census = results[results.check == "census_2025"]
    assert len(census) >= 52
    assert census.passed.all()


def test_missingness_profile_shape() -> None:
    profile = validate.missingness_profile(io_microdata.read_all())
    assert set(profile.year) == set(range(2016, 2025))
    assert len(profile) == 9 * len(validate.PROFILE_COLUMNS)
    assert ((profile.share_observed >= 0) & (profile.share_observed <= 1)).all()
    weather_2016 = profile[(profile.year == 2016) & (profile.column == "CONDICION_METEO")].iloc[0]
    assert abs(weather_2016.share_not_specified - 0.10) < 0.01


def test_province_name_normalisation() -> None:
    assert validate._normalise_province("Balears, Illes") == validate._normalise_province(
        "Balears (Illes)"
    )
    assert validate._normalise_province("Coruña, A") == "coruña (a)"


def test_driver_deaths_cover_every_year_and_zone(results: pd.DataFrame) -> None:
    rows = results[results.check == "driver_deaths"]
    assert len(rows) == len(TABLE_YEARS) * 3
    assert rows.passed.all()
