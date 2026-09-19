"""Code lists for the DGT crash microdata and the missing-value states they use.

The dictionary workbook (`data/raw/microdata/diccionario.xlsx`) has one sheet per coded column with
two columns, ``Valor`` and ``Etiqueta``. A handful of sheets describe free-text or numeric fields and
are not code lists. Missing information is encoded four different ways in the microdata and must stay
distinguishable:

* ``999``  "Sin especificar": the field was not reported.
* ``998``  "No aplica": the field does not apply to this crash (e.g. sidewalk on an interurban road).
* an explicit "unknown" code inside the code list (e.g. weather ``7`` "Se desconoce").
* an empty cell, used for optional fields (island, km post, fog, wind, junction detail).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import openpyxl
import pandas as pd

from dgt_stats.paths import DICTIONARY_PATH

NOT_SPECIFIED_CODE = 999
NOT_APPLICABLE_CODE = 998

# Dictionary sheets that document non-coded fields.
NOT_CODE_SHEETS = frozenset(
    {"COD_MUNICIPIO", "CARRETERA", "KM", "CARRETERA_CRUCE", "TOTALIZADORES"}
)

# Codes that occur in the published files but are absent from the dictionary, with the meaning
# inferred from the data. ``ISLA`` 0 appears from 2018 on, almost only in island provinces, where a
# crash was assigned to no island; it is treated as "not specified".
UNDOCUMENTED_CODES: dict[str, dict[str, str]] = {"ISLA": {"0": "Isla sin especificar"}}
UNDOCUMENTED_NOT_SPECIFIED: dict[str, str] = {"ISLA": "0"}

# Code that means "unknown" inside a column's own code list.
EXPLICIT_UNKNOWN: dict[str, int] = {
    "SENTIDO_1F": 4,
    "CONDICION_NIVEL_CIRCULA": 6,
    "CONDICION_FIRME": 9,
    "CONDICION_METEO": 7,
    "VISIB_RESTRINGIDA_POR": 18,
    "TRAZADO_PLANTA": 4,
}

PRIORI_COLUMNS: tuple[str, ...] = (
    "PRIORI_NORMA",
    "PRIORI_AGENTE",
    "PRIORI_SEMAFORO",
    "PRIORI_VERT_STOP",
    "PRIORI_VERT_CEDA",
    "PRIORI_HORIZ_STOP",
    "PRIORI_HORIZ_CEDA",
    "PRIORI_MARCAS",
    "PRIORI_PEA_NO_ELEV",
    "PRIORI_PEA_ELEV",
    "PRIORI_MARCA_CICLOS",
    "PRIORI_CIRCUNSTANCIAL",
    "PRIORI_OTRA",
)

CONDITION_COLUMNS: tuple[str, ...] = (
    "CONDICION_NIVEL_CIRCULA",
    "CONDICION_FIRME",
    "CONDICION_ILUMINACION",
    "CONDICION_METEO",
    "CONDICION_NIEBLA",
    "CONDICION_VIENTO",
    "VISIB_RESTRINGIDA_POR",
    "ACERA",
    "TRAZADO_PLANTA",
)

LOCATION_COLUMNS: tuple[str, ...] = (
    "DIA_SEMANA",
    "COD_PROVINCIA",
    "ISLA",
    "ZONA",
    "ZONA_AGRUPADA",
    "SENTIDO_1F",
    "TITULARIDAD_VIA",
    "TIPO_VIA",
    "TIPO_ACCIDENTE",
    "NUDO",
    "NUDO_INFO",
)

CATEGORICAL_COLUMNS: tuple[str, ...] = LOCATION_COLUMNS + PRIORI_COLUMNS + CONDITION_COLUMNS

STATUS_LEVELS: tuple[str, ...] = (
    "observed",
    "unknown",
    "not_specified",
    "not_applicable",
    "empty",
)


def _is_missing(value: object) -> bool:
    return value is None or value is pd.NA or (isinstance(value, float) and pd.isna(value))


def _code_key(value: object) -> str | None:
    """Normalise a raw cell or Series value to the string key used in the code map."""
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    text = str(value).strip()
    if text == "":
        return None
    if text.lstrip("-").isdigit():
        return str(int(text))
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


@lru_cache(maxsize=1)
def load_dictionary() -> dict[str, dict[str, str]]:
    """Return ``{column: {code: label}}`` for every code-list sheet in the dictionary workbook.

    Codes are strings (``"1"``, ``"999"``, ``"."``). A row with an empty code and a label (the
    ``ISLA`` sheet's "No aplica") is stored under the empty string so callers can label empty cells.
    """
    workbook = openpyxl.load_workbook(DICTIONARY_PATH, read_only=True, data_only=True)
    dictionary: dict[str, dict[str, str]] = {}
    for sheet in workbook.worksheets:
        if sheet.title in NOT_CODE_SHEETS:
            continue
        codes: dict[str, str] = {}
        in_body = False
        for row in sheet.iter_rows(values_only=True):
            first = row[0] if row else None
            second = row[1] if len(row) > 1 else None
            if not in_body:
                if isinstance(first, str) and first.strip().lower() == "valor":
                    in_body = True
                continue
            if second is None or str(second).strip() == "":
                continue
            key = _code_key(first)
            codes["" if key is None else key] = str(second).strip()
        if codes:
            codes.update(UNDOCUMENTED_CODES.get(sheet.title, {}))
            dictionary[sheet.title] = codes
    workbook.close()
    return dictionary


def code_columns() -> tuple[str, ...]:
    """Columns that have a code list in the dictionary."""
    return tuple(load_dictionary())


def labels_for(column: str) -> dict[str, str]:
    """Code → label map for one column; raises ``KeyError`` for non-coded columns."""
    return load_dictionary()[column]


def decode(column: str, values: Iterable[object]) -> pd.Series:
    """Map raw codes of ``column`` to their Spanish labels.

    Empty cells become ``<NA>``. A code missing from the dictionary is returned unchanged as text so
    that unexpected values stay visible rather than silently disappearing.
    """
    mapping = labels_for(column)
    series = values if isinstance(values, pd.Series) else pd.Series(list(values))
    keys = series.map(_code_key)
    out = keys.map(lambda k: pd.NA if _is_missing(k) else mapping.get(k, k))
    return out.astype("string")


def status(column: str, values: Iterable[object]) -> pd.Series:
    """Classify each value as observed / unknown / not_specified / not_applicable / empty."""
    series = values if isinstance(values, pd.Series) else pd.Series(list(values))
    keys = series.map(_code_key)
    unknown = EXPLICIT_UNKNOWN.get(column)
    unknown_key = None if unknown is None else str(unknown)
    not_specified_keys = {str(NOT_SPECIFIED_CODE), UNDOCUMENTED_NOT_SPECIFIED.get(column)}

    def classify(key: object) -> str:
        if _is_missing(key):
            return "empty"
        if key in not_specified_keys:
            return "not_specified"
        if key == str(NOT_APPLICABLE_CODE):
            return "not_applicable"
        if unknown_key is not None and key == unknown_key:
            return "unknown"
        return "observed"

    return pd.Series(
        pd.Categorical(keys.map(classify), categories=list(STATUS_LEVELS)),
        index=series.index,
        name=f"status_{column}",
    )


def allowed_codes(column: str) -> set[str]:
    """Every code that may legitimately appear in ``column``: dictionary codes plus 999 and 998."""
    allowed = set(labels_for(column)) - {""}
    allowed.update({str(NOT_SPECIFIED_CODE), str(NOT_APPLICABLE_CODE)})
    return allowed
