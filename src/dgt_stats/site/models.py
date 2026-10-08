"""Crash severity: whether the Catalan severity model can tell which serious crashes were fatal,
and a calculator to try it.

The page answers its question in the order a reader asks it: does the model's estimate match what
happened on years that played no part in fitting or tuning it (predicted against observed,
with a simple table beside it, and where it misses),
the calculator, what the model shows about circumstances, and a short account of how it was
built. Ranking skill is given as ROC-AUC to two decimals, defined once in plain words, as on the
External validation page. Scores tables and the inventory of every model the project fitted are in
the research documents, not here.

On a wide screen the calculator's result and comparison sit in a column beside the form that stays
in view while the form scrolls; on a phone they follow the form, and every change is announced.

Every number is read from the ``sev_*`` tables and the exported model
(``reports/models/severity_model.json``), and every qualitative sentence is checked against them.
The model is ``docs/research/SEVERITY_CALCULATOR.md``; the re-evaluation of every model is
``docs/research/ML_MODEL_REVIEW.md``.
"""

from __future__ import annotations

import json

import pandas as pd

from dgt_stats.microdata.validation import decisions as rules
from dgt_stats.paths import REPORTS_DIR
from dgt_stats.severity_model import PREVIOUS_VALIDATION_YEARS
from dgt_stats.site.components import (
    DOCS_URL,
    _fmt_dec,
    _fmt_pct,
    _join,
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
ZONE_WORDS = {
    "urban": "urban streets",
    "through_town": "roads through towns",
    "interurban": "interurban roads",
}
SPECIFICATION_WORDS = {
    "common": "model whose terms are the same on every kind of road",
    "by_zone": "model whose terms may differ between urban streets and interurban roads",
}
# The rows of sev_population the page quotes.
FITTED = "fitted (named owner network or not a conventional road)"
EXCLUDED = "excluded: both"
EVERYTHING = "all crashes in the file"
# The years the penalty was chosen on before the evaluation was nested.
PREVIOUS_YEARS = f"{PREVIOUS_VALIDATION_YEARS[0]}–{PREVIOUS_VALIDATION_YEARS[-1]}"


def _check(holds: bool, claim: str) -> None:
    if not holds:
        raise ValueError(f"models page: the tables no longer support: {claim}")


def _model() -> dict:
    with MODEL_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _auc(value: float) -> str:
    """A ROC-AUC, or a difference of two, to two decimals: the one scale on this page and the
    External validation page."""
    return _fmt_dec(value, 2)


def _range(low: float, high: float) -> str:
    """A percentage interval with the unit once, as 'low–high%'."""
    return f"{_fmt_dec(100 * float(low), 1)}–{_fmt_pct(high)}"


def _fmt_c(value: float) -> str:
    """A penalty setting C to two significant figures: 0.1, 0.032, 32."""
    return f"{float(value):,.0f}" if float(value) >= 100 else f"{float(value):.2g}"


def _other(specification: str) -> str:
    return next(key for key in SPECIFICATION_WORDS if key != specification)


def _through_town_text(yearly: pd.DataFrame, published: pd.Series, scores: pd.Series) -> str:
    """How roads through towns were treated in the test and by the calculator."""
    average = int((yearly.through_town == "average").sum())
    lead = (
        "On roads through towns the calculator shows the average fatal share of such roads in "
        "the province instead of an estimate"
        if published.through_town == "average"
        else "On roads through towns the calculator gives the model's estimate"
    )
    return (
        f"{lead}. That rule was chosen like the other settings: in {_words(average)} of the "
        f"{_words(len(yearly))} test years the average had predicted the two years before "
        "better than the model, and the test scores whichever was chosen (ROC-AUC "
        f"{_auc(scores.roc_auc)} on those roads)."
    )


def _words(value: int) -> str:
    """Small counts in words, as in running prose."""
    words = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
    words += ("eleven", "twelve")
    return words[value] if 0 <= value < len(words) else f"{value:,}"


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
    # The form, then the panel with the result and the comparison: beside the form on a wide
    # screen (it stays in view while the form scrolls), after it on a phone.
    return (
        '<section class="calculator" id="calculator" data-model="models/severity_model.json" '
        f'data-model-id="{esc(model["model_id"])}" aria-labelledby="calculator-title" hidden>'
        '<h3 id="calculator-title">Describe a crash</h3>'
        '<div class="calc-layout">'
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
        '<div class="calc-panel">'
        '<div class="calc-result" data-output></div>'
        '<div class="calc-baseline" data-baseline></div>'
        "</div></div>"
        '<p class="visually-hidden" role="status" aria-live="polite" data-status></p>'
        "</section>"
        '<p id="calculator-fallback">The calculator needs JavaScript. Without it, the worked '
        "examples below give the model's estimates for typical crashes.</p>"
    )


def _pooled(scores: pd.DataFrame) -> str:
    """The subset that pools every evaluation year (written ``first-last`` in the table)."""
    return str(scores.subset[scores.subset.str.fullmatch(r"\d{4}-\d{4}")].iloc[0])


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
                    f"({_range(row.probability_low, row.probability_high)})"
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
        "changes one input. The calculator gives the same numbers. The intervals cover the "
        "uncertainty of the model's coefficients only.",
    )


