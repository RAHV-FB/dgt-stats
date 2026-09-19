"""Policy case study (question Q8): interrupted time series on monthly road deaths.

Two interventions, two designs. The points-based licence of 1 July 2006 is a segmented regression
on the yearbook's monthly death series (1993–2024). The 90 km/h limit on conventional roads of
29 January 2019 is a difference-in-differences interrupted series on the microdata: conventional
roads against motorways and dual carriageways, month by month, 2016–2024. Both are Poisson
regressions with Newey–West standard errors; the estimates are read as coincidences unless the
pre-trend, the placebo distribution and the sensitivity fits all agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from dgt_stats import io_tables
from dgt_stats.paths import PROCESSED_DATA_DIR

PROCESSED_CRASHES = PROCESSED_DATA_DIR / "accidentes.parquet"

TREATED = "conventional"
CONTROL = "motorway_dual"
CONTROL_GROUPS = ("motorway", "dual_carriageway")
GROUP_LABELS = {TREATED: "Conventional roads", CONTROL: "Motorways and dual carriageways"}


@dataclass(frozen=True)
class Intervention:
    """One policy change and the windows its fits use.

    ``date`` is the first month treated as post-intervention. ``pre_start`` opens the fitting
    window, ``post_end`` closes the clean post-period, ``long_post_end`` the extended one used in
    the sensitivity fit, and ``second_break`` marks a confounding change inside that extended
    window. ``placebo_pre`` and ``placebo_post`` are the months a placebo break needs on each side.
    """

    key: str
    label: str
    date: pd.Timestamp
    pre_start: pd.Timestamp
    post_end: pd.Timestamp
    design: str  # "segmented" or "did"
    long_post_end: pd.Timestamp | None = None
    second_break: pd.Timestamp | None = None
    second_break_label: str = ""
    exclude_from: pd.Timestamp | None = None
    exclude_label: str = ""
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
        second_break_label="Penal Code reform on driving offences, 2 December 2007",
    ),
    "speed_limit_90": Intervention(
        key="speed_limit_90",
        label="90 km/h limit on conventional roads, 29 January 2019",
        date=pd.Timestamp("2019-02-01"),
        pre_start=pd.Timestamp("2016-01-01"),
        post_end=pd.Timestamp("2020-02-01"),
        design="did",
        long_post_end=pd.Timestamp("2024-12-01"),
        exclude_from=pd.Timestamp("2020-03-01"),
        exclude_label="pandemic restrictions from March 2020",
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
    is present, with zero deaths where a group had none.
    """
    if crashes is None:
        crashes = pd.read_parquet(
            PROCESSED_CRASHES, columns=["ANYO", "MES", "road_group", "TOTAL_MU30DF"]
        )
    group = pd.Series(pd.NA, index=crashes.index, dtype="string")
    group[crashes.road_group == TREATED] = TREATED
    group[crashes.road_group.isin(CONTROL_GROUPS)] = CONTROL
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


def fleet_offset(periods: pd.Series) -> pd.Series:
    """Registered vehicles for each month, the annual series interpolated between mid-years."""
    annual = io_tables.read_table("series_annual")
    fleet = annual[(annual.metric == "vehicle_fleet") & (annual.zone == "all")]
    fleet = fleet.dropna(subset=["value"]).sort_values("year")
    knots = pd.to_datetime(fleet.year.astype(int).astype(str) + "-07-01")
    x = knots.astype("int64").to_numpy(dtype=float)
    y = fleet.value.to_numpy(dtype=float)
    target = pd.to_datetime(periods).astype("int64").to_numpy(dtype=float)
    return pd.Series(np.interp(target, x, y), index=periods.index, name="fleet")


def window(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Rows with ``period`` between ``start`` and ``end`` inclusive."""
    return frame[(frame.period >= start) & (frame.period <= end)].reset_index(drop=True)


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


def _segmented_design(
    frame: pd.DataFrame,
    break_date: pd.Timestamp,
    slope: bool,
    second_break: pd.Timestamp | None,
    pandemic: bool,
) -> pd.DataFrame:
    period = frame.period
    t = period.apply(lambda p: _months_between(period.iloc[0], p)).astype(float)
    post = (period >= break_date).astype(float)
    design = pd.DataFrame({"const": 1.0, "t": t, "post": post}, index=frame.index)
    if slope:
        since = period.apply(lambda p: _months_between(break_date, p)).astype(float)
        design["post_t"] = post * since
    if second_break is not None:
        design["post2"] = (period >= second_break).astype(float)
    design = pd.concat([design, _month_dummies(period)], axis=1)
    if pandemic:
        design = pd.concat([design, _pandemic_columns(period)], axis=1)
    return design


def _hac(groups: np.ndarray | None = None) -> dict[str, object]:
    """Newey–West covariance with 12 lags; within each group when ``groups`` is given (a panel)."""
    if groups is None:
        return {"cov_type": "HAC", "cov_kwds": {"maxlags": HAC_LAGS}}
    return {"cov_type": "hac-panel", "cov_kwds": {"groups": groups, "maxlags": HAC_LAGS}}


def _fit(
    y: pd.Series,
    design: pd.DataFrame,
    family: str,
    offset: pd.Series | None,
    cov: dict[str, object] | None = None,
) -> tuple[pd.Series, pd.DataFrame, float, np.ndarray]:
    """Fit a Poisson or negative-binomial regression with Newey–West errors.

    Returns the parameters, their 95 % intervals, the Pearson dispersion and the fitted means.
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
    return params, coefficients, dispersion, mu


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
    offset: bool = False,
    slope: bool = True,
    second_break: pd.Timestamp | None = None,
    pandemic: bool = False,
) -> ItsFit:
    """Segmented regression of monthly deaths with a level (and slope) change at ``break_date``."""
    break_date = break_date or intervention.date
    frame = window(series, start or intervention.pre_start, end or intervention.post_end)
    if frame.empty or (frame.period >= break_date).sum() == 0:
        raise ValueError("segmented_fit: the window has no post-intervention months")
    design = _segmented_design(frame, break_date, slope, second_break, pandemic)
    exposure = fleet_offset(frame.period) if offset else None
    params, coefficients, dispersion, mu = _fit(frame.deaths, design, family, exposure)
    counterfactual_design = design.copy()
    for column in ("post", "post_t", "post2"):
        if column in counterfactual_design:
            counterfactual_design[column] = 0.0
    out = frame[["period", "deaths"]].copy()
    out["fitted"] = mu
    out["counterfactual"] = _predict(counterfactual_design, params, exposure)
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
    )


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
    params, coefficients, dispersion, mu = _fit(frame.deaths, design, family, None, _hac(groups))
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


