"""Does a severity model learned in one observed domain keep its performance in another?

Every test here is on real, held-out records; nothing is extrapolated. The questions are measured,
not argued:

* **geographic** (Catalonia file): trained outside Barcelona municipality, tested on it; the
  reverse; each demarcation held out in turn; and later years in Barcelona from earlier years
  elsewhere (time and place at once).
* **cross-source** (common-feature models): the Catalan model restricted to variables the DGT
  microdata record identically (validated on the crashes both sources hold), tested on DGT crashes
  outside Catalonia, on DGT's Catalan crashes of the years the Catalan file does not have, and
  province by province; the model restricted to Barcelona's variables, tested on Barcelona's year
  where the sample allows.
* **distributions** (domain shift): how the features and the outcome differ between the domains,
  so a transfer result can be read against what changed.

Positive-class N is computed before any metric. A test set with fewer than
:data:`MIN_POSITIVES` positives or negatives gets no ROC-AUC: it is reported as insufficient,
with only its counts and calibration-in-the-large. Transferring a prediction says nothing about
cause: a model that transfers has associations that hold elsewhere, not effects.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from dgt_stats.microdata.common import wilson
from dgt_stats.microdata.ml import features, modelling
from dgt_stats.microdata.validation import harmonise

log = logging.getLogger(__name__)

MIN_POSITIVES = 30
MIN_SUBGROUP_POSITIVES = 20
N_BOOT_TRANSPORT = 500
N_THRESHOLD_FOLDS = 3
WEIGHT_CAP = 10.0
BARCELONA = "Barcelona municipality"
REST = "rest of Catalonia"
NATIONAL = "Spain outside Catalonia"
DGT_CATALONIA = "Catalonia (DGT records)"


# ----------------------------------------------------------------------------- core
def estimators_from(task: modelling.TaskResult, feature_set: str) -> dict[str, dict]:
    """The prior baseline, the logistic regression and the selected estimator, with the grid point
    each was given on the task's own validation data."""
    detail = task.detailed[feature_set]
    params = {r.estimator: r.params for r in detail["all"]}
    out = {"baseline_prior": {}, "logistic": params["logistic"]}
    out[detail["chosen"].estimator] = params[detail["chosen"].estimator]
    return out


def _threshold(table, feature_set, geography, estimator, params, train, y, weights) -> float:
    """F1-best cut from out-of-fold predictions inside the training domain only."""
    folds = StratifiedKFold(N_THRESHOLD_FOLDS, shuffle=True, random_state=modelling.SEED)
    preds = np.zeros(len(y))
    for a, b in folds.split(train, y):
        model = modelling.make_model(table, feature_set, geography, estimator, params)
        fit_kwargs = {"model__sample_weight": weights[a]} if weights is not None else {}
        model.fit(train.iloc[a], y[a], **fit_kwargs)
        preds[b] = modelling.predict(model, train.iloc[b])
    return modelling.best_threshold(y, preds)


def evaluate(
    table,
    feature_set: str,
    geography: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    estimators: dict[str, dict],
    experiment: dict,
    weights: np.ndarray | None = None,
    groups: np.ndarray | None = None,
) -> tuple[list[dict], dict]:
    """Fit on ``train``, score ``test``; rows of metrics, and the test predictions by estimator."""
    y_train = train[table.target].to_numpy()
    y_test = test[table.target].to_numpy()
    base = {
        **experiment,
        "model": table.name,
        "feature_set": feature_set,
        "train_n": len(train),
        "train_positives": int(y_train.sum()),
        "train_prevalence": float(y_train.mean()),
        "test_n": len(test),
        "test_positives": int(y_test.sum()),
        "test_prevalence": float(y_test.mean()) if len(test) else math.nan,
    }
    enough = MIN_POSITIVES <= y_test.sum() <= len(y_test) - MIN_POSITIVES
    if enough and experiment.get("in_domain_reference", True):
        base.update(in_domain_reference(table, feature_set, geography, test, estimators))
    rows, predictions = [], {}
    for estimator, params in estimators.items():
        model = modelling.make_model(table, feature_set, geography, estimator, params)
        fit_kwargs = {"model__sample_weight": weights} if weights is not None else {}
        model.fit(train, y_train, **fit_kwargs)
        p = modelling.predict(model, test)
        predictions[estimator] = p
        observed_low, observed_high = wilson(np.array([y_test.sum()]), np.array([len(y_test)]))
        row = {
            **base,
            "estimator": estimator,
            "mean_predicted": float(p.mean()),
            "observed_low": float(observed_low[0]),
            "observed_high": float(observed_high[0]),
        }
        if not enough:
            row["status"] = (
                f"insufficient positives ({int(y_test.sum())}); no discrimination metric reported"
            )
            if y_test.sum() > 0:
                ranks = pd.Series(p).rank(pct=True).to_numpy()[y_test == 1]
                row["positive_score_percentile_median"] = float(np.median(ranks))
                row["positive_score_percentile_min"] = float(ranks.min())
                row["positive_score_percentile_max"] = float(ranks.max())
            rows.append(row)
            continue
        threshold = (
            0.5
            if estimator == "baseline_prior"
            else _threshold(
                table, feature_set, geography, estimator, params, train, y_train, weights
            )
        )
        row.update(status="reported", **modelling.metrics(y_test, p, threshold))
        row.pop("n", None)
        row.pop("positives", None)
        row.pop("prevalence", None)
        if estimator != "baseline_prior":
            row.update(modelling.bootstrap_ci(y_test, p, groups, n=N_BOOT_TRANSPORT))
            row.update(modelling.calibration_fit(y_test, p))
        rows.append(row)
    return rows, predictions


