import pandas as pd
import pytest

from dgt_stats import io_microdata as io
from dgt_stats.paths import MICRODATA_YEARS

EXPECTED_ROWS = {
    2016: 102_362,
    2017: 102_233,
    2018: 102_299,
    2019: 104_080,
    2020: 72_959,
    2021: 89_862,
    2022: 97_916,
    2023: 101_306,
    2024: 101_996,
}


def _synthetic(year: int, id_column: str, extra: dict[str, list[object]]) -> pd.DataFrame:
    base = {column: [0, 1, 0] for column in io.CANONICAL_COLUMNS}
    base["ANYO"] = [year] * 3
    base["COD_MUNICIPIO"] = ["01059", "00000", None]
    base["CARRETERA"] = ["A-1", "No inventariada", " "]
    base["CARRETERA_CRUCE"] = ["", None, "N-II"]
    base["CONDICION_VIENTO"] = [None, ".", 1]
    base["KM"] = [12.5, None, 3]
    base.pop("TOT_VMP_MU24H")
    base.pop("TOT_VMP_MU30DF")
    base[id_column] = base.pop("ID_ACCIDENTE")
    base.update(extra)
    return pd.DataFrame(base)


def test_harmonise_2016_and_2020_layouts_give_one_schema() -> None:
    old = io.harmonise(_synthetic(2016, "SECUENCIAL", {}), 2016)
    mid = io.harmonise(
        _synthetic(2020, "SECUENCIAL", {"TOT_VMP_MU24H": [0, 0, 1], "TOT_VMP_MU30DF": [0, 1, 1]}),
        2020,
    )
    new = io.harmonise(_synthetic(2024, "ID_ACCIDENTE", {"TOT_VMP_MU30DF": [0, 0, 0]}), 2024)
    for frame in (old, mid, new):
        assert list(frame.columns) == list(io.CANONICAL_COLUMNS)
    assert old.dtypes.equals(mid.dtypes)
    assert mid.dtypes.equals(new.dtypes)
    assert old["TOT_VMP_MU30DF"].isna().all()
    assert new["TOT_VMP_MU24H"].isna().all()
    assert mid["TOT_VMP_MU24H"].sum() == 1


def test_harmonise_cleans_text_and_numbers() -> None:
    frame = io.harmonise(_synthetic(2016, "SECUENCIAL", {}), 2016)
    assert str(frame["ID_ACCIDENTE"].dtype) == "int32"
    assert str(frame["TIPO_VIA"].dtype) == "Int16"
    assert str(frame["KM"].dtype) == "float32"
    assert list(frame["COD_MUNICIPIO"].fillna("<NA>")) == ["01059", "00000", "<NA>"]
    assert list(frame["CARRETERA"].fillna("<NA>")) == ["A-1", "No inventariada", "<NA>"]
    assert list(frame["CARRETERA_CRUCE"].fillna("<NA>")) == ["<NA>", "<NA>", "N-II"]
    assert list(frame["CONDICION_VIENTO"].fillna("<NA>")) == ["<NA>", ".", "1"]


def test_harmonise_rejects_unknown_columns() -> None:
    frame = _synthetic(2016, "SECUENCIAL", {"EXTRA": [1, 2, 3]})
    with pytest.raises(ValueError, match="unexpected columns"):
        io.harmonise(frame, 2016)


def test_harmonise_rejects_wrong_year() -> None:
    with pytest.raises(ValueError, match="ANYO"):
        io.harmonise(_synthetic(2016, "SECUENCIAL", {}), 2017)


@pytest.mark.skipif(
    not io.all_years_path().exists(), reason="run `python scripts/ingest.py microdata` first"
)
def test_interim_row_counts_match_audit() -> None:
    frame = io.read_all()
    assert list(frame.columns) == list(io.CANONICAL_COLUMNS)
    counts = frame.groupby("ANYO").size().to_dict()
    assert counts == EXPECTED_ROWS
    assert set(counts) == set(MICRODATA_YEARS)
    assert not frame.duplicated(["ANYO", "ID_ACCIDENTE"]).any()
