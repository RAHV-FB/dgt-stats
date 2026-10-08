"""A working-day check in Barcelona city: crashes of 2025, driving of 2022-2024.

**Numerator.** Car drivers (``Turisme`` and ``Tot terreny``) involved in a crash recorded by the
Guàrdia Urbana in Barcelona in 2025 with at least one casualty (any injury, including people who
refused medical care), on a working day (:mod:`calendar`), by exact age. Taxis are left out, and
so are drivers of ordinary cars whose trip motive is recorded as ``Taxi`` (ride-hailing cars), as
in the national design. The person table lists every driver of a crash, uninjured drivers
included, in the 2024 and 2025 files only (earlier years list casualties only), and
:func:`involved_drivers` checks both that and that a driver row exists for nearly every vehicle.
The police record the age of 94% of the drivers on working days; the rest are almost all drivers
with no age, sex or injury recorded, probably drivers who were never identified.

The numerator also holds drivers the denominator does not count: drivers living outside the
province, traffic passing through the city without stopping, and drivers at work in ordinary
cars (emergency services, deliveries, staff on errands). These lean to working ages, so the
older drivers' ratio is biased downwards by an unknown amount. :func:`rates` also gives the
ratios with on-duty drivers left out and with crashes whose only casualties refused care left
out.

**Denominator.** Car-driver kilometres driven inside Barcelona on a working day by residents of
the survey area, from the EMEF 2022-2024 (:mod:`dgt_stats.emef.exposure`), times the 248 working
days of 2025. A trip with both ends in Barcelona is inside the city in full. A trip with one end in
the city is inside it only in part, and the public files give neither coordinates nor the
municipality at the other end, so that part cannot be measured. Three denominators span the
treatments of those crossing trips; they do not bound the kilometres of all drivers in the city,
because every one of them omits the traffic named above:

* ``internal trips only``: crossing trips count for nothing (the largest rates);
* ``crossing trips at an internal trip's length``: each crossing trip counts for the mean road
  length of a trip inside the city, or its own length if shorter;
* ``crossing trips in full``: every crossing trip counts in full (the smallest rates).

Only the ratio of each age group's rate to that of drivers aged 45-64 is read.

**Uncertainty.** Each interval combines the sampling error of the denominator (the EMEF
bootstrap replicates) with Poisson error in the count (a gamma draw per replicate), paired
replicate by replicate. Drivers whose age was not recorded are left out of the rates; the ratios
then assume their ages follow the recorded mix. :func:`unknown_age_bounds` gives the ratios if
they were all of one age group. ``rate_allocated_per_bn_km`` spreads them across ages in
proportion to those recorded.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd

from dgt_stats.emef import exposure, publication
from dgt_stats.exposure_risk import calendar
from dgt_stats.microdata import barcelona

CAR_TYPES = ("Turisme", "Tot terreny")
TAXI = "Taxi"
MOTIVE = "Descripcio_Motiu_desplacament_conductor"
# Trip motives of drivers at work in an ordinary car, whose working kilometres the EMEF does not
# record: left out in a sensitivity variant. "Taxi" on an ordinary car (ride-hailing) is always
# left out.
ON_DUTY_MOTIVES = (
    "Bombers, policia, ambulància",
    "En missió",
    "En pràctiques d'autoescola",
    "Transport professional de mercaderies",
    "Bus de línia regular",
)
REFUSED_CARE = "minor_refused_care"
MIN_UNINJURED_SHARE = 0.25
NUMERATORS = (
    "taxis and ride-hailing cars left out",
    "on-duty drivers also left out",
    "crashes whose only casualties refused care also left out",
)
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
    every_driver = people[people.person_role == "driver"]
    # Every driver is listed, injured or not, only if many drivers in crashes with a casualty are
    # uninjured (a file of casualties alone would have almost none) and nearly every vehicle of
    # those crashes has a driver row.
    in_injury = every_driver[every_driver[barcelona.KEY].isin(injury)]
    uninjured = float((in_injury.victimisation == "uninjured").mean())
    if uninjured < MIN_UNINJURED_SHARE:
        raise ValueError(f"Barcelona person file: {uninjured:.0%} uninjured drivers, not every one")
    per_crash = in_injury.groupby(barcelona.KEY).size()
    vehicles = crashes[crashes.n_victims > 0].set_index(barcelona.KEY)
    vehicles = vehicles.Numero_vehicles_implicats.astype(float)
    complete = float((per_crash.reindex(vehicles.index).fillna(0) == vehicles).mean())
    if complete < 0.95:
        raise ValueError(f"Barcelona person file: a driver row for every vehicle in {complete:.1%}")
    drivers = every_driver[
        every_driver.Desc_Tipus_vehicle_implicat.isin((*CAR_TYPES, TAXI))
        & every_driver[barcelona.KEY].isin(injury)
    ].copy()
    ride_hailing = drivers[MOTIVE].eq(TAXI)
    drivers["vehicle"] = np.where(
        (drivers.Desc_Tipus_vehicle_implicat == TAXI) | ride_hailing, "taxi", "car"
    )
    drivers["on_duty"] = drivers[MOTIVE].isin(ON_DUTY_MOTIVES)
    casualties = people[
        people[barcelona.KEY].isin(injury)
        & ~people.victimisation.isin(["uninjured", "not_recorded", "natural_death"])
    ]
    refused_only = casualties.groupby(barcelona.KEY).victimisation.agg(
        lambda v: bool((v == REFUSED_CARE).all())
    )
    drivers["refused_care_only"] = (
        drivers[barcelona.KEY].map(refused_only).fillna(False).astype(bool)
    )
    drivers["day_type"] = calendar.day_type(drivers.date)
    drivers["age4"] = _group(drivers.age, AGE_GROUPS)
    drivers["age_older"] = _group(drivers.age, OLDER_GROUPS)
    out = drivers.reset_index(drop=True)
    out.attrs["drivers_per_vehicle_complete"] = complete
    return out


def numerator(name: str = NUMERATORS[0]) -> pd.DataFrame:
    """The working-day car drivers counted under one of :data:`NUMERATORS`."""
    drivers = involved_drivers()
    cars = drivers[(drivers.vehicle == "car") & (drivers.day_type == calendar.WORKING_DAY)]
    if name in NUMERATORS[1:]:
        cars = cars[~cars.on_duty]
    if name == NUMERATORS[2]:
        cars = cars[~cars.refused_care_only]
    return cars


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
    denominator and numerator, with each group's ratio to drivers aged 45-64."""
    frame = city_person_day()
    n_years = frame.year.nunique()
    factors = exposure.replicate_factors(frame)
    weight = frame.weight.to_numpy() / n_years
    working_days = calendar.days_in_year(YEAR)[calendar.WORKING_DAY]
    labels = [label for _, _, label in AGE_GROUPS]
    n_rep = factors.shape[1]
    rows = []
    for name in NUMERATORS:
        cars = numerator(name)
        known = cars.age4.value_counts()
        unknown_share = float(cars.age.isna().mean())
        rng = np.random.default_rng(SEED)
        count_draws = {label: rng.gamma(known.get(label, 0) + 0.5, 1.0, n_rep) for label in labels}
        for denominator, km in _denominator_columns(frame).items():
            point, replicate = {}, {}
            block = []
            for label in labels:
                mask = (frame.age4 == label).to_numpy()
                w = weight[mask] * km[mask]
                yearly_km = working_days * float(w.sum())
                yearly_rep = working_days * (w @ factors[mask])
                n = float(known.get(label, 0))
                point[label] = n / yearly_km * BILLION
                replicate[label] = count_draws[label] / yearly_rep * BILLION
                block.append(
                    {
                        "numerator": name,
                        "denominator": denominator,
                        "age4": label,
                        "drivers_involved": int(n),
                        "drivers_age_not_recorded": int(cars.age.isna().sum()),
                        "drivers_allocated": n / (1 - unknown_share),
                        "billion_km": yearly_km / BILLION,
                        "rate_per_bn_km": point[label],
                        "rate_low": float(np.percentile(replicate[label], 2.5)),
                        "rate_high": float(np.percentile(replicate[label], 97.5)),
                        "rate_allocated_per_bn_km": point[label] / (1 - unknown_share),
                    }
                )
            for row in block:
                label = row["age4"]
                ratio = replicate[label] / replicate[REFERENCE]
                row["ratio_to_45_64"] = point[label] / point[REFERENCE]
                row["ratio_low"] = float(np.percentile(ratio, 2.5))
                row["ratio_high"] = float(np.percentile(ratio, 97.5))
            rows += block
    out = pd.DataFrame(rows)
    out.attrs["internal_trip_mean_km"] = frame.attrs["internal_trip_mean_km"]
    return out


