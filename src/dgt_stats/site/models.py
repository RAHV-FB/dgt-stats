"""Crash severity: the model behind the calculator, how well its predictions match what happened,
the calculator itself, and the re-evaluation of every model the project fitted.

The page leads with predicted against observed outcomes on years the model had not seen, not
with a ranking score, and states what the model can and cannot answer before the calculator.
Every number is read from the ``sev_*`` and ``review_*`` tables, the calculator's options from
the exported model (``reports/models/severity_model.json``), and every qualitative sentence is
checked against them. The re-evaluation is ``docs/research/ML_MODEL_REVIEW.md``; the calculator's
model is ``docs/research/SEVERITY_CALCULATOR.md``.
"""

from __future__ import annotations

import json

import pandas as pd

from dgt_stats.paths import REPORTS_DIR
from dgt_stats.site.components import (
    DOCS_URL,
    _fmt_pct,
    downloads,
    esc,
    evidence_note,
    figure,
    key_result,
    limitation,
    read_table,
    render_page,
    summary,
    table,
    technical,
)

MODEL_PATH = REPORTS_DIR / "models" / "severity_model.json"
REVIEW_DOC = f"{DOCS_URL}/research/ML_MODEL_REVIEW.md"
CALCULATOR_DOC = f"{DOCS_URL}/research/SEVERITY_CALCULATOR.md"
# The inputs in the order the form asks for them, in two groups.
ROAD_INPUTS = ("road", "speed_limit", "junction", "lighting", "weather", "surface", "hour")
CRASH_INPUTS = ("crash_type", "units")
# The contrasts quoted as worked examples, each a change of one input from the reference crash.
EXAMPLES = (
    ("users", "heavy_vehicle", "A heavy vehicle (lorry or bus) involved as well as the car"),
    ("crash_type", "run_off_road", "The car ran off the road"),
    ("crash_type", "pedestrian_struck", "A pedestrian struck"),
    ("crash_type", "head_on", "A head-on collision"),
    ("hour", "22-23", "Between 22:00 and 23:59"),
    ("hour", "00-05", "Between 00:00 and 05:59"),
    ("lighting", "night_unlit", "At night on an unlit road"),
    ("junction", "junction", "Within a junction"),
    ("speed_limit", "40_50", "A posted limit of 40–50 km/h"),
    ("weather", "heavy_rain_snow", "In heavy rain, hail or snow"),
    ("road", "urban_street", "On an urban street"),
)


def _check(holds: bool, claim: str) -> None:
    if not holds:
        raise ValueError(f"models page: the tables no longer support: {claim}")


def _model() -> dict:
    with MODEL_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _select(name: str, spec: dict) -> str:
    options = "".join(
        f'<option value="{esc(level["value"])}"'
        f"{' selected' if level['value'] == spec['default'] else ''}>{esc(level['label'])}</option>"
        for level in spec["levels"]
    )
    return (
        f'<div class="calc-field"><label for="calc-{name}">{esc(spec["label"])}</label>'
        f'<select id="calc-{name}" name="{name}">{options}</select></div>'
    )