def in_domain_reference(
    table, feature_set, geography, domain: pd.DataFrame, estimators: dict[str, dict]
) -> dict:
    """How well the same kind of model does when trained *inside* the test domain (5-fold CV).

    The gap between this and the transferred score is the cost of moving domains; a low in-domain
    score means the domain is hard to rank in itself, whatever the training data.
    """
    estimator = (
        next(e for e in estimators if e not in ("baseline_prior", "logistic"))
        if len(estimators) > 2
        else "logistic"
    )
    y = domain[table.target].to_numpy()
    folds = StratifiedKFold(modelling.N_FOLDS, shuffle=True, random_state=modelling.SEED)
    scores = np.zeros(len(y))
    for a, b in folds.split(domain, y):
        model = modelling.make_model(
            table, feature_set, geography, estimator, estimators[estimator]
        )
        model.fit(domain.iloc[a], y[a])
        scores[b] = modelling.predict(model, domain.iloc[b])
    return {
        "in_domain_cv_estimator": estimator,
        "in_domain_cv_roc_auc": float(roc_auc_score(y, scores)),
    }


# ----------------------------------------------------------------------------- experiments
def catalonia_geographic(task: modelling.TaskResult) -> list[dict]:
    """The full Catalonia model (no geography features) across places and time inside the file."""
    table = features.CATALONIA_TABLE
    frame = features.read(table.name).reset_index(drop=True)
    domain = np.where(frame.municipality.eq("Barcelona"), BARCELONA, REST)
    estimators = estimators_from(task, table.primary_set)
    rows = []

    def run(name, train_mask, test_mask, kind, train_desc, test_desc):
        log.info("transport %s", name)
        out, _ = evaluate(
            table,
            table.primary_set,
            "none",
            frame[train_mask],
            frame[test_mask],
            estimators,
            {
                "experiment": name,
                "evidence_level": kind,
                "train_domain": train_desc,
                "test_domain": test_desc,
            },
        )
        rows.extend(out)

    years = sorted(int(y) for y in frame.year.unique())
    run(
        "rest of Catalonia -> Barcelona municipality",
        domain == REST,
        domain == BARCELONA,
        "3 geographic",
        f"{REST}, {years[0]}-{years[-1]}",
        f"{BARCELONA}, {years[0]}-{years[-1]}",
    )
    run(
        "Barcelona municipality -> rest of Catalonia",
        domain == BARCELONA,
        domain == REST,
        "3 geographic",
        f"{BARCELONA}, {years[0]}-{years[-1]}",
        f"{REST}, {years[0]}-{years[-1]}",
    )
    for demarcation in sorted(frame.demarcation.unique()):
        held = frame.demarcation.eq(demarcation)
        run(
            f"leave out {demarcation} demarcation",
            ~held,
            held,
            "3 geographic",
            "the other three demarcations",
            f"{demarcation} demarcation",
        )
    # Time and place at once: the earliest split that leaves enough later Barcelona fatal crashes.
    for split in years[::-1]:
        later = (domain == BARCELONA) & (frame.year > split)
        if frame.loc[later, table.target].sum() >= 2 * MIN_POSITIVES:
            break
    run(
        f"rest of Catalonia to {split} -> Barcelona municipality after {split}",
        (domain == REST) & (frame.year <= split),
        (domain == BARCELONA) & (frame.year > split),
        "2+3 temporal and geographic",
        f"{REST}, {years[0]}-{split}",
        f"{BARCELONA}, {split + 1}-{years[-1]}",
    )
    return rows


