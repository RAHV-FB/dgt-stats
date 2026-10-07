"""The points-based driving licence: monthly road deaths around its start, the choice of
pre-trend, and the falsification tests (July placebos, forecasts made before each July,
twelve-month comparisons) that the apparent fall does not pass; and the design for the lower speed
limit on conventional roads, whose placebo test fails."""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import policy
from dgt_stats.site.components import (
    DOCS_URL,
    _join,
    _ordinal,
    _signed_pct,
    downloads,
    figure,
    limitation,
    read_table,
    render_page,
    summary,
    table,
    technical,
)
from dgt_stats.site.numbers import _policy_numbers

# Human labels for the specifications in ``q8_points_sensitivity``. The two whose labels carry a
# date keep the table's own wording, lightly rephrased (see ``_specification_label``).
SPECIFICATIONS = {
    "main": "Preferred: pre-trend with one bend, chosen on the earlier months",
    "linear_trend": "Straight-line pre-trend",
    "quadratic": "Curved (quadratic) pre-trend",
    "fuel": "Road fuel consumption (CORES) added",
    "toll": "Toll-motorway traffic intensity added",
    "24h": "Deaths within 24 hours instead of 30 days",
    "interurban": "Interurban roads only",
    "urban": "Urban streets only",
    "no_slope": "Step without a change of slope",
    "negative_binomial": "Negative binomial model",
}
DATED_SPECIFICATIONS = {
    "knot_2004": ("Piecewise pre-trend with the knot fixed at", "Pre-trend with its bend fixed at"),
    "long": ("Post-period to", "Window extended to"),
}


def _specification_label(variant: str, label: str) -> str:
    if variant in SPECIFICATIONS:
        return SPECIFICATIONS[variant]
    old, new = DATED_SPECIFICATIONS[variant]
    if not label.startswith(old):
        raise ValueError(f"policy page: unexpected label for {variant}: {label}")
    return new + label[len(old) :]


def _count_word(value: int) -> str:
    """A small count as a capitalised word."""
    words = {
        1: "One",
        2: "Two",
        3: "Three",
        4: "Four",
        5: "Five",
        6: "Six",
        7: "Seven",
        8: "Eight",
        9: "Nine",
        10: "Ten",
    }
    return words.get(value, str(value))


def _month(value: object) -> str:
    """A month and its year in words."""
    return f"{pd.Timestamp(value):%B %Y}"


# The specifications whose interval includes no change are listed in prose; these read better
# than the table labels in a sentence.
PROSE = {
    "no_slope": "a step without a change of slope",
    "interurban": "interurban roads alone",
    "urban": "urban streets alone",
}


def _crossing_phrases(crosses: pd.DataFrame) -> list[str]:
    """The specifications in ``crosses`` as phrases for a sentence, in table order."""
    phrases = []
    for variant, row in crosses.iterrows():
        if variant in PROSE:
            phrases.append(PROSE[variant])
        elif variant == "knot_2004":
            phrases.append("a bend fixed at " + str(row.label).rsplit(" at ", 1)[-1])
        else:
            label = _specification_label(variant, str(row.label))
            prefix = "the " if variant == "long" else ""
            phrases.append(prefix + label[0].lower() + label[1:])
    return phrases


