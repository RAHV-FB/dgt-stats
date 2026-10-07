"""Which models earn their place: the model decision table.

The question for every model: *does it provide useful information beyond a simple descriptive
table?* Each row is filled from the result tables of the same run; the decision follows rules
declared here, before any result is read, in this order:

1. **DROP** when the model does not beat chance on its own unseen test rows (the ROC-AUC
   interval reaches 0.5) or does not hold on later records (stage 2 of the outward path fails).
2. **KEEP as research/diagnostic model** when its purpose is to examine the data rather than to
   rank cases: a variant that uses information recorded after the event (causes, "influence"
   judgements), a model restricted to the variables another source shares (it exists to measure
   transfer), or a model on a source whose audit does not allow predictive use.
3. **REPLACE with descriptive table** when it does not beat its descriptive lookup table
   (:mod:`dgt_stats.microdata.ml.rules`) on the same unseen rows; the table is what is shown.
4. **KEEP as useful predictive model** when it beats the table and its probabilities pass the
   pre-declared calibration rule, so they can be read as estimates for groups of similar cases.
5. **KEEP but ranking-only** when it beats the table but its probabilities fail that rule.

The monthly deaths forecast is judged the same way, with the naive forecasts (last year, mean of
three years) as its descriptive baseline, on the held-out ordinary years; the lockdown years,
scored apart by the forecast module, are reported beside the decision.

Every row also carries the furthest level its evidence reaches on the outward path (same source,
later time, another region, another recording source, Spain), the in-domain and transferred
scores of its external tests with the gap, and what it does not answer. Writes
``reports/tables/ml_model_decisions.csv`` and ``docs/MODEL_DECISIONS.md``.
"""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import layers
from dgt_stats.paths import DOCS_DIR, TABLES_DIR

DOC = DOCS_DIR / "MODEL_DECISIONS.md"

KEEP_PREDICTIVE = "KEEP as useful predictive model"
KEEP_RANKING = "KEEP but ranking-only"
KEEP_RESEARCH = "KEEP as research/diagnostic model"
REPLACE = "REPLACE with descriptive table"
DROP = "DROP"
OUTCOMES = (KEEP_PREDICTIVE, KEEP_RANKING, KEEP_RESEARCH, REPLACE, DROP)
FEATURED = (KEEP_PREDICTIVE, KEEP_RANKING)

LEVELS = {
    0: "none",
    1: "same source",
    2: "later time",
    3: "another region",
    4: "another recording source",
    5: "Spain nationally",
}

SOURCE_MODELS = {
    "catalonia_crash_severity": {
        "unit": "one Catalan crash with a death or serious injury",
        "target": "fatal (a death) rather than serious",
        "source": "Servei Català de Trànsit, 2010-2023",
        "layer": layers.CATALONIA.title,
        "purpose": "ranking",
        "question": "ranks recorded serious-or-fatal crashes by how likely they were fatal, from "
        "road, crash and environmental circumstances",
        "not_answered": "whether a crash happens; risk per trip or kilometre; any causal effect; "
        "crashes with only slight injuries",
    },
    "barcelona_person_severity": {
        "unit": "one person recorded in a Barcelona crash",
        "target": "serious or fatal injury",
        "source": "Guàrdia Urbana, 2025",
        "layer": layers.BARCELONA.title,
        "purpose": "ranking",
        "question": "ranks the people recorded in crashes by how likely they were seriously or "
        "fatally injured, from road role, vehicle, age, sex and crash circumstances",
        "not_answered": "anyone's risk per trip; the behaviour of a person (causes have no "
        "person key); other cities or years",
    },
    "barcelona_crash_severity": {
        "unit": "one Barcelona crash",
        "target": "a serious or fatal injury in the crash",
        "source": "Guàrdia Urbana, 2025",
        "layer": layers.BARCELONA.title,
        "purpose": "ranking",
        "question": "ranks recorded crashes by how likely they involved a serious or fatal injury",
        "not_answered": "anyone's risk per trip; the behaviour of a person; other cities or years",
    },
    "catalonia_common_dgt": {
        "unit": "one Catalan crash with a death or serious injury",
        "target": "fatal (a death within 24 hours) rather than serious",
        "source": "Servei Català de Trànsit, restricted to the variables DGT records alike",
        "layer": layers.VALIDATION.title,
        "purpose": "transfer",
        "question": "measures whether a Catalan model keeps its ranking on crashes recorded "
        "elsewhere in Spain",
        "not_answered": "anything the full Catalan model answers (it drops most variables)",
    },
    "catalonia_common_bcn": {
        "unit": "one Catalan crash with a death or serious injury",
        "target": "fatal rather than serious",
        "source": "Servei Català de Trànsit, restricted to the variables Barcelona records alike",
        "layer": layers.VALIDATION.title,
        "purpose": "transfer",
        "question": "measures whether a Catalan model keeps its ranking on Barcelona's crashes",
        "not_answered": "a fatal-against-serious benchmark on Barcelona 2025 (too few fatal "
        "crashes)",
    },
}
RETROSPECTIVE = {
    "catalonia_crash_severity": "retrospective_administrative",
    "barcelona_person_severity": "retrospective",
    "barcelona_crash_severity": "retrospective",
}