def _fifth(groups: pd.DataFrame, top: bool) -> float:
    """Observed fatal share in the fifth of crashes rated most (or least) likely to be fatal."""
    ordered = groups.sort_values("group")
    part = ordered.tail(2) if top else ordered.head(2)
    return float(part.positives.sum() / part.n.sum())


def _outside(row: pd.Series) -> bool:
    """The mean estimate lies outside the 95% interval of the observed share."""
    return not float(row.observed_low) <= float(row.mean_predicted) <= float(row.observed_high)


def _misses(scores: pd.DataFrame) -> pd.DataFrame:
    """The zones of provinces in which the nested test's mean estimate lies outside the 95%
    interval of the observed share, with the province and zone as columns."""
    cells = scores[
        scores.subset.str.startswith("province and zone: ") & (scores.estimator == "calculator")
    ].copy()
    keys = cells.subset.str.removeprefix("province and zone: ").str.split("|", expand=True)
    cells["province"], cells["zone"] = keys[0], keys[1]
    return cells[cells.apply(_outside, axis=1)]


def _miss_text(row: pd.Series) -> str:
    """'on interurban roads in the province of Girona, x% estimated and y% observed (interval)',
    with a second decimal where one decimal would print the estimate at an end of the interval
    it falls outside."""
    digits = 1
    if round(100 * float(row.mean_predicted), 1) in (
        round(100 * float(row.observed_low), 1),
        round(100 * float(row.observed_high), 1),
    ):
        digits = 2
    return (
        f"on {ZONE_WORDS[row.zone]} in the province of {row.province}, "
        f"{_fmt_pct(row.mean_predicted, digits)} "
        f"estimated and {_fmt_pct(row.prevalence, digits)} observed "
        f"({_fmt_dec(100 * float(row.observed_low), digits)}–"
        f"{_fmt_pct(row.observed_high, digits)})"
    )


def _stability_lists(stability: pd.DataFrame, periods: list[str]) -> tuple[list[str], list[str]]:
    """The worked examples whose 95% interval excludes 1 on the same side in models fitted
    separately on each period (held), and the others."""
    held, unsettled = [], []
    for name, level, label in EXAMPLES:
        rows = [stability.loc[(period, name, level)] for period in periods]
        above = all(float(r.ratio_low) > 1 for r in rows)
        below = all(float(r.ratio_high) < 1 for r in rows)
        ratios = " and ".join(f"{float(r.ratio):.2f}" for r in rows)
        entry = f"{label[:1].lower()}{label[1:]} ({ratios})"
        (held if above or below else unsettled).append(entry)
    return held, unsettled


