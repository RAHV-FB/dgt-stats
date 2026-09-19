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


def test_every_check_family_present(results: pd.DataFrame) -> None:
    assert set(results.check) == {
        "row_count",
        "victim_total",
        "table_1_1_province",
        "table_3_1_month",
        "unique_key",
        "code_domain",
        "census_2025",
    }


def test_reconciliation_checks_pass_exactly(results: pd.DataFrame) -> None:
    exact = results[results.check != "census_2025"]
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
