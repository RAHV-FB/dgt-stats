"""Methodology: definitions, rates and denominators, crash records, models, checks, reproduction."""

from __future__ import annotations

import re

import pandas as pd

from dgt_stats import io_exposure, risk_trends, severity_model
from dgt_stats.microdata.ml import modelling, recording, rules
from dgt_stats.microdata.validation import transport
from dgt_stats.paths import RAW_DATA_DIR, TABLES_DIR
from dgt_stats.site.components import (
    ALL_PAGES,
    DOCS_URL,
    REPO_URL,
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
)
from dgt_stats.site.numbers import _driver_numbers
from dgt_stats.site.regional_common import _year_label

TITLES = dict(ALL_PAGES)
# A fall of more than this in the share of crashes with an empty junction-type field, from one
# year to the next, marks the year the junction fields began to be recorded differently.
JUNCTION_BREAK_DROP = 0.05
# The share of crashes with a recorded junction type counts as unchanged across that break if it
# moves by less than this.
JUNCTION_OBSERVED_TOLERANCE = 0.02
# The grouping of each descriptive comparison table, in words.
RULE_LABELS = {
    "D_SUBTIPUS_ACCIDENT": "crash subtype",
    "D_SUBZONA": "zone",
    "person_role": "road-user role",
    "associated_vehicle_group": "vehicle",
    "accident_type": "accident type",
}
# Harmonised variables, in words.
FIELD_LABELS = {"road_class": "road type", "hour_band": "hour"}
# A circumstance field left blank in more than this share of crashes counts as often blank.
MOSTLY_BLANK = 0.3
NUMBER_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
}


def _fail(claim: str) -> None:
    raise ValueError(f"methodology page: the tables no longer support: {claim}")


def _require(checks: dict[str, bool]) -> None:
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        _fail(", ".join(failed))


def _span(years: pd.Series) -> str:
    return f"{int(years.min())}–{int(years.max())}"


def _words(number: int) -> str:
    """A count under ten in words, as in running prose."""
    return NUMBER_WORDS.get(number, _fmt_int(number))


# ----------------------------------------------------------------------------- definitions
def _definitions() -> str:
    semantics = read_table("mq_bcn_count_semantics").set_index("check").value
    no_victim = int(semantics["blank cells in Numero_victimes"])
    _require({"some Barcelona crashes record no victim": no_victim > 0})
    victims = read_table("validation")
    victims = victims[victims.check == "victim_total"].pivot_table(
        index="year", columns="unit", values="actual"
    )
    later = 1 - victims.deaths_24h.sum() / victims.deaths_30d.sum()
    _require({"some deaths within 30 days occur after the first day": later > 0})
    items = [
        (
            "Injury crash",
            "a crash on a public road in which at least one person is killed or injured. DGT's "
            "national records and series count only injury crashes, and a slight injury there "
            "needs medical care. Barcelona's crash table also holds crashes the Guàrdia Urbana "
            f"attended in which nobody was hurt ({_fmt_int(no_victim)} in its year), and it counts "
            "people who refused medical care as slightly injured.",
        ),
        (
            "Death",
            "a death within 30 days of the crash, DGT's consolidated definition, used for the "
            "national series and rates, monthly as well as annual. The Catalan file counts "
            "deaths within 24 hours; Barcelona's records keep deaths within 24 hours apart from "
            "later deaths, and the analysis of people counts both. In DGT's national records for "
            f"{_span(victims.index.to_series())}, {_fmt_pct(later)} of the deaths within 30 days "
            "occurred after the first 24 hours, so the two definitions are never combined.",
        ),
        (
            "Serious injury",
            "admission to hospital for more than 24 hours; any other injury is slight. The "
            "Catalan file and Barcelona's crash table classify at 24 hours, so a person who "
            "died later counts there as seriously injured. The Catalan file holds crashes with "
            "a death or serious injury (serious and fatal crashes); those in which nobody died "
            "within 24 hours are non-fatal.",
        ),
        (
            "Fatal share",
            "among the serious and fatal crashes in Catalonia, the share in which someone died "
            "within 24 hours. For Barcelona the site gives a serious-or-fatal share instead: of "
            "the people whose outcome was recorded, or of the crashes the police attended, the "
            "share with a serious or fatal injury.",
        ),
        (
            "Zone",
            "DGT's grouping of roads into interurban roads, and urban streets and crossings. The "
            "Catalan file also distinguishes through-town roads, which count as urban in "
            "comparisons with DGT's records.",
        ),
        (
            "Driver involved",
            "the driver of a vehicle in an injury crash, injured or not.",
        ),
        (
            "Licence holder",
            "a holder of any driving permit in DGT's census; the B permit is the car licence.",
        ),
        (
            "Crash frequency",
            "how often a group appears in injury crashes relative to a measure of its exposure, "
            "such as "
            "kilometres driven, fuel sold or licence holders.",
        ),
        (
            "Severity",
            "how serious the outcome is once a crash, or a person in one, is already in the "
            "records: deaths per injury crash, deaths per driver involved, the fatal share of "
            "serious crashes. A death rate per unit of exposure is crash frequency multiplied "
            "by severity.",
        ),
        (
            "Recorded factor",
            "a circumstance the police record about a crash, such as alcohol, inappropriate speed "
            "or distraction (Barcelona's records call them causes). It is a police judgement, "
            "not a finding by this study that the circumstance caused the crash.",
        ),
        (
            "Association",
            "a statistical relationship in observed records. Every comparison on the site "
            "between an outcome and a circumstance is an association; none is an estimate of a "
            "causal effect, which would need a design that these records do not provide.",
        ),
        (
            "Predictive model",
            "a model judged only on records not used to fit it, and kept only if it ranks those "
            "records better than a simple table of the same data.",
        ),
    ]
    rows = "".join(f"<li><strong>{term}</strong>: {text}</li>" for term, text in items)
    return f'<h2 id="definitions">Definitions</h2><ul>{rows}</ul>'


