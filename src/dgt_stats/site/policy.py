"""The points-based driving licence: monthly road deaths around its start, the step that did not
last once the slope change is read with it, and the falsification tests (July placebos, which also
show the model's intervals to be too narrow, and forecasts made before each July) that the apparent
fall does not pass. The model, the choice of pre-trend, the twelve-month comparisons, every
specification and the design for the lower speed limit on conventional roads, whose placebo test
fails, are technical notes on the methodology page (``technical_notes``)."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pandas as pd

from dgt_stats import policy, risk_trends
from dgt_stats.site.components import (
    ALL_PAGES,
    DOCS_URL,
    _fmt_pct,
    _join,
    _ordinal,
    _signed_pct,
    downloads,
    figure,
    read_table,
    render_page,
    summary,
    table,
)
from dgt_stats.site.numbers import _long_run_numbers, _policy_numbers

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
TITLES = dict(ALL_PAGES)
# The section of the methodology page that holds this page's technical notes.
NOTES = "policy-method"


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


def _year_runs(years: list[int]) -> str:
    """Years as runs of consecutive years, so [1, 3, 4, 5] reads '1 and 3–5'."""
    runs: list[list[int]] = []
    for year in sorted(years):
        if runs and year == runs[-1][-1] + 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    return _join([str(r[0]) if len(r) == 1 else f"{r[0]}–{r[-1]}" for r in runs])


def _months_after(start: pd.Timestamp, months: float) -> pd.Timestamp:
    """The month ``months`` (rounded) after ``start``."""
    return start + pd.DateOffset(months=int(round(months)))


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the tables, with the checks
    that the sentences built on them still hold."""
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
    # The steep segment of the long-run count, against which a fall across one July is read.
    segments = _long_run_numbers()["segments"].query("measure == 'count'")
    steep = segments[(segments.start <= it.date.year) & (segments.end > it.date.year)].iloc[0]
    window_years = definitions[definitions.year.between(it.pre_start.year, it.post_end.year)]
    # The Julys the placebo design leaves out inside its range, and why: their windows hold the
    # true July.
    placebo_years = sorted(int(year) for year in calendar.year)
    left_out = sorted(set(range(placebo_years[0], placebo_years[-1] + 1)) - set(placebo_years))
    series = read_table("q8_points_series")
    after = series[series.post.astype(bool)]
    crosses = sensitivity[sensitivity.level_high > 0]
    checks = {
        "every specification has a human label": not unmapped,
        "the Julys left out inside the placebo range are those whose window holds the change": (
            bool(left_out)
            and all(
                pd.Timestamp(year=y, month=7, day=1) - pd.DateOffset(months=pre_months)
                <= it.date
                < pd.Timestamp(year=y, month=7, day=1) + pd.DateOffset(months=post_months)
                for y in left_out
            )
        ),
        "the slope change makes the average smaller than the step": abs(float(main.mean_change))
        < abs(float(main.level_change)),
        "the straight-line counterfactual lies above the preferred one after the change": bool(
            len(after) > 0 and (after.counterfactual_linear > after.counterfactual_main).all()
        ),
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
        "the true July's interval overlaps the runner-up's and the third's": float(runner_up.low)
        <= float(true_calendar.high)
        and float(third.low) <= float(true_calendar.high),
        # A rank of 1 among n fits is a one-sided p of 1/n; the notes call it short of
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
        "that year is the first DGT counted 30-day deaths directly": regime_from
        == risk_trends.DEATHS_30D_COUNTED_FROM,
        "the change falls inside the steep segment of the long-run count, and the fall across "
        "it is no larger than a year of that segment's decline": float(steep.annual_change) < 0
        and abs(math.expm1(float(true_transition.twelve_month_ratio)))
        < abs(float(steep.annual_change)) * 1.25,
        "the window ends before the second break": it.post_end < it.second_break,
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"policy page: the tables no longer support: {failed}")
    return SimpleNamespace(**locals())


def _adjusted(f: SimpleNamespace) -> str:
    """The step with each traffic series added, in words."""
    with_fuel = _signed_pct(float(f.fuel.level_change))
    with_toll = _signed_pct(float(f.toll.level_change))
    return (
        f"to {with_fuel} in both cases"
        if with_fuel == with_toll
        else f"to {with_fuel} and {with_toll}"
    )


