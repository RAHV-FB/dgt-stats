"""Write the model results: result tables, model cards, the leakage audit and the rare-cause check.

Every number in the generated documents is read from the fitted models or the feature tables in
the same run; nothing is typed in. Wording rules: importance is "used by the model", not causal;
a recorded cause is "recorded", not "caused"; probabilities are shown as estimates only when the
pre-declared calibration rule in :mod:`modelling` passes.
"""

from __future__ import annotations

import pickle

import pandas as pd

from dgt_stats.microdata import barcelona
from dgt_stats.microdata.common import read_provenance
from dgt_stats.microdata.ml import features, modelling, recording, rules
from dgt_stats.paths import DOCS_DIR, FEATURES_DATA_DIR, TABLES_DIR

MODEL_DOCS = DOCS_DIR / "models"
LEAKAGE_DOC = DOCS_DIR / "ML_LEAKAGE_AUDIT.md"

CARD_NAMES = {
    "catalonia_crash_severity": "catalonia_fatal_severity",
    "barcelona_person_severity": "barcelona_person_severity",
    "barcelona_crash_severity": "barcelona_crash_severity",
}

QUESTIONS = {
    "catalonia_crash_severity": (
        "Among recorded crashes in Catalonia with a death or a serious injury, which combinations "
        "of road, crash and environmental characteristics are most predictive of the crash being "
        "fatal rather than serious?"
    ),
    "barcelona_person_severity": (
        "Among people recorded in Barcelona crashes, which observed circumstances and road-user "
        "characteristics are most predictive of a serious or fatal injury?"
    ),
    "barcelona_crash_severity": (
        "Which recorded crash circumstances distinguish Barcelona crashes with a serious or fatal "
        "injury from lower-severity recorded crashes?"
    ),
}

VALID = {
    "catalonia_crash_severity": [
        "Ranking recorded serious-or-fatal crash profiles by how often similar crashes were fatal, "
        "to choose which road and crash configurations deserve closer analysis.",
        "Comparing the fatal share of crash types, road types and conditions within this "
        "conditioned dataset, alongside the descriptive tables that show each N.",
        "Checking whether the association between recorded characteristics and fatality is "
        "stable from year to year (the temporal evaluation).",
    ],
    "barcelona_person_severity": [
        "Identifying which recorded road-user groups (role, associated vehicle type, age) and "
        "crash types concentrate serious and fatal injuries among people involved in Barcelona "
        "crashes in 2025.",
        "Ranking person profiles for road-safety analysis of vulnerable users; probabilities are "
        "shown only as a ranking when calibration fails.",
    ],
    "barcelona_crash_severity": [
        "A multivariable check on the descriptive tables: whether the recorded circumstances "
        "(vehicles present, time, district) add anything to the accident type in ranking crashes "
        "by severity (the rule comparison below answers it).",
        "The retrospective variant shows how much the police's recorded causes add once a crash "
        "has been investigated; it is a retrospective classification, not a real-time predictor.",
    ],
}
INVALID = [
    "It is not a causal model: a feature that the model uses is associated with the outcome in "
    "these records; changing it is not shown to change the outcome.",
    "It does not predict whether a crash will happen, or anyone's risk per trip, per kilometre or "
    "per person: there is no exposure in these data.",
    "It is not a prediction about an individual driver, and recorded causes are not findings "
    "about a person (the cause tables have no person key).",
    "It does not say how many deaths or injuries any measure would prevent.",
]
LIMITS = {
    "catalonia_crash_severity": [
        "The data contain only crashes with a death or serious injury: the model compares fatal "
        "with serious crashes and says nothing about crashes with only minor injuries or none.",
        "Recording completeness follows the outcome (fatal crashes are documented more fully); "
        "the fields where this is visible are kept out of the primary model and shown in the "
        "recording check.",
        "No vehicle speeds, no person records, no alcohol or drug tests: `C_VELOCITAT_VIA` is the "
        "road's limit, and is a code rather than a limit wherever the generic limit applies.",
        "Severity definitions are those of the Servei Català de Trànsit export; the file does not "
        "state the time window of a death.",
    ],
    "barcelona_person_severity": [
        "One year (2025) of one city; the test months are the last three of the same year.",
        "Few positive cases: every count of serious or fatal injuries is in the tables, and the "
        "intervals are wide.",
        "Person records without a recorded victimisation (mostly drivers whose age and sex are "
        "also missing) and one natural death are excluded from the target.",
        "The vehicle type on a pedestrian's record does not say which vehicle it is; crash-level "
        "recorded causes are crash context, never the person's own behaviour.",
    ],
    "barcelona_crash_severity": [
        "One year of one city, with few serious-or-fatal crashes.",
        "Vehicle involvement is the presence of a vehicle type among the crash's vehicle records; "
        "vehicle counts from that table are quarantined (see the vehicle audit).",
        "Recorded causes are police coding after the event, used only in the labelled "
        "retrospective variant.",
    ],
}


