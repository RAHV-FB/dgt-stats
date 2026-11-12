"""Crash severity: how well a model of Catalonia's severe crashes tells which were fatal.

One page: the circumstances the model associates with a fatal outcome, how well it ranks crashes
against a table of fatal shares by road and crash type, its calibration, where it misses, and
the tests on years and places left out of its fitting, all within Catalonia. ``technical_notes``
says how the model was built, for the methodology page.

Every number is read from the ``sev_*`` tables and every qualitative sentence is checked against
them. The method is in ``docs/SEVERITY_MODEL.md``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from dgt_stats.site.components import (
    DOCS_URL,
    _fmt_dec,
    _fmt_int,
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

MODEL_DOC = f"{DOCS_URL}/SEVERITY_MODEL.md"
# The contrasts quoted as worked examples, each a change of one input from the reference crash.
# The reference is in daylight at 10:00-13:59, so changes of the hour or the lighting alone would
# describe conditions that cannot go together; none is quoted.
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


def _check(holds: bool, claim: str) -> None:
    if not holds:
        raise ValueError(f"models page: the tables no longer support: {claim}")


def _auc(value: float) -> str:
    """A ROC-AUC, or a difference of two, to two decimals."""
    return _fmt_dec(value, 2)


def _range(low: float, high: float) -> str:
    """A percentage interval with the unit once, as 'low–high%'."""
    return f"{_fmt_dec(100 * float(low), 1)}–{_fmt_pct(high)}"


def _fmt_c(value: float) -> str:
    """A penalty setting C to two significant figures: 0.1, 0.032, 32."""
    return f"{float(value):,.0f}" if float(value) >= 100 else f"{float(value):.2g}"


def _other(specification: str) -> str:
    return next(key for key in SPECIFICATION_WORDS if key != specification)


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


def _misses(scores: pd.DataFrame) -> pd.DataFrame:
    """The zones of provinces in which the nested test's mean estimate lies outside the 95%
    interval of the observed share, with the province and zone as columns."""
    cells = scores[
        scores.subset.str.startswith("province and zone: ") & (scores.estimator == "model")
    ].copy()
    keys = cells.subset.str.removeprefix("province and zone: ").str.split("|", expand=True)
    cells["province"], cells["zone"] = keys[0], keys[1]
    return cells[cells.apply(_outside, axis=1)]


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the tables, with the
    checks that the sentences built on them still hold."""
    scores = read_table("sev_rolling_scores")
    comparison = read_table("sev_comparison").set_index(["estimator", "metric"])
    calibration = read_table("sev_calibration")
    contrasts = read_table("sev_contrasts")
    choices = read_table("sev_choices")
    tests = read_table("sev_tests")
    population = read_table("sev_population").set_index(["population", "zone"])
    stability = read_table("sev_stability")
    stability = stability[stability.base == "interurban"].set_index(["subset", "input", "level"])
    years = read_table("cat_frequency").year

    span = _pooled(scores)
    first_test, last_test = span.split("-")
    pooled = scores[scores.subset == span].set_index("estimator")
    calc, trees, tab = (pooled.loc[n] for n in ("model", "boosted_trees", "road_x_crash_table"))
    model_groups = calibration[calibration.estimator == "model"].sort_values("group")
    table_groups = calibration[calibration.estimator == "road_x_crash_table"]
    by_subset = scores.set_index(["subset", "estimator"])
    yearly_scores = scores[scores.subset.str.fullmatch(r"\d{4}") & (scores.estimator == "model")]
    table_years = scores[
        scores.subset.str.fullmatch(r"\d{4}") & (scores.estimator == "road_x_crash_table")
    ].set_index("subset")
    base = float(contrasts[contrasts.base == "interurban"].base_probability.iloc[0])
    interurban = contrasts[contrasts.base == "interurban"].set_index(["input", "level"])
    heavy = interurban.loc[("users", "heavy_vehicle")]
    junction = interurban.loc[("junction", "junction")]
    gap = comparison.loc[("road_x_crash_table", "roc_auc_minus_model")]
    tree_gap = comparison.loc[("boosted_trees", "roc_auc_minus_model")]
    zone = {key: by_subset.loc[(subset, "model")] for key, subset in ZONE_SUBSETS.items()}
    zone_table = {
        key: by_subset.loc[(subset, "road_x_crash_table")] for key, subset in ZONE_SUBSETS.items()
    }
    outside = by_subset.loc[("urban streets outside Barcelona city", "model")]
    inside = ~model_groups.apply(_outside, axis=1)
    group_misses = model_groups[~inside]
    misses = _misses(scores)
    miss_years = [str(row.subset) for row in yearly_scores.itertuples() if _outside(row)]
    published = choices[choices.fit == "published model"].iloc[0]
    yearly = choices[choices.fit != "published model"]
    at_limit = yearly[yearly.c_at_weak_limit.astype(bool)]
    fitted_all = population.loc[(FITTED, "all zones")]
    fitted_interurban = population.loc[(FITTED, "interurban roads")]
    everything = population.loc[(EVERYTHING, "all zones")]
    everything_interurban = population.loc[(EVERYTHING, "interurban roads")]
    excluded = population.loc[(EXCLUDED, "all zones")]
    first_year, last_year = int(years.min()), int(years.max())
    stability_periods = [s for s in stability.index.get_level_values(0).unique() if s[:1].isdigit()]

    # The held-out tests: the last year, each province left out, Barcelona city.
    later = tests[tests.experiment.str.startswith("temporal")].iloc[0]
    left_out = tests[tests.experiment.str.startswith("leave out")].copy()
    left_out["province"] = left_out.experiment.str.extract(r"leave out (\w+) demarcation")[0]
    left_out = left_out.set_index("province")
    city = tests[tests.experiment.str.contains("Barcelona municipality")].iloc[0]
    left_out_misses = left_out[left_out.apply(_outside, axis=1)]

    slope = float(calc.calibration_slope)
    _check(
        0.8 < slope < 1.25 and abs(float(calc.mean_predicted) - float(calc.prevalence)) < 0.005,
        "the pooled estimates are calibrated on the nested test, within the project's rule",
    )
    _check(float(gap.high) < 0, "the model ranks crashes better than the table")
    _check(float(tree_gap.high) < 0.03, "the trees rank no more than slightly better")
    trees_compared = "a little better" if float(tree_gap.low) > 0 else "about as well"
    ahead = yearly_scores.set_index("subset").roc_auc > table_years.roc_auc
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
        float(zone["through_town"].roc_auc) <= float(zone_table["through_town"].roc_auc),
        "on roads through towns the model ranks no better than the table",
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
    _check(not misses.empty, "the estimates miss in some provinces and kinds of road")
    _check(
        bool(published.c_bracketed),
        "the published penalty lies inside the grid it was chosen from",
    )
    _check(
        bool((yearly.c_bracketed.astype(bool) | yearly.c_at_weak_limit.astype(bool)).all()),
        "every test year's chosen penalty lies inside its grid, or at its weak end where the "
        "validation loss had stopped changing",
    )
    _check(
        float(excluded.fatal_share) > float(fitted_all.fatal_share)
        and float(everything_interurban.fatal_share) < float(fitted_interurban.fatal_share),
        "the left-out crashes raise the overall fatal share and lower the interurban one",
    )
    top, bottom = _fifth(model_groups, True), _fifth(model_groups, False)
    top_table, bottom_table = _fifth(table_groups, True), _fifth(table_groups, False)
    _check(top > top_table and bottom < bottom_table, "the model separates the extremes better")
    _check(
        bool((left_out.roc_auc > left_out.table_roc_auc).all())
        and float(city.roc_auc) > float(city.table_roc_auc)
        and float(later.roc_auc) > float(later.table_roc_auc),
        "in every held-out test the model ranks the held-out crashes above the table",
    )
    _check(
        not left_out_misses.empty and len(left_out_misses) < len(left_out),
        "with a province left out, the estimates miss in some provinces and not in others",
    )
    _check(
        float(city.mean_predicted) < float(city.observed_low),
        "fitted without Barcelona city, the model puts the city's fatal share too low",
    )
    _check(
        float(later.observed_low) <= float(later.mean_predicted) <= float(later.observed_high),
        "the estimate for the last year, fitted on the years before, lies inside the observed "
        "interval",
    )
    first_period, second_period = (p.replace("-", "–") for p in stability_periods[:2])
    # Every name above is a fact the page or its notes quote.
    return SimpleNamespace(**locals())


