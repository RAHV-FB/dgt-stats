import numpy as np
import pandas as pd
import pytest

from dgt_stats import io_tables, policy, summaries

pytestmark = pytest.mark.skipif(
    not (io_tables.staging_path("series_monthly").exists() and policy.PROCESSED_CRASHES.exists()),
    reason="run `python scripts/ingest.py tables` and `python scripts/build_tables.py` first",
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


def test_road_group_panel_covers_every_month_and_sums_to_the_microdata() -> None:
    panel = policy.monthly_by_road_group()
    assert set(panel.group) == {policy.TREATED, policy.CONTROL}
    assert panel.groupby("group").size().eq(9 * 12).all()
    treated = panel[panel.group == policy.TREATED].set_index("period").deaths
    control = panel[panel.group == policy.CONTROL].set_index("period").deaths
    # Snapshots of the two series, kept as a tripwire on the shape of the panel.
    assert treated.loc["2016-01-01"] == 67 and treated.loc["2016-07-01"] == 110
    assert control.loc["2016-01-01"] == 24 and control.loc["2016-07-01"] == 30
    # The panel reconciles to the microdata for the road-type codes methodology section 14 names.
    crashes = summaries.read_crashes(["TIPO_VIA", "TOTAL_MU30DF"])
    codes = [*policy.TREATED_CODES, *policy.CONTROL_CODES]
    assert panel.deaths.sum() == crashes[crashes.TIPO_VIA.isin(codes)].TOTAL_MU30DF.sum() == 10_741
    assert (
        panel[panel.group == policy.TREATED].deaths.sum()
        == crashes[crashes.TIPO_VIA.isin(policy.TREATED_CODES)].TOTAL_MU30DF.sum()
    )
    micro = pd.read_parquet(
        summaries.PROCESSED_CRASHES, columns=["ANYO", "MES", "TIPO_VIA", "TOTAL_MU30DF"]
    )
    by_year = panel.groupby([panel.period.dt.year, "group"]).deaths.sum().unstack()
    treated_raw = (
        micro[micro.TIPO_VIA.isin(policy.TREATED_CODES)].groupby("ANYO").TOTAL_MU30DF.sum()
    )
    control_raw = (
        micro[micro.TIPO_VIA.isin(policy.CONTROL_CODES)].groupby("ANYO").TOTAL_MU30DF.sum()
    )
    assert (by_year[policy.TREATED] == treated_raw.loc[by_year.index]).all()
    assert (by_year[policy.CONTROL] == control_raw.loc[by_year.index]).all()
    raw = pd.DataFrame(
        {
            "ANYO": [2016, 2016, 2016, 2016, 2016],
            "MES": [1, 1, 2, 3, 3],
            "TIPO_VIA": [6, 9, 1, 4, 5],
            "TOTAL_MU30DF": [2, 5, 1, 3, 4],
        }
    )
    small = policy.monthly_by_road_group(raw)
    # Code 9 (street) and code 4 (vía para automóviles) belong to neither group.
    assert len(small) == 24 and small.deaths.sum() == 7
    assert (
        small[(small.group == policy.CONTROL) & (small.period == "2016-02-01")].deaths.iloc[0] == 1
    )


def test_intervention_windows_and_the_toll_covariate() -> None:
    points = policy.INTERVENTIONS["points_licence"]
    assert points.post_months == 17
    assert points.second_break == pd.Timestamp("2007-12-01")
    speed = policy.INTERVENTIONS["speed_limit_90"]
    assert speed.post_months == 13 and speed.design == "did"
    series = policy.monthly_series()
    inside = policy.window(series, points.pre_start, points.post_end)
    assert len(inside) == 78 + 17
    # The toll covariate is the network's intensity, not its vehicle-km, which step with the
    # length of the network in service at the very month of the break.
    from dgt_stats import io_traffic

    toll = io_traffic.read_toll_traffic().set_index("period")
    june, july = toll.loc["2006-06-01"], toll.loc["2006-07-01"]
    assert july.network_km > june.network_km
    covariate = policy.exposure_covariate(inside.period, "toll")
    logged = np.log(inside.period.map(toll.imd).to_numpy(dtype=float))
    assert covariate.log_toll.to_numpy() == pytest.approx(logged - logged.mean())


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


def test_death_definition_ratio_finds_where_the_ratio_starts_to_vary() -> None:
    periods = pd.date_range("2000-01-01", "2003-12-01", freq="MS")
    one_day = pd.DataFrame({"period": periods, "deaths": 100.0})
    wobble = np.where(periods.year >= 2002, np.tile([0.1, -0.1], 24), np.tile([0.01, -0.01], 24))
    thirty = pd.DataFrame({"period": periods, "deaths": 100.0 * (1.15 + wobble)})
    out = policy.death_definition_ratio(thirty, one_day)
    assert list(out.year) == [2000, 2001, 2002, 2003]
    assert (out.regime_from == 2002).all()
    assert list(out.later_regime) == [False, False, True, True]
    assert out["mean"].to_numpy() == pytest.approx(1.15)
    steady = policy.death_definition_ratio(
        pd.DataFrame({"period": periods, "deaths": 115.0}), one_day
    )
    assert steady.regime_from.isna().all() and not steady.later_regime.any()


def test_placebo_distribution_ranks_a_real_break_first() -> None:
    it = policy.INTERVENTIONS["points_licence"]
    placebo = policy.placebo_fits(_synthetic_series(-0.2, "2006-07-01"), it)
    assert placebo.is_true.sum() == 1
    true = placebo[placebo.is_true].iloc[0]
    assert true["rank"] == 1 and placebo.n_fits.iloc[0] == len(placebo) == 39
    assert placebo.break_date.min() == it.pre_start + pd.DateOffset(months=it.placebo_pre)
    assert placebo[~placebo.is_true].break_date.max() < it.date - pd.DateOffset(
        months=it.post_months - 1
    )
    assert placebo[~placebo.is_true].level_change.abs().mean() < 0.1


def test_did_fit_recovers_a_treated_change_and_a_flat_control() -> None:
    rng = np.random.default_rng(5)
    periods = pd.date_range("2016-01-01", "2020-02-01", freq="MS")
    post = (periods >= pd.Timestamp("2019-02-01")).astype(float)
    season = 0.15 * np.sin(2 * np.pi * (periods.month - 1) / 12)
    rows = []
    for group, base, effect in ((policy.TREATED, 60, -0.25), (policy.CONTROL, 40, 0.0)):
        mu = np.exp(
            np.log(base) - 0.003 * np.arange(len(periods)) + season + np.log1p(effect) * post
        )
        rows.append(pd.DataFrame({"period": periods, "group": group, "deaths": rng.poisson(mu)}))
    panel = pd.concat(rows, ignore_index=True).astype({"deaths": float})
    it = policy.INTERVENTIONS["speed_limit_90"]
    fit = policy.did_fit(panel, it)
    assert fit.level_change == pytest.approx(-0.25, abs=0.08)
    control = fit.coefficients.set_index("term")
    assert abs(np.expm1(control.estimate["post"])) < 0.12
    assert control.low["post"] < 0 < control.high["post"]
    interleaved = panel.sort_values(["period", "group"]).reset_index(drop=True)
    again = policy.did_fit(interleaved, it)
    assert again.level_low == pytest.approx(fit.level_low)  # errors do not depend on row order
    assert again.level_high == pytest.approx(fit.level_high)
    placebo = policy.did_placebos(panel, it)
    assert list(placebo.break_date) == [*it.placebo_dates, it.date]
    assert placebo[placebo.is_true].level_change.iloc[0] == fit.level_change
    assert (placebo[~placebo.is_true].low < 0).all() and (placebo[~placebo.is_true].high > 0).all()


def test_points_licence_fits_assembles_the_published_tables() -> None:
    tables = policy.points_licence_fits()
    assert set(tables) == {
        "q8_points_fit",
        "q8_points_series",
        "q8_points_sensitivity",
        "q8_points_trend_choice",
        "q8_points_placebo",
        "q8_points_calendar_placebo",
        "q8_points_calibration",
        "q8_points_death_definitions",
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
        "fuel",
        "toll",
        "24h",
        "interurban",
        "urban",
        "long",
    }
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
    placebo = tables["q8_points_placebo"]
    assert placebo.is_true.sum() == 1 and int(placebo[placebo.is_true]["rank"].iloc[0]) >= 1


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
    assert row.deaths_before > row.deaths_after > 0
    assert row.twelve_month_ratio == pytest.approx(
        float(np.log(row.deaths_after / row.deaths_before))
    )
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
    assert true.log_ratio < 0 and true.z < 0  # fewer deaths than the pre-July fit projects
    assert int(true["rank"]) > 1  # other Julys undershot their own forecast by more
    # The rank is the proportional shortfall the page describes; the z score keeps its own.
    assert int(true["rank"]) == int((forecast.log_ratio < true.log_ratio).sum()) + 1
    assert int(true.rank_z) == int((forecast.z < true.z).sum()) + 1


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


def test_exposure_covariate_is_a_centred_log_series() -> None:
    it = policy.INTERVENTIONS["points_licence"]
    series = policy.window(policy.monthly_series(), it.pre_start, it.post_end)
    for name in policy.EXPOSURE_SERIES:
        column = policy.exposure_covariate(series.period, name)
        assert list(column.columns) == [f"log_{name}"]
        assert column.iloc[:, 0].mean() == pytest.approx(0.0, abs=1e-12)
        assert column.notna().all().all()
    with pytest.raises(ValueError):
        policy.exposure_covariate(series.period, "not a series")
    # Fuel consumption starts in 1996, so a window that reaches 1993 has to raise rather than fill.
    with pytest.raises(ValueError):
        policy.exposure_covariate(policy.monthly_series().period.head(24), "fuel")


def test_speed_limit_fits_keep_only_the_negative_result_tables() -> None:
    tables = policy.speed_limit_fits()
    assert set(tables) == {"q8_speed_placebo", "q8_speed_sensitivity"}
    sens = tables["q8_speed_sensitivity"]
    it = policy.INTERVENTIONS["speed_limit_90"]
    main = policy.did_fit(policy.monthly_by_road_group(), it)
    assert sens.variant.iloc[0] == "main"
    assert sens.level_change.iloc[0] == pytest.approx(main.level_change)
    assert sens.control_change.notna().all()
    placebo = tables["q8_speed_placebo"]
    assert placebo.is_true.sum() == 1
    assert sorted(pd.to_datetime(placebo.break_date)) == sorted([*it.placebo_dates, it.date])
    # The design fails: at least one placebo break moves the two groups apart on its own.
    fake = placebo[~placebo.is_true]
    assert ((fake.low > 0) | (fake.high < 0)).any()