def _form(model: dict) -> str:
    inputs = model["inputs"]
    road = "".join(_select(name, inputs[name]) for name in ROAD_INPUTS)
    crash = "".join(_select(name, inputs[name]) for name in CRASH_INPUTS)
    users = inputs["users"]
    boxes = "".join(
        f'<li><label><input type="checkbox" name="users" value="{esc(level["value"])}"'
        f"{' checked' if level['value'] in users['default'] else ''}> {esc(level['label'])}"
        "</label></li>"
        for level in users["levels"]
    )
    return (
        '<section class="calculator" id="calculator" data-model="models/severity_model.json" '
        'aria-labelledby="calculator-title" hidden>'
        '<h3 id="calculator-title">Estimate the share for a crash</h3>'
        "<form>"
        f'<fieldset><legend>The road and the conditions</legend><div class="calc-fields">{road}'
        "</div></fieldset>"
        f'<fieldset><legend>The crash</legend><div class="calc-fields">{crash}</div></fieldset>'
        f'<fieldset><legend>{esc(users["label"])}</legend><ul class="calc-users">{boxes}</ul>'
        "</fieldset>"
        '<div class="calc-actions">'
        '<button type="button" data-keep>Keep this crash for comparison</button>'
        '<button type="button" data-clear hidden>Clear the comparison</button>'
        '<button type="reset">Reset the inputs</button></div>'
        "</form>"
        '<div class="calc-result" data-output aria-live="polite"></div>'
        '<div class="calc-baseline" data-baseline aria-live="polite"></div>'
        '<p class="visually-hidden" role="status" data-status></p>'
        "</section>"
        '<p id="calculator-fallback">The calculator needs JavaScript. Without it, the worked '
        "examples above give its estimates for typical crashes.</p>"
    )


def _pooled(scores: pd.DataFrame) -> str:
    """The subset that pools every evaluation year (written ``first-last`` in the table)."""
    return str(scores.subset[scores.subset.str.fullmatch(r"\d{4}-\d{4}")].iloc[0])


def _span_text(label: str, sep: str = "–") -> str:
    first, last = label.split("-")
    return f"{first}{sep}{last}"


def _scores_table(scores: pd.DataFrame) -> str:
    names = {
        "calculator": "The calculator's model (penalised logistic regression)",
        "boosted_trees": "Gradient-boosted trees, the same inputs",
        "road_x_crash_table": "A table: the fatal share by road and crash type",
    }
    span = _pooled(scores)
    pooled = scores[scores.subset == span].set_index("estimator")
    rows = [
        {
            "Estimator": label,
            "ROC-AUC": float(pooled.loc[name, "roc_auc"]),
            "Brier skill": float(pooled.loc[name, "brier_skill"]),
            "Calibration slope": float(pooled.loc[name, "calibration_slope"]),
            "Mean predicted": float(pooled.loc[name, "mean_predicted"]),
        }
        for name, label in names.items()
    ]
    observed = float(pooled.loc["calculator", "prevalence"])
    return table(
        pd.DataFrame(rows),
        f"Scores on the crashes of {_span_text(span)}, each year predicted by a model fitted only on the "
        f"years before it ({int(pooled.loc['calculator', 'n']):,} crashes, "
        f"{_fmt_pct(observed)} fatal). ROC-AUC is the chance that a fatal crash is ranked above "
        "a non-fatal one; Brier skill is the improvement in squared error over predicting the "
        "average for every crash; a calibration slope of 1 means the predictions spread as far as "
        "the outcomes.",
        {
            "ROC-AUC": "dec2",
            "Brier skill": "dec2",
            "Calibration slope": "dec2",
            "Mean predicted": "pct",
        },
    )


def _zone_table(scores: pd.DataFrame) -> str:
    span = _span_text(_pooled(scores))
    rows = []
    for subset, label in (
        ("zone: interurban", "Interurban roads"),
        ("zone: urban", "Urban streets"),
        ("zone: through_town", "Roads through towns"),
    ):
        row = scores[(scores.subset == subset) & (scores.estimator == "calculator")].iloc[0]
        rows.append(
            {
                "Zone": label,
                "Crashes": row.n,
                "Fatal": row.positives,
                "ROC-AUC": row.roc_auc,
                "Calibration slope": row.calibration_slope,
            }
        )
    return table(
        pd.DataFrame(rows),
        f"The model behind the calculator, by zone, {span}, each year predicted by a model fitted only on "
        "the years before it.",
        {"Crashes": "int", "Fatal": "int", "ROC-AUC": "dec2", "Calibration slope": "dec2"},
    )