# ----------------------------------------------------------------------------- rates
def _rates() -> str:
    scatter = read_table("risk_dispersion").set_index("outcome")
    dispersion = {key: float(scatter.loc[key, "dispersion"]) for key in scatter.index}
    _require(
        {
            "deaths, admissions and crashes scatter more than Poisson chance": all(
                dispersion[key] > 1 for key in ("deaths_30d", "hospitalised_30d", "crashes")
            ),
        }
    )
    vehicles = risk_trends.MOTOR_VEHICLES
    denominators = [
        (
            "Residents",
            "measure the burden of road deaths on a population, most of whom were not "
            "travelling at the time; a rate per resident falls when people travel less.",
        ),
        (
            "Licence holders",
            f"divide only the drivers of {vehicles} killed or admitted to hospital.",
        ),
        (
            "Registered vehicles",
            f"divide only the occupants of {vehicles}.",
        ),
        (
            "Road fuel",
            "is the tonnes of petrol and diesel sold, the only annual measure of traffic that "
            "covers every road.",
        ),
        (
            "Vehicle-kilometres",
            "are the Ministerio de Transportes' measurements on State, regional and provincial "
            "interurban roads, and DGT's estimates from inspection odometer readings by vehicle "
            "type. Kilometres by driver age are estimated from the EMEF working-day survey's "
            "age profile applied to Spain's population and scaled to DGT's car kilometres.",
        ),
        (
            "Drivers involved",
            "in injury crashes give deaths per driver involved: how often involvement ends in "
            "death. This rate needs no measure of travel.",
        ),
    ]
    items = "".join(f"<li><strong>{name}</strong> {text}</li>" for name, text in denominators)
    trends = f'<a href="trends.html">{TITLES["trends"]}</a>'
    return (
        '<h2 id="rates">Rates, denominators and intervals</h2>'
        "<p>Each rate pairs a count with a denominator meant to contain it:</p>"
        f"<ul>{items}</ul>"
        "<p>Pedestrians and cyclists hold no licence for the trip in which they are hurt and "
        "travel in no registered vehicle, so they are counted against residents and road fuel "
        "only. Road fuel stands in for the kilometres driven on all roads "
        f'(<a href="trends.html#road-fuel">{TITLES["trends"]}</a>), and the kilometres by '
        "driver age transfer one region's survey to Spain; both were tested "
        '(<a href="#assumptions-tested">assumptions tested</a>). Three rates do not fully '
        "meet the rule, and each page says so: rates by sex count unlicensed and foreign "
        "drivers but divide by holders of any licence, rates by vehicle type count foreign "
        "vehicles against the kilometres of Spanish ones, and interurban deaths are compared "
        "with national road fuel only as a check.</p>"
        "<h3>How often crashes happen and how deadly they are</h3>"
        "<p>A death rate measured against traffic combines two quantities that can move "
        "separately: deaths per kilometre (or per tonne of fuel) equal injury crashes per "
        "kilometre multiplied by deaths per injury crash. The split "
        "depends on how completely slight-injury crashes are recorded: if fewer are recorded, "
        "crashes per kilometre fall and deaths per crash rise by the same factor, and their "
        "product does not move. Deaths are counted completely, so the death rate is the firmer "
        "measure and its split the more fragile reading. The "
        f'split is applied on <a href="long-run.html">{TITLES["long-run"]}</a>, '
        f'<a href="drivers.html">{TITLES["drivers"]}</a> and '
        f'<a href="vehicles.html">{TITLES["vehicles"]}</a>.</p>'
        "<h3>Ordinary year-to-year variation</h3>"
        "<p>Rates carry 95% intervals that treat counts as Poisson with a known denominator; "
        "ratios of two rates carry log-normal intervals. Spain's annual counts scatter around "
        "their trend more than chance alone would produce (over "
        f"{risk_trends.SCATTER_YEARS[0]}–{risk_trends.SCATTER_YEARS[1]}, "
        f"{_fmt_dec(dispersion['deaths_30d'])} times the Poisson variance for deaths, "
        f"{_fmt_dec(dispersion['hospitalised_30d'])} times for hospital admissions and "
        f"{_fmt_dec(dispersion['crashes'], 0)} times for injury crashes), so changes against "
        f"{risk_trends.BASE_YEAR} are read against intervals widened to span that ordinary "
        f"year-to-year variation ({trends}).</p>"
    )


