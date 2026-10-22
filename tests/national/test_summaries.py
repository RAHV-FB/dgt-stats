import pytest

from dgt_stats.drivers import driver_risk
from dgt_stats.national import io_exposure, io_tables, summaries

pytestmark = pytest.mark.skipif(
    not (
        summaries.PROCESSED_CRASHES.exists()
        and io_tables.staging_path("series_annual").exists()
        and io_exposure.staging_path("conductores_por_edad").exists()
        and io_exposure.staging_path("censo_edad").exists()
    ),
    reason="run `python scripts/run.py national.ingest` and `python scripts/run.py national.process` first",
)


def test_annual_headline_matches_yearbook() -> None:
    headline = summaries.annual_headline()
    row = headline[headline.year == 2024].iloc[0]
    assert row.crashes == 101_996
    assert row.deaths_30d == 1_785
    assert row.hospitalised_30d == 9_561
    base = headline[headline.year == summaries.BASE_YEAR].iloc[0]
    assert base.crashes_index == 100.0 and base.deaths_30d_index == 100.0
    assert headline.year.min() == 1993 and len(headline) == 32


def test_night_share_by_year_and_zone() -> None:
    night = summaries.night_share_by_year_zone()
    assert set(night.zone) == {"interurban", "urban"}
    assert ((night.night_crash_share > 0) & (night.night_crash_share < 1)).all()
    # Darkness holds a larger share of deaths than of crashes in every year and zone, which is the
    # one sentence the context page draws from this table.
    assert (night.night_death_share > night.night_crash_share).all()


def test_other_road_by_period_splits_the_pooled_row() -> None:
    other = summaries.other_road_by_period().set_index("period")
    assert list(other.index) == ["2016-2023", "2024"]
    assert (
        other.crashes.sum() == summaries.read_crashes(["road_group"]).road_group.eq("other").sum()
    )
    assert other.share_of_row.sum() == pytest.approx(1, abs=1e-3)
    assert other.loc["2024", "share_of_row"] == pytest.approx(0.3945, abs=5e-4)
    assert other.loc["2024", "street_share"] > 0.8 > other.loc["2016-2023", "street_share"]
    # the 2024 "other" row is mostly urban street and much less deadly than the 2016-2023 one
    assert other.loc["2016-2023", "fatal_share"] > 2 * other.loc["2024", "fatal_share"]
    assert (other.fatal_share == (other.fatal_crashes / other.crashes).round(4)).all()


def test_registry_holds_only_tables_the_site_or_a_figure_uses() -> None:
    names = set(summaries.SUMMARIES)
    # The withdrawn forecast's tables are rebuilt only on request (``scripts/run.py national.withdrawn``).
    assert {name.split("_")[0] for name in summaries.WITHDRAWN_SUMMARIES} == {"forecast"}
    assert not names & set(summaries.WITHDRAWN_SUMMARIES)
    # One prefix per page: the five national pillars (risk, longrun, season, speed, factor), the
    # road classes (road), the earlier analyses they keep (q6 vehicles, q8 policy, q9 speed
    # status), the context tables (q1, q2) and the data page's missing-values chart
    # (missingness). The association analysis is written by national.associations and the
    # driver tables by drivers.tables (``driver_risk.TABLES``); neither is here.
    assert {name.split("_")[0] for name in names} == {
        "missingness",
        "risk",
        "road",
        "longrun",
        "season",
        "speed",
        "factor",
        "q1",
        "q2",
        "q6",
        "q8",
        "q9",
    }
    assert not any(name.startswith("q3_") for name in names)
    assert "q4_province_rates" not in names  # the province ranking was dropped, not hidden
    assert not names & set(driver_risk.TABLES)
    assert {"q7_km_rates", "q7_km_ratio", "q7_denominator_contrast"} <= set(driver_risk.TABLES)
    assert {"q8_points_calendar_placebo", "q8_points_forecast", "q8_points_transitions"} <= names


def test_model_table_access_is_guarded() -> None:
    with pytest.raises(KeyError):
        summaries.read_model_table("q3_not_a_table")
    assert "q3_adverse_conditions" in summaries.MODEL_TABLES
    if summaries.model_tables_present():
        adverse = summaries.read_model_table("q3_adverse_conditions")
        assert {"fatal", "serious"} == set(adverse.outcome)
