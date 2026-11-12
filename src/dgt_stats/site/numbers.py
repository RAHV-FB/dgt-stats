"""Result tables read once and shared by the pages that quote them."""

from __future__ import annotations

import pandas as pd

from dgt_stats import factors
from dgt_stats.site.components import read_table


def _severity_numbers() -> dict[str, object]:
    holdout = read_table("q3_holdout_summary").set_index("outcome")
    coefficients = read_table("q3_model_coefficients")
    fatal = coefficients[coefficients.outcome == "fatal"]
    adverse = read_table("q3_adverse_conditions")
    fatal_adverse = adverse[adverse.outcome == "fatal"].set_index(["variant", "level"])
    return {
        "n": int(fatal.n.iloc[0]),
        "fatal_share": float(fatal.events.iloc[0]) / float(fatal.n.iloc[0]),
        "auc_fatal": float(holdout.loc["fatal", "auc"]),
        "auc_serious": float(holdout.loc["serious", "auc"]),
        "adverse": fatal_adverse,
        "coefficients": coefficients,
        "holdout": holdout,
    }


def _policy_numbers() -> dict[str, object]:
    sensitivity = read_table("q8_points_sensitivity").set_index("variant")
    calendar = read_table("q8_points_calendar_placebo")
    forecast = read_table("q8_points_forecast")
    transitions = read_table("q8_points_transitions")
    trend = read_table("q8_points_trend_choice")
    return {
        "sensitivity": sensitivity,
        "calendar": calendar,
        "calibration": read_table("q8_points_calibration").iloc[0],
        "forecast": forecast,
        "transitions": transitions,
        "trend": trend,
        "main": sensitivity.loc["main"],
        "linear": sensitivity.loc["linear_trend"],
        "true_calendar": calendar[calendar.is_true].iloc[0],
        "true_forecast": forecast[forecast.is_true].iloc[0],
    }


def _risk_numbers() -> dict[str, object]:
    """``latest``: the last year's rows by (outcome, denominator)."""
    index = read_table("risk_index")
    last = int(index.year.max())
    latest = index[index.year == last].set_index(["outcome", "denominator"])
    return {"index": index, "base": int(index.year.min()), "last": last, "latest": latest}


def _long_run_numbers() -> dict[str, object]:
    series = read_table("longrun_series")
    segments = read_table("longrun_segments")
    efficiency = read_table("longrun_efficiency")
    projected = series[series.period == "projected"].set_index(["measure", "year"])
    return {
        "series": series,
        "segments": segments,
        "efficiency": efficiency,
        "projected": projected,
        "last": int(series.year.max()),
    }


def _season_numbers() -> dict[str, object]:
    """Month effects per day (``none``) and per tonne of road fuel (the only exposure); the
    lockdown table compares deaths with road fuel sold."""
    effects = read_table("season_month_effects").set_index(["exposure", "month"])
    lockdown = read_table("season_lockdown").set_index("month")
    return {"effects": effects, "lockdown": lockdown}


def _sex_numbers() -> dict[str, object]:
    ratios = read_table("drivers_sex_ratios").set_index(["scope", "band", "measure"])
    rates = read_table("drivers_sex_rates").set_index(["scope", "band", "sex"])
    return {"ratios": ratios, "rates": rates}


def _speed_numbers() -> dict[str, object]:
    pooled = read_table("speed_severity_pooled").set_index("road_type")
    yearly = read_table("speed_severity")
    all_roads = yearly[yearly.road_type == "all"].set_index("year")
    return {"pooled": pooled, "yearly": yearly, "all_roads": all_roads}


def _factor_numbers() -> dict[str, object]:
    table = read_table("factor_shares")
    # The comparable runs and the year-to-year changes follow from the published shares.
    windows = factors.comparable_windows(shares=table)
    changes = factors.factor_consistency(shares=table)
    shares = table.set_index(["zone", "factor", "year"])
    return {"windows": windows, "changes": changes, "shares": shares}


def _window(windows: pd.DataFrame, zone: str, factor: str, year: int) -> pd.Series:
    """The comparable window of ``factor`` in ``zone`` that contains ``year``."""
    match = windows[
        (windows.zone == zone)
        & (windows.factor == factor)
        & (windows.first_year <= year)
        & (windows.last_year >= year)
    ]
    return match.iloc[0]


