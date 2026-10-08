"""Policy case study (question Q8): interrupted time series on monthly road deaths.

Two interventions, two designs. The points-based licence of 1 July 2006 is a segmented regression
on the yearbook's monthly death series (1993–2024). The 90 km/h limit on conventional roads of
29 January 2019 is a difference-in-differences interrupted series on the microdata: conventional
roads (road-type codes 5 and 6) against motorways and dual carriageways (codes 1 to 3), month by
month, 2016–2024. Both are Poisson
regressions with Newey–West standard errors; the estimates are read as coincidences unless the
pre-trend, the placebo distribution and the sensitivity fits all agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from dgt_stats import io_tables
from dgt_stats.paths import DGT_PROCESSED_CRASHES

PROCESSED_CRASHES = DGT_PROCESSED_CRASHES

TREATED = "conventional"
CONTROL = "motorway_dual"
# The two-group panel is built from the road-type code, not from ``road_group``: DGT's
# "carretera convencional de doble calzada" (code 5) is a conventional road under RD 1514/2018,
# so it belongs with the treated roads, and from 2021 most of its crashes are coded as
# single-carriageway conventional (code 6) anyway. Keeping 5 and 6 together removes that 2021
# recoding from the contrast. Code 4 ("vía para automóviles", a handful of deaths a year) is
# left out of both groups.
TREATED_CODES = (5, 6)
CONTROL_CODES = (1, 2, 3)


@dataclass(frozen=True)
class Intervention:
    """One policy change and the windows its fits use.

    ``date`` is the first month treated as post-intervention. ``pre_start`` opens the fitting
    window, ``post_end`` closes the clean post-period, ``long_post_end`` the extended one used in
    the sensitivity fit, and ``second_break`` marks a confounding change inside that extended
    window. ``placebo_pre`` is how many months of pre-period a placebo break needs before it, and
    the placebo post-window is as long as the true one (``post_months``); ``placebo_dates`` lists
    the explicit placebo break months used by the difference-in-differences design.
    """

    key: str
    label: str
    date: pd.Timestamp
    pre_start: pd.Timestamp
    post_end: pd.Timestamp
    design: str  # "segmented" or "did"
    long_post_end: pd.Timestamp | None = None
    second_break: pd.Timestamp | None = None
    placebo_pre: int = 24
    placebo_dates: tuple[pd.Timestamp, ...] = field(default_factory=tuple)

    @property
    def post_months(self) -> int:
        return _months_between(self.date, self.post_end) + 1


def _months_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


INTERVENTIONS: dict[str, Intervention] = {
    "points_licence": Intervention(
        key="points_licence",
        label="Points-based licence, 1 July 2006",
        date=pd.Timestamp("2006-07-01"),
        pre_start=pd.Timestamp("2000-01-01"),
        post_end=pd.Timestamp("2007-11-01"),
        design="segmented",
        long_post_end=pd.Timestamp("2009-12-01"),
        second_break=pd.Timestamp("2007-12-01"),
    ),
    "speed_limit_90": Intervention(
        key="speed_limit_90",
        label="90 km/h limit on conventional roads, 29 January 2019",
        date=pd.Timestamp("2019-02-01"),
        pre_start=pd.Timestamp("2016-01-01"),
        post_end=pd.Timestamp("2020-02-01"),
        design="did",
        long_post_end=pd.Timestamp("2024-12-01"),
        placebo_dates=(pd.Timestamp("2017-01-01"), pd.Timestamp("2018-01-01")),
    ),
}

# Pandemic periods for the extended 2019 fit: (start, end, label).
PANDEMIC_PERIODS = (
    (pd.Timestamp("2020-03-01"), pd.Timestamp("2020-06-01"), "lockdown"),
    (pd.Timestamp("2020-07-01"), pd.Timestamp("2021-12-01"), "restrictions"),
)


# --------------------------------------------------------------------------- data


def _period(year: pd.Series, month: pd.Series) -> pd.Series:
    return pd.to_datetime(
        pd.DataFrame({"year": year.astype(int), "month": month.astype(int), "day": 1})
    )


def monthly_series(metric: str = "deaths_30d", zone: str = "all") -> pd.DataFrame:
    """One row per month, 1993–2024, from the yearbook series: ``period``, ``deaths``."""
    monthly = io_tables.read_table("series_monthly")
    rows = monthly[(monthly.metric == metric) & (monthly.zone == zone)]
    out = pd.DataFrame(
        {"period": _period(rows.year, rows.month), "deaths": rows.value.astype(float)}
    ).sort_values("period")
    out = out.reset_index(drop=True)
    expected = pd.date_range(out.period.min(), out.period.max(), freq="MS")
    if len(out) != len(expected) or not out.period.eq(expected).all():
        raise ValueError(f"monthly series {metric}/{zone} has gaps or duplicates")
    if out.deaths.isna().any():
        raise ValueError(f"monthly series {metric}/{zone} has missing months")
    out["metric"] = metric
    out["zone"] = zone
    return out


def monthly_by_road_group(crashes: pd.DataFrame | None = None) -> pd.DataFrame:
    """Monthly 30-day deaths on conventional roads and on motorways + dual carriageways, 2016–2024.

    Long format: ``period``, ``group`` (treated or control), ``deaths``. Every month of every year
    is present, with zero deaths where a group had none. The groups follow ``TREATED_CODES`` and
    ``CONTROL_CODES`` on the raw road-type code.
    """
    if crashes is None:
        crashes = pd.read_parquet(
            PROCESSED_CRASHES, columns=["ANYO", "MES", "TIPO_VIA", "TOTAL_MU30DF"]
        )
    code = pd.to_numeric(crashes.TIPO_VIA, errors="coerce")
    group = pd.Series(pd.NA, index=crashes.index, dtype="string")
    group[code.isin(TREATED_CODES)] = TREATED
    group[code.isin(CONTROL_CODES)] = CONTROL
    rows = crashes[group.notna()].assign(group=group[group.notna()])
    counts = rows.groupby(["ANYO", "MES", "group"], observed=True).TOTAL_MU30DF.sum()
    years = sorted(crashes.ANYO.unique())
    index = pd.MultiIndex.from_product(
        [years, range(1, 13), [TREATED, CONTROL]], names=["ANYO", "MES", "group"]
    )
    counts = counts.reindex(index, fill_value=0).reset_index()
    out = pd.DataFrame(
        {
            "period": _period(counts.ANYO, counts.MES),
            "group": counts.group.astype("string"),
            "deaths": counts.TOTAL_MU30DF.astype(float),
        }
    )
    return out.sort_values(["group", "period"]).reset_index(drop=True)


def window(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Rows with ``period`` between ``start`` and ``end`` inclusive."""
    return frame[(frame.period >= start) & (frame.period <= end)].reset_index(drop=True)