def page_policy(captions: dict[str, str]) -> str:
    numbers = _policy_numbers()
    main, linear = numbers["main"], numbers["linear"]
    calendar, forecast = numbers["calendar"], numbers["forecast"]
    transitions = numbers["transitions"]
    trend = numbers["trend"]
    sensitivity = numbers["sensitivity"]
    chosen = trend[trend.chosen].iloc[0]
    straight = trend[trend.label == "one linear trend"].iloc[0]
    true_calendar = numbers["true_calendar"]
    true_forecast = numbers["true_forecast"]
    it = policy.INTERVENTIONS["points_licence"]
    speed_limit = policy.INTERVENTIONS["speed_limit_90"]
    licence_date = f"{it.date.day} {it.date:%B %Y}"
    break_month = f"{it.date:%B %Y}"
    true_transition = transitions[transitions.year == it.date.year].iloc[0]
    pre_months, post_months = policy.CALENDAR_PRE_MONTHS, it.post_months
    ranked = transitions[transitions["rank"].notna()]
    larger = ranked[ranked.twelve_month_ratio < float(true_transition.twelve_month_ratio)]
    excluded = sorted(int(year) for year in transitions[transitions.excluded].year)
    beyond = forecast[forecast.z < float(true_forecast.z)].sort_values("z")
    others = calendar[~calendar.is_true].sort_values("level_change")
    runner_up, third = others.iloc[0], others.iloc[1]
    fuel, toll = sensitivity.loc["fuel"], sensitivity.loc["toll"]
    knot_2004 = sensitivity.loc["knot_2004"]
    negative_binomial = sensitivity.loc["negative_binomial"]
    fit = read_table("q8_points_fit")
    hinge = fit[fit.term.str.startswith("t_hinge")]
    speed_placebo = read_table("q8_speed_placebo")
    failed_placebo = speed_placebo[
        ~speed_placebo.is_true.astype(bool) & ((speed_placebo.low > 0) | (speed_placebo.high < 0))
    ]
    penal_months = (it.second_break.year - it.date.year) * 12 + (
        it.second_break.month - it.date.month
    )
    unmapped = set(sensitivity.index) - set(SPECIFICATIONS) - set(DATED_SPECIFICATIONS)
    checks = {
        "every specification has a human label": not unmapped,
        "the preferred pre-trend gives the smaller step": bool(
            linear.level_change < main.level_change < 0
        ),
        "the straight-line pre-trend gives the largest fall of every specification": bool(
            float(linear.level_change) == float(sensitivity.level_change.min())
        ),
        "the pre-period months reject the straight line by more than 10 AIC points": float(
            straight.delta_aic
        )
        > 10,
        "every larger twelve-month fall came after the break": bool(
            len(larger) >= 1 and (larger.year > it.date.year).all()
        ),
        # The prose prints these two as falls, by their absolute size.
        "deaths fell across the July of the change": float(true_transition.twelve_month_ratio) < 0,
        "the months after the change fell below their forecast": float(true_forecast.log_ratio) < 0,
        "the out-of-sample test ranks other Julys above the true one": len(beyond) >= 1,
        "the traffic covariates barely move the step": all(
            abs(float(row.level_change) - float(main.level_change)) < 0.01 for row in (fuel, toll)
        ),
        "the negative binomial fit gives a similar step": abs(
            float(negative_binomial.level_change) - float(main.level_change)
        )
        < 0.01,
        "the knot fixed at the alternative month gives an interval that includes no change": bool(
            knot_2004.level_low < 0 < knot_2004.level_high
        ),
        "a placebo break before the speed limit fails that design": len(failed_placebo) >= 1,
        "the true July is the largest fall of the July placebos": int(true_calendar["rank"]) == 1,
        "the true July's interval overlaps the runner-up's": float(runner_up.low)
        <= float(true_calendar.high),
        # A rank of 1 among n fits is a one-sided p of 1/n; the prose calls it short of
        # conventional significance.
        "rank 1 of the July placebos falls short of conventional significance": 1
        / float(true_calendar.n_fits)
        > 0.05,
        "the chosen bend beats the straight line": float(chosen.aic) < float(straight.aic),
        # The hinge term is the change of slope at the bend: negative means a steeper decline.
        "the decline steepened at the chosen bend": bool(
            len(hinge) == 1 and float(hinge.estimate.iloc[0]) < 0
        ),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"policy page: the tables no longer support: {failed}")

    body = summary(
        f"Monthly road deaths in Spain fell around {licence_date}, when the points-based "
        "driving licence came into force. The size of the fall depends on how the earlier "
        "trend is projected. A straight-line trend gives a step of "
        f"{_signed_pct(float(linear.level_change))}; the trend the earlier months themselves "
        f"favour, which steepens in {_month(chosen.knot)}, gives "
        f"{_signed_pct(float(main.level_change))} (95% interval "
        f"{_signed_pct(float(main.level_low))} to {_signed_pct(float(main.level_high))}). "
        "When a step model with a straight-line trend is fitted at each of "
        f"{int(true_calendar.n_fits)} Julys "
        f"on a common window, {it.date.year} shows the largest fall, but only narrowly; "
        "against forecasts made before each July it ranks "
        f"{_ordinal(int(true_forecast['rank']))} of {int(true_forecast.n_fits)}. The series "
        "supports a modest fall in deaths around the change. It gives no basis for "
        "attributing that fall to the licence."
    )

    body += "<h2>The before-and-after estimate</h2>"
    body += (
        "<p>A monthly national series can test only a change with a known date, and even "
        "then the test is weak. An interrupted time-series analysis fits the months before a "
        "change, projects them forward and measures how far the months after fall below the "
        "projection. The model is a Poisson regression of monthly deaths within 30 days, from "
        f"{_month(it.pre_start)} to {_month(it.post_end)}, with a term for each calendar "
        f"month, a pre-existing trend, and a step and a change of slope at {break_month}. A "
        "straight line through the months before the change gives a step of "
        f"{_signed_pct(float(linear.level_change))}.</p>"
    )
    body += figure(
        "p1_points_series",
        f"Monthly road deaths, {it.pre_start.year}–{it.post_end.year}, with the fitted model "
        "and two projections of deaths without the change: the preferred pre-trend (dashed) "
        "and a straight-line pre-trend (dotted)",
        captions,
    )
    body += "<h2>The choice of pre-trend</h2>"
    body += (
        "<p>The straight line can be tested against alternatives on the months before the "
        "change alone, so the choice does not look at the outcome. Among trends with a single "
        f"bend, the best fit places the bend at {_month(chosen.knot)}, where the decline "
        "steepened, and it fits the earlier months better than the straight line by "
        f"{float(straight.delta_aic):.0f} points of AIC. (Akaike's information criterion "
        "rewards fit and penalises extra parameters; lower is better, and a difference of more "
        "than 10 points is usually read as strong evidence.) With the bend in place, the "
        f"estimated step at {break_month} shrinks by about "
        f"{abs(float(linear.level_change) - float(main.level_change)) * 100:.0f} percentage "
        f"points, to {_signed_pct(float(main.level_change))}.</p>"
    )
    candidates = trend.assign(
        label=[
            "Straight line, no bend" if pd.isna(knot) else f"Bend at {_month(knot)}"
            for knot in trend.knot
        ]
    )[["label", "aic", "delta_aic"]].rename(
        columns={"label": "Pre-trend", "aic": "AIC", "delta_aic": "Difference from the best"}
    )
    body += technical(
        "Pre-trend candidates and their fit",
        table(
            candidates,
            f"Pre-trends fitted to the months before {break_month} only: the best candidates "
            "and the straight line. Lower AIC is better.",
            {"AIC": "dec", "Difference from the best": "dec"},
        ),
    )

    body += "<h2>Comparison with other Julys</h2>"
    body += (
        "<p>Spanish road deaths peak every July and August, so a break placed on 1 July may "
        "partly capture an ordinary summer movement. A placebo test repeats the estimate at "
        "Julys when the licence cannot have acted, each with a straight-line trend on a common "
        f"window of {pre_months} months before and {post_months} after; years whose window "
        f"contains {break_month} or the pandemic are left out. If the {it.date.year} fall is "
        "exceptional, it should stand out among these Julys.</p>"
    )
    body += figure(
        "p2_july_placebos",
        f"Estimated step in deaths at 1 July of each year from {int(calendar.year.min())} to "
        f"{int(calendar.year.max())}, with 95% intervals; {break_month} is marked",
        captions,
    )
    body += (
        f"<p>On this common window July {it.date.year} gives the largest fall of the "
        f"{int(true_calendar.n_fits)}, {_signed_pct(float(true_calendar.level_change), 1)}, "
        f"but only narrowly: July {int(runner_up.year)} gives "
        f"{_signed_pct(float(runner_up.level_change), 1)} and July {int(third.year)} "
        f"{_signed_pct(float(third.level_change), 1)}, and their intervals overlap. A rank of "
        f"{int(true_calendar['rank'])} of {int(true_calendar.n_fits)} corresponds to a "
        f"one-sided empirical p-value of about {1 / float(true_calendar.n_fits):.2f}, which is "
        "suggestive but short of conventional significance.</p>"
    )
    body += (
        "<p>A second test uses no step at all. For each July, a model with a trend and calendar "
        f"months is fitted to the {pre_months} months before it and used to forecast the "
        f"{post_months} months after; the measure is how far the recorded months fall below "
        f"that forecast. After {break_month} they fall "
        f"{abs(float(true_forecast.log_ratio)) * 100:.0f}% below it, a rank of "
        f"{int(true_forecast['rank'])} of {int(true_forecast.n_fits)} among the Julys: the "
        f"months after July {int(beyond.iloc[0].year)} fell further below their own forecast"
        + (
            f", and so did those after July {_join([str(int(y)) for y in beyond.year.iloc[1:]])}"
            if len(beyond) > 1
            else ""
        )
        + ". This is the clearest evidence against reading the straight-line estimate of "
        f"{_signed_pct(float(linear.level_change))} as an effect of the licence.</p>"
    )

    body += "<h2>Twelve months either side of each July</h2>"
    body += (
        "<p>A check without any model divides the deaths in the twelve months from each July "
        "by those in the twelve months before it. Each side contains one of every calendar "
        f"month, so seasonality cancels exactly. Across July {it.date.year} deaths fell "
        f"{abs(math.expm1(float(true_transition.twelve_month_ratio))) * 100:.1f}%, the "
        f"{_ordinal(int(true_transition['rank']))} largest fall of the "
        f"{int(true_transition.n_ranked)} years that can be measured; the larger falls all came "
        f"later, in {_join([str(int(year)) for year in sorted(larger.year)])}. The series was "
        f"falling steeply on both sides of {it.date.year}, the same pattern the choice of "
        "pre-trend revealed.</p>"
    )
    largest = ranked.nsmallest(8, "twelve_month_ratio")
    show = pd.concat([largest, ranked[ranked.year == it.date.year]]).drop_duplicates("year")
    show = show.sort_values("twelve_month_ratio")
    # The table carries log changes; the page prints them as signed percentage changes.
    shown_transitions = pd.DataFrame(
        {
            "Year": show.year.astype(int).astype(str),
            "June to July": [_signed_pct(math.expm1(v)) for v in show.jun_to_jul],
            "July to August": [_signed_pct(math.expm1(v)) for v in show.jul_to_aug],
            "August to September": [_signed_pct(math.expm1(v)) for v in show.aug_to_sep],
            "Twelve months after against twelve before": [
                _signed_pct(math.expm1(v), 1) for v in show.twelve_month_ratio
            ],
            "Rank": show["rank"].astype(int).astype(str),
        }
    )
    body += technical(
        "The largest falls across a July",
        table(
            shown_transitions,
            f"The {_count_word(len(largest)).lower()} largest falls across a July, among the "
            f"{int(true_transition.n_ranked)} years that can be measured. The month-to-month "
            "columns show the summer movement; the twelve-month column compares the same "
            f"calendar months on each side. The years {excluded[0]}–{excluded[-1]} are left out "
            "because the pandemic breaks the comparison.",
        ),
    )

    body += f"<h2>Traffic and other changes around {it.date.year}</h2>"
    body += (
        "<p>A fall in deaths can reflect a fall in traffic. Two monthly series reach back "
        f"before {it.date.year}: CORES's national road-fuel consumption, which "
        "covers every road, and traffic on the state toll-motorway network, measured directly "
        "on a small part of it as its average daily intensity (vehicles a day on the average "
        "kilometre, so that newly opened sections do not inflate it). Adding either series to "
        f"the model barely moves the estimate: {_signed_pct(float(fuel.level_change))} with "
        f"fuel and {_signed_pct(float(toll.level_change))} with toll-motorway intensity, "
        f"against {_signed_pct(float(main.level_change))} without either. Neither measures "
        "the kilometres driven on all roads, so this shows only that the step does not follow "
        "these two series.</p>"
    )
    body += (
        "<p>Other changes overlap the licence. The decline in deaths had already steepened in "
        f"{pd.Timestamp(chosen.knot).year}, before any of them. Automatic speed cameras were "
        "being installed on the main road network under the national road-safety plan over "
        "the same years. The reform of the Penal Code that made serious speeding and "
        f"drink-driving criminal offences came into force in {_month(it.second_break)}, "
        f"{penal_months} months after the licence, and the recession that followed reduced "
        "traffic and freight.</p>"
    )

    body += "<h2>Sensitivity to the specification</h2>"
    crosses = sensitivity[sensitivity.level_high > 0]
    phrases = _crossing_phrases(crosses)
    body += (
        f"<p>The estimate was repeated under {len(sensitivity)} specifications. The "
        "straight-line pre-trend gives the largest fall of all of them. "
        f"{_count_word(len(crosses))} give an interval that includes no change"
        + (": " + _join(phrases) + "." if phrases else ".")
        + " A fall of about "
        f"{abs(float(main.level_change)) * 100:.0f}%, with a wide interval, is as much as the "
        "series supports.</p>"
    )
    shown = sensitivity.reset_index()
    shown = pd.DataFrame(
        {
            "Specification": [
                _specification_label(v, label) for v, label in zip(shown.variant, shown.label)
            ],
            f"Step at {break_month} (95% interval)": [
                f"{_signed_pct(r.level_change, 1)} ({_signed_pct(r.level_low, 1)} to "
                f"{_signed_pct(r.level_high, 1)})"
                for r in shown.itertuples()
            ],
        }
    )
    body += technical(
        f"All {len(sensitivity)} specifications",
        table(
            shown,
            f"Step in deaths at {break_month} under each specification, monthly deaths "
            f"{_month(it.pre_start)} to {_month(it.post_end)} unless stated.",
        ),
    )

    body += (
        f"<h2>The {speed_limit.date.year} speed limit on conventional roads</h2>"
        "<p>The lower speed limit on conventional roads was examined with a different design, "
        "comparing conventional roads with motorways and dual carriageways month by month. "
        "That design "
        "fails its placebo test: a break placed in "
        f"{_month(failed_placebo.break_date.iloc[0])}, before the change, produces a divergence "
        f"of its own ({_signed_pct(float(failed_placebo.level_change.iloc[0]))}, with an "
        "interval that excludes zero), so no estimate of the speed-limit change is reported. "
        'The fits are published (<a href="tables/q8_speed_placebo.csv">placebos</a>, '
        '<a href="tables/q8_speed_sensitivity.csv">specifications</a>).</p>'
    )

    body += "<h2>The fall and the licence</h2>"
    body += (
        "<p>The monthly series shows a fall in deaths of about "
        f"{abs(float(main.level_change)) * 100:.0f}% around {break_month}. The fall survives "
        "the pre-trend the earlier months favour and is the largest of the July placebos, "
        "though narrowly, while the forecast test and the twelve-month comparison place "
        f"{it.date.year} within the range of other years. Whether the fall was unusual is "
        "therefore only partly settled. That the points licence caused it is a separate "
        "claim, which the series cannot test: speed cameras, the Penal Code reform and the "
        "recession overlapped or closely followed the licence, and a single national series "
        "cannot separate their effects from the licence's.</p>"
    )
    body += limitation(
        "Monthly deaths vary more than a Poisson model assumes and are correlated from month "
        "to month; the intervals use Newey–West standard errors with "
        f"{policy.HAC_LAGS} lags, and a negative binomial model gives a similar step "
        f"({_signed_pct(float(negative_binomial.level_change))}). Choosing the pre-trend by "
        "AIC is itself a selection step, which is why the alternative pre-trends and "
        "specifications are reported."
    )
    body += downloads(
        [
            ("q8_points_calendar_placebo", "July placebos"),
            ("q8_points_forecast", "forecasts made before each July"),
            ("q8_points_transitions", "twelve months either side of each July"),
            ("q8_points_trend_choice", "pre-trend candidates"),
            ("q8_points_sensitivity", "every specification"),
            ("q8_points_placebo", "placebo breaks at arbitrary months"),
        ],
        method=(f"{DOCS_URL}/methodology.md", "the case study in the full methodology"),
    )
    return render_page(
        "policy",
        f"The {it.date.year} points-based licence",
        f"Spain's monthly road deaths from {it.pre_start.year} to {it.post_end.year}, before "
        "and after the points-based driving licence came into force.",
        body,
    )
