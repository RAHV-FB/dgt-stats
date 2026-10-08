"""A working-day design matched in place and time: Barcelona city.

**Numerator.** Car drivers (``Turisme`` and ``Tot terreny``; taxis apart) involved in a crash
recorded by the Guàrdia Urbana in Barcelona in 2025 with at least one person injured or killed, on
a working day (:mod:`calendar`), by exact age. The person table lists every driver of a crash,
uninjured drivers included (a driver row exists for every vehicle in 98.4% of crashes). The
police do not record where drivers live, so the numerator also counts drivers from outside the
province, and professional drivers of ordinary cars (ride-hailing, company cars).

**Denominator.** Car-driver kilometres driven inside Barcelona on a working day by residents of
the province, from the EMEF 2022-2024 (:mod:`dgt_stats.emef.exposure`), times the 248 working days
of 2025. A trip with both ends in Barcelona is inside the city in full. A trip with one end in
the city is inside it only in part, and the public files give neither coordinates nor the
municipality at the other end, so that part cannot be measured; trips passing through without
stopping cannot be identified at all. Three denominators bracket the unknown:

* ``internal trips only``: crossing trips count for nothing (the smallest possible total, so the
  largest rates);
* ``crossing trips at an internal trip's length``: each crossing trip counts for the mean road
  length of a trip inside the city (4.6 km), or its own length if shorter;
* ``crossing trips in full``: every crossing trip counts in full (far more than the city holds,
  so the smallest rates).

Rates per kilometre are therefore given as a range, and the comparison that matters is the ratio
of each age group's rate to that of drivers aged 45-64, which is checked under all three.

**Uncertainty.** Each interval combines the sampling error of the denominator (the EMEF
bootstrap replicates) with Poisson error in the count (a gamma draw per replicate), paired
replicate by replicate. Drivers whose age the police did not record (about 8%) are allocated
across ages in proportion to those recorded for the absolute rates; the ratios do not depend on
that allocation.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd

from dgt_stats.emef import exposure
from dgt_stats.exposure_risk import calendar
from dgt_stats.microdata import barcelona

CAR_TYPES = ("Turisme", "Tot terreny")
TAXI = "Taxi"
YEAR = 2025
AGE_GROUPS: tuple[tuple[int, int, str], ...] = (
    (16, 29, "16-29"),
    (30, 44, "30-44"),
    (45, 64, "45-64"),
    (65, 200, "65+"),
)
OLDER_GROUPS: tuple[tuple[int, int, str], ...] = ((65, 74, "65-74"), (75, 200, "75+"))
REFERENCE = "45-64"
BILLION = 1e9
SEED = 20261008
BARCELONA_ZONE = 1
DENOMINATORS = (
    "internal trips only",
    "crossing trips at an internal trip's length",
    "crossing trips in full",
)


def _group(age: pd.Series, groups: tuple[tuple[int, int, str], ...]) -> pd.Series:
    out = pd.Series(pd.NA, index=age.index, dtype="string")
    for low, high, label in groups:
        out[(age >= low) & (age <= high)] = label
    return out


@cache
def involved_drivers() -> pd.DataFrame:
    """Car and taxi drivers in Barcelona crashes of 2025 with at least one casualty."""
    people = barcelona.read_people()
    crashes = barcelona.read_crashes()
    injury = crashes.loc[crashes.n_victims > 0, barcelona.KEY]
    drivers = people[
        (people.person_role == "driver")
        & people.Desc_Tipus_vehicle_implicat.isin((*CAR_TYPES, TAXI))
        & people[barcelona.KEY].isin(injury)
    ].copy()
    drivers["vehicle"] = np.where(drivers.Desc_Tipus_vehicle_implicat == TAXI, "taxi", "car")
    drivers["day_type"] = calendar.day_type(drivers.date)
    drivers["age4"] = _group(drivers.age, AGE_GROUPS)
    drivers["age_older"] = _group(drivers.age, OLDER_GROUPS)
    return drivers.reset_index(drop=True)


def counts_by_day_type() -> pd.DataFrame:
    """Car drivers involved, by age group and type of day, with the days of each type."""
    cars = involved_drivers()
    cars = cars[cars.vehicle == "car"]
    days = calendar.days_in_year(YEAR)
    rows = []
    for labels, column in ((AGE_GROUPS, "age4"), (OLDER_GROUPS, "age_older")):
        for _, _, label in labels:
            part = cars[cars[column] == label]
            for kind in calendar.DAY_TYPES:
                n = int((part.day_type == kind).sum())
                rows.append(
                    {"age": label, "day_type": kind, "drivers": n, "per_day": n / days[kind]}
                )
    unknown = cars[cars.age.isna()]
    for kind in calendar.DAY_TYPES:
        n = int((unknown.day_type == kind).sum())
        rows.append(
            {"age": "not recorded", "day_type": kind, "drivers": n, "per_day": n / days[kind]}
        )
    out = pd.DataFrame(rows)
    working = out[out.day_type == calendar.WORKING_DAY].set_index("age").per_day
    out["per_day_relative_to_working_day"] = out.per_day / out.age.map(working)
    return out


@cache
def city_person_day(years: tuple[int, ...] = exposure.CONTEMPORARY_YEARS) -> pd.DataFrame:
    """One row per EMEF respondent of ``years``: car-driver km on trips inside Barcelona, and the
    trips and km of trips with one end in the city."""
    trips = exposure.car_driver_trips()
    trips = trips[trips.year.isin(years)]
    origin = trips.origin_zone.eq(BARCELONA_ZONE).fillna(False)
    destination = trips.destination_zone.eq(BARCELONA_ZONE).fillna(False)
    internal = trips[origin & destination]
    crossing = trips[origin ^ destination]
    internal_mean = float(
        np.average(internal.km_road / internal.car_share, weights=internal.weight)
    )
    keys = ["year", "person_id"]
    sums = pd.concat(
        [
            internal.groupby(keys).km_road.sum().rename("internal_km"),
            crossing.groupby(keys).km_road.sum().rename("crossing_km"),
            crossing.assign(
                capped=np.minimum(crossing.km_road / crossing.car_share, internal_mean)
                * crossing.car_share
            )
            .groupby(keys)
            .capped.sum()
            .rename("crossing_capped_km"),
        ],
        axis=1,
    )
    people = exposure.person_day()
    people = people[people.year.isin(years)].reset_index(drop=True)
    out = people.merge(sums, on=keys, how="left")
    for column in ("internal_km", "crossing_km", "crossing_capped_km"):
        out[column] = out[column].fillna(0.0)
    out.attrs["internal_trip_mean_km"] = internal_mean
    return out


def _denominator_columns(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        DENOMINATORS[0]: frame.internal_km.to_numpy(),
        DENOMINATORS[1]: (frame.internal_km + frame.crossing_capped_km).to_numpy(),
        DENOMINATORS[2]: (frame.internal_km + frame.crossing_km).to_numpy(),
    }


def rates() -> pd.DataFrame:
    """Car drivers involved per billion working-day km inside Barcelona, by age group, under each
    denominator, with each group's ratio to drivers aged 45-64."""
    frame = city_person_day()
    n_years = frame.year.nunique()
    factors = exposure.replicate_factors(frame)
    weight = frame.weight.to_numpy() / n_years
    working_days = calendar.days_in_year(YEAR)[calendar.WORKING_DAY]
    drivers = involved_drivers()
    cars = drivers[(drivers.vehicle == "car") & (drivers.day_type == calendar.WORKING_DAY)]
    known = cars.age4.value_counts()
    unknown_share = float(cars.age.isna().mean())
    rng = np.random.default_rng(SEED)
    n_rep = factors.shape[1]
    labels = [label for _, _, label in AGE_GROUPS]
    count_draws = {label: rng.gamma(known.get(label, 0) + 0.5, 1.0, n_rep) for label in labels}
    rows = []
    for denominator, km in _denominator_columns(frame).items():
        point, replicate = {}, {}
        for label in labels:
            mask = (frame.age4 == label).to_numpy()
            w = weight[mask] * km[mask]
            yearly_km = working_days * float(w.sum())
            yearly_rep = working_days * (w @ factors[mask])
            n = float(known.get(label, 0))
            point[label] = n / yearly_km * BILLION
            replicate[label] = count_draws[label] / yearly_rep * BILLION
            rows.append(
                {
                    "denominator": denominator,
                    "age4": label,
                    "drivers_involved": int(n),
                    "drivers_allocated": n / (1 - unknown_share),
                    "billion_km": yearly_km / BILLION,
                    "rate_per_bn_km": point[label],
                    "rate_low": float(np.percentile(replicate[label], 2.5)),
                    "rate_high": float(np.percentile(replicate[label], 97.5)),
                    "rate_allocated_per_bn_km": point[label] / (1 - unknown_share),
                }
            )
        for row in rows[-len(labels) :]:
            label = row["age4"]
            ratio = replicate[label] / replicate[REFERENCE]
            row["ratio_to_45_64"] = point[label] / point[REFERENCE]
            row["ratio_low"] = float(np.percentile(ratio, 2.5))
            row["ratio_high"] = float(np.percentile(ratio, 97.5))
    out = pd.DataFrame(rows)
    out.attrs["unknown_age_share"] = unknown_share
    out.attrs["internal_trip_mean_km"] = frame.attrs["internal_trip_mean_km"]
    return out


def km_composition() -> pd.DataFrame:
    """Working-day car-driver km inside and into Barcelona per day, by age, with sample trips."""
    frame = city_person_day()
    n_years = frame.year.nunique()
    rows = []
    for label in [label for _, _, label in AGE_GROUPS]:
        part = frame[frame.age4 == label]
        w = part.weight / n_years
        rows.append(
            {
                "age4": label,
                "respondents": len(part),
                "respondents_with_internal_trip": int((part.internal_km > 0).sum()),
                "respondents_with_crossing_trip": int((part.crossing_km > 0).sum()),
                "internal_km_per_day": float((w * part.internal_km).sum()),
                "crossing_capped_km_per_day": float((w * part.crossing_capped_km).sum()),
                "crossing_km_per_day": float((w * part.crossing_km).sum()),
            }
        )
    out = pd.DataFrame(rows)
    for column in ("internal_km_per_day", "crossing_capped_km_per_day", "crossing_km_per_day"):
        out[column.replace("_per_day", "_share")] = out[column] / out[column].sum()
    return out
