import numpy as np
import pytest

from dgt_stats import io_exposure, io_tables, risk_trends
from dgt_stats.paths import CORES_FUEL_PATH, DGT_PROCESSED_CRASHES


def test_joinpoint_search_recovers_known_turning_points() -> None:
    # A series that falls 2 % a year, then 12 % a year from 2003, then is flat from 2013: the
    # search has to find both turning points, and not invent a third.
    rng = np.random.default_rng(7)
    years = np.arange(1993, 2020)
    log_mu = np.log(6000) - 0.02 * (years - 1993)
    log_mu -= 0.10 * np.clip(years - 2003, 0, None)
    log_mu += 0.12 * np.clip(years - 2013, 0, None)
    counts = rng.poisson(np.exp(log_mu)).astype(float)
    fit, table = risk_trends.joinpoint_search(years, counts)
    assert len(fit.breaks) == 2
    assert abs(fit.breaks[0] - 2003) <= 1 and abs(fit.breaks[1] - 2013) <= 1
    assert int(table[table.chosen].n_breaks.iloc[0]) == 2
    segments = risk_trends.segment_changes(fit)
    assert segments.annual_change.iloc[1] == pytest.approx(np.exp(-0.12) - 1, abs=0.02)
    assert segments.low.iloc[1] < segments.annual_change.iloc[1] < segments.high.iloc[1]


def test_projection_interval_widens_away_from_the_fitted_years() -> None:
    rng = np.random.default_rng(3)
    years = np.arange(2000, 2020)
    counts = rng.poisson(1000 * np.exp(-0.03 * (years - 2000))).astype(float)
    fit, _ = risk_trends.joinpoint_search(years, counts)
    out = risk_trends.project(fit, np.arange(2020, 2030))
    # Relative to the expected count, the interval grows as the projection runs on, because the
    # uncertainty of the fitted slope compounds with distance.
    relative = ((out.high - out.low) / out.expected).to_numpy()
    assert (np.diff(relative) > 0).all()
    assert (out.low < out.expected).all() and (out.expected < out.high).all()


pytestmark_data = pytest.mark.skipif(
    not (
        io_tables.staging_path("series_annual").exists()
        and io_exposure.staging_path("conductores_por_edad").exists()
        and CORES_FUEL_PATH.exists()
    ),
    reason="run `python scripts/ingest.py all` first",
)


@pytestmark_data
def test_annual_panel_has_every_denominator_where_its_source_runs() -> None:
    panel = risk_trends.annual_panel().set_index("year")
    assert panel.index.min() == 1993
    assert panel.loc[1993:, "vehicle_fleet"].notna().all()
    assert (
        panel.loc[2002:, "residents"].notna().all() and panel.loc[:2001, "residents"].isna().all()
    )
    assert panel.loc[2014:, "licence_holders"].notna().all()
    assert panel.loc[1996:, "road_fuel_tonnes"].notna().all()
    # Plausibility of the magnitudes, so a unit slip cannot pass silently.
    assert 45e6 < panel.loc[2024, "residents"] < 52e6
    assert 25e6 < panel.loc[2024, "licence_holders"] < 30e6
    assert 20e6 < panel.loc[2024, "road_fuel_tonnes"] < 40e6
    # The driver and occupant numerators run every year, and nest: drivers are occupants, and
    # occupants of motor vehicles are a part of all casualties.
    for outcome in risk_trends.ROAD_USER_OUTCOMES:
        drivers = panel[f"drivers_{outcome}"]
        occupants = panel[f"occupants_{outcome}"]
        assert drivers.notna().all() and occupants.notna().all()
        assert (drivers <= occupants).all() and (occupants < panel[outcome]).all()


@pytestmark_data
def test_licence_holders_and_the_fleet_divide_only_the_casualties_they_can_contain() -> None:
    index = risk_trends.risk_index()
    pairs = index.drop_duplicates(["outcome", "denominator"]).set_index(["outcome", "denominator"])
    for outcome in ("deaths_30d", "hospitalised_30d"):
        assert pairs.loc[(outcome, "licence_holders"), "numerator"] == f"drivers_{outcome}"
        assert pairs.loc[(outcome, "vehicles"), "numerator"] == f"occupants_{outcome}"
        for key in ("count", "residents", "road_fuel"):
            assert pairs.loc[(outcome, key), "numerator"] == outcome
    # Injury crashes are not split by vehicle type, so they get neither denominator.
    crashes = set(index[index.outcome == "crashes"].denominator)
    assert crashes == {"count", "residents", "road_fuel"}
    # Every numerator carries its own year-to-year dispersion.
    dispersion = risk_trends.year_to_year_dispersion()
    assert set(index.numerator) <= set(dispersion.outcome)


