"""Crash circumstances and fatal outcomes: associations in DGT's national crash records.

A description of which recorded circumstances go with a fatal outcome in DGT's injury-crash
records (the crash-severity regressions). The project does not train a predictive model on DGT's
file: its audit keeps it out. The page gives the results; how the regressions are specified and
checked, the inverted junction flag, the model variants and the missing-value levels are technical
notes on the methodology page (``technical_notes``).

Every number is read from the ``q3_*`` tables that ``scripts/model.py`` writes; the qualitative
sentences are guarded by checks that stop the build when the tables stop supporting them. The
levels that stand for a missing value are nuisance terms (``is_nuisance`` in the tables): they are
reported and explained, never read as an effect.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pandas as pd

from dgt_stats import features
from dgt_stats.site.components import (
    ALL_PAGES,
    DOCS_URL,
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
    "at a junction": "At a junction",
}

# The profile labels in ``q3_profiles`` use DGT's Spanish name for a dual carriageway.
PROFILE_TERMS = {"Autovía": "Dual carriageway"}

NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
# Two shares at a junction closer than this are "close": the corrected Catalan share and the rest
# of Spain's.
CLOSE_SHARE = 0.02
TITLES = dict(ALL_PAGES)
# The section of the methodology page that holds this page's technical notes.
NOTES = "severity-method"


def _ci(odds: float, low: float, high: float) -> str:
    return f"{odds:.2f} ({low:.2f}–{high:.2f})"


def _ci_of(row: pd.Series) -> str:
    """An odds ratio with its 95% interval: '0.69 (0.65–0.73)'."""
    return _ci(float(row.odds_ratio), float(row.or_low), float(row.or_high))


def _interval(row: pd.Series) -> str:
    return f"{float(row.or_low):.2f}–{float(row.or_high):.2f}"


def _ci_inline(row: pd.Series) -> str:
    """An odds ratio and its interval for use inside parentheses: '0.63, 0.54–0.74'."""
    return f"{float(row.odds_ratio):.2f}, {_interval(row)}"


def _pct_span(values: pd.Series) -> str:
    """One share, or the lowest and highest as a range when they round apart."""
    low, high = _fmt_pct(float(values.min()), 0), _fmt_pct(float(values.max()), 0)
    return low if low == high else f"{low}–{high}"


def _span(row: pd.Series) -> str:
    return f"{int(row.first_year)}–{int(row.last_year)}"


def _auc(value: float) -> str:
    """ROC-AUC to two decimals, the scale of the model and validation pages."""
    return f"{float(value):.2f}"


def _count(value: int) -> str:
    """A count in words below ten, as house style asks in running prose."""
    return NUMBER_WORDS[value] if 0 <= value < len(NUMBER_WORDS) else _fmt_int(value)


def _junction_break_year() -> int:
    """The year the Catalan provinces' records began to code the junction flag the wrong way
    round, read from the table behind data.html's coding breaks: the first year of the
    province-years whose junction flag reads inverted, which must be the four Catalan provinces
    in every year from then to the last."""
    junctions = read_table("dgt_audit_junction_coding")
    inverted = junctions[junctions.junction_flag_inverted.astype(bool)]
    catalan = junctions[junctions.catalan.astype(bool)]
    first = int(inverted.year.min())
    years = set(range(first, int(junctions.year.max()) + 1))
    if not (
        set(inverted.province) == set(catalan.province)
        and set(inverted.year) == years
        and len(inverted) == catalan.province.nunique() * len(years)
    ):
        raise ValueError(
            "severity page: the junction flag is no longer inverted in the Catalan provinces "
            "alone, from one year to the last"
        )
    return first


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the ``q3_*`` tables, with
    the checks that the sentences built on them still hold."""
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
    periods = read_table("q3_period_refits")
    periods = periods[periods.outcome == "fatal"].set_index(
        ["period", "scope", "predictor", "level"]
    )
    locations = read_table("q3_location_contrasts")
    locations = locations[locations.outcome == "fatal"]
    # The junction flag as published and as the model reads it.
    junction_coding = read_table("q3_junction_coding")
    junction_sensitivity = read_table("q3_junction_sensitivity")
    junction_sensitivity = junction_sensitivity[junction_sensitivity.outcome == "fatal"]
    audit = read_table("dgt_audit_checks")
    calibration = read_table("q3_calibration")
    calibration = calibration[calibration.outcome == "fatal"].sort_values("decile")

    first_year, last_year = int(holdout.first_train_year.min()), int(holdout.last_test_year.max())
    train_span = f"{int(holdout.first_train_year.min())}–{int(holdout.last_train_year.max())}"
    test_span = f"{int(holdout.first_test_year.min())}–{int(holdout.last_test_year.max())}"
    n_variants = variants.variant.nunique()

    # The recording regime: alignment "unknown" and where its crashes are.
    alignment = regime.loc[("alignment", "unknown")]
    others = regime.drop(index=("alignment", "unknown"))
    kept = sensitivity[~sensitivity.is_nuisance.astype(bool)]
    # How many full-model odds ratios lie inside the interval of the refit without Catalonia
    # (the symmetric comparison), and the largest moves.
    full_inside = int(
        ((kept.odds_ratio >= kept.or_low_without) & (kept.odds_ratio <= kept.or_high_without)).sum()
    )
    largest = kept.loc[(kept.ratio_without_to_full - 1).abs().sort_values(ascending=False).index]
    biggest_moves = largest.head(3)
    n_excluded = int(kept.n.iloc[0] - kept.n_without.iloc[0])

    junction_break = _junction_break_year()
    junction_key = ("junction", "at a junction")
    junction = fatal.loc[junction_key]
    junction_before = periods.loc[("before", "all provinces", *junction_key)]
    junction_from = periods.loc[("from", "all provinces", *junction_key)]
    junction_from_outside = periods.loc[("from", "outside Catalonia", *junction_key)]
    junction_before_outside = periods.loc[("before", "outside Catalonia", *junction_key)]

    # How the model reads the inverted junction flag, and what the rest of each record says.
    catalan_junctions = junction_coding[junction_coding.region == "Catalonia"].set_index("year")
    other_junctions = junction_coding[junction_coding.region != "Catalonia"].set_index("year")
    flipped = catalan_junctions[catalan_junctions.recoded > 0]
    flipped_years = [int(year) for year in flipped.index]
    earlier = catalan_junctions[catalan_junctions.index < junction_break]
    recoded = int(junction_coding.recoded.sum())
    flagged_at = int(flipped.flagged_at.sum())
    flagged_at_fields = int(flipped.flagged_at_with_junction_fields.sum())
    flagged_away = int(flipped.flagged_away.sum())
    away_fields_share = float(flipped.flagged_away_with_junction_fields.sum()) / flagged_away
    earlier_at_fields = earlier.flagged_at_with_junction_fields / earlier.flagged_at
    corrected_shares = flipped.share_at_junction
    elsewhere_shares = other_junctions.loc[flipped_years].share_at_junction
    treatments = junction_sensitivity[junction_sensitivity.fit == "full"].set_index("treatment")
    used_treatment = treatments[treatments.used.astype(bool)].iloc[0]
    from_break = junction_sensitivity[junction_sensitivity.fit == "from break"].set_index(
        "treatment"
    )

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

    def orr(variant: str, level: str) -> str:
        return _ci_of(adverse.loc[(variant, level)])

    wet_full_row = adverse.loc[("full", "wet")]
    rain_full_row = adverse.loc[("full", "rain")]
    wet_alone = float(adverse.loc[("no_weather", "wet"), "odds_ratio"])
    rain_alone = float(adverse.loc[("no_surface", "rain"), "odds_ratio"])

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
    top_decile = calibration.iloc[-1]

    # The strongest single terms outside zone and road type, by distance from 1.
    single = strength[
        ~strength.is_nuisance.astype(bool)
        & ~strength.index.get_level_values("predictor").isin(["zone", "road"])
    ]
    single = single.reindex(
        single.odds_ratio.map(lambda v: abs(math.log(v))).sort_values(ascending=False).index
    )
    head_on = fatal.loc[("crash_type", "head-on collision")]
    pedestrian = fatal.loc[("crash_type", "pedestrian struck")]
    strongest_three = min(
        abs(math.log(float(row.odds_ratio))) for row in (head_on, pedestrian, conventional)
    )
    reference_crash = str(features.PREDICTORS["crash_type"]["levels"][0])  # type: ignore[index]
    # The strongest single term after the two crash types, outside zone and road type.
    next_term = single.iloc[2]

    # Illustrative crash profiles, with DGT's Spanish road-type name in English.
    profiles = read_table("q3_profiles")
    for spanish, english in PROFILE_TERMS.items():
        profiles["profile"] = profiles.profile.str.replace(spanish, english, regex=False)
    lowest = profiles.loc[profiles.fatal.idxmin()]
    highest = profiles.loc[profiles.fatal.idxmax()]

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
        "outside zone and road type the two strongest terms are the same two crash types": set(
            single.index[:2]
        )
        == {("crash_type", "head-on collision"), ("crash_type", "pedestrian struck")},
        "the conventional interurban contrast is as large as the crash-type terms": overlaps(
            conventional, head_on
        )
        and overlaps(conventional, pedestrian),
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
        "leaving out surface strengthens rain, and leaving out weather strengthens wet": rain_alone
        < float(rain_full_row.odds_ratio)
        and wet_alone < float(wet_full_row.odds_ratio),
        "rain alone and a wet surface alone give about the same odds ratio": abs(
            math.log(rain_alone / wet_alone)
        )
        < 0.1,
        "a wet surface goes with lower odds of a death in the full model": float(
            wet_full_row.or_high
        )
        < 1,
        "the wet-surface odds ratio is below 1 in every variant that has it": bool(
            (adverse.xs("wet", level="level").or_high < 1).all()
        ),
        "a junction goes with lower odds of a death": float(junction.or_high) < 1,
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
        "and after it, with the flag corrected": float(junction_from.or_high) < 1,
        "outside Catalonia the junction association is found in both periods": float(
            junction_from_outside.or_high
        )
        < 1
        and float(junction_before_outside.or_high) < 1,
        "the model reads the flag the other way round in the inverted years alone": flipped_years
        == list(range(junction_break, last_year + 1))
        and recoded == int(flipped.crashes.sum())
        and recoded == int(used_treatment.recoded)
        and abs(float(used_treatment.odds_ratio) - float(junction.odds_ratio)) < 1e-9,
        "as published, the Catalan share coded at a junction jumps at the break": float(
            flipped.share_flagged_at.min()
        )
        > float(earlier.share_flagged_at.max()) + 0.15,
        "corrected, the Catalan share at a junction is close to the rest of Spain's": float(
            (corrected_shares - elsewhere_shares).abs().max()
        )
        < CLOSE_SHARE,
        "the crashes flagged at a junction carry almost no junction field, those flagged away "
        "almost all one": flagged_at_fields < 0.001 * flagged_at and away_fields_share > 0.99,
        "as crashes at a junction do in the earlier years": bool((earlier_at_fields > 0.99).all()),
        "while elsewhere the share at a junction barely moves": abs(
            float(junction_from_outside.share_at_level)
            - float(junction_before_outside.share_at_level)
        )
        < 0.03,
        "the flag as published gives the odds ratio closest to 1, in the full fit and from the "
        "break": float(treatments.loc["as published", "odds_ratio"])
        > float(treatments.loc["flip", "odds_ratio"])
        and float(from_break.loc["as published", "odds_ratio"])
        > float(from_break.loc["flip", "odds_ratio"])
        and set(treatments.index) == {"flip", "as published"},
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
        "the regression for a death ranks later years' crashes at an AUC of about 0.8": 0.75
        <= numbers["auc_fatal"]
        <= 0.85
        and numbers["auc_serious"] > 0.5,
        "the fitted probabilities for a death are close to calibrated": abs(
            float(top_decile.predicted) - float(top_decile.observed)
        )
        < 0.01
        and abs(float(fatal_holdout.mean_predicted) - float(fatal_holdout.base_rate_test)) < 0.002,
        "the fitted probabilities improve little on the base rate by the Brier score": float(
            fatal_holdout.brier_skill
        )
        < 0.1
        and float(serious_holdout.brier_skill) < 0.1,
        "the missing-value levels rank a little on their own and add a little": 0.5
        < float(fatal_holdout.auc_missing_only)
        < float(fatal_holdout.auc_recorded_only)
        < float(fatal_holdout.auc),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"severity page: the tables no longer support: {failed}")
    return SimpleNamespace(**locals())


