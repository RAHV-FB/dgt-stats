"""Crash severity: whether the Catalan severity model can tell which serious crashes were fatal.

The public page is short: how its estimates compared with later years (predicted against
observed), the circumstances it associates with a fatal outcome, and where it has been tested.
``technical_notes`` gives the test in detail and how the model was built; the Model method and
tests page (``validation.py``) carries it. The calculator has its own page (``tool_calculator``).

Every number is read from the ``sev_*`` tables and the exported model
(``reports/models/severity_model.json``), and every qualitative sentence is checked against them.
The model is ``docs/research/SEVERITY_CALCULATOR.md``; the re-evaluation of every model is
``docs/research/ML_MODEL_REVIEW.md``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

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
    evidence_note,
    figure,
    limitation,
    read_table,
    render_page,
    summary,
    table,
)

MODEL_PATH = REPORTS_DIR / "models" / "severity_model.json"
REVIEW_DOC = f"{DOCS_URL}/research/ML_MODEL_REVIEW.md"
CALCULATOR_DOC = f"{DOCS_URL}/research/SEVERITY_CALCULATOR.md"
# The contrasts quoted as worked examples, each a change of one input from the reference crash.
# The reference is in daylight at 10:00-13:59, so changes of the hour or the lighting alone would
# describe conditions the calculator refuses; none is quoted.
EXAMPLES = (
    ("users", "heavy_vehicle", "A heavy vehicle (lorry or bus) involved as well as the car"),
    ("crash_type", "run_off_road", "The car ran off the road"),
    ("crash_type", "pedestrian_struck", "A pedestrian struck"),
    ("crash_type", "head_on", "A head-on collision"),
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
    Model method and tests page."""
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
        "changes one input. The intervals cover the "
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


def _coarse_misses(scores: pd.DataFrame) -> list[str]:
    """The years, zones and provinces in which the nested test's mean estimate lies outside the
    95% interval of the observed share, each as 'in 2016, x% estimated and y% observed (interval)'.
    """
    out = []
    for row in scores[scores.estimator == "calculator"].itertuples():
        subset = str(row.subset)
        if subset.isdigit():
            place = f"in {subset}"
        elif subset.startswith("zone: "):
            place = f"on {ZONE_WORDS[subset.removeprefix('zone: ')]} as a whole"
        elif subset.startswith("province: "):
            place = f"in the province of {subset.removeprefix('province: ')} as a whole"
        else:
            continue
        if _outside(row):
            out.append(_miss_text(row, place))
    return out