def _examples_table(contrasts: pd.DataFrame, base: float) -> str:
    interurban = contrasts[contrasts.base == "interurban"].set_index(["input", "level"])
    rows = [
        {
            "The reference crash, changed in one respect": "(the reference crash)",
            "Predicted fatal share": f"{_fmt_pct(base)}",
            "Ratio to the reference (95% interval)": "1 (reference)",
        }
    ]
    for name, level, label in EXAMPLES:
        row = interurban.loc[(name, level)]
        rows.append(
            {
                "The reference crash, changed in one respect": label,
                "Predicted fatal share": (
                    f"{_fmt_pct(row.probability)} "
                    f"({_fmt_pct(row.probability_low)}–{_fmt_pct(row.probability_high)})"
                ),
                "Ratio to the reference (95% interval)": (
                    f"{row.ratio:.2f} ({row.ratio_low:.2f}–{row.ratio_high:.2f})"
                ),
            }
        )
    return table(
        pd.DataFrame(rows),
        "Worked examples: the predicted share of crashes that were fatal, among crashes with a "
        "death or serious injury. The reference crash is a side collision between two cars or vans on a "
        "conventional regional road, between junctions, in daylight, fine weather and on a dry "
        "surface, between 10:00 and 13:59, with no posted limit recorded; each row changes one "
        "input.",
    )


def _review_table(rolling: pd.DataFrame, barcelona: pd.DataFrame, forecast: pd.DataFrame) -> str:
    pooled = rolling[rolling.year.astype(str).str.fullmatch(r"\d{4}-\d{4}")].set_index("estimator")
    bcn = barcelona.set_index(["model", "estimator"])
    held = forecast[forecast.set == "holdout"].set_index(["method", "window"])
    published = held.loc[("month + trend + fuel + calendar (the published model)", 4)]
    naive = held.loc[("naive: same months last year", 1)]
    rows = [
        {
            "Model": "Catalan crash severity, original (boosted trees)",
            "Against its benchmark": (
                f"ROC-AUC {pooled.loc['boosted_trees', 'roc_auc']:.2f} against "
                f"{pooled.loc['type_x_zone_table', 'roc_auc']:.2f} for a type × zone table"
            ),
            "Decision": "Rebuilt as the calculator: its strongest predictor was a recording "
            "artefact (the road's owner, blank on some fatal records)",
        },
        {
            "Model": "Barcelona person severity (boosted trees)",
            "Against its benchmark": (
                f"ROC-AUC {bcn.loc[('barcelona_person_severity', 'boosted_trees'), 'roc_auc']:.2f}"
                f" against {bcn.loc[('barcelona_person_severity', 'table'), 'roc_auc']:.2f}, on "
                f"{int(bcn.loc[('barcelona_person_severity', 'table'), 'positives'])} serious or "
                "fatal cases"
            ),
            "Decision": "Research only: too few serious cases to publish probabilities",
        },
        {
            "Model": "Barcelona crash severity (logistic regression)",
            "Against its benchmark": (
                f"ROC-AUC {bcn.loc[('barcelona_crash_severity', 'logistic'), 'roc_auc']:.3f} "
                f"against {bcn.loc[('barcelona_crash_severity', 'table'), 'roc_auc']:.3f}"
            ),
            "Decision": "Removed: no gain over the table",
        },
        {
            "Model": "Monthly road deaths forecast (Poisson regression)",
            "Against its benchmark": (
                f"error {_fmt_pct(published.rmse)} of a year's deaths against "
                f"{_fmt_pct(naive.rmse)} for last year's count, in the ordinary held-out years"
            ),
            "Decision": "Removed: last year's count does better",
        },
        {
            "Model": "Catalan models on DGT or Barcelona variables",
            "Against its benchmark": "transfer tests, not predictions",
            "Decision": "Research only: see the external validation",
        },
        {
            "Model": "DGT crash severity (association model)",
            "Against its benchmark": "not compared",
            "Decision": "Research only: its coefficients describe police records",
        },
    ]
    return table(
        pd.DataFrame(rows),
        "Every predictive model the project fitted, re-evaluated on records it was not fitted on.",
    )


