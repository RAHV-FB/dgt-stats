"""Strict common-feature catalogues between Catalonia and the two other crash-level sources.

A variable enters a cross-source test only if both sources record the *same thing*. Each
:class:`CommonField` names the column on each side, the semantics, the category mapping and a
status:

``exact``         the same quantity on the same scale (hour of day, weekday, year)
``defensible``    the same concept under the same published label or code meaning, mapped to
                  coarser shared levels; for the DGT pair the mapping is also *validated* on the
                  crashes both sources describe (Catalonia 2016-2023), see :func:`validate_dgt`
``approximate``   similar label, different scope (e.g. "light vehicles"); excluded
``unusable``      present on one side only, or present only as an outcome count; excluded

Only ``exact`` and ``defensible`` fields are built into the common columns. Nothing is filled in
for a missing side: a variable one source lacks is simply absent from the common model.

The two pairs:

* **Catalonia <-> DGT national crash microdata (2016-2024).** Both are crash-level police records
  of the same national accident report, and Catalonia's counts equal the DGT microdata's 24-hour
  fatal counts in every province-year (``crosssource``). The compatible DGT population is the
  crashes with a death or serious injury within 24 hours; its target is a death within 24 hours.
* **Catalonia <-> Barcelona 2025.** Barcelona records far fewer of the road and condition
  variables; the compatible Barcelona population is the crashes with a death or serious
  injury (``Numero_morts`` deaths within 24 hours, ``Numero_lesionats_greus`` hospitalised over
  24 hours, both checked against the person table in the quality report).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from dgt_stats.microdata import barcelona, catalonia
from dgt_stats.microdata.common import write_parquet
from dgt_stats.paths import DGT_PROCESSED_CRASHES, FEATURES_DATA_DIR

NOT_SPECIFIED = "not specified"
CATALAN_PROVINCES = tuple(catalonia.DEMARCATION_PROVINCE_CODE.values())

CAT_COMMON_PATH = FEATURES_DATA_DIR / "catalonia_common_features.parquet"
DGT_COMMON_PATH = FEATURES_DATA_DIR / "dgt_common_crashes.parquet"
BCN_COMMON_PATH = FEATURES_DATA_DIR / "barcelona_common_crashes.parquet"


@dataclass(frozen=True)
class CommonField:
    name: str
    kind: str
    catalonia: str
    other: str
    semantics: str
    mapping: str
    status: str


HOUR_BANDS = catalonia.HOUR_BANDS

# ----------------------------------------------------------------------------- Catalonia <-> DGT
DGT_FIELDS: tuple[CommonField, ...] = (
    CommonField(
        "year", "numeric", "Any", "ANYO", "calendar year of the crash", "identity", "exact"
    ),
    CommonField(
        "month", "categorical", "dat (month)", "MES", "month of the crash", "identity", "exact"
    ),
    CommonField(
        "weekday",
        "categorical",
        "dat (weekday)",
        "DIA_SEMANA",
        "day of the week",
        "DGT 1-7 = Monday-Sunday",
        "exact",
    ),
    CommonField(
        "hour_band",
        "categorical",
        "hor (hour)",
        "HORA",
        "hour of the crash, six bands",
        "same bands from the hour",
        "exact",
    ),
    CommonField(
        "zone",
        "categorical",
        "zona",
        "ZONA_AGRUPADA",
        "urban or interurban road (through-town roads are urban in both)",
        "Zona urbana / VÍAS URBANAS -> urban; Carretera / VÍAS INTERURBANAS -> interurban",
        "defensible",
    ),
    CommonField(
        "road_class",
        "categorical",
        "D_TIPUS_VIA",
        "TIPO_VIA",
        "type of road",
        "Autopista / 1-2 -> motorway; Autovia / 3 -> dual carriageway; Carretera "
        "convencional / 4-6 -> conventional; Via urbana / 9 -> urban street; Camí rural / "
        "10 -> rural track; Altres / 7-8, 11-14 -> other",
        "defensible",
    ),
    CommonField(
        "crash_type",
        "categorical",
        "D_SUBTIPUS_ACCIDENT",
        "TIPO_ACCIDENTE",
        "how the crash happened",
        "Atropellament / 7 -> pedestrian struck; Col·lisió frontal / 1 -> head-on; "
        "Envestida (frontal lateral) / 2 -> front-side; Fregament o col·lisió lateral / 3 "
        "-> side; Encalç / 4-5 -> rear-end or multiple; Xoc contra objecte / 6 -> fixed "
        "object; Sortida de via (all) / 11-19 -> run-off-road; Caiguda en la via / 9-10 "
        "-> fall or overturn; Xoc amb animal, Altres / 8, 20 -> other (animals are coded too "
        "differently to keep apart)",
        "defensible",
    ),
    CommonField(
        "lighting",
        "categorical",
        "D_LLUMINOSITAT",
        "CONDICION_ILUMINACION",
        "light conditions",
        "day (clear or overcast) / 1 -> daylight; dawn or dusk / 2-3 -> twilight; any "
        "night / 4-6 -> dark; not specified / 999",
        "defensible",
    ),
    CommonField(
        "weather",
        "categorical",
        "D_CLIMATOLOGIA",
        "CONDICION_METEO",
        "weather",
        "Bon temps / 1-2 -> fine; Pluja dèbil or forta / 3-4 -> rain; "
        "Calamarsa, Nevant / 5-6 -> hail or snow; Sense especificar / 7, 999 -> not "
        "specified",
        "defensible",
    ),
    CommonField(
        "surface",
        "categorical",
        "D_SUPERFICIE",
        "CONDICION_FIRME",
        "road surface",
        "Sec i net / 1 -> dry; Mullat, Inundat / 3-4 -> wet; Relliscós, "
        "Gelat, Nevat / 2, 5-8 -> slippery, icy or snowy; Sense especificar / 9, 999 -> "
        "not specified",
        "defensible",
    ),
    CommonField(
        "junction",
        "categorical",
        "D_INTER_SECCIO",
        "NUDO",
        "at a junction or on a road section",
        "Dintre intersecció / 1 -> junction; En secció and 'Arribant o eixint fins 50m' / "
        "2 -> section (the choice for the approach zone is validated on the overlap)",
        "defensible",
    ),
    CommonField(
        "vehicles",
        "categorical",
        "F_UNITATS_IMPLICADES - F_VIANANTS_IMPLICADES",
        "TOTAL_VEHICULOS",
        "vehicles involved (pedestrians are units in the Catalan file, not in DGT's vehicle count)",
        "1, 2, 3 or more",
        "defensible",
    ),
    CommonField(
        "speed_limit",
        "categorical",
        "C_VELOCITAT_VIA",
        "(none)",
        "posted speed limit",
        "DGT microdata has no speed-limit field",
        "unusable",
    ),
    CommonField(
        "unit_types",
        "binary",
        "F_*_IMPLICADES",
        "TOT_*_MU24H",
        "vehicle types involved",
        "DGT microdata gives deaths by vehicle type, not involvement: an outcome count",
        "unusable",
    ),
    CommonField(
        "geography",
        "categorical",
        "nomDem / nomCom / nomMun",
        "COD_PROVINCIA",
        "place",
        "held-out domains are new places by design",
        "unusable",
    ),
)

# ----------------------------------------------------------------------------- Catalonia <-> BCN
BCN_FIELDS: tuple[CommonField, ...] = (
    CommonField(
        "weekday",
        "categorical",
        "dat (weekday)",
        "Dia_mes/Mes_any/NK_Any (date)",
        "day of the week",
        "from the date on both sides",
        "exact",
    ),
    CommonField(
        "hour_band",
        "categorical",
        "hor (hour)",
        "Hora_dia",
        "hour of the crash, six bands",
        "same bands from the hour",
        "exact",
    ),
    CommonField(
        "crash_type",
        "categorical",
        "D_SUBTIPUS_ACCIDENT",
        "Descripcio_tipus_accident",
        "how the crash happened, only where both sources publish the same label",
        "Atropellament -> pedestrian struck; Col·lisió frontal -> head-on; Sortida de "
        "via (all) and Resta sortides de via -> run-off-road; Xoc amb animal -> animal; "
        "everything else -> other (not harmonised)",
        "defensible",
    ),
    CommonField(
        "involves_pedestrian",
        "binary",
        "F_VIANANTS_IMPLICADES > 0",
        "a person record with Descripcio_tipus_persona = Vianant",
        "a pedestrian was involved (Barcelona records uninjured pedestrians too)",
        "presence",
        "defensible",
    ),
    CommonField(
        "involves_motorcycle",
        "binary",
        "F_MOTOCICLETES_IMPLICADES > 0",
        "vehicle record of type Motocicleta",
        "a motorcycle was involved",
        "presence",
        "defensible",
    ),
    CommonField(
        "involves_moped",
        "binary",
        "F_CICLOMOTORS_IMPLICADES > 0",
        "vehicle record of type Ciclomotor",
        "a moped was involved",
        "presence",
        "defensible",
    ),
    CommonField(
        "involves_bicycle",
        "binary",
        "F_BICICLETES_IMPLICADES > 0",
        "vehicle record of type Bicicleta or Bicicleta pedaleig assistit",
        "a bicycle (including pedal-assisted) was involved",
        "presence",
        "defensible",
    ),
    CommonField(
        "vehicles",
        "categorical",
        "F_UNITATS_IMPLICADES - F_VIANANTS_IMPLICADES",
        "Numero_vehicles_implicats",
        "vehicles involved",
        "1, 2, 3 or more",
        "defensible",
    ),
    CommonField(
        "involves_heavy_vehicle",
        "binary",
        "F_VEH_PESANTS_IMPLICADES > 0",
        "heavy truck or bus records",
        "a heavy vehicle was involved",
        "the Catalan 'heavy vehicle' class is not defined in the file; buses may or may "
        "not be in it",
        "approximate",
    ),
    CommonField(
        "involves_light_vehicle",
        "binary",
        "F_VEH_LLEUGERS_IMPLICADES > 0",
        "car, taxi, van records",
        "a light vehicle was involved",
        "class boundaries not published",
        "approximate",
    ),
    CommonField(
        "personal_mobility_vehicle",
        "binary",
        "(none)",
        "Veh. mobilitat personal",
        "a personal mobility vehicle was involved",
        "no such category in the Catalan file",
        "unusable",
    ),
    CommonField(
        "road_and_conditions",
        "categorical",
        "D_TIPUS_VIA, D_LLUMINOSITAT, D_CLIMATOLOGIA, D_SUPERFICIE, C_VELOCITAT_VIA",
        "(none)",
        "road, light, weather, surface, speed limit",
        "not recorded in the Barcelona files",
        "unusable",
    ),
    CommonField(
        "people",
        "categorical",
        "(none)",
        "Edat, Descripcio_sexe, tipus persona",
        "age, sex, role",
        "the Catalan file has no person records",
        "unusable",
    ),
)

USABLE = ("exact", "defensible")


def usable(fields: tuple[CommonField, ...]) -> list[CommonField]:
    return [field for field in fields if field.status in USABLE]


def _hour_band(hours: pd.Series) -> pd.Series:
    return (
        catalonia.band(pd.to_numeric(hours, errors="coerce").astype("Float64"), HOUR_BANDS)
        .fillna(NOT_SPECIFIED)
        .astype(str)
    )


def _vehicles_band(n: pd.Series) -> pd.Series:
    n = pd.to_numeric(n, errors="coerce")
    out = pd.Series(NOT_SPECIFIED, index=n.index, dtype=object)
    out[n <= 1] = "1"
    out[n == 2] = "2"
    out[n >= 3] = "3 or more"
    return out


# ----------------------------------------------------------------------------- Catalonia side
CAT_ROAD = {
    "Autopista": "motorway",
    "Autovia": "dual carriageway",
    "Carretera convencional": "conventional",
    "Via urbana( inclou carrer i carrer residencial)": "urban street",
    "Camí rural/pista forestal": "rural track",
    "Altres": "other",
}
CAT_CRASH = {
    "Atropellament": "pedestrian struck",
    "Col·lisió frontal": "head-on",
    "Envestida (frontal lateral)": "front-side",
    "Fregament o col·lisió lateral": "side",
    "Encalç": "rear-end or multiple",
    "Xoc contra objecte/obstacle sense sortida prèvia de via": "fixed object",
    "Sortida de via amb xoc o col·lisió": "run-off-road",
    "Sortida de via amb bolcada": "run-off-road",
    "Sortida de via amb atropellament": "run-off-road",
    "Resta sortides de via": "run-off-road",
    "Caiguda en la via": "fall or overturn",
    "Xoc amb animal a la calçada": "other",
    "Altres": "other",
    "Sense Especificar": NOT_SPECIFIED,
}
CAT_LIGHT = {
    "De dia, dia clar": "daylight",
    "De dia, dia fosc": "daylight",
    "Alba o capvespre": "twilight",
    "De nit, il·luminació artificial suficient": "dark",
    "De nit, il·luminació artificial insuficient": "dark",
    "De nit, sense llum artificial": "dark",
    "Sense especificar": NOT_SPECIFIED,
}
CAT_WEATHER = {
    "Bon temps": "fine",
    "Pluja dèbil": "rain",
    "Pluja forta": "rain",
    "Calamarsa": "hail or snow",
    "Nevant": "hail or snow",
    "Sense especificar": NOT_SPECIFIED,
}
CAT_SURFACE = {
    "Sec i net": "dry",
    "Mullat": "wet",
    "Inundat": "wet",
    "Relliscós": "slippery, icy or snowy",
    "Gelat": "slippery, icy or snowy",
    "Nevat": "slippery, icy or snowy",
    "Sense especificar": NOT_SPECIFIED,
}
CAT_JUNCTION = {
    "Dintre intersecció": "junction",
    "En secció": "section",
    "Arribant o eixint intersecció fins 50m": "section",
}
BCN_CRASH = {
    "pedestrian struck": "pedestrian struck",
    "head-on collision": "head-on",
    "run-off-road with collision": "run-off-road",
    "run-off-road with overturn": "run-off-road",
    "other run-off-road": "run-off-road",
    "collision with an animal": "animal",
}
CAT_CRASH_BCN = {
    "Atropellament": "pedestrian struck",
    "Col·lisió frontal": "head-on",
    "Sortida de via amb xoc o col·lisió": "run-off-road",
    "Sortida de via amb bolcada": "run-off-road",
    "Sortida de via amb atropellament": "run-off-road",
    "Resta sortides de via": "run-off-road",
    "Xoc amb animal a la calçada": "animal",
}
OTHER_TYPES = "other (not harmonised)"


def catalonia_common(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Every Catalan crash with both common column sets (``dgt_*`` and ``bcn_*``)."""
    frame = catalonia.read() if frame is None else frame
    vehicles = frame["n_units"].astype(float) - frame["n_pedestrians"].astype(float)
    out = pd.DataFrame(
        {
            "cat_crash_id": frame["cat_crash_id"],
            "fatal": frame["fatal"].astype("int8"),
            "year": frame["year"].astype(int),
            "demarcation": frame["demarcation"].astype(str),
            "province_code": frame["province_code"].astype(int),
            "municipality": frame["municipality"].astype(str),
            "domain": np.where(
                frame["municipality"].eq("Barcelona"), "Barcelona municipality", "rest of Catalonia"
            ),
        }
    )
    hour_band = _hour_band(frame["hour"])
    weekday = frame["weekday"].astype(str)
    out["dgt_year"] = out["year"].astype(float)
    out["dgt_month"] = frame["month"].astype(int).astype(str)
    out["dgt_weekday"] = weekday
    out["dgt_hour_band"] = hour_band
    out["dgt_zone"] = frame["zona"].map({"Zona urbana": "urban", "Carretera": "interurban"})
    out["dgt_road_class"] = frame["D_TIPUS_VIA"].map(CAT_ROAD).fillna(NOT_SPECIFIED)
    out["dgt_crash_type"] = frame["D_SUBTIPUS_ACCIDENT"].map(CAT_CRASH).fillna(NOT_SPECIFIED)
    out["dgt_lighting"] = frame["D_LLUMINOSITAT"].map(CAT_LIGHT).fillna(NOT_SPECIFIED)
    out["dgt_weather"] = frame["D_CLIMATOLOGIA"].map(CAT_WEATHER).fillna(NOT_SPECIFIED)
    out["dgt_surface"] = frame["D_SUPERFICIE"].map(CAT_SURFACE).fillna(NOT_SPECIFIED)
    out["dgt_junction"] = frame["D_INTER_SECCIO"].map(CAT_JUNCTION).fillna(NOT_SPECIFIED)
    out["dgt_vehicles"] = _vehicles_band(vehicles)
    out["bcn_weekday"] = weekday
    out["bcn_hour_band"] = hour_band
    out["bcn_crash_type"] = frame["D_SUBTIPUS_ACCIDENT"].map(CAT_CRASH_BCN).fillna(OTHER_TYPES)
    out["bcn_involves_pedestrian"] = frame["n_pedestrians"].astype(float).gt(0).astype(float)
    out["bcn_involves_motorcycle"] = frame["n_motorcycles"].astype(float).gt(0).astype(float)
    out["bcn_involves_moped"] = frame["n_mopeds"].astype(float).gt(0).astype(float)
    out["bcn_involves_bicycle"] = frame["n_bicycles"].astype(float).gt(0).astype(float)
    out["bcn_vehicles"] = _vehicles_band(vehicles)
    return out


