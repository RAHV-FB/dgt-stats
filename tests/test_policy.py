import numpy as np
import pandas as pd
import pytest

from dgt_stats import io_tables, policy

pytestmark = pytest.mark.skipif(
    not io_tables.staging_path("series_monthly").exists(),
    reason="run `python scripts/ingest.py tables` first",
)


def test_monthly_series_is_complete_and_matches_the_yearbook() -> None:
    series = policy.monthly_series()
    assert len(series) == 384
    assert series.period.iloc[0] == pd.Timestamp("1993-01-01")
    assert series.period.iloc[-1] == pd.Timestamp("2024-12-01")
    year_2006 = series[series.period.dt.year == 2006].set_index(
        series.period.dt.month[series.period.dt.year == 2006]
    )
    assert year_2006.deaths.loc[7] == 380 and year_2006.deaths.loc[12] == 324
    assert series[series.period.dt.year == 2024].deaths.sum() == 1_785
    interurban = policy.monthly_series(zone="interurban")
    urban = policy.monthly_series(zone="urban")
    gap = interurban.deaths + urban.deaths - series.deaths
    # The yearbook's zone sheets differ from its all-roads sheet by one death in four months of 1995.
    assert (gap.abs() <= 1).all() and (gap != 0).sum() == 4
    assert set(series.period[gap != 0].dt.year) == {1995}
    day = policy.monthly_series(metric="deaths_24h")
    assert (day.deaths <= series.deaths).all()


def test_intervention_windows() -> None:
    points = policy.INTERVENTIONS["points_licence"]
    assert points.post_months == 17
    assert points.second_break == pd.Timestamp("2007-12-01")
    series = policy.monthly_series()
    inside = policy.window(series, points.pre_start, points.post_end)
    assert len(inside) == 78 + 17


def _synthetic_series(
    level_change: float, break_date: str, seed: int = 3, slope_change: float = 0.0
) -> pd.DataFrame:
    """Poisson counts with a trend, a season, a known level change at ``break_date`` and an
    optional extra slope (per month, log scale) after it."""
    rng = np.random.default_rng(seed)
    periods = pd.date_range("2000-01-01", "2007-11-01", freq="MS")
    t = np.arange(len(periods))
    season = 0.12 * np.sin(2 * np.pi * (periods.month - 1) / 12)
    post = (periods >= pd.Timestamp(break_date)).astype(float)
    since = np.clip(t - int(np.argmax(post)), 0, None) * post
    mu = np.exp(
        np.log(380) - 0.004 * t + season + np.log1p(level_change) * post + slope_change * since
    )
    deaths = rng.poisson(mu).astype(float)
    return pd.DataFrame({"period": periods, "deaths": deaths})


def test_segmented_fit_recovers_a_known_level_change() -> None:
    it = policy.INTERVENTIONS["points_licence"]
    series = _synthetic_series(-0.15, "2006-07-01")
    fit = policy.segmented_fit(series, it)
    assert fit.n == 95 and fit.break_date == it.date
    assert fit.level_change == pytest.approx(-0.15, abs=0.04)
    assert fit.level_low < -0.15 < fit.level_high
    assert abs(fit.slope_change) < 0.15
    assert 0.5 < fit.dispersion < 2.0
    assert set(fit.series.columns) == {"period", "deaths", "fitted", "counterfactual", "post"}
    pre = fit.series[~fit.series.post]
    assert np.allclose(pre.fitted, pre.counterfactual)
    post = fit.series[fit.series.post]
    assert (post.fitted < post.counterfactual).all()
    trend = fit.coefficients.set_index("term").estimate["t"]
    assert trend == pytest.approx(-0.004, abs=0.001)
    no_slope = policy.segmented_fit(series, it, slope=False)
    assert np.isnan(no_slope.slope_change)
    nb = policy.segmented_fit(series, it, family="negative_binomial")
    assert nb.level_change == pytest.approx(fit.level_change, abs=0.02)
    sloped = policy.segmented_fit(_synthetic_series(0.0, "2006-07-01", slope_change=-0.01), it)
    assert sloped.slope_change == pytest.approx(np.expm1(-0.12), abs=0.06)  # annualised
    late = sloped.series[sloped.series.post].tail(6)
    assert (late.fitted < late.counterfactual).all()


def test_post_period_change_reads_the_step_with_its_slope() -> None:
    it = policy.INTERVENTIONS["points_licence"]
    # A step of -10% that a slope of +1% a month wears away in about ten and a half months.
    series = _synthetic_series(-0.10, "2006-07-01", slope_change=0.01, seed=11)
    fit = policy.segmented_fit(series, it)
    change = policy.post_period_change(fit, it.post_months)
    params = fit.coefficients.set_index("term").estimate
    assert change["mean_change"] == pytest.approx(np.expm1(params.post + 8 * params.post_t))
    assert change["end_change"] == pytest.approx(np.expm1(params.post + 16 * params.post_t))
    assert change["months_to_zero"] == pytest.approx(-params.post / params.post_t)
    assert 6 < change["months_to_zero"] < 16
    assert change["mean_low"] < change["mean_change"] < change["mean_high"]
    # The average log change equals the log of the fitted deaths over the projection's,
    # month by month, averaged.
    post = fit.series[fit.series.post]
    assert np.log1p(change["mean_change"]) == pytest.approx(
        np.mean(np.log(post.fitted / post.counterfactual))
    )
    flat = policy.segmented_fit(series, it, slope=False)
    level_only = policy.post_period_change(flat, it.post_months)
    assert level_only["mean_change"] == pytest.approx(flat.level_change)
    assert level_only["end_change"] == pytest.approx(flat.level_change)
    assert np.isnan(level_only["months_to_zero"])


