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


def _junction_break_year() -> int:
    """The year the junction fields were first coded differently, read from the table behind
    data.html's coding breaks: the one year in which the junction-type field stops being empty
    for a large share of crashes."""
    missing = read_table("missingness_by_year")
    info = missing[missing.column == "NUDO_INFO"].set_index("year").share_empty.sort_index()
    drops = info.diff()
    junction = [int(year) for year in drops[drops < -JUNCTION_BREAK_DROP].index]
    if len(junction) != 1:
        raise ValueError("severity page: the junction coding break is no longer one year")
    return junction[0]


def page_severity(captions: dict[str, str]) -> str:
    numbers = _severity_numbers()
    adverse = numbers["adverse"]
    coefficients = numbers["coefficients"]
    holdout = numbers["holdout"]
    fatal = coefficients[coefficients.outcome == "fatal"].set_index(["predictor", "level"])
    variants = read_table("q3_adverse_conditions")
    regime = read_table("q3_recording_regime").set_index(["predictor", "level"])
    sensitivity = read_table("q3_regime_sensitivity")
    other_road = sensitivity[
        (sensitivity.outcome == "fatal")
        & (sensitivity.predictor == "road")
        & (sensitivity.level == "other road")
    ].iloc[0]
    sensitivity = sensitivity[sensitivity.outcome == "fatal"].set_index(["predictor", "level"])
    stability = read_table("q3_year_stability")
    stability = stability[stability.outcome == "fatal"]
    exclusions = read_table("q3_adverse_exclusions")
    composition = read_table("q3_adverse_composition")
    periods = read_table("q3_period_refits")
    periods = periods[periods.outcome == "fatal"].set_index(
        ["period", "scope", "predictor", "level"]
    )
    locations = read_table("q3_location_contrasts")
    locations = locations[locations.outcome == "fatal"]
    artefacts = read_table("dgt_audit_artefacts")
    audit = read_table("dgt_audit_checks")
    # The published Catalan model (the calculator's), scored on the years it had not seen.
    rolling = read_table("sev_rolling_scores")
    pooled_span = str(rolling.subset[rolling.subset.str.fullmatch(r"\d{4}-\d{4}")].iloc[0])
    catalonia_model = (
        rolling[rolling.subset == pooled_span].set_index("estimator").loc["calculator"]
    )

    def orr(variant: str, level: str, frame=adverse) -> str:
        row = frame.loc[(variant, level)]
        return _ci(float(row.odds_ratio), float(row.or_low), float(row.or_high))

    wet_alone = float(adverse.loc[("no_weather", "wet"), "odds_ratio"])
    wet_full = float(adverse.loc[("full", "wet"), "odds_ratio"])
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

    # The yearly refits: how many estimates leave the full model's interval, which terms vary
    # between years by more than their yearly errors allow, and the junction coding break.
    outside = int((~stability.within_full_interval.astype(bool)).sum())
    full_outside_year = int((~stability.full_within_year_interval.astype(bool)).sum())
    outside_by_term = (
        (~stability.within_full_interval.astype(bool)).groupby(stability.predictor_label).sum()
    )
    terms = stability[["predictor", "level", "is_largest", "heterogeneity_p"]].drop_duplicates(
        ["predictor", "level"]
    )
    largest_terms = terms[terms.is_largest.astype(bool)]
    largest_labels = list(
        dict.fromkeys(stability[stability.is_largest.astype(bool)].predictor_label.str.lower())
    )
    hyphenated = [label.replace(" ", "-") for label in largest_labels]
    kinds = ", ".join(hyphenated[:-1]) + " or " + hyphenated[-1]
    varying = terms[terms.heterogeneity_p < 0.05]
    junction_years = stability[stability.level == "at a junction"].set_index("year").odds_ratio
    yearly = stability.pivot_table(index="year", columns=["predictor", "level"], values="log_odds")
    zone_road = float(yearly[("zone", "interurban road")].corr(yearly[("road", "conventional")]))
    junction_break = _junction_break_year()
    junction_before_years = junction_years[junction_years.index < junction_break]
    junction_after_years = junction_years[junction_years.index >= junction_break]
    after_values = {f"{value:.2f}" for value in junction_after_years}
    after_text = (
        f"{after_values.pop()} in {_join([str(year) for year in junction_after_years.index])}"
        if len(after_values) == 1
        else _join([f"{value:.2f} in {year}" for year, value in junction_after_years.items()])
    )

    # The junction association before and after the coding break, and outside Catalonia.
    junction_key = ("junction", "at a junction")
    junction_before = periods.loc[("before", "all provinces", *junction_key)]
    junction_from = periods.loc[("from", "all provinces", *junction_key)]
    junction_from_outside = periods.loc[("from", "outside Catalonia", *junction_key)]
    junction_before_outside = periods.loc[("before", "outside Catalonia", *junction_key)]

    # Zone and road type read together: the joint contrasts against an urban street.
    shown_locations = locations[~locations.is_reference.astype(bool)]
    conventional = shown_locations[
        (shown_locations.zone == "interurban road") & (shown_locations.road == "conventional")
    ].iloc[0]
    interurban_locations = shown_locations[shown_locations.zone == "interurban road"]
    crossings = shown_locations[
        (shown_locations.zone == "urban crossing") & (shown_locations.road == "conventional")
    ]
    strongest_location = shown_locations.loc[shown_locations.odds_ratio.idxmax()]

    # How much of the holdout ranking the missing-value levels carry.
    artefact = artefacts[artefacts.target.str.startswith("death within 30 days")].iloc[0]

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

    # The strongest single terms outside zone and road type, by distance from 1.
    single = strength[
        ~strength.is_nuisance.astype(bool)
        & ~strength.index.get_level_values("predictor").isin(["zone", "road"])
    ]
    single = single.reindex(
        single.odds_ratio.map(lambda v: abs(math.log(v))).sort_values(ascending=False).index
    )
    head_on_row = fatal.loc[("crash_type", "head-on collision")]
    pedestrian_row = fatal.loc[("crash_type", "pedestrian struck")]
    strongest_three = min(
        abs(math.log(float(row.odds_ratio))) for row in (head_on_row, pedestrian_row, conventional)
    )

    def overlaps(a: pd.Series, b: pd.Series) -> bool:
        return float(a.or_low) <= float(b.or_high) and float(b.or_low) <= float(a.or_high)

    checks = {
        "the other road type's odds ratio rises without Catalonia's crashes": float(
            other_road.odds_ratio_without
        )
        > float(other_road.odds_ratio),
        "the audit keeps DGT's file out of model training": not str(
            audit.decision.iloc[0]
        ).startswith("DGT microdata may train"),
        "the two largest odds ratios are a head-on collision and a pedestrian struck": set(
            zip(ranked.predictor.iloc[:2], ranked.level.iloc[:2], strict=True)
        )
        == {("crash_type", "head-on collision"), ("crash_type", "pedestrian struck")},
        # The summary names crash type and location together as the strongest associations.
        "outside zone and road type the two strongest terms are the same two crash types": set(
            single.index[:2]
        )
        == {("crash_type", "head-on collision"), ("crash_type", "pedestrian struck")},
        "the conventional interurban contrast is as large as the crash-type terms": overlaps(
            conventional, head_on_row
        )
        and overlaps(conventional, pedestrian_row),
        "no other single term outside zone and road type comes close": bool(
            single.iloc[2:].odds_ratio.map(lambda v: abs(math.log(v))).max() < strongest_three / 2
        ),
        "every interurban road type goes with higher odds than an urban street": bool(
            (interurban_locations.or_low > 1).all()
        )
        and len(interurban_locations) == 4,
        "a conventional road through a town has the largest location contrast": len(crossings) == 1
        and strongest_location.zone == "urban crossing"
        and strongest_location.road == "conventional",
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
        "the period refits split at the junction coding break": int(junction_from.first_year)
        == junction_break
        and int(junction_before.last_year) == junction_break - 1,
        "a junction goes with lower odds of a death before the break": float(
            junction_before.or_high
        )
        < 1,
        "and not after it": float(junction_from.or_low) < 1 < float(junction_from.or_high),
        "outside Catalonia the junction association is found in both periods": float(
            junction_from_outside.or_high
        )
        < 1
        and float(junction_before_outside.or_high) < 1,
        "the share of Catalan crashes coded at a junction jumps at the break": float(
            junction_from.share_at_level_inside
        )
        - float(junction_before.share_at_level_inside)
        > 0.15,
        "while elsewhere it barely moves": abs(
            float(junction_from_outside.share_at_level)
            - float(junction_before_outside.share_at_level)
        )
        < 0.03,
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
        "the Catalan severity model's crashes are already selected for severity": float(
            catalonia_model.prevalence
        )
        > 5 * float(numbers["fatal_share"]),
        "the fitted probabilities improve little on the base rate": float(fatal_holdout.brier_skill)
        < 0.1
        and float(serious_holdout.brier_skill) < 0.1,
        "the largest terms are all crash type, zone or road type": set(largest_terms.predictor)
        <= {"crash_type", "zone", "road"},
        "road type accounts for most departures from the full model's interval": str(
            outside_by_term.idxmax()
        )
        == "Road type",
        "zone and road-type odds ratios move against each other from year to year": zone_road
        < -0.5,
        "only the junction term varies between years by more than its errors allow": list(
            zip(varying.predictor, varying.level, strict=True)
        )
        == [junction_key],
        "the yearly junction odds ratio is below 0.85 in every year before the break": bool(
            (junction_before_years < 0.85).all()
        ),
        "and about 1 in every year from it": bool(junction_after_years.between(0.9, 1.1).all()),
        "the missing-value levels rank a little on their own and add a little": 0.5
        < float(fatal_holdout.auc_missing_only)
        < float(fatal_holdout.auc_recorded_only)
        < float(fatal_holdout.auc),
        "the audit's blank fields rank fatal crashes well on their own": float(
            artefact.roc_auc_unrecorded_flags_only
        )
        > 0.65,
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"severity page: the tables no longer support: {failed}")

    head_on = fatal.loc[("crash_type", "head-on collision")]
    pedestrian = fatal.loc[("crash_type", "pedestrian struck")]
    reference_crash = str(features.PREDICTORS["crash_type"]["levels"][0])  # type: ignore[index]
    # The strongest single term after the two crash types, outside zone and road type.
    next_term = single.iloc[2]
    wet_row = adverse.loc[("no_weather", "wet")]

    def span(row: pd.Series) -> str:
        return f"{int(row.first_year)}–{int(row.last_year)}"

    def interval(row: pd.Series) -> str:
        return f"{float(row.or_low):.2f}–{float(row.or_high):.2f}"

    def ci_of(row: pd.Series) -> str:
        return _ci(float(row.odds_ratio), float(row.or_low), float(row.or_high))

    def auc(value: float) -> str:
        """ROC-AUC to two decimals, the scale of the model and validation pages."""
        return f"{float(value):.2f}"

    body = summary(
        f"DGT's national records hold {_fmt_int(numbers['n'])} injury crashes in Spain for "
        f"{first_year}–{last_year}; {_fmt_pct(numbers['fatal_share'])} had at least one death "
        "within 30 days. With the other recorded circumstances held equal, the odds of a death "
        "went most strongly with the type of crash and where it happened. Against a "
        f"{reference_crash}, a head-on collision had {float(head_on.odds_ratio):.2f} times the "
        f"odds of a death (95% interval {interval(head_on)}) and a pedestrian struck "
        f"{float(pedestrian.odds_ratio):.2f} times ({interval(pedestrian)}); against a crash on "
        "an urban street, a crash on a conventional interurban road had "
        f"{float(conventional.odds_ratio):.2f} times the odds ({interval(conventional)}). Wet "
        f"conditions went with lower odds ({wet_alone:.2f} times the odds, {interval(wet_row)}), "
        f"and so did junctions in {span(junction_before)} "
        f"({float(junction_before.odds_ratio):.2f}, {interval(junction_before)}) but not in "
        f"{span(junction_from)} ({float(junction_from.odds_ratio):.2f}, "
        f"{interval(junction_from)}), after DGT began to code junctions differently, mostly in "
        "Catalonia. These associations among crashes that happened say nothing about how often "
        "crashes happen or why some are deadlier. The pages on "
        '<a href="catalonia.html">Catalonia</a> (crashes with a death or serious injury, deaths '
        'within 24 hours) and <a href="barcelona.html">Barcelona</a> (every crash the city police '
        "attended in one year) cover other crashes with other definitions, so their figures "
        "differ."
    )

    body += "<h2>Crash type and location go most strongly with a death</h2>"
    body += (
        "<p>An odds ratio compares the odds of a death in crashes with a circumstance against "
        "those in crashes at its reference level, with the other recorded circumstances held "
        "equal; 1 means no difference. The chart gives the odds ratio of every circumstance the "
        "police record. Outside zone and road type, a head-on collision and a pedestrian struck "
        "stand far above the rest: the next strongest is the "
        f"{str(next_term.predictor_label).lower()} "
        f"“{next_term.name[1]}”, at {float(next_term.odds_ratio):.2f} "
        f"({interval(next_term)}).</p>"
    )
    body += figure(
        "s1_forest_fatal",
        "Odds ratios of a death for each recorded circumstance against its reference level, "
        f"with 95% intervals. A pedestrian struck ({float(pedestrian.odds_ratio):.2f}) and a "
        f"head-on collision ({float(head_on.odds_ratio):.2f}) are furthest above 1; a wet "
        "surface and a junction are below 1.",
        captions,
    )
    body += (
        "<p>Zone and road type describe one location between them, so the chart shows each "
        "against the other's reference, and the table below adds the two together. Against a "
        "crash on an urban street, a crash on any of the four interurban road types had "
        f"{float(interurban_locations.odds_ratio.min()):.2f} to "
        f"{float(interurban_locations.odds_ratio.max()):.2f} times the odds of a death, and a "
        "crash on a conventional road where it runs through a town (the zone DGT calls an urban "
        f"crossing) {float(strongest_location.odds_ratio):.2f} times. The road type “other” "
        f"mixes two kinds of crash: in {last_year} DGT's records for the four Catalan provinces "
        "code "
        'urban streets as another kind of road (<a href="data.html#coding-breaks">coding '
        f"breaks</a>), so its odds ratio, {float(other_road.odds_ratio):.2f}, rises to "
        f"{float(other_road.odds_ratio_without):.2f} without Catalonia's crashes.</p>"
    )
    location_rows = pd.DataFrame(
        {
            "Zone": shown_locations.zone.str.capitalize(),
            "Road type": shown_locations.road.map(
                lambda v: PROFILE_TERMS.get(v.capitalize(), v.capitalize())
            ),
            "Crashes": shown_locations.crashes,
            "Odds ratio of a death (95% interval)": [
                _ci(float(r.odds_ratio), float(r.or_low), float(r.or_high))
                for r in shown_locations.itertuples()
            ],
        }
    )
    body += table(
        location_rows,
        "Odds ratio of a death by zone and road type together, against a crash on an urban "
        "street. Combinations with at least "
        f"{_fmt_int(features.MIN_LEVEL_CRASHES)} crashes, from the full model with the "
        "covariance of the two terms; 95% intervals clustered by province.",
        {"Crashes": "int"},
    )
    profiles = read_table("q3_profiles")
    for spanish, english in PROFILE_TERMS.items():
        profiles["profile"] = profiles.profile.str.replace(spanish, english, regex=False)
    lowest = profiles.loc[profiles.fatal.idxmin()]
    highest = profiles.loc[profiles.fatal.idxmax()]
    body += (
        f"<p>Turned into probabilities for illustrative crashes in {last_year}, with every "
        "circumstance not named at its reference level, the odds ratios give a fitted "
        f"probability of a death from {_fmt_pct(float(lowest.fatal))} "
        f"({str(lowest.profile).lower()}) to {_fmt_pct(float(highest.fatal))} "
        f"({str(highest.profile).lower()}).</p>"
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
        "Circumstances not named are at their reference level, including two vehicles; most "
        "crashes in which a pedestrian was struck involve one vehicle.",
        {"Death": "pct", "Death or hospitalisation": "pct"},
    )

    body += "<h2>Lower odds of a death on wet roads, and at junctions until the coding changed</h2>"
    body += (
        "<p>Weather and road surface record much the same thing, so a model that contains both "
        "divides one association between them. With road surface left out, the odds ratio for "
        f"rain moves from {orr('full', 'rain')} to {orr('no_surface', 'rain')}; with weather "
        f"left out, the odds ratio for a wet surface moves from {orr('full', 'wet')} to "
        f"{orr('no_weather', 'wet')}. Rain and a wet surface are therefore one association of "
        f"about {wet_alone:.2f} for wet conditions. The full model's {wet_full:.2f} for a wet "
        "surface, with rain alongside it, is the value in the tables below.</p>"
        "<p>Wet weather is also unevenly spread across roads: "
        f"{_fmt_pct(float(rain_interurban.share_of_level), 0)} of crashes in the rain are on "
        f"interurban roads, against {_fmt_pct(float(rain_interurban.share_overall), 0)} of all "
        "crashes. Fitting interurban roads and urban streets separately holds that context "
        f"fixed: the wet-surface odds ratio is {orr('interurban', 'wet')} on interurban roads "
        f"and {orr('street', 'wet')} on urban streets. Its interval lies below 1 in every model "
        "variant.</p>"
        "<p>The junction association is below 1 in every variant too, at "
        f"{orr('full', 'at a junction')} in the full model, but that figure pools two ways of "
        "recording junctions. From "
        f"{junction_break}, DGT's records code junctions differently, and almost all of the "
        "change is in Catalonia, where the share of crashes recorded at a junction went from "
        f"{_fmt_pct(float(junction_before.share_at_level_inside), 0)} in "
        f"{span(junction_before)} to {_fmt_pct(float(junction_from.share_at_level_inside), 0)} "
        f"in {span(junction_from)}, against "
        f"{_fmt_pct(float(junction_before_outside.share_at_level), 0)} and "
        f"{_fmt_pct(float(junction_from_outside.share_at_level), 0)} elsewhere. Fitted on each "
        "period apart, crashes at a junction had "
        f"{ci_of(junction_before)} times the odds of a death in {span(junction_before)} and "
        f"{ci_of(junction_from)} in {span(junction_from)}. Outside Catalonia the later figure "
        f"is {ci_of(junction_from_outside)}, so the association disappears only where the coding changed. The results for "
        "junctions are read from the earlier years.</p>"
    )
    body += figure(
        "s2_adverse_conditions",
        "Odds ratios of a death for a wet surface, rain, hail or snow and a junction under "
        f"each of {_count(n_variants)} model variants, with 95% intervals. The wet-surface and "
        "junction odds ratios are below 1 in every variant.",
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
        f"{ci_of(widest)}, inside the full model's interval.</p>"
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

    body += "<h2>What the records cannot show</h2>"
    body += (
        "<p>A circumstance can raise the number of crashes and lower the share that are fatal "
        "at the same time, and these records observe only the fatal share: they contain no "
        "measure of how much driving takes place on wet roads or through junctions. Why crashes "
        "in wet conditions or at junctions are less often fatal is also untested, since the "
        "file has no data on speed or on the drivers.</p>"
    )

    body += "<h2>The records and the regressions</h2>"
    body += (
        "<p>DGT's file has one row per injury crash, with counts of the people killed and "
        "injured, but no record of individual drivers, vehicles or people. Its fields are "
        "recorded too unevenly between provinces to train a predictive model "
        '(<a href="sources.html">data sources and scope</a>), but they can describe '
        "associations. Two logistic regressions are fitted, one for at least one death within "
        "30 days and one for a death or a hospitalisation. Their circumstances are those the "
        "police record: zone, road type, crash type, junction, lighting, weather, road surface, "
        "alignment, time of day, weekend (from 20:00 on Friday to the end of Sunday), number of "
        "vehicles and year. A missing value is kept as a level of its own, so no crash is "
        "dropped, and levels with fewer than "
        f"{_fmt_int(features.MIN_LEVEL_CRASHES)} crashes are merged into their reference "
        "category. The intervals are 95% confidence intervals, with standard errors clustered "
        "by province.</p>"
    )
    body += technical(
        "How stable the associations are over time",
        f"<p>Fitted on {train_span} without a year term and applied to the crashes of "
        f"{test_span}, the two regressions keep their ordering of crashes. Given one crash with "
        "the outcome and one without, the share of such pairs in which a regression gives the "
        "crash with the outcome the higher probability is its ROC-AUC, from 0.5 for chance to 1 "
        f"for a perfect ranking: {auc(numbers['auc_fatal'])} for the regression for a death and "
        f"{auc(numbers['auc_serious'])} for a death or a hospitalisation. Part of that ordering "
        "comes from how the form was filled in rather than from the crash: refitted with every "
        "level that records a missing value folded into its reference, the regression for a "
        f"death scores {auc(fatal_holdout.auc_recorded_only)}, and those levels on their own "
        f"{auc(fatal_holdout.auc_missing_only)}. Across the wider set of fields the DGT "
        "microdata audit examines, which fields were left blank scores "
        f"{auc(artefact.roc_auc_unrecorded_flags_only)} on its own, one reason the file is not "
        "used to train a predictive model. The "
        '<a href="severity-models.html">Catalan severity model</a> scores '
        f"{auc(catalonia_model.roc_auc)} on years it had not seen, but among "
        "crashes already selected for a death or serious injury; here the deaths are picked out "
        f"among all injury crashes, of which {_fmt_pct(numbers['fatal_share'])} were fatal. As "
        "probabilities, the fitted values improve little on giving every crash the training "
        "years' share of each outcome: their Brier score (mean squared error) is "
        f"{_fmt_pct(float(fatal_holdout.brier_skill))} lower for a death and "
        f"{_fmt_pct(float(serious_holdout.brier_skill))} lower for a death or a "
        "hospitalisation.</p>"
        "<p>Refitted one year at a time, "
        f"{outside} of the {len(stability)} yearly estimates for the regression's "
        f"{len(largest_terms)} largest terms (each a {kinds} term) and its junction "
        "and wet-surface terms fall outside the full model's interval. Each year's estimate has "
        "its own sampling error, so some departures are expected: the full model's value lies "
        f"outside the year's own interval for {full_outside_year}. Road type accounts for "
        f"{int(outside_by_term.get('Road type', 0))} of the {outside}; its odds ratios swing from "
        "year to year against the zone odds ratios, the two splitting one location contrast "
        "between them. Tested against their yearly errors (Cochran's Q), only the junction term "
        "varies between years by more than chance: its odds ratio lies between "
        f"{float(junction_before_years.min()):.2f} and {float(junction_before_years.max()):.2f} "
        f"in every year to {junction_break - 1} and is {after_text}, the years of the new "
        'junction coding (<a href="data.html#coding-breaks">coding breaks</a>).</p>',
    )

    body += "<h2>Missing values and regional recording</h2>"
    body += (
        "<p>Some levels stand for a missing value, a field's “unknown” or “not specified” "
        "code. They stay in the regression but are left out of the charts and of the results "
        "in the text. One of them is among the strongest terms in the whole regression, and it "
        "sits almost entirely in one region. Road alignment “unknown”, with an odds ratio of "
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
        "coefficients through such a level, so the regression for a death was refitted "
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
            ("q3_period_refits", "refits before and after the junction coding change"),
            ("q3_location_contrasts", "zone and road type together"),
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
