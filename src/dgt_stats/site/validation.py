"""External validation of the severity models: how well they rank crashes from years, places and
data sources they were not fitted on, and how the crash populations compare.

The page leads with the tests of the published model, the Catalan severity model behind the
calculator. The tests of the original Catalan model, which it replaced, follow under that name:
first its harmonised version on DGT's records elsewhere in Spain, the only test on another source,
then the original model within Catalonia and Barcelona city. Ranking skill is given as ROC-AUC to
two decimals, defined once in plain words, as on the Severity model page.
"""

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
# The models as the validation tables name them, as table rows. The Catalan severity model (the
# calculator's) is the one the site publishes. The original Catalan model was retired because its
# strongest predictor, the road's owner, records how a crash was documented; its tests, and those
# of its versions restricted to the variables another source records alike, are kept as a record.
# The Barcelona crash-severity model was replaced by its table of shares by accident type.
MODELS = {
    transport_rules.CALCULATOR: "Catalan severity model",
    "catalonia_crash_severity": "Original Catalan model (retired)",
    "catalonia_common_dgt": "Original model, harmonised with DGT's records",
    "catalonia_common_bcn": "Original model, restricted to Barcelona's variables",
    "barcelona_person_severity": "Barcelona person-severity model",
    "barcelona_crash_severity": "Barcelona crash-severity model (replaced by a table)",
}
# The kinds of test, from the records closest to the fitting data to the comparison with Spain.
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
# A value the tests do not give is left blank, and the table note says why.
NOT_RECORDED = ""
# A province's observed fatal share counts as far from the mean estimate beyond this gap.
PROVINCE_GAP = 0.03


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
            r"rolling origin.*every choice nested",
            lambda m: (
                f"Each year {_years(row.test_domain)} from the years before it, every setting "
                "chosen on earlier years"
            ),
        ),
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
                "Spain outside Catalonia, fitting reweighted to the national mix of zone "
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
    """The model column of the detailed table: which model, and how it was fitted."""
    if row.model == "catalonia_crash_severity":
        if row.experiment.startswith("Barcelona municipality -> rest"):
            return "Original model's specification, fitted on Barcelona city only"
        return _model(row.model) + ", without province"
    return _model(row.model)


def _auc(value: float) -> str:
    """A ROC-AUC, or a difference of two, to two decimals: the one scale on this page and the
    Severity model page. A difference that rounds to zero carries no sign."""
    return _fmt_dec(value, 2)


def _signed(value: float) -> str:
    """A difference with its sign, to two decimals: +0.05, −0.04, 0.00."""
    text = _auc(value)
    return "+" + text if round(float(value), 2) > 0 else text


def _interval(low: float, high: float) -> str:
    """'0.73–0.75' when neither end carries a sign, '−0.05 to 0.02' when one does."""
    first, second = _auc(low), _auc(high)
    return f"{first} to {second}" if MINUS in first + second else f"{first}–{second}"


def _with_interval(value: float, low: float, high: float) -> str:
    """A ROC-AUC with its 95% interval where the table has one: '0.74 (0.73–0.75)'."""
    if pd.isna(value):
        return NOT_RECORDED
    if pd.isna(low) or pd.isna(high):
        return _auc(value)
    return f"{_auc(value)} ({_interval(low, high)})"


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


def _outside(row) -> bool:
    """The mean estimate lies outside the 95% interval of the observed share."""
    return not float(row.observed_low) <= float(row.mean_predicted) <= float(row.observed_high)


def _left_out_provinces(calculator: pd.DataFrame) -> pd.DataFrame:
    """The Catalan severity model's tests with one province left out, named by province."""
    provinces = calculator[calculator.experiment.str.match(r"leave out \w+ demarcation$")]
    return provinces.assign(
        name=provinces.experiment.str.extract(r"leave out (\w+) demarcation")[0]
    ).set_index("name")


def _direction(row) -> str:
    return "too high" if float(row.mean_predicted) > float(row.observed_high) else "too low"


