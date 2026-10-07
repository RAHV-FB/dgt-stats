"""Barcelona 2025: staging, the canonical crash and person tables, and the cause aggregates.

The six Guàrdia Urbana tables share one key, ``Numero_expedient`` (spelt ``Número_expedient`` in
the driver-cause file; the *name* is normalised in :mod:`sources`, never the values). Their
cardinalities, checked on every build rather than assumed:

=====================  =========================  ==========================================
table                  rows per crash             how it reaches the crash table
=====================  =========================  ==========================================
crashes                exactly 1                  is the crash table
accident types         exactly 1                  ``merge(validate="one_to_one")``
mediate causes         1 or more (blank = none)   aggregated to one row per crash first
driver causes          1 or more (no person key)  aggregated to one row per crash first
people                 1 or more                  stays person-level; crash context joins
                                                  onto it ``validate="many_to_one"``
vehicle records        1 or more (semantics       only type *presence* per crash is used;
                       unproven, see vehicles.py) row counts are not read as vehicles
=====================  =========================  ==========================================

Every source column is kept with its published values; derived columns are added beside them in
English snake_case. Wording follows the source: a cause flag says a cause *was recorded* for the
crash, not that it caused the crash or which person it concerned.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from dgt_stats.microdata import coordinates, sources
from dgt_stats.microdata.common import (
    assert_unique,
    blank,
    read_provenance,
    slug,
    to_float,
    to_int,
    write_parquet,
)
from dgt_stats.paths import BARCELONA_STAGING_DIR, PROCESSED_DATA_DIR

log = logging.getLogger(__name__)

KEY = sources.BCN_ID
ROLES = (
    "bcn_accidents",
    "bcn_accident_types",
    "bcn_mediate_causes",
    "bcn_driver_causes",
    "bcn_people",
    "bcn_vehicles",
)

PROCESSED_ACCIDENTS = PROCESSED_DATA_DIR / "barcelona_accidents.parquet"
PROCESSED_PEOPLE = PROCESSED_DATA_DIR / "barcelona_people.parquet"
PROCESSED_MEDIATE = PROCESSED_DATA_DIR / "barcelona_crash_mediate_causes.parquet"
PROCESSED_DRIVER_CAUSES = PROCESSED_DATA_DIR / "barcelona_crash_driver_causes.parquet"
PROCESSED_VEHICLE_TYPES = PROCESSED_DATA_DIR / "barcelona_crash_vehicle_types.parquet"


def staging_path(role: str) -> Path:
    return BARCELONA_STAGING_DIR / f"{role}.parquet"


# ----------------------------------------------------------------------------- code lists
# Every value below was read from the 2025 files. A value that is not listed stops the build
# (victimisation) or is kept under its own slug (causes), so nothing is silently re-coded.

WEEKDAYS = {
    "Dilluns": "Monday",
    "Dimarts": "Tuesday",
    "Dimecres": "Wednesday",
    "Dijous": "Thursday",
    "Divendres": "Friday",
    "Dissabte": "Saturday",
    "Diumenge": "Sunday",
}
SHIFTS = {"Matí": "morning", "Tarda": "afternoon", "Nit": "night"}
SEXES = {"H": "male", "D": "female"}
ROLES_OF_PERSON = {"Conductor": "driver", "Passatger": "passenger", "Vianant": "pedestrian"}

# Descripcio_victimitzacio: (detailed category, severity level). "Mort natural" is a death the
# police recorded as natural, not as an injury from the crash: it is kept and reported, and left
# out of every injury-severity target. A blank is "not recorded", never "uninjured".
VICTIMISATION: dict[str, tuple[str, str]] = {
    "Il.lès": ("uninjured", "uninjured"),
    "Ferit lleu: Rebutja assistència sanitària": ("minor_refused_care", "minor"),
    "Ferit lleu: Amb assistència sanitària en lloc d'accident": ("minor_treated_at_scene", "minor"),
    "Ferit lleu: Hospitalització fins a 24h": ("minor_hospital_up_to_24h", "minor"),
    "Ferit greu: hospitalització superior a 24h": ("serious_hospital_over_24h", "serious"),
    "Mort (dins 24h posteriors accident)": ("died_within_24h", "fatal"),
    "Mort (després de 24h posteriors accident)": ("died_after_24h", "fatal"),
    "Mort natural": ("natural_death", "excluded_natural_death"),
    "": ("not_recorded", "not_recorded"),
}
SEVERITY_TARGET = {"uninjured": 0, "minor": 0, "serious": 1, "fatal": 1}

MEDIATE_CAUSES = {
    "Alcoholèmia": ("alcohol", "alcohol"),
    "Excés de velocitat o inadequada": ("speed", "excessive or inappropriate speed"),
    "Drogues o medicaments": ("drugs_medication", "drugs or medication"),
    "Calçada en mal estat": ("road_surface", "road surface in poor condition"),
    "Estat de la senyalització": ("signalling", "state of the signalling"),
    "Factors meteorològics": ("weather", "weather"),
    "Objectes o animals a la calçada": ("object_or_animal", "objects or animals on the road"),
}
DRIVER_CAUSES = {
    "Manca d'atenció a la conducció": ("inattention", "lack of attention to driving"),
    "No respectar distàncies": ("following_distance", "not keeping a safe distance"),
    "Gir indegut o sense precaució": ("improper_turn", "improper or careless turn"),
    "Desobeir semàfor": ("traffic_light", "disobeying a traffic light"),
    "Canvi de carril sense precaució": ("lane_change", "careless lane change"),
    "Desobeir altres senyals": ("other_signal", "disobeying other signals"),
    "Avançament defectuós/improcedent": ("overtaking", "faulty or improper overtaking"),
    "Manca precaució incorporació circulació": ("merging", "careless merging into traffic"),
    "No respectat pas de vianants": ("pedestrian_crossing", "not respecting a pedestrian crossing"),
    "Manca precaució efectuar marxa enrera": ("reversing", "careless reversing"),
    "No cedir la dreta": ("right_of_way", "not giving way to the right"),
    "Envair calçada contrària": ("wrong_side", "invading the opposite carriageway"),
    "Fallada mecànica o avaria": ("mechanical_failure", "mechanical failure or breakdown"),
    "Altres": ("other", "other"),
    "No determinada": ("not_determined", "not determined"),
}
# Categories that say no specific driver cause was established: kept, but not counted as causes.
DRIVER_CAUSE_NON_SUBSTANTIVE = {"not_determined"}

# Vehicle types (people: Desc_Tipus_vehicle_implicat; vehicle records: Descripcio_tipus_vehicle).
VEHICLE_GROUPS = {
    "Turisme": "car",
    "Tot terreny": "car",
    "Taxi": "taxi",
    "Motocicleta": "motorcycle",
    "Ciclomotor": "moped",
    "Bicicleta": "bicycle",
    "Bicicleta pedaleig assistit": "bicycle",
    "Veh. mobilitat personal amb motor": "personal_mobility_vehicle",
    "Veh. mobilitat personal sense motor": "personal_mobility_vehicle",
    "Furgoneta": "van_or_light_truck",
    "Camió rígid <= 3,5 tones": "van_or_light_truck",
    "Pick-up": "van_or_light_truck",
    "Camió rígid > 3,5 tones": "heavy_truck",
    "Tractor camió": "heavy_truck",
    "Autobús": "bus_or_coach",
    "Autobús articulat": "bus_or_coach",
    "Autocar": "bus_or_coach",
    "Microbús <= 17": "bus_or_coach",
    "Tren o tramvia": "tram_or_train",
    "Ambulància": "other",
    "Maquinària d'obres i serveis": "other",
    "Altres vehicles amb motor": "other",
    "Tricicle": "other",
    "Quadricicle < 75 cc": "other",
    "Autocaravana": "other",
    "Sense Informar": "not_recorded",
    "": "not_recorded",
}
VEHICLE_GROUP_ORDER = (
    "car",
    "taxi",
    "motorcycle",
    "moped",
    "bicycle",
    "personal_mobility_vehicle",
    "van_or_light_truck",
    "heavy_truck",
    "bus_or_coach",
    "tram_or_train",
    "other",
    "not_recorded",
)

AGE_BANDS = (
    (0, 15, "0-15"),
    (16, 24, "16-24"),
    (25, 34, "25-34"),
    (35, 44, "35-44"),
    (45, 54, "45-54"),
    (55, 64, "55-64"),
    (65, 74, "65-74"),
    (75, 200, "75+"),
)

ACCIDENT_TYPES = {
    "Col.lisió lateral": "side collision",
    "Abast": "rear-end collision",
    "Col.lisió fronto-lateral": "front-side collision",
    "Atropellament": "pedestrian struck",
    "Xoc contra element estàtic": "collision with a fixed object",
    "Caiguda (dues rodes)": "fall (two-wheeler)",
    "Caiguda interior vehicle": "fall inside a vehicle",
    "Abast multiple": "multiple rear-end collision",
    "Altres": "other",
    "Col.lisió frontal": "head-on collision",
    "Encalç": "rear collision while catching up",
    "Sortida de via amb xoc o col.lisió": "run-off-road with collision",
    "Xoc amb animal a la calçada": "collision with an animal",
    "Bolcada (més de dues rodes)": "overturn (more than two wheels)",
    "Sortida de via amb bolcada": "run-off-road with overturn",
    "Resta sortides de via": "other run-off-road",
    "": "not recorded",
}

PEDESTRIAN_CAUSES = {
    "Desobeir el senyal del semàfor": "disobeying the traffic light",
    "Creuar per fora pas de vianants": "crossing outside a pedestrian crossing",
    "Transitar a peu per la calçada": "walking on the carriageway",
    "Desobeir altres senyals": "disobeying other signals",
    "Altres": "other",
    "": "none recorded",
}


# ----------------------------------------------------------------------------- staging
def stage(force: bool = False) -> dict[str, Path]:
    """Copy each raw table into ``data/staging/barcelona`` as text with normalised column names."""
    files = sources.discover()
    written = {}
    for role in ROLES:
        target = staging_path(role)
        item = sources.resolve_one(role, files)
        if target.exists() and not force:
            if read_provenance(target).get("source_sha256") == item.sha256:
                written[role] = target
                continue
        frame = sources.read_raw(item.path)
        frame.insert(1, "source_file", item.relative)
        write_parquet(
            frame,
            target,
            {
                "table": role,
                "unit_of_observation": item.role.unit,
                "cardinality": item.role.cardinality,
                "source_file": item.relative,
                "source_sha256": item.sha256,
                "years": list(item.years),
            },
        )
        log.info("staged %s: %s rows from %s", role, f"{len(frame):,}", item.relative)
        written[role] = target
    return written


def load(role: str) -> pd.DataFrame:
    path = staging_path(role)
    if not path.exists():
        stage()
    return pd.read_parquet(path)


# ----------------------------------------------------------------------------- crash table
def _date_fields(frame: pd.DataFrame, year: str, month: str, day: str) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out["year"] = to_int(frame[year])
    out["month"] = to_int(frame[month])
    out["day"] = to_int(frame[day])
    out["date"] = pd.to_datetime(dict(year=out.year, month=out.month, day=out.day), errors="coerce")
    return out


def crash_core(accidents: pd.DataFrame) -> pd.DataFrame:
    """The crash file with its derived fields; one row per ``Numero_expedient``."""
    assert_unique(accidents, KEY, "Barcelona crash table")
    out = accidents.copy()
    dates = _date_fields(out, "NK_Any", "Mes_any", "Dia_mes")
    out = pd.concat([out, dates], axis=1)
    out["weekday"] = out["Descripcio_dia_setmana"].map(WEEKDAYS).astype("string")
    out["weekday_from_date"] = out["date"].dt.day_name().astype("string")
    out["hour"] = to_int(out["Hora_dia"])
    out["shift"] = out["Descripcio_torn"].map(SHIFTS).astype("string")
    out["district_code"] = to_int(out["Codi_districte"])
    out["district"] = out["Nom_districte"].astype("string")
    out["neighbourhood_code"] = to_int(out["Codi_barri"])
    out["neighbourhood"] = out["Nom_barri"].astype("string")
    out["street"] = out["Nom_carrer"].astype("string")
    # Count columns: the files leave a zero blank. No count cell holds "0", and the identity
    # victims = deaths + serious + minor holds on every row only when a blank is read as zero;
    # quality.py re-checks both on every build and against the person table.
    for source_column, name in (
        ("Numero_morts", "n_deaths"),
        ("Numero_lesionats_greus", "n_serious_injuries"),
        ("Numero_lesionats_lleus", "n_minor_injuries"),
        ("Numero_victimes", "n_victims"),
        ("Numero_vehicles_implicats", "n_vehicles"),
    ):
        out[name] = to_int(out[source_column]).fillna(0).astype("int64")
    out["serious_or_fatal_crash"] = (out.n_deaths + out.n_serious_injuries > 0).astype("int8")
    out["fatal_crash"] = (out.n_deaths > 0).astype("int8")
    out["pedestrian_cause"] = out["Descripcio_causa_vianant"].map(PEDESTRIAN_CAUSES)
    out["pedestrian_cause"] = (
        out["pedestrian_cause"].fillna(out["Descripcio_causa_vianant"]).astype("string")
    )
    out["pedestrian_cause_recorded"] = (~blank(out["Descripcio_causa_vianant"])).astype(bool)
    corrected = coordinates.corrected_utm(out, "bcn_accidents")
    out = pd.concat([out, corrected], axis=1)
    out["longitude"] = to_float(out["Longitud_WGS84"])
    out["latitude"] = to_float(out["Latitud_WGS84"])
    return out


def accident_types(types: pd.DataFrame) -> pd.DataFrame:
    """One row per crash: the recorded accident type (raw and English)."""
    assert_unique(types, KEY, "Barcelona accident-type table")
    out = types[[KEY, "Descripcio_tipus_accident"]].copy()
    out["accident_type"] = out["Descripcio_tipus_accident"].map(ACCIDENT_TYPES)
    unknown = out["accident_type"].isna()
    out.loc[unknown, "accident_type"] = out.loc[unknown, "Descripcio_tipus_accident"]
    out["accident_type"] = out["accident_type"].astype("string")
    return out


def _cause_flags(
    frame: pd.DataFrame, column: str, codes: dict[str, tuple[str, str]], prefix: str
) -> tuple[pd.DataFrame, list[str]]:
    """Crash x category indicator of which categories appear among a crash's rows."""
    values = frame[column].fillna("")
    slugs = values.map(lambda v: codes[v][0] if v in codes else slug(v) if v.strip() else "")
    present = (
        pd.crosstab(frame[KEY], slugs).drop(columns="", errors="ignore").gt(0)
        if len(frame)
        else pd.DataFrame()
    )
    ordered = [code for code, _ in codes.values() if code in present.columns]
    ordered += sorted(c for c in present.columns if c not in ordered)
    present = present[ordered]
    present.columns = [f"{prefix}_{name}_recorded" for name in ordered]
    return present, ordered


