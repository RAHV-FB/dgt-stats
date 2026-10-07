"""The severity models: the two that rank recorded cases better than a descriptive table, and the
table of shares by accident type that stands for the third."""

from __future__ import annotations

import re

import pandas as pd

from dgt_stats.microdata.barcelona import ACCIDENT_TYPES
from dgt_stats.microdata.ml.modelling import CALIBRATION_LARGE_TOLERANCE, CALIBRATION_SLOPE_RANGE
from dgt_stats.microdata.ml.rules import MIN_GAIN
from dgt_stats.microdata.validation import decisions as decision_rules
from dgt_stats.microdata.validation.transport import MIN_SUBGROUP_POSITIVES
from dgt_stats.site.components import (
    DOCS_URL,
    _fmt_dec,
    _fmt_int,
    _fmt_pct,
    _join,
    downloads,
    esc,
    figure,
    read_table,
    render_page,
    summary,
    table,
    technical,
)
from dgt_stats.site.regional_common import CARDS, MIN_N, _check, _year_label

PAGE = "severity models"
# The three models trained on regional records, in the order the page discusses them.
NAMES = {
    "catalonia_crash_severity": "Catalonia severity model",
    "barcelona_person_severity": "Barcelona person-severity model",
    "barcelona_crash_severity": "Barcelona crash model",
}
# Shorter labels for the technical tables, where the column already says "Model".
SHORT = {
    "catalonia_crash_severity": "Catalonia severity",
    "barcelona_person_severity": "Barcelona person-severity",
    "barcelona_crash_severity": "Barcelona crash",
}
KEPT = ["catalonia_crash_severity", "barcelona_person_severity"]
REPLACED = ["barcelona_crash_severity"]
# The two fitting methods, in the words the rest of the site uses.
METHODS = {"logistic": "logistic regression", "boosted_trees": "gradient-boosted trees"}
# The grouping of each descriptive table, as the result table names it, in words.
RULE_LABELS = {
    "D_SUBTIPUS_ACCIDENT x D_SUBZONA": ("crash subtype × zone", "crash subtype and zone"),
    "person_role x associated_vehicle_group": (
        "road-user role × vehicle group",
        "road-user role and vehicle group",
    ),
    "accident_type": ("accident type", "accident type"),
}
# What the version with information recorded after the crash adds to each model.
RETROSPECTIVE = {
    "catalonia_crash_severity": "police judgements of which conditions influenced the crash, "
    "and fields whose completeness follows the outcome",
    "barcelona_person_severity": "causes recorded by the police",
    "barcelona_crash_severity": "causes recorded by the police",
}
# The variables the importance figures rank highest, in words.
FEATURES = {
    "D_TITULARITAT_VIA": "the road's owner",
    "D_SUBZONA": "the zone (urban street, interurban road or road through a town)",
    "D_SUBTIPUS_ACCIDENT": "the crash subtype",
    "involves_heavy_vehicle": "the presence of a heavy vehicle",
    "speed_limit_category": "the posted speed limit",
    "D_TIPUS_VIA": "the road type",
    "associated_vehicle_group": "the vehicle group on the person's record",
    "accident_type": "the accident type",
    "person_role": "the road-user role (driver, passenger or pedestrian)",
    "pedestrian_location": "where a pedestrian was struck",
    "age": "age",
}
# The Catalan model's three leading variables, as the importance table names them.
OWNER, ZONE, SUBTYPE = "D_TITULARITAT_VIA", "D_SUBZONA", "D_SUBTIPUS_ACCIDENT"
# The two Barcelona accident types a reader may take for one: the Guàrdia Urbana's own categories.
CATCHING_UP, REAR_END = "rear collision while catching up", "rear-end collision"
SOURCE_TYPE = {label: code for code, label in ACCIDENT_TYPES.items()}
SUBGROUP_DIMENSIONS = ("all", "role", "associated vehicle", "age band", "sex")
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 9: "nine", 10: "ten"}
FRACTIONS = {5: "fifth", 10: "tenth"}
CATALAN_DESIGN = re.compile(r"train (\d{4})-(\d{4}), choose on (\d{4})-(\d{4}), test (\d{4})")
BARCELONA_DESIGN = re.compile(
    r"train months (\d+)-(\d+) with \d+-fold cross-validation grouped by crash; "
    r"test months (\d+)-(\d+)"
)


def _word(value: int) -> str:
    return WORDS.get(value, str(value))


def _signed(value: float, decimals: int = 2) -> str:
    """A difference with its sign, for the tables: +0.09, −0.04, and 0.00 without one."""
    if round(value, decimals) == 0:
        return f"{0:.{decimals}f}"
    return ("+" if value > 0 else "") + _fmt_dec(value, decimals)


def _range(low: float, high: float, decimals: int = 2) -> str:
    """An interval in prose: 0.07–0.12 when both ends are unsigned, −0.04 to 0.05 otherwise."""
    if round(low, decimals) < 0 or round(high, decimals) < 0:
        return f"{_fmt_dec(low, decimals)} to {_fmt_dec(high, decimals)}"
    return f"{_fmt_dec(low, decimals)}–{_fmt_dec(high, decimals)}"