def test_placebo_calibration_counts_misses_and_widens_the_interval() -> None:
    calendar = pd.DataFrame(
        {
            "year": [2000, 2001, 2002, 2003, 2006],
            "level_change": [0.05, -0.05, 0.02, -0.02, -0.10],
            "low": [0.01, -0.09, -0.01, -0.05, -0.14],
            "high": [0.09, -0.01, 0.05, 0.01, -0.06],
            "is_true": [False, False, False, False, True],
        }
    )
    row = policy.placebo_calibration(calendar).iloc[0]
    assert row.year == 2006 and row.n_placebos == 4
    assert row.n_excluding_zero == 2 and row.expected_excluding_zero == pytest.approx(0.2)
    steps = np.log1p([0.05, -0.05, 0.02, -0.02])
    assert row.placebo_sd == pytest.approx(np.std(steps, ddof=1))
    from scipy import stats

    t = stats.t.ppf(0.975, 3)
    assert row.calibrated_low == pytest.approx(np.expm1(np.log1p(-0.10) - t * row.placebo_sd))
    assert row.calibrated_high == pytest.approx(np.expm1(np.log1p(-0.10) + t * row.placebo_sd))
    assert row.se_ratio > 1


def test_points_licence_fits_assembles_the_published_tables() -> None:
    tables = policy.points_licence_fits()
    assert set(tables) == {
        "q8_points_fit",
        "q8_points_series",
        "q8_points_sensitivity",
        "q8_points_trend_choice",
        "q8_points_calendar_placebo",
        "q8_points_calibration",
        "q8_points_transitions",
        "q8_points_forecast",
    }
    sens = tables["q8_points_sensitivity"]
    assert sens.variant.iloc[0] == "main"
    assert set(sens.variant) >= {
        "main",
        "linear_trend",
        "quadratic",
        "knot_2004",
        "no_slope",
        "negative_binomial",
        "long",
    }
    assert not {"fuel", "toll", "24h", "interurban", "urban"} & set(sens.variant)
    assert "fleet_offset" not in set(sens.variant)  # the fleet does not divide every road user
    long_row = sens[sens.variant == "long"].iloc[0]
    assert long_row.n_months > sens[sens.variant == "main"].iloc[0].n_months
    assert np.isfinite(long_row.second_break_change)
    assert sens[sens.variant != "long"].second_break_change.isna().all()
    # The main specification is the piecewise one and it gives a smaller drop than the straight
    # line: that difference is the finding the page reports, so it is asserted here.
    main = sens[sens.variant == "main"].iloc[0]
    linear = sens[sens.variant == "linear_trend"].iloc[0]
    assert main.level_change < 0 and linear.level_change < main.level_change
    # Read with its slope change, the preferred step wears off inside the window: the average
    # change over the 17 months is small and its interval includes no change. Only the straight
    # line gives a fall that lasts.
    assert (sens.post_months == 17).all()
    assert main.slope_change_annual > 0 and 0 < main.months_to_zero < 17
    assert main.mean_low < main.mean_change < 0 < main.mean_high and main.end_change > 0
    assert main.mean_change == pytest.approx(
        np.expm1(np.log1p(main.level_change) + 8 * np.log1p(main.slope_change_annual) / 12)
    )
    assert linear.mean_high < 0
    no_slope = sens[sens.variant == "no_slope"].iloc[0]
    assert no_slope.mean_change == pytest.approx(no_slope.level_change)
    assert np.isnan(no_slope.months_to_zero)
    trend = tables["q8_points_trend_choice"]
    assert trend.chosen.sum() == 1
    straight = trend[trend.label == "one linear trend"].iloc[0]
    assert straight.delta_qaic > 2  # the pre-period prefers a bend
    assert trend[trend.chosen].delta_qaic.iloc[0] == 0
    calibration = tables["q8_points_calibration"].iloc[0]
    assert calibration.n_placebos == 14
    assert calibration.expected_excluding_zero == pytest.approx(0.7)
    assert calibration.n_excluding_zero > 2 * calibration.expected_excluding_zero
    assert calibration.calibrated_low < calibration.nominal_low < calibration.level_change
    forecast = tables["q8_points_forecast"]
    assert (forecast["rank"] == forecast.log_ratio.rank(method="min")).all()
    series = tables["q8_points_series"]
    assert {"fitted_main", "counterfactual_main", "counterfactual_linear"} <= set(series.columns)
    assert not {"z", "rank_z", "dispersion"} & set(forecast.columns)
    assert not {"deaths_after", "deaths_before"} & set(tables["q8_points_transitions"].columns)


