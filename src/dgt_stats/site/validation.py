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
    compare,
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
REVIEW = f'<a href="{DOCS_URL}/research/ML_MODEL_REVIEW.md">model review</a>'

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
# The models as the validation tables name them, as table rows. The calculator's model is the one
# the site publishes. The original Catalonia model was retired because its strongest predictor,
# the road's owner, records how a crash was documented; its tests are kept as a record. The
# Barcelona crash-severity model was replaced by its table of shares by accident type.
MODELS = {
    transport_rules.CALCULATOR: "Calculator's model",
    "catalonia_crash_severity": "Original Catalonia model (retired)",
    "catalonia_common_dgt": "Harmonised Catalonia model",
    "catalonia_common_bcn": "Catalonia model restricted to Barcelona's variables",
    "barcelona_person_severity": "Barcelona person-severity model",
    "barcelona_crash_severity": "Barcelona crash-severity model (replaced by a table)",
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
OUTCOMES = {
    "crashes with a death or serious injury (24 h), share of injury crashes": "serious",
    "fatal (24 h) among crashes with a death or serious injury": "fatal_24h",
    "fatal (30 days) among injury crashes": "fatal_30d",
}


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
            r"rolling origin",
            lambda m: f"Each year {_years(row.test_domain)} from the years before it",
        ),
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


def _table_model(row) -> str:
    """The model column of the detailed table: which model, and how it was trained."""
    if row.model == "catalonia_crash_severity":
        if row.experiment.startswith("Barcelona municipality -> rest"):
            return "Original model's specification, trained on Barcelona city only"
        return _model(row.model) + ", without province"
    return _model(row.model)


def _signed(value: float, decimals: int = 2) -> str:
    """A difference with its sign: +0.05, −0.04, 0.00."""
    text = _fmt_dec(value, decimals)
    return "+" + text if round(float(value), decimals) > 0 else text


def _interval(low: float, high: float, decimals: int = 2) -> str:
    """'0.023–0.086' when neither end carries a sign, '−0.021 to 0.054' when one does."""
    first, second = _fmt_dec(low, decimals), _fmt_dec(high, decimals)
    return f"{first} to {second}" if MINUS in first + second else f"{first}–{second}"


def _per_resident(rates: pd.DataFrame) -> dict[bool, pd.Series]:
    """Injury, severe and fatal crashes per 100,000 resident-years, Catalonia (True) and the
    rest of Spain (False), pooled over the province-years of the table."""
    totals = rates.groupby("catalan_province")[
        ["injury_crashes", "severe_crashes", "fatal_crashes", "population"]
    ].sum()
    per = totals[["injury_crashes", "severe_crashes", "fatal_crashes"]].div(
        totals.population, axis=0
    )
    return {bool(key): row * 1e5 for key, row in per.iterrows()}


