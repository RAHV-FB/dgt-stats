"""Monthly deaths: a forecasting model fitted only to the repository's series, how it was chosen
and tested on years it had not seen, and how large a change in deaths the yearly counts can show.

Every number is read from the committed ``forecast_*`` tables; the sentences that compare
forecasts are guarded by checks that stop the build when the tables no longer say so.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import forecast
from dgt_stats.site.components import (
    _fmt_int,
    _fmt_pct,
    _signed_pct,
    conclusion,
    downloads,
    figure,
    key_figures,
    limits,
    read_table,
    render_page,
    table,
)

SETS = ("selection", "holdout", "pandemic")
ZONES = ("deaths_all", "deaths_interurban", "deaths_urban")


def _span(years: list[int]) -> str:
    """Consecutive runs of years in words: '2006–2015', '2016–2019 and 2022–2024'."""
    years = sorted(years)
    runs: list[list[int]] = []
    for year in years:
        if runs and year == runs[-1][-1] + 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    parts = [str(r[0]) if len(r) == 1 else f"{r[0]}–{r[-1]}" for r in runs]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def forecast_numbers() -> dict:
    """The tables behind the page, and the checks that hold its sentences to them."""
    validation = (
        read_table("forecast_validation").set_index(["outcome", "set", "method"]).sort_index()
    )
    selection = read_table("forecast_selection")
    backtest = read_table("forecast_backtest")
    detect = read_table("forecast_detectability").set_index(["outcome", "horizon"]).sort_index()
    coefficients = read_table("forecast_coefficients").set_index(["outcome", "term"])
    chosen, tree = forecast.CHOSEN, forecast.TREE_METHOD
    years = {kind: sorted(backtest[backtest.set == kind].year.unique()) for kind in SETS}
    held = backtest[(backtest.outcome == "deaths_all") & (backtest.set == "holdout")]
    errors = (held.observed / held.model - 1).abs()
    worst_year = int(held.year.loc[errors.idxmax()])

    def rmse(outcome: str, kind: str, method: str) -> float:
        return float(validation.loc[(outcome, kind, method), "rmse"])

    # The comparator found by looking at the held-back years: the trees' leaf size that scores best
    # there. It is disclosed, never a candidate.
    trees = selection[
        (selection.family == "trees") & (selection.outcome == "deaths_all")
    ].pivot_table(index="method", columns="set", values="rmse")
    hindsight = str(trees.drop(index=tree).holdout.idxmin())
    holdout_all = selection[(selection.outcome == "deaths_all") & (selection.set == "holdout")]
    checks = {
        "the model is chosen on the selection years": bool(
            selection[selection.chosen & (selection.family == "model")].method.eq(chosen).all()
        ),
        "the model beats last year's count by more than half where the trend or traffic moved": all(
            rmse("deaths_all", kind, chosen) < rmse("deaths_all", kind, "last_year") / 2
            for kind in ("selection", "pandemic")
        ),
        "last year's count does slightly better in the held-back years": (
            rmse("deaths_all", "holdout", "last_year")
            < rmse("deaths_all", "holdout", chosen)
            < rmse("deaths_all", "holdout", "last_year") + 0.02
        ),
        "the tuned trees do worse than the model in every zone and set": all(
            rmse(zone, kind, tree) > rmse(zone, kind, chosen) for zone in ZONES for kind in SETS
        ),
        "the hindsight trees are the best forecast of the held-back years": (
            holdout_all.loc[holdout_all.rmse.idxmin(), "method"] == hindsight
        ),
        "the hindsight trees lose where the trend or traffic moved": all(
            float(trees.loc[hindsight, kind]) > rmse("deaths_all", kind, chosen)
            for kind in ("selection", "pandemic")
        ),
        "waiting makes a change harder to see in every zone": all(
            detect.loc[zone].mde.is_monotonic_increasing for zone in ZONES
        ),
        "urban streets need a larger change than interurban roads": (
            float(detect.loc[("deaths_urban", 1), "mde"])
            > float(detect.loc[("deaths_interurban", 1), "mde"])
        ),
        "the coefficients' window includes a lockdown year": (
            int(coefficients.first_year.min()) <= max(years["pandemic"])
        ),
        "urban streets have the less steady trend": (
            float(detect.loc[("deaths_urban", 1), "tau"])
            > float(detect.loc[("deaths_interurban", 1), "tau"])
        ),
        # The words "four times in five", "the 5% level" and "the four years before" are fixed
        # in the prose; they hold only while the module's constants say so.
        "the power, level and window are the ones the prose names": (
            forecast.POWER == 0.8 and forecast.ALPHA == 0.05 and forecast.WINDOW_YEARS == 4
        ),
        "the worst held-back year was forecast from a window with a lockdown year": bool(
            set(range(worst_year - forecast.WINDOW_YEARS, worst_year)) & set(years["pandemic"])
        ),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"forecast page: the tables no longer support: {failed}")
    return {
        "validation": validation,
        "trees": trees,
        "hindsight": hindsight,
        "backtest": backtest,
        "detect": detect,
        "coefficients": coefficients,
        "years": years,
        "rmse": rmse,
        "worst_year": worst_year,
    }


def _detect_rows(detect: pd.DataFrame, last_years: str) -> pd.DataFrame:
    rows = []
    for zone in ZONES:
        one, five = detect.loc[(zone, 1)], detect.loc[(zone, 5)]
        rise = forecast.minimum_detectable_rise(float(one.expected), float(one.tau))
        rows.append(
            {
                "Roads": one.outcome_label,
                f"Deaths a year, {last_years}": _fmt_int(one.expected),
                "Drift of the forecast, one year": _fmt_pct(one.tau),
                "Fall one year shows 4 times in 5": (
                    f"{_fmt_pct(one.mde, 0)} ({_fmt_int(one.mde_deaths_per_year)} deaths)"
                ),
                "Rise one year shows 4 times in 5": (
                    f"{_fmt_pct(rise, 0)} ({_fmt_int(rise * float(one.expected))} deaths)"
                ),
                "Fall five years of deaths show 4 times in 5": _fmt_pct(five.mde, 0),
            }
        )
    return pd.DataFrame(rows)


def page_forecast(captions: dict[str, str]) -> str:
    n = forecast_numbers()
    rmse, years, detect = n["rmse"], n["years"], n["detect"]
    trees, hindsight = n["trees"], n["hindsight"]
    chosen, tree = forecast.CHOSEN, forecast.TREE_METHOD
    selection_years, holdout_years = _span(years["selection"]), _span(years["holdout"])
    pandemic_years = _span(years["pandemic"])
    last = int(n["backtest"].year.max())
    last_years = f"{last - 2}–{last}"
    one_all, five_all = detect.loc[("deaths_all", 1)], detect.loc[("deaths_all", 5)]
    one_inter, one_urban = detect.loc[("deaths_interurban", 1)], detect.loc[("deaths_urban", 1)]
    rise_all = forecast.minimum_detectable_rise(float(one_all.expected), float(one_all.tau))
    half = 0.5 * float(one_all.mde)
    half_power = forecast.detection_power(
        -half * float(one_all.expected), float(one_all.expected), float(one_all.tau)
    )
    fuel = n["coefficients"].loc[("deaths_all", "log_fuel")]
    saturday = n["coefficients"].loc[("deaths_all", "saturdays")]
    worst_year = n["worst_year"]
    leaf = hindsight.rsplit("_", 1)[-1]

    body = key_figures(
        [
            (
                "Error on years it had not seen",
                _fmt_pct(rmse("deaths_all", "holdout", chosen)),
                f"of a year's deaths on all roads, {holdout_years}; last year's count "
                f"{_fmt_pct(rmse('deaths_all', 'holdout', 'last_year'))}",
            ),
            (
                "Error in the lockdown years",
                _fmt_pct(rmse("deaths_all", "pandemic", chosen)),
                f"{pandemic_years}; last year's count "
                f"{_fmt_pct(rmse('deaths_all', 'pandemic', 'last_year'))}",
            ),
            (
                "Fall one year's count shows",
                _fmt_pct(one_all.mde, 0),
                f"of {_fmt_int(one_all.expected)} deaths a year on all roads, four times in five",
            ),
            (
                "Summed over five years",
                _fmt_pct(five_all.mde, 0),
                "the threshold grows as the trend drifts from the forecast",
            ),
        ]
    )
    body += (
        '<p class="answer">A Poisson model of each month\'s deaths, fitted to the four years '
        "before the year it predicts, forecasts a year's deaths on Spain's roads with a "
        f"root-mean-square error of {_fmt_pct(rmse('deaths_all', 'holdout', chosen))} in "
        "years it had not seen, and of "
        f"{_fmt_pct(rmse('deaths_all', 'pandemic', chosen))} in the lockdown years, when "
        "repeating last year's count was off by "
        f"{_fmt_pct(rmse('deaths_all', 'pandemic', 'last_year'))}. That error sets how large a "
        "change the yearly counts can show: against the forecast, one year of deaths on all "
        f"roads shows a fall of {_fmt_pct(one_all.mde, 0)} "
        f"({_fmt_int(one_all.mde_deaths_per_year)} deaths) or a rise of "
        f"{_fmt_pct(rise_all, 0)} four times in five. Smaller changes show less often, and "
        "waiting longer does not help.</p>"
    )

    body += "<h2>What the model is</h2>"
    body += (
        "<p>Any before-and-after reading of the death counts compares the deaths after a change "
        "with the deaths there would have been without it, and the second number is a forecast. "
        "This one is a Poisson regression of each month's deaths within 30 days on the month of "
        "the year, a linear trend over the four years before, the month's road fuel (CORES "
        "petrol plus diesel, standing for the traffic) and its number of Fridays, Saturdays and "
        "Sundays. It is fitted separately for all roads, interurban roads and urban streets, "
        "only to DGT's monthly series and CORES fuel; no value in it comes from a study made "
        f"elsewhere. Fitted on {int(fuel.first_year)}–{int(fuel.last_year)}, a window that "
        "includes a lockdown year, a month with 1% more road fuel is associated with about "
        f"{fuel.estimate:.1f}% more deaths ({fuel.low:.1f} to {fuel.high:.1f}), and one more "
        f"Saturday with {_signed_pct(float(saturday.estimate) - 1)} "
        f"({_signed_pct(float(saturday.low) - 1)} to {_signed_pct(float(saturday.high) - 1)}). "
        "These are associations within four years of months, not effects of traffic or of "
        "weekends.</p>"
    )

    body += "<h2>How it was chosen and tested</h2>"
    body += (
        f"<p>{len(forecast.SPECIFICATIONS)} forms of the model and windows of "
        f"{min(forecast.CANDIDATE_WINDOWS)} to {max(forecast.CANDIDATE_WINDOWS)} years were "
        "scored by "
        "forecasting each year from the years before it. The form and the window were chosen on "
        f"the forecasts of {selection_years} alone; {holdout_years} played no part in the "
        f"choice and are the test, and the lockdown years {pandemic_years} are scored apart. "
        "Beside the model are two naive forecasts and gradient-boosted trees given the same "
        "inputs, their leaf size tuned on the same selection years.</p>"
    )

    def row(label: str, errors: dict[str, float]) -> dict[str, str]:
        return {
            "Forecast": label,
            f"Years used to choose, {selection_years}": _fmt_pct(errors["selection"]),
            f"Held-back years, {holdout_years}": _fmt_pct(errors["holdout"]),
            f"Lockdown years, {pandemic_years}": _fmt_pct(errors["pandemic"]),
        }

    def method(name: str) -> dict[str, float]:
        return {kind: rmse("deaths_all", kind, name) for kind in SETS}

    rows = [
        row("Poisson model: month, trend, road fuel and weekend days (chosen)", method(chosen)),
        row("The same with month and trend only", method("trend")),
        row(
            f"Gradient-boosted trees, same inputs, tuned on {selection_years}",
            method(tree),
        ),
        row("Last year's count", method("last_year")),
        row("Mean of the last three years", method("mean_3_years")),
    ]
    body += table(
        pd.DataFrame(rows),
        "Error of each forecast of a year's deaths on all roads (root mean square, as a share of "
        "the year's deaths): each year forecast from the four before it",
    )
    body += (
        "<p><strong>What the test shows.</strong> The model beats the tuned trees in every set "
        "of years and in each zone: a tree cannot extend a trend beyond the years it has seen, "
        f"and with {forecast.WINDOW_YEARS * 12} monthly rows it fits the noise. In the lockdown "
        "years it beats last year's "
        "count by far, since it is given each month's fuel. In the flat held-back years last "
        "year's count does slightly better "
        f"({_fmt_pct(rmse('deaths_all', 'holdout', 'last_year'))} against "
        f"{_fmt_pct(rmse('deaths_all', 'holdout', chosen))}; the worst year is {worst_year}, "
        "forecast from a window that includes the lockdowns). A before-and-after comparison has "
        "to hold in years when traffic or the trend moves, and whether the years ahead will be "
        "flat is not known when the forecast is made, so the model is the one used.</p>"
    )
    body += (
        "<p><strong>A comparator disclosed, not chosen.</strong> Looking at the held-back years "
        f"afterwards, trees with leaves of at least {leaf} months would have scored "
        f"{_fmt_pct(float(trees.loc[hindsight, 'holdout']))} there, better than every other "
        "forecast. That leaf size was found by looking at the test years, so its score there is "
        "not a test, and it was never a candidate; it also does worse than the model in the "
        f"selection years ({_fmt_pct(float(trees.loc[hindsight, 'selection']))}) and in the "
        f"lockdowns ({_fmt_pct(float(trees.loc[hindsight, 'pandemic']))}). It is reported so "
        "that the choice can be judged with it in view.</p>"
    )
    body += figure("k1_forecast_check", "Each year's deaths against two forecasts", captions)

    body += "<h2>How large a change the counts can show</h2>"
    body += (
        "<p>The forecast's error on a year's total splits into Poisson chance, which shrinks as "
        "the count grows, and a drift of the trend away from the forecast, measured here on "
        f"every forecast the model made from {years['selection'][0]} on. Together they give the "
        "change in deaths "
        "that a comparison of the observed count with the forecast picks up four times in five "
        "at the 5% level. For one year of deaths on all roads that is a fall of "
        f"{_fmt_pct(one_all.mde, 0)} or a rise of {_fmt_pct(rise_all, 0)}; a fall half that "
        f"size, about {_fmt_pct(half, 0)}, shows only {_fmt_pct(half_power, 0)} of the time. "
        f"Interurban roads need a fall of {_fmt_pct(one_inter.mde, 0)}, and urban streets, with "
        f"fewer deaths and a less steady trend, {_fmt_pct(one_urban.mde, 0)}. Summing more years "
        "does not help, because the drift grows faster than the count: over five years the fall "
        f"that shows four times in five on all roads is {_fmt_pct(five_all.mde, 0)}.</p>"
    )
    body += table(
        _detect_rows(detect, last_years),
        "The change in deaths a comparison with the forecast picks up four times in five, at the "
        f"5% level, at each zone's deaths a year in {last_years}",
    )
    body += figure(
        "k2_detectability",
        "The fall in deaths a comparison detects four times in five, by years summed",
        captions,
    )
    body += downloads(
        [
            ("forecast_validation", "model against the naive forecasts and the trees"),
            ("forecast_selection", "every specification, window and leaf size"),
            ("forecast_backtest", "each year's forecasts"),
            ("forecast_horizons", "forecast error by years summed"),
            ("forecast_detectability", "changes detected four times in five"),
            ("forecast_coefficients", "what the model learned"),
        ]
    )

    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Fitted only to Spain's own monthly deaths and road fuel, a small Poisson model "
        "forecasts a year's deaths about as well as last year's count in flat years and far "
        "better when traffic or the trend moves, and gradient-boosted trees given the same "
        "inputs and tuned the same way do not beat it. Its error means that one year of "
        "national counts shows a change in "
        f"deaths reliably only from about {_fmt_pct(one_all.mde, 0)} down or "
        f"{_fmt_pct(rise_all, 0)} up, and urban counts only from about "
        f"{_fmt_pct(one_urban.mde, 0)}. A smaller change, whatever its cause, can be real and "
        "still not show in a year's deaths; a year without a visible change is not evidence "
        "that nothing changed."
    )
    body += limits(
        "The form of the model was chosen on all roads; on urban streets alone the month-and-"
        "trend form scored better in the selection years "
        f"({_fmt_pct(rmse('deaths_urban', 'selection', 'trend'))} against "
        f"{_fmt_pct(rmse('deaths_urban', 'selection', chosen))}). The drift that sets the "
        f"detectable change is measured on forecasts made from {years['selection'][0]} on, the "
        "selection years "
        "included, so it describes the whole period rather than the held-back years alone. Road "
        "fuel is national and is observed after any change being judged: for a change that "
        "itself alters how much people drive, the comparison speaks only of deaths for the "
        "traffic there was. The detectable change assumes the forecast's errors are as large "
        "after a change as before it, and a comparison with a forecast says whether deaths "
        "differ from it, not why."
    )
    return render_page(
        "forecast",
        "Monthly deaths: a forecasting model",
        "A small model of Spain's monthly road deaths, fitted only to DGT's series and road "
        "fuel, tested on years it had not seen, and what its error says about how large a "
        "change in deaths a year of counts can show.",
        body,
    )