# ----------------------------------------------------------------------------- DGT side
DGT_ROAD = {
    1: "motorway",
    2: "motorway",
    3: "dual carriageway",
    4: "conventional",
    5: "conventional",
    6: "conventional",
    9: "urban street",
    10: "rural track",
    7: "other",
    8: "other",
    11: "other",
    12: "other",
    13: "other",
    14: "other",
}
DGT_CRASH = {
    7: "pedestrian struck",
    1: "head-on",
    2: "front-side",
    3: "side",
    4: "rear-end or multiple",
    5: "rear-end or multiple",
    6: "fixed object",
    **{code: "run-off-road" for code in range(11, 20)},
    9: "fall or overturn",
    10: "fall or overturn",
    8: "other",
    20: "other",
}
DGT_LIGHT = {1: "daylight", 2: "twilight", 3: "twilight", 4: "dark", 5: "dark", 6: "dark"}
DGT_WEATHER = {1: "fine", 2: "fine", 3: "rain", 4: "rain", 5: "hail or snow", 6: "hail or snow"}
DGT_SURFACE = {
    1: "dry",
    3: "wet",
    4: "wet",
    2: "slippery, icy or snowy",
    5: "slippery, icy or snowy",
    6: "slippery, icy or snowy",
    7: "slippery, icy or snowy",
    8: "slippery, icy or snowy",
}
DGT_WEEKDAY = dict(enumerate(catalonia.WEEKDAYS, start=1))
DGT_COLUMNS = [
    "ID_ACCIDENTE",
    "ANYO",
    "MES",
    "DIA_SEMANA",
    "HORA",
    "COD_PROVINCIA",
    "COD_MUNICIPIO",
    "ZONA_AGRUPADA",
    "TIPO_VIA",
    "TIPO_ACCIDENTE",
    "CONDICION_ILUMINACION",
    "CONDICION_METEO",
    "CONDICION_FIRME",
    "NUDO",
    "TOTAL_VEHICULOS",
    "TOTAL_MU24H",
    "TOTAL_HG24H",
    "TOTAL_MU30DF",
]