def common_dgt(task: modelling.TaskResult) -> tuple[list[dict], pd.DataFrame, pd.DataFrame]:
    """The DGT-common Catalan model on DGT crash records: same crashes, new crashes, all Spain."""
    table = next(t for t in features.common_tables() if t.name == "catalonia_common_dgt")
    cat = features.read(table.name).reset_index(drop=True)
    dgt = harmonise.read(harmonise.DGT_COMMON_PATH).reset_index(drop=True)
    columns = table.columns("common", "none")
    for column in columns:
        kind = next(f.kind for f in table.catalogue if f.column == column)
        if kind == "categorical":
            dgt[column] = dgt[column].astype(str)
    estimators = estimators_from(task, "common")
    rows: list[dict] = []
    cat_years = sorted(cat.year.unique())
    dgt_first = int(dgt.year.min())
    first_block = [y for y in cat_years if y < dgt_first]
    overlap = [y for y in cat_years if y >= dgt_first]

    def run(name, train, test, kind, train_desc, test_desc, weights=None):
        log.info("transport %s", name)
        out, preds = evaluate(
            table,
            "common",
            "none",
            train,
            test,
            estimators,
            {
                "experiment": name,
                "evidence_level": kind,
                "train_domain": train_desc,
                "test_domain": test_desc,
            },
            weights=weights,
        )
        rows.extend(out)
        return preds

    # Another Catalan region, with only the DGT-common features (stage 3 of the outward path).
    for demarcation in sorted(cat.demarcation.unique()):
        held = cat.demarcation.eq(demarcation)
        run(
            f"leave out {demarcation} demarcation (DGT-common features)",
            cat[~held],
            cat[held],
            "3 geographic",
            "the other three demarcations",
            f"{demarcation} demarcation",
        )
    early = cat[cat.year.isin(first_block)]
    run(
        "same crashes, two sources: Catalan file",
        early,
        cat[cat.year.isin(overlap)],
        "2 temporal (source check)",
        f"Catalan file {first_block[0]}-{first_block[-1]}",
        f"Catalan file {overlap[0]}-{overlap[-1]}",
    )
    run(
        "same crashes, two sources: DGT records",
        early,
        dgt[dgt.domain.eq(DGT_CATALONIA) & dgt.year.isin(overlap)],
        "4 cross-source (same crashes)",
        f"Catalan file {first_block[0]}-{first_block[-1]}",
        f"DGT microdata, Catalan provinces {overlap[0]}-{overlap[-1]}",
    )
    later = sorted(set(dgt.year) - set(cat_years))
    if later:
        run(
            "Catalonia, a year the Catalan file does not have (DGT records)",
            cat,
            dgt[dgt.domain.eq(DGT_CATALONIA) & dgt.year.isin(later)],
            "2+4 temporal and cross-source",
            f"Catalan file {cat_years[0]}-{cat_years[-1]}",
            f"DGT microdata, Catalan provinces {later[0]}-{later[-1]}",
        )
    national = dgt[dgt.domain.eq(NATIONAL)].reset_index(drop=True)
    preds = run(
        "Catalonia -> Spain outside Catalonia",
        cat,
        national,
        "3+4 geographic and cross-source (national crash-level)",
        f"Catalan file {cat_years[0]}-{cat_years[-1]}",
        f"DGT microdata outside Catalonia {national.year.min()}-{national.year.max()}",
    )
    run(
        "Catalonia early years -> Spain outside Catalonia later",
        early,
        national,
        "2+3+4 temporal, geographic and cross-source",
        f"Catalan file {first_block[0]}-{first_block[-1]}",
        f"DGT microdata outside Catalonia {national.year.min()}-{national.year.max()}",
    )
    provinces = by_province(national, preds, task.detailed["common"]["chosen"].estimator)
    # Sensitivity: reweight the Catalan training crashes to the national mix of the shared
    # variables zone x crash type, capped. Not a national model: a check on how much the
    # difference in mix moves the transfer result.
    weights, weight_table = reweight(cat, national, ["dgt_zone", "dgt_crash_type"])
    run(
        "Catalonia reweighted to the national zone x crash-type mix -> Spain outside Catalonia",
        cat,
        national,
        "sensitivity (reweighting)",
        f"Catalan file {cat_years[0]}-{cat_years[-1]}, weighted (cap {WEIGHT_CAP:g})",
        f"DGT microdata outside Catalonia {national.year.min()}-{national.year.max()}",
        weights=weights,
    )
    return rows, provinces, weight_table


def by_province(
    test: pd.DataFrame, predictions: dict[str, np.ndarray], estimator: str
) -> pd.DataFrame:
    p = predictions[estimator]
    rows = []
    for province, idx in test.groupby("province_code").indices.items():
        y = test.fatal.to_numpy()[idx]
        pp = p[idx]
        enough = MIN_POSITIVES <= y.sum() <= len(y) - MIN_POSITIVES
        rows.append(
            {
                "province_code": int(province),
                "n": len(idx),
                "positives": int(y.sum()),
                "prevalence": float(y.mean()),
                "mean_predicted": float(pp.mean()),
                "roc_auc": float(roc_auc_score(y, pp)) if enough else math.nan,
                "reported": bool(enough),
            }
        )
    return pd.DataFrame(rows).sort_values("province_code")


