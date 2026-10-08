"""Predicting a year's road deaths, and how large a change in them the counts can detect.

**Status: withdrawn, kept as the record of the analysis; the site reads nothing from it.** Two
findings retired it. It is not a forecast in the ordinary sense: it conditions on each month's own
road-fuel sales, which are known only once the month is over, so it estimates the deaths a month's
traffic would have brought rather than predicting them ahead. And on the ordinary held-out years it
lost to repeating last year's count (an error of 6.6% of a year's deaths against 5.9%;
``reports/tables/review_forecast.csv``, ``docs/research/ML_MODEL_REVIEW.md``). The description
below is of the model as it was built.

Any before-and-after reading of the death counts compares the deaths after a change with the
deaths there would have been without it. The second number is a forecast, and its error decides
how large a change the comparison can see. This module builds that forecast as a small model of
Spain's monthly deaths, fitted and validated only on the repository's own series (DGT's monthly
30-day deaths and CORES road fuel), and measures its error out of sample. Nothing in it comes
from an external study: its result is the minimum detectable change, a property of the Spanish
death series and of how well its recent past predicts its next years.

**The model** is a Poisson regression (a generalised linear model) of monthly 30-day deaths, fitted
on the four years before the year it predicts, separately for all roads, interurban roads and
urban streets; one row is one month of Spain:

    log E[deaths] = month of year + linear trend + b · log(road fuel) + calendar

where *road fuel* is CORES automotive petrol plus diesel for that month (the traffic) and the
*calendar* terms count the month's Fridays, Saturdays and Sundays. Traffic and calendar are known
once the month is over, so the forecast is the deaths the month's traffic and calendar would have
been associated with on the recent trend: the counterfactual a before-and-after comparison needs.
Fuel is national and covers every road, so it is a predictor with a fitted coefficient, not a
denominator for urban or interurban deaths. It is also observed after any change being judged:
for a change that itself alters how much people drive, conditioning on fuel removes the part of
the change that works through traffic, and the comparison then speaks only of deaths for the
traffic there was. Easter is left out: in a four-year window it often falls in the same month
every year, and its effect cannot then be told from that month's.

**How it was chosen.** Four specifications and windows of three to eight years were compared by
rolling-origin forecasts: fit on the years before a year, predict that year's twelve months, move
on. The specification and window were chosen on the forecast years 2006–2015 alone; the errors
reported for it are those of 2016–2019 and 2022–2024, which played no part in the choice
(``SELECTION_YEARS``, ``HOLDOUT_YEARS``). The two lockdown years, 2020 and 2021, are scored
separately and never used to choose. Two naive forecasts (the same months last year; the mean of
the last three years) and gradient-boosted trees with the same inputs are scored beside it; the
trees' leaf size, the one setting that matters on 48 monthly rows, is chosen on the same
selection years from ``TREE_LEAF_CANDIDATES``.

The result is a split verdict. In the years when the trend moved (the selection years) or traffic
collapsed (the lockdowns) the model beats last year's count by a wide margin; in the flat
held-back years, the only ones that played no part in choosing it, last year's count does better
(an error of 5.9% of the year's deaths against 6.6%). The independent review of every model
(``docs/research/ML_MODEL_REVIEW.md``) therefore removed the model as a published forecast, and
with it the minimum detectable change derived from its errors: the module is kept as the record
of the analysis and is no longer read by the site. The trees, tuned
the same way, do worse than the model in every zone and every kind of year: a tree cannot extend
a trend beyond the years it has seen, and with 48 rows a small leaf fits the noise. Looking at
the held-back years afterwards, trees with larger leaves, worse on the selection years, would
have beaten both the model and last year's count there; that leaf size was found with the test
years, so it is reported only as a disclosed comparator and is never a candidate. A setting that
wins only in flat years cannot be picked in advance, because whether the years ahead will be flat
is not known when a forecast is made.

**What the error means.** The forecast error of a sum of ``n`` years, measured the same way at each
horizon, splits into Poisson chance (``1 / expected deaths``) and an extra, multiplicative part
``tau_n`` that comes from the trend drifting away from the extrapolation. The second part grows
with the horizon, which is why waiting longer after a change does not make it easier to see. The
chance that a two-sided comparison at the 5 % level shows a change in its own direction
(:func:`detection_power`) is ``Φ(d − z_0.975)``, with ``d = |log(1 + change / expected)| / sigma``
and ``sigma = sqrt(1 / expected + tau_n²)``. It is 80 % for a fall of

    MDE = 1 − exp(−(z_0.975 + z_0.80) · sigma),

the minimum detectable effect, and for a rise of ``exp((z_0.975 + z_0.80) · sigma) − 1``. The MDE
is the change detected four times in five, not a line below which nothing shows. ``tau_n`` is
measured on every forecast origin from 2006 on, the selection years included, so it describes the
chosen model's error over the whole period rather than on the held-back years alone.
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
# The trees' smallest leaf, tuned on the selection years like the model's specification: the
# library default of 20 leaves room for one split in 48 monthly rows, which cannot carry a season.
TREE_LEAF_CANDIDATES = (1, 2, 3, 5, 8, 12, 20)
SPECIFICATION_LABELS = {
    "trend": "Month + trend",
    "trend_calendar": "Month + trend + calendar",
    "trend_traffic": "Month + trend + traffic",
    "trend_traffic_calendar": "Month + trend + traffic + calendar",
    "last_year": "Naive: same months last year",
    "mean_3_years": "Naive: mean of the last three years",
    **{
        f"boosted_trees_leaf_{n}": f"Gradient-boosted trees, same inputs, leaves of at least {n}"
        for n in TREE_LEAF_CANDIDATES
    },
}
CHOSEN = "trend_traffic_calendar"
TREE_FEATURES = ("month", "t", "log_fuel", "fridays", "saturdays", "sundays")
TREE_LEAF = 1
TREE_METHOD = f"boosted_trees_leaf_{TREE_LEAF}"


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
    if method.startswith("boosted_trees_leaf_"):
        model = HistGradientBoostingRegressor(
            loss="poisson",
            max_iter=200,
            learning_rate=0.05,
            max_depth=3,
            min_samples_leaf=int(method.rsplit("_", 1)[1]),
            random_state=0,
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
            runs += [(m, WINDOW_YEARS) for m in ("last_year", "mean_3_years")]
            runs += [(f"boosted_trees_leaf_{n}", WINDOW_YEARS) for n in TREE_LEAF_CANDIDATES]
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

    Errors are on the log scale of the annual total: an ``rmse`` of 0.06 is about 6 %. ``family``
    is ``model`` (the Poisson regressions), ``trees`` or ``naive``; ``chosen`` marks the best model
    and the best trees on the selection years for all roads, the only years used to choose.
    """
    frame = _rolling()
    out = (
        frame.groupby(["outcome", "method", "window", "set"])
        .apply(_error_summary, include_groups=False)
        .reset_index()
    )
    out["outcome_label"] = out.outcome.map(OUTCOMES)
    out["method_label"] = out.method.map(SPECIFICATION_LABELS)
    out["family"] = [
        "model" if m in SPECIFICATIONS else "trees" if m.startswith("boosted_trees") else "naive"
        for m in out.method
    ]
    selection = out[(out.set == "selection") & (out.outcome == "deaths_all")]
    out["chosen"] = False
    for family in ("model", "trees"):
        rows = selection[selection.family == family]
        best = rows.loc[rows.rmse.idxmin()]
        out.loc[(out.method == best.method) & (out.window == best.window), "chosen"] = True
    return out[
        [
            "outcome",
            "outcome_label",
            "family",
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
    keep = [CHOSEN, "trend", "last_year", "mean_3_years", TREE_METHOD]
    out = rows[rows.method.isin(keep)].copy()
    out["order"] = out.method.map({name: i for i, name in enumerate(keep)})
    out["set_order"] = out.set.map({"selection": 0, "holdout": 1, "pandemic": 2})
    out = out.sort_values(["outcome", "set_order", "order"])
    return out.drop(columns=["order", "set_order", "chosen"]).reset_index(drop=True)


def backtest() -> pd.DataFrame:
    """Each scored year's deaths beside the chosen model's forecast and last year's count."""
    frame = _rolling()
    keep = frame[
        (frame.window == WINDOW_YEARS) & frame.method.isin([CHOSEN, "last_year", TREE_METHOD])
    ]
    out = keep.pivot_table(
        index=["outcome", "year", "set", "observed"], columns="method", values="predicted"
    ).reset_index()
    out.columns.name = None
    out = out.rename(
        columns={CHOSEN: "model", "last_year": "naive_last_year", TREE_METHOD: "boosted_trees"}
    )
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
    predicted with their observed traffic and calendar. Forecast spans that contain 2020 or 2021
    are left out; fits whose four-year window contains them (origins 2022–2024) are kept, because
    a forecast made today is fitted on such a window too, and they raise the error.
    ``tau`` is the error left once Poisson chance on the observed total is taken out: the drift of
    the trend, which applies to any count of deaths in the same zone whatever its size.
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


def detection_power(change: float, expected: float, tau: float, alpha: float = ALPHA) -> float:
    """Chance that a two-sided comparison at the ``alpha`` level shows a change of ``change`` deaths.

    Only a result in the direction of the change counts: a count that moves the other way and
    clears the test has not shown it. The change is taken on the log scale against a count of
    ``expected`` deaths whose forecast error is Poisson chance plus ``tau``. At the minimum
    detectable effect it is ``POWER`` exactly; when nothing changes it is ``alpha / 2``.
    """
    sigma = np.sqrt(1 / expected + tau**2)
    shift = abs(np.log1p(change / expected)) / sigma
    return float(stats.norm.cdf(shift - stats.norm.ppf(1 - alpha / 2)))


def minimum_detectable_rise(
    expected: float, tau: float, power: float = POWER, alpha: float = ALPHA
) -> float:
    """Smallest proportional rise in a count of ``expected`` deaths that the comparison detects."""
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float(np.expm1(z * np.sqrt(1 / expected + tau**2)))


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
    the proportional change in a month's deaths associated with one more Friday, Saturday or
    Sunday. With four years of data these are imprecise, and they are reported with that in view.
    The window is the four years to the last complete one (``first_year`` to ``last_year``), so
    with data to 2024 it starts in 2021, a year of pandemic restrictions, whose low traffic months
    weigh on the fuel coefficient.
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