def decide(
    *,
    beats_chance: bool,
    holds_later: bool,
    research: bool,
    beats_table: bool | None,
    calibrated: bool,
) -> str:
    """The declared rules, in order."""
    if not beats_chance or not holds_later:
        return DROP
    if research:
        return KEEP_RESEARCH
    if beats_table is False:
        return REPLACE
    return KEEP_PREDICTIVE if calibrated else KEEP_RANKING


def _transfer(transport: pd.DataFrame, model: str, estimator: str) -> str:
    part = transport[
        transport.model.eq(model)
        & transport.estimator.eq(estimator)
        & transport.transfer_gap.notna()
        & transport.status.eq("reported")
        & ~transport.experiment.str.startswith("temporal holdout")
    ]
    if part.empty:
        return "no external test with an in-domain reference"
    return "; ".join(
        f"{r.experiment}: target-domain native {r.in_domain_cv_roc_auc:.3f}, transferred "
        f"{r.roc_auc:.3f}, gap {r.transfer_gap:+.3f} (n={int(r.test_n):,}, "
        f"positives={int(r.test_positives):,}, calibration slope {r.calibration_slope:.2f})"
        for r in part.itertuples()
    )


def _level(path: pd.DataFrame, model: str) -> tuple[int, str, str]:
    part = path[path.model.eq(model)].set_index("stage")
    highest = int(part.highest_consecutive_stage.iloc[0])
    name = part.loc[highest, "stage_name"] if highest else LEVELS[0]
    blocked = (
        f"stage {highest + 1} ({part.loc[highest + 1, 'stage_name']}): "
        f"{part.loc[highest + 1, 'status']}"
        if highest < 5
        else "none"
    )
    return highest, name, blocked