def page_severity_models(captions: dict[str, str]) -> str:
    model = _model()
    scores = read_table("sev_rolling_scores")
    comparison = read_table("sev_comparison").set_index(["estimator", "metric"])
    calibration = read_table("sev_calibration")
    contrasts = read_table("sev_contrasts")
    geography = read_table("sev_geography").set_index(["test", "estimator"])
    penalty = read_table("sev_penalty")
    choices = read_table("sev_choices")
    steps = read_table("sev_nested_steps")
    population = read_table("sev_population").set_index(["population", "zone"])
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
    inside = ~model_groups.apply(_outside, axis=1)
    group_misses = model_groups[~inside]
    misses = _misses(scores)
    tests = geography.index.get_level_values(0)
    estimators = geography.index.get_level_values(1)
    left_out = (
        geography[tests.str.endswith("from the other demarcations") & (estimators == "calculator")]
        .reset_index()
        .assign(name=lambda d: d.test.str.extract(r"^(\w+) from")[0])
        .set_index("name")
    )
    left_out_misses = left_out[left_out.apply(_outside, axis=1)]
    left_out_fits = left_out[~left_out.apply(_outside, axis=1)]
    training = model["training"]
    published = choices[choices.fit == "published model"].iloc[0]
    yearly = choices[choices.fit != "published model"]
    final_grid = penalty[(penalty.fit == "published model")]
    chosen_grid = final_grid[final_grid.specification == published.specification]
    pooled_steps = steps[steps.subset == span].set_index("estimator")
    previous = pooled_steps.loc["previous_design"]
    nested = pooled_steps.loc["calculator"]
    fitted_all = population.loc[(FITTED, "all zones")]
    fitted_interurban = population.loc[(FITTED, "interurban roads")]
    everything = population.loc[(EVERYTHING, "all zones")]
    everything_interurban = population.loc[(EVERYTHING, "interurban roads")]
    excluded = population.loc[(EXCLUDED, "all zones")]

    decisions = read_table("ml_model_decisions")
    decisions = decisions[decisions.variant == "context"].set_index("model").decision
    stability_periods = [s for s in stability.index.get_level_values(0).unique() if s[:1].isdigit()]

    slope = float(calc.calibration_slope)
    _check(
        0.8 < slope < 1.25 and abs(float(calc.mean_predicted) - float(calc.prevalence)) < 0.005,
        "the pooled estimates are calibrated on the nested test, within the project's rule",
    )
    _check(
        int(evaluation["crashes"]) == int(calc.n)
        and evaluation["design"].startswith("nested rolling origin"),
        "the exported model's evaluation is the nested test",
    )
    _check(float(gap.high) < 0, "the model ranks crashes better than the table")
    _check(float(tree_gap.high) < 0.03, "the trees rank no more than slightly better")
    trees_compared = "a little better" if float(tree_gap.low) > 0 else "about as well"
    ahead = years.set_index("subset").roc_auc > table_years.roc_auc
    ahead_text = (
        f"and it is ahead in every year from {first_test} to {last_test}"
        if bool(ahead.all())
        else f"and it is ahead in {_words(int(ahead.sum()))} of the {_words(len(ahead))} years"
    )
    _check(
        float(zone["interurban"].roc_auc) > float(zone["urban"].roc_auc) > 0.6,
        "the model ranks interurban crashes best, urban ones less well",
    )
    _check(
        float(calc.roc_auc) > max(float(z.roc_auc) for z in zone.values())
        and float(zone["interurban"].prevalence) > 2 * float(zone["urban"].prevalence),
        "the pooled score is above every zone's, and the zones' fatal shares differ widely",
    )
    _check(
        1.75 <= float(heavy.ratio) <= 2.25 and float(heavy.ratio_low) > 1.5,
        "a heavy vehicle goes with about twice the estimated share",
    )
    others = contrasts[(contrasts.base == "interurban") & (contrasts.input != "province")]
    _check(
        float(heavy.ratio) == float(others.ratio.max()),
        "a heavy vehicle brings the largest increase of any one input",
    )
    _check(float(junction.ratio_high) < 1, "a junction goes with a lower share")

    held, unsettled = _stability_lists(stability, stability_periods[:2])
    _check(
        bool(held) and bool(unsettled),
        "some worked examples hold in both periods and some do not",
    )
    heavy_label = EXAMPLES[0][2]
    _check(
        any(entry.startswith(heavy_label[:1].lower() + heavy_label[1:]) for entry in held),
        "the heavy-vehicle association holds in both periods",
    )
    _check(
        float(outside.mean_predicted) > float(outside.prevalence),
        "estimates on urban streets outside Barcelona city run high",
    )
    _check(
        not left_out_misses.empty and not left_out_fits.empty,
        "with a province left out, the estimates miss in some provinces and not in others",
    )
    with_terms = by_subset.xs("calculator", level="estimator")
    _check(
        all(
            abs(
                float(with_terms.loc[f"province: {name}"].mean_predicted)
                - float(with_terms.loc[f"province: {name}"].prevalence)
            )
            < abs(float(row.mean_predicted) - float(row.prevalence))
            for name, row in left_out.iterrows()
        ),
        "with province terms, every province's estimate in the nested test is closer to its "
        "observed share than with the province left out",
    )
    _check(
        bool(published.c_bracketed)
        and float(chosen_grid.c.min()) < float(published.c) < float(chosen_grid.c.max()),
        "the published penalty lies inside the grid it was chosen from",
    )
    at_limit = yearly[yearly.c_at_weak_limit.astype(bool)]
    _check(
        bool((yearly.c_bracketed.astype(bool) | yearly.c_at_weak_limit.astype(bool)).all()),
        "every test year's chosen penalty lies inside its grid, or at its weak end where the "
        "validation loss had stopped changing",
    )
    _check(
        model["choice"]["specification"] == published.specification
        and float(model["penalty"]["C"]) == float(published.c)
        and model["through_town"] == published.through_town,
        "the exported model is the published choice",
    )
    _check(
        float(excluded.fatal_share) > float(fitted_all.fatal_share)
        and float(everything_interurban.fatal_share) < float(fitted_interurban.fatal_share),
        "the left-out crashes raise the overall fatal share and lower the interurban one",
    )
    _check(
        decisions["barcelona_crash_severity"] == rules.REPLACE
        and decisions["barcelona_person_severity"] == rules.KEEP_RANKING,
        "the Barcelona crash model gave way to its table, and the person model only ranks",
    )

    top, bottom = _fifth(model_groups, True), _fifth(model_groups, False)
    top_table, bottom_table = _fifth(table_groups, True), _fifth(table_groups, False)
    _check(top > top_table and bottom < bottom_table, "the model separates the extremes better")

    miss_provinces = sorted(set(misses.province))
    body = summary(
        "Of the crashes in Catalonia in which someone was killed or seriously injured, the "
        "Catalan severity model estimates which were fatal (someone died within 24 hours) from "
        "the road, the conditions, the type of crash and who was involved. Each year from "
        f"{first_test} to {last_test} was predicted by a model whose settings and coefficients "
        "came only from earlier years. Over those years its estimates matched the overall "
        "fatal share, and it sorted crashes into more and less deadly groups somewhat better "
        "than a table of fatal shares by road and crash type"
        + (
            f"; in the provinces of {_join(miss_provinces)} some of its estimates by kind of "
            "road missed. "
            if miss_provinces
            else ". "
        )
        + "It cannot say whether a crash will happen, only how often crashes like a given one, "
        "already recorded with a death or serious injury, were fatal."
    )

    # ------------------------------------------------------------------- predicted and observed
    _check(
        not misses.empty,
        "the heading says that the estimates miss in some provinces",
    )
    body += "<h2>The estimates matched later years overall, but not in every province</h2>"
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
    group_text = (
        f"In {_words(int(inside.sum()))} of the ten groups, from the crashes it rated least "
        "likely to be fatal to those it rated most likely, its mean estimate lies inside the "
        "95% interval of the share observed"
    )
    if len(group_misses):
        group_text += "; " + _join(
            [
                f"in group {int(g.group)} it said {_fmt_pct(g.mean_predicted)} and "
                f"{_fmt_pct(g.observed)} were fatal ({_range(g.observed_low, g.observed_high)})"
                for g in group_misses.itertuples()
            ]
        )
    body += (
        f"<p>The test covers the {int(calc.n):,} crashes of {first_test}–{last_test} on the roads "
        "the calculator offers. For each year, the model's settings (the strength of its "
        "penalty, whether each circumstance may count differently on urban streets and "
        "interurban roads, whether roads through towns get an estimate or the average, and "
        "whether each province has a starting level of its own) were chosen on the two years "
        "before it, and the model was then fitted on all earlier "
        "years: no choice saw the year it predicts. Over all the years the model estimated "
        f"{_fmt_pct(calc.mean_predicted)} fatal, and {_fmt_pct(calc.prevalence)} were "
        f"({_range(calc.observed_low, calc.observed_high)}). {group_text}. Its calibration "
        f"slope, 1 when the estimates spread as widely as the outcomes, is "
        f"{_fmt_dec(slope, 2)}"
        + (
            ": the crashes it rated most and least likely to be fatal turned out somewhat more "
            "extreme than it said."
            if slope > 1.05
            else (
                ": its estimates were somewhat more extreme than the outcomes."
                if slope < 0.95
                else "."
            )
        )
        + "</p>"
    )
    if len(misses):
        body += (
            "<p>By province and kind of road the estimates were less close. The mean estimate "
            "fell outside the 95% interval of the observed share "
            + _join([_miss_text(row) for row in misses.itertuples()])
            + ". A reader should not take an estimate for those roads at face value.</p>"
        )
    body += (
        "<p>Of the fifth of crashes the model rated most likely to have been fatal, "
        f"{_fmt_pct(top, 0)} were; of the fifth it rated least likely, {_fmt_pct(bottom, 0)}. "
        f"The table separates them less ({_fmt_pct(top_table, 0)} and "
        f"{_fmt_pct(bottom_table, 0)}). Ranking is measured by the ROC-AUC: given one fatal and "
        "one non-fatal crash, the share of pairs in which the fatal one gets the higher "
        "estimate, from 0.5 for chance to 1 for a perfect ranking. The model's ROC-AUC is "
        f"{_auc(calc.roc_auc)} and the table's {_auc(tab.roc_auc)}; the model's lead is "
        f"{_auc(-gap.high)}–{_auc(-gap.low)} (95% interval), {ahead_text}. The gain is real but "
        "modest: most of what these records can tell is in the road and the type of crash.</p>"
        "<p>Within one kind of road the ranking is harder, because the kind of road alone "
        "separates many fatal crashes from the rest. The model ranks interurban crashes best "
        f"(ROC-AUC {_auc(zone['interurban'].roc_auc)}) and urban ones less well "
        f"({_auc(zone['urban'].roc_auc)}). "
        + _through_town_text(yearly, published, zone["through_town"])
        + " On urban streets outside Barcelona "
        f"city its estimates ran somewhat high ({_fmt_pct(outside.mean_predicted)} against "
        f"{_fmt_pct(outside.prevalence)} fatal); in Barcelona city they were "
        + (
            "close"
            if not _outside(city)
            else ("low" if float(city.mean_predicted) < float(city.prevalence) else "high")
        )
        + f" ({_fmt_pct(city.mean_predicted)} against {_fmt_pct(city.prevalence)}).</p>"
    )

    # ------------------------------------------------------------------- calculator
    few = next(rule["threshold"] for rule in model["rules"] if rule["id"] == "few_similar")
    body += "<h2>Try the model</h2>"
    body += (
        "<p>Describe a crash in which someone was killed or seriously injured, and the "
        "calculator gives the model's estimate of the share of such crashes that were fatal, "
        "with a 95% confidence interval, and the share that were fatal among the crashes the "
        "model was fitted on, on the same kind of road in the same province. Those crashes "
        f"leave out the {training['excluded_owner_not_recorded']:,} on conventional roads whose "
        "owning network is not named (below). The estimate is a share among crashes already "
        "recorded with a death or serious injury, not the chance that a crash happens or that "
        "someone dies on a journey. "
        "Three impossible combinations, such as a pedestrian struck with no pedestrian "
        f"involved, are refused; combinations with fewer than {few} similar recorded crashes, "
        "including none, still get an estimate, with a warning that it rests on the model's "
        "assumptions.</p>"
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
    first_period, second_period = (p.replace("-", "–") for p in stability_periods[:2])
    body += "<h2>Crashes involving a heavy vehicle: about twice the fatal share</h2>"
    body += (
        "<p>Starting from a typical crash on a regional road and changing one thing at a time "
        "shows which circumstances the records associate with a fatal outcome. The largest "
        "increase comes with a heavy vehicle: with a lorry or bus involved, the estimated fatal "
        f"share is {float(heavy.ratio):.2f} times that of the same crash between cars (95% "
        f"confidence interval {float(heavy.ratio_low):.2f}–{float(heavy.ratio_high):.2f}). A "
        f"crash within a junction carries {float(junction.ratio):.2f} times the share of one "
        f"between junctions ({float(junction.ratio_low):.2f}–{float(junction.ratio_high):.2f}). "
        f"Refitted separately on {first_period} and on {second_period}, "
        f"{_words(len(held))} of the {_words(len(EXAMPLES))} changes in the table below have "
        "95% intervals on the same side of 1 in both periods (the two ratios in brackets): "
        f"{_join(held)}. For the other {_words(len(unsettled))} the interval "
        f"includes 1 in at least one period, so they should not be read as settled: "
        f"{_join(unsettled)}.</p>"
    )
    body += _examples_table(contrasts, base)
    body += evidence_note(
        "These compare crashes that had already killed or seriously injured someone. A smaller "
        "fatal share in heavy rain or at a junction does not mean that rain or junctions are "
        "safer: they may bring more crashes, slower and less often fatal. A posted limit is not "
        "a speed. Each figure is an association in police records, adjusted for the other "
        "inputs, not the effect of changing a road or a vehicle. The same circumstances among "
        "all injury crashes in Spain, with deaths counted within 30 days, are on "
        '<a href="severity.html">Crash circumstances in Spain</a>; Catalonia\'s unadjusted '
        'fatal shares are on <a href="catalonia.html">Catalonia</a>.'
    )

    # ------------------------------------------------------------------- method
    specification = (
        "one term for each other input, the same on every kind of road"
        if published.specification == "common"
        else "one term for each other input, which may differ between urban streets and "
        "interurban roads"
    )
    body += "<h2>How the model was built</h2>"
    body += (
        f"<p>The model is a logistic regression fitted to the {training['crashes']:,} crashes "
        f"of {training['years'][0]}–{training['years'][1]} in the Servei Català de Trànsit's "
        "file. It has a starting level for each zone (urban street, road through a town, "
        f"interurban road) in each province, and {specification}. Its settings were chosen "
        "by the rule used for every test year: fitted on "
        f"{published.train_years.replace('-', '–')} and scored on "
        f"{published.validation_years.replace('-', '–')}, the "
        f"{SPECIFICATION_WORDS[published.specification]} predicted better than the "
        f"{SPECIFICATION_WORDS[_other(published.specification)]}, with a penalty setting C "
        f"of {_fmt_c(published.c)} (a smaller C penalises the terms more strongly), chosen "
        f"from values between {_fmt_c(chosen_grid.c.min())} and {_fmt_c(chosen_grid.c.max())} "
        "(the grid is extended while its best value lies at an end) and better than its "
        "neighbours on both sides; "
        + (
            "roads through towns get the average because it predicted those years better than "
            "the model; "
            if published.through_town == "average"
            else "roads through towns get the model's estimate because it predicted those "
            "years better than the average; "
        )
        + (
            "and each province has a starting level of its own because that predicted those "
            "years better than one level per zone for all of Catalonia. "
            if bool(published.provinces)
            else "and the provinces share one starting level per zone because that predicted "
            "those years better than a level for each. "
        )
        + "In the test years the same rule chose the model whose terms may differ by kind of "
        f"road in {_words(int((yearly.specification == 'by_zone').sum()))} of the "
        f"{_words(len(yearly))} years, with C from {_fmt_c(yearly.c.min())} to "
        f"{_fmt_c(yearly.c.max())}, and a starting level for each province in "
        f"{_words(int(yearly.provinces.astype(bool).sum()))}"
        + (
            f"; in {_join([str(int(y)) for y in at_limit.test_year])} the best penalty was the "
            "weakest the grid allows, where the validation loss had stopped changing, so that "
            "year's model is in effect unpenalised"
            if len(at_limit)
            else ""
        )
        + ". Its intervals come from refitting it on resampled crashes, and the calculator and "
        "the table above use the same arithmetic.</p>"
        "<p>Left out are "
        f"{training['excluded_owner_not_recorded']:,} crashes on conventional roads whose owner "
        "is recorded as “other” or left blank: a blank owner is far commoner on fatal records "
        "and “other” on non-fatal ones, so the field records how a crash was documented, not "
        "the road. The estimates, the averages and the tests therefore describe crashes on "
        "roads with a named owning network or of another type. The crashes left out were "
        f"fatal in {_fmt_pct(excluded.fatal_share)} of cases. With them, "
        f"{_fmt_pct(everything.fatal_share)} of all crashes would count as fatal instead of "
        f"{_fmt_pct(fitted_all.fatal_share)}, and {_fmt_pct(everything_interurban.fatal_share)} "
        f"of interurban crashes instead of {_fmt_pct(fitted_interurban.fatal_share)}.</p>"
        "<p>Before this test was nested, the penalty had been chosen on "
        f"{PREVIOUS_YEARS}, which are also test years, and the form of the model, the rule "
        "for roads through towns and the starting level for each province had been settled on "
        "the test scores themselves, so its score "
        f"was not a test on untouched years: a ROC-AUC of {_auc(previous.roc_auc)}, against "
        f"{_auc(previous.table_roc_auc)} for the table. With every choice nested it is "
        f"{_auc(nested.roc_auc)}"
        + (
            ": the earlier choices had not flattered it."
            if float(nested.roc_auc) >= float(previous.roc_auc) - 0.005
            else ": part of the earlier score came from choices made on the test years."
        )
        + " A more flexible method, "
        f"gradient-boosted trees, ranked crashes {trees_compared} ({_auc(trees.roc_auc)}) but "
        "gives no interval for an estimate and cannot be read term by term, so the logistic "
        "model is the one published.</p>"
        "<p>The model has been tested only within Catalonia. Fitted on three of the four "
        "provinces without province terms, with its settings chosen on those three, it ranked "
        f"the fourth's crashes with a ROC-AUC of {_auc(left_out.roc_auc.min())} to "
        f"{_auc(left_out.roc_auc.max())}. Its estimates of the fatal share missed in "
        f"{_words(len(left_out_misses))} of the four: "
        + _join(
            [
                f"{name} {_fmt_pct(row.mean_predicted)} estimated against "
                f"{_fmt_pct(row.prevalence)} observed "
                f"({_range(row.observed_low, row.observed_high)})"
                for name, row in left_out_misses.iterrows()
            ]
        )
        + "; it lay inside the observed interval only in "
        + _join(
            [
                f"{name} ({_fmt_pct(row.mean_predicted)} against {_fmt_pct(row.prevalence)})"
                for name, row in left_out_fits.iterrows()
            ]
        )
        + ". With a term for each province, the published model came closer to each "
        "province's observed share in the test on later years, though not in every zone "
        "(above); it should not be used for a place it was not fitted on. These and the other "
        'tests are on <a href="validation.html">External '
        "validation</a>. The project's Barcelona models are not used as predictors: the crash "
        "model ranked crashes no better than a table of shares by type of accident, and the "
        "person model can only rank people, not give probabilities. Every model the project "
        f'fitted is re-evaluated in <a href="{REVIEW_DOC}">the model review</a>, and this one '
        f'is documented in <a href="{CALCULATOR_DOC}">its own report</a>.</p>'
    )

    body += limitation(
        f"The model describes crashes recorded in Catalonia in {training['years'][0]}–"
        f"{training['years'][1]} on roads with a named owning network or of another type. "
        "“Fatal” means a death within 24 hours, the Servei Català de "
        "Trànsit's definition; Spain's official figures count deaths within 30 days, so the "
        "shares here are lower than a 30-day share would be. The inputs are police records, "
        "coded as recorded."
    )
    body += downloads(
        [
            ("sev_calibration", "predicted against observed, by tenth"),
            ("sev_rolling_scores", "scores by year, zone, province and Barcelona city"),
            ("sev_comparison", "differences between the model, the trees and the table"),
            ("sev_choices", "the settings chosen for each test year and for the model"),
            ("sev_penalty", "every setting tried, with its validation score"),
            ("sev_nested_steps", "from the earlier design to the nested test, step by step"),
            ("sev_geography", "provinces and Barcelona city left out"),
            ("sev_population", "the crashes left out and the fatal share"),
            ("sev_contrasts", "one input changed at a time"),
            ("sev_marginal_adjusted", "raw and standardised shares"),
            ("sev_stability", "the contrasts on earlier and later years"),
            ("sev_coefficients", "coefficients and bootstrap standard errors"),
        ],
        method=(CALCULATOR_DOC, "how the model was built and checked"),
    )
    return render_page(
        "severity-models",
        "Crash severity model and calculator",
        "How well the Catalan severity model tells which crashes with a death or serious injury "
        "in Catalonia were fatal, tested by predicting each year from a model fitted and tuned "
        "on the years before it, and a calculator to try it.",
        body,
        head='\n<script src="models/severity-engine.js" defer></script>'
        '\n<script src="models/severity-calculator.js" defer></script>',
    )