# ----------------------------------------------------------------------------- records
def _coding_breaks() -> str:
    other = read_table("q2_other_road_by_period")
    earlier, later = other.iloc[0], other.iloc[-1]
    earlier_years = [int(year) for year in re.findall(r"\d{4}", str(earlier.period))]
    earlier_count = earlier_years[-1] - earlier_years[0] + 1
    missing = read_table("missingness_by_year")
    junction_field = missing[missing.column == "NUDO_INFO"].set_index("year").sort_index()
    info = junction_field.share_empty
    drops = info.diff()
    breaks = [int(year) for year in drops[drops < -JUNCTION_BREAK_DROP].index]
    _require(
        {
            "most of the later 'other' crashes are on urban streets": float(later.street_share)
            > 0.5
            > float(earlier.street_share),
            "far more urban-street crashes are coded 'other' in the later year": float(
                later.street_crashes
            )
            > 2 * float(earlier.street_crashes) / earlier_count,
            "the junction-type field changes once": len(breaks) == 1,
            "the later road-type period is a single year": str(later.period).isdigit(),
        }
    )
    junction = breaks[0]
    before, after = junction_field.loc[junction - 1], junction_field.loc[junction]
    _require(
        {
            "the junction-type field stays empty less often after the change": bool(
                (info.loc[junction:] < info.loc[: junction - 1].min()).all()
            ),
            "the blanks become 'not specified' codes": float(after.share_not_specified)
            - float(before.share_not_specified)
            > JUNCTION_BREAK_DROP,
            "the share with a recorded junction type barely changes": abs(
                float(after.share_observed) - float(before.share_observed)
            )
            < JUNCTION_OBSERVED_TOLERANCE,
        }
    )
    coding = read_table("gen_coding_by_region").set_index(["region", "year"]).sort_index()
    cat, rest = coding.loc["Catalonia"], coding.loc["Spain outside Catalonia"]
    switch = int(cat[cat.road_type_5_dual_carriageway.eq(0)].index.min())
    cat_before = cat.loc[switch - 1]
    rest_dual = rest.road_type_5_dual_carriageway
    other_year = int(later.period)
    cat_other = int(cat.loc[other_year, "road_type_14_other"])
    all_other = cat_other + int(rest.loc[other_year, "road_type_14_other"])
    cat_blank = cat.junction_type_blank / cat.crashes
    rest_blank = rest.junction_type_blank / rest.crashes
    cat_unspecified = cat.junction_type_not_specified / cat.crashes
    _require(
        {
            "until the switch the Catalan records use the dual-carriageway code for conventional "
            "roads": bool(
                (
                    cat.loc[: switch - 1].road_type_6_single_carriageway
                    < 0.01 * cat.loc[: switch - 1].road_type_5_dual_carriageway
                ).all()
            )
            and bool((cat.loc[switch:].road_type_5_dual_carriageway == 0).all()),
            "elsewhere the dual-carriageway code holds steady": float(
                rest_dual.max() / rest_dual.min()
            )
            < 1.5,
            "the later 'other' road-type crashes are mostly Catalan": cat_other > 0.75 * all_other,
            "the junction-field change is Catalan": float(
                cat_blank.loc[junction - 1] - cat_blank.loc[junction]
            )
            > 0.5
            and float(abs(rest_blank.loc[junction] - rest_blank.loc[junction - 1]))
            < JUNCTION_OBSERVED_TOLERANCE,
        }
    )
    return (
        '<h3 id="coding-breaks">Coding breaks</h3>'
        "<p>Three changes in DGT's coding affect series by road type and junction, and all three "
        "come from the records for the four Catalan provinces. Until "
        f"{switch - 1} those records code almost every crash on a conventional road as a "
        "conventional road with a dual carriageway "
        f"({_fmt_int(cat_before.road_type_5_dual_carriageway)} such crashes in {switch - 1}, "
        f"{_fmt_int(cat_before.road_type_6_single_carriageway)} on single carriageways); from "
        f"{switch} they use the single-carriageway code instead. Elsewhere the dual-carriageway "
        f"code holds between {_fmt_int(rest_dual.min())} and {_fmt_int(rest_dual.max())} crashes "
        f"a year. In {later.period} many crashes on urban streets begin to be coded as road "
        f"type “other”: {_fmt_pct(later.street_share, 0)} of that year's “other” crashes are on "
        f"urban streets, against {_fmt_pct(earlier.street_share, 0)} in "
        f"{str(earlier.period).replace('-', '–')}, and {_fmt_int(cat_other)} of the "
        f"{_fmt_int(all_other)} crashes with the code for another kind of road are Catalan. In "
        f"{junction} the junction-type field changes how it marks a missing value: in Spain as a "
        f"whole blank cells fall from {_fmt_pct(before.share_empty, 0)} to "
        f"{_fmt_pct(after.share_empty, 0)} of crashes and “not specified” rises from "
        f"{_fmt_pct(before.share_not_specified, 0)} to {_fmt_pct(after.share_not_specified, 0)}, "
        "while the share with a recorded junction type barely changes "
        f"({_fmt_pct(before.share_observed)} and {_fmt_pct(after.share_observed)}). In the "
        f"Catalan records blank cells fall from {_fmt_pct(cat_blank.loc[junction - 1], 0)} to "
        f"{_fmt_pct(cat_blank.loc[junction], 0)} and “not specified” rises from "
        f"{_fmt_pct(cat_unspecified.loc[junction - 1], 0)} to "
        f"{_fmt_pct(cat_unspecified.loc[junction], 0)}; elsewhere the field does not change. "
        "Road-type series are therefore read year by year and alongside zone, the two kinds of "
        "conventional road form one group, and no road-type trend is drawn. Comparisons of "
        "Catalonia with the rest of Spain group every conventional road together for the same "
        'reason (<a href="validation.html">External validation</a>).</p>'
    )


