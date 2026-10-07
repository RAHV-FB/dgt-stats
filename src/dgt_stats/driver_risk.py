"""Car-driver crashes and deaths by age and sex, against the denominators the repository holds.

Age, 2024. DGT's driver tables give, by the driver's age band, car drivers involved in injury
crashes (table 4.2) and car drivers killed within 30 days (table 4.1.1). Two kinds of rate follow:

* **drivers killed per 1,000 drivers involved**: numerator and denominator are the same drivers, by
  the same age, in the same year, so it needs no exposure;
* **drivers involved, and drivers killed, per billion km driven by cars registered to owners of
  this age**: the kilometres are DGT's *Kilómetros anualizados recorridos por el parque móvil*
  2024 by the registered owner's age band. Their product with the first is the second.

The kilometres are the *owner's* age, not the driver's, and cars registered to companies carry no
age at all (``COMPANY_BAND``). ``owner_age_check`` shows where owner and driver diverge and
recomputes every per-km ratio under a transfer scenario, and ``company_km_sensitivity`` does the
same for company cars, so the per-km ratios are read as ranges rather than points.

The bands are ``agebands.EXPOSURE_BANDS``: 18-24 and 25-34 apart, 35-54 as the reference, then
55-64, 65-74 and 75 and over. Every source cuts at those ages, except INE's residents, whose
five-year groups start a band at 15 and 20; the per-resident comparison therefore starts at 25.

Sex, 2014–2024. The same tables by sex, against licence holders from the driver census. No file in
the repository measures driving by sex, so the sex rates are per licence holder and per driver
involved, never per kilometre.
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
COMPARED_BANDS = ("18-24", "25-34", "35-54", "55-64", "65-74", "75+")
# INE publishes residents in five-year groups (15-19, 20-24, ...), so no resident count can be cut
# at 18; the four-denominator contrast therefore starts at 25, where every denominator is exact.
CONTRAST_BANDS = ("25-34", "35-54", "55-64", "65-74", "75+")
REFERENCE_BAND = "35-54"
# The bands whose driving the owner-age kilometres may credit to older owners (owner_age_check).
TRANSFER_BANDS = ("18-24", "25-34")


def car_driver_counts(year: int = KM_YEAR) -> pd.DataFrame:
    """Car drivers involved in injury crashes and killed within 30 days, by exposure band.

    Both zones and both sexes are summed. Drivers whose age the tables do not record (2,243 of
    the 100,660 car drivers involved in 2024, 2.2 %, and one of the 495 deaths; 2.0 % and 2.3 %
    of those involved in 2022 and 2023) have no band and are returned in the ``unknown`` row
    rather than silently dropped.
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
    private = cars[~cars.is_company]
    private = private.assign(band=private.band.map(_exposure_band_key))
    private = private.groupby("band")[["n_vehicles", "total_km"]].sum()
    company = cars[cars.is_company][["n_vehicles", "total_km"]].sum()
    out = private.reindex(list(agebands.EXPOSURE_BANDS)).dropna(how="all")
    out.loc[COMPANY_BAND] = company
    out.index.name = "band"
    out = out.reset_index()
    out["share_of_km"] = out.total_km / out.total_km.sum()
    return out.astype({"band": "string", "n_vehicles": "int64", "total_km": "int64"})


COMPANY_BAND = "company"


