"""Counts against risk: the same deaths divided by what could have produced them.

Two questions share this module because they share the denominators.

* **2019 to 2024.** Did road risk in Spain rise or fall after the pandemic? The count of deaths
  says one thing; deaths per resident, per licence holder, per registered vehicle and per tonne of
  road fuel say others, and they do not agree on the sign. The table is built so the reader sees
  all five side by side, each indexed to 2019, with the uncertainty of the change.
* **1993 to 2024.** Which of the changes in the long series are structural and which are the
  pandemic? A segmented (joinpoint) log-linear trend is fitted to the deaths of 1993–2019, with the
  number and position of its turning points chosen by the data, and its last segment is projected
  through 2020–2024. Fitting the same model to deaths per tonne of road fuel asks whether 2020 was
  an exposure effect (less driving) or a change in risk.

Denominators, and what each is:

* ``residents``: INE resident population on 1 July (2002 onwards).
* ``licence_holders``: DGT driver census at the end of the year (2014 onwards).
* ``vehicle_fleet``: DGT's registered vehicle fleet from the yearbook rate table (1993 onwards).
* ``road_fuel_tonnes``: CORES automotive petrol plus diesel consumption, complete years only
  (1996 onwards). It is the only all-roads, all-vehicles measure of traffic with an annual (and
  monthly) series. It is a proxy for vehicle-kilometres, not a count of them: fleet fuel economy
  improves, electric kilometres burn no fuel, freight and cars are mixed, and fuel bought in Spain
  is not all burnt on Spanish roads. ``fuel_efficiency_sensitivity`` puts a number on the first
  two; ``km_crosscheck`` shows why DGT's two published kilometre estimates cannot replace it.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd
import statsmodels.api as sm

from dgt_stats import io_exposure, io_population, io_tables, io_traffic, rates

BASE_YEAR = 2019
FIRST_YEAR = 1993
PANDEMIC_YEARS = (2020, 2021)
# The joinpoint search: segments at least this many years long, at most this many turning points.
MIN_SEGMENT_YEARS = 4
MAX_BREAKS = 3
# The simplest model whose QBIC is within this many points of the best is chosen.
QBIC_TOLERANCE = 2.0

OUTCOMES = {
    "deaths_30d": "Deaths within 30 days",
    "hospitalised_30d": "Injured and hospitalised",
    "crashes": "Injury crashes",
}
# Denominator key -> (exposure column, label, rate per this many units of exposure).
DENOMINATORS: dict[str, tuple[str | None, str, float]] = {
    "count": (None, "Count, no denominator", 1.0),
    "residents": ("residents", "Per 100,000 residents", 1e5),
    "licence_holders": ("licence_holders", "Per 100,000 licence holders", 1e5),
    "vehicles": ("vehicle_fleet", "Per 100,000 registered vehicles", 1e5),
    "road_fuel": ("road_fuel_tonnes", "Per million tonnes of road fuel", 1e6),
}


# --------------------------------------------------------------------------- inputs


def annual_outcomes() -> pd.DataFrame:
    """Injury crashes, 30-day deaths and hospitalised injured per year, national, 1993 onwards."""
    annual = io_tables.read_table("series_annual")
    annual = annual[annual.zone == "all"]
    wide = annual.pivot_table(index="year", columns="metric", values="value", aggfunc="first")
    out = wide[list(OUTCOMES)].copy()
    out.index = out.index.astype(int)
    return out


def annual_exposure() -> pd.DataFrame:
    """The four denominators by year; NA where a series has not started.

    Fuel is summed over complete years only, so a partly published final year never enters.
    """
    annual = io_tables.read_table("series_annual")
    fleet = (
        annual[(annual.metric == "vehicle_fleet") & (annual.zone == "all")]
        .set_index("year")
        .value.rename("vehicle_fleet")
    )
    population = io_population.read_population()
    residents = (
        population[
            (population.province_code == io_population.NATIONAL_CODE)
            & population.all_ages
            & (population.sex == "total")
            & (population.reference == "1 July")
        ]
        .set_index("year")
        .population.rename("residents")
    )
    licences = io_exposure.read_exposure("conductores_por_edad")
    licence_holders = (
        licences[licences.sex == "total"].groupby("year").n_drivers.sum().rename("licence_holders")
    )
    fuel = io_traffic.read_cores_fuel().groupby("year").road_fuel_tonnes.agg(["sum", "count"])
    road_fuel = fuel.loc[fuel["count"] == 12, "sum"].rename("road_fuel_tonnes")
    out = pd.concat([residents, licence_holders, fleet, road_fuel], axis=1)
    out.index = out.index.astype(int)
    return out.sort_index().astype(float)


def annual_panel() -> pd.DataFrame:
    """Outcomes and denominators on one row per year, 1993 to the last year with deaths."""
    outcomes = annual_outcomes()
    exposure = annual_exposure()
    out = outcomes.join(exposure, how="left")
    out = out[out.index >= FIRST_YEAR]
    out.index.name = "year"
    return out.reset_index()


# --------------------------------------------------------------------------- 2019 to 2024


def risk_index(base_year: int = BASE_YEAR) -> pd.DataFrame:
    """Each outcome under each denominator, as a rate and as a ratio to the base year.

    ``ratio_to_base`` is (rate this year) / (rate in ``base_year``), with a log-normal interval
    that treats both counts as Poisson and the denominators as known. For the count itself the
    "denominator" is 1 and the ratio is the change in the count.
    """
    panel = annual_panel().set_index("year")
    last_year = int(panel.index.max())
    years = range(base_year, last_year + 1)
    records = []
    for outcome, outcome_label in OUTCOMES.items():
        for key, (column, label, per) in DENOMINATORS.items():
            base_count = float(panel.loc[base_year, outcome])
            base_exposure = 1.0 if column is None else float(panel.loc[base_year, column])
            for year in years:
                count = float(panel.loc[year, outcome])
                exposure = 1.0 if column is None else float(panel.loc[year, column])
                if column is None:
                    value, low, high = count, *rates.poisson_interval(count)
                else:
                    value, low, high = rates.rate(count, exposure, per=per)
                ratio, ratio_low, ratio_high = rates.rate_ratio(
                    count, exposure, base_count, base_exposure
                )
                records.append(
                    {
                        "outcome": outcome,
                        "outcome_label": outcome_label,
                        "denominator": key,
                        "denominator_label": label,
                        "year": year,
                        "count": count,
                        "exposure": exposure if column is not None else np.nan,
                        "rate": value,
                        "rate_low": low,
                        "rate_high": high,
                        "ratio_to_base": ratio,
                        "ratio_low": ratio_low,
                        "ratio_high": ratio_high,
                        "index": 100 * ratio,
                    }
                )
    return pd.DataFrame.from_records(records)


EFFICIENCY_GAINS = (0.0, 0.01, 0.02)


def fuel_efficiency_sensitivity(base_year: int = BASE_YEAR) -> pd.DataFrame:
    """How the per-fuel change since ``base_year`` moves if kilometres grew faster than fuel.

    A fleet that burns ``g`` less fuel per kilometre each year drives ``(1 + g)`` more kilometres
    per tonne each year, and an electric kilometre burns none. Dividing by fuel grossed up by
    ``(1 + g) ** (year - base_year)`` gives the ratio to the base year under that assumption.
    Spain's car fleet has improved by roughly one per cent a year; two per cent is a generous upper
    case that also absorbs the growth in electric and plug-in kilometres to 2024.
    """
    panel = annual_panel().set_index("year")
    last_year = int(panel.index.max())
    records = []
    for outcome in ("deaths_30d", "hospitalised_30d"):
        for gain in EFFICIENCY_GAINS:
            base_km = float(panel.loc[base_year, "road_fuel_tonnes"])
            for year in range(base_year, last_year + 1):
                km = float(panel.loc[year, "road_fuel_tonnes"]) * (1 + gain) ** (year - base_year)
                ratio, low, high = rates.rate_ratio(
                    float(panel.loc[year, outcome]),
                    km,
                    float(panel.loc[base_year, outcome]),
                    base_km,
                )
                records.append(
                    {
                        "outcome": outcome,
                        "outcome_label": OUTCOMES[outcome],
                        "annual_efficiency_gain": gain,
                        "year": year,
                        "ratio_to_base": ratio,
                        "ratio_low": low,
                        "ratio_high": high,
                    }
                )
    return pd.DataFrame.from_records(records)


def km_crosscheck() -> pd.DataFrame:
    """DGT's two kilometre estimates against road fuel: why they cannot be chained into a trend.

    DGT published vehicle-kilometres for 2022 (from ITV odometer readings) and for 2024 (an
    annualised estimate built differently). Their ratio is compared with the ratio of road fuel
    over the same two years; if the estimates measured the same thing the ratios would be close.
    """
    km_2022 = io_exposure.read_exposure("km_medios_2022")
    km_2024 = io_exposure.read_exposure("km_medios_tipo_2024")
    panel = annual_panel().set_index("year")
    car_2022 = float(km_2022.loc[km_2022.vehicle_type == "Turismo", "vehicle_km"].sum())
    car_2024 = float(km_2024.loc[km_2024.vehicle_group == "car", "total_km"].sum())
    rows = [
        ("All vehicle types", float(km_2022.vehicle_km.sum()), float(km_2024.total_km.sum())),
        ("Cars", car_2022, car_2024),
    ]
    fuel_ratio = float(panel.loc[2024, "road_fuel_tonnes"] / panel.loc[2022, "road_fuel_tonnes"])
    return pd.DataFrame(
        [
            {
                "measure": label,
                "billion_km_2022": first / 1e9,
                "billion_km_2024": second / 1e9,
                "km_ratio_2024_to_2022": second / first,
                "fuel_ratio_2024_to_2022": fuel_ratio,
            }
            for label, first, second in rows
        ]
    )


# --------------------------------------------------------------------------- 1993 to 2024


@dataclass
class Joinpoint:
    """A segmented log-linear Poisson trend with quasi-likelihood (overdispersed) errors."""

    years: np.ndarray
    breaks: tuple[int, ...]
    result: sm.genmod.generalized_linear_model.GLMResultsWrapper

    @property
    def dispersion(self) -> float:
        return float(self.result.scale)


def _design(years: np.ndarray, first: int, breaks: tuple[int, ...]) -> np.ndarray:
    t = years.astype(float)
    columns = [np.ones_like(t), t - first]
    columns += [np.clip(t - b, 0, None) for b in breaks]
    return np.column_stack(columns)


def _fit(years: np.ndarray, counts: np.ndarray, offset: np.ndarray | None, breaks) -> Joinpoint:
    design = _design(years, int(years[0]), tuple(breaks))
    model = sm.GLM(counts, design, family=sm.families.Poisson(), offset=offset)
    return Joinpoint(years, tuple(breaks), model.fit(scale="X2"))


def _candidate_breaks(years: np.ndarray) -> list[int]:
    first, last = int(years[0]), int(years[-1])
    span = MIN_SEGMENT_YEARS - 1
    return [int(y) for y in years if y - first >= span and last - y >= span]


def joinpoint_search(
    years: np.ndarray, counts: np.ndarray, offset: np.ndarray | None = None
) -> tuple[Joinpoint, pd.DataFrame]:
    """Best fit for 0 to ``MAX_BREAKS`` turning points, and the chosen model.

    For each number of breaks every admissible placement is fitted and the one with the smallest
    deviance kept. The number of breaks is chosen by QBIC (BIC on the Poisson likelihood divided
    by the dispersion of the largest model, each break costing two parameters: its position and
    its slope change), taking the simplest model within ``QBIC_TOLERANCE`` of the minimum.
    """
    candidates = _candidate_breaks(years)
    best: dict[int, Joinpoint] = {}
    for k in range(MAX_BREAKS + 1):
        for breaks in itertools.combinations(candidates, k):
            gaps = np.diff([int(years[0]), *breaks, int(years[-1])])
            if (gaps < MIN_SEGMENT_YEARS - 1).any():
                continue
            fit = _fit(years, counts, offset, breaks)
            if k not in best or fit.result.deviance < best[k].result.deviance:
                best[k] = fit
    dispersion = best[max(best)].dispersion
    n = len(years)
    records = []
    for k, fit in sorted(best.items()):
        loglike = fit.result.family.loglike(counts, fit.result.mu, scale=1.0)
        records.append(
            {
                "n_breaks": k,
                "breaks": " ".join(str(b) for b in fit.breaks),
                "deviance": float(fit.result.deviance),
                "qbic": float(-2 * loglike / dispersion + np.log(n) * (2 + 2 * k)),
            }
        )
    table = pd.DataFrame.from_records(records)
    admissible = table[table.qbic <= table.qbic.min() + QBIC_TOLERANCE]
    chosen = int(admissible.n_breaks.min())
    table["chosen"] = table.n_breaks == chosen
    return best[chosen], table


def segment_changes(fit: Joinpoint) -> pd.DataFrame:
    """Annual percentage change in each segment, with a 95 % interval from the scaled covariance."""
    params = fit.result.params
    cov = fit.result.cov_params()
    edges = [int(fit.years[0]), *fit.breaks, int(fit.years[-1])]
    records = []
    for index in range(len(edges) - 1):
        weights = np.zeros(len(params))
        weights[1] = 1.0
        weights[2 : 2 + index] = 1.0
        slope = float(weights @ params)
        se = float(np.sqrt(weights @ cov @ weights))
        records.append(
            {
                "start": edges[index],
                "end": edges[index + 1],
                "annual_change": np.exp(slope) - 1,
                "low": np.exp(slope - 1.96 * se) - 1,
                "high": np.exp(slope + 1.96 * se) - 1,
            }
        )
    return pd.DataFrame.from_records(records)


def project(fit: Joinpoint, years: np.ndarray, offset: np.ndarray | None = None) -> pd.DataFrame:
    """Expected counts on the fitted trend for ``years``, with a 95 % prediction interval.

    The interval combines the uncertainty of the fitted line (delta method on the linear predictor)
    with overdispersed Poisson noise around it: ``var = dispersion × mu + mu² × var(eta)``.
    """
    design = _design(np.asarray(years), int(fit.years[0]), fit.breaks)
    eta = design @ fit.result.params
    if offset is not None:
        eta = eta + offset
    var_eta = np.einsum("ij,jk,ik->i", design, fit.result.cov_params(), design)
    mu = np.exp(eta)
    sd = np.sqrt(fit.dispersion * mu + mu**2 * var_eta)
    return pd.DataFrame(
        {"year": years, "expected": mu, "low": mu - 1.96 * sd, "high": mu + 1.96 * sd}
    )


# The three views of the long series: the count, and the count over two denominators.
LONG_RUN_MEASURES: dict[str, tuple[str | None, str, int]] = {
    "count": (None, "Deaths", FIRST_YEAR),
    "vehicles": ("vehicle_fleet", "Deaths per registered vehicle", FIRST_YEAR),
    "road_fuel": ("road_fuel_tonnes", "Deaths per tonne of road fuel", 1996),
}


@cache
def _long_run_fits(last_pre_year: int = BASE_YEAR):
    panel = annual_panel().set_index("year")
    fits = {}
    for key, (column, label, start) in LONG_RUN_MEASURES.items():
        window = panel.loc[start:last_pre_year]
        years = window.index.to_numpy()
        counts = window.deaths_30d.to_numpy(dtype=float)
        offset = None if column is None else np.log(window[column].to_numpy(dtype=float))
        fit, table = joinpoint_search(years, counts, offset)
        fits[key] = (fit, table, label, column, start)
    return panel, fits


def long_run_segments() -> pd.DataFrame:
    """The chosen turning points and each segment's annual change, for the three measures."""
    _, fits = _long_run_fits()
    frames = []
    for key, (fit, _, label, _, _) in fits.items():
        segments = segment_changes(fit)
        segments.insert(0, "measure", key)
        segments.insert(1, "measure_label", label)
        segments["dispersion"] = fit.dispersion
        frames.append(segments)
    return pd.concat(frames, ignore_index=True)


