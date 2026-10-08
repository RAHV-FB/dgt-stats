"""Crash severity: whether a model can tell which serious crashes were fatal, and a calculator.

The page answers its question in the order a reader asks it: does the model's estimate match what
happened on years it had not seen (predicted against observed, with a simple table beside it),
what that means in plain words, the calculator, what the model shows about circumstances, and a
short account of how it was built and tested. Scores tables and the inventory of every model the
project fitted are in the research documents, not here.

Every number is read from the ``sev_*`` tables and the exported model
(``reports/models/severity_model.json``), and every qualitative sentence is checked against them.
The model is ``docs/research/SEVERITY_CALCULATOR.md``; the re-evaluation of every model is
``docs/research/ML_MODEL_REVIEW.md``.
"""

from __future__ import annotations

import json

import pandas as pd

from dgt_stats.paths import REPORTS_DIR
from dgt_stats.severity_model import TRAIN_LAST_YEAR, VALIDATION_YEARS
from dgt_stats.site.components import (
    DOCS_URL,
    _fmt_pct,
    downloads,
    esc,
    evidence_note,
    figure,
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
ROAD_INPUTS = (
    "province",
    "road",
    "speed_limit",
    "junction",
    "lighting",
    "weather",
    "surface",
    "hour",
)
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
ZONE_SUBSETS = {
    "interurban": "zone: interurban",
    "urban": "zone: urban",
    "through_town": "zone: through_town",
}


def _check(holds: bool, claim: str) -> None:
    if not holds:
        raise ValueError(f"models page: the tables no longer support: {claim}")


def _model() -> dict:
    with MODEL_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _in_100(auc: float) -> str:
    """ROC-AUC as 'times in 100': how often a fatal crash gets the higher estimate."""
    return f"{round(100 * float(auc))}"


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
        f'data-model-id="{esc(model["model_id"])}" aria-labelledby="calculator-title" hidden>'
        '<h3 id="calculator-title">Describe a crash</h3>'
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
        '<div class="calc-result" data-output></div>'
        '<div class="calc-baseline" data-baseline></div>'
        '<p class="visually-hidden" role="status" aria-live="polite" data-status></p>'
        "</section>"
        '<p id="calculator-fallback">The calculator needs JavaScript. Without it, the worked '
        "examples below give the model's estimates for typical crashes.</p>"
    )


def _pooled(scores: pd.DataFrame) -> str:
    """The subset that pools every evaluation year (written ``first-last`` in the table)."""
    return str(scores.subset[scores.subset.str.fullmatch(r"\d{4}-\d{4}")].iloc[0])


def _fifth(groups: pd.DataFrame, top: bool) -> float:
    """Observed fatal share in the fifth of crashes rated most (or least) likely to be fatal."""
    ordered = groups.sort_values("group")
    part = ordered.tail(2) if top else ordered.head(2)
    return float(part.positives.sum() / part.n.sum())


def _examples_table(contrasts: pd.DataFrame, base: float) -> str:
    interurban = contrasts[contrasts.base == "interurban"].set_index(["input", "level"])
    rows = [
        {
            "The reference crash, changed in one respect": "(the reference crash)",
            "Estimated fatal share (95% confidence interval)": f"{_fmt_pct(base)}",
            "Times the reference (95% confidence interval)": "1",
        }
    ]
    for name, level, label in EXAMPLES:
        row = interurban.loc[(name, level)]
        rows.append(
            {
                "The reference crash, changed in one respect": label,
                "Estimated fatal share (95% confidence interval)": (
                    f"{_fmt_pct(row.probability)} "
                    f"({_fmt_pct(row.probability_low)}–{_fmt_pct(row.probability_high)})"
                ),
                "Times the reference (95% confidence interval)": (
                    f"{row.ratio:.2f} ({row.ratio_low:.2f}–{row.ratio_high:.2f})"
                ),
            }
        )
    return table(
        pd.DataFrame(rows),
        "Estimated share of crashes that were fatal, among crashes with a death or serious "
        "injury. The reference crash is a side or angle collision between two cars or "
        "vans on a conventional regional road in the province of Barcelona, between junctions, "
        "in daylight, fine weather and "
        "on a dry surface, between 10:00 and 13:59, with no posted limit recorded; each row "
        "changes one input. The calculator gives the same numbers.",
    )