def _md(frame: pd.DataFrame) -> str:
    def fmt(value, column):
        if isinstance(value, float):
            if any(w in column for w in ("share", "prevalence", "precision", "recall")):
                return f"{value:.1%}"
            return f"{value:.3f}"
        if isinstance(value, int) and not isinstance(value, bool):
            return f"{value:,}"
        return str(value).replace("|", "/")

    header = "| " + " | ".join(frame.columns) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = [
        "| " + " | ".join(fmt(v, c) for v, c in zip(row, frame.columns)) + " |"
        for row in frame.itertuples(index=False)
    ]
    return "\n".join([header, rule, *rows])


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


# ----------------------------------------------------------------------------- rare causes
def rare_causes() -> pd.DataFrame:
    """Could a model predict a recorded cause? Positives, prevalence and the verdict per cause."""
    crashes = barcelona.read_crashes()
    n_context = len(features.BARCELONA_CRASH_TABLE.columns("context", "broad"))
    rows = []
    for prefix, codes in (
        ("mediate", barcelona.MEDIATE_CAUSES),
        ("driver_cause", barcelona.DRIVER_CAUSES),
    ):
        for source, (code, label) in codes.items():
            column = f"{prefix}_{code}_recorded"
            if column not in crashes.columns:
                continue
            values = crashes[column]
            positives = int(values.sum())
            rows.append(
                {
                    "table": "mediate causes" if prefix == "mediate" else "driver causes",
                    "category": source,
                    "label": label,
                    "crashes_recorded": positives,
                    "crashes_missing": int(values.isna().sum()),
                    "prevalence": positives / len(crashes),
                    "events_per_context_feature": positives / n_context,
                }
            )
    out = pd.DataFrame(rows)
    out["verdict"] = [
        "insufficient data for a reliable model"
        if n < 100
        else "enough cases for descriptive comparison; no predictive model fitted (a recorded "
        "cause reflects police investigation and testing practice, so predicting it has no "
        "defensible use here)"
        for n in out.crashes_recorded
    ]
    return out.sort_values(["table", "crashes_recorded"], ascending=[False, False])


# ----------------------------------------------------------------------------- outputs
def write_tables(results: list[modelling.TaskResult]) -> dict[str, pd.DataFrame]:
    checks = []
    for task in results:
        rows = modelling.refit_rows(task.split)
        checks.append(features.recording_check(task.table.name, rows))
    missing = pd.concat([features.missingness(t.table.name) for t in results], ignore_index=True)
    cat_task = next(t for t in results if t.table.name == "catalonia_crash_severity")
    artefacts = recording.audit(rows=modelling.refit_rows(cat_task.split))
    tables = {
        "ml_recording_artefacts": artefacts,
        "ml_selected": modelling.selected_table(results),
        "ml_variants": modelling.variant_table(results),
        "ml_geography": modelling.geography_table(results),
        "ml_calibration": modelling.calibration_table(results),
        "ml_importance": modelling.importance_table(results),
        "ml_stability": modelling.stability_table(results),
        "ml_split_isolation": modelling.isolation_table(results),
        "ml_feature_catalogue": features.catalogue_frame(),
        "ml_missingness": missing,
        "ml_recording_check": pd.concat(checks, ignore_index=True),
        "ml_rare_causes": rare_causes(),
    }
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.6g")
    return tables


