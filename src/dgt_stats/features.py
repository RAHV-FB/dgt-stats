"""Model frame for the crash-severity models: grouped, labelled predictors with reference levels.

Every predictor is an ordered categorical whose first level is the reference (the most common level,
so odds ratios read "relative to the typical crash"). The missing states (not specified, not
applicable, and a field's explicit unknown code) are levels of their own and no row is dropped,
because missingness is year-dependent. They are *nuisance* levels (``is_nuisance``): they record
how a police force fills in the form, which differs by jurisdiction and year (alignment "unknown"
is almost entirely Cataluña's), so their odds ratios are kept in the tables, flagged, and never
read as an effect. The grouping maps are data, so the severity page can print them.

Levels with fewer than ``MIN_LEVEL_CRASHES`` crashes are merged into the reference on the counts of
the frame passed in, all years together; the counts are of predictors only, never of outcomes.
``models.holdout_check`` repeats the merge on the training years alone, so the held-out years
decide nothing about the model scored on them.

The junction predictor is the one place the frame corrects DGT's coding rather than reading it.
In the province-years whose junction flag is the wrong way round (:func:`inverted_junction_rows`,
the DGT microdata audit's rule: the four Catalan provinces in 2023 and 2024), the flag is read the
other way round (:func:`junction_codes`). The processed layer keeps the flag as DGT publishes it,
so the audit can still find the inversion; the other treatments are fitted as a sensitivity
(``models.junction_sensitivity``).
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import codes
from dgt_stats.paths import DGT_PROCESSED_CRASHES

PROCESSED_CRASHES = DGT_PROCESSED_CRASHES

OUTCOMES = ("fatal", "serious")
NOT_SPECIFIED = "not specified"
NOT_APPLICABLE = "not applicable"
# The label a field's explicit unknown code takes (weather 7, surface 9, alignment 4).
UNKNOWN = "unknown"
# The three missing states together: levels that record what the form says, not what happened.
MISSING_LEVELS = frozenset({NOT_SPECIFIED, NOT_APPLICABLE, UNKNOWN})
# Cataluña's four provinces (Barcelona, Girona, Lleida, Tarragona; INE codes). Their crashes carry
# road alignment "unknown" far more often than any other province's (``models.recording_regime``),
# so the model is refitted without them as a check on the recording regime.
CATALAN_PROVINCES = ("8", "17", "25", "43")
# A level with fewer crashes than this is merged into the reference level: it cannot be estimated
# (several such levels have no events at all) and would only add noise to the table.
MIN_LEVEL_CRASHES = 500
# The grouping table's last row per predictor: every value the map does not list, and empty cells.
FALLBACK_CODE = "any other value or empty"

# Each predictor: source column, ordered levels (reference first) and a code -> level map.
# Codes not listed fall to ``fallback`` (the missing markers 999/998 are handled first).
PREDICTORS: dict[str, dict[str, object]] = {
    "zone": {
        "source": "ZONA",
        "levels": [
            "street",
            "interurban road",
            "urban crossing",
            "urban motorway or dual carriageway",
        ],
        "map": {
            3: "street",
            1: "interurban road",
            2: "urban crossing",
            4: "urban motorway or dual carriageway",
        },
        "fallback": NOT_SPECIFIED,
        # Code 4 is 0.6-0.7 % of crashes in 2016-2018 and under 0.1 % from 2019 (0.4 % in 2021),
        # so its level is mostly an early-period estimate; the severity page says so.
    },
    "road": {
        # From the road-type code itself, not ``road_group``: code 5, a conventional road with a
        # dual carriageway, is a conventional road, and from 2021 most of its crashes are coded 6
        # (code 5 falls from about 7,600 crashes a year to about 1,600). Grouping 5 with 6 keeps
        # that recoding inside one level instead of moving crashes between two (as policy.py does).
        "source": "TIPO_VIA",
        "levels": ["urban street", "conventional", "autovía", "motorway", "other road"],
        "map": {
            1: "motorway",
            2: "motorway",
            3: "autovía",
            4: "conventional",
            5: "conventional",
            6: "conventional",
            9: "urban street",
            7: "other road",
            8: "other road",
            10: "other road",
            11: "other road",
            12: "other road",
            13: "other road",
            14: "other road",
        },
        "fallback": NOT_SPECIFIED,
    },
    "crash_type": {
        "source": "TIPO_ACCIDENTE",
        # DGT code 2 is a front-side collision ("fronto-lateral") and code 3 a side collision
        # ("lateral"); the reference level holds both, so its label names both.
        "levels": [
            "side or front-side collision",
            "rear-end or chain collision",
            "pedestrian struck",
            "run-off or overturn",
            "head-on collision",
            "fall",
            "object or animal struck",
            "other crash type",
        ],
        "map": {
            1: "head-on collision",
            2: "side or front-side collision",
            3: "side or front-side collision",
            4: "rear-end or chain collision",
            5: "rear-end or chain collision",
            6: "object or animal struck",
            7: "pedestrian struck",
            8: "object or animal struck",
            9: "run-off or overturn",
            10: "fall",
            11: "run-off or overturn",
            12: "run-off or overturn",
            13: "run-off or overturn",
            14: "run-off or overturn",
            15: "run-off or overturn",
            16: "run-off or overturn",
            17: "run-off or overturn",
            18: "run-off or overturn",
            19: "run-off or overturn",
            20: "other crash type",
        },
        "fallback": NOT_SPECIFIED,
    },
    "junction": {
        # The yes/no field, read the other way round in the province-years whose flag is
        # inverted (:func:`junction_codes`); the junction type (NUDO_INFO) only decides which
        # province-years those are. ``models.period_refits`` fits 2016-2022 and 2023-2024 apart
        # as a check that the corrected flag means the same in both.
        "source": "NUDO",
        "levels": ["not at a junction", "at a junction"],
        "map": {2: "not at a junction", 1: "at a junction"},
        "fallback": NOT_SPECIFIED,
    },
    "lighting": {
        "source": "CONDICION_ILUMINACION",
        "levels": ["daylight", "dusk or dawn", "dark, street lighting", "dark, no lighting"],
        "map": {
            1: "daylight",
            2: "dusk or dawn",
            3: "dusk or dawn",
            4: "dark, street lighting",
            5: "dark, no lighting",
            6: "dark, no lighting",
        },
        "fallback": NOT_SPECIFIED,
    },
    "weather": {
        "source": "CONDICION_METEO",
        "levels": ["clear", "cloudy", "rain", "hail or snow", "unknown"],
        "map": {
            1: "clear",
            2: "cloudy",
            3: "rain",
            4: "rain",
            5: "hail or snow",
            6: "hail or snow",
            7: "unknown",
        },
        "fallback": NOT_SPECIFIED,
    },
    "surface": {
        "source": "CONDICION_FIRME",
        "levels": ["dry", "wet", "other surface", "unknown"],
        "map": {
            1: "dry",
            3: "wet",
            2: "other surface",
            4: "other surface",
            5: "other surface",
            6: "other surface",
            7: "other surface",
            8: "other surface",
            9: "unknown",
        },
        "fallback": NOT_SPECIFIED,
    },
    "alignment": {
        "source": "TRAZADO_PLANTA",
        "levels": ["straight", "curve", "unknown"],
        "map": {1: "straight", 2: "curve", 3: "curve", 4: "unknown"},
        "fallback": NOT_SPECIFIED,
        # 998 (not applicable) is exactly the street zone, so it cannot be its own level next to
        # zone; alignment is only recorded outside streets and streets take the reference.
        "fold": {NOT_APPLICABLE: "straight"},
    },
    "hour_band": {
        "source": "hour_band",
        "levels": ["10-13", "00-06", "07-09", "14-16", "17-19", "20-23"],
        "map": {key: key for key in ("00-06", "07-09", "10-13", "14-16", "17-19", "20-23")},
        "fallback": NOT_SPECIFIED,
    },
    "weekend": {
        "source": "weekend",
        "levels": ["weekday", "weekend"],
        "map": {False: "weekday", True: "weekend"},
        "fallback": NOT_SPECIFIED,
    },
    "vehicles": {
        "source": "TOTAL_VEHICULOS",
        "levels": ["2 vehicles", "1 vehicle", "3 or more vehicles"],
        "map": {0: "1 vehicle", 1: "1 vehicle", 2: "2 vehicles"},
        "fallback": "3 or more vehicles",
    },
    "year": {
        "source": "ANYO",
        "levels": ["2019", "2016", "2017", "2018", "2020", "2021", "2022", "2023", "2024"],
        "map": {year: str(year) for year in range(2016, 2025)},
        "fallback": NOT_SPECIFIED,
    },
}

PREDICTOR_LABELS = {
    "zone": "Zone",
    "road": "Road type",
    "crash_type": "Crash type",
    "junction": "Junction",
    "lighting": "Lighting",
    "weather": "Weather",
    "surface": "Road surface",
    "alignment": "Alignment",
    "hour_band": "Time of day",
    "weekend": "Weekend",
    "vehicles": "Vehicles involved",
    "year": "Year",
}

# The junction type: DGT records it for a crash at a junction and leaves it empty otherwise, so it
# shows where the junction flag is the wrong way round (:func:`inverted_junction_rows`).
JUNCTION_TYPE = "NUDO_INFO"
MODEL_COLUMNS = list(
    dict.fromkeys(
        ["ANYO", "COD_PROVINCIA", "fatal", "serious"]
        + [str(spec["source"]) for spec in PREDICTORS.values()]
        + [JUNCTION_TYPE]
    )
)
# With the right-of-way flags, which describe how priority was regulated at the junction: the
# columns :func:`junction_coding_table` and the near-junction treatment read.
JUNCTION_COLUMNS = [*MODEL_COLUMNS, *codes.PRIORI_COLUMNS]

# The grouping table's suffix for a junction code in a province-year whose flag is inverted.
INVERTED_KEY = " where the flag is inverted"
AT_JUNCTION = "at a junction"
NOT_AT_JUNCTION = "not at a junction"
# A province-year in which more than this share of the crashes flagged away from a junction carry
# a junction type has the flag the wrong way round. It is the DGT microdata audit's rule and share
# (``dgt_audit.junction_coding``, column ``junction_flag_inverted``), and a test holds the two to
# the same province-years.
INVERTED_TYPE_SHARE = 0.5
# How the model reads the junction flag of the inverted province-years, and the alternatives
# ``models.junction_sensitivity`` fits beside it. The flag read the other way round is the one
# the rest of each record supports crash by crash (``q3_junction_coding``): the crashes it places
# away from a junction carry neither a junction type nor a right-of-way flag, and those it places
# at one carry a junction type or, lacking one, right-of-way flags, as junction crashes do in the
# earlier years. Reading the junction type alone would place the junction crashes that have no
# type away from a junction; "unrecorded" drops what the records establish. "near junctions"
# also places at a junction the Catalan crashes flagged away from one whose record carries a
# junction type or a right-of-way flag: crashes near a junction that the 2021 records flag away
# (the Catalan file counts them at a junction in the other years).
JUNCTION_TREATMENT = "flip"
JUNCTION_TREATMENTS = {
    "flip": "flag read the other way round",
    "junction type": "at a junction when the record carries a junction type",
    "unrecorded": "junction unrecorded",
    "as published": "flag as DGT publishes it",
    "flip and near junctions": "flag read the other way round, and Catalan crashes flagged away "
    "from a junction with a junction type or a right-of-way flag placed at one",
}


def read_crashes(columns: list[str] | None = None) -> pd.DataFrame:
    """The processed crash table, with the columns the model frame and the junction checks read."""
    return pd.read_parquet(PROCESSED_CRASHES, columns=columns or JUNCTION_COLUMNS)


def _junction_code(level: str) -> int:
    """NUDO's code for a junction level, from the junction predictor's own map."""
    mapping: dict = PREDICTORS["junction"]["map"]  # type: ignore[assignment]
    return next(int(code) for code, name in mapping.items() if name == level)


def junction_flags(crashes: pd.DataFrame) -> pd.DataFrame:
    """Per crash: its province and year, whether DGT flags it at or away from a junction, and
    whether its record carries a junction type and (when the columns are there) a right-of-way
    flag. A field counts as carried when it holds a dictionary value, not 999 or a blank."""
    nudo = pd.to_numeric(crashes["NUDO"], errors="coerce")
    at = nudo.eq(_junction_code(AT_JUNCTION)).fillna(False).astype(bool)
    out = pd.DataFrame(
        {
            "province": crashes["COD_PROVINCIA"].astype("Int16").astype(str).to_numpy(),
            "year": pd.to_numeric(crashes["ANYO"]).astype(int).to_numpy(),
            "flagged_at": at.to_numpy(),
            "flagged_away": (nudo.notna() & ~at).astype(bool).to_numpy(),
            "junction_type": codes.status(JUNCTION_TYPE, crashes[JUNCTION_TYPE])
            .eq("observed")
            .to_numpy(),
        },
        index=crashes.index,
    )
    if all(column in crashes for column in codes.PRIORI_COLUMNS):
        carried = [codes.status(c, crashes[c]).eq("observed") for c in codes.PRIORI_COLUMNS]
        out["right_of_way"] = pd.concat(carried, axis=1).any(axis=1).to_numpy()
    return out


def inverted_junction_rows(crashes: pd.DataFrame, flags: pd.DataFrame | None = None) -> pd.Series:
    """The crashes of the province-years whose junction flag is the wrong way round: more than
    ``INVERTED_TYPE_SHARE`` of their crashes flagged away from a junction carry a junction type."""
    flags = junction_flags(crashes) if flags is None else flags
    counts = (
        flags.assign(typed_away=flags.flagged_away & flags.junction_type)
        .groupby(["province", "year"])[["flagged_away", "typed_away"]]
        .transform("sum")
    )
    return (counts.typed_away > INVERTED_TYPE_SHARE * counts.flagged_away).rename("inverted")


def junction_codes(
    crashes: pd.DataFrame, treatment: str = JUNCTION_TREATMENT, flags: pd.DataFrame | None = None
) -> pd.Series:
    """DGT's junction flag as the model reads it: as published outside the inverted
    province-years, and inside them as ``treatment`` says (``JUNCTION_TREATMENTS``)."""
    if treatment not in JUNCTION_TREATMENTS:
        raise ValueError(f"unknown junction treatment {treatment!r}")
    flags = junction_flags(crashes) if flags is None else flags
    inverted = inverted_junction_rows(crashes, flags)
    at_code, away_code = _junction_code(AT_JUNCTION), _junction_code(NOT_AT_JUNCTION)
    out = pd.to_numeric(crashes["NUDO"], errors="coerce").astype("Int64")
    if treatment in ("flip", "flip and near junctions"):
        out = out.mask(inverted & flags.flagged_at, away_code)
        out = out.mask(inverted & flags.flagged_away, at_code)
    elif treatment == "junction type":
        recorded = inverted & (flags.flagged_at | flags.flagged_away)
        out = out.mask(recorded & flags.junction_type, at_code)
        out = out.mask(recorded & ~flags.junction_type, away_code)
    elif treatment == "unrecorded":
        out = out.mask(inverted, pd.NA)
    if treatment == "flip and near junctions":
        if "right_of_way" not in flags:
            raise ValueError("the near-junction treatment needs the right-of-way flags")
        near = (
            flags.province.isin(CATALAN_PROVINCES)
            & ~inverted
            & flags.flagged_away
            & (flags.junction_type | flags.right_of_way)
        )
        out = out.mask(near, at_code)
    return out


def junction_coding_table(crashes: pd.DataFrame) -> pd.DataFrame:
    """The junction flag by year in Cataluña and in the rest of Spain, as published and as the
    model reads it, with what the rest of each record says about it.

    ``*_with_junction_type`` and ``*_with_right_of_way`` count the crashes whose record carries a
    junction type, or a right-of-way flag; ``*_with_junction_fields`` either. Read crash by crash,
    they show whether the corrected flag agrees with the rest of the record: as published, the
    inverted province-years' crashes flagged at a junction carry neither, like crashes away from a
    junction elsewhere. ``recoded`` counts the crashes whose flag the model reads the other way
    round; ``near_junction_fields`` the Catalan crashes flagged away from a junction outside those
    province-years whose record carries a junction type or right-of-way flag.
    """
    flags = junction_flags(crashes)
    inverted = inverted_junction_rows(crashes, flags)
    corrected = junction_codes(crashes, JUNCTION_TREATMENT, flags)
    at_code = _junction_code(AT_JUNCTION)
    published = pd.to_numeric(crashes["NUDO"], errors="coerce").astype("Int64")
    fields = flags.junction_type | flags.right_of_way
    catalan = flags.province.isin(CATALAN_PROVINCES)
    corrected_at = corrected.eq(at_code).fillna(False).astype(bool)
    corrected_away = corrected.notna() & ~corrected_at
    parts = pd.DataFrame(
        {
            "region": catalan.map({True: "Catalonia", False: "rest of Spain"}),
            "year": flags.year,
            "crashes": True,
            "inverted": inverted,
            "flagged_at": flags.flagged_at,
            "flagged_at_with_junction_type": flags.flagged_at & flags.junction_type,
            "flagged_at_with_right_of_way": flags.flagged_at & flags.right_of_way,
            "flagged_at_with_junction_fields": flags.flagged_at & fields,
            "flagged_away": flags.flagged_away,
            "flagged_away_with_junction_type": flags.flagged_away & flags.junction_type,
            "flagged_away_with_right_of_way": flags.flagged_away & flags.right_of_way,
            "flagged_away_with_junction_fields": flags.flagged_away & fields,
            "at_junction": corrected_at,
            "at_junction_with_junction_fields": corrected_at & fields,
            "away_from_junction": corrected_away,
            "away_with_junction_fields": corrected_away & fields,
            "recoded": corrected.ne(published).fillna(False).astype(bool),
            "near_junction_fields": catalan & ~inverted & flags.flagged_away & fields,
        }
    )
    out = parts.groupby(["region", "year"]).sum().astype(int).reset_index()
    out = out.rename(columns={"inverted": "crashes_in_inverted_province_years"})
    pairs = flags.loc[inverted, ["province", "year"]].drop_duplicates()
    regions = pairs.province.isin(CATALAN_PROVINCES).map(
        {True: "Catalonia", False: "rest of Spain"}
    )
    counts = pairs.groupby([regions, pairs.year]).size()
    out.insert(
        3,
        "inverted_province_years",
        [int(counts.get((region, year), 0)) for region, year in zip(out.region, out.year)],
    )
    out["share_flagged_at"] = out.flagged_at / out.crashes
    out["share_at_junction"] = out.at_junction / out.crashes
    return out


def _level_series(values: pd.Series, spec: dict[str, object]) -> pd.Series:
    """Map raw values to level labels: missing markers first, then the map, then the fallback."""
    mapping: dict = spec["map"]  # type: ignore[assignment]
    fallback = str(spec["fallback"])
    out = pd.Series(fallback, index=values.index, dtype="object")
    numeric = pd.to_numeric(values, errors="coerce") if values.dtype != bool else values
    if values.dtype != bool and numeric.notna().any():
        out[numeric == codes.NOT_APPLICABLE_CODE] = NOT_APPLICABLE
        out[numeric == codes.NOT_SPECIFIED_CODE] = NOT_SPECIFIED
        matched = numeric.map(mapping)
        out[matched.notna()] = matched[matched.notna()]
    else:
        matched = values.map(mapping)
        out[matched.notna()] = matched[matched.notna()]
    if values.dtype != bool:
        out[values.isna()] = NOT_SPECIFIED
    return out


def _code_keys(values: pd.Series, spec: dict[str, object]) -> pd.Series:
    """The grouping table's code for each row: a listed code, 999, 998, or the fallback row.

    Mirrors :func:`_level_series` so the counts describe exactly the rows the grouping table shows.
    """
    mapping: dict = spec["map"]  # type: ignore[assignment]
    out = pd.Series(FALLBACK_CODE, index=values.index, dtype="object")
    numeric = pd.to_numeric(values, errors="coerce") if values.dtype != bool else values
    if values.dtype != bool and numeric.notna().any():
        for code in (codes.NOT_APPLICABLE_CODE, codes.NOT_SPECIFIED_CODE):
            out[numeric == code] = str(code)
        for code in mapping:
            out[numeric == code] = str(code)
    else:
        for code in mapping:
            out[values == code] = str(code)
    return out


def is_nuisance(level: object) -> bool:
    """A missing-state level: what the form says rather than what happened, never an effect."""
    return str(level) in MISSING_LEVELS


def levels(predictor: str) -> list[str]:
    """Ordered levels of a predictor including the missing states it can take."""
    spec = PREDICTORS[predictor]
    base = list(spec["levels"])  # type: ignore[arg-type]
    extra = [str(spec["fallback"]), NOT_SPECIFIED, NOT_APPLICABLE]
    return base + [level for level in dict.fromkeys(extra) if level not in base]


def model_frame(
    crashes: pd.DataFrame | None = None, junction: str = JUNCTION_TREATMENT
) -> pd.DataFrame:
    """One row per crash: outcomes, province, numeric ``crash_year`` and every predictor as an ordered
    categorical (``year`` is the categorical predictor).

    The junction predictor reads DGT's flag through :func:`junction_codes` with ``junction`` as
    the treatment of the province-years whose flag is inverted."""
    if crashes is None:
        crashes = pd.read_parquet(PROCESSED_CRASHES, columns=MODEL_COLUMNS)
    out = pd.DataFrame(index=crashes.index)
    out["crash_year"] = crashes["ANYO"].astype("int16")
    out["province"] = crashes["COD_PROVINCIA"].astype("Int16").astype(str)
    for outcome in OUTCOMES:
        out[outcome] = crashes[outcome].astype(bool)
    flags = junction_flags(crashes)
    inverted = inverted_junction_rows(crashes, flags)
    merged: dict[str, dict[str, int]] = {}
    code_counts: dict[str, dict[str, int]] = {}
    for name, spec in PREDICTORS.items():
        raw = crashes[str(spec["source"])]
        keys = _code_keys(raw, spec)
        if name == "junction":
            # The grouping table counts DGT's codes as published, those of the inverted
            # province-years apart; the levels come from the flag as the model reads it.
            keys = keys.where(~inverted, keys + INVERTED_KEY)
            raw = junction_codes(crashes, junction, flags)
        code_counts[name] = {str(code): int(count) for code, count in keys.value_counts().items()}
        mapped = _level_series(raw, spec)
        reference = str(list(spec["levels"])[0])  # type: ignore[index]
        for source_level, target in dict(spec.get("fold", {})).items():  # type: ignore[union-attr]
            mapped[mapped == source_level] = target
        counts = mapped.value_counts()
        small = {
            str(level): int(count)
            for level, count in counts.items()
            if count < MIN_LEVEL_CRASHES and level != reference
        }
        if small and len(crashes) >= MIN_LEVEL_CRASHES:
            mapped[mapped.isin(list(small))] = reference
            merged[name] = small
        used = [level for level in levels(name) if (mapped == level).any()]
        out[name] = pd.Categorical(mapped, categories=used, ordered=True)
    # Which levels were merged, how many crashes each had, and how many crashes carry each code:
    # the grouping table needs all three to describe the model that was actually fitted.
    out.attrs["merged_levels"] = merged
    out.attrs["code_counts"] = code_counts
    # The province-years whose junction flag is inverted and how the model reads it there.
    pairs = flags.loc[inverted, ["province", "year"]].drop_duplicates()
    out.attrs["junction_inverted"] = sorted(
        (int(province), int(year)) for province, year in zip(pairs.province, pairs.year)
    )
    out.attrs["junction_treatment"] = junction
    return out


def grouping_table(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Every original code with its model level, for the severity page.

    Includes the missing markers and the "any other value" fallback. When ``frame`` (from
    :func:`model_frame`) is given, the table describes the model that was actually fitted: a code
    whose level was merged into the reference for having fewer than ``MIN_LEVEL_CRASHES`` crashes
    says so with the level's count, and a code no crash carries is marked as absent.
    """
    records = []
    for name, spec in PREDICTORS.items():
        source = str(spec["source"])
        mapping: dict = spec["map"]  # type: ignore[assignment]
        fold: dict = spec.get("fold", {})  # type: ignore[assignment]
        reference = str(list(spec["levels"])[0])  # type: ignore[index]
        rows: list[tuple[str, str]] = [(str(code), level) for code, level in mapping.items()]
        # The missing markers belong to the coded source columns only: a count (TOTAL_VEHICULOS)
        # and the year never carry 999 or 998, and neither do the derived columns.
        if source not in ("hour_band", "weekend", "TOTAL_VEHICULOS", "ANYO"):
            rows.append((str(codes.NOT_SPECIFIED_CODE), NOT_SPECIFIED))
            rows.append(
                (
                    str(codes.NOT_APPLICABLE_CODE),
                    f"{fold[NOT_APPLICABLE]} (folded: code 998 is exactly the street zone)"
                    if NOT_APPLICABLE in fold
                    else NOT_APPLICABLE,
                )
            )
        rows.append((FALLBACK_CODE, str(spec["fallback"])))
        counts: dict[str, int] | None = (
            None if frame is None else frame.attrs.get("code_counts", {}).get(name, {})
        )
        merged: dict[str, int] = (
            {} if frame is None else frame.attrs.get("merged_levels", {}).get(name, {})
        )
        for code, level in rows:
            shown, is_reference = level, level == reference
            # A code no crash carries says so; the merged annotation belongs to the codes that
            # actually brought the crashes, and counts the level, not the code.
            taken = counts is None or counts.get(code, 0) > 0
            if level in merged:
                is_reference = True
                shown = (
                    f"{reference} (merged: the {level} level's {merged[level]:,} crashes, "
                    f"fewer than {MIN_LEVEL_CRASHES})"
                    if taken
                    else f"{reference} (the {level} level was merged; no crash takes this code)"
                )
            elif not taken:
                shown = f"{level} (no crash takes this value)"
            records.append(
                {
                    "predictor": PREDICTOR_LABELS[name],
                    "source": source,
                    "code": code,
                    "level": shown,
                    "reference": is_reference,
                }
            )
        inverted = [] if frame is None else frame.attrs.get("junction_inverted", [])
        if name == "junction" and inverted:
            treatment = str(frame.attrs.get("junction_treatment", JUNCTION_TREATMENT))
            where = province_years(inverted)
            for code, level in mapping.items():
                read = _inverted_level(int(code), treatment)
                records.append(
                    {
                        "predictor": PREDICTOR_LABELS[name],
                        "source": source,
                        "code": f"{code}{INVERTED_KEY}",
                        "level": f"{read} ({JUNCTION_TREATMENTS[treatment]}: {where})",
                        "reference": read == reference,
                    }
                )
    return pd.DataFrame.from_records(records)