def unknown_age_bounds() -> pd.DataFrame:
    """Ratios to 45-64 (central numerator, internal trips only) if every driver of unrecorded age
    were in one age group."""
    central = rates()
    central = central[
        (central.numerator == NUMERATORS[0]) & (central.denominator == DENOMINATORS[0])
    ].set_index("age4")
    unknown = float(central.drivers_age_not_recorded.iloc[0])
    rows = []
    for assigned in (None, *central.index):
        n = central.drivers_involved.astype(float).copy()
        if assigned is not None:
            n[assigned] += unknown
        rate = n / central.billion_km
        for label in central.index:
            rows.append(
                {
                    "unknown_age_assigned_to": assigned or "left out",
                    "age4": label,
                    "ratio_to_45_64": float(rate[label] / rate[REFERENCE]),
                }
            )
    return pd.DataFrame(rows)


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
    # The EMEF's publication rule: an estimate needs 20 respondents behind it.
    internal = ["internal_km_per_day", "internal_km_share"]
    crossing = [c for c in out.columns if c.startswith("crossing_")]
    out = publication.suppress_small_cells(out, "respondents_with_internal_trip", internal)
    return publication.suppress_small_cells(out, "respondents_with_crossing_trip", crossing)


def older_ratios() -> pd.DataFrame:
    """Ratios to 45-64 at 65-74 and 75 and over in the working-day design (central numerator),
    with the city's 65-and-over kilometres split by each national split (the Madrid survey's
    ratios, the RACC limit or licence holding, by sex) and the province's population at 65-74
    and 75 and over.

    Each has a 95% sampling interval: the city frame's EMEF bootstrap replicates, crossed with the
    Madrid survey's household replicates for the two Madrid splits, with gamma draws of the
    counts in every cell. The RACC constant and licence holding are held fixed."""
    from dgt_stats.exposure_risk import national

    frame = city_person_day()
    factors = exposure.replicate_factors(frame)
    weight = frame.weight.to_numpy() / frame.year.nunique()
    cars = numerator()
    counts = cars.age_older.value_counts()
    reference_n = float((cars.age4 == REFERENCE).sum())
    population = national.barcelona_older_population().set_index(["sex", "group"]).population
    n_rep = factors.shape[1]
    rows = []
    for denominator, km in _denominator_columns(frame).items():
        reference_mask = (frame.age4 == REFERENCE).to_numpy()
        reference_km = float((weight * km)[reference_mask].sum())
        reference_rep = (weight * km)[reference_mask] @ factors[reference_mask]
        km_65, km_65_rep = {}, {}
        for sex in national.SEXES:
            mask = ((frame.age4 == "65+") & (frame.sex == sex)).to_numpy()
            km_65[sex] = float((weight * km)[mask].sum())
            km_65_rep[sex] = (weight * km)[mask] @ factors[mask]
        for split in national.SPLITS:
            ratios = national._older_ratios()[split]
            replicates = national._split_replicates(split)
            point = {"65-74": 0.0, "75+": 0.0}
            draws = {"65-74": 0.0, "75+": 0.0}
            for sex in national.SEXES:
                young = population[(sex, "65-74")]
                old = population[(sex, "75+")] * ratios[sex]
                point["65-74"] += km_65[sex] * young / (young + old)
                point["75+"] += km_65[sex] * old / (young + old)
                r = replicates[sex]
                r = r[None, :] if np.ndim(r) else r
                old_rep = population[(sex, "75+")] * r
                share = old_rep / (young + old_rep)
                draws["75+"] = draws["75+"] + km_65_rep[sex][:, None] * share
                draws["65-74"] = draws["65-74"] + km_65_rep[sex][:, None] * (1 - share)
            shape = (n_rep, n_rep)
            rng = np.random.default_rng(SEED)
            reference = rng.gamma(reference_n + 0.5, 1.0, shape) / reference_rep[:, None]
            for group in OLDER_GROUPS:
                label = group[2]
                n = float(counts.get(label, 0))
                rate = n / point[label]
                ratio = rng.gamma(n + 0.5, 1.0, shape) / np.broadcast_to(draws[label], shape)
                ratio = ratio / reference
                rows.append(
                    {
                        "denominator": denominator,
                        "assumption": split,
                        "age": label,
                        "drivers_involved": int(n),
                        "ratio_to_45_64": rate / (reference_n / reference_km),
                        "ratio_low": float(np.percentile(ratio, 2.5)),
                        "ratio_high": float(np.percentile(ratio, 97.5)),
                        "sampling_sources": national._sampling_sources(
                            split, "EMEF (Barcelona city frame)"
                        ),
                    }
                )
    return pd.DataFrame(rows)
