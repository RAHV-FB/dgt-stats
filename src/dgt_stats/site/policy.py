"""Supporting analysis: the 2006 points licence and why the test is weak."""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import policy
from dgt_stats.site.components import (
    SUPPORTING_NOTES,
    _join,
    _ordinal,
    _signed_pct,
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
from dgt_stats.site.numbers import _policy_numbers

CONFOUNDERS = [
    ("2003–2004", "The decline in road deaths steepens, before any of the measures below"),
    ("2005–2008", "Road-safety plan: automatic speed cameras rolled out on the main network"),
    ("1 July 2006", "Points-based driving licence in force (Ley 17/2005); the intervention"),
    (
        "2 December 2007",
        "Penal Code reform: speeding and drink-driving thresholds become offences (LO 15/2007)",
    ),
    ("2008–2009", "Recession; traffic and freight fall"),
]


def page_policy(captions: dict[str, str]) -> str:
    numbers = _policy_numbers()
    main, linear = numbers["main"], numbers["linear"]
    calendar, forecast = numbers["calendar"], numbers["forecast"]
    transitions = numbers["transitions"]
    trend = numbers["trend"]
    chosen = trend[trend.chosen].iloc[0]
    straight = trend[trend.label == "one linear trend"].iloc[0]
    true_calendar = numbers["true_calendar"]
    true_forecast = numbers["true_forecast"]
    it = policy.INTERVENTIONS["points_licence"]
    true_transition = transitions[transitions.year == it.date.year].iloc[0]
    pre_months, post_months = policy.CALENDAR_PRE_MONTHS, it.post_months
    step = f"{abs(float(main.level_change)) * 100:.0f}"
    straight_step = f"{abs(float(linear.level_change)) * 100:.0f}"
    ranked = transitions[transitions["rank"].notna()]
    larger = ranked[ranked.twelve_month_ratio < float(true_transition.twelve_month_ratio)]
    excluded = sorted(int(year) for year in transitions[transitions.excluded].year)
    beyond = forecast[forecast.z < float(true_forecast.z)].sort_values("z")
    fuel = numbers["sensitivity"].loc["fuel"]
    toll = numbers["sensitivity"].loc["toll"]
    knot_2004 = numbers["sensitivity"].loc["knot_2004"]
    speed_placebo = read_table("q8_speed_placebo")
    failed_placebo = speed_placebo[
        ~speed_placebo.is_true.astype(bool) & ((speed_placebo.low > 0) | (speed_placebo.high < 0))
    ]
    penal_months = (it.second_break.year - it.date.year) * 12 + (
        it.second_break.month - it.date.month
    )
    checks = {
        "the preferred pre-trend gives the smaller step": bool(
            linear.level_change < main.level_change < 0
        ),
        "every larger twelve-month fall came after the break": bool(
            (larger.year > it.date.year).all()
        ),
        "the out-of-sample test ranks other Julys above 2006": len(beyond) >= 1,
        "the traffic covariates barely move the step": all(
            abs(float(row.level_change) - float(main.level_change)) < 0.01 for row in (fuel, toll)
        ),
        "the knot fixed at January 2004 gives an interval that includes no change": bool(
            knot_2004.level_low < 0 < knot_2004.level_high
        ),
        "a placebo break before 2019 fails the speed-limit design": len(failed_placebo) >= 1,
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"policy page: the tables no longer support: {failed}")

    body = key_figures(
        [
            (
                "Level change at July 2006",
                _signed_pct(float(main.level_change)),
                f"{_signed_pct(float(main.level_low))} to {_signed_pct(float(main.level_high))}, "
                "preferred pre-trend",
            ),
            (
                "Under a straight pre-trend",
                _signed_pct(float(linear.level_change)),
                "the specification the pre-2006 months reject",
            ),
            (
                "Rank among July breaks",
                f"{int(true_calendar['rank'])} of {int(true_calendar.n_fits)}",
                "same model placed at July of other years",
            ),
            (
                "Rank on out-of-sample error",
                f"{int(true_forecast['rank'])} of {int(true_forecast.n_fits)}",
                "how abnormal the months after each July were",
            ),
        ]
    )
    body += (
        '<p class="answer">Something did happen to Spanish road deaths around July 2006, when the '
        "points-based licence came in. It is smaller and less exceptional than a straight-line "
        f"model says. Fitting the pre-trend the earlier months actually prefer cuts the step from "
        f"{_signed_pct(float(linear.level_change))} to {_signed_pct(float(main.level_change))} "
        f"({_signed_pct(float(main.level_low))} to {_signed_pct(float(main.level_high))}), and a "
        "forecast made before each July finds 2006 only the "
        f"{_ordinal(int(true_forecast['rank']))} most abnormal July of "
        f"{int(true_forecast.n_fits)}. What the series supports is a step of roughly {step} "
        "per cent that no single measure can be credited with.</p>"
    )

    body += "<h2>How the pre-trend was chosen, and why it matters</h2>"
    body += figure(
        "p1_points_series",
        "Monthly road deaths 2000–2007 with the fitted model and two counterfactuals",
        captions,
    )
    body += (
        "<p>An interrupted time series fits the months before a change, projects them forward and "
        "asks whether the months after sit below. Everything therefore depends on what is "
        "projected. Earlier versions of this study used one straight trend through 2000–2006. "
        "Tested on the pre-intervention months alone, with no post-period involved, that "
        "straight line is worse than a trend with a single kink by "
        f"{float(straight.delta_aic):.0f} points "
        f"of AIC, and the kink the data pick is at {chosen.label.replace('knot at ', '')}, where "
        "the decline steepened. Put that kink in and the estimated step at July 2006 falls by "
        f"about {abs(float(linear.level_change) - float(main.level_change)) * 100:.0f} percentage "
        "points. The dotted line on the chart is the straight-line counterfactual; the gap "
        "between the two counterfactuals is the disagreement.</p>"
    )
    body += table(
        trend.assign(label=lambda f: f.label.str[0].str.upper() + f.label.str[1:])[
            ["label", "aic", "delta_aic"]
        ].rename(columns={"label": "Pre-trend", "aic": "AIC", "delta_aic": "Δ AIC"}),
        "Choosing the pre-trend on the months before July 2006 only: the best candidates, with "
        "the straight line for comparison. Lower AIC is better",
        {"AIC": "dec", "Δ AIC": "dec"},
    )

    body += "<h2>Was July 2006 unusual for a July?</h2>"
    body += (
        "<p>Spanish road deaths peak every July and August. A placebo distribution built by "
        "moving the break to arbitrary months cannot answer whether the summer of 2006 was "
        "unusual, so this one places the break at 1 July of every year with a clean window: the "
        f"same model, the same {pre_months} months before and {post_months} after, at Julys the "
        "points licence cannot explain.</p>"
    )
    body += figure(
        "p2_july_placebos",
        "Estimated level change at 1 July of each year, with July 2006 marked",
        captions,
    )
    others = calendar[~calendar.is_true].sort_values("level_change")
    runner_up = others.iloc[0]
    body += (
        f"<p>July 2006 is the largest fall of the {int(true_calendar.n_fits)}, but only just. "
        f"July {int(runner_up.year)} gives {_signed_pct(float(runner_up.level_change), 1)} and "
        f"July {int(others.iloc[1].year)} {_signed_pct(float(others.iloc[1].level_change), 1)}, "
        f"and the intervals overlap. Rank 1 of {int(true_calendar.n_fits)} is a one-sided "
        f"empirical p-value of about {1 / float(true_calendar.n_fits):.2f}: suggestive, not "
        "decisive.</p>"
    )

    body += "<h2>Two tests without a model</h2>"
    body += (
        "<p>Take the twelve months from each July and divide by the twelve months before it. Both "
        "sides then contain one of every calendar month, so seasonality cancels exactly and no "
        "model is involved. Across July 2006 that ratio is "
        f"{_signed_pct(math.expm1(float(true_transition.twelve_month_ratio)), 1)}"
        f", a large fall, and the {_ordinal(int(true_transition['rank']))} largest of the "
        f"{int(true_transition.n_ranked)} years that can be measured. The larger falls all "
        f"came later, in {_join([str(int(year)) for year in sorted(larger.year)])}. The "
        "series was falling steeply either side of 2006, which is the same problem the "
        "pre-trend test found, seen without a regression.</p>"
    )
    largest = ranked.nsmallest(8, "twelve_month_ratio")
    show = pd.concat([largest, ranked[ranked.year == 2006]]).drop_duplicates("year")
    show = show.sort_values("twelve_month_ratio")[
        ["year", "jun_to_jul", "jul_to_aug", "aug_to_sep", "twelve_month_ratio", "rank"]
    ].copy()
    # The table carries log changes; the page prints them as percentage changes.
    for column in ("jun_to_jul", "jul_to_aug", "aug_to_sep", "twelve_month_ratio"):
        show[column] = show[column].map(math.expm1)
    show = show.rename(
        columns={
            "year": "Year",
            "jun_to_jul": "June → July",
            "jul_to_aug": "July → August",
            "aug_to_sep": "August → September",
            "twelve_month_ratio": "12 months after ÷ 12 before",
            "rank": "Rank",
        }
    )
    body += table(
        show,
        f"The {len(largest)} largest falls across a July, of the "
        f"{int(true_transition.n_ranked)} years that can be measured. The last column has the "
        "same twelve calendar months on each side, so seasonality cancels; "
        f"{excluded[0]}–{excluded[-1]} are left out because the pandemic breaks the comparison",
        {
            "Year": "year",
            "June → July": "pct0",
            "July → August": "pct0",
            "August → September": "pct0",
            "12 months after ÷ 12 before": "pct",
            "Rank": "int",
        },
    )
    body += (
        f"<p>The second test fits the {pre_months} months before each July, with a trend and "
        f"seasonality and no intervention term, then forecasts the {post_months} months after "
        "it. The question is how far the "
        f"observed months fall below that forecast. After July 2006 they fall "
        f"{abs(float(true_forecast.log_ratio)) * 100:.0f}% below, which sounds decisive until the "
        f"same exercise is run at the other Julys: 2006 comes "
        f"{_ordinal(int(true_forecast['rank']))} of {int(true_forecast.n_fits)}. The months after "
        f"July {int(beyond.iloc[0].year)} were further below their own forecast"
        + (
            f", and so were those after July {_join([str(int(y)) for y in beyond.year.iloc[1:]])}"
            if len(beyond) > 1
            else ""
        )
        + f". This is the single clearest reason not to report a {straight_step} per cent "
        "policy effect.</p>"
    )
    body += downloads(
        [
            ("q8_points_calendar_placebo", "July placebos"),
            ("q8_points_forecast", "out-of-sample forecasts"),
            ("q8_points_transitions", "summer transitions"),
            ("q8_points_trend_choice", "pre-trend selection"),
            ("q8_points_sensitivity", "every specification"),
            ("q8_points_placebo", "the older arbitrary-month placebos"),
        ]
    )

    body += "<h2>Exposure, and everything else that changed</h2>"
    body += (
        "<p>A fall in deaths can be a fall in traffic. Two Spanish series are monthly and reach "
        "back past 2006: CORES's national road-fuel consumption, which covers every road, and the "
        "Ministerio de Transportes' traffic on the state toll-motorway network, a direct "
        "measurement on a small part of it. The toll series enters as its average daily "
        "intensity, vehicles a day on the average kilometre, not as vehicle-kilometres, which "
        "grow with the length of the network in service and step up whenever new sections open. "
        "Adding either as a covariate barely moves the estimate: "
        f"{_signed_pct(float(fuel.level_change))} with fuel and "
        f"{_signed_pct(float(toll.level_change))} with toll-motorway intensity, against "
        f"{_signed_pct(float(main.level_change))} without either. Neither is vehicle-kilometres "
        "on all Spanish roads by month, which does not exist, so the two series show that the "
        "step is not tracking these measures of traffic; they do not measure exposure.</p>"
    )
    body += table(
        pd.DataFrame(CONFOUNDERS, columns=["When", "What changed"]),
        "What else was happening around the intervention",
    )
    sensitivity = numbers["sensitivity"].reset_index()
    shown = sensitivity[
        ["label", "window", "level_change", "level_low", "level_high", "dispersion"]
    ]
    shown = shown.assign(
        interval=shown.apply(
            lambda r: (
                f"{_signed_pct(r.level_change, 1)} ({_signed_pct(r.level_low, 1)} to "
                f"{_signed_pct(r.level_high, 1)})"
            ),
            axis=1,
        )
    )[["label", "window", "interval", "dispersion"]].rename(
        columns={
            "label": "Specification",
            "window": "Window",
            "interval": "Level change (95% interval)",
            "dispersion": "Dispersion",
        }
    )
    body += table(
        shown, "The July 2006 level change under every specification", {"Dispersion": "dec2"}
    )

    body += "<h2>Conclusion</h2>"
    crosses = numbers["sensitivity"][numbers["sensitivity"].level_high > 0]
    body += conclusion(
        "Two different claims have to be kept apart. <strong>That the death series changed "
        f"unusually around July 2006</strong>: partly supported. A step of about "
        f"{abs(float(main.level_change)) * 100:.0f}% survives the specification the pre-period "
        "prefers and the largest of the calendar-matched July placebos, but the out-of-sample "
        "test and the seasonality-free transition both put 2006 inside the range of ordinary "
        "years. <strong>That the points licence caused it</strong>: not supported by this series "
        "at all. The speed-camera programme was rolling out over the same two years, the Penal "
        f"Code reform followed {penal_months} months later, and the recession after that."
    )
    body += (
        f"<p>And the step is fragile. Of the {len(numbers['sensitivity'])} specifications in the "
        f"table above, {len(crosses)} give an interval that includes no change at all"
        + (
            ": " + _join([str(row.label).lower() for row in crosses.itertuples()]) + ". "
            if len(crosses)
            else ". "
        )
        + f"{straight_step.capitalize()} per cent is not what this series supports; {step}, "
        "with a wide interval, is about as much as it will carry.</p>"
    )
    body += limits(
        "Monthly deaths are overdispersed and serially correlated; standard errors are "
        "Newey–West "
        f"with {policy.HAC_LAGS} lags and a negative-binomial fit is in the table above. "
        "Choosing the pre-trend by AIC on the pre-period is a selection step, so the tables show "
        "the alternatives: the best knots and their AIC, and a knot fixed at January 2004, which "
        f"gives {_signed_pct(float(knot_2004.level_change))} with an interval "
        f"({_signed_pct(float(knot_2004.level_low))} to "
        f"{_signed_pct(float(knot_2004.level_high))}) that includes no change. A separate study "
        "of the 2019 speed-limit cut on conventional roads is not published here: its control "
        "design fails a placebo break placed in "
        f"{pd.Timestamp(failed_placebo.break_date.iloc[0]):%B %Y}, which produces a divergence "
        "of its own, so no claim can be made from it. Its fits are kept as evidence of the "
        "negative result "
        '(<a href="tables/q8_speed_placebo.csv">placebos</a>, '
        '<a href="tables/q8_speed_sensitivity.csv">specifications</a>).'
    )
    return render_page(
        "policy",
        "The July 2006 break",
        "Monthly road deaths fell around the points-based licence. How much of that was the "
        "policy, how much the trend already under way, and how much July?",
        note(SUPPORTING_NOTES["policy"]) + body,
    )
