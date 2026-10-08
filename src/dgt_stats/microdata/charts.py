"""Figures for the regional pages, drawn from the committed result tables with the site's plots.

Every figure is a single-series dot-and-interval or bar chart in the project's fixed palette (or
a calibration chart with one line per model), with its N in the caption, and the same numbers
in a table on the page. Nothing is recomputed here: the tables in ``reports/tables`` are the
input, so a figure cannot disagree with the table beside it. The labels a reader sees are
translated from the source field names and pipeline codes by the maps below.
"""

from __future__ import annotations

import calendar
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dgt_stats import plots
from dgt_stats.paths import TABLES_DIR

MIN_N = 30
CAT_SOURCE = "Servei Català de Trànsit, crashes with a death or serious injury"
BCN_SOURCE = "Ajuntament de Barcelona, Guàrdia Urbana crash records"
# The same publication title as ``figures.MICRODATA_SOURCE``, so the site marks it as Spanish.
DGT_SOURCE = "DGT, Ficheros de microdatos de accidentes con víctimas 2016–2024"
REGIONAL_SOURCES = f"{CAT_SOURCE}; {BCN_SOURCE}"

# The three models trained on regional records, in the order the figures show them.
REGIONAL_MODELS = {
    "catalonia_crash_severity": "Catalonia crash-severity model",
    "barcelona_person_severity": "Barcelona person-severity model",
    "barcelona_crash_severity": "Barcelona crash-severity model",
}
# The two validation instruments: the Catalan model restricted to variables recorded alike.
VALIDATION_MODELS = {
    "catalonia_common_dgt": "Harmonised Catalonia model",
    "catalonia_common_bcn": "Catalonia model restricted to Barcelona's variables",
}
MODEL_LABELS = {**REGIONAL_MODELS, **VALIDATION_MODELS}
# Barcelona road users as the person table names them (role and vehicle type), where English has
# a natural word; the other labels are shown as recorded. The regional page uses the same map.
ROAD_USER_LABELS = {
    "bicycle driver": "cyclist",
    "motorcycle driver": "motorcyclist",
    "moped driver": "moped rider",
    "personal mobility vehicle driver": "personal mobility vehicle rider",
}
MODEL_SOURCES = {
    "catalonia_crash_severity": CAT_SOURCE,
    "barcelona_person_severity": BCN_SOURCE,
    "barcelona_crash_severity": BCN_SOURCE,
}