EXPOSURE_SERIES = {
    "fuel": "CORES road-fuel consumption",
    "toll": "toll-motorway average daily intensity",
}


def exposure_covariate(periods: pd.Series, name: str) -> pd.DataFrame:
    """The log of a monthly traffic series, centred, as one design column.

    ``fuel`` is CORES's national road-fuel consumption (petrol plus road diesel, tonnes) and
    ``toll`` the average daily intensity on the state toll-motorway network (vehicles a day on the
    average kilometre, ``imd``). The toll network's vehicle-kilometres are not used: they grow with
    the length of the network in service, which steps up in July 2006 as new sections open, the
    very month of the break, whereas the intensity is a traffic level per kilometre. Both series
    are centred on their own mean over the window, so the intercept keeps its meaning. A month the
    series does not cover raises rather than being filled.
    """
    from dgt_stats import io_traffic

    if name == "fuel":
        source = io_traffic.read_cores_fuel().set_index("period").road_fuel_tonnes
    elif name == "toll":
        source = io_traffic.read_toll_traffic().set_index("period").imd
    else:
        raise ValueError(f"unknown exposure series {name!r}")
    values = pd.to_datetime(periods).map(source)
    if values.isna().any():
        missing = pd.to_datetime(periods)[values.isna()]
        raise ValueError(f"{name}: no value for {missing.min():%Y-%m} to {missing.max():%Y-%m}")
    logged = np.log(values.to_numpy(dtype=float))
    return pd.DataFrame({f"log_{name}": logged - logged.mean()}, index=periods.index)


# --------------------------------------------------------------------------- fitting

HAC_LAGS = 12
SEGMENTED_TERMS = {"post": "level change", "post_t": "slope change (per month)"}


@dataclass
class ItsFit:
    """A fitted interrupted series: the estimates the page needs and the series behind them."""

    key: str
    variant: str
    family: str
    n: int
    break_date: pd.Timestamp
    coefficients: pd.DataFrame  # term, estimate, se, low, high
    level_change: float
    level_low: float
    level_high: float
    slope_change: float  # annualised, NaN when the model has no slope term
    slope_low: float
    slope_high: float
    dispersion: float
    series: pd.DataFrame  # period (, group), deaths, fitted, counterfactual, post
    # The Newey–West covariance of the coefficients, for combinations of the level and slope terms.
    cov: pd.DataFrame | None = None


def _month_dummies(period: pd.Series) -> pd.DataFrame:
    months = period.dt.month
    return pd.DataFrame(
        {f"m{m}": (months == m).astype(float).to_numpy() for m in range(2, 13)}, index=period.index
    )


def _pandemic_columns(period: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            f"p_{label}": ((period >= start) & (period <= end)).astype(float).to_numpy()
            for start, end, label in PANDEMIC_PERIODS
        },
        index=period.index,
    )


def _trend_columns(period: pd.Series, trend: str, knots: tuple[pd.Timestamp, ...]) -> pd.DataFrame:
    """The pre-trend basis: one linear term, or a more flexible one in the same time variable.

    ``linear`` is the main specification. ``quadratic`` adds a squared term. ``piecewise`` adds one
    hinge per knot, ``max(0, t - t_knot)``, so the trend is continuous and changes slope at each
    knot; the knots are chosen on the pre-intervention months alone (``choose_trend_knot``), never
    on the post-intervention fit.
    """
    origin = period.iloc[0]
    t = period.apply(lambda p: _months_between(origin, p)).astype(float)
    columns: dict[str, np.ndarray] = {"t": t.to_numpy(dtype=float)}
    if trend == "linear":
        pass
    elif trend == "quadratic":
        columns["t2"] = (t.to_numpy(dtype=float) / 12.0) ** 2
    elif trend == "piecewise":
        if not knots:
            raise ValueError("piecewise trend needs at least one knot")
        for index, knot in enumerate(knots, start=1):
            offset = float(_months_between(origin, knot))
            columns[f"t_hinge{index}"] = np.clip(t.to_numpy(dtype=float) - offset, 0.0, None)
    else:
        raise ValueError(f"unknown trend {trend!r}")
    return pd.DataFrame(columns, index=period.index)


def _segmented_design(
    frame: pd.DataFrame,
    break_date: pd.Timestamp,
    slope: bool,
    second_break: pd.Timestamp | None,
    pandemic: bool,
    trend: str = "linear",
    knots: tuple[pd.Timestamp, ...] = (),
    covariates: pd.DataFrame | None = None,
) -> pd.DataFrame:
    period = frame.period
    post = (period >= break_date).astype(float)
    design = pd.DataFrame({"const": 1.0}, index=frame.index)
    design = pd.concat([design, _trend_columns(period, trend, knots)], axis=1)
    design["post"] = post
    if slope:
        since = period.apply(lambda p: _months_between(break_date, p)).astype(float)
        design["post_t"] = post * since
    if second_break is not None:
        design["post2"] = (period >= second_break).astype(float)
    design = pd.concat([design, _month_dummies(period)], axis=1)
    if pandemic:
        design = pd.concat([design, _pandemic_columns(period)], axis=1)
    if covariates is not None:
        design = pd.concat([design, covariates.set_index(design.index)], axis=1)
    return design


def _hac(groups: np.ndarray | None = None) -> dict[str, object]:
    """Newey–West covariance with 12 lags; within each group when ``groups`` is given (a panel).

    The small-sample correction is off in both designs, stated rather than left to two different
    library defaults (none for the series fit, the panel's own for the panel fit).
    """
    if groups is None:
        return {"cov_type": "HAC", "cov_kwds": {"maxlags": HAC_LAGS, "use_correction": False}}
    return {
        "cov_type": "hac-panel",
        "cov_kwds": {"groups": groups, "maxlags": HAC_LAGS, "use_correction": False},
    }


