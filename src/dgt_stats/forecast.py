"""Predicting a year's road deaths, and how large a change must be before the counts can show it.

A law is judged by comparing the deaths after it with the deaths that would have happened without
it. The second number is a forecast, and its error decides what the comparison can see. This
module builds that forecast as a small, validated model and measures its error honestly, out of
sample, so that the simulator can say whether a simulated effect would ever be visible.

**The model** is a Poisson regression (a generalised linear model) of monthly 30-day deaths, fitted
on the four years before the year it predicts:

    log E[deaths] = month of year + linear trend + b · log(road fuel) + calendar

where *road fuel* is CORES automotive petrol plus diesel for that month (the traffic) and the
*calendar* terms count the month's Fridays, Saturdays and Sundays. Traffic and calendar are known
once the month is over, so the forecast is the deaths the month's traffic and calendar would have
produced on the recent trend: the counterfactual a before-and-after comparison needs. Easter is
left out: in a four-year window it often falls in the same month every year, and its effect
cannot then be told from that month's.

**How it was chosen.** Four specifications and windows of three to eight years were compared by
rolling-origin forecasts: fit on the years before a year, predict that year's twelve months, move
on. The specification and window were chosen on the forecast years 2006–2015 alone; the errors
reported for it are those of 2016–2019 and 2022–2024, which played no part in the choice
(``SELECTION_YEARS``, ``HOLDOUT_YEARS``). The two lockdown years, 2020 and 2021, are scored
separately and never used to choose. Two naive forecasts (the same months last year; the mean of
the last three years) and a gradient-boosted tree with the same inputs are scored beside it.

The result is a split verdict, and the page reports it as one. In the years when the trend moved
(the selection years) or traffic collapsed (the lockdowns) the model beats last year's count by a
wide margin; in the flat years since 2016 last year's count is as good. A counterfactual for a law
has to survive both kinds of year, so the model is the one used. The trees do worse than the
model throughout, because a tree cannot extend a trend beyond the years it has seen.

**What the error means.** The forecast error of a sum of ``n`` years, measured the same way at each
horizon, splits into Poisson chance (``1 / expected deaths``) and an extra, multiplicative part
``tau_n`` that comes from the trend drifting away from the extrapolation. The second part grows
with the horizon, which is why waiting longer after a law does not make it easier to see. The
smallest effect a comparison can detect with 80 % power at the 5 % level is

    MDE = 1 − exp(−(z_0.975 + z_0.80) · sqrt(1 / expected + tau_n²)).
"""

from __future__ import annotations

import calendar
from functools import cache

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor

from dgt_stats import io_tables, io_traffic

OUTCOMES = {
    "deaths_all": "All roads",
    "deaths_interurban": "Interurban roads",
    "deaths_urban": "Urban streets",
}
WINDOW_YEARS = 4
CANDIDATE_WINDOWS = (3, 4, 5, 6, 7, 8)
SELECTION_YEARS = tuple(range(2006, 2016))
HOLDOUT_YEARS = (2016, 2017, 2018, 2019, 2022, 2023, 2024)
PANDEMIC_YEARS = (2020, 2021)
HORIZONS = (1, 2, 3, 4, 5)
POWER = 0.80
ALPHA = 0.05

CALENDAR = "fridays + saturdays + sundays"
SPECIFICATIONS = {
    "trend": "C(month) + t",
    "trend_calendar": f"C(month) + t + {CALENDAR}",
    "trend_traffic": "C(month) + t + log_fuel",
    "trend_traffic_calendar": f"C(month) + t + log_fuel + {CALENDAR}",
}
SPECIFICATION_LABELS = {
    "trend": "Month + trend",
    "trend_calendar": "Month + trend + calendar",
    "trend_traffic": "Month + trend + traffic",
    "trend_traffic_calendar": "Month + trend + traffic + calendar",
    "last_year": "Naive: same months last year",
    "mean_3_years": "Naive: mean of the last three years",
    "boosted_trees": "Gradient-boosted trees, same inputs",
}
CHOSEN = "trend_traffic_calendar"
TREE_FEATURES = ("month", "t", "log_fuel", "fridays", "saturdays", "sundays")


# --------------------------------------------------------------------------- inputs