# Human names for every variable a model can use (``ml_feature_catalogue.csv``). Families of
# flags (a vehicle type present, a cause recorded) are composed in ``feature_label``.
FEATURE_LABELS = {
    # Catalonia: the Servei Català de Trànsit fields and the variables derived from them.
    "year": "Year",
    "month": "Month",
    "weekday": "Day of the week",
    "hour": "Hour of the day",
    "hour_band": "Time of day",
    "D_TIPUS_VIA": "Road type",
    "D_TITULARITAT_VIA": "Road owner",
    "D_SUBZONA": "Zone",
    "D_FUNC_ESP_VIA": "Special road function",
    "D_INTER_SECCIO": "Junction or open road",
    "D_SUBTIPUS_TRAM": "Junction type",
    "D_REGULACIO_PRIORITAT": "Right-of-way control",
    "D_SUPERFICIE": "Road surface",
    "D_LLUMINOSITAT": "Lighting",
    "D_CLIMATOLOGIA": "Weather",
    "D_VENT": "Wind",
    "D_BOIRA": "Fog",
    "D_CIRCULACIO_MESURES_ESP": "Special traffic measures",
    "D_SUBTIPUS_ACCIDENT": "Crash subtype",
    "speed_limit_category": "Speed limit",
    "n_units": "Vehicles and pedestrians involved",
    "single_unit": "Single vehicle or pedestrian",
    "demarcation": "Province",
    "comarca": "County (comarca)",
    "municipality": "Municipality",
    "D_TRACAT_ALTIMETRIC": "Gradient",
    "D_CARACT_ENTORN": "Surroundings",
    "D_SENTITS_VIA": "One-way or two-way road",
    "D_CARRIL_ESPECIAL": "Special lane",
    "D_ACC_AMB_FUGA": "A driver left the scene",
    "D_INFLUIT_BOIRA": "Influence of fog",
    "D_INFLUIT_CARACT_ENTORN": "Influence of the surroundings",
    "D_INFLUIT_CIRCULACIO": "Influence of traffic",
    "D_INFLUIT_ESTAT_CLIMA": "Influence of the weather",
    "D_INFLUIT_INTEN_VENT": "Influence of wind",
    "D_INFLUIT_LLUMINOSITAT": "Influence of lighting",
    "D_INFLUIT_MESU_ESP": "Influence of special measures",
    "D_INFLUIT_OBJ_CALCADA": "Influence of objects on the road",
    "D_INFLUIT_SOLCS_RASES": "Influence of ruts or ditches",
    "D_INFLUIT_VISIBILITAT": "Influence of visibility",
    # Barcelona: the Guàrdia Urbana tables.
    "age": "Age",
    "sex": "Sex",
    "person_role": "Road-user role",
    "associated_vehicle_group": "Vehicle group",
    "pedestrian_location": "Where a pedestrian was struck",
    "accident_type": "Accident type",
    "n_vehicles": "Number of vehicles",
    "district": "District",
    "neighbourhood": "Neighbourhood",
    "driver_cause_status": "Whether a driver cause was recorded",
    "pedestrian_cause": "Pedestrian behaviour recorded",
    # The harmonised variables, after their source prefix is removed.
    "zone": "Zone",
    "crash_type": "Crash type",
    "vehicles": "Number of vehicles",
    "lighting": "Lighting",
    "weather": "Weather",
    "surface": "Road surface",
}
# Vehicle and road-user types in the flag names (``involves_bicycle``,
# ``vehicle_records_include_bus_or_coach``), with their article.
VEHICLE_TYPES = {
    "pedestrian": "a pedestrian",
    "bicycle": "a bicycle",
    "moped": "a moped",
    "motorcycle": "a motorcycle",
    "light_vehicle": "a light vehicle",
    "heavy_vehicle": "a heavy vehicle",
    "other_unit": "another vehicle",
    "car": "a car",
    "taxi": "a taxi",
    "personal_mobility_vehicle": "a personal mobility vehicle",
    "van_or_light_truck": "a van or light truck",
    "heavy_truck": "a heavy truck",
    "bus_or_coach": "a bus or coach",
    "tram_or_train": "a tram or train",
    "other": "another vehicle type",
    "not_recorded": "a vehicle of unrecorded type",
}
# Causes the Guàrdia Urbana records for a crash.
CAUSES = {
    "alcohol": "alcohol",
    "speed": "speed",
    "drugs_medication": "drugs or medication",
    "road_surface": "road surface",
    "signalling": "signalling",
    "weather": "weather",
    "object_or_animal": "object or animal on the road",
    "inattention": "inattention",
    "following_distance": "following too closely",
    "improper_turn": "improper turn",
    "traffic_light": "red light",
    "lane_change": "careless lane change",
    "other_signal": "other signal disobeyed",
    "overtaking": "improper overtaking",
    "merging": "careless merging",
    "pedestrian_crossing": "pedestrian crossing not respected",
    "reversing": "careless reversing",
    "right_of_way": "right of way not given",
    "wrong_side": "wrong side of the road",
    "mechanical_failure": "mechanical failure",
    "other": "other",
    "not_determined": "not determined",
}

# Catalan category labels shortened for the charts, so the label column leaves room for the data.
CAT_SHORT_LABELS = {
    "other unit": "other",
    "generic limit for the road (value not recorded)": "generic limit (not recorded)",
    "hit an object without leaving the road": "hit an object on the road",
}

# The external tests of the Catalan models, as a reader would name them.
EXPERIMENT_LABELS = {
    "rest of Catalonia -> Barcelona municipality": "Rest of Catalonia to Barcelona city",
    "Barcelona municipality -> rest of Catalonia": "Barcelona city to the rest of Catalonia",
    "rest of Catalonia to 2019 -> Barcelona municipality after 2019": (
        "Rest of Catalonia to Barcelona city, later years"
    ),
    "same crashes, two sources: Catalan file": "Later years: Catalan file",
    "same crashes, two sources: DGT records": "Later years: the same crashes in DGT records",
    "Catalonia, a year the Catalan file does not have (DGT records)": (
        "Catalonia, a year after the Catalan file (DGT records)"
    ),
    "Catalonia -> Spain outside Catalonia": "Spain outside Catalonia (DGT records)",
    "Catalonia early years -> Spain outside Catalonia later": (
        "Spain outside Catalonia, trained on early years (DGT records)"
    ),
    "Catalonia reweighted to the national zone x crash-type mix -> Spain outside Catalonia": (
        "Spain outside Catalonia, reweighted training (DGT records)"
    ),
}