def _calculator_section(calculator: pd.DataFrame, rolling_scores: pd.DataFrame) -> str:
    """The published model's tests: later years, provinces and Barcelona city left out."""
    tolerance = generalisability.MAX_TRANSFER_GAP
    slope_low, slope_high = modelling.CALIBRATION_SLOPE_RANGE
    rows = calculator.set_index("experiment")

    def one(prefix: str) -> pd.Series:
        part = calculator[calculator.experiment.str.startswith(prefix)]
        _check(len(part) == 1, PAGE, f"one test of the Catalan severity model named {prefix!r}")
        return part.iloc[0]

    rolling = one("rolling origin")
    later = one("temporal holdout")
    later_label = re.search(r"test (\d{4})", later.experiment).group(1)
    city = one("rest of Catalonia -> Barcelona municipality")
    provinces = _left_out_provinces(calculator)
    held_out = pd.concat([provinces, city.to_frame().T])
    lowest_name = provinces.roc_auc.astype(float).idxmin()
    highest_name = provinces.roc_auc.astype(float).idxmax()
    missed = provinces[provinces.apply(_outside, axis=1)]
    matched = provinces[~provinces.apply(_outside, axis=1)]
    tolerance_band = modelling.CALIBRATION_LARGE_TOLERANCE
    cells = rolling_scores[
        rolling_scores.subset.str.startswith("province and zone: ")
        & rolling_scores.estimator.eq("calculator")
    ]
    cells = cells.assign(
        province=cells.subset.str.extract(r": (\w+)\|")[0],
        zone=cells.subset.str.extract(r"\|(\w+)$")[0],
    )
    cell_misses = cells[cells.apply(_outside, axis=1)]
    zone_words = {
        "urban": "urban streets",
        "through_town": "roads through towns",
        "interurban": "interurban roads",
    }

    def calibrated(row) -> bool:
        return (
            slope_low <= row.calibration_slope <= slope_high
            and abs(row.mean_predicted - row.test_prevalence)
            <= tolerance_band * row.test_prevalence
        )

    _check(
        bool((rows.roc_auc_low > 0.5).all()),
        PAGE,
        "every test of the Catalan severity model lies above chance",
    )
    _check(
        rolling.roc_auc > rolling.table_roc_auc
        and calibrated(rolling)
        and "every choice nested" in rolling.experiment,
        PAGE,
        "on later years, every choice nested, the Catalan severity model ranks above the table "
        "and its pooled estimates hold",
    )
    _check(
        later.transfer_gap > 0 and later.train_n > later.in_domain_train_n,
        PAGE,
        "on the last year the model beats the same model fitted on that year alone",
    )
    _check(
        bool((held_out.transfer_gap.astype(float) >= -tolerance).all())
        and bool((held_out.roc_auc.astype(float) > held_out.table_roc_auc.astype(float)).all()),
        PAGE,
        "in every place left out the Catalan severity model is within the limit of a model "
        "fitted there and ranks above the table",
    )
    _check(
        len(missed) >= 2 and not matched.empty,
        PAGE,
        "with a province left out, the estimates miss in more than one province, not in all",
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
    _check(
        not cell_misses.empty,
        PAGE,
        "even with province terms, some province's estimates by kind of road miss",
    )

    def share(row) -> str:
        return (
            f"{_fmt_pct(row.mean_predicted)} estimated against {_fmt_pct(row.test_prevalence)} "
            f"observed, {_fmt_pct(row.observed_low)} to {_fmt_pct(row.observed_high)}"
        )

    by_province = _join(
        [f"{_direction(row)} for {name} ({share(row)})" for name, row in missed.iterrows()]
    )
    inside = _join([f"for {name} ({share(row)})" for name, row in matched.iterrows()])
    cell_text = _join(
        [
            f"on {zone_words[row.zone]} in the province of {row.province} "
            f"{_fmt_pct(row.mean_predicted)} "
            f"estimated against {_fmt_pct(row.prevalence)} observed "
            f"({_fmt_pct(row.observed_low)} to {_fmt_pct(row.observed_high)})"
            for row in cell_misses.itertuples()
        ]
    )
    return (
        "<h2>The Catalan severity model: ranking holds, estimates of the fatal share miss in "
        "several provinces</h2>"
        "<p>Every test on this page scores crashes that played no part in fitting the model. "
        "Ranking is measured by the ROC-AUC: given one fatal and one non-fatal crash, the share "
        "of pairs in which the fatal one gets the higher estimate, from 0.5 for chance to 1 for "
        "a perfect ranking. Each score is set beside a reference, the same kind of model fitted "
        "and cross-validated within the test population, which shows how well that "
        "population's crashes can be ranked at all. A small test population gives a weak "
        "reference, which a model fitted elsewhere on many more crashes can beat.</p>"
        "<p>The Catalan severity model is the one behind the calculator "
        '(<a href="severity-models.html">Severity model and calculator</a>). It has been tested '
        "only within the Catalan file, on crashes on the roads a reader can choose. Each year "
        f"of {_years(rolling.test_domain)} was predicted by a model whose settings (penalty, "
        "form and the rule for roads through towns) were chosen on the two years before it and "
        "whose coefficients were fitted on all earlier years, so no choice saw the year it "
        f"predicts. Over the {_fmt_int(rolling.test_n)} crashes this gives a ROC-AUC of "
        f"{_auc(rolling.roc_auc)} (95% interval "
        f"{_interval(rolling.roc_auc_low, rolling.roc_auc_high)}), against "
        f"{_auc(rolling.table_roc_auc)} for a table of fatal shares by road and crash type, "
        f"and a mean estimate of {_fmt_pct(rolling.mean_predicted)} where "
        f"{_fmt_pct(rolling.test_prevalence)} were fatal. On {later_label} alone it scores "
        f"{_auc(later.roc_auc)}, against {_auc(later.in_domain_cv_roc_auc)} for the same model "
        f"fitted and cross-validated on that year's {_fmt_int(later.test_n)} crashes. By "
        "province and kind of road the estimates were less close, even with each province's "
        f"own terms fitted on earlier years: {cell_text}.</p>"
        "<p>With each province left out of the fitting in turn, and the settings chosen on the "
        f"other three, it scores between {_auc(provinces.loc[lowest_name].roc_auc)} "
        f"({lowest_name}) and {_auc(provinces.loc[highest_name].roc_auc)} ({highest_name}) on "
        f"the province it did not see: in every province within {tolerance:g} of the same "
        "model fitted there, and above the table. Its estimates of the fatal share carry over "
        f"less well. They were {by_province}; only {inside} did the estimate lie inside the "
        "observed interval. Fitted on the rest of Catalonia, it "
        f"ranks Barcelona city's crashes at {_auc(city.roc_auc)}, against "
        f"{_auc(city.in_domain_cv_roc_auc)} for the same model fitted in the city, but it "
        f"estimates a fatal share of {_fmt_pct(city.mean_predicted)} where "
        f"{_fmt_pct(city.test_prevalence)} were fatal. Once the city's earlier crashes are in the "
        f"fitting, its estimates for the city's streets are close "
        f"({_fmt_pct(in_city.mean_predicted)} against {_fmt_pct(in_city.prevalence)}).</p>"
        "<p>No other source records its inputs: DGT's national records have no field for the "
        "road's owning network or the posted limit, and their road-type and junction codings "
        "disagree with the Catalan file's on the crashes both hold. The Catalan severity model "
        "therefore has no test outside Catalonia. The tests that follow are of other models.</p>"
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
    decisions = read_table("ml_model_decisions").set_index(["model", "variant"])
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
        "the Catalonia-fitted model ranks Spanish crashes about as well as a model fitted there",
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
        "no fitting population resembles Spain's, so national use is not established",
    )
    used = mapping[mapping.enters_cross_source_tests]
    left_out = _left_out_provinces(calculator)
    missed_provinces = list(left_out[left_out.apply(_outside, axis=1)].index)
    body = summary(
        "The Catalan severity model, the one behind the calculator, has been tested only within "
        "Catalonia: no other source records its inputs. On later years and on provinces left "
        "out of its fitting it ranked crashes better than a table of fatal shares by road and "
        "crash type, but its estimates of the fatal share were off for "
        f"{_join(missed_provinces)} when each was left out of its fitting, and for the city of "
        "Barcelona. A harmonised version of the original Catalan model (retired) "
        "ranked crashes elsewhere in Spain about as well as a model fitted there. Because "
        "Catalonia's serious crashes differ from the rest of Spain's in the mix of crash types "
        "and in how several fields are recorded, national use of the models is not established."
    )

    # ------------------------------------------------------------------ the published model
    body += _calculator_section(calculator, rolling_scores)
    body += figure(
        "tr0_calculator_transfer",
        "Dot chart of the Catalan severity model's ROC-AUC, with 95% intervals, on later years, "
        "each province left out and Barcelona city, each beside the same model fitted in the "
        f"test population; the scores lie between {_auc(calculator.roc_auc.min())} and "
        f"{_auc(calculator.roc_auc.max())}.",
        captions,
        title="The Catalan severity model on held-out years and places",
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
    _check(
        str(decisions.loc[("catalonia_common_dgt", "common"), "usefulness"]).startswith(
            "measures transfer"
        ),
        PAGE,
        "the harmonised version is a test instrument, not a model to rank crashes with",
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
        "the national mean prediction lies between the fitting and test fatal shares",
    )
    for row in (early, reweighted):
        _check(
            abs(row.roc_auc - national.roc_auc) < 0.01,
            PAGE,
            "the national result is unchanged by earlier fitting years or reweighting",
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

    shown_provinces = provinces[provinces.reported].assign(
        gap=lambda d: d.prevalence - d.mean_predicted
    )
    off_provinces = shown_provinces[shown_provinces.gap.abs() > PROVINCE_GAP]
    under = off_provinces.gap > 0
    _check(
        len(off_provinces) > len(shown_provinces) / 3,
        PAGE,
        "province by province the harmonised model's estimates often miss by more than the gap",
    )
    weather_blank = level("weather", "not specified")
    surface_blank = level("surface", "not specified")
    same_score = _auc(national.roc_auc) == _auc(national.in_domain_cv_roc_auc)
    body += "<h2>Spain outside Catalonia: a version of the original model holds its ranking</h2>"
    body += (
        "<p>DGT's records of crashes outside Catalonia are kept separately from the Catalan "
        "file, so they give a test on a source no Catalan model has seen. The model tested is "
        "the harmonised version of the original Catalan model (retired): the same method "
        f"restricted to the {_count(len(used))} variables both sources record in the same way, "
        "none of them the road's owner, and fitted on the Catalan file alone. It serves only to "
        "measure transfer; it is not the published model. The outcome means the same in both "
        "sources: the Catalan file's fatal crashes match DGT's crashes with a death within 24 "
        "hours in every province and year both cover "
        '(<a href="catalonia.html#dgt-agreement">Catalonia</a>).</p>'
    )
    body += (
        f"<p>On the {_fmt_int(national.test_n)} crashes with a death or serious injury that DGT "
        "recorded elsewhere in Spain, the harmonised version has a ROC-AUC of "
        f"{_auc(national.roc_auc)} (95% interval "
        f"{_interval(national.roc_auc_low, national.roc_auc_high)}), "
        + (
            "the same to two decimals as "
            if same_score
            else f"against {_auc(national.in_domain_cv_roc_auc)} for "
        )
        + "a model of the same kind fitted on DGT's records outside Catalonia. Taken "
        "together, its estimates are close to calibrated, but not province by province: in "
        f"{_count(len(off_provinces))} of the {_count(len(shown_provinces))} provinces shown "
        "below, the observed fatal share differs from the mean estimate by more than "
        f"{_fmt_dec(100 * PROVINCE_GAP, 0)} percentage points ({_count(int(under.sum()))} "
        f"higher, {_count(int((~under).sum()))} lower; largest gap "
        f"{_fmt_dec(100 * float(off_provinces.gap.abs().max()), 1)} points). Fatal crashes are "
        "commoner in the test "
        f"({_fmt_pct(national.test_prevalence)}) than in the Catalan records it was fitted on "
        f"({_fmt_pct(national.train_prevalence)}); its mean estimate, "
        f"{_fmt_pct(national.mean_predicted)}, falls between the two. Its calibration slope, 1 "
        "when the estimates spread as widely as the outcomes, is "
        f"{_fmt_dec(national.calibration_slope, 2)}"
        + (
            ": the estimates are a little less extreme than the outcomes warrant.</p>"
            if national.calibration_slope > 1
            else ": the estimates are a little more extreme than the outcomes warrant.</p>"
        )
    )
    harmonised = reported[reported.model == "catalonia_common_dgt"]
    body += figure(
        "tr2_dgt_transfer",
        "Dot chart of the harmonised version of the original model's ROC-AUC, with 95% "
        "intervals, on a later Catalan year, each province left out, the same crashes from both "
        "sources, a year only DGT records, and DGT crashes elsewhere in Spain, each beside a "
        "model fitted in the test population. The scores lie between "
        f"{_auc(harmonised.roc_auc.min())} and {_auc(harmonised.roc_auc.max())}.",
        captions,
        title="Harmonised version of the original model on other sources, years and Spain",
    )
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
        f"{minimum} non-fatal crashes, the ROC-AUC runs from {_auc(worst.roc_auc)} "
        f"({names[worst.province_code]}) to {_auc(best.roc_auc)} "
        f"({names[best.province_code]}), with a median of "
        f"{_auc(shown_provinces.roc_auc.median())}. These scores have no intervals, and the "
        f"smallest provinces hold only {_fmt_int(shown_provinces.positives.min())} fatal "
        "crashes, so the order of provinces with similar scores means little.</p>"
    )
    body += figure(
        "tr3_province_auc",
        "Dot chart of the harmonised version of the original model's ROC-AUC in each of the "
        f"{len(shown_provinces)} provinces outside Catalonia with enough fatal and non-fatal "
        f"crashes, from {_auc(worst.roc_auc)} to {_auc(best.roc_auc)}.",
        captions,
        title="Harmonised version of the original model, province by province outside Catalonia",
    )
    _check(
        weather_blank.share_b > 0,
        PAGE,
        "weather is sometimes unspecified in DGT's records outside Catalonia",
    )
    body += technical(
        "Variables of the harmonised version",
        f"<p>The {_count(len(used))} variables are {_variables(used.field)}. "
        f"{_variables(disagree.field).capitalize()} were left out because their codings "
        "disagree on the crashes both sources hold, and "
        f"{_join(['the ' + _variable(v) for v in unusable.field])} are not available in a "
        "comparable form. Averaged over the variables used, values recorded as not specified "
        f"make up at most {_fmt_pct(max(missing) / 100)} of any source's records, although "
        f"weather is unspecified in {_fmt_pct(weather_blank.share_b)} of serious and fatal "
        "crashes outside Catalonia.</p>",
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
    body += "<h2>Catalonia's serious crashes differ from Spain's in type and in recording</h2>"
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
        "the later-year model beats a model fitted on that year alone",
    )
    _check(
        chosen_estimator["catalonia_crash_severity"] == "boosted_trees",
        PAGE,
        "the original model is gradient-boosted trees",
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
    body += "<h2>The original Catalan model (retired), tested within Catalonia</h2>"
    body += (
        "<p>Before the Catalan severity model, the project's Catalan model was gradient-boosted "
        "trees on the file's circumstance fields. Its strongest predictor was the road's owner, "
        "a field that turned out to record how a crash was documented rather than the road: a "
        "blank owner is far commoner on fatal records. That model was retired, and its tests "
        f"are kept here as a record ({REVIEW}); their scores include whatever the artefact "
        "contributed. For these tests the model is used without its province variable, so that "
        "a province left out of fitting is new to it. On the last year of the Catalan file "
        f"({later_year_label}), held back from fitting and from every choice of settings, it "
        f"scores {_auc(later_year.roc_auc)}, against {_auc(later_year.in_domain_cv_roc_auc)} for "
        "a model fitted and cross-validated on the "
        f"{_fmt_int(later_year.test_n)} crashes of that year alone. With each of the "
        f"{_count(len(cat_provinces))} provinces left out of fitting in turn, it scores between "
        f"{_auc(lowest.roc_auc)} ({lowest['name']}) and {_auc(highest.roc_auc)} "
        f"({highest['name']}) on the province it did not see. That is better than the "
        f"province's own model in {_join(list(ahead.name))}, whose own records are few, and "
        f"{_auc(-gap_behind.transfer_gap)} below it in the province of Barcelona, which holds "
        "most of the crashes.</p>"
    )
    catalan_tests = reported[reported.model == "catalonia_crash_severity"]
    _check(
        bool((catalan_tests.roc_auc_low.fillna(catalan_tests.roc_auc) > 0.5).all()),
        PAGE,
        "every test of the original model lies above chance",
    )
    body += figure(
        "tr1_catalonia_transfer",
        "Dot chart of the original Catalan model's ROC-AUC, with 95% intervals, on records it "
        "was not fitted on (a later year, each province left out and Barcelona city), each "
        "beside a model of the same kind fitted in the test population. Every tested score lies "
        "above the chance level of 0.5.",
        captions,
        title="Original Catalan model (retired) on held-out places and years",
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
        "a model fitted on Barcelona ranks the rest of Catalonia poorly",
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
        "the Barcelona difference is the net cost of using a model fitted elsewhere, and it "
        "cannot be told from zero",
    )
    size = shown_components.loc["training-size cost"]
    urban = shown_components.loc["intrinsic difference against urban crashes"]
    _check(
        size.low > 0 and urban.high < 0 < shown_components.loc["intrinsic difference", "low"],
        PAGE,
        "Barcelona's crashes are harder to rank than the rest of Catalonia's mix, not harder "
        "than its urban crashes, and fewer are available to fit on",
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
    _check(
        max(to_bcn.roc_auc, to_bcn.in_domain_cv_roc_auc) < rest_reference - tolerance,
        PAGE,
        "a model fitted in Barcelona city ranks its crashes well below the rest of Catalonia's",
    )
    body += (
        "<h2>Barcelona city: the original model's ranking carries over, its estimates do not</h2>"
    )
    body += (
        "<p>Barcelona city is the hardest test inside Catalonia. Fitted on the rest of "
        f"Catalonia, the original model ranks the city's crashes at {_auc(to_bcn.roc_auc)}, "
        f"against {_auc(to_bcn.in_domain_cv_roc_auc)} for a model fitted in Barcelona; the 95% "
        f"interval of the difference, {_interval(-moving.high, -moving.low)}, includes zero. "
        f"Both scores are well below the {_auc(rest_reference)} that a model reaches when "
        "fitted and tested in the rest of Catalonia. That fall comes from the kind of crashes "
        "and the number available to fit on: at the same fitting size, Barcelona's crashes are "
        "harder to rank than the rest of Catalonia's mix of interurban and urban crashes, but "
        f"not harder than its urban crashes (difference {_signed(urban.value)}, 95% interval "
        f"{_interval(urban.low, urban.high)}).</p>"
    )
    body += (
        "<p>The ranking carries over to the city, but the probabilities do not: the original "
        f"model's calibration slope there is {_fmt_dec(to_bcn.calibration_slope, 2)}, far from "
        "1, so in Barcelona its scores order crashes without estimating their fatal share. The "
        f"Guàrdia Urbana's own records for {bcn_records_year}, a second source for the city, "
        f"hold {_fmt_int(bcn_records.test_n)} crashes defined compatibly with the Catalan file, "
        f"only {_fmt_int(bcn_records.test_positives)} of them fatal: too few for a ranking test. "
        f"Their fatal share, {_fmt_pct(bcn_records.test_prevalence)} (95% interval "
        f"{_fmt_dec(100 * bcn_records.observed_low, 1)}–{_fmt_pct(bcn_records.observed_high)}), "
        "is below the city's share in the Catalan file "
        f"({_fmt_pct(within_city.test_prevalence)} over {catalan_period}, "
        f"{_fmt_pct(later_bcn.test_prevalence)} over {_years(later_bcn.test_domain)}). The "
        "original model restricted to Barcelona's variables, whose estimate for the city in the "
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
    district_scores = f"{_auc(districts.roc_auc)} on the district it did not see, " + (
        "the same to two decimals as in ordinary cross-validation on the same records"
        if _auc(districts.roc_auc) == _auc(district_reference.roc_auc)
        else f"against {_auc(district_reference.roc_auc)} in ordinary cross-validation on "
        "the same records"
    )
    body += (
        f"<p>Within the city, the {MODELS['barcelona_person_severity']} keeps its ranking when "
        f"each of the {_count(int(districts.districts))} districts is left out of fitting in "
        f"turn: {district_scores}. The model is kept for research only. It uses the crash type "
        "as recorded, including a term the Guàrdia Urbana uses almost only for serious crashes "
        '(<a href="barcelona.html#serious-injury-by-type-of-crash">Barcelona</a>), so part of '
        "its ranking may come from how serious crashes are coded.</p>"
    )

    # ------------------------------------------------------------------ every test, by model
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
        "only the harmonised model has an independent Spanish test; the Catalan severity model "
        "is validated on later years and places within Catalonia, the Barcelona models across "
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
        "the harmonised model scores slightly below the model fitted on the Spanish records",
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
    body += "<h2>No model has passed every kind of test</h2>"
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
            "Result of each kind of test, by model, from the records closest to the fitting "
            "data to the comparison of the fitting crashes with Spain's.",
        )
        + "<p>“Passed” means that the model ranks above chance with 95% confidence and, where a "
        "model fitted within the test population gives a reference, scores no more than "
        f"{tolerance:g} below it. The last column is “yes” only if no variable's distribution "
        "differs from Spain's by more than a Jensen–Shannon divergence of "
        f"{resemblance:g}, a measure that is 0 for identical distributions. Both limits were "
        "set before any result was "
        "read. “Not run”: no second source holds the model's variables or the crashes it would "
        f"need. “Too few cases”: Barcelona's own records for {bcn_records_year} hold "
        f"{_fmt_int(bcn_records.test_positives)} fatal crashes. The test that fits the "
        "original model's specification on Barcelona city's crashes alone and scores the rest "
        "of Catalonia tests a model of the city, not a Catalan model, so no column counts "
        f"it; it falls {_auc(-from_bcn.transfer_gap)} short of its reference (detailed "
        "results below).</p>",
    )

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
    unscored = shown[shown.roc_auc_low.isna()]
    _check(
        bool(unscored.experiment.str.startswith("temporal holdout").all())
        and bool(unscored.calibration_slope.isna().all())
        and not unscored.model.eq(calc).any(),
        PAGE,
        "only the original model's later-year tests, and its versions', lack an interval and a "
        "calibration slope",
    )
    body += technical(
        "Detailed results of every external test",
        table(
            pd.DataFrame(
                {
                    "Test": [_test_label(r) for r in shown.itertuples()],
                    "Model": [_table_model(r) for r in shown.itertuples()],
                    "Fitting records": [_fmt_int(v) for v in shown.train_n],
                    "Test records": [_fmt_int(v) for v in shown.test_n],
                    "Outcome cases": [_fmt_int(v) for v in shown.test_positives],
                    "Model tested (95% interval)": [
                        _with_interval(r.roc_auc, r.roc_auc_low, r.roc_auc_high)
                        for r in shown.itertuples()
                    ],
                    "Fitted in test population": [_auc(v) for v in shown.in_domain_cv_roc_auc],
                    "Difference": [
                        NOT_RECORDED if pd.isna(v) else _signed(v) for v in shown.transfer_gap
                    ],
                    "Calibration slope": [_fmt_dec(v, 2) for v in shown.calibration_slope],
                }
            ),
            "ROC-AUC of each model on records it was not fitted on, beside a model of the same "
            "kind fitted and cross-validated in the test population (difference: model tested "
            "minus that reference). Outcome cases are fatal crashes for the Catalan models and "
            "serious or fatal injuries for the Barcelona person-severity model. The Catalan "
            "severity model is a penalised logistic regression; each of the other models uses "
            "the method, logistic regression or gradient-boosted trees, chosen on its own "
            "validation data. The original model is tested without its province variable, the "
            "Catalan severity model without its province terms when a province is left out. "
            "Differences are computed before rounding. The calibration slope is 1 when the "
            "estimates spread as widely as the outcomes. "
            "A blank cell marks a value the tests do not give. The test of each "
            "year from the years before it has no single test population to fit a reference "
            "in, and its fitting records vary by year. The later-year rows of the original "
            "model and its versions come from each model's own test on that year, which "
            "recorded no interval or calibration slope.",
        )
        + f'<p>The <a href="{DOCS_URL}/GENERALISABILITY.md">generalisability report</a> lists '
        "every test with its fitting and test periods, for both logistic regression and "
        "gradient-boosted trees, and the Catalan severity model's tests beside the table of "
        "fatal shares by road and crash type.</p>",
    )
    body += downloads(
        [
            ("gen_calculator_transfer", "Catalan severity model"),
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
        "How the Catalan severity model, and the original Catalan model it replaced, rank "
        "crashes from years, places and records they were not fitted on.",
        body,
    )