def aggregate_mediate(mediate: pd.DataFrame) -> pd.DataFrame:
    """One row per crash from the mediate-cause table (one or more rows per crash).

    A crash with a single blank row has no mediate cause recorded; the source has no category for
    "explicitly no cause", so a ``False`` flag means *not recorded*, not *absent*.
    """
    flags, codes = _cause_flags(mediate, "Descripcio_causa_mediata", MEDIATE_CAUSES, "mediate")
    texts = mediate.assign(_v=mediate["Descripcio_causa_mediata"].fillna("").str.strip())
    grouped = texts.groupby(KEY)["_v"]
    out = pd.DataFrame(
        {
            "mediate_table_rows": grouped.size(),
            "mediate_causes": grouped.agg(lambda s: " | ".join(sorted(v for v in s if v))),
            "n_mediate_causes": grouped.agg(lambda s: int((s != "").sum())),
        }
    )
    out = out.join(flags).fillna({c: False for c in flags.columns})
    for column in flags.columns:
        out[column] = out[column].astype(bool)
    out["mediate_cause_status"] = np.where(out.n_mediate_causes > 0, "recorded", "none_recorded")
    out = out.reset_index()
    assert_unique(out, KEY, "aggregated mediate causes")
    out.attrs["codes"] = codes
    return out