@pytestmark_data
def test_risk_index_is_relative_to_the_base_year_under_every_denominator() -> None:
    index = risk_trends.risk_index()
    base = index[index.year == risk_trends.BASE_YEAR]
    assert (base.ratio_to_base == 1.0).all() and (base["index"] == 100).all()
    assert set(index.denominator) == set(risk_trends.DENOMINATORS)
    last = index[index.year == index.year.max()].set_index(["outcome", "denominator"])
    # The count's ratio is the ratio of counts; the others divide by the exposure ratio.
    count = last.loc[("deaths_30d", "count")]
    fuel = last.loc[("deaths_30d", "road_fuel")]
    panel = risk_trends.annual_panel().set_index("year")
    final, base_year = index.year.max(), risk_trends.BASE_YEAR

    def ratio(column: str) -> float:
        return panel.loc[final, column] / panel.loc[base_year, column]

    assert fuel.ratio_to_base == pytest.approx(count.ratio_to_base / ratio("road_fuel_tonnes"))
    licence = last.loc[("deaths_30d", "licence_holders")]
    assert licence.ratio_to_base == pytest.approx(
        ratio("drivers_deaths_30d") / ratio("licence_holders")
    )
    assert (
        (index.ratio_low <= index.ratio_to_base) & (index.ratio_to_base <= index.ratio_high)
    ).all()


@pytestmark_data
def test_long_run_measures_agree_on_the_history_and_the_pandemic() -> None:
    segments = risk_trends.long_run_segments()
    for _, group in segments.groupby("measure"):
        # Each measure finds the steep decade: the fastest-falling segment is the middle one.
        assert len(group) == 3
        assert group.annual_change.idxmin() == group.index[1]
        assert group.annual_change.iloc[1] < -0.08
    series = risk_trends.long_run_series().set_index(["measure", "year"])
    # As a count 2020 is far below trend; per tonne of fuel it is within the interval.
    assert bool(series.loc[("count", 2020), "outside_interval"])
    assert series.loc[("count", 2020), "ratio"] < 0.85
    assert not bool(series.loc[("road_fuel", 2020), "outside_interval"])
    # The per-vehicle measure divides occupant deaths, not every death.
    occupants = series.xs("occupants_per_vehicle", level="measure")
    panel = risk_trends.annual_panel().set_index("year")
    assert (occupants.numerator == "occupants_deaths_30d").all()
    assert occupants.observed.to_numpy() == pytest.approx(
        panel.loc[occupants.index, "occupants_deaths_30d"].to_numpy()
    )


@pytestmark_data
def test_the_fuel_drift_grid_is_labelled_hypothetical_and_zero_reproduces_the_index() -> None:
    grid = risk_trends.fuel_efficiency_sensitivity()
    assert tuple(sorted(grid.hypothetical_annual_gain.unique())) == risk_trends.HYPOTHETICAL_GAINS
    at_zero = grid[(grid.hypothetical_annual_gain == 0) & (grid.outcome == "deaths_30d")]
    index = risk_trends.risk_index()
    fuel = index[(index.outcome == "deaths_30d") & (index.denominator == "road_fuel")]
    assert at_zero.ratio_to_base.to_numpy() == pytest.approx(fuel.ratio_to_base.to_numpy())
    extra = risk_trends.long_run_efficiency_sensitivity()
    assert "hypothetical_extra_annual_gain" in extra.columns


@pytest.mark.skipif(
    not (DGT_PROCESSED_CRASHES.exists() and io_tables.staging_path("series_monthly").exists()),
    reason="run `python scripts/ingest.py` and `python scripts/build_tables.py` first",
)
def test_network_coverage_reproduces_the_series_and_measures_the_gap() -> None:
    coverage = risk_trends.interurban_network_coverage().set_index("year")
    # The microdata's interurban deaths are the yearbook's, year by year.
    assert (coverage.deaths_microdata == coverage.deaths_series).all()
    parts = coverage.deaths_counted_network + coverage.deaths_outside
    assert (parts == coverage.deaths_microdata).all()
    assert (
        coverage.deaths_municipal + coverage.deaths_other_owner <= coverage.deaths_outside
    ).all()
    # Roads outside the networks table 1.2.14 counts carry a real but minority share.
    assert ((coverage.outside_share > 0.02) & (coverage.outside_share < 0.25)).all()
    # The per-fuel arm of the kilometre check is labelled as a diagnostic, not a rate.
    assert "diagnostic" in risk_trends.KM_MEASURES["per_fuel"][1]


