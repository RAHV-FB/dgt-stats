import pandas as pd
import pytest

from dgt_stats import factors, io_reports
from dgt_stats.paths import INTERIM_DATA_DIR


def _shares(values: dict[int, tuple[float, float]]) -> pd.DataFrame:
    rows = [
        {"year": y, "zone": "urban", "factor": "Alcohol", "crashes": c, "all_crashes": t}
        for y, (c, t) in values.items()
    ]
    frame = pd.DataFrame(rows)
    frame["share"] = frame.crashes / frame.all_crashes
    frame["zone_label"] = "Urban streets"
    return frame


def test_break_rule_splits_runs_at_jumps_and_at_untestable_changes(monkeypatch) -> None:
    # A smooth series with one 60 % jump in 2016, then counts that fall below the testable minimum.
    values = {
        2014: (1000, 40000),
        2015: (1020, 40000),
        2016: (1640, 40000),
        2017: (1660, 40000),
        2018: (150, 40000),
        2019: (160, 40000),
    }
    monkeypatch.setattr(factors, "factor_shares", lambda: _shares(values))
    changes = factors.factor_consistency().set_index("to_year")
    assert not changes.loc[2015, "is_break"]
    assert changes.loc[2016, "is_break"] and changes.loc[2016, "jump"]
    assert changes.loc[2018, "is_break"] and changes.loc[2018, "too_few"]
    windows = factors.comparable_windows()
    runs = list(zip(windows.first_year, windows.last_year))
    assert runs == [(2014, 2015), (2016, 2017), (2018, 2018), (2019, 2019)]
    assert windows.set_index("first_year").loc[2018, "too_few"]


def test_severity_row_splits_speed_from_the_rest() -> None:
    row = factors._severity_row(2020, "urban", 1000, 50, 21000, 150, "test")
    assert row["other_crashes"] == 20000 and row["other_deaths"] == 100
    assert row["speed_deaths_per_100"] == pytest.approx(5.0)
    assert row["other_deaths_per_100"] == pytest.approx(0.5)
    assert row["rate_ratio"] == pytest.approx(10.0)
    assert row["ratio_low"] < 10.0 < row["ratio_high"]


pytestmark_data = pytest.mark.skipif(
    not (
        io_reports.SPEED_REPORT_INTERIM.exists()
        and (INTERIM_DATA_DIR.parent / "processed" / "accidentes.parquet").exists()
    ),
    reason="run `python scripts/ingest.py all` and `python scripts/build_tables.py` first",
)


@pytestmark_data
def test_scoped_microdata_reproduce_the_report_totals() -> None:
    micro = factors.scoped_microdata_totals()
    report = factors.report_totals().set_index(["year", "zone"])
    by_year = micro.groupby("year")[["crashes", "deaths"]].sum()
    for year in sorted(set(micro.year) & set(report.index.get_level_values("year"))):
        assert by_year.loc[year, "crashes"] == report.loc[(year, "all"), "crashes"]
        assert by_year.loc[year, "deaths"] == report.loc[(year, "all"), "deaths"]


@pytestmark_data
def test_speed_severity_is_higher_everywhere_and_adjustment_shrinks_it() -> None:
    pooled = factors.speed_severity_pooled().set_index("road_type")
    detail = pooled.drop(index="adjusted")
    assert (detail.rate_ratio > 1).all()
    adjusted = pooled.loc["adjusted"]
    # Speed crashes concentrate on deadlier roads, so allowing for road type lowers the ratio.
    assert adjusted.rate_ratio < adjusted.crude_ratio
    assert adjusted.ratio_low > 1


@pytestmark_data
def test_known_recording_breaks_are_found() -> None:
    changes = factors.factor_consistency()
    breaks = changes[changes.jump]
    urban_distraction = breaks[
        (breaks.zone == "urban") & (breaks.factor == "Distraction or inattention")
    ]
    assert set(urban_distraction.to_year) == {2016, 2019}
    interurban_alcohol = changes[(changes.zone == "interurban") & (changes.factor == "Alcohol")]
    assert not interurban_alcohol.is_break.any()