def model_card(task: modelling.TaskResult, tables: dict[str, pd.DataFrame]) -> str:
    table = task.table
    name = table.name
    selected = tables["ml_selected"].query("model == @name")
    primary = selected[selected.primary].iloc[0]
    detail = task.detailed[table.primary_set]
    provenance = read_provenance(table.path)
    variants = tables["ml_variants"].query(
        "model == @name and evaluated_on == 'test' and geography == @table.primary_geography"
    )
    comparison = variants[
        [
            "feature_set",
            "estimator",
            "n",
            "positives",
            "prevalence",
            "roc_auc",
            "pr_auc",
            "brier",
            "brier_skill",
            "balanced_accuracy",
            "precision",
            "recall",
            "f1",
        ]
    ]
    geography = tables["ml_geography"].query("model == @name")[
        [
            "feature_set",
            "geography",
            "estimator",
            "training_fit_roc_auc",
            "validation_roc_auc",
            "test_roc_auc",
        ]
    ]
    stability = (
        tables["ml_stability"]
        .query("model == @name")
        .groupby("evaluation")
        .agg(
            blocks=("roc_auc", "size"),
            roc_auc_mean=("roc_auc", "mean"),
            roc_auc_min=("roc_auc", "min"),
            roc_auc_max=("roc_auc", "max"),
        )
        .reset_index()
    )
    importance = detail["importance"].head(12)[
        ["feature", "kind", "status", "auc_drop_mean", "auc_drop_std"]
    ]
    catalogue = [f for f in table.catalogue]
    used = table.features(table.primary_set, table.primary_geography)
    second = next(s for s in table.feature_sets if s != table.primary_set)
    retro_only = [
        f
        for f in table.features(second, table.primary_geography)
        if f.column not in {u.column for u in used}
    ]
    leak = [f for f in catalogue if f.status == "direct_leakage"]
    held = [f for f in catalogue if f.status == "questionable" and not f.sets]
    excluded = [f for f in catalogue if f.status == "excluded"]
    confusion = (
        f"{int(primary.tp)} true positives, {int(primary.fp)} false positives, "
        f"{int(primary.fn)} false negatives, {int(primary.tn)} true negatives"
    )
    reliable = bool(primary.probabilities_shown_as_estimates)
    decisions = tables["ml_model_decisions"]
    decision = decisions[decisions.model.eq(name) & decisions.variant.eq(table.primary_set)].iloc[0]
    rule = tables["ml_rule_comparison"].set_index("model").loc[name]
    path = tables["ml_outward_path"].query("model == @name")[
        ["stage", "stage_name", "status", "evidence"]
    ]
    lines = [
        f"# Model card: {CARD_NAMES[name].replace('_', ' ')}",
        "",
        "Generated by `python scripts/microdata.py validate`; do not edit by hand.",
        "",
        "## Task",
        "",
        QUESTIONS[name],
        "",
        f"- **Observation (one row):** {table.unit}.",
        f"- **Target:** `{table.target}` = {table.target_definition}.",
        f"- **Feature table:** `data/features/{table.path.name}` "
        f"({provenance['rows']:,} rows, id `{table.id_column}`"
        + (f", grouped by `{table.group_column}`" if table.group_column else "")
        + ").",
        "- **Source files:** "
        + "; ".join(
            f"`data/raw/{v['file']}` (SHA-256 `{v['sha256'][:12]}…`)"
            for v in provenance["sources"].values()
        )
        + ".",
        f"- **Layer:** {decision.layer}.",
        f"- **Decision:** {decision.decision} ({decision.usefulness}).",
        f"- **What it does:** {decision.question_answered}.",
        f"- **Not answered:** {decision.question_not_answered}.",
        "",
        "## Data and split",
        "",
        f"- Design: {task.split.description}.",
        f"- Training rows (final fit): {int(primary.train_rows):,}, of which "
        f"{int(primary.train_positives):,} positive.",
        f"- Test rows: {int(primary.n):,}, of which {int(primary.positives):,} positive "
        f"(prevalence {primary.prevalence:.1%}).",
        f"- Isolation: ids shared between training and test: {task.isolation['shared_ids']}; "
        f"crashes shared: {task.isolation['shared_groups']}; crashes shared across "
        f"cross-validation folds: {task.isolation['fold_shared_groups']}.",
        "- Model choice (estimator and its two-point grid) is made on validation data only; the "
        "test rows are used once, for the numbers below.",
        "",
        "## Features",
        "",
        f"Primary model (`{table.primary_set}`, geography `{table.primary_geography}`): "
        + ", ".join(f"`{f.column}`" for f in used)
        + ".",
        "",
        f"Added in the `{second}` variant (recorded after the event or dependent on how fully "
        "a crash was documented): "
        + (", ".join(f"`{f.column}`" for f in retro_only) or "none")
        + ".",
        "",
        "Never used (direct leakage): " + ", ".join(f"`{f.column}`" for f in leak) + ".",
        "",
        "Held out as questionable: " + (", ".join(f"`{f.column}`" for f in held) or "none") + ".",
        "",
        "Excluded for other reasons: " + ", ".join(f"`{f.column}`" for f in excluded) + ".",
        "",
        "Every decision and its reason: [`ML_LEAKAGE_AUDIT.md`](../ML_LEAKAGE_AUDIT.md).",
        "",
        "## Performance on the test rows",
        "",
        f"Selected model: **{modelling.ESTIMATOR_LABELS[primary.estimator]}** ({primary.params}),"
        f" validation ROC-AUC {primary.validation_roc_auc:.3f}.",
        "",
        f"- ROC-AUC {primary.roc_auc:.3f} (95% bootstrap interval {primary.roc_auc_low:.3f}–"
        f"{primary.roc_auc_high:.3f}); the prior-only baseline scores 0.500.",
        f"- PR-AUC {primary.pr_auc:.3f} ({primary.pr_auc_low:.3f}–{primary.pr_auc_high:.3f}) "
        f"against a prevalence of {primary.prevalence:.3f}.",
        f"- Brier score {primary.brier:.4f} against {primary.baseline_test_brier:.4f} for the "
        f"baseline (skill {primary.brier_skill:+.3f}).",
        f"- At the threshold chosen on validation data ({primary.threshold:.3f}): precision "
        f"{primary.precision:.1%}, recall {primary.recall:.1%}, F1 {primary.f1:.3f}, balanced "
        f"accuracy {primary.balanced_accuracy:.3f}; {confusion}.",
        "",
        "All estimators and both feature sets on the same test rows:",
        "",
        _md(comparison),
        "",
        "## Calibration",
        "",
        f"Calibration slope {primary.calibration_slope:.2f} (95% interval "
        f"{primary.calibration_slope_low:.2f}–{primary.calibration_slope_high:.2f}), calibration "
        f"intercept {primary.calibration_intercept:+.2f}, mean predicted "
        f"{primary.mean_predicted:.3f} against {primary.prevalence:.3f} observed.",
        "",
        (
            "The pre-declared rule (slope between "
            f"{modelling.CALIBRATION_SLOPE_RANGE[0]} and {modelling.CALIBRATION_SLOPE_RANGE[1]}, "
            f"mean prediction within {modelling.CALIBRATION_LARGE_TOLERANCE:.0%} of the "
            "prevalence) "
            + (
                "passes: probabilities may be shown as estimates for groups of similar crashes."
                if reliable
                else "fails: probabilities are **not** shown as risk estimates; the model is used "
                "only to rank profiles."
            )
        ),
        "",
        _md(detail["calibration_curve"][["bin", "n", "positives", "mean_predicted", "observed"]]),
        "",
        "## Generalisation",
        "",
        _md(stability),
        "",
        "Geography variants (training fit against validation and test; a large training-test gap "
        "with granular geography means the model memorises places):",
        "",
        _md(geography),
        "",
        "## What the model uses",
        "",
        "Permutation importance on the test rows: the fall in ROC-AUC when one feature's values "
        "are shuffled (mean and standard deviation over "
        f"{modelling.N_PERMUTATIONS} shuffles). It measures what the model relies on, not what "
        "causes severity.",
        "",
        _md(importance),
        "",
        "## Does it add anything over a descriptive table?",
        "",
        f"The competitor is the outcome share of each group of `{rule.rule}` in the training "
        f"rows ({int(rule.rule_groups_in_training)} groups), scored on the same test rows: "
        f"ROC-AUC {rule.model_roc_auc:.3f} for the model against {rule.rule_roc_auc:.3f} for the "
        f"table, a gain of {rule.roc_auc_gain:+.3f} (paired 95% interval "
        f"{rule.roc_auc_gain_low:+.3f} to {rule.roc_auc_gain_high:+.3f}); PR-AUC "
        f"{rule.model_pr_auc:.3f} against {rule.rule_pr_auc:.3f}. "
        + (
            "The model adds signal over the table."
            if rule.model_adds_signal_over_table
            else "The model does **not** add measurable signal over the table: the table is "
            "what the site shows."
        ),
        "",
        "## Validation outside its own test rows",
        "",
        f"Highest validated level on the outward path "
        f"([`GENERALISABILITY.md`](../GENERALISABILITY.md)): "
        f"{decision.highest_validated_level_name}; the next level is blocked by "
        f"{decision.next_level_blocked_by}. Transfer evidence: {decision.transfer_evidence}.",
        "",
        _md(path),
        "",
        "## Valid interpretation",
        "",
        *_bullets(VALID[name]),
        "",
        "## Invalid interpretation",
        "",
        *_bullets(INVALID),
        "",
        "## Limitations",
        "",
        *_bullets(LIMITS[name]),
        "",
    ]
    return "\n".join(lines)