def _driver_numbers() -> dict[str, object]:
    """Involvement per km by driver age and sex, read from ``risk_*``: the central estimate
    (the average of the Barcelona and Madrid profiles; ``central`` for the four age groups,
    ``older`` for 65-74 and 75 and over under the Madrid split), the ranges across alternative
    assumptions (``ranges``, a table by measure and group), deaths once involved (``severity``)
    and the working-day check in Barcelona (``city``)."""
    from dgt_stats.exposure_risk import national

    rates = read_table("risk_national_rates")
    central = rates[rates.method == national.CENTRAL_METHOD].set_index("group")
    split = read_table("risk_older_split")
    older = split[
        (split.profile == national.CENTRAL_METHOD) & (split.assumption == national.REFERENCE_SPLIT)
    ].set_index("group")
    ranges = read_table("risk_national_ranges")
    city = read_table("risk_barcelona_rates")
    return {
        "central": central,
        "older": older,
        "ranges": ranges,
        "involved_ranges": ranges[ranges.measure == "involved per km"].set_index("group"),
        "city": city[city.numerator == city.numerator.iloc[0]],
        "city_all": city,
        "severity": read_table("risk_severity_and_licences").set_index("group"),
    }


def per_km_ratio(numbers: dict[str, object], group: str) -> dict[str, float | str]:
    """One group's involvement per km against drivers aged 45-64: the central ratio, its 95%
    sampling interval and the range across the alternative assumptions, all to one decimal."""
    row = numbers["involved_ranges"].loc[group]
    return {
        "ratio": f"{row.ratio:.1f}",
        "interval": f"{row.ratio_low:.1f}–{row.ratio_high:.1f}",
        "range": f"{row.range_min:.1f}–{row.range_max:.1f}",
        "low": float(row.range_min),
        "high": float(row.range_max),
    }


# How many Monte Carlo standard errors an end of a joint sampling interval must stand from the
# 45-64 rate for a wording to rest on which side of it the end lies.
MC_MARGIN = 3


def mc_digits(*standard_errors: float, coarsest: int = 0) -> int:
    """The decimals that Monte Carlo standard errors support: the unit of the last digit printed
    is at least twice the largest error (two decimals need errors up to 0.005, one up to 0.05,
    whole numbers up to 0.5, tens, digits -1, up to 5). Another set of the surveys' replicates
    would then rarely change the printed figure by more than one unit of its last digit. No
    figure is printed coarser than ``coarsest`` decimals."""
    worst = max(float(se) for se in standard_errors)
    for digits in range(2, coarsest, -1):
        if 2 * worst <= 10.0**-digits:
            return digits
    return coarsest


def _fixed(value: float, digits: int) -> str:
    """``value`` to ``digits`` decimals; negative digits round to tens, hundreds..."""
    if digits >= 0:
        return f"{float(value):,.{digits}f}"
    return f"{round(float(value), digits):,.0f}"


# The most decimals an interval end gets so that it does not print as 1 (:func:`_clear_of_one`).
FINEST = 2


def _clear_of_one(value: float, se: float, digits: int) -> int:
    """``digits``, or more, up to :data:`FINEST`, when ``value`` stands :data:`MC_MARGIN` Monte
    Carlo errors clear of 1 but would print as 1: an interval that lies wholly on one side of 1
    is then not printed as reaching it."""
    while (
        digits < FINEST
        and round(float(value), digits) == 1
        and abs(float(value) - 1) >= MC_MARGIN * float(se)
    ):
        digits += 1
    return digits


def mc_interval(
    low: float,
    high: float,
    se_low: float,
    se_high: float,
    digits: int | None = None,
    sep: str = "–",
    coarsest: int = 0,
) -> str:
    """A sampling interval printed at the precision its Monte Carlo errors support
    (:func:`mc_digits`), or at ``digits`` if that is coarser. An interval that lies wholly on
    one side of 1, with its nearer end standing clear of 1 but printing as 1, gets the decimals
    that end needs on both ends (:func:`_clear_of_one`), so it is not shown reaching 1."""
    supported = mc_digits(se_low, se_high, coarsest=coarsest)
    shown = supported if digits is None else min(digits, supported)
    if float(low) > 1:
        shown = _clear_of_one(low, se_low, shown)
    elif float(high) < 1:
        shown = _clear_of_one(high, se_high, shown)
    return f"{_fixed(low, shown)}{sep}{_fixed(high, shown)}"


def joint_interval(row: pd.Series, digits: int | None = None, sep: str = "–") -> str:
    """A joint sampling interval (``ratio_low``, ``ratio_high``) printed at the precision its Monte
    Carlo errors (``mc_se_low``, ``mc_se_high``) support, or at ``digits`` if that is coarser."""
    return mc_interval(
        row["ratio_low"], row["ratio_high"], row["mc_se_low"], row["mc_se_high"], digits, sep
    )


def rate_interval(row: pd.Series, column: str, sep: str = "–", coarsest: int = 0) -> str:
    """The interval of ``column`` in a row of ``risk_national_rates`` (``{column}_low``,
    ``{column}_high``, with ``{column}_mc_se_low`` and ``_high``) at the precision its Monte Carlo
    errors support. Rates per billion km pass ``coarsest=-2`` to round to tens if need be."""
    return mc_interval(
        row[f"{column}_low"],
        row[f"{column}_high"],
        row[f"{column}_mc_se_low"],
        row[f"{column}_mc_se_high"],
        sep=sep,
        coarsest=coarsest,
    )