def aggregate_driver_causes(driver: pd.DataFrame) -> pd.DataFrame:
    """One row per crash from the driver-cause table, which has no person or vehicle key.

    These flags say which driver-related causes the police recorded *in the crash*. They cannot say
    which driver, person or vehicle a cause belongs to, and are never attached to a person.
    """
    flags, codes = _cause_flags(driver, "Causa_conductor", DRIVER_CAUSES, "driver_cause")
    values = driver.assign(_v=driver["Causa_conductor"].fillna("").str.strip())
    values["_slug"] = values["_v"].map(
        lambda v: DRIVER_CAUSES[v][0] if v in DRIVER_CAUSES else slug(v) if v else ""
    )
    substantive = values["_slug"].ne("") & ~values["_slug"].isin(DRIVER_CAUSE_NON_SUBSTANTIVE)
    grouped = values.groupby(KEY)
    out = pd.DataFrame(
        {
            "driver_cause_table_rows": grouped.size(),
            "driver_causes": grouped["_v"].agg(lambda s: " | ".join(sorted(v for v in s if v))),
            "n_driver_causes_recorded": values[substantive].groupby(KEY).size(),
        }
    )
    out["n_driver_causes_recorded"] = out["n_driver_causes_recorded"].fillna(0).astype("int64")
    out = out.join(flags)
    for column in flags.columns:
        out[column] = out[column].fillna(False).astype(bool)
    has_not_determined = values[values._slug == "not_determined"].groupby(KEY).size()
    out["driver_cause_status"] = np.select(
        [
            out.n_driver_causes_recorded > 0,
            out.index.isin(has_not_determined.index),
        ],
        ["recorded", "not_determined"],
        default="blank",
    )
    out = out.reset_index()
    assert_unique(out, KEY, "aggregated driver causes")
    out.attrs["codes"] = codes
    return out


