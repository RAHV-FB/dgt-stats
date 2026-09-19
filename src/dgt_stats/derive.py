"""Derived fields for the crash microdata.

Everything here is a deterministic function of the harmonised columns. Raw codes are never
overwritten; derived columns are added alongside them.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import codes, labels

ROAD_GROUP_BY_TYPE: dict[int, str] = {
    1: "motorway",
    2: "motorway",
    3: "dual_carriageway",
    5: "dual_carriageway",
    4: "conventional",
    6: "conventional",
    9: "urban_street",
    7: "other",
    8: "other",
    10: "other",
    11: "other",
    12: "other",
    13: "other",
    14: "other",
}

HOUR_BAND_EDGES: tuple[tuple[int, int, str], ...] = (
    (0, 6, "00-06"),
    (7, 9, "07-09"),
    (10, 13, "10-13"),
    (14, 16, "14-16"),
    (17, 19, "17-19"),
    (20, 23, "20-23"),
)

NIGHT_LIGHTING_CODES: frozenset[int] = frozenset({4, 5, 6})
ZONE_BY_CODE: dict[int, str] = {1: "interurban", 2: "urban"}


def hour_band(hours: pd.Series) -> pd.Series:
    """Map an hour (0–23) to its band label; missing or out-of-range hours become ``<NA>``."""
    edges = [-1] + [high for _, high, _ in HOUR_BAND_EDGES]
    names = [name for _, _, name in HOUR_BAND_EDGES]
    numeric = pd.to_numeric(hours, errors="coerce")
    out = pd.cut(numeric, bins=edges, labels=names)
    return out.astype("string")


def road_group(tipo_via: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(tipo_via, errors="coerce")
    return numeric.map(ROAD_GROUP_BY_TYPE).astype("string")


def add_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with outcome flags, groupings, status companions and English labels."""
    out = df.copy()

    deaths = out["TOTAL_MU30DF"].fillna(0).astype("int32")
    hospitalised = out["TOTAL_HG30DF"].fillna(0).astype("int32")
    out["n_deaths"] = deaths
    out["fatal"] = deaths > 0
    out["serious"] = (deaths > 0) | (hospitalised > 0)
    vulnerable = sum(out[column].fillna(0).astype("int32") for column in labels.VULNERABLE_TYPES)
    out["n_vulnerable_deaths"] = vulnerable.astype("int32")

    out["zone"] = pd.to_numeric(out["ZONA_AGRUPADA"], errors="coerce").map(ZONE_BY_CODE)
    out["zone"] = out["zone"].astype("string")
    out["road_group"] = road_group(out["TIPO_VIA"])
    out["hour_band"] = hour_band(out["HORA"])

    lighting = pd.to_numeric(out["CONDICION_ILUMINACION"], errors="coerce")
    out["night"] = lighting.isin(NIGHT_LIGHTING_CODES).fillna(False).astype(bool)

    weekday = pd.to_numeric(out["DIA_SEMANA"], errors="coerce")
    hour = pd.to_numeric(out["HORA"], errors="coerce")
    friday_night = (weekday == 5) & (hour >= 20)
    out["weekend"] = (weekday.isin([6, 7]) | friday_night).fillna(False).astype(bool)

    for column in codes.CONDITION_COLUMNS:
        out[f"status_{column}"] = codes.status(column, out[column]).astype("string")

    for column in labels.LABELLED_COLUMNS:
        out[f"{column}_label"] = labels.english(column, out[column])

    return out


DERIVED_COLUMNS: tuple[str, ...] = (
    "n_deaths",
    "fatal",
    "serious",
    "n_vulnerable_deaths",
    "zone",
    "road_group",
    "hour_band",
    "night",
    "weekend",
    *(f"status_{column}" for column in codes.CONDITION_COLUMNS),
    *(f"{column}_label" for column in labels.LABELLED_COLUMNS),
)