def _calculator_section(calculator: pd.DataFrame, rolling_scores: pd.DataFrame) -> str:
    """The published model's tests: later years, provinces and Barcelona city left out."""
    tolerance = generalisability.MAX_TRANSFER_GAP
    slope_low, slope_high = modelling.CALIBRATION_SLOPE_RANGE
    rows = calculator.set_index("experiment")

    def one(prefix: str) -> pd.Series:
        part = calculator[calculator.experiment.str.startswith(prefix)]
        _check(len(part) == 1, PAGE, f"one calculator test named {prefix!r}")
        return part.iloc[0]

    rolling = one("rolling origin")
    later = one("temporal holdout")
    city = one("rest of Catalonia -> Barcelona municipality")
    provinces = calculator[calculator.experiment.str.match(r"leave out \w+ demarcation$")].assign(
        name=lambda d: d.experiment.str.extract(r"leave out (\w+) demarcation")[0]
    )
    held_out = pd.concat([provinces, city.to_frame().T])
    lowest = provinces.loc[provinces.roc_auc.idxmin()]
    highest = provinces.loc[provinces.roc_auc.idxmax()]
    barcelona = provinces.set_index("name").loc["Barcelona"]
    tolerance_band = modelling.CALIBRATION_LARGE_TOLERANCE

    def calibrated(row) -> bool:
        return (
            slope_low <= row.calibration_slope <= slope_high
            and abs(row.mean_predicted - row.test_prevalence)
            <= tolerance_band * row.test_prevalence
        )

    _check(
        bool((rows.roc_auc_low > 0.5).all()),
        PAGE,
        "every test of the calculator's model lies above chance",
    )
    _check(
        rolling.roc_auc > rolling.table_roc_auc and calibrated(rolling),
        PAGE,
        "on later years the calculator's model ranks above the table and its estimates hold",
    )
    _check(
        later.transfer_gap > 0 and later.train_n > later.in_domain_train_n,
        PAGE,
        "on the last year the calculator's model beats the same model fitted on that year alone",
    )
    _check(
        bool((held_out.transfer_gap.astype(float) >= -tolerance).all())
        and bool((held_out.roc_auc.astype(float) > held_out.table_roc_auc.astype(float)).all()),
        PAGE,
        "in every place left out the calculator's model is within the limit of a model fitted "
        "there and ranks above the table",
    )
    _check(
        barcelona.mean_predicted > barcelona.observed_high and not calibrated(barcelona),
        PAGE,
        "with the province of Barcelona left out the estimates run too high",
    )
    _check(
        city.mean_predicted < city.observed_low and not calibrated(city),
        PAGE,
        "with Barcelona city left out the estimates run too low",
    )
    in_city = rolling_scores[
        rolling_scores.subset.eq("Barcelona city, urban streets")
        & rolling_scores.estimator.eq("calculator")
    ].iloc[0]
    _check(
        abs(in_city.mean_predicted - in_city.prevalence) <= tolerance_band * in_city.prevalence,
        PAGE,
        "with the city's earlier crashes in the fitting, the estimates for its streets are close",
    )
    return (
        "<h2>The calculator's model</h2>"
        "<p>The calculator's model is the one the site publishes "
        '(<a href="severity-models.html">Crash severity model and calculator</a>). It has been '
        "tested only within the Catalan file, on crashes on the roads a reader can choose. "
        f"Predicting each year of {_years(rolling.test_domain)} with the model fitted on the years "
        f"before it gives a ROC-AUC of {rolling.roc_auc:.3f} (95% interval "
        f"{rolling.roc_auc_low:.3f}–{rolling.roc_auc_high:.3f}) over the "
        f"{_fmt_int(rolling.test_n)} crashes, against {rolling.table_roc_auc:.3f} for the table "
        "of fatal shares by road and crash type. On the last year alone it scores "
        f"{later.roc_auc:.3f}, against {later.in_domain_cv_roc_auc:.3f} for the same model "
        f"fitted and cross-validated on that year's {_fmt_int(later.test_n)} crashes.</p>"
        "<p>With each province left out of the fitting in turn, it scores between "
        f"{lowest.roc_auc:.2f} ({lowest['name']}) and {highest.roc_auc:.2f} ({highest['name']}) "
        "on the province it did not see. In every province that is within "
        f"{tolerance:g} of the same model fitted and cross-validated there, and above the table. "
        "Its estimates carry over less well. With the province of Barcelona left out they run "
        f"too high ({_fmt_pct(barcelona.mean_predicted)} predicted against "
        f"{_fmt_pct(barcelona.test_prevalence)} observed). Fitted on the rest of Catalonia, it "
        f"ranks Barcelona city's crashes at {city.roc_auc:.3f}, against "
        f"{city.in_domain_cv_roc_auc:.3f} for the same model fitted in the city, but it "
        f"estimates a fatal share of {_fmt_pct(city.mean_predicted)} where "
        f"{_fmt_pct(city.test_prevalence)} were fatal. Once the city's earlier crashes are in the "
        f"fitting, its estimates for the city's streets are close "
        f"({_fmt_pct(in_city.mean_predicted)} against {_fmt_pct(in_city.prevalence)}).</p>"
        "<p>No other source records the calculator's inputs: DGT's national records have no "
        "field for the road's owning network or the posted limit, and their road-type and "
        "junction codings disagree with the Catalan file's on the crashes both hold. The "
        "calculator's model therefore has no test outside Catalonia. The tests below, on other "
        "sources, use other models.</p>"
    )