def _fit_row(fit: ItsFit, window_text: str) -> dict[str, object]:
    return {
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


def _window_text(start: pd.Timestamp, end: pd.Timestamp) -> str:
    return f"{start:%b %Y} to {end:%b %Y}"


def points_licence_fits() -> dict[str, pd.DataFrame]:
    """Main fit, placebo distribution and sensitivity table for the 2006 points licence."""
    it = INTERVENTIONS["points_licence"]
    series = monthly_series()
    main = segmented_fit(series, it)
    variants: list[tuple[str, ItsFit, pd.Timestamp, pd.Timestamp]] = [
        ("Main: 30-day deaths, all roads, Poisson", main, it.pre_start, it.post_end),
        (
            "24-hour deaths",
            segmented_fit(monthly_series("deaths_24h"), it, variant="24h"),
            it.pre_start,
            it.post_end,
        ),
        (
            "Interurban roads only",
            segmented_fit(monthly_series(zone="interurban"), it, variant="interurban"),
            it.pre_start,
            it.post_end,
        ),
        (
            "Urban streets only",
            segmented_fit(monthly_series(zone="urban"), it, variant="urban"),
            it.pre_start,
            it.post_end,
        ),
        (
            "Pre-period from January 1993",
            segmented_fit(series, it, variant="from_1993", start=pd.Timestamp("1993-01-01")),
            pd.Timestamp("1993-01-01"),
            it.post_end,
        ),
        (
            "Level change only, no slope term",
            segmented_fit(series, it, variant="no_slope", slope=False),
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
            ),
            it.pre_start,
            it.long_post_end,  # type: ignore[arg-type]
        ),
        (
            "Registered fleet as exposure offset",
            segmented_fit(series, it, variant="fleet_offset", offset=True),
            it.pre_start,
            it.post_end,
        ),
        (
            "Negative binomial",
            segmented_fit(series, it, variant="negative_binomial", family="negative_binomial"),
            it.pre_start,
            it.post_end,
        ),
    ]
    sensitivity = pd.DataFrame(
        [{"label": label, **_fit_row(fit, _window_text(s, e))} for label, fit, s, e in variants]
    )
    second_break = _change(variants[6][1].coefficients, "post2")
    sensitivity["second_break_change"] = np.nan
    sensitivity.loc[6, "second_break_change"] = second_break[0]
    placebo = placebo_fits(series, it)
    series_out = segmented_fit(
        series, it, variant="display", end=it.long_post_end, second_break=it.second_break
    ).series
    shown = main.series.set_index("period")
    series_out["fitted_main"] = series_out.period.map(shown.fitted)
    series_out["counterfactual_main"] = series_out.period.map(shown.counterfactual)
    series_out = series_out.rename(
        columns={"fitted": "fitted_long", "counterfactual": "counterfactual_long"}
    )
    coefficients = main.coefficients.assign(
        label=main.coefficients.term.map(SEGMENTED_TERMS).fillna(main.coefficients.term)
    )
    return {
        "q8_points_fit": coefficients,
        "q8_points_series": series_out,
        "q8_points_placebo": placebo,
        "q8_points_sensitivity": sensitivity,
    }


def speed_limit_fits() -> dict[str, pd.DataFrame]:
    """Main fit, placebos and sensitivity table for the 2019 conventional-road speed limit."""
    it = INTERVENTIONS["speed_limit_90"]
    panel = monthly_by_road_group()
    main = did_fit(panel, it)
    variants: list[tuple[str, ItsFit, pd.Timestamp, pd.Timestamp]] = [
        (
            "Main: conventional against motorways and dual carriageways, Poisson",
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
    placebo = did_placebos(panel, it)
    long = did_fit(panel, it, variant="display", end=it.long_post_end, pandemic=True).series
    shown = main.series.set_index(["group", "period"])
    keys = list(zip(long.group, long.period))
    long["fitted_main"] = [shown.fitted.get(k, np.nan) for k in keys]
    long["counterfactual_main"] = [shown.counterfactual.get(k, np.nan) for k in keys]
    long = long.rename(columns={"fitted": "fitted_long", "counterfactual": "counterfactual_long"})
    long["group_label"] = long.group.map(GROUP_LABELS)
    coefficients = main.coefficients.assign(
        label=main.coefficients.term.map(
            {"post_treated": "level change, conventional roads", "post": "level change, control"}
        ).fillna(main.coefficients.term)
    )
    return {
        "q8_speed_fit": coefficients,
        "q8_speed_series": long,
        "q8_speed_placebo": placebo,
        "q8_speed_sensitivity": sensitivity,
    }
