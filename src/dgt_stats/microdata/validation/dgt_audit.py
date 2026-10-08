"""Does the DGT crash microdata belong in a severity model, or only in the national layer?

The DGT microdata (one row per police-recorded crash with victims, all of Spain, 2016-2024) are the
national analytical layer: trends, province and year comparisons, the denominator-free shares the
site reports. Using them to *train* or *test* a severity model is a different claim, and it is
allowed only if the file passes seven checks, declared here before any result is read:

1. **unit**: one row is one crash (unique key; rows equal the yearbook's crash totals);
2. **target observed**: the outcome columns are present on every row and internally consistent
   (deaths within 30 days are never fewer than deaths within 24 hours);
3. **feature definitions**: every candidate column has a dictionary entry and every code that
   appears is in the dictionary;
4. **sample construction**: the rows reproduce the published totals of crashes, deaths and
   injuries each year, so the file is the complete published universe, not a sample;
5. **severity and inclusion definitions**: 24-hour and 30-day deaths and hospitalised injuries
   are separate columns that reconcile with the yearbook;
6. **comparable across regions**: a field's share of unrecorded values ("not specified",
   "unknown", blank), among the crashes the field applies to, varies by no more than
   :data:`MAX_REGIONAL_SPREAD` between provinces with at least :data:`MIN_PROVINCE_CRASHES`
   crashes;
7. **recording artefacts do not dominate**: a model that sees only *which fields were left
   unrecorded* reaches less than :data:`MAX_ARTEFACT_SHARE` of the ranking ability (ROC-AUC above
   0.5) of a model that sees the recorded values.

A cell where the field does not apply is not unrecorded (:func:`statuses`): a 998 "No aplica"
code, an empty fog or wind field (they record only a condition that was present), and an empty or
999 junction type or right-of-way flag in a crash recorded away from a junction.

Checks 1-5 are about the file; 6-7 about whether its variables mean the same everywhere. A field
that fails 6 can still be used where it was validated against another source on the same crashes
(the common-feature tests do exactly that); a file that fails 7 cannot be used to train a
national model without its recording regime becoming part of what the model learns.

The second half audits the one place the DGT file does enter the modelling: the national test of
the Catalan common-feature model (target and inclusion equivalence, no Catalan records in the
national test, prevalence, coding, missingness, in-domain reference and transfer gap).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from dgt_stats import codes
from dgt_stats.microdata import catalonia
from dgt_stats.microdata.ml import modelling
from dgt_stats.microdata.validation import harmonise, transport
from dgt_stats.paths import DGT_PROCESSED_CRASHES, DOCS_DIR, TABLES_DIR

log = logging.getLogger(__name__)

DOC = DOCS_DIR / "DGT_MICRODATA_AUDIT.md"
MAX_REGIONAL_SPREAD = 0.10
MIN_PROVINCE_CRASHES = 2000
MAX_ARTEFACT_SHARE = 0.5
SAMPLE_ROWS = 200_000
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
    "Niebla intensa"). In both an empty cell is the recorded "no", not a missing value.
    """
    labels = codes.labels_for(column)
    return column in codes.CONDITION_COLUMNS and str(codes.NOT_SPECIFIED_CODE) not in labels


# The fields that describe the junction a crash happened at: its type and how right of way was
# regulated there. For a crash NUDO places away from a junction DGT leaves the junction type empty
# and, having no "not applicable" code for the right-of-way flags, mostly writes 999 in them.
JUNCTION_FIELDS = ("NUDO_INFO", *codes.PRIORI_COLUMNS)


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


def statuses(frame: pd.DataFrame) -> pd.DataFrame:
    """observed / not_specified / unknown / not_applicable / empty for every candidate field.

    A cell where the field does not apply is "not applicable", whether DGT's dictionary says so
    with a code (998, as in the pavement field) or the field's own logic does: an empty presence
    field (:func:`presence_field`) is the recorded "no", and an empty or "not specified" junction
    field (:data:`JUNCTION_FIELDS`) in a crash NUDO places away from a junction does not apply. A
    junction field with a recorded value stays observed wherever NUDO places the crash, and a crash
    with no NUDO value keeps its junction fields as they are.
    """
    nudo = pd.to_numeric(frame["NUDO"], errors="coerce")
    away = nudo.notna() & nudo.ne(junction_code())
    out = {}
    for column in CANDIDATES:
        status = codes.status(column, frame[column]).astype(str)
        if presence_field(column):
            status = status.replace("empty", "observed")
        if column in JUNCTION_FIELDS:
            status = status.mask(away & status.isin(["empty", "not_specified"]), "not_applicable")
        out[column] = status
    return pd.DataFrame(out, index=frame.index)