def _fit(
    y: pd.Series,
    design: pd.DataFrame,
    family: str,
    offset: pd.Series | None,
    cov: dict[str, object] | None = None,
) -> tuple[pd.Series, pd.DataFrame, float, np.ndarray, pd.DataFrame]:
    """Fit a Poisson or negative-binomial regression with Newey–West errors.

    Returns the parameters, their 95 % intervals, the Pearson dispersion, the fitted means and the
    covariance of the parameters.
    """
    import statsmodels.api as sm  # imported here: the site build never needs statsmodels

    log_offset = None if offset is None else np.log(offset.to_numpy(dtype=float))
    cov = cov or _hac()
    values = y.to_numpy(dtype=float)
    if family == "poisson":
        model = sm.GLM(values, design, family=sm.families.Poisson(), offset=log_offset)
        result = model.fit(**cov)
        mu = np.asarray(result.fittedvalues)
        variance = mu
    elif family == "negative_binomial":
        # NB2 with the dispersion set by moments from the Poisson fit: alpha solves
        # Pearson chi2 / df = 1 + alpha * mean(mu). Deterministic, and never fails to converge.
        poisson = sm.GLM(values, design, family=sm.families.Poisson(), offset=log_offset).fit()
        mu_p = np.asarray(poisson.fittedvalues)
        df = len(values) - design.shape[1]
        excess = float(np.sum((values - mu_p) ** 2 / mu_p) / df) - 1.0
        alpha = max(excess / float(np.mean(mu_p)), 1e-6)
        family_nb = sm.families.NegativeBinomial(alpha=alpha)
        result = sm.GLM(values, design, family=family_nb, offset=log_offset).fit(**cov)
        mu = np.asarray(result.fittedvalues)
        variance = mu + alpha * mu**2
    else:
        raise ValueError(f"unknown family {family!r}")
    params = pd.Series(np.asarray(result.params), index=list(result.params.index))
    conf = pd.DataFrame(np.asarray(result.conf_int()), index=params.index, columns=["low", "high"])
    se = pd.Series(np.asarray(result.bse), index=params.index)
    coefficients = pd.DataFrame(
        {"term": params.index, "estimate": params.values, "se": se.values}
    ).assign(low=conf.low.values, high=conf.high.values)
    df_resid = len(values) - design.shape[1]
    dispersion = float(np.sum((values - mu) ** 2 / variance) / df_resid)
    cov_params = pd.DataFrame(
        np.asarray(result.cov_params()), index=params.index, columns=params.index
    )
    return params, coefficients, dispersion, mu, cov_params


def _change(
    coefficients: pd.DataFrame, term: str, scale: float = 1.0
) -> tuple[float, float, float]:
    row = coefficients[coefficients.term == term]
    if row.empty:
        return (np.nan, np.nan, np.nan)
    row = row.iloc[0]
    return tuple(float(np.expm1(scale * v)) for v in (row.estimate, row.low, row.high))


def _predict(design: pd.DataFrame, params: pd.Series, offset: pd.Series | None) -> np.ndarray:
    columns = [c for c in design.columns if c in params.index]
    eta = design[columns].to_numpy(dtype=float) @ params[columns].to_numpy(dtype=float)
    if offset is not None:
        eta = eta + np.log(offset.to_numpy(dtype=float))
    return np.exp(eta)


def segmented_fit(
    series: pd.DataFrame,
    intervention: Intervention,
    *,
    variant: str = "main",
    break_date: pd.Timestamp | None = None,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    family: str = "poisson",
    slope: bool = True,
    second_break: pd.Timestamp | None = None,
    pandemic: bool = False,
    trend: str = "linear",
    knots: tuple[pd.Timestamp, ...] = (),
    exposure_series: str | None = None,
) -> ItsFit:
    """Segmented regression of monthly deaths with a level (and slope) change at ``break_date``.

    ``exposure_series`` adds the log of a monthly traffic series as a free covariate (``fuel`` or
    ``toll``, see ``exposure_covariate``), which lets the data say how much of the movement in
    deaths the traffic series explains rather than imposing proportionality. No series is used as
    an offset: the registered fleet, the only monthly-interpolable count of vehicles, does not
    correspond to deaths of every road user, pedestrians and cyclists included.
    """
    break_date = break_date or intervention.date
    frame = window(series, start or intervention.pre_start, end or intervention.post_end)
    if frame.empty or (frame.period >= break_date).sum() == 0:
        raise ValueError("segmented_fit: the window has no post-intervention months")
    covariates = exposure_covariate(frame.period, exposure_series) if exposure_series else None
    design = _segmented_design(
        frame, break_date, slope, second_break, pandemic, trend, knots, covariates
    )
    params, coefficients, dispersion, mu, cov = _fit(frame.deaths, design, family, None)
    counterfactual_design = design.copy()
    for column in ("post", "post_t", "post2"):
        if column in counterfactual_design:
            counterfactual_design[column] = 0.0
    out = frame[["period", "deaths"]].copy()
    out["fitted"] = mu
    out["counterfactual"] = _predict(counterfactual_design, params, None)
    out["post"] = (frame.period >= break_date).to_numpy()
    level = _change(coefficients, "post")
    slope_change = _change(coefficients, "post_t", scale=12.0)
    return ItsFit(
        intervention.key,
        variant,
        family,
        len(frame),
        break_date,
        coefficients,
        *level,
        *slope_change,
        dispersion,
        out,
        cov,
    )