def _pair(a: float, b: float, each: str = "") -> str:
    """Two figures that may round alike: 'about 0.15' rather than '0.15 and 0.15'."""
    return f"about {a:.2f}{each}" if f"{a:.2f}" == f"{b:.2f}" else f"{a:.2f} and {b:.2f}"


def _auc_ci(row) -> str:
    return f"{row.roc_auc:.2f} ({row.roc_auc_low:.2f}–{row.roc_auc_high:.2f})"


def _gain_ci(rule, label: str = "") -> str:
    """The gain over the table with its interval; ``label`` names the interval where needed."""
    return (
        f"{_fmt_dec(rule.roc_auc_gain, 2)} "
        f"({label}{_range(rule.roc_auc_gain_low, rule.roc_auc_gain_high)})"
    )


def _feature(name: str) -> str:
    _check(name in FEATURES, PAGE, f"the variable {name} has a label")
    return FEATURES[name]


def _age_band(level: str) -> str:
    """'25-34' as 25–34 and the open band '75+' as 75 and over."""
    return f"{level[:-1]} and over" if level.endswith("+") else level.replace("-", "–")


def _subgroup_label(row) -> str:
    level = str(row.level).replace("_", " ")
    if row.dimension == "all":
        return "Everyone"
    if row.dimension == "role":
        return f"{level.capitalize()}s"
    if row.dimension == "associated vehicle":
        return f"Vehicle group: {level}"
    if row.dimension == "age band":
        return f"Aged {_age_band(level)}"
    return level.capitalize()


def _subgroup_prose(row) -> str:
    level = str(row.level).replace("_", " ")
    if row.dimension == "role":
        return f"{level}s"
    if row.dimension == "associated vehicle":
        article = "an" if level[0] in "aeiou" else "a"
        return f"people whose record names {article} {level}"
    if row.dimension == "age band":
        return f"people aged {_age_band(level)}"
    return f"{level} road users"