def reweight(train: pd.DataFrame, target: pd.DataFrame, columns: list[str]):
    """Weights making the training mix of ``columns`` match the target's, capped at WEIGHT_CAP."""
    key_train = train[columns].astype(str).agg(" | ".join, axis=1)
    key_target = target[columns].astype(str).agg(" | ".join, axis=1)
    p_train = key_train.value_counts(normalize=True)
    p_target = key_target.value_counts(normalize=True)
    ratio = (p_target / p_train).reindex(p_train.index).fillna(0.0)
    weights = key_train.map(ratio).clip(upper=WEIGHT_CAP).to_numpy()
    weights = weights * len(weights) / weights.sum()
    table = pd.DataFrame(
        {
            "cell": p_train.index,
            "train_share": p_train.values,
            "target_share": p_target.reindex(p_train.index).fillna(0).values,
            "raw_weight": ratio.values,
        }
    )
    table["capped"] = table.raw_weight > WEIGHT_CAP
    weighted = pd.Series(weights).groupby(key_train.values).sum() / weights.sum()
    table["weighted_train_share"] = table.cell.map(weighted).fillna(0).values
    missing = sorted(set(p_target.index) - set(p_train.index))
    table.attrs["target_cells_absent_from_training"] = missing
    return weights, table.sort_values("target_share", ascending=False)


def common_bcn(task: modelling.TaskResult) -> list[dict]:
    """The Barcelona-common Catalan model: Barcelona municipality in the file, then Barcelona's own year."""
    table = next(t for t in features.common_tables() if t.name == "catalonia_common_bcn")
    cat = features.read(table.name).reset_index(drop=True)
    bcn = harmonise.read(harmonise.BCN_COMMON_PATH).reset_index(drop=True)
    for f in table.catalogue:
        if f.kind == "categorical":
            bcn[f.column] = bcn[f.column].astype(str)
    estimators = estimators_from(task, "common")
    rows: list[dict] = []
    years = sorted(cat.year.unique())
    bcn_year = "-".join(str(y) for y in sorted(set(bcn.year.astype(int))))
    for name, train, test, kind, train_desc, test_desc in (
        (
            "rest of Catalonia -> Barcelona municipality (Barcelona-common features)",
            cat[cat.domain.eq(REST)],
            cat[cat.domain.eq(BARCELONA)],
            "3 geographic",
            f"{REST}, {years[0]}-{years[-1]}",
            f"{BARCELONA}, {years[0]}-{years[-1]}",
        ),
        (
            f"Catalonia -> Barcelona {bcn_year} (Guàrdia Urbana, serious or fatal crashes)",
            cat,
            bcn,
            "2+4 temporal and cross-source",
            f"Catalan file {years[0]}-{years[-1]}",
            f"Barcelona {bcn_year} crashes with a death or serious injury",
        ),
    ):
        log.info("transport %s", name)
        out, _ = evaluate(
            table,
            "common",
            "none",
            train,
            test,
            estimators,
            {
                "experiment": name,
                "evidence_level": kind,
                "train_domain": train_desc,
                "test_domain": test_desc,
            },
        )
        rows.extend(out)
    return rows


def reference_rows(task: modelling.TaskResult, geography: str) -> list[dict]:
    """The task's own temporal holdout, in the same layout, for comparison, with the in-domain
    reference computed inside the test year."""
    table = task.table
    frame = features.read(table.name).reset_index(drop=True)
    reference = in_domain_reference(
        table,
        table.primary_set,
        geography,
        frame.iloc[task.split.test],
        estimators_from(task, table.primary_set),
    )
    rows = []
    for v in task.variants:
        if v.feature_set != table.primary_set or v.geography != geography:
            continue
        rows.append(
            {
                "experiment": f"temporal holdout ({task.split.description})",
                "evidence_level": "2 temporal",
                "train_domain": "all of Catalonia, earlier years",
                "test_domain": "all of Catalonia, last year",
                "model": table.name,
                "feature_set": table.primary_set,
                "estimator": v.estimator,
                "train_n": int(v.train_fit["n"]),
                "train_positives": int(v.train_fit["positives"]),
                "train_prevalence": v.train_fit["prevalence"],
                "test_n": v.test["n"],
                "test_positives": v.test["positives"],
                "test_prevalence": v.test["prevalence"],
                "status": "reported",
                **{
                    k: val for k, val in v.test.items() if k not in ("n", "positives", "prevalence")
                },
                **reference,
            }
        )
    return rows


