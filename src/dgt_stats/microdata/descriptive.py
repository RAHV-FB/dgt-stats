"""Transparent rates behind the models: severity shares and frequencies, each with its N.

Three questions are kept apart, as the data allow:

* **frequency**: how many recorded crashes or people (counts, by month, hour, place, year);
* **severity**: among recorded crashes or people, how often the outcome was fatal or serious
  (shares with Wilson 95% intervals);
* **risk** (an outcome per unit of exposure) is not computed here: neither regional source has an
  exposure denominator. The only population-based rate is in :mod:`crosssource`, at the
  province-year level where INE residents correspond to the numerator's geography.

Every row carries ``n`` and the event count. Levels with fewer than :data:`MIN_N` rows are kept and
flagged ``small_n``; the site does not quote them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgt_stats.microdata import barcelona, catalonia
from dgt_stats.microdata.common import wilson
from dgt_stats.paths import TABLES_DIR

MIN_N = 30

CAT_DIMENSIONS = {
    "zone": "D_SUBZONA",
    "road type": "D_TIPUS_VIA",
    "speed limit": "speed_limit_category",
    "lighting": "D_LLUMINOSITAT",
    "crash type": "tipAcc",
    "crash subtype": "D_SUBTIPUS_ACCIDENT",
    "intersection": "D_INTER_SECCIO",
    "weather": "D_CLIMATOLOGIA",
    "surface": "D_SUPERFICIE",
    "hour": "hour_band",
    "weekday": "weekday",
    "demarcation": "demarcation",
    "year": "year",
    "units involved": "single_unit_label",
}
# English labels for the Catalan code values shown on the site; the published value is kept in
# ``level`` beside it. Definitions only: no value is re-coded.
CATALAN_LABELS = {
    "Zona urbana": "urban street",
    "Carretera": "interurban road",
    "Travessera": "through-town road",
    "Via urbana( inclou carrer i carrer residencial)": "urban street",
    "Carretera convencional": "conventional road",
    "Autovia": "dual carriageway",
    "Autopista": "motorway",
    "Camí rural/pista forestal": "rural track",
    "Altres": "other",
    "De dia, dia clar": "daylight, clear",
    "De dia, dia fosc": "daylight, overcast",
    "Alba o capvespre": "dawn or dusk",
    "De nit, il·luminació artificial suficient": "night, adequate street lighting",
    "De nit, il·luminació artificial insuficient": "night, inadequate street lighting",
    "De nit, sense llum artificial": "night, no street lighting",
    "Sense especificar": "not specified",
    "Sense Especificar": "not specified",
    "Col.lisió de vehicles en marxa": "collision between moving vehicles",
    "Atropellament": "pedestrian struck",
    "Sortida de la calcada sense especificar": "run-off-road",
    "Bolcada a la calcada": "fall or overturn on the road",
    "Col.lisió d'un vehicle contra un obstacle de la calcada": "collision with an obstacle",
    "Envestida (frontal lateral)": "front-side collision",
    "Resta sortides de via": "other run-off-road",
    "Caiguda en la via": "fall on the road",
    "Fregament o col·lisió lateral": "side collision",
    "Col·lisió frontal": "head-on collision",
    "Encalç": "rear-end collision",
    "Xoc contra objecte/obstacle sense sortida prèvia de via": "hit an object without leaving the road",
    "Sortida de via amb xoc o col·lisió": "run-off-road with collision",
    "Sortida de via amb bolcada": "run-off-road with overturn",
    "Xoc amb animal a la calçada": "hit an animal",
    "Sortida de via amb atropellament": "run-off-road striking a pedestrian",
    "En secció": "road section",
    "Dintre intersecció": "inside a junction",
    "Arribant o eixint intersecció fins 50m": "within 50 m of a junction",
    "Bon temps": "fine",
    "Pluja dèbil": "light rain",
    "Pluja forta": "heavy rain",
    "Calamarsa": "hail",
    "Nevant": "snow",
    "Sec i net": "dry and clean",
    "Mullat": "wet",
    "Relliscós": "slippery",
    "Inundat": "flooded",
    "Gelat": "icy",
    "Nevat": "snow-covered",
}

CAT_UNIT_FLAGS = {
    flag: flag.replace("involves_", "").replace("_", " ") for flag in catalonia.UNIT_FLAGS.values()
}

BCN_PERSON_DIMENSIONS = {
    "road user": "road_user",
    "age band": "age_band",
    "role": "person_role",
    "associated vehicle": "associated_vehicle_group",
    "sex": "sex",
    "crash type": "accident_type",
    "shift": "shift",
    "district": "district",
}
BCN_CRASH_DIMENSIONS = {
    "crash type": "accident_type",
    "district": "district",
    "shift": "shift",
    "weekday": "weekday",
    "vehicles involved": "n_vehicles_band",
    "mediate causes recorded": "mediate_cause_status",
    "driver causes recorded": "driver_cause_status",
    "pedestrian cause": "pedestrian_cause",
}


def shares(
    frame: pd.DataFrame,
    target: str,
    dimensions: dict[str, str],
    dataset: str,
    outcome: str,
    unit: str,
) -> pd.DataFrame:
    rows = []
    for dimension, column in dimensions.items():
        grouped = frame.groupby(column, dropna=False)[target].agg(["size", "sum"])
        for level, (n, events) in grouped.iterrows():
            rows.append(
                {
                    "dataset": dataset,
                    "unit": unit,
                    "outcome": outcome,
                    "dimension": dimension,
                    "level": str(level),
                    "n": int(n),
                    "events": int(events),
                }
            )
    return _finish(pd.DataFrame(rows))


def flag_shares(
    frame: pd.DataFrame,
    target: str,
    flags: dict[str, str],
    dataset: str,
    outcome: str,
    unit: str,
    dimension: str,
) -> pd.DataFrame:
    """Shares among the rows where each (overlapping) flag is true, and among all rows."""
    rows = [
        {
            "dataset": dataset,
            "unit": unit,
            "outcome": outcome,
            "dimension": dimension,
            "level": "all",
            "n": len(frame),
            "events": int(frame[target].sum()),
        }
    ]
    for column, label in flags.items():
        mask = frame[column].fillna(False).astype(bool)
        rows.append(
            {
                "dataset": dataset,
                "unit": unit,
                "outcome": outcome,
                "dimension": dimension,
                "level": label,
                "n": int(mask.sum()),
                "events": int(frame.loc[mask, target].sum()),
            }
        )
    return _finish(pd.DataFrame(rows))


def _finish(out: pd.DataFrame) -> pd.DataFrame:
    out["label"] = out.level.map(CATALAN_LABELS).fillna(out.level)
    out["share"] = out.events / out.n
    low, high = wilson(out.events, out.n)
    out["ci_low"], out["ci_high"] = low, high
    out["small_n"] = out.n < MIN_N
    return out


def _catalonia_label(crashes: pd.DataFrame) -> str:
    return f"Catalonia {int(crashes.year.min())}-{int(crashes.year.max())}"


def _barcelona_label(frame: pd.DataFrame) -> str:
    years = sorted(int(y) for y in frame["year"].dropna().unique())
    return f"Barcelona {years[0]}" if len(years) == 1 else f"Barcelona {years[0]}-{years[-1]}"


def catalonia_severity() -> pd.DataFrame:
    crashes = catalonia.read().copy()
    crashes["single_unit_label"] = np.where(crashes.single_unit, "one unit", "two or more units")
    out = shares(
        crashes,
        "fatal",
        CAT_DIMENSIONS,
        _catalonia_label(crashes),
        "fatal",
        "crash with a death or serious injury",
    )
    flags = flag_shares(
        crashes,
        "fatal",
        CAT_UNIT_FLAGS,
        _catalonia_label(crashes),
        "fatal",
        "crash with a death or serious injury",
        "unit type involved",
    )
    return pd.concat([out, flags], ignore_index=True)


def road_user(people: pd.DataFrame) -> pd.Series:
    """Role and the vehicle type on the record: 'motorcycle driver', 'car passenger', 'pedestrian'."""
    group = people.associated_vehicle_group.str.replace("_", " ")
    label = group + " " + people.person_role
    return label.where(people.person_role.ne("pedestrian"), "pedestrian").astype("string")


def barcelona_person_severity() -> pd.DataFrame:
    people = barcelona.read_people()
    crashes = barcelona.read_crashes()[[barcelona.KEY, "accident_type", "shift", "district"]]
    labelled = (
        people[people.serious_or_fatal.notna()]
        .drop(columns=["shift", "district"], errors="ignore")
        .merge(crashes, on=barcelona.KEY, how="left", validate="many_to_one")
    )
    labelled["road_user"] = road_user(labelled)
    labelled["serious_or_fatal"] = labelled.serious_or_fatal.astype(int)
    return shares(
        labelled,
        "serious_or_fatal",
        BCN_PERSON_DIMENSIONS,
        _barcelona_label(people),
        "serious or fatal injury",
        "person record with a recorded victimisation",
    )


def barcelona_crash_severity() -> pd.DataFrame:
    crashes = barcelona.read_crashes().copy()
    crashes["n_vehicles_band"] = pd.cut(
        crashes.n_vehicles, [0, 1, 2, 3, 100], labels=["1", "2", "3", "4 or more"]
    ).astype(str)
    out = shares(
        crashes,
        "serious_or_fatal_crash",
        BCN_CRASH_DIMENSIONS,
        _barcelona_label(crashes),
        "serious or fatal injury",
        "crash",
    )
    mediate = {
        f"mediate_{code}_recorded": f"{label} (mediate)"
        for code, label in barcelona.MEDIATE_CAUSES.values()
    }
    driver = {
        f"driver_cause_{code}_recorded": f"{label} (driver)"
        for code, label in barcelona.DRIVER_CAUSES.values()
    }
    vehicles = {
        f"vehicle_records_include_{g}": g.replace("_", " ") for g in barcelona.VEHICLE_GROUP_ORDER
    }
    parts = [
        out,
        flag_shares(
            crashes,
            "serious_or_fatal_crash",
            vehicles,
            _barcelona_label(crashes),
            "serious or fatal injury",
            "crash",
            "vehicle type present",
        ),
        flag_shares(
            crashes,
            "serious_or_fatal_crash",
            {**mediate, **driver},
            _barcelona_label(crashes),
            "serious or fatal injury",
            "crash",
            "cause recorded",
        ),
    ]
    return pd.concat(parts, ignore_index=True)


def barcelona_frequency() -> pd.DataFrame:
    """Counts of recorded crashes and of people by severity: frequency, not risk."""
    crashes = barcelona.read_crashes()
    people = barcelona.read_people()
    rows = []
    for dimension, column in (
        ("month", "month"),
        ("hour", "hour"),
        ("weekday", "weekday"),
        ("district", "district"),
    ):
        counts = crashes.groupby(column).agg(
            crashes=(barcelona.KEY, "size"),
            serious_or_fatal_crashes=("serious_or_fatal_crash", "sum"),
            deaths=("n_deaths", "sum"),
            serious_injuries=("n_serious_injuries", "sum"),
        )
        for level, values in counts.iterrows():
            rows.append({"dimension": dimension, "level": str(level), **values.to_dict()})
    out = pd.DataFrame(rows)
    severity = people.groupby(["person_role", "injury_severity"]).size().rename("person_records")
    return out, severity.reset_index()


def catalonia_frequency() -> pd.DataFrame:
    crashes = catalonia.read()
    return (
        crashes.groupby(["year", "demarcation", "zone"])
        .agg(
            crashes=("fatal", "size"),
            fatal_crashes=("fatal", "sum"),
            deaths=("n_deaths", "sum"),
            serious_injuries=("n_serious_injuries", "sum"),
        )
        .reset_index()
    )


def cause_profiles() -> pd.DataFrame:
    """How crashes with a recorded cause differ from the rest: shares of time and type, with N.

    A secondary analysis for the two mediate causes with the most cases. It describes recorded
    crashes; it does not say the cause made them happen at night or be of a given type.
    """
    crashes = barcelona.read_crashes().copy()
    crashes["weekend"] = crashes.weekday.isin(["Saturday", "Sunday"])
    crashes["night_shift"] = crashes["shift"].eq("night")
    crashes["single_vehicle"] = crashes.n_vehicles.eq(1)
    rows = []
    for code in ("alcohol", "speed"):
        flag = crashes[f"mediate_{code}_recorded"].fillna(False).astype(bool)
        for group, mask in ((f"{code} recorded", flag), (f"{code} not recorded", ~flag)):
            part = crashes[mask]
            for measure in ("night_shift", "weekend", "single_vehicle", "serious_or_fatal_crash"):
                events = int(part[measure].sum())
                rows.append(
                    {
                        "cause": code,
                        "group": group,
                        "measure": measure,
                        "n": len(part),
                        "events": events,
                    }
                )
            for crash_type, count in part.accident_type.value_counts().head(5).items():
                rows.append(
                    {
                        "cause": code,
                        "group": group,
                        "measure": f"crash type: {crash_type}",
                        "n": len(part),
                        "events": int(count),
                    }
                )
    out = pd.DataFrame(rows)
    out["share"] = out.events / out.n
    out["ci_low"], out["ci_high"] = wilson(out.events, out.n)
    out["small_n"] = out.n < MIN_N
    return out


def write() -> dict[str, pd.DataFrame]:
    bcn_frequency, bcn_people_counts = barcelona_frequency()
    tables = {
        "cat_fatal_share": catalonia_severity(),
        "cat_frequency": catalonia_frequency(),
        "bcn_person_severity_share": barcelona_person_severity(),
        "bcn_crash_severity_share": barcelona_crash_severity(),
        "bcn_frequency": bcn_frequency,
        "bcn_people_by_severity": bcn_people_counts,
        "bcn_cause_profiles": cause_profiles(),
    }
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.6g")
    return tables
