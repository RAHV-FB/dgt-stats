"""External validation of the severity models: how well they rank crashes from years, places and
data sources they were not trained on, and how the crash populations compare."""

from __future__ import annotations

import re

import pandas as pd

from dgt_stats.microdata.ml import modelling
from dgt_stats.microdata.validation import generalisability, harmonise
from dgt_stats.microdata.validation import transport as transport_rules
from dgt_stats.site.components import (
    DOCS_URL,
    MINUS,
    _fmt_dec,
    _fmt_int,
    _fmt_pct,
    _join,
    downloads,
    figure,
    read_table,
    render_page,
    summary,
    table,
    technical,
)
from dgt_stats.site.regional_common import _check

PAGE = "validation"

# Reader-facing names for the variables compared between sources and populations.
VARIABLES = {
    "alignment_recorded": "road alignment",
    "road_class": "road type",
    "crash_type": "crash type",
    "weather": "weather",
    "surface": "road surface",
    "junction": "junction",
    "lighting": "lighting",
    "vehicles": "number of vehicles",
    "zone": "urban or interurban zone",
    "hour_band": "time of day",
    "weekday": "day of the week",
    "year": "year",
    "month": "month",
    "speed_limit": "speed limit",
    "unit_types": "types of vehicle involved",
    "geography": "location",
}
# Where a variable reads better in a table heading than in a sentence.
VARIABLE_HEADINGS = {"alignment_recorded": "road alignment (including unknown)"}
# The populations as the tables name them, and as a reader sees them.
PLACES = {
    "Barcelona municipality": "Barcelona city",
    "Barcelona city": "Barcelona city",
    "rest of Catalonia": "rest of Catalonia",
    "Catalonia": "Catalonia",
    "Spain outside Catalonia": "Spain outside Catalonia",
    "urban crashes": "urban crashes",
    "interurban crashes": "interurban crashes",
}
# The models as the validation tables name them. The Barcelona crash model was replaced by its
# table of shares by accident type; it appears only in the table of evidence by model.
MODELS = {
    "catalonia_crash_severity": "Catalonia severity model",
    "catalonia_common_dgt": "Harmonised Catalonia model",
    "catalonia_common_bcn": "Catalonia model restricted to Barcelona's variables",
    "barcelona_person_severity": "Barcelona person-severity model",
    "barcelona_crash_severity": "Barcelona crash model (replaced by a descriptive table)",
}
# The kinds of test, from the records closest to the training data to the comparison with Spain.
EVIDENCE_COLUMNS = {
    1: "Held-out records, same source",
    2: "Later years or months",
    3: "Another province, city or district",
    4: "Another data source",
    5: "Crashes resemble Spain's",
}
EVIDENCE_CELLS = {
    "passed": "passed",
    "failed": "failed",
    "partly": "partly passed",
    "not run": "not run",
    "not testable": "too few cases",
}
RESEMBLANCE_CELLS = {"passed": "yes", "failed": "no"}
# The parts of the fall from the rest of Catalonia to Barcelona city: a short name and what is
# compared. The first four add up; the last two are read beside them.
COMPONENTS = {
    "total drop": (
        "Total fall",
        "Rest of Catalonia scored by a model trained there, against Barcelona city scored by "
        "the model trained on the rest of Catalonia",
    ),
    "training-size cost": (
        "Smaller training set",
        "Rest of Catalonia: a model trained on all its training crashes, against one trained "
        "on only as many as Barcelona's own model uses",
    ),
    "intrinsic difference": (
        "Crashes harder to rank",
        "Same variables and training size: rest of Catalonia against Barcelona city",
    ),
    "transport cost": (
        "Change of population (net)",
        "Barcelona city: a model trained there, against the model trained on the rest of Catalonia",
    ),
    "intrinsic difference against urban crashes": (
        "Compared with other urban crashes",
        "Same variables and training size: the rest of Catalonia's urban crashes against "
        "Barcelona city (negative: those crashes are harder to rank)",
    ),
    "urban-only training": (
        "Training on urban crashes only",
        "Barcelona city: the model trained on the rest of Catalonia's urban crashes, against "
        "the one trained on all its crashes (negative: worse)",
    ),
}
OUTCOMES = {
    "crashes with a death or serious injury (24 h), share of injury crashes": "serious",
    "fatal (24 h) among crashes with a death or serious injury": "fatal_24h",
    "fatal (30 days) among injury crashes": "fatal_30d",
}


def _place(name: str, capital: bool = False) -> str:
    label = PLACES.get(name)
    if label is None:
        raise ValueError(f"{PAGE} page: no reader-facing name for the population {name!r}")
    return label[0].upper() + label[1:] if capital else label


def _variable(name: str) -> str:
    label = VARIABLES.get(name)
    if label is None:
        raise ValueError(f"{PAGE} page: no reader-facing name for the variable {name!r}")
    return label


def _variables(names) -> str:
    """'road type, crash type and weather'."""
    return _join([_variable(name) for name in names])


def _model(name: str) -> str:
    label = MODELS.get(name)
    if label is None:
        raise ValueError(f"{PAGE} page: no reader-facing name for the model {name!r}")
    return label


def _count(value: int) -> str:
    """Small counts in words, as in running prose; larger ones as figures."""
    words = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
    words += ("ten", "eleven", "twelve")
    return words[value] if 0 <= value < len(words) else _fmt_int(value)


def _years(text: str) -> str:
    """The period named in a table's label, as a range of years or a single year."""
    match = re.search(r"(\d{4})-(\d{4})", str(text))
    if match is None:
        raise ValueError(f"{PAGE} page: no period in {text!r}")
    first, last = match.groups()
    return first if first == last else f"{first}–{last}"


def _test_label(row) -> str:
    """A plain-English name for one external test, built from the table's own labels."""
    experiment = row.experiment
    rules = (
        (r"temporal holdout.*test (\d{4})", lambda m: f"Later year ({m.group(1)})"),
        (
            r"rest of Catalonia -> Barcelona municipality",
            lambda m: "Rest of Catalonia to Barcelona city",
        ),
        (
            r"Barcelona municipality -> rest of Catalonia",
            lambda m: "Barcelona city to the rest of Catalonia",
        ),
        (r"leave out (\w+) demarcation", lambda m: f"{m.group(1)} province left out"),
        (
            r"rest of Catalonia to \d+ -> Barcelona municipality after",
            lambda m: (
                f"Rest of Catalonia {_years(row.train_domain)} to Barcelona city "
                f"{_years(row.test_domain)}"
            ),
        ),
        (
            r"same crashes, two sources: Catalan file",
            lambda m: f"Catalan crashes {_years(row.test_domain)}, from the Catalan file",
        ),
        (
            r"same crashes, two sources: DGT records",
            lambda m: f"Catalan crashes {_years(row.test_domain)}, from DGT records",
        ),
        (
            r"Catalonia, a year the Catalan file does not have",
            lambda m: f"Catalonia {_years(row.test_domain)}, DGT records only",
        ),
        (
            r"Catalonia -> Spain outside Catalonia$",
            lambda m: f"Spain outside Catalonia, DGT records {_years(row.test_domain)}",
        ),
        (
            r"Catalonia early years -> Spain outside Catalonia",
            lambda m: f"Catalan file {_years(row.train_domain)} to Spain outside Catalonia",
        ),
        (
            r"Catalonia reweighted .* -> Spain outside Catalonia",
            lambda m: (
                "Spain outside Catalonia, training reweighted to the national mix of zone "
                "and crash type"
            ),
        ),
        (r"leave one district out", lambda m: "Each Barcelona district left out in turn"),
    )
    for pattern, label in rules:
        match = re.match(pattern, experiment)
        if match:
            return label(match)
    raise ValueError(f"{PAGE} page: no reader-facing name for the test {experiment!r}")