# ----------------------------------------------------------------------------- distributions
def shift_metrics(
    a: pd.DataFrame,
    b: pd.DataFrame,
    columns: dict[str, str],
    comparison: str,
    a_label: str,
    b_label: str,
) -> pd.DataFrame:
    """Per feature: Jensen-Shannon divergence and PSI for categories, standardised difference for
    numbers, and the level whose share differs most."""
    rows = []
    for column, kind in columns.items():
        row = {
            "comparison": comparison,
            "domain_a": a_label,
            "domain_b": b_label,
            "feature": column,
            "kind": kind,
            "n_a": len(a),
            "n_b": len(b),
        }
        if kind == "categorical":
            pa = a[column].astype(str).value_counts(normalize=True)
            pb = b[column].astype(str).value_counts(normalize=True)
            index = pa.index.union(pb.index)
            pa, pb = pa.reindex(index, fill_value=0.0), pb.reindex(index, fill_value=0.0)
            eps = 1e-4
            psi = float(np.sum((pa - pb) * np.log((pa + eps) / (pb + eps))))
            diff = pa - pb
            level = diff.abs().idxmax()
            row.update(
                jsd=harmonise.jensen_shannon(a[column], b[column]),
                psi=psi,
                largest_difference_level=str(level),
                share_a=float(pa[level]),
                share_b=float(pb[level]),
                share_difference=float(diff[level]),
            )
        else:
            xa, xb = a[column].astype(float), b[column].astype(float)
            pooled = math.sqrt((xa.var() + xb.var()) / 2) or float("nan")
            row.update(
                mean_a=float(xa.mean()),
                mean_b=float(xb.mean()),
                standardised_difference=float((xa.mean() - xb.mean()) / pooled),
                missing_a=float(xa.isna().mean()),
                missing_b=float(xb.isna().mean()),
            )
        rows.append(row)
    return pd.DataFrame(rows)


def outcome_row(
    a: pd.DataFrame,
    b: pd.DataFrame,
    comparison: str,
    a_label: str,
    b_label: str,
    target: str = "fatal",
) -> dict:
    ka, na, kb, nb = int(a[target].sum()), len(a), int(b[target].sum()), len(b)
    (la, ha), (lb, hb) = [wilson(np.array([k]), np.array([n])) for k, n in ((ka, na), (kb, nb))]
    return {
        "comparison": comparison,
        "domain_a": a_label,
        "domain_b": b_label,
        "feature": f"outcome: {target}",
        "kind": "outcome",
        "n_a": na,
        "n_b": nb,
        "share_a": ka / na,
        "share_b": kb / nb,
        "share_difference": ka / na - kb / nb,
        "share_a_low": float(la[0]),
        "share_a_high": float(ha[0]),
        "share_b_low": float(lb[0]),
        "share_b_high": float(hb[0]),
    }


def domain_shift() -> pd.DataFrame:
    table = features.CATALONIA_TABLE
    cat = features.read(table.name)
    context = {f.column: f.kind for f in table.features("context", "none")}
    context.update(
        {
            c: "categorical"
            for c in (
                "D_TRACAT_ALTIMETRIC",
                "D_CARACT_ENTORN",
                "D_SENTITS_VIA",
                "D_CARRIL_ESPECIAL",
            )
        }
    )
    frames = []
    bcn_mask = cat.municipality.eq("Barcelona")
    pairs = [
        (
            "Barcelona municipality vs rest of Catalonia (Catalan file)",
            cat[bcn_mask],
            cat[~bcn_mask],
            BARCELONA,
            REST,
        )
    ]
    for demarcation in sorted(cat.demarcation.unique()):
        held = cat.demarcation.eq(demarcation)
        pairs.append(
            (
                f"{demarcation} demarcation vs the other three (Catalan file)",
                cat[held],
                cat[~held],
                demarcation,
                "other demarcations",
            )
        )
    for comparison, a, b, la, lb in pairs:
        frames.append(shift_metrics(a, b, context, comparison, la, lb))
        frames.append(pd.DataFrame([outcome_row(a, b, comparison, la, lb)]))

    dgt_table = next(t for t in features.common_tables() if t.name == "catalonia_common_dgt")
    common = features.read(dgt_table.name)
    dgt = harmonise.read(harmonise.DGT_COMMON_PATH)
    dgt_columns = {f.column: f.kind for f in dgt_table.catalogue}
    for c, k in dgt_columns.items():
        if k == "categorical":
            dgt[c] = dgt[c].astype(str)
    overlap = sorted(set(common.year) & set(dgt.year))
    for comparison, a, b, la, lb in (
        (
            "Spain outside Catalonia (DGT) vs Catalonia (Catalan file), shared years",
            dgt[dgt.domain.eq(NATIONAL) & dgt.year.isin(overlap)],
            common[common.year.isin(overlap)],
            NATIONAL,
            "Catalonia",
        ),
        (
            "Catalonia: DGT records vs Catalan file, same crashes (mapping check)",
            dgt[dgt.domain.eq(DGT_CATALONIA) & dgt.year.isin(overlap)],
            common[common.year.isin(overlap)],
            DGT_CATALONIA,
            "Catalan file",
        ),
        (
            "Barcelona city (DGT, 08019) vs Spain outside Catalonia (DGT)",
            dgt[dgt.municipality_code.eq("08019")],
            dgt[dgt.domain.eq(NATIONAL)],
            "Barcelona city (DGT)",
            NATIONAL,
        ),
    ):
        frames.append(shift_metrics(a, b, dgt_columns, comparison, la, lb))
        frames.append(pd.DataFrame([outcome_row(a, b, comparison, la, lb)]))

    bcn_table = next(t for t in features.common_tables() if t.name == "catalonia_common_bcn")
    bcn_common = features.read(bcn_table.name)
    bcn = harmonise.read(harmonise.BCN_COMMON_PATH)
    bcn_columns = {f.column: f.kind for f in bcn_table.catalogue}
    a = bcn
    b = bcn_common[bcn_common.domain.eq(BARCELONA)]
    bcn_label = "Barcelona " + "-".join(str(y) for y in sorted(set(a.year.astype(int))))
    comparison = f"{bcn_label} (Guàrdia Urbana) vs Barcelona municipality in the Catalan file"
    frames.append(
        shift_metrics(
            a,
            b,
            bcn_columns,
            comparison,
            bcn_label,
            f"{BARCELONA} {b.year.min()}-{b.year.max()}",
        )
    )
    frames.append(
        pd.DataFrame(
            [outcome_row(a, b, comparison, bcn_label, f"{BARCELONA} {b.year.min()}-{b.year.max()}")]
        )
    )
    return pd.concat(frames, ignore_index=True)