def vehicle_type_presence(vehicles: pd.DataFrame) -> pd.DataFrame:
    """One row per crash: which vehicle groups appear among its vehicle records.

    Only presence is used, so whether a vehicle record is one vehicle, a duplicate or a record per
    person (see :mod:`vehicles`) does not change the answer: a crash with any record of a
    motorcycle involved a motorcycle. Row counts of this table are never read as vehicle counts.
    """
    groups = vehicles["Descripcio_tipus_vehicle"].fillna("").map(VEHICLE_GROUPS)
    groups = groups.fillna("other")
    present = pd.crosstab(vehicles[KEY], groups).gt(0)
    present = present.reindex(columns=list(VEHICLE_GROUP_ORDER), fill_value=False)
    present.columns = [f"vehicle_records_include_{name}" for name in present.columns]
    present.insert(0, "vehicle_table_rows", vehicles.groupby(KEY).size())
    out = present.reset_index()
    assert_unique(out, KEY, "vehicle-type presence")
    return out


def person_composition(people: pd.DataFrame) -> pd.DataFrame:
    """One row per crash: how many person records of each role it has (records, not people)."""
    roles = people["Descripcio_tipus_persona"].map(ROLES_OF_PERSON).fillna("other")
    counts = pd.crosstab(people[KEY], roles)
    counts = counts.reindex(columns=["driver", "passenger", "pedestrian"], fill_value=0)
    counts.columns = [f"n_{role}_records" for role in counts.columns]
    counts.insert(0, "n_person_records", people.groupby(KEY).size())
    return counts.reset_index()