def page_severity(captions: dict[str, str]) -> str:
    f = _facts()
    head_on, pedestrian, junction = f.head_on, f.pedestrian, f.junction
    shown_locations, next_term = f.shown_locations, f.next_term
    notes = f'<a href="data.html#{NOTES}">technical notes</a>'

    body = summary(
        f"In Spain's {f.first_year}–{f.last_year} injury crashes, other recorded "
        f"circumstances held equal, a head-on collision had {float(head_on.odds_ratio):.2f} "
        f"times the odds of a death within 30 days (against a {f.reference_crash}) and a crash "
        f"on a conventional interurban road {float(f.conventional.odds_ratio):.2f} times the "
        "odds (against an urban street). With an inverted Catalan junction flag read the other "
        f"way round, crashes at junctions ({float(junction.odds_ratio):.2f}, "
        f"{_interval(junction)}) and on wet roads ({float(f.wet_full_row.odds_ratio):.2f}, "
        f"{_interval(f.wet_full_row)}) had lower odds; this says "
        'nothing about how often crashes happen there. <a href="catalonia.html">Catalonia</a> '
        '(deaths within 24 hours) and <a href="barcelona.html">Barcelona</a> cover other '
        "crashes."
    )
    body += (
        '<p><a href="crash-explorer.html">Explore these records</a> by year, region, road type '
        "and crash type.</p>"
    )

    body += "<h2>Crash type and location go most strongly with a death</h2>"
    body += (
        f"<p>Of the {_fmt_int(f.numbers['n'])} injury crashes in DGT's national records for "
        f"{f.first_year}–{f.last_year}, {_fmt_pct(f.numbers['fatal_share'])} had at least one "
        "death within 30 days. An odds ratio compares the odds of a death in crashes with a "
        "circumstance against those at its reference level, with the other recorded "
        "circumstances held equal; 1 means no difference. Outside zone and road type, a "
        f"pedestrian struck ({float(pedestrian.odds_ratio):.2f}, {_interval(pedestrian)}) and a "
        f"head-on collision ({float(head_on.odds_ratio):.2f}, {_interval(head_on)}) stand far "
        "above every other circumstance; the next strongest is the "
        f"{str(next_term.predictor_label).lower()} “{next_term.name[1]}”, at "
        f"{float(next_term.odds_ratio):.2f} ({_interval(next_term)}).</p>"
    )
    body += figure(
        "s1_forest_fatal",
        "Odds ratios of a death for each recorded circumstance against its reference level, "
        f"with 95% intervals. A pedestrian struck ({float(pedestrian.odds_ratio):.2f}) and a "
        f"head-on collision ({float(head_on.odds_ratio):.2f}) are furthest above 1; a wet "
        "surface and a junction are below 1.",
        captions,
    )
    interurban = f.interurban_locations
    body += (
        "<p>Zone and road type describe one location between them, so the table adds the two "
        "together. Against a crash on an urban street, a crash on any of the four interurban "
        f"road types had {float(interurban.odds_ratio.min()):.2f} to "
        f"{float(interurban.odds_ratio.max()):.2f} times the odds of a death, and a crash on a "
        "conventional road where it runs through a town (the zone DGT calls an urban crossing) "
        f"{float(f.strongest_location.odds_ratio):.2f} times.</p>"
    )
    location_rows = pd.DataFrame(
        {
            "Zone": shown_locations.zone.str.capitalize(),
            "Road type": shown_locations.road.map(
                lambda v: PROFILE_TERMS.get(v.capitalize(), v.capitalize())
            ),
            "Crashes": shown_locations.crashes,
            "Odds ratio of a death (95% interval)": [
                _ci_of(row) for _, row in shown_locations.iterrows()
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

    body += "<h2>Lower odds of a death on wet roads and at junctions</h2>"
    body += (
        f"<p>In the full model a wet surface had {_ci_of(f.wet_full_row)} times the odds of a "
        f"death and rain {_ci_of(f.rain_full_row)}. Weather and road surface record much the "
        "same thing, so a model that contains both divides one association between them: with "
        f"weather left out a wet surface goes with {f.wet_alone:.2f}, and with surface left out "
        f"rain with {f.rain_alone:.2f}. The wet-surface interval lies below 1 in every model "
        f"variant, including interurban roads ({_ci_inline(f.adverse.loc[('interurban', 'wet')])}) "
        f"and urban streets ({_ci_inline(f.adverse.loc[('street', 'wet')])}) fitted "
        "separately.</p>"
        f"<p>A crash at a junction had {_ci_of(junction)} times the odds of a death, below 1 in "
        f"every variant. In {_join([str(y) for y in f.flipped_years])} DGT's records for the "
        "four Catalan provinces code the junction flag the wrong way round "
        '(<a href="data.html#coding-breaks">coding breaks</a>), so the analysis reads it the '
        f"other way round for these {_fmt_int(f.recoded)} crashes. Fitted on each period apart, "
        f"the odds ratio is {_ci_of(f.junction_before)} in {_span(f.junction_before)} and "
        f"{_ci_of(f.junction_from)} in {_span(f.junction_from)}; with the flag as published it "
        f"is {_ci_of(f.treatments.loc['as published'])}.</p>"
    )

    body += (
        "<h2>The records show which crashes were deadlier, not how often crashes happen or why</h2>"
    )
    body += (
        "<p>A circumstance can raise the number of crashes and lower the share that are fatal "
        "at the same time, and these records observe only the fatal share: they contain no "
        "measure of how much driving takes place on wet roads or through junctions. Why crashes "
        "in wet conditions or at junctions are less often fatal is also untested, since the "
        "file has no data on speed or on the drivers.</p>"
        "<p>The two regressions, one for a death within 30 days and one for a death or a "
        "hospitalisation, describe associations only. The file's fields are recorded too "
        'unevenly between provinces to train a predictive model (<a href="sources.html">data '
        "sources and scope</a>), and the regressions are not used to predict, as a matter of "
        f"purpose. How they are specified and checked is set out in the {notes}.</p>"
    )
    body += downloads(
        [
            ("q3_model_coefficients", "all coefficients"),
            ("q3_location_contrasts", "zone and road type together"),
            ("q3_adverse_conditions", "wet surface, rain and junction under model variants"),
            ("q3_junction_sensitivity", "the junction odds ratio under each reading of the flag"),
            ("q3_regime_sensitivity", "every odds ratio with and without Catalonia"),
            ("q3_holdout_summary", "scores on later years"),
        ],
        method=(f"data.html#{NOTES}", "how the regressions are fitted and checked"),
    )
    return render_page(
        "severity",
        "Crash circumstances and fatal outcomes",
        "Which circumstances recorded by the police go with a death once an injury crash has "
        f"happened, in DGT's national records for {f.first_year}–{f.last_year}: an analysis of "
        "associations, not a predictive model.",
        body,
    )


def technical_notes(captions: dict[str, str]) -> str:
    """How the regressions are specified, the model variants for wet conditions, the inverted
    junction flag, the checks on later years and the missing-value levels: one section for the
    methodology page."""
    del captions
    f = _facts()
    without, numbers = f.without, f.numbers
    fatal_holdout, serious_holdout = f.fatal_holdout, f.serious_holdout
    page = f'<a href="severity.html">{TITLES["severity"]}</a>'
    document = f'<a href="{DOCS_URL}/methodology.md">methods document</a>'
    coding = '<a href="#coding-breaks">coding breaks</a>'
    flipped = _join([str(y) for y in f.flipped_years])

    body = (
        f'<h2 id="{NOTES}">{TITLES["severity"]}: the regressions and their checks</h2>'
        f"<p>These notes support {page}; the {document}, in its section on associations in DGT "
        "crash records, gives the full account.</p>"
        '<h3 id="severity-regressions">The records and the regressions</h3>'
        "<p>DGT's file has one row per injury crash, with counts of the people killed and "
        "injured but no record of individual drivers, vehicles or people. Two logistic "
        "regressions are fitted, one for at least one death within 30 days and one for a death "
        "or a hospitalisation, on the circumstances the police record: zone, road type, crash "
        "type, junction, lighting, weather, road surface, alignment, time of day, weekend (from "
        "20:00 on Friday to the end of Sunday), number of vehicles and year. A missing value is "
        "kept as a level of its own, so no crash is dropped, and levels with fewer than "
        f"{_fmt_int(features.MIN_LEVEL_CRASHES)} crashes are merged into their reference "
        "category. The intervals are 95% confidence intervals, with standard errors clustered "
        "by province.</p>"
    )

    lowest, highest = f.lowest, f.highest
    profiles = f.profiles.rename(
        columns={
            "profile": "Crash profile",
            "fatal": "Death",
            "serious": "Death or hospitalisation",
        }
    )
    body += (
        '<h3 id="severity-locations">Illustrative crash profiles</h3>'
        f"<p>Turned into probabilities for illustrative crashes in {f.last_year}, with every "
        "circumstance not named at its reference level, the odds ratios give a fitted "
        f"probability of a death from {_fmt_pct(float(lowest.fatal))} "
        f"({str(lowest.profile).lower()}) to {_fmt_pct(float(highest.fatal))} "
        f"({str(highest.profile).lower()}). The profiles show the size of the odds ratios, not "
        "a forecast for any one crash. The road type “other” mixes two kinds of crash: in "
        f"{f.last_year} DGT's records for the four Catalan provinces code urban streets as "
        f"another kind of road ({coding}), so its odds ratio, "
        f"{float(f.other_road.odds_ratio):.2f}, rises to "
        f"{float(f.other_road.odds_ratio_without):.2f} without Catalonia's crashes.</p>"
    )
    body += table(
        profiles,
        f"Fitted probability of each outcome for illustrative crash profiles in {f.last_year}. "
        "Circumstances not named are at their reference level, including two vehicles; most "
        "crashes in which a pedestrian was struck involve one vehicle.",
        {"Death": "pct", "Death or hospitalisation": "pct"},
    )

    shown = f.variants[f.variants.outcome.isin(["fatal", "serious"])].copy()
    shown["ci"] = shown.apply(lambda r: _ci(r.odds_ratio, r.or_low, r.or_high), axis=1)
    wide = shown.pivot_table(
        index=["variant_label", "level"], columns="outcome", values="ci", aggfunc="first"
    ).reset_index()
    order = list(dict.fromkeys(f.variants.variant_label))
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
    body += (
        '<h3 id="severity-wet">Wet conditions under other model variants</h3>'
        "<p>Rain and a wet surface are one association: with road surface left out, the odds "
        f"ratio for rain moves from {f.orr('full', 'rain')} to {f.orr('no_surface', 'rain')}; "
        f"with weather left out, that for a wet surface moves from {f.orr('full', 'wet')} to "
        f"{f.orr('no_weather', 'wet')}. The page quotes the full model's values. Fitting "
        "interurban roads and urban streets apart holds the road context fixed by "
        "construction instead of adjusting for it.</p>"
    )
    body += table(
        wide,
        "Odds ratios for a wet surface, rain and a junction under each model variant, for a "
        "death and for a death or hospitalisation. A blank cell is a condition the variant does "
        "not contain.",
    )

    treatments = f.treatments
    body += (
        '<h3 id="severity-junction">The inverted junction flag</h3>'
        f"<p>In {flipped} DGT's records for the four Catalan provinces code the junction flag "
        f"the wrong way round ({coding}), and the rest of each record shows it: only "
        f"{_count(f.flagged_at_fields)} of the {_fmt_int(f.flagged_at)} crashes they flag at a "
        "junction carry a junction type or a right-of-way flag, while "
        f"{_fmt_pct(f.away_fields_share)} of the {_fmt_int(f.flagged_away)} they flag away "
        "from one carry either, as nearly every crash at a junction does in "
        f"{_span(f.junction_before)}. The analysis reads the flag the other way round for these "
        f"{_fmt_int(f.recoded)} crashes ({_fmt_pct(f.recoded / numbers['n'])} of all). The "
        "Catalan share at a junction is then "
        + _join(
            [f"{_fmt_pct(float(f.corrected_shares.loc[y]), 0)} in {y}" for y in f.flipped_years]
        )
        + f", close to the rest of Spain's ({_pct_span(f.elsewhere_shares)}).</p>"
        "<p>Outside Catalonia the odds ratio from "
        f"{f.junction_from.first_year} is {_ci_of(f.junction_from_outside)}. In the full model "
        f"the flag as published gives {_ci_of(treatments.loc['as published'])} against "
        f"{_ci_of(treatments.loc['flip'])} read the other way round, and from "
        f"{f.junction_from.first_year} alone {_ci_of(f.from_break.loc['as published'])} against "
        f"{_ci_of(f.from_break.loc['flip'])}: the inverted records pull the published flag's "
        "association towards 1.</p>"
    )

    body += (
        '<h3 id="severity-stability">Checks on later years</h3>'
        f"<p>Fitted on {f.train_span} without a year term and applied to the crashes of "
        f"{f.test_span}, the regression for a death ranks crashes well: given one crash with "
        "the outcome and one without, it gives the crash with the outcome the higher "
        f"probability in {_auc(numbers['auc_fatal'])} of pairs (ROC-AUC; 0.5 is chance, 1 a "
        f"perfect ranking), and the regression for a death or a hospitalisation in "
        f"{_auc(numbers['auc_serious'])}. The probabilities are also calibrated: in the tenth "
        f"of crashes with the highest fitted risk, {_fmt_pct(float(f.top_decile.predicted))} "
        f"were predicted to be fatal and {_fmt_pct(float(f.top_decile.observed))} were, and the "
        f"mean fitted probability is {_fmt_pct(float(fatal_holdout.mean_predicted))} against "
        f"{_fmt_pct(float(fatal_holdout.base_rate_test))} observed. Their Brier score (mean "
        "squared error) is nonetheless only "
        f"{_fmt_pct(float(fatal_holdout.brier_skill))} lower than giving every crash the "
        f"training years' share ({_fmt_pct(float(serious_holdout.brier_skill))} for a death or "
        "a hospitalisation), because deaths are rare. The regressions are not used for "
        "prediction, as a matter of purpose: they describe associations.</p>"
        "<p>Refitted with every level that records a missing value folded into its reference, "
        f"the regression for a death scores {_auc(fatal_holdout.auc_recorded_only)}, and those "
        f"levels on their own {_auc(fatal_holdout.auc_missing_only)}.</p>"
    )

    alignment, others, kept = f.alignment, f.others, f.kept
    moves = _join(
        [
            f"the {str(row.predictor_label).lower()} “{key[1]}” "
            f"({float(row.odds_ratio):.2f} to {float(row.odds_ratio_without):.2f})"
            for key, row in f.biggest_moves.iterrows()
        ]
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
    body += (
        '<h3 id="severity-missing">Missing values and regional recording</h3>'
        "<p>Some levels stand for a missing value, a field's “unknown” or “not specified” "
        "code. They stay in the regression but are left out of the charts and of the results "
        "in the text. Road alignment “unknown”, with an odds ratio of "
        f"{float(f.fatal.loc[('alignment', 'unknown'), 'odds_ratio']):.2f}, is among the "
        "strongest terms and sits almost entirely in one region: it is recorded for "
        f"{_fmt_pct(float(alignment.share_of_catalan_crashes))} of crashes in Catalonia "
        f"against {_fmt_pct(float(alignment.share_of_other_crashes))} elsewhere, and "
        f"{_fmt_pct(float(alignment.catalan_share_of_level))} of its "
        f"{_fmt_int(alignment.crashes)} crashes are Catalan, although Catalonia has "
        f"{_fmt_pct(float(alignment.catalan_share_of_all_crashes))} of all crashes. It marks "
        "recording practice, not an effect. The other missing-value levels are almost all "
        f"outside Catalonia (at most {_fmt_pct(float(others.catalan_share_of_level.max()), 2)} "
        "Catalan).</p>"
        "<p>A recording practice that goes with the outcome could distort the other "
        "coefficients through such a level, so the regression for a death was refitted "
        f"without Catalonia's {_fmt_int(f.n_excluded)} crashes. The full model's odds ratio "
        f"lies inside the interval of the refit for {f.full_inside} of the {len(kept)} "
        f"terms. The largest moves are in zone and road type, which have to be read together: "
        f"{moves}. The wet-surface odds ratio moves from "
        f"{float(without(('surface', 'wet')).odds_ratio):.2f} to "
        f"{float(without(('surface', 'wet')).odds_ratio_without):.2f} and the junction odds "
        f"ratio from {float(without(('junction', 'at a junction')).odds_ratio):.2f} to "
        f"{float(without(('junction', 'at a junction')).odds_ratio_without):.2f}, both still "
        "below 1.</p>"
    )
    body += table(
        pd.DataFrame(regime_rows),
        "Odds ratios for a death in the full model and refitted without Catalonia's "
        "crashes, with 95% intervals clustered by province.",
    )
    return body