def page_severity_models(captions: dict[str, str]) -> str:
    selected = read_table("ml_selected")
    places = read_table("ml_geography")
    rules = read_table("ml_rule_comparison").set_index("model")
    decisions = read_table("ml_model_decisions")
    calibration = read_table("ml_calibration")
    importance = read_table("ml_importance")
    artefacts = read_table("ml_recording_artefacts")
    subgroups = read_table("ml_subgroup_validation")
    crashes = read_table("bcn_crash_severity_share")
    rare = read_table("ml_rare_causes").set_index("label")
    transport = read_table("ml_transport_validation")
    path = read_table("ml_outward_path")
    audit = read_table("dgt_audit_checks")
    primary = selected[selected.primary].set_index("model")
    retro = selected[~selected.primary].set_index("model")
    year = _year_label(crashes)

    # The page is written around the declared decisions: two models kept, the third replaced by
    # its descriptive table. Each kept model beats chance and its table; the replaced one does not.
    models = [m for m in NAMES if m in rules.index]
    context = decisions[decisions.model.isin(models) & decisions.variant.eq("context")]
    context = context.set_index("model").decision
    kept = [m for m in models if context[m] in decision_rules.FEATURED]
    replaced = [m for m in models if context[m] == decision_rules.REPLACE]
    _check(kept == KEPT and replaced == REPLACED, PAGE, "two models kept, one replaced")
    for name in models:
        row, rule = primary.loc[name], rules.loc[name]
        _check(row.roc_auc_low > 0.5, PAGE, f"{name} beats chance")
        _check(
            bool(rule.model_adds_signal_over_table) == (name in kept),
            PAGE,
            f"{name}: the decision follows the table comparison",
        )
        _check(rule.rule in RULE_LABELS, PAGE, f"{name}: the table's grouping has a label")
        _check(row.estimator in METHODS, PAGE, f"{name}: the method has a name")
        # The method kept for each model is the one that ranked the validation records better.
        options = places[
            places.model.eq(name)
            & places.feature_set.eq(row.feature_set)
            & places.geography.eq(row.geography)
        ]
        best = options.loc[options.validation_roc_auc.idxmax()].estimator
        _check(best == row.estimator, PAGE, f"{name}: the method was chosen on validation")
    cat, person, crash = (primary.loc[m] for m in models)
    _check(bool(cat.probabilities_shown_as_estimates), PAGE, "Catalan probabilities calibrated")
    _check(
        not person.probabilities_shown_as_estimates, PAGE, "Barcelona probabilities not calibrated"
    )

    catalan = CATALAN_DESIGN.fullmatch(cat.design)
    barcelona = BARCELONA_DESIGN.fullmatch(person.design)
    _check(catalan is not None and barcelona is not None, PAGE, "the split designs are read")
    _check(person.design == crash.design, PAGE, "both Barcelona models share one split")
    train_years = f"{catalan.group(1)}–{catalan.group(2)}"
    choice_years = f"{catalan.group(3)}–{catalan.group(4)}"
    test_year = catalan.group(5)
    train_months = int(barcelona.group(2)) - int(barcelona.group(1)) + 1
    test_months = int(barcelona.group(4)) - int(barcelona.group(3)) + 1
    _check("–" not in year, PAGE, "Barcelona's records cover a single year")

    def bins(model: str) -> pd.DataFrame:
        frame = calibration[
            calibration.model.eq(model) & calibration.feature_set.eq(primary.loc[model].feature_set)
        ].sort_values("bin")
        _check(len(frame) in FRACTIONS, PAGE, f"{model}: calibration bins are tenths or fifths")
        _check(
            int(frame.n.sum()) == int(primary.loc[model].n)
            and int(frame.positives.sum()) == int(primary.loc[model].positives),
            PAGE,
            f"{model}: the calibration bins cover the test records",
        )
        return frame

    def reliance(model: str) -> pd.DataFrame:
        row = primary.loc[model]
        return importance[
            importance.model.eq(model)
            & importance.feature_set.eq(row.feature_set)
            & importance.estimator.eq(row.estimator)
        ].sort_values("auc_drop_mean", ascending=False)

    body = summary(
        f"{_word(len(kept)).capitalize()} models rank recorded cases by severity better than a "
        "descriptive table of the same records, on later records not used to build them. The "
        f"{NAMES[models[0]]} estimates which crashes with a death or serious injury in Catalonia "
        "were fatal, and its probabilities match the observed shares in the test year. The "
        f"{NAMES[models[1]]} estimates which people in Barcelona crashes were seriously or "
        "fatally injured; it ranks people well, but its probabilities are not calibrated, so it "
        f"is used for ranking only. A third model, the {NAMES[models[2]]}, ranked crashes no "
        "better than a table of the share of crashes with a serious or fatal injury by accident "
        "type, and the table is used instead."
    )

    # ------------------------------------------------------------------- ranking and calibration
    low, high = CALIBRATION_SLOPE_RANGE
    body += "<h2>Ranking and calibration</h2>"
    body += (
        "<p>Each model was built on earlier records and tested once on later ones. The "
        f"{NAMES[models[0]]} was fitted to crashes from {train_years}, tuned on {choice_years} "
        f"and tested on {test_year}. Barcelona's records cover only {year}, so the two Barcelona "
        f"models were fitted to its first {_word(train_months)} months and tested on the last "
        f"{_word(test_months)}.</p>"
    )
    body += (
        "<p>Ranking is measured by the ROC-AUC: the probability that a randomly chosen case with "
        "the outcome (a fatal crash, or a person seriously or fatally injured) scores higher than "
        "one without it; 0.5 is chance and 1 a perfect ranking. Each model is compared with a "
        "descriptive table, fixed in advance, of the share of cases with the outcome in each "
        "group of the training records. Calibration is the agreement between predicted "
        "probabilities and observed shares: among cases given a probability of one in ten, about "
        "one in ten should have the outcome "
        '(<a href="data.html#models">Methodology</a>).</p>'
    )
    body += figure(
        "ml1_test_auc",
        "Dot chart of the ROC-AUC on the test records for each of the three models, the "
        "descriptive table it was compared with and a baseline that gives every case the same "
        "probability, with 95% intervals for the models. The Catalonia severity and Barcelona "
        "person-severity models score above their tables; the Barcelona crash model scores level "
        "with its table.",
        captions,
    )

    # ------------------------------------------------------------------------------ Catalonia
    rule = rules.loc[models[0]]
    deciles = bins(models[0])
    top, bottom = deciles.iloc[-1], deciles.iloc[0]
    part = FRACTIONS[len(deciles)]
    _check(
        low <= cat.calibration_slope <= high, PAGE, "the Catalan calibration slope is close to 1"
    )
    city = transport[
        transport.experiment.eq("rest of Catalonia -> Barcelona municipality")
        & transport.model.eq(models[0])
        & transport.estimator.eq(cat.estimator)
        & transport.status.eq("reported")
    ].iloc[0]
    _check(
        not low <= city.calibration_slope <= high,
        PAGE,
        "the Catalan model's calibration does not carry over to Barcelona city",
    )
    body += f"<h2>The {NAMES[models[0]]}</h2>"
    body += (
        f"<p>The {NAMES[models[0]]} estimates, for each crash with a death or serious injury in "
        "the Catalan file, the probability that it was fatal, from the recorded circumstances of "
        f"the road, the crash and its environment. Its test set is the {_fmt_int(cat.n)} crashes "
        f"of {test_year}, of which {_fmt_int(cat.positives)} ({_fmt_pct(cat.prevalence)}) were "
        "fatal.</p>"
    )
    body += (
        "<p>On those crashes it ranks clearly better than the table of fatal shares by "
        f"{RULE_LABELS[rule.rule][1]} ({int(rule.rule_groups_in_training)} groups): ROC-AUC "
        f"{cat.roc_auc:.2f} (95% interval {cat.roc_auc_low:.2f}–{cat.roc_auc_high:.2f}) against "
        f"{rule.rule_roc_auc:.2f}, a gain of {_gain_ci(rule)}. In the {part} of test crashes it "
        f"ranks highest ({_fmt_int(top.n)}), {_fmt_pct(top.observed)} were fatal, "
        f"{int(top.positives)} of the {_fmt_int(cat.positives)}; in the lowest {part}, "
        f"{_fmt_pct(bottom.observed)} were.</p>"
    )
    body += (
        "<p>Its probabilities also match the observed shares: an average predicted fatal share of "
        f"{_fmt_pct(cat.mean_predicted)} against {_fmt_pct(cat.prevalence)} observed, "
        f"{_fmt_pct(top.mean_predicted)} against {_fmt_pct(top.observed)} in the highest {part}, "
        f"and a calibration slope of {cat.calibration_slope:.2f}, close to the value of 1 at which "
        "predictions are neither too spread out nor too compressed. Among Catalan crashes like "
        "those tested, the probabilities therefore estimate the fatal share of groups of similar "
        "crashes. "
        "They do not carry over to Barcelona city: trained on the rest of Catalonia and applied "
        f"there, the same model has a calibration slope of {city.calibration_slope:.2f}.</p>"
    )
    ranked = reliance(models[0])
    first = ranked.head(3)
    table_columns = set(rule.rule.split(" x "))
    _check(
        set(first.feature.iloc[:2]) == {OWNER, ZONE}
        and first.feature.iloc[2] == SUBTYPE
        and table_columns == {ZONE, SUBTYPE},
        PAGE,
        "the road's owner and the zone lead, then the crash subtype; the table uses the last two",
    )
    spread = first.set_index("feature")
    _check(
        abs(spread.auc_drop_mean[OWNER] - spread.auc_drop_mean[ZONE])
        <= max(spread.auc_drop_std[OWNER], spread.auc_drop_std[ZONE]),
        PAGE,
        "the road's owner and the zone are close given the variation between shuffles",
    )
    blank_owner = artefacts[
        artefacts.column.eq(OWNER)
        & artefacts.structural_explanation.fillna("").str.startswith("urban street")
    ]
    _check(
        len(blank_owner) == 1 and blank_owner.structural_coverage.iloc[0] >= 0.9,
        PAGE,
        "the road's owner is left blank for urban streets",
    )
    labels = [_feature(f) for f in first.feature]
    drops = [f"{d:.2f}" for d in first.auc_drop_mean]
    body += (
        "<p>Shuffling one variable at a time and measuring how far the test ROC-AUC falls shows "
        f"what the model relies on. The largest falls come from {labels[0]}, {labels[1]} and "
        f"{labels[2]} ({drops[0]}, {drops[1]} and {drops[2]}). The first two are close, given how "
        "much the falls vary between shuffles, and they overlap: the owner is left blank for "
        "urban streets, so it also carries the urban–interurban distinction that the zone "
        "records. The zone and the crash subtype are the dimensions of the comparison table.</p>"
    )
    body += figure(
        f"ml3_importance_{models[0]}",
        f"Chart of the variables the {NAMES[models[0]]} relies on most, measured by the fall in "
        f"its test ROC-AUC when each is shuffled; {labels[0]}, {labels[1]} and {labels[2]} lead.",
        captions,
    )
    allowed = audit.decision.iloc[0].startswith("DGT microdata may train")
    _check(not allowed, PAGE, "the DGT audit keeps DGT records out of training")
    failed = set(audit.loc[~audit.passed, "check"].str.split(" ", n=1).str[1])
    _check(
        "comparable across regions" in failed,
        PAGE,
        "the DGT audit fails on recording that differs between provinces",
    )
    harmonised = primary.loc["catalonia_common_dgt"]
    national = transport[
        transport.experiment.eq("Catalonia -> Spain outside Catalonia")
        & transport.estimator.eq(harmonised.estimator)
        & transport.status.eq("reported")
    ].iloc[0]
    _check(-0.01 <= national.transfer_gap <= 0, PAGE, "the national test ranks almost as well")
    target = decisions[decisions.model.eq("catalonia_common_dgt")].target
    _check(
        len(target) == 1 and "death within 24 hours" in target.iloc[0],
        PAGE,
        "the national test's outcome is a death within 24 hours",
    )
    population = path[path.model.eq("catalonia_common_dgt") & path.stage.eq(5)]
    _check(
        population.status.eq("failed").all()
        and not path.verdict.eq("potentially nationally transferable").any(),
        PAGE,
        "Catalonia's crashes differ from Spain's, so national use is not established",
    )
    body += (
        "<p>DGT's national crash records are filled in too unevenly between provinces to train "
        'a model (<a href="sources.html">Data sources and scope</a>), but they can test one. '
        "Restricted to the variables both sources record in the same way, the harmonised "
        "Catalonia model ranks "
        f"fatal outcomes (a death within 24 hours) among {_fmt_int(national.test_n)} serious "
        "and fatal crashes DGT "
        "recorded elsewhere in Spain almost as well as a model trained on them (ROC-AUC "
        f"{national.roc_auc:.3f} against {national.in_domain_cv_roc_auc:.3f}). Catalonia's "
        "serious and fatal crashes differ from Spain's, however, so national use is not "
        'established (<a href="validation.html">External validation</a>).</p>'
    )

    # ------------------------------------------------------------------- Barcelona person model
    rule = rules.loc[models[1]]
    fifths = bins(models[1])
    top, lowest = fifths.iloc[-1], fifths.iloc[:2]
    part = FRACTIONS[len(fifths)]
    _check(
        abs(person.mean_predicted - person.prevalence)
        <= CALIBRATION_LARGE_TOLERANCE * person.prevalence,
        PAGE,
        "the Barcelona predictions are right on average",
    )
    _check(person.calibration_slope < low, PAGE, "the Barcelona predictions are too spread out")
    _check(
        top.mean_predicted > top.observed
        and (fifths.observed > fifths.mean_predicted).iloc[:-1].any(),
        PAGE,
        "the highest Barcelona scores overstate the outcome and a lower group understates it",
    )
    missed = int(lowest.positives.sum())
    _check(top.mean_predicted < 0.1, PAGE, "the Barcelona calibration points are at low values")
    _check(
        rule.roc_auc_gain_high - rule.roc_auc_gain_low
        > rules.loc[models[0]].roc_auc_gain_high - rules.loc[models[0]].roc_auc_gain_low,
        PAGE,
        "the Barcelona gain is less precisely estimated than the Catalan one",
    )
    predicted, observed = _fmt_pct(person.mean_predicted), _fmt_pct(person.prevalence)
    average = (
        f"{predicted} predicted and observed"
        if predicted == observed
        else f"{predicted} predicted against {observed} observed"
    )
    body += f"<h2>The {NAMES[models[1]]}</h2>"
    body += (
        "<p>The Guàrdia Urbana's records list each person involved in a Barcelona crash, with "
        f"their role, the vehicle on their record, age and sex. The {NAMES[models[1]]} estimates "
        "the probability that a person was seriously or fatally injured. In the test months it "
        f"scored {_fmt_int(person.n)} people; {_fmt_int(person.positives)} of them "
        f"({_fmt_pct(person.prevalence)}) had such an injury.</p>"
    )
    body += (
        "<p>It ranks them better than the table of shares by "
        f"{RULE_LABELS[rule.rule][1]} ({int(rule.rule_groups_in_training)} groups): ROC-AUC "
        f"{person.roc_auc:.2f} (95% interval {person.roc_auc_low:.2f}–"
        f"{person.roc_auc_high:.2f}) against {rule.rule_roc_auc:.2f}, a gain of "
        f"{_gain_ci(rule)}. With only {_fmt_int(person.positives)} serious or fatal cases the "
        "gain is less precisely estimated than in Catalonia, and a single year of records allows "
        f"no test on another year. The {part} of people it ranks highest ({_fmt_int(top.n)}) "
        f"includes {int(top.positives)} of the {_fmt_int(person.positives)}; the two {part}s it "
        f"ranks lowest ({_fmt_int(lowest.n.sum())} people) include "
        f"{'none' if missed == 0 else _fmt_int(missed)}.</p>"
    )
    body += (
        f"<p>Its probabilities are right on average ({average}), but the calibration slope is "
        f"{person.calibration_slope:.2f}: the predictions are too spread "
        "out, so the highest scores overstate the chance of serious injury and lower ones "
        f"understate it ({_fmt_pct(top.mean_predicted)} predicted on average in the highest "
        f"{part}, {_fmt_pct(top.observed)} observed). The probabilities are therefore not reliable "
        "as the share of similar cases with a serious injury, and the model is used only to rank "
        "people.</p>"
    )
    body += figure(
        "ml2_calibration",
        f"Calibration chart for the {NAMES[models[0]]} and the {NAMES[models[1]]}: the observed "
        "share of cases with the outcome against the average predicted probability, in "
        f"equal-sized groups of test records. The {NAMES[models[0]]}'s points lie close to the "
        "diagonal, where predicted and observed shares are equal; the "
        f"{NAMES[models[1]]}'s points are bunched at low probabilities.",
        captions,
    )
    ranked = reliance(models[1])
    first = ranked.head(4)
    drops = list(first.auc_drop_mean)
    _check(min(drops[:2]) >= 3 * drops[2], PAGE, "two variables dominate the Barcelona model")
    labels = [_feature(f) for f in first.feature]
    body += (
        f"<p>The model relies above all on two variables, {labels[0]} and {labels[1]}: "
        f"shuffling either lowers the test ROC-AUC by {_pair(drops[0], drops[1])}. "
        f"{labels[2].capitalize()} and {labels[3]} follow well behind "
        f"({_pair(drops[2], drops[3], ' each')}).</p>"
    )
    body += figure(
        f"ml3_importance_{models[1]}",
        f"Chart of the variables the {NAMES[models[1]]} relies on most, measured by the fall in "
        f"its test ROC-AUC when each is shuffled; {labels[0]} and {labels[1]} stand far above "
        "the rest.",
        captions,
    )

    shown = subgroups[subgroups.dimension.isin(SUBGROUP_DIMENSIONS)]
    enough = (shown.positives >= MIN_SUBGROUP_POSITIVES) & (
        shown.n - shown.positives >= MIN_SUBGROUP_POSITIVES
    )
    _check(bool((shown.auc_reported == enough).all()), PAGE, "group scores need enough cases")
    shown = shown[shown.auc_reported]
    everyone = shown[shown.dimension.eq("all")].iloc[0]
    groups = shown[shown.dimension.ne("all")]
    roles = groups[groups.dimension.eq("role")].set_index("level")
    pedestrians = roles.loc["pedestrian"]
    best = groups.loc[groups.roc_auc.idxmax()]
    _check(
        pedestrians.roc_auc == groups.roc_auc.min() and pedestrians.roc_auc - 0.5 < 0.1,
        PAGE,
        "pedestrians are ranked worst, little better than chance",
    )
    _check(
        pedestrians.observed == roles.observed.max() and pedestrians.observed > everyone.observed,
        PAGE,
        "pedestrians are the road users most often seriously hurt",
    )
    body += (
        "<p>The test months hold too few serious cases to score groups of road users, so every "
        f"person recorded in {year} was scored by a version of the model fitted without their "
        f"crash. The ROC-AUC is then {everyone.roc_auc:.2f} for everyone "
        f"and can be computed for {len(groups)} groups with at least {MIN_SUBGROUP_POSITIVES} "
        "serious or fatal cases. It is highest "
        f"for {_subgroup_prose(best)} ({best.roc_auc:.2f}) and lowest for pedestrians "
        f"({pedestrians.roc_auc:.2f}), little better than chance, although pedestrians are the "
        f"road users most often seriously hurt ({_fmt_pct(pedestrians.observed)}, "
        f"{int(pedestrians.positives)} of {_fmt_int(pedestrians.n)}, against "
        f"{_fmt_pct(everyone.observed)} for everyone). The model should not be relied on to rank "
        "pedestrians.</p>"
    )
    body += table(
        pd.DataFrame(
            {
                "Group": [_subgroup_label(r) for r in shown.itertuples()],
                "People": shown.n,
                "Serious or fatal": shown.positives,
                "Observed share": shown.observed,
                "Average prediction": shown.mean_predicted,
                "ROC-AUC": shown.roc_auc,
            }
        ),
        f"{NAMES[models[1]]} by group of road users, {year}: each person scored by a "
        f"version fitted without their crash; groups with at least {MIN_SUBGROUP_POSITIVES} "
        "serious or fatal cases.",
        {
            "People": "int",
            "Serious or fatal": "int",
            "Observed share": "pct",
            "Average prediction": "pct",
            "ROC-AUC": "dec2",
        },
    )

    # ------------------------------------------------------------------- Barcelona crash table
    rule = rules.loc[models[2]]
    _check(
        rule.roc_auc_gain_low < 0 < rule.roc_auc_gain_high,
        PAGE,
        "the Barcelona crash model ranks no better than its table",
    )
    types = crashes[crashes.dimension.eq("crash type") & crashes.n.ge(MIN_N)].sort_values(
        "share", ascending=False
    )
    _check(not types.empty, PAGE, "the accident-type table exists")
    coded = types.set_index("level")
    _check(
        {CATCHING_UP, REAR_END} <= set(coded.index)
        and CATCHING_UP in SOURCE_TYPE
        and REAR_END in SOURCE_TYPE,
        PAGE,
        "the two rear collision types are in the table, with their source categories",
    )
    body += "<h2>Barcelona crashes: shares by accident type</h2>"
    body += (
        f"<p>The {NAMES[models[2]]} estimated whether a recorded crash involved a serious or "
        f"fatal injury. On the {_fmt_int(crash.n)} crashes of the test months "
        f"({_fmt_int(crash.positives)} with such an injury) it ranked no better than the table "
        f"of shares by {RULE_LABELS[rule.rule][1]}: ROC-AUC {crash.roc_auc:.2f} against "
        f"{rule.rule_roc_auc:.2f}, a difference of {_gain_ci(rule, '95% interval ')}. The table is simpler and "
        "ranks as well, so it is used in place of the model; below, it is computed over all "
        "crashes of the year.</p>"
    )
    body += table(
        pd.DataFrame(
            {
                "Accident type": types.label.str[:1].str.upper() + types.label.str[1:],
                "Crashes": types.n,
                "Serious or fatal": types.events,
                "Share": types.share,
                "95% interval": [
                    f"{_fmt_pct(lo)[:-1]}–{_fmt_pct(hi)}"
                    for lo, hi in zip(types.ci_low, types.ci_high)
                ],
            }
        ),
        f"Barcelona, {year}: share of crashes with a serious or fatal injury, by accident type as "
        f"coded by the Guàrdia Urbana (types with at least {MIN_N} crashes).",
        {"Crashes": "int", "Serious or fatal": "int", "Share": "pct"},
    )
    body += (
        "<p>The Guàrdia Urbana codes a rear "
        f'collision while catching up (<i lang="ca">{esc(SOURCE_TYPE[CATCHING_UP].lower())}</i>, '
        f"{_fmt_int(coded.n[CATCHING_UP])} crashes) separately from a rear-end collision "
        f'(<i lang="ca">{esc(SOURCE_TYPE[REAR_END].lower())}</i>, '
        f"{_fmt_int(coded.n[REAR_END])}).</p>"
    )

    # ---------------------------------------------------------------- prediction and explanation
    gains = {m: retro.loc[m].roc_auc - primary.loc[m].roc_auc for m in models}
    _check(
        all(0 < gains[m] < 0.01 for m in kept),
        PAGE,
        "information recorded after the crash improves the kept models by less than 0.01",
    )
    insufficient = rare.verdict.str.startswith("insufficient")
    speed, drugs = rare.loc["excessive or inappropriate speed"], rare.loc["drugs or medication"]
    _check(
        bool(insufficient["excessive or inappropriate speed"])
        and bool(insufficient["drugs or medication"]),
        PAGE,
        "speed and drugs are too rare to model",
    )
    body += "<h2>Prediction and explanation</h2>"
    body += (
        "<p>Both models are observational predictions: they learn which recorded circumstances "
        "go with a severe outcome among crashes that have already happened, and are judged by "
        f"whether that pattern holds on later records. The {NAMES[models[0]]} shows in which "
        "kinds of road and crash the outcome is most often fatal and, within the population on "
        "which its calibration was checked, gives the number of fatal crashes to expect. The "
        f"{NAMES[models[1]]} orders people by their relative chance of serious injury, without "
        "estimating how many will be hurt.</p>"
    )
    body += (
        "<p>A ranking of this kind does not identify causes, for three reasons. First, the "
        "records contain no measure of exposure, so each model estimates severity given that a "
        'crash happened and was recorded (<a href="data.html#records">Methodology</a>). Second, '
        "the variables a model relies on are bound up with others the records do not contain: "
        "the road's owner, for example, cannot itself injure anyone, and stands for differences "
        "between roads, from whether they are urban to features the records do not measure. "
        "Third, part of each record is written after the outcome is known, such as the police's "
        "judgement of which conditions influenced a Catalan crash or the causes they record in "
        "Barcelona; versions of the models that add this information rank better by less than "
        "0.01 and are not used for prediction. In Barcelona, "
        f"{_word(int(insufficient.sum()))} of the {len(rare)} recorded causes are too rare "
        "to model, among them excessive or inappropriate speed "
        f"({_fmt_int(speed.crashes_recorded)} crashes in {year}) and drugs or medication "
        f"({_fmt_int(drugs.crashes_recorded)}); the "
        '<a href="barcelona.html">Barcelona</a> page describes them.</p>'
    )
    body += (
        "<p>Separating the effect of one factor from the circumstances it travels with requires "
        "a design these records do not provide: a comparison of otherwise similar roads, for "
        "example, or a change in one factor while the others stay fixed. The models describe "
        "where severe outcomes concentrate among recorded crashes.</p>"
    )

    # -------------------------------------------------------------------------------- technical
    forecast = decisions[decisions.model.eq("dgt_monthly_deaths_forecast")].decision.iloc[0]
    _check(forecast not in decision_rules.FEATURED, PAGE, "the forecast is not a featured model")
    performance = pd.DataFrame(
        {
            "Model": [SHORT[m] for m in models],
            "Test records": [primary.loc[m].n for m in models],
            "With outcome": [
                f"{_fmt_int(primary.loc[m].positives)} ({_fmt_pct(primary.loc[m].prevalence)})"
                for m in models
            ],
            "ROC-AUC": [_auc_ci(primary.loc[m]) for m in models],
            "PR-AUC": [primary.loc[m].pr_auc for m in models],
            "Brier": [_fmt_dec(primary.loc[m].brier, 3) for m in models],
            "Calibration slope": [
                f"{primary.loc[m].calibration_slope:.2f} "
                f"({primary.loc[m].calibration_slope_low:.2f}–"
                f"{primary.loc[m].calibration_slope_high:.2f})"
                for m in models
            ],
        }
    )
    comparison = pd.DataFrame(
        {
            "Model": [SHORT[m] for m in models],
            "Table grouping": [RULE_LABELS[rules.loc[m].rule][0] for m in models],
            "Groups": [rules.loc[m].rule_groups_in_training for m in models],
            "Table ROC-AUC": [rules.loc[m].rule_roc_auc for m in models],
            "Model ROC-AUC": [rules.loc[m].model_roc_auc for m in models],
            "Difference": [
                f"{_signed(rules.loc[m].roc_auc_gain)} ({_signed(rules.loc[m].roc_auc_gain_low)} "
                f"to {_signed(rules.loc[m].roc_auc_gain_high)})"
                for m in models
            ],
            "Adds to the table": ["yes" if m in kept else "no" for m in models],
        }
    )
    later = pd.DataFrame(
        {
            "Model": [SHORT[m] for m in models],
            "Information added": [RETROSPECTIVE[m] for m in models],
            "ROC-AUC": [f"{retro.loc[m].roc_auc:.3f}" for m in models],
            "Main model": [f"{primary.loc[m].roc_auc:.3f}" for m in models],
            "Difference": [_signed(gains[m], 3) for m in models],
        }
    )
    geography = []
    for name, broad_place, fine_place in (
        (models[0], "province", "municipality"),
        (models[1], "district", "neighbourhood"),
    ):
        row = primary.loc[name]
        geo = places[
            places.model.eq(name)
            & places.feature_set.eq(row.feature_set)
            & places.estimator.eq(row.estimator)
        ].set_index("geography")
        fine, broad = geo.loc["granular"], geo.loc["broad"]
        _check(
            row.geography == "broad"
            and fine.test_roc_auc < broad.test_roc_auc
            and fine.training_fit_roc_auc > fine.test_roc_auc,
            PAGE,
            f"{name}: the finest geography fits training better and tests worse",
        )
        geography.append(
            f"With {fine_place} in place of {broad_place}, the {NAMES[name]} reaches a ROC-AUC of "
            f"{fine.training_fit_roc_auc:.2f} on its training records but "
            f"{fine.test_roc_auc:.2f} on the test records, against {broad.test_roc_auc:.2f} with "
            f"{broad_place}."
        )
    methods: dict[str, list[str]] = {}
    for name in models:
        methods.setdefault(METHODS[primary.loc[name].estimator], []).append(name)
    chosen = "; ".join(
        f"{method} for the {_join([SHORT[m] for m in names])} model{'s' if len(names) > 1 else ''}"
        for method, names in methods.items()
    )
    cards = ", ".join(
        f'<a href="{DOCS_URL}/{CARDS[m]}">{esc(NAMES[m])}</a>' for m in models if m in CARDS
    )
    details = (
        "<p>For each model a logistic regression and gradient-boosted trees were fitted, and the "
        f"method that ranked the validation records better was used: {chosen}. The Barcelona "
        "models' settings were chosen by cross-validation within the training months that keeps "
        "all the records of one crash together.</p>"
    )
    details += (
        "<p>A model was preferred to its descriptive table only if its ROC-AUC exceeded the "
        f"table's by at least {MIN_GAIN:.2f}, with a 95% interval for the difference above zero. "
        "Its probabilities were treated as estimates only if the average prediction differed "
        f"from the observed share by no more than {_fmt_pct(CALIBRATION_LARGE_TOLERANCE, 0)} of "
        f"that share and the calibration slope lay between {low:g} and {high:g}. Both rules were "
        "fixed before any result was read.</p>"
    )
    details += (
        "<p>PR-AUC is the average precision over all thresholds; its chance level is the share "
        "of test records with the outcome. The Brier score is the mean squared error of the "
        "predicted probabilities (lower is better). Intervals are 95% bootstrap intervals that "
        "resample crashes.</p>"
    )
    details += table(
        performance,
        "Results on the test records, with 95% intervals. Outcome: a fatal crash (Catalonia); a "
        "serious or fatal injury (Barcelona).",
        {"Test records": "int", "PR-AUC": "dec2"},
    )
    details += table(
        comparison,
        "Each model against its descriptive table, on the same test records: ROC-AUC, and the "
        "difference with its 95% interval.",
        {"Groups": "int", "Table ROC-AUC": "dec2", "Model ROC-AUC": "dec2"},
    )
    details += (
        "<p>A second version of each model adds information recorded after the crash. Because "
        "that information is known only once the crash has been investigated, these versions are "
        "not used for prediction; they measure how much the information changes the ranking.</p>"
    )
    details += table(
        later,
        "Versions with information recorded after the crash, on the same test records (ROC-AUC "
        "to three decimals).",
    )
    details += (
        "<p>Finer geography. Replacing the broad place variable with the most detailed one "
        "raises the fit on the training records and lowers the test score, the pattern of a model "
        "that memorises places. " + " ".join(geography) + " The broad variables are used.</p>"
    )
    details += (
        f'<p>Model cards: {cards}. The <a href="{DOCS_URL}/MODEL_DECISIONS.md">model decision '
        "record</a> lists every model considered, with the rule applied to each, including the "
        "versions built only for validation, the association analysis of DGT's crash records "
        '(<a href="severity.html">Crash circumstances</a>) and the <a href="forecast.html">'
        f'monthly deaths forecast</a>. The <a href="{DOCS_URL}/ML_LEAKAGE_AUDIT.md">audit of '
        "variables recorded after the crash</a> sets out which were excluded.</p>"
    )
    body += technical("Technical details: test metrics, rules and checks", details)
    body += downloads(
        [
            ("ml_rule_comparison", "models against tables"),
            ("ml_selected", "selected models"),
            ("ml_variants", "all versions"),
            ("ml_calibration", "calibration groups"),
            ("ml_importance", "variable importance"),
            ("ml_subgroup_validation", "scores by group"),
            ("ml_geography", "geography check"),
            ("ml_feature_catalogue", "variables"),
            ("ml_split_isolation", "split checks"),
            ("ml_rare_causes", "recorded causes"),
            ("ml_model_decisions", "model decisions"),
        ],
        method=("data.html#models", "how the models were built and judged"),
    )
    return render_page(
        "severity-models",
        "Predictive models of crash severity",
        "Models trained on crash records from Catalonia and Barcelona rank recorded crashes, and "
        "the people recorded in them, by the severity of the outcome.",
        body,
    )