def _miss_text(row: pd.Series, place: str | None = None) -> str:
    """'on interurban roads in the province of Girona, x% estimated and y% observed (interval)',
    with a second decimal where one decimal would print the estimate at an end of the interval
    it falls outside."""
    digits = 1
    if round(100 * float(row.mean_predicted), 1) in (
        round(100 * float(row.observed_low), 1),
        round(100 * float(row.observed_high), 1),
    ):
        digits = 2
    place = place or f"on {ZONE_WORDS[row.zone]} in the province of {row.province}"
    return (
        f"{place}, "
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


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the tables, with the
    checks that the sentences built on them still hold."""
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
    yearly_scores = scores[(scores.estimator == "calculator") & scores.subset.str.isdigit()]
    miss_years = [str(row.subset) for row in yearly_scores.itertuples() if _outside(row)]
    _check(not misses.empty, "the heading says that the estimates miss in some provinces")
    left_tables = (
        geography[
            tests.str.endswith("from the other demarcations") & (estimators == "road_x_crash_table")
        ]
        .reset_index()
        .assign(name=lambda d: d.test.str.extract(r"^(\w+) from")[0])
        .set_index("name")
    )
    _check(
        bool((left_out.roc_auc > left_tables.roc_auc.reindex(left_out.index)).all()),
        "with a province left out, the model ranks that province above the table",
    )
    city_left_out = geography.xs("calculator", level="estimator")
    city_left_out = city_left_out[city_left_out.index.str.startswith("Barcelona city")].iloc[0]
    _check(
        float(city_left_out.mean_predicted) < float(city_left_out.observed_low),
        "fitted without Barcelona city, the model puts the city's fatal share too low",
    )
    first_period, second_period = (p.replace("-", "–") for p in stability_periods[:2])
    # Every name above is a fact the page or its notes quote.
    return SimpleNamespace(**locals())


def _place(row) -> str:
    """'interurban roads in Girona', for a province and zone the estimates missed."""
    return f"{ZONE_WORDS[row.zone]} in {row.province}"


def page_severity_models(captions: dict[str, str]) -> str:
    f = _facts()
    body = summary(
        "Among crashes in Catalonia in which someone was killed or seriously injured, the "
        "Catalan severity model estimates the share that were fatal (someone died within 24 "
        "hours) from the road, the conditions, the type of crash and who was involved. "
        f"Predicting each year from {f.first_test} to {f.last_test} from earlier years only, it "
        "matched the overall fatal share"
        + (f" (though not in {_join(f.miss_years)})" if f.miss_years else "")
        + " and sorted crashes better than a simple table, but missed in some provinces."
    )

    body += "<h2>The estimates matched later years overall, but not in every province</h2>"
    body += figure(
        "sev1_predicted_observed",
        "Dot chart of the observed share of fatal crashes against the predicted chance, in ten "
        "equal groups for the model (filled dots) and for a table by road and crash type (hollow "
        f"dots). The model's groups run from about {_fmt_pct(f.model_groups.observed.min(), 0)} "
        f"to {_fmt_pct(f.model_groups.observed.max(), 0)} fatal, the table's from about "
        f"{_fmt_pct(f.table_groups.observed.min(), 0)} to "
        f"{_fmt_pct(f.table_groups.observed.max(), 0)}; both follow the diagonal on which "
        "prediction equals observation.",
        captions,
    )
    body += (
        "<p>Each year was predicted by a model whose settings and coefficients came only from "
        f"the years before it. Over the {int(f.calc.n):,} crashes of "
        f"{f.first_test}–{f.last_test} the model estimated {_fmt_pct(f.calc.mean_predicted)} "
        f"fatal, and {_fmt_pct(f.calc.prevalence)} were "
        f"({_range(f.calc.observed_low, f.calc.observed_high)}).</p>"
        "<p>Of the fifth of crashes it "
        f"rated most likely to have been fatal, {_fmt_pct(f.top, 0)} were; of the fifth it "
        f"rated least likely, {_fmt_pct(f.bottom, 0)}. A table of fatal shares by road and "
        f"crash type separates them less ({_fmt_pct(f.top_table, 0)} and "
        f"{_fmt_pct(f.bottom_table, 0)}): the gain is real but modest. The model cannot say "
        "whether a crash will happen, only how often crashes like a given one were fatal once "
        "recorded with a death or serious injury.</p>"
        "<p>By province and kind of road the estimates were less close. On "
        + _join([_place(row) for row in f.misses.itertuples()])
        + " the mean estimate fell outside the 95% interval of the observed share "
        '(<a href="validation.html#later-years">the figures</a>), so an estimate for those '
        "roads should not be taken at face value.</p>"
    )

    body += "<h2>Crashes involving a heavy vehicle: about twice the fatal share</h2>"
    body += (
        "<p>Starting from a typical crash on a regional road and changing one thing at a time "
        "shows which circumstances the records associate with a fatal outcome. With a lorry or "
        f"bus involved, the estimated fatal share is {float(f.heavy.ratio):.2f} times that of "
        f"the same crash between cars (95% confidence interval {float(f.heavy.ratio_low):.2f}–"
        f"{float(f.heavy.ratio_high):.2f}), the largest increase of any input. A crash within a "
        f"junction carries {float(f.junction.ratio):.2f} times the share of one between "
        f"junctions. Refitted separately on {f.first_period} and on {f.second_period}, "
        f"{_words(len(f.held))} of the {_words(len(EXAMPLES))} changes below kept the same "
        f"direction; the other {_words(len(f.unsettled))} should not be read as settled.</p>"
    )
    body += _examples_table(f.contrasts, f.base)
    body += evidence_note(
        "These compare crashes that had already killed or seriously injured someone: a smaller "
        "fatal share in heavy rain or at a junction does not make them safer, as they may bring "
        "more crashes that are less often fatal. A posted limit is not a speed. Each figure is "
        "an association in police records, not the effect of changing a road or a vehicle. "
        'All injury crashes in Spain are on <a href="severity.html">Crash circumstances in '
        "Spain</a>."
    )

    body += "<h2>Tested only within Catalonia</h2>"
    body += (
        "<p>No other source records the model's inputs, so it has been tested only within "
        "Catalonia. With each province left out of its fitting, it still ranked that province's "
        "crashes better than the table, but its estimates of the fatal share missed for "
        f"{_join(list(f.left_out_misses.index))}; fitted without Barcelona city, it put the "
        "city's fatal share too low. It should not be used for a place it was not fitted on. "
        "The project's Barcelona models are not used as predictors: one ranked crashes no "
        "better than a table, and the other can only rank people.</p>"
        '<p id="calculator">Try the model in the <a href="calculator.html">crash severity '
        'calculator</a>. How it was built and every test are on <a href="validation.html">'
        "Model method and tests</a>, and every model the project fitted is re-evaluated in "
        f'<a href="{REVIEW_DOC}">the model review</a>.</p>'
    )
    body += limitation(
        f"The model describes crashes recorded in Catalonia in {f.training['years'][0]}–"
        f"{f.training['years'][1]} on roads with a named owning network or of another type. "
        "“Fatal” means a death within 24 hours, the Catalan definition; Spain's official "
        "figures count deaths within 30 days."
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
        "Crash severity model",
        "How well a model of crashes in Catalonia tells which crashes with a death or serious "
        "injury were fatal, and which circumstances it associates with a fatal outcome.",
        body,
    )


def technical_notes(captions: dict[str, str]) -> str:
    """The Catalan severity model's test on later years in detail and how it was built: two
    sections for the Model method and tests page."""
    del captions
    f = _facts()
    group_text = (
        (
            f"In all {_words(len(f.inside))} groups"
            if bool(f.inside.all())
            else f"In {_words(int(f.inside.sum()))} of the {_words(len(f.inside))} groups"
        )
        + ", from the crashes it rated least likely to be fatal to those it rated most likely, "
        "its mean estimate lies inside the 95% interval of the share observed"
    )
    if len(f.group_misses):
        group_text += "; " + _join(
            [
                f"in group {int(g.group)} it said {_fmt_pct(g.mean_predicted)} and "
                f"{_fmt_pct(g.observed)} were fatal ({_range(g.observed_low, g.observed_high)})"
                for g in f.group_misses.itertuples()
            ]
        )
    slope = f.slope
    body = '<h2 id="later-years">The Catalan severity model on later years</h2>'
    body += (
        f"<p>The test covers the {int(f.calc.n):,} crashes of {f.first_test}–{f.last_test} on "
        "the roads the calculator offers. For each year, the model's settings (the strength of "
        "its penalty, whether each circumstance may count differently on urban streets and "
        "interurban roads, whether roads through towns get an estimate or the average, and "
        "whether each province has a starting level of its own) were chosen on the two years "
        "before it, and the model was then fitted on all earlier years: no choice saw the year "
        f"it predicts. Over all the years the model estimated {_fmt_pct(f.calc.mean_predicted)} "
        f"fatal, and {_fmt_pct(f.calc.prevalence)} were "
        f"({_range(f.calc.observed_low, f.calc.observed_high)}). {group_text}. Its calibration "
        f"slope is {_fmt_dec(slope, 2)}"
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
    coarse = _coarse_misses(f.scores)
    if coarse:
        body += (
            "<p>By year, kind of road and province the mean estimate fell outside the 95% "
            f"interval of the observed share {_join(coarse)}. By province and kind of road it "
            "fell outside " + _join([_miss_text(row) for row in f.misses.itertuples()]) + ".</p>"
        )
    body += (
        f"<p>The model's ROC-AUC is {_auc(f.calc.roc_auc)} and the table's "
        f"{_auc(f.tab.roc_auc)}; the model's lead is {_auc(-f.gap.high)}–{_auc(-f.gap.low)} "
        f"(95% interval), {f.ahead_text}. Within one kind of road the ranking is harder, "
        "because the kind of road alone separates many fatal crashes from the rest: the model "
        f"ranks interurban crashes best (ROC-AUC {_auc(f.zone['interurban'].roc_auc)}) and "
        f"urban ones less well ({_auc(f.zone['urban'].roc_auc)}). "
        + _through_town_text(f.yearly, f.published, f.zone["through_town"])
        + (
            " "
            + _miss_text(
                f.outside, "On urban streets outside Barcelona city its estimates ran high"
            )
            + ", outside the interval of the observed share"
            if _outside(f.outside)
            else " On urban streets outside Barcelona city its estimates ran somewhat high "
            f"({_fmt_pct(f.outside.mean_predicted)} against {_fmt_pct(f.outside.prevalence)} "
            "fatal)"
        )
        + "; in Barcelona city they were "
        + (
            "close"
            if not _outside(f.city)
            else ("low" if float(f.city.mean_predicted) < float(f.city.prevalence) else "high")
        )
        + f" ({_fmt_pct(f.city.mean_predicted)} against {_fmt_pct(f.city.prevalence)}).</p>"
        f"<p>Refitted separately on {f.first_period} and on {f.second_period}, these changes of "
        "one input have 95% intervals on the same side of 1 in both periods (the two ratios in "
        f"brackets): {_join(f.held)}. For the others the interval includes 1 in at least one "
        f"period: {_join(f.unsettled)}.</p>"
    )

    published, yearly, chosen_grid = f.published, f.yearly, f.chosen_grid
    specification = (
        "one term for each other input, the same on every kind of road"
        if published.specification == "common"
        else "one term for each other input, which may differ between urban streets and "
        "interurban roads"
    )
    body += '<h2 id="how-the-model-was-built">How the Catalan severity model was built</h2>'
    body += (
        f"<p>The model is a logistic regression fitted to the {f.training['crashes']:,} crashes "
        f"of {f.training['years'][0]}–{f.training['years'][1]} in the Servei Català de "
        "Trànsit's file. It has a starting level for each zone (urban street, road through a "
        f"town, interurban road) in each province, and {specification}. Its settings were "
        "chosen by the rule used for every test year: fitted on "
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
            f"; in {_join([str(int(y)) for y in f.at_limit.test_year])} the best penalty was "
            "the weakest the grid allows, where the validation loss had stopped changing, so "
            "that year's model is in effect unpenalised"
            if len(f.at_limit)
            else ""
        )
        + ". Its intervals come from refitting it on resampled crashes, and the calculator and "
        "the table of examples use the same arithmetic.</p>"
        "<p>Left out are "
        f"{f.training['excluded_owner_not_recorded']:,} crashes on conventional roads whose "
        "owner is recorded as “other” or left blank: a blank owner is far commoner on fatal "
        "records and “other” on non-fatal ones, so the field records how a crash was "
        "documented, not the road. The estimates, the averages and the tests therefore "
        "describe crashes on roads with a named owning network or of another type. The "
        f"crashes left out were fatal in {_fmt_pct(f.excluded.fatal_share)} of cases. With "
        f"them, {_fmt_pct(f.everything.fatal_share)} of all crashes would count as fatal "
        f"instead of {_fmt_pct(f.fitted_all.fatal_share)}, and "
        f"{_fmt_pct(f.everything_interurban.fatal_share)} of interurban crashes instead of "
        f"{_fmt_pct(f.fitted_interurban.fatal_share)}.</p>"
        "<p>Before this test was nested, the penalty had been chosen on "
        f"{PREVIOUS_YEARS}, which are also test years, and the form of the model, the rule "
        "for roads through towns and the starting level for each province had been settled on "
        "the test scores themselves, so its score was not a test on untouched years: a ROC-AUC "
        f"of {_auc(f.previous.roc_auc)}, against {_auc(f.previous.table_roc_auc)} for the "
        f"table. With every choice nested it is {_auc(f.nested.roc_auc)}"
        + (
            ": the earlier choices had not flattered it."
            if float(f.nested.roc_auc) >= float(f.previous.roc_auc) - 0.005
            else ": part of the earlier score came from choices made on the test years."
        )
        + " A more flexible method, "
        f"gradient-boosted trees, ranked crashes {f.trees_compared} ({_auc(f.trees.roc_auc)}) "
        "but gives no interval for an estimate and cannot be read term by term, so the "
        "logistic model is the one published. The project's Barcelona models are not used as "
        "predictors: the crash model ranked crashes no better than a table of shares by type "
        "of accident, and the person model can only rank people, not give probabilities. The "
        f'model is documented in <a href="{CALCULATOR_DOC}">its own report</a>.</p>'
    )
    return body
