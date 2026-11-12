"""The Catalan crash feature table and the catalogue that governs its columns.

The table has one row per crash with a death or serious injury, a stable identifier, the target
(``fatal``) and the candidate features the catalogue allows. The catalogue
(:data:`CATALONIA_CATALOGUE`) is the single place a column's status is decided:

``safe``            a circumstance recorded about the crash, not derived from the outcome
``questionable``    plausibly influenced by the outcome or only established by later investigation
``direct_leakage``  encodes the target (a casualty count, the severity label); never in the table
``excluded``        not used for another reason (identifier, duplicate, too granular, constant)

Categorical gaps become an explicit "not recorded" category; numeric gaps stay missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from dgt_stats.microdata import catalonia
from dgt_stats.microdata.common import assert_unique, read_provenance, write_parquet
from dgt_stats.paths import FEATURES_DATA_DIR

NOT_RECORDED = "not recorded"


@dataclass(frozen=True)
class Feature:
    column: str
    kind: str  # numeric | categorical | binary
    status: str  # safe | questionable | direct_leakage | excluded
    reason: str
    sets: tuple[str, ...] = ()  # the feature sets the column enters (empty = none)
    geography: str = ""  # "" | broad | granular: the geography variant it belongs to


@dataclass(frozen=True)
class FeatureTable:
    name: str
    path: Path
    unit: str
    id_column: str
    target: str
    target_definition: str
    time_column: str
    catalogue: tuple[Feature, ...]

    def candidate_columns(self) -> list[str]:
        """Every column the feature table carries: usable in at least one variant."""
        return [f.column for f in self.catalogue if f.status in ("safe", "questionable") and f.sets]


S = "safe"
Q = "questionable"
L = "direct_leakage"
X = "excluded"
# Catalonia's second set holds police judgements and fields whose completeness follows the
# outcome: a retrospective *administrative* model, never the primary one.
CAT_CTX = ("context", "retrospective_administrative")
CAT_RETRO = ("retrospective_administrative",)


# ----------------------------------------------------------------------------- Catalonia
_CAT_CONDITIONS = [
    ("D_TIPUS_VIA", "road type"),
    ("D_TITULARITAT_VIA", "road owner ('NA' on urban streets)"),
    ("D_SUBZONA", "zone detail (urban street, interurban road, through-town road)"),
    ("D_FUNC_ESP_VIA", "special road function"),
    ("D_INTER_SECCIO", "intersection or road section"),
    ("D_SUBTIPUS_TRAM", "junction type"),
    ("D_REGULACIO_PRIORITAT", "priority regulation"),
    ("D_SUPERFICIE", "surface"),
    ("D_LLUMINOSITAT", "lighting"),
    ("D_CLIMATOLOGIA", "weather"),
    ("D_VENT", "wind"),
    ("D_BOIRA", "fog present"),
    ("D_CIRCULACIO_MESURES_ESP", "special traffic measures"),
    ("D_SUBTIPUS_ACCIDENT", "accident subtype"),
]
# Fields whose "not specified" (or unexplained "NA") level is far less often fatal than the rest
# in the training years: the placeholder's rate differs by outcome (the file does not say why),
# so the level carries information about the outcome. Checked by the tests.
DOCUMENTATION_DEPENDENT = {
    "D_TRACAT_ALTIMETRIC": ("vertical alignment", "Sense especificar"),
    "D_CARACT_ENTORN": ("roadside profile", "Sense Especificar"),
    "D_SENTITS_VIA": ("one-way or two-way", "Sense especificar"),
    "D_CARRIL_ESPECIAL": ("special lane", "NA"),
}
_CAT_INFLUENCE = [
    "D_INFLUIT_BOIRA",
    "D_INFLUIT_CARACT_ENTORN",
    "D_INFLUIT_CIRCULACIO",
    "D_INFLUIT_ESTAT_CLIMA",
    "D_INFLUIT_INTEN_VENT",
    "D_INFLUIT_LLUMINOSITAT",
    "D_INFLUIT_MESU_ESP",
    "D_INFLUIT_OBJ_CALCADA",
    "D_INFLUIT_SOLCS_RASES",
    "D_INFLUIT_VISIBILITAT",
]

CATALONIA_CATALOGUE: tuple[Feature, ...] = (
    Feature("year", "numeric", S, "calendar year of the crash; also the split variable", CAT_CTX),
    Feature("month", "categorical", S, "month of the crash", CAT_CTX),
    Feature("weekday", "categorical", S, "day of the week, from the date", CAT_CTX),
    Feature("hour_band", "categorical", S, "hour of the crash in six bands, from `hor`", CAT_CTX),
    *(Feature(c, "categorical", S, f"recorded {label}", CAT_CTX) for c, label in _CAT_CONDITIONS),
    Feature(
        "speed_limit_category",
        "categorical",
        S,
        "posted speed limit in bands, or 'generic limit' where the record has no value "
        "(the road's limit, not a vehicle's speed)",
        CAT_CTX,
    ),
    Feature("n_units", "numeric", S, "units involved (vehicles and pedestrians)", CAT_CTX),
    Feature("single_unit", "binary", S, "one unit involved", CAT_CTX),
    *(
        Feature(flag, "binary", S, f"at least one unit of this type involved ({count})", CAT_CTX)
        for count, flag in catalonia.UNIT_FLAGS.items()
    ),
    Feature(
        "demarcation", "categorical", S, "demarcation (province): broad geography", CAT_CTX, "broad"
    ),
    Feature("comarca", "categorical", S, "comarca (43): finer geography", CAT_CTX, "comarca"),
    Feature(
        "municipality",
        "categorical",
        S,
        "municipality (about 900): granular geography, tested for memorisation",
        CAT_CTX,
        "granular",
    ),
    *(
        Feature(
            c,
            "categorical",
            Q,
            "the police's retrospective judgement that this condition influenced the crash; "
            "fatal crashes may be investigated more fully, so the recording can depend on the "
            "outcome: retrospective administrative set only",
            CAT_RETRO,
        )
        for c in _CAT_INFLUENCE
    ),
    *(
        Feature(
            c,
            "categorical",
            Q,
            f"recorded {label}; its '{level}' level is much less often fatal than the rest, so "
            "it partly records how fully the crash was documented, which follows the outcome: "
            "retrospective administrative set only",
            CAT_RETRO,
        )
        for c, (label, level) in DOCUMENTATION_DEPENDENT.items()
    ),
    Feature(
        "D_ACC_AMB_FUGA",
        "categorical",
        Q,
        "a driver left the scene: behaviour after the crash that may depend on its outcome; "
        "retrospective administrative set only",
        CAT_RETRO,
    ),
    Feature("F_MORTS", "numeric", L, "deaths: defines the target"),
    Feature("n_deaths", "numeric", L, "deaths: defines the target"),
    Feature("D_GRAVETAT", "categorical", L, "the severity label itself"),
    Feature("severity", "categorical", L, "the severity label in English"),
    Feature("F_VICTIMES", "numeric", L, "victims, which include the deaths"),
    Feature("n_victims", "numeric", L, "victims, which include the deaths"),
    Feature(
        "F_FERITS_GREUS",
        "numeric",
        L,
        "serious injuries: every non-fatal crash in this file has at least one, so zero "
        "serious injuries identifies a fatal crash",
    ),
    Feature("n_serious_injuries", "numeric", L, "as F_FERITS_GREUS"),
    Feature(
        "F_FERITS_LLEUS",
        "numeric",
        Q,
        "minor injuries: a casualty count established after the crash; excluded",
    ),
    Feature("n_minor_injuries", "numeric", Q, "as F_FERITS_LLEUS; excluded"),
    Feature(
        "C_VELOCITAT_VIA",
        "categorical",
        X,
        "raw limit field mixing posted limits with codes; replaced by speed_limit_category",
    ),
    Feature("D_LIMIT_VELOCITAT", "categorical", X, "contained in speed_limit_category"),
    Feature("tipAcc", "categorical", X, "a coarser grouping of D_SUBTIPUS_ACCIDENT"),
    Feature("zona", "categorical", X, "a coarser grouping of D_SUBZONA"),
    Feature("grupHor", "categorical", X, "a coarser grouping of hour_band"),
    Feature("grupDiaLab", "categorical", X, "a coarser grouping of weekday"),
    Feature("tipDia", "categorical", X, "a coarser grouping of weekday"),
    Feature("dat", "categorical", X, "the date: month, weekday and year are used instead"),
    Feature("via", "categorical", X, "road name (773 values): would memorise roads"),
    Feature("pk", "numeric", X, "kilometre point: a location identifier"),
    Feature("F_UNIT_DESC_IMPLICADES", "numeric", X, "unknown units: non-zero once"),
    Feature("n_pedestrians", "numeric", X, "count kept as the involves_pedestrian flag"),
    Feature("n_bicycles", "numeric", X, "count kept as a flag"),
    Feature("n_mopeds", "numeric", X, "count kept as a flag"),
    Feature("n_motorcycles", "numeric", X, "count kept as a flag"),
    Feature("n_light_vehicles", "numeric", X, "count kept as a flag"),
    Feature("n_heavy_vehicles", "numeric", X, "count kept as a flag"),
    Feature("n_other_units", "numeric", X, "count kept as a flag"),
    Feature("cat_crash_id", "categorical", X, "surrogate identifier"),
)


CATALONIA_TABLE = FeatureTable(
    name="catalonia_crash_severity",
    path=FEATURES_DATA_DIR / "catalonia_crash_severity.parquet",
    unit="one crash with at least one death or serious injury (Catalonia)",
    id_column="cat_crash_id",
    target="fatal",
    target_definition="1 if D_GRAVETAT is 'Accident mortal' (equivalently F_MORTS > 0), "
    "0 if 'Accident greu' (serious injury, no death)",
    time_column="year",
    catalogue=CATALONIA_CATALOGUE,
)


def _prepare(frame: pd.DataFrame, table: FeatureTable) -> pd.DataFrame:
    """Typed feature columns: categoricals as text with explicit 'not recorded'."""
    out = pd.DataFrame(index=frame.index)
    for feature in table.catalogue:
        if feature.column not in table.candidate_columns():
            continue
        values = frame[feature.column]
        if feature.kind == "categorical":
            text = values.astype("string").str.strip()
            out[feature.column] = text.mask(text.isna() | text.eq(""), NOT_RECORDED).astype(str)
        elif feature.kind == "binary":
            out[feature.column] = values.astype("Float64").astype(float)
        else:
            out[feature.column] = pd.to_numeric(values, errors="coerce").astype(float)
    return out


def _with_time(out: pd.DataFrame, source: pd.DataFrame, table: FeatureTable) -> pd.DataFrame:
    """Carry the split variable even where it is not a feature."""
    if table.time_column not in out.columns:
        out[table.time_column] = pd.to_numeric(source[table.time_column]).astype("int64").values
    return out


def build_catalonia() -> pd.DataFrame:
    crashes = catalonia.read()
    table = CATALONIA_TABLE
    out = crashes[[table.id_column]].copy()
    out[table.target] = crashes["fatal"].astype("int8")
    out = pd.concat([out, _prepare(crashes, table)], axis=1)
    return _with_time(out, crashes, table)


def build() -> pd.DataFrame:
    table = CATALONIA_TABLE
    frame = build_catalonia()
    assert_unique(frame, table.id_column, table.name)
    leaks = [f.column for f in table.catalogue if f.status == "direct_leakage"]
    present = sorted(set(leaks) & set(frame.columns) - {table.target})
    if present:
        raise ValueError(f"{table.name}: direct-leakage columns in the feature table: {present}")
    write_parquet(
        frame,
        table.path,
        {
            "feature_table": table.name,
            "unit_of_observation": table.unit,
            "id_column": table.id_column,
            "target": table.target,
            "target_definition": table.target_definition,
            "time_column": table.time_column,
            "feature_columns": table.candidate_columns(),
            "processed_inputs": [catalonia.PROCESSED.name],
            "sources": read_provenance(catalonia.PROCESSED).get("sources", {}),
        },
    )
    return frame


def read() -> pd.DataFrame:
    if not CATALONIA_TABLE.path.exists():
        build()
    return pd.read_parquet(CATALONIA_TABLE.path)
