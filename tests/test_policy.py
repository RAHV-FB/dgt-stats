import numpy as np
import pandas as pd
import pytest

from dgt_stats import io_tables, policy, summaries

pytestmark = pytest.mark.skipif(
    not (io_tables.interim_path("series_monthly").exists() and policy.PROCESSED_CRASHES.exists()),
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
    # The panel reconciles to the microdata for the road-type codes methodology section 7 names.
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


def test_intervention_windows_and_fleet_offset() -> None:
    points = policy.INTERVENTIONS["points_licence"]
    assert points.post_months == 17
    assert points.second_break == pd.Timestamp("2007-12-01")
    speed = policy.INTERVENTIONS["speed_limit_90"]
    assert speed.post_months == 13 and speed.design == "did"
    series = policy.monthly_series()
    inside = policy.window(series, points.pre_start, points.post_end)
    assert len(inside) == 78 + 17
    fleet = policy.fleet_offset(inside.period)
    assert fleet.is_monotonic_increasing
    july_2006 = fleet[inside.period == "2006-07-01"].iloc[0]
    annual = io_tables.read_table("series_annual")
    published = annual[
        (annual.metric == "vehicle_fleet") & (annual.zone == "all") & (annual.year == 2006)
    ]
    assert july_2006 == pytest.approx(float(published.value.iloc[0]))


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
        "fleet_offset",
    }
    long_row = sens[sens.variant == "long"].iloc[0]
    assert long_row.n_months > sens[sens.variant == "main"].iloc[0].n_months
    assert np.isfinite(long_row.second_break_change)
    assert sens[sens.variant != "long"].second_break_change.isna().all()
    # The main specification is the piecewise one and it gives a smaller drop than the straight
    # line: that difference is the finding the page reports, so it is asserted here.
    main = sens[sens.variant == "main"].iloc[0]
    linear = sens[sens.variant == "linear_trend"].iloc[0]
    assert main.level_change < 0 and linear.level_change < main.level_change
    trend = tables["q8_points_trend_choice"]
    assert trend.chosen.sum() == 1
    straight = trend[trend.label == "one linear trend"].iloc[0]
    assert straight.delta_aic > 2  # the pre-period rejects one straight line
    assert trend[trend.chosen].delta_aic.iloc[0] == 0
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


def test_flexible_pre_trend_is_chosen_on_the_pre_period_only() -> None:
    it = policy.INTERVENTIONS["points_licence"]
    series = policy.monthly_series()
    knot, table = policy.choose_trend_knot(series, it)
    assert knot is not None and it.pre_start < knot < it.date
    assert table.aic.is_monotonic_increasing and table.delta_aic.iloc[0] == 0
    assert (table.label == "one linear trend").sum() == 1
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
