import pytest

from dgt_stats import io_exposure, io_tables, summaries

pytestmark = pytest.mark.skipif(
    not (
        summaries.PROCESSED_CRASHES.exists()
        and io_tables.staging_path("series_annual").exists()
        and io_exposure.staging_path("conductores_por_edad").exists()
        and io_exposure.staging_path("censo_edad").exists()
    ),
    reason="run `python scripts/ingest.py tables exposure` and `python scripts/build_tables.py` first",
)


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
    # One prefix per page: the six pillars (risk, longrun, season, drivers, speed, factor), the
    # road classes (road), the earlier analyses they keep
    # (q6 vehicles, q8 policy, q9 speed status), the 2024 road-type recoding (q2) and the crash
    # explorer's counts (explore). The severity models are written by scripts/model.py and are not
    # here.
    assert {name.split("_")[0] for name in names} == {
        "explore",
        "risk",
        "road",
        "longrun",
        "season",
        "drivers",
        "speed",
        "factor",
        "q2",
        "q6",
        "q8",
        "q9",
    }
    assert not any(name.startswith("q3_") for name in names)
    assert {"q8_points_calendar_placebo", "q8_points_forecast", "q8_points_transitions"} <= names


def test_model_table_access_is_guarded() -> None:
    with pytest.raises(KeyError):
        summaries.read_model_table("q3_not_a_table")
    assert "q3_adverse_conditions" in summaries.MODEL_TABLES
    if summaries.model_tables_present():
        adverse = summaries.read_model_table("q3_adverse_conditions")
        assert {"fatal", "serious"} == set(adverse.outcome)