def long_run_model_choice() -> pd.DataFrame:
    """QBIC for 0 to 3 turning points, per measure, and which model was chosen."""
    _, fits = _long_run_fits()
    frames = []
    for key, (_, table, label, _, _) in fits.items():
        frames.append(table.assign(measure=key, measure_label=label))
    columns = ["measure", "measure_label", "n_breaks", "breaks", "deviance", "qbic", "chosen"]
    return pd.concat(frames, ignore_index=True)[columns]


def long_run_series() -> pd.DataFrame:
    """Observed deaths against the pre-pandemic trend, every year, for the three measures.

    ``expected`` is the fitted trend up to 2019 and its projection afterwards, in deaths: for the
    per-vehicle and per-fuel measures the projection is multiplied by the actual fleet or fuel of
    each year, so all three are on one scale and ``observed / expected`` reads the same way. For
    2020 onward the interval is a prediction interval.
    """
    panel, fits = _long_run_fits()
    last_year = int(panel.index.max())
    frames = []
    for key, (fit, _, label, column, start) in fits.items():
        window = panel.loc[start:last_year]
        years = window.index.to_numpy()
        offset = None if column is None else np.log(window[column].to_numpy(dtype=float))
        projected = project(fit, years, offset)
        projected["observed"] = window.deaths_30d.to_numpy(dtype=float)
        projected["ratio"] = projected.observed / projected.expected
        projected["outside_interval"] = (projected.observed < projected.low) | (
            projected.observed > projected.high
        )
        projected["period"] = np.where(years <= BASE_YEAR, "fitted", "projected")
        projected.insert(0, "measure", key)
        projected.insert(1, "measure_label", label)
        if column is not None:
            per = DENOMINATORS["vehicles" if key == "vehicles" else "road_fuel"][2]
            exposure = window[column].to_numpy(dtype=float)
            projected["observed_rate"] = projected.observed / exposure * per
            projected["expected_rate"] = projected.expected / exposure * per
        else:
            projected["observed_rate"] = projected.observed
            projected["expected_rate"] = projected.expected
        frames.append(projected)
    return pd.concat(frames, ignore_index=True)


def long_run_efficiency_sensitivity() -> pd.DataFrame:
    """The 2022–2024 per-fuel excess over trend if kilometres grew faster than fuel after 2019.

    The pre-2020 per-fuel trend already carries the fuel-economy gains of 1996–2019, so projecting
    it assumes they continued at the same pace. This asks what an *extra* ``g`` a year of
    kilometres per tonne from 2020 (faster electrification, a lighter fleet) would do.
    """
    series = long_run_series()
    fuel = series[(series.measure == "road_fuel") & (series.period == "projected")]
    records = []
    for gain in EFFICIENCY_GAINS:
        for row in fuel.itertuples(index=False):
            factor = (1 + gain) ** (row.year - BASE_YEAR)
            records.append(
                {
                    "extra_annual_efficiency_gain": gain,
                    "year": row.year,
                    "ratio": row.ratio / factor,
                    "ratio_low": row.observed / (row.high * factor),
                    "ratio_high": row.observed / (row.low * factor),
                }
            )
    return pd.DataFrame.from_records(records)
