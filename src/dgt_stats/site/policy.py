"""The points-based driving licence: monthly road deaths around its start, the choice of
pre-trend, how long the step lasts once the slope change is read with it, and the falsification
tests (July placebos, which also show the model's intervals to be too narrow, forecasts made before
each July, twelve-month comparisons) that the apparent fall does not pass; and the design for the
lower speed limit on conventional roads, whose placebo test fails."""

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


def _months_after(start: pd.Timestamp, months: float) -> pd.Timestamp:
    """The month ``months`` (rounded) after ``start``."""
    return start + pd.DateOffset(months=int(round(months)))


def page_policy(captions: dict[str, str]) -> str:
    numbers = _policy_numbers()
    main, linear = numbers["main"], numbers["linear"]
    calendar, forecast = numbers["calendar"], numbers["forecast"]
    calibration, definitions = numbers["calibration"], numbers["definitions"]
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
    # The forecast check ranks the Julys by the proportional shortfall (the log ratio).
    beyond = forecast[forecast.log_ratio < float(true_forecast.log_ratio)].sort_values("log_ratio")
    others = calendar[~calendar.is_true].sort_values("level_change")
    runner_up, third = others.iloc[0], others.iloc[1]
    fuel, toll = sensitivity.loc["fuel"], sensitivity.loc["toll"]
    knot_2004 = sensitivity.loc["knot_2004"]
    negative_binomial = sensitivity.loc["negative_binomial"]
    extended = sensitivity.loc["long"]
    day_deaths = sensitivity.loc["24h"]
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
    # Which months had most deaths, year by year.
    peaks = transitions.dropna(subset=["peak_month"])
    summer_peaks = int(peaks.peak_month.isin((7, 8)).sum())
    # The point at which the slope change has worn the step away.
    back_on_path = _months_after(it.date, float(main.months_to_zero))
    lasting = sensitivity[sensitivity.mean_high < 0]
    # The 30-day and 24-hour series before and after the year their monthly ratio starts to vary.
    regime_from = int(definitions.regime_from.iloc[0])
    early_ratio = definitions[~definitions.later_regime.astype(bool)]
    late_ratio = definitions[definitions.later_regime.astype(bool)]
    window_years = definitions[definitions.year.between(it.pre_start.year, it.post_end.year)]
    checks = {
        "every specification has a human label": not unmapped,
        "the preferred pre-trend gives the smaller step": bool(
            linear.level_change < main.level_change < 0
        ),
        "the straight-line pre-trend gives the largest fall of every specification": bool(
            float(linear.level_change) == float(sensitivity.level_change.min())
        ),
        # The prose calls the bend's advantage clear but not decisive.
        "the pre-period months favour the bend by between 4 and 10 QAIC points": 4
        < float(straight.delta_qaic)
        < 10,
        "the step is followed by a rising slope that brings deaths back within the window": bool(
            float(main.slope_change_annual) > 0
            and math.isfinite(float(main.months_to_zero))
            and float(main.months_to_zero) < post_months
        ),
        "at the end of the window fitted deaths are above the projection": float(main.end_change)
        > 0,
        "averaged over the window, deaths are below the projection, with an interval that "
        "includes no change": float(main.mean_low)
        < float(main.mean_change)
        < 0
        < float(main.mean_high),
        "only the straight-line pre-trend gives an average fall whose interval excludes no "
        "change": list(lasting.index) == ["linear_trend"],
        "the extended window keeps a step whose interval includes no change": float(
            extended.level_low
        )
        < 0
        < float(extended.level_high),
        "July or August is the deadliest month in most years, but not all": len(peaks) // 2
        < summer_peaks
        < len(peaks),
        "every larger twelve-month fall came after the break": bool(
            len(larger) >= 1 and (larger.year > it.date.year).all()
        ),
        # The prose prints these two as falls, by their absolute size.
        "deaths fell across the July of the change": float(true_transition.twelve_month_ratio) < 0,
        "the months after the change fell below their forecast": float(true_forecast.log_ratio) < 0,
        "the out-of-sample test ranks other Julys above the true one": len(beyond) >= 1,
        "the forecast rank is the proportional shortfall": int(true_forecast["rank"])
        == len(beyond) + 1,
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
        "the placebo Julys exclude no change far more often than a 95% interval should": int(
            calibration.n_excluding_zero
        )
        > 2 * float(calibration.expected_excluding_zero)
        and float(calibration.se_ratio) > 1.5,
        "the interval set by the placebo spread includes no change": float(
            calibration.calibrated_low
        )
        < 0
        < float(calibration.calibrated_high),
        "the calibration describes the calendar-matched July": int(calibration.year) == it.date.year
        and abs(float(calibration.level_change) - float(true_calendar.level_change)) < 1e-9,
        "the chosen bend beats the straight line": float(chosen.qaic) < float(straight.qaic),
        # The hinge term is the change of slope at the bend: negative means a steeper decline.
        "the decline steepened at the chosen bend": bool(
            len(hinge) == 1 and float(hinge.estimate.iloc[0]) < 0
        ),
        "the 24-hour fit gives a similar step": abs(
            float(day_deaths.level_change) - float(main.level_change)
        )
        < 0.02,
        "the fitted window lies before the year the monthly 30-day to 24-hour ratio starts to "
        "vary": it.post_end.year < regime_from and not window_years.later_regime.astype(bool).any(),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"policy page: the tables no longer support: {failed}")

    crosses = sensitivity[sensitivity.level_high > 0]
    phrases = _crossing_phrases(crosses)
    body = summary(
        f"Spain's points-based driving licence came into force on {licence_date}. Monthly road "
        "deaths fell around that date, but the series cannot show that the licence caused the "
        "fall, or that the fall lasted. With the earlier trend projected the way the earlier "
        "months favour, a model of monthly deaths finds an immediate step of "
        f"{_signed_pct(float(main.level_change))} in {break_month} (95% interval "
        f"{_signed_pct(float(main.level_low))} to {_signed_pct(float(main.level_high))}), after "
        "which deaths drifted back to the projected path by about "
        f"{_month(back_on_path)}. Averaged over the {post_months} months to "
        f"{_month(it.post_end)}, deaths were "
        f"{abs(float(main.mean_change)) * 100:.1f}% below the projection (95% interval "
        f"{_signed_pct(float(main.mean_low), 1)} to {_signed_pct(float(main.mean_high), 1)}). "
        "Only a straight-line projection, which fits the earlier months less well, gives a fall "
        f"that lasts ({_signed_pct(float(linear.mean_change), 1)} on average). These intervals "
        f"are too narrow: at {int(calibration.n_excluding_zero)} of the "
        f"{int(calibration.n_placebos)} other Julys that can be tested, where nothing was "
        "introduced, the same kind of model finds a step whose 95% interval lies entirely on "
        "one side of zero. "
        f"Against those Julys the {it.date.year} step is the largest of "
        f"{int(true_calendar.n_fits)}, but only narrowly, and its shortfall against forecasts "
        f"made before each July is the {_ordinal(int(true_forecast['rank']))} largest of "
        f"{int(true_forecast.n_fits)}. Deaths had already begun to fall faster in "
        f"{pd.Timestamp(chosen.knot).year}."
    )

    body += "<h2>The estimate</h2>"
    body += (
        "<p>An interrupted time series fits the months before a change, projects them forward "
        "and measures how far the months after fall below the projection. The model here is a "
        "Poisson regression of monthly deaths within 30 days, from "
        f"{_month(it.pre_start)} to {_month(it.post_end)}, with a term for each calendar month, "
        f"a trend, and a step and a change of slope at {break_month}. The result depends on how "
        "the earlier trend is projected. A straight line through the months before the change "
        f"gives a step of {_signed_pct(float(linear.level_change))}. But the earlier months "
        "themselves favour a trend that bends: among trends with one bend, the best fit places "
        f"it at {_month(chosen.knot)}, where the decline steepened. It fits those months better "
        f"than the straight line by {float(straight.delta_qaic):.0f} points of QAIC, a measure "
        "of fit that penalises extra terms and here allows for monthly deaths varying more "
        "than a Poisson model assumes, with the position of the bend counted as a term. A "
        "difference of that size favours the bend but is not decisive. The choice uses only "
        "the months before the change.</p>"
        f"<p>With the bend in place the step is {_signed_pct(float(main.level_change))}, but it "
        "does not last. After the break the slope changes by "
        f"{_signed_pct(float(main.slope_change_annual), 1)} a year (95% interval "
        f"{_signed_pct(float(main.slope_low), 1)} to {_signed_pct(float(main.slope_high), 1)}), "
        f"so fitted deaths meet the projection again in about {_month(back_on_path)} and end "
        f"the window {float(main.end_change) * 100:.1f}% above it. Averaged over the "
        f"{post_months} months the change is {_signed_pct(float(main.mean_change), 1)} "
        f"({_signed_pct(float(main.mean_low), 1)} to {_signed_pct(float(main.mean_high), 1)}). "
        f"With the straight-line pre-trend the step is {_signed_pct(float(linear.level_change))} "
        f"and the average {_signed_pct(float(linear.mean_change), 1)} "
        f"({_signed_pct(float(linear.mean_low), 1)} to "
        f"{_signed_pct(float(linear.mean_high), 1)}).</p>"
    )
    body += figure(
        "p1_points_series",
        f"Monthly road deaths, {it.pre_start.year}–{it.post_end.year}, with the fitted model "
        "and two projections of deaths without the change: the preferred pre-trend (dashed) "
        "and a straight-line pre-trend (dotted)",
        captions,
    )
    candidates = trend.assign(
        label=[
            "Straight line, no bend" if pd.isna(knot) else f"Bend at {_month(knot)}"
            for knot in trend.knot
        ]
    )[["label", "qaic", "delta_qaic"]].rename(
        columns={"label": "Pre-trend", "qaic": "QAIC", "delta_qaic": "Difference from the best"}
    )
    body += technical(
        "Pre-trend candidates and their fit",
        table(
            candidates,
            f"Pre-trends fitted to the months before {break_month} only: the best candidates "
            "and the straight line. Lower QAIC is better; the log-likelihood is divided by the "
            f"Pearson dispersion of the best one-bend fit ({float(chosen.dispersion):.2f}), and a "
            "bend counts as two terms, its change of slope and its position.",
            {"QAIC": "dec", "Difference from the best": "dec"},
        ),
    )

    body += "<h2>How unusual the fall was</h2>"
    body += (
        "<p>Spanish road deaths usually peak in July or August: one of the two was the deadliest "
        f"month in {summer_peaks} of the {len(peaks)} years from {int(peaks.year.min())} to "
        f"{int(peaks.year.max())}. A break placed on 1 July can therefore pick up an ordinary "
        "summer movement. The same step model, with a straight-line trend "
        f"on a common window of {pre_months} months before and {post_months} after, was "
        f"therefore fitted at every July whose window avoids {break_month} and the pandemic. "
        f"July {it.date.year} gives the largest fall of the {int(true_calendar.n_fits)}, "
        f"{_signed_pct(float(true_calendar.level_change), 1)}, but only narrowly: July "
        f"{int(runner_up.year)} gives {_signed_pct(float(runner_up.level_change), 1)} and July "
        f"{int(third.year)} {_signed_pct(float(third.level_change), 1)}, and their intervals "
        f"overlap. Ranking first of {int(true_calendar.n_fits)} corresponds to a one-sided "
        f"p-value of about {1 / float(true_calendar.n_fits):.2f}, short of conventional "
        "significance.</p>"
        "<p>The same fits show that the model's own intervals are too narrow. At "
        f"{int(calibration.n_excluding_zero)} of the {int(calibration.n_placebos)} other Julys, "
        "where nothing was introduced, the 95% interval lies entirely on one side of zero; an "
        "interval with "
        "the coverage it claims would do so about "
        f"{float(calibration.expected_excluding_zero):.1f} times in "
        f"{int(calibration.n_placebos)}. The placebo steps vary "
        f"{float(calibration.se_ratio):.1f} times as much as the model's standard errors "
        f"imply. An interval set by that spread instead puts the July {it.date.year} step at "
        f"{_signed_pct(float(calibration.calibrated_low))} to "
        f"{_signed_pct(float(calibration.calibrated_high))}, which includes no change. The "
        "other intervals on this page come from the same kind of model and are labelled "
        "model-based.</p>"
    )
    body += figure(
        "p2_july_placebos",
        f"Estimated step in deaths at 1 July {it.date.year} and at the "
        f"{int(calibration.n_placebos)} other Julys of {int(calendar.year.min())}–"
        f"{int(calendar.year.max())} whose window avoids {break_month} and the pandemic, with "
        f"model-based 95% intervals; {break_month} is marked",
        captions,
    )
    body += (
        "<p>Two checks that use no step point the same way. Forecasting the "
        f"{post_months} months after each July from the {pre_months} months before it, the "
        f"months after {break_month} fall "
        f"{abs(math.expm1(float(true_forecast.log_ratio))) * 100:.1f}% below their forecast, "
        f"the {_ordinal(int(true_forecast['rank']))} largest shortfall of the "
        f"{int(true_forecast.n_fits)} Julys: the months after July "
        f"{_join([str(int(y)) for y in beyond.year])} fell further below their own forecasts. "
        "Dividing the deaths in the twelve months "
        "from each July by those in the twelve months before it, which cancels the seasons, "
        f"deaths fell {abs(math.expm1(float(true_transition.twelve_month_ratio))) * 100:.1f}% "
        f"across July {it.date.year}, the {_ordinal(int(true_transition['rank']))} largest fall "
        f"of the {int(true_transition.n_ranked)} years that can be measured; the larger falls "
        f"all came later, in {_join([str(int(year)) for year in sorted(larger.year)])}.</p>"
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

    with_fuel = _signed_pct(float(fuel.level_change))
    with_toll = _signed_pct(float(toll.level_change))
    adjusted = (
        f"to {with_fuel} in both cases"
        if with_fuel == with_toll
        else f"to {with_fuel} and {with_toll}"
    )
    body += "<h2>Why the fall cannot be attributed to the licence</h2>"
    body += (
        "<p>The step does not follow the available traffic series: adding national road-fuel "
        "consumption (CORES) or traffic intensity on the state toll motorways to the model "
        f"barely moves it, {adjusted}, against "
        f"{_signed_pct(float(main.level_change))} without either. But neither series measures "
        "kilometres on all roads. Inside the fitted window the step competes with two other "
        f"explanations: the decline had already steepened in {pd.Timestamp(chosen.knot).year}, "
        "and July-to-July movements nearly as large occur in years when nothing was introduced. "
        f"The window ends in {_month(it.post_end)}, so it leaves out the Penal Code reform "
        "that made serious speeding and drink-driving criminal offences, in force from "
        f"{_month(it.second_break)}, {penal_months} months after the licence, and the "
        "recession that followed. Extended to "
        f"{_month(it.long_post_end)}, with a second step at the reform, the model puts the "
        f"step at {break_month} at {_signed_pct(float(extended.level_change), 1)} "
        f"({_signed_pct(float(extended.level_low), 1)} to "
        f"{_signed_pct(float(extended.level_high), 1)}), and over that longer period the "
        "reform and the recession cannot be separated from the licence.</p>"
        f"<p>The estimate was repeated under {len(sensitivity)} specifications. The "
        "straight-line pre-trend gives the largest fall of all of them, and "
        f"{_count_word(len(crosses)).lower()} give a step whose interval includes no change"
        + (": " + _join(phrases) + "." if phrases else ".")
        + f" Averaged over the {post_months} months, every specification except the "
        "straight-line pre-trend gives a change whose interval includes no change. An "
        f"immediate fall of about {abs(float(main.level_change)) * 100:.0f}% that did not "
        "last is as much as the series supports.</p>"
    )
    shown = sensitivity.reset_index()
    shown = pd.DataFrame(
        {
            "Specification": [
                _specification_label(v, label) for v, label in zip(shown.variant, shown.label)
            ],
            f"Step at {break_month}": [
                f"{_signed_pct(r.level_change, 1)} ({_signed_pct(r.level_low, 1)} to "
                f"{_signed_pct(r.level_high, 1)})"
                for r in shown.itertuples()
            ],
            f"Average over the {post_months} months": [
                f"{_signed_pct(r.mean_change, 1)} ({_signed_pct(r.mean_low, 1)} to "
                f"{_signed_pct(r.mean_high, 1)})"
                for r in shown.itertuples()
            ],
        }
    )
    body += technical(
        f"Detailed results of all {len(sensitivity)} specifications",
        table(
            shown,
            f"Change in deaths at {break_month} and averaged over the {post_months} months from "
            f"it under each specification, with model-based 95% intervals, which the July "
            "placebos show to be too narrow; monthly deaths "
            f"{_month(it.pre_start)} to {_month(it.post_end)} unless stated. Before "
            f"{regime_from} the monthly ratio of 30-day to 24-hour deaths varies little within a "
            "year (a standard deviation of at most "
            f"{float(early_ratio.sd.max()):.3f}, against at least "
            f"{float(late_ratio.sd.min()):.3f} from {regime_from}), so the 30-day counts of the "
            "fitted window appear to be derived from the 24-hour counts, and the 24-hour "
            "specification repeats the main one rather than checking it.",
        ),
    )
    body += technical(
        f"The {speed_limit.date.year} speed limit on conventional roads",
        "<p>The lower speed limit on conventional roads was examined with a different design, "
        "comparing conventional roads with motorways and dual carriageways month by month. "
        "That design fails its placebo test: a break placed in "
        f"{_month(failed_placebo.break_date.iloc[0])}, before the change, produces a divergence "
        f"of its own ({_signed_pct(float(failed_placebo.level_change.iloc[0]))}, with an "
        "interval that excludes zero), so no estimate of the speed-limit change is reported. "
        'The fits are published (<a href="tables/q8_speed_placebo.csv">placebos</a>, '
        '<a href="tables/q8_speed_sensitivity.csv">specifications</a>).</p>',
    )
    body += limitation(
        "Monthly deaths vary more than a Poisson model assumes and are correlated from month "
        "to month; the intervals use Newey–West standard errors with "
        f"{policy.HAC_LAGS} lags, and a negative binomial model gives a similar step "
        f"({_signed_pct(float(negative_binomial.level_change))}). Even so, the July placebos "
        "show these model-based intervals to be too narrow. Choosing the pre-trend by QAIC is "
        "itself a selection step, which is why the alternative pre-trends and specifications "
        "are reported."
    )
    body += downloads(
        [
            ("q8_points_calendar_placebo", "July placebos"),
            ("q8_points_calibration", "how the July placebos calibrate the intervals"),
            ("q8_points_forecast", "forecasts made before each July"),
            ("q8_points_transitions", "twelve months either side of each July"),
            ("q8_points_trend_choice", "pre-trend candidates"),
            ("q8_points_sensitivity", "every specification"),
            ("q8_points_death_definitions", "30-day and 24-hour deaths by year"),
            ("q8_points_placebo", "placebo breaks at arbitrary months"),
        ],
        method=(f"{DOCS_URL}/methodology.md", "the case study in the full methodology"),
    )
    return render_page(
        "policy",
        f"The {it.date.year} points-based licence",
        f"Spain's monthly road deaths from {it.pre_start.year} to {it.post_end.year}, before "
        "and after the points-based driving licence came into force: how large the fall was, "
        "how long it lasted, how unusual it was, and why it cannot be attributed to the "
        "licence.",
        body,
    )
