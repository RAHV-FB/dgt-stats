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
   "unknown", blank) varies by no more than :data:`MAX_REGIONAL_SPREAD` between provinces with at
   least :data:`MIN_PROVINCE_CRASHES` crashes;
7. **recording artefacts do not dominate**: a model that sees only *which fields were left
   unrecorded* reaches less than :data:`MAX_ARTEFACT_SHARE` of the ranking ability (ROC-AUC above
   0.5) of a model that sees the recorded values.

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


def absence_coded(column: str) -> bool:
    """A presence field whose dictionary codes absence as '.' (CONDICION_VIENTO: '.' = no strong
    wind): a blank cell there is the recorded "no", not a missing value."""
    return "." in codes.labels_for(column)


def statuses(frame: pd.DataFrame) -> pd.DataFrame:
    """observed / not_specified / unknown / not_applicable / empty for every candidate field."""
    out = {}
    for column in CANDIDATES:
        status = codes.status(column, frame[column]).astype(str)
        if absence_coded(column):
            status = status.replace("empty", "observed")
        out[column] = status
    return pd.DataFrame(out)


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
def regional_recording(frame: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """Share of unrecorded values per field and province, summarised per field."""
    province = pd.to_numeric(frame.COD_PROVINCIA, errors="coerce").astype(int)
    sizes = province.value_counts()
    large = sizes[sizes >= MIN_PROVINCE_CRASHES].index
    names = codes.labels_for("COD_PROVINCIA")
    catalan = province.isin(harmonise.CATALAN_PROVINCES)
    rows = []
    for column in CANDIDATES:
        unrecorded = status[column].isin(UNRECORDED)
        by_province = unrecorded.groupby(province).mean().loc[large]
        top = by_province.sort_values(ascending=False)
        spread = float(by_province.max() - by_province.min())
        rows.append(
            {
                "field": column,
                "unrecorded_share": float(unrecorded.mean()),
                "unrecorded_share_catalonia": float(unrecorded[catalan].mean()),
                "unrecorded_share_rest_of_spain": float(unrecorded[~catalan].mean()),
                "province_min": float(by_province.min()),
                "province_max": float(by_province.max()),
                "province_spread": spread,
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
def _cv_auc(x: pd.DataFrame, y: np.ndarray) -> float:
    prep = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), list(x.columns))]
    )
    model = Pipeline([("prep", prep), ("model", LogisticRegression(max_iter=2000))])
    folds = StratifiedKFold(modelling.N_FOLDS, shuffle=True, random_state=modelling.SEED)
    p = cross_val_predict(model, x, y, cv=folds, method="predict_proba")[:, 1]
    return float(roc_auc_score(y, p))


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
        auc_values = _cv_auc(values, y)
        auc_flags = _cv_auc(flags, y)
        share = (auc_flags - 0.5) / (auc_values - 0.5) if auc_values > 0.5 else np.nan
        rows.append(
            {
                "universe": universe,
                "target": target_label,
                "rows": int(len(index)),
                "positives": int(y.sum()),
                "prevalence": float(y.mean()),
                "roc_auc_recorded_values": auc_values,
                "roc_auc_unrecorded_flags_only": auc_flags,
                "artefact_share_of_lift": float(share),
                "artefacts_dominate": bool(share >= MAX_ARTEFACT_SHARE),
            }
        )
    return pd.DataFrame(rows)