def leakage_audit(tables: dict[str, pd.DataFrame]) -> str:
    catalogue = tables["ml_feature_catalogue"]
    recording = tables["ml_recording_check"]
    lines = [
        "# ML leakage audit",
        "",
        "Generated by `python scripts/microdata.py models` from the feature catalogue in",
        "`src/dgt_stats/microdata/features.py`; do not edit by hand. The tests fail if a",
        "direct-leakage column reaches a feature table or a model matrix.",
        "",
        "Statuses:",
        "",
        "- **safe**: a circumstance recorded about the crash or the person, not derived from the",
        "  outcome; used in every feature set it is listed for.",
        "- **questionable**: plausibly shaped by the outcome or established only by later",
        "  investigation; used only in the labelled `retrospective` set, or not at all.",
        "- **direct leakage**: encodes the target; never in a feature table.",
        "- **excluded**: not used for another reason (identifier, duplicate, too granular).",
        "",
        "Joins: the Catalonia table needs none. The Barcelona crash table joins the accident-type",
        "table one-to-one and the cause and vehicle-record tables after aggregating them to one",
        "row per crash; the person table receives crash context many-to-one on",
        "`Numero_expedient`. Each join is validated by pandas on every build.",
        "",
    ]
    for table in features.TABLES:
        part = catalogue[catalogue.feature_table == table.name]
        lines += [
            f"## {table.name}",
            "",
            f"Target: `{table.target}` = {table.target_definition}.",
            "",
            _md(part[["column", "kind", "status", "feature_sets", "geography_variant", "reason"]]),
            "",
        ]
        rec = recording[recording.feature_table == table.name]
        rec = rec[rec.rows >= 20]
        if not rec.empty:
            lines += [
                "Recording check on the training rows: the target share where a categorical",
                "feature is a placeholder (`NA`, not specified, not recorded) against the other",
                "rows. A ratio far from 1 for a field with no structural reason (such as `NA`",
                'meaning "not at a junction" or "urban street") marks the field as',
                "documentation-dependent.",
                "",
                _md(
                    rec[
                        [
                            "column",
                            "status",
                            "level",
                            "rows",
                            "share_of_rows",
                            "target_share_level",
                            "target_share_other_rows",
                            "ratio",
                        ]
                    ]
                ),
                "",
            ]
    return "\n".join(lines)