def feature_label(name: str) -> str:
    """The human name of a model variable; an unlisted name falls back to its words."""
    if name in FEATURE_LABELS:
        return FEATURE_LABELS[name]
    for prefix in ("dgt_", "bcn_"):
        if name.startswith(prefix):
            return feature_label(name.removeprefix(prefix))
    if match := re.fullmatch(r"(?:involves|vehicle_records_include)_(\w+)", name):
        kind = match.group(1)
        return f"Crash involves {VEHICLE_TYPES.get(kind, kind.replace('_', ' '))}"
    if match := re.fullmatch(r"(mediate|driver_cause)_(\w+)_recorded", name):
        kind, cause = match.groups()
        prefix = "Recorded cause" if kind == "mediate" else "Recorded driver cause"
        return f"{prefix}: {CAUSES.get(cause, cause.replace('_', ' '))}"
    return name.removeprefix("D_").replace("_", " ").lower().capitalize()


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def rule_label(rule: str) -> str:
    """A descriptive table's grouping, e.g. ``D_SUBTIPUS_ACCIDENT x D_SUBZONA`` -> 'crash
    subtype × zone'."""
    return " × ".join(_lower_first(feature_label(part)) for part in rule.split(" x "))


def experiment_label(experiment: str) -> str:
    """The plain-English name of an external test of a Catalan model."""
    text = re.sub(r"\s*\((?:DGT|Barcelona)-common features\)$", "", experiment)
    if text.startswith("temporal holdout"):
        return "Later year"
    if text.startswith("rolling origin"):
        return "Each year from the years before it"
    if match := re.fullmatch(r"leave out (\w+) demarcation", text):
        return f"{match.group(1)} province left out"
    if text in EXPERIMENT_LABELS:
        return EXPERIMENT_LABELS[text]
    return text[:1].upper() + text[1:].replace(" -> ", " to ")


def _province_name(name: str) -> str:
    """'Palmas, Las' -> 'Las Palmas': the article the INE list puts after the name, in front."""
    head, _, article = name.partition(", ")
    return f"{article} {head}" if article else name


def _ranges(text: str) -> str:
    """A range written with a hyphen between numbers (age 0-15, 10-30 km/h) with an en dash."""
    return re.sub(r"(?<=\d)-(?=\d)", "–", text)


def _caption(shown: str, source: str, n: int | str | None = None) -> str:
    """A figure caption: what is shown (population and period included), source, count."""
    text = f"{shown}. Source: {source}."
    if n is not None:
        text += f" n = {n:,}." if isinstance(n, int) else f" n = {n}."
    return text


def table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


def _labelled(frame: pd.DataFrame, label: str = "label") -> pd.DataFrame:
    frame = frame[frame.n >= MIN_N].copy()
    frame["row"] = (
        frame[label].astype(str).map(_ranges) + "  (n=" + frame.n.map("{:,}".format) + ")"
    )
    return frame


def _roc_limits(highs: pd.Series) -> tuple[float, float]:
    """A ROC-AUC axis from just below chance to just above the highest interval."""
    return 0.45, math.ceil((float(highs.max()) + 0.02) * 20) / 20


def _shares(
    frame: pd.DataFrame,
    dimension: str,
    path: Path,
    title: str,
    xlabel: str,
    reference: float,
    keep_order: bool = False,
    order: list[str] | None = None,
    xlim: tuple[float, float] | None = None,
) -> Path:
    # The overall share is the dotted reference line, not a row of its own.
    block = _labelled(frame[(frame.dimension == dimension) & (frame.level != "all")])
    if order:
        block = block.set_index("level").reindex([o for o in order if o in set(block.level)])
        block = block.reset_index()
    return plots.dot_interval(
        block,
        "row",
        "share",
        "ci_low",
        "ci_high",
        path,
        title,
        xlabel=xlabel,
        reference=reference,
        reference_label="all",
        percent=True,
        keep_order=keep_order,
        xlim=xlim,
    )


