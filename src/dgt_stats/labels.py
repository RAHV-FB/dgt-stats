"""English labels for the DGT codes that appear on the site.

Every code of a labelled column has an entry; the two generic missing markers (999, 998) and the
explicit "unknown" codes are labelled too, so that tables never show a bare number. The Spanish
originals stay available through :func:`dgt_stats.codes.decode`.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from dgt_stats import codes

NOT_SPECIFIED = "Not specified"
NOT_APPLICABLE = "Not applicable"

ENGLISH: dict[str, dict[str, str]] = {
    "DIA_SEMANA": {
        "1": "Monday",
        "2": "Tuesday",
        "3": "Wednesday",
        "4": "Thursday",
        "5": "Friday",
        "6": "Saturday",
        "7": "Sunday",
    },
    "ZONA": {
        "1": "Interurban road",
        "2": "Urban crossing (travesía)",
        "3": "Street",
        "4": "Urban motorway",
    },
    "ZONA_AGRUPADA": {"1": "Interurban", "2": "Urban"},
    "TIPO_VIA": {
        "1": "Toll motorway",
        "2": "Free motorway",
        "3": "Dual carriageway (autovía)",
        "4": "Road for motor vehicles",
        "5": "Conventional road, dual carriageway",
        "6": "Conventional road, single carriageway",
        "7": "Service road",
        "8": "Slip road",
        "9": "Street",
        "10": "Local track",
        "11": "Enclosed area",
        "12": "Cycle track",
        "13": "Cycle path",
        "14": "Other",
    },
    "TIPO_ACCIDENTE": {
        "1": "Head-on collision",
        "2": "Head-on/side collision",
        "3": "Side collision",
        "4": "Rear-end collision",
        "5": "Multiple or chain collision",
        "6": "Collision with obstacle or road element",
        "7": "Pedestrian struck",
        "8": "Animal struck",
        "9": "Overturn",
        "10": "Fall (rider or occupant)",
        "11": "Run-off road only",
        "12": "Run-off to the left with collision",
        "13": "Run-off to the left with plunge",
        "14": "Run-off to the left with overturn",
        "15": "Run-off to the left, other",
        "16": "Run-off to the right with collision",
        "17": "Run-off to the right with plunge",
        "18": "Run-off to the right with overturn",
        "19": "Run-off to the right, other",
        "20": "Other crash type",
    },
    "NUDO": {"1": "At a junction", "2": "Not at a junction"},
    "CONDICION_ILUMINACION": {
        "1": "Daylight",
        "2": "Dawn or dusk, no artificial light",
        "3": "Dawn or dusk, artificial light",
        "4": "Dark, street lighting on",
        "5": "Dark, street lighting off",
        "6": "Dark, no lighting",
    },
    "CONDICION_METEO": {
        "1": "Clear",
        "2": "Cloudy",
        "3": "Light rain",
        "4": "Heavy rain",
        "5": "Hail",
        "6": "Snow",
        "7": "Unknown",
    },
    "CONDICION_FIRME": {
        "1": "Dry and clean",
        "2": "Mud or loose gravel",
        "3": "Wet",
        "4": "Flooded",
        "5": "Ice",
        "6": "Snow",
        "7": "Oil",
        "8": "Other",
        "9": "Unknown",
    },
    "TRAZADO_PLANTA": {
        "1": "Straight",
        "2": "Signed curve",
        "3": "Unsigned curve",
        "4": "Unknown",
    },
}

# Derived groupings used on the site.
ROAD_GROUPS: dict[str, str] = {
    "motorway": "Motorway",
    "dual_carriageway": "Dual carriageway",
    "conventional": "Conventional road",
    "urban_street": "Urban street",
    "other": "Other road",
}

HOUR_BANDS: dict[str, str] = {
    "00-06": "00:00–06:59",
    "07-09": "07:00–09:59",
    "10-13": "10:00–13:59",
    "14-16": "14:00–16:59",
    "17-19": "17:00–19:59",
    "20-23": "20:00–23:59",
}

ZONES: dict[str, str] = {"interurban": "Interurban", "urban": "Urban", "all": "All roads"}

MONTHS: dict[int, str] = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

WEEKDAYS: dict[int, str] = {int(k): v for k, v in ENGLISH["DIA_SEMANA"].items()}

# 30-day death columns by road-user type -> label.
ROAD_USER_TYPES: dict[str, str] = {
    "TOT_PEAT_MU30DF": "Pedestrians",
    "TOT_BICI_MU30DF": "Cyclists",
    "TOT_CICLO_MU30DF": "Moped riders",
    "TOT_MOTO_MU30DF": "Motorcyclists",
    "TOT_VMP_MU30DF": "Personal mobility vehicles",
    "TOT_TUR_MU30DF": "Car occupants",
    "TOT_FURG_MU30DF": "Van occupants",
    "TOT_CAM_MENOS3500_MU30DF": "Light truck occupants (≤3.5 t)",
    "TOT_CAM_MAS3500_MU30DF": "Heavy truck occupants (>3.5 t)",
    "TOT_BUS_MU30DF": "Bus occupants",
    "TOT_OTRO_MU30DF": "Other vehicles",
    "TOT_SINESPECIF_MU30DF": "Unspecified vehicle",
}

VULNERABLE_TYPES: tuple[str, ...] = (
    "TOT_PEAT_MU30DF",
    "TOT_BICI_MU30DF",
    "TOT_CICLO_MU30DF",
    "TOT_MOTO_MU30DF",
    "TOT_VMP_MU30DF",
)

# Series-workbook vehicle-type names -> English.
SERIES_VEHICLE_TYPES: dict[str, str] = {
    "Bicicletas": "Bicycles",
    "VMP": "Personal mobility vehicles",
    "Ciclomotores": "Mopeds",
    "Motocicletas": "Motorcycles",
    "Turismos": "Cars",
    "Camiones hasta 3.500 kg y furgonetas": "Vans and light trucks (≤3.5 t)",
    "Camiones más de 3.500 kg": "Heavy trucks (>3.5 t)",
    "Autobuses": "Buses",
    "Otros": "Other",
    "TOTAL": "Total",
}

LABELLED_COLUMNS: tuple[str, ...] = tuple(ENGLISH)


def english(column: str, values: Iterable[object]) -> pd.Series:
    """English label for each code of ``column``; missing markers get their generic label."""
    mapping = ENGLISH[column]
    series = values if isinstance(values, pd.Series) else pd.Series(list(values))
    keys = series.map(codes._code_key)

    def label(key: object) -> object:
        if key is None or key is pd.NA or (isinstance(key, float) and pd.isna(key)):
            return pd.NA
        if key == str(codes.NOT_SPECIFIED_CODE):
            return NOT_SPECIFIED
        if key == str(codes.NOT_APPLICABLE_CODE):
            return NOT_APPLICABLE
        return mapping.get(key, key)

    return keys.map(label).astype("string")