def _ranking_table(f: SimpleNamespace) -> str:
    rows = [("All crashes", f.calc, f.tab)] + [
        (ZONE_WORDS[key][:1].upper() + ZONE_WORDS[key][1:], f.zone[key], f.zone_table[key])
        for key in ("interurban", "urban", "through_town")
    ]
    frame = pd.DataFrame(
        {
            "Group": [label for label, _, _ in rows],
            "Crashes": [int(model.n) for _, model, _ in rows],
            "Fatal": [int(model.positives) for _, model, _ in rows],
            "Model": [float(model.roc_auc) for _, model, _ in rows],
            "Table": [float(lookup.roc_auc) for _, _, lookup in rows],
        }
    )
    return table(
        frame,
        f"ROC-AUC of the model and of a table of fatal shares by road and crash type, "
        f"{f.first_test}–{f.last_test}, each year predicted from the years before it. 0.5 is no "
        "better than chance and 1 a perfect ranking.",
        {"Crashes": "int", "Fatal": "int", "Model": "dec2", "Table": "dec2"},
    )


def _tests_table(f: SimpleNamespace) -> str:
    rows = pd.concat([f.tests.iloc[:1], f.left_out.reset_index(drop=True), f.tests.iloc[-1:]])
    labels = [
        f"Last year ({f.later.test_domain}) from the years before it",
        *[f"{name} left out" for name in f.left_out.index],
        "Barcelona city from the rest of Catalonia",
    ]
    frame = pd.DataFrame(
        {
            "Test": labels,
            "Crashes": rows.test_n.to_numpy(),
            "Fatal share": rows.test_prevalence.to_numpy(),
            "Estimated": rows.mean_predicted.to_numpy(),
            "Model": rows.roc_auc.to_numpy(),
            "Same model fitted in the test crashes": rows.in_domain_cv_roc_auc.to_numpy(),
            "Table": rows.table_roc_auc.to_numpy(),
        }
    )
    return table(
        frame,
        "The model on crashes left out of its fitting: the share estimated and observed to be "
        "fatal, and ROC-AUC beside the same model fitted and cross-validated in the test "
        "crashes and beside the table fitted on the training crashes.",
        {
            "Crashes": "int",
            "Fatal share": "pct",
            "Estimated": "pct",
            "Model": "dec2",
            "Same model fitted in the test crashes": "dec2",
            "Table": "dec2",
        },
    )