def post_period_change(fit: ItsFit, months: int) -> dict[str, float]:
    """The level and slope terms read together over the first ``months`` months from the break.

    The step (``post``) is the change in the first month only. With a slope change after the
    break, the change in month ``k`` (0 for the month of the break) is ``post + k * post_t`` on
    the log scale, so a positive slope change wears the step away. ``mean_*`` is that change
    averaged over months 0 to ``months - 1`` (equal to the change in the middle month),
    ``end_*`` the change in the last of those months, each with a 95 % interval from the fit's
    covariance, as proportional changes. ``months_to_zero`` is the month (from the break) in which
    the fitted change reaches zero, NaN when the slope does not bring it back or the model has no
    slope term.
    """
    if fit.cov is None:
        raise ValueError("post_period_change needs a fit that carries its covariance")
    params = fit.coefficients.set_index("term").estimate
    weights_mean = {"post": 1.0, "post_t": (months - 1) / 2.0}
    weights_end = {"post": 1.0, "post_t": float(months - 1)}

    def combine(weights: dict[str, float]) -> tuple[float, float, float]:
        terms = [term for term in weights if term in params.index]
        w = np.array([weights[term] for term in terms])
        estimate = float(w @ params[terms].to_numpy())
        se = float(np.sqrt(w @ fit.cov.loc[terms, terms].to_numpy() @ w))
        return tuple(
            float(np.expm1(v)) for v in (estimate, estimate - 1.96 * se, estimate + 1.96 * se)
        )

    mean, end = combine(weights_mean), combine(weights_end)
    step, slope = float(params["post"]), float(params.get("post_t", np.nan))
    crossing = -step / slope if np.isfinite(slope) and slope != 0 else np.nan
    return {
        "mean_change": mean[0],
        "mean_low": mean[1],
        "mean_high": mean[2],
        "end_change": end[0],
        "end_low": end[1],
        "end_high": end[2],
        "months_to_zero": crossing if np.isfinite(crossing) and crossing > 0 else np.nan,
    }


def placebo_fits(
    series: pd.DataFrame, intervention: Intervention, family: str = "poisson"
) -> pd.DataFrame:
    """The level change re-estimated with the break at every admissible pre-period month.

    Each placebo fit uses the same pre-window start and a post-window of the same length as the
    true one, and ends before the true intervention. The true estimate is the row with
    ``is_true`` set; ``rank`` counts how many estimates (true one included) are at least as low.
    """
    true = segmented_fit(series, intervention, family=family)
    records = [
        {
            "break_date": intervention.date,
            "level_change": true.level_change,
            "low": true.level_low,
            "high": true.level_high,
            "is_true": True,
        }
    ]
    post = intervention.post_months
    first = intervention.pre_start + pd.DateOffset(months=intervention.placebo_pre)
    last = intervention.date - pd.DateOffset(months=post)
    for date in pd.date_range(first, last, freq="MS"):
        fit = segmented_fit(
            series,
            intervention,
            variant="placebo",
            break_date=date,
            end=date + pd.DateOffset(months=post - 1),
            family=family,
        )
        records.append(
            {
                "break_date": date,
                "level_change": fit.level_change,
                "low": fit.level_low,
                "high": fit.level_high,
                "is_true": False,
            }
        )
    out = pd.DataFrame.from_records(records).sort_values("break_date").reset_index(drop=True)
    out["rank"] = out.level_change.rank(method="min").astype(int)
    out["n_fits"] = len(out)
    return out


# --------------------------------------------------------------------- calendar falsification

# The calendar-matched placebo fits use a shorter pre-window than the main fit so that enough
# other Julys qualify: 60 months before the break and the true post-window of 17 months after it.
CALENDAR_PRE_MONTHS = 60
EXCLUDED_WINDOW = (pd.Timestamp("2020-03-01"), pd.Timestamp("2021-12-01"))


def _window_is_clean(
    start: pd.Timestamp, end: pd.Timestamp, intervention: Intervention, series: pd.DataFrame
) -> bool:
    """A placebo window must lie inside the series, miss the true break and miss the pandemic."""
    if start < series.period.min() or end > series.period.max():
        return False
    if start <= intervention.date <= end:
        return False
    if start < EXCLUDED_WINDOW[1] and end > EXCLUDED_WINDOW[0]:
        return False
    return True


def calendar_placebo_years(
    series: pd.DataFrame, intervention: Intervention, month: int = 7
) -> list[pd.Timestamp]:
    """Every year whose ``month`` can carry a placebo break on a clean, equally shaped window."""
    post = intervention.post_months
    years = range(int(series.period.dt.year.min()), int(series.period.dt.year.max()) + 1)
    out = []
    for year in years:
        date = pd.Timestamp(year=year, month=month, day=1)
        if date == intervention.date:
            continue
        start = date - pd.DateOffset(months=CALENDAR_PRE_MONTHS)
        end = date + pd.DateOffset(months=post - 1)
        if _window_is_clean(start, end, intervention, series):
            out.append(date)
    return out


def calendar_placebo_fits(
    series: pd.DataFrame, intervention: Intervention, month: int = 7
) -> pd.DataFrame:
    """The same segmented model with the break at the same calendar month of other years.

    The generic placebo distribution (``placebo_fits``) moves the break to arbitrary months, which
    answers "is a drop this size unusual for this series?" but not the question a sceptic asks of a
    July intervention: Spanish road deaths usually peak in July or August (``peak_month`` in
    ``seasonal_transitions``), so is the summer 2006 movement unusual *for a July*? Each fit here uses a window of the same shape, 60 months before
    the break and 17 after, placed at July of a year the points licence cannot have affected, and
    the true break is refitted on that same shape so the comparison is like for like.
    """
    post = intervention.post_months
    records: list[dict[str, object]] = []
    dates = [intervention.date, *calendar_placebo_years(series, intervention, month)]
    for date in dates:
        is_true = date == intervention.date
        fit = segmented_fit(
            series,
            intervention,
            variant="calendar_true" if is_true else "calendar_placebo",
            break_date=date,
            start=date - pd.DateOffset(months=CALENDAR_PRE_MONTHS),
            end=date + pd.DateOffset(months=post - 1),
        )
        records.append(
            {
                "break_date": date,
                "year": int(date.year),
                "level_change": fit.level_change,
                "low": fit.level_low,
                "high": fit.level_high,
                "dispersion": fit.dispersion,
                "is_true": is_true,
            }
        )
    out = pd.DataFrame.from_records(records).sort_values("break_date").reset_index(drop=True)
    out["rank"] = out.level_change.rank(method="min").astype(int)
    out["n_fits"] = len(out)
    return out


