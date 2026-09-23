"""Car-driver risk by age, per kilometre driven.

The question is whether older drivers are more dangerous, and the answer has always depended on
what it is divided by. Deaths per resident say no, because most people over 75 do not drive; deaths
per licence holder say a little; deaths per driver already in a crash say a great deal, but that is
a measure of what happens *after* the crash, not of how often one happens.

What was missing was kilometres. DGT's 2024 release of *Kilómetros anualizados recorridos por el
parque móvil* publishes vehicles and annual kilometres by vehicle category and by the owner's age
band. Paired with the car rows of DGT's driver tables for the same year it gives the two
quantities that matter, on the same bands, with the same construction for the middle-aged baseline
as for the older groups:

* **involvement per kilometre**: how often a driver of this age is in an injury crash per
  kilometre driven, which is about crashing;
* **fatality given involvement**: how often an involved driver of this age is killed, which is
  about what a crash does to a body.

Their product is driver deaths per kilometre. Separating them is the point: the two answers are
different, and the second is much larger than the first.

The denominator's own limit is that it is the *owner's* age, not the driver's, and that cars
registered to companies carry no age at all (``COMPANY_BAND``); ``company_km_sensitivity`` puts a
bound on what the second does to the comparison.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgt_stats import agebands, io_exposure, io_population, io_tables, rates

KM_YEAR = 2024
BILLION = 1e9

# The car rows of DGT's driver tables. Both publication spellings appear across the years.
CAR_VEHICLE_TYPES = (
    "TURISMO SIN REMOLQUE",
    "TURISMO CON REMOLQUE",
    "TURISMO DE SP HASTA 9 PLAZAS",
    "Turismo sin remolque",
    "Turismo con remolque",
    "Turismo de SP hasta 9 plazas",
)
# Bands compared on the page: everything the kilometre table can carry, 15-17 excepted.
COMPARED_BANDS = ("18-34", "35-54", "55-64", "65-74", "75+")
# INE publishes residents in five-year groups, so no resident count can be cut at 18; the
# four-denominator contrast therefore starts at 35, where every denominator is exact.
CONTRAST_BANDS = ("35-54", "55-64", "65-74", "75+")
REFERENCE_BAND = "35-54"


def car_driver_counts(year: int = KM_YEAR) -> pd.DataFrame:
    """Car drivers involved in injury crashes and killed within 30 days, by exposure band.

    Both zones and both sexes are summed. Drivers whose age the tables do not record (about 5 % of
    those involved and one of the deaths in 2024) have no band and are returned in the
    ``unknown`` row rather than silently dropped.
    """
    victims = io_tables.read_table("tables_driver_victims")
    involved = io_tables.read_table("tables_drivers_involved")
    victims = victims[(victims.year == year) & victims.vehicle_type.isin(CAR_VEHICLE_TYPES)]
    involved = involved[(involved.year == year) & involved.vehicle_type.isin(CAR_VEHICLE_TYPES)]
    if victims.empty or involved.empty:
        raise ValueError(f"car driver counts: no car rows for {year}")
    deaths = victims[victims.severity == "deaths_30d"]
    out = pd.DataFrame(
        {
            "driver_deaths": _by_exposure_band(deaths),
            "drivers_involved": _by_exposure_band(involved),
        }
    ).fillna(0.0)
    out.index.name = "band"
    return out.reset_index().astype({"band": "string"})


def _by_exposure_band(frame: pd.DataFrame) -> pd.Series:
    """Sum a driver table onto the exposure bands, keeping unknown age as its own row."""
    keys = [
        agebands.UNKNOWN
        if band == agebands.UNKNOWN
        else agebands.band_for(*agebands.DGT_BANDS[band], agebands.EXPOSURE_BANDS)
        if band in agebands.DGT_BANDS
        else None  # DGT's 0-14 row: below every band here, and empty in the car tables
        for band in frame.band
    ]
    tagged = frame.assign(exposure_band=pd.Series(keys, index=frame.index, dtype="object"))
    tagged = tagged[tagged.exposure_band.notna()]
    return tagged.groupby("exposure_band").value.sum()


def car_kilometres(year: int = KM_YEAR) -> pd.DataFrame:
    """Cars and annual kilometres by owner age band, plus the company-registered row."""
    km = io_exposure.read_exposure("km_edad_propietario_2024")
    cars = km[(km.vehicle_group == "car") & (km.year == year)]
    private = cars[~cars.is_company].groupby("band")[["n_vehicles", "total_km"]].sum()
    company = cars[cars.is_company][["n_vehicles", "total_km"]].sum()
    out = private.reindex(list(agebands.EXPOSURE_BANDS)).dropna(how="all")
    out.loc[COMPANY_BAND] = company
    out.index.name = "band"
    out = out.reset_index()
    out["share_of_km"] = out.total_km / out.total_km.sum()
    return out.astype({"band": "string", "n_vehicles": "int64", "total_km": "int64"})


COMPANY_BAND = "company"


def km_rates(year: int = KM_YEAR) -> pd.DataFrame:
    """The three rates, band by band: involvement per km, fatality given involvement, deaths per km.

    ``involved_per_bn_km`` and ``deaths_per_bn_km`` divide by the kilometres driven by cars whose
    registered owner is in the band; ``deaths_per_1000_involved`` divides by the drivers of that
    age already in an injury crash, so it needs no exposure at all and is the one rate here that
    the kilometre estimate cannot affect. Intervals are exact Poisson on the count, with the
    kilometres treated as known.
    """
    counts = car_driver_counts(year).set_index("band")
    km = car_kilometres(year).set_index("band")
    bands = [band for band in COMPARED_BANDS if band in km.index]
    out = pd.DataFrame({"band": bands})
    out["band_label"] = [agebands.band_label(band) for band in bands]
    out["drivers_involved"] = [float(counts.drivers_involved.get(b, np.nan)) for b in bands]
    out["driver_deaths"] = [float(counts.driver_deaths.get(b, np.nan)) for b in bands]
    out["n_cars"] = [float(km.n_vehicles.get(b, np.nan)) for b in bands]
    out["billion_km"] = [float(km.total_km.get(b, np.nan)) / BILLION for b in bands]
    out["mean_km_per_car"] = out.billion_km * BILLION / out.n_cars
    out = rates.add_rate(out, "drivers_involved", "billion_km", "involved_per_bn_km", per=1)
    out = rates.add_rate(out, "driver_deaths", "billion_km", "deaths_per_bn_km", per=1)
    out = rates.add_rate(
        out, "driver_deaths", "drivers_involved", "deaths_per_1000_involved", per=1000
    )
    return out


RATE_DEFINITIONS = {
    "involved_per_bn_km": ("drivers_involved", "billion_km"),
    "deaths_per_1000_involved": ("driver_deaths", "drivers_involved"),
    "deaths_per_bn_km": ("driver_deaths", "billion_km"),
}
RATE_LABELS = {
    "involved_per_bn_km": "Drivers involved in an injury crash, per billion km",
    "deaths_per_1000_involved": "Drivers killed per 1,000 drivers involved",
    "deaths_per_bn_km": "Drivers killed per billion km",
}


def km_rate_ratios(year: int = KM_YEAR) -> pd.DataFrame:
    """Each band against the 35–54 baseline, for each of the three rates, with 95 % intervals."""
    frame = km_rates(year).set_index("band")
    reference = frame.loc[REFERENCE_BAND]
    records = []
    for measure, (count, exposure) in RATE_DEFINITIONS.items():
        for band, row in frame.iterrows():
            ratio, low, high = rates.rate_ratio(
                row[count], row[exposure], reference[count], reference[exposure]
            )
            records.append(
                {
                    "measure": measure,
                    "measure_label": RATE_LABELS[measure],
                    "band": band,
                    "band_label": agebands.band_label(band),
                    "is_reference": band == REFERENCE_BAND,
                    "ratio": ratio,
                    "low": low,
                    "high": high,
                }
            )
    return pd.DataFrame.from_records(records)


def company_km_sensitivity(year: int = KM_YEAR) -> pd.DataFrame:
    """What the kilometres of company-registered cars could do to the comparison.

    Company cars have no owner age, so they leave the denominator; their drivers do not leave the
    numerator. Three treatments bound the effect: leaving those kilometres out (the published
    rates), spreading them over the bands from 18 to 64 in proportion to their private kilometres
    (the assumption that a company car is driven by someone of working age) and spreading them
    over every band. The first two bracket the answer and the third is the neutral case.
    """
    counts = car_driver_counts(year).set_index("band")
    km = car_kilometres(year).set_index("band")
    company_km = float(km.total_km.get(COMPANY_BAND, 0.0))
    bands = [band for band in COMPARED_BANDS if band in km.index]
    base = pd.Series({band: float(km.total_km[band]) for band in bands})
    working = [band for band in bands if band in ("18-34", "35-54", "55-64")]
    allocations = {
        "excluded": pd.Series(0.0, index=base.index),
        "to_working_age": company_km
        * base[working].reindex(base.index).fillna(0.0)
        / base[working].sum(),
        "to_all_bands": company_km * base / base.sum(),
    }
    labels = {
        "excluded": "Company kilometres left out (published)",
        "to_working_age": "Company kilometres spread over 18–64",
        "to_all_bands": "Company kilometres spread over every band",
    }
    records = []
    for key, extra in allocations.items():
        exposure = base + extra
        reference_deaths = float(counts.driver_deaths[REFERENCE_BAND])
        for band in bands:
            ratio, low, high = rates.rate_ratio(
                float(counts.driver_deaths[band]),
                exposure[band],
                reference_deaths,
                exposure[REFERENCE_BAND],
            )
            records.append(
                {
                    "allocation": key,
                    "allocation_label": labels[key],
                    "band": band,
                    "band_label": agebands.band_label(band),
                    "billion_km": exposure[band] / BILLION,
                    "deaths_per_bn_km": float(counts.driver_deaths[band])
                    / (exposure[band] / BILLION),
                    "ratio_to_reference": ratio,
                    "low": low,
                    "high": high,
                }
            )
    return pd.DataFrame.from_records(records)


def denominator_contrast(year: int = KM_YEAR) -> pd.DataFrame:
    """The same car-driver deaths against four denominators, as ratios to the 35–54 baseline.

    Residents and licence holders are the denominators DGT and the press use; drivers involved is
    the one that isolates what happens after a crash; kilometres is the one that answers the
    question actually being asked. The four are shown together once, because the point is that the
    answer moves, and then the page uses kilometres.
    """
    counts = car_driver_counts(year).set_index("band")
    km = car_kilometres(year).set_index("band")
    resident_bands = {band: agebands.EXPOSURE_BANDS[band] for band in CONTRAST_BANDS}
    residents = io_population.population_by_band(year, bands=resident_bands).set_index("band")
    licences = io_exposure.read_exposure("conductores_por_edad")
    licences = licences[(licences.year == year) & (licences.sex == "total")]
    keys = [
        agebands.band_for(*agebands.DGT_BANDS[band], agebands.EXPOSURE_BANDS)
        if band in agebands.DGT_BANDS
        else None
        for band in licences.band
    ]
    licences = licences.assign(exposure_band=pd.Series(keys, index=licences.index, dtype="object"))
    licence_holders = (
        licences.dropna(subset=["exposure_band"]).groupby("exposure_band").n_drivers.sum()
    )
    bands = [band for band in CONTRAST_BANDS if band in km.index]
    exposures = {
        "residents": {b: float(residents.population.get(b, np.nan)) for b in bands},
        "licence_holders": {b: float(licence_holders.get(b, np.nan)) for b in bands},
        "drivers_involved": {b: float(counts.drivers_involved.get(b, np.nan)) for b in bands},
        "kilometres": {b: float(km.total_km.get(b, np.nan)) for b in bands},
    }
    # Short enough to sit over a panel; the caption and the methodology say what each one is.
    labels = {
        "residents": "Per resident",
        "licence_holders": "Per licence holder",
        "drivers_involved": "Per driver involved",
        "kilometres": "Per kilometre driven",
    }
    records = []
    for key, exposure in exposures.items():
        for band in bands:
            ratio, low, high = rates.rate_ratio(
                float(counts.driver_deaths[band]),
                exposure[band],
                float(counts.driver_deaths[REFERENCE_BAND]),
                exposure[REFERENCE_BAND],
            )
            records.append(
                {
                    "denominator": key,
                    "denominator_label": labels[key],
                    "band": band,
                    "band_label": agebands.band_label(band),
                    "driver_deaths": float(counts.driver_deaths[band]),
                    "exposure": exposure[band],
                    "ratio": ratio,
                    "low": low,
                    "high": high,
                }
            )
    return pd.DataFrame.from_records(records)