def _bars(values: pd.Series, path: Path, title: str, ylabel: str) -> Path:
    plots.apply_style()
    fig, axis = plt.subplots(figsize=(plots.FIGURE_WIDTH, 3.6))
    positions = np.arange(len(values))
    axis.bar(positions, values.to_numpy(), width=0.68, color=plots.ACCENT, linewidth=0)
    axis.set_xticks(positions, [str(v) for v in values.index], fontsize=plots.NOTE_SIZE)
    axis.tick_params(axis="x", length=0)
    axis.set_ylabel(ylabel)
    plots._thousands(axis)
    plots._title(path, title)
    return plots.save(fig, path)


def catalonia_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    shares = table("cat_fatal_share")
    # The file's 'other unit' is any vehicle outside the named types; the figure says 'other'.
    shares["label"] = shares.label.replace(CAT_SHORT_LABELS)
    overall = shares[(shares.dimension == "unit type involved") & (shares.level == "all")]
    base = float(overall.share.iloc[0])
    n = f"{int(overall.n.iloc[0]):,} crashes"
    years = shares[shares.dimension == "year"].level.astype(int)
    period = f"{years.min()}–{years.max()}"
    charts = (
        ("cat1_fatal_by_road", "road type", "Fatal share by road type", "road type"),
        (
            "cat2_fatal_by_speed_limit",
            "speed limit",
            "Fatal share by posted speed limit (the road's limit, not vehicle speed)",
            "posted speed limit (the limit signposted on the road, not a measured speed)",
        ),
        (
            "cat3_fatal_by_unit",
            "unit type involved",
            "Fatal share by type of road user or vehicle involved (a crash can involve several)",
            "type of road user or vehicle involved",
        ),
        ("cat4_fatal_by_crash_type", "crash subtype", "Fatal share by crash type", "crash type"),
    )
    # The four charts share one scale, so the overall line and the axis line up down the page.
    shown = _labelled(shares[shares.dimension.isin([c[1] for c in charts])])
    top = math.ceil(float(shown.ci_high.max()) * 20) / 20
    for name, dimension, title, by in charts:
        _shares(
            shares,
            dimension,
            figures_dir / f"{name}.svg",
            title,
            "Fatal crashes among serious and fatal crashes",
            base,
            xlim=(0, top),
        )
        captions[name] = _caption(
            f"Fatal crashes as a share of crashes with a death or serious injury, by {by}, "
            f"Catalonia, {period}, with 95% intervals; groups of fewer than {MIN_N} crashes "
            "are left out",
            CAT_SOURCE,
            n,
        )
    frequency = table("cat_frequency").groupby("year").crashes.sum()
    _bars(
        frequency,
        figures_dir / "cat6_crashes_by_year.svg",
        "Crashes with a death or serious injury, by year",
        "Crashes",
    )
    captions["cat6_crashes_by_year"] = _caption(
        f"Recorded crashes with at least one death or serious injury, Catalonia, {period}; "
        "counts of recorded crashes, not rates",
        CAT_SOURCE,
        f"{int(frequency.sum()):,} crashes",
    )