def source_rows(tables: dict[str, pd.DataFrame]) -> list[dict]:
    selected = tables["ml_selected"]
    rules = tables["ml_rule_comparison"].set_index("model")
    path = tables["ml_outward_path"]
    transport = tables["ml_transport_validation"]
    rows = []
    for model, spec in SOURCE_MODELS.items():
        primary = selected[selected.model.eq(model) & selected.primary].iloc[0]
        highest, level_name, blocked = _level(path, model)
        stage2 = path[path.model.eq(model) & path.stage.eq(2)].status.iloc[0]
        calibrated = bool(primary.probabilities_shown_as_estimates)
        calibration = (
            f"slope {primary.calibration_slope:.2f}, mean predicted {primary.mean_predicted:.3f} "
            f"against {primary.prevalence:.3f} observed: "
            + ("probabilities usable as estimates" if calibrated else "ranking only")
        )
        if model in rules.index:
            r = rules.loc[model]
            beats_table = bool(r.model_adds_signal_over_table)
            baseline = (
                f"table of {r.rule.replace('_', ' ')}: ROC-AUC {r.rule_roc_auc:.3f}, PR-AUC "
                f"{r.rule_pr_auc:.3f}"
            )
            usefulness = (
                f"gain {r.roc_auc_gain:+.3f} ({r.roc_auc_gain_low:+.3f} to "
                f"{r.roc_auc_gain_high:+.3f}) over the table: "
                + ("adds signal" if beats_table else "no measurable gain")
            )
        else:
            beats_table = None
            baseline = "prior only (a validation instrument, not compared with a table)"
            usefulness = "measures transfer; not a model to rank cases with"
        decision = decide(
            beats_chance=bool(primary.roc_auc_low > 0.5),
            holds_later=stage2 == "passed",
            research=spec["purpose"] == "transfer",
            beats_table=beats_table,
            calibrated=calibrated,
        )
        base = {
            "model": model,
            "variant": primary.feature_set,
            "unit": spec["unit"],
            "target": spec["target"],
            "source": spec["source"],
            "layer": spec["layer"],
            "baseline": baseline,
            "ml": f"{primary.estimator.replace('_', ' ')}: ROC-AUC {primary.roc_auc:.3f} "
            f"({primary.roc_auc_low:.3f}-{primary.roc_auc_high:.3f}), PR-AUC "
            f"{primary.pr_auc:.3f}; n={int(primary.n):,}, positives={int(primary.positives):,}",
            "test_roc_auc": float(primary.roc_auc),
            "test_n": int(primary.n),
            "test_positives": int(primary.positives),
            "transfer_evidence": _transfer(transport, model, primary.estimator),
            "highest_validated_level": highest,
            "highest_validated_level_name": level_name,
            "next_level_blocked_by": blocked,
            "calibration": calibration,
            "usefulness": usefulness,
            "question_answered": spec["question"],
            "question_not_answered": spec["not_answered"],
            "decision": decision,
        }
        rows.append(base)
        if model in RETROSPECTIVE:
            retro = selected[
                selected.model.eq(model) & selected.feature_set.eq(RETROSPECTIVE[model])
            ]
            if not retro.empty:
                rr = retro.iloc[0]
                rows.append(
                    {
                        **base,
                        "variant": rr.feature_set,
                        "ml": f"{rr.estimator.replace('_', ' ')}: ROC-AUC {rr.roc_auc:.3f} "
                        f"({rr.roc_auc_low:.3f}-{rr.roc_auc_high:.3f})",
                        "test_roc_auc": float(rr.roc_auc),
                        "baseline": f"the primary model: ROC-AUC {primary.roc_auc:.3f}",
                        "usefulness": f"{rr.roc_auc - primary.roc_auc:+.3f} over the primary "
                        "model from information recorded after the event",
                        "transfer_evidence": "not tested (a diagnostic of the record)",
                        "highest_validated_level": 2,
                        "highest_validated_level_name": path[
                            path.model.eq(model) & path.stage.eq(2)
                        ].stage_name.iloc[0],
                        "next_level_blocked_by": "not tested beyond its own test rows",
                        "question_answered": "how much the information recorded after the "
                        "event adds to the ranking",
                        "decision": decide(
                            beats_chance=bool(rr.roc_auc_low > 0.5),
                            holds_later=stage2 == "passed",
                            research=True,
                            beats_table=None,
                            calibrated=bool(rr.probabilities_shown_as_estimates),
                        ),
                    }
                )
    return rows


