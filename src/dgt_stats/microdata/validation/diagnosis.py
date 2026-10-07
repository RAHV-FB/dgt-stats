"""Why does the Catalan severity model rank Barcelona's crashes less well? Measured, not argued.

Everything here uses the Catalan file only (one row = one crash with a death or serious injury,
2010-2023); the domains are Barcelona municipality and the rest of Catalonia, as in
:mod:`transport`. Every score is a ROC-AUC on real held-out crashes.

**Decomposition.** Moving the model from the rest of Catalonia to Barcelona can lose ranking
ability for four different reasons, and each has its own measurement:

* *feature loss*: the Barcelona-common feature set (what Guàrdia Urbana's files also record) is
  poorer than the full Catalan set; measured inside one domain, same rows, two feature sets;
* *training size*: Barcelona has about one crash in eight, so a model trained inside it sees
  fewer rows; measured by training on the rest of Catalonia with the training folds cut to
  Barcelona's size (:data:`SIZE_REPEATS` random cuts, averaged);
* *intrinsic difficulty*: Barcelona's crashes may simply be harder to rank with these variables,
  whatever the training data; measured as the matched-size score in the rest of Catalonia (and in
  its urban crashes) against the score inside Barcelona;
* *transport failure*: the associations learned elsewhere may not hold in Barcelona; measured as
  Barcelona's in-domain score against the transferred score, on the same Barcelona crashes.

These telescope exactly: rest in-domain minus rest-to-Barcelona = training-size cost + intrinsic
difference + transport gap. Differences on the same rows get paired bootstrap intervals; the
intrinsic difference compares two sets of crashes and gets independent ones.

**Domain-specific against pooled.** For each target domain (Barcelona, the rest of Catalonia,
urban crashes, interurban crashes) the target domain is split into five folds and four kinds of
model score the same held-out crashes: trained only inside the domain, only on the other domain,
on both pooled, and pooled with a flag for the domain. For Barcelona and the rest of Catalonia a
fifth, the pooled model on the Barcelona-common features, is the "universal" model the
cross-source tests use.
"""

from __future__ import annotations

import dataclasses
import logging

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split

from dgt_stats.microdata.ml import features, modelling
from dgt_stats.microdata.ml.features import Feature
from dgt_stats.microdata.validation import transport

log = logging.getLogger(__name__)

SIZE_REPEATS = 3
N_BOOT_DIAGNOSIS = 500
FLAG = "in_target_domain"
URBAN = "urban crashes"
INTERURBAN = "interurban crashes"


# ----------------------------------------------------------------------------- data
@dataclasses.dataclass
class Setting:
    """One feature table with the estimators chosen for it on its own validation data."""

    label: str
    table: features.FeatureTable
    feature_set: str
    frame: pd.DataFrame
    estimators: dict[str, dict]


def settings(
    results: dict[str, modelling.TaskResult],
) -> tuple[Setting, Setting, pd.Series, pd.Series]:
    """The full and Barcelona-common settings on aligned rows, the domain and the zone."""
    full_table = features.CATALONIA_TABLE
    full = features.read(full_table.name).reset_index(drop=True)
    common_table = next(t for t in features.common_tables() if t.name == "catalonia_common_bcn")
    common = features.read(common_table.name).reset_index(drop=True)
    zone = features.read("catalonia_common_dgt").reset_index(drop=True)
    for other in (common, zone):
        if not np.array_equal(other.cat_crash_id.to_numpy(), full.cat_crash_id.to_numpy()):
            raise ValueError("Catalan feature tables are not row-aligned on cat_crash_id")
    domain = pd.Series(
        np.where(full.municipality.eq("Barcelona"), transport.BARCELONA, transport.REST)
    )
    if not domain.eq(common.domain).all():
        raise ValueError("domain coding differs between the Catalan feature tables")
    zone_label = zone.dgt_zone.map({"urban": URBAN, "interurban": INTERURBAN})

    def chosen(task: modelling.TaskResult, feature_set: str) -> dict[str, dict]:
        out = transport.estimators_from(task, feature_set)
        out.pop("baseline_prior")
        return out

    return (
        Setting(
            "full Catalan context features",
            full_table,
            full_table.primary_set,
            full,
            chosen(results[full_table.name], full_table.primary_set),
        ),
        Setting(
            "Barcelona-common features",
            common_table,
            "common",
            common,
            chosen(results[common_table.name], "common"),
        ),
        domain,
        zone_label,
    )