def page_validation(captions: dict[str, str]) -> str:
    tests = read_table("ml_transport_validation")
    calculator = read_table("gen_calculator_transfer")
    rolling_scores = read_table("sev_rolling_scores")
    path = read_table("ml_outward_path")
    provinces = read_table("ml_transport_provinces")
    mapping = read_table("ml_common_feature_validation")
    outcomes = read_table("gen_outcomes")
    shares = read_table("gen_representativeness")
    components = read_table("ml_barcelona_diagnosis_components")
    verdicts = read_table("ml_barcelona_diagnosis_verdicts")
    national_checks = read_table("dgt_audit_transfer").set_index("check")
    province_years = read_table("cat_vs_dgt_province_year")
    rates = read_table("gen_province_rates")
    variants = read_table("ml_variants")
    selected = read_table("ml_selected")
    importance = read_table("ml_importance")
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
    later_bcn = test_row("rest of Catalonia to ", "catalonia_crash_severity")
    later_year = test_row("temporal holdout", "catalonia_crash_severity")
    national = test_row("Catalonia -> Spain outside Catalonia", "catalonia_common_dgt")
    early = test_row("Catalonia early years -> Spain", "catalonia_common_dgt")
    reweighted = test_row("Catalonia reweighted", "catalonia_common_dgt")
    same_cat = test_row("same crashes, two sources: Catalan file", "catalonia_common_dgt")
    same_dgt = test_row("same crashes, two sources: DGT records", "catalonia_common_dgt")
    dgt_only = test_row("Catalonia, a year the Catalan file", "catalonia_common_dgt")
    districts = test_row("leave one district out", "barcelona_person_severity")
    district_reference = test_row("grouped 5-fold cross-validation", "barcelona_person_severity")
    # Shown with the estimator its model chose on its own validation data, as every other test.
    records_rows = fitted[fitted.experiment.str.match(r"Catalonia -> Barcelona \d")]
    bcn_records = records_rows[
        records_rows.estimator.eq(records_rows.model.map(chosen_estimator))
    ].iloc[0]
    bcn_records_year = re.search(r"Barcelona (\d{4})", bcn_records.experiment).group(1)
    dgt_period = f"{int(rates.year.min())}–{int(rates.year.max())}"
    catalan_years = read_table("cat_frequency").year
    catalan_period = f"{int(catalan_years.min())}–{int(catalan_years.max())}"
    later_year_label = re.search(r"test (\d{4})", later_year.experiment).group(1)
    tolerance = generalisability.MAX_TRANSFER_GAP
    resemblance = generalisability.MAX_RESEMBLANCE_JSD
    slope_low, slope_high = modelling.CALIBRATION_SLOPE_RANGE
    minimum = transport_rules.MIN_POSITIVES
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
    _check(
        abs(
            main.total_drop
            - (main.training_size_cost + main.intrinsic_difference + main.transport_cost)
        )
        < 1e-6,
        PAGE,
        "the components of the Barcelona fall add up",
    )
    shown_components = components[
        components.features.str.startswith("full Catalan")
        & components.estimator.eq(to_bcn.estimator)
    ].set_index("component")
    _check(
        not slope_low <= to_bcn.calibration_slope <= slope_high,
        PAGE,
        "the original model's probabilities do not carry over to Barcelona",
    )
    _check(
        {"crash_type", "alignment_recorded"} <= set(material.index)
        and "road_class" not in material.index,
        PAGE,
        "Catalonia's serious crashes differ from Spain's in crash type and road alignment, not "
        "in road type once every conventional road is one group",
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
        "This page asks whether the study's severity models still rank crashes when they are "
        "applied to years, places and records they were not fitted on. ROC-AUC measures how "
        "well a model ranks fatal crashes above the others, on a scale from 0.5 (chance) to 1 "
        "(perfect). The calculator's model, the one the site publishes, was tested only within "
        "the Catalan file. It ranked later years' crashes better than a table of fatal shares "
        "by road and crash type, and the crashes of each province and of Barcelona city left "
        "out of its fitting about as well as the same model fitted there, but its estimates of "
        "the fatal share did not carry over to the province or the city of Barcelona. No other "
        "source records its inputs. A model restricted to the "
        f"{_count(len(used))} variables that DGT's national crash records code in the same way, "
        "trained on the Catalan file and applied to the "
        f"{_fmt_int(national.test_n)} crashes with a death or serious injury that DGT recorded "
        "elsewhere in Spain, ranked them almost as well as a model trained on those DGT records. "
        "That does not establish that any of the models can be used nationally: the published "
        "model was not part of that test, and Catalonia's serious crashes differ from the rest "
        "of Spain's in the mix of crash types and in how several fields are recorded."
    )
    body += compare(
        [
            (
                f"{national.roc_auc:.3f}",
                "ROC-AUC of the Catalonia-trained harmonised model on DGT's records of serious "
                "crashes elsewhere in Spain",
            ),
            (
                f"{national.in_domain_cv_roc_auc:.3f}",
                "ROC-AUC of a model of the same kind trained on those DGT records",
            ),
        ],
        "Little ranking performance was lost in this test.",
    )
    body += (
        "<p>Every test on this page scores crashes that played no part in training and sets "
        "the result beside a reference: a model of the same kind trained within the test "
        "population and cross-validated there. The reference shows how well that population's "
        "crashes can be ranked at all, and the difference between the two scores is what is "
        "lost by using a model trained elsewhere. A small test population gives a weak "
        "reference, which a model trained elsewhere on many more crashes can beat.</p>"
    )

    # ------------------------------------------------------------------ the calculator's model
    body += _calculator_section(calculator, rolling_scores)
    body += figure(
        "tr0_calculator_transfer",
        "Dot chart of the calculator's model's ROC-AUC, with 95% intervals, on later years, each "
        "province left out and Barcelona city, each beside the same model fitted in the test "
        f"population; the scores lie between {calculator.roc_auc.min():.2f} and "
        f"{calculator.roc_auc.max():.2f}.",
        captions,
    )

    # ------------------------------------------------------------------ DGT records elsewhere
    disagree = mapping[mapping.a_priori_status.isin(["exact", "defensible"]) & ~mapping.validated]
    unusable = mapping[mapping.a_priori_status.eq("unusable")]
    _check(
        used.overlap_jsd.max() <= harmonise.MAX_OVERLAP_JSD,
        PAGE,
        "the harmonised variables agree between the two sources",
    )
    _check(
        "zone" in set(used.field) and "geography" not in set(used.field),
        PAGE,
        "the harmonised model uses no field for the road's owner",
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
    body += "<h2>Tested on DGT records outside Catalonia</h2>"
    body += (
        "<p>DGT's records of crashes outside Catalonia are kept separately from the Catalan "
        "file, so they give a test on a source the model has never seen. The test uses the "
        "harmonised Catalonia model: the project's original Catalan model restricted to the "
        f"{_count(len(used))} variables both sources record in the same way, none of them the "
        "road's owner, and trained on the Catalan file alone. The outcome means the same in "
        "both: the Catalan file's fatal crashes match DGT's crashes with a death within 24 "
        "hours in every province and year both cover "
        '(<a href="catalonia.html#dgt-agreement">Catalonia</a>).</p>'
    )
    body += (
        "<p>On these crashes the Catalonia-trained model has a ROC-AUC of "
        f"{national.roc_auc:.3f} (95% interval {national.roc_auc_low:.3f}–"
        f"{national.roc_auc_high:.3f}), against {national.in_domain_cv_roc_auc:.3f} for a model "
        "of the same kind trained on DGT's records outside Catalonia, a difference of "
        f"{_signed(national.transfer_gap, 3)}. Its probabilities are close to calibrated. Fatal "
        f"crashes are commoner in the test ({_fmt_pct(national.test_prevalence)}) than in the "
        f"Catalan training records ({_fmt_pct(national.train_prevalence)}); the model's mean "
        f"prediction, {_fmt_pct(national.mean_predicted)}, falls between the two, and its "
        f"calibration slope is {national.calibration_slope:.2f}"
        + (
            ", a little less extreme than the outcomes warrant.</p>"
            if national.calibration_slope > 1
            else ", a little more extreme than the outcomes warrant.</p>"
        )
    )
    harmonised = reported[reported.model == "catalonia_common_dgt"]
    body += figure(
        "tr2_dgt_transfer",
        "Dot chart of the harmonised Catalonia model's ROC-AUC, with 95% intervals, on a later "
        "Catalan year, each province left out, the same crashes from both sources, a year "
        "only DGT records, and DGT crashes elsewhere in Spain, each beside a model trained in "
        f"the test population. The scores lie between {harmonised.roc_auc.min():.2f} and "
        f"{harmonised.roc_auc.max():.2f}.",
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
    body += figure(
        "tr3_province_auc",
        f"Dot chart of the harmonised Catalonia model's ROC-AUC in each of the "
        f"{len(shown_provinces)} provinces outside Catalonia with enough fatal and non-fatal "
        f"crashes, from {worst.roc_auc:.2f} to {best.roc_auc:.2f}.",
        captions,
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

    # ------------------------------------------------------------------ the original model
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
    owner = importance[
        importance.model.eq("catalonia_crash_severity")
        & importance.feature_set.eq(primary.loc["catalonia_crash_severity", "feature_set"])
    ].sort_values("auc_drop_mean", ascending=False)
    _check(
        not owner.empty and owner.feature.iloc[0] == "D_TITULARITAT_VIA",
        PAGE,
        "the original model's strongest predictor is the road's owner",
    )
    lowest = cat_provinces.loc[cat_provinces.roc_auc.idxmin()]
    highest = cat_provinces.loc[cat_provinces.roc_auc.idxmax()]
    gap_behind = behind.iloc[0]
    body += "<h2>The original Catalan model, tested within Catalonia</h2>"
    body += (
        "<p>Before the calculator, the project's Catalan model was gradient-boosted trees on the "
        "file's circumstance fields. Its strongest predictor was the road's owner, a field that "
        "turned out to record how a crash was documented rather than the road: a blank owner is "
        "far commoner on fatal records. That model was retired, and its tests are kept here as a "
        f"record ({REVIEW}). Their scores include whatever the artefact contributed. For these "
        "tests the model is used without its province variable, so that a province left out of "
        f"training is new to it. On the last year of the Catalan file ({later_year_label}), "
        f"held back from training and from every choice of settings, it scores "
        f"{later_year.roc_auc:.2f}, against {later_year.in_domain_cv_roc_auc:.2f} for a model "
        f"trained and cross-validated on the {_fmt_int(later_year.test_n)} crashes of that year "
        f"alone. With each of the {_count(len(cat_provinces))} provinces left out of training in "
        f"turn, it scores between {lowest.roc_auc:.2f} ({lowest['name']}) and "
        f"{highest.roc_auc:.2f} ({highest['name']}) on the province it did not see. That is "
        f"better than the province's own model in {_join(list(ahead.name))}, whose own records "
        f"are few, and {_fmt_dec(-gap_behind.transfer_gap, 2)} below it in the province of "
        "Barcelona, which holds most of the crashes.</p>"
    )
    catalan_tests = reported[reported.model == "catalonia_crash_severity"]
    _check(
        bool((catalan_tests.roc_auc_low.fillna(catalan_tests.roc_auc) > 0.5).all()),
        PAGE,
        "every test of the original model lies above chance",
    )
    body += figure(
        "tr1_catalonia_transfer",
        "Dot chart of the original Catalonia model's ROC-AUC, with 95% intervals, on records it "
        "was not trained on (a later year, each province left out and Barcelona city), each "
        "beside a model of the same kind trained in the test population. Every tested score lies "
        "above the chance level of 0.5.",
        captions,
    )

    # ------------------------------------------------------------------ Barcelona
    _check(
        to_bcn.roc_auc < cat_provinces.roc_auc.min(),
        PAGE,
        "Barcelona city is the hardest test inside Catalonia",
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
    moving = shown_components.loc["transport cost"]
    _check(
        abs(to_bcn.transfer_gap + main.transport_cost) < 1e-6
        and abs(moving.value - main.transport_cost) < 1e-6
        and not main.transport_cost_excludes_zero
        and abs(to_bcn.transfer_gap) < tolerance,
        PAGE,
        "the Barcelona difference is the net cost of using a model trained elsewhere, and it "
        "cannot be told from zero",
    )
    size = shown_components.loc["training-size cost"]
    urban = shown_components.loc["intrinsic difference against urban crashes"]
    _check(
        size.low > 0 and urban.high < 0 < shown_components.loc["intrinsic difference", "low"],
        PAGE,
        "Barcelona's crashes are harder to rank than the rest of Catalonia's mix, not harder "
        "than its urban crashes, and fewer are available to train on",
    )
    _check(
        bcn_records.status != "reported"
        and min(bcn_records.test_positives, bcn_records.test_n - bcn_records.test_positives)
        < minimum,
        PAGE,
        "Barcelona's own records have too few fatal crashes for a ranking test",
    )
    within_city = test_row(
        "rest of Catalonia -> Barcelona municipality (Barcelona-common", "catalonia_common_bcn"
    )
    _check(
        bcn_records.mean_predicted > bcn_records.observed_high
        and bcn_records.observed_high < later_bcn.test_prevalence
        and bcn_records.observed_high < within_city.test_prevalence,
        PAGE,
        "the Guàrdia Urbana records' fatal share is below the city's share in the Catalan file, "
        "and the model's estimate above that share's interval",
    )
    body += "<h2>The original model on Barcelona city</h2>"
    body += (
        "<p>Barcelona city is the hardest test inside Catalonia. Trained on the rest of "
        f"Catalonia, the original model ranks the city's crashes at {to_bcn.roc_auc:.3f}, against "
        f"{to_bcn.in_domain_cv_roc_auc:.3f} for a model trained in Barcelona: a difference of "
        f"{_signed(to_bcn.transfer_gap, 3)} (95% interval "
        f"{_interval(-moving.high, -moving.low, 3)}), too small to separate from zero. Both "
        f"scores are well below the {rest_reference:.3f} that a model reaches when trained and "
        "tested in the rest of Catalonia. That fall comes from the kind of crashes and the "
        "number available to train on: at the same training size, "
        "Barcelona's crashes are harder to rank than the rest of Catalonia's mix of interurban "
        "and urban crashes, but not harder than its urban crashes (difference "
        f"{_signed(urban.value, 3)}, 95% interval {_interval(urban.low, urban.high, 3)}).</p>"
    )
    body += (
        "<p>The ranking carries over to the city, but the probabilities do not: the "
        f"calibration slope there is {to_bcn.calibration_slope:.2f}, far from 1, so in "
        "Barcelona the model's scores order crashes without estimating their fatal share. The "
        f"Guàrdia Urbana's own records for {bcn_records_year}, a second source for the city, "
        f"hold {_fmt_int(bcn_records.test_n)} crashes defined compatibly with the Catalan file, "
        f"only {_fmt_int(bcn_records.test_positives)} of them fatal: too few for a ranking test. "
        f"Their fatal share, {_fmt_pct(bcn_records.test_prevalence)} (95% interval "
        f"{_fmt_dec(100 * bcn_records.observed_low, 1)}–{_fmt_pct(bcn_records.observed_high)}), "
        "is below the city's share in the Catalan file "
        f"({_fmt_pct(within_city.test_prevalence)} over {catalan_period}, "
        f"{_fmt_pct(later_bcn.test_prevalence)} over {_years(later_bcn.test_domain)}). The "
        "Catalonia model restricted to Barcelona's variables, whose estimate for the city in the "
        f"Catalan file is close ({_fmt_pct(within_city.mean_predicted)}), predicts "
        f"{_fmt_pct(bcn_records.mean_predicted)} for these crashes. The comparison mixes a "
        "change of year and of recording source with any error of the model, so it is weak "
        "evidence about transfer.</p>"
    )
    _check(
        abs(within_city.mean_predicted - within_city.test_prevalence)
        <= modelling.CALIBRATION_LARGE_TOLERANCE * within_city.test_prevalence,
        PAGE,
        "within the Catalan file the restricted model's estimate for the city is close",
    )
    _check(
        districts.transfer_gap >= -tolerance and districts.roc_auc_low > 0.5,
        PAGE,
        "the person-severity model keeps its ranking across Barcelona's districts",
    )
    body += (
        f"<p>Within the city, the {MODELS['barcelona_person_severity']} keeps its ranking when "
        f"each of the {_count(int(districts.districts))} districts is left out of training in "
        f"turn: {districts.roc_auc:.3f} on the district it did not see, against "
        f"{district_reference.roc_auc:.3f} in ordinary cross-validation on the same records. "
        "The model is kept for research only. It uses the crash type as recorded, including a "
        "term the Guàrdia Urbana uses almost only for serious crashes "
        '(<a href="barcelona.html#serious-injury-by-type-of-crash">Barcelona</a>), so part of '
        "its ranking may come from how serious crashes are coded.</p>"
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
    per_resident = _per_resident(rates)
    cat_rate, spain_rate = per_resident[True], per_resident[False]
    _check(
        cat_rate.injury_crashes > 1.5 * spain_rate.injury_crashes
        and abs(cat_rate.severe_crashes / spain_rate.severe_crashes - 1) < 0.2,
        PAGE,
        "Catalonia records far more injury crashes per resident but about as many severe ones",
    )

    def largest(variable: str) -> str:
        part = serious[
            serious.comparison.eq("Catalonia vs Spain outside Catalonia")
            & serious.variable.eq(variable)
        ]
        return part.loc[part.difference.abs().idxmax(), "level"]

    conventional = level("road_class", "conventional")
    run_off = level("crash_type", "run-off-road")
    unknown = level("alignment_recorded", "unknown")
    _check(
        abs(conventional.difference) < 0.05 and cat_mix["road_class"] <= resemblance,
        PAGE,
        "with every conventional road in one group, road type barely differs",
    )
    _check(
        largest("crash_type") == "run-off-road" and run_off.difference < 0,
        PAGE,
        "run-off-road crashes carry the largest difference in crash type",
    )
    _check(
        unknown.share_a > unknown.share_b
        and weather_blank.share_b > weather_blank.share_a
        and weather_blank.share_a < 0.005
        and surface_blank.share_b > surface_blank.share_a
        and cat_mix.index[0] == "alignment_recorded",
        PAGE,
        "'unknown' alignment is commoner in Catalonia and leads the differences; weather and "
        "surface are left unspecified more often elsewhere, weather almost never in Catalonia",
    )
    coding = read_table("gen_coding_by_region")
    cat_coding = coding[coding.region.eq("Catalonia")].set_index("year")
    switch = int(cat_coding[cat_coding.road_type_5_dual_carriageway.eq(0)].index.min())
    _check(
        bool(
            (
                cat_coding.loc[: switch - 1].road_type_6_single_carriageway
                < 0.01 * cat_coding.loc[: switch - 1].road_type_5_dual_carriageway
            ).all()
        ),
        PAGE,
        "DGT's Catalan records use the dual-carriageway code for conventional roads until the "
        "switch",
    )
    bcn_mix = divergences("Barcelona city vs Spain outside Catalonia")
    bcn_material = bcn_mix[bcn_mix > resemblance]
    _check(
        len(bcn_material) > len(material) and bcn_mix.iloc[0] > 2 * cat_mix.iloc[0],
        PAGE,
        "Barcelona's serious crashes differ from Spain's far more than Catalonia's do",
    )
    body += "<h2>How the crash populations differ</h2>"
    body += (
        "<p>A model can rank well in a population whose crashes look quite different from its "
        "own, so a successful transfer says nothing about how alike the populations are. DGT's "
        f"records for {dgt_period} compare them on the same fields and the same outcome "
        "definitions, although each police force fills the fields in its own way. A death or "
        "serious injury occurs in a smaller share of injury crashes in Catalonia than elsewhere "
        f"in Spain ({_fmt_pct(cat['serious'][0])} against {_fmt_pct(spain['serious'][0])}), and "
        f"fewer of those crashes are fatal within 24 hours ({_fmt_pct(cat['fatal_24h'][0])} "
        f"against {_fmt_pct(spain['fatal_24h'][0])}). Barcelona city lies further from the "
        f"national pattern, at {_fmt_pct(bcn['serious'][0])} and {_fmt_pct(bcn['fatal_24h'][0])}. "
        "The lower severe share comes from the denominator: per 100,000 residents a year, "
        f"Catalonia's records hold {_fmt_dec(cat_rate.injury_crashes, 0)} injury crashes against "
        f"{_fmt_dec(spain_rate.injury_crashes, 0)} elsewhere, but about as many crashes with a "
        f"death or serious injury ({_fmt_dec(cat_rate.severe_crashes)} against "
        f"{_fmt_dec(spain_rate.severe_crashes)}). How completely each force records "
        "slight-injury crashes is part of that difference, and these data cannot separate it "
        'from real differences (<a href="data.html#rates">how often crashes happen and how '
        "deadly they are</a>).</p>"
    )
    body += (
        "<p>Among crashes with a death or serious injury, "
        f"{_count(len(material))} of the {_count(len(cat_mix))} variables compared differ by more "
        f"than a limit set in advance: {_variables(material.index)}. The largest gaps are in "
        "how crashes are recorded. DGT's code for an unknown road alignment covers "
        f"{_fmt_pct(unknown.share_a)} of these crashes in Catalonia and "
        f"{_fmt_pct(unknown.share_b)} elsewhere, and weather is unspecified in "
        f"{_fmt_pct(weather_blank.share_b)} outside Catalonia but almost never inside it. Fewer "
        f"Catalan crashes are run-off-road crashes ({_fmt_pct(run_off.share_a)} against "
        f"{_fmt_pct(run_off.share_b)}), and crash types too are coded by different police "
        "forces. Road type does not differ beyond the limit: conventional roads hold "
        f"{_fmt_pct(conventional.share_a)} of these crashes in Catalonia and "
        f"{_fmt_pct(conventional.share_b)} elsewhere, counting every conventional road together, "
        f"because DGT's records for Catalonia code them as dual carriageways until "
        f"{switch - 1} and as single carriageways from {switch} "
        '(<a href="data.html#coding-breaks">coding breaks</a>). Barcelona city\'s serious and '
        "fatal crashes differ from Spain's far more, on "
        f"{_count(len(bcn_material))} variables, led by {_variables(bcn_material.index[:3])}.</p>"
    )

    # ------------------------------------------------------------------ scope
    status = path.set_index(["model", "stage"]).status
    calc = transport_rules.CALCULATOR
    _check(
        status[("catalonia_common_dgt", 4)] == "passed"
        and status[(calc, 4)] != "passed"
        and status[(calc, 2)] == "passed"
        and status[(calc, 3)] == "passed"
        and status[("catalonia_crash_severity", 4)] != "passed"
        and status[("barcelona_person_severity", 4)] != "passed"
        and status[("barcelona_person_severity", 2)] == "passed"
        and status[("barcelona_person_severity", 3)] == "passed",
        PAGE,
        "only the harmonised model has an independent Spanish test; the calculator's model is "
        "validated on later years and places within Catalonia, the Barcelona models across "
        "months and districts",
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
    body += "<h2>What the tests support</h2>"
    body += (
        "<p>The tests support ranking serious and fatal crashes in Catalonia with the "
        "calculator's model, on later years and in places left out of its fitting, better than "
        "the table of fatal shares by road and crash type. Its estimates held on later years "
        "but not when the province or the city of Barcelona was left out. A version of the "
        "original Catalan model restricted to the variables DGT records alike ranks serious "
        "crashes elsewhere in Spain about as well as a model trained there, losing only "
        f"{_fmt_dec(-national.transfer_gap, 3)} of ROC-AUC; it is not the published model. The "
        f"calculator's model, the original model and the {MODELS['barcelona_person_severity']} "
        "use variables or records that no second source holds, so they are tested only within "
        "their own files. Catalonia's serious crashes differ materially from Spain's on "
        f"{_count(len(material))} of the {_count(len(cat_mix))} variables compared. No model has "
        "been shown to be fit for use across Spain, so national use of the models is not "
        "established.</p>"
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
            _check("too few" in row.evidence, PAGE, "an untestable test had too few cases")
        return cells[row.status]

    not_testable = path[path.status.eq("not testable")]
    _check(
        list(not_testable.model) == ["catalonia_common_bcn"],
        PAGE,
        "only the test on Barcelona's own records had too few cases",
    )
    body += technical(
        "Tests passed by each model",
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
        f"{tolerance:g} below it. The last column is “yes” only if no variable's distribution "
        "differs from Spain's by more than a Jensen–Shannon divergence of "
        f"{resemblance:g}, a measure that is 0 for identical distributions. Both limits were "
        "set before any result was "
        "read. “Not run”: no second source holds the model's variables or the crashes it would "
        f"need. “Too few cases”: Barcelona's own records for {bcn_records_year} hold "
        f"{_fmt_int(bcn_records.test_positives)} fatal crashes. The test that trains the "
        "original model's specification on Barcelona city's crashes alone and scores the rest "
        "of Catalonia tests a model of the city, not the Catalonia model, so no column counts "
        f"it; it falls {_fmt_dec(-from_bcn.transfer_gap, 2)} short of its reference (detailed "
        "results below).</p>",
    )

    # ------------------------------------------------------------------ all tests
    held_out_calculator = calculator[~calculator.experiment.str.startswith("random")]
    shown = pd.concat(
        [
            held_out_calculator,
            reported[
                reported.in_domain_cv_roc_auc.notna()
                & reported.model.ne("barcelona_crash_severity")
            ],
        ],
        ignore_index=True,
    ).drop_duplicates(["model", "experiment"])
    shown = shown.assign(
        _order=shown.model.map({m: i for i, m in enumerate(model_order)})
    ).sort_values("_order", kind="stable")
    # The original model is tested without its province variable, so that a province left out
    # is new to it.
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
        "the external tests use the original model without its province variable",
    )
    body += technical(
        "Detailed results of every external test",
        table(
            pd.DataFrame(
                {
                    "Test": [_test_label(r) for r in shown.itertuples()],
                    "Model": [_table_model(r) for r in shown.itertuples()],
                    "Training records": [_fmt_int(v) for v in shown.train_n],
                    "Test records": [_fmt_int(v) for v in shown.test_n],
                    "Outcome cases": [_fmt_int(v) for v in shown.test_positives],
                    "Model tested": [_fmt_dec(v, 3) for v in shown.roc_auc],
                    "Trained in test population": [
                        _fmt_dec(v, 3) for v in shown.in_domain_cv_roc_auc
                    ],
                    "Difference": ["" if pd.isna(v) else _signed(v, 3) for v in shown.transfer_gap],
                    "Calibration slope": [_fmt_dec(v, 2) for v in shown.calibration_slope],
                }
            ),
            "ROC-AUC of each model on records it was not trained on, beside a model of the same "
            "kind trained and cross-validated in the test population (difference: model tested "
            "minus that reference). Outcome cases are fatal crashes for the Catalan models and "
            "serious or fatal injuries for the Barcelona person-severity model. The calculator's "
            "model is a penalised logistic regression; each of the other models uses the "
            "method, logistic regression or gradient-boosted trees, chosen on its own "
            "validation data. The original model is tested without its province variable, the "
            "calculator's model without its province intercepts when a province is left out. "
            "The test of each year from the years before it has no single test population to "
            "train a reference in; its training records vary by year.",
        )
        + f'<p>The <a href="{DOCS_URL}/GENERALISABILITY.md">generalisability report</a> lists '
        "every test with its training and test periods, for both logistic regression and "
        "gradient-boosted trees, and the calculator's tests beside the table of fatal shares by "
        "road and crash type.</p>",
    )
    body += downloads(
        [
            ("gen_calculator_transfer", "calculator's model"),
            ("ml_transport_validation", "external tests"),
            ("ml_outward_path", "tests passed by each model"),
            ("ml_barcelona_diagnosis", "Barcelona scores"),
            ("ml_barcelona_diagnosis_components", "parts of the Barcelona fall"),
            ("ml_domain_strategies", "pooled models"),
            ("ml_transport_provinces", "provinces"),
            ("ml_domain_shift", "variable distributions"),
            ("ml_common_feature_validation", "variable mapping"),
            ("dgt_audit_transfer", "national test checks"),
            ("gen_representativeness", "variable mixes"),
            ("gen_outcomes", "outcome shares"),
            ("gen_province_rates", "crashes per resident"),
            ("gen_coding_by_region", "road-type and junction codes by region"),
            ("gen_cross_source_register", "source comparison"),
        ],
        method=("data.html#models", "how the models were built and judged"),
    )
    return render_page(
        PAGE,
        "External validation of the severity models",
        "Whether the severity models still rank crashes well when they are applied to a later "
        "year, to places left out of training and to another source's records.",
        body,
    )