def test_calendar_placebos_use_clean_windows_at_the_same_month() -> None:
    it = policy.INTERVENTIONS["points_licence"]
    series = policy.monthly_series()
    dates = policy.calendar_placebo_years(series, it)
    assert dates and all(date.month == 7 for date in dates)
    assert it.date not in dates
    for date in dates:
        start = date - pd.DateOffset(months=policy.CALENDAR_PRE_MONTHS)
        end = date + pd.DateOffset(months=it.post_months - 1)
        assert start >= series.period.min() and end <= series.period.max()
        assert not (start <= it.date <= end)  # never contains the real intervention
        assert not (start < policy.EXCLUDED_WINDOW[1] and end > policy.EXCLUDED_WINDOW[0])
    fits = policy.calendar_placebo_fits(series, it)
    assert fits.is_true.sum() == 1 and len(fits) == len(dates) + 1
    true = fits[fits.is_true].iloc[0]
    assert true.level_change == fits.level_change.min()
    assert int(true["rank"]) == 1 and int(true.n_fits) == len(fits)
    # The point of the test is that rank 1 is not the same as "outside the distribution".
    runner_up = fits[~fits.is_true].level_change.min()
    assert runner_up < 0 and abs(runner_up - true.level_change) < 0.05


def test_seasonal_transitions_cancel_seasonality_and_rank_2006() -> None:
    series = policy.monthly_series()
    transitions = policy.seasonal_transitions(series)
    assert set(transitions.year) == set(series.period.dt.year)
    # The first and last years cannot have a twelve-month ratio on both sides.
    assert transitions.twelve_month_ratio.isna().sum() == 2
    assert transitions[transitions.year.isin((2019, 2020, 2021))].excluded.all()
    assert transitions[transitions.excluded]["rank"].isna().all()
    ranked = transitions[transitions["rank"].notna()]
    assert len(ranked) == int(transitions.n_ranked.iloc[0])
    row = transitions[transitions.year == 2006].iloc[0]
    values = series.set_index("period").deaths
    after = values["2006-07-01":"2007-06-01"].sum()
    before = values["2005-07-01":"2006-06-01"].sum()
    assert row.twelve_month_ratio == pytest.approx(float(np.log(after / before)))
    assert 1 < row["rank"] <= 6  # a large fall, but not the largest in the series
    # The deadliest month of each year: usually July or August, but not always.
    by_month = series.assign(year=series.period.dt.year, month=series.period.dt.month)
    peaks = by_month.loc[by_month.groupby("year").deaths.idxmax()].set_index("year").month
    assert (transitions.set_index("year").peak_month == peaks).all()
    assert len(transitions) // 2 < transitions.peak_month.isin((7, 8)).sum() < len(transitions)


def test_forecast_validation_compares_like_with_like() -> None:
    it = policy.INTERVENTIONS["points_licence"]
    series = policy.monthly_series()
    forecast = policy.forecast_validation(series, it)
    assert forecast.is_true.sum() == 1
    assert len(forecast) == len(policy.calendar_placebo_years(series, it)) + 1
    assert (forecast.predicted > 0).all() and (forecast.observed > 0).all()
    assert np.allclose(forecast.log_ratio, np.log(forecast.observed / forecast.predicted))
    true = forecast[forecast.is_true].iloc[0]
    assert true.log_ratio < 0  # fewer deaths than the pre-July fit projects
    assert int(true["rank"]) > 1  # other Julys undershot their own forecast by more
    # The rank is the proportional shortfall the page describes.
    assert int(true["rank"]) == int((forecast.log_ratio < true.log_ratio).sum()) + 1


def test_flexible_pre_trend_is_chosen_on_the_pre_period_only() -> None:
    it = policy.INTERVENTIONS["points_licence"]
    series = policy.monthly_series()
    knot, table = policy.choose_trend_knot(series, it)
    assert knot is not None and it.pre_start < knot < it.date
    assert table.qaic.is_monotonic_increasing and table.delta_qaic.iloc[0] == 0
    assert (table.label == "one linear trend").sum() == 1
    # QAIC divides the deviance by one dispersion for every candidate and charges a knot two
    # terms, so the straight line's deficit is its extra deviance scaled, less four.
    straight = table[table.label == "one linear trend"].iloc[0]
    best = table.iloc[0]
    assert (table.dispersion == best.dispersion).all() and best.dispersion > 1
    assert best.n_parameters == straight.n_parameters + 2
    assert straight.delta_qaic == pytest.approx(
        (straight.deviance - best.deviance) / best.dispersion - 4
    )
    piecewise = policy.segmented_fit(series, it, trend="piecewise", knots=(knot,))
    linear = policy.segmented_fit(series, it)
    assert piecewise.level_change > linear.level_change
    # A knot placed anywhere reasonable gives the same story, which is what makes it reportable.
    for month in ("2003-01-01", "2004-01-01", "2005-01-01"):
        alternative = policy.segmented_fit(
            series, it, trend="piecewise", knots=(pd.Timestamp(month),)
        )
        assert -0.11 < alternative.level_change < -0.05
