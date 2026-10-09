"""The crash explorer's table (``explore_dgt_crashes.csv``) and the data file the page reads.

The table must reconcile exactly with DGT's published yearly totals, its road-user deaths must
add up to its deaths, it must hold no empty cell, and the JSON the page loads must decode back to
the table row for row.
"""

from __future__ import annotations

import pandas as pd
import pytest
from scipy import stats

from dgt_stats import crash_cells, derive, features, labels, regions
from dgt_stats.paths import DGT_PROCESSED_CRASHES, TABLES_DIR

TABLE = TABLES_DIR / f"{crash_cells.NAME}.csv"
needs_table = pytest.mark.skipif(not TABLE.exists(), reason="run `python scripts/model.py` first")


@pytest.fixture(scope="module")
def table() -> pd.DataFrame:
    return pd.read_csv(TABLE)


def test_every_province_belongs_to_one_community() -> None:
    assert sorted(regions.COMMUNITY_BY_PROVINCE) == list(range(1, 53))
    assert len(regions.COMMUNITIES) == 19
    every = [code for codes in regions.COMMUNITIES.values() for code in codes]
    assert len(every) == len(set(every)) == 52
    # The four Catalan provinces as the rest of the analysis names them.
    assert {str(code) for code in regions.COMMUNITIES["Catalonia"]} == set(
        features.CATALAN_PROVINCES
    )
    assert regions.COMMUNITY_BY_PROVINCE[28] == "Madrid"
    assert regions.COMMUNITY_BY_PROVINCE[48] == "Basque Country"
    out = regions.community(pd.Series([8, 41, 52], dtype="Int16"))
    assert list(out) == ["Catalonia", "Andalusia", "Melilla"]
    with pytest.raises(ValueError, match="53"):
        regions.community(pd.Series([1, 53]))


def test_the_groupings_cover_every_code() -> None:
    assert set(crash_cells.ROAD_TYPES) == set(derive.ROAD_GROUP_BY_TYPE.values())
    assert sorted(crash_cells.CRASH_TYPE_BY_CODE) == list(range(1, 21))
    run_off = [
        code for code, name in crash_cells.CRASH_TYPE_BY_CODE.items() if name == "Run-off road"
    ]
    assert run_off == list(range(11, 20))
    # Every other crash type keeps DGT's own label.
    for code, name in crash_cells.CRASH_TYPE_BY_CODE.items():
        if code not in run_off:
            assert name == labels.ENGLISH["TIPO_ACCIDENTE"][str(code)]
    grouped = [c for _, columns in crash_cells.ROAD_USERS.values() for c in columns]
    assert sorted(grouped) == sorted(labels.ROAD_USER_TYPES)


def _crashes(**columns) -> pd.DataFrame:
    base = {
        "ANYO": [2020, 2020, 2020, 2021],
        "COD_PROVINCIA": [8, 17, 28, 28],
        "road_group": ["urban_street", "urban_street", pd.NA, "motorway"],
        "TIPO_ACCIDENTE": pd.array([7, 7, 12, pd.NA], dtype="Int16"),
        "fatal": [True, False, True, False],
        "n_deaths": [2, 0, 1, 0],
    }
    base.update({column: [0, 0, 0, 0] for column in labels.ROAD_USER_TYPES})
    base["TOT_PEAT_MU30DF"] = [2, 0, 0, 0]
    base["TOT_VMP_MU30DF"] = pd.array([pd.NA, pd.NA, 1, 0], dtype="Int16")
    base.update(columns)
    return pd.DataFrame(base)


def test_cells_add_up_crashes_and_keep_unrecorded_codes() -> None:
    out = crash_cells.crash_cells(_crashes())
    assert list(out.columns) == [*crash_cells.DIMENSIONS, *crash_cells.COUNTS]
    first = out.iloc[0]
    # Barcelona and Girona fall in one Catalan cell; a missing code counts as not recorded.
    assert tuple(first[list(crash_cells.DIMENSIONS)]) == (
        2020,
        "Catalonia",
        "Urban streets",
        "Pedestrian struck",
    )
    assert (first.injury_crashes, first.fatal_crashes, first.deaths_30d) == (2, 1, 2)
    assert first.deaths_pedestrians == 2
    madrid = out[(out.community == "Madrid") & (out.year == 2020)].iloc[0]
    assert (madrid.road_type, madrid.crash_type) == ("Not recorded", "Run-off road")
    assert madrid.deaths_other == 1
    later = out[out.year == 2021].iloc[0]
    assert (later.road_type, later.crash_type) == ("Motorways", "Not recorded")
    assert len(out) == 3 and out.injury_crashes.sum() == 4


