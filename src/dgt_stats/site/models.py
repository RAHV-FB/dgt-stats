"""The predictive models: what each one predicts, whether it beats a simple table of the same
records, and whether its probabilities can be read as estimates.

Each model is presented in the same order: what it predicts, what one row is, the outcome, the
information it uses, what it cannot predict, how it compares with its table, and its calibration.
The page follows the decisions declared before the test (two models kept, one replaced by its
table); every number is read from the ``ml_*`` and ``bcn_*`` tables and every qualitative sentence
is checked against them.
"""

from __future__ import annotations

import calendar
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
    decision_label,
    downloads,
    esc,
    facts,
    figure,
    read_table,
    render_page,
    summary,
    table,
    technical,
)
from dgt_stats.site.regional_common import CARDS, MIN_N, MODEL_NAMES, _check, _year_label

PAGE = "severity models"
CATALONIA, PERSON, CRASH = (
    "catalonia_crash_severity",
    "barcelona_person_severity",
    "barcelona_crash_severity",
)
MODELS = (CATALONIA, PERSON, CRASH)
KEPT = [CATALONIA, PERSON]
REPLACED = [CRASH]
NAMES = {model: MODEL_NAMES[model] for model in MODELS}
# Shorter labels for the technical tables, where the column already says "Model".
SHORT = {CATALONIA: "Catalonia crash", PERSON: "Barcelona person", CRASH: "Barcelona crash"}
# The two fitting methods, in the words the rest of the site uses.
METHODS = {"logistic": "logistic regression", "boosted_trees": "gradient-boosted trees"}
# The grouping of each descriptive table, as the result table names it, in words.
RULE_LABELS = {
    "D_SUBTIPUS_ACCIDENT x D_SUBZONA": (
        "crash subtype × zone",
        "crash type and zone (urban street, interurban road or road through a town)",
    ),
    "person_role x associated_vehicle_group": (
        "road-user role × vehicle group",
        "road-user role (driver, passenger or pedestrian) and the vehicle on the person's record",
    ),
    "accident_type": ("accident type", "accident type"),
}
# What each model may use, in words: every variable of the model's main feature set must fall in
# one of these groups, so a change to the features stops the build until the words follow it.
INPUT_GROUPS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    CATALONIA: (
        ("the date and time", ("year", "month", "weekday", "hour_band")),
        (
            "the road (its type, owner, zone, junction, priority rules and posted speed limit)",
            (
                "D_TIPUS_VIA",
                "D_TITULARITAT_VIA",
                "D_SUBZONA",
                "D_FUNC_ESP_VIA",
                "D_INTER_SECCIO",
                "D_SUBTIPUS_TRAM",
                "D_REGULACIO_PRIORITAT",
                "speed_limit_category",
            ),
        ),
        (
            "the conditions (road surface, light, weather, wind, fog and any special traffic "
            "measures)",
            (
                "D_SUPERFICIE",
                "D_LLUMINOSITAT",
                "D_CLIMATOLOGIA",
                "D_VENT",
                "D_BOIRA",
                "D_CIRCULACIO_MESURES_ESP",
            ),
        ),
        ("the type of crash", ("D_SUBTIPUS_ACCIDENT",)),
        (
            "the number and kinds of vehicles and pedestrians involved",
            ("n_units", "single_unit", "involves_"),
        ),
        ("the province", ("demarcation",)),
    ),
    PERSON: (
        (
            "the person's age, sex and role, the vehicle on their record and, for a pedestrian, "
            "where they were struck",
            ("age", "sex", "person_role", "associated_vehicle_group", "pedestrian_location"),
        ),
        (
            "the type of crash and the vehicles involved",
            ("accident_type", "n_vehicles", "vehicle_records_include_"),
        ),
        ("the hour and day of the week", ("hour", "weekday")),
        ("the district", ("district",)),
    ),
    CRASH: (
        (
            "the type of crash and the vehicles involved",
            ("accident_type", "n_vehicles", "vehicle_records_include_"),
        ),
        ("the hour and day of the week", ("hour", "weekday")),
        ("the district", ("district",)),
    ),
}
# What the version with information recorded after the crash adds to each model.
RETROSPECTIVE = {
    CATALONIA: "police judgements of which conditions influenced the crash, and fields whose "
    "completeness follows the outcome",
    PERSON: "causes recorded by the police",
    CRASH: "causes recorded by the police",
}
# The variables the importance figures rank highest, in words.
FEATURES = {
    "D_TITULARITAT_VIA": "the road's owner",
    "D_SUBZONA": "the zone",
    "D_SUBTIPUS_ACCIDENT": "the crash type",
    "associated_vehicle_group": "the vehicle on the person's record",
    "accident_type": "the accident type",
    "person_role": "the road-user role",
    "pedestrian_location": "where a pedestrian was struck",
}
# The Catalan model's three leading variables, as the importance table names them.
OWNER, ZONE, SUBTYPE = "D_TITULARITAT_VIA", "D_SUBZONA", "D_SUBTIPUS_ACCIDENT"
# The two Barcelona accident types a reader may take for one: the Guàrdia Urbana's own categories.
CATCHING_UP, REAR_END = "rear collision while catching up", "rear-end collision"
SOURCE_TYPE = {label: code for code, label in ACCIDENT_TYPES.items()}
SUBGROUP_DIMENSIONS = ("all", "role", "associated vehicle", "age band", "sex")
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 9: "nine", 10: "ten"}
FRACTIONS = {5: "fifth", 10: "tenth"}
# The decision on each model, as its section heading labels it.
DECISIONS = {CATALONIA: "Kept", PERSON: "Ranking only", CRASH: "Replaced by table"}
CATALAN_DESIGN = re.compile(r"train (\d{4})-(\d{4}), choose on (\d{4})-(\d{4}), test (\d{4})")
BARCELONA_DESIGN = re.compile(
    r"train months (\d+)-(\d+) with \d+-fold cross-validation grouped by crash; "
    r"test months (\d+)-(\d+)"
)


