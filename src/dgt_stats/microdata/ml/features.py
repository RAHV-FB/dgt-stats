"""The three ML feature tables and the feature catalogue that governs them.

Each table has one row per real observation, a stable identifier, the target, the grouping key
where rows share a crash, and only the candidate features the leakage audit allows. The catalogue
(:data:`CATALOGUES`) is the single place a column's status is decided:

``safe``            a circumstance recorded about the crash or person, not derived from the outcome
``questionable``    plausibly influenced by the outcome or only established by later investigation;
                    used only in a feature set that is labelled for it (e.g. ``retrospective``)
``direct_leakage``  encodes the target (a casualty count, the severity label); never in a matrix
``excluded``        not used for another reason (identifier, duplicate, too granular, constant)

The same catalogue writes ``docs/ML_LEAKAGE_AUDIT.md`` and is checked by the tests, so a column
cannot reach a model without a recorded decision. Joins happen here and only on real keys: the
person table receives crash context through ``Numero_expedient`` with ``validate="many_to_one"``.
Categorical gaps become an explicit "not recorded" category; numeric gaps stay missing and are
imputed inside the model pipeline, fitted on training rows only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from dgt_stats.microdata import barcelona, catalonia
from dgt_stats.microdata.common import assert_unique, read_provenance, write_parquet
from dgt_stats.paths import FEATURES_DATA_DIR

NOT_RECORDED = "not recorded"


@dataclass(frozen=True)
class Feature:
    column: str
    kind: str  # numeric | categorical | binary
    status: str  # safe | questionable | direct_leakage | excluded
    reason: str
    sets: tuple[str, ...] = ()  # feature sets the column enters (empty = none)
    geography: str = ""  # "" | broad | granular: enters only the matching geography variant


@dataclass(frozen=True)
class FeatureTable:
    name: str
    path: Path
    unit: str
    id_column: str
    target: str
    target_definition: str
    group_column: str | None
    time_column: str
    feature_sets: tuple[str, ...]
    primary_set: str
    geography_variants: tuple[str, ...]
    primary_geography: str
    catalogue: tuple[Feature, ...]

    def features(self, feature_set: str, geography: str) -> list[Feature]:
        """The usable features of one variant: in the set, and in the geography variant if any."""
        chosen = []
        for feature in self.catalogue:
            if feature.status not in ("safe", "questionable") or feature_set not in feature.sets:
                continue
            if feature.geography and feature.geography != geography:
                continue
            chosen.append(feature)
        return chosen

    def columns(self, feature_set: str, geography: str) -> list[str]:
        return [feature.column for feature in self.features(feature_set, geography)]

    def candidate_columns(self) -> list[str]:
        """Every column the feature table carries: usable in at least one variant."""
        return [f.column for f in self.catalogue if f.status in ("safe", "questionable") and f.sets]


S = "safe"
Q = "questionable"
L = "direct_leakage"
X = "excluded"
CTX = ("context", "retrospective")
RETRO = ("retrospective",)
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
# in the training years: they record how fully a crash was documented, and fatal crashes are
# documented more fully, so the level partly follows the outcome. Checked on every build by
# ``recording_check`` and the tests.
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


# ----------------------------------------------------------------------------- Barcelona
_GEO_BCN = (
    Feature("district", "categorical", S, "district (10): broad geography", CTX, "broad"),
    Feature(
        "neighbourhood",
        "categorical",
        S,
        "neighbourhood (73): granular geography, tested for memorisation",
        CTX,
        "granular",
    ),
)
_CRASH_CONTEXT = (
    Feature("hour", "numeric", S, "hour of the crash", CTX),
    Feature("weekday", "categorical", S, "day of the week", CTX),
    Feature(
        "month",
        "categorical",
        X,
        "month: one year of data, so the test months are never seen in training; it is the "
        "split variable instead",
    ),
    Feature(
        "accident_type",
        "categorical",
        S,
        "recorded crash type (collision, pedestrian struck, fall...)",
        CTX,
    ),
    Feature("n_vehicles", "numeric", S, "vehicles involved, from the crash table", CTX),
    *(
        Feature(
            f"vehicle_records_include_{g}",
            "binary",
            S,
            f"the crash has a vehicle record of type {g} (presence only; see the vehicle audit)",
            CTX,
        )
        for g in barcelona.VEHICLE_GROUP_ORDER
    ),
)
_RETROSPECTIVE = (
    *(
        Feature(
            f"mediate_{code}_recorded",
            "binary",
            Q,
            f"'{label}' recorded as a mediate cause of the crash (police coding after the "
            "event; says the cause was recorded, not that it caused the crash): retrospective "
            "set only",
            RETRO,
        )
        for code, label in barcelona.MEDIATE_CAUSES.values()
    ),
    *(
        Feature(
            f"driver_cause_{code}_recorded",
            "binary",
            Q,
            f"'{label}' recorded as a driver-related cause in the crash (not attributable to "
            "a person or vehicle): retrospective set only",
            RETRO,
        )
        for code, label in barcelona.DRIVER_CAUSES.values()
    ),
    Feature(
        "driver_cause_status",
        "categorical",
        Q,
        "whether any driver cause, only 'not determined', or nothing was recorded: "
        "retrospective set only",
        RETRO,
    ),
    Feature(
        "pedestrian_cause",
        "categorical",
        Q,
        "pedestrian behaviour recorded for the crash (crash-level, not the person's own): "
        "retrospective set only",
        RETRO,
    ),
)
_CRASH_LEAKS = (
    Feature("n_deaths", "numeric", L, "deaths in the crash"),
    Feature("n_serious_injuries", "numeric", L, "serious injuries in the crash"),
    Feature("n_victims", "numeric", L, "victims, including the serious and fatal ones"),
    Feature("Numero_morts", "numeric", L, "deaths (source column)"),
    Feature("Numero_lesionats_greus", "numeric", L, "serious injuries (source column)"),
    Feature("Numero_victimes", "numeric", L, "victims (source column)"),
    Feature("fatal_crash", "binary", L, "derived from deaths"),
    Feature("n_minor_injuries", "numeric", Q, "minor injuries: an outcome count; excluded"),
    Feature("Numero_lesionats_lleus", "numeric", Q, "minor injuries (source column); excluded"),
)

BARCELONA_CRASH_CATALOGUE: tuple[Feature, ...] = (
    *_CRASH_CONTEXT,
    *_GEO_BCN,
    *_RETROSPECTIVE,
    *_CRASH_LEAKS,
    Feature("serious_or_fatal_crash", "binary", L, "the target"),
    Feature(
        "n_person_records",
        "numeric",
        Q,
        "person records: who is recorded depends partly on who was hurt; excluded",
    ),
    Feature("n_pedestrian_records", "numeric", Q, "as n_person_records; excluded"),
    Feature("n_passenger_records", "numeric", Q, "as n_person_records; excluded"),
    Feature("n_driver_records", "numeric", Q, "as n_person_records; excluded"),
    Feature(
        "vehicle_table_rows",
        "numeric",
        X,
        "row count of the vehicle table: not a vehicle count (quarantined)",
    ),
    Feature("shift", "categorical", X, "a coarser grouping of hour"),
    Feature("Codi_carrer", "categorical", X, "street: would memorise locations"),
    Feature("utm_x_ed50", "numeric", X, "coordinates: would memorise locations"),
    Feature("Numero_expedient", "categorical", X, "identifier"),
)

BARCELONA_PERSON_CATALOGUE: tuple[Feature, ...] = (
    Feature(
        "age",
        "numeric",
        S,
        "age of the person (missing for 7%: imputed in the pipeline with a missing indicator)",
        CTX,
    ),
    Feature("sex", "categorical", S, "sex, with 'not recorded' as its own category", CTX),
    Feature("person_role", "categorical", S, "driver, passenger or pedestrian", CTX),
    Feature(
        "associated_vehicle_group",
        "categorical",
        S,
        "vehicle type on the person's record (for a pedestrian the source does not say which "
        "vehicle this is)",
        CTX,
    ),
    Feature(
        "pedestrian_location",
        "categorical",
        S,
        "where a pedestrian was struck (crossing with lights, outside a crossing...); "
        "'not a pedestrian' otherwise",
        CTX,
    ),
    *_CRASH_CONTEXT,
    *_GEO_BCN,
    *_RETROSPECTIVE,
    *_CRASH_LEAKS,
    Feature(
        "serious_or_fatal_crash",
        "binary",
        L,
        "the crash had a serious or fatal injury: includes this person's own outcome",
    ),
    Feature("Descripcio_victimitzacio", "categorical", L, "the person's victimisation: the target"),
    Feature("injury_severity", "categorical", L, "grouping of the victimisation: the target"),
    Feature("victimisation", "categorical", L, "English victimisation: the target"),
    Feature("fatal", "binary", L, "subset of the target"),
    Feature(
        "trip_purpose",
        "categorical",
        Q,
        "trip purpose: often 'unknown', and whether it can be asked depends on the person's "
        "condition; excluded",
    ),
    Feature(
        "n_person_records",
        "numeric",
        Q,
        "person records in the crash: who is recorded depends partly on who was hurt; excluded",
    ),
    Feature("person_record_id", "categorical", X, "identifier"),
    Feature("Numero_expedient", "categorical", X, "crash identifier: the grouping key"),
)


CATALONIA_TABLE = FeatureTable(
    name="catalonia_crash_severity",
    path=FEATURES_DATA_DIR / "catalonia_crash_severity.parquet",
    unit="one crash with at least one death or serious injury (Catalonia)",
    id_column="cat_crash_id",
    target="fatal",
    target_definition="1 if D_GRAVETAT is 'Accident mortal' (equivalently F_MORTS > 0), "
    "0 if 'Accident greu' (serious injury, no death)",
    group_column=None,
    time_column="year",
    feature_sets=("context", "retrospective_administrative"),
    primary_set="context",
    geography_variants=("none", "broad", "comarca", "granular"),
    primary_geography="broad",
    catalogue=CATALONIA_CATALOGUE,
)
BARCELONA_PERSON_TABLE = FeatureTable(
    name="barcelona_person_severity",
    path=FEATURES_DATA_DIR / "barcelona_person_severity.parquet",
    unit="one person record in a Barcelona crash, 2025",
    id_column="person_record_id",
    target="serious_or_fatal",
    target_definition="1 if Descripcio_victimitzacio is 'Ferit greu' or 'Mort' (within or after "
    "24 h), 0 if 'Il.lès' or 'Ferit lleu' (any of three); records with a blank victimisation or "
    "'Mort natural' are excluded",
    group_column="Numero_expedient",
    time_column="month",
    feature_sets=("context", "retrospective"),
    primary_set="context",
    geography_variants=("none", "broad", "granular"),
    primary_geography="broad",
    catalogue=BARCELONA_PERSON_CATALOGUE,
)
BARCELONA_CRASH_TABLE = FeatureTable(
    name="barcelona_crash_severity",
    path=FEATURES_DATA_DIR / "barcelona_crash_severity.parquet",
    unit="one Barcelona crash (Numero_expedient), 2025",
    id_column="Numero_expedient",
    target="serious_or_fatal_crash",
    target_definition="1 if the crash table records at least one death or serious injury "
    "(Numero_morts + Numero_lesionats_greus > 0), else 0",
    group_column=None,
    time_column="month",
    feature_sets=("context", "retrospective"),
    primary_set="context",
    geography_variants=("none", "broad", "granular"),
    primary_geography="broad",
    catalogue=BARCELONA_CRASH_CATALOGUE,
)
TABLES = (CATALONIA_TABLE, BARCELONA_PERSON_TABLE, BARCELONA_CRASH_TABLE)


# The common-feature Catalonia models: trained on Catalan crashes, restricted to variables another
# source records the same way (``harmonise``), so they can be tested on that source.
def _common_catalogue(prefix: str, fields) -> tuple[Feature, ...]:
    return tuple(
        Feature(
            f"{prefix}_{field.name}",
            field.kind,
            S,
            f"{field.semantics} ({field.status}: {field.mapping})",
            ("common",),
        )
        for field in fields
    )


def _common_table(name: str, prefix: str, fields, partner: str) -> FeatureTable:
    return FeatureTable(
        name=name,
        path=FEATURES_DATA_DIR / f"{name}.parquet",
        unit="one crash with at least one death or serious injury (Catalonia)",
        id_column="cat_crash_id",
        target="fatal",
        target_definition=CATALONIA_TABLE.target_definition
        + f"; features restricted to those {partner} records compatibly",
        group_column=None,
        time_column="year",
        feature_sets=("common",),
        primary_set="common",
        geography_variants=("none",),
        primary_geography="none",
        catalogue=_common_catalogue(prefix, fields),
    )


def common_tables() -> tuple[FeatureTable, FeatureTable]:
    from dgt_stats.microdata.validation import harmonise

    dgt_fields = [
        f for f in harmonise.DGT_FIELDS if f"dgt_{f.name}" in harmonise.dgt_model_fields()
    ]
    return (
        _common_table("catalonia_common_dgt", "dgt", dgt_fields, "the DGT microdata"),
        _common_table(
            "catalonia_common_bcn",
            "bcn",
            harmonise.usable(harmonise.BCN_FIELDS),
            "the Barcelona 2025 files",
        ),
    )


def build_common() -> dict[str, pd.DataFrame]:
    """Write the two common-feature Catalonia tables (one row per Catalan crash)."""
    from dgt_stats.microdata.validation import harmonise

    harmonise.build()
    common = harmonise.catalonia_common()
    out = {}
    for table in common_tables():
        columns = [f.column for f in table.catalogue]
        frame = common[
            [
                "cat_crash_id",
                "fatal",
                "year",
                "demarcation",
                "municipality",
                "domain",
                *[c for c in columns if c != "year"],
            ]
        ].copy()
        frame = pd.concat(
            [
                frame[["cat_crash_id", "fatal"]],
                _prepare(frame, table),
                frame[["year", "demarcation", "municipality", "domain"]],
            ],
            axis=1,
        )
        frame = frame.loc[:, ~frame.columns.duplicated()]
        write_parquet(
            frame,
            table.path,
            {
                "feature_table": table.name,
                "unit_of_observation": table.unit,
                "id_column": table.id_column,
                "target": table.target,
                "feature_columns": columns,
                "sources": read_provenance(catalonia.PROCESSED).get("sources", {}),
            },
        )
        out[table.name] = frame
    return out


def table_by_name(name: str) -> FeatureTable:
    if name in TABLE_BY_NAME:
        return TABLE_BY_NAME[name]
    return {t.name: t for t in common_tables()}[name]


TABLE_BY_NAME = {table.name: table for table in TABLES}


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


def build_barcelona_crash() -> pd.DataFrame:
    crashes = barcelona.read_crashes()
    table = BARCELONA_CRASH_TABLE
    out = crashes[[table.id_column]].copy()
    out[table.target] = crashes["serious_or_fatal_crash"].astype("int8")
    out = pd.concat([out, _prepare(crashes, table)], axis=1)
    return _with_time(out, crashes, table)


def build_barcelona_person() -> pd.DataFrame:
    people = barcelona.read_people()
    crashes = barcelona.read_crashes()
    table = BARCELONA_PERSON_TABLE
    # Only records with a recorded injury outcome have a target; the others are left out, not
    # counted as uninjured.
    labelled = people[people["serious_or_fatal"].notna()].copy()
    labelled["pedestrian_location"] = labelled["Descripcio_Lloc_atropellament_vianant"].mask(
        labelled["person_role"].ne("pedestrian"), "not a pedestrian"
    )
    # Crash context comes from the canonical crash table. The person file repeats the crash's
    # month, hour and place (identical on every row, see the quality report); the crash table's
    # columns are taken for everything the person table does not itself carry.
    person_level = {"age", "sex", "person_role", "associated_vehicle_group", "pedestrian_location"}
    crash_columns = [
        column
        for column in table.candidate_columns()
        if column not in person_level and column in crashes.columns
    ]
    context = crashes[[barcelona.KEY, *crash_columns]]
    joined = labelled.drop(columns=[c for c in crash_columns if c in labelled.columns]).merge(
        context, on=barcelona.KEY, how="left", validate="many_to_one", indicator=True
    )
    if len(joined) != len(labelled) or not joined["_merge"].eq("both").all():
        raise ValueError("the crash-context join did not find exactly one crash per person row")
    out = joined[[table.id_column, table.group_column]].copy()
    out[table.target] = joined["serious_or_fatal"].astype("int8")
    out = pd.concat([out, _prepare(joined, table)], axis=1)
    return _with_time(out, joined, table)


BUILDERS = {
    CATALONIA_TABLE.name: (build_catalonia, (catalonia.PROCESSED,)),
    BARCELONA_PERSON_TABLE.name: (
        build_barcelona_person,
        (barcelona.PROCESSED_PEOPLE, barcelona.PROCESSED_ACCIDENTS),
    ),
    BARCELONA_CRASH_TABLE.name: (build_barcelona_crash, (barcelona.PROCESSED_ACCIDENTS,)),
}


def build(name: str) -> pd.DataFrame:
    table = TABLE_BY_NAME[name]
    builder, inputs = BUILDERS[name]
    frame = builder()
    assert_unique(frame, table.id_column, name)
    leaks = [f.column for f in table.catalogue if f.status == "direct_leakage"]
    present = sorted(set(leaks) & set(frame.columns) - {table.target})
    if present:
        raise ValueError(f"{name}: direct-leakage columns in the feature table: {present}")
    sources = {}
    for path in inputs:
        sources.update(read_provenance(path).get("sources", {}))
    write_parquet(
        frame,
        table.path,
        {
            "feature_table": name,
            "unit_of_observation": table.unit,
            "id_column": table.id_column,
            "target": table.target,
            "target_definition": table.target_definition,
            "group_column": table.group_column,
            "time_column": table.time_column,
            "feature_columns": table.candidate_columns(),
            "processed_inputs": [path.name for path in inputs],
            "sources": sources,
        },
    )
    return frame


def build_all() -> dict[str, pd.DataFrame]:
    return {table.name: build(table.name) for table in TABLES}


def read(name: str) -> pd.DataFrame:
    table = table_by_name(name)
    if not table.path.exists():
        build(name) if name in TABLE_BY_NAME else build_common()
    return pd.read_parquet(table.path)


def catalogue_frame() -> pd.DataFrame:
    """The leakage audit as a table: one row per model and candidate column."""
    rows = []
    for table in TABLES:
        for feature in table.catalogue:
            rows.append(
                {
                    "feature_table": table.name,
                    "column": feature.column,
                    "kind": feature.kind,
                    "status": feature.status,
                    "feature_sets": ", ".join(feature.sets) or "none",
                    "geography_variant": feature.geography or "all",
                    "reason": feature.reason,
                }
            )
    return pd.DataFrame(rows)


def missingness(name: str) -> pd.DataFrame:
    """Missing values of each candidate feature, before the pipeline imputes anything."""
    table = table_by_name(name)
    frame = read(name)
    rows = []
    for feature in table.catalogue:
        if feature.column not in frame.columns or feature.column == table.target:
            continue
        values = frame[feature.column]
        missing = values.isna() if feature.kind != "categorical" else values.eq(NOT_RECORDED)
        placeholder = (
            values.isin(["NA", "Sense especificar", "Sense Especificar", "Sense especificar"])
            if feature.kind == "categorical"
            else pd.Series(False, index=values.index)
        )
        rows.append(
            {
                "feature_table": name,
                "column": feature.column,
                "kind": feature.kind,
                "missing": int(missing.sum()),
                "missing_share": float(missing.mean()),
                "source_placeholder_rows": int(placeholder.sum()),
                "treatment": (
                    "explicit 'not recorded' category; source placeholders kept as categories"
                    if feature.kind == "categorical"
                    else "median imputation with a missing indicator, fitted on training rows"
                    if missing.any()
                    else "none needed"
                ),
            }
        )
    return pd.DataFrame(rows)


PLACEHOLDERS = ("NA", "Sense especificar", "Sense Especificar", NOT_RECORDED)


def recording_check(name: str, rows=None) -> pd.DataFrame:
    """Target share among a categorical feature's placeholder level against the other rows.

    A placeholder level ("not specified", "NA", "not recorded") whose rows have a very different
    outcome from the rest may record documentation rather than circumstance. Computed on the rows
    given (the training rows when called by the models).
    """
    table = table_by_name(name)
    frame = read(name)
    if rows is not None:
        frame = frame.iloc[rows]
    target = frame[table.target]
    out = []
    for feature in table.catalogue:
        if feature.kind != "categorical" or feature.column not in frame.columns:
            continue
        for level in PLACEHOLDERS:
            mask = frame[feature.column].eq(level)
            if not mask.any() or mask.all():
                continue
            out.append(
                {
                    "feature_table": name,
                    "column": feature.column,
                    "status": feature.status,
                    "level": level,
                    "rows": int(mask.sum()),
                    "share_of_rows": float(mask.mean()),
                    "target_share_level": float(target[mask].mean()),
                    "target_share_other_rows": float(target[~mask].mean()),
                    "ratio": float(target[mask].mean() / target[~mask].mean())
                    if target[~mask].mean() > 0
                    else float("nan"),
                }
            )
    return pd.DataFrame(out)