def write_docs(results: list[modelling.TaskResult], tables: dict[str, pd.DataFrame]) -> None:
    MODEL_DOCS.mkdir(parents=True, exist_ok=True)
    for task in results:
        path = MODEL_DOCS / f"{CARD_NAMES[task.table.name]}.md"
        path.write_text(model_card(task, tables), encoding="utf-8")


def write_csvs(tables: dict[str, pd.DataFrame]) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.6g")


def read_tables(
    prefixes: tuple[str, ...] = ("ml_", "cat_", "bcn_", "mq_"),
) -> dict[str, pd.DataFrame]:
    """The result tables a later step needs, read back from ``reports/tables``."""
    return {
        path.stem: pd.read_csv(path)
        for path in sorted(TABLES_DIR.glob("*.csv"))
        if path.stem.startswith(prefixes)
    }


RESULTS_CACHE = FEATURES_DATA_DIR / "model_results.pkl"


def fit() -> dict[str, modelling.TaskResult]:
    """Fit every source model and keep the fitted results for the validation step."""
    features.build_common()
    names = [t.name for t in features.TABLES] + [t.name for t in features.common_tables()]
    results = {name: modelling.run_task(name) for name in names}
    with RESULTS_CACHE.open("wb") as handle:
        pickle.dump(results, handle)
    return results


def load() -> dict[str, modelling.TaskResult]:
    if not RESULTS_CACHE.exists():
        raise FileNotFoundError(f"{RESULTS_CACHE} missing: run `scripts/microdata.py models`")
    with RESULTS_CACHE.open("rb") as handle:
        return pickle.load(handle)


def run() -> dict[str, pd.DataFrame]:
    """The source models: fit, evaluate on their own held-out rows, compare with a lookup table,
    and write the model tables and the leakage audit. Transfer tests are a separate step
    (:mod:`dgt_stats.microdata.validation.pipeline`)."""
    results = fit()
    tables = write_tables(list(results.values()))
    tables["ml_rule_comparison"] = rules.run(list(results.values()))
    write_csvs({"ml_rule_comparison": tables["ml_rule_comparison"]})
    LEAKAGE_DOC.write_text(leakage_audit(tables), encoding="utf-8")
    return tables
