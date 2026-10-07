"""Supporting analysis: associations in DGT crash records (the crash-severity regressions).

A description of which recorded circumstances go with a fatal outcome in DGT's injury-crash
records, not a predictive model: the project does not train a severity model on DGT's file.

Every number is read from the ``q3_*`` tables that ``scripts/model.py`` writes; the qualitative
sentences are guarded by checks that stop the build when the tables stop supporting them. The
levels that stand for a missing value are nuisance terms (``is_nuisance`` in the tables): they are
reported and explained, never read as an effect.
"""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import features
from dgt_stats.site.components import (
    SUPPORTING_NOTES,
    _fmt_int,
    _fmt_pct,
    _join,
    conclusion,
    downloads,
    figure,
    key_figures,
    limits,
    note,
    read_table,
    render_page,
    table,
)
from dgt_stats.site.numbers import _severity_numbers

# The odds ratios the page quotes, set beside the refit without Cataluña's provinces.
REGIME_ROWS = (
    ("surface", "wet", "Wet road surface"),
    ("junction", "at a junction", "At a junction"),
    ("weather", "rain", "Rain"),
    ("crash_type", "head-on collision", "Head-on collision"),
    ("crash_type", "pedestrian struck", "Pedestrian struck"),
    ("zone", "interurban road", "Interurban zone"),
    ("road", "conventional", "Conventional road"),
    ("alignment", "unknown", "Alignment “unknown” (nuisance)"),
)


def _ci(odds: float, low: float, high: float) -> str:
    return f"{odds:.2f} ({low:.2f}–{high:.2f})"