def km_rates(year: int = KM_YEAR) -> pd.DataFrame:
    """The three rates, band by band: involvement per km, deaths per driver involved, deaths per km.

    ``involved_per_bn_km`` and ``deaths_per_bn_km`` divide by the kilometres driven by cars whose
    registered owner is in the band, which is not the distance driven by drivers of that age;
    ``deaths_per_1000_involved`` divides by the drivers of that age already in an injury crash, so
    it needs no exposure at all and is the one rate here that the kilometres cannot affect.
    Intervals are exact Poisson on the count, with the kilometres treated as known.
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
# What each per-km rate divides by, said exactly: the kilometres are the owner's age band's.
OWNER_KM = "per billion km driven by cars registered to owners of this age"
RATE_LABELS = {
    "involved_per_bn_km": f"Drivers involved in an injury crash, {OWNER_KM}",
    "deaths_per_1000_involved": "Drivers killed per 1,000 drivers involved",
    "deaths_per_bn_km": f"Drivers killed, {OWNER_KM}",
}
# The measures whose denominator is the owner-age kilometres.
KM_MEASURES = tuple(m for m, (_, exposure) in RATE_DEFINITIONS.items() if exposure == "billion_km")


def km_rate_ratios(year: int = KM_YEAR, reference_band: str = REFERENCE_BAND) -> pd.DataFrame:
    """Each band against a reference band (35–54 unless named), for each of the three rates, with
    95 % intervals.

    The three rates chain: involvement per kilometre times deaths per driver involved is deaths
    per kilometre, so for every band the first two ratios multiply to the third. These are the
    published per-km ratios; ``owner_age_check`` gives them under the transfer scenario too.
    """
    frame = km_rates(year).set_index("band")
    reference = frame.loc[reference_band]
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
                    "is_reference": band == reference_band,
                    "ratio": ratio,
                    "low": low,
                    "high": high,
                }
            )
    return pd.DataFrame.from_records(records)


def _exposure_band_key(band: str) -> str | None:
    if band not in agebands.DGT_BANDS:
        return None
    return agebands.band_for(*agebands.DGT_BANDS[band], agebands.EXPOSURE_BANDS)


def _on_exposure_bands(frame: pd.DataFrame, column: str) -> pd.Series:
    """Sum a census frame (fine DGT bands) onto the exposure bands; unknown and 15-17 drop out."""
    keyed = frame.assign(exposure_band=frame.band.map(_exposure_band_key))
    keyed = keyed[keyed.exposure_band.notna()]
    return keyed.groupby("exposure_band")[column].sum().astype(float)


def licence_holders(year: int = KM_YEAR) -> pd.Series:
    """Holders of a licence of any class, by exposure band (the census total)."""
    licences = io_exposure.read_exposure("conductores_por_edad")
    licences = licences[(licences.year == year) & (licences.sex == "total")]
    return _on_exposure_bands(licences, "n_drivers")


def b_permit_holders(year: int = KM_YEAR) -> pd.Series:
    """Holders of a B (car) permit, by exposure band: the population licensed to drive a car."""
    permits = io_exposure.b_permit_holders_by_age(year)
    return _on_exposure_bands(permits[permits.sex == "total"], "n_b_permit_holders")


def owner_age_check(year: int = KM_YEAR) -> pd.DataFrame:
    """How far the owner's age can stand for the driver's, and every per-km ratio under one
    scenario for the gap.

    One row per band: licence holders of any class and B-permit holders (the car licence), the
    cars and kilometres registered to owners of that age, and cars and kilometres per holder. If
    every car were registered to the person who drives it, cars per B-permit holder would say how
    many cars each driver has; the 18–24 and 25–34 bands have far fewer cars and kilometres per
    holder than 35–54, and owners aged 75 and over can hold more cars than there are B-permit
    holders of that age, so neither end of the age range drives only the kilometres credited to it.

    ``transfer_bn_km`` is a scenario, not an estimate: kilometres move from the 35–54 reference
    band to 18–24 and 25–34 until the three bands drive the same distance per B-permit holder, as
    if the whole gap were young drivers' driving registered to owners aged 35–54. The data say
    neither how much of the gap that is nor which older band holds it. For every band and measure
    the table gives the published ratio to 35–54 (``{measure}_ratio``, ``_low``, ``_high``) and the
    ratio under the scenario (``{measure}_ratio_transfer``, ``_low_transfer``, ``_high_transfer``),
    each with a 95 % interval that treats the kilometres as known, and for the per-km measures the
    two ratios in ascending order (``{measure}_range_low``, ``{measure}_range_high``). Deaths per
    1,000 involved need no kilometres and are the same under both. The scenario moves no
    kilometres of 55–64, 65–74 or 75+, so ratios among those three bands are the same under both.
    """
    rates_frame = km_rates(year).set_index("band")
    bands = list(rates_frame.index)
    out = pd.DataFrame(index=pd.Index(bands, name="band"))
    out["band_label"] = rates_frame.band_label
    out["licence_holders"] = licence_holders(year).reindex(bands)
    out["b_permit_holders"] = b_permit_holders(year).reindex(bands)
    out["b_permit_share"] = out.b_permit_holders / out.licence_holders
    out["cars"] = rates_frame.n_cars
    out["billion_km"] = rates_frame.billion_km
    out["drivers_involved"] = rates_frame.drivers_involved
    out["driver_deaths"] = rates_frame.driver_deaths
    out["cars_per_licence"] = out.cars / out.licence_holders
    out["km_per_licence"] = out.billion_km * BILLION / out.licence_holders
    out["cars_per_b_permit"] = out.cars / out.b_permit_holders
    out["km_per_b_permit"] = out.billion_km * BILLION / out.b_permit_holders
    # The transfers that equalise km per B-permit holder across the young bands and the
    # reference: every band in the pool ends at the pool's own km per holder, each young band
    # gaining what it lacks and the reference giving up the sum.
    pool = [*TRANSFER_BANDS, REFERENCE_BAND]
    per_holder = out.loc[pool, "billion_km"].sum() / out.loc[pool, "b_permit_holders"].sum()
    out["transfer_bn_km"] = 0.0
    for band in TRANSFER_BANDS:
        out.loc[band, "transfer_bn_km"] = (
            per_holder * out.loc[band, "b_permit_holders"] - out.loc[band, "billion_km"]
        )
    out.loc[REFERENCE_BAND, "transfer_bn_km"] = -out.loc[
        list(TRANSFER_BANDS), "transfer_bn_km"
    ].sum()
    out["billion_km_transfer"] = out.billion_km + out.transfer_bn_km
    for measure, (count, exposure) in RATE_DEFINITIONS.items():
        variants = {"": exposure}
        if measure in KM_MEASURES:
            variants["_transfer"] = "billion_km_transfer"
        for suffix, column in variants.items():
            reference = out.loc[REFERENCE_BAND]
            triples = [
                rates.rate_ratio(
                    float(out.loc[band, count]),
                    float(out.loc[band, column]),
                    float(reference[count]),
                    float(reference[column]),
                )
                for band in bands
            ]
            for position, name in enumerate(("ratio", "low", "high")):
                out[f"{measure}_{name}{suffix}"] = [triple[position] for triple in triples]
        if measure in KM_MEASURES:
            pair = out[[f"{measure}_ratio", f"{measure}_ratio_transfer"]]
            out[f"{measure}_range_low"] = pair.min(axis=1)
            out[f"{measure}_range_high"] = pair.max(axis=1)
    return out.reset_index()


COMPANY_ALLOCATION_LABELS = {
    "excluded": "Company kilometres left out (published)",
    "to_working_age": "Scenario: company kilometres spread over 18–64",
    "to_all_bands": "Scenario: company kilometres spread over every band",
}


def company_km_sensitivity(year: int = KM_YEAR) -> pd.DataFrame:
    """What the kilometres of company-registered cars could do to the deaths-per-km ratios.

    Company cars have no owner age, so they leave the denominator; their drivers, whatever their
    age, stay in the numerator. Three treatments: leaving those kilometres out (the published
    rates) and two scenarios, spreading them over the bands from 18 to 64 in proportion to their
    private kilometres, or over every band. The data hold no driver age for company cars, so
    neither scenario is an estimate. Spreading over every band in proportion changes no ratio
    between bands; spreading over 18–64 adds kilometres to the 35–54 reference and none to 65 and
    over, so it raises the older bands' ratios by arithmetic.
    """
    counts = car_driver_counts(year).set_index("band")
    km = car_kilometres(year).set_index("band")
    company_km = float(km.total_km.get(COMPANY_BAND, 0.0))
    bands = [band for band in COMPARED_BANDS if band in km.index]
    base = pd.Series({band: float(km.total_km[band]) for band in bands})
    working = [band for band in bands if band in ("18-24", "25-34", "35-54", "55-64")]
    allocations = {
        "excluded": pd.Series(0.0, index=base.index),
        "to_working_age": company_km
        * base[working].reindex(base.index).fillna(0.0)
        / base[working].sum(),
        "to_all_bands": company_km * base / base.sum(),
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
                    "allocation_label": COMPANY_ALLOCATION_LABELS[key],
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


CONTRAST_LABELS = {
    "residents": "Per resident",
    "b_permit_holders": "Per B-permit holder",
    "drivers_involved": "Per driver involved",
    "kilometres": "Per km driven by cars registered to owners of this age",
}


def denominator_contrast(year: int = KM_YEAR) -> pd.DataFrame:
    """The same car-driver deaths against four denominators, as ratios to the 35–54 baseline.

    Residents (INE, 1 July) and B-permit holders (the census) are populations, not exposure;
    drivers involved isolates what follows a crash; kilometres are those driven by cars registered
    to owners of the band, with the owner-age limits of ``owner_age_check``. The numerator is the
    same in every panel, so only the denominator moves.
    """
    counts = car_driver_counts(year).set_index("band")
    km = car_kilometres(year).set_index("band")
    resident_bands = {band: agebands.EXPOSURE_BANDS[band] for band in CONTRAST_BANDS}
    residents = io_population.population_by_band(year, bands=resident_bands).set_index("band")
    holders = b_permit_holders(year)
    bands = [band for band in CONTRAST_BANDS if band in km.index]
    exposures = {
        "residents": {b: float(residents.population.get(b, np.nan)) for b in bands},
        "b_permit_holders": {b: float(holders.get(b, np.nan)) for b in bands},
        "drivers_involved": {b: float(counts.drivers_involved.get(b, np.nan)) for b in bands},
        "kilometres": {b: float(km.total_km.get(b, np.nan)) for b in bands},
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
                    "denominator_label": CONTRAST_LABELS[key],
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


# --------------------------------------------------------------------------- sex


SEX_BANDS = ("18-24", "25-34", "35-54", "55-64", "65-74", "75+")
ADULT_BAND = "18+"
# Three years pooled, so that the rates for women over 65, a few deaths a year, are readable.
SEX_POOL_YEARS = (2022, 2023, 2024)
SEX_LABELS = {"male": "Men", "female": "Women"}
VEHICLE_SCOPES = {"motor": "Drivers of motor vehicles", "car": "Car drivers"}
# Rows of DGT's driver tables that are not a licensed motor vehicle: cyclists and personal
# mobility vehicles need no licence, and the rest are not vehicles or not known.
NOT_MOTOR = frozenset(
    {
        "bicicleta",
        "vmp",
        "peatón",
        "tren/metro/tranvía",
        "tren/metro",
        "tranvía",
        "se desconoce",
        "sin especificar",
        "otras categorías",
        "total",
    }
)
SEX_MEASURES = {
    "involved_per_1000_licences": ("drivers_involved", "licence_holder_years", 1000),
    "deaths_per_million_licences": ("driver_deaths", "licence_holder_years", 1e6),
    "deaths_per_1000_involved": ("driver_deaths", "drivers_involved", 1000),
}
SEX_MEASURE_LABELS = {
    "involved_per_1000_licences": "Involved in an injury crash, per 1,000 licence holders",
    "deaths_per_million_licences": "Killed, per million licence holders",
    "deaths_per_1000_involved": "Killed, per 1,000 drivers involved",
}


def _in_scope(vehicle_type: pd.Series, scope: str) -> pd.Series:
    if scope == "car":
        return vehicle_type.isin(CAR_VEHICLE_TYPES)
    return ~vehicle_type.str.casefold().isin(NOT_MOTOR)


def driver_counts_by_sex(years: tuple[int, ...], scope: str) -> pd.DataFrame:
    """Drivers involved and killed, and licence holders, by sex and exposure band, summed over years.

    Licence holders summed over the years are licence-holder-years, the denominator for a pooled
    rate. They are holders of a licence of any class (the census total) in both scopes: B-permit
    holders by sex and age exist only from 2021 (published tables) and 2023 (text files), so the
    2014–2024 series cannot use them. The numerator counts every driver involved, including
    unlicensed and foreign drivers. Drivers whose sex or age the tables do not record are left
    out (in 2022–2024, under 1 % and about 2 % of car drivers involved).
    """
    victims = io_tables.read_table("tables_driver_victims")
    involved = io_tables.read_table("tables_drivers_involved")
    licences = io_exposure.read_exposure("conductores_por_edad")
    victims = victims[
        victims.year.isin(years)
        & (victims.severity == "deaths_30d")
        & _in_scope(victims.vehicle_type, scope)
    ]
    involved = involved[involved.year.isin(years) & _in_scope(involved.vehicle_type, scope)]
    licences = licences[licences.year.isin(years)]
    frames = {}
    for name, frame, value in (
        ("driver_deaths", victims, "value"),
        ("drivers_involved", involved, "value"),
        ("licence_holder_years", licences, "n_drivers"),
    ):
        keyed = frame.assign(exposure_band=frame.band.map(_exposure_band_key))
        keyed = keyed[keyed.sex.isin(SEX_LABELS) & keyed.exposure_band.isin(SEX_BANDS)]
        frames[name] = keyed.groupby(["sex", "exposure_band"])[value].sum()
    out = pd.DataFrame(frames).fillna(0.0)
    out.index.names = ["sex", "band"]
    adult = out.groupby(level="sex").sum()
    adult.index = pd.MultiIndex.from_product([adult.index, [ADULT_BAND]], names=["sex", "band"])
    return pd.concat([out, adult]).reset_index()


def sex_age_rates(years: tuple[int, ...] = SEX_POOL_YEARS) -> pd.DataFrame:
    """The three driver rates by sex and age band, for motor-vehicle drivers and car drivers."""
    frames = []
    for scope, scope_label in VEHICLE_SCOPES.items():
        counts = driver_counts_by_sex(years, scope)
        for measure, (count, exposure, per) in SEX_MEASURES.items():
            counts = rates.add_rate(counts, count, exposure, measure, per=per)
        counts.insert(0, "scope", scope)
        counts.insert(1, "scope_label", scope_label)
        counts["sex_label"] = counts.sex.map(SEX_LABELS)
        counts["band_label"] = [
            "18 and over" if band == ADULT_BAND else agebands.band_label(band)
            for band in counts.band
        ]
        counts["years"] = f"{min(years)}-{max(years)}"
        frames.append(counts)
    return pd.concat(frames, ignore_index=True)


def sex_ratios(years: tuple[int, ...] = SEX_POOL_YEARS) -> pd.DataFrame:
    """Men against women on each measure, by band, with 95 % log-normal intervals."""
    table = sex_age_rates(years).set_index(["scope", "band", "sex"])
    records = []
    for scope, scope_label in VEHICLE_SCOPES.items():
        for band in (*SEX_BANDS, ADULT_BAND):
            men, women = table.loc[(scope, band, "male")], table.loc[(scope, band, "female")]
            for measure, (count, exposure, _) in SEX_MEASURES.items():
                ratio, low, high = rates.rate_ratio(
                    float(men[count]),
                    float(men[exposure]),
                    float(women[count]),
                    float(women[exposure]),
                )
                records.append(
                    {
                        "scope": scope,
                        "scope_label": scope_label,
                        "band": band,
                        "band_label": men.band_label,
                        "measure": measure,
                        "measure_label": SEX_MEASURE_LABELS[measure],
                        "ratio": ratio,
                        "low": low,
                        "high": high,
                    }
                )
    return pd.DataFrame.from_records(records)


def sex_trend(first: int = 2014, last: int = KM_YEAR) -> pd.DataFrame:
    """The three rates for drivers aged 18 and over, by sex and year, for both scopes."""
    frames = []
    for year in range(first, last + 1):
        table = sex_age_rates((year,))
        table = table[table.band == ADULT_BAND].assign(year=year)
        frames.append(table)
    return pd.concat(frames, ignore_index=True)