def _weekday_count(year: int, month: int, weekday: int) -> int:
    days = calendar.monthrange(year, month)[1]
    return sum(1 for day in range(1, days + 1) if calendar.weekday(year, month, day) == weekday)


@cache
def model_panel() -> pd.DataFrame:
    """Monthly deaths by zone with road fuel and the calendar, from January 1996.

    Deaths are the yearbook's monthly 30-day series; fuel is CORES petrol plus diesel. The panel
    stops at the last month with both.
    """
    monthly = io_tables.read_table("series_monthly")
    deaths = monthly[monthly.metric == "deaths_30d"].pivot_table(
        index=["year", "month"], columns="zone", values="value", aggfunc="first"
    )
    deaths.columns = [f"deaths_{zone}" for zone in deaths.columns]
    fuel = io_traffic.read_cores_fuel()[["year", "month", "road_fuel_tonnes"]]
    out = deaths.reset_index().merge(fuel, on=["year", "month"], how="inner")
    out = out.dropna(subset=[*OUTCOMES, "road_fuel_tonnes"]).astype({"year": int, "month": int})
    out["t"] = out.year + (out.month - 0.5) / 12
    out["log_fuel"] = np.log(out.road_fuel_tonnes)
    out["fridays"] = [_weekday_count(y, m, 4) for y, m in zip(out.year, out.month)]
    out["saturdays"] = [_weekday_count(y, m, 5) for y, m in zip(out.year, out.month)]
    out["sundays"] = [_weekday_count(y, m, 6) for y, m in zip(out.year, out.month)]
    return out.sort_values(["year", "month"]).reset_index(drop=True)


# --------------------------------------------------------------------------- fitting


def fit(train: pd.DataFrame, outcome: str, specification: str = CHOSEN):
    """The Poisson regression of ``outcome`` on one specification, with Pearson dispersion."""
    formula = f"{outcome} ~ {SPECIFICATIONS[specification]}"
    return smf.glm(formula, data=train, family=sm.families.Poisson()).fit(scale="X2")


def _training(panel: pd.DataFrame, year: int, window: int) -> pd.DataFrame:
    return panel[(panel.year >= year - window) & (panel.year < year)]


def predict_year(
    panel: pd.DataFrame, outcome: str, year: int, method: str, window: int = WINDOW_YEARS
) -> np.ndarray:
    """Monthly predictions for ``year`` from the ``window`` years before it, by one method."""
    test = panel[panel.year == year]
    if method == "last_year":
        previous = panel[panel.year == year - 1].set_index("month")[outcome]
        return previous.loc[test.month].to_numpy(dtype=float)
    if method == "mean_3_years":
        recent = panel[panel.year.between(year - 3, year - 1)].groupby("month")[outcome].mean()
        return recent.loc[test.month].to_numpy(dtype=float)
    train = _training(panel, year, window)
    if method == "boosted_trees":
        model = HistGradientBoostingRegressor(
            loss="poisson", max_iter=200, learning_rate=0.05, max_depth=3, random_state=0
        )
        model.fit(train[list(TREE_FEATURES)], train[outcome])
        return model.predict(test[list(TREE_FEATURES)])
    return np.asarray(fit(train, outcome, method).predict(test), dtype=float)


def _scored_years() -> tuple[int, ...]:
    return SELECTION_YEARS + PANDEMIC_YEARS + HOLDOUT_YEARS


def _set(year: int) -> str:
    if year in SELECTION_YEARS:
        return "selection"
    return "pandemic" if year in PANDEMIC_YEARS else "holdout"


def rolling_forecasts() -> pd.DataFrame:
    """One row per outcome, method, window and forecast year: observed and predicted annual totals.

    The GLM specifications are run at every candidate window; the naive forecasts and the trees
    at the chosen window only (the naive ones do not use it).
    """
    panel = model_panel()
    last = int(panel.year.max())
    records = []
    for outcome in OUTCOMES:
        for year in [y for y in _scored_years() if y <= last]:
            observed = float(panel.loc[panel.year == year, outcome].sum())
            runs = [(spec, window) for spec in SPECIFICATIONS for window in CANDIDATE_WINDOWS]
            runs += [(m, WINDOW_YEARS) for m in ("last_year", "mean_3_years", "boosted_trees")]
            for method, window in runs:
                predicted = float(predict_year(panel, outcome, year, method, window).sum())
                records.append(
                    {
                        "outcome": outcome,
                        "method": method,
                        "window": window,
                        "year": year,
                        "set": _set(year),
                        "observed": observed,
                        "predicted": predicted,
                        "log_error": np.log(observed / predicted),
                    }
                )
    return pd.DataFrame.from_records(records)