def test_a_refitted_segment_recovers_its_slope_and_widens_with_t() -> None:
    rng = np.random.default_rng(11)
    years = np.arange(2011, 2020)
    counts = rng.poisson(1800 * np.exp(-0.02 * (years - 2011))).astype(float)
    trend = risk_trends.fit_segment(years, counts, None)
    change, low, high = trend.slope()
    assert low < np.exp(-0.02) - 1 < high and low < change < high
    assert trend.df == len(years) - 2 and trend.dispersion >= 1
    with_t = risk_trends.project_segment(trend, np.arange(2020, 2025))
    with_z = risk_trends.project_segment(
        trend, np.arange(2020, 2025), quantile=risk_trends.NORMAL_QUANTILE
    )
    # Same trend, wider interval: the t quantile for seven degrees of freedom exceeds the normal.
    assert with_t.expected.to_numpy() == pytest.approx(with_z.expected.to_numpy())
    ratio = (with_t.high - with_t.expected) / (with_z.high - with_z.expected)
    assert ratio.to_numpy() == pytest.approx(
        risk_trends.t_quantile(trend.df) / risk_trends.NORMAL_QUANTILE
    )


@pytestmark_data
def test_ordinary_variation_uses_t_with_the_scatter_fits_degrees_of_freedom() -> None:
    scatter = risk_trends.year_to_year_dispersion().set_index("outcome")
    years = risk_trends.SCATTER_YEARS[1] - risk_trends.SCATTER_YEARS[0] + 1
    assert (scatter.df_resid == years - 2).all()
    assert (scatter.dispersion_low < scatter.pearson_dispersion).all()
    assert (scatter.pearson_dispersion < scatter.dispersion_high).all()
    assert (scatter.dispersion == scatter.pearson_dispersion.clip(lower=1)).all()
    index = risk_trends.risk_index()
    row = index[(index.year == index.year.max()) & (index.denominator == "count")].iloc[0]
    base = index[
        (index.year == risk_trends.BASE_YEAR)
        & (index.denominator == "count")
        & (index.outcome == row.outcome)
    ].iloc[0]
    phi = scatter.loc[row.numerator, "dispersion"]
    spread = risk_trends.t_quantile(years - 2) * np.sqrt(
        phi * (1 / row["count"] + 1 / base["count"])
    )
    assert np.log(row.ratio_high_yty / row.ratio_to_base) == pytest.approx(spread)


@pytestmark_data
def test_both_splits_of_deaths_per_tonne_multiply_to_it() -> None:
    split = risk_trends.frequency_severity()
    assert (split.frequency_index * split.severity_index / 100).to_numpy() == pytest.approx(
        split.deaths_per_fuel_index.to_numpy()
    )
    assert (
        split.hospitalised_per_fuel_index * split.deaths_per_hospitalised_index / 100
    ).to_numpy() == pytest.approx(split.deaths_per_fuel_index.to_numpy())


@pytestmark_data
def test_the_projection_continues_the_last_segment_refitted_on_its_own_years() -> None:
    series = risk_trends.long_run_series()
    segments = risk_trends.long_run_segments()
    panel = risk_trends.annual_panel().set_index("year")
    for measure, block in series.groupby("measure"):
        projected = block[block.period == "projected"]
        start = int(segments[segments.measure == measure].start.iloc[-1])
        assert (projected.projection_start == start).all()
        column, _, _, numerator, _ = risk_trends.LONG_RUN_MEASURES[measure]
        window = panel.loc[start : risk_trends.BASE_YEAR]
        offset = None if column is None else np.log(window[column].to_numpy(dtype=float))
        trend = risk_trends.fit_segment(
            window.index.to_numpy(), window[numerator].to_numpy(dtype=float), offset
        )
        assert projected.projection_dispersion.iloc[0] == pytest.approx(trend.dispersion)
        # A year lies outside its range exactly when its ratio leaves range_low..range_high.
        outside = (projected.ratio < projected.range_low) | (projected.ratio > projected.range_high)
        assert (outside == projected.outside_interval).all()
    sensitivity = risk_trends.long_run_projection_sensitivity()
    main = sensitivity[sensitivity.variant == "main"].set_index(["measure", "year"])
    shown = series[series.period == "projected"].set_index(["measure", "year"])
    assert main.ratio.to_numpy() == pytest.approx(shown.loc[main.index].ratio.to_numpy())
    # Occupant deaths are not published within 24 hours, so that variant has no per-vehicle rows.
    within_day = sensitivity[sensitivity.variant == "deaths_24h"]
    assert set(within_day.measure) == {"count", "road_fuel"}


@pytest.mark.skipif(
    not io_exposure.staging_path("km_medios_serie_2024").exists(),
    reason="run `python scripts/ingest.py exposure` first",
)
@pytestmark_data
def test_dgts_kilometre_series_repeats_the_first_release_and_runs_on() -> None:
    series = io_exposure.read_exposure("km_medios_serie_2024")
    assert sorted(series.year.unique()) == [2022, 2023, 2024]
    assert series.vehicle_group.notna().all()
    check = risk_trends.km_crosscheck().set_index("year")
    # The car mean of the first year is the 2022 release's fleet-weighted mean, to the kilometre.
    assert check.loc[2022, "car_mean_km"] == 13_073
    assert check.billion_km.isna().tolist() == [False, True, False]
    assert check.loc[2022, "billion_km_ratio"] == 1.0
