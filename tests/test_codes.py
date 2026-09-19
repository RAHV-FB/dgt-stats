import pandas as pd

from dgt_stats import codes


def test_dictionary_has_every_coded_column() -> None:
    dictionary = codes.load_dictionary()
    assert len(dictionary) == 33
    for column in codes.CATEGORICAL_COLUMNS:
        assert column in dictionary, column
    for column in codes.NOT_CODE_SHEETS:
        assert column not in dictionary


def test_dictionary_keeps_special_codes() -> None:
    assert codes.labels_for("CONDICION_VIENTO")["."] == "No se aprecia viento fuerte"
    assert codes.labels_for("ISLA")[""] == "No aplica"
    assert codes.labels_for("ACERA")["998"] == "No aplica"
    assert codes.labels_for("TITULARIDAD_VIA")["999"] == "Sin especificar"


def test_decode_maps_codes_and_keeps_unknown_values() -> None:
    out = codes.decode("TIPO_VIA", pd.Series([9, 999, None, 42, "6"], dtype="object"))
    assert out.iloc[0] == "Calle"
    assert out.iloc[1] == "999"
    assert pd.isna(out.iloc[2])
    assert out.iloc[3] == "42"
    assert out.iloc[4] == "Carretera Convencional de calzada única"


def test_decode_accepts_nullable_integer_series() -> None:
    values = pd.Series([1, 7, pd.NA], dtype="Int16")
    out = codes.decode("CONDICION_METEO", values)
    assert out.iloc[0] == "Despejado"
    assert out.iloc[1] == "Se desconoce"
    assert pd.isna(out.iloc[2])


def test_status_distinguishes_every_missing_state() -> None:
    values = pd.Series([1, 7, 999, 998, None], dtype="object")
    out = codes.status("CONDICION_METEO", values)
    assert list(out) == ["observed", "unknown", "not_specified", "not_applicable", "empty"]
    assert out.name == "status_CONDICION_METEO"
    assert list(out.cat.categories) == list(codes.STATUS_LEVELS)


def test_status_without_explicit_unknown_code() -> None:
    out = codes.status("TIPO_VIA", pd.Series([4, 999]))
    assert list(out) == ["observed", "not_specified"]


def test_allowed_codes_include_missing_markers() -> None:
    allowed = codes.allowed_codes("ZONA")
    assert allowed == {"1", "2", "3", "4", "998", "999"}