def dgt_common() -> pd.DataFrame:
    """DGT crashes with a death or serious injury within 24 hours, in the common columns.

    The universe matches the Catalan file's inclusion rule (validated by the province-year
    reconciliation); the target is a death within 24 hours.
    """
    dgt = pd.read_parquet(DGT_PROCESSED_CRASHES, columns=DGT_COLUMNS)
    deaths = pd.to_numeric(dgt.TOTAL_MU24H, errors="coerce").fillna(0)
    serious = pd.to_numeric(dgt.TOTAL_HG24H, errors="coerce").fillna(0)
    dgt = dgt[(deaths + serious) > 0].copy()

    def code(column: str) -> pd.Series:
        return pd.to_numeric(dgt[column], errors="coerce")

    province = code("COD_PROVINCIA").astype("Int64")
    out = pd.DataFrame(
        {
            "dgt_crash_id": dgt.ANYO.astype(str) + "-" + dgt.ID_ACCIDENTE.astype(str),
            "fatal": (pd.to_numeric(dgt.TOTAL_MU24H, errors="coerce").fillna(0) > 0).astype("int8"),
            "fatal_30d": (pd.to_numeric(dgt.TOTAL_MU30DF, errors="coerce").fillna(0) > 0).astype(
                "int8"
            ),
            "year": code("ANYO").astype(int),
            "province_code": province,
            "municipality_code": dgt.COD_MUNICIPIO.astype(str),
            "domain": np.where(
                province.isin(CATALAN_PROVINCES),
                "Catalonia (DGT records)",
                "Spain outside Catalonia",
            ),
        }
    )
    out["dgt_year"] = out["year"].astype(float)
    out["dgt_month"] = code("MES").astype("Int64").astype(str)
    out["dgt_weekday"] = code("DIA_SEMANA").map(DGT_WEEKDAY).fillna(NOT_SPECIFIED)
    out["dgt_hour_band"] = _hour_band(code("HORA"))
    out["dgt_zone"] = code("ZONA_AGRUPADA").map({1: "interurban", 2: "urban"}).fillna(NOT_SPECIFIED)
    out["dgt_road_class"] = code("TIPO_VIA").map(DGT_ROAD).fillna(NOT_SPECIFIED)
    out["dgt_crash_type"] = code("TIPO_ACCIDENTE").map(DGT_CRASH).fillna(NOT_SPECIFIED)
    out["dgt_lighting"] = code("CONDICION_ILUMINACION").map(DGT_LIGHT).fillna(NOT_SPECIFIED)
    out["dgt_weather"] = code("CONDICION_METEO").map(DGT_WEATHER).fillna(NOT_SPECIFIED)
    out["dgt_surface"] = code("CONDICION_FIRME").map(DGT_SURFACE).fillna(NOT_SPECIFIED)
    out["dgt_junction"] = code("NUDO").map({1: "junction", 2: "section"}).fillna(NOT_SPECIFIED)
    out["dgt_vehicles"] = _vehicles_band(code("TOTAL_VEHICULOS"))
    return out.reset_index(drop=True)