def page_severity_models(captions: dict[str, str]) -> str:
    model = _model()
    scores = read_table("sev_rolling_scores")
    comparison = read_table("sev_comparison").set_index(["estimator", "metric"])
    calibration = read_table("sev_calibration")
    contrasts = read_table("sev_contrasts")
    rolling = read_table("review_catalonia_rolling")
    barcelona = read_table("review_barcelona")
    forecast = read_table("review_forecast")

    span = _pooled(scores)
    first_test, last_test = span.split("-")
    pooled = scores[scores.subset == span].set_index("estimator")
    calc, trees, tab = (
        pooled.loc[n] for n in ("calculator", "boosted_trees", "road_x_crash_table")
    )
    calc_bands = calibration[calibration.estimator == "calculator"]
    years = scores[scores.subset.str.fullmatch(r"\d{4}") & (scores.estimator == "calculator")]
    base = float(contrasts[contrasts.base == "interurban"].base_probability.iloc[0])
    urban_base = float(contrasts[contrasts.base == "urban"].base_probability.iloc[0])
    interurban = contrasts[contrasts.base == "interurban"].set_index(["input", "level"])
    heavy = interurban.loc[("users", "heavy_vehicle")]
    gap = comparison.loc[("road_x_crash_table", "roc_auc_minus_calculator")]
    tree_gap = comparison.loc[("boosted_trees", "roc_auc_minus_calculator")]
    zones = scores[scores.estimator == "calculator"].set_index("subset")
    evaluation = model["evaluation"]

    _check(
        bool(
            (
                (calc_bands.mean_predicted >= calc_bands.observed_low)
                & (calc_bands.mean_predicted <= calc_bands.observed_high)
            ).all()
        ),
        "in every band the mean prediction lies inside the interval of the observed share",
    )
    _check(
        float(gap.high) < 0 and float(tree_gap.low) > 0 and float(tree_gap.high) < 0.02,
        "the model ranks better than the table, and the trees only slightly better than it",
    )
    _check(
        0.9 < float(calc.calibration_slope) < 1.1
        and abs(float(calc.mean_predicted) - float(calc.prevalence)) < 0.005,
        "the predictions are calibrated on the pooled years",
    )
    table_years = scores[
        scores.subset.str.fullmatch(r"\d{4}") & (scores.estimator == "road_x_crash_table")
    ].set_index("subset")
    _check(
        float(years.roc_auc.min()) > 0.7
        and bool((years.set_index("subset").roc_auc > table_years.roc_auc).all()),
        "the model holds in every year and ranks better than the table in each",
    )
    _check(
        float(zones.loc["zone: through_town", "roc_auc"]) < 0.65
        and float(zones.loc["zone: interurban", "roc_auc"]) > 0.74,
        "the model separates crashes well on interurban roads and barely on roads through towns",
    )
    _check(float(heavy.ratio_low) > 1.5, "a heavy vehicle roughly doubles the predicted share")
    _check(
        evaluation["crashes"] == int(calc.n) and evaluation["fatal"] == int(calc.positives),
        "the exported model's evaluation matches the table",
    )

    body = summary(
        "Among crashes in Catalonia with a death or a serious injury, a model fitted on the "
        f"{model['training']['crashes']:,} such crashes recorded in "
        f"{model['training']['years'][0]}–{model['training']['years'][1]} estimates which were "
        "fatal from the road, the conditions, the type of crash and the road users involved. Tested on each "
        f"year from {first_test} to {last_test} with a model fitted only on the years before it, its predictions "
        "matched what happened: across the range of predictions, the share of crashes that were "
        "fatal lay where the model put it. It separates fatal from serious crashes better than "
        "a table of the same records, though not by much, and well on interurban roads but "
        "barely in towns. The calculator below applies it to any crash a reader describes."
    )

    # ------------------------------------------------------------------- predicted and observed
    body += "<h2>Predicted and observed</h2>"
    body += figure(
        "sev1_predicted_observed",
        "Dot chart of the observed share of fatal crashes against the predicted probability, in "
        f"{len(calc_bands)} bands of prediction from under {_fmt_pct(calc_bands.band_high.min(), 0)} "
        f"to over {_fmt_pct(calc_bands.band_low.max(), 0)}, with 95% intervals. Every dot lies "
        "on or close to the diagonal where prediction equals observation.",
        captions,
    )
    body += (
        f"<p>The {int(calc.n):,} crashes of {_span_text(span)} are grouped by the probability the model "
        "gave each one, using in each year only a model fitted on earlier years. In every group "
        "the average prediction lies inside the 95% interval of the observed share of fatal "
        f"crashes. Over all the years the model predicted {_fmt_pct(calc.mean_predicted)} fatal "
        f"on average, against {_fmt_pct(calc.prevalence)} observed, and its calibration slope is "
        f"{float(calc.calibration_slope):.2f}: its predictions spread about as far as the "
        "outcomes do, so a predicted share can be read as the share of such crashes that were "
        "fatal.</p>"
    )

    # ------------------------------------------------------------------- separation
    body += "<h2>How well it separates fatal from serious crashes</h2>"
    body += key_result(
        f"{float(calc.roc_auc):.2f}",
        f"ROC-AUC of the calculator's model on the crashes of {_span_text(span)} predicted from earlier "
        f"years (95% interval {comparison.loc[('calculator', 'roc_auc'), 'low']:.2f}–"
        f"{comparison.loc[('calculator', 'roc_auc'), 'high']:.2f}), against "
        f"{float(tab.roc_auc):.2f} for a table of the fatal share by road and crash type.",
    )
    body += _scores_table(scores)
    body += (
        f"<p>The model ranks crashes better than the table in every year from {first_test} to "
        f"{last_test}. "
        "Gradient-boosted trees with the same inputs rank them slightly better again "
        f"({float(trees.roc_auc):.3f} against {float(calc.roc_auc):.3f}; the difference, "
        f"{float(tree_gap.low):.3f} to {float(tree_gap.high):.3f}, is small), but their "
        f"predictions spread too far (calibration slope {float(trees.calibration_slope):.2f}) "
        "and cannot be computed in a reader's browser from published coefficients, so the "
        "logistic model is the one published.</p>"
    )
    body += _zone_table(scores)
    body += (
        "<p>Most of the model's skill is on interurban roads. On urban streets few severe "
        f"crashes are fatal ({_fmt_pct(urban_base)} for the reference crash in town, against "
        f"{_fmt_pct(base)} on a regional road), and the model ranks them less well; on roads "
        "through towns it barely ranks them at all, and the calculator says so when one is "
        "chosen.</p>"
    )

    # ------------------------------------------------------------------- what it shows
    body += "<h2>What the model shows</h2>"
    body += (
        "<p>Changing one thing at a time from a reference crash shows which circumstances the "
        "records associate with a fatal outcome. The largest is a heavy vehicle: with a lorry or "
        f"bus involved, the predicted fatal share is {float(heavy.ratio):.2f} times that of the "
        f"same crash between cars ({float(heavy.ratio_low):.2f}–{float(heavy.ratio_high):.2f}). "
        "These are associations in police records, adjusted for the other inputs, not the effect "
        "of changing a road or a vehicle.</p>"
    )
    body += _examples_table(contrasts, base)
    body += evidence_note(
        "A posted speed limit is not a speed: the records hold the limit on the road, not how "
        "fast anyone drove. The conditions are those the police recorded at the scene."
    )

    # ------------------------------------------------------------------- calculator
    body += "<h2>The calculator</h2>"
    body += (
        "<p>Describe a crash, and the calculator gives the share of crashes like it that the "
        "model predicts were fatal, among crashes with a death or a serious injury, with a 95% "
        "interval and the number of recorded crashes that share its zone, type, road users and "
        "number involved. Keep one crash and change an input to compare two. It answers only "
        "that question: it cannot say how likely a crash is to happen, or whether someone will "
        "be hurt in it, because every record in the file is already a crash with a death or a "
        "serious injury.</p>"
    )
    body += _form(model)
    body += technical(
        "What the inputs mean and what is left out",
        "<p>Every input is information available before or at the moment of the crash: the "
        "road, its posted limit, the junction, the light, the weather, the surface, the hour, "
        "the type of crash and who was involved. Information recorded afterwards, such as the "
        "police's judgement of which factors influenced the crash, is left out: it is known only "
        "once the outcome is, so it would make the model look better without helping a "
        "prediction. Combinations the records do not contain are refused, and combinations "
        "with fewer than "
        f"{next(rule['threshold'] for rule in model['rules'] if rule['id'] == 'few_similar')} "
        "similar recorded crashes carry a warning. The arithmetic runs in the browser from the "
        "published coefficients and their covariance, and gives the same results as the "
        "project's Python code to ten decimal places.</p>",
    )

    # ------------------------------------------------------------------- every model
    body += "<h2>Every model the project fitted</h2>"
    body += (
        "<p>Each predictive model was refitted with independent code and scored against a "
        "simple table on records it had not been fitted on. The original Catalan model's gain "
        "rested partly on a recording artefact, so it was rebuilt as the calculator's model; "
        "the others were kept for research only or removed.</p>"
    )
    body += _review_table(rolling, barcelona, forecast)
    body += (
        "<p>The DGT association model is reported with the "
        '<a href="severity.html">crash circumstances</a>, and the transfer tests on the '
        '<a href="validation.html">external validation</a> page. The re-evaluation is set out in '
        f'<a href="{REVIEW_DOC}">the model review</a> and the calculator\'s model in '
        f'<a href="{CALCULATOR_DOC}">its documentation</a>.</p>'
    )

    body += limitation(
        f"The model describes Catalonia's records of {model['training']['years'][0]}–"
        f"{model['training']['years'][1]} and the crashes the Servei Català "
        "de Trànsit classifies as fatal (a death within 24 hours) or serious. Its inputs are "
        "police records, coded as recorded; a posted limit is not a speed, and a recorded "
        "condition is not a cause. On roads through towns its estimates are close to the "
        "average for such roads."
    )
    body += downloads(
        [
            ("sev_rolling_scores", "scores by year and zone"),
            ("sev_comparison", "paired differences between estimators"),
            ("sev_calibration", "predicted against observed, by band"),
            ("sev_contrasts", "one input changed at a time"),
            ("sev_marginal_adjusted", "raw and standardised shares"),
            ("sev_stability", "the contrasts on earlier and later years"),
            ("sev_coefficients", "coefficients and bootstrap standard errors"),
            ("sev_penalty", "choice of penalty"),
            ("review_catalonia_rolling", "re-evaluation: Catalonia, rolling years"),
            ("review_catalonia_2023", "re-evaluation: Catalonia, the original test year"),
            ("review_barcelona", "re-evaluation: Barcelona models"),
            ("review_forecast", "re-evaluation: monthly deaths forecast"),
            ("ml_selected", "original models as published"),
            ("ml_missingness", "original models: missing values"),
            ("ml_transport_reweighting", "original models: reweighted transfer"),
        ],
        method=(CALCULATOR_DOC, "how the calculator's model was built and checked"),
    )
    return render_page(
        "severity-models",
        "Crash severity model and calculator",
        "Which crashes with a death or serious injury in Catalonia were fatal: how well a model "
        "predicts it on years it had not seen, and a calculator that applies it to any crash.",
        body,
        head='\n<script src="models/severity-engine.js" defer></script>'
        '\n<script src="models/severity-calculator.js" defer></script>',
    )