# ----------------------------------------------------------------------------- Barcelona people
def person_subgroups(task: modelling.TaskResult) -> pd.DataFrame:
    """Where the person model ranks well and where it does not, from grouped out-of-fold scores.

    Each person's score comes from a model that never saw their crash (5 folds grouped by
    ``Numero_expedient`` over the whole year), so every person in the year is scored once.
    """
    table = task.table
    frame = features.read(table.name).reset_index(drop=True)
    chosen = task.detailed[table.primary_set]["chosen"]
    y = frame[table.target].to_numpy()
    groups = frame[table.group_column].to_numpy()
    folds = modelling.StratifiedGroupKFold(
        modelling.N_FOLDS, shuffle=True, random_state=modelling.SEED
    )
    scores = np.zeros(len(frame))
    for a, b in folds.split(frame, y, groups):
        if set(groups[a]) & set(groups[b]):
            raise AssertionError("a crash appears on both sides of a fold")
        model = modelling.make_model(
            table, chosen.feature_set, chosen.geography, chosen.estimator, chosen.params
        )
        model.fit(frame.iloc[a], y[a])
        scores[b] = modelling.predict(model, frame.iloc[b])
    people = features.barcelona.read_people()[["person_record_id", "age_band"]]
    frame = frame.merge(people, on="person_record_id", how="left", validate="one_to_one")
    threshold = chosen.threshold
    rows = []
    dimensions = {
        "all": None,
        "role": "person_role",
        "associated vehicle": "associated_vehicle_group",
        "age band": "age_band",
        "sex": "sex",
        "district": "district",
    }
    for dimension, column in dimensions.items():
        groups_of = (
            [("all", np.ones(len(frame), bool))]
            if column is None
            else [
                (str(level), frame[column].astype(str).eq(level).to_numpy())
                for level in sorted(frame[column].astype(str).unique())
            ]
        )
        for level, mask in groups_of:
            yy, pp = y[mask], scores[mask]
            positives = int(yy.sum())
            enough = MIN_SUBGROUP_POSITIVES <= positives <= len(yy) - MIN_SUBGROUP_POSITIVES
            predicted = pp >= threshold
            rows.append(
                {
                    "dimension": dimension,
                    "level": level,
                    "n": int(mask.sum()),
                    "positives": positives,
                    "observed": float(yy.mean()),
                    "mean_predicted": float(pp.mean()),
                    "brier": float(np.mean((pp - yy) ** 2)),
                    "roc_auc": float(roc_auc_score(yy, pp)) if enough else math.nan,
                    "recall_at_threshold": float(predicted[yy == 1].mean())
                    if positives
                    else math.nan,
                    "flagged_share": float(predicted.mean()),
                    "auc_reported": bool(enough),
                }
            )
    return pd.DataFrame(rows)


