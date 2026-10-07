"""Forecasting monthly road deaths: a Poisson model fitted only to DGT's monthly series and CORES
road fuel, how well it forecasts years it had not seen, and how large a change in deaths the yearly
counts can reveal. The selection details, the coefficients and the comparison made after the test
sit in collapsed technical blocks.

Every number is read from the committed ``forecast_*`` tables or the forecast module's constants;
the sentences that compare forecasts are guarded by checks that stop the build when the tables no
longer say so.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import forecast
from dgt_stats.site.components import (
    DOCS_URL,
    _fmt_int,
    _fmt_pct,
    downloads,
    figure,
    limitation,
    read_table,
    render_page,
    summary,
    table,
    technical,
)

SETS = ("selection", "holdout", "pandemic")
ZONES = ("deaths_all", "deaths_interurban", "deaths_urban")
# The four versions of the model share month and trend terms and differ only in whether they add
# road fuel and the weekend-day counts; the prose describes them that way.
VERSIONS = {"trend", "trend_calendar", "trend_traffic", "trend_traffic_calendar"}


def _count_word(value: int) -> str:
    """A small count as a capitalised word, for the start of a sentence."""
    words = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight"}
    return words.get(value, str(value))


def _span(years: list[int]) -> str:
    """Consecutive runs of years as ranges with an en dash, joined in words."""
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

    # The trees' leaf size that scores best on the held-out years, found by looking at them after
    # the test; it is reported beside the comparison and was never among the forecasts chosen from.
    trees = selection[
        (selection.family == "trees") & (selection.outcome == "deaths_all")
    ].pivot_table(index="method", columns="set", values="rmse")
    hindsight = str(trees.drop(index=tree).holdout.idxmin())
    holdout_all = selection[(selection.outcome == "deaths_all") & (selection.set == "holdout")]
    checks = {
        "on urban streets the month-and-trend form scored better in the selection years": rmse(
            "deaths_urban", "selection", "trend"
        )
        < rmse("deaths_urban", "selection", chosen),
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
        # The plain reason for "summing more years does not help": the trend's drift grows with
        # every year summed.
        "the drift of the trend grows with the years summed in every zone": all(
            detect.loc[zone].tau.is_monotonic_increasing for zone in ZONES
        ),
        # "Four times in five" and "the four years before" are fixed in the prose; they hold
        # only while the module's constants say so.
        "the power and window are the ones the prose names": (
            forecast.POWER == 0.8 and forecast.WINDOW_YEARS == 4
        ),
        "the versions differ only by road fuel and the weekend-day counts": (
            set(forecast.SPECIFICATIONS) == VERSIONS
        ),
        "the worst held-back year was forecast from a window with a lockdown year": bool(
            set(range(worst_year - forecast.WINDOW_YEARS, worst_year)) & set(years["pandemic"])
        ),
        "the model does worse than last year's count in the ordinary held-out years": (
            rmse("deaths_all", "holdout", chosen) > rmse("deaths_all", "holdout", "last_year")
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
                "Drift of the trend, one year": _fmt_pct(one.tau),
                "Fall detected in one year": (
                    f"{_fmt_pct(one.mde, 0)} ({_fmt_int(one.mde_deaths_per_year)} deaths)"
                ),
                "Rise detected in one year": (
                    f"{_fmt_pct(rise, 0)} ({_fmt_int(rise * float(one.expected))} deaths)"
                ),
                "Fall detected over five years": _fmt_pct(five.mde, 0),
            }
        )
    return pd.DataFrame(rows)


def page_forecast(captions: dict[str, str]) -> str:
    n = forecast_numbers()
    rmse, years, detect = n["rmse"], n["years"], n["detect"]
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
    worst_year = n["worst_year"]
    level = _fmt_pct(forecast.ALPHA, 0)
    window = forecast.WINDOW_YEARS
    model_holdout = rmse("deaths_all", "holdout", chosen)
    naive_holdout = rmse("deaths_all", "holdout", "last_year")
    model_lockdown = rmse("deaths_all", "pandemic", chosen)
    naive_lockdown = rmse("deaths_all", "pandemic", "last_year")

    body = summary(
        f"In ordinary years not used to build the model ({holdout_years}), repeating the "
        "previous year's monthly counts forecast a year's road deaths more accurately than the "
        f"fitted Poisson model: an error of {_fmt_pct(naive_holdout)} of the year's deaths against "
        f"{_fmt_pct(model_holdout)}. The model is therefore not used as the forecast for "
        f"ordinary years. It did much better in the lockdown years, {pandemic_years}, when "
        "traffic collapsed and the model was given each month's fuel sales: an error of "
        f"{_fmt_pct(model_lockdown)} against {_fmt_pct(naive_lockdown)}. Its errors also set "
        "how large a change a year of counts can reveal: against the forecast, a fall of "
        f"{_fmt_pct(one_all.mde, 0)} ({_fmt_int(one_all.mde_deaths_per_year)} deaths) or a "
        f"rise of {_fmt_pct(rise_all, 0)} in one year's deaths on all roads is detected four "
        "times in five."
    )

    body += "<h2>The model and the simple forecasts</h2>"
    body += (
        "<p>The model is a Poisson regression (the standard regression for counts) of each "
        "month's deaths within 30 days on the month of the year, a linear trend, the month's "
        "road-fuel sales (CORES petrol plus diesel) and its number of Fridays, Saturdays and "
        f"Sundays, fitted to the {_count_word(window).lower()} years before the year being "
        "forecast. It is fitted "
        "separately for all roads, interurban roads and urban streets, from DGT's monthly series "
        "and CORES fuel alone. Its form and fitting window were chosen on its forecasts of "
        f"{selection_years}, and it was then scored on {holdout_years}, years that played no "
        f"part in the choice; the lockdown years, {pandemic_years}, are scored separately. It is "
        "compared with repeating last year's monthly counts, the mean of the last three years, "
        "and gradient-boosted trees (a flexible machine-learning method) given the same "
        "inputs.</p>"
    )

    def row(label: str, errors: dict[str, float]) -> dict[str, str]:
        return {
            "Forecast": label,
            f"Selection years, {selection_years}": _fmt_pct(errors["selection"]),
            f"Held-out years, {holdout_years}": _fmt_pct(errors["holdout"]),
            f"Lockdown years, {pandemic_years}": _fmt_pct(errors["pandemic"]),
        }

    def method(name: str) -> dict[str, float]:
        return {kind: rmse("deaths_all", kind, name) for kind in SETS}

    rows = [
        row("Poisson model: month, trend, road fuel and weekend days", method(chosen)),
        row("Poisson model: month and trend only", method("trend")),
        row("Gradient-boosted trees, same inputs", method(tree)),
        row("Last year's monthly counts", method("last_year")),
        row("Mean of the last three years", method("mean_3_years")),
    ]
    body += table(
        pd.DataFrame(rows),
        "Forecast error for a year's deaths on all roads (root-mean-square error as a share of "
        f"the year's deaths), each year forecast from the {_count_word(window).lower()} years "
        "before it.",
    )
    body += (
        f"<p>The model's largest miss in the held-out years was {worst_year}, forecast from a "
        "window that included the lockdowns. The trees were less accurate than the model in "
        "every set of years and on every type of road: a tree cannot extend a trend beyond the "
        f"range it has seen, and with only {window * 12} monthly observations it fits "
        "noise.</p>"
    )
    body += figure(
        "k1_forecast_check",
        "Each year's deaths on all roads, with the model's forecast and last year's count",
        captions,
    )
    body += technical(
        "How the model and the trees were chosen",
        f"<p>{_count_word(len(forecast.SPECIFICATIONS))} versions of the model (all with month "
        "and trend terms, with or without road fuel and the weekend-day counts) and fitting "
        f"windows of {min(forecast.CANDIDATE_WINDOWS)} to {max(forecast.CANDIDATE_WINDOWS)} "
        "years were compared by forecasting each year from the years before it, and the "
        f"version and window with the smallest error on all roads in {selection_years} were "
        "kept. The trees' one important setting, the smallest number of months a tree may "
        "group together, was chosen on the same years. On urban streets alone the "
        "month-and-trend form scored better in the selection years "
        f"({_fmt_pct(rmse('deaths_urban', 'selection', 'trend'))} against "
        f"{_fmt_pct(rmse('deaths_urban', 'selection', chosen))}), but one form is used for "
        "every type of road. The "
        f'<a href="{DOCS_URL}/models/dgt_monthly_deaths_forecast.md">model card</a> also '
        "reports a tree setting found by looking at the held-out years, which is therefore not "
        "an independent test.</p>",
    )

    body += "<h2>How large a change a year of counts can reveal</h2>"
    body += (
        "<p>Judging whether deaths changed after some event means comparing the recorded count "
        "with a forecast of what it would otherwise have been, and a change shows only when it "
        "is large against the forecast's ordinary error. That error has two parts. Chance "
        "variation in the number of deaths shrinks, as a share, the more deaths are counted. "
        "Drift, the distance between the trend fitted to earlier years and the real course of "
        "deaths, grows the further the trend is projected: measured on the model's own past "
        f"forecasts for all roads, it is {_fmt_pct(one_all.tau)} of one year's deaths and "
        f"{_fmt_pct(five_all.tau)} of a five-year total. This section uses the model's errors "
        "rather than those of last year's counts because the model allows for changes in "
        "traffic through fuel sales: a change being judged may come with a change in traffic, "
        "as in the lockdown years, when repeating last year's counts missed badly.</p>"
        "<p>Together the two parts set the change that such a comparison detects four times in "
        f"five, with a two-sided test at the {level} level. For one year of deaths on all roads "
        f"that is a fall of {_fmt_pct(one_all.mde, 0)} or a rise of {_fmt_pct(rise_all, 0)}; a "
        f"fall half that size, about {_fmt_pct(half, 0)}, is detected only "
        f"{_fmt_pct(half_power, 0)} of the time. Interurban roads need a fall of "
        f"{_fmt_pct(one_inter.mde, 0)}, and urban streets, with fewer deaths and a less steady "
        f"trend, {_fmt_pct(one_urban.mde, 0)}. Because the drift grows faster than chance "
        "variation shrinks, summing more years raises the threshold: over five years it is "
        f"{_fmt_pct(five_all.mde, 0)} on all roads.</p>"
    )
    body += table(
        _detect_rows(detect, last_years),
        "Changes in deaths that a comparison with the forecast detects four times in five "
        f"(two-sided test at the {level} level), at each road type's average deaths in "
        f"{last_years}. Drift is the error of the extrapolated trend.",
    )
    body += figure(
        "k2_detectability",
        "Fall in deaths detected four times in five against the number of years summed, for "
        "all roads, interurban roads and urban streets",
        captions,
    )
    body += (
        "<p>A change smaller than these thresholds, whatever its cause, can be real and still "
        "leave no clear mark on a year's deaths, so a year without a visible change is weak "
        "evidence that nothing changed.</p>"
    )
    body += limitation(
        f"The drift is measured on forecasts made from {years['selection'][0]} on, the "
        "selection years included, so it describes the whole period, and the thresholds "
        "assume the forecast's errors are as large after a change as before it. Road fuel is "
        "national and is observed after any change being judged: for a change that itself "
        "alters how much people drive, the comparison measures the change in deaths at the "
        "fuel sales actually recorded and leaves out any part that works through traffic."
    )
    body += downloads(
        [
            ("forecast_validation", "the model against the naive forecasts and the trees"),
            ("forecast_selection", "every version, window and tree setting"),
            ("forecast_backtest", "each year's forecasts"),
            ("forecast_horizons", "forecast error by years summed"),
            ("forecast_detectability", "changes detected four times in five"),
            ("forecast_coefficients", "the model's coefficients"),
        ],
        method=("data.html#models", "how models are tested on held-out data"),
    )
    return render_page(
        "forecast",
        "Forecasting monthly road deaths",
        "A Poisson model of Spain's monthly road deaths, tested against repeating the previous "
        "year's counts, and the size of change in deaths that one or several years of counts "
        "can reveal.",
        body,
    )
