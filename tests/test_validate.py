import pandas as pd
import pytest

from dgt_stats import io_microdata, validate

pytestmark = pytest.mark.skipif(
    not io_microdata.all_years_path().exists(),
    reason="run `python scripts/ingest.py all` first",
)


@pytest.fixture(scope="module")
def results() -> pd.DataFrame:
    return validate.run_checks()


def test_every_check_family_is_present_and_complete(results: pd.DataFrame) -> None:
    # The published count of checks: a family that shrank would otherwise pass unnoticed.
    assert len(results) == 482
    assert results.groupby("check").size().to_dict() == {
        "census_2025": 53,
        "census_age_2023": 15,
        "code_domain": 33,
        "driver_deaths": 33,
        "row_count": 9,
        "speed_report_scope": 48,
        "table_1_1_province": 104,
        "table_2_2_deaths": 60,
        "table_2_3_vehicles": 5,
        "table_3_1_month": 24,
        "table_6_1_drivers": 44,
        "unique_key": 9,
        "victim_total": 45,
    }


def test_reconciliation_checks_pass_exactly(results: pd.DataFrame) -> None:
    exact = results[~results.check.isin(["census_2025", "census_age_2023"])]
    failed = exact[~exact.passed]
    assert failed.empty, failed.to_string()


def test_census_within_tolerance(results: pd.DataFrame) -> None:
    census = results[results.check == "census_2025"]
    assert len(census) == 53
    failed = census[~census.passed]
    assert failed.empty, failed.to_string()


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


def test_census_age_within_tolerance(results: pd.DataFrame) -> None:
    rows = results[results.check == "census_age_2023"]
    assert len(rows) == 15
    failed = rows[~rows.passed]
    assert failed.empty, failed.to_string()


def test_driver_deaths_cover_every_year_and_zone(results: pd.DataFrame) -> None:
    rows = results[results.check == "driver_deaths"]
    assert len(rows) == 11 * 3
    assert rows.passed.all()