def _inverted_level(code: int, treatment: str) -> str:
    """The level a published junction code takes in an inverted province-year."""
    mapping: dict = PREDICTORS["junction"]["map"]  # type: ignore[assignment]
    if treatment in ("flip", "flip and near junctions"):
        return str(next(level for other, level in mapping.items() if other != code))
    if treatment == "junction type":
        return f"{AT_JUNCTION} with a junction type, otherwise {NOT_AT_JUNCTION}"
    if treatment == "unrecorded":
        return NOT_SPECIFIED
    return str(mapping[code])


def province_years(pairs: list[tuple[int, int]]) -> str:
    """Province-years in words, provinces that share their years together: "Barcelona, Girona,
    Lleida and Tarragona in 2023–2024"."""
    names = codes.labels_for("COD_PROVINCIA")
    by_province: dict[int, list[int]] = {}
    for province, year in sorted(pairs):
        by_province.setdefault(province, []).append(year)
    by_years: dict[tuple[int, ...], list[str]] = {}
    for province, years in by_province.items():
        by_years.setdefault(tuple(years), []).append(names.get(str(province), str(province)))

    def join(items: list[str]) -> str:
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]

    def span(years: tuple[int, ...]) -> str:
        if len(years) > 1 and list(years) == list(range(years[0], years[-1] + 1)):
            return f"{years[0]}–{years[-1]}"
        return join([str(year) for year in years])

    return "; ".join(f"{join(provinces)} in {span(years)}" for years, provinces in by_years.items())
