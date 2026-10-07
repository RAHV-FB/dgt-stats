"""Which models genuinely work, for what, and which are kept: the model decision table.

The question for every model: *what real decision or analytical problem does it improve over a
descriptive table?* Each row is filled from the result tables of the same run; the decision
follows rules declared here, before any result is read:

* a source model is kept as a **primary model** when it adds signal over its descriptive lookup
  table (:mod:`dgt_stats.microdata.ml.rules`) and passes stage 2 of the outward path (later years
  or months);
* a model that does not beat its table is **replaced by the table**: the site shows the table,
  and the model stays in the repository only as a diagnostic;
* a model restricted to the variables another source shares is a **validation instrument**: it
  exists to test transfer, and is not presented as a model of its own;
* a variant that uses information recorded after the event (causes, "influence" judgements) is
  a **diagnostic**: it shows what the record adds afterwards, never a predictor;
* a model on the DGT microdata is used for prediction only if the DGT microdata audit allows it;
  otherwise it describes associations, with the recording-regime terms flagged;
* the monthly deaths forecast is kept when its chosen method beats the naive comparators on the
  held-out years.

Writes ``reports/tables/ml_model_decisions.csv`` and ``docs/MODEL_DECISIONS.md``.
"""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import layers
from dgt_stats.paths import DOCS_DIR, TABLES_DIR

DOC = DOCS_DIR / "MODEL_DECISIONS.md"

SOURCE_MODELS = {
    "catalonia_crash_severity": {
        "observation": "one Catalan crash with a death or serious injury",
        "target": "fatal (a death) rather than serious",
        "source": "Servei Català de Trànsit, 2010-2023",
        "layer": layers.CATALONIA.title,
        "question": "which recorded road, crash and environmental circumstances are associated "
        "with a fatal rather than a serious outcome, beyond the crash type and zone alone",
        "not_answered": "whether a crash happens; risk per trip or kilometre; any causal effect; "
        "crashes with only slight injuries",
    },
    "barcelona_person_severity": {
        "observation": "one person recorded in a Barcelona crash",
        "target": "serious or fatal injury",
        "source": "Guàrdia Urbana, 2025",
        "layer": layers.BARCELONA.title,
        "question": "which recorded people (road role, vehicle, age, sex) and crash circumstances "
        "concentrate serious and fatal injuries, beyond road role and vehicle alone",
        "not_answered": "anyone's risk per trip; the behaviour of a person (causes have no person "
        "key); other cities or years",
    },
    "barcelona_crash_severity": {
        "observation": "one Barcelona crash",
        "target": "a serious or fatal injury in the crash",
        "source": "Guàrdia Urbana, 2025",
        "layer": layers.BARCELONA.title,
        "question": "which recorded crash circumstances distinguish serious-or-fatal crashes, "
        "beyond the accident type alone",
        "not_answered": "anyone's risk per trip; the behaviour of a person; other cities or "
        "years",
    },
    "catalonia_common_dgt": {
        "observation": "one Catalan crash with a death or serious injury",
        "target": "fatal (a death within 24 hours) rather than serious",
        "source": "Servei Català de Trànsit, restricted to the variables DGT records alike",
        "layer": layers.VALIDATION.title,
        "question": "does a Catalan model keep its ranking on crashes recorded elsewhere in Spain",
        "not_answered": "anything the full Catalan model answers (it drops most variables)",
    },
    "catalonia_common_bcn": {
        "observation": "one Catalan crash with a death or serious injury",
        "target": "fatal rather than serious",
        "source": "Servei Català de Trànsit, restricted to the variables Barcelona records alike",
        "layer": layers.VALIDATION.title,
        "question": "does a Catalan model keep its ranking on Barcelona's crashes",
        "not_answered": "a fatal-against-serious benchmark on Barcelona 2025 (too few fatal "
        "crashes)",
    },
}
RETROSPECTIVE = {
    "catalonia_crash_severity": "retrospective_administrative",
    "barcelona_person_severity": "retrospective",
    "barcelona_crash_severity": "retrospective",
}


def _path_summary(path: pd.DataFrame, model: str) -> tuple[str, str, str, int]:
    part = path[path.model.eq(model)].set_index("stage")
    works = [
        f"stage {s} ({part.loc[s, 'stage_name']})"
        for s in part.index
        if part.loc[s, "status"] == "passed"
    ]
    fails = [
        f"stage {s}: {part.loc[s, 'status']}"
        for s in part.index
        if part.loc[s, "status"] != "passed"
    ]
    return (
        "; ".join(works) or "no stage passed",
        "; ".join(fails) or "none",
        str(part.verdict.iloc[0]),
        int(part.highest_consecutive_stage.iloc[0]),
    )