def barcelona_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    people = table("bcn_person_severity_share")
    year = str(people.dataset.iloc[0]).replace("Barcelona ", "")
    is_road_user = people.dimension == "road user"
    people.loc[is_road_user, "label"] = people.loc[is_road_user, "label"].replace(ROAD_USER_LABELS)
    road_users = people[is_road_user]
    base = float(road_users.events.sum() / road_users.n.sum())
    n = f"{int(road_users.n.sum()):,} people"

    def people_caption(by: str) -> str:
        return _caption(
            "People seriously or fatally injured as a share of the people in recorded crashes "
            f"with a recorded injury outcome, by {by}, Barcelona, {year}, with 95% intervals; "
            f"groups of fewer than {MIN_N} people are left out",
            BCN_SOURCE,
            n,
        )

    _shares(
        people,
        "road user",
        figures_dir / "bcn1_severity_by_road_user.svg",
        "Serious or fatal injury by road user (role and vehicle type on the record)",
        "Share of people in recorded crashes",
        base,
    )
    captions["bcn1_severity_by_road_user"] = people_caption("road-user role and vehicle type")
    ages = ["0-15", "16-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]
    _shares(
        people,
        "age band",
        figures_dir / "bcn2_severity_by_age.svg",
        "Serious or fatal injury by age band",
        "Share of people in recorded crashes",
        base,
        keep_order=True,
        order=ages,
    )
    captions["bcn2_severity_by_age"] = people_caption("age band")
    crashes = table("bcn_crash_severity_share")
    crash_base = crashes[(crashes.dimension == "cause recorded") & (crashes.level == "all")]
    # One crash type far above the rest is written out at the axis end, so that the scale is set
    # by the others.
    types = _labelled(crashes[crashes.dimension == "crash type"]).sort_values("share")
    limit = None
    if float(types.share.iloc[-1]) > 2 * float(types.ci_high.iloc[-2]):
        limit = (0, math.ceil(float(types.ci_high.iloc[-2]) * 1.15 * 20) / 20)
    _shares(
        crashes,
        "crash type",
        figures_dir / "bcn4_crash_severity_by_type.svg",
        "Crashes with a serious or fatal injury, by crash type",
        "Share of crashes",
        float(crash_base.share.iloc[0]),
        xlim=limit,
    )
    captions["bcn4_crash_severity_by_type"] = _caption(
        "Crashes with at least one death or serious injury as a share of recorded crashes, by "
        f"crash type, Barcelona, {year}, with 95% intervals; types of fewer than {MIN_N} "
        "crashes are left out",
        BCN_SOURCE,
        f"{int(crash_base.n.iloc[0]):,} crashes",
    )


def _test_records(design: str, bcn_year: str) -> str:
    """The test records of a model, from its design ('… test 2023'; '… test months 10-12')."""
    if match := re.search(r"test (\d{4})$", design):
        return f"Catalan crashes of {match.group(1)}"
    if match := re.search(r"test months (\d+)-(\d+)$", design):
        first, last = (calendar.month_name[int(m)] for m in match.groups())
        return f"Barcelona records of {first}–{last} {bcn_year}"
    raise ValueError(f"unrecognised model design: {design!r}")


def _featured_models(selected: pd.DataFrame) -> list[str]:
    """The models the site features (the decision table's keepers), in the figures' order."""
    decisions_path = TABLES_DIR / "ml_model_decisions.csv"
    if not decisions_path.exists():
        return [model for model in REGIONAL_MODELS if model in set(selected.model)]
    from dgt_stats.microdata.validation.decisions import FEATURED

    decisions = pd.read_csv(decisions_path)
    featured = set(decisions.loc[decisions.decision.isin(FEATURED), "model"])
    return [model for model in REGIONAL_MODELS if model in featured]


def model_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    selected = table("ml_selected")
    variants = table("ml_variants")
    test = variants[(variants.evaluated_on == "test")]
    rule_path = TABLES_DIR / "ml_rule_comparison.csv"
    rules = pd.read_csv(rule_path).set_index("model") if rule_path.exists() else pd.DataFrame()
    bcn_year = str(table("bcn_person_severity_share").dataset.iloc[0]).replace("Barcelona ", "")
    primary = selected[selected.primary].set_index("model")
    regional = [model for model in REGIONAL_MODELS if model in primary.index]
    tests = {model: _test_records(primary.loc[model, "design"], bcn_year) for model in regional}
    # Each model trained on regional records (its selected estimator, with the bootstrap
    # interval), the descriptive table it was compared with, and the baseline.
    rows = []
    for model in regional:
        row = primary.loc[model]
        block = test[
            (test.model == model)
            & (test.feature_set == row.feature_set)
            & (test.geography == row.geography)
        ].set_index("estimator")
        name = REGIONAL_MODELS[model]
        rows.append(
            {
                "model": name,
                "row": "Model",
                "kind": "focal",
                "auc": block.loc[row.estimator, "roc_auc"],
                "low": row.roc_auc_low,
                "high": row.roc_auc_high,
            }
        )
        if model in rules.index:
            auc = rules.loc[model, "rule_roc_auc"]
            rows.append(
                {
                    "model": name,
                    "row": f"Descriptive table ({rule_label(rules.loc[model, 'rule'])})",
                    "kind": "context",
                    "auc": auc,
                    "low": auc,
                    "high": auc,
                }
            )
        auc = block.loc["baseline_prior", "roc_auc"]
        rows.append(
            {
                "model": name,
                "row": "Baseline (one probability for every case)",
                "kind": "baseline",
                "auc": auc,
                "low": auc,
                "high": auc,
            }
        )
    plots.dot_interval(
        pd.DataFrame(rows),
        "row",
        "auc",
        "low",
        "high",
        figures_dir / "ml1_test_auc.svg",
        "Test ROC-AUC: each model against its descriptive table and the baseline",
        xlabel="ROC-AUC on the test records (0.5 = chance)",
        reference=0.5,
        style="kind",
        group="model",
        xlim=_roc_limits(pd.DataFrame(rows).high),
    )
    cat_test = tests.get("catalonia_crash_severity", "")
    bcn_test = tests.get("barcelona_person_severity", "")
    captions["ml1_test_auc"] = _caption(
        "ROC-AUC of each model, of the descriptive table it was compared with and of a baseline "
        f"that gives every case the same probability, on test records not used to build them "
        f"({cat_test}; {bcn_test}), with 95% intervals for the models",
        REGIONAL_SOURCES,
        f"{int(primary.loc[regional].n.sum()):,} test records",
    )

    featured = _featured_models(selected)
    calibration = table("ml_calibration")
    calibration = calibration.merge(
        primary.loc[featured].reset_index()[["model", "feature_set"]], on=["model", "feature_set"]
    )
    calibration["series"] = calibration.model.map(REGIONAL_MODELS)
    plots.calibration(
        calibration.set_index("model").loc[featured].reset_index(),
        "mean_predicted",
        "observed",
        figures_dir / "ml2_calibration.svg",
        "Calibration on the test records: observed share against predicted probability",
        series="series",
        xlabel="Mean predicted probability in the group",
    )
    groups = calibration.groupby("model").bin.nunique()
    captions["ml2_calibration"] = _caption(
        "Observed share with the outcome against mean predicted probability in equal-size "
        "groups of test records ("
        + "; ".join(f"{REGIONAL_MODELS[m]}: {groups[m]} groups, {tests[m]}" for m in featured)
        + "); on the diagonal, predicted probabilities match observed shares",
        REGIONAL_SOURCES,
        f"{int(calibration.n.sum()):,} test records",
    )

    importance = table("ml_importance")
    for model in featured:
        row = primary.loc[model]
        part = importance[(importance.model == model) & (importance.feature_set == row.feature_set)]
        part = part.head(10).assign(
            variable=lambda d: d.feature.map(feature_label),
            low=lambda d: d.auc_drop_mean - d.auc_drop_std,
            high=lambda d: d.auc_drop_mean + d.auc_drop_std,
        )
        name = REGIONAL_MODELS[model]
        plots.dot_interval(
            part,
            "variable",
            "auc_drop_mean",
            "low",
            "high",
            figures_dir / f"ml3_importance_{model}.svg",
            f"{name}: the variables it relies on most",
            xlabel="Fall in test ROC-AUC when the variable is shuffled",
            reference=0.0,
        )
        captions[f"ml3_importance_{model}"] = _caption(
            f"The {len(part)} variables the {name} relies on most: the mean fall in its ROC-AUC "
            f"on the test records ({tests[model]}) when each variable is randomly shuffled, "
            "over 30 shuffles, with one standard deviation either side",
            MODEL_SOURCES[model],
        )


def transport_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    from dgt_stats.microdata.validation.transport import MIN_POSITIVES

    transport = table("ml_transport_validation")
    reported = transport[
        transport.status.eq("reported") & transport.estimator.ne("baseline_prior")
    ].copy()
    selected = table("ml_selected")
    chosen = selected[selected.primary].set_index("model").estimator
    reported = reported[reported.estimator.eq(reported.model.map(chosen))]
    # The reverse Barcelona test trains the specification on Barcelona city's crashes alone: a
    # model of the city, not the Catalonia model, so it is not drawn with the model's tests.
    best = reported.drop_duplicates(["experiment", "model"])
    best = best[~best.experiment.str.startswith("Barcelona municipality -> rest")]
    calculator = table("gen_calculator_transfer")
    calculator = calculator[~calculator.experiment.str.startswith("random")]
    best = pd.concat([best, calculator], ignore_index=True)
    best["test"] = best.experiment.map(experiment_label)
    # Each test is drawn beside its reference: the same kind of model trained and cross-
    # validated inside the test population, where one exists.
    tested = best.assign(
        row="Model tested",
        kind="focal",
        low=best.roc_auc_low.fillna(best.roc_auc),
        high=best.roc_auc_high.fillna(best.roc_auc),
    )
    references = best[best.in_domain_cv_roc_auc.notna()].assign(
        row="Trained in the test population",
        kind="reference",
        roc_auc=lambda d: d.in_domain_cv_roc_auc,
        low=lambda d: d.in_domain_cv_roc_auc,
        high=lambda d: d.in_domain_cv_roc_auc,
    )
    drawn = pd.concat([tested, references]).sort_index(kind="stable")
    for model, name, title, shown, source in (
        (
            "calculator",
            "tr0_calculator_transfer",
            "The calculator's model on held-out years and places",
            "ROC-AUC of the calculator's model on crashes held out of its fitting (each year from "
            "the years before it, the last year, each province of Catalonia in turn, Barcelona "
            "city from the rest of Catalonia), with 95% intervals, beside the same model fitted "
            "and cross-validated in the test population (hollow)",
            CAT_SOURCE,
        ),
        (
            "catalonia_crash_severity",
            "tr1_catalonia_transfer",
            "Original Catalonia model (retired) on held-out places and years",
            "ROC-AUC of the original Catalonia crash-severity model, retired because it relied on "
            "a recording artefact, on records held out of its training (a later year, each "
            "province of Catalonia in turn, Barcelona city from the rest of Catalonia), with 95% "
            "intervals where computed, beside a model of the same kind trained and "
            "cross-validated in the test population (hollow)",
            CAT_SOURCE,
        ),
        (
            "catalonia_common_dgt",
            "tr2_dgt_transfer",
            "Harmonised Catalonia model on other sources, years and Spain",
            "ROC-AUC of the harmonised Catalonia model (restricted to the variables DGT records "
            "in the same way) on records held out of its training: later years and each province "
            "in the Catalan file, the same crashes in DGT records, and DGT records from Spain "
            "outside Catalonia, with 95% intervals where computed, beside a model of the same "
            "kind trained and cross-validated in the test population (hollow)",
            f"{CAT_SOURCE}; {DGT_SOURCE}",
        ),
    ):
        part = drawn[drawn.model == model]
        plots.dot_interval(
            part,
            "row",
            "roc_auc",
            "low",
            "high",
            figures_dir / f"{name}.svg",
            title,
            xlabel="ROC-AUC on the held-out records",
            reference=0.5,
            reference_label="chance",
            style="kind",
            group="test",
            xlim=_roc_limits(part.high),
        )
        captions[name] = _caption(shown, source)
    provinces = table("ml_transport_provinces")
    provinces = provinces[provinces.reported].copy()
    rates = table("gen_province_rates")
    dgt_period = f"{int(rates.year.min())}–{int(rates.year.max())}"
    names = rates.drop_duplicates("province_code").set_index("province_code").province
    provinces["row"] = (
        provinces.province_code.map(names)
        .map(_province_name, na_action="ignore")
        .fillna(provinces.province_code.astype(str))
        + "  ("
        + provinces.positives.map("{:,}".format)
        + " fatal)"
    )
    provinces["low"] = provinces.roc_auc
    provinces["high"] = provinces.roc_auc
    plots.dot_interval(
        provinces,
        "row",
        "roc_auc",
        "low",
        "high",
        figures_dir / "tr3_province_auc.svg",
        "Harmonised Catalonia model, province by province outside Catalonia",
        xlabel="ROC-AUC on the province's DGT records",
        reference=0.5,
        reference_label="chance",
        xlim=_roc_limits(provinces.high),
    )
    captions["tr3_province_auc"] = _caption(
        "ROC-AUC of the harmonised Catalonia model, trained on the Catalan file, on DGT records "
        "of crashes with a death or serious injury within 24 hours in each province outside "
        f"Catalonia, {dgt_period}; provinces with at least {MIN_POSITIVES} fatal and "
        f"{MIN_POSITIVES} non-fatal "
        "crashes, fatal crashes in brackets",
        DGT_SOURCE,
        f"{int(provinces.n.sum()):,} crashes",
    )


def build(figures_dir: Path, captions: dict[str, str]) -> None:
    """Every regional figure; skipped quietly when the microdata tables are not built."""
    needed = (
        "bcn_crash_severity_share",
        "bcn_frequency",
        "bcn_person_severity_share",
        "cat_fatal_share",
        "cat_frequency",
        "gen_province_rates",
        "ml_calibration",
        "ml_importance",
        "ml_model_decisions",
        "ml_selected",
        "ml_transport_provinces",
        "ml_transport_validation",
        "ml_variants",
    )
    if not all((TABLES_DIR / f"{name}.csv").exists() for name in needed):
        return
    catalonia_figures(figures_dir, captions)
    barcelona_figures(figures_dir, captions)
    model_figures(figures_dir, captions)
    transport_figures(figures_dir, captions)
