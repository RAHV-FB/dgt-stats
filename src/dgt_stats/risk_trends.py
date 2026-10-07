"""Counts against exposure: the same counts divided by what they can be divided by.

Two questions share this module because they share the denominators.

* **2019 to 2024.** Did the counts change after the pandemic once they are divided by something?
  Deaths, hospitalised injured and injury crashes are set against residents and road fuel; driver
  casualties against licence holders; motor-vehicle occupant casualties against the registered
  fleet. Each is indexed to 2019, with the uncertainty of the change.
* **1993 to 2024.** Which of the changes in the long series are structural and which are the
  pandemic? A segmented (joinpoint) log-linear trend is fitted to the deaths of 1993–2019, with the
  number and position of its turning points chosen by the data, and its last segment is projected
  through 2020–2024: for the count, for motor-vehicle occupant deaths over the registered fleet,
  and for deaths over road fuel.

Denominators, what each is, and the numerator each is paired with:

* ``residents``: INE resident population on 1 July (2002 onwards), against every casualty. A rate
  per resident is a population rate, not a risk of travelling.
* ``licence_holders``: DGT driver census at the end of the year (2014 onwards), every permit class,
  against the *drivers* of motorcycles, cars, vans, trucks and buses (``MOTOR_VEHICLE_TYPES``) in
  the yearbook's driver series. Pedestrians, passengers, cyclists and riders of personal mobility
  vehicles need no licence for the trip in which they are hurt, so they are left out of it.
* ``vehicle_fleet``: DGT's registered vehicle fleet from the yearbook rate table (1993 onwards),
  used or not, against the *occupants* (drivers and passengers) of the same vehicle types.
  Pedestrians and cyclists are in no registered vehicle.
* ``road_fuel_tonnes``: CORES automotive petrol plus diesel sold, complete years only (1996
  onwards), against every casualty. It covers all roads and all vehicles and is the only annual
  traffic series that does; it is a proxy for vehicle-kilometres, not a count of them: fuel per
  kilometre changes, electric kilometres burn no fuel, freight and cars are mixed, and fuel bought
  in Spain is not all burnt on Spanish roads. No series in the repository measures how kilometres
  per tonne moved on all roads; ``fuel_efficiency_sensitivity`` shows only how far the per-fuel
  change moves under hypothetical drifts, and ``km_crosscheck`` shows why DGT's two published
  kilometre estimates cannot replace fuel as a series.

Injury crashes are not split by vehicle type in the yearbook series, so they are set against
residents and road fuel only.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd
import statsmodels.api as sm

from dgt_stats import io_exposure, io_population, io_tables, io_traffic, rates
from dgt_stats.paths import DGT_PROCESSED_CRASHES

BASE_YEAR = 2019
FIRST_YEAR = 1993
PANDEMIC_YEARS = (2020, 2021)
# The joinpoint search: segments at least this many years long, at most this many turning points.
MIN_SEGMENT_YEARS = 4
MAX_BREAKS = 3
# The simplest model whose QBIC is within this many points of the best is chosen.
QBIC_TOLERANCE = 2.0
# The plateau after the last turning point the long-run search finds (about 2013) and before the
# pandemic: the stretch whose scatter around its own trend measures an ordinary year.
SCATTER_YEARS = (2013, 2019)

OUTCOMES = {
    "deaths_30d": "Deaths within 30 days",
    "hospitalised_30d": "Injured and hospitalised",
    "crashes": "Injury crashes",
}
# The vehicle types of the yearbook's driver and occupant series whose drivers need a licence and
# which are in the registered fleet. Bicycles and personal mobility vehicles need neither. "Otros"
# is left out because it held personal mobility vehicles until they got their own column in 2020
# (its 2019 count of drivers slightly injured is nearly three times 2018's), and mopeds because the
# repository does not establish whether the fleet in the rate table counts them.
MOTOR_VEHICLE_TYPES = (
    "Motocicletas",
    "Turismos",
    "Camiones hasta 3.500 kg y furgonetas",
    "Camiones más de 3.500 kg",
    "Autobuses",
)
MOTOR_VEHICLES = "motorcycles, cars, vans, trucks and buses"
# Numerator group -> the yearbook road-user population it is summed from.
ROAD_USER_GROUPS = {"drivers": "drivers", "occupants": "drivers_and_passengers"}
# The outcomes the road-user series split by vehicle type (it has no crash counts).
ROAD_USER_OUTCOMES = ("deaths_30d", "hospitalised_30d")
NUMERATORS = {
    **OUTCOMES,
    "drivers_deaths_30d": f"Drivers of {MOTOR_VEHICLES} killed within 30 days",
    "drivers_hospitalised_30d": f"Drivers of {MOTOR_VEHICLES} injured and hospitalised",
    "occupants_deaths_30d": f"Occupants of {MOTOR_VEHICLES} killed within 30 days",
    "occupants_hospitalised_30d": f"Occupants of {MOTOR_VEHICLES} injured and hospitalised",
}
# Denominator key -> (exposure column, label, rate per this many units of exposure, numerator
# group). A group of None divides the whole outcome; "drivers" and "occupants" divide only the
# casualties that the denominator can contain (``ROAD_USER_GROUPS``).
DENOMINATORS: dict[str, tuple[str | None, str, float, str | None]] = {
    "count": (None, "Count, no denominator", 1.0, None),
    "residents": ("residents", "Per 100,000 residents", 1e5, None),
    "licence_holders": (
        "licence_holders",
        "Drivers only, per 100,000 licence holders",
        1e5,
        "drivers",
    ),
    "vehicles": (
        "vehicle_fleet",
        "Vehicle occupants only, per 100,000 registered vehicles",
        1e5,
        "occupants",
    ),
    "road_fuel": ("road_fuel_tonnes", "Per million tonnes of road fuel", 1e6, None),
}


def numerator_for(outcome: str, denominator: str) -> str | None:
    """The numerator column paired with ``denominator`` for ``outcome``; None if there is none."""
    group = DENOMINATORS[denominator][3]
    if group is None:
        return outcome
    if outcome not in ROAD_USER_OUTCOMES:
        return None
    return f"{group}_{outcome}"


# --------------------------------------------------------------------------- inputs


def road_user_outcomes() -> pd.DataFrame:
    """Driver and occupant deaths and hospitalised of ``MOTOR_VEHICLE_TYPES`` per year, national.

    Summed from the yearbook's road-user series (all roads); a year in which any of the vehicle
    types is missing stays NA rather than being summed short.
    """
    users = io_tables.read_table("series_road_users")
    users = users[
        (users.zone == "all")
        & users.vehicle_type.isin(MOTOR_VEHICLE_TYPES)
        & users.severity.isin(ROAD_USER_OUTCOMES)
    ]
    columns = {}
    for group, population in ROAD_USER_GROUPS.items():
        for outcome in ROAD_USER_OUTCOMES:
            rows = users[(users.population == population) & (users.severity == outcome)]
            columns[f"{group}_{outcome}"] = rows.groupby("year").value.sum(
                min_count=len(MOTOR_VEHICLE_TYPES)
            )
    out = pd.DataFrame(columns)
    out.index = out.index.astype(int)
    return out


def annual_outcomes() -> pd.DataFrame:
    """Injury crashes, 30-day deaths and hospitalised injured per year, national, 1993 onwards.

    With the driver and occupant counts of ``road_user_outcomes`` beside them.
    """
    annual = io_tables.read_table("series_annual")
    annual = annual[annual.zone == "all"]
    wide = annual.pivot_table(index="year", columns="metric", values="value", aggfunc="first")
    out = wide[list(OUTCOMES)].copy()
    out.index = out.index.astype(int)
    return out.join(road_user_outcomes(), how="left")


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


def year_to_year_dispersion(years: tuple[int, int] = SCATTER_YEARS) -> pd.DataFrame:
    """How much more each annual count scatters around its trend than Poisson chance allows.

    A log-linear Poisson trend is fitted to each outcome over ``years`` and the Pearson dispersion
    is kept (at least 1). A dispersion of 8 means a year's count varies eight times as much as a
    Poisson count of the same size: recording practice, weather and the calendar all move a year,
    and the pure Poisson interval does not see them. Crashes, whose count depends on how
    completely slight injuries are recorded, scatter far more than deaths. One row per numerator
    in ``NUMERATORS``, the driver and occupant counts included.
    """
    panel = annual_panel().set_index("year").loc[years[0] : years[1]]
    t = (panel.index.to_numpy(dtype=float) - years[0]).reshape(-1, 1)
    design = sm.add_constant(t)
    records = []
    for outcome, label in NUMERATORS.items():
        fit = sm.GLM(panel[outcome].to_numpy(), design, family=sm.families.Poisson()).fit(
            scale="X2"
        )
        records.append(
            {
                "outcome": outcome,
                "outcome_label": label,
                "first_year": years[0],
                "last_year": years[1],
                "dispersion": max(float(fit.scale), 1.0),
                "mean_count": float(panel[outcome].mean()),
            }
        )
    return pd.DataFrame.from_records(records)


def risk_index(base_year: int = BASE_YEAR) -> pd.DataFrame:
    """Each outcome under each denominator it can be paired with, as a rate and a ratio to 2019.

    The numerator is the outcome itself, or for licence holders and the registered fleet only the
    drivers or occupants of ``MOTOR_VEHICLE_TYPES`` (``numerator_for``); injury crashes have no
    such split and are not divided by those two. ``ratio_to_base`` is (rate this year) / (rate in
    ``base_year``), with a log-normal interval that treats both counts as Poisson and the
    denominators as known. For the count itself the "denominator" is 1 and the ratio is the change
    in the count. ``ratio_low_yty`` and ``ratio_high_yty`` widen that interval by the numerator's
    ``year_to_year_dispersion``, so they cover an ordinary year's variation and not just Poisson
    chance; the pages read changes against these.
    """
    panel = annual_panel().set_index("year")
    dispersion = year_to_year_dispersion().set_index("outcome").dispersion
    last_year = int(panel.index.max())
    years = range(base_year, last_year + 1)
    z = 1.959963984540054
    records = []
    for outcome, outcome_label in OUTCOMES.items():
        for key, (column, label, per, _) in DENOMINATORS.items():
            numerator = numerator_for(outcome, key)
            if numerator is None:
                continue
            base_count = float(panel.loc[base_year, numerator])
            base_exposure = 1.0 if column is None else float(panel.loc[base_year, column])
            for year in years:
                count = float(panel.loc[year, numerator])
                exposure = 1.0 if column is None else float(panel.loc[year, column])
                if column is None:
                    value, low, high = count, *rates.poisson_interval(count)
                else:
                    value, low, high = rates.rate(count, exposure, per=per)
                ratio, ratio_low, ratio_high = rates.rate_ratio(
                    count, exposure, base_count, base_exposure
                )
                spread = z * np.sqrt(float(dispersion[numerator]) * (1 / count + 1 / base_count))
                records.append(
                    {
                        "outcome": outcome,
                        "outcome_label": outcome_label,
                        "numerator": numerator,
                        "numerator_label": NUMERATORS[numerator],
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
                        "ratio_low_yty": ratio * np.exp(-spread),
                        "ratio_high_yty": ratio * np.exp(spread),
                        "index": 100 * ratio,
                    }
                )
    return pd.DataFrame.from_records(records)


FREQUENCY_SEVERITY_BASE = 1996


def frequency_severity(base_year: int = FREQUENCY_SEVERITY_BASE) -> pd.DataFrame:
    """Deaths per tonne of road fuel split into crashes per tonne and deaths per crash.

    Deaths per tonne of road fuel is the product of injury crashes per tonne (frequency) and
    deaths per injury crash (severity), so the two indices multiply to the third exactly. Each is
    indexed to ``base_year`` (the first year of the fuel series) = 100. The injury-crash count
    depends on how completely slight injuries are recorded, which moves the split between the two
    without moving the product: deaths are the completely counted outcome.
    """
    panel = annual_panel().set_index("year")
    panel = panel[panel.road_fuel_tonnes.notna()]
    out = pd.DataFrame(
        {
            "crashes": panel.crashes,
            "deaths_30d": panel.deaths_30d,
            "hospitalised_30d": panel.hospitalised_30d,
            "road_fuel_tonnes": panel.road_fuel_tonnes,
        }
    )
    out["crashes_per_kt_fuel"] = out.crashes / out.road_fuel_tonnes * 1e3
    out["deaths_per_100_crashes"] = out.deaths_30d / out.crashes * 100
    out["hospitalised_per_100_crashes"] = out.hospitalised_30d / out.crashes * 100
    out["deaths_per_mt_fuel"] = out.deaths_30d / out.road_fuel_tonnes * 1e6
    for column, name in (
        ("crashes_per_kt_fuel", "frequency_index"),
        ("deaths_per_100_crashes", "severity_index"),
        ("deaths_per_mt_fuel", "deaths_per_fuel_index"),
    ):
        out[name] = out[column] / out.loc[base_year, column] * 100
    out.index.name = "year"
    return out.reset_index()


# Hypothetical yearly growth in kilometres per tonne of road fuel. They are a grid, not estimates:
# no series in the repository measures kilometres per tonne on all roads, so none of them is more
# likely than another, and the tables built on them support no conclusion about kilometres.
HYPOTHETICAL_GAINS = (0.0, 0.01, 0.02)


def fuel_efficiency_sensitivity(base_year: int = BASE_YEAR) -> pd.DataFrame:
    """How far the per-fuel change since ``base_year`` moves under hypothetical drifts of the proxy.

    If kilometres per tonne grew by ``g`` a year, dividing by fuel grossed up by
    ``(1 + g) ** (year - base_year)`` gives the ratio to the base year under that assumption.
    ``g`` takes the values of ``HYPOTHETICAL_GAINS``; the output shows how much the per-fuel
    figure depends on a drift the data do not measure, not what the change per kilometre was.
    """
    panel = annual_panel().set_index("year")
    last_year = int(panel.index.max())
    records = []
    for outcome in ("deaths_30d", "hospitalised_30d"):
        for gain in HYPOTHETICAL_GAINS:
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
                        "hypothetical_annual_gain": gain,
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
    """A segmented log-linear Poisson trend with quasi-likelihood errors, dispersion at least 1."""

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
    """Fit one placement of the turning points, with the dispersion floored at 1.

    A Pearson dispersion below 1 in a dozen points is chance, not a series steadier than Poisson,
    so the scale is never allowed to make an interval narrower than pure Poisson noise would.
    """
    design = _design(years, int(years[0]), tuple(breaks))
    model = sm.GLM(counts, design, family=sm.families.Poisson(), offset=offset)
    result = model.fit(scale="X2")
    if result.scale < 1.0:
        result = model.fit(scale=1.0)
    return Joinpoint(years, tuple(breaks), result)


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


# The three views of the long series: measure -> (exposure column, label, first year, numerator,
# denominator key in ``DENOMINATORS``). The registered fleet is paired with the occupants of
# ``MOTOR_VEHICLE_TYPES``, as in the 2019 to 2024 index; the count and road fuel with all deaths.
LONG_RUN_MEASURES: dict[str, tuple[str | None, str, int, str, str]] = {
    "count": (None, "Deaths", FIRST_YEAR, "deaths_30d", "count"),
    "occupants_per_vehicle": (
        "vehicle_fleet",
        "Vehicle occupant deaths per registered vehicle",
        FIRST_YEAR,
        "occupants_deaths_30d",
        "vehicles",
    ),
    "road_fuel": (
        "road_fuel_tonnes",
        "Deaths per tonne of road fuel",
        1996,
        "deaths_30d",
        "road_fuel",
    ),
}


@cache
def _long_run_fits(last_pre_year: int = BASE_YEAR):
    panel = annual_panel().set_index("year")
    fits = {}
    for key, (column, label, start, numerator, _) in LONG_RUN_MEASURES.items():
        window = panel.loc[start:last_pre_year]
        years = window.index.to_numpy()
        counts = window[numerator].to_numpy(dtype=float)
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

    ``expected`` is the fitted trend up to 2019 and its projection afterwards, in deaths of the
    measure's numerator (``numerator``: all deaths, or the occupant deaths of the per-vehicle
    measure): for the per-vehicle and per-fuel measures the projection is multiplied by the actual
    fleet or fuel of each year, so ``observed / expected`` reads the same way for all three. For
    2020 onward the interval is a prediction interval.
    """
    panel, fits = _long_run_fits()
    last_year = int(panel.index.max())
    frames = []
    for key, (fit, _, label, column, start) in fits.items():
        numerator, denominator = LONG_RUN_MEASURES[key][3:]
        window = panel.loc[start:last_year]
        years = window.index.to_numpy()
        offset = None if column is None else np.log(window[column].to_numpy(dtype=float))
        projected = project(fit, years, offset)
        projected["observed"] = window[numerator].to_numpy(dtype=float)
        projected["ratio"] = projected.observed / projected.expected
        projected["outside_interval"] = (projected.observed < projected.low) | (
            projected.observed > projected.high
        )
        projected["period"] = np.where(years <= BASE_YEAR, "fitted", "projected")
        projected.insert(0, "measure", key)
        projected.insert(1, "measure_label", label)
        projected.insert(2, "numerator", numerator)
        if column is not None:
            per = DENOMINATORS[denominator][2]
            exposure = window[column].to_numpy(dtype=float)
            projected["observed_rate"] = projected.observed / exposure * per
            projected["expected_rate"] = projected.expected / exposure * per
        else:
            projected["observed_rate"] = projected.observed
            projected["expected_rate"] = projected.expected
        frames.append(projected)
    return pd.concat(frames, ignore_index=True)