def test_cells_refuse_a_code_with_no_group_and_deaths_that_do_not_add_up() -> None:
    with pytest.raises(ValueError, match="TIPO_ACCIDENTE"):
        crash_cells.crash_cells(_crashes(TIPO_ACCIDENTE=pd.array([7, 7, 12, 99], dtype="Int16")))
    with pytest.raises(ValueError, match="add up"):
        crash_cells.crash_cells(_crashes(n_deaths=[2, 0, 1, 1]))


@needs_table
def test_the_table_has_one_row_per_non_empty_cell(table: pd.DataFrame) -> None:
    assert list(table.columns) == [*crash_cells.DIMENSIONS, *crash_cells.COUNTS]
    assert not table.duplicated(list(crash_cells.DIMENSIONS)).any()
    assert (table.injury_crashes >= 1).all()
    assert (table[list(crash_cells.COUNTS)] >= 0).all().all()
    assert (table.fatal_crashes <= table.injury_crashes).all()
    assert (table.deaths_30d >= table.fatal_crashes).all()
    assert table.year.min() == 2016
    assert list(table.year.drop_duplicates()) == list(range(2016, table.year.max() + 1))
    assert set(table.community) == set(regions.COMMUNITIES)
    assert set(table.road_type) <= {*crash_cells.ROAD_TYPES.values(), crash_cells.NOT_RECORDED}
    assert set(table.crash_type) <= {*crash_cells.CRASH_TYPES, crash_cells.NOT_RECORDED}


@needs_table
def test_the_table_reconciles_with_the_published_yearly_totals(table: pd.DataFrame) -> None:
    published = pd.read_csv(TABLES_DIR / "q1_annual_headline.csv").set_index("year")
    yearly = table.groupby("year")[["injury_crashes", "deaths_30d"]].sum()
    assert set(yearly.index) <= set(published.index)
    for year, row in yearly.iterrows():
        assert row.injury_crashes == published.loc[year, "crashes"], year
        assert row.deaths_30d == published.loc[year, "deaths_30d"], year


@needs_table
def test_road_user_deaths_add_up_to_the_deaths(table: pd.DataFrame) -> None:
    by_user = table[list(crash_cells.ROAD_USERS)].sum(axis=1)
    assert (by_user == table.deaths_30d).all()


@needs_table
@pytest.mark.skipif(not DGT_PROCESSED_CRASHES.exists(), reason="no processed DGT records")
def test_the_committed_table_is_what_the_records_give(table: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(crash_cells.crash_cells(), table, check_dtype=False)


@needs_table
def test_the_data_file_decodes_back_to_the_table(table: pd.DataFrame) -> None:
    from dgt_stats.site import tool_crashes

    payload = tool_crashes.data_files()[tool_crashes.DATA_FILE]
    lists = [payload["years"], payload["regions"], payload["roads"], payload["types"]]
    assert payload["regions"] == [c for c in regions.COMMUNITIES if c in set(table.community)]
    assert payload["regions"][payload["catalonia"]] == "Catalonia"
    assert payload["users"] == [label for label, _ in crash_cells.ROAD_USERS.values()]
    decoded = pd.DataFrame(
        [[lists[i][row[i]] for i in range(4)] + row[4:] for row in payload["rows"]],
        columns=[*crash_cells.DIMENSIONS, *crash_cells.COUNTS],
    )
    pd.testing.assert_frame_equal(decoded, table, check_dtype=False)
    assert all(row[4] > 0 for row in payload["rows"])
    assert payload["z"] == pytest.approx(stats.norm.ppf(0.975), abs=1e-15)
    assert payload["minSupport"] == tool_crashes.MIN_SUPPORT
    # The years of the coding breaks it names.
    breaks = payload["breaks"]
    assert (
        breaks["dualUntil"] < breaks["otherFrom"] and breaks["junction"][0] <= breaks["junction"][1]
    )
    assert breaks["junction"][-1] <= table.year.max()


@needs_table
def test_the_page_describes_the_years_the_table_covers(table: pd.DataFrame) -> None:
    from dgt_stats.site import tool_crashes

    coverage = tool_crashes.describe()["coverage"]
    assert f"{table.year.min()}–{table.year.max()}" in coverage