def _brief(
    unit: str, outcome: str, tested: str, benchmark: str, model: str, decision: str, name: str
) -> str:
    """The definition table that opens each model's section."""
    return facts(
        [
            ("Unit", unit),
            ("Outcome", outcome),
            ("Test records", tested),
            ("Simple benchmark ROC-AUC", benchmark),
            ("Model ROC-AUC", model),
            ("Decision", decision),
        ],
        f"{name}: summary",
    )


def _title(name: str) -> str:
    return name[:1].upper() + name[1:]


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


def _pair(a: float, b: float) -> str:
    """Two figures that may round alike: 'about 0.15 each' rather than '0.15 and 0.15'."""
    return f"about {a:.2f} each" if f"{a:.2f}" == f"{b:.2f}" else f"{a:.2f} and {b:.2f}"


def _feature(name: str) -> str:
    _check(name in FEATURES, PAGE, f"the variable {name} has a label")
    return FEATURES[name]


def _age_band(level: str) -> str:
    return f"{level[:-1]} and over" if level.endswith("+") else level.replace("-", "–")


def _subgroup_label(row) -> str:
    level = str(row.level).replace("_", " ")
    if row.dimension == "all":
        return "Everyone"
    if row.dimension == "role":
        return f"{level.capitalize()}s"
    if row.dimension == "associated vehicle":
        return f"Vehicle on record: {level}"
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


