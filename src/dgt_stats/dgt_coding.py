"""How the DGT crash microdata record circumstances: unrecorded values, junction and presence coding.

The DGT microdata (one row per police-recorded crash with victims, all of Spain, 2016-2024) are
the national layer. This module measures three things about how its circumstance fields are
filled in, and the tables it writes are read by the models, the figures and the pages:

* **unrecorded shares** by field and province (:func:`regional_recording`,
  ``dgt_audit_regional``): the share of values "not specified", "unknown" or blank, among the
  crashes the field applies to, and how far the provinces differ;
* **the junction flag** (:func:`junction_coding`, ``dgt_audit_junction_coding``): from 2023 the
  records of the four Catalan provinces give the junction flag inverted, crashes away from a
  junction counting as at one;
* **fog and wind** (:func:`presence_coding`, ``dgt_audit_presence_coding``): these fields record a
  condition only when it was present, so an empty cell is a recorded "no"; some province-years
  code them the other way;
* **road type** (:func:`coding_by_region`, ``gen_coding_by_region``): the use of road-type codes 5,
  6 and 14 by year, for Catalonia and the rest of Spain.

A cell where the field does not apply is not unrecorded (:func:`statuses`): a 998 "No aplica"
code, an empty fog or wind field, and an empty or 999 junction type or right-of-way flag in a
crash recorded away from a junction.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from dgt_stats import codes
from dgt_stats.microdata import catalonia
from dgt_stats.paths import DGT_PROCESSED_CRASHES, TABLES_DIR

MAX_REGIONAL_SPREAD = 0.10
MIN_PROVINCE_CRASHES = 2000
CATALAN_PROVINCES = tuple(catalonia.DEMARCATION_PROVINCE_CODE.values())
UNRECORDED = ("not_specified", "unknown", "empty")

# Circumstance columns a severity model could use: every coded column of the dictionary except
# the geography codes (province, island) and the free direction field.
CANDIDATES = (
    "DIA_SEMANA",
    "ZONA",
    "ZONA_AGRUPADA",
    "TITULARIDAD_VIA",
    "TIPO_VIA",
    "TIPO_ACCIDENTE",
    "NUDO",
    "NUDO_INFO",
    "PRIORI_NORMA",
    "PRIORI_AGENTE",
    "PRIORI_SEMAFORO",
    "PRIORI_VERT_STOP",
    "PRIORI_VERT_CEDA",
    "PRIORI_HORIZ_STOP",
    "PRIORI_HORIZ_CEDA",
    "PRIORI_MARCAS",
    "PRIORI_PEA_NO_ELEV",
    "PRIORI_PEA_ELEV",
    "PRIORI_MARCA_CICLOS",
    "PRIORI_CIRCUNSTANCIAL",
    "PRIORI_OTRA",
    "CONDICION_NIVEL_CIRCULA",
    "CONDICION_FIRME",
    "CONDICION_ILUMINACION",
    "CONDICION_METEO",
    "CONDICION_NIEBLA",
    "CONDICION_VIENTO",
    "VISIB_RESTRINGIDA_POR",
    "ACERA",
    "TRAZADO_PLANTA",
)
OUTCOMES = ("TOTAL_MU24H", "TOTAL_HG24H", "TOTAL_MU30DF", "TOTAL_HG30DF", "TOTAL_VICTIMAS_30DF")


def read() -> pd.DataFrame:
    columns = ["ANYO", "ID_ACCIDENTE", "COD_PROVINCIA", *CANDIDATES, *OUTCOMES]
    return pd.read_parquet(DGT_PROCESSED_CRASHES, columns=columns)


def presence_field(column: str) -> bool:
    """A condition field that records the condition only when it was present.

    Every condition field in DGT's dictionary has a "Sin especificar" (999) code for a condition
    that was not recorded, except fog and wind. The wind field's dictionary codes absence as "."
    ("No se aprecia viento fuerte"); the fog field's lists only its two grades ("Niebla ligera",
    "Niebla intensa"). In both an empty cell is the recorded "no", not a missing value, except in
    the province-years whose records code the field another way (:func:`presence_coding`).
    """
    if column not in codes.CONDITION_COLUMNS:
        return False
    return str(codes.NOT_SPECIFIED_CODE) not in codes.labels_for(column)


# The fields that describe the junction a crash happened at: its type and how right of way was
# regulated there. For a crash NUDO places away from a junction DGT leaves the junction type empty
# and, having no "not applicable" code for the right-of-way flags, mostly writes 999 in them.
JUNCTION_FIELDS = ("NUDO_INFO", *codes.PRIORI_COLUMNS)
# The number of the road met at the junction. It is not a candidate (a road number, not a coded
# circumstance), but it describes the junction too: DGT fills it in only for crashes at one (99.9%
# of its filled cells), so where it is read (the data page's missing-values chart) the junction
# rule applies to it as well.
CROSSING_ROAD = "CARRETERA_CRUCE"
AT_JUNCTION_ONLY = (*JUNCTION_FIELDS, CROSSING_ROAD)


def junction_code() -> int:
    """NUDO's code for a crash at a junction, read from DGT's dictionary by its label."""
    found = [
        code
        for code, label in codes.labels_for("NUDO").items()
        if label.lower().startswith("en intersección")
    ]
    if len(found) != 1:
        raise ValueError(f"DGT dictionary: expected one NUDO code for a junction, found {found}")
    return int(found[0])


def statuses(frame: pd.DataFrame, columns: tuple[str, ...] = CANDIDATES) -> pd.DataFrame:
    """observed / not_specified / unknown / not_applicable / empty for each of ``columns`` (the
    candidate fields unless told otherwise).

    A cell where the field does not apply is "not applicable", whether DGT's dictionary says so
    with a code (998, as in the pavement field) or the field's own logic does: an empty presence
    field (:func:`presence_field`) is the recorded "no", and an empty or "not specified" junction
    field (:data:`JUNCTION_FIELDS`, and the crossing road where it is read) in a crash NUDO places
    away from a junction does not apply. A junction field with a recorded value stays observed
    wherever NUDO places the crash, and a crash with no NUDO value keeps its junction fields as
    they are. NUDO is read as ``frame`` holds it.
    """
    nudo = pd.to_numeric(frame["NUDO"], errors="coerce")
    away = nudo.notna() & nudo.ne(junction_code())
    out = {}
    for column in columns:
        status = codes.status(column, frame[column]).astype(str)
        if presence_field(column):
            status = status.replace("empty", "observed")
        if column in AT_JUNCTION_ONLY:
            status = status.mask(away & status.isin(["empty", "not_specified"]), "not_applicable")
        out[column] = status
    return pd.DataFrame(out, index=frame.index)


def recording_by_year(
    frame: pd.DataFrame | None = None,
    status: pd.DataFrame | None = None,
    columns: tuple[str, ...] = CANDIDATES,
) -> pd.DataFrame:
    """Per year and field of ``columns``: the crashes, those the field applies to (every status of
    :func:`statuses` but "not applicable") and those with a value recorded ("observed").

    The missing-values chart on the data page draws these fields from this table, so it judges
    each field on the crashes it applies to by the same rule as checks 6 and 7.
    """
    frame = read() if frame is None else frame
    status = statuses(frame, columns) if status is None else status
    year = pd.to_numeric(frame.ANYO, errors="coerce").astype(int)
    parts = []
    for column in columns:
        counts = (
            pd.DataFrame(
                {
                    "year": year,
                    "rows": True,
                    "applies": status[column].ne("not_applicable"),
                    "recorded": status[column].eq("observed"),
                }
            )
            .groupby("year")
            .sum()
            .astype(int)
            .reset_index()
        )
        counts.insert(1, "column", column)
        parts.append(counts)
    out = pd.concat(parts, ignore_index=True)
    out["share_applies"] = out.applies / out.rows
    out["share_recorded_where_applies"] = out.recorded / out.applies
    return out


# A presence field read as one records its condition in few crashes: elsewhere fog or strong wind
# is recorded in a few per cent of a province-year's crashes at most. A province-year whose
# records give the condition to more than this share of its crashes code the field their own way
# (``presence_coding``, columns ``*_coding_break``), and a blank there is not read as absence.
MAX_PRESENCE_SHARE = 0.1
# The Catalan file's fog field (D_BOIRA): fog present ("Si") or not ("No n'hi ha").
CAT_FOG = "D_BOIRA"
CAT_FOG_PRESENT = "Si"


def presence_coding(frame: pd.DataFrame) -> pd.DataFrame:
    """How often each presence field (:func:`presence_field`) records its condition, by province
    and year, and the fog field among the crashes with a death or serious injury within 24 hours
    beside the Catalan file's for the same crashes.

    A presence field records fog or strong wind only when there was some, so a blank there is
    read as the condition's absence. That reading holds where the field is filled in for the few
    crashes with the condition, not where a province's records fill it in for a large share of
    its crashes.
    """
    present = [column for column in CANDIDATES if presence_field(column)]
    d24 = pd.to_numeric(frame.TOTAL_MU24H, errors="coerce").fillna(0)
    s24 = pd.to_numeric(frame.TOTAL_HG24H, errors="coerce").fillna(0)
    severe = (d24 + s24).gt(0)
    # The condition recorded present: a numeric dictionary code (fog's two grades, wind's "1"),
    # not a blank nor the wind field's "." for its absence.
    recorded = {
        f"{column}_recorded": pd.to_numeric(frame[column], errors="coerce").isin(
            [int(code) for code in codes.labels_for(column) if code.isdigit()]
        )
        for column in present
    }
    fog = recorded["CONDICION_NIEBLA_recorded"]
    flags = pd.DataFrame(
        {
            "province": pd.to_numeric(frame.COD_PROVINCIA, errors="coerce").astype(int),
            "year": pd.to_numeric(frame.ANYO, errors="coerce").astype(int),
            "crashes": True,
            **recorded,
            "severe_crashes": severe,
            "severe_CONDICION_NIEBLA_recorded": severe & fog,
        }
    )
    out = flags.groupby(["province", "year"]).sum().astype(int).reset_index()
    names = codes.labels_for("COD_PROVINCIA")
    out.insert(1, "province_name", [names.get(str(p), str(p)) for p in out.province])
    out.insert(3, "catalan", out.province.isin(CATALAN_PROVINCES))
    for column in present:
        out[f"{column}_share"] = out[f"{column}_recorded"] / out.crashes
        out[f"{column}_coding_break"] = out[f"{column}_share"] > MAX_PRESENCE_SHARE
    cat = pd.read_parquet(catalonia.PROCESSED, columns=["year", "province_code", CAT_FOG])
    counts = (
        pd.DataFrame(
            {
                "province": pd.to_numeric(cat.province_code, errors="coerce").astype(int),
                "year": pd.to_numeric(cat.year, errors="coerce").astype(int),
                "cat_file_severe_crashes": True,
                "cat_file_fog": cat[CAT_FOG].eq(CAT_FOG_PRESENT),
            }
        )
        .groupby(["province", "year"])
        .sum()
        .astype(int)
        .reset_index()
    )
    out = out.merge(counts, on=["province", "year"], how="left", validate="one_to_one")
    return out.sort_values(["province", "year"]).reset_index(drop=True)


# The Catalan file's junction field (D_INTER_SECCIO): within a junction, within 50 m of one, or
# between junctions ("En secció").
CAT_WITHIN_JUNCTION = "Dintre intersecció"
CAT_NEAR_JUNCTION = "Arribant o eixint intersecció fins 50m"
# How far from a junction the Catalan file's approach zone reaches, read from its label.
NEAR_JUNCTION_METRES = int(re.search(r"(\d+)\s*m$", CAT_NEAR_JUNCTION).group(1))
CAT_BETWEEN_JUNCTIONS = "En secció"


def junction_coding(frame: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """How DGT's records use the junction flag, by province and year, beside the Catalan file.

    The junction type describes a junction, so DGT records it for crashes NUDO places at one and
    leaves it empty for the others. A province-year in which most crashes recorded away from a
    junction carry a junction type has the flag the wrong way round (``junction_flag_inverted``):
    its crashes recorded at a junction then carry 999 junction fields where none apply. For the
    Catalan provinces the Servei Català de Trànsit's file, which holds the crashes with a death or
    serious injury within 24 hours, gives the same crashes' place in its own coding.
    """
    nudo = pd.to_numeric(frame["NUDO"], errors="coerce")
    at = nudo.eq(junction_code())
    away = nudo.notna() & ~at
    d24 = pd.to_numeric(frame.TOTAL_MU24H, errors="coerce").fillna(0)
    s24 = pd.to_numeric(frame.TOTAL_HG24H, errors="coerce").fillna(0)
    severe = (d24 + s24).gt(0)
    flags = pd.DataFrame(
        {
            "province": pd.to_numeric(frame.COD_PROVINCIA, errors="coerce").astype(int),
            "year": pd.to_numeric(frame.ANYO, errors="coerce").astype(int),
            "crashes": True,
            "at_junction": at,
            "at_junction_type_not_specified": at & status["NUDO_INFO"].eq("not_specified"),
            "away_from_junction": away,
            "away_with_junction_type": away & status["NUDO_INFO"].eq("observed"),
            "severe_crashes": severe,
            "severe_at_junction": severe & at,
        }
    )
    out = flags.groupby(["province", "year"]).sum().astype(int).reset_index()
    names = codes.labels_for("COD_PROVINCIA")
    out.insert(1, "province_name", [names.get(str(p), str(p)) for p in out.province])
    out.insert(3, "catalan", out.province.isin(CATALAN_PROVINCES))
    out["junction_flag_inverted"] = out.away_with_junction_type > 0.5 * out.away_from_junction
    cat = pd.read_parquet(catalonia.PROCESSED, columns=["year", "province_code", "D_INTER_SECCIO"])
    place = {
        "cat_file_within_junction": CAT_WITHIN_JUNCTION,
        "cat_file_near_junction": CAT_NEAR_JUNCTION,
        "cat_file_between_junctions": CAT_BETWEEN_JUNCTIONS,
    }
    counts = (
        pd.DataFrame(
            {
                "province": pd.to_numeric(cat.province_code, errors="coerce").astype(int),
                "year": pd.to_numeric(cat.year, errors="coerce").astype(int),
                "cat_file_severe_crashes": True,
                **{name: cat.D_INTER_SECCIO.eq(label) for name, label in place.items()},
            }
        )
        .groupby(["province", "year"])
        .sum()
        .astype(int)
        .reset_index()
    )
    out = out.merge(counts, on=["province", "year"], how="left", validate="one_to_one")
    return out.sort_values(["province", "year"]).reset_index(drop=True)


def _inverted_rows(frame: pd.DataFrame, coding: pd.DataFrame) -> pd.Series:
    """The crashes of the province-years whose junction flag reads inverted."""
    inverted = coding[coding.junction_flag_inverted]
    keys = pd.MultiIndex.from_arrays(
        [
            pd.to_numeric(frame.COD_PROVINCIA, errors="coerce").astype(int),
            pd.to_numeric(frame.ANYO, errors="coerce").astype(int),
        ]
    )
    marked = keys.isin(pd.MultiIndex.from_frame(inverted[["province", "year"]]))
    return pd.Series(marked, index=frame.index)


# DGT's count of severe Catalan crashes at a junction "matches" a place in the Catalan file's coding
# when the two differ by at most this share of the year's severe crashes. The two files hold the
# same crashes (the transfer checks' inclusion equivalence), so a coding that maps one place to the
# other gives counts this close.
MATCH_TOLERANCE = 0.01
CATALAN_PLACES = {
    "within or near a junction": ("cat_file_within_junction", "cat_file_near_junction"),
    "within a junction": ("cat_file_within_junction",),
    "between junctions": ("cat_file_between_junctions",),
}


def catalan_junction_years(coding: pd.DataFrame) -> pd.DataFrame:
    """DGT's severe crashes at a junction in the Catalan provinces, by year, against the places
    the Catalan file gives the same crashes, and which place DGT's count matches."""
    cat = coding[coding.catalan.astype(bool) & coding.cat_file_severe_crashes.notna()]
    columns = [
        "severe_crashes",
        "severe_at_junction",
        "cat_file_severe_crashes",
        "cat_file_within_junction",
        "cat_file_near_junction",
        "cat_file_between_junctions",
    ]
    year = cat.groupby("year")[columns].sum()
    year["dgt_share_at_junction"] = year.severe_at_junction / year.severe_crashes
    matches = []
    for row in year.itertuples():
        gaps = {
            place: abs(row.severe_at_junction - sum(getattr(row, c) for c in parts))
            for place, parts in CATALAN_PLACES.items()
        }
        place = min(gaps, key=gaps.get)
        matches.append(place if gaps[place] <= MATCH_TOLERANCE * row.severe_crashes else "none")
    for place, parts in CATALAN_PLACES.items():
        share = year[list(parts)].sum(axis=1) / year.cat_file_severe_crashes
        year["cat_share_" + place.replace(" ", "_")] = share
    year["dgt_at_junction_matches"] = matches
    flagged = coding[coding.catalan.astype(bool) & coding.junction_flag_inverted.astype(bool)]
    year["junction_flag_inverted"] = year.index.isin(flagged.year.unique())
    return year.reset_index()


