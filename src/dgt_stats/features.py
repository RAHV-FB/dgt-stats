"""Model frame for the crash-severity models: grouped, labelled predictors with reference levels.

Every predictor is an ordered categorical whose first level is the reference (the most common level,
so odds ratios read "relative to the typical crash"). The missing states (not specified, not
applicable, and a field's explicit unknown code) are levels of their own and no row is dropped,
because missingness is year-dependent. The grouping maps are data, so the severity page can print
them.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import codes
from dgt_stats.paths import PROCESSED_DATA_DIR

PROCESSED_CRASHES = PROCESSED_DATA_DIR / "accidentes.parquet"

OUTCOMES = ("fatal", "serious")
NOT_SPECIFIED = "not specified"
NOT_APPLICABLE = "not applicable"
# The label a field's explicit unknown code takes (weather 7, surface 9, alignment 4).
UNKNOWN = "unknown"
# The three missing states together: levels that record what the form says, not what happened.
MISSING_LEVELS = frozenset({NOT_SPECIFIED, NOT_APPLICABLE, UNKNOWN})
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
        "source": "road_group",
        "levels": ["urban street", "conventional", "dual carriageway", "motorway", "other road"],
        "map": {
            "urban_street": "urban street",
            "conventional": "conventional",
            "dual_carriageway": "dual carriageway",
            "motorway": "motorway",
            "other": "other road",
        },
        "fallback": NOT_SPECIFIED,
    },
    "crash_type": {
        "source": "TIPO_ACCIDENTE",
        "levels": [
            "side collision",
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
            2: "side collision",
            3: "side collision",
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
        # Only the yes/no field is used; the junction type (NUDO_INFO) is not. From 2023 the
        # at-junction share rises from 38 % to 44 %, mostly in Barcelona, and NUDO_INFO stops
        # being empty exactly when NUDO says "not at a junction"; the level pools both regimes.
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

MODEL_COLUMNS = list(
    dict.fromkeys(
        ["ANYO", "COD_PROVINCIA", "fatal", "serious"]
        + [str(spec["source"]) for spec in PREDICTORS.values()]
    )
)


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


def levels(predictor: str) -> list[str]:
    """Ordered levels of a predictor including the missing states it can take."""
    spec = PREDICTORS[predictor]
    base = list(spec["levels"])  # type: ignore[arg-type]
    extra = [str(spec["fallback"]), NOT_SPECIFIED, NOT_APPLICABLE]
    return base + [level for level in dict.fromkeys(extra) if level not in base]


def model_frame(crashes: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per crash: outcomes, province, numeric ``crash_year`` and every predictor as an ordered
    categorical (``year`` is the categorical predictor)."""
    if crashes is None:
        crashes = pd.read_parquet(PROCESSED_CRASHES, columns=MODEL_COLUMNS)
    out = pd.DataFrame(index=crashes.index)
    out["crash_year"] = crashes["ANYO"].astype("int16")
    out["province"] = crashes["COD_PROVINCIA"].astype("Int16").astype(str)
    for outcome in OUTCOMES:
        out[outcome] = crashes[outcome].astype(bool)
    merged: dict[str, dict[str, int]] = {}
    code_counts: dict[str, dict[str, int]] = {}
    for name, spec in PREDICTORS.items():
        raw = crashes[str(spec["source"])]
        code_counts[name] = {
            str(code): int(count) for code, count in _code_keys(raw, spec).value_counts().items()
        }
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
        if source not in ("hour_band", "weekend", "road_group", "TOTAL_VEHICULOS", "ANYO"):
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
    return pd.DataFrame.from_records(records)