def _error_summary(frame: pd.DataFrame) -> pd.Series:
    errors = frame.log_error
    return pd.Series(
        {
            "years": int(len(errors)),
            "rmse": float(np.sqrt(np.mean(errors**2))),
            "mean_abs_error": float(np.mean(np.abs(errors))),
            "bias": float(np.mean(errors)),
        }
    )


@cache
def _rolling() -> pd.DataFrame:
    return rolling_forecasts()


def model_selection() -> pd.DataFrame:
    """Every method and window, scored separately on the selection years and the holdout years.

    Errors are on the log scale of the annual total: an ``rmse`` of 0.06 is about 6 %.
    """
    frame = _rolling()
    out = (
        frame.groupby(["outcome", "method", "window", "set"])
        .apply(_error_summary, include_groups=False)
        .reset_index()
    )
    out["outcome_label"] = out.outcome.map(OUTCOMES)
    out["method_label"] = out.method.map(SPECIFICATION_LABELS)
    selection = out[(out.set == "selection") & (out.outcome == "deaths_all")]
    glm = selection[selection.method.isin(SPECIFICATIONS)]
    best = glm.loc[glm.rmse.idxmin()]
    out["chosen"] = (out.method == best.method) & (out.window == best.window)
    return out[
        [
            "outcome",
            "outcome_label",
            "method",
            "method_label",
            "window",
            "set",
            "years",
            "rmse",
            "mean_abs_error",
            "bias",
            "chosen",
        ]
    ]


def validation() -> pd.DataFrame:
    """The chosen model against the naive forecasts and the trees, in each kind of year.

    ``set`` is ``selection`` (2006–2015, used to choose), ``holdout`` (2016–2019 and 2022–2024,
    never used to choose) or ``pandemic`` (2020–2021, never used to choose).
    """
    selection = model_selection()
    rows = selection[selection.window == WINDOW_YEARS]
    keep = [CHOSEN, "trend", "last_year", "mean_3_years", "boosted_trees"]
    out = rows[rows.method.isin(keep)].copy()
    out["order"] = out.method.map({name: i for i, name in enumerate(keep)})
    out["set_order"] = out.set.map({"selection": 0, "holdout": 1, "pandemic": 2})
    out = out.sort_values(["outcome", "set_order", "order"])
    return out.drop(columns=["order", "set_order", "chosen"]).reset_index(drop=True)


def backtest() -> pd.DataFrame:
    """Each scored year's deaths beside the chosen model's forecast and last year's count."""
    frame = _rolling()
    keep = frame[
        (frame.window == WINDOW_YEARS) & frame.method.isin([CHOSEN, "last_year", "boosted_trees"])
    ]
    out = keep.pivot_table(
        index=["outcome", "year", "set", "observed"], columns="method", values="predicted"
    ).reset_index()
    out.columns.name = None
    out = out.rename(columns={CHOSEN: "model", "last_year": "naive_last_year"})
    out["outcome_label"] = out.outcome.map(OUTCOMES)
    return out[
        [
            "outcome",
            "outcome_label",
            "year",
            "set",
            "observed",
            "model",
            "naive_last_year",
            "boosted_trees",
        ]
    ].sort_values(["outcome", "year"])


# --------------------------------------------------------------------------- horizons