def leave_one_district_out(task: modelling.TaskResult) -> list[dict]:
    """Each Barcelona district scored by a model trained on the other nine (pooled scores).

    Districts hold too few serious or fatal cases for a score each, so the out-of-district scores
    are pooled and compared with grouped cross-validation over the same rows. The model uses no
    geography feature, so a district is genuinely new to it.
    """
    table = task.table
    frame = features.read(table.name).reset_index(drop=True)
    chosen = task.detailed[table.primary_set]["chosen"]
    y = frame[table.target].to_numpy()
    district = frame["district"].astype(str).to_numpy()
    scores = np.zeros(len(frame))
    per_district = []
    for name in sorted(set(district)):
        held = district == name
        model = modelling.make_model(
            table, chosen.feature_set, "none", chosen.estimator, chosen.params
        )
        model.fit(frame[~held], y[~held])
        scores[held] = modelling.predict(model, frame[held])
        per_district.append((name, int(held.sum()), int(y[held].sum())))
    groups = frame[table.group_column or table.id_column].to_numpy()
    folds = modelling.StratifiedGroupKFold(
        modelling.N_FOLDS, shuffle=True, random_state=modelling.SEED
    )
    cv = np.zeros(len(frame))
    for a, b in folds.split(frame, y, groups):
        model = modelling.make_model(
            table, chosen.feature_set, "none", chosen.estimator, chosen.params
        )
        model.fit(frame.iloc[a], y[a])
        cv[b] = modelling.predict(model, frame.iloc[b])
    smallest = min(per_district, key=lambda item: item[2])
    rows = []
    for name, preds, kind in (
        ("leave one district out (pooled out-of-district scores)", scores, "3 geographic"),
        ("grouped 5-fold cross-validation, same rows (reference)", cv, "1 internal"),
    ):
        rows.append(
            {
                "experiment": name,
                "evidence_level": kind,
                "model": table.name,
                "feature_set": chosen.feature_set,
                "estimator": chosen.estimator,
                "train_domain": "nine districts"
                if kind.startswith("3")
                else "four fifths of crashes",
                "test_domain": "the held-out district" if kind.startswith("3") else "one fifth",
                "test_n": len(frame),
                "test_positives": int(y.sum()),
                "test_prevalence": float(y.mean()),
                "status": "reported",
                "districts": len(per_district),
                "smallest_district_positives": f"{smallest[0]}: {smallest[2]}",
                **{
                    k: v
                    for k, v in modelling.metrics(y, preds).items()
                    if k not in ("n", "positives", "prevalence")
                },
                **modelling.bootstrap_ci(y, preds, groups, n=N_BOOT_TRANSPORT),
                **modelling.calibration_fit(y, preds),
            }
        )
    # The grouped cross-validation is the in-domain reference of the district hold-out.
    rows[0]["in_domain_cv_estimator"] = chosen.estimator
    rows[0]["in_domain_cv_roc_auc"] = rows[1]["roc_auc"]
    return rows


# ----------------------------------------------------------------------------- calculator
CALCULATOR = "calculator"


def calculator_tests() -> pd.DataFrame:
    """The published calculator's model (:mod:`dgt_stats.severity_model`) on crashes it was not
    fitted on, with the same rule as every other test here.

    The specification, the crashes (every road a reader can choose; the road-owner artefact
    roads are left out) and the penalty are the calculator's own. Each held-out test sits beside
    the same specification fitted and cross-validated inside the test population (5 folds), and
    beside the table of fatal shares by road and crash type fitted on the same training crashes.
    A province left out has no intercept of its own to learn, so those tests use the
    specification without province intercepts; the other tests use the published one. No test
    uses another source: no other file records the calculator's inputs (DGT's records lack the
    road's owning network and the posted limit, and their road-type coding disagrees with the
    Catalan file's on the same crashes).
    """
    from dgt_stats import severity_model as sev

    frame, years, y = sev.load()
    scenarios = sev.scenarios_from_records(frame)
    c = sev.chosen_penalty()
    designs = {
        True: (sev.design_columns(), None),
        False: (sev.design_columns(provinces=False), None),
    }
    designs = {
        key: (columns, sev.design_matrix(scenarios, columns))
        for key, (columns, _) in designs.items()
    }
    city = (frame.municipality == "Barcelona").to_numpy()
    first, last = int(years.min()), int(years.max())
    rolling = sev.ROLLING_TEST_YEARS

    def fitted(train: np.ndarray, test: np.ndarray, provinces: bool) -> np.ndarray:
        columns, x = designs[provinces]
        model = sev.fit_logistic(x[train], y[train], c, columns)
        return sev.expit(x[test] @ model.coef)

    def cross_validated(domain: np.ndarray, provinces: bool) -> np.ndarray:
        index = np.flatnonzero(domain)
        folds = StratifiedKFold(modelling.N_FOLDS, shuffle=True, random_state=modelling.SEED)
        out = np.zeros(len(index))
        for a, b in folds.split(index, y[index]):
            train = np.zeros(len(y), dtype=bool)
            test = np.zeros(len(y), dtype=bool)
            train[index[a]], test[index[b]] = True, True
            out[b] = fitted(train, test, provinces)
        return out

    rows = []

    def row(experiment, kind, train_desc, test_desc, train, test, p, table, reference=None):
        yt = y[test]
        low, high = wilson(np.array([yt.sum()]), np.array([len(yt)]))
        out = {
            "experiment": experiment,
            "evidence_level": kind,
            "model": CALCULATOR,
            "feature_set": "calculator inputs",
            "estimator": "logistic",
            "train_domain": train_desc,
            "test_domain": test_desc,
            "train_n": int(train.sum()) if train is not None else math.nan,
            "train_positives": int(y[train].sum()) if train is not None else math.nan,
            "test_n": int(test.sum()),
            "test_positives": int(yt.sum()),
            "test_prevalence": float(yt.mean()),
            "mean_predicted": float(p.mean()),
            "observed_low": float(low[0]),
            "observed_high": float(high[0]),
            "status": "reported",
            "roc_auc": float(roc_auc_score(yt, p)),
            **modelling.bootstrap_ci(yt, p, None, n=N_BOOT_TRANSPORT),
            **modelling.calibration_fit(yt, p),
            "table_roc_auc": float(roc_auc_score(yt, table)) if table is not None else math.nan,
            "in_domain_cv_estimator": "logistic" if reference is not None else None,
            "in_domain_cv_roc_auc": float(roc_auc_score(yt, reference))
            if reference is not None
            else math.nan,
        }
        rows.append(out)

    everything = np.ones(len(y), dtype=bool)
    log.info("calculator: random cross-validation")
    row(
        f"random 5-fold cross-validation {first}-{last}",
        "1 internal",
        f"four fifths of {first}-{last}",
        "one fifth",
        None,
        everything,
        cross_validated(everything, True),
        None,
    )
    log.info("calculator: rolling origin")
    tested = np.isin(years, rolling)
    p_rolling, t_rolling = np.zeros(len(y)), np.zeros(len(y))
    for year in rolling:
        train, test = years < year, years == year
        p_rolling[test] = fitted(train, test, True)
        t_rolling[test] = sev._table(scenarios[train], y[train], scenarios[test])
    row(
        f"rolling origin: each year {rolling[0]}-{rolling[-1]} from the years before it",
        "2 temporal",
        f"{first} to the year before each test year",
        f"{rolling[0]}-{rolling[-1]}",
        None,
        tested,
        p_rolling[tested],
        t_rolling[tested],
    )

    def held_out(experiment, kind, train_desc, test_desc, train, test, provinces):
        log.info("calculator: %s", experiment)
        row(
            experiment,
            kind,
            train_desc,
            test_desc,
            train,
            test,
            fitted(train, test, provinces),
            sev._table(scenarios[train], y[train], scenarios[test]),
            cross_validated(test, provinces),
        )

    held_out(
        f"temporal holdout: train {first}-{last - 1}, test {last}",
        "2 temporal",
        f"{first}-{last - 1}",
        str(last),
        years < last,
        years == last,
        True,
    )
    for name in sorted(frame.demarcation.astype(str).unique()):
        test = (frame.demarcation.astype(str) == name).to_numpy()
        held_out(
            f"leave out {name} demarcation",
            "3 geographic",
            "the other three demarcations",
            f"{name} demarcation",
            ~test,
            test,
            False,
        )
    held_out(
        "rest of Catalonia -> Barcelona municipality",
        "3 geographic",
        REST,
        BARCELONA,
        ~city,
        city,
        True,
    )
    out = pd.DataFrame(rows)
    out["in_domain_train_n"] = (out.test_n * (modelling.N_FOLDS - 1)) // modelling.N_FOLDS
    out.loc[out.in_domain_cv_roc_auc.isna(), "in_domain_train_n"] = np.nan
    out["transfer_gap"] = out.roc_auc - out.in_domain_cv_roc_auc
    return out