def outcome_recording(frame: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """Unrecorded share among fatal (30-day) and non-fatal crashes, per field and region."""
    fatal = pd.to_numeric(frame.TOTAL_MU30DF, errors="coerce").fillna(0).gt(0)
    catalan = pd.to_numeric(frame.COD_PROVINCIA, errors="coerce").isin(harmonise.CATALAN_PROVINCES)
    rows = []
    for column in CANDIDATES:
        unrecorded = status[column].isin(UNRECORDED)
        for region, mask in (("Catalonia", catalan), ("rest of Spain", ~catalan)):
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
    gap = float(national.in_domain_cv_roc_auc - national.roc_auc)
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
            "evidence": f"in-domain ROC-AUC {national.in_domain_cv_roc_auc:.3f}, transferred "
            f"{national.roc_auc:.3f} ({national.roc_auc_low:.3f}-{national.roc_auc_high:.3f}); "
            f"gap {gap:+.3f}",
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


def document(out: dict[str, pd.DataFrame]) -> str:
    checks, regional, artefacts = (
        out["dgt_audit_checks"],
        out["dgt_audit_regional"],
        out["dgt_audit_artefacts"],
    )
    transfer = out["dgt_audit_transfer"]
    failing = regional[~regional.comparable_across_provinces]
    lines = [
        "# DGT microdata audit",
        "",
        "Generated by `src/dgt_stats/microdata/validation/dgt_audit.py`; every number below is "
        "computed from `data/processed/dgt_accidentes.parquet` and the reconciliation table "
        "`reports/tables/validation.csv`. Do not edit by hand.",
        "",
        "The question: may the DGT crash microdata train a severity model in this project, or do "
        "they stay the national analytical layer (trends, province and year comparisons, "
        "exposure) and a test domain? The checks and their thresholds are declared in the "
        "module before any result is read.",
        "",
        f"**Decision: {decide(checks)}.**",
        "",
        "## Checks on the file",
        "",
        _md(checks[["check", "criterion", "evidence", "passed"]]),
        "",
        "## Check 6: are the fields recorded alike across Spain?",
        "",
        f"Share of unrecorded values (not specified, unknown or blank) per field; spread between "
        f"the {int(regional.provinces_compared.iloc[0])} provinces with at least "
        f"{MIN_PROVINCE_CRASHES:,} crashes. {len(failing)} of {len(regional)} fields vary by more "
        f"than {MAX_REGIONAL_SPREAD:.0%} between provinces.",
        "",
        _md(
            regional[
                [
                    "field",
                    "unrecorded_share",
                    "unrecorded_share_catalonia",
                    "unrecorded_share_rest_of_spain",
                    "province_spread",
                    "highest_provinces",
                    "comparable_across_provinces",
                ]
            ],
            pct=(
                "unrecorded_share",
                "unrecorded_share_catalonia",
                "unrecorded_share_rest_of_spain",
                "province_spread",
            ),
        ),
        "",
        "## Check 7: how much of a model's ranking would come from the recording itself?",
        "",
        "Two logistic regressions per universe, 5-fold cross-validation on a random sample: one "
        "sees the recorded values of every candidate field (unrecorded values kept as their own "
        "codes), the other sees only whether each field was left unrecorded. The share is the "
        "second model's lift over 0.5 as a fraction of the first's.",
        "",
        _md(
            artefacts,
            pct=("prevalence", "artefact_share_of_lift"),
            dec=("roc_auc_recorded_values", "roc_auc_unrecorded_flags_only"),
        ),
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
        "- The DGT file is complete and internally consistent (checks 1-5): it is the right "
        "source for national counts, trends and province comparisons, and for the descriptive "
        "shares the site reports.",
        "- Fields whose recording differs between provinces measure, in part, *who recorded the "
        "crash*. A model trained on all of Spain would learn that, so the file is used in "
        "modelling only through fields validated against the Catalan file on the same crashes.",
        "- The national transfer test is a test of the Catalan model on a separately recorded "
        "population with the same target and inclusion rule; its transfer gap is reported beside "
        "the in-domain reference, never alone.",
        "",
    ]
    return "\n".join(lines)


def run(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    frame = read()
    status = statuses(frame)
    checks = file_checks(frame)
    regional = regional_recording(frame, status)
    artefacts = artefact_strength(frame, status)
    comparable = bool(regional.comparable_across_provinces.all())
    checks.append(
        {
            "check": "6 comparable across regions",
            "criterion": f"every candidate field's unrecorded share within {MAX_REGIONAL_SPREAD:.0%}"
            f" between provinces with at least {MIN_PROVINCE_CRASHES:,} crashes",
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
                f"{r.target}: {r.artefact_share_of_lift:.0%}" for r in artefacts.itertuples()
            ),
            "passed": not dominate,
        }
    )
    out = {
        "dgt_audit_checks": pd.DataFrame(checks),
        "dgt_audit_regional": regional,
        "dgt_audit_artefacts": artefacts,
        "dgt_audit_outcome_recording": outcome_recording(frame, status),
        "dgt_audit_transfer": pd.DataFrame(transfer_checks(tables)),
    }
    out["dgt_audit_checks"]["decision"] = decide(out["dgt_audit_checks"])
    DOC.write_text(document(out), encoding="utf-8")
    return out