def long_run_efficiency_sensitivity() -> pd.DataFrame:
    """The 2020–2024 per-fuel ratio to trend under hypothetical extra drifts of the fuel proxy.

    Projecting the pre-2020 per-fuel trend assumes that whatever moved kilometres per tonne during
    its last segment went on at the same pace. This shows what an *extra* ``g`` a year from 2020
    (``HYPOTHETICAL_GAINS``) would do to the ratio and its interval. The values are hypothetical:
    no series in the repository measures kilometres per tonne on all roads, so the table shows how
    much the per-fuel excess depends on that unmeasured drift, not what the drift was.
    """
    series = long_run_series()
    fuel = series[(series.measure == "road_fuel") & (series.period == "projected")]
    records = []
    for gain in HYPOTHETICAL_GAINS:
        for row in fuel.itertuples(index=False):
            factor = (1 + gain) ** (row.year - BASE_YEAR)
            records.append(
                {
                    "hypothetical_extra_annual_gain": gain,
                    "year": row.year,
                    "ratio": row.ratio / factor,
                    "ratio_low": row.observed / (row.high * factor),
                    "ratio_high": row.observed / (row.low * factor),
                }
            )
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------------------------- measured kilometres

# The first year of the Ministry's interurban vehicle-km that is comparable with the rest: its 2008
# figures follow a new road inventory.
KM_FIRST_YEAR = io_traffic.ROAD_TRAFFIC_BREAK_YEAR
# ``per_km`` is the rate: interurban deaths over interurban vehicle-km. ``per_fuel`` divides the
# same interurban deaths by fuel sold for every road in Spain, towns included; its scope does not
# match its numerator, so it is not a rate of anything and is kept only as a diagnostic of how the
# fuel proxy behaves against measured kilometres.
KM_MEASURES = {
    "per_km": ("vehicle_km", "Interurban deaths per measured interurban vehicle-km"),
    "per_fuel": (
        "road_fuel_tonnes",
        "Interurban deaths over national road fuel (scopes differ; fuel-proxy diagnostic)",
    ),
}
# Road owners in the microdata (``TITULARIDAD_VIA``) whose roads table 1.2.14 counts: State,
# regions, and provincial councils, cabildos and consells.
KM_NETWORK_OWNERS = (1, 2, 3)