def _inputs(model: str, catalogue: pd.DataFrame, feature_set: str) -> str:
    """The information a model uses, as groups in words, checked against its feature catalogue."""
    rows = catalogue[
        catalogue.feature_table.eq(model)
        & catalogue.feature_sets.fillna("").str.contains(rf"\b{feature_set}\b")
        & catalogue.geography_variant.isin(["all", "broad"])
    ]
    groups = INPUT_GROUPS[model]

    def group_of(column: str) -> str | None:
        for words, prefixes in groups:
            if any(column == p or (p.endswith("_") and column.startswith(p)) for p in prefixes):
                return words
        return None

    found = {column: group_of(column) for column in rows.column}
    unplaced = sorted(column for column, words in found.items() if words is None)
    _check(not unplaced, PAGE, f"{model}: every input variable is described ({unplaced})")
    used = [words for words, _ in groups if words in found.values()]
    _check(len(used) == len(groups), PAGE, f"{model}: every described group has a variable")
    return _join(used)


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
    catalogue = read_table("ml_feature_catalogue")
    primary = selected[selected.primary].set_index("model")
    retro = selected[~selected.primary].set_index("model")
    year = _year_label(crashes)

    # The page is written around the declared decisions: two models kept, the third replaced by
    # its descriptive table. Each kept model beats chance and its table; the replaced one does not.
    models = [m for m in MODELS if m in rules.index]
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
    low, high = CALIBRATION_SLOPE_RANGE
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
        "The project fitted three predictive models to individual crash records and kept only "
        "those that ranked later, unseen records better than a simple table of the same data. "
        f"The {NAMES[CATALONIA]} ranks crashes with a death or serious injury by how likely "
        "they were to be fatal. It is kept: it clearly beats its table, and on the held-out "
        f"crashes of {test_year} its probabilities matched the observed fatal shares well "
        f"overall. The {NAMES[PERSON]} orders people involved in crashes from lower to higher "
        "predicted severity. It is kept for ranking only: it beats its table, but its scores are "
        "too extreme to read as probabilities, and it ranks pedestrians little better than "
        "chance. The "
        f"{NAMES[CRASH]} ranked crashes no better than a table of accident types, so it was "
        "dropped and the table is reported instead. None of the models predicts whether a crash "
        "will happen; they work only on crashes that happened and were recorded."
    )

    # ------------------------------------------------------------------------------ Catalonia
    rule = rules.loc[CATALONIA]
    deciles = bins(CATALONIA)
    top, bottom = deciles.iloc[-1], deciles.iloc[0]
    part = FRACTIONS[len(deciles)]
    _check(low <= cat.calibration_slope <= high, PAGE, "the Catalan calibration slope is near 1")
    city = transport[
        transport.experiment.eq("rest of Catalonia -> Barcelona municipality")
        & transport.model.eq(CATALONIA)
        & transport.estimator.eq(cat.estimator)
        & transport.status.eq("reported")
    ].iloc[0]
    _check(
        not low <= city.calibration_slope <= high,
        PAGE,
        "the Catalan model's calibration does not carry over to Barcelona city",
    )
    body += f"<h2>{_title(NAMES[CATALONIA])} {decision_label(DECISIONS[CATALONIA])}</h2>"
    body += _brief(
        "One crash in Catalonia in which someone was killed or seriously injured",
        "Anyone killed within 24 hours",
        f"{_fmt_int(cat.n)} crashes of {test_year}, {_fmt_int(cat.positives)} fatal",
        f"{rule.rule_roc_auc:.2f}, a table of fatal shares by {RULE_LABELS[rule.rule][0]}",
        f"{cat.roc_auc:.2f} (95% interval {cat.roc_auc_low:.2f}–{cat.roc_auc_high:.2f})",
        "Kept: it ranks crashes better than its table, and its probabilities can be read as "
        f"estimates for Catalan crashes like those of {test_year}",
        NAMES[CATALONIA],
    )
    body += (
        "<p>The model estimates the probability that a crash in the Servei Català de Trànsit's "
        "file was fatal from what the police recorded about "
        f"{_inputs(CATALONIA, catalogue, cat.feature_set)}. It cannot predict whether a crash "
        "will happen: the file contains only crashes in which someone was killed or seriously "
        "injured, so the model says nothing about how likely a journey, or an ordinary crash, "
        "is to end in a death.</p>"
    )
    body += (
        f"<p>It was fitted to the crashes of {train_years}, tuned on {choice_years} and tested "
        f"once on the {_fmt_int(cat.n)} crashes of {test_year}, of which "
        f"{_fmt_int(cat.positives)} ({_fmt_pct(cat.prevalence)}) were fatal. On those crashes, a "
        f"simple table of fatal shares by {RULE_LABELS[rule.rule][1]} reaches a ROC-AUC of "
        f"{rule.rule_roc_auc:.2f}. The model reaches {cat.roc_auc:.2f} (95% interval "
        f"{cat.roc_auc_low:.2f}–{cat.roc_auc_high:.2f}), a gain of {rule.roc_auc_gain:.2f} "
        f"({_range(rule.roc_auc_gain_low, rule.roc_auc_gain_high)}). It therefore separates "
        "fatal from non-fatal serious crashes clearly better than the simple grouping does. "
        "ROC-AUC measures ranking: 0.5 is no better than chance and 1 is a perfect ranking. A "
        f"score of {cat.roc_auc:.2f} means that if one fatal and one non-fatal crash are picked "
        "at random, the model gives the fatal crash the higher score "
        f"{_fmt_pct(cat.roc_auc, 0)} of the time. In the {part} of {test_year} crashes it "
        f"ranked highest ({_fmt_int(top.n)}), {_fmt_pct(top.observed)} were fatal, "
        f"{int(top.positives)} of the {_fmt_int(cat.positives)}; in the lowest {part}, "
        f"{_fmt_pct(bottom.observed)} were.</p>"
    )
    body += (
        f"<p>On the held-out Catalan crashes of {test_year}, the predicted probabilities "
        "matched the observed fatal shares reasonably well overall: "
        f"{_fmt_pct(cat.mean_predicted)} predicted on average against "
        f"{_fmt_pct(cat.prevalence)} observed, and {_fmt_pct(top.mean_predicted)} against "
        f"{_fmt_pct(top.observed)} in the highest {part}. The calibration slope is "
        f"{cat.calibration_slope:.2f}, close to the value of 1 at which predictions are neither "
        "too spread out nor too compressed. That calibration should not be assumed for every "
        "place or subgroup. In Barcelona city it did not carry over: trained on the rest of "
        "Catalonia and applied there, the same model has a slope of "
        f"{city.calibration_slope:.2f}.</p>"
    )
    ranked = reliance(CATALONIA)
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
        "<p>To see what the model relies on, each variable was shuffled at random in the test "
        "crashes and the fall in ROC-AUC measured. Shuffling "
        f"{labels[0]} lowered it by {drops[0]}, {labels[1]} by {drops[1]} and {labels[2]} by "
        f"{drops[2]}; no other variable lowered it as much. The road's owner and the zone "
        "overlap: the owner is left blank for urban streets, so it also carries the "
        "urban–interurban distinction "
        "that the zone records. A variable the model relies on is not necessarily a cause of "
        "severe crashes: the road's owner stands in for differences between roads that the "
        "file does not measure.</p>"
    )
    body += figure(
        f"ml3_importance_{CATALONIA}",
        f"Chart of the variables the {NAMES[CATALONIA]} relies on most, measured by the fall in "
        f"its test ROC-AUC when each is shuffled; {labels[0]}, {labels[1]} and {labels[2]} lead.",
        captions,
    )
    body += (
        "<p>The model was also tested on a province left out of training, on Barcelona city, "
        "and, in a version restricted to the variables DGT records in the same way, on DGT's "
        'records of serious crashes in the rest of Spain (<a href="validation.html">External '
        "validation</a>).</p>"
    )

    # ------------------------------------------------------------------- Barcelona person model
    rule = rules.loc[PERSON]
    fifths = bins(PERSON)
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
    _check(
        rule.roc_auc_gain_high - rule.roc_auc_gain_low
        > rules.loc[CATALONIA].roc_auc_gain_high - rules.loc[CATALONIA].roc_auc_gain_low,
        PAGE,
        "the Barcelona gain is less precisely estimated than the Catalan one",
    )
    predicted, observed = _fmt_pct(person.mean_predicted), _fmt_pct(person.prevalence)
    average = (
        f"{predicted} predicted and observed"
        if predicted == observed
        else f"{predicted} predicted against {observed} observed"
    )
    test_span = (
        f"{calendar.month_name[int(barcelona.group(3))]}–"
        f"{calendar.month_name[int(barcelona.group(4))]} {year}"
    )
    body += f"<h2>{_title(NAMES[PERSON])} {decision_label(DECISIONS[PERSON])}</h2>"
    body += _brief(
        f"One person involved in a crash attended by Barcelona's police in {year}",
        "Seriously injured (more than 24 hours in hospital) or killed",
        f"{_fmt_int(person.n)} people, {test_span}; {_fmt_int(person.positives)} seriously or "
        "fatally injured",
        f"{rule.rule_roc_auc:.2f}, a table of shares by {RULE_LABELS[rule.rule][0]}",
        f"{person.roc_auc:.2f} (95% interval {person.roc_auc_low:.2f}–{person.roc_auc_high:.2f})",
        "Ranking only: it orders people better than its table, but its scores are too extreme "
        "to read as probabilities",
        NAMES[PERSON],
    )
    body += (
        "<p>Each person in the Guàrdia Urbana's records is a driver, a passenger or a "
        "pedestrian. The model uses "
        f"{_inputs(PERSON, catalogue, person.feature_set)}. It cannot predict who will be in a "
        "crash: everyone in the data was in one, and the records hold no measure of how much "
        "each group travels.</p>"
    )
    body += (
        f"<p>It was fitted to the first {_word(train_months)} months of {year} and tested on "
        f"the last {_word(test_months)}, in which {_fmt_int(person.positives)} of "
        f"{_fmt_int(person.n)} people ({_fmt_pct(person.prevalence)}) were seriously or fatally "
        f"injured. A table of shares by {RULE_LABELS[rule.rule][1]} reaches a ROC-AUC of "
        f"{rule.rule_roc_auc:.2f}; the model reaches {person.roc_auc:.2f} (95% interval "
        f"{person.roc_auc_low:.2f}–{person.roc_auc_high:.2f}), a gain of "
        f"{rule.roc_auc_gain:.2f} ({_range(rule.roc_auc_gain_low, rule.roc_auc_gain_high)}). It "
        f"ranks people better than the table, although with only {_fmt_int(person.positives)} "
        "serious or fatal cases the gain is less precisely estimated than in Catalonia, and a "
        "single year of records allows no test on a later year. The "
        f"{part} of people it ranked highest ({_fmt_int(top.n)}) held {int(top.positives)} of "
        f"the {_fmt_int(person.positives)} serious or fatal injuries; the two {part}s it ranked "
        f"lowest ({_fmt_int(lowest.n.sum())} people) held "
        f"{'none' if missed == 0 else _fmt_int(missed)}.</p>"
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
        "<p>Its probabilities cannot be read literally. They are right on average "
        f"({average}) but too extreme: in the highest {part} of scores the model predicted "
        f"{_fmt_pct(top.mean_predicted)} against {_fmt_pct(top.observed)} observed, and lower "
        "scores understated the observed share. The calibration slope is "
        f"{person.calibration_slope:.2f}, well below 1. The model is therefore used only to "
        "order records from lower to higher predicted severity.</p>"
    )
    body += (
        "<p>It should not be used to rank pedestrians. Because the test months hold too few "
        f"serious cases to score groups, every person recorded in {year} was scored by a "
        "version of the model fitted without their crash. The ROC-AUC is then "
        f"{pedestrians.roc_auc:.2f} for pedestrians, little better than chance, although "
        "pedestrians are the road users most often seriously hurt "
        f"({_fmt_pct(pedestrians.observed)}, against {_fmt_pct(everyone.observed)} for "
        f"everyone); for {_subgroup_prose(best)} it is {best.roc_auc:.2f}. Its ranking has been "
        f"shown only for people in crashes recorded by Barcelona's police in {year}.</p>"
    )
    body += technical(
        "Scores by group of road users",
        table(
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
            f"{NAMES[PERSON]} by group of road users, {year}: each person scored by a version "
            f"fitted without their crash; groups with at least {MIN_SUBGROUP_POSITIVES} serious "
            "or fatal cases.",
            {
                "People": "int",
                "Serious or fatal": "int",
                "Observed share": "pct",
                "Average prediction": "pct",
                "ROC-AUC": "dec2",
            },
        ),
    )
    ranked = reliance(PERSON)
    first = ranked.head(4)
    person_drops = list(first.auc_drop_mean)
    _check(min(person_drops[:2]) >= 3 * person_drops[2], PAGE, "two variables dominate the model")
    labels = [_feature(f) for f in first.feature]
    body += (
        f"<p>Shuffling {labels[0]} or {labels[1]} lowered the test ROC-AUC by "
        f"{_pair(person_drops[0], person_drops[1])}; shuffling {labels[2]} or {labels[3]} "
        f"lowered it by {_pair(person_drops[2], person_drops[3])}. The model relies mostly on "
        f"{labels[0]} and {labels[1]}.</p>"
    )
    body += figure(
        f"ml3_importance_{PERSON}",
        f"Chart of the variables the {NAMES[PERSON]} relies on most, measured by the fall in "
        f"its test ROC-AUC when each is shuffled; {labels[0]} and {labels[1]} stand far above "
        "the rest.",
        captions,
    )

    # ------------------------------------------------------------------- Barcelona crash table
    rule = rules.loc[CRASH]
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
    body += f"<h2>{_title(NAMES[CRASH])} {decision_label(DECISIONS[CRASH])}</h2>"
    body += _brief(
        f"One crash attended by Barcelona's police in {year}",
        "Anyone seriously or fatally injured",
        f"{_fmt_int(crash.n)} crashes, {test_span}; {_fmt_int(crash.positives)} with a serious "
        "or fatal injury",
        f"{rule.rule_roc_auc:.2f}, a table of shares by {RULE_LABELS[rule.rule][0]}",
        f"{crash.roc_auc:.2f} (95% interval {crash.roc_auc_low:.2f}–{crash.roc_auc_high:.2f})",
        "Replaced by table: the model ranks crashes no better than the table, which is shown "
        "below instead",
        NAMES[CRASH],
    )
    body += (
        "<p>The model used "
        f"{_inputs(CRASH, catalogue, crash.feature_set)}. On the {_fmt_int(crash.n)} crashes of "
        f"the test months ({_fmt_int(crash.positives)} with a serious or fatal injury) it "
        f"reached a ROC-AUC of {crash.roc_auc:.2f}, against {rule.rule_roc_auc:.2f} for a table "
        f"of shares by {RULE_LABELS[rule.rule][1]}: a difference of {_signed(rule.roc_auc_gain)} "
        f"(95% interval {_range(rule.roc_auc_gain_low, rule.roc_auc_gain_high)}). A ROC-AUC of "
        f"{crash.roc_auc:.2f} is well above chance, but the one-column table ranks crashes as "
        "well, so the table is used in place of the model. The table below is computed over all "
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
        "<p>The Guàrdia Urbana codes a rear collision while catching up "
        f'(<i lang="ca">{esc(SOURCE_TYPE[CATCHING_UP].lower())}</i>, '
        f"{_fmt_int(coded.n[CATCHING_UP])} crashes) separately from a rear-end collision "
        f'(<i lang="ca">{esc(SOURCE_TYPE[REAR_END].lower())}</i>, '
        f"{_fmt_int(coded.n[REAR_END])}).</p>"
    )

    # ------------------------------------------------------------------- how they were judged
    body += "<h2>How the models were judged</h2>"
    body += figure(
        "ml1_test_auc",
        "Dot chart of the ROC-AUC on the test records for each of the three models, the "
        "descriptive table it was compared with and a baseline that gives every case the same "
        "probability, with 95% intervals for the models. The Catalonia and Barcelona person "
        "models score above their tables; the Barcelona crash model scores level with its table.",
        captions,
    )
    body += (
        "<p>Each model's benchmark was a table of the share of severe outcomes in each group "
        "of the training "
        "records, using the grouping a descriptive analysis would lead with, fixed before the "
        f"test. A model was kept only if it beat its table by at least {MIN_GAIN:.2f} of "
        "ROC-AUC, with a 95% interval for the difference above zero, and its probabilities were "
        "read as estimates only if their average was within "
        f"{_fmt_pct(CALIBRATION_LARGE_TOLERANCE, 0)} of the observed share and the calibration "
        f"slope lay between {low:g} and {high:g}. Both rules were set before any test result "
        "was read.</p>"
    )
    body += figure(
        "ml2_calibration",
        f"Calibration chart for the {NAMES[CATALONIA]} and the {NAMES[PERSON]}: the observed "
        "share of cases with the outcome against the average predicted probability, in "
        f"equal-sized groups of test records. The {NAMES[CATALONIA]}'s points lie close to the "
        "diagonal, where predicted and observed shares are equal; the "
        f"{NAMES[PERSON]}'s points are bunched at low probabilities.",
        captions,
    )

    # ---------------------------------------------------------------- prediction, not causes
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
    body += "<h2>What the models do not show</h2>"
    body += (
        "<p>The models rank recorded crashes and people by how severe the outcome was, using "
        "associations in the records. They do not explain why outcomes were severe, and the "
        "records contain no measure of how much anyone travels. Information recorded after the "
        "outcome was known, such as the causes the Barcelona police record, is left out of the "
        "models used for prediction.</p>"
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
            "ROC-AUC": [
                f"{primary.loc[m].roc_auc:.2f} ({primary.loc[m].roc_auc_low:.2f}–"
                f"{primary.loc[m].roc_auc_high:.2f})"
                for m in models
            ],
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
            "Beats the table": ["yes" if m in kept else "no" for m in models],
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
        (CATALONIA, "province", "municipality"),
        (PERSON, "district", "neighbourhood"),
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
        "all the records of one crash together. PR-AUC is the average precision over all "
        "thresholds; its chance level is the share of test records with the outcome. The Brier "
        "score is the mean squared error of the predicted probabilities (lower is better). "
        "Intervals are 95% bootstrap intervals that resample crashes.</p>"
    )
    details += table(
        performance,
        "Results on the test records, with 95% intervals. Outcome: a fatal crash (Catalonia); a "
        "serious or fatal injury (Barcelona).",
        {"Test records": "int", "PR-AUC": "dec2"},
    )
    details += table(
        comparison,
        "Each model against its table, on the same test records: ROC-AUC, and the difference "
        "with its 95% interval.",
        {"Groups": "int", "Table ROC-AUC": "dec2", "Model ROC-AUC": "dec2"},
    )
    details += (
        "<p>A second version of each model adds information recorded after the crash. Because "
        "that information is known only once the crash has been investigated, these versions are "
        "not used for prediction; they measure how much the information changes the ranking. "
        "It improves the kept models' ranking by less than 0.01.</p>"
    )
    details += table(
        later,
        "Versions with information recorded after the crash, on the same test records (ROC-AUC "
        "to three decimals).",
    )
    details += (
        "<p>Some causes recorded by the Barcelona police are too rare to model at all, among "
        f"them excessive or inappropriate speed ({_fmt_int(speed.crashes_recorded)} crashes in "
        f"{year}) and drugs or medication ({_fmt_int(drugs.crashes_recorded)}).</p>"
    )
    details += (
        "<p>Replacing the broad place variable with the most detailed one raises the fit on the "
        "training records and lowers the test score, the pattern of a model that memorises "
        "places. " + " ".join(geography) + " The broad variables are used.</p>"
    )
    details += (
        f'<p>Model cards: {cards}. The <a href="{DOCS_URL}/MODEL_DECISIONS.md">model decision '
        "record</a> lists every model considered and the rule applied to each, including the "
        "versions built only for validation, the association analysis of DGT's crash records "
        '(<a href="severity.html">crash circumstances</a>) and the <a href="forecast.html">'
        f'monthly deaths forecast</a>. The <a href="{DOCS_URL}/ML_LEAKAGE_AUDIT.md">audit of '
        "variables recorded after the crash</a> sets out which were excluded.</p>"
    )
    body += technical("Detailed model diagnostics", details)
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
        "Models of crash and injury severity",
        "Three models trained on Catalan and Barcelona crash records, each judged on later "
        "records it had not seen and against a simple table of the same records: two are kept, "
        "one is replaced by its table.",
        body,
    )