def placebo_calibration(calendar: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """How well the model's own intervals hold up at the July placebos, and an interval that
    uses the placebos instead.

    At a placebo July nothing was introduced, so a model whose 95 % intervals were right would
    exclude no change at about one placebo in twenty. ``n_excluding_zero`` counts how often the
    Newey–West interval does. ``placebo_sd`` is the standard deviation of the placebo steps on
    the log scale: how much the step estimate moves from July to July when nothing happens, which
    includes the error of projecting a trend that is not straight. ``se_ratio`` compares it with
    the median standard error the model reports for those same fits. The calibrated interval for
    the true July is its step plus or minus the Student t quantile (``n_placebos - 1`` degrees of
    freedom) times ``placebo_sd``; it is computed for the calendar-matched fit, which has the same
    window shape as the placebos, and for no other specification.
    """
    from scipy import stats

    z = float(stats.norm.ppf(1 - alpha / 2))
    placebos = calendar[~calendar.is_true.astype(bool)]
    true = calendar[calendar.is_true.astype(bool)].iloc[0]
    steps = np.log1p(placebos.level_change.to_numpy(dtype=float))
    nominal_se = (
        np.log1p(placebos.high.to_numpy(dtype=float)) - np.log1p(placebos.low.to_numpy(dtype=float))
    ) / (2 * z)
    excluding = int(((placebos.low > 0) | (placebos.high < 0)).sum())
    spread = float(np.std(steps, ddof=1))
    quantile = float(stats.t.ppf(1 - alpha / 2, len(steps) - 1))
    estimate = float(np.log1p(true.level_change))
    return pd.DataFrame(
        [
            {
                "year": int(true.year),
                "level_change": float(true.level_change),
                "nominal_low": float(true.low),
                "nominal_high": float(true.high),
                "n_placebos": len(placebos),
                "n_excluding_zero": excluding,
                "expected_excluding_zero": alpha * len(placebos),
                "placebo_sd": spread,
                "median_nominal_se": float(np.median(nominal_se)),
                "se_ratio": spread / float(np.median(nominal_se)),
                "t_quantile": quantile,
                "calibrated_low": float(np.expm1(estimate - quantile * spread)),
                "calibrated_high": float(np.expm1(estimate + quantile * spread)),
            }
        ]
    )


def seasonal_transitions(series: pd.DataFrame) -> pd.DataFrame:
    """Year-by-year summer transitions in monthly deaths, with no model between them.

    For every year the frame carries the log change from June to July, July to August and August to
    September, and, the statistic that answers the question directly, the log ratio of the twelve
    months from July to the twelve months before July. The last one has the same number of each
    calendar month on both sides, so seasonality cancels exactly and what is left is the level
    change across that July. ``rank`` orders the years by that statistic, smallest first.
    ``peak_month`` is the calendar month with most deaths in the year (the first, on a tie).
    """
    values = series.set_index("period").deaths
    records: list[dict[str, object]] = []
    for year in sorted(series.period.dt.year.unique()):
        row: dict[str, object] = {"year": int(year)}

        def month(y: int, m: int) -> float:
            return float(values.get(pd.Timestamp(year=y, month=m, day=1), np.nan))

        months = [month(year, m) for m in range(1, 13)]
        row["peak_month"] = int(np.nanargmax(months)) + 1 if not np.isnan(months).all() else np.nan

        for label, (m1, m2) in {
            "jun_to_jul": (6, 7),
            "jul_to_aug": (7, 8),
            "aug_to_sep": (8, 9),
        }.items():
            row[label] = float(np.log(month(year, m2) / month(year, m1)))
        after = [month(year, m) for m in range(7, 13)] + [month(year + 1, m) for m in range(1, 7)]
        before = [month(year - 1, m) for m in range(7, 13)] + [month(year, m) for m in range(1, 7)]
        if any(np.isnan(after)) or any(np.isnan(before)):
            row["twelve_month_ratio"] = np.nan
            row["deaths_after"] = np.nan
            row["deaths_before"] = np.nan
        else:
            row["deaths_after"] = float(np.sum(after))
            row["deaths_before"] = float(np.sum(before))
            row["twelve_month_ratio"] = float(np.log(np.sum(after) / np.sum(before)))
        records.append(row)
    out = pd.DataFrame.from_records(records)
    out["excluded"] = out.year.isin((2019, 2020, 2021))
    ranked = out[out.twelve_month_ratio.notna() & ~out.excluded]
    out["rank"] = np.nan
    out.loc[ranked.index, "rank"] = ranked.twelve_month_ratio.rank(method="min")
    out["n_ranked"] = len(ranked)
    return out


def forecast_validation(
    series: pd.DataFrame, intervention: Intervention, month: int = 7
) -> pd.DataFrame:
    """How far the months after each July fall below a model fitted only on the months before it.

    For each break date the model (linear trend and month-of-year terms, no intervention term at
    all) is fitted on the 60 months before it and used to predict the 17 months after it. The
    statistic is the log ratio of observed to predicted deaths over the forecast window, the
    proportional shortfall the page describes; ``rank`` orders the Julys by it, largest shortfall
    first. The z score, which scales the difference by the Poisson standard error inflated by the
    fit's own dispersion, is kept with its own rank (``rank_z``): it weighs the large counts of the
    early years more heavily, so the two orders differ. Running the same exercise at July of other
    years turns the true year's forecast error into a rank inside an empirical distribution,
    rather than a number with nothing to compare it to.
    """
    import statsmodels.api as sm

    post = intervention.post_months
    dates = [intervention.date, *calendar_placebo_years(series, intervention, month)]
    records: list[dict[str, object]] = []
    for date in dates:
        pre = window(series, date - pd.DateOffset(months=CALENDAR_PRE_MONTHS), date)
        pre = pre[pre.period < date].reset_index(drop=True)
        ahead = window(series, date, date + pd.DateOffset(months=post - 1))
        design_pre = pd.concat(
            [
                pd.DataFrame({"const": 1.0}, index=pre.index),
                _trend_columns(pre.period, "linear", ()),
                _month_dummies(pre.period),
            ],
            axis=1,
        )
        fit = sm.GLM(
            pre.deaths.to_numpy(dtype=float), design_pre, family=sm.families.Poisson()
        ).fit()
        mu_pre = np.asarray(fit.fittedvalues)
        dispersion = float(
            np.sum((pre.deaths.to_numpy(dtype=float) - mu_pre) ** 2 / mu_pre)
            / (len(pre) - design_pre.shape[1])
        )
        origin = pre.period.iloc[0]
        t_ahead = ahead.period.apply(lambda p: _months_between(origin, p)).astype(float)
        design_ahead = pd.concat(
            [
                pd.DataFrame({"const": 1.0, "t": t_ahead.to_numpy()}, index=ahead.index),
                _month_dummies(ahead.period),
            ],
            axis=1,
        )
        predicted = _predict(
            design_ahead, pd.Series(np.asarray(fit.params), index=fit.params.index), None
        )
        observed = ahead.deaths.to_numpy(dtype=float)
        total_observed = float(observed.sum())
        total_predicted = float(predicted.sum())
        se = float(np.sqrt(max(dispersion, 1.0) * total_predicted))
        records.append(
            {
                "break_date": date,
                "year": int(date.year),
                "observed": total_observed,
                "predicted": total_predicted,
                "log_ratio": float(np.log(total_observed / total_predicted)),
                "z": (total_observed - total_predicted) / se,
                "dispersion": dispersion,
                "is_true": date == intervention.date,
            }
        )
    out = pd.DataFrame.from_records(records).sort_values("break_date").reset_index(drop=True)
    out["rank"] = out.log_ratio.rank(method="min").astype(int)
    out["rank_z"] = out.z.rank(method="min").astype(int)
    out["n_fits"] = len(out)
    return out


def choose_trend_knot(
    series: pd.DataFrame, intervention: Intervention, *, edge_months: int = 18
) -> tuple[pd.Timestamp | None, pd.DataFrame]:
    """Pick the knot of a piecewise pre-trend from the pre-intervention months alone.

    Every candidate month that leaves ``edge_months`` on each side is tried as the single knot of a
    continuous piecewise-linear trend fitted to the months before the intervention, with the same
    month-of-year terms and nothing else. The candidates are compared on QAIC, the Poisson AIC
    with the log-likelihood divided by the Pearson dispersion of the best one-knot fit (floored at
    1), because monthly deaths vary more than a Poisson model assumes; a knot costs two
    parameters, its slope change and its position, which was searched for (as in the long-run
    joinpoint search). The knot with the lowest QAIC wins, and the one-line trend is in the
    comparison as the no-knot case, so a flexible pre-trend is only adopted if the pre-2006
    series asks for it. Returns the winning knot (``None`` when the straight line wins) and the
    table of candidates.
    """
    import statsmodels.api as sm

    pre = window(series, intervention.pre_start, intervention.date)
    pre = pre[pre.period < intervention.date].reset_index(drop=True)
    y = pre.deaths.to_numpy(dtype=float)

    def fit(knots: tuple[pd.Timestamp, ...]) -> dict[str, float]:
        design = pd.concat(
            [
                pd.DataFrame({"const": 1.0}, index=pre.index),
                _trend_columns(pre.period, "piecewise" if knots else "linear", knots),
                _month_dummies(pre.period),
            ],
            axis=1,
        )
        result = sm.GLM(y, design, family=sm.families.Poisson()).fit()
        return {
            "log_likelihood": float(result.llf),
            "deviance": float(result.deviance),
            "n_parameters": design.shape[1] + len(knots),
            "pearson_dispersion": float(result.pearson_chi2 / result.df_resid),
        }

    records = [{"knot": pd.NaT, "label": "one linear trend", **fit(())}]
    candidates = pre.period.iloc[edge_months:-edge_months]
    for knot in candidates:
        records.append({"knot": knot, "label": f"knot at {knot:%b %Y}", **fit((knot,))})
    table = pd.DataFrame.from_records(records)
    knotted = table[table.knot.notna()]
    dispersion = max(1.0, float(knotted.loc[knotted.deviance.idxmin(), "pearson_dispersion"]))
    table["dispersion"] = dispersion
    table["qaic"] = -2 * table.log_likelihood / dispersion + 2 * table.n_parameters
    table["delta_qaic"] = table.qaic - table.qaic.min()
    best = table.loc[table.qaic.idxmin()]
    chosen = None if pd.isna(best.knot) else pd.Timestamp(best.knot)
    columns = ["knot", "label", "n_parameters", "deviance", "dispersion", "qaic", "delta_qaic"]
    return chosen, table.sort_values("qaic").reset_index(drop=True)[columns]


def _did_design(
    frame: pd.DataFrame, break_date: pd.Timestamp, slope: bool, pandemic: bool
) -> pd.DataFrame:
    period = frame.period
    start = period.min()
    t = period.apply(lambda p: _months_between(start, p)).astype(float)
    treated = (frame.group == TREATED).astype(float)
    post = (period >= break_date).astype(float)
    design = pd.DataFrame(
        {
            "const": 1.0,
            "t": t,
            "treated": treated,
            "post": post,
            "post_treated": post * treated,
        },
        index=frame.index,
    )
    if slope:
        since = period.apply(lambda p: _months_between(break_date, p)).astype(float)
        design["post_t"] = post * since
        design["post_t_treated"] = post * since * treated
    design = pd.concat([design, _month_dummies(period)], axis=1)
    if pandemic:
        pandemic_columns = _pandemic_columns(period)
        design = pd.concat([design, pandemic_columns], axis=1)
        for column in pandemic_columns:
            design[f"{column}_treated"] = pandemic_columns[column] * treated
    return design


def did_fit(
    panel: pd.DataFrame,
    intervention: Intervention,
    *,
    variant: str = "main",
    break_date: pd.Timestamp | None = None,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    family: str = "poisson",
    slope: bool = False,
    pandemic: bool = False,
) -> ItsFit:
    """Difference-in-differences interrupted series: treated against control, one count model.

    The estimate is the ``post_treated`` term; the ``post`` term is the control group's own
    change at the break, which a valid design expects to be near zero. The Newey–West covariance
    runs within each group (a panel), never across the group boundary.
    """
    break_date = break_date or intervention.date
    frame = window(panel, start or intervention.pre_start, end or intervention.post_end)
    frame = frame.sort_values(["group", "period"]).reset_index(drop=True)
    if frame.empty or (frame.period >= break_date).sum() == 0:
        raise ValueError("did_fit: the window has no post-intervention months")
    design = _did_design(frame, break_date, slope, pandemic)
    groups = frame.group.astype("category").cat.codes.to_numpy()
    params, coefficients, dispersion, mu, cov = _fit(
        frame.deaths, design, family, None, _hac(groups)
    )
    counterfactual_design = design.copy()
    for column in ("post_treated", "post_t_treated"):
        if column in counterfactual_design:
            counterfactual_design[column] = 0.0
    out = frame[["period", "group", "deaths"]].copy()
    out["fitted"] = mu
    out["counterfactual"] = _predict(counterfactual_design, params, None)
    out["post"] = (frame.period >= break_date).to_numpy()
    level = _change(coefficients, "post_treated")
    slope_change = _change(coefficients, "post_t_treated", scale=12.0)
    return ItsFit(
        intervention.key,
        variant,
        family,
        len(frame),
        break_date,
        coefficients,
        *level,
        *slope_change,
        dispersion,
        out,
        cov,
    )


def did_placebos(
    panel: pd.DataFrame, intervention: Intervention, family: str = "poisson"
) -> pd.DataFrame:
    """The treated-group change re-estimated at each placebo date, with the true estimate."""
    true = did_fit(panel, intervention, family=family)
    control = _change(true.coefficients, "post")
    records = [
        {
            "break_date": intervention.date,
            "level_change": true.level_change,
            "low": true.level_low,
            "high": true.level_high,
            "control_change": control[0],
            "control_low": control[1],
            "control_high": control[2],
            "is_true": True,
        }
    ]
    post = intervention.post_months
    for date in intervention.placebo_dates:
        fit = did_fit(
            panel,
            intervention,
            variant="placebo",
            break_date=date,
            end=date + pd.DateOffset(months=post - 1),
            family=family,
        )
        control = _change(fit.coefficients, "post")
        records.append(
            {
                "break_date": date,
                "level_change": fit.level_change,
                "low": fit.level_low,
                "high": fit.level_high,
                "control_change": control[0],
                "control_low": control[1],
                "control_high": control[2],
                "is_true": False,
            }
        )
    return pd.DataFrame.from_records(records).sort_values("break_date").reset_index(drop=True)


# --------------------------------------------------------------------------- Q8 tables


def _fit_row(fit: ItsFit, window_text: str, months: int | None = None) -> dict[str, object]:
    """One specification's row; with ``months``, also its change over that many months from the
    break (``post_period_change``), for the segmented design."""
    row = {
        "variant": fit.variant,
        "family": fit.family,
        "window": window_text,
        "n_months": int(fit.series.period.nunique()),
        "level_change": fit.level_change,
        "level_low": fit.level_low,
        "level_high": fit.level_high,
        "slope_change_annual": fit.slope_change,
        "slope_low": fit.slope_low,
        "slope_high": fit.slope_high,
        "dispersion": fit.dispersion,
    }
    if months is not None:
        row["post_months"] = months
        row.update(post_period_change(fit, months))
    return row


def _window_text(start: pd.Timestamp, end: pd.Timestamp) -> str:
    return f"{start:%b %Y} to {end:%b %Y}"


def death_definition_ratio(thirty_day: pd.DataFrame, one_day: pd.DataFrame) -> pd.DataFrame:
    """The monthly ratio of 30-day to 24-hour deaths, summarised by year.

    A 30-day count that follows each victim moves from month to month independently of the
    24-hour count; one derived from the 24-hour count with a correction factor keeps an almost
    constant ratio within a year. ``sd`` is the standard deviation of the twelve monthly ratios.
    ``regime_from`` names the first year, if any, from which every year's ``sd`` exceeds that of
    every earlier year (NaN when no such year exists); ``later_regime`` marks the years from it.
    The page reads from this whether the 24-hour fit is an independent check of the 30-day one.
    """
    ratio = thirty_day.set_index("period").deaths / one_day.set_index("period").deaths
    if ratio.isna().any():
        raise ValueError("the 30-day and 24-hour series do not cover the same months")
    frame = ratio.rename("ratio").reset_index()
    out = (
        frame.groupby(frame.period.dt.year)
        .ratio.agg(mean="mean", sd="std", low="min", high="max", months="size")
        .reset_index()
        .rename(columns={"period": "year"})
    )
    full = out[out.months == 12].reset_index(drop=True)
    split = np.nan
    for index in range(1, len(full)):
        if float(full.sd.iloc[index:].min()) > float(full.sd.iloc[:index].max()):
            split = int(full.year.iloc[index])
            break
    out["regime_from"] = split
    out["later_regime"] = out.year >= split if np.isfinite(split) else False
    return out


def points_licence_fits() -> dict[str, pd.DataFrame]:
    """Main fit, falsification tests and sensitivity table for the 2006 points licence.

    The main specification is the one the months *before* July 2006 prefer: a continuous
    piecewise-linear trend whose single knot is chosen by QAIC on the pre-intervention months
    alone (``choose_trend_knot``), with month-of-year terms and a level and slope change at the
    break. The straight-line trend that earlier versions of this study used is kept as the first
    sensitivity row, because the difference between the two is most of the difference between a
    twelve per cent drop and a seven per cent one. Every specification also carries its change
    averaged over the post-period and in its last month (``post_period_change``): under the
    preferred pre-trend the slope change wears the step away within the window, which the step
    alone does not show.
    """
    it = INTERVENTIONS["points_licence"]
    series = monthly_series()
    knot, trend_choice = choose_trend_knot(series, it)
    knots = () if knot is None else (knot,)
    trend = "linear" if knot is None else "piecewise"
    fixed = {"trend": trend, "knots": knots}
    main = segmented_fit(series, it, **fixed)
    linear = segmented_fit(series, it, variant="linear_trend")
    variants: list[tuple[str, ItsFit, pd.Timestamp, pd.Timestamp]] = [
        ("Main: piecewise pre-trend chosen on the pre-period", main, it.pre_start, it.post_end),
        ("One straight pre-trend (the earlier specification)", linear, it.pre_start, it.post_end),
        (
            "Quadratic pre-trend",
            segmented_fit(series, it, variant="quadratic", trend="quadratic"),
            it.pre_start,
            it.post_end,
        ),
        (
            "Piecewise pre-trend with the knot fixed at January 2004",
            segmented_fit(
                series,
                it,
                variant="knot_2004",
                trend="piecewise",
                knots=(pd.Timestamp("2004-01-01"),),
            ),
            it.pre_start,
            it.post_end,
        ),
        (
            "CORES road-fuel consumption as a covariate",
            segmented_fit(series, it, variant="fuel", exposure_series="fuel", **fixed),
            it.pre_start,
            it.post_end,
        ),
        (
            "Toll-motorway traffic intensity as a covariate",
            segmented_fit(series, it, variant="toll", exposure_series="toll", **fixed),
            it.pre_start,
            it.post_end,
        ),
        (
            "24-hour deaths",
            segmented_fit(monthly_series("deaths_24h"), it, variant="24h", **fixed),
            it.pre_start,
            it.post_end,
        ),
        (
            "Interurban roads only",
            segmented_fit(monthly_series(zone="interurban"), it, variant="interurban", **fixed),
            it.pre_start,
            it.post_end,
        ),
        (
            "Urban streets only",
            segmented_fit(monthly_series(zone="urban"), it, variant="urban", **fixed),
            it.pre_start,
            it.post_end,
        ),
        (
            "Level change only, no slope term",
            segmented_fit(series, it, variant="no_slope", slope=False, **fixed),
            it.pre_start,
            it.post_end,
        ),
        (
            "Negative binomial",
            segmented_fit(
                series, it, variant="negative_binomial", family="negative_binomial", **fixed
            ),
            it.pre_start,
            it.post_end,
        ),
        (
            "Post-period to December 2009 with a second break in December 2007",
            segmented_fit(
                series,
                it,
                variant="long",
                end=it.long_post_end,
                second_break=it.second_break,
                **fixed,
            ),
            it.pre_start,
            it.long_post_end,  # type: ignore[arg-type]
        ),
    ]
    sensitivity = pd.DataFrame(
        [
            {"label": label, **_fit_row(fit, _window_text(s, e), it.post_months)}
            for label, fit, s, e in variants
        ]
    )
    long_index = len(variants) - 1
    sensitivity["second_break_change"] = np.nan
    sensitivity.loc[long_index, "second_break_change"] = _change(
        variants[long_index][1].coefficients, "post2"
    )[0]
    series_out = main.series.rename(
        columns={"fitted": "fitted_main", "counterfactual": "counterfactual_main"}
    )
    straight = linear.series.set_index("period")
    series_out["fitted_linear"] = series_out.period.map(straight.fitted)
    series_out["counterfactual_linear"] = series_out.period.map(straight.counterfactual)
    coefficients = main.coefficients.assign(
        label=main.coefficients.term.map(SEGMENTED_TERMS).fillna(main.coefficients.term)
    )
    trend_choice = trend_choice.assign(
        chosen=trend_choice.label
        == ("one linear trend" if knot is None else f"knot at {knot:%b %Y}")
    )
    # The published table keeps the best candidates and always the straight line, which is the
    # specification the page is arguing against and would otherwise fall off the end.
    straight = trend_choice[trend_choice.label == "one linear trend"]
    trend_choice = pd.concat([trend_choice.head(8), straight]).drop_duplicates(subset="label")
    calendar = calendar_placebo_fits(series, it)
    return {
        "q8_points_fit": coefficients,
        "q8_points_series": series_out,
        "q8_points_sensitivity": sensitivity,
        "q8_points_trend_choice": trend_choice,
        "q8_points_placebo": placebo_fits(series, it),
        "q8_points_calendar_placebo": calendar,
        "q8_points_calibration": placebo_calibration(calendar),
        "q8_points_death_definitions": death_definition_ratio(series, monthly_series("deaths_24h")),
        "q8_points_transitions": seasonal_transitions(series),
        "q8_points_forecast": forecast_validation(series, it),
    }


def speed_limit_fits() -> dict[str, pd.DataFrame]:
    """The 2019 conventional-road speed limit: the two tables that record why no claim is made.

    The design compares conventional roads with motorways and dual carriageways month by month.
    It fails its own falsification check (a break placed in January 2017 makes the two groups
    diverge by +12 % with an interval that excludes zero), so the estimate is reported nowhere on
    the site except as a negative result. These two tables are kept so that the negative result is
    reproducible; the fitted series and coefficient table that only ever fed figures are not.
    """
    it = INTERVENTIONS["speed_limit_90"]
    panel = monthly_by_road_group()
    main = did_fit(panel, it)
    variants: list[tuple[str, ItsFit, pd.Timestamp, pd.Timestamp]] = [
        (
            "Design as specified: conventional against motorways and dual carriageways, Poisson",
            main,
            it.pre_start,
            it.post_end,
        ),
        (
            "With a slope change for the treated group",
            did_fit(panel, it, variant="slope", slope=True),
            it.pre_start,
            it.post_end,
        ),
        (
            "Negative binomial",
            did_fit(panel, it, variant="negative_binomial", family="negative_binomial"),
            it.pre_start,
            it.post_end,
        ),
        (
            "Post-period to December 2024 with pandemic periods",
            did_fit(panel, it, variant="long", end=it.long_post_end, pandemic=True),
            it.pre_start,
            it.long_post_end,  # type: ignore[arg-type]
        ),
    ]
    sensitivity = pd.DataFrame(
        [{"label": label, **_fit_row(fit, _window_text(s, e))} for label, fit, s, e in variants]
    )
    control = [_change(fit.coefficients, "post")[0] for _, fit, _, _ in variants]
    sensitivity["control_change"] = control
    # Every row is a fit of a design that fails its placebo test: none is an estimate.
    sensitivity.insert(0, "status", "not an estimate: the design fails its placebo test")
    return {
        "q8_speed_placebo": did_placebos(panel, it),
        "q8_speed_sensitivity": sensitivity,
    }