def page_severity_models(captions: dict[str, str]) -> str:
    model = _model()
    scores = read_table("sev_rolling_scores")
    comparison = read_table("sev_comparison").set_index(["estimator", "metric"])
    calibration = read_table("sev_calibration")
    contrasts = read_table("sev_contrasts")
    geography = read_table("sev_geography").set_index(["test", "estimator"])
    penalty = read_table("sev_penalty")
    stability = read_table("sev_stability")
    stability = stability[stability.base == "interurban"].set_index(["subset", "input", "level"])

    span = _pooled(scores)
    first_test, last_test = span.split("-")
    pooled = scores[scores.subset == span].set_index("estimator")
    calc, trees, tab = (
        pooled.loc[n] for n in ("calculator", "boosted_trees", "road_x_crash_table")
    )
    model_groups = calibration[calibration.estimator == "calculator"].sort_values("group")
    table_groups = calibration[calibration.estimator == "road_x_crash_table"]
    by_subset = scores.set_index(["subset", "estimator"])
    years = scores[scores.subset.str.fullmatch(r"\d{4}") & (scores.estimator == "calculator")]
    table_years = scores[
        scores.subset.str.fullmatch(r"\d{4}") & (scores.estimator == "road_x_crash_table")
    ].set_index("subset")
    base = float(contrasts[contrasts.base == "interurban"].base_probability.iloc[0])
    interurban = contrasts[contrasts.base == "interurban"].set_index(["input", "level"])
    heavy = interurban.loc[("users", "heavy_vehicle")]
    junction = interurban.loc[("junction", "junction")]
    gap = comparison.loc[("road_x_crash_table", "roc_auc_minus_calculator")]
    tree_gap = comparison.loc[("boosted_trees", "roc_auc_minus_calculator")]
    evaluation = model["evaluation"]
    zone = {key: by_subset.loc[(subset, "calculator")] for key, subset in ZONE_SUBSETS.items()}
    city = by_subset.loc[("Barcelona city, urban streets", "calculator")]
    outside = by_subset.loc[("urban streets outside Barcelona city", "calculator")]
    last_year = by_subset.loc[(last_test, "calculator")]
    last_table = by_subset.loc[(last_test, "road_x_crash_table")]
    inside = (model_groups.mean_predicted >= model_groups.observed_low) & (
        model_groups.mean_predicted <= model_groups.observed_high
    )
    outliers = model_groups[~inside]
    tests = geography.index.get_level_values(0)
    estimators = geography.index.get_level_values(1)
    province = geography.loc[("Barcelona from the other demarcations", "calculator")]
    other_provinces = geography[
        tests.str.endswith("from the other demarcations")
        & (estimators == "calculator")
        & ~tests.str.startswith("Barcelona")
    ]
    training = model["training"]
    flat = float(penalty.validation_log_loss.max() - penalty.validation_log_loss.min())

    slope = float(calc.calibration_slope)
    _check(
        0.8 < slope < 1.25 and abs(float(calc.mean_predicted) - float(calc.prevalence)) < 0.005,
        "the estimates are calibrated on the pooled years, within the project's rule",
    )
    _check(int(inside.sum()) >= len(model_groups) - 1, "all but at most one group is inside")
    _check(float(gap.high) < 0, "the model ranks crashes better than the table")
    _check(float(tree_gap.high) < 0.03, "the trees rank no more than slightly better")
    trees_compared = "a little better" if float(tree_gap.low) > 0 else "about as well"
    _check(
        bool((years.set_index("subset").roc_auc > table_years.roc_auc).all()),
        "the model ranks better than the table in every year",
    )
    _check(
        float(zone["through_town"].roc_auc) < 0.62
        and float(zone["through_town"].calibration_slope) < 0.8,
        "the model cannot rank crashes on roads through towns",
    )
    _check(
        float(zone["interurban"].roc_auc) > float(zone["urban"].roc_auc) > 0.62,
        "the model ranks interurban crashes best, urban ones less well",
    )
    _check(float(heavy.ratio_low) > 1.5, "a heavy vehicle roughly doubles the estimated share")
    _check(float(junction.ratio_high) < 1, "a junction goes with a lower share")

    def held(input_: str, level: str) -> tuple[float, float]:
        """The ratio in each period (the first two subsets of the stability table)."""
        periods = [s for s in stability.index.get_level_values(0).unique() if s[:1].isdigit()]
        return tuple(float(stability.loc[(s, input_, level), "ratio"]) for s in periods[:2])

    heavy_periods = held("users", "heavy_vehicle")
    junction_periods = held("junction", "junction")
    rain_periods = held("weather", "heavy_rain_snow")
    limit_periods = held("speed_limit", "40_50")
    _check(
        min(heavy_periods) > 1.5 and max(junction_periods) < 1,
        "the heavy-vehicle and junction associations hold in both periods",
    )
    _check(
        (min(rain_periods) < 1 < max(rain_periods))
        and abs(limit_periods[0] - limit_periods[1]) > 0.1,
        "the heavy-rain and posted-limit associations change between periods",
    )
    _check(
        float(outside.mean_predicted) > float(outside.prevalence),
        "estimates on urban streets outside Barcelona city run high",
    )
    _check(
        float(province.mean_predicted) > float(province.prevalence)
        and float(province.roc_auc) < float(other_provinces.roc_auc.min()),
        "fitted on the other provinces, the model ranks Barcelona province's crashes least well "
        "and overstates their fatal share",
    )
    _check(
        evaluation["crashes"] == int(calc.n) and evaluation["fatal"] == int(calc.positives),
        "the exported model's evaluation matches the table",
    )
    _check(flat < 0.001, "the choice of penalty barely changes the validation loss")

    top, bottom = _fifth(model_groups, True), _fifth(model_groups, False)
    top_table, bottom_table = _fifth(table_groups, True), _fifth(table_groups, False)
    _check(top > top_table and bottom < bottom_table, "the model separates the extremes better")
    low_group, high_group = model_groups.iloc[4], model_groups.iloc[-3]

    body = summary(
        "Of the crashes in Catalonia in which someone was killed or seriously injured, a model "
        "estimates which were fatal (someone died within 24 hours) from the road, the "
        "conditions, the type of crash and who was involved. Tested on each year from "
        f"{first_test} to {last_test} with a model fitted only on earlier years, its estimates "
        "matched what happened, and it sorted crashes into more and less deadly groups "
        "somewhat better than a table of fatal shares by road and crash type. It cannot say "
        "whether a crash will happen, only how often crashes like a given one were fatal."
    )

    # ------------------------------------------------------------------- predicted and observed
    body += "<h2>Predicted and observed</h2>"
    body += figure(
        "sev1_predicted_observed",
        "Dot chart of the observed share of fatal crashes against the predicted chance, in ten "
        "equal groups for the model (filled dots) and for a table by road and crash type (hollow "
        f"dots). The model's groups run from about {_fmt_pct(model_groups.observed.min(), 0)} "
        f"to {_fmt_pct(model_groups.observed.max(), 0)} fatal, the table's from about "
        f"{_fmt_pct(table_groups.observed.min(), 0)} to "
        f"{_fmt_pct(table_groups.observed.max(), 0)}; both follow the diagonal on which "
        "prediction equals observation.",
        captions,
    )
    exception_text = ""
    if len(outliers):
        exception = outliers.iloc[0]
        exception_text = (
            " The exception is one group in which the model said "
            f"{_fmt_pct(exception.mean_predicted)} and {_fmt_pct(exception.observed)} were fatal."
        )
    body += (
        f"<p>The test covers the {int(calc.n):,} crashes of {first_test}–{last_test} on the roads "
        "the calculator offers, each year predicted by a model that had seen only earlier "
        f"years. Over all of them the model estimated {_fmt_pct(calc.mean_predicted)} fatal, and "
        f"{_fmt_pct(calc.prevalence)} were. Its estimates can be read roughly at face value: "
        f"where it said about {_fmt_pct(low_group.mean_predicted, 0)}, "
        f"{_fmt_pct(low_group.observed, 0)} of the crashes were fatal, and where it said about "
        f"{_fmt_pct(high_group.mean_predicted, 0)}, {_fmt_pct(high_group.observed, 0)} "
        f"were.{exception_text}"
        + (
            " The estimates were a little too cautious: the crashes it rated most and least "
            "likely to be fatal turned out somewhat more extreme than it said."
            if slope > 1.05
            else ""
        )
        + "</p>"
        "<p>Of the fifth of crashes the model rated most likely to have been fatal, "
        f"{_fmt_pct(top, 0)} were; of the fifth it rated least likely, {_fmt_pct(bottom, 0)}. "
        f"The table separates them less ({_fmt_pct(top_table, 0)} and "
        f"{_fmt_pct(bottom_table, 0)}). Put another way, given one fatal and one non-fatal "
        f"crash, the model gives the fatal one the higher estimate {_in_100(calc.roc_auc)} "
        f"times in 100, and the table {_in_100(tab.roc_auc)} times. The model does better than "
        f"the table in every year from {first_test} to {last_test}. The gain is real but "
        "modest: most of what these records can tell is in the road and the type of "
        "crash.</p>"
        "<p>The model works best on interurban roads "
        f"({_in_100(zone['interurban'].roc_auc)} times in 100) and less well on urban streets "
        f"({_in_100(zone['urban'].roc_auc)}). On roads through towns it cannot tell more and "
        f"less deadly crashes apart ({_in_100(zone['through_town'].roc_auc)}), so the "
        "calculator shows the average for such roads instead of an estimate. On urban streets "
        "outside Barcelona city its estimates ran somewhat high "
        f"({_fmt_pct(outside.mean_predicted)} against {_fmt_pct(outside.prevalence)} fatal); "
        f"in Barcelona city they were close ({_fmt_pct(city.mean_predicted)} against "
        f"{_fmt_pct(city.prevalence)}).</p>"
    )

    # ------------------------------------------------------------------- calculator
    few = next(rule["threshold"] for rule in model["rules"] if rule["id"] == "few_similar")
    body += "<h2>Try the model</h2>"
    body += (
        "<p>Describe a crash in which someone was killed or seriously injured, and the "
        "calculator gives the model's estimate of the share of such crashes that were fatal, "
        "with a 95% confidence interval and, beside it, the share for all crashes on the same "
        "kind of road. To compare two crashes, press “Keep this crash for comparison” and change "
        "one input. Three impossible combinations, such as a pedestrian struck with no "
        f"pedestrian involved, are refused; combinations with fewer than {few} similar recorded "
        "crashes, including none, still get an estimate, with a warning that it rests on the "
        "model's assumptions.</p>"
    )
    body += _form(model)
    body += technical(
        "What the inputs mean and what is left out",
        "<p>Every input is something the police record about the road, the conditions or the "
        "crash. The road is the zone and type of road and, for conventional roads, the network "
        "that owns it. The posted limit is the signposted limit where the record gives one, "
        "never a vehicle's speed; most records give none, and the road's generic limit "
        "applies. “Vehicles and pedestrians involved” counts every vehicle and every "
        "pedestrian. Information recorded only after the crash, such as the police's judgement "
        "of which factors influenced it, is left out: it is written once the outcome is known, "
        "so it would flatter the model without helping anyone predict.</p>",
    )

    # ------------------------------------------------------------------- what it shows
    body += "<h2>What the model shows</h2>"
    body += (
        "<p>Starting from a typical crash on a regional road and changing one thing at a time "
        "shows which circumstances the records associate with a fatal outcome. The largest "
        "increase comes with a heavy vehicle: with a lorry or bus involved, the estimated fatal "
        f"share is {float(heavy.ratio):.2f} times that of the same crash between cars "
        f"({float(heavy.ratio_low):.2f}–{float(heavy.ratio_high):.2f}). A crash within a "
        f"junction carries {float(junction.ratio):.2f} times the share of one between "
        "junctions. These two hold in models fitted separately on the earlier and the later "
        "half of the years; others do not, and should not be read as settled: heavy rain goes "
        f"with {rain_periods[0]:.2f} times the share in the first half and {rain_periods[1]:.2f} "
        "in the second, a posted 40–50 km/h limit with "
        f"{limit_periods[0]:.2f} and {limit_periods[1]:.2f}.</p>"
    )
    body += _examples_table(contrasts, base)
    body += evidence_note(
        "These compare crashes that had already killed or seriously injured someone. A smaller "
        "fatal share in heavy rain or at a junction does not mean that rain or junctions are "
        "safer: they may bring more crashes, slower and less often fatal. A posted limit is not "
        "a speed. Each figure is an association in police records, adjusted for the other "
        "inputs, not the effect of changing a road or a vehicle."
    )

    # ------------------------------------------------------------------- method
    body += "<h2>How it was built and tested</h2>"
    body += (
        f"<p>The model is a logistic regression fitted to the {training['crashes']:,} crashes "
        f"of {training['years'][0]}–{training['years'][1]} in the Servei Català de Trànsit's "
        "file. It has a starting level for each zone (urban street, road through a town, "
        "interurban road) in each province, and one effect for each other input, the same on "
        "every kind of road. "
        f"{training['excluded_owner_not_recorded']:,} crashes on conventional roads whose owner "
        "is recorded as “other” or left blank are left out: a blank owner is far commoner on "
        "fatal records and “other” on non-fatal ones, so the field records how a crash was "
        "documented, not the road. The strength "
        "of the penalty that keeps the estimates stable was chosen from "
        f"{penalty.shape[0]} values by fitting on {training['years'][0]}–{TRAIN_LAST_YEAR} and "
        f"scoring {VALIDATION_YEARS[0]}–{VALIDATION_YEARS[-1]}, years that are also in the "
        f"test; the choice made almost no difference, and on {last_test}, which "
        "played no part in it, the model gave the fatal crash the higher estimate "
        f"{_in_100(last_year.roc_auc)} times in 100 against {_in_100(last_table.roc_auc)} for "
        f"the table. A more flexible method, gradient-boosted trees, ranked crashes "
        f"{trees_compared} ({_in_100(trees.roc_auc)} times in 100) but gives no interval for an "
        "estimate and cannot be read term by term, so the logistic model is the one published. "
        "Its "
        "intervals come from refitting it on resampled crashes, and the calculator and the "
        "table above use the same arithmetic.</p>"
        "<p>The model has been tested only on later years and other places within Catalonia. "
        "Fitted on three of the four provinces, it ranked the fourth's crashes "
        f"{_in_100(other_provinces.roc_auc.min())} to {_in_100(other_provinces.roc_auc.max())} "
        "times in 100, except in the province of Barcelona, where most crashes are urban: "
        f"{_in_100(province.roc_auc)} times in 100, with estimates too high "
        f"({_fmt_pct(province.mean_predicted)} against {_fmt_pct(province.prevalence)}). "
        "The project's other models, of Barcelona's crash records and of monthly deaths in "
        "Spain, are not used as predictors: the Barcelona crash model and the deaths forecast "
        "did no better than simple benchmarks, and the Barcelona person model can only rank "
        "people, not give probabilities. All of them are re-evaluated in "
        f'<a href="{REVIEW_DOC}">the model review</a>, and this model is documented in '
        f'<a href="{CALCULATOR_DOC}">its own report</a>.</p>'
    )

    body += limitation(
        f"The model describes crashes recorded in Catalonia in {training['years'][0]}–"
        f"{training['years'][1]}. “Fatal” means a death within 24 hours, the Servei Català de "
        "Trànsit's definition; Spain's official figures count deaths within 30 days, so the "
        "shares here are lower than a 30-day share would be. The inputs are police records, "
        "coded as recorded. The model's intervals reflect the uncertainty of its coefficients, "
        "not the differences between places and years described above."
    )
    body += downloads(
        [
            ("sev_calibration", "predicted against observed, by tenth"),
            ("sev_rolling_scores", "scores by year, zone and Barcelona city"),
            ("sev_comparison", "differences between the model, the trees and the table"),
            ("sev_geography", "provinces and Barcelona city left out"),
            ("sev_specification", "common effects against effects differing by zone"),
            ("sev_contrasts", "one input changed at a time"),
            ("sev_marginal_adjusted", "raw and standardised shares"),
            ("sev_stability", "the contrasts on earlier and later years"),
            ("sev_coefficients", "coefficients and bootstrap standard errors"),
            ("sev_penalty", "choice of penalty"),
        ],
        method=(CALCULATOR_DOC, "how the model was built and checked"),
    )
    return render_page(
        "severity-models",
        "Crash severity model and calculator",
        "How well a model tells which crashes with a death or serious injury in Catalonia were "
        "fatal, tested on years it had not seen, and a calculator to try it.",
        body,
        head='\n<script src="models/severity-engine.js" defer></script>'
        '\n<script src="models/severity-calculator.js" defer></script>',
    )