def _records(captions: dict[str, str]) -> str:
    regional = read_table("dgt_audit_regional")
    outcome = read_table("dgt_audit_outcome_recording")
    artefacts = read_table("ml_recording_artefacts")
    semantics = read_table("mq_bcn_count_semantics").set_index("check").value
    limit = recording.RATIO_LIMIT
    dependent = outcome[
        (outcome.unrecorded_share_not_fatal >= recording.MIN_RATE)
        & (
            (outcome.ratio_fatal_to_not_fatal >= limit)
            | (outcome.ratio_fatal_to_not_fatal <= 1 / limit)
        )
    ]
    catalan = artefacts[artefacts.verdict == "outcome-dependent recording"]
    catalogue = read_table("ml_feature_catalogue")
    catalogue = catalogue[catalogue.feature_table == "catalonia_crash_severity"]
    in_main = catalogue[catalogue.feature_sets.str.contains("context")].column
    explicit_zeros = int(semantics.filter(like="explicit zero").iloc[0])
    adds_up = int(semantics["crashes where victims = deaths + serious + minor (blank read as 0)"])
    _require(
        {
            "Barcelona's blank counts mean zero": explicit_zeros == 0
            and adds_up == int(semantics["crashes"]),
            "the outcome-dependent Catalan placeholders are rarer among fatal crashes": bool(
                (catalan.ratio_fatal_to_serious <= 1 / limit).all()
            )
            and not catalan.empty,
            "some DGT fields are recorded differently for fatal crashes": not dependent.empty,
            "the outcome-dependent Catalan fields stay out of the main model": not set(
                catalan.column
            )
            & set(in_main),
            "blank shares differ widely between provinces": not bool(
                regional.comparable_across_provinces.astype(bool).all()
            ),
        }
    )
    levels, fields = len(catalan), catalan.column.nunique()
    # The right-of-way flags answer one question (who had priority) in 13 columns that are blank
    # together, so they count as one question here.
    priority = regional.field.str.startswith("PRIORI_")
    questions = pd.concat(
        [
            regional[~priority].set_index("field").unrecorded_share,
            pd.Series({"right of way": regional[priority].unrecorded_share.max()}),
        ]
    )
    mostly_blank = int((questions > MOSTLY_BLANK).sum())
    _require(
        {
            "the right-of-way flags are blank together": float(
                regional[priority].unrecorded_share.max()
                - regional[priority].unrecorded_share.min()
            )
            < 0.01,
            "blank shares split into fields nearly always filled and fields often blank": 0
            < mostly_blank
            < len(questions) / 2,
        }
    )
    return (
        '<h2 id="records">Reading police crash records</h2>'
        "<p>Crash records contain only the crashes the police recorded, and the Catalan file "
        "only those with a death or serious injury. A share computed from such records, such as "
        "the fatal share on interurban roads, measures how severe crashes were once they had "
        "happened and been recorded. It does not measure how often "
        "crashes happen or how dangerous a road is per kilometre travelled, because the records "
        "contain no measure of travel. The severity models share this limit: they predict a "
        "severe outcome only among crashes that were recorded. Every result is observational. Where an "
        "outcome is related to a circumstance, the study reports an association, and no "
        "analysis estimates the causal effect of a road, a vehicle, a behaviour or a "
        "policy.</p>"
        "<p>Recorded factors are judgements the police make after the event: the factors DGT "
        "records, such as speed, alcohol or distraction, the Catalan file's “influence” fields, "
        "and Barcelona's contributing factors and driver causes. They show what the police "
        "attributed to the crash; none is established as a cause, a crash can carry several, "
        "and how completely they are recorded varies by year and with the severity of the "
        "crash. The Catalan file's speed field is the posted limit; no file records a "
        "vehicle's speed.</p>"
        "<p>Missing values keep their own categories. “Not specified”, “not applicable”, a "
        "field's own “unknown” code and an empty cell are four different states, and none is "
        "read as zero or as “no”, except where DGT's dictionary itself codes an absence as an "
        "empty cell, as in the field for strong wind. Of the "
        f"{_fmt_int(len(questions))} fields of DGT's records that the audit examines (the "
        f"{_fmt_int(int(priority.sum()))} right-of-way flags counted as one), "
        f"{_words(mostly_blank)} are left blank in more than {_fmt_pct(MOSTLY_BLANK, 0)} of "
        "crashes, and blank shares differ widely between provinces, which keeps the national "
        "file out of model training "
        '(<a href="sources.html">Data sources and scope</a>). In Barcelona\'s crash table, by '
        "contrast, a blank count means zero: no cell holds an explicit zero, and with blanks "
        "read as zero the victims add up in every crash.</p>"
        + figure(
            "d1_missingness",
            "Share of DGT crash records with a value recorded, by field and year",
            captions,
        )
        + "<p>Recording can also depend on the outcome. Fatal crashes may be investigated more "
        "fully, so fields left unspecified in non-fatal crashes are more often filled in for "
        f"fatal ones. In the Catalan file, {_words(levels)} placeholder levels in "
        f"{_words(fields)} fields (“not specified” or an unexplained blank) are recorded at "
        f"least {_fmt_dec(limit)} times as often in non-fatal crashes as in fatal ones; these "
        "fields are left out of every published model. The road owner is the reverse case, "
        "blank far more often on fatal records, and the calculator leaves out the crashes it "
        f'affects (<a href="{DOCS_URL}/research/ML_MODEL_REVIEW.md">model review</a>). In '
        "DGT's records, "
        f"{_words(dependent.field.nunique())} fields are left blank at rates that differ by a "
        f"factor of {_fmt_dec(limit)} or more between fatal and other crashes in at least one "
        "region.</p>"
        "<p>Records are never linked across sources "
        '(<a href="sources.html">how the sources are compared</a>).</p>' + _coding_breaks()
    )


