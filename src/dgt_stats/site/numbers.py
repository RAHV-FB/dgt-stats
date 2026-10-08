"""Result tables read once and shared by the pages that quote them."""

from __future__ import annotations

import pandas as pd

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
        "definitions": read_table("q8_points_death_definitions"),
        "forecast": forecast,
        "transitions": transitions,
        "trend": trend,
        "main": sensitivity.loc["main"],
        "linear": sensitivity.loc["linear_trend"],
        "true_calendar": calendar[calendar.is_true].iloc[0],
        "true_forecast": forecast[forecast.is_true].iloc[0],
    }


def _risk_numbers() -> dict[str, object]:
    """``latest``: the last year's rows by (outcome, denominator). Licence holders and the fleet
    divide only driver and occupant casualties (``numerator``) and have no injury-crash rows."""
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
    """Month effects with no exposure (``none``) and per tonne of road fuel (the only exposure);
    the lockdown table keeps petrol and toll-motorway changes as traffic beside deaths only."""
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
    windows = read_table("factor_windows")
    changes = read_table("factor_changes")
    shares = read_table("factor_shares").set_index(["zone", "factor", "year"])
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


CENTRAL_KM = "less taxi and ride-hailing"


def _driver_numbers() -> dict[str, object]:
    """Involvement per km by driver age (central Method A, the licence-calibrated A2, every
    sensitivity), the Barcelona working-day check and the split at 75, read from ``risk_*``."""
    rates = read_table("risk_national_rates")
    rates = rates[rates.km_total == CENTRAL_KM]
    central = rates[rates.method.str.startswith("A:")].set_index("group")
    licence = rates[rates.method.str.startswith("A2:")].set_index("group")
    sensitivity = read_table("risk_national_sensitivity")
    ranges = sensitivity.groupby("group").involved_ratio.agg(["min", "max"])
    by_source = sensitivity.groupby(["source", "group"]).involved_ratio.agg(["min", "max"])
    older = read_table("risk_older_split")
    older_range = read_table("risk_older_sensitivity")
    city = read_table("risk_barcelona_rates")
    city = city[city.numerator == city.numerator.iloc[0]]
    city_older = read_table("risk_barcelona_older")
    return {
        "rates": rates,
        "central": central,
        "licence": licence,
        "sensitivity": sensitivity,
        "ranges": ranges,
        "by_source": by_source,
        "older": older,
        "older_range": {
            "65-74": (float(older_range.ratio_65_74.min()), float(older_range.ratio_65_74.max())),
            "75+": (float(older_range.ratio_75_plus.min()), float(older_range.ratio_75_plus.max())),
        },
        "city": city,
        "city_all": read_table("risk_barcelona_rates"),
        "city_older": city_older,
        "severity": read_table("risk_severity_and_licences").set_index("group"),
    }


# The three wordings of what the per-km figures say about drivers aged 75 and over, from the
# strongest to the weakest; :func:`_older_numbers` picks the one the tables support.
PASS, INTERMEDIATE, FAIL = "pass", "intermediate", "fail"
# What the 75+ sensitivity range allows, as a clause after "the sensitivity range is a to b times
# the 45-64 rate", for every page that states it: the same evidence gets the same words.
OLDER_CONCLUSION = {
    PASS: "; every combination tested that agrees with surveys of men's driving puts them above "
    "that rate, even allowing for sampling error, but how far above is not established",
    INTERMEDIATE: ", so the data do not establish that they are involved more often per "
    "kilometre than drivers aged 45–64, or by how much",
    FAIL: ", so whether they are involved more or less often per kilometre is not established",
}
# How many Monte Carlo standard errors an end of a joint sampling interval must stand from the
# 45-64 rate for a wording to rest on which side of it the end lies.
MC_MARGIN = 3


def mc_digits(*standard_errors: float) -> int:
    """The decimals that Monte Carlo standard errors support: the unit of the last digit printed
    is at least twice the largest error (two decimals need errors up to 0.005, one up to 0.05).
    Another set of the surveys' replicates would then rarely change the printed figure by more
    than one unit of its last digit."""
    worst = max(float(se) for se in standard_errors)
    for digits in (2, 1):
        if 2 * worst <= 10.0**-digits:
            return digits
    return 0


def joint_interval(row: pd.Series, digits: int | None = None, sep: str = "–") -> str:
    """A joint sampling interval (``ratio_low``, ``ratio_high``) printed at the precision its Monte
    Carlo errors (``mc_se_low``, ``mc_se_high``) support, or at ``digits`` if that is coarser."""
    supported = mc_digits(row["mc_se_low"], row["mc_se_high"])
    shown = supported if digits is None else min(digits, supported)
    return f"{float(row['ratio_low']):.{shown}f}{sep}{float(row['ratio_high']):.{shown}f}"


def _older_numbers() -> dict[str, object]:
    """Ages 75 and over: the conditional (Madrid-pattern) estimate with its joint sampling
    interval, the sensitivity range, the span of the combinations not marked as at odds with
    men's driving, the sampling intervals at its ends, and the wording the tables allow.

    PASS needs the lowest unmarked combination above the 45-64 rate even at the bottom of its
    sampling interval, and the conditional estimate's interval above it too; INTERMEDIATE, the
    lowest unmarked combination above it at its point value; otherwise FAIL."""
    from dgt_stats.exposure_risk import national

    split = read_table("risk_older_split")
    older = read_table("risk_older_sensitivity")
    extremes = read_table("risk_older_extremes").set_index(["group", "end"])
    conditional = split[split.assumption == national.REFERENCE_SPLIT].set_index("group")
    unmarked = older[~older.at_odds_with_mens_driving]
    lowest = extremes.loc[("75+", "lowest unmarked")]
    clear_min = float(unmarked.ratio_75_plus.min())
    if abs(float(lowest.value) - clear_min) > 1e-9:
        raise ValueError("risk_older_extremes does not match risk_older_sensitivity")
    # A wording that rests on which side of the 45-64 rate an interval's lower end lies needs
    # that end clear of it by more than its Monte Carlo error; otherwise more replicates decide.
    for name, row in (
        ("the lowest unmarked combination", lowest),
        ("the conditional estimate", conditional.loc["75+"]),
    ):
        if abs(float(row.ratio_low) - 1) < MC_MARGIN * float(row.mc_se_low):
            raise ValueError(
                f"75+: the sampling interval of {name} ends within Monte Carlo error of the "
                "45-64 rate; rerun with more replicates before choosing a wording"
            )
    if (
        clear_min > 1
        and float(lowest.ratio_low) > 1
        and float(conditional.loc["75+", "ratio_low"]) > 1
    ):
        tier = PASS
    elif clear_min > 1:
        tier = INTERMEDIATE
    else:
        tier = FAIL
    return {
        "split": split,
        "older": older,
        "unmarked": unmarked,
        "extremes": extremes,
        "conditional": conditional,
        "range": {
            "65-74": (float(older.ratio_65_74.min()), float(older.ratio_65_74.max())),
            "75+": (float(older.ratio_75_plus.min()), float(older.ratio_75_plus.max())),
        },
        "clear": {
            "65-74": (float(unmarked.ratio_65_74.min()), float(unmarked.ratio_65_74.max())),
            "75+": (clear_min, float(unmarked.ratio_75_plus.max())),
        },
        "lowest_clear": lowest,
        "tier": tier,
    }