def page_severity_models(captions: dict[str, str]) -> str:
    f = _facts()
    body = summary(
        "Among crashes in Catalonia in which someone was killed or seriously injured, a "
        "statistical model estimates the share that were fatal (someone died within 24 hours) "
        "from the road, the conditions, the type of crash and who was involved. Predicting each "
        f"year from {f.first_test} to {f.last_test} from earlier years only, it matched the "
        "overall fatal share and ranked crashes better than a simple table, but only moderately "
        f"(ROC-AUC {_auc(f.calc.roc_auc)}), and not at all on roads through towns. A heavy "
        "vehicle involved goes with about twice the fatal share."
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

    body += "<h2>It ranks crashes better than a table, but only moderately</h2>"
    body += (
        "<p>Each year was predicted by a model whose settings and coefficients came only from "
        f"the years before it. A table of the fatal share of each road and crash type, fitted on "
        "the same years, is the benchmark. Over the "
        f"{_fmt_int(f.calc.n)} crashes of {f.first_test}–{f.last_test} the model's ROC-AUC, the "
        "chance that it rates a fatal crash above a non-fatal one, is "
        f"{_auc(f.calc.roc_auc)} and the table's {_auc(f.tab.roc_auc)}; the model's lead is "
        f"{_auc(-f.gap.high)}–{_auc(-f.gap.low)} (95% interval), {f.ahead_text}. On roads "
        f"through towns it does not beat the table ({_auc(f.zone['through_town'].roc_auc)} "
        f"against {_auc(f.zone_table['through_town'].roc_auc)}). Within one kind of road the "
        "ranking is harder, because the kind of road alone separates many fatal crashes from "
        f"the rest: the model ranks interurban crashes best ({_auc(f.zone['interurban'].roc_auc)}) "
        f"and urban ones less well ({_auc(f.zone['urban'].roc_auc)}).</p>"
    )
    body += _ranking_table(f)
    body += (
        "<p>Of the fifth of crashes it "
        f"rated most likely to have been fatal, {_fmt_pct(f.top, 0)} were; of the fifth it "
        f"rated least likely, {_fmt_pct(f.bottom, 0)}. The table separates them less "
        f"({_fmt_pct(f.top_table, 0)} and {_fmt_pct(f.bottom_table, 0)}): the gain is real but "
        "modest. The model cannot say whether a crash will happen, only how often crashes like a "
        "given one were fatal once recorded with a death or serious injury.</p>"
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
        f"<p>Over all the years the model estimated {_fmt_pct(f.calc.mean_predicted)} fatal, "
        f"and {_fmt_pct(f.calc.prevalence)} were "
        f"({_range(f.calc.observed_low, f.calc.observed_high)}); its calibration slope is "
        f"{_fmt_dec(f.slope, 2)}, where 1 means the estimates spread as widely as the outcomes."
        + (
            f" The mean estimate fell outside the observed interval in {_join(f.miss_years)}."
            if f.miss_years
            else ""
        )
        + " By province and kind of road the estimates were less close. On "
        + _join([_miss_text(row) for row in f.misses.itertuples()])
        + " the mean estimate fell outside the 95% interval of the observed share, so an "
        "estimate for those roads should not be taken at face value. "
        + _miss_text(f.outside, "On urban streets outside Barcelona city the estimates ran high")
        + ".</p>"
    )

    body += "<h2>Tested only within Catalonia</h2>"
    body += (
        "<p>No other source records the model's inputs, so it has been tested only on crashes "
        "from the same file: the last year, fitted on the years before it, each province left "
        "out of the fitting in turn, and Barcelona city fitted on the rest of Catalonia. In "
        "every test it ranked the held-out crashes better than the table, but its estimate of "
        f"the fatal share missed for {_join(list(f.left_out_misses.index))}, and fitted without "
        f"Barcelona city it put the city's fatal share too low ({_fmt_pct(f.city.mean_predicted)} "
        f"estimated against {_fmt_pct(f.city.test_prevalence)} observed). The last year, "
        f"{f.later.test_domain}, was estimated at {_fmt_pct(f.later.mean_predicted)} against "
        f"{_fmt_pct(f.later.test_prevalence)} observed. The model should not be used for a "
        "place it was not fitted on.</p>"
    )
    body += _tests_table(f)
    body += figure(
        "sev2_held_out",
        "Dot chart of the model's ROC-AUC on crashes left out of its fitting, with 95% "
        "intervals, beside the same model fitted in the test crashes: the last year, each "
        "province in turn and Barcelona city.",
        captions,
    )
    body += limitation(
        f"The model describes crashes recorded in Catalonia in {f.first_year}–{f.last_year} "
        "on roads with a named owning network or of another type; the crashes on roads whose "
        "owner is recorded as “other” or left blank are left out. “Fatal” means a death within "
        "24 hours, the Catalan definition; Spain's official figures count deaths within 30 "
        "days. The estimates are shares of recorded severe crashes, not the chance that a "
        "person in a crash dies."
    )
    body += downloads(
        [
            ("sev_contrasts", "one input changed at a time"),
            ("sev_stability", "the contrasts on earlier and later years"),
            ("sev_coefficients", "coefficients and bootstrap standard errors"),
            ("sev_rolling_scores", "scores by year, zone, province and Barcelona city"),
            ("sev_comparison", "differences between the model, the trees and the table"),
            ("sev_calibration", "predicted against observed, by tenth"),
            ("sev_tests", "years and places left out of the fitting"),
            ("sev_geography", "provinces and Barcelona city's urban streets left out"),
            ("sev_population", "the crashes left out and the fatal share"),
            ("sev_choices", "the settings chosen for each test year and for the model"),
        ],
        method=("data.html#how-the-model-was-built", "how the model was built"),
    )
    return render_page(
        "severity-models",
        "Crash severity model",
        "How well a model of crashes in Catalonia tells which crashes with a death or serious "
        "injury were fatal, and which circumstances it associates with a fatal outcome.",
        body,
    )


def technical_notes(captions: dict[str, str]) -> str:
    """How the Catalan severity model was built, for the methodology page."""
    del captions
    f = _facts()
    published, yearly = f.published, f.yearly
    final_grid_low = _fmt_c(published.c_lowest_tried)
    final_grid_high = _fmt_c(published.c_highest_tried)
    specification = (
        "one term for each other input, the same on every kind of road"
        if published.specification == "common"
        else "one term for each other input, which may differ between urban streets and "
        "interurban roads"
    )
    return (
        '<h2 id="how-the-model-was-built">How the Catalan severity model was built</h2>'
        f"<p>The model is a penalised logistic regression fitted to the {_fmt_int(f.fitted_all.crashes)} "
        f"crashes of {f.first_year}–{f.last_year} in the Servei Català de Trànsit's file. It has "
        "a starting level for each zone (urban street, road through a town, interurban road) "
        f"in each province, and {specification}. Its settings were chosen by the rule used for "
        f"every test year: fitted on {published.train_years.replace('-', '–')} and scored on "
        f"{published.validation_years.replace('-', '–')}, the "
        f"{SPECIFICATION_WORDS[published.specification]} predicted better than the "
        f"{SPECIFICATION_WORDS[_other(published.specification)]}, with a penalty setting C of "
        f"{_fmt_c(published.c)} (a smaller C penalises the terms more strongly), chosen from "
        f"values between {final_grid_low} and {final_grid_high} (the grid is extended while "
        "its best value lies at an end) and better than its neighbours on both sides; "
        + (
            "roads through towns get the average fatal share of such roads in the province "
            "because it predicted those years better than the model; "
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
            f"; in {_join([str(y) for y in f.at_limit.fit])} "
            "the best penalty was the weakest the grid allows, where the validation loss had "
            "stopped changing, so that year's model is in effect unpenalised"
            if len(f.at_limit)
            else ""
        )
        + ". Its intervals come from refitting it on crashes resampled with replacement.</p>"
        "<p>Left out are "
        f"{_fmt_int(f.excluded.crashes)} crashes on conventional roads whose owner is recorded "
        "as “other” or left blank: a blank owner is far commoner on fatal records and “other” "
        "on non-fatal ones, so the field records how a crash was documented, not the road. "
        "The estimates, the averages and the tests therefore describe crashes on roads with a "
        f"named owning network or of another type. The crashes left out were fatal in "
        f"{_fmt_pct(f.excluded.fatal_share)} of cases. With them, "
        f"{_fmt_pct(f.everything.fatal_share)} of all crashes would count as fatal instead of "
        f"{_fmt_pct(f.fitted_all.fatal_share)}, and "
        f"{_fmt_pct(f.everything_interurban.fatal_share)} of interurban crashes instead of "
        f"{_fmt_pct(f.fitted_interurban.fatal_share)}.</p>"
        "<p>A more flexible method, gradient-boosted trees, ranked crashes "
        f"{f.trees_compared} ({_auc(f.trees.roc_auc)}) but gives no interval for an estimate and "
        f"cannot be read term by term, so the logistic model is the one published. The method "
        f'is described in the <a href="{MODEL_DOC}">model note</a>.</p>'
    )