def fuel_bio_share() -> pd.DataFrame:
    """Biofuel in road fuel by year: the mass CORES reports blended into petrol and diesel.

    Biofuel carries less energy per tonne than the petrol and diesel it replaces, so a change in
    its share would change the kilometres a tonne of road fuel stands for. Only years in which
    CORES reports the share for all twelve months are kept.
    """
    fuel = io_traffic.read_cores_fuel()
    fuel = fuel.assign(
        bio_tonnes=fuel.petrol_tonnes * fuel.petrol_bio_share
        + fuel.diesel_tonnes * fuel.diesel_bio_share
    )
    annual = fuel.groupby("year").agg(
        road_fuel_tonnes=("road_fuel_tonnes", "sum"),
        bio_tonnes=("bio_tonnes", "sum"),
        months=("bio_tonnes", "count"),
    )
    annual = annual[annual.months == 12].drop(columns="months")
    annual["bio_share"] = annual.bio_tonnes / annual.road_fuel_tonnes
    return annual.reset_index()


def interurban_km_panel() -> pd.DataFrame:
    """Interurban deaths beside measured interurban vehicle-km and national road fuel, from 2004.

    ``vehicle_km`` is the Ministry's measured total on the interurban network of the State, the
    regions and the provincial councils (table 1.2.14). The deaths are the yearbook's interurban
    deaths, which also include interurban roads run by municipalities and other bodies; the share
    of those is measured from 2016 by ``interurban_network_coverage``. ``deaths_per_bn_km`` is the
    rate. ``km_per_tonne`` divides interurban kilometres by fuel sold for every road, towns
    included: it mixes scopes, so it is a diagnostic of how the two exposures diverge and not a
    measure of fuel economy.
    """
    traffic = io_traffic.read_road_traffic().set_index("year")
    monthly = io_tables.read_table("series_monthly")
    deaths = (
        monthly[(monthly.metric == "deaths_30d") & (monthly.zone == "interurban")]
        .groupby("year")
        .value.sum()
    )
    fuel = annual_panel().set_index("year").road_fuel_tonnes
    out = pd.DataFrame(
        {
            "deaths_interurban": deaths,
            "vehicle_km": traffic.total * 1e6,
            "road_fuel_tonnes": fuel,
        }
    ).dropna()
    out.index = out.index.astype(int)
    out["km_per_tonne"] = out.vehicle_km / out.road_fuel_tonnes
    out["deaths_per_bn_km"] = out.deaths_interurban / out.vehicle_km * 1e9
    out["comparable"] = out.index >= KM_FIRST_YEAR
    out.index.name = "year"
    return out.reset_index()