# ----------------------------------------------------------------------------- models
def _models() -> str:
    split = read_table("ml_split_isolation").set_index("model")
    comparison = read_table("ml_rule_comparison").set_index("model")
    selected = read_table("ml_selected")
    primary = selected[selected.primary].set_index("model")
    common = read_table("ml_common_feature_validation")
    shared = read_table("ml_common_features")
    catalogue = read_table("ml_feature_catalogue")
    cat_checks = read_table("mq_cat_checks").set_index("check").value
    bcn_year = _year_label(read_table("bcn_person_severity_share"))
    scores = read_table("sev_rolling_scores")
    pooled = scores[scores.subset.str.fullmatch(r"\d{4}-\d{4}")]
    rolling = _span(pd.Series([int(y) for y in re.findall(r"\d{4}", pooled.subset.iloc[0])]))
    pooled = pooled.set_index("estimator")
    calc, lookup = pooled.loc["calculator"], pooled.loc["road_x_crash_table"]
    gaps = read_table("sev_comparison").set_index(["estimator", "metric"])
    against = gaps.loc[("road_x_crash_table", "roc_auc_minus_calculator")]
    gain_low, gain_high = -float(against.high), -float(against.low)
    catalan_years = read_table("cat_frequency").year
    cat_years = re.findall(r"\d{4}", split.loc["catalonia_crash_severity", "design"])
    bcn_numbers = re.findall(r"\d+", split.loc["barcelona_person_severity", "design"])
    candidates = common[common.a_priori_status.isin(["exact", "defensible"])]
    used = candidates[candidates.enters_cross_source_tests.astype(bool)]
    dropped = candidates[~candidates.enters_cross_source_tests.astype(bool)]
    bcn_pair = shared[shared.pair.str.contains("Barcelona")]
    bcn_shared = bcn_pair[bcn_pair.enters_cross_source_tests.astype(bool)]
    mappable = bcn_pair.status.isin(["exact", "defensible"])
    catalan_last = int(catalan_years.max())
    main_sets = catalogue.feature_sets.str.contains("context")
    adds = comparison.model_adds_signal_over_table.astype(bool)
    low, high = modelling.CALIBRATION_SLOPE_RANGE
    tolerance = modelling.CALIBRATION_LARGE_TOLERANCE
    _require(
        {
            "the calculator's model beats its table by the rule": float(
                calc.roc_auc - lookup.roc_auc
            )
            >= rules.MIN_GAIN
            and gain_low > 0,
            "the calculator's estimates pass the calibration rule": low
            <= float(calc.calibration_slope)
            <= high
            and abs(float(calc.mean_predicted - calc.prevalence)) <= tolerance * calc.prevalence,
            "the original Catalan design names training, choice and test years": len(cat_years)
            == 5,
            "the Barcelona design names months and folds": len(bcn_numbers) == 5,
            "no crash or group straddles a split": bool(
                (split.shared_ids == 0).all() and (split.shared_groups == 0).all()
            ),
            "the Barcelona crash model does not beat its table": not bool(
                adds["barcelona_crash_severity"]
            ),
            "the Barcelona person-severity model is for ranking only": not bool(
                primary.loc["barcelona_person_severity", "probabilities_shown_as_estimates"]
            ),
            "the main models use only circumstances of the crash or person": bool(
                (catalogue[main_sets].status == "safe").all()
            ),
            "variables that encode the outcome are in no model": bool(
                (catalogue[catalogue.status == "direct_leakage"].feature_sets == "none").all()
            ),
            "some candidate variables fail the overlap check": not dropped.empty,
            "the Barcelona variables are exactly those that map exactly or defensibly": bool(
                (bcn_pair.enters_cross_source_tests.astype(bool) == mappable).all()
            ),
            "the Barcelona records share no year with the Catalan file": int(bcn_year[:4])
            > catalan_last,
        }
    )
    provinces = int(cat_checks["demarcations"])
    excluded = _join([FIELD_LABELS.get(field, field.replace("_", " ")) for field in dropped.field])
    overlap = read_table("cat_vs_dgt_province_year").year
    validation = '<a href="validation.html">External validation</a>'
    calculator = f'<a href="severity-models.html">{TITLES["severity-models"]}</a>'
    review = f'<a href="{DOCS_URL}/research/ML_MODEL_REVIEW.md">model review</a>'
    report = f'<a href="{DOCS_URL}/research/SEVERITY_CALCULATOR.md">calculator report</a>'
    choice = _join([str(year) for year in severity_model.VALIDATION_YEARS])
    return (
        '<h2 id="models">How the models were built and judged</h2>'
        "<p>The published model is the calculator's: a penalised logistic regression of whether "
        "a crash with a death or serious injury in Catalonia was fatal, with a death within 24 "
        f"hours, given circumstances a reader can describe ({calculator}). It is tested by "
        f"rolling origin: each year of {rolling} is predicted by the model fitted only on the "
        "years before it, beside a table of fatal shares by road and crash type fitted on the "
        "same years. The strength of its penalty was chosen from "
        f"{_words(len(severity_model.C_GRID))} values by fitting on "
        f"{int(catalan_years.min())}–{severity_model.TRAIN_LAST_YEAR} and scoring {choice}, "
        "years that are also tested. Its intervals come from "
        f"{_fmt_int(severity_model.N_BOOTSTRAP)} refits on resampled crashes. Crashes on "
        "conventional roads whose owner is recorded as “other” or left blank are left out, "
        f"because that field records how a crash was documented ({review}). The model is also "
        f"tested on each province and on Barcelona city left out of its fitting ({validation}), "
        f"and its method is set out in the {report}.</p>"
        "<p>ROC-AUC measures how well a model ranks: it is the probability that the model "
        "places a randomly chosen case with the outcome above a randomly chosen case without "
        "it. A value of 0.5 is no better than chance and 1 is a perfect ranking. When the "
        "outcome is rare, as deaths are, ROC-AUC can be high while most of the cases ranked "
        "highest are still cases without it. PR-AUC (average precision) measures how often the "
        "highest-ranked cases have the outcome; a model with no information scores the "
        "outcome's prevalence.</p>"
        "<p>A model that ranks well may still add nothing to what a simple table shows. Each "
        "model is therefore compared, on the same test records, with a table fixed before the "
        "test: the share of severe outcomes in each group of the training records. A model is "
        f"kept only if its ROC-AUC exceeds the table's by at least {rules.MIN_GAIN:.2f} and the "
        "95% interval of the difference excludes zero. Over "
        f"{rolling} the calculator's model scores {calc.roc_auc:.3f} against "
        f"{lookup.roc_auc:.3f} for its table, a gain of {calc.roc_auc - lookup.roc_auc:.3f} "
        f"(95% interval {gain_low:.3f}–{gain_high:.3f}).</p>"
        "<p>A model can rank well and still give probabilities that are too high or too low. "
        "Calibration compares the predicted probabilities with the observed shares in groups "
        "of test records; its slope is 1 when the predictions spread exactly as widely as the "
        "outcomes, and above 1 when they are not spread widely enough. Probabilities are shown "
        f"as estimates only if the slope lies between {low} and {high} and the mean predicted "
        f"probability is within {_fmt_pct(tolerance, 0)} of the observed share, a rule fixed in "
        "advance. The calculator's model passes it (slope "
        f"{_fmt_dec(calc.calibration_slope, 2)}, mean prediction "
        f"{_fmt_pct(calc.mean_predicted)} against {_fmt_pct(calc.prevalence)} observed). Intervals "
        f"for the scores come from {_fmt_int(modelling.N_BOOT)} bootstrap resamples of the test "
        f"records, {_fmt_int(transport.N_BOOT_TRANSPORT)} in the external tests.</p>"
        "<p>The project's earlier models used a single split by time. The original Catalan "
        f"model was trained on the crashes of {cat_years[0]}–{cat_years[1]}, its settings were "
        f"chosen on {cat_years[2]}–{cat_years[3]}, it was refitted on {cat_years[0]}–"
        f"{cat_years[3]} and tested once on {cat_years[4]}. It was replaced by the calculator's "
        "model, because its strongest predictor was the road's owner. The Barcelona models were "
        f"trained on months {bcn_numbers[0]}–{bcn_numbers[1]} of {bcn_year}, with settings "
        f"chosen by {bcn_numbers[2]}-fold cross-validation that keeps the people of one crash "
        f"in the same fold, and tested on months {bcn_numbers[3]}–{bcn_numbers[4]}; no crash "
        "appears on both sides of a split. The Barcelona crash-severity model ranked unseen "
        "crashes no better than its table of shares by accident type, so the study reports the "
        "table instead; the Barcelona person-severity model ranks people without giving "
        f"probabilities and is kept for research. Every model was re-evaluated in the {review}."
        "</p>"
        "<p>The external tests set each model beside a model of the same kind trained in the "
        f"test population: the original Catalan model with each of the {_words(provinces)} "
        "provinces left out in turn and with Barcelona city against the rest of Catalonia, and "
        "the Barcelona models on one district at a time. For DGT's records elsewhere in Spain, "
        f"the original model's specification is refitted on the {len(used)} of "
        f"{len(candidates)} candidate variables whose mapped distributions match on the Catalan "
        f"crashes of {_span(overlap)}, which both files contain ({excluded} do not). Barcelona's "
        f"records share no crash with the Catalan file, so the {_words(len(bcn_shared))} "
        "variables used for Barcelona were chosen only because their codings map exactly or "
        f"defensibly; there were no shared crashes to check them on ({validation}).</p>"
        "<p>Before fitting, each variable was classified by how far the outcome could shape "
        "it. The models use only circumstances recorded about the crash or the person. "
        "Variables the outcome may shape, such as police causes and the Catalan influence "
        "fields, enter only separate comparison versions of the original models, and variables "
        "that encode the outcome enter none "
        f'(<a href="{DOCS_URL}/ML_LEAKAGE_AUDIT.md">audit of the variables</a>). The check for '
        "fields recorded differently when a crash was fatal looked only for placeholders rarer "
        "among fatal crashes, pooled over zones, and did not catch the road-owner field; the "
        "re-evaluation found it.</p>"
    )


