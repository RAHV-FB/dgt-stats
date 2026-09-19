import pandas as pd
import pytest

from dgt_stats import io_reports

pytestmark = pytest.mark.skipif(
    not io_reports.SPEED_REPORT_PATH.exists(), reason="speed report PDF not present"
)


@pytest.fixture(scope="module")
def report() -> pd.DataFrame:
    return io_reports.read_speed_report()


def _grid(report: pd.DataFrame, breakdown: str, metric: str, zone: str = "all") -> pd.DataFrame:
    rows = report[
        (report.breakdown == breakdown) & (report.metric == metric) & (report.zone == zone)
    ]
    return rows.pivot(index="category", columns="column", values="value")


def test_executive_summary_numbers_are_reproduced(report: pd.DataFrame) -> None:
    assert (report.region_scope == io_reports.REGION_SCOPE).all()
    road = _grid(report, "road_type", "crashes")
    assert road.loc["Total", "2023"] == 5_070 and road.loc["Vías urbanas", "2023"] == 1_490
    assert road.loc["Total", "2014"] == 6_295
    deaths = _grid(report, "road_type", "deaths")
    assert (
        deaths.loc["Total", "2023"] == 319
        and deaths.loc["Resto de vías interurbanas", "2023"] == 211
    )
    factors = _grid(report, "factors", "crashes")
    assert factors.loc["Velocidad inadecuada", "2023"] == 5_070
    assert factors.loc["Conducción distraída o desatenta", "2023"] == 12_475
    shares = _grid(report, "factors", "crash_share")
    assert shares.loc["Velocidad inadecuada", "2023"] == pytest.approx(0.07)
    assert shares.loc["Velocidad inadecuada", "2014"] == pytest.approx(0.10)
    interurban = _grid(report, "factors", "crashes", "interurban")
    urban = _grid(report, "factors", "crashes", "urban")
    assert interurban.loc["Velocidad inadecuada", "2023"] == 3_580
    assert urban.loc["Velocidad inadecuada", "2023"] == 1_490


def test_rows_add_up_and_grids_are_complete(report: pd.DataFrame) -> None:
    for metric in ("crashes", "deaths", "hospitalised", "non_hospitalised"):
        road = _grid(report, "road_type", metric)
        parts = road.drop(index="Total")
        assert (parts.sum() == road.loc["Total"]).all(), metric
        limits = _grid(report, "speed_limit", metric)
        assert "30 km/h" in limits.index and "Total" in limits.index
        assert (limits.drop(index="Total").sum() == limits.loc["Total"]).all(), metric
    grid = _grid(report, "day_hour", "crashes")
    assert grid.shape == (25, 8)
    weekdays = [c for c in grid.columns if c != "Total"]
    assert set(weekdays) == {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }
    assert (grid[weekdays].sum(axis=1) == grid["Total"]).all()
    assert grid.loc["Total", "Total"] == 57_383
    men = _grid(report, "driver_age_men", "crashes")
    assert men.index[0] == "De 0 a 14 años" and "Subtotal" in men.index
    vehicle = _grid(report, "vehicle", "crashes")
    assert vehicle.loc["VMP", "2014"] != vehicle.loc["VMP", "2014"]  # n.d. is missing
    assert vehicle.loc["VMP", "2023"] == 116
    assert report.table_index.nunique() >= 57