def _strategy_label(strategy: str) -> str:
    rules = (
        (
            r"domain-specific: (.+) only$",
            lambda m: f"{_place(m.group(1), True)} only (separate model)",
        ),
        (r"other domain only: (.+)$", lambda m: f"{_place(m.group(1), True)} only"),
        (r"pooled: both domains$", lambda m: "Both, pooled"),
        (r"pooled with a domain flag$", lambda m: "Both, pooled, with a population indicator"),
        (
            r"pooled, Barcelona-common features",
            lambda m: "Both, pooled, Barcelona's variables only",
        ),
    )
    for pattern, label in rules:
        match = re.match(pattern, strategy)
        if match:
            return label(match)
    raise ValueError(f"{PAGE} page: no reader-facing name for the strategy {strategy!r}")


def _signed(value: float, decimals: int = 2) -> str:
    """A difference with its sign: +0.05, −0.04, 0.00."""
    text = _fmt_dec(value, decimals)
    return "+" + text if round(float(value), decimals) > 0 else text


def _interval(low: float, high: float, decimals: int = 2) -> str:
    """'0.023–0.086' when neither end carries a sign, '−0.021 to 0.054' when one does."""
    first, second = _fmt_dec(low, decimals), _fmt_dec(high, decimals)
    return f"{first} to {second}" if MINUS in first + second else f"{first}–{second}"