# ----------------------------------------------------------------------------- checks
def _assumptions() -> str:
    """The assumptions behind the results that the data can test, each with what testing found."""
    km = read_table("longrun_km_panel").set_index("year")
    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_last = int(km.index.max())
    segments = read_table("longrun_segments")
    base_year = int(segments[segments.measure == "road_fuel"].start.max())
    bio = read_table("longrun_fuel_bio").set_index("year").bio_share
    drivers = _driver_numbers()
    ranges = drivers["ranges"]
    central = drivers["central"].involved_ratio
    licence = drivers["licence"].involved_ratio
    prevalence = read_table("risk_licence_prevalence")
    young_licensed = prevalence[prevalence.group == "15-29"].set_index(["place", "sex"]).prevalence
    city_older = drivers["city"][drivers["city"].age4 == "65+"].ratio_to_45_64
    reference = risk_trends.BASE_YEAR
    per_km_last = km_check.loc[("per_km", km_last)]

    def growth(a: int, b: int) -> float:
        ratio = float(km.loc[b, "km_per_tonne"] / km.loc[a, "km_per_tonne"])
        return ratio ** (1 / (b - a)) - 1

    early, recent = growth(base_year, reference), growth(reference, km_last)
    _require(
        {
            "per measured interurban km the last year is inside its interval": not bool(
                per_km_last.outside_interval
            ),
            "interurban km per tonne of national fuel rise in both periods": early > 0
            and recent > 0,
            "the biofuel share rose, which lowers km per tonne": float(bio.loc[km_last])
            > float(bio.loc[reference]),
            "every assumption keeps the young above the middle-aged per km": float(
                ranges.loc["18-29", "min"]
            )
            > 1.5,
            "young residents of the province hold car licences less often than Spain's": all(
                young_licensed[("08", sex)] < young_licensed[("Spain", sex)]
                for sex in ("male", "female")
            ),
        }
    )
    fuel_pages = _join([TITLES[slug] for slug in ("trends", "long-run", "seasons")])
    rows = [
        (
            f"Road fuel tracks the kilometres driven ({fuel_pages})",
            "Measured interurban vehicle-kilometres set against national road fuel: kilometres "
            f"per tonne rise in both {base_year}–{reference} and {reference}–{km_last} "
            f"({TITLES['long-run']}).",
            "The proxy can be checked only on interurban roads, since the measured kilometres "
            "cover State, regional and provincial roads. There, deaths per measured kilometre "
            f"in {km_last} lie within the interval of their pre-pandemic trend.",
        ),
        (
            f"A tonne of road fuel means the same every year ({fuel_pages})",
            "CORES subtotals equal their products, biofuels included, in every month; biofuel "
            f"was {_fmt_pct(float(bio.loc[reference]))} of road fuel by mass in {reference} and "
            f"{_fmt_pct(float(bio.loc[km_last]))} in {km_last}.",
            "Confirmed. Biofuel carries less energy per tonne, so its rise would lower "
            "kilometres per tonne slightly; it cannot explain the rise in interurban kilometres "
            "per tonne.",
        ),
        (
            f"One region's age profile of driving holds for Spain ({TITLES['drivers']})",
            "Young residents of the province of Barcelona hold car licences less often than "
            "Spain's, so the survey's driving per licence holder, carried to Spain instead of "
            f"its driving per resident, puts involvement per km at 18–29 at {float(licence['18-29']):.2f}× "
            f"the 45–64 rate against {float(central['18-29']):.2f}× centrally, and at 65 and over "
            f"at {float(licence['65+']):.2f}× against {float(central['65+']):.2f}×. With other "
            "regional profiles, distance treatments, survey years and weekend mixes the ratio at "
            f"18–29 runs from {float(ranges.loc['18-29', 'min']):.2f}× to "
            f"{float(ranges.loc['18-29', 'max']):.2f}×, and at 65 and over from "
            f"{float(ranges.loc['65+', 'min']):.2f}× to {float(ranges.loc['65+', 'max']):.2f}×.",
            "The assumption does not hold exactly, so the ratios per km by age are given with "
            "these sensitivity ranges, and the direction at 18–29 is the firm result. A separate "
            "check inside Barcelona on working days, the city's crashes against the same survey's "
            f"driving inside the city, gives {float(city_older.min()):.2f}×–"
            f"{float(city_older.max()):.2f}× at 65 and over. Deaths per driver involved need no "
            "kilometres.",
        ),
    ]
    frame = pd.DataFrame(rows, columns=["Assumption", "Test and result", "Consequence"])
    return (
        '<h3 id="assumptions-tested">Assumptions tested</h3>'
        "<p>Several results rest on assumptions that the data can test.</p>"
        + table(frame, "Assumptions behind the results, how each was tested, and what follows.")
    )