def recording_by_year(
    frame: pd.DataFrame | None = None, status: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Per year and candidate field: the crashes, those the field applies to (every status of
    :func:`statuses` but "not applicable") and those with a value recorded ("observed").

    The missing-values chart on the data page draws these fields from this table, so it judges
    each field on the crashes it applies to by the same rule as checks 6 and 7.
    """
    frame = read() if frame is None else frame
    status = statuses(frame) if status is None else status
    year = pd.to_numeric(frame.ANYO, errors="coerce").astype(int)
    parts = []
    for column in CANDIDATES:
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


# The Catalan file's junction field (D_INTER_SECCIO): within a junction, within 50 m of one, or
# between junctions ("En secció").
CAT_WITHIN_JUNCTION = "Dintre intersecció"
CAT_NEAR_JUNCTION = "Arribant o eixint intersecció fins 50m"
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
    out.insert(3, "catalan", out.province.isin(harmonise.CATALAN_PROVINCES))
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


# ----------------------------------------------------------------------------- checks 1-5
def file_checks(frame: pd.DataFrame) -> list[dict]:
    validation = pd.read_csv(TABLES_DIR / "validation.csv")

    def passed(check: str) -> tuple[int, int]:
        rows = validation[validation.check.eq(check)]
        return int(rows.passed.sum()), len(rows)

    key_ok, key_n = passed("unique_key")
    rows_ok, rows_n = passed("row_count")
    victims_ok, victims_n = passed("victim_total")
    domain_ok, domain_n = passed("code_domain")
    duplicated = int(frame.duplicated(["ANYO", "ID_ACCIDENTE"]).sum())
    missing_outcome = {
        c: int(pd.to_numeric(frame[c], errors="coerce").isna().sum()) for c in OUTCOMES
    }
    d24 = pd.to_numeric(frame.TOTAL_MU24H, errors="coerce")
    d30 = pd.to_numeric(frame.TOTAL_MU30DF, errors="coerce")
    inconsistent = int((d30 < d24).sum())
    undocumented = [c for c in CANDIDATES if not codes.labels_for(c)]
    return [
        {
            "check": "1 unit",
            "criterion": "one row per crash: no duplicate (year, ID_ACCIDENTE); rows per year "
            "equal the yearbook's crash totals",
            "evidence": f"{duplicated} duplicate keys in {len(frame):,} rows; yearly key checks "
            f"{key_ok}/{key_n} and row-count reconciliations {rows_ok}/{rows_n} passed",
            "passed": duplicated == 0 and key_ok == key_n and rows_ok == rows_n,
        },
        {
            "check": "2 target observed",
            "criterion": "outcome columns present on every row; 30-day deaths never below "
            "24-hour deaths",
            "evidence": "missing values: "
            + ", ".join(f"{c} {n}" for c, n in missing_outcome.items())
            + f"; rows with fewer 30-day than 24-hour deaths: {inconsistent}",
            "passed": not any(missing_outcome.values()) and inconsistent == 0,
        },
        {
            "check": "3 feature definitions",
            "criterion": "every candidate column documented in the dictionary; every code that "
            "appears is a dictionary code",
            "evidence": f"{len(CANDIDATES) - len(undocumented)}/{len(CANDIDATES)} candidate "
            f"columns have dictionary labels; code-domain checks {domain_ok}/{domain_n} passed",
            "passed": not undocumented and domain_ok == domain_n,
        },
        {
            "check": "4 sample construction",
            "criterion": "rows reproduce the published annual totals of crashes, deaths and "
            "injuries (the file is the complete published universe, not a sample)",
            "evidence": f"crash-count reconciliations {rows_ok}/{rows_n}, victim-total "
            f"reconciliations {victims_ok}/{victims_n} passed",
            "passed": rows_ok == rows_n and victims_ok == victims_n,
        },
        {
            "check": "5 severity and inclusion definitions",
            "criterion": "24-hour and 30-day deaths and hospitalised injuries are separate "
            "columns that reconcile with the yearbook",
            "evidence": "TOTAL_MU24H, TOTAL_MU30DF, TOTAL_HG24H, TOTAL_HG30DF present; the "
            f"victim-total reconciliations ({victims_ok}/{victims_n}) cover 30-day victims and "
            "24-hour deaths",
            "passed": victims_ok == victims_n,
        },
    ]


# ----------------------------------------------------------------------------- check 6
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
    catalan = province.isin(harmonise.CATALAN_PROVINCES)
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
                    top.head(5).index.isin(harmonise.CATALAN_PROVINCES).sum()
                ),
                "provinces_compared": int(len(by_province)),
                "comparable_across_provinces": spread <= MAX_REGIONAL_SPREAD,
            }
        )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- check 7
def _cv_predictions(x: pd.DataFrame, y: np.ndarray) -> np.ndarray:
    """Out-of-fold probabilities of a one-hot logistic regression."""
    prep = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), list(x.columns))]
    )
    model = Pipeline([("prep", prep), ("model", LogisticRegression(max_iter=2000))])
    folds = StratifiedKFold(modelling.N_FOLDS, shuffle=True, random_state=modelling.SEED)
    return cross_val_predict(model, x, y, cv=folds, method="predict_proba")[:, 1]


def _share_of_lift(y: np.ndarray, flags: np.ndarray, values: np.ndarray) -> float:
    lift = roc_auc_score(y, values) - 0.5
    return float((roc_auc_score(y, flags) - 0.5) / lift) if lift > 0 else np.nan


def share_interval(y: np.ndarray, flags: np.ndarray, values: np.ndarray) -> tuple[float, float]:
    """Paired percentile interval for the artefact share: both models' out-of-fold scores are
    resampled together, so the interval covers the sampling of the evaluated crashes, not the
    refitting of the models."""
    shares = [
        _share_of_lift(y[idx], flags[idx], values[idx])
        for idx in modelling.resamples(len(y), None, modelling.N_BOOT)
        if 0 < y[idx].sum() < len(idx)
    ]
    low, high = np.nanpercentile(shares, [2.5, 97.5])
    return float(low), float(high)


def artefact_strength(frame: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """Ranking ability from *which fields are unrecorded* against from the recorded values."""
    deaths24 = pd.to_numeric(frame.TOTAL_MU24H, errors="coerce").fillna(0)
    serious24 = pd.to_numeric(frame.TOTAL_HG24H, errors="coerce").fillna(0)
    deaths30 = pd.to_numeric(frame.TOTAL_MU30DF, errors="coerce").fillna(0)
    universes = (
        (
            "every crash with victims",
            np.ones(len(frame), dtype=bool),
            (deaths30 > 0).to_numpy(),
            "death within 30 days",
        ),
        (
            "crashes with a death or serious injury within 24 hours (the transfer test's universe)",
            ((deaths24 + serious24) > 0).to_numpy(),
            (deaths24 > 0).to_numpy(),
            "death within 24 hours",
        ),
    )
    rng = np.random.default_rng(modelling.SEED)
    rows = []
    for universe, mask, target, target_label in universes:
        index = np.flatnonzero(mask)
        if len(index) > SAMPLE_ROWS:
            index = np.sort(rng.choice(index, SAMPLE_ROWS, replace=False))
        y = target[index].astype(int)
        values = frame.iloc[index][list(CANDIDATES)].astype(str)
        flags = status.iloc[index].isin(UNRECORDED).astype(int).astype(str)
        log.info("DGT audit: artefact strength on %s (%d rows)", universe, len(index))
        p_values = _cv_predictions(values, y)
        p_flags = _cv_predictions(flags, y)
        share = _share_of_lift(y, p_flags, p_values)
        low, high = share_interval(y, p_flags, p_values)
        rows.append(
            {
                "universe": universe,
                "target": target_label,
                "rows": int(len(index)),
                "positives": int(y.sum()),
                "prevalence": float(y.mean()),
                "roc_auc_recorded_values": float(roc_auc_score(y, p_values)),
                "roc_auc_unrecorded_flags_only": float(roc_auc_score(y, p_flags)),
                "artefact_share_of_lift": share,
                "artefact_share_low": low,
                "artefact_share_high": high,
                # The criterion, fixed in advance, is on the estimate; the interval is reported.
                "artefacts_dominate": bool(share >= MAX_ARTEFACT_SHARE),
            }
        )
    return pd.DataFrame(rows)


def outcome_recording(frame: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """Unrecorded share among fatal (30-day) and non-fatal crashes the field applies to, per field
    and region."""
    fatal = pd.to_numeric(frame.TOTAL_MU30DF, errors="coerce").fillna(0).gt(0)
    catalan = pd.to_numeric(frame.COD_PROVINCIA, errors="coerce").isin(harmonise.CATALAN_PROVINCES)
    rows = []
    for column in CANDIDATES:
        applies = status[column].ne("not_applicable")
        unrecorded = status[column].isin(UNRECORDED)
        for region, area in (("Catalonia", catalan), ("rest of Spain", ~catalan)):
            mask = area & applies
            a = float(unrecorded[mask & fatal].mean())
            b = float(unrecorded[mask & ~fatal].mean())
            rows.append(
                {
                    "field": column,
                    "region": region,
                    "unrecorded_share_fatal": a,
                    "unrecorded_share_not_fatal": b,
                    "ratio_fatal_to_not_fatal": a / b if b > 0 else np.nan,
                }
            )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- the transfer test
def transfer_checks(tables: dict[str, pd.DataFrame]) -> list[dict]:
    """Is the Catalonia -> Spain test what it says it is?"""
    comparison = pd.read_csv(TABLES_DIR / "cat_vs_dgt_province_year.csv")
    dgt = harmonise.read(harmonise.DGT_COMMON_PATH)
    cat = harmonise.read(harmonise.CAT_COMMON_PATH)
    validation = tables["ml_common_feature_validation"]
    moved = tables["ml_transport_validation"]
    national = moved[
        moved.experiment.eq("Catalonia -> Spain outside Catalonia")
        & moved.estimator.ne("baseline_prior")
        & moved.status.eq("reported")
    ].iloc[0]
    test = dgt[dgt.domain.eq(transport.NATIONAL)]
    leaked = int(test.province_code.isin(harmonise.CATALAN_PROVINCES).sum())
    no_province = int(test.province_code.isna().sum())
    fatal_equal = int((comparison.ratio_fatal_24h == 1).sum())
    severe = comparison.cat_crashes_fatal_or_serious / comparison.dgt_crashes_fatal_or_serious_24h
    used = validation[validation.enters_cross_source_tests]
    fields = [f"dgt_{f}" for f in used.field]
    ns = harmonise.NOT_SPECIFIED
    miss = {
        name: float(np.mean([frame[f].astype(str).eq(ns).mean() for f in fields if f in frame]))
        for name, frame in (
            ("Catalan file", cat),
            ("DGT Catalonia", dgt[dgt.domain.eq(transport.DGT_CATALONIA)]),
            ("DGT outside Catalonia", test),
        )
    }
    gap = float(national.roc_auc - national.in_domain_cv_roc_auc)
    return [
        {
            "check": "target equivalence",
            "criterion": "the Catalan file's fatal crashes are DGT's crashes with a death "
            "within 24 hours (same count in every province-year both hold)",
            "evidence": f"{fatal_equal} of {len(comparison)} province-years equal",
            "passed": fatal_equal == len(comparison),
        },
        {
            "check": "inclusion equivalence",
            "criterion": "the Catalan file holds the crashes DGT records with a death or serious "
            "injury within 24 hours (counts within 2% in every province-year)",
            "evidence": f"Catalan / DGT count ratio {severe.min():.3f} to {severe.max():.3f}",
            "passed": bool(severe.between(0.98, 1.02).all()),
        },
        {
            "check": "no Catalan records in the national test",
            "criterion": "test rows exclude the four Catalan provinces; the model is trained on "
            "the Catalan file only",
            "evidence": f"{leaked} test rows in a Catalan province, {no_province} without a "
            f"province, of {len(test):,}",
            "passed": leaked == 0 and no_province == 0,
        },
        {
            "check": "prevalence",
            "criterion": "reported, not a pass/fail: a shift moves calibration, not ranking",
            "evidence": f"training {national.train_prevalence:.1%}, national test "
            f"{national.test_prevalence:.1%}; mean predicted {national.mean_predicted:.1%}",
            "passed": True,
        },
        {
            "check": "feature coding",
            "criterion": "only fields whose two codings agree on the crashes both sources hold "
            f"(Jensen-Shannon divergence at most {harmonise.MAX_OVERLAP_JSD})",
            "evidence": f"{len(used)} fields used, largest divergence "
            f"{used.overlap_jsd.max():.2g}; excluded: "
            + ", ".join(validation.loc[~validation.enters_cross_source_tests, "field"]),
            "passed": bool(used.overlap_jsd.max() <= harmonise.MAX_OVERLAP_JSD),
        },
        {
            "check": "missingness",
            "criterion": "reported: mean share 'not specified' over the fields used",
            "evidence": "; ".join(f"{k} {v:.1%}" for k, v in miss.items()),
            "passed": True,
        },
        {
            "check": "in-domain reference and transfer gap",
            "criterion": "a model trained on DGT crashes outside Catalonia, same fields "
            "(5-fold CV), against the transferred Catalan model on the same crashes",
            "evidence": f"target-domain native ROC-AUC {national.in_domain_cv_roc_auc:.3f}, "
            f"transferred {national.roc_auc:.3f} ({national.roc_auc_low:.3f}-"
            f"{national.roc_auc_high:.3f}); gap (transferred minus native) {gap:+.3f}; "
            f"n={int(national.test_n):,}, positives={int(national.test_positives):,}, "
            f"calibration slope {national.calibration_slope:.2f}",
            "passed": True,
        },
    ]


# ----------------------------------------------------------------------------- verdict and document
def decide(checks: pd.DataFrame) -> str:
    failed = checks[~checks.passed & checks.check.str.match(r"\d")]
    if failed.empty:
        return "DGT microdata may train a severity model"
    return (
        "DGT microdata stay the national analytical layer and an external test domain for "
        "fields validated against another source; they do not train a severity model here"
    )


def _md(frame: pd.DataFrame, pct: tuple[str, ...] = (), dec: tuple[str, ...] = ()) -> str:
    head = "| " + " | ".join(frame.columns) + " |"
    sep = "|" + "---|" * len(frame.columns)
    lines = [head, sep]
    for row in frame.itertuples(index=False):
        cells = []
        for column, value in zip(frame.columns, row):
            if column in pct and pd.notna(value):
                cells.append(f"{value:.1%}")
            elif column in dec and pd.notna(value):
                cells.append(f"{value:.3f}")
            elif isinstance(value, (bool, np.bool_)):
                cells.append("yes" if value else "no")
            else:
                cells.append(str(value).replace("|", "/"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _span(years: list[int]) -> str:
    """Years as runs: 2016-2020 and 2022."""
    runs: list[list[int]] = []
    for year in sorted({int(y) for y in years}):
        if runs and year == runs[-1][-1] + 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    return _join([f"{r[0]}-{r[-1]}" if len(r) > 1 else str(r[0]) for r in runs])


def _range(values: pd.Series) -> str:
    low, high = float(values.min()), float(values.max())
    return f"{low:.1%}" if f"{low:.1%}" == f"{high:.1%}" else f"{low:.1%}-{high:.1%}"


def _junction_section(coding: pd.DataFrame, regional: pd.DataFrame) -> list[str]:
    """The province-years whose junction flag reads inverted, worded from the coding table."""
    inverted = coding[coding.junction_flag_inverted]
    if inverted.empty:
        return [
            "In every province-year the junction type is recorded for crashes at a junction and "
            "left empty away from one.",
            "",
        ]
    by_years: dict[tuple[int, ...], list[str]] = {}
    for name, years in inverted.groupby("province_name").year.apply(tuple).items():
        by_years.setdefault(years, []).append(str(name))
    where = "; ".join(f"{_join(names)} in {_span(list(y))}" for y, names in by_years.items())
    typed = inverted.away_with_junction_type / inverted.away_from_junction
    others = coding[~coding.junction_flag_inverted]
    typed_elsewhere = others.away_with_junction_type / others.away_from_junction
    blank_at = inverted.at_junction_type_not_specified / inverted.at_junction
    lines = [
        f"In {where}, {_range(typed)} of the crashes DGT records away from a junction carry a "
        f"junction type, against at most {float(typed_elsewhere.max()):.1%} in any other "
        "province-year, and "
        f"{_range(blank_at)} of the crashes it records at a junction carry 999 for it. The junction "
        "flag reads the wrong way round there.",
    ]
    years = catalan_junction_years(coding)
    if not years.empty:
        matched = years.groupby("dgt_at_junction_matches", sort=False).year.apply(list)
        lines[0] += (
            " The Servei Català de Trànsit's file holds the same crashes with a death or serious "
            "injury within 24 hours. DGT's count of those it records at a junction in the Catalan "
            "provinces matches, within "
            f"{MATCH_TOLERANCE:.0%} of the year's crashes, the Catalan file's crashes "
            + _join(
                [
                    f"{place} in {_span(y)}" if place != "none" else f"no place in {_span(y)}"
                    for place, y in matched.items()
                ]
            )
            + "."
        )
    junction = regional[regional.field.isin(JUNCTION_FIELDS)].set_index("field")
    priority = junction.loc[[f for f in codes.PRIORI_COLUMNS if f in junction.index]]
    if "NUDO_INFO" in junction.index and not priority.empty:
        info_spread = float(
            junction.loc["NUDO_INFO"].province_spread_without_inverted_junction_years
        )
        priority_spread = float(priority.province_spread_without_inverted_junction_years.max())

        def verdict(spread: float) -> str:
            return "within" if spread <= MAX_REGIONAL_SPREAD else "beyond"

        lines[0] += (
            " In those province-years the 999 junction fields of the crashes recorded at a "
            "junction count as unrecorded, so the spreads above include them. Without those "
            "province-years the junction type's spread between provinces is "
            f"{info_spread * 100:.1f} percentage points, {verdict(info_spread)} the limit, and the "
            f"right-of-way flags' {priority_spread * 100:.1f}, {verdict(priority_spread)} it (the "
            "largest province share is "
            f"{float(priority.province_max_without_inverted_junction_years.max()):.1%})."
        )
    lines.append("")
    if not years.empty:
        shown = [
            "year",
            "severe_crashes",
            "dgt_share_at_junction",
            "cat_share_within_a_junction",
            "cat_share_within_or_near_a_junction",
            "cat_share_between_junctions",
            "dgt_at_junction_matches",
        ]
        lines += [
            "Crashes with a death or serious injury within 24 hours in the four Catalan provinces "
            "(`dgt_audit_junction_coding.csv`):",
            "",
            _md(years[shown], pct=tuple(c for c in shown if "share" in c)),
            "",
        ]
    return lines


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:] + "."


def _margin(row) -> str:
    share, limit = float(row.artefact_share_of_lift), MAX_ARTEFACT_SHARE
    side = "above" if share >= limit else "below"
    return (
        f"{row.target}: {share:.1%} (95% interval {float(row.artefact_share_low):.1%} to "
        f"{float(row.artefact_share_high):.1%}), {abs(share - limit) * 100:.1f} percentage points "
        f"{side} the {limit:.0%} limit"
    )


def _meaning(checks: pd.DataFrame, artefacts: pd.DataFrame) -> list[str]:
    """What the checks imply, worded from their results."""
    status = checks.set_index("check").passed
    file_ok = all(status[c] for c in status.index if c[:1] in "12345")
    lines = [
        "- The file checks (1-5) "
        + (
            "pass: the file is the complete published universe, so it is the right source for "
            "national counts, trends, province comparisons and descriptive shares."
            if file_ok
            else "do not all pass: national counts from it are read with the failing checks above."
        )
    ]
    if not status.get("6 comparable across regions", True):
        lines.append(
            "- Several fields are left unrecorded at very different rates in different provinces, "
            "among the crashes they apply to. A field's unrecorded share then varies with where "
            "the crash was recorded as well as with the crash; the data do not establish whether "
            "the difference lies in recording practice or in the crashes. A model trained on all "
            "of Spain would learn it."
        )
    if not status.get("7 recording artefacts do not dominate", True):
        failing = artefacts[artefacts.artefacts_dominate.astype(bool)]
        lines.append(
            "- Which fields were left unrecorded ranks the outcome on its own (check 7): "
            + "; ".join(_margin(r) for r in failing.itertuples())
            + ". A model's score on these records would partly measure how completely crashes "
            "were recorded."
        )
    lines.append(
        "- The file enters modelling only through fields validated against the Catalan file on "
        "the crashes both hold, as an external test: the Catalan model scored on crashes recorded "
        "outside Catalonia, its transfer gap always beside the target domain's native score."
        if decide(checks).startswith("DGT microdata stay")
        else "- The file passes every check and may train a model."
    )
    return lines


def document(out: dict[str, pd.DataFrame]) -> str:
    checks, regional, artefacts = (
        out["dgt_audit_checks"],
        out["dgt_audit_regional"],
        out["dgt_audit_artefacts"],
    )
    transfer = out["dgt_audit_transfer"]
    coding = out.get("dgt_audit_junction_coding")
    failing = regional[~regional.comparable_across_provinces]
    applies = regional[regional.applies_share < 1].set_index("field").applies_share
    priority = [f for f in codes.PRIORI_COLUMNS if f in applies.index]
    na_coded = [c for c in CANDIDATES if str(codes.NOT_APPLICABLE_CODE) in codes.labels_for(c)]
    present = [c for c in CANDIDATES if presence_field(c)]
    junction_names = ["NUDO_INFO", "PRIORI_*"]
    applies_text = _join(
        [
            f"{name} {float(applies[field]):.1%}"
            for field, name in (
                ("NUDO_INFO", "the junction type"),
                (priority[0] if priority else "", "the right-of-way flags"),
                ("ACERA", "the pavement field"),
                ("TRAZADO_PLANTA", "the road alignment"),
            )
            if field in applies.index
        ]
    )
    lines = [
        "# DGT microdata audit",
        "",
        "Generated by `src/dgt_stats/microdata/validation/dgt_audit.py`; every number below is "
        "computed from `data/processed/dgt_accidentes.parquet`, the Catalan file "
        "`data/processed/catalonia_severe_crashes.parquet` and the reconciliation table "
        "`reports/tables/validation.csv`. Do not edit by hand.",
        "",
        "The question: may the DGT crash microdata train a severity model in this project, or do "
        "they stay the national analytical layer (trends, province and year comparisons, "
        "exposure) and a test domain? The checks and their thresholds are declared in the "
        "module before any result is read.",
        "",
        f"**Decision: {decide(checks)}.**",
        "",
        "## What counts as unrecorded",
        "",
        'A field is unrecorded in a crash when it is 999 ("Sin especificar"), its own '
        '"unknown" code, or blank, and only in a crash the field applies to. Two kinds of cell '
        "are therefore not unrecorded:",
        "",
        '- a cell where the field does not apply, which is "not applicable" and left out of '
        'every share below: a 998 "No aplica" code, which DGT\'s dictionary gives '
        + _join(na_coded)
        + ", and a blank or 999 junction type or right-of-way flag ("
        + ", ".join(junction_names)
        + ") in a crash NUDO records away from a junction. DGT leaves the junction type blank "
        'there and, having no "not applicable" code for the right-of-way flags, mostly writes 999 '
        "in them. A recorded value counts as recorded wherever the crash is;",
        "- a blank presence field ("
        + _join(present)
        + '), which is the recorded "no" and counts as recorded. Every other condition field has '
        'a "Sin especificar" code; these record a condition only when it was present (the wind '
        'field\'s dictionary codes its absence as ".", the fog field\'s lists only "Niebla '
        'ligera" and "Niebla intensa").',
        "",
        f"Share of crashes each such field applies to: {applies_text}.",
        "",
        "## Checks on the file",
        "",
        _md(checks[["check", "criterion", "evidence", "passed"]]),
        "",
        "## Check 6: are the fields recorded alike across Spain?",
        "",
        "Share of unrecorded values (not specified, unknown or blank) per field, among the "
        "crashes it applies to; spread between "
        f"the {int(regional.provinces_compared.iloc[0])} provinces with at least "
        f"{MIN_PROVINCE_CRASHES:,} crashes. {len(failing)} of {len(regional)} fields vary by more "
        f"than {MAX_REGIONAL_SPREAD:.0%} between provinces.",
        "",
        _md(
            regional[
                [
                    "field",
                    "applies_share",
                    "unrecorded_share",
                    "unrecorded_share_catalonia",
                    "unrecorded_share_rest_of_spain",
                    "province_spread",
                    "highest_provinces",
                    "comparable_across_provinces",
                ]
            ],
            pct=(
                "applies_share",
                "unrecorded_share",
                "unrecorded_share_catalonia",
                "unrecorded_share_rest_of_spain",
                "province_spread",
            ),
        ),
        "",
        *(_junction_section(coding, regional) if coding is not None else []),
        "## Check 7: how much of a model's ranking would come from the recording itself?",
        "",
        "Two logistic regressions per universe, 5-fold cross-validation on a random sample: one "
        "sees the recorded values of every candidate field (unrecorded values kept as their own "
        "codes), the other sees only whether each field was left unrecorded where it applies. "
        "The share is the second model's lift over 0.5 as a fraction of the first's. Its 95% "
        "interval resamples the evaluated crashes with both models' out-of-fold scores held "
        "fixed; it does not cover refitting the models. The criterion, fixed in advance, is read "
        "on the share itself.",
        "",
        _md(
            artefacts,
            pct=(
                "prevalence",
                "artefact_share_of_lift",
                "artefact_share_low",
                "artefact_share_high",
            ),
            dec=("roc_auc_recorded_values", "roc_auc_unrecorded_flags_only"),
        ),
        "",
        _sentence("; ".join(_margin(r) for r in artefacts.itertuples())),
        "",
        "## The one place DGT records enter the modelling: the national transfer test",
        "",
        "The Catalan common-feature model is scored on DGT crashes outside Catalonia. These checks "
        "establish what that test measures.",
        "",
        _md(transfer[["check", "criterion", "evidence", "passed"]]),
        "",
        "## What this means",
        "",
        *_meaning(checks, artefacts),
        "",
    ]
    return "\n".join(lines)


def run(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    frame = read()
    status = statuses(frame)
    checks = file_checks(frame)
    coding = junction_coding(frame, status)
    regional = regional_recording(frame, status, coding)
    artefacts = artefact_strength(frame, status)
    comparable = bool(regional.comparable_across_provinces.all())
    checks.append(
        {
            "check": "6 comparable across regions",
            "criterion": "every candidate field's unrecorded share, among the crashes it applies "
            f"to, within {MAX_REGIONAL_SPREAD:.0%} between provinces with at least "
            f"{MIN_PROVINCE_CRASHES:,} crashes",
            "evidence": f"{int(regional.comparable_across_provinces.sum())}/{len(regional)} "
            "fields within the limit; failing: "
            + (", ".join(regional.loc[~regional.comparable_across_provinces, "field"]) or "none"),
            "passed": comparable,
        }
    )
    dominate = bool(artefacts.artefacts_dominate.any())
    checks.append(
        {
            "check": "7 recording artefacts do not dominate",
            "criterion": f"a model of unrecorded-field flags reaches under {MAX_ARTEFACT_SHARE:.0%}"
            " of the lift of a model of recorded values",
            "evidence": "; ".join(
                f"{r.target}: {r.artefact_share_of_lift:.0%} (95% interval "
                f"{r.artefact_share_low:.0%} to {r.artefact_share_high:.0%})"
                for r in artefacts.itertuples()
            ),
            "passed": not dominate,
        }
    )
    out = {
        "dgt_audit_checks": pd.DataFrame(checks),
        "dgt_audit_regional": regional,
        "dgt_audit_artefacts": artefacts,
        "dgt_audit_outcome_recording": outcome_recording(frame, status),
        "dgt_audit_junction_coding": coding,
        "dgt_audit_transfer": pd.DataFrame(transfer_checks(tables)),
    }
    out["dgt_audit_checks"]["decision"] = decide(out["dgt_audit_checks"])
    DOC.write_text(document(out), encoding="utf-8")
    return out