# ----------------------------------------------------------------------------- driver
def run(results: dict[str, modelling.TaskResult]) -> dict[str, pd.DataFrame]:
    cat_task = results["catalonia_crash_severity"]
    geographic = catalonia_geographic(cat_task)
    reference = reference_rows(cat_task, "none")
    dgt_rows, provinces, weights = common_dgt(results["catalonia_common_dgt"])
    bcn_rows = common_bcn(results["catalonia_common_bcn"])
    common_reference = reference_rows(results["catalonia_common_dgt"], "none") + reference_rows(
        results["catalonia_common_bcn"], "none"
    )
    districts = leave_one_district_out(
        results["barcelona_person_severity"]
    ) + leave_one_district_out(results["barcelona_crash_severity"])
    validation = pd.DataFrame(
        reference + geographic + common_reference + dgt_rows + bcn_rows + districts
    )
    # The transfer gap: the transferred score minus the target domain's native (in-domain)
    # reference, so a negative gap is ranking lost in the move. The in-domain model trains on four
    # fifths of the test domain, so a positive gap can mean the larger foreign training set
    # outweighs the change of domain. The prior-only baseline has no gap.
    validation["in_domain_train_n"] = (validation.test_n * (modelling.N_FOLDS - 1)) // (
        modelling.N_FOLDS
    )
    validation.loc[validation.in_domain_cv_roc_auc.isna(), "in_domain_train_n"] = np.nan
    validation["transfer_gap"] = (validation.roc_auc - validation.in_domain_cv_roc_auc).where(
        validation.estimator.ne("baseline_prior")
    )
    return {
        "ml_transport_validation": validation,
        "ml_transport_provinces": provinces,
        "ml_transport_reweighting": weights,
        "ml_domain_shift": domain_shift(),
        "ml_subgroup_validation": person_subgroups(results["barcelona_person_severity"]),
        "ml_common_features": harmonise.catalogue_frame(),
        "ml_common_feature_validation": harmonise.validate_dgt(),
    }