def _checks() -> str:
    validation = pd.read_csv(TABLES_DIR / "validation.csv")
    passed = int(validation.passed.astype(bool).sum())
    total = int(len(validation))
    outcome = (
        "All of them pass, and the crash records match the yearbook exactly, year by year. "
        if passed == total
        else f"{_fmt_int(total - passed)} of them do not pass; the list says which. "
    )
    return (
        '<h2 id="checks">Checks on the data</h2>'
        f"<p>Before any analysis, {_fmt_int(total)} checks tie DGT's crash records, yearbook "
        "tables and driver census to DGT's published totals, from crashes and victims per year "
        "and deaths by province and month to every code against the dictionary. "
        f"{outcome}The kilometre table by owner's age reconciles with the same release's "
        f"published fleet to within {_fmt_pct(io_exposure.KM_OWNER_TOLERANCE)}, the margin left "
        'by owners DGT could not classify. The <a href="tables/validation.csv">full list of '
        "checks</a> is published as a table.</p>" + _assumptions()
    )


# ----------------------------------------------------------------------------- reproduction
def _reproduce() -> str:
    return (
        '<h2 id="reproduce">Reproducing the results</h2>'
        "<p>Every result in the study is computed from the raw published files by the code in "
        "the repository. The raw files are kept with their checksums and, "
        "where recorded, their download addresses, and one command sequence in the "
        f'<a href="{REPO_URL}#reproduce">README</a> rebuilds the checks, tables, models, '
        "figures and pages in order. Each page reads its numbers from the result tables, and "
        "the build stops if a table no longer supports a sentence that describes it. Automated "
        "tests rerun the checks on every change.</p>"
        f'<p>The repository also holds the <a href="{DOCS_URL}/methodology.md">implementation '
        "notes</a>, with the module behind each method, the "
        f'<a href="{DOCS_URL}/data_sources.md">source register</a>, with each file\'s address, '
        f'terms and checksum, and the <a href="{DOCS_URL}/data_inventory.md">data '
        "inventory</a>.</p>"
        "<p>The project was developed through a reproducible, source-driven workflow. The "
        "research questions, the choice of sources, the statistical design, the interpretation "
        "and the decision to publish each result are the author's, and so is responsibility for "
        "them. AI coding assistants were used during implementation, debugging, data-processing "
        "work and review.</p>"
    )