def regional_recording(
    frame: pd.DataFrame, status: pd.DataFrame, coding: pd.DataFrame
) -> pd.DataFrame:
    """Share of unrecorded values per field and province, summarised per field.

    Each share is taken over the crashes the field applies to (every status but
    "not applicable"), so a province with fewer junction crashes, say, does not look better
    recorded for it. For the junction fields the spread is also given without the province-years
    whose junction flag reads inverted (:func:`junction_coding`), where crashes away from a
    junction count as unrecorded junction crashes; the criterion is read on every province-year.
    """
    province = pd.to_numeric(frame.COD_PROVINCIA, errors="coerce").astype(int)
    sizes = province.value_counts()
    large = sizes[sizes >= MIN_PROVINCE_CRASHES].index
    names = codes.labels_for("COD_PROVINCIA")
    catalan = province.isin(CATALAN_PROVINCES)
    inverted = _inverted_rows(frame, coding)
    rows = []
    for column in CANDIDATES:
        applies = status[column].ne("not_applicable")
        unrecorded = status[column].isin(UNRECORDED)[applies]
        by_province = unrecorded.groupby(province[applies]).mean().loc[large]
        top = by_province.sort_values(ascending=False)
        spread = float(by_province.max() - by_province.min())
        consistent_max = consistent = np.nan
        if column in JUNCTION_FIELDS:
            kept = unrecorded[~inverted[applies]]
            shares = kept.groupby(province[kept.index]).mean().reindex(large).dropna()
            consistent_max, consistent = float(shares.max()), float(shares.max() - shares.min())
        rows.append(
            {
                "field": column,
                "applies_share": float(applies.mean()),
                "unrecorded_share": float(unrecorded.mean()),
                "unrecorded_share_catalonia": float(unrecorded[catalan[applies]].mean()),
                "unrecorded_share_rest_of_spain": float(unrecorded[~catalan[applies]].mean()),
                "province_min": float(by_province.min()),
                "province_max": float(by_province.max()),
                "province_spread": spread,
                "province_max_without_inverted_junction_years": consistent_max,
                "province_spread_without_inverted_junction_years": consistent,
                "highest_provinces": "; ".join(
                    f"{names.get(str(p), p)} {v:.0%}" for p, v in top.head(3).items()
                ),
                "catalan_provinces_in_top_five": int(
                    top.head(5).index.isin(CATALAN_PROVINCES).sum()
                ),
                "provinces_compared": int(len(by_province)),
                "comparable_across_provinces": spread <= MAX_REGIONAL_SPREAD,
            }
        )
    return pd.DataFrame(rows)