def page_severity(captions: dict[str, str]) -> str:
    numbers = _severity_numbers()
    adverse = numbers["adverse"]
    coefficients = numbers["coefficients"]
    holdout = numbers["holdout"]
    fatal = coefficients[coefficients.outcome == "fatal"].set_index(["predictor", "level"])
    variants = read_table("q3_adverse_conditions")
    regime = read_table("q3_recording_regime").set_index(["predictor", "level"])
    sensitivity = read_table("q3_regime_sensitivity")
    sensitivity = sensitivity[sensitivity.outcome == "fatal"].set_index(["predictor", "level"])
    stability = read_table("q3_year_stability")
    stability = stability[stability.outcome == "fatal"]
    exclusions = read_table("q3_adverse_exclusions")
    composition = read_table("q3_adverse_composition")

    def orr(variant: str, level: str, frame=adverse) -> str:
        row = frame.loc[(variant, level)]
        return _ci(float(row.odds_ratio), float(row.or_low), float(row.or_high))

    wet_alone = float(adverse.loc[("no_weather", "wet"), "odds_ratio"])
    junction_full = float(adverse.loc[("full", "at a junction"), "odds_ratio"])
    first_year, last_year = int(holdout.first_train_year.min()), int(holdout.last_test_year.max())
    train_span = f"{int(holdout.first_train_year.min())}–{int(holdout.last_train_year.max())}"
    test_span = f"{int(holdout.first_test_year.min())}–{int(holdout.last_test_year.max())}"
    n_variants = variants.variant.nunique()

    # The recording regime: alignment "unknown" and where its crashes are.
    alignment = regime.loc[("alignment", "unknown")]
    others = regime.drop(index=("alignment", "unknown"))
    kept = sensitivity[~sensitivity.is_nuisance.astype(bool)]
    within = int(kept.within_full_interval.astype(bool).sum())
    largest = kept.loc[(kept.ratio_without_to_full - 1).abs().sort_values(ascending=False).index]
    biggest = largest.iloc[0]
    n_excluded = int(kept.n.iloc[0] - kept.n_without.iloc[0])
    nuisance = coefficients[
        (coefficients.outcome == "fatal") & coefficients.is_nuisance.astype(bool)
    ]
    estimated = nuisance[nuisance.odds_ratio.notna()]
    outside_by_year = (~stability.within_full_interval.astype(bool)).groupby(stability.year).sum()
    top_years = sorted(int(year) for year in outside_by_year.nlargest(2).index)
    outside = int(outside_by_year.sum())

    def without(key: tuple[str, str]) -> pd.Series:
        return sensitivity.loc[key]

    checks = {
        "wet conditions go with lower odds of a death": wet_alone < 1
        and float(adverse.loc[("no_weather", "wet"), "or_high"]) < 1,
        "a junction goes with lower odds of a death": float(
            adverse.loc[("full", "at a junction"), "or_high"]
        )
        < 1,
        "the wet-surface effect is below 1 in every variant that has it": bool(
            (adverse.xs("wet", level="level").or_high < 1).all()
        ),
        "the junction effect is present in every stratum": bool(
            (adverse.xs("at a junction", level="level").or_high < 1).all()
        ),
        "hail or snow covers no effect on conventional roads alone": float(
            adverse.loc[("conventional", "hail or snow"), "or_low"]
        )
        < 1
        < float(adverse.loc[("conventional", "hail or snow"), "or_high"]),
        "dropping the provinces that record most hail or snow keeps it below 1": float(
            exclusions.iloc[-1].or_high
        )
        < 1,
        "alignment unknown is mostly Catalan": float(alignment.catalan_share_of_level) > 0.9
        and float(alignment.share_of_catalan_crashes)
        > 10 * float(alignment.share_of_other_crashes),
        "the other missing levels are almost all outside Cataluña": bool(
            (others.catalan_share_of_level < 0.01).all()
        ),
        "wet and junction survive the refit without Cataluña": all(
            float(without(key).or_high_without) < 1
            for key in (("surface", "wet"), ("junction", "at a junction"))
        ),
        "the largest move without Cataluña is in zone or road type": biggest.name[0]
        in ("zone", "road"),
        "alignment unknown moves out of its interval without Cataluña": not bool(
            without(("alignment", "unknown")).within_full_interval
        ),
        "the year-by-year departures are most frequent in the coding-break years": top_years
        == [2023, 2024],
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"severity page: the tables no longer support: {failed}")

    fatal_holdout, serious_holdout = holdout.loc["fatal"], holdout.loc["serious"]
    # The missing-value levels are among the strongest terms of the fatal regression: one
    # reason the file is used to describe associations and not to train a predictive model.
    ranked = fatal[(fatal.index.get_level_values("predictor") != "year")].dropna(
        subset=["odds_ratio"]
    )
    ranked = ranked[~ranked.is_reference.astype(bool)]
    strongest = ranked.reindex(
        ranked.odds_ratio.map(lambda v: abs(math.log(v))).sort_values(ascending=False).index
    )
    if not strongest.head(3).is_nuisance.astype(bool).any():
        raise ValueError("severity page: no missing-value level is among the strongest terms")
    top_nuisance = strongest[strongest.is_nuisance.astype(bool)].iloc[0]
    body = key_figures(
        [
            (
                "Injury crashes described",
                f"{numbers['n']:,}",
                f"{first_year}–{last_year}, none dropped",
            ),
            ("Fatal", _fmt_pct(numbers["fatal_share"], 2), "at least one death within 30 days"),
            (
                "Wet road, fatal odds",
                f"{wet_alone:.2f}×",
                "against a dry road, everything else held constant",
            ),
            (
                "Holdout check, fatal",
                f"{numbers['auc_fatal']:.2f}",
                f"area under the ROC curve: {train_span} associations scored on {test_span}",
            ),
        ]
    )

    body += (
        '<p class="answer">Once an injury crash has happened, the conditions a driver would '
        "call dangerous go with a <em>lower</em> chance that someone dies. A wet road carries "
        f"{wet_alone:.2f} times the odds of a death of a dry one, a junction {junction_full:.2f} "
        "times the odds of a stretch away from one. Rain and a wet surface are one effect counted "
        "twice, worth about "
        f"{wet_alone:.2f} on its own. These are associations in the police record of crashes "
        "that happened, given an injury crash. It says nothing about how often crashes happen.</p>"
        "<p>This page describes associations in DGT's records; it is not the project's "
        "predictive model. Levels that record a missing value rather than what happened are "
        "among the strongest terms of the regression ("
        f"{str(top_nuisance.predictor_label).lower()} “{top_nuisance.name[1]}”, odds ratio "
        f"{float(top_nuisance.odds_ratio):.2f}), which is one reason DGT's file is used here to "
        "describe associations and not to train a model that predicts severity.</p>"
    )

    body += "<h2>Testing the finding</h2>"
    body += (
        "<p>The description is two logistic regressions on every injury crash of "
        f"{first_year} to {last_year}, one for a death and one for a death or a "
        "hospitalisation. The predictors are the circumstances the police record: zone, road "
        "type, crash type, junction, lighting, weather, surface, alignment, time of day, "
        "weekend, number of vehicles and year.</p>"
        "<p>The first objection is that weather and road surface measure much the same thing, so "
        "a model carrying both splits one effect between two columns. That is what happens. With "
        f"surface dropped, rain moves from {orr('full', 'rain')} to {orr('no_surface', 'rain')}. "
        f"With weather dropped, a wet surface moves from {orr('full', 'wet')} to "
        f"{orr('no_weather', 'wet')}. The right reading is a single wet-conditions effect of "
        f"about {wet_alone:.2f}.</p>"
    )
    body += (
        "<p>The second objection is that adverse weather falls in particular places. Fitting "
        "interurban roads and urban streets separately holds the road context fixed instead of "
        f"adjusting for it. The wet-surface effect stays: {orr('interurban', 'wet')} on interurban "
        f"roads and {orr('street', 'wet')} on urban streets. The junction effect, "
        f"{orr('full', 'at a junction')} overall, is present in every stratum too. Hail and snow "
        f"behave differently. They give {orr('full', 'hail or snow')} in the full model but "
        f"{orr('conventional', 'hail or snow')} on conventional roads alone, where the interval "
        "covers no effect at all.</p>"
    )
    body += figure(
        "s2_adverse_conditions",
        f"Odds ratios for wet, rain, hail or snow and junctions under {n_variants} model variants",
        captions,
    )

    shown = variants[variants.outcome.isin(["fatal", "serious"])].copy()
    shown["ci"] = shown.apply(lambda r: _ci(r.odds_ratio, r.or_low, r.or_high), axis=1)
    wide = shown.pivot_table(
        index=["variant_label", "level"], columns="outcome", values="ci", aggfunc="first"
    ).reset_index()
    wide = wide.rename(
        columns={
            "variant_label": "Model",
            "level": "Condition",
            "fatal": "Fatal (95% interval)",
            "serious": "Serious (95% interval)",
        }
    )
    order = list(dict.fromkeys(variants.variant_label))
    conditions = ["wet", "rain", "hail or snow", "at a junction"]
    wide["_model"] = wide.Model.map({label: i for i, label in enumerate(order)})
    wide["_condition"] = wide.Condition.map({name: i for i, name in enumerate(conditions)})
    wide = wide.sort_values(["_condition", "_model"]).drop(columns=["_model", "_condition"])
    body += table(
        wide,
        "Odds ratios for the adverse conditions under every model variant, both outcomes. A blank "
        "cell is a level the variant does not contain",
    )
    body += downloads(
        [
            ("q3_adverse_conditions", "sensitivity fits"),
            ("q3_adverse_composition", "where hail and snow crashes happen"),
            ("q3_adverse_exclusions", "hail and snow with the top provinces removed"),
        ]
    )

    snow = composition[(composition.level == "hail or snow") & (composition.dimension == "zone")]
    interurban_share = float(snow[snow.category == "interurban road"].share_of_level.iloc[0])
    widest = exclusions.iloc[-1]
    body += (
        f"<p>Hail and snow are only "
        f"{int(adverse.loc[('full', 'hail or snow'), 'n_level']):,} crashes, and "
        f"{interurban_share:.0%} of them are on interurban roads, so it is fair to suspect a few "
        f"mountain provinces. That is not what the data show. Dropping the "
        f"{int(widest.n_excluded)} provinces that record most of them moves the odds ratio only "
        f"to {_ci(float(widest.odds_ratio), float(widest.or_low), float(widest.or_high))}. The "
        "road type is what moves it, and on conventional roads alone the effect disappears.</p>"
    )

    body += "<h2>Missing values and who recorded the crash</h2>"
    body += (
        "<p>Some levels stand for a missing value: a field's own “unknown” code or “not "
        "specified”. They describe how the form was filled in, which differs between police "
        "forces and years, so they are in the model only so that no crash is dropped. They are "
        "flagged as nuisance terms in the coefficient tables (<code>is_nuisance</code>) and left "
        "out of the figure below and of every headline. One of them sits almost entirely in one "
        "place: road alignment “unknown” is "
        f"{_fmt_pct(float(alignment.share_of_catalan_crashes))} of the crashes in Cataluña's "
        f"four provinces against {_fmt_pct(float(alignment.share_of_other_crashes))} elsewhere, "
        f"so {_fmt_pct(float(alignment.catalan_share_of_level))} of its "
        f"{_fmt_int(alignment.crashes)} crashes are Catalan, while Cataluña has "
        f"{_fmt_pct(float(alignment.catalan_share_of_all_crashes))} of all crashes. Its odds "
        f"ratio, {float(fatal.loc[('alignment', 'unknown'), 'odds_ratio']):.2f}, cannot be read "
        "as a property of the road: it marks crashes recorded mostly by Cataluña's forces. The "
        "weather and surface "
        "unknowns are almost all outside Cataluña (at most "
        f"{_fmt_pct(float(others.catalan_share_of_level.max()), 2)} Catalan).</p>"
    )
    body += (
        "<p>A recording practice that goes with the outcome could lean on the other "
        "coefficients through such a level, so the fatal model was refitted without Cataluña's "
        f"{_fmt_int(n_excluded)} crashes. "
        + (
            f"All {len(kept)} other odds ratios stay"
            if within == len(kept)
            else f"Of the {len(kept)} other odds ratios, {within} stay"
        )
        + " inside the full model's interval. The largest moves are in zone and road type, which "
        f"have to be read together: {biggest.predictor_label.lower()} “{biggest.name[1]}” goes "
        f"from {float(biggest.odds_ratio):.2f} to {float(biggest.odds_ratio_without):.2f}. The "
        f"wet-surface ratio moves from {float(without(('surface', 'wet')).odds_ratio):.2f} to "
        f"{float(without(('surface', 'wet')).odds_ratio_without):.2f} and the junction ratio "
        f"from {float(without(('junction', 'at a junction')).odds_ratio):.2f} to "
        f"{float(without(('junction', 'at a junction')).odds_ratio_without):.2f}, both still "
        "below 1; alignment “unknown” itself moves from "
        f"{float(without(('alignment', 'unknown')).odds_ratio):.2f} to "
        f"{float(without(('alignment', 'unknown')).odds_ratio_without):.2f} once most of its "
        "crashes are gone.</p>"
    )
    regime_rows = [
        {
            "Circumstance": label,
            "Full model": _ci(
                float(without((predictor, level)).odds_ratio),
                float(without((predictor, level)).or_low),
                float(without((predictor, level)).or_high),
            ),
            "Without Cataluña": _ci(
                float(without((predictor, level)).odds_ratio_without),
                float(without((predictor, level)).or_low_without),
                float(without((predictor, level)).or_high_without),
            ),
        }
        for predictor, level, label in REGIME_ROWS
    ]
    body += table(
        pd.DataFrame(regime_rows),
        "Odds of a fatal outcome in the full model and refitted without the crashes of "
        "Barcelona, Girona, Lleida and Tarragona, with 95% intervals clustered by province",
    )
    body += downloads(
        [
            ("q3_recording_regime", "missing-value levels in Cataluña and elsewhere"),
            ("q3_regime_sensitivity", "every odds ratio with and without Cataluña"),
        ]
    )

    body += "<h2>The other coefficients</h2>"
    body += figure(
        "s1_forest_fatal",
        "Odds ratios for a fatal outcome by crash circumstance, with 95% intervals",
        captions,
    )
    head_on = fatal.loc[("crash_type", "head-on collision")]
    pedestrian = fatal.loc[("crash_type", "pedestrian struck")]
    body += (
        "<p>The large ratios are for the kind of crash. A head-on collision carries "
        f"{head_on.odds_ratio:.1f} times the odds of a death of a side collision, and a pedestrian "
        f"struck {pedestrian.odds_ratio:.1f} times, against {junction_full:.2f} for a junction and "
        f"{wet_alone:.2f} for a wet road. As a check that the associations carry across "
        f"years, the regressions were fitted on {train_span} without a year term and scored on "
        f"{test_span}: the area under the ROC curve is {numbers['auc_fatal']:.2f} for a death "
        f"and {numbers['auc_serious']:.2f} for a death or a hospitalisation, far better than "
        "chance at ranking, while the fitted probabilities improve little on the training "
        "years' share of each outcome given to every crash: the Brier score is "
        f"{_fmt_pct(float(fatal_holdout.brier_skill))} better for a death and "
        f"{_fmt_pct(float(serious_holdout.brier_skill))} better for a death or a "
        "hospitalisation.</p>"
    )
    profiles = read_table("q3_profiles").rename(
        columns={"profile": "Crash profile", "fatal": "Fatal", "serious": "Serious"}
    )
    body += table(
        profiles,
        f"Fitted share of each outcome for named crash profiles ({last_year}; circumstances "
        "not named are at their reference level): the associations combined for illustration, "
        "not a prediction",
        {"Fatal": "pct2", "Serious": "pct"},
    )
    body += downloads(
        [
            ("q3_model_coefficients", "all coefficients"),
            ("q3_marginal_effects", "average marginal effects"),
            ("q3_holdout_summary", "holdout scores"),
            ("q3_calibration", "holdout calibration"),
            ("q3_year_stability", "year-by-year refits"),
            ("q3_groupings", "how DGT's codes map to model levels"),
        ]
    )

    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Wet conditions and junctions are associated with materially lower odds that an injury "
        f"crash kills someone: about {wet_alone:.2f} and {junction_full:.2f} times the reference "
        "odds, holding the other recorded circumstances constant. Both survive every sensitivity "
        "fit run here, the refit without Cataluña's recording included, so treat them as "
        "established associations in the record. The hail and snow result does not survive, so "
        "treat it as unresolved. The levels that stand for a missing value are not findings. "
        "None of this identifies a mechanism, and none of it says anything about how likely a "
        "crash is in the first place."
    )

    years_text = _join([str(year) for year in top_years])
    body += limits(
        "DGT's national microdata are one row per crash with no driver, vehicle or person "
        "fields, so nothing here says who was driving, how fast or whether alcohol was involved, "
        "and no mechanism for any of these associations can be tested with them. A model of "
        "recorded crashes describes which recorded crashes end badly, not the risk of crashing. "
        f"Refitting one year at a time, {outside} of the {len(stability)} year-by-term estimates "
        f"fall outside the full model's interval, the most in {years_text} ("
        f"{_join([str(int(outside_by_year.loc[year])) for year in top_years])}), when DGT "
        'changed how junctions and urban road types are coded (see the <a href="data.html">data '
        "page</a>); road type and zone have to be read together. The levels that stand for a "
        f"missing value, {len(nuisance)} of them ({len(estimated)} estimated, "
        f"{len(nuisance) - len(estimated)} with too few events or repeating another column), are "
        "flagged in the coefficient table. Levels with fewer than "
        f"{features.MIN_LEVEL_CRASHES} crashes are merged into their reference: on all years for "
        "the full model, on the training years alone for the holdout check."
    )
    return render_page(
        "severity",
        "Associations in DGT crash records",
        "Which recorded circumstances go with a fatal outcome once an injury crash has "
        "happened, and how those associations hold up under sensitivity fits: a description "
        "of DGT's records, not a predictive model.",
        note(SUPPORTING_NOTES["severity"]) + body,
    )