def national_rows(tables: dict[str, pd.DataFrame]) -> list[dict]:
    rows = []
    checks = tables.get("dgt_audit_checks")
    artefacts = tables.get("dgt_audit_artefacts")
    q3_path = TABLES_DIR / "q3_holdout_summary.csv"
    if q3_path.exists() and checks is not None:
        q3 = pd.read_csv(q3_path).set_index("outcome")
        fatal = q3.loc["fatal"] if "fatal" in q3.index else q3.iloc[0]
        audit = checks.decision.iloc[0]
        allowed = audit.startswith("DGT microdata may train")
        failing = ", ".join(checks.loc[~checks.passed, "check"]) or "none"
        artefact_text = ""
        if artefacts is not None:
            a = artefacts.iloc[0]
            artefact_text = (
                f"; which fields were left unrecorded alone ranks {a.target} at ROC-AUC "
                f"{a.roc_auc_unrecorded_flags_only:.3f} against {a.roc_auc_recorded_values:.3f} "
                "from the recorded values"
            )
        # An association analysis, not a predictive model: it is not compared with a table.
        beats_table, baseline, usefulness = None, "not compared", "an association model"
        rows.append(
            {
                "model": "dgt_crash_severity",
                "variant": "logistic regression with grouped, labelled predictors",
                "unit": "one DGT crash with victims",
                "target": "a death within 30 days",
                "source": "DGT crash microdata",
                "layer": layers.NATIONAL.title,
                "baseline": baseline,
                "ml": f"logistic regression: ROC-AUC {fatal.auc:.3f} on {fatal.test_years}; "
                f"n={int(fatal.test_crashes):,}, positives={int(fatal.test_events):,}",
                "test_roc_auc": float(fatal.auc),
                "test_n": int(fatal.test_crashes),
                "test_positives": int(fatal.test_events),
                "transfer_evidence": "not tested across sources",
                "highest_validated_level": 2,
                "highest_validated_level_name": LEVELS[2],
                "next_level_blocked_by": f"DGT microdata audit: failing checks {failing}"
                + artefact_text,
                "calibration": f"Brier skill {fatal.brier_skill:+.3f}",
                "usefulness": usefulness,
                "question_answered": "which recorded circumstances are associated with fatal "
                "outcomes in Spain's injury crashes, adjusting for each other",
                "question_not_answered": "a prediction for a new crash; any causal effect; "
                "whether an association reflects the road or the recording force",
                "decision": decide(
                    beats_chance=bool(fatal.auc > 0.5),
                    holds_later=True,
                    research=not allowed,
                    beats_table=beats_table,
                    calibrated=False,
                ),
            }
        )
    validation = TABLES_DIR / "forecast_validation.csv"
    if validation.exists():
        from dgt_stats import forecast

        val = pd.read_csv(validation)
        val = val[val.outcome.eq("deaths_all")]
        # The project's forecasting model is the Poisson regression the module selects
        # (forecast.CHOSEN); the trees are a disclosed comparator, not the model.
        chosen = val[val.family.eq("model") & val.method.eq(forecast.CHOSEN)]
        naive = val[val.family.eq("naive")]
        held = chosen[chosen.set.eq("holdout")]
        if not held.empty and naive.set.eq("holdout").any():
            c = held.iloc[0]
            best_naive = naive[naive.set.eq("holdout")].sort_values("rmse").iloc[0]
            beats = bool(c.rmse < best_naive.rmse)
            shock = chosen[chosen.set.eq("pandemic")]
            shock_naive = naive[naive.set.eq("pandemic")].sort_values("rmse")
            shock_text = (
                f"; in the lockdown years, scored apart, {shock.rmse.iloc[0]:.3f} against "
                f"{shock_naive.rmse.iloc[0]:.3f} for {shock_naive.method_label.iloc[0]}"
                if not shock.empty and not shock_naive.empty
                else ""
            )
            rows.append(
                {
                    "model": "dgt_monthly_deaths_forecast",
                    "variant": "Poisson regression, " + c.method_label,
                    "unit": "one month, Spain",
                    "target": "road deaths in the month (yearbook series)",
                    "source": "DGT yearbook series, CORES fuel",
                    "layer": layers.NATIONAL.title,
                    "baseline": f"{best_naive.method_label}: held-out error {best_naive.rmse:.3f}",
                    "ml": f"Poisson regression, {c.method_label}: held-out error {c.rmse:.3f} "
                    f"over {int(c.years)} ordinary years{shock_text}",
                    "test_roc_auc": math.nan,
                    "test_n": int(c.years),
                    "test_positives": math.nan,
                    "transfer_evidence": "not applicable (one national series)",
                    "highest_validated_level": 2,
                    "highest_validated_level_name": LEVELS[2],
                    "next_level_blocked_by": "one national series: no other domain",
                    "calibration": "not applicable (counts)",
                    "usefulness": (
                        "beats the naive forecasts on the held-out ordinary years"
                        if beats
                        else "does not beat last year's count on the held-out ordinary years"
                    )
                    + shock_text.replace("; in", ". In"),
                    "question_answered": "is a year's death count outside what the series' "
                    "normal variation predicts",
                    "question_not_answered": "why a change happened; any measure's effect",
                    "decision": decide(
                        beats_chance=True,
                        holds_later=True,
                        research=False,
                        beats_table=beats,
                        calibrated=True,
                    ),
                }
            )
    return rows