PRESENCE_NAMES = {"CONDICION_NIEBLA": "fog", "CONDICION_VIENTO": "strong wind"}


def presence_breaks(presence: pd.DataFrame) -> pd.DataFrame:
    """The province-years whose records give a presence field's condition to more than
    :data:`MAX_PRESENCE_SHARE` of their crashes: field, province, years and shares."""
    rows = []
    for column in [c for c in CANDIDATES if presence_field(c)]:
        flagged = presence[presence[f"{column}_coding_break"].astype(bool)]
        for (province, name), part in flagged.groupby(["province", "province_name"]):
            rows.append(
                {
                    "field": column,
                    "province": int(province),
                    "province_name": str(name),
                    "years": [int(y) for y in part.year],
                    "share_low": float(part[f"{column}_share"].min()),
                    "share_high": float(part[f"{column}_share"].max()),
                }
            )
    return pd.DataFrame(
        rows, columns=["field", "province", "province_name", "years", "share_low", "share_high"]
    )


def coding_by_region() -> pd.DataFrame:
    """Codes whose use changes in DGT's records, by year, for Catalonia and the rest of Spain.

    Road-type code 5 (a conventional road with a dual carriageway) against code 6 (single
    carriageway), code 14 ("other"), and the junction-type field left blank or marked "not
    specified" (999). Each count is of injury crashes, so a change confined to one region shows as
    a jump in that region's row only.
    """
    dgt = pd.read_parquet(
        DGT_PROCESSED_CRASHES, columns=["ANYO", "COD_PROVINCIA", "TIPO_VIA", "NUDO_INFO"]
    )
    road = pd.to_numeric(dgt.TIPO_VIA, errors="coerce")
    junction = pd.to_numeric(dgt.NUDO_INFO, errors="coerce")
    frame = pd.DataFrame(
        {
            "year": pd.to_numeric(dgt.ANYO, errors="coerce").astype(int),
            "region": np.where(
                pd.to_numeric(dgt.COD_PROVINCIA, errors="coerce").isin(CATALAN_PROVINCES),
                "Catalonia",
                "Spain outside Catalonia",
            ),
            "road_type_5_dual_carriageway": road.eq(5),
            "road_type_6_single_carriageway": road.eq(6),
            "road_type_14_other": road.eq(14),
            "junction_type_blank": dgt.NUDO_INFO.isna(),
            "junction_type_not_specified": junction.eq(999),
        }
    )
    out = frame.groupby(["year", "region"]).agg(
        crashes=("year", "size"),
        **{
            column: (column, "sum")
            for column in frame.columns
            if column.startswith(("road_type", "junction_type"))
        },
    )
    return out.reset_index().astype({c: int for c in out.columns})


def write() -> dict[str, pd.DataFrame]:
    """Write ``dgt_audit_regional``, ``dgt_audit_junction_coding``,
    ``dgt_audit_presence_coding`` and ``gen_coding_by_region`` to ``reports/tables``."""
    frame = read()
    status = statuses(frame)
    coding = junction_coding(frame, status)
    tables = {
        "dgt_audit_regional": regional_recording(frame, status, coding),
        "dgt_audit_junction_coding": coding,
        "dgt_audit_presence_coding": presence_coding(frame),
        "gen_coding_by_region": coding_by_region(),
    }
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.6g")
    return tables