def build_crashes(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The canonical crash table: the crash file, its type, and the per-crash aggregates."""
    crashes = crash_core(tables["bcn_accidents"])
    types = accident_types(tables["bcn_accident_types"])
    out = crashes.merge(types, on=KEY, how="left", validate="one_to_one", indicator="_types")
    missing = int((out._types != "both").sum())
    if missing:
        raise ValueError(f"{missing} crashes have no accident-type row")
    out = out.drop(columns="_types")
    for extra in (
        aggregate_mediate(tables["bcn_mediate_causes"]),
        aggregate_driver_causes(tables["bcn_driver_causes"]),
        vehicle_type_presence(tables["bcn_vehicles"]),
        person_composition(tables["bcn_people"]),
    ):
        unknown = set(extra[KEY]) - set(out[KEY])
        if unknown:
            raise ValueError(
                f"{len(unknown)} ids in an aggregate are not crashes: {sorted(unknown)[:3]}"
            )
        out = out.merge(extra, on=KEY, how="left", validate="one_to_one")
    flag_columns = [
        c for c in out.columns if c.endswith("_recorded") and c.startswith(("mediate_", "driver_"))
    ]
    for column in flag_columns:
        # A crash absent from a cause table would be missing, not "not recorded"; none is today.
        out[column] = out[column].astype("boolean")
    for column in ("mediate_cause_status", "driver_cause_status"):
        out[column] = out[column].fillna("absent_from_table").astype("string")
    assert_unique(out, KEY, "canonical Barcelona crash table")
    return out


# ----------------------------------------------------------------------------- people
def age_band(age: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=age.index, dtype="string")
    for low, high, label in AGE_BANDS:
        out[(age >= low) & (age <= high)] = label
    return out.fillna("not recorded")


def build_people(people: pd.DataFrame) -> pd.DataFrame:
    """One row per person record, with the documented severity target beside the raw category."""
    unknown = set(people["Descripcio_victimitzacio"].fillna("")) - set(VICTIMISATION)
    if unknown:
        raise ValueError(f"unlisted victimisation categories: {sorted(unknown)}; review the target")
    out = people.copy()
    order = out.groupby(KEY).cumcount() + 1
    out.insert(0, "person_record_id", out[KEY] + "-P" + order.astype(str).str.zfill(2))
    assert_unique(out, "person_record_id", "Barcelona person table")
    dates = _date_fields(out, "NK_Any", "Mes_any", "Dia_mes")
    out = pd.concat([out, dates], axis=1)
    out["age"] = to_int(out["Edat"])
    out["age_band"] = age_band(out["age"])
    out["sex"] = out["Descripcio_sexe"].map(SEXES).fillna("not recorded").astype("string")
    out["person_role"] = out["Descripcio_tipus_persona"].map(ROLES_OF_PERSON).astype("string")
    raw_vehicle = out["Desc_Tipus_vehicle_implicat"].fillna("")
    out["associated_vehicle_group"] = raw_vehicle.map(VEHICLE_GROUPS).fillna("other")
    out["associated_vehicle_group"] = out["associated_vehicle_group"].astype("string")
    victim = out["Descripcio_victimitzacio"].fillna("")
    out["victimisation"] = victim.map(lambda v: VICTIMISATION[v][0]).astype("string")
    out["injury_severity"] = victim.map(lambda v: VICTIMISATION[v][1]).astype("string")
    out["serious_or_fatal"] = out["injury_severity"].map(SEVERITY_TARGET).astype("Int8")
    out["fatal"] = (
        out["injury_severity"].map({"fatal": 1, "serious": 0, "minor": 0, "uninjured": 0})
    ).astype("Int8")
    out["hour"] = to_int(out["Hora_dia"])
    return out


# ----------------------------------------------------------------------------- build
def build(force: bool = False) -> dict[str, Path]:
    """Stage the six tables and write the processed Barcelona tables."""
    staged = stage(force=force)
    tables = {role: pd.read_parquet(path) for role, path in staged.items()}
    provenance = {
        "sources": {
            role: {
                "file": read_provenance(staged[role])["source_file"],
                "sha256": read_provenance(staged[role])["source_sha256"],
            }
            for role in ROLES
        }
    }
    crashes = build_crashes(tables)
    people = build_people(tables["bcn_people"])
    orphans = set(people[KEY]) - set(crashes[KEY])
    if orphans:
        raise ValueError(f"{len(orphans)} person records point at unknown crashes")
    mediate = aggregate_mediate(tables["bcn_mediate_causes"])
    driver = aggregate_driver_causes(tables["bcn_driver_causes"])
    vehicles = vehicle_type_presence(tables["bcn_vehicles"])
    outputs = {
        PROCESSED_ACCIDENTS: (crashes, "one crash (Numero_expedient)", KEY),
        PROCESSED_PEOPLE: (people, "one person record (no source person id)", "person_record_id"),
        PROCESSED_MEDIATE: (mediate, "one crash (aggregated mediate causes)", KEY),
        PROCESSED_DRIVER_CAUSES: (driver, "one crash (aggregated driver causes)", KEY),
        PROCESSED_VEHICLE_TYPES: (vehicles, "one crash (vehicle-type presence)", KEY),
    }
    written = {}
    for path, (frame, unit, key) in outputs.items():
        write_parquet(frame, path, {"unit_of_observation": unit, "key": key, **provenance})
        log.info("processed %s: %s rows", path.name, f"{len(frame):,}")
        written[path.stem] = path
    return written


def read_crashes() -> pd.DataFrame:
    if not PROCESSED_ACCIDENTS.exists():
        build()
    return pd.read_parquet(PROCESSED_ACCIDENTS)


def read_people() -> pd.DataFrame:
    if not PROCESSED_PEOPLE.exists():
        build()
    return pd.read_parquet(PROCESSED_PEOPLE)
