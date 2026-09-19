import pytest

from dgt_stats import agebands


@pytest.mark.parametrize(
    "label, expected",
    [
        ("De 15 a 17 años", (15, 17)),
        ("15 a 17\naños", (15, 17)),
        ("De 0 a 1", (0, 1)),
        ("Más de 74 años", (75, None)),
        ("Más de\n74 años", (75, None)),
        ("De 75 o más", (75, None)),
        ("Hasta 14 años", (0, 14)),
        ("65 y más años", (65, None)),
        ("90 y más años", (90, None)),
        ("0\\14 años", (0, 14)),
        ("Todas las edades", (0, None)),
        ("Se desconoce", None),
        ("Se\ndesconoce", None),
        ("Desconocido", None),
        ("No especificada", None),
    ],
)
def test_parse_age_label(label: str, expected: tuple[int, int | None] | None) -> None:
    assert agebands.parse_age_label(label) == expected


def test_parse_age_label_rejects_unknown_text() -> None:
    with pytest.raises(ValueError):
        agebands.parse_age_label("Total")


def test_band_for_nested_and_open_ended() -> None:
    assert agebands.band_for(15, 17) == "15-24"
    assert agebands.band_for(21, 24) == "15-24"
    assert agebands.band_for(70, 74) == "65-74"
    assert agebands.band_for(75, None) == "75+"
    assert agebands.band_for(90, None) == "75+"
    assert agebands.band_for(80, 84) == "75+"
    assert agebands.band_for(None, None) == agebands.UNKNOWN
    assert agebands.band_for(0, 14) is None
    assert agebands.band_for(70, 74, {"70-74": (70, 74)}) == "70-74"


def test_band_for_rejects_straddling_intervals() -> None:
    with pytest.raises(ValueError):
        agebands.band_for(15, 29)
    with pytest.raises(ValueError):
        agebands.band_for(65, None)  # open-ended from 65 spans 65-74 and 75+