@cache
def horizon_errors() -> pd.DataFrame:
    """Error of the chosen model's forecast of an ``n``-year total, for n = 1 to 5.

    Each origin year from 2006 is fitted on the four years before it and the next ``n`` years are
    predicted with their observed traffic and calendar; windows that contain 2020 or 2021 are left
    out. ``tau`` is the error left once Poisson chance on the observed total is taken out: the
    drift of the trend, which applies to any count of deaths in the same zone whatever its size.
    """
    panel = model_panel()
    last = int(panel.year.max())
    records = []
    for outcome in OUTCOMES:
        for origin in range(SELECTION_YEARS[0], last + 1):
            if origin in PANDEMIC_YEARS:
                continue
            result = fit(_training(panel, origin, WINDOW_YEARS), outcome)
            for n in HORIZONS:
                years = list(range(origin, origin + n))
                if years[-1] > last or set(years) & set(PANDEMIC_YEARS):
                    continue
                test = panel[panel.year.isin(years)]
                observed = float(test[outcome].sum())
                predicted = float(np.asarray(result.predict(test)).sum())
                records.append(
                    {
                        "outcome": outcome,
                        "horizon": n,
                        "origin": origin,
                        "observed": observed,
                        "log_error": np.log(observed / predicted),
                    }
                )
    errors = pd.DataFrame.from_records(records)
    out = (
        errors.groupby(["outcome", "horizon"])
        .apply(
            lambda g: pd.Series(
                {
                    "origins": int(len(g)),
                    "rmse": float(np.sqrt(np.mean(g.log_error**2))),
                    "bias": float(g.log_error.mean()),
                    "poisson_variance": float(np.mean(1 / g.observed)),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    out["tau"] = np.sqrt(np.clip(out.rmse**2 - out.poisson_variance, 0, None))
    out["outcome_label"] = out.outcome.map(OUTCOMES)
    return out


def minimum_detectable_effect(
    expected: float, tau: float, power: float = POWER, alpha: float = ALPHA
) -> float:
    """Smallest proportional fall in a count of ``expected`` deaths that the comparison detects."""
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float(1 - np.exp(-z * np.sqrt(1 / expected + tau**2)))


def detectability() -> pd.DataFrame:
    """The minimum detectable effect for each zone and horizon, at the zone's recent deaths.

    ``expected`` is the mean annual deaths of the last three years times the horizon.
    """
    panel = model_panel()
    last = int(panel.year.max())
    recent = panel[panel.year > last - 3].groupby("year")[list(OUTCOMES)].sum().mean()
    out = horizon_errors()[["outcome", "outcome_label", "horizon", "tau"]].copy()
    out["expected"] = [float(recent[o]) * n for o, n in zip(out.outcome, out.horizon)]
    out["mde"] = [minimum_detectable_effect(e, t) for e, t in zip(out.expected, out.tau)]
    out["mde_deaths_per_year"] = out.mde * out.expected / out.horizon
    return out


# --------------------------------------------------------------------------- what it learned


def coefficients() -> pd.DataFrame:
    """The chosen model fitted on the last four years: what it says about traffic and calendar.

    The traffic coefficient is an elasticity (a 1 % change in road fuel goes with a ``b`` % change
    in deaths, month for month, given the season and the trend); the calendar coefficients are
    the proportional change in a month's deaths for one more Friday, Saturday or Sunday. With
    four years of data these are imprecise, and they are reported with that in view.
    """
    panel = model_panel()
    last = int(panel.year.max())
    train = _training(panel, last + 1, WINDOW_YEARS)
    labels = {
        "log_fuel": "Road fuel (elasticity)",
        "fridays": "One more Friday",
        "saturdays": "One more Saturday",
        "sundays": "One more Sunday",
        "t": "Trend, per year",
    }
    records = []
    for outcome in OUTCOMES:
        result = fit(train, outcome)
        interval = result.conf_int()
        for term, label in labels.items():
            estimate, low, high = (
                float(result.params[term]),
                float(interval.loc[term, 0]),
                float(interval.loc[term, 1]),
            )
            as_ratio = term != "log_fuel"
            records.append(
                {
                    "outcome": outcome,
                    "outcome_label": OUTCOMES[outcome],
                    "term": term,
                    "term_label": label,
                    "estimate": np.exp(estimate) if as_ratio else estimate,
                    "low": np.exp(low) if as_ratio else low,
                    "high": np.exp(high) if as_ratio else high,
                    "scale": "rate ratio" if as_ratio else "elasticity",
                    "first_year": last - WINDOW_YEARS + 1,
                    "last_year": last,
                    "dispersion": float(result.scale),
                }
            )
    return pd.DataFrame.from_records(records)
