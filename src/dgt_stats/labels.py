"""English labels for the DGT crash-type codes and the road-user death columns."""

from __future__ import annotations

ENGLISH: dict[str, dict[str, str]] = {
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
}


# Hour bands: (first hour, last hour) inclusive. Key and label are derived from the edges.
HOUR_BAND_EDGES: tuple[tuple[int, int], ...] = (
    (0, 6),
    (7, 9),
    (10, 13),
    (14, 16),
    (17, 19),
    (20, 23),
)
HOUR_BANDS: dict[str, str] = {
    f"{low:02d}-{high:02d}": f"{low:02d}:00–{high:02d}:59" for low, high in HOUR_BAND_EDGES
}

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