def km_trend_check(last_pre_year: int = BASE_YEAR) -> pd.DataFrame:
    """The long-run trend re-run on measured kilometres, for interurban deaths.

    The same joinpoint search as the long-run page is fitted to interurban deaths, 2008 to
    ``last_pre_year``, with measured interurban vehicle-km as exposure (``per_km``, the rate), and
    projected to every later year with that year's kilometres. ``ratio`` is observed over expected.
    The same deaths are also fitted with national road fuel as exposure (``per_fuel``): its scope
    does not match the numerator, so its ratios describe how the fuel proxy behaves beside the
    measured kilometres, not a rate.
    """
    panel = interurban_km_panel().set_index("year")
    panel = panel[panel.comparable]
    records = []
    for key, (column, label) in KM_MEASURES.items():
        window = panel.loc[:last_pre_year]
        years = window.index.to_numpy()
        fit, _ = joinpoint_search(
            years,
            window.deaths_interurban.to_numpy(dtype=float),
            np.log(window[column].to_numpy(dtype=float)),
        )
        all_years = panel.index.to_numpy()
        projected = project(fit, all_years, np.log(panel[column].to_numpy(dtype=float)))
        last_segment = segment_changes(fit).iloc[-1]
        for row, (year, observed) in zip(projected.itertuples(), panel.deaths_interurban.items()):
            records.append(
                {
                    "measure": key,
                    "measure_label": label,
                    "year": int(year),
                    "observed": float(observed),
                    "expected": float(row.expected),
                    "low": float(row.low),
                    "high": float(row.high),
                    "ratio": float(observed / row.expected),
                    "projected": int(year) > last_pre_year,
                    "outside_interval": bool(observed < row.low or observed > row.high),
                    "breaks": " ".join(str(b) for b in fit.breaks),
                    "last_segment_start": int(last_segment.start),
                    "last_segment_annual_change": float(last_segment.annual_change),
                }
            )
    return pd.DataFrame.from_records(records)