def _fit_predict(
    s: Setting, estimator: str, train: np.ndarray, test: np.ndarray, table=None, frame=None
) -> np.ndarray:
    table = table or s.table
    frame = s.frame if frame is None else frame
    y = frame[table.target].to_numpy()
    model = modelling.make_model(table, s.feature_set, "none", estimator, s.estimators[estimator])
    model.fit(frame.iloc[train], y[train])
    return modelling.predict(model, frame.iloc[test])


def _folds(y: np.ndarray, rows: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Five stratified folds of ``rows`` (positions in the full frame)."""
    folds = StratifiedKFold(modelling.N_FOLDS, shuffle=True, random_state=modelling.SEED)
    return [(rows[a], rows[b]) for a, b in folds.split(rows, y[rows])]


def in_domain(
    s: Setting, estimator: str, rows: np.ndarray, size: int | None = None, seed: int = 0
) -> np.ndarray:
    """Out-of-fold predictions for ``rows`` from models trained inside them; with ``size``, each
    training fold is cut (stratified) to that many crashes."""
    y = s.frame[s.table.target].to_numpy()
    out = pd.Series(np.nan, index=rows)
    for train, test in _folds(y, rows):
        if size is not None and size < len(train):
            train, _ = train_test_split(
                train, train_size=size, stratify=y[train], random_state=modelling.SEED + seed
            )
        out.loc[test] = _fit_predict(s, estimator, train, test)
    return out.loc[rows].to_numpy()


# ----------------------------------------------------------------------------- scores
def _score(code, description, s, estimator, train_desc, design, y, p, train_n, groups=None):
    ci = modelling.bootstrap_ci(y, p, groups, n=N_BOOT_DIAGNOSIS)
    cal = modelling.calibration_fit(y, p)
    return {
        "code": code,
        "score": description,
        "features": s.label,
        "estimator": estimator,
        "trained_on": train_desc,
        "design": design,
        "train_n": int(train_n),
        "test_n": int(len(y)),
        "test_positives": int(y.sum()),
        "test_prevalence": float(y.mean()),
        "mean_predicted": float(np.mean(p)),
        "roc_auc": float(roc_auc_score(y, p)),
        **ci,
        "calibration_intercept": cal["calibration_intercept"],
        "calibration_slope": cal["calibration_slope"],
    }


def _mean_auc(y: np.ndarray, repeats: list[np.ndarray], idx: np.ndarray | None = None) -> float:
    if idx is None:
        return float(np.mean([roc_auc_score(y, p) for p in repeats]))
    return float(np.mean([roc_auc_score(y[idx], p[idx]) for p in repeats]))


def _paired_against_repeats(
    y: np.ndarray, p: np.ndarray, repeats: list[np.ndarray]
) -> tuple[float, float]:
    """Interval of AUC(p) minus the mean AUC of the size-matched repeats, same crashes."""
    diffs = []
    for idx in modelling.resamples(len(y), None, N_BOOT_DIAGNOSIS):
        if 0 < y[idx].sum() < len(idx):
            diffs.append(roc_auc_score(y[idx], p[idx]) - _mean_auc(y, repeats, idx))
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def _independent_repeats(
    y1: np.ndarray, repeats: list[np.ndarray], y2: np.ndarray, p2: np.ndarray
) -> tuple[float, float]:
    """Interval of the repeats' mean AUC on one set of crashes minus AUC(p2) on another."""
    rng = np.random.default_rng(modelling.SEED)
    diffs = []
    for _ in range(N_BOOT_DIAGNOSIS):
        a = rng.integers(0, len(y1), len(y1))
        b = rng.integers(0, len(y2), len(y2))
        if 0 < y1[a].sum() < len(a) and 0 < y2[b].sum() < len(b):
            diffs.append(_mean_auc(y1, repeats, a) - roc_auc_score(y2[b], p2[b]))
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def _matched_auc_ci(y: np.ndarray, repeats: list[np.ndarray]) -> tuple[float, float, float]:
    """Mean ROC-AUC over the size-matched repeats, with a bootstrap interval of that mean."""
    mean = float(np.mean([roc_auc_score(y, p) for p in repeats]))
    draws = []
    for idx in modelling.resamples(len(y), None, N_BOOT_DIAGNOSIS):
        if 0 < y[idx].sum() < len(idx):
            draws.append(np.mean([roc_auc_score(y[idx], p[idx]) for p in repeats]))
    return mean, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def decomposition(
    full: Setting, common: Setting, domain: pd.Series, zone: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Scores A-K and the components they telescope into, for each estimator of each setting."""
    bcn = np.flatnonzero(domain.eq(transport.BARCELONA))
    rest = np.flatnonzero(domain.eq(transport.REST))
    rest_urban = np.flatnonzero(domain.eq(transport.REST) & zone.eq(URBAN))
    y = full.frame[full.table.target].to_numpy()
    if not np.array_equal(y, common.frame[common.table.target].to_numpy()):
        raise ValueError("targets differ between the full and the common Catalan tables")
    bcn_train_size = min(len(a) for a, _ in _folds(y, bcn))
    scores, components = [], []
    for s, code_in_rest, code_matched, code_bcn, code_transfer in (
        (full, "A", "G", "C", "E"),
        (common, "B", "H", "D", "F"),
    ):
        for estimator in s.estimators:
            log.info("diagnosis: %s / %s", s.label, estimator)
            p_rest = in_domain(s, estimator, rest)
            p_bcn = in_domain(s, estimator, bcn)
            p_transfer = _fit_predict(s, estimator, rest, bcn)
            matched = [
                in_domain(s, estimator, rest, size=bcn_train_size, seed=k)
                for k in range(SIZE_REPEATS)
            ]
            matched_urban = [
                in_domain(s, estimator, rest_urban, size=bcn_train_size, seed=k)
                for k in range(SIZE_REPEATS)
            ]
            p_urban_transfer = _fit_predict(s, estimator, rest_urban, bcn)
            y_rest, y_bcn, y_urban = y[rest], y[bcn], y[rest_urban]
            scores += [
                _score(
                    code_in_rest,
                    "rest of Catalonia, trained inside it (5-fold CV)",
                    s,
                    estimator,
                    transport.REST,
                    "in-domain",
                    y_rest,
                    p_rest,
                    len(rest) * 4 / 5,
                ),
                _score(
                    code_bcn,
                    "Barcelona, trained inside it (5-fold CV)",
                    s,
                    estimator,
                    transport.BARCELONA,
                    "in-domain",
                    y_bcn,
                    p_bcn,
                    bcn_train_size,
                ),
                _score(
                    code_transfer,
                    "Barcelona, trained on the rest of Catalonia",
                    s,
                    estimator,
                    transport.REST,
                    "transfer",
                    y_bcn,
                    p_transfer,
                    len(rest),
                ),
                _score(
                    f"{code_transfer}u",
                    "Barcelona, trained on the rest of Catalonia's urban crashes",
                    s,
                    estimator,
                    f"{transport.REST}, {URBAN}",
                    "transfer",
                    y_bcn,
                    p_urban_transfer,
                    len(rest_urban),
                ),
            ]
            for code, rows_y, repeats, desc in (
                (code_matched, y_rest, matched, "rest of Catalonia"),
                (f"{code_matched}u", y_urban, matched_urban, f"rest of Catalonia, {URBAN}"),
            ):
                auc, low, high = _matched_auc_ci(rows_y, repeats)
                scores.append(
                    {
                        "code": code,
                        "score": f"{desc}, trained inside it with Barcelona's training size",
                        "features": s.label,
                        "estimator": estimator,
                        "trained_on": desc,
                        "design": f"in-domain, size-matched ({SIZE_REPEATS} repeats)",
                        "train_n": int(bcn_train_size),
                        "test_n": int(len(rows_y)),
                        "test_positives": int(rows_y.sum()),
                        "test_prevalence": float(rows_y.mean()),
                        "mean_predicted": float(np.mean([p.mean() for p in repeats])),
                        "roc_auc": auc,
                        "roc_auc_low": low,
                        "roc_auc_high": high,
                    }
                )
            auc_matched = np.mean([roc_auc_score(y_rest, p) for p in matched])
            auc_matched_urban = np.mean([roc_auc_score(y_urban, p) for p in matched_urban])
            base = {"features": s.label, "estimator": estimator}

            def paired(name, definition, yy, first, second, value=None):
                d = modelling.paired_difference(yy, first, second, n=N_BOOT_DIAGNOSIS)
                components.append(
                    {
                        **base,
                        "component": name,
                        "definition": definition,
                        "value": d["roc_auc_difference"] if value is None else value,
                        "low": d["roc_auc_difference_low"],
                        "high": d["roc_auc_difference_high"],
                        "interval": "paired bootstrap (same crashes)",
                    }
                )

            def interval(name, definition, value, low, high, kind):
                components.append(
                    {
                        **base,
                        "component": name,
                        "definition": definition,
                        "value": value,
                        "low": low,
                        "high": high,
                        "interval": kind,
                    }
                )

            interval(
                "training-size cost",
                f"{code_in_rest} - {code_matched}: the rest of "
                "Catalonia in-domain, full training folds against Barcelona-sized ones",
                float(roc_auc_score(y_rest, p_rest) - auc_matched),
                *_paired_against_repeats(y_rest, p_rest, matched),
                "paired bootstrap (same crashes)",
            )
            interval(
                "intrinsic difference",
                f"{code_matched} - {code_bcn}: same features, "
                "same training size, rest of Catalonia against Barcelona",
                float(auc_matched - roc_auc_score(y_bcn, p_bcn)),
                *_independent_repeats(y_rest, matched, y_bcn, p_bcn),
                "independent bootstrap (different crashes)",
            )
            interval(
                "intrinsic difference against urban crashes",
                f"{code_matched}u - {code_bcn}: same features, same training size, "
                "the rest of Catalonia's urban crashes against Barcelona",
                float(auc_matched_urban - roc_auc_score(y_bcn, p_bcn)),
                *_independent_repeats(y_urban, matched_urban, y_bcn, p_bcn),
                "independent bootstrap (different crashes)",
            )
            paired(
                "transport gap",
                f"{code_bcn} - {code_transfer}: Barcelona trained inside "
                "it against trained on the rest of Catalonia (negative: the larger foreign "
                "training set more than makes up for the change of domain)",
                y_bcn,
                p_bcn,
                p_transfer,
            )
            paired(
                "urban-only training",
                f"{code_transfer}u - {code_transfer}: transfer from "
                "the rest of Catalonia's urban crashes against from all of its crashes",
                y_bcn,
                p_urban_transfer,
                p_transfer,
            )
            components.append(
                {
                    **base,
                    "component": "total drop",
                    "definition": f"{code_in_rest} - {code_transfer}: = training-size cost + "
                    "intrinsic difference + transport gap",
                    "value": float(
                        roc_auc_score(y_rest, p_rest) - roc_auc_score(y_bcn, p_transfer)
                    ),
                    "interval": "sum of the three components",
                }
            )
    # Feature loss: same rows, same estimator kind, full against common features.
    by = {(r["code"], r["estimator"]): r for r in scores}
    for estimator in sorted(set(full.estimators) & set(common.estimators)):
        for rows, full_code, common_code, where in (
            (rest, "A", "B", transport.REST),
            (bcn, "C", "D", transport.BARCELONA),
        ):
            p_full = in_domain(full, estimator, rows)
            p_common = in_domain(common, estimator, rows)
            d = modelling.paired_difference(y[rows], p_full, p_common, n=N_BOOT_DIAGNOSIS)
            components.append(
                {
                    "features": "full against Barcelona-common",
                    "estimator": estimator,
                    "component": f"feature loss in {where}",
                    "definition": f"{full_code} - {common_code}: in-domain, same crashes, full "
                    "Catalan features against the Barcelona-common ones",
                    "value": by[(full_code, estimator)]["roc_auc"]
                    - by[(common_code, estimator)]["roc_auc"],
                    "low": d["roc_auc_difference_low"],
                    "high": d["roc_auc_difference_high"],
                    "interval": "paired bootstrap (same crashes)",
                }
            )
    return pd.DataFrame(scores), pd.DataFrame(components)


# ----------------------------------------------------------------------------- strategies
def strategies(
    s: Setting,
    target: np.ndarray,
    other: np.ndarray,
    target_label: str,
    other_label: str,
    universal: Setting | None = None,
) -> list[dict]:
    """Domain-specific, other-domain, pooled and pooled-with-flag models on the same held-out
    crashes of the target domain (and the pooled common-feature model when given)."""
    y = s.frame[s.table.target].to_numpy()
    flagged = s.frame.assign(**{FLAG: 0})
    flagged.loc[target, FLAG] = 1
    flag_table = dataclasses.replace(
        s.table,
        catalogue=s.table.catalogue
        + (Feature(FLAG, "binary", "safe", "1 for the target domain", (s.feature_set,)),),
    )
    folds = _folds(y, target)
    rows = []
    for estimator in s.estimators:
        log.info("strategies: %s / %s / %s", target_label, s.label, estimator)
        preds = {k: pd.Series(np.nan, index=target) for k in ("specific", "pooled", "flag", "uni")}
        preds["other"] = pd.Series(_fit_predict(s, estimator, other, target), index=target)
        for train, test in folds:
            preds["specific"].loc[test] = _fit_predict(s, estimator, train, test)
            pooled = np.concatenate([other, train])
            preds["pooled"].loc[test] = _fit_predict(s, estimator, pooled, test)
            preds["flag"].loc[test] = _fit_predict(
                s, estimator, pooled, test, table=flag_table, frame=flagged
            )
            if universal is not None and estimator in universal.estimators:
                preds["uni"].loc[test] = _fit_predict(universal, estimator, pooled, test)
        yy = y[target]
        specific = preds["specific"].to_numpy()
        labels = {
            "specific": (f"domain-specific: {target_label} only", s.label, len(target) * 4 / 5),
            "other": (f"other domain only: {other_label}", s.label, len(other)),
            "pooled": ("pooled: both domains", s.label, len(other) + len(target) * 4 / 5),
            "flag": ("pooled with a domain flag", s.label, len(other) + len(target) * 4 / 5),
            "uni": (
                "pooled, Barcelona-common features (universal)",
                universal.label if universal else "",
                len(other) + len(target) * 4 / 5,
            ),
        }
        for key, (strategy, feature_label, train_n) in labels.items():
            p = preds[key].to_numpy()
            if np.isnan(p).any():
                continue
            row = {
                "target_domain": target_label,
                "strategy": strategy,
                "features": feature_label,
                "estimator": estimator,
                "train_n": int(train_n),
                **modelling.metrics(yy, p),
                **modelling.bootstrap_ci(yy, p, None, n=N_BOOT_DIAGNOSIS),
                **modelling.calibration_fit(yy, p),
            }
            if key != "specific":
                d = modelling.paired_difference(yy, p, specific, n=N_BOOT_DIAGNOSIS)
                row.update(
                    gain_over_specific=d["roc_auc_difference"],
                    gain_over_specific_low=d["roc_auc_difference_low"],
                    gain_over_specific_high=d["roc_auc_difference_high"],
                )
            rows.append(row)
    return rows


def domain_strategies(
    full: Setting, common: Setting, domain: pd.Series, zone: pd.Series
) -> pd.DataFrame:
    bcn = np.flatnonzero(domain.eq(transport.BARCELONA))
    rest = np.flatnonzero(domain.eq(transport.REST))
    urban = np.flatnonzero(zone.eq(URBAN))
    interurban = np.flatnonzero(zone.eq(INTERURBAN))
    rows = strategies(full, bcn, rest, transport.BARCELONA, transport.REST, universal=common)
    rows += strategies(full, rest, bcn, transport.REST, transport.BARCELONA, universal=common)
    rows += strategies(full, urban, interurban, URBAN, INTERURBAN)
    rows += strategies(full, interurban, urban, INTERURBAN, URBAN)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- reading
def verdicts(components: pd.DataFrame, strategies_frame: pd.DataFrame) -> pd.DataFrame:
    """One line per question, read off the tables by a rule declared here.

    A component is *material* when its interval excludes zero and it is at least
    :data:`rules.MIN_GAIN` in size; the largest material component of the total drop is named.
    """
    from dgt_stats.microdata.ml.rules import MIN_GAIN

    out = []
    parts = ("training-size cost", "intrinsic difference", "transport gap")
    for (feats, estimator), group in components.groupby(["features", "estimator"]):
        if feats.startswith("full against"):
            continue
        g = group.set_index("component")
        material = [
            c
            for c in parts
            if abs(g.loc[c, "value"]) >= MIN_GAIN and (g.loc[c, "low"] > 0 or g.loc[c, "high"] < 0)
        ]
        largest = max(parts, key=lambda c: g.loc[c, "value"])
        out.append(
            {
                "question": "what makes up the drop from the rest of Catalonia to Barcelona",
                "features": feats,
                "estimator": estimator,
                "total_drop": float(g.loc["total drop", "value"]),
                **{c.replace(" ", "_").replace("-", "_"): float(g.loc[c, "value"]) for c in parts},
                "intrinsic_difference_against_urban": float(
                    g.loc["intrinsic difference against urban crashes", "value"]
                ),
                "urban_comparison_excludes_zero": bool(
                    g.loc["intrinsic difference against urban crashes", "low"] > 0
                    or g.loc["intrinsic difference against urban crashes", "high"] < 0
                ),
                "material_components": "; ".join(material) or "none",
                "largest_component": largest,
                "transport_gap_excludes_zero": bool(
                    g.loc["transport gap", "low"] > 0 or g.loc["transport gap", "high"] < 0
                ),
            }
        )
    return pd.DataFrame(out)


def run(results: dict[str, modelling.TaskResult]) -> dict[str, pd.DataFrame]:
    full, common, domain, zone = settings(results)
    scores, components = decomposition(full, common, domain, zone)
    strat = domain_strategies(full, common, domain, zone)
    return {
        "ml_barcelona_diagnosis": scores,
        "ml_barcelona_diagnosis_components": components,
        "ml_barcelona_diagnosis_verdicts": verdicts(components, strat),
        "ml_domain_strategies": strat,
    }