# ----------------------------------------------------------------------------- Barcelona side
def barcelona_common() -> pd.DataFrame:
    """Barcelona 2025 crashes with a death or a serious injury, in the common columns."""
    crashes = barcelona.read_crashes()
    compatible = crashes[(crashes.n_deaths + crashes.n_serious_injuries) > 0].copy()
    out = pd.DataFrame(
        {
            "Numero_expedient": compatible[barcelona.KEY],
            "fatal": (compatible.n_deaths > 0).astype("int8"),
            "year": compatible["year"].astype(int),
            "domain": "Barcelona 2025 (Guàrdia Urbana)",
        }
    )
    out["bcn_weekday"] = compatible["weekday"].astype(str)
    out["bcn_hour_band"] = _hour_band(compatible["hour"])
    out["bcn_crash_type"] = compatible["accident_type"].map(BCN_CRASH).fillna(OTHER_TYPES)
    out["bcn_involves_pedestrian"] = compatible["n_pedestrian_records"].gt(0).astype(float)
    out["bcn_involves_motorcycle"] = compatible["vehicle_records_include_motorcycle"].astype(float)
    out["bcn_involves_moped"] = compatible["vehicle_records_include_moped"].astype(float)
    out["bcn_involves_bicycle"] = compatible["vehicle_records_include_bicycle"].astype(float)
    out["bcn_vehicles"] = _vehicles_band(compatible["n_vehicles"])
    return out.reset_index(drop=True)


