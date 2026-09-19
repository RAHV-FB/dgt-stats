"""Vehicle groups shared by the yearbook unit tables, the 2022 kilometre estimates, the historical
series and the microdata death columns.

The yearbook tables list 22 unit types, the kilometre table 7 vehicle types, the series 9 columns and
the microdata 12 death columns. One dictionary maps all four onto the same groups so that a rate's
numerator and denominator always describe the same vehicles.
"""

from __future__ import annotations

# Group -> the names it takes in each source. ``units`` are the row labels of TABLA 2.2 and 2.3
# (whitespace collapsed), ``km_type`` the vehicle type of the 2022 kilometre table (``None`` when the
# group has no kilometre denominator), ``microdata`` the 30-day death column, ``series`` the column of
# the ``Cond-Pasj_MU`` sheets (``None`` when the series merges the group with another).
VEHICLE_GROUPS: dict[str, dict[str, object]] = {
    "moped": {
        "label": "Mopeds",
        "units": ("Ciclomotor",),
        "km_type": "Ciclomotor",
        "microdata": "TOT_CICLO_MU30DF",
        "series": "mopeds",
    },
    "motorcycle": {
        "label": "Motorcycles",
        "units": ("Motocicleta",),
        "km_type": "Motocicleta",
        "microdata": "TOT_MOTO_MU30DF",
        "series": "motorcycles",
    },
    "car": {
        "label": "Cars",
        "units": ("Turismo sin remolque", "Turismo con remolque", "Turismo de SP hasta 9 plazas"),
        "km_type": "Turismo",
        "microdata": "TOT_TUR_MU30DF",
        "series": "cars",
    },
    "van": {
        "label": "Vans",
        "units": ("Furgoneta",),
        "km_type": "Furgoneta",
        "microdata": "TOT_FURG_MU30DF",
        "series": None,
    },
    "light_truck": {
        "label": "Trucks up to 3,500 kg",
        "units": ("Camión <=3.500 kg sin remolque", "Camión <=3.500 kg con remolque"),
        "km_type": "Camión hasta 3.500Kg",
        "microdata": "TOT_CAM_MENOS3500_MU30DF",
        "series": None,
    },
    "heavy_truck": {
        "label": "Trucks over 3,500 kg",
        "units": (
            "Camión >3.500 kg sin remolque",
            "Camión >3.500 kg con remolque",
            "Tractocamión (cabeza tractora)",
            "Vehículo articulado",
        ),
        "km_type": "Camión más de 3.500Kg",
        "microdata": "TOT_CAM_MAS3500_MU30DF",
        "series": "heavy_trucks",
    },
    "bus": {
        "label": "Buses",
        "units": ("Autobús (no escolar)", "Autobús escolar"),
        "km_type": "Autobús",
        "microdata": "TOT_BUS_MU30DF",
        "series": "buses",
    },
    "pedestrian": {
        "label": "Pedestrians",
        "units": ("Peatón",),
        "km_type": None,
        "microdata": "TOT_PEAT_MU30DF",
        "series": None,
    },
    "bicycle": {
        "label": "Bicycles",
        "units": ("Bicicleta",),
        "km_type": None,
        "microdata": "TOT_BICI_MU30DF",
        "series": "bicycles",
    },
    "vmp": {
        "label": "Personal mobility vehicles",
        "units": ("VMP",),
        "km_type": None,
        "microdata": "TOT_VMP_MU30DF",
        "series": "vmp",
    },
    "other": {
        "label": "Other vehicles",
        "units": (
            "Maquinaria obras y agrícola y tractores agrícolas",
            "Cuadriciclo",
            "Tren/metro/tranvía",
            "Otro vehículo",
        ),
        "km_type": None,
        "microdata": "TOT_OTRO_MU30DF",
        "series": "other",
    },
    "unknown": {
        "label": "Unknown vehicle",
        "units": ("Se desconoce",),
        "km_type": None,
        "microdata": "TOT_SINESPECIF_MU30DF",
        "series": None,
    },
}

# Groups with a kilometre denominator, in the order the page shows them.
KM_GROUPS = tuple(name for name, spec in VEHICLE_GROUPS.items() if spec["km_type"] is not None)

# The series merges vans with light trucks in one column.
SERIES_MERGED = {"vans_light_trucks": ("van", "light_truck")}

UNIT_TO_GROUP: dict[str, str] = {
    unit: name
    for name, spec in VEHICLE_GROUPS.items()
    for unit in spec["units"]  # type: ignore[attr-defined]
}


def group_of(unit_type: str) -> str:
    """Group of a yearbook unit label; raises for a label the mapping does not know."""
    try:
        return UNIT_TO_GROUP[unit_type]
    except KeyError as error:
        raise KeyError(f"unit type {unit_type!r} is not in VEHICLE_GROUPS") from error


def label(group: str) -> str:
    return str(VEHICLE_GROUPS[group]["label"])
