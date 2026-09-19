import numpy as np
import pandas as pd
import pytest

from dgt_stats import io_tables, policy

pytestmark = pytest.mark.skipif(
    not io_tables.interim_path("series_monthly").exists(),
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


def test_road_group_panel_covers_every_month_and_sums_to_the_microdata() -> None:
    panel = policy.monthly_by_road_group()
    assert set(panel.group) == {policy.TREATED, policy.CONTROL}
    assert panel.groupby("group").size().eq(9 * 12).all()
    treated = panel[panel.group == policy.TREATED].set_index("period").deaths
    assert treated.loc["2016-01-01"] == 55 and treated.loc["2016-07-01"] == 93
    control = panel[panel.group == policy.CONTROL].set_index("period").deaths
    assert control.loc["2016-01-01"] == 28 + 8
    raw = pd.DataFrame(
        {
            "ANYO": [2016, 2016, 2016, 2016],
            "MES": [1, 1, 2, 3],
            "road_group": ["conventional", "urban_street", "motorway", pd.NA],
            "TOTAL_MU30DF": [2, 5, 1, 3],
        }
    )
    small = policy.monthly_by_road_group(raw)
    assert len(small) == 24 and small.deaths.sum() == 3
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
