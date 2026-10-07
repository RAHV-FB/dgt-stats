"""Catalonia: the canonical table of crashes with at least one death or serious injury.

The Servei Català de Trànsit export has one row per crash and no crash identifier. Its universe is
*conditioned on severity*: every row has a death or a serious injury (``D_GRAVETAT`` is "Accident
greu" or "Accident mortal"), so it supports questions about frequency and severity *among serious
and fatal crashes*, never about whether a crash happens or how likely a crash is to be serious.

Each crash gets a surrogate key, ``cat_crash_id`` (the 1-based data row of the hash-pinned source
file), and a SHA-1 of its raw row so a repeated record can be found. All 58 source columns are kept
as published; derived columns are added beside them.

``C_VELOCITAT_VIA`` is the road's speed limit, not a vehicle's speed. The file codes it as a
number only when ``D_LIMIT_VELOCITAT`` is "Senyal velocitat" (a posted limit). Under "Genérica
via" (the generic limit for the type of road) it holds 100, 999 or "NA" whatever the road, 100
even on thousands of urban streets, so there it is a code, not a limit: ``speed_limit_kmh`` is
filled only for posted limits and the generic case is its own category.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from dgt_stats.microdata import sources
from dgt_stats.microdata.common import (
    assert_unique,
    read_provenance,
    to_float,
    to_int,
    write_parquet,
)
from dgt_stats.paths import CATALONIA_STAGING_DIR, PROCESSED_DATA_DIR

log = logging.getLogger(__name__)

ROLE = "cat_severe_crashes"
STAGING = CATALONIA_STAGING_DIR / f"{ROLE}.parquet"
PROCESSED = PROCESSED_DATA_DIR / "catalonia_severe_crashes.parquet"
KEY = "cat_crash_id"

COUNT_COLUMNS = {
    "F_MORTS": "n_deaths",
    "F_FERITS_GREUS": "n_serious_injuries",
    "F_FERITS_LLEUS": "n_minor_injuries",
    "F_VICTIMES": "n_victims",
    "F_UNITATS_IMPLICADES": "n_units",
    "F_VIANANTS_IMPLICADES": "n_pedestrians",
    "F_BICICLETES_IMPLICADES": "n_bicycles",
    "F_CICLOMOTORS_IMPLICADES": "n_mopeds",
    "F_MOTOCICLETES_IMPLICADES": "n_motorcycles",
    "F_VEH_LLEUGERS_IMPLICADES": "n_light_vehicles",
    "F_VEH_PESANTS_IMPLICADES": "n_heavy_vehicles",
    "F_ALTRES_UNIT_IMPLICADES": "n_other_units",
    "F_UNIT_DESC_IMPLICADES": "n_unknown_units",
}
UNIT_FLAGS = {
    "n_pedestrians": "involves_pedestrian",
    "n_bicycles": "involves_bicycle",
    "n_mopeds": "involves_moped",
    "n_motorcycles": "involves_motorcycle",
    "n_light_vehicles": "involves_light_vehicle",
    "n_heavy_vehicles": "involves_heavy_vehicle",
    "n_other_units": "involves_other_unit",
}
SEVERITY = {"Accident mortal": "fatal", "Accident greu": "serious"}

POSTED = "Senyal velocitat"
GENERIC = "Genérica via"
PLAUSIBLE_LIMITS = frozenset({10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120})
SPEED_BANDS = (
    (0, 30, "posted 10-30 km/h"),
    (31, 50, "posted 40-50 km/h"),
    (51, 70, "posted 60-70 km/h"),
    (71, 90, "posted 80-90 km/h"),
    (91, 120, "posted 100-120 km/h"),
)

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
HOUR_BANDS = (
    (0, 5, "00-05"),
    (6, 9, "06-09"),
    (10, 13, "10-13"),
    (14, 17, "14-17"),
    (18, 21, "18-21"),
    (22, 23, "22-23"),
)

# The four Catalan demarcations are the four provinces; their INE codes are the official ones.
DEMARCATION_PROVINCE_CODE = {"Barcelona": 8, "Girona": 17, "Lleida": 25, "Tarragona": 43}


def stage(force: bool = False) -> Path:
    item = sources.resolve_one(ROLE)
    if STAGING.exists() and not force:
        if read_provenance(STAGING).get("source_sha256") == item.sha256:
            return STAGING
    frame = sources.read_raw(item.path)
    frame.insert(1, "source_file", item.relative)
    write_parquet(
        frame,
        STAGING,
        {
            "table": ROLE,
            "unit_of_observation": item.role.unit,
            "source_file": item.relative,
            "source_sha256": item.sha256,
            "years": list(item.years),
        },
    )
    log.info("staged %s: %s rows from %s", ROLE, f"{len(frame):,}", item.relative)
    return STAGING


def parse_hour(text: pd.Series) -> pd.DataFrame:
    """``hor`` is hours and minutes as "H,MM" with a trailing zero dropped: "18,3" is 18:30."""
    parts = text.fillna("").str.strip().str.split(",", n=1, expand=True)
    hours = pd.to_numeric(parts[0], errors="coerce")
    minutes_text = parts[1] if parts.shape[1] > 1 else pd.Series("", index=text.index)
    minutes_text = minutes_text.fillna("")
    minutes = pd.to_numeric(
        minutes_text.str.ljust(2, "0").where(minutes_text != "", "0"), errors="coerce"
    )
    valid = hours.between(0, 23) & minutes.between(0, 59)
    return pd.DataFrame(
        {
            "hour": hours.where(valid).astype("Int64"),
            "minute": minutes.where(valid).astype("Int64"),
        }
    )


def speed_limit(raw: pd.Series, kind: pd.Series) -> pd.DataFrame:
    """The posted limit where the record has one; the generic case kept as its own category."""
    value = pd.to_numeric(raw.where(raw.str.fullmatch(r"\d+")), errors="coerce")
    posted = kind.eq(POSTED)
    plausible = value.isin(PLAUSIBLE_LIMITS)
    kmh = value.where(posted & plausible).astype("Int64")
    category = pd.Series("generic limit for the road (value not recorded)", index=raw.index)
    category[posted & ~plausible] = "posted, implausible value"
    for low, high, label in SPEED_BANDS:
        category[posted & plausible & value.between(low, high)] = label
    category[~posted & ~kind.eq(GENERIC)] = "not recorded"
    return pd.DataFrame({"speed_limit_kmh": kmh, "speed_limit_category": category.astype("string")})


def band(values: pd.Series, bands) -> pd.Series:
    out = pd.Series(pd.NA, index=values.index, dtype="string")
    for low, high, label in bands:
        out[values.between(low, high)] = label
    return out


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()
    out.insert(0, KEY, "CAT-" + out["source_row"].astype(str).str.zfill(6))
    source_columns = [c for c in raw.columns if c not in ("source_row", "source_file")]
    out["row_sha1"] = [
        hashlib.sha1("\x1f".join(values).encode("utf-8")).hexdigest()
        for values in raw[source_columns].astype(str).itertuples(index=False, name=None)
    ]
    out["year"] = to_int(out["Any"])
    out["date"] = pd.to_datetime(out["dat"], format="%d/%m/%Y", errors="coerce")
    out["month"] = out["date"].dt.month.astype("Int64")
    out["weekday"] = out["date"].dt.dayofweek.map(dict(enumerate(WEEKDAYS))).astype("string")
    out = pd.concat([out, parse_hour(out["hor"])], axis=1)
    out["hour_band"] = band(out["hour"].astype("Float64"), HOUR_BANDS)
    out["zone"] = out["zona"].map({"Zona urbana": "urban", "Carretera": "interurban road"})
    out["zone"] = out["zone"].astype("string")
    out["municipality"] = out["nomMun"].astype("string")
    out["comarca"] = out["nomCom"].astype("string")
    out["demarcation"] = out["nomDem"].astype("string")
    out["province_code"] = out["nomDem"].map(DEMARCATION_PROVINCE_CODE).astype("Int64")
    out["road"] = out["via"].astype("string")
    out["km_point"] = to_float(out["pk"], decimal_comma=True)
    # 999999 (and once 9999) stand for "no kilometre point", as on urban streets.
    out.loc[out["km_point"] >= 9999, "km_point"] = pd.NA
    for source_column, name in COUNT_COLUMNS.items():
        out[name] = to_int(out[source_column])
    for count, flag in UNIT_FLAGS.items():
        out[flag] = out[count].fillna(0).gt(0)
    out["single_unit"] = out["n_units"].eq(1)
    out["severity"] = out["D_GRAVETAT"].map(SEVERITY).astype("string")
    out["fatal"] = out["severity"].eq("fatal").astype("int8")
    out = pd.concat([out, speed_limit(out["C_VELOCITAT_VIA"], out["D_LIMIT_VELOCITAT"])], axis=1)
    assert_unique(out, KEY, "Catalonia crash table")
    return out


def build(force: bool = False) -> Path:
    staged = stage(force=force)
    provenance = read_provenance(staged)
    frame = clean(pd.read_parquet(staged))
    write_parquet(
        frame,
        PROCESSED,
        {
            "unit_of_observation": "one crash with at least one death or serious injury",
            "key": f"{KEY} (surrogate: data row of the source file)",
            "sources": {
                ROLE: {"file": provenance["source_file"], "sha256": provenance["source_sha256"]}
            },
        },
    )
    log.info("processed %s: %s rows", PROCESSED.name, f"{len(frame):,}")
    return PROCESSED


def read() -> pd.DataFrame:
    if not PROCESSED.exists():
        build()
    return pd.read_parquet(PROCESSED)


def severity_consistency(frame: pd.DataFrame) -> pd.DataFrame:
    """The severity label against the death and serious-injury counts, crash by crash."""
    return pd.crosstab(
        frame["severity"],
        np.select(
            [frame.n_deaths > 0, frame.n_serious_injuries > 0],
            ["deaths > 0", "no deaths, serious > 0"],
            default="no deaths, no serious",
        ),
    )