COLUMNS = (
    "model",
    "variant",
    "unit",
    "target",
    "source",
    "baseline",
    "ml",
    "transfer_evidence",
    "highest_validated_level_name",
    "usefulness",
    "decision",
)


def _md(frame: pd.DataFrame) -> str:
    head = "| " + " | ".join(frame.columns) + " |"
    sep = "|" + "---|" * len(frame.columns)
    body = []
    for row in frame.itertuples(index=False):
        cells = []
        for value in row:
            if isinstance(value, float):
                cells.append("" if math.isnan(value) else f"{value:.3f}")
            else:
                cells.append(str(value).replace("|", "/"))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([head, sep, *body])


def document(frame: pd.DataFrame) -> str:
    summary = frame[list(COLUMNS)].rename(
        columns={
            "model": "Model",
            "variant": "Variant",
            "unit": "Unit",
            "target": "Target",
            "source": "Source",
            "baseline": "Baseline",
            "ml": "ML",
            "transfer_evidence": "Transfer evidence",
            "highest_validated_level_name": "Highest validated level",
            "usefulness": "Usefulness",
            "decision": "Decision",
        }
    )
    lines = [
        "# Model decisions",
        "",
        "Generated by `python scripts/microdata.py validate`; do not edit by hand. The rules are",
        "declared in `src/dgt_stats/microdata/validation/decisions.py` before any result is read.",
        "",
        "For every model: does it provide useful information beyond a simple descriptive table,",
        "how far its evidence reaches, and what it does not answer. Possible decisions: "
        + "; ".join(OUTCOMES)
        + ". Only the first two are featured on the site as models.",
        "",
        "Levels: 1 same source, 2 later time, 3 another region, 4 another recording source, 5",
        "Spain nationally ([`GENERALISABILITY.md`](GENERALISABILITY.md)).",
        "",
        _md(summary),
        "",
    ]
    for row in frame.itertuples():
        lines += [
            f"## {row.model} ({row.variant})",
            "",
            f"- **Decision:** {row.decision}.",
            f"- **Unit / target / source:** {row.unit}; {row.target}; {row.source} ({row.layer}).",
            f"- **What it does:** {row.question_answered}.",
            f"- **Not answered:** {row.question_not_answered}.",
            f"- **Baseline:** {row.baseline}. **ML:** {row.ml}. **Usefulness:** {row.usefulness}.",
            f"- **Calibration:** {row.calibration}.",
            f"- **Transfer evidence:** {row.transfer_evidence}.",
            f"- **Highest validated level:** {row.highest_validated_level_name}; next level "
            f"blocked by: {row.next_level_blocked_by}.",
            "",
        ]
    return "\n".join(lines)


def run(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    frame = pd.DataFrame(source_rows(tables) + national_rows(tables))
    unknown = set(frame.decision) - set(OUTCOMES)
    if unknown:
        raise ValueError(f"decisions outside the declared outcomes: {unknown}")
    frame.to_csv(TABLES_DIR / "ml_model_decisions.csv", index=False)
    DOC.write_text(document(frame), encoding="utf-8")
    return {"ml_model_decisions": frame}