def page_policy(captions: dict[str, str]) -> str:
    f = _facts()
    main, linear, it = f.main, f.linear, f.it
    calibration, true_calendar, true_forecast = f.calibration, f.true_calendar, f.true_forecast
    runner_up, third, post_months = f.runner_up, f.third, f.post_months
    notes_link = f'<a href="data.html#{NOTES}">technical notes</a>'

    body = summary(
        f"Spain's points-based driving licence came into force on {f.licence_date}. Road deaths "
        "fell around that date, but the series cannot show that the licence caused the fall, or "
        f"that it lasted: averaged over the {post_months} months to {_month(it.post_end)}, "
        f"deaths were {abs(float(main.mean_change)) * 100:.1f}% below the projection from the "
        f"earlier trend (95% interval {_signed_pct(float(main.mean_low), 1)} to "
        f"{_signed_pct(float(main.mean_high), 1)}). The model's intervals are too narrow: at "
        f"{int(calibration.n_excluding_zero)} of the {int(calibration.n_placebos)} other Julys, "
        "when nothing was introduced, it finds a step whose interval excludes zero."
    )

    body += (
        f'<h2 id="estimate">An immediate fall of about {abs(float(main.level_change)) * 100:.0f}% '
        "that did not last</h2>"
        "<p>A Poisson regression of monthly deaths within 30 days from "
        f"{_month(it.pre_start)} to {_month(it.post_end)}, with a term for each calendar month, "
        f"a trend, and a step and a change of slope at {f.break_month}, finds an immediate step "
        f"of {_signed_pct(float(main.level_change))} (95% interval "
        f"{_signed_pct(float(main.level_low))} to {_signed_pct(float(main.level_high))}). The "
        f"slope then changes by {_signed_pct(float(main.slope_change_annual), 1)} a year, so "
        f"fitted deaths rejoin the projected path in about {_month(f.back_on_path)} and end the "
        f"window {float(main.end_change) * 100:.1f}% above it; averaged over the {post_months} "
        f"months, the change is {_signed_pct(float(main.mean_change), 1)}.</p>"
        "<p>The result depends on how the earlier trend is projected. A straight line gives a "
        f"step of {_signed_pct(float(linear.level_change))} and a lasting fall, "
        f"{_signed_pct(float(linear.mean_change), 1)} on average "
        f"({_signed_pct(float(linear.mean_low), 1)} to "
        f"{_signed_pct(float(linear.mean_high), 1)}), but fits the months before the change "
        f"less well than a trend that bends once, in {_month(f.chosen.knot)}, where the decline "
        f"steepened: by {float(f.straight.delta_qaic):.0f} points of QAIC, a measure of fit that "
        "penalises extra terms. That difference favours the bend without being decisive.</p>"
    )
    body += figure(
        "p1_points_series",
        f"Line chart of observed monthly road deaths, {it.pre_start.year}–{it.post_end.year}, "
        f"with the fitted model and, from {f.licence_date}, two counterfactual projections "
        "without the change: the preferred pre-trend (dashed) and a straight-line pre-trend "
        "(dotted). Fitted deaths drop below the dashed projection at the change and rejoin it "
        f"by about {_month(f.back_on_path)}. The dotted projection lies above the dashed one "
        "throughout, so it gives the larger drop.",
        captions,
    )

    body += (
        '<h2 id="placebos">Falls nearly as large occur in Julys when nothing changed</h2>'
        "<p>Deaths usually peak in July or August, so a break placed on 1 July can pick up an "
        "ordinary summer movement. Fitted with a straight-line trend at July "
        f"{it.date.year} and at every other July from {f.placebo_years[0]} to "
        f"{f.placebo_years[-1]} whose window avoids it and the pandemic, the same kind of model "
        f"puts the July {it.date.year} step at "
        f"{_signed_pct(float(true_calendar.level_change), 1)}, the largest of "
        f"{int(true_calendar.n_fits)}, but only narrowly: July {int(runner_up.year)} gives "
        f"{_signed_pct(float(runner_up.level_change), 1)} and July {int(third.year)} "
        f"{_signed_pct(float(third.level_change), 1)}, with overlapping intervals.</p>"
    )
    body += figure(
        "p2_july_placebos",
        f"Dot chart of the estimated step in monthly deaths at 1 July of each of "
        f"{int(true_calendar.n_fits)} years from {f.placebo_years[0]} to "
        f"{f.placebo_years[-1]}, with model-based 95% intervals; the Julys of "
        f"{_year_runs(f.left_out)} are left out because their windows include {f.break_month}. "
        f"July {it.date.year} has the largest fall, "
        f"{_signed_pct(float(true_calendar.level_change), 1)}, with July {int(runner_up.year)} "
        f"({_signed_pct(float(runner_up.level_change), 1)}) and July {int(third.year)} "
        f"({_signed_pct(float(third.level_change), 1)}) close behind and overlapping it. Of "
        f"the other {int(calibration.n_placebos)} intervals, "
        f"{int(calibration.n_excluding_zero)} exclude zero.",
        captions,
    )
    body += (
        "<p>The same fits show the model's intervals to be too narrow: at "
        f"{int(calibration.n_excluding_zero)} of the {int(calibration.n_placebos)} other Julys "
        "the 95% interval excludes zero, where about "
        f"{float(calibration.expected_excluding_zero):.1f} would be expected. An interval set "
        f"by the spread of the placebo steps puts July {it.date.year} at "
        f"{_signed_pct(float(calibration.calibrated_low))} to "
        f"{_signed_pct(float(calibration.calibrated_high))}, which includes no change. "
        "Forecasts made before each July agree: the months after "
        f"{f.break_month} fall {abs(math.expm1(float(true_forecast.log_ratio))) * 100:.1f}% "
        f"below their forecast, the {_ordinal(int(true_forecast['rank']))} largest of "
        f"{int(true_forecast.n_fits)}.</p>"
    )

    body += (
        '<h2 id="attribution">The fall cannot be attributed to the licence</h2>'
        "<p>Adding national road-fuel consumption (CORES) or traffic intensity on the state toll "
        f"motorways barely moves the step, {_adjusted(f)}, against "
        f"{_signed_pct(float(main.level_change))} without either, but neither series measures "
        "kilometres on all roads. Within the fitted window the step competes with two other "
        f"explanations: the decline had already steepened in {pd.Timestamp(f.chosen.knot).year}, "
        "and Julys when nothing was introduced show steps nearly as large.</p>"
        f"<p>The window ends in {_month(it.post_end)}, before the Penal Code reform that made "
        "serious speeding and drink-driving criminal offences and before the recession that "
        "followed; over a longer window they cannot be separated from the licence. Every "
        f"specification tried, and the twelve-month comparisons, are in the {notes_link}.</p>"
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
        method=(f"data.html#{NOTES}", "the model, the placebos and every specification"),
    )
    return render_page(
        "policy",
        f"The {it.date.year} points-based licence",
        f"Monthly road deaths in Spain from {it.pre_start.year} to {it.post_end.year}, before "
        f"and after the points-based driving licence came into force in {f.break_month}.",
        body,
    )