def interurban_network_coverage() -> pd.DataFrame:
    """How many interurban deaths are on roads the measured kilometres leave out, by year.

    Table 1.2.14 counts vehicle-km on the roads of the State, the regions and the provincial
    councils; the yearbook's interurban deaths also include roads run by municipalities and other
    bodies. The microdata (2016 onwards) record the road's owner (``TITULARIDAD_VIA``), so the
    share of interurban deaths outside the counted networks can be measured year by year:
    ``deaths_outside`` sums municipal (4), other (5) and unspecified owners. ``deaths_series`` is
    the yearbook's interurban count for the same year, against which the microdata total is
    checked.
    """
    crashes = pd.read_parquet(
        DGT_PROCESSED_CRASHES, columns=["ANYO", "zone", "TITULARIDAD_VIA", "n_deaths"]
    )
    crashes = crashes[crashes.zone == "interurban"]
    owner = crashes.TITULARIDAD_VIA.astype("float").fillna(-1).astype(int)
    deaths = crashes.n_deaths.astype(int)
    by_year = pd.DataFrame(
        {
            "deaths_microdata": deaths.groupby(crashes.ANYO).sum(),
            "deaths_counted_network": deaths.where(owner.isin(KM_NETWORK_OWNERS), 0)
            .groupby(crashes.ANYO)
            .sum(),
            "deaths_municipal": deaths.where(owner == 4, 0).groupby(crashes.ANYO).sum(),
            "deaths_other_owner": deaths.where(owner == 5, 0).groupby(crashes.ANYO).sum(),
        }
    )
    by_year.index = by_year.index.astype(int)
    by_year["deaths_outside"] = by_year.deaths_microdata - by_year.deaths_counted_network
    by_year["outside_share"] = by_year.deaths_outside / by_year.deaths_microdata
    monthly = io_tables.read_table("series_monthly")
    series = (
        monthly[(monthly.metric == "deaths_30d") & (monthly.zone == "interurban")]
        .groupby("year")
        .value.sum()
    )
    series.index = series.index.astype(int)
    by_year["deaths_series"] = series.reindex(by_year.index)
    by_year.index.name = "year"
    return by_year.reset_index().astype(
        {
            "deaths_microdata": int,
            "deaths_counted_network": int,
            "deaths_municipal": int,
            "deaths_other_owner": int,
            "deaths_outside": int,
        }
    )
