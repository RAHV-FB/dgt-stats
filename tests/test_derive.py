import pandas as pd

from dgt_stats import codes, derive, labels
from dgt_stats.io_microdata import CANONICAL_COLUMNS


def _frame() -> pd.DataFrame:
    base = {column: [0] * 6 for column in CANONICAL_COLUMNS}
    base.update(
        {
            "ANYO": [2024] * 6,
            "HORA": [0, 6, 7, 13, 20, None],
            "DIA_SEMANA": [1, 5, 5, 6, 7, 3],
            "ZONA_AGRUPADA": [1, 1, 2, 2, 1, 2],
            "TIPO_VIA": [1, 3, 6, 9, 14, None],
            "CONDICION_ILUMINACION": [1, 4, 5, 6, 2, 999],
            "CONDICION_METEO": [1, 7, 999, 998, None, 3],
            "TOTAL_MU30DF": [0, 1, 0, 2, 0, 0],
            "TOTAL_HG30DF": [0, 0, 1, 0, 0, 0],
            "TOT_PEAT_MU30DF": [0, 1, 0, 0, 0, 0],
            "TOT_MOTO_MU30DF": [0, 0, 0, 1, 0, 0],
            "TOT_VMP_MU30DF": [None, None, None, 1, None, None],
        }
    )
    frame = pd.DataFrame(base)
    for column in ("TOT_VMP_MU30DF", "HORA", "TIPO_VIA", "CONDICION_METEO"):
        frame[column] = frame[column].astype("Int16")
    return frame


def test_add_fields_outcomes_and_groupings() -> None:
    out = derive.add_fields(_frame())
    assert list(out.fatal) == [False, True, False, True, False, False]
    assert list(out.serious) == [False, True, True, True, False, False]
    assert list(out.n_vulnerable_deaths) == [0, 1, 0, 2, 0, 0]
    assert list(out.zone) == ["interurban", "interurban", "urban", "urban", "interurban", "urban"]
    assert list(out.road_group.fillna("<NA>")) == [
        "motorway",
        "dual_carriageway",
        "conventional",
        "urban_street",
        "other",
        "<NA>",
    ]
    assert list(out.hour_band.fillna("<NA>")) == [
        "00-06",
        "00-06",
        "07-09",
        "10-13",
        "20-23",
        "<NA>",
    ]
    assert list(out.night) == [False, True, True, True, False, False]
    assert list(out.weekend) == [False, False, False, True, True, False]


def test_add_fields_keeps_the_canonical_columns_first() -> None:
    out = derive.add_fields(_frame())
    for column in derive.DERIVED_COLUMNS:
        assert column in out.columns, column
    assert list(out.columns[: len(CANONICAL_COLUMNS)]) == list(CANONICAL_COLUMNS)
    assert len(out.columns) == len(CANONICAL_COLUMNS) + len(derive.DERIVED_COLUMNS)


def test_every_crash_type_code_has_an_english_label() -> None:
    dictionary = codes.load_dictionary()
    spanish = {code for code in dictionary["TIPO_ACCIDENTE"] if code not in {"", "998", "999"}}
    assert spanish == set(labels.ENGLISH["TIPO_ACCIDENTE"])


def test_road_user_types_cover_every_death_column() -> None:
    death_columns = {c for c in CANONICAL_COLUMNS if c.startswith("TOT_") and c.endswith("_MU30DF")}
    assert set(labels.ROAD_USER_TYPES) == death_columns
    assert set(labels.VULNERABLE_TYPES) <= death_columns