def _transfer(transport: pd.DataFrame, model: str, estimator: str) -> str:
    part = transport[
        transport.model.eq(model)
        & transport.estimator.eq(estimator)
        & transport.transfer_gap.notna()
        & transport.status.eq("reported")
    ]
    if part.empty:
        return "no transfer test with an in-domain reference"
    return "; ".join(
        f"{r.experiment}: {r.roc_auc:.3f} against in-domain {r.in_domain_cv_roc_auc:.3f} "
        f"(gap {r.transfer_gap:+.3f})"
        for r in part.itertuples()
    )


def source_rows(tables: dict[str, pd.DataFrame]) -> list[dict]:
    selected = tables["ml_selected"]
    rules = tables["ml_rule_comparison"].set_index("model")
    path = tables["ml_outward_path"]
    transport = tables["ml_transport_validation"]
    rows = []
    for model, spec in SOURCE_MODELS.items():
        primary = selected[selected.model.eq(model) & selected.primary].iloc[0]
        works, fails, verdict, highest = _path_summary(path, model)
        calibration = (
            f"slope {primary.calibration_slope:.2f}, mean predicted {primary.mean_predicted:.3f} "
            f"against {primary.prevalence:.3f}: "
            + (
                "probabilities usable as estimates"
                if primary.probabilities_shown_as_estimates
                else "ranking only"
            )
        )
        base = {
            "model": model,
            "variant": primary.feature_set,
            **{k: spec[k] for k in ("observation", "target", "source", "layer")},
            "question_answered": spec["question"],
            "question_not_answered": spec["not_answered"],
            "test_roc_auc": float(primary.roc_auc),
            "test_n": int(primary.n),
            "test_positives": int(primary.positives),
            "works_where": works,
            "fails_or_untested": fails,
            "outward_path": verdict,
            "highest_stage": highest,
            "calibration": calibration,
            "transfer": _transfer(transport, model, primary.estimator),
        }
        if model in rules.index:
            r = rules.loc[model]
            adds = bool(r.model_adds_signal_over_table)
            base["over_descriptive_table"] = (
                f"ROC-AUC {r.model_roc_auc:.3f} against {r.rule_roc_auc:.3f} for the table of "
                f"{r.rule} (gain {r.roc_auc_gain:+.3f}, {r.roc_auc_gain_low:+.3f} to "
                f"{r.roc_auc_gain_high:+.3f}): "
                + ("adds signal" if adds else "does not add signal")
            )
            stage2 = path[path.model.eq(model) & path.stage.eq(2)].status.iloc[0]
            if adds and stage2 == "passed":
                keep = "keep: primary model"
                reason = "beats its descriptive table and holds on later, unseen records"
                use = (
                    "rank recorded profiles for closer analysis, beside the table that shows each N"
                )
            elif not adds:
                keep = "replace with the descriptive table"
                reason = (
                    "no measurable gain over the lookup table; the model stays only as a diagnostic"
                )
                use = "none beyond the table"
            else:
                keep = "keep as a diagnostic"
                reason = "beats the table but does not hold on later records"
                use = "diagnostic only"
        else:
            base["over_descriptive_table"] = "not applicable (a validation instrument)"
            keep = "keep as a validation instrument"
            reason = "exists to test transfer across sources; not presented as a model of its own"
            use = "testing whether associations learned in Catalonia hold elsewhere"
        rows.append({**base, "real_use": use, "keep": keep, "reason": reason})
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
                        "question_answered": "how much the information recorded after the event "
                        "(causes, 'influence' judgements, documentation completeness) adds",
                        "test_roc_auc": float(rr.roc_auc),
                        "over_descriptive_table": f"ROC-AUC {rr.roc_auc:.3f} against "
                        f"{primary.roc_auc:.3f} for the primary model",
                        "real_use": "diagnostic of the record, never a predictor",
                        "keep": "keep as a diagnostic",
                        "reason": "uses information recorded after the event",
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
        decision = checks.decision.iloc[0]
        allowed = decision.startswith("DGT microdata may train")
        failing = ", ".join(checks.loc[~checks.passed, "check"]) or "none"
        artefact_text = ""
        if artefacts is not None:
            a = artefacts.iloc[0]
            artefact_text = (
                f"; a model of which fields were left unrecorded alone reaches ROC-AUC "
                f"{a.roc_auc_unrecorded_flags_only:.3f} against {a.roc_auc_recorded_values:.3f} "
                f"({a.target})"
            )
        rows.append(
            {
                "model": "dgt_crash_severity",
                "variant": "logistic regression with grouped, labelled predictors",
                "observation": "one DGT crash with victims",
                "target": "a death within 30 days (and, separately, a serious injury)",
                "source": "DGT crash microdata",
                "layer": layers.NATIONAL.title,
                "question_answered": "which recorded circumstances are associated with fatal "
                "outcomes in Spain's injury crashes, adjusting for each other",
                "question_not_answered": "a calibrated prediction for a new crash; any causal "
                "effect; whether an association reflects the road or the recording force",
                "test_roc_auc": float(fatal.auc),
                "test_n": int(fatal.test_crashes),
                "test_positives": int(fatal.test_events),
                "over_descriptive_table": "not compared (an association model)",
                "works_where": f"later years {fatal.test_years}",
                "fails_or_untested": f"DGT microdata audit, failing checks: {failing}"
                + artefact_text,
                "outward_path": "national records, but recording differs by province",
                "highest_stage": math.nan,
                "calibration": f"Brier skill {fatal.brier_skill:+.3f}",
                "transfer": "not applicable",
                "real_use": "describe associations with the recording-regime levels flagged",
                "keep": "keep as a description of associations, not as a predictive model"
                if not allowed
                else "keep",
                "reason": decision,
            }
        )
    selection = TABLES_DIR / "forecast_selection.csv"
    validation = TABLES_DIR / "forecast_validation.csv"
    if selection.exists() and validation.exists():
        sel = pd.read_csv(selection)
        val = pd.read_csv(validation)
        chosen = sel[sel.chosen & sel.set.eq("holdout") & sel.outcome.eq("deaths_all")]
        naive = val[val.family.eq("naive") & val.set.eq("holdout") & val.outcome.eq("deaths_all")]
        if not chosen.empty and not naive.empty:
            c = chosen.iloc[0]
            best_naive = naive.sort_values("rmse").iloc[0]
            beats = bool(c.rmse < best_naive.rmse)
            rows.append(
                {
                    "model": "dgt_monthly_deaths_forecast",
                    "variant": c.method_label,
                    "observation": "one month, Spain",
                    "target": "road deaths in the month (yearbook series)",
                    "source": "DGT yearbook series, CORES fuel, Ministry toll traffic",
                    "layer": layers.NATIONAL.title,
                    "question_answered": "is a year's death count outside what the series' "
                    "normal variation predicts",
                    "question_not_answered": "why a change happened; any measure's effect",
                    "test_roc_auc": math.nan,
                    "test_n": int(c.years),
                    "test_positives": math.nan,
                    "over_descriptive_table": f"held-out error {c.rmse:.3f} against "
                    f"{best_naive.rmse:.3f} for {best_naive.method_label}",
                    "works_where": f"{int(c.years)} held-out years",
                    "fails_or_untested": "pandemic years (separate set)",
                    "outward_path": "national series: no transfer question",
                    "highest_stage": math.nan,
                    "calibration": "not applicable (counts)",
                    "transfer": "not applicable",
                    "real_use": "flag years whose deaths depart from the expected range",
                    "keep": "keep" if beats else "replace with the naive comparator",
                    "reason": "beats the naive comparators on held-out years"
                    if beats
                    else "does not beat a naive comparator",
                }
            )
    return rows


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
    summary = frame[
        ["model", "variant", "observation", "target", "source", "real_use", "outward_path", "keep"]
    ]
    lines = [
        "# Model decisions",
        "",
        "Generated by `python scripts/microdata.py validate`; do not edit by hand. The rules are",
        "declared in `src/dgt_stats/microdata/validation/decisions.py` before any result is read.",
        "",
        "For every model: what real decision or analytical problem does it improve over a",
        "descriptive table, where it works, where it fails, whether its probabilities can be read",
        "as estimates, and whether it transfers.",
        "",
        _md(summary),
        "",
    ]
    for row in frame.itertuples():
        lines += [
            f"## {row.model} ({row.variant})",
            "",
            f"- **Decision:** {row.keep}. {row.reason}.",
            f"- **Observation / target / source:** {row.observation}; {row.target}; {row.source} "
            f"({row.layer}).",
            f"- **Question answered:** {row.question_answered}.",
            f"- **Not answered:** {row.question_not_answered}.",
            f"- **Over a descriptive table:** {row.over_descriptive_table}.",
            f"- **Works:** {row.works_where}.",
            f"- **Fails or untested:** {row.fails_or_untested}.",
            f"- **Calibration:** {row.calibration}.",
            f"- **Transfer:** {row.transfer}.",
            f"- **Outward path:** {row.outward_path}.",
            "",
        ]
    return "\n".join(lines)


def run(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    frame = pd.DataFrame(source_rows(tables) + national_rows(tables))
    frame.to_csv(TABLES_DIR / "ml_model_decisions.csv", index=False)
    DOC.write_text(document(frame), encoding="utf-8")
    return {"ml_model_decisions": frame}
