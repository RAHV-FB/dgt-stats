"""Crash circumstances and fatal outcomes: associations in DGT's national crash records.

A description of which recorded circumstances go with a fatal outcome in DGT's injury-crash
records (the crash-severity regressions). The project does not train a predictive model on DGT's
file: its audit keeps it out.

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
from dgt_stats.site.numbers import _severity_numbers

# The odds ratios set beside the refit without Catalonia's provinces, with reader-facing labels.
REGIME_ROWS = (
    ("surface", "wet", "Wet road surface"),
    ("junction", "at a junction", "At a junction"),
    ("weather", "rain", "Rain"),
    ("crash_type", "head-on collision", "Head-on collision"),
    ("crash_type", "pedestrian struck", "Pedestrian struck"),
    ("zone", "interurban road", "Interurban road (zone)"),
    ("road", "conventional", "Conventional road (road type)"),
    ("alignment", "unknown", "Alignment unknown (missing value)"),
)

CONDITION_LABELS = {
    "wet": "Wet surface",
    "rain": "Rain",
    "hail or snow": "Hail or snow",
    "at a junction": "At a junction",
}

# The profile labels in ``q3_profiles`` use DGT's Spanish name for a dual carriageway.
PROFILE_TERMS = {"Autovía": "Dual carriageway"}

# A fall of more than this in the share of crashes with an empty junction-type field, from one
# year to the next, marks the year DGT began to code junctions differently (as on data.html).
JUNCTION_BREAK_DROP = 0.05

NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")


def _ci(odds: float, low: float, high: float) -> str:
    return f"{odds:.2f} ({low:.2f}–{high:.2f})"


def _count(value: int) -> str:
    """A count in words below ten, as house style asks in running prose."""
    return NUMBER_WORDS[value] if 0 <= value < len(NUMBER_WORDS) else _fmt_int(value)


def _coding_break_years() -> tuple[int, int]:
    """The year the junction fields were first coded differently, and the year most crashes coded
    as road type "other" became urban, both read from the tables behind data.html's coding breaks."""
    missing = read_table("missingness_by_year")
    info = missing[missing.column == "NUDO_INFO"].set_index("year").share_empty.sort_index()
    drops = info.diff()
    junction = [int(year) for year in drops[drops < -JUNCTION_BREAK_DROP].index]
    other = read_table("q2_other_road_by_period")
    earlier, later = other.iloc[0], other.iloc[-1]
    if (
        len(junction) != 1
        or not str(later.period).isdigit()
        or not float(later.street_share) > 0.5 > float(earlier.street_share)
    ):
        raise ValueError("severity page: the coding breaks are no longer one year each")
    return junction[0], int(later.period)


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
    audit = read_table("dgt_audit_checks")
    selected = read_table("ml_selected")
    catalonia_model = selected[selected.primary].set_index("model").loc["catalonia_crash_severity"]

    def orr(variant: str, level: str, frame=adverse) -> str:
        row = frame.loc[(variant, level)]
        return _ci(float(row.odds_ratio), float(row.or_low), float(row.or_high))

    wet_alone = float(adverse.loc[("no_weather", "wet"), "odds_ratio"])
    wet_full = float(adverse.loc[("full", "wet"), "odds_ratio"])
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

    # The yearly refits: which years depart most from the full model, and the coding breaks.
    outside_by_year = (~stability.within_full_interval.astype(bool)).groupby(stability.year).sum()
    top_years = sorted(int(year) for year in outside_by_year.nlargest(2).index)
    rest_of_years = outside_by_year.drop(index=top_years)
    outside = int(outside_by_year.sum())
    outside_by_term = (
        (~stability.within_full_interval.astype(bool)).groupby(stability.predictor_label).sum()
    )
    terms = stability[["predictor", "level"]].drop_duplicates()
    term_labels = list(dict.fromkeys(stability.predictor_label.str.lower().str.replace(" ", "-")))
    junction_break, road_type_break = _coding_break_years()

    # Where crashes in the rain happen, against all crashes.
    rain_zone = composition[(composition.level == "rain") & (composition.dimension == "zone")]
    rain_interurban = rain_zone[rain_zone.category == "interurban road"].iloc[0]
    snow = composition[(composition.level == "hail or snow") & (composition.dimension == "zone")]
    snow_interurban = float(snow[snow.category == "interurban road"].share_of_level.iloc[0])
    widest = exclusions.iloc[-1]
    snow_variants = adverse.xs("hail or snow", level="level").dropna(subset=["odds_ratio"])

    def without(key: tuple[str, str]) -> pd.Series:
        return sensitivity.loc[key]

    ranked = coefficients[
        (coefficients.outcome == "fatal")
        & ~coefficients.is_nuisance.astype(bool)
        & ~coefficients.is_reference.astype(bool)
    ].sort_values("odds_ratio", ascending=False)
    # The strongest terms by distance from 1 on the multiplicative scale, year terms aside.
    strength = fatal[(fatal.index.get_level_values("predictor") != "year")].dropna(
        subset=["odds_ratio"]
    )
    strength = strength[~strength.is_reference.astype(bool)]
    strongest = strength.reindex(
        strength.odds_ratio.map(lambda v: abs(math.log(v))).sort_values(ascending=False).index
    )
    top_nuisance = strongest[strongest.is_nuisance.astype(bool)].iloc[0]
    fatal_holdout, serious_holdout = holdout.loc["fatal"], holdout.loc["serious"]

    checks = {
        "the audit keeps DGT's file out of model training": not str(
            audit.decision.iloc[0]
        ).startswith("DGT microdata may train"),
        "the two largest odds ratios are a head-on collision and a pedestrian struck": set(
            zip(ranked.predictor.iloc[:2], ranked.level.iloc[:2], strict=True)
        )
        == {("crash_type", "head-on collision"), ("crash_type", "pedestrian struck")},
        "leaving out surface strengthens rain, and leaving out weather strengthens wet": float(
            adverse.loc[("no_surface", "rain"), "odds_ratio"]
        )
        < float(adverse.loc[("full", "rain"), "odds_ratio"])
        and wet_alone < wet_full,
        "rain alone and a wet surface alone give about the same odds ratio": abs(
            math.log(float(adverse.loc[("no_surface", "rain"), "odds_ratio"]) / wet_alone)
        )
        < 0.1,
        "wet conditions go with lower odds of a death": wet_alone < 1
        and float(adverse.loc[("no_weather", "wet"), "or_high"]) < 1,
        "a junction goes with lower odds of a death": float(
            adverse.loc[("full", "at a junction"), "or_high"]
        )
        < 1,
        "the wet-surface odds ratio is below 1 in every variant that has it": bool(
            (adverse.xs("wet", level="level").or_high < 1).all()
        ),
        "the junction association is present in every variant": bool(
            (adverse.xs("at a junction", level="level").or_high < 1).all()
        ),
        "crashes in the rain lie on interurban roads more often than crashes overall": float(
            rain_interurban.share_of_level
        )
        > float(rain_interurban.share_overall),
        "hail or snow covers no difference on conventional roads alone": float(
            adverse.loc[("conventional", "hail or snow"), "or_low"]
        )
        < 1
        < float(adverse.loc[("conventional", "hail or snow"), "or_high"]),
        "and in no other variant": bool(
            (snow_variants.drop(index="conventional").or_high < 1).all()
        ),
        "dropping the provinces that record most hail or snow keeps it below 1": float(
            widest.or_high
        )
        < 1,
        "and inside the full model's interval": float(
            adverse.loc[("full", "hail or snow"), "or_low"]
        )
        <= float(widest.odds_ratio)
        <= float(adverse.loc[("full", "hail or snow"), "or_high"]),
        "a missing-value level is among the three strongest terms": bool(
            strongest.head(3).is_nuisance.astype(bool).any()
        ),
        "that level is alignment unknown": top_nuisance.name == ("alignment", "unknown"),
        "alignment unknown is mostly Catalan": float(alignment.catalan_share_of_level) > 0.9
        and float(alignment.share_of_catalan_crashes)
        > 10 * float(alignment.share_of_other_crashes),
        "the other missing levels are almost all outside Catalonia": bool(
            (others.catalan_share_of_level < 0.01).all()
        ),
        "wet and junction survive the refit without Catalonia": all(
            float(without(key).or_high_without) < 1
            for key in (("surface", "wet"), ("junction", "at a junction"))
        ),
        "the three largest moves without Catalonia are in zone or road type": all(
            predictor in ("zone", "road")
            for predictor in largest.index.get_level_values("predictor")[:3]
        ),
        "alignment unknown moves out of its interval without Catalonia": not bool(
            without(("alignment", "unknown")).within_full_interval
        ),
        "the fatal regression keeps its ordering of later years' crashes": numbers["auc_fatal"]
        >= 0.75
        and numbers["auc_serious"] > 0.5,
        "the Catalonia crash-severity model's crashes are already selected for severity": float(
            catalonia_model.prevalence
        )
        > 5 * float(numbers["fatal_share"]),
        "the fitted probabilities improve little on the base rate": float(fatal_holdout.brier_skill)
        < 0.1
        and float(serious_holdout.brier_skill) < 0.1,
        "the two years with most departures each have more than any other year": int(
            outside_by_year.loc[top_years].min()
        )
        > int(rest_of_years.max()),
        "those are the years of the junction and road-type coding breaks": top_years
        == sorted({junction_break, road_type_break})
        and len(top_years) == 2,
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"severity page: the tables no longer support: {failed}")

    head_on = fatal.loc[("crash_type", "head-on collision")]
    pedestrian = fatal.loc[("crash_type", "pedestrian struck")]

    body = summary(
        "Among the injury crashes in DGT's national records, a death was most strongly "
        "associated with the type of crash: compared with a side collision, a head-on "
        f"collision had {float(head_on.odds_ratio):.2f} times the odds of a death and a "
        f"pedestrian struck {float(pedestrian.odds_ratio):.2f} times, other recorded "
        "circumstances held equal. Crashes in wet conditions and at junctions were less often "
        f"fatal than otherwise similar crashes: {wet_alone:.2f} times the odds of a death for "
        f"wet conditions and {junction_full:.2f} times at a junction. An odds ratio of 1 would "
        "mean no difference. These are associations in police records of crashes that "
        "happened, given that an injury crash occurred. They say nothing about how often crashes "
        "happen, and they do not show why some crashes are deadlier."
    )

    body += "<h2>The records and the regression</h2>"
    body += (
        f"<p>DGT's national records hold {_fmt_int(numbers['n'])} injury crashes for "
        f"{first_year}–{last_year}, of which {_fmt_pct(numbers['fatal_share'])} had at least "
        "one death within 30 days. The file has one row per crash and no fields for drivers, "
        "vehicles or people. Its fields are recorded too unevenly between provinces to train a "
        'predictive model (<a href="sources.html">data sources and scope</a>), but they can '
        "describe associations. Two logistic regressions are fitted, one for at least one death "
        "within 30 days and one for a death or a hospitalisation; an odds ratio compares the "
        "odds of the outcome with a circumstance present and without it, holding the other "
        "circumstances equal. The circumstances are those the police record: zone, "
        "road type, crash type, junction, lighting, weather, road surface, alignment, time of "
        "day, weekend, number of vehicles and year. A missing value is kept as a level of its "
        "own, so no crash is dropped, and levels with fewer than "
        f"{_fmt_int(features.MIN_LEVEL_CRASHES)} crashes are merged into their reference "
        "category. The intervals are 95% confidence intervals, with standard errors clustered "
        "by province.</p>"
    )

    body += "<h2>Wet conditions and junctions</h2>"
    body += (
        "<p>Weather and road surface record much the same thing, so a model that contains both "
        "divides one association between them. With road surface left out, the odds ratio for "
        f"rain moves from {orr('full', 'rain')} to {orr('no_surface', 'rain')}; with weather "
        f"left out, the odds ratio for a wet surface moves from {orr('full', 'wet')} to "
        f"{orr('no_weather', 'wet')}. Rain and a wet surface are therefore one wet-conditions "
        f"association of about {wet_alone:.2f}, the figure given above. The full model's "
        f"{wet_full:.2f} for a wet surface, with rain alongside it, is the value in the tables "
        "below and in the refit without Catalonia.</p>"
    )
    body += (
        "<p>Wet weather is also unevenly spread across roads: "
        f"{_fmt_pct(float(rain_interurban.share_of_level), 0)} of crashes in the rain are on "
        f"interurban roads, against {_fmt_pct(float(rain_interurban.share_overall), 0)} of all "
        "crashes. Fitting interurban roads and urban streets separately holds that context "
        f"fixed: the wet-surface odds ratio is {orr('interurban', 'wet')} on interurban roads "
        f"and {orr('street', 'wet')} on urban streets. Its interval lies below 1 in every model "
        "variant, and so does that of the junction association, "
        f"{orr('full', 'at a junction')} in the full model.</p>"
    )
    body += figure(
        "s2_adverse_conditions",
        "Odds ratios of a death for a wet surface, rain, hail or snow and a junction under "
        f"each of {_count(n_variants)} model variants, with 95% intervals.",
        captions,
    )
    body += (
        "<p>Hail and snow behave differently. Their odds ratio is "
        f"{orr('full', 'hail or snow')} in the full model but "
        f"{orr('conventional', 'hail or snow')} on conventional roads alone, where the interval "
        "includes 1. Hail and snow are recorded in only "
        f"{_fmt_int(adverse.loc[('full', 'hail or snow'), 'n_level'])} crashes, "
        f"{_fmt_pct(snow_interurban, 0)} of them on interurban roads, so a handful of provinces "
        f"could drive the result. Removing the {_count(int(widest.n_excluded))} provinces that "
        "record most of them leaves the odds ratio at "
        f"{_ci(float(widest.odds_ratio), float(widest.or_low), float(widest.or_high))}, "
        "inside the full model's interval.</p>"
    )

    shown = variants[variants.outcome.isin(["fatal", "serious"])].copy()
    shown["ci"] = shown.apply(lambda r: _ci(r.odds_ratio, r.or_low, r.or_high), axis=1)
    wide = shown.pivot_table(
        index=["variant_label", "level"], columns="outcome", values="ci", aggfunc="first"
    ).reset_index()
    order = list(dict.fromkeys(variants.variant_label))
    wide["_model"] = wide.variant_label.map({label: i for i, label in enumerate(order)})
    wide["_condition"] = wide.level.map({name: i for i, name in enumerate(CONDITION_LABELS)})
    wide = wide.sort_values(["_condition", "_model"])
    wide = pd.DataFrame(
        {
            "Condition": wide.level.map(CONDITION_LABELS),
            "Model variant": wide.variant_label,
            "Death (95% interval)": wide.fatal,
            "Death or hospitalisation (95% interval)": wide.serious,
        }
    )
    body += technical(
        "Odds ratios under every model variant, for both outcomes",
        table(
            wide,
            "Odds ratios for the adverse conditions under every model variant, for a death and "
            "for a death or hospitalisation. A blank cell is a condition the variant does not "
            "contain.",
        ),
    )

    body += "<h2>Missing values and regional recording</h2>"
    body += (
        "<p>Some levels stand for a missing value, a field's “unknown” or “not specified” "
        "code. They stay in the regression but are left out of the figures and of the results "
        "in the text. One of them is among the strongest terms in the whole regression, and it "
        "sits "
        "almost entirely in one region. Road alignment “unknown”, with an odds ratio of "
        f"{float(fatal.loc[('alignment', 'unknown'), 'odds_ratio']):.2f}, is recorded for "
        f"{_fmt_pct(float(alignment.share_of_catalan_crashes))} of crashes in Catalonia "
        f"against {_fmt_pct(float(alignment.share_of_other_crashes))} elsewhere: "
        f"{_fmt_pct(float(alignment.catalan_share_of_level))} of its "
        f"{_fmt_int(alignment.crashes)} crashes are Catalan, although Catalonia has "
        f"{_fmt_pct(float(alignment.catalan_share_of_all_crashes))} of all crashes. The odds "
        "ratio marks crashes recorded mostly by Catalonia's police forces: it describes "
        "recording practice. The other missing-value levels are almost all outside Catalonia "
        f"(at most {_fmt_pct(float(others.catalan_share_of_level.max()), 2)} Catalan).</p>"
    )
    body += (
        "<p>A recording practice that goes with the outcome could distort the other "
        "coefficients through such a level, so the fatal-outcome regression was refitted "
        f"without Catalonia's {_fmt_int(n_excluded)} crashes. "
        + (
            f"All {len(kept)} other odds ratios stay"
            if within == len(kept)
            else f"Of the {len(kept)} other odds ratios, {within} stay"
        )
        + " inside the full model's interval. The largest moves are in zone and road type, "
        "which have to be read together: for the "
        f"{str(biggest.predictor_label).lower()} “{biggest.name[1]}”, the odds ratio goes from "
        f"{float(biggest.odds_ratio):.2f} to {float(biggest.odds_ratio_without):.2f}. The "
        f"wet-surface odds ratio moves from {float(without(('surface', 'wet')).odds_ratio):.2f} "
        f"to {float(without(('surface', 'wet')).odds_ratio_without):.2f} and the junction odds "
        f"ratio from {float(without(('junction', 'at a junction')).odds_ratio):.2f} to "
        f"{float(without(('junction', 'at a junction')).odds_ratio_without):.2f}, both still "
        "below 1, while alignment “unknown” itself moves from "
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
            "Without Catalonia": _ci(
                float(without((predictor, level)).odds_ratio_without),
                float(without((predictor, level)).or_low_without),
                float(without((predictor, level)).or_high_without),
            ),
        }
        for predictor, level, label in REGIME_ROWS
    ]
    body += technical(
        "Selected odds ratios with and without Catalonia's crashes",
        table(
            pd.DataFrame(regime_rows),
            "Odds ratios for a death in the full model and refitted without Catalonia's "
            "crashes, with 95% intervals clustered by province.",
        ),
    )

    body += "<h2>All recorded circumstances</h2>"
    profiles = read_table("q3_profiles")
    for spanish, english in PROFILE_TERMS.items():
        profiles["profile"] = profiles.profile.str.replace(spanish, english, regex=False)
    lowest = profiles.loc[profiles.fatal.idxmin()]
    highest = profiles.loc[profiles.fatal.idxmax()]
    body += (
        "<p>The figure gives the odds ratio of every recorded circumstance against its "
        "reference level. Combined for illustrative crash profiles in "
        f"{last_year}, with every circumstance not named at its reference level, they give a "
        f"fitted probability of a death from {_fmt_pct(float(lowest.fatal))} "
        f"({str(lowest.profile).lower()}) to {_fmt_pct(float(highest.fatal))} "
        f"({str(highest.profile).lower()}).</p>"
    )
    body += figure(
        "s1_forest_fatal",
        "Odds ratios of a death for each recorded circumstance against its reference level, "
        "with 95% intervals.",
        captions,
    )
    profiles = profiles.rename(
        columns={
            "profile": "Crash profile",
            "fatal": "Death",
            "serious": "Death or hospitalisation",
        }
    )
    body += table(
        profiles,
        f"Fitted probability of each outcome for illustrative crash profiles in {last_year}. "
        "Circumstances not named are at their reference level.",
        {"Death": "pct", "Death or hospitalisation": "pct"},
    )

    body += technical(
        "How stable the associations are over time",
        f"<p>Fitted on {train_span} without a year term and applied to the crashes of "
        f"{test_span}, the fatal-outcome regression keeps its ordering of crashes: ROC-AUC "
        f"{numbers['auc_fatal']:.2f} for a death and {numbers['auc_serious']:.2f} for a death "
        "or a hospitalisation (0.5 is chance and 1 a perfect ranking). This is not the task of "
        'the <a href="severity-models.html">Catalonia crash-severity model</a>, whose ROC-AUC of '
        f"{float(catalonia_model.roc_auc):.2f} picks out deaths among crashes already selected "
        "for a death or serious injury; here the deaths are picked out among all injury "
        f"crashes, of which {_fmt_pct(numbers['fatal_share'])} were fatal. As probabilities, the "
        "fitted values improve little on giving every crash the training years' share of each "
        "outcome: their Brier score (mean squared error) is "
        f"{_fmt_pct(float(fatal_holdout.brier_skill))} lower for a death and "
        f"{_fmt_pct(float(serious_holdout.brier_skill))} lower for a death or a "
        "hospitalisation.</p>"
        "<p>Refitted one year at a time, "
        f"{outside} of the {len(stability)} yearly estimates for the regression's {len(terms)} "
        f"{_join(term_labels)} terms fall outside the full model's interval, more in "
        f"{_join([str(year) for year in top_years])} than in any other year ("
        f"{_join([str(int(outside_by_year.loc[year])) for year in top_years])}): the years in "
        "which the coding of junctions and of urban road types changed "
        '(<a href="data.html#records">coding breaks</a>). '
        f"Road type accounts for {int(outside_by_term.get('Road type', 0))} of the {outside}."
        "</p>",
    )

    body += "<h2>Limits of these associations</h2>"
    body += (
        "<p>A circumstance can raise the number of crashes and lower the share that are fatal "
        "at the same time, and these records observe only the fatal share: they contain no "
        "measure of how much driving takes place on wet roads or through junctions. Why the "
        "fatal share is lower is also untested, since the file has no data on speed, vehicles "
        "or drivers.</p>"
    )
    body += downloads(
        [
            ("q3_model_coefficients", "all coefficients"),
            ("q3_adverse_conditions", "model variants"),
            ("q3_adverse_composition", "where hail and snow crashes happen"),
            ("q3_adverse_exclusions", "hail and snow with the top provinces removed"),
            ("q3_recording_regime", "missing-value levels in Catalonia and elsewhere"),
            ("q3_regime_sensitivity", "every odds ratio with and without Catalonia"),
            ("q3_marginal_effects", "average marginal effects"),
            ("q3_holdout_summary", "scores on later years"),
            ("q3_calibration", "calibration on later years"),
            ("q3_year_stability", "year-by-year refits"),
            ("q3_profiles", "crash profiles"),
            ("q3_groupings", "how DGT's codes map to these levels"),
        ],
        method=("data.html#records", "severity among recorded crashes"),
    )
    return render_page(
        "severity",
        "Crash circumstances and fatal outcomes",
        "Which circumstances recorded by the police go with a death once an injury crash has "
        f"happened, in DGT's national records for {first_year}–{last_year}: an analysis of "
        "associations, not a predictive model.",
        body,
    )