def catalogue_frame() -> pd.DataFrame:
    rows = []
    for pair, fields in (
        ("Catalonia <-> DGT microdata", DGT_FIELDS),
        ("Catalonia <-> Barcelona 2025", BCN_FIELDS),
    ):
        for field in fields:
            rows.append(
                {
                    "pair": pair,
                    "field": field.name,
                    "kind": field.kind,
                    "catalonia_source": field.catalonia,
                    "other_source": field.other,
                    "semantics": field.semantics,
                    "mapping": field.mapping,
                    "status": field.status,
                    "enters_cross_source_tests": field.status in USABLE,
                }
            )
    return pd.DataFrame(rows)


def build() -> dict[str, pd.DataFrame]:
    tables = {
        CAT_COMMON_PATH: (catalonia_common(), "one Catalan crash", "cat_crash_id"),
        DGT_COMMON_PATH: (
            dgt_common(),
            "one DGT crash with a death or serious injury within 24 hours (Spain, 2016-2024)",
            "dgt_crash_id",
        ),
        BCN_COMMON_PATH: (
            barcelona_common(),
            "one Barcelona 2025 crash with a death or serious injury",
            "Numero_expedient",
        ),
    }
    out = {}
    for path, (frame, unit, key) in tables.items():
        if frame[key].duplicated().any():
            raise ValueError(f"{path.name}: duplicate ids")
        write_parquet(
            frame,
            path,
            {
                "unit_of_observation": unit,
                "key": key,
                "harmonised_columns": [c for c in frame.columns if c.startswith(("dgt_", "bcn_"))],
            },
        )
        out[path.stem] = frame
    return out


