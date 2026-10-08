"""Counts against exposure: the same counts divided by what they can be divided by.

Two questions share this module because they share the denominators.

* **2019 to 2024.** Did the counts change after the pandemic once they are divided by something?
  Deaths, hospitalised injured and injury crashes are set against residents and road fuel; driver
  casualties against licence holders; motor-vehicle occupant casualties against the registered
  fleet. Each is indexed to 2019, with the uncertainty of the change.
* **1993 to 2024.** Which of the changes in the long series are structural and which are the
  pandemic? A segmented (joinpoint) log-linear trend is fitted to the deaths of 1993–2019, with the
  number and position of its turning points chosen by the data, and its last segment, refitted on
  its own years, is projected through 2020–2024: for the count, for motor-vehicle occupant deaths
  over the registered fleet, and for deaths over road fuel. ``long_run_projection_sensitivity``
  shows how the reading of those years moves with the choices behind the projection.

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
  per tonne moved on all roads since 2019; ``fuel_efficiency_sensitivity`` shows only how far the
  per-fuel change moves under hypothetical drifts, and ``km_crosscheck`` sets DGT's kilometre
  estimates for 2022–2024 beside fuel over the years they cover.

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
from scipy import stats

from dgt_stats import io_exposure, io_population, io_tables, io_traffic, rates
from dgt_stats.paths import DGT_PROCESSED_CRASHES

BASE_YEAR = 2019
FIRST_YEAR = 1993
PANDEMIC_YEARS = (2020, 2021)
# Two-sided coverage of every interval in this module.
COVERAGE = 0.95
NORMAL_QUANTILE = float(stats.norm.ppf(0.5 + COVERAGE / 2))
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


def t_quantile(df: float) -> float:
    """The two-sided ``COVERAGE`` quantile of Student's t with ``df`` degrees of freedom.

    Used wherever an interval rests on a scatter factor estimated from the same few points: the
    factor is itself uncertain, and the normal quantile would treat it as known.
    """
    return float(stats.t.ppf(0.5 + COVERAGE / 2, df))


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

    With the driver and occupant counts of ``road_user_outcomes`` beside them, injury crashes on
    interurban roads and in towns (``crashes_interurban``, ``crashes_urban``: the recording of
    urban crashes rose in steps that the national count inherits), and deaths within 24 hours
    (``deaths_24h``: counted directly by the police in every year, whereas DGT estimated the 30-day
    deaths of 1993–2010 from them with correction factors).
    """
    annual = io_tables.read_table("series_annual")
    zones = annual.pivot_table(
        index="year", columns=["metric", "zone"], values="value", aggfunc="first"
    )
    out = zones.xs("all", axis=1, level="zone")[list(OUTCOMES)].copy()
    for zone in ("interurban", "urban"):
        out[f"crashes_{zone}"] = zones[("crashes", zone)]
    monthly = io_tables.read_table("series_monthly")
    out["deaths_24h"] = (
        monthly[(monthly.metric == "deaths_24h") & (monthly.zone == "all")]
        .groupby("year")
        .value.sum(min_count=12)
    )
    out.index = out.index.astype(int)
    out.columns.name = None
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

    Seven years leave five residual degrees of freedom (``df_resid``), so each factor is itself
    uncertain: ``pearson_dispersion`` is the estimate before the floor, ``dispersion_low`` and
    ``dispersion_high`` its chi-square interval, and ``t_quantile`` the Student-t quantile with
    which ``risk_index`` widens its intervals instead of the normal one.
    """
    panel = annual_panel().set_index("year").loc[years[0] : years[1]]
    t = (panel.index.to_numpy(dtype=float) - years[0]).reshape(-1, 1)
    design = sm.add_constant(t)
    records = []
    for outcome, label in NUMERATORS.items():
        fit = sm.GLM(panel[outcome].to_numpy(), design, family=sm.families.Poisson()).fit(
            scale="X2"
        )
        df = float(fit.df_resid)
        estimate = float(fit.scale)
        tail = (1 - COVERAGE) / 2
        records.append(
            {
                "outcome": outcome,
                "outcome_label": label,
                "first_year": years[0],
                "last_year": years[1],
                "dispersion": max(estimate, 1.0),
                "pearson_dispersion": estimate,
                "df_resid": int(df),
                "dispersion_low": df * estimate / float(stats.chi2.ppf(1 - tail, df)),
                "dispersion_high": df * estimate / float(stats.chi2.ppf(tail, df)),
                "t_quantile": t_quantile(df),
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
    chance; the pages read changes against these. Because that dispersion is estimated from seven
    years, they use the Student-t quantile with its residual degrees of freedom, not the normal.
    """
    panel = annual_panel().set_index("year")
    scatter = year_to_year_dispersion().set_index("outcome")
    dispersion, quantile = scatter.dispersion, scatter.t_quantile
    last_year = int(panel.index.max())
    years = range(base_year, last_year + 1)
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
                spread = float(quantile[numerator]) * np.sqrt(
                    float(dispersion[numerator]) * (1 / count + 1 / base_count)
                )
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
    """Deaths per tonne of road fuel split two ways into a frequency and a severity.

    Deaths per tonne of road fuel is the product of injury crashes per tonne (``frequency_index``)
    and deaths per injury crash (``severity_index``); it is equally the product of people admitted
    to hospital per tonne (``hospitalised_per_fuel_index``) and deaths per person admitted
    (``deaths_per_hospitalised_index``). Each pair multiplies to the third index exactly. Each is
    indexed to ``base_year`` (the first year of the fuel series) = 100. The two splits answer the
    same question with different thresholds of casualty, and they disagree: how completely slight
    injuries and admissions were recorded moves each split without moving the product, so deaths
    per tonne is the firm measure and neither split identifies how the fall divides.
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
    out["hospitalised_per_kt_fuel"] = out.hospitalised_30d / out.road_fuel_tonnes * 1e3
    out["deaths_per_100_hospitalised"] = out.deaths_30d / out.hospitalised_30d * 100
    for column, name in (
        ("crashes_per_kt_fuel", "frequency_index"),
        ("deaths_per_100_crashes", "severity_index"),
        ("deaths_per_mt_fuel", "deaths_per_fuel_index"),
        ("hospitalised_per_kt_fuel", "hospitalised_per_fuel_index"),
        ("deaths_per_100_hospitalised", "deaths_per_hospitalised_index"),
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


# The 2022 release's kilometre types that table 6 of the 2024 release repeats one for one; the
# heavy categories are split differently in the two releases and are not compared.
KM_SERIES_SAME_TYPES = {
    "Ciclomotor": "moped",
    "Motocicleta": "motorcycle",
    "Turismo": "car",
    "Furgoneta": "van",
    "Autobús": "bus",
}
# Table 6 rounds its means to whole kilometres.
KM_SERIES_TOLERANCE = 1.0


def km_crosscheck() -> pd.DataFrame:
    """DGT's kilometre estimates for 2022–2024 beside road fuel and deaths, one row per year.

    DGT's 2024 release gives mean annual kilometres per vehicle for 2022, 2023 and 2024 as one
    series (its table 6); for 2022 they equal the means of the 2022 release, which is checked
    here type by type. ``car_mean_km`` is that series for cars. Vehicle-kilometres need the fleet,
    which the repository holds for 2022 (the 2022 release) and 2024 (the 2024 release's detail
    sheet) but not 2023, so ``billion_km`` and ``car_billion_km`` are empty for 2023. The ratios
    are to the first year of the series; ``deaths_per_bn_km`` divides 30-day deaths by DGT's
    vehicle-kilometres of every type, beside ``deaths_per_mt_fuel``.
    """
    km_2022 = io_exposure.read_exposure("km_medios_2022")
    km_2024 = io_exposure.read_exposure("km_medios_tipo_2024")
    series = io_exposure.read_exposure("km_medios_serie_2024")
    means = series.pivot(index="year", columns="vehicle_group", values="mean_km")
    first = int(means.index.min())
    by_type = km_2022.groupby("vehicle_type")[["n_vehicles", "vehicle_km"]].sum()
    for vehicle_type, group in KM_SERIES_SAME_TYPES.items():
        own = float(
            by_type.loc[vehicle_type, "vehicle_km"] / by_type.loc[vehicle_type, "n_vehicles"]
        )
        if abs(own - float(means.loc[first, group])) > KM_SERIES_TOLERANCE:
            raise ValueError(
                f"km table 6: {group} {first} mean {means.loc[first, group]:,.0f} km differs from "
                f"the {first} release's {own:,.0f} km"
            )
    totals = {
        int(km_2022.year.iloc[0]): (
            float(km_2022.vehicle_km.sum()),
            float(by_type.loc["Turismo", "vehicle_km"]),
        ),
        int(km_2024.year.iloc[0]): (
            float(km_2024.total_km.sum()),
            float(km_2024.loc[km_2024.vehicle_group == "car", "total_km"].sum()),
        ),
    }
    panel = annual_panel().set_index("year")
    records = []
    for year in means.index:
        year = int(year)
        all_km, car_km = totals.get(year, (np.nan, np.nan))
        records.append(
            {
                "year": year,
                "car_mean_km": float(means.loc[year, "car"]),
                "billion_km": all_km / 1e9,
                "car_billion_km": car_km / 1e9,
                "road_fuel_tonnes": float(panel.loc[year, "road_fuel_tonnes"]),
                "deaths_30d": float(panel.loc[year, "deaths_30d"]),
            }
        )
    out = pd.DataFrame.from_records(records)
    for column in ("car_mean_km", "billion_km", "car_billion_km", "road_fuel_tonnes"):
        out[f"{column}_ratio"] = out[column] / float(out.loc[out.year == first, column].iloc[0])
    out["deaths_per_bn_km"] = out.deaths_30d / out.billion_km
    out["deaths_per_mt_fuel"] = out.deaths_30d / out.road_fuel_tonnes * 1e6
    return out


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
    """Annual percentage change in each segment, with a 95 % interval from the scaled covariance.

    The interval uses the Student-t quantile with the fit's residual degrees of freedom, because
    the dispersion is estimated, and it takes the turning points as known: the uncertainty of
    where they fall is not in it.
    """
    params = fit.result.params
    cov = fit.result.cov_params()
    quantile = t_quantile(fit.result.df_resid)
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
                "low": np.exp(slope - quantile * se) - 1,
                "high": np.exp(slope + quantile * se) - 1,
            }
        )
    return pd.DataFrame.from_records(records)


def project(
    fit: Joinpoint,
    years: np.ndarray,
    offset: np.ndarray | None = None,
    quantile: float | None = None,
) -> pd.DataFrame:
    """Expected counts on the fitted joinpoint trend for ``years``, with a prediction interval.

    The interval combines the uncertainty of the fitted line (delta method on the linear predictor)
    with overdispersed Poisson noise around it: ``var = dispersion × mu + mu² × var(eta)``, both
    from the whole fit. ``quantile`` defaults to Student's t with the fit's residual degrees of
    freedom.
    """
    design = _design(np.asarray(years), int(fit.years[0]), fit.breaks)
    eta = design @ fit.result.params
    if offset is not None:
        eta = eta + offset
    var_eta = np.einsum("ij,jk,ik->i", design, fit.result.cov_params(), design)
    mu = np.exp(eta)
    sd = np.sqrt(fit.dispersion * mu + mu**2 * var_eta)
    q = t_quantile(fit.result.df_resid) if quantile is None else quantile
    return pd.DataFrame({"year": years, "expected": mu, "low": mu - q * sd, "high": mu + q * sd})


@dataclass
class SegmentTrend:
    """A log-linear Poisson trend with quasi-likelihood errors fitted to one run of years.

    Used to project the last segment of a joinpoint trend: refitted on its own years, it carries
    the scatter of those years rather than the scatter of the whole series, which early-period
    misfit can inflate. The dispersion is floored at 1, as in ``_fit``.
    """

    first: int
    last: int
    result: sm.genmod.generalized_linear_model.GLMResultsWrapper

    @property
    def dispersion(self) -> float:
        return float(self.result.scale)

    @property
    def df(self) -> int:
        return int(self.result.df_resid)

    @property
    def annual_change(self) -> float:
        return float(np.exp(self.result.params[1]) - 1)

    def slope(self, quantile: float | None = None) -> tuple[float, float, float]:
        """The annual change and its 95 % interval, by default from Student's t with the fit's df."""
        slope, se = float(self.result.params[1]), float(self.result.bse[1])
        q = t_quantile(self.df) if quantile is None else quantile
        low, high = np.exp(slope - q * se) - 1, np.exp(slope + q * se) - 1
        return self.annual_change, float(low), float(high)


def fit_segment(years: np.ndarray, counts: np.ndarray, offset: np.ndarray | None) -> SegmentTrend:
    """A log-linear quasi-Poisson trend over ``years``, its dispersion floored at 1."""
    years = np.asarray(years)
    design = sm.add_constant((years - years[0]).astype(float))
    model = sm.GLM(counts, design, family=sm.families.Poisson(), offset=offset)
    result = model.fit(scale="X2")
    if result.scale < 1.0:
        result = model.fit(scale=1.0)
    return SegmentTrend(int(years[0]), int(years[-1]), result)


def project_segment(
    trend: SegmentTrend,
    years: np.ndarray,
    offset: np.ndarray | None = None,
    quantile: float | None = None,
) -> pd.DataFrame:
    """Expected counts on a segment's trend for ``years``, with a prediction interval.

    As ``project``: ``var = dispersion × mu + mu² × var(eta)``, here from the segment's own fit.
    ``quantile`` defaults to Student's t with the segment's residual degrees of freedom, because
    its dispersion is estimated from those few years.
    """
    years = np.asarray(years)
    design = sm.add_constant((years - trend.first).astype(float), has_constant="add")
    eta = design @ trend.result.params
    if offset is not None:
        eta = eta + offset
    var_eta = np.einsum("ij,jk,ik->i", design, trend.result.cov_params(), design)
    mu = np.exp(eta)
    sd = np.sqrt(trend.dispersion * mu + mu**2 * var_eta)
    q = t_quantile(trend.df) if quantile is None else quantile
    return pd.DataFrame({"year": years, "expected": mu, "low": mu - q * sd, "high": mu + q * sd})


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


# Deaths within 24 hours are counted by the police in every year. DGT estimated the 30-day deaths of
# 1993–2010 from them with correction factors and has counted 30-day deaths by matching records
# with the death register since 2011, so the long-run trends are refitted on them as a check.
DEATHS_30D = "deaths_30d"
DEATHS_24H = "deaths_24h"
# The first year whose 30-day deaths DGT counted by matching crash records with the death register
# rather than estimating them from 24-hour deaths (DGT, Anuario estadístico de accidentes 2014,
# annex II, "Metodología revisada para el cálculo de fallecidos a 30 días").
DEATHS_30D_COUNTED_FROM = 2011
DEATHS_LABELS = {DEATHS_30D: "within 30 days", DEATHS_24H: "within 24 hours"}


def _numerator(numerator: str, deaths: str) -> str | None:
    """The measure's numerator counted with ``deaths``; None if the yearbook has no such count.

    Only all deaths are published within 24 hours, so the per-vehicle measure, whose numerator is
    occupant deaths, has no 24-hour version.
    """
    if deaths == DEATHS_30D:
        return numerator
    return deaths if numerator == DEATHS_30D else None


@cache
def _long_run_fits(last_pre_year: int = BASE_YEAR, deaths: str = DEATHS_30D):
    panel = annual_panel().set_index("year")
    fits = {}
    for key, (column, label, start, numerator, _) in LONG_RUN_MEASURES.items():
        numerator = _numerator(numerator, deaths)
        if numerator is None:
            continue
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


def _offset(frame: pd.DataFrame, column: str | None) -> np.ndarray | None:
    return None if column is None else np.log(frame[column].to_numpy(dtype=float))


def _segment_projection(
    panel: pd.DataFrame,
    key: str,
    start: int,
    deaths: str = DEATHS_30D,
    quantile: float | None = None,
    last_pre_year: int = BASE_YEAR,
) -> tuple[SegmentTrend, pd.DataFrame]:
    """The trend of ``start``–``last_pre_year`` refitted alone and projected to every later year.

    The projection is multiplied by each later year's fleet or fuel for the two rates, so it is in
    deaths of the measure's numerator, like ``observed``.
    """
    column = LONG_RUN_MEASURES[key][0]
    numerator = _numerator(LONG_RUN_MEASURES[key][3], deaths)
    window = panel.loc[start:last_pre_year]
    trend = fit_segment(
        window.index.to_numpy(), window[numerator].to_numpy(dtype=float), _offset(window, column)
    )
    after = panel.loc[last_pre_year + 1 :]
    projected = project_segment(trend, after.index.to_numpy(), _offset(after, column), quantile)
    projected["observed"] = after[numerator].to_numpy(dtype=float)
    return trend, projected


def _read_against_trend(frame: pd.DataFrame) -> pd.DataFrame:
    """Observed over expected, the trend's range around 1, and whether a year lies outside it.

    ``range_low`` and ``range_high`` are the prediction interval divided by the expected count: a
    year lies outside the range exactly when its ``ratio`` lies outside them.
    """
    frame = frame.copy()
    frame["ratio"] = frame.observed / frame.expected
    frame["range_low"] = frame.low / frame.expected
    frame["range_high"] = frame.high / frame.expected
    frame["outside_interval"] = (frame.observed < frame.low) | (frame.observed > frame.high)
    return frame


def long_run_series() -> pd.DataFrame:
    """Observed deaths against the pre-pandemic trend, every year, for the three measures.

    Up to 2019 ``expected`` is the fitted joinpoint trend, with its prediction interval. From 2020
    it is the projection of the last segment: the trend of the years from the last turning point
    to 2019, refitted on those years alone (``projection_start`` to 2019) and continued, with a
    prediction interval from that fit's own scatter and the Student-t quantile of its residual
    degrees of freedom (``projection_df``). Refitting the segment keeps the misfit of the early
    years out of the scatter a projected year is read against.

    Values are in deaths of the measure's numerator (``numerator``: all deaths, or the occupant
    deaths of the per-vehicle measure); for the per-vehicle and per-fuel measures the trend is
    multiplied by the actual fleet or fuel of each year, so ``observed / expected`` reads the same
    way for all three. ``range_low`` and ``range_high`` are the interval over the expected count.
    """
    panel, fits = _long_run_fits()
    last_year = int(panel.index.max())
    frames = []
    for key, (fit, _, label, column, start) in fits.items():
        numerator, denominator = LONG_RUN_MEASURES[key][3:]
        fitted_window = panel.loc[start:BASE_YEAR]
        fitted = project(fit, fitted_window.index.to_numpy(), _offset(fitted_window, column))
        fitted["observed"] = fitted_window[numerator].to_numpy(dtype=float)
        trend, projected = _segment_projection(panel, key, fit.breaks[-1])
        both = pd.concat([fitted, projected], ignore_index=True)
        both = _read_against_trend(both)
        years = both.year.to_numpy()
        both["period"] = np.where(years <= BASE_YEAR, "fitted", "projected")
        both["projection_start"] = trend.first
        both["projection_annual_change"] = trend.annual_change
        both["projection_dispersion"] = trend.dispersion
        both["projection_df"] = trend.df
        both.insert(0, "measure", key)
        both.insert(1, "measure_label", label)
        both.insert(2, "numerator", numerator)
        window = panel.loc[start:last_year]
        if column is not None:
            per = DENOMINATORS[denominator][2]
            exposure = window[column].to_numpy(dtype=float)
            both["observed_rate"] = both.observed / exposure * per
            both["expected_rate"] = both.expected / exposure * per
        else:
            both["observed_rate"] = both.observed
            both["expected_rate"] = both.expected
        frames.append(both)
    return pd.concat(frames, ignore_index=True)


def long_run_projection_sensitivity() -> pd.DataFrame:
    """How the 2020 onward reading of each measure moves under other reasonable projections.

    For every measure and every year after 2019, one row per variant:

    * ``main``: the projection of ``long_run_series``;
    * ``start_<year>``: the last segment taken to start in a year where one of the other measures
      puts its last turning point, refitted and projected the same way;
    * ``normal_quantile``: the main projection with the normal quantile in place of Student's t;
    * ``joinpoint``: the continuous joinpoint trend continued, with the scatter of the whole fit
      from the first year to 2019 and the normal quantile;
    * ``deaths_24h``: deaths within 24 hours instead of 30 days, with the joinpoint search re-run
      on them and its last segment projected as in ``main`` (the count and per tonne of fuel only:
      occupant deaths are not published within 24 hours).

    ``breaks`` are the turning points of the joinpoint fit the variant uses and ``segment_start``
    the first year of the projected trend, whose ``annual_change``, ``dispersion`` and ``df`` are
    given with the ``interval_quantile`` used (for ``joinpoint`` those of the whole fit's last segment and scatter).
    """
    panel, fits = _long_run_fits()
    _, fits_24h = _long_run_fits(deaths=DEATHS_24H)
    last_starts = sorted({int(fit.breaks[-1]) for fit, *_ in fits.values()})
    records = []

    def add(key, variant, label, deaths, breaks, trend_values, projected):
        frame = _read_against_trend(projected)
        start, (change, change_low, change_high), dispersion, df, quantile = trend_values
        for row in frame.itertuples(index=False):
            records.append(
                {
                    "measure": key,
                    "measure_label": LONG_RUN_MEASURES[key][1],
                    "variant": variant,
                    "variant_label": label,
                    "deaths": DEATHS_LABELS[deaths],
                    "breaks": " ".join(str(b) for b in breaks),
                    "segment_start": int(start),
                    "annual_change": float(change),
                    "annual_change_low": float(change_low),
                    "annual_change_high": float(change_high),
                    "dispersion": float(dispersion),
                    "df": int(df),
                    "interval_quantile": float(quantile),
                    "year": int(row.year),
                    "observed": float(row.observed),
                    "expected": float(row.expected),
                    "low": float(row.low),
                    "high": float(row.high),
                    "ratio": float(row.ratio),
                    "range_low": float(row.range_low),
                    "range_high": float(row.range_high),
                    "outside_interval": bool(row.outside_interval),
                }
            )

    for key, (fit, _, _, column, _) in fits.items():
        own = int(fit.breaks[-1])
        trend, projected = _segment_projection(panel, key, own)
        values = (own, trend.slope(), trend.dispersion, trend.df, t_quantile(trend.df))
        add(key, "main", "Main projection", DEATHS_30D, fit.breaks, values, projected)
        for start in last_starts:
            if start == own:
                continue
            trend, projected = _segment_projection(panel, key, start)
            add(
                key,
                f"start_{start}",
                f"Last segment from {start}",
                DEATHS_30D,
                fit.breaks,
                (start, trend.slope(), trend.dispersion, trend.df, t_quantile(trend.df)),
                projected,
            )
        trend, projected = _segment_projection(panel, key, own, quantile=NORMAL_QUANTILE)
        add(
            key,
            "normal_quantile",
            "Main projection, normal quantile",
            DEATHS_30D,
            fit.breaks,
            (own, trend.slope(NORMAL_QUANTILE), trend.dispersion, trend.df, NORMAL_QUANTILE),
            projected,
        )
        after = panel.loc[BASE_YEAR + 1 :]
        projected = project(fit, after.index.to_numpy(), _offset(after, column), NORMAL_QUANTILE)
        projected["observed"] = after[LONG_RUN_MEASURES[key][3]].to_numpy(dtype=float)
        last_segment = segment_changes(fit).iloc[-1]
        add(
            key,
            "joinpoint",
            "Joinpoint trend continued, scatter of the whole fit, normal quantile",
            DEATHS_30D,
            fit.breaks,
            (
                own,
                (last_segment.annual_change, last_segment.low, last_segment.high),
                fit.dispersion,
                fit.result.df_resid,
                NORMAL_QUANTILE,
            ),
            projected,
        )
        if key in fits_24h:
            fit_24h = fits_24h[key][0]
            start = int(fit_24h.breaks[-1])
            trend, projected = _segment_projection(panel, key, start, deaths=DEATHS_24H)
            add(
                key,
                "deaths_24h",
                "Deaths within 24 hours, own turning points",
                DEATHS_24H,
                fit_24h.breaks,
                (start, trend.slope(), trend.dispersion, trend.df, t_quantile(trend.df)),
                projected,
            )
    return pd.DataFrame.from_records(records)


def long_run_efficiency_sensitivity() -> pd.DataFrame:
    """The 2020–2024 per-fuel ratio to trend under hypothetical extra drifts of the fuel proxy.

    Projecting the pre-2020 per-fuel trend assumes that whatever moved kilometres per tonne during
    its last segment went on at the same pace. This shows what an *extra* ``g`` a year from 2020
    (``HYPOTHETICAL_GAINS``) would do: dividing deaths by fuel grossed up by ``(1 + g) ** (year -
    2019)`` turns them into deaths per implied kilometre, and ``ratio`` is that rate against its
    trend. ``ratio_low`` and ``ratio_high`` are the interval of the ratio, and
    ``outside_interval`` says whether the year lies outside the trend's range. The values are
    hypothetical: no series in the repository measures kilometres per tonne on all roads since
    2019, so the table shows how much the per-fuel excess depends on that unmeasured drift, not
    what the drift was.
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
                    "outside_interval": bool(
                        row.observed / factor > row.high or row.observed / factor < row.low
                    ),
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
    ``last_pre_year``, with measured interurban vehicle-km as exposure (``per_km``, the rate). As
    on that page, the fitted years carry the joinpoint trend, and later years the projection of
    its last segment refitted on its own years (``projection_start`` to ``last_pre_year``), with
    that year's kilometres and a Student-t prediction interval. ``ratio`` is observed over
    expected and ``range_low``/``range_high`` the interval over the expected count. The same
    deaths are also fitted with national road fuel as exposure (``per_fuel``): its scope does not
    match the numerator, so its ratios describe how the fuel proxy behaves beside the measured
    kilometres, not a rate.
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
        fitted = project(fit, years, np.log(window[column].to_numpy(dtype=float)))
        segment = window.loc[fit.breaks[-1] :]
        trend = fit_segment(
            segment.index.to_numpy(),
            segment.deaths_interurban.to_numpy(dtype=float),
            np.log(segment[column].to_numpy(dtype=float)),
        )
        after = panel.loc[last_pre_year + 1 :]
        projected = project_segment(
            trend, after.index.to_numpy(), np.log(after[column].to_numpy(dtype=float))
        )
        both = pd.concat([fitted, projected], ignore_index=True)
        both["observed"] = panel.deaths_interurban.to_numpy(dtype=float)
        both = _read_against_trend(both)
        last_segment = segment_changes(fit).iloc[-1]
        for row in both.itertuples(index=False):
            records.append(
                {
                    "measure": key,
                    "measure_label": label,
                    "year": int(row.year),
                    "observed": float(row.observed),
                    "expected": float(row.expected),
                    "low": float(row.low),
                    "high": float(row.high),
                    "ratio": float(row.ratio),
                    "range_low": float(row.range_low),
                    "range_high": float(row.range_high),
                    "projected": int(row.year) > last_pre_year,
                    "outside_interval": bool(row.outside_interval),
                    "breaks": " ".join(str(b) for b in fit.breaks),
                    "last_segment_start": int(last_segment.start),
                    "last_segment_annual_change": float(last_segment.annual_change),
                    "projection_start": trend.first,
                    "projection_annual_change": trend.annual_change,
                    "projection_df": trend.df,
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