def page_validation(captions: dict[str, str]) -> str:
    tests = read_table("ml_transport_validation")
    path = read_table("ml_outward_path")
    provinces = read_table("ml_transport_provinces")
    mapping = read_table("ml_common_feature_validation")
    outcomes = read_table("gen_outcomes")
    shares = read_table("gen_representativeness")
    components = read_table("ml_barcelona_diagnosis_components")
    verdicts = read_table("ml_barcelona_diagnosis_verdicts")
    strategies = read_table("ml_domain_strategies")
    national_checks = read_table("dgt_audit_transfer").set_index("check")
    province_years = read_table("cat_vs_dgt_province_year")
    rates = read_table("gen_province_rates")
    register = read_table("gen_cross_source_register")
    rule_comparison = read_table("ml_rule_comparison").set_index("model")
    variants = read_table("ml_variants")
    selected = read_table("ml_selected")
    primary = selected[selected.primary].set_index("model")
    chosen_estimator = primary.estimator
    fitted = tests[tests.estimator.ne("baseline_prior")]
    # Each model is shown with the estimator chosen on its own validation data, never the better
    # of two after seeing the external results.
    reported = fitted[
        fitted.status.eq("reported")
        & (fitted.estimator == fitted.model.map(chosen_estimator).fillna(fitted.estimator))
    ]

    def test_row(prefix: str, model: str):
        part = reported[(reported.model == model) & reported.experiment.str.startswith(prefix)]
        return part.iloc[0]

    to_bcn = test_row("rest of Catalonia -> Barcelona municipality", "catalonia_crash_severity")
    from_bcn = test_row("Barcelona municipality -> rest of Catalonia", "catalonia_crash_severity")
    later_year = test_row("temporal holdout", "catalonia_crash_severity")
    national = test_row("Catalonia -> Spain outside Catalonia", "catalonia_common_dgt")
    early = test_row("Catalonia early years -> Spain", "catalonia_common_dgt")
    reweighted = test_row("Catalonia reweighted", "catalonia_common_dgt")
    same_cat = test_row("same crashes, two sources: Catalan file", "catalonia_common_dgt")
    same_dgt = test_row("same crashes, two sources: DGT records", "catalonia_common_dgt")
    dgt_only = test_row("Catalonia, a year the Catalan file", "catalonia_common_dgt")
    bcn_vars = test_row(
        "rest of Catalonia -> Barcelona municipality (Barcelona-common", "catalonia_common_bcn"
    )
    districts = test_row("leave one district out", "barcelona_person_severity")
    district_reference = test_row("grouped 5-fold cross-validation", "barcelona_person_severity")
    # Shown with the estimator its model chose on its own validation data, as every other test.
    records_rows = fitted[fitted.experiment.str.match(r"Catalonia -> Barcelona \d")]
    bcn_records = records_rows[
        records_rows.estimator.eq(records_rows.model.map(chosen_estimator))
    ].iloc[0]
    bcn_records_year = re.search(r"Barcelona (\d{4})", bcn_records.experiment).group(1)
    dgt_period = f"{int(rates.year.min())}–{int(rates.year.max())}"
    later_year_label = re.search(r"test (\d{4})", later_year.experiment).group(1)
    tolerance = generalisability.MAX_TRANSFER_GAP
    resemblance = generalisability.MAX_RESEMBLANCE_JSD
    slope_low, slope_high = modelling.CALIBRATION_SLOPE_RANGE
    minimum = transport_rules.MIN_POSITIVES

    # ------------------------------------------------------------------ the principal result
    _check(national.roc_auc_low > 0.5, PAGE, "the national test ranks well above chance")
    _check(
        abs(national.transfer_gap) < 0.01,
        PAGE,
        "the Catalonia-trained model ranks Spanish crashes almost as well as a model trained there",
    )
    _check(
        slope_low <= national.calibration_slope <= slope_high
        and abs(national.mean_predicted - national.test_prevalence)
        <= modelling.CALIBRATION_LARGE_TOLERANCE * national.test_prevalence,
        PAGE,
        "the national predictions are close to calibrated",
    )
    full = verdicts[verdicts.features.str.startswith("full")]
    main = full.set_index("estimator").loc[to_bcn.estimator]
    _check(main.total_drop > 0, PAGE, "the model ranks Barcelona's crashes less well")
    _check(main.intrinsic_difference > 0, PAGE, "Barcelona's crashes are harder to rank")
    _check(
        abs(
            main.total_drop
            - (main.training_size_cost + main.intrinsic_difference + main.transport_cost)
        )
        < 1e-6,
        PAGE,
        "the components of the Barcelona fall add up",
    )
    # The parts are shown to three decimals; they must add up as shown.
    _check(
        round(main.total_drop, 3)
        == round(
            round(main.training_size_cost, 3)
            + round(main.intrinsic_difference, 3)
            + round(main.transport_cost, 3),
            3,
        ),
        PAGE,
        "the Barcelona fall and its parts add up to three decimals",
    )
    shown_components = components[
        components.features.str.startswith("full Catalan")
        & components.estimator.eq(to_bcn.estimator)
    ].set_index("component")
    _check(
        shown_components.loc["training-size cost", "low"] > 0
        and shown_components.loc["intrinsic difference", "low"] > 0
        and not main.transport_cost_excludes_zero
        and abs(to_bcn.transfer_gap) < tolerance,
        PAGE,
        "Barcelona's crashes are harder to rank at equal training size, and applying the model "
        "there costs no measurable ranking",
    )
    within = reported[
        (reported.model == "catalonia_crash_severity")
        & reported.experiment.str.match(r"temporal holdout|leave out \w+ demarcation")
    ]
    _check(
        len(within) > 1 and bool((within.transfer_gap >= -tolerance).all()),
        PAGE,
        "the Catalonia severity model keeps its ranking in a later year and in each province "
        "left out",
    )
    serious = shares[shares.universe.str.startswith("crashes with")]

    def divergences(comparison: str) -> pd.Series:
        return (
            serious[serious.comparison.eq(comparison)]
            .drop_duplicates("variable")
            .set_index("variable")
            .variable_jsd.sort_values(ascending=False)
        )

    cat_mix = divergences("Catalonia vs Spain outside Catalonia")
    material = cat_mix[cat_mix > resemblance]
    _check(
        {"road_class", "crash_type", "alignment_recorded"} <= set(material.index),
        PAGE,
        "Catalonia's serious crashes differ from Spain's in road type, crash type and recording",
    )
    stage5 = path[path.stage.eq(5)]
    _check(
        bool(stage5.status.eq("failed").all())
        and not path.verdict.eq("potentially nationally transferable").any(),
        PAGE,
        "no training population resembles Spain's, so national use is not established",
    )
    used = mapping[mapping.enters_cross_source_tests]
    body = summary(
        "The Catalonia severity model, restricted to the "
        f"{_count(len(used))} variables that DGT's national crash records code in the same way, "
        "ranks serious and fatal crashes elsewhere in Spain by their probability of being fatal "
        "almost as well as a model trained on those records. On the "
        f"{_fmt_int(national.test_n)} such crashes recorded outside Catalonia, "
        f"{_fmt_int(national.test_positives)} of them fatal within 24 hours, this harmonised "
        f"Catalonia model has a ROC-AUC of {national.roc_auc:.3f} (0.5 is chance and 1 a perfect "
        f"ranking), against {national.in_domain_cv_roc_auc:.3f} for the model trained on DGT's "
        "records. Within Catalonia, the Catalonia severity model itself keeps its ranking in a "
        "later year and in each province left out of training. Trained on the rest of "
        f"Catalonia, it scores {to_bcn.roc_auc:.3f} in Barcelona city, against "
        f"{to_bcn.in_domain_cv_roc_auc:.3f} for a model trained on the city's own crashes: the "
        "city's crashes are harder to rank than the rest of Catalonia's, and applying the model "
        "there costs no measurable ranking. Catalonia's serious "
        "and fatal crashes differ from Spain's in road type, crash type and recording practice, "
        "so national use of the models is not established."
    )
    body += (
        "<p>Every test scores crashes that played no part in training and sets the score beside "
        "a reference: a model of the same kind trained within the test population and "
        "cross-validated there. The reference shows how much ranking that population allows; the "
        "difference between the scores measures what is lost by applying a model outside the "
        "population it learned from. A small test population gives a weak reference, which a "
        "model trained elsewhere on many more crashes can beat.</p>"
    )

    # ------------------------------------------------------------------ DGT records elsewhere
    disagree = mapping[mapping.a_priori_status.isin(["exact", "defensible"]) & ~mapping.validated]
    unusable = mapping[mapping.a_priori_status.eq("unusable")]
    _check(
        used.overlap_jsd.max() <= harmonise.MAX_OVERLAP_JSD,
        PAGE,
        "the harmonised variables agree between the two sources",
    )
    for check in (
        "target equivalence",
        "inclusion equivalence",
        "no Catalan records in the national test",
        "feature coding",
    ):
        _check(bool(national_checks.loc[check, "passed"]), PAGE, f"the national test: {check}")
    equal_years = int((province_years.ratio_fatal_24h == 1).sum())
    inclusion = (
        province_years.cat_crashes_fatal_or_serious
        / province_years.dgt_crashes_fatal_or_serious_24h
    )
    _check(
        equal_years == len(province_years) and float((inclusion - 1).abs().max()) < 0.01,
        PAGE,
        "the Catalan file's counts match DGT's 24-hour counts in every province-year",
    )
    missing = [
        float(v)
        for v in re.findall(r"([\d.]+)%", str(national_checks.loc["missingness", "evidence"]))
    ]
    _check(len(missing) == 3, PAGE, "missing values are reported for the three record sets")
    _check(
        national.train_prevalence < national.mean_predicted < national.test_prevalence,
        PAGE,
        "the national mean prediction lies between the training and test fatal shares",
    )
    for row in (early, reweighted):
        _check(
            abs(row.roc_auc - national.roc_auc) < 0.01,
            PAGE,
            "the national result is unchanged by earlier training years or reweighting",
        )
    _check(
        abs(same_cat.roc_auc - same_dgt.roc_auc) < 0.005,
        PAGE,
        "the same crashes score alike from either source",
    )
    _check(
        dgt_only.transfer_gap >= -tolerance and dgt_only.roc_auc_low > 0.5,
        PAGE,
        "the model keeps its ranking on Catalan crashes only DGT records",
    )

    def level(variable: str, name: str) -> pd.Series:
        part = serious[
            serious.comparison.eq("Catalonia vs Spain outside Catalonia")
            & serious.variable.eq(variable)
        ]
        return part.set_index("level").loc[name]

    weather_blank = level("weather", "not specified")
    surface_blank = level("surface", "not specified")
    body += "<h2>Validation on DGT records outside Catalonia</h2>"
    body += (
        "<p>DGT's records of crashes outside Catalonia are kept separately from the Catalan "
        "file, so they provide an external test. It uses the harmonised Catalonia model: the "
        f"Catalonia severity model restricted to the {_count(len(used))} variables both sources "
        "record in the same way, trained on the Catalan file alone, with no Catalan crash in the "
        "test. The outcome means the same in both sources: the Catalan file's counts match DGT's "
        "24-hour counts in every province and year both cover "
        '(<a href="catalonia.html#dgt-agreement">Catalonia</a>).</p>'
    )
    body += (
        "<p>On these crashes the Catalonia-trained model has a ROC-AUC of "
        f"{national.roc_auc:.3f} (95% interval {national.roc_auc_low:.3f}–"
        f"{national.roc_auc_high:.3f}), against {national.in_domain_cv_roc_auc:.3f} for a model "
        "of the same kind trained on DGT's records outside Catalonia, a difference of "
        f"{_signed(national.transfer_gap, 3)}. Fatal crashes are commoner in the test "
        f"({_fmt_pct(national.test_prevalence)}) than in the Catalan training records "
        f"({_fmt_pct(national.train_prevalence)}). The model's mean prediction, "
        f"{_fmt_pct(national.mean_predicted)}, falls between the two, and its calibration slope of "
        f"{national.calibration_slope:.2f} shows probabilities close to calibrated, "
        + (
            "slightly less extreme than the outcomes warrant."
            if national.calibration_slope > 1
            else "slightly more extreme than the outcomes warrant."
        )
        + "</p>"
    )
    body += (
        "<p>The result holds when the test is varied: the model scores "
        f"{early.roc_auc:.3f} when trained only on the Catalan years before DGT's records begin "
        f"({_years(early.train_domain)}), and {reweighted.roc_auc:.3f} when its training "
        "crashes are reweighted to the national mix of zone and crash type. The same Catalan "
        f"crashes of {_years(same_cat.test_domain)} score {same_cat.roc_auc:.3f} from the "
        f"Catalan file and {same_dgt.roc_auc:.3f} from DGT's records, so the source of the "
        "record makes almost no difference.</p>"
    )
    harmonised = reported[reported.model == "catalonia_common_dgt"]
    body += figure(
        "tr2_dgt_transfer",
        "Dot chart of the harmonised Catalonia model's ROC-AUC, with 95% intervals, on a later "
        "Catalan year, each province left out, the same crashes from both sources, a year "
        "only DGT records, and DGT crashes elsewhere in Spain. The scores lie between "
        f"{harmonised.roc_auc.min():.2f} and {harmonised.roc_auc.max():.2f}.",
        captions,
    )
    shown_provinces = provinces[provinces.reported]
    names = rates.drop_duplicates("province_code").set_index("province_code").province
    worst = shown_provinces.loc[shown_provinces.roc_auc.idxmin()]
    best = shown_provinces.loc[shown_provinces.roc_auc.idxmax()]
    _check(
        bool(
            (
                (shown_provinces.positives >= minimum)
                & (shown_provinces.n - shown_provinces.positives >= minimum)
            ).all()
        ),
        PAGE,
        "every province shown has enough fatal and non-fatal crashes",
    )
    body += (
        f"<p>Across the {len(shown_provinces)} provinces with at least {minimum} fatal and "
        f"{minimum} non-fatal crashes, the ROC-AUC runs from {worst.roc_auc:.2f} "
        f"({names[worst.province_code]}) to {best.roc_auc:.2f} ({names[best.province_code]}), "
        f"with a median of {shown_provinces.roc_auc.median():.2f}.</p>"
    )
    body += technical(
        "Results by province outside Catalonia",
        figure(
            "tr3_province_auc",
            "Dot chart of the harmonised Catalonia model's ROC-AUC in each province outside "
            f"Catalonia, from {worst.roc_auc:.2f} in {names[worst.province_code]} to "
            f"{best.roc_auc:.2f} in {names[best.province_code]}.",
            captions,
        ),
    )
    _check(
        weather_blank.share_b > 0,
        PAGE,
        "weather is sometimes unspecified in DGT's records outside Catalonia",
    )
    body += technical(
        "Variables of the harmonised Catalonia model",
        f"<p>The {_count(len(used))} variables are {_variables(used.field)}. "
        f"{_variables(disagree.field).capitalize()} were left out because their codings "
        "disagree on the crashes both sources hold, and "
        f"{_join(['the ' + _variable(v) for v in unusable.field])} are not available in a "
        "comparable form. Averaged over the variables used, values recorded as not specified "
        f"make up at most {_fmt_pct(max(missing) / 100)} of any source's records, although "
        f"weather is unspecified in {_fmt_pct(weather_blank.share_b)} of serious and fatal "
        "crashes outside Catalonia.</p>",
    )

    # ------------------------------------------------------------------ within Catalonia
    cat_provinces = reported[
        (reported.model == "catalonia_crash_severity")
        & reported.experiment.str.match(r"leave out \w+ demarcation$")
    ].assign(name=lambda d: d.experiment.str.extract(r"leave out (\w+) demarcation")[0])
    ahead = cat_provinces[cat_provinces.transfer_gap > 0]
    behind = cat_provinces[cat_provinces.transfer_gap <= 0]
    _check(
        list(behind.name) == ["Barcelona"]
        and behind.iloc[0].test_n > behind.iloc[0].train_n
        and bool((ahead.train_n > ahead.in_domain_train_n).all()),
        PAGE,
        "the model beats the small provinces' own models and falls short only in the "
        "Barcelona province, which holds most of the crashes",
    )
    _check(
        later_year.transfer_gap > 0 and later_year.train_n > later_year.in_domain_train_n,
        PAGE,
        "the later-year model beats a model trained on that year alone",
    )
    lowest = cat_provinces.loc[cat_provinces.roc_auc.idxmin()]
    highest = cat_provinces.loc[cat_provinces.roc_auc.idxmax()]
    gap_behind = behind.iloc[0]
    # The year-alone reference and the descriptive table on the models page are different
    # comparators; where they round alike, the page says so.
    descriptive = rule_comparison.loc["catalonia_crash_severity", "rule_roc_auc"]
    same_display = f"{descriptive:.2f}" == f"{later_year.in_domain_cv_roc_auc:.2f}"
    body += "<h2>Validation within Catalonia</h2>"
    body += (
        "<p>Tested without its province variable, so that a province left out of training is "
        "new to it, the Catalonia severity model keeps its ranking inside Catalonia. On the final "
        f"year of the Catalan file ({later_year_label}), held back from training and model "
        f"choice, it scores {later_year.roc_auc:.2f}, against "
        f"{later_year.in_domain_cv_roc_auc:.2f} for a model trained and cross-validated on the "
        f"{_fmt_int(later_year.test_n)} crashes of that year alone"
        + (
            " (a different benchmark from the descriptive table on "
            '<a href="severity-models.html">Severity models</a>, which also scores '
            f"{descriptive:.2f})"
            if same_display
            else ""
        )
        + f". With each of the {_count(len(cat_provinces))} provinces left out of training in "
        f"turn, it scores between {lowest.roc_auc:.2f} ({lowest['name']}) and "
        f"{highest.roc_auc:.2f} ({highest['name']}) on the province it did not see: above the "
        f"province's own model in {_join(list(ahead.name))}, whose own records are few, and "
        f"{_fmt_dec(-gap_behind.transfer_gap, 2)} below it in the province of Barcelona, which "
        "holds most of the crashes.</p>"
    )
    catalan_tests = reported[reported.model == "catalonia_crash_severity"]
    _check(
        bool((catalan_tests.roc_auc_low.fillna(catalan_tests.roc_auc) > 0.5).all()),
        PAGE,
        "every test of the Catalonia severity model lies above chance",
    )
    body += figure(
        "tr1_catalonia_transfer",
        "Dot chart of the Catalonia severity model's ROC-AUC, with 95% intervals, on records it "
        "was not trained on: a later year, each province left out, Barcelona city from the "
        "rest of Catalonia and the reverse. Every score lies above the chance level of 0.5; "
        "the lowest is the model trained on Barcelona and scored on the rest of Catalonia.",
        captions,
    )

    # ------------------------------------------------------------------ Barcelona
    _check(
        to_bcn.roc_auc < cat_provinces.roc_auc.min(),
        PAGE,
        "Barcelona city is the hardest test inside Catalonia",
    )
    _check(
        not slope_low <= to_bcn.calibration_slope <= slope_high,
        PAGE,
        "the Catalonia severity model's probabilities do not carry over to Barcelona",
    )
    _check(
        from_bcn.transfer_gap < -tolerance,
        PAGE,
        "a model trained on Barcelona ranks the rest of Catalonia poorly",
    )
    rest_reference = from_bcn.in_domain_cv_roc_auc
    _check(
        abs(rest_reference - (to_bcn.roc_auc + main.total_drop)) < 1e-3,
        PAGE,
        "the rest of Catalonia's reference is the start of the Barcelona fall",
    )
    _check(
        to_bcn.in_domain_train_n < to_bcn.train_n,
        PAGE,
        "Barcelona's own model learns from fewer crashes than the model trained elsewhere",
    )
    intrinsic = shown_components.loc["intrinsic difference"]
    moving = shown_components.loc["transport cost"]
    # intrinsic_difference_against_urban = (other urban Catalan crashes, same training size)
    # minus Barcelona: negative means those urban crashes are harder to rank than Barcelona's.
    urban = main.intrinsic_difference_against_urban
    urban_only = shown_components.loc["urban-only training"]
    _check(
        urban_only.value < 0 and urban_only.high < 0,
        PAGE,
        "training on urban crashes alone transfers worse to Barcelona",
    )
    if urban <= 0 and main.urban_comparison_excludes_zero:
        urban_sentence = (
            "The difficulty is shared by urban crashes: at the same training size, the rest of "
            f"Catalonia's urban crashes are ranked {_fmt_dec(-urban, 3)} less well than "
            "Barcelona's."
        )
    elif not main.urban_comparison_excludes_zero:
        urban_sentence = (
            "The difficulty is shared by urban crashes: at the same training size, the rest of "
            "Catalonia's urban crashes are about as hard to rank as Barcelona's (difference "
            f"{_signed(urban, 3)})."
        )
    else:
        urban_sentence = (
            "Barcelona's crashes are harder to rank than the rest of Catalonia's urban crashes "
            f"too, by {_fmt_dec(urban, 3)} at the same training size."
        )
    body += "<h2>Validation in Barcelona</h2>"
    body += (
        "<p>Barcelona city is the hardest test inside Catalonia. Trained on the rest of "
        "Catalonia, the Catalonia severity model ranks the city's crashes at "
        f"{to_bcn.roc_auc:.3f}, against {to_bcn.in_domain_cv_roc_auc:.3f} for a model trained "
        f"in Barcelona (a difference of {_signed(to_bcn.transfer_gap, 3)}) and "
        f"{rest_reference:.3f} for a model trained and tested in the rest of Catalonia. The "
        f"fall of {main.total_drop:.3f} can be traced in three steps. Cutting a rest-of-Catalonia model's training set to the "
        f"{_fmt_int(to_bcn.in_domain_train_n)} crashes from which Barcelona's own model learns "
        f"lowers its score by {main.training_size_cost:.3f}. At that equal size, Barcelona's "
        f"crashes are ranked {main.intrinsic_difference:.3f} less well than the rest of "
        f"Catalonia's (95% interval {_interval(intrinsic.low, intrinsic.high, 3)}): they are "
        f"harder to rank. The last {main.transport_cost:.3f} separates Barcelona's own model "
        f"from the one trained on {_fmt_int(to_bcn.train_n)} crashes elsewhere: the loss from "
        "applying a model outside the population it learned from, net of the gain from its "
        f"larger training set. Its interval ({_interval(moving.low, moving.high, 3)}) includes "
        "zero.</p>"
    )
    body += (
        f"<p>{urban_sentence} Training the model on those urban crashes alone lowers its score "
        f"in Barcelona by {_fmt_dec(-urban_only.value, 3)}. The Catalonia-trained model's "
        "probabilities do not carry over "
        f"to the city (calibration slope {to_bcn.calibration_slope:.2f}, where 1 is "
        "calibrated), so there its scores order crashes without estimating their fatal share. "
        "In the reverse direction, a model trained on Barcelona alone ranks the rest of "
        f"Catalonia poorly ({from_bcn.roc_auc:.3f}, against {rest_reference:.3f}).</p>"
    )
    component_order = [c for c in COMPONENTS if c in shown_components.index]
    _check(
        len(component_order) == len(shown_components),
        PAGE,
        "every component of the Barcelona fall has a reader-facing name",
    )
    body += technical(
        "Components of the fall in Barcelona",
        table(
            pd.DataFrame(
                {
                    "Component": [COMPONENTS[c][0] for c in component_order],
                    "ROC-AUC difference": [
                        _fmt_dec(shown_components.loc[c, "value"], 3) for c in component_order
                    ],
                    "95% interval": [
                        ""
                        if pd.isna(shown_components.loc[c, "low"])
                        else _interval(
                            shown_components.loc[c, "low"], shown_components.loc[c, "high"], 3
                        )
                        for c in component_order
                    ],
                    "What is compared": [COMPONENTS[c][1] for c in component_order],
                }
            ),
            "Catalonia severity model without its province variable. The second, third and "
            "fourth rows add up to the total fall.",
        ),
    )

    groups = []
    for _, group in strategies.groupby("target_domain", sort=False):
        if group.estimator.eq(to_bcn.estimator).any():
            group = group[group.estimator.eq(to_bcn.estimator)]
        groups.append(group)
    chosen = pd.concat(groups)
    pooled = chosen[chosen.strategy.eq("pooled: both domains")].set_index("target_domain")
    specific = chosen[chosen.strategy.str.startswith("domain-specific")].set_index("target_domain")
    _check(
        bool((pooled.gain_over_specific_high >= 0).all()),
        PAGE,
        "a pooled model ranks each population at least as well as a separate model",
    )
    _check(
        abs(specific.loc["Barcelona municipality", "roc_auc"] - to_bcn.in_domain_cv_roc_auc) < 1e-6,
        PAGE,
        "the separate Barcelona model is the Barcelona reference of the transfer test",
    )
    body += (
        "<p>A single model trained on Barcelona's and the rest of Catalonia's crashes together "
        "ranks each population as well as a separate model does ("
        f"{pooled.loc['Barcelona municipality', 'roc_auc']:.3f} against "
        f"{specific.loc['Barcelona municipality', 'roc_auc']:.3f} in Barcelona, "
        f"{pooled.loc['rest of Catalonia', 'roc_auc']:.3f} against "
        f"{specific.loc['rest of Catalonia', 'roc_auc']:.3f} in the rest of Catalonia), so a "
        "separate model for Barcelona brings no measurable gain.</p>"
    )
    body += technical(
        "Pooled and separate models",
        table(
            pd.DataFrame(
                {
                    "Crashes scored": [_place(d, True) for d in chosen.target_domain],
                    "Model trained on": [_strategy_label(s) for s in chosen.strategy],
                    "ROC-AUC": [_fmt_dec(v, 3) for v in chosen.roc_auc],
                    "Difference from the separate model (95% interval)": [
                        ""
                        if s.startswith("domain-specific")
                        else f"{_signed(g, 3)} ({_interval(lo, hi, 3)})"
                        for s, g, lo, hi in zip(
                            chosen.strategy,
                            chosen.gain_over_specific,
                            chosen.gain_over_specific_low,
                            chosen.gain_over_specific_high,
                        )
                    ],
                }
            ),
            "Models scored on the same held-out crashes of each population, Catalan file.",
        ),
    )

    loss = components[components.component.str.startswith("feature loss")]
    loss_bcn = loss[
        loss.component.str.endswith("Barcelona municipality") & loss.estimator.eq(to_bcn.estimator)
    ]
    _check(
        bcn_records.status != "reported"
        and min(bcn_records.test_positives, bcn_records.test_n - bcn_records.test_positives)
        < minimum,
        PAGE,
        "Barcelona's own records have too few fatal crashes for a ranking test",
    )
    _check(
        bcn_records.mean_predicted > bcn_records.observed_high,
        PAGE,
        "the model overstates the fatal share in Barcelona's own records",
    )
    _check(
        bcn_vars.roc_auc < bcn_vars.in_domain_cv_roc_auc,
        PAGE,
        "on Barcelona's variables the Catalonia model starts lower in the city",
    )
    body += (
        f"<p>The Guàrdia Urbana's own records for {bcn_records_year} hold "
        f"{_fmt_int(bcn_records.test_n)} crashes defined compatibly with the Catalan file, only "
        f"{_fmt_int(bcn_records.test_positives)} of them fatal: too few for a ranking test. For "
        "these crashes the Catalonia model restricted to Barcelona's variables predicts a fatal "
        f"share of {_fmt_pct(bcn_records.mean_predicted)}, against "
        f"{_fmt_pct(bcn_records.test_prevalence)} observed (95% interval "
        f"{_fmt_dec(100 * bcn_records.observed_low, 1)}–{_fmt_pct(bcn_records.observed_high)}), "
        "so it overstates the fatal share in the city.</p>"
    )
    records = ""
    if not loss_bcn.empty:
        lb = loss_bcn.iloc[0]
        _check(lb.low > 0, PAGE, "Barcelona's variables cost ranking within Barcelona")
        records = (
            "Restricting the Catalonia severity model to the variables Barcelona records costs "
            f"{lb.value:.3f} of ROC-AUC within Barcelona (95% interval "
            f"{_interval(lb.low, lb.high, 3)}). "
        )
    body += technical(
        "Barcelona's own crash records",
        f"<p>{records}On the city's crashes in the Catalan file, the model restricted to "
        f"Barcelona's variables scores {bcn_vars.roc_auc:.3f}, against "
        f"{bcn_vars.in_domain_cv_roc_auc:.3f} for a model trained in Barcelona on the same "
        "variables. The crashes taken from the Guàrdia Urbana's records are those with a death "
        "within 24 hours or a hospital stay of more than 24 hours, compatible with the "
        f"definition of the Catalan file. A ranking test needs at least {minimum} fatal and {minimum} non-fatal "
        "crashes, so no ROC-AUC is reported for them.</p>",
    )
    _check(
        districts.transfer_gap >= -tolerance and districts.roc_auc_low > 0.5,
        PAGE,
        "the person-severity model keeps its ranking across Barcelona's districts",
    )
    body += (
        "<p>Within the city, the Barcelona person-severity model keeps its ranking when each of "
        f"the {_count(int(districts.districts))} districts is left out of training in turn: "
        f"{districts.roc_auc:.3f} on the district it did not see, against "
        f"{district_reference.roc_auc:.3f} in ordinary cross-validation on the same records.</p>"
    )

    # ------------------------------------------------------------------ population differences
    populations: dict[str, dict[str, tuple[float, float]]] = {}
    for r in outcomes.itertuples():
        key = OUTCOMES.get(r.outcome)
        if key is None:
            raise ValueError(f"{PAGE} page: no reader-facing name for the outcome {r.outcome!r}")
        first, second = r.comparison.split(" vs ")
        for name, share, n in ((first, r.share_a, r.n_a), (second, r.share_b, r.n_b)):
            seen = populations.setdefault(name, {})
            if key in seen:
                _check(
                    abs(seen[key][0] - share) < 1e-9 and seen[key][1] == n,
                    PAGE,
                    f"{name} has one set of outcome shares",
                )
            seen[key] = (share, n)
    order = ["Barcelona city", "rest of Catalonia", "Catalonia", "Spain outside Catalonia"]
    _check(set(order) == set(populations), PAGE, "the outcome table covers four populations")
    for name in order:
        _check(
            populations[name]["serious"][1] == populations[name]["fatal_30d"][1],
            PAGE,
            f"{name}: the 30-day and 24-hour shares share a denominator",
        )
    cat, spain = populations["Catalonia"], populations["Spain outside Catalonia"]
    bcn, rest = populations["Barcelona city"], populations["rest of Catalonia"]
    _check(
        cat["serious"][0] < spain["serious"][0]
        and cat["fatal_24h"][0] < spain["fatal_24h"][0]
        and bcn["serious"][0] < rest["serious"][0]
        and bcn["fatal_24h"][0] < cat["fatal_24h"][0],
        PAGE,
        "serious and fatal shares are lower in Catalonia, and lower still in Barcelona",
    )
    same_source = register[register.comparison.str.startswith("DGT severe crashes per resident")]
    _check(
        not same_source.empty
        and same_source.definition_compatibility.eq("same source for every province").all(),
        PAGE,
        "DGT's records apply one source's definitions in every province",
    )
    body += "<h2>Population differences</h2>"
    body += (
        "<p>In DGT's records, which use the same definitions in every province, a death or "
        "serious injury occurs in a smaller share of injury crashes in Catalonia than elsewhere "
        f"in Spain ({_fmt_pct(cat['serious'][0])} against {_fmt_pct(spain['serious'][0])}), and "
        "fewer of those crashes are fatal within 24 hours "
        f"({_fmt_pct(cat['fatal_24h'][0])} against {_fmt_pct(spain['fatal_24h'][0])}). Barcelona "
        "city lies further from the national pattern, at "
        f"{_fmt_pct(bcn['serious'][0])} and {_fmt_pct(bcn['fatal_24h'][0])}.</p>"
    )
    rows = {
        "Injury crashes": [_fmt_int(populations[p]["serious"][1]) for p in order],
        "Share with a death or serious injury (24 hours)": [
            _fmt_pct(populations[p]["serious"][0]) for p in order
        ],
        "Share fatal (30 days)": [_fmt_pct(populations[p]["fatal_30d"][0]) for p in order],
        "Crashes with a death or serious injury (24 hours)": [
            _fmt_int(populations[p]["fatal_24h"][1]) for p in order
        ],
        "Of these, share fatal (24 hours)": [
            _fmt_pct(populations[p]["fatal_24h"][0]) for p in order
        ],
    }
    body += table(
        pd.DataFrame(
            [[label, *values] for label, values in rows.items()],
            columns=["Measure", *[_place(p, True) for p in order]],
        ),
        f"Crash severity in DGT records, {dgt_period}. Barcelona city is part of Catalonia.",
    )

    def largest(variable: str) -> str:
        part = serious[
            serious.comparison.eq("Catalonia vs Spain outside Catalonia")
            & serious.variable.eq(variable)
        ]
        return part.loc[part.difference.abs().idxmax(), "level"]

    dual = level("road_class", "dual_carriageway")
    conventional = level("road_class", "conventional")
    run_off = level("crash_type", "run-off-road")
    unknown = level("alignment_recorded", "unknown")
    _check(
        largest("road_class") in ("conventional", "dual_carriageway")
        and conventional.difference < 0 < dual.difference
        and largest("crash_type") == "run-off-road"
        and run_off.difference < 0,
        PAGE,
        "road type and run-off-road crashes carry the largest compositional differences",
    )
    _check(
        unknown.share_a > unknown.share_b
        and weather_blank.share_b > weather_blank.share_a
        and weather_blank.share_a < 0.005
        and surface_blank.share_b > surface_blank.share_a,
        PAGE,
        "'unknown' alignment is commoner in Catalonia; weather and surface are left unspecified "
        "more often elsewhere, weather almost never in Catalonia",
    )
    # Barcelona's serious crashes against Spain's, the same population as Catalonia's above.
    bcn_mix = divergences("Barcelona city vs Spain outside Catalonia")
    bcn_material = bcn_mix[bcn_mix > resemblance]
    _check(
        len(bcn_material) > len(material) and bcn_mix.iloc[0] > 2 * cat_mix.iloc[0],
        PAGE,
        "Barcelona's serious crashes differ from Spain's far more than Catalonia's do",
    )
    body += (
        "<p>Catalonia's serious and fatal crashes also occur more often on dual carriageways "
        f"({_fmt_pct(dual.share_a)} against {_fmt_pct(dual.share_b)} elsewhere in Spain) and "
        f"less often on conventional roads ({_fmt_pct(conventional.share_a)} against "
        f"{_fmt_pct(conventional.share_b)}), and fewer are run-off-road crashes "
        f"({_fmt_pct(run_off.share_a)} against {_fmt_pct(run_off.share_b)}). "
        f"{_count(len(material)).capitalize()} of the {_count(len(cat_mix))} variables compared "
        f"differ by more than a limit fixed in advance: {_variables(material.index)}. Part of "
        "the difference lies in recording practice, which the data cannot separate from "
        "differences in the crashes themselves: DGT's code for an unknown road alignment covers "
        f"{_fmt_pct(unknown.share_a)} of these crashes in Catalonia and "
        f"{_fmt_pct(unknown.share_b)} elsewhere, and weather is unspecified in "
        f"{_fmt_pct(weather_blank.share_b)} outside Catalonia but almost never inside it. "
        "Barcelona city's "
        f"serious and fatal crashes differ from Spain's far more, on {_count(len(bcn_material))} "
        f"variables, led by {_variables(bcn_material.index[:3])}.</p>"
    )
    body += technical(
        "Divergence of each variable from Spain outside Catalonia",
        "<p>The Jensen–Shannon divergence compares two distributions of a variable's categories: "
        "it is 0 when they are identical and grows as they separate. A divergence above "
        f"{resemblance:g} was fixed in advance as a material difference.</p>"
        + table(
            pd.DataFrame(
                {
                    "Variable": [
                        VARIABLE_HEADINGS.get(v, _variable(v)).capitalize() for v in cat_mix.index
                    ],
                    "Catalonia": [_fmt_dec(v, 3) for v in cat_mix],
                    "Barcelona city": [_fmt_dec(bcn_mix.get(v), 3) for v in cat_mix.index],
                }
            ),
            "Divergence from Spain outside Catalonia, crashes with a death or serious injury, "
            f"DGT records {dgt_period}.",
        ),
    )

    # ------------------------------------------------------------------ scope
    status = path.set_index(["model", "stage"]).status
    _check(
        status[("catalonia_common_dgt", 4)] == "passed"
        and status[("catalonia_crash_severity", 4)] != "passed"
        and status[("barcelona_person_severity", 4)] != "passed"
        and status[("barcelona_person_severity", 2)] == "passed"
        and status[("barcelona_person_severity", 3)] == "passed",
        PAGE,
        "only the harmonised model has an independent Spanish test; the Barcelona models are "
        "validated across months and districts",
    )
    _check(
        not ((status == "passed").groupby(level="model").all()).any(),
        PAGE,
        "no model passes every kind of test",
    )
    _check(
        national.transfer_gap <= 0,
        PAGE,
        "the harmonised model scores slightly below the model trained on the Spanish records",
    )
    body += "<h2>Scope of generalisation</h2>"
    body += (
        "<p>A successful external test shows that the associations a model has learned order "
        "cases in much the same way in a population it has not seen, recorded by another body "
        "under its own procedures. The test on DGT's records meets that standard: the two "
        "sources are kept separately and define the outcome in the same way, and the "
        f"harmonised Catalonia model loses only {_fmt_dec(-national.transfer_gap, 3)} of ROC-AUC "
        "against a model trained on the Spanish records.</p>"
        "<p>Such a test leaves three questions open. It does not show that the training "
        "population resembles the population tested: Catalonia's serious and fatal crashes "
        f"differ materially from Spain's on {_count(len(material))} of the "
        f"{_count(len(cat_mix))} variables compared, and a model can rank well in a population "
        "whose composition differs from its own. It does not make the associations causal: a "
        "variable can rank fatal outcomes well because it travels with something the records "
        'do not hold (see <a href="severity-models.html">Severity models</a>). And it covers '
        f"only the {_count(len(used))} variables that both sources record alike. The Catalonia "
        "severity model itself and the Barcelona person-severity model rest on "
        "variables or records that no second source holds, so both are validated only within "
        "their own files.</p>"
        "<p>The evidence therefore supports using the Catalonia severity model to rank serious "
        "and fatal crashes within Catalonia. No model has passed every kind of test, from "
        "held-out records to a comparison of its training crashes with Spain's, and none has "
        "been shown to be fit for use across Spain.</p>"
    )
    model_order = list(MODELS)
    _check(
        set(model_order) == set(path.model),
        PAGE,
        "every model in the validation evidence has a reader-facing name",
    )

    def evidence_cell(model: str, stage: int) -> str:
        row = path[path.model.eq(model) & path.stage.eq(stage)].iloc[0]
        cells = RESEMBLANCE_CELLS if stage == 5 else EVIDENCE_CELLS
        if row.status not in cells:
            raise ValueError(f"{PAGE} page: no reader-facing word for {row.status!r}")
        if row.status == "not testable":
            _check("too few" in row.evidence, PAGE, "an untestable stage had too few cases")
        return cells[row.status]

    not_testable = path[path.status.eq("not testable")]
    _check(
        list(not_testable.model) == ["catalonia_common_bcn"],
        PAGE,
        "only the test on Barcelona's own records had too few cases",
    )
    body += technical(
        "Validation evidence by model",
        table(
            pd.DataFrame(
                {
                    "Model": [_model(m) for m in model_order],
                    **{
                        label: [evidence_cell(m, stage) for m in model_order]
                        for stage, label in EVIDENCE_COLUMNS.items()
                    },
                }
            ),
            "Result of each kind of test, by model, from the records closest to the training "
            "data to the comparison of the training crashes with Spain's.",
        )
        + "<p>“Passed” means that the model ranks above chance with 95% confidence and, where a "
        "model trained within the test population gives a reference, scores no more than "
        f"{tolerance:g} below it. The last column is “yes” only if no variable's divergence "
        f"from Spain's mix exceeds {resemblance:g}. Both limits were fixed before any result was "
        "read. “Not run”: no second source holds the model's variables or the crashes it would "
        f"need. “Too few cases”: Barcelona's own records for {bcn_records_year} hold "
        f"{_fmt_int(bcn_records.test_positives)} fatal crashes.</p>",
    )

    # ------------------------------------------------------------------ all tests
    shown = reported[
        reported.in_domain_cv_roc_auc.notna() & reported.model.ne("barcelona_crash_severity")
    ].drop_duplicates(["model", "experiment"])
    shown = shown.assign(
        _order=shown.model.map({m: i for i, m in enumerate(model_order)})
    ).sort_values("_order", kind="stable")
    # The Catalonia severity model is tested without its province variable, so that a province
    # left out is new to it; the models page reports the version with it.
    no_province = variants[
        variants.model.eq("catalonia_crash_severity")
        & variants.feature_set.eq(primary.loc["catalonia_crash_severity", "feature_set"])
        & variants.geography.eq("none")
        & variants.estimator.eq(later_year.estimator)
        & variants.evaluated_on.eq("test")
    ]
    _check(
        len(no_province) == 1 and abs(no_province.roc_auc.iloc[0] - later_year.roc_auc) < 1e-6,
        PAGE,
        "the external tests use the Catalonia severity model without its province variable",
    )
    with_province = primary.loc["catalonia_crash_severity", "roc_auc"]
    body += technical(
        "All external tests",
        table(
            pd.DataFrame(
                {
                    "Test": [_test_label(r) for r in shown.itertuples()],
                    "Model": [
                        _model(m)
                        + (" (without province)" if m == "catalonia_crash_severity" else "")
                        for m in shown.model
                    ],
                    "Training records": [_fmt_int(v) for v in shown.train_n],
                    "Test records": [_fmt_int(v) for v in shown.test_n],
                    "Outcome cases": [_fmt_int(v) for v in shown.test_positives],
                    "Model tested": [_fmt_dec(v, 3) for v in shown.roc_auc],
                    "Trained in test population": [
                        _fmt_dec(v, 3) for v in shown.in_domain_cv_roc_auc
                    ],
                    "Difference": [_signed(v, 3) for v in shown.transfer_gap],
                    "Calibration slope": [_fmt_dec(v, 2) for v in shown.calibration_slope],
                }
            ),
            "ROC-AUC of each model on records it was not trained on, beside a model of the same "
            "kind trained and cross-validated in the test population (difference: model tested "
            "minus that reference). Outcome cases are fatal crashes for the Catalan models and "
            "serious or fatal injuries for the Barcelona person-severity model. Each model uses "
            "the method, logistic regression or gradient-boosted trees, chosen on its own "
            "validation data. The Catalonia severity model is tested without its province "
            "variable, so that a province left out is new to it; in the later year this version "
            f"scores {later_year.roc_auc:.3f}, against {with_province:.3f} for the version with "
            "the province variable reported on Severity models.",
        )
        + f'<p>The <a href="{DOCS_URL}/GENERALISABILITY.md">generalisability report</a> lists '
        "every test with its training and test periods, for both logistic regression and "
        "gradient-boosted trees.</p>",
    )
    body += downloads(
        [
            ("ml_transport_validation", "external tests"),
            ("ml_outward_path", "evidence by model"),
            ("ml_barcelona_diagnosis", "Barcelona scores"),
            ("ml_barcelona_diagnosis_components", "Barcelona components"),
            ("ml_domain_strategies", "pooled models"),
            ("ml_transport_provinces", "provinces"),
            ("ml_domain_shift", "variable distributions"),
            ("ml_common_feature_validation", "variable mapping"),
            ("dgt_audit_transfer", "national test checks"),
            ("gen_representativeness", "variable mixes"),
            ("gen_outcomes", "outcome shares"),
            ("gen_province_rates", "crashes per resident"),
            ("gen_cross_source_register", "source comparison"),
        ],
        method=("data.html#models", "how the models were built and judged"),
    )
    return render_page(
        PAGE,
        "External validation of the severity models",
        "Tests of the severity models on crashes from other years, places and data sources, "
        "and how Catalonia's and Barcelona's crashes compare with those of the rest of Spain.",
        body,
    )