def read(path) -> pd.DataFrame:
    if not path.exists():
        build()
    return pd.read_parquet(path)


# ----------------------------------------------------------------------------- validation
MAX_OVERLAP_JSD = 0.005


def jensen_shannon(a: pd.Series, b: pd.Series) -> float:
    """Jensen-Shannon divergence (base 2, 0 = identical, 1 = disjoint) of two category mixes."""
    p = a.astype(str).value_counts(normalize=True)
    q = b.astype(str).value_counts(normalize=True)
    index = p.index.union(q.index)
    p, q = p.reindex(index, fill_value=0.0).to_numpy(), q.reindex(index, fill_value=0.0).to_numpy()
    m = (p + q) / 2

    def kl(x: np.ndarray, y: np.ndarray) -> float:
        mask = x > 0
        return float(np.sum(x[mask] * np.log2(x[mask] / y[mask])))

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def validate_dgt(cat: pd.DataFrame | None = None, dgt: pd.DataFrame | None = None) -> pd.DataFrame:
    """Each DGT common field on the crashes both sources describe: Catalonia, 2016-2023.

    The Catalan file and the DGT microdata's Catalan provinces hold the same crashes (their
    province-year counts agree), so a correct mapping gives the same distribution on both sides.
    A field whose mapped distributions differ (JSD above :data:`MAX_OVERLAP_JSD`) measures
    different things in the two sources and is left out of every cross-source model.
    """
    cat = read(CAT_COMMON_PATH) if cat is None else cat
    dgt = read(DGT_COMMON_PATH) if dgt is None else dgt
    years = sorted(set(cat.year) & set(dgt.year))
    left = cat[cat.year.isin(years)]
    right = dgt[dgt.domain.eq("Catalonia (DGT records)") & dgt.year.isin(years)]
    rows = []
    for field in DGT_FIELDS:
        column = f"dgt_{field.name}"
        if column not in cat.columns:
            rows.append(
                {
                    "field": field.name,
                    "a_priori_status": field.status,
                    "overlap_jsd": float("nan"),
                    "validated": False,
                    "enters_cross_source_tests": False,
                }
            )
            continue
        divergence = 0.0 if field.kind == "numeric" else jensen_shannon(left[column], right[column])
        ok = field.status in USABLE and divergence <= MAX_OVERLAP_JSD
        rows.append(
            {
                "field": field.name,
                "a_priori_status": field.status,
                "overlap_jsd": divergence,
                "validated": divergence <= MAX_OVERLAP_JSD,
                "enters_cross_source_tests": ok,
            }
        )
    out = pd.DataFrame(rows)
    out.attrs["overlap"] = {
        "years": f"{years[0]}-{years[-1]}",
        "catalan_rows": len(left),
        "dgt_rows": len(right),
        "catalan_fatal": int(left.fatal.sum()),
        "dgt_fatal": int(right.fatal.sum()),
    }
    return out


def dgt_model_fields() -> list[str]:
    """DGT common fields that passed both the a-priori and the overlap validation."""
    table = validate_dgt()
    return [f"dgt_{name}" for name in table.loc[table.enters_cross_source_tests, "field"]]
