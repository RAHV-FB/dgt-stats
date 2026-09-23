import pytest

from dgt_stats import io_exposure, io_tables, summaries

pytestmark = pytest.mark.skipif(
    not (
        summaries.PROCESSED_CRASHES.exists()
        and io_tables.interim_path("series_annual").exists()
        and io_exposure.interim_path("conductores_por_edad").exists()
        and io_exposure.interim_path("censo_edad").exists()
    ),
    reason="run `python scripts/ingest.py tables exposure` and `python scripts/build_tables.py` first",
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


def test_annual_by_zone_sums_to_yearbook() -> None:
    by_zone = summaries.annual_by_zone()
    year = by_zone[by_zone.year == 2024].set_index("zone")
    assert year.loc["interurban", "crashes"] == 35_772
    assert year.loc["urban", "crashes"] == 66_224
    assert year.loc["interurban", "deaths_30d"] + year.loc["urban", "deaths_30d"] == 1_785


def test_night_share_by_year_and_zone() -> None:
    night = summaries.night_share_by_year_zone()
    assert set(night.zone) == {"interurban", "urban"}
    assert ((night.night_crash_share > 0) & (night.night_crash_share < 1)).all()
    # Darkness holds a larger share of deaths than of crashes in every year and zone, which is the
    # one sentence the context page draws from this table.
    assert (night.night_death_share > night.night_crash_share).all()


def test_deaths_by_road_user_reconciles() -> None:
    users = summaries.deaths_by_road_user()
    assert users[users.year == 2024].deaths_30d.sum() == 1_785
    # The road-user split of each year and zone adds up to the zone table, not just to itself.
    zone_totals = summaries.annual_by_zone().set_index(["year", "zone"]).deaths_30d
    assert users.groupby(["year", "zone"]).deaths_30d.sum().eq(zone_totals).all()


def test_licence_share_by_age() -> None:
    share = summaries.licence_share_by_age()
    assert set(share.sex.unique()) == {"total", "male", "female"}
    older = share[(share.year == 2024) & (share.sex == "female") & (share.band == "75+")].iloc[0]
    assert older.licence_share < 0.4
    men = share[(share.year == 2024) & (share.sex == "male") & (share.band == "75+")].iloc[0]
    assert men.licence_share > 2 * older.licence_share


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
    # earlier analyses they keep (q6 vehicles, q7 age, q8 policy, q9 speed status) and the context
    # tables (q1, q2). The severity models are written by scripts/model.py and are not here.
    assert {name.split("_")[0] for name in names} == {
        "risk",
        "longrun",
        "season",
        "drivers",
        "speed",
        "factor",
        "q1",
        "q2",
        "q6",
        "q7",
        "q8",
        "q9",
    }
    assert not any(name.startswith("q3_") for name in names)
    assert "q4_province_rates" not in names  # the province ranking was dropped, not hidden
    assert {"q7_km_rates", "q7_km_ratio", "q7_denominator_contrast"} <= names
    assert {"q8_points_calendar_placebo", "q8_points_forecast", "q8_points_transitions"} <= names


def test_model_table_access_is_guarded() -> None:
    with pytest.raises(KeyError):
        summaries.read_model_table("q3_not_a_table")
    assert "q3_adverse_conditions" in summaries.MODEL_TABLES
    if summaries.model_tables_present():
        adverse = summaries.read_model_table("q3_adverse_conditions")
        assert {"fatal", "serious"} == set(adverse.outcome)