def technical_notes(captions: dict[str, str]) -> str:
    """The model and the choice of pre-trend, the July placebos and the comparisons that fit no
    step, every specification and the speed-limit design: one section for the methodology
    page."""
    del captions
    f = _facts()
    main, it, calibration = f.main, f.it, f.calibration
    true_calendar, true_forecast, true_transition = (
        f.true_calendar,
        f.true_forecast,
        f.true_transition,
    )
    sensitivity, break_month, post_months, pre_months = (
        f.sensitivity,
        f.break_month,
        f.post_months,
        f.pre_months,
    )
    licence = f'<a href="policy.html">{TITLES["policy"]}</a>'
    document = f'<a href="{DOCS_URL}/methodology.md">methods document</a>'

    body = (
        f'<h2 id="{NOTES}">{TITLES["policy"]}: model, placebos and specifications</h2>'
        f"<p>These notes support {licence}; the {document} gives the full account, in its "
        f"section on the {it.date.year} case study.</p>"
        '<h3 id="policy-model">The model and the choice of pre-trend</h3>'
        "<p>The model is a Poisson regression of monthly deaths within 30 days from "
        f"{_month(it.pre_start)} to {_month(it.post_end)}, with a term for each calendar month, "
        f"a trend, and a step and a change of slope at {break_month}. It projects the months "
        "before the change forward and measures how far the months after fall below that "
        f"projection. After the step of {_signed_pct(float(main.level_change))}, the slope "
        f"changes by {_signed_pct(float(main.slope_change_annual), 1)} a year (95% interval "
        f"{_signed_pct(float(main.slope_low), 1)} to {_signed_pct(float(main.slope_high), 1)}), "
        f"so fitted deaths meet the projection again in about {_month(f.back_on_path)}. That is "
        f"why the average over the {post_months} months is smaller than the step.</p>"
        "<p>Monthly deaths vary more than a Poisson model assumes and are correlated from month "
        "to month; the intervals use standard errors that allow for both (Newey–West, "
        f"{policy.HAC_LAGS} lags), and a negative binomial model gives a similar step "
        f"({_signed_pct(float(f.negative_binomial.level_change))}). Even so, the July placebos "
        "show these model-based intervals to be too narrow.</p>"
        f"<p>The earlier months favour a trend that bends once, in {_month(f.chosen.knot)}, "
        "where the decline steepened: it fits them better than the straight line by "
        f"{float(f.straight.delta_qaic):.0f} points of QAIC, a measure of fit that penalises "
        "extra terms and allows for monthly deaths varying more than a Poisson model assumes. "
        "A difference of that size favours the bend but is not decisive. The choice uses only "
        "the months before the change; it is still a selection step, which is why the "
        "alternative pre-trends and specifications are reported.</p>"
    )
    candidates = f.trend.assign(
        label=[
            "Straight line, no bend" if pd.isna(knot) else f"Bend at {_month(knot)}"
            for knot in f.trend.knot
        ]
    )[["label", "qaic", "delta_qaic"]].rename(
        columns={"label": "Pre-trend", "qaic": "QAIC", "delta_qaic": "Difference from the best"}
    )
    body += table(
        candidates,
        f"Pre-trends fitted to the months before {break_month} only: the best candidates "
        "and the straight line. Lower QAIC is better; the log-likelihood is divided by the "
        f"Pearson dispersion of the best one-bend fit ({float(f.chosen.dispersion):.2f}), and a "
        "bend counts as two terms, its change of slope and its position.",
        {"QAIC": "dec", "Difference from the best": "dec"},
    )

    peaks = f.peaks
    body += (
        '<h3 id="policy-placebos">July placebos, forecasts and twelve-month comparisons</h3>'
        "<p>Spanish road deaths usually peak in July or August: one of the two was the deadliest "
        f"month in {f.summer_peaks} of the {len(peaks)} years from {int(peaks.year.min())} to "
        f"{int(peaks.year.max())}. The same step model, with a straight-line trend on a common "
        f"window of {pre_months} months before and {post_months} after, was fitted at every "
        f"July from {f.placebo_years[0]} to {f.placebo_years[-1]} whose window does not include "
        f"{break_month} or the pandemic; that leaves out the Julys of {_year_runs(f.left_out)}.</p>"
        f"<p>If the licence had changed nothing, July {it.date.year} would still rank first one "
        f"time in {int(true_calendar.n_fits)}, a one-sided p-value of about "
        f"{1 / float(true_calendar.n_fits):.2f}. That is the smallest this test can give with "
        f"{int(true_calendar.n_fits)} Julys, so it cannot reach conventional significance; the "
        "narrow margin over the next July is the better guide.</p>"
        f"<p>At {int(calibration.n_excluding_zero)} of the {int(calibration.n_placebos)} other "
        "Julys, where nothing was introduced, the 95% interval lies entirely on one side of "
        "zero; an interval with the coverage it claims would do so about "
        f"{float(calibration.expected_excluding_zero):.1f} times in "
        f"{int(calibration.n_placebos)}. The placebo steps vary "
        f"{float(calibration.se_ratio):.1f} times as much as the model's standard errors imply. "
        f"An interval set by that spread puts the July {it.date.year} step at "
        f"{_signed_pct(float(calibration.calibrated_low))} to "
        f"{_signed_pct(float(calibration.calibrated_high))}, which includes no change. The other "
        "intervals of the case study come from the same kind of model, so they are probably too "
        "narrow as well.</p>"
        f"<p>Two checks fit no step. Forecasting the {post_months} months after each July from "
        f"the {pre_months} months before it, the months after {break_month} fall "
        f"{abs(math.expm1(float(true_forecast.log_ratio))) * 100:.1f}% below their forecast, "
        f"the {_ordinal(int(true_forecast['rank']))} largest shortfall of the "
        f"{int(true_forecast.n_fits)} Julys; the months after July "
        f"{_join([str(int(y)) for y in f.beyond.year])} fell further below their own forecasts. "
        "Comparing the twelve months from each July with the twelve months before it, which "
        "cancels the seasons, deaths fell "
        f"{abs(math.expm1(float(true_transition.twelve_month_ratio))) * 100:.1f}% across July "
        f"{it.date.year}, the {_ordinal(int(true_transition['rank']))} largest fall of the "
        f"{int(true_transition.n_ranked)} years that can be measured.</p>"
        "<p>The larger falls all came later, in "
        f"{_join([str(int(year)) for year in sorted(f.larger.year)])}. This comparison does not "
        f"remove the trend: over {int(f.steep.start)}–{int(f.steep.end)} deaths fell about "
        f"{_fmt_pct(abs(float(f.steep.annual_change)), 0)} a year, so a fall of this size across "
        "one July is what the trend alone would give.</p>"
    )
    largest = f.ranked.nsmallest(8, "twelve_month_ratio")
    show = pd.concat([largest, f.ranked[f.ranked.year == it.date.year]]).drop_duplicates("year")
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
    body += table(
        shown_transitions,
        f"The {_count_word(len(largest)).lower()} largest falls across a July, among the "
        f"{int(true_transition.n_ranked)} years that can be measured. The month-to-month "
        "columns show the summer movement; the twelve-month column compares the same "
        f"calendar months on each side. The years {f.excluded[0]}–{f.excluded[-1]} are left out "
        "because the pandemic breaks the comparison.",
    )

    extended, phrases = f.extended, _crossing_phrases(f.crosses)
    body += (
        '<h3 id="policy-specifications">Every specification</h3>'
        "<p>Adding national road-fuel consumption (CORES) or traffic intensity on the state toll "
        f"motorways to the model barely moves the step, {_adjusted(f)}, against "
        f"{_signed_pct(float(main.level_change))} without either. The window ends in "
        f"{_month(it.post_end)}, so it leaves out the Penal Code reform that made serious "
        "speeding and drink-driving criminal offences, in force from "
        f"{_month(it.second_break)}, {f.penal_months} months after the licence, and the "
        f"recession that followed. Extended to {_month(it.long_post_end)}, with a second step at "
        f"the reform, the model puts the step at {break_month} at "
        f"{_signed_pct(float(extended.level_change), 1)} "
        f"({_signed_pct(float(extended.level_low), 1)} to "
        f"{_signed_pct(float(extended.level_high), 1)}).</p>"
        f"<p>The estimate was repeated under {len(sensitivity)} specifications. The "
        "straight-line pre-trend gives the largest fall of all of them, and "
        f"{_count_word(len(f.crosses)).lower()} give a step whose interval includes no change"
        + (": " + _join(phrases) + "." if phrases else ".")
        + f" Averaged over the {post_months} months, every specification except the "
        "straight-line pre-trend gives a change whose interval includes no change.</p>"
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
    body += table(
        shown,
        f"Change in deaths at {break_month} and averaged over the {post_months} months from "
        f"it under each specification, with model-based 95% intervals, which the July "
        "placebos show to be too narrow; monthly deaths "
        f"{_month(it.pre_start)} to {_month(it.post_end)} unless stated. Until "
        f"{f.regime_from - 1} DGT estimated 30-day deaths from 24-hour deaths with correction "
        "factors (see Long-run trends), so the 30-day counts of the "
        "fitted window are derived from the 24-hour counts, and the 24-hour specification "
        "repeats the main one rather than checking it.",
    )
    body += (
        f'<h3 id="policy-speed-limit">The {f.speed_limit.date.year} speed limit on conventional '
        "roads</h3>"
        "<p>The lower speed limit on conventional roads was examined with a different design, "
        "comparing conventional roads with motorways and dual carriageways month by month. "
        "That design fails its placebo test: a break placed in "
        f"{_month(f.failed_placebo.break_date.iloc[0])}, before the change, produces a "
        f"divergence of its own ({_signed_pct(float(f.failed_placebo.level_change.iloc[0]))}, "
        "with an interval that excludes zero), so no estimate of the speed-limit change is "
        'reported. The fits are published (<a href="tables/q8_speed_placebo.csv">placebos</a>, '
        '<a href="tables/q8_speed_sensitivity.csv">specifications</a>).</p>'
    )
    return body