def _manifest_note(path_prefix: str, pattern: str) -> str:
    """A date or phrase the source register records in the manifest description of a file."""
    manifest = pd.read_csv(RAW_DATA_DIR / "manifest.csv")
    rows = manifest[manifest.path.str.startswith(path_prefix)]
    found = sorted({m for text in rows.description for m in re.findall(pattern, str(text))})
    _require({f"the manifest records {pattern!r} for {path_prefix}": len(found) >= 1})
    return found[-1]


def _reuse() -> str:
    catalan_update = _manifest_note(
        "catalonia/", r"rows last updated on the portal (\d{4}-\d{2}-\d{2})"
    )
    barcelona_update = _manifest_note("barcelona/", r"last modified (\d{4}-\d{2}-\d{2})")
    manifest = pd.read_csv(RAW_DATA_DIR / "manifest.csv")
    emef_years = sorted(
        {int(y) for y in manifest.path.str.extract(r"^emef/(\d{4})/", expand=False).dropna()}
    )
    _require(
        {
            "the EMEF files cover consecutive years": emef_years
            == list(range(emef_years[0], emef_years[-1] + 1))
        }
    )
    emef_span = f"{emef_years[0]}–{emef_years[-1]}"
    return (
        '<h2 id="reuse">Reuse</h2>'
        f'<p>The code is under the <a href="{REPO_URL}/blob/main/LICENSE">MIT licence</a>. The '
        "data keep the terms of the bodies that publish them. DGT's statistics are reused as "
        "public-sector information under Ley 37/2007 on the reuse of public-sector "
        "information, with the datos.gob.es conditions applied: the source is named, the "
        "meaning is not distorted, the dates are kept and no endorsement is implied. INE's "
        "population data are under CC BY 4.0.</p>"
        "<p>The Catalan crash file is reused under the "
        '<a href="https://administraciodigital.gencat.cat/ca/dades/dades-obertes/informacio-'
        "practica/llicencies/\">Llicència oberta d'ús d'informació - Catalunya</a>. Source: "
        "Generalitat de Catalunya. Departament d'Interior i Seguretat Pública. Servei Català "
        f"de Trànsit; data last updated {catalan_update}. The Barcelona crash records are "
        "published by the Ajuntament de Barcelona on Open Data BCN under the "
        '<a href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution '
        f"4.0</a> licence (2025 files last modified {barcelona_update}); the site reads them "
        "into its own tables and does not alter the files. The EMEF figures are this study's "
        "own calculations from the public-use microdata (ATM, Idescat and Institut Metròpoli, "
        f"Enquesta de mobilitat en dia feiner {emef_span}, Autoritat del Transport "
        "Metropolità), reused under the open-data clause of the Observatori de la Mobilitat de "
        "Catalunya; they are not official results. The Madrid survey figures use the "
        "Consorcio Regional de Transportes de Madrid's EDM2018 data "
        '(<a href="https://www.crtm.es">Powered by CRTM</a>), and the tables derived from them '
        "are distributed under the CRTM's licence, as it requires.</p>"
        "<p>Every published figure is an aggregate, and nothing identifies a person. The "
        f'file-by-file terms are in the <a href="{DOCS_URL}/data_sources.md">source '
        "register</a>.</p>"
    )


def page_data(captions: dict[str, str]) -> str:
    body = summary(
        "This page defines the terms the site uses and explains how its rates, police records "
        "and models are built and read. Each count is divided by a denominator meant to contain "
        "it, with the exceptions named below, and a change is read against the variation of an "
        "ordinary year. Severity "
        "among recorded crashes is kept apart from how often crashes happen, police-recorded "
        "factors are treated as judgements, and missing values stay missing. A predictive model "
        "is kept only if it ranks unseen records better than a simple table fixed in advance."
    )
    body += _definitions()
    body += _rates()
    body += _records(captions)
    body += _models()
    body += _checks()
    body += _reproduce()
    body += _reuse()
    body += downloads(
        [
            ("validation", "reconciliation checks"),
            ("risk_dispersion", "year-to-year dispersion"),
            ("missingness_by_year", "missing values by field and year"),
            ("ml_split_isolation", "training and test splits"),
            ("ml_rule_comparison", "models against their tables"),
            ("ml_common_feature_validation", "harmonised variables"),
            ("ml_feature_catalogue", "variable classification"),
        ]
    )
    return render_page(
        "data",
        "Methodology",
        "The definitions, rates, model tests and data checks used throughout the study, and how "
        "to reproduce its results.",
        body,
    )
