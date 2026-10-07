"""Figures for the microdata pages, drawn from the committed result tables with the site's plots.

Every figure is a single-series dot-and-interval or bar chart in the project's fixed palette (or
a calibration chart with one line per model), with its N in the caption, and the same numbers
in a table on the page. Nothing is recomputed here: the tables in ``reports/tables`` are the
input, so a figure cannot disagree with the table beside it.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dgt_stats import plots
from dgt_stats.paths import TABLES_DIR

MIN_N = 30
CAT_SOURCE = "Servei Català de Trànsit, crashes with a death or serious injury"
BCN_SOURCE = "Ajuntament de Barcelona, Guàrdia Urbana crash records"
MODEL_LABELS = {
    "catalonia_crash_severity": "Catalonia: fatal vs serious crash",
    "barcelona_person_severity": "Barcelona: serious or fatal injury, person",
    "barcelona_crash_severity": "Barcelona: serious or fatal crash",
    "catalonia_common_dgt": "Catalonia, DGT-common features",
    "catalonia_common_bcn": "Catalonia, Barcelona-common features",
}
ESTIMATOR_LABELS = {
    "logistic": "logistic",
    "boosted_trees": "boosted trees",
    "baseline_prior": "baseline",
}


def table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


def _labelled(frame: pd.DataFrame, label: str = "label") -> pd.DataFrame:
    frame = frame[frame.n >= MIN_N].copy()
    frame["row"] = frame[label].astype(str) + "  (n=" + frame.n.map("{:,}".format) + ")"
    return frame


def _shares(
    frame: pd.DataFrame,
    dimension: str,
    path: Path,
    title: str,
    xlabel: str,
    reference: float,
    keep_order: bool = False,
    order: list[str] | None = None,
) -> Path:
    block = _labelled(frame[frame.dimension == dimension])
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
    )


def _bars(values: pd.Series, path: Path, title: str, ylabel: str) -> Path:
    plots.apply_style()
    fig, axis = plt.subplots(figsize=(plots.FIGURE_WIDTH, 3.6))
    positions = np.arange(len(values))
    axis.bar(
        positions,
        values.to_numpy(),
        width=0.72,
        color=plots.CATEGORICAL[0],
        edgecolor=plots.SURFACE,
        linewidth=2,
    )
    axis.set_xticks(positions, [str(v) for v in values.index], fontsize=8)
    axis.set_ylabel(ylabel)
    plots._thousands(axis)
    axis.set_title(title)
    return plots.save(fig, path)


def catalonia_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    shares = table("cat_fatal_share")
    overall = shares[(shares.dimension == "unit type involved") & (shares.level == "all")]
    base = float(overall.share.iloc[0])
    n = int(overall.n.iloc[0])
    years = shares[shares.dimension == "year"].level.astype(int)
    period = f"{years.min()}-{years.max()}"
    definition = (
        "share of crashes that were fatal among crashes with a death or serious "
        "injury, with 95% Wilson intervals; categories with fewer than 30 crashes "
        "are left out"
    )
    for name, dimension, title in (
        ("cat1_fatal_by_road", "road type", "Fatal share by road type"),
        (
            "cat2_fatal_by_speed_limit",
            "speed limit",
            "Fatal share by the road's speed limit (posted limits only)",
        ),
        (
            "cat3_fatal_by_unit",
            "unit type involved",
            "Fatal share by type of unit involved (a crash can involve several)",
        ),
        ("cat4_fatal_by_crash_type", "crash subtype", "Fatal share by crash type"),
        ("cat5_fatal_by_lighting", "lighting", "Fatal share by lighting"),
    ):
        _shares(
            shares,
            dimension,
            figures_dir / f"{name}.svg",
            title,
            "Fatal crashes among serious and fatal crashes",
            base,
        )
        captions[name] = plots.caption(CAT_SOURCE, period, definition, n)
    frequency = table("cat_frequency").groupby("year").crashes.sum()
    _bars(
        frequency,
        figures_dir / "cat6_crashes_by_year.svg",
        "Crashes with a death or serious injury, by year",
        "Crashes",
    )
    captions["cat6_crashes_by_year"] = plots.caption(
        CAT_SOURCE,
        period,
        "recorded crashes with at least one death or serious injury (a "
        "count of recorded crashes, not a rate)",
        int(frequency.sum()),
    )


def barcelona_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    people = table("bcn_person_severity_share")
    year = str(people.dataset.iloc[0]).replace("Barcelona ", "")
    road_users = people[people.dimension == "road user"]
    base = float(road_users.events.sum() / road_users.n.sum())
    n = int(road_users.n.sum())
    definition = (
        "share of person records with a serious or fatal injury ('Ferit greu' or "
        "'Mort'), among records with a recorded victimisation, with 95% Wilson "
        "intervals; groups with fewer than 30 records are left out"
    )
    _shares(
        people,
        "road user",
        figures_dir / "bcn1_severity_by_road_user.svg",
        "Serious or fatal injury by road user (role and vehicle type on the record)",
        "Share of person records",
        base,
    )
    captions["bcn1_severity_by_road_user"] = plots.caption(BCN_SOURCE, year, definition, n)
    ages = ["0-15", "16-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"]
    _shares(
        people,
        "age band",
        figures_dir / "bcn2_severity_by_age.svg",
        "Serious or fatal injury by age band",
        "Share of person records",
        base,
        keep_order=True,
        order=ages,
    )
    captions["bcn2_severity_by_age"] = plots.caption(BCN_SOURCE, year, definition, n)
    frequency = table("bcn_frequency")
    hours = frequency[frequency.dimension == "hour"].assign(level=lambda d: d.level.astype(int))
    hours = hours.set_index("level").sort_index().crashes
    _bars(
        hours,
        figures_dir / "bcn3_crashes_by_hour.svg",
        "Recorded crashes by hour of day",
        "Crashes",
    )
    captions["bcn3_crashes_by_hour"] = plots.caption(
        BCN_SOURCE,
        year,
        "crashes attended by the Guàrdia Urbana, by hour (a count of recorded crashes, not a rate)",
        int(hours.sum()),
    )
    crashes = table("bcn_crash_severity_share")
    crash_base = crashes[(crashes.dimension == "cause recorded") & (crashes.level == "all")]
    _shares(
        crashes,
        "crash type",
        figures_dir / "bcn4_crash_severity_by_type.svg",
        "Crashes with a serious or fatal injury, by crash type",
        "Share of crashes",
        float(crash_base.share.iloc[0]),
    )
    captions["bcn4_crash_severity_by_type"] = plots.caption(
        BCN_SOURCE,
        year,
        "share of crashes with at least one death or serious injury, with "
        "95% Wilson intervals; types with fewer than 30 crashes are left out",
        int(crash_base.n.iloc[0]),
    )


def model_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    selected = table("ml_selected")
    variants = table("ml_variants")
    test = variants[(variants.evaluated_on == "test")]
    rows = []
    for row in selected[selected.primary].itertuples():
        block = test[
            (test.model == row.model)
            & (test.feature_set == row.feature_set)
            & (test.geography == row.geography)
        ]
        for v in block.itertuples():
            rows.append(
                {
                    "row": f"{MODEL_LABELS[row.model]}: {ESTIMATOR_LABELS[v.estimator]}",
                    "auc": v.roc_auc,
                    "model": row.model,
                    "estimator": v.estimator,
                }
            )
        rule_path = TABLES_DIR / "ml_rule_comparison.csv"
        if rule_path.exists():
            rules = pd.read_csv(rule_path).set_index("model")
            if row.model in rules.index:
                rows.append(
                    {
                        "row": f"{MODEL_LABELS[row.model]}: table of "
                        f"{rules.loc[row.model, 'rule'].replace('_', ' ')}",
                        "auc": rules.loc[row.model, "rule_roc_auc"],
                        "model": row.model,
                        "estimator": "table",
                    }
                )
    frame = pd.DataFrame(rows)
    ci = selected[selected.primary].set_index("model")
    frame["low"] = frame.auc
    frame["high"] = frame.auc
    for model, row in ci.iterrows():
        mask = (frame.model == model) & (frame.estimator == row.estimator)
        frame.loc[mask, "low"] = row.roc_auc_low
        frame.loc[mask, "high"] = row.roc_auc_high
    plots.dot_interval(
        frame,
        "row",
        "auc",
        "low",
        "high",
        figures_dir / "ml1_test_auc.svg",
        "ROC-AUC on held-out test rows (interval for the selected model)",
        xlabel="ROC-AUC (0.5 = no better than the baseline)",
        reference=0.5,
        reference_label="baseline",
        keep_order=True,
    )
    captions["ml1_test_auc"] = plots.caption(
        "the three feature tables built from the Catalan and Barcelona files",
        "Catalonia tested on its last year; Barcelona on its last three months",
        "area under the ROC curve on rows not used for training or model choice; 95% "
        "bootstrap interval (crashes resampled) for the selected estimator; 'table' rows are a "
        "lookup of outcome shares by group built on the training rows",
        int(selected[selected.primary].n.sum()),
    )
    calibration = table("ml_calibration")
    calibration = calibration.merge(
        selected[selected.primary][["model", "feature_set"]], on=["model", "feature_set"]
    )
    calibration["series"] = calibration.model.map(MODEL_LABELS)
    plots.calibration(
        calibration,
        "mean_predicted",
        "observed",
        figures_dir / "ml2_calibration.svg",
        "Calibration on the test rows: observed share against predicted",
        series="series",
    )
    captions["ml2_calibration"] = plots.caption(
        "the three feature tables",
        "test rows as above",
        "test rows grouped into equal-size bins of predicted probability; a well calibrated "
        "model lies on the diagonal",
        int(calibration.n.sum()),
    )
    importance = table("ml_importance")
    for row in selected[selected.primary].itertuples():
        model = row.model
        part = importance[(importance.model == model) & (importance.feature_set == row.feature_set)]
        part = part.head(10).assign(
            low=lambda d: d.auc_drop_mean - d.auc_drop_std,
            high=lambda d: d.auc_drop_mean + d.auc_drop_std,
        )
        name = f"ml3_importance_{model}"
        plots.dot_interval(
            part,
            "feature",
            "auc_drop_mean",
            "low",
            "high",
            figures_dir / f"{name}.svg",
            f"What the model uses: {MODEL_LABELS[model]}",
            xlabel="Fall in test ROC-AUC when the feature is shuffled",
            reference=0.0,
        )
        captions[name] = plots.caption(
            "the feature table",
            "test rows",
            "permutation importance, mean and one standard deviation over 30 shuffles; it "
            "measures what the model relies on, not what causes severity",
            None,
        )


def transport_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    transport = table("ml_transport_validation")
    reported = transport[
        transport.status.eq("reported") & transport.estimator.ne("baseline_prior")
    ].copy()
    selected = table("ml_selected")
    chosen = selected[selected.primary].set_index("model").estimator
    reported = reported[reported.estimator.eq(reported.model.map(chosen))]
    best = reported.drop_duplicates(["experiment", "model"])
    best["row"] = (
        best.experiment.str.slice(0, 70) + "  (" + best.estimator.map(ESTIMATOR_LABELS) + ")"
    )
    best["low"] = best.roc_auc_low.fillna(best.roc_auc)
    best["high"] = best.roc_auc_high.fillna(best.roc_auc)
    for model, name, title in (
        (
            "catalonia_crash_severity",
            "tr1_catalonia_transfer",
            "Full Catalan model: held-out places and years",
        ),
        (
            "catalonia_common_dgt",
            "tr2_dgt_transfer",
            "DGT-common Catalan model: other sources, years and Spain",
        ),
    ):
        part = best[best.model == model]
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
            reference_label="baseline",
        )
        captions[name] = plots.caption(
            "Catalan file; DGT crash microdata for the cross-source rows",
            "as named in each row",
            "area under the ROC curve on records from the held-out domain, 95% bootstrap "
            "interval; the estimator selected on the model's own validation data",
            None,
        )
    provinces = table("ml_transport_provinces")
    provinces = provinces[provinces.reported].copy()
    rates = table("gen_province_rates")
    dgt_period = f"{int(rates.year.min())}-{int(rates.year.max())}"
    names = rates.drop_duplicates("province_code").set_index("province_code").province
    provinces["row"] = (
        provinces.province_code.map(names).fillna(provinces.province_code.astype(str))
        + "  (fatal "
        + provinces.positives.map("{:,}".format)
        + ")"
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
        "DGT-common Catalan model, province by province outside Catalonia",
        xlabel="ROC-AUC",
        reference=0.5,
        reference_label="baseline",
    )
    captions["tr3_province_auc"] = plots.caption(
        "DGT crash microdata",
        dgt_period,
        "crashes with a death or serious injury within 24 hours, scored by the model trained "
        "on the Catalan file; provinces with at least 30 fatal and 30 non-fatal crashes",
        int(provinces.n.sum()),
    )


def build(figures_dir: Path, captions: dict[str, str]) -> None:
    """Every microdata figure; skipped quietly when the microdata tables are not built."""
    needed = (
        "cat_fatal_share",
        "bcn_person_severity_share",
        "ml_selected",
        "ml_transport_validation",
    )
    if not all((TABLES_DIR / f"{name}.csv").exists() for name in needed):
        return
    catalonia_figures(figures_dir, captions)
    barcelona_figures(figures_dir, captions)
    model_figures(figures_dir, captions)
    transport_figures(figures_dir, captions)
