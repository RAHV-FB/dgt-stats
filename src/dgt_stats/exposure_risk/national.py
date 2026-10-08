"""Spain: car-driving kilometres by driver age, and car drivers involved in injury crashes per
kilometre (Tasks 14-17).

No national source measures kilometres by the driver's age, so four methods are compared.

* **A, demographic calibration.** The EMEF's working-day car-driver km per resident by age group
  and sex (province of Barcelona, 2022-2024) is applied to the population of Spain on 1 July 2024
  (INE, single years of age). This gives each age group's share of driving, assuming that, within
  an age group and sex, residents of Spain drive in the same proportion to one another as
  residents of the province of Barcelona.
* **A2, licence-calibrated transfer.** Method A, but carrying over the km per B-licence holder
  instead of per resident: each group's EMEF km per resident is scaled by the ratio of Spain's
  B-licence prevalence to the province's (DGT driver census 2024, INE population), by sex. Young
  residents of the province hold car licences less often than Spain's, so A2 gives Spain's young
  drivers more of the kilometres than A does.
* **B, kilometre scale.** Those shares are applied to DGT's 2024 total of car kilometres
  (inspection odometer readings, annualised), less taxi and ride-hailing cars, whose drivers drive
  for a living and are outside both the EMEF and the crash numerator used here. The level of the
  rates depends on B; their ratios between ages do not.
* **C, regional calibration.** Method A repeated with the age profile of each part of the province
  (Barcelona city, the rest of the metropolitan area, the rest of the metropolitan region and the
  rest of the province) and with the Madrid household survey of 2018 (:mod:`dgt_stats.edm2018`).
* **D, registered owners.** DGT's 2024 kilometres by the registered owner's age band, the
  denominator of the former driver-age figure. Cars are driven by people other than their owners
  and company cars carry no age, so D is a comparison only.

**Sensitivity.** :func:`sensitivity` recomputes the ratios under every alternative: the regional
profiles (C), the licence-calibrated transfer (A2), the distance treatments of
:data:`dgt_stats.emef.exposure.TRIP_VARIANTS` and the band midpoints, the survey years,
professionals' unrecorded work driving, the older sample's employment set to the census, and the
age mix of non-working days. The spread is reported as a sensitivity range beside the sampling
interval, never as a confidence interval.

**Numerator.** Car drivers involved in injury crashes in Spain in 2024 (DGT, tables 4.2 I and U),
private cars with and without trailer; drivers of public-service cars (taxi and ride-hailing) are
left out to match the denominator. The EMEF group 16-29 is matched to drivers aged 18-29: residents
aged 16 and 17 count in its population but cannot hold a car licence, and the 41 drivers aged
15-17 in the tables are left out. Drivers of unrecorded age (2.3% of those involved) are left out
of every rate; the ratios between ages are unchanged by that only if their ages follow the recorded
mix (:func:`unknown_age_bounds` gives the ratios if they were all of one age group).

**Uncertainty.** Each interval pairs the EMEF bootstrap replicates (sampling error of the
exposure shares) with gamma draws for the counts (Poisson error), replicate by replicate. The
spread between methods and variants is reported separately, as a sensitivity range.

**Ages 75 and over.** The EMEF stops at 65 and over. :func:`older_split` divides that group's
km between 65-74 and 75 and over using the ratio of their km per resident in the Madrid survey,
by sex, and the population of each age in the province of Barcelona and in Spain. It is a
*model-dependent* estimate, reported beside the measured 65-and-over figure and never in its
place, with two alternatives: equal km per licence holder at 65-74 and 75 and over (an upper
bound for 75 and over's km), and the Madrid km per licence holder applied to Spain's licence
holders. :func:`older_sensitivity` repeats the split under every 65-and-over variant of
:func:`sensitivity`.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd

from dgt_stats import edm2018, io_exposure, io_population, io_tables
from dgt_stats.emef import exposure
from dgt_stats.paths import RAW_DATA_DIR

YEAR = 2024
REFERENCE_DATE = "1 July"
BILLION = 1e9
SEED = 20261008
SEXES = ("male", "female")
GROUPS = ("16-29", "30-44", "45-64", "65+")
OLDER = ("65-74", "75+")
REFERENCE = "45-64"
GROUP_AGES: dict[str, tuple[int, int]] = {
    "16-29": (16, 29),
    "30-44": (30, 44),
    "45-64": (45, 64),
    "65+": (65, 200),
    "65-74": (65, 74),
    "75+": (75, 200),
}
# DGT driver-table bands summed into each group (the EMEF's 16-29 is matched to drivers 18-29).
NUMERATOR_BANDS: dict[str, tuple[str, ...]] = {
    "16-29": ("18-20", "21-24", "25-29"),
    "30-44": ("30-34", "35-39", "40-44"),
    "45-64": ("45-49", "50-54", "55-59", "60-64"),
    "65+": ("65-69", "70-74", "75+"),
    "65-74": ("65-69", "70-74"),
    "75+": ("75+",),
}
PRIVATE_CARS = ("Turismo sin remolque", "Turismo con remolque")
PUBLIC_SERVICE_CARS = ("Turismo de SP hasta 9 plazas",)
BARCELONA_PROVINCE = "08"
KM_SERVICE_PATH = RAW_DATA_DIR / "dgt" / "km_itv_2024" / "km_servicio_2024.xlsx"
# Service classes of DGT's kilometre table: taxi (A04) and car hire with driver (A02, the
# ride-hailing licences) are driven for a living; car hire without driver (A01) and driving
# schools (A03) are driven by ordinary drivers and learners, and are removed only in a variant.
PROFESSIONAL_SERVICES = ("A04", "A02")
RENTAL_AND_SCHOOL_SERVICES = ("A01", "A03")


# ----------------------------------------------------------------------------- population


@cache
def single_age_population(year: int = YEAR, reference: str = REFERENCE_DATE) -> pd.DataFrame:
    """Residents of Spain by single year of age (105 = 105 and over) and sex."""
    raw = pd.read_csv(RAW_DATA_DIR / "ine" / "ine_poblacion_edad_simple_sexo.csv")
    raw = raw[(raw.year == year) & (raw.reference == reference)]
    # Keep single years and the open "105 y más"; drop the totals and the overlapping
    # aggregates "85 y más" and "100 y más".
    raw = raw[raw.age.str.match(r"^\d+ años?$") | (raw.age == "105 y más años")]
    sexes = {"Hombres": "male", "Mujeres": "female", "Total": "total"}
    out = pd.DataFrame(
        {
            "age": raw.age.str.extract(r"^(\d+)")[0].astype(int).to_numpy(),
            "sex": raw.sex.map(sexes).to_numpy(),
            "population": raw.population.astype(float).to_numpy(),
        }
    )
    total = out[out.sex == "total"].population.sum()
    parts = out[out.sex != "total"].population.sum()
    if abs(total - parts) > 100 or out.duplicated(["age", "sex"]).any():
        raise ValueError("single-age population: duplicated ages, or sexes not adding up")
    if not (out[out.sex == "total"].age.sort_values().to_numpy() == np.arange(106)).all():
        raise ValueError("single-age population: ages 0-105 expected")
    return out[out.sex != "total"].reset_index(drop=True)


def population_by_group(year: int = YEAR) -> pd.DataFrame:
    """Residents of Spain by sex and exposure group (16-29 ... 65+, 65-74, 75+)."""
    people = single_age_population(year)
    rows = []
    for sex in SEXES:
        part = people[people.sex == sex]
        for group, (low, high) in GROUP_AGES.items():
            mask = part.age.between(low, high)
            rows.append(
                {"sex": sex, "group": group, "population": float(part[mask].population.sum())}
            )
    return pd.DataFrame(rows)


def barcelona_older_population(
    years: tuple[int, ...] = exposure.CONTEMPORARY_YEARS,
) -> pd.DataFrame:
    """Mean residents of the province of Barcelona aged 65-74 and 75 and over, by sex (1 July)."""
    rows = []
    for sex in SEXES:
        for group, (low, high) in (("65-74", (65, 74)), ("75+", (75, 200))):
            values = []
            for year in years:
                table = io_population.population(year, REFERENCE_DATE, sex, BARCELONA_PROVINCE)
                mask = (table.age_low >= low) & (table.age_low <= high)
                values.append(float(table[mask].population.sum()))
            rows.append({"sex": sex, "group": group, "population": float(np.mean(values))})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- exposure profiles


@cache
def _person_frame() -> pd.DataFrame:
    """Every EMEF respondent with the reference day's car-driver km under the central treatment
    and under each distance variant, and the work driving of mobility professionals."""
    frame = exposure.person_day()
    names = exposure.trip_variant_names()
    totals = exposure.trip_km_variants().groupby(["year", "person_id"])[names].sum()
    frame = frame.merge(totals, on=["year", "person_id"], how="left", validate="one_to_one")
    frame[names] = frame[names].fillna(0.0)
    for fraction in exposure.PROFESSIONAL_CAR_SHARES:
        frame[_professional_column(fraction)] = frame.car_km + exposure.professional_km(fraction)
    return frame


def _professional_column(fraction: float) -> str:
    return f"professionals: {fraction:.0%} of work trips by car"


@cache
def _emef_frame(
    area: str | None = None,
    years: tuple[int, ...] = exposure.CONTEMPORARY_YEARS,
    employment_reweighted: bool = False,
) -> tuple[pd.DataFrame, np.ndarray]:
    frame = _person_frame()
    frame = frame[frame.year.isin(years)]
    if area is not None:
        frame = frame[frame.zone_code.isin(exposure.AREAS[area])]
    frame = frame.reset_index(drop=True)
    if employment_reweighted:
        frame = frame.assign(weight=exposure.employment_reweighted(frame))
    return frame, exposure.replicate_factors(frame)


def emef_profile(
    area: str | None = None,
    column: str = "car_km",
    years: tuple[int, ...] = exposure.CONTEMPORARY_YEARS,
    employment_reweighted: bool = False,
) -> dict:
    """Working-day car-driver km per resident by (sex, group), point and bootstrap replicates."""
    frame, factors = _emef_frame(area, years, employment_reweighted)
    out = {}
    for sex in SEXES:
        for group in GROUPS:
            mask = ((frame.sex == sex) & (frame.age4 == group)).to_numpy()
            w = frame.weight.to_numpy()[mask]
            km = frame[column].to_numpy()[mask]
            f = factors[mask]
            out[(sex, group)] = (float((w * km).sum() / w.sum()), ((w * km) @ f) / (w @ f))
    return out


# Licence prevalence by group is read on five-year population groups, so 16-29 is measured as
# licence holders over residents aged 15-29 in both places; only the ratio of the two is used.
PREVALENCE_AGES: dict[str, tuple[int, int]] = {
    "16-29": (15, 29),
    "30-44": (30, 44),
    "45-64": (45, 64),
    "65+": (65, 200),
}


def licence_prevalence(province_code: str | None = None, year: int = YEAR) -> pd.DataFrame:
    """B-licence holders per resident (1 July) by sex and group, Spain or one province."""
    holders = io_exposure.b_permit_holders_by_age(year, province_code)
    rows = []
    for sex in SEXES:
        lic = holders[holders.sex == sex].set_index("band").n_b_permit_holders
        people = io_population.population(
            year, REFERENCE_DATE, sex, province_code or io_population.NATIONAL_CODE
        )
        for group, (low, high) in PREVALENCE_AGES.items():
            residents = float(people[people.age_low.between(low, high)].population.sum())
            licensed = float(lic.reindex(list(NUMERATOR_BANDS[group])).fillna(0).sum())
            rows.append(
                {
                    "place": province_code or "Spain",
                    "sex": sex,
                    "group": group,
                    "b_licence_holders": licensed,
                    "residents": residents,
                    "prevalence": licensed / residents,
                }
            )
    return pd.DataFrame(rows)


def licence_calibrated(profile: dict) -> dict:
    """Method A2: a province profile scaled by Spain's licence prevalence over the province's."""
    spain = licence_prevalence().set_index(["sex", "group"]).prevalence
    province = licence_prevalence(BARCELONA_PROVINCE).set_index(["sex", "group"]).prevalence
    return {
        key: (point * spain[key] / province[key], replicates * spain[key] / province[key])
        for key, (point, replicates) in profile.items()
    }


def edm_profile() -> dict:
    """The Madrid survey's car-driver km per resident by (sex, group); 65+ from 65-74 and 75+."""
    frame = edm2018.person_day()
    factors = edm2018.replicate_factors()
    out = {}
    for sex in SEXES:
        for group in GROUPS:
            low, high = GROUP_AGES[group]
            mask = ((frame.sex == sex) & frame.EDAD_FIN.between(low, high)).to_numpy()
            w = frame.weight.to_numpy()[mask]
            km = frame.car_km.to_numpy()[mask]
            f = factors[mask]
            out[(sex, group)] = (float((w * km).sum() / w.sum()), ((w * km) @ f) / (w @ f))
    return out


def national_km(profile: dict, year: int = YEAR) -> tuple[pd.Series, np.ndarray]:
    """Method A: working-day car-driver km per day in Spain by group, point and replicates."""
    population = population_by_group(year).set_index(["sex", "group"]).population
    point = {}
    replicates = []
    for group in GROUPS:
        point[group] = sum(profile[(sex, group)][0] * population[(sex, group)] for sex in SEXES)
        replicates.append(sum(profile[(sex, group)][1] * population[(sex, group)] for sex in SEXES))
    return pd.Series(point), np.vstack(replicates)


# ----------------------------------------------------------------------------- DGT kilometres


@cache
def dgt_car_km() -> dict[str, float]:
    """DGT's 2024 car kilometres: all cars, less taxi and ride-hailing (central), and less car
    hire without driver and driving schools as well."""
    table = pd.read_excel(KM_SERVICE_PATH, header=0)
    table.columns = ["category", "service", "description", "vehicles", "km", "mean_km"]
    cars = table[table.category.str.strip() == "TURISMOS"]
    total = float(cars.km.sum())
    professional = float(cars[cars.service.isin(PROFESSIONAL_SERVICES)].km.sum())
    rental = float(cars[cars.service.isin(RENTAL_AND_SCHOOL_SERVICES)].km.sum())
    return {
        "all cars": total,
        "less taxi and ride-hailing": total - professional,
        "less taxi, ride-hailing, car hire and driving schools": total - professional - rental,
    }


def owner_km_shares() -> pd.Series:
    """Method D: shares of private owners' car km by owner age band (company cars excluded)."""
    from dgt_stats import driver_risk

    km = driver_risk.car_kilometres(YEAR).set_index("band")
    km = km[km.index != driver_risk.COMPANY_BAND]
    return km.total_km / km.total_km.sum()


# ----------------------------------------------------------------------------- numerator


def drivers_involved(year: int = YEAR) -> pd.DataFrame:
    """Car drivers involved in injury crashes and killed within 30 days, by group."""
    involved = io_tables.read_table("tables_drivers_involved")
    victims = io_tables.read_table("tables_driver_victims")
    involved = involved[(involved.year == year) & involved.vehicle_type.isin(PRIVATE_CARS)]
    deaths = victims[
        (victims.year == year)
        & victims.vehicle_type.isin(PRIVATE_CARS)
        & (victims.severity == "deaths_30d")
    ]
    by_band = pd.DataFrame(
        {
            "involved": involved.groupby("band").value.sum(),
            "killed": deaths.groupby("band").value.sum(),
        }
    ).fillna(0.0)
    rows = []
    for group, bands in NUMERATOR_BANDS.items():
        rows.append({"group": group} | by_band.loc[list(bands)].sum().to_dict())
    for label, bands in (("15-17", ("15-17",)), ("unknown", ("unknown",))):
        rows.append({"group": label} | by_band.reindex(list(bands)).fillna(0).sum().to_dict())
    out = pd.DataFrame(rows)
    known = out[out.group.isin(GROUPS)].involved.sum()
    out.attrs["unknown_share"] = float(
        out.set_index("group").involved["unknown"]
        / (known + out.set_index("group").involved["unknown"])
    )
    out.attrs["public_service_drivers_left_out"] = float(
        io_tables.read_table("tables_drivers_involved")
        .query("year == @year and vehicle_type in @PUBLIC_SERVICE_CARS")
        .value.sum()
    )
    return out


def licence_holders(year: int = YEAR) -> pd.Series:
    """B-licence holders in Spain by group (DGT driver census)."""
    table = io_exposure.b_permit_holders_by_age(year)
    table = table[table.sex == "total"].set_index("band").n_b_permit_holders
    return pd.Series(
        {group: float(table.reindex(list(bands)).sum()) for group, bands in NUMERATOR_BANDS.items()}
    )


# ----------------------------------------------------------------------------- results


CENTRAL_METHOD = "A: EMEF, province of Barcelona"
LICENCE_METHOD = "A2: EMEF, province of Barcelona, per licence holder"


def exposure_profiles() -> dict[str, tuple[pd.Series, np.ndarray]]:
    """National working-day km per day by group under Methods A, A2 and each Method C profile."""
    out = {
        CENTRAL_METHOD: national_km(emef_profile()),
        LICENCE_METHOD: national_km(licence_calibrated(emef_profile())),
    }
    for area in exposure.AREAS:
        out[f"C: EMEF, {area}"] = national_km(emef_profile(area))
    out["C: Madrid survey 2018"] = national_km(edm_profile())
    return out


def shares() -> pd.DataFrame:
    """Each group's share of national car-driver km under every method, with intervals."""
    rows = []
    for method, (km, replicates) in exposure_profiles().items():
        share = km / km.sum()
        share_rep = replicates / replicates.sum(axis=0)
        for i, group in enumerate(GROUPS):
            rows.append(
                {
                    "method": method,
                    "group": group,
                    "workday_km_per_day_millions": float(km[group]) / 1e6,
                    "share_of_km": float(share[group]),
                    "share_low": float(np.percentile(share_rep[i], 2.5)),
                    "share_high": float(np.percentile(share_rep[i], 97.5)),
                }
            )
    owner = owner_km_shares()
    for band, value in owner.items():
        rows.append(
            {"method": "D: registered owners (DGT)", "group": band, "share_of_km": float(value)}
        )
    return pd.DataFrame(rows)


def rates(km_variant: str = "less taxi and ride-hailing") -> pd.DataFrame:
    """Car drivers involved and killed per billion km, by group and method, with each group's
    ratio to drivers aged 45-64. Intervals combine exposure and count uncertainty."""
    total_km = dgt_car_km()[km_variant]
    counts = drivers_involved().set_index("group")
    unknown_share = drivers_involved().attrs["unknown_share"]
    rng = np.random.default_rng(SEED)
    rows = []
    for method, (km, replicates) in exposure_profiles().items():
        n_rep = replicates.shape[1]
        share = km / km.sum()
        share_rep = replicates / replicates.sum(axis=0)
        draws = {
            (group, measure): rng.gamma(counts.loc[group, measure] + 0.5, 1.0, n_rep)
            for group in GROUPS
            for measure in ("involved", "killed")
        }
        reference = GROUPS.index(REFERENCE)
        for i, group in enumerate(GROUPS):
            billion_km = float(share[group]) * total_km / BILLION
            row = {
                "method": method,
                "km_total": km_variant,
                "group": group,
                "billion_km": billion_km,
                "share_of_km": float(share[group]),
            }
            for measure in ("involved", "killed"):
                n = float(counts.loc[group, measure])
                rate_rep = draws[(group, measure)] / (share_rep[i] * total_km / BILLION)
                ref_rep = draws[(REFERENCE, measure)] / (share_rep[reference] * total_km / BILLION)
                point = n / billion_km
                ref_point = float(counts.loc[REFERENCE, measure]) / (
                    float(share[REFERENCE]) * total_km / BILLION
                )
                row |= {
                    measure: n,
                    f"{measure}_per_bn_km": point,
                    f"{measure}_per_bn_km_low": float(np.percentile(rate_rep, 2.5)),
                    f"{measure}_per_bn_km_high": float(np.percentile(rate_rep, 97.5)),
                    f"{measure}_ratio": point / ref_point,
                    f"{measure}_ratio_low": float(np.percentile(rate_rep / ref_rep, 2.5)),
                    f"{measure}_ratio_high": float(np.percentile(rate_rep / ref_rep, 97.5)),
                }
            row["involved_per_bn_km_allocated"] = row["involved_per_bn_km"] / (1 - unknown_share)
            rows.append(row)
    return pd.DataFrame(rows)


def severity_and_licences() -> pd.DataFrame:
    """Measures that need no kilometres: drivers killed per 1,000 drivers involved, and drivers
    involved per 1,000 B-licence holders, by group."""
    counts = drivers_involved().set_index("group")
    licences = licence_holders()
    rng = np.random.default_rng(SEED)
    rows = []
    for group in (*GROUPS, *OLDER):
        involved = float(counts.loc[group, "involved"])
        killed = float(counts.loc[group, "killed"])
        draws = rng.beta(killed + 0.5, involved - killed + 0.5, 4000)
        rows.append(
            {
                "group": group,
                "involved": involved,
                "killed": killed,
                "killed_per_1000_involved": 1000 * killed / involved,
                "killed_per_1000_involved_low": float(1000 * np.percentile(draws, 2.5)),
                "killed_per_1000_involved_high": float(1000 * np.percentile(draws, 97.5)),
                "b_licence_holders": float(licences[group]),
                "involved_per_1000_licence_holders": 1000 * involved / float(licences[group]),
            }
        )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- ages 75 and over


def _older_ratios() -> dict[str, dict[str, float]]:
    """Ratio of km per resident at 75+ to 65-74, by sex, under each assumption."""
    madrid = edm2018.older_split().set_index("sex")
    licences = io_exposure.b_permit_holders_by_age(YEAR)
    people = population_by_group().set_index(["sex", "group"]).population
    out: dict[str, dict[str, float]] = {
        "Madrid survey: km per resident": {},
        "equal km per licence holder": {},
        "Madrid km per licence holder, Spain's licence holders": {},
    }
    for sex in SEXES:
        lic = licences[licences.sex == sex].set_index("band").n_b_permit_holders
        prevalence_young = (lic["65-69"] + lic["70-74"]) / people[(sex, "65-74")]
        prevalence_old = lic["75+"] / people[(sex, "75+")]
        out["Madrid survey: km per resident"][sex] = float(
            madrid.loc[sex, "ratio_75_plus_to_65_74"]
        )
        out["equal km per licence holder"][sex] = float(prevalence_old / prevalence_young)
        km_ratio = (
            madrid.loc[sex, "km_per_licence_holder_75_plus"]
            / madrid.loc[sex, "km_per_licence_holder_65_74"]
        )
        out["Madrid km per licence holder, Spain's licence holders"][sex] = float(
            km_ratio * prevalence_old / prevalence_young
        )
    return out


def _split_older(profile: dict, ratios: dict[str, float]) -> dict[str, float]:
    """Spain's working-day km at 65-74 and 75 and over from a 65+ profile and a 75+/65-74 ratio
    of km per resident by sex."""
    bcn = barcelona_older_population().set_index(["sex", "group"]).population
    spain = population_by_group().set_index(["sex", "group"]).population
    national = {"65-74": 0.0, "75+": 0.0}
    for sex in SEXES:
        k65 = profile[(sex, "65+")][0]
        r = ratios[sex]
        young, old = bcn[(sex, "65-74")], bcn[(sex, "75+")]
        k_young = k65 * (young + old) / (young + r * old)
        national["65-74"] += k_young * spain[(sex, "65-74")]
        national["75+"] += r * k_young * spain[(sex, "75+")]
    return national


def _older_ratios_to_reference(km: pd.Series, older_share: float) -> dict[str, float]:
    """65-74 and 75+ involvement per km over 45-64's, from national km by group and the 75+
    share of the 65+ km (the km total cancels)."""
    counts = drivers_involved().set_index("group").involved
    reference = float(counts[REFERENCE]) / float(km[REFERENCE])
    km_65 = float(km["65+"])
    return {
        "65-74": float(counts["65-74"]) / ((1 - older_share) * km_65) / reference,
        "75+": float(counts["75+"]) / (older_share * km_65) / reference,
    }


def older_split(km_variant: str = "less taxi and ride-hailing") -> pd.DataFrame:
    """Model-dependent kilometres and rates for 65-74 and 75 and over (Method A/B, central), with
    95% intervals from the profile's replicates and the counts' Poisson error."""
    profile = emef_profile()
    km, replicates = national_km(profile)
    total_km = dgt_car_km()[km_variant]
    counts = drivers_involved().set_index("group")
    rng = np.random.default_rng(SEED)
    n_rep = replicates.shape[1]
    draws = {g: rng.gamma(counts.loc[g, "involved"] + 0.5, 1.0, n_rep) for g in (*OLDER, REFERENCE)}
    rows = []
    for assumption, ratios in _older_ratios().items():
        national = _split_older(profile, ratios)
        share = national["75+"] / sum(national.values())
        point = _older_ratios_to_reference(km, share)
        reference = GROUPS.index(REFERENCE)
        older_index = GROUPS.index("65+")
        for group in OLDER:
            part = share if group == "75+" else 1 - share
            billion_km = part * float(km["65+"] / km.sum()) * total_km / BILLION
            km_rep = part * replicates[older_index]
            rate_rep = draws[group] / km_rep
            ref_rep = draws[REFERENCE] / replicates[reference]
            rows.append(
                {
                    "assumption": assumption,
                    "group": group,
                    "ratio_75_to_65_74_male": ratios["male"],
                    "ratio_75_to_65_74_female": ratios["female"],
                    "share_of_65_plus_km": part,
                    "billion_km": billion_km,
                    "involved": float(counts.loc[group, "involved"]),
                    "involved_per_bn_km": float(counts.loc[group, "involved"]) / billion_km,
                    "ratio_to_45_64": point[group],
                    "ratio_low": float(np.percentile(rate_rep / ref_rep, 2.5)),
                    "ratio_high": float(np.percentile(rate_rep / ref_rep, 97.5)),
                }
            )
    return pd.DataFrame(rows)


def older_sensitivity() -> pd.DataFrame:
    """The 65-74 and 75+ ratios under every split assumption and every 65+ variant of
    :func:`sensitivity`: the profiles (EMEF areas, Madrid, licence-calibrated), the distance
    treatments, survey years, professionals' work driving, the older sample's employment and the
    weekend mixes."""
    variants = [
        (source, variant, profile, km) for source, variant, profile, km in _variant_profiles()
    ]
    # Weekend mixes change the age shares of the annual km, not the split within 65+.
    weekend = weekend_sensitivity()
    weekend = weekend[weekend.non_working_share_of_km.notna()]
    for (mix, share), part in weekend.groupby(["non_working_age_mix", "non_working_share_of_km"]):
        variants.append(
            (
                "non-working days",
                f"{mix}, {share:.0%} of km",
                emef_profile(),
                part.set_index("group").share_of_km,
            )
        )
    rows = []
    for source, variant, profile, km in variants:
        if profile is None:
            continue
        for assumption, ratios in _older_ratios().items():
            national = _split_older(profile, ratios)
            share = national["75+"] / sum(national.values())
            ratio = _older_ratios_to_reference(km, share)
            rows.append(
                {
                    "source": source,
                    "variant": variant,
                    "assumption": assumption,
                    "ratio_65_74": ratio["65-74"],
                    "ratio_75_plus": ratio["75+"],
                }
            )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- weekends


# Non-working days (weekends and public holidays) are about 117 of 365 days. If a non-working
# day carries as much car driving as a working day they hold 32% of annual km; if it carries 60%
# as much, 22%. The two values bound the sensitivity analysis; neither is a measurement.
NON_WORKING_SHARES = (0.22, 0.32)


EMEF_WEEKEND_PROXY = "overnight weekend stays away, driving (EMEF 2023, proxy)"
MOVILIA_WEEKEND = "car trips on an average weekend day (MOVILIA 2006, Spain)"
MOVILIA_PATH = RAW_DATA_DIR / "transportes" / "movilia_2006.xls"


def weekend_weights() -> pd.Series:
    """How much more (or less) each group drives on weekends than on working days, relative to
    everyone aged 16 and over, as far as the EMEF 2023 shows it.

    The 2023 module (V11) asks how many of the last four weekends the respondent spent Saturday
    night away from their municipality, and the means of transport of the most recent such trip.
    The weight is the share who drove away for such a weekend over the share who drove on the
    reference working day, each relative to all residents: a ratio of prevalences, not of
    kilometres, and silent on day trips and local weekend driving. It is a proxy."""
    weekend = exposure.weekend_away_2023().set_index("age4").share_away_driving
    frame = exposure.person_day()
    frame = frame[frame.year == 2023]
    working = frame.groupby("age4").apply(
        lambda g: float((g.weight * g.drove).sum() / g.weight.sum()), include_groups=False
    )
    working_all = float((frame.weight * frame.drove).sum() / frame.weight.sum())
    return pd.Series(
        {g: (weekend[g] / weekend["16+"]) / (working[g] / working_all) for g in GROUPS}
    )


def movilia_weekend_weights() -> pd.Series:
    """MOVILIA 2006 table 64: trips whose main mode is a car or motorcycle (drivers and
    passengers) on an average weekend day over an average working day, by age, relative to all
    residents aged 15 and over. The survey's bands are 15-29, 30-39, 40-49, 50-64 and 65+; half of
    40-49 is given to 30-44 and half to 45-64."""

    def car_trips(sheet: str) -> pd.Series:
        table = pd.read_excel(MOVILIA_PATH, sheet, header=None)
        labels = table[0].astype(str).str.strip()
        rows = {}
        for label, key in (
            ("De 15 a 29", "15-29"),
            ("De 30 a 39", "30-39"),
            ("De 40 a 49", "40-49"),
            ("De 50 a 64", "50-64"),
            ("65 y más años", "65+"),
        ):
            # The first block of each sheet is both sexes.
            rows[key] = float(table.loc[labels[labels == label].index[0], 3])
        return pd.Series(rows)

    working, weekend = car_trips("T64-1"), car_trips("T64-5")
    if not str(pd.read_excel(MOVILIA_PATH, "T64-5", header=None).iloc[6, 0]).startswith(
        "V. En día"
    ):
        raise ValueError("MOVILIA 2006 table 64: sheet T64-5 is not the average weekend day")

    def group(series: pd.Series) -> pd.Series:
        return pd.Series(
            {
                "16-29": series["15-29"],
                "30-44": series["30-39"] + series["40-49"] / 2,
                "45-64": series["40-49"] / 2 + series["50-64"],
                "65+": series["65+"],
            }
        )

    ratio = group(weekend) / group(working)
    overall = weekend.sum() / working.sum()
    return ratio / overall


def weekend_sensitivity(km_variant: str = "less taxi and ride-hailing") -> pd.DataFrame:
    """Method A/B rates if non-working days hold a different share of km and a different age mix.
    With the working days' age mix the share of km on non-working days changes nothing."""
    km, _ = national_km(emef_profile())
    workday = km / km.sum()
    total_km = dgt_car_km()[km_variant]
    counts = drivers_involved().set_index("group").involved
    mixes = {
        "same age mix as working days": (pd.Series(1.0, index=GROUPS), (None,)),
        EMEF_WEEKEND_PROXY: (weekend_weights(), NON_WORKING_SHARES),
        MOVILIA_WEEKEND: (movilia_weekend_weights(), NON_WORKING_SHARES),
    }
    rows = []
    for mix, (alpha, shares) in mixes.items():
        weekend = alpha * workday / float((alpha * workday).sum())
        for share in shares:
            annual = workday if share is None else (1 - share) * workday + share * weekend
            rate = counts[list(GROUPS)] / (annual * total_km / BILLION)
            for group in GROUPS:
                rows.append(
                    {
                        "non_working_age_mix": mix,
                        "non_working_share_of_km": share,
                        "group": group,
                        "weekend_weight": float(alpha[group]),
                        "share_of_km": float(annual[group]),
                        "involved_per_bn_km": float(rate[group]),
                        "ratio_to_45_64": float(rate[group] / rate[REFERENCE]),
                    }
                )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- sensitivity

SURVEY_YEARS_VARIANTS: tuple[tuple[int, ...], ...] = (
    (2024,),
    (2023, 2024),
    (2021, 2022, 2023, 2024),
    (2019, 2021, 2022, 2023, 2024),
)


def _variant_profiles():
    """(source, variant, EMEF profile or None, national km by group) for every alternative."""
    for method, (km, _) in exposure_profiles().items():
        if method == CENTRAL_METHOD:
            continue
        source = "licence-calibrated transfer" if method == LICENCE_METHOD else "regional profile"
        profile = None
        if method == LICENCE_METHOD:
            profile = licence_calibrated(emef_profile())
        elif method.startswith("C: EMEF, "):
            profile = emef_profile(method.removeprefix("C: EMEF, "))
        elif method.startswith("C: Madrid"):
            profile = edm_profile()
        yield source, method.split(": ", 1)[1], profile, km
    for name in exposure.trip_variant_names():
        profile = emef_profile(column=name)
        yield "distance", name, profile, national_km(profile)[0]
    for years in SURVEY_YEARS_VARIANTS:
        profile = emef_profile(years=years)
        yield "survey years", "-".join(map(str, years)), profile, national_km(profile)[0]
    for fraction in exposure.PROFESSIONAL_CAR_SHARES:
        profile = emef_profile(column=_professional_column(fraction))
        yield (
            "professionals' work driving",
            f"{fraction:.0%} of work trips by car",
            profile,
            (national_km(profile)[0]),
        )
    profile = emef_profile(employment_reweighted=True)
    yield "older sample", "65+ employed share set to the census", profile, national_km(profile)[0]


def sensitivity() -> pd.DataFrame:
    """Every group's ratio to 45-64 (involved and killed per km) under each alternative choice,
    beside the central Method A; the weekend mixes come from :func:`weekend_sensitivity`."""
    counts = drivers_involved().set_index("group")
    central_km, _ = national_km(emef_profile())
    rows = []

    def record(source: str, variant: str, km: pd.Series) -> None:
        share = km / km.sum()
        for group in GROUPS:
            row = {"source": source, "variant": variant, "group": group}
            row["share_of_km"] = float(share[group])
            for measure in ("involved", "killed"):
                rate = float(counts.loc[group, measure]) / float(km[group])
                ref = float(counts.loc[REFERENCE, measure]) / float(km[REFERENCE])
                row[f"{measure}_ratio"] = rate / ref
            rows.append(row)

    record("central", "Method A", central_km)
    for source, variant, _, km in _variant_profiles():
        record(source, variant, km)
    weekend = weekend_sensitivity()
    weekend = weekend[weekend.non_working_share_of_km.notna()]
    for (mix, share), part in weekend.groupby(["non_working_age_mix", "non_working_share_of_km"]):
        km = part.set_index("group").share_of_km
        record("non-working days", f"{mix}, {share:.0%} of km", km)
    return pd.DataFrame(rows)


def unknown_age_bounds() -> pd.DataFrame:
    """Involvement ratios to 45-64 if every driver of unrecorded age were in one group."""
    counts = drivers_involved().set_index("group").involved
    km, _ = national_km(emef_profile())
    unknown = float(counts["unknown"])
    rows = []
    for assigned in (None, *GROUPS):
        involved = counts[list(GROUPS)].copy()
        if assigned is not None:
            involved[assigned] += unknown
        rate = involved / km[list(GROUPS)]
        for group in GROUPS:
            rows.append(
                {
                    "unknown_age_assigned_to": assigned or "left out",
                    "group": group,
                    "involved_ratio": float(rate[group] / rate[REFERENCE]),
                }
            )
    return pd.DataFrame(rows)


def sex_per_km() -> pd.DataFrame:
    """Men against women aged 18 and over: private-car drivers involved and killed per km, with
    the km split by sex from the Method A profile (the same transfer as for age), and the ratio
    under each other profile as a sensitivity range."""
    out = _sex_per_km(emef_profile()).assign(profile=CENTRAL_METHOD)
    others = {
        LICENCE_METHOD: licence_calibrated(emef_profile()),
        **{f"C: EMEF, {area}": emef_profile(area) for area in exposure.AREAS},
        "C: Madrid survey 2018": edm_profile(),
    }
    spread = pd.concat(
        [_sex_per_km(profile).assign(profile=name) for name, profile in others.items()]
    )
    ranges = spread.groupby("measure").ratio_men_to_women.agg(["min", "max"])
    out["range_low"] = out.measure.map(ranges["min"])
    out["range_high"] = out.measure.map(ranges["max"])
    return out


def _sex_per_km(profile: dict) -> pd.DataFrame:
    population = population_by_group().set_index(["sex", "group"]).population
    involved = io_tables.read_table("tables_drivers_involved")
    victims = io_tables.read_table("tables_driver_victims")
    bands = [b for group in GROUPS for b in NUMERATOR_BANDS[group]]
    rows = []
    km_rep = {}
    for sex in SEXES:
        km = sum(profile[(sex, g)][0] * population[(sex, g)] for g in GROUPS)
        km_rep[sex] = sum(profile[(sex, g)][1] * population[(sex, g)] for g in GROUPS)
        n_inv = involved[
            (involved.year == YEAR)
            & involved.vehicle_type.isin(PRIVATE_CARS)
            & (involved.sex == sex)
            & involved.band.isin(bands)
        ].value.sum()
        n_killed = victims[
            (victims.year == YEAR)
            & victims.vehicle_type.isin(PRIVATE_CARS)
            & (victims.sex == sex)
            & (victims.severity == "deaths_30d")
            & victims.band.isin(bands)
        ].value.sum()
        rows.append(
            {"sex": sex, "share_of_km": km, "involved": float(n_inv), "killed": float(n_killed)}
        )
    out = pd.DataFrame(rows).set_index("sex")
    out["share_of_km"] = out.share_of_km / out.share_of_km.sum()
    rng = np.random.default_rng(SEED)
    n_rep = len(km_rep["male"])
    result = []
    for measure in ("involved", "killed"):
        point = (out.loc["male", measure] / out.loc["male", "share_of_km"]) / (
            out.loc["female", measure] / out.loc["female", "share_of_km"]
        )
        male = rng.gamma(out.loc["male", measure] + 0.5, 1.0, n_rep) / km_rep["male"]
        female = rng.gamma(out.loc["female", measure] + 0.5, 1.0, n_rep) / km_rep["female"]
        result.append(
            {
                "measure": f"{measure} per km",
                "men_share_of_km": float(out.loc["male", "share_of_km"]),
                "men": float(out.loc["male", measure]),
                "women": float(out.loc["female", measure]),
                "ratio_men_to_women": float(point),
                "ratio_low": float(np.percentile(male / female, 2.5)),
                "ratio_high": float(np.percentile(male / female, 97.5)),
            }
        )
    return pd.DataFrame(result)


# ----------------------------------------------------------------------------- old figure


def owner_km_by_group() -> pd.Series:
    """Private owners' car km in 2024 summed onto the driver groups (18-29 from the owner bands
    18-20 to 25-29, as the numerator; company cars excluded)."""
    km = io_exposure.read_exposure("km_edad_propietario_2024")
    cars = km[(km.vehicle_group == "car") & (km.year == YEAR) & ~km.is_company]
    by_band = cars.groupby("band").total_km.sum()
    return pd.Series(
        {
            group: float(by_band.reindex(list(bands)).sum())
            for group, bands in NUMERATOR_BANDS.items()
        }
    )


def owner_age_comparison() -> pd.DataFrame:
    """The former figure (involvement per km of cars registered to owners of each age, all car
    types including public service, against 35-54), the same owner km on the driver groups and
    reference used now (private cars, against 45-64), and the driver-age estimate of Method
    A/B."""
    from dgt_stats import driver_risk

    old = driver_risk.km_rates(YEAR)
    ratios = driver_risk.km_rate_ratios(YEAR).query("measure == 'involved_per_bn_km'")
    old = old.merge(ratios[["band", "ratio"]], on="band")
    rows = [
        {
            "denominator": "km of cars registered to owners of this age (former figure)",
            "group": band,
            "involved": involved,
            "billion_km": km,
            "involved_per_bn_km": rate,
            "ratio_to_reference": ratio,
            "reference": "35-54",
        }
        for band, involved, km, rate, ratio in zip(
            old.band, old.drivers_involved, old.billion_km, old.involved_per_bn_km, old.ratio
        )
    ]
    owner = owner_km_by_group()
    counts = drivers_involved().set_index("group").involved
    reference_rate = float(counts[REFERENCE]) / float(owner[REFERENCE])
    rows += [
        {
            "denominator": "km of cars registered to owners of this age, same age groups",
            "group": group,
            "involved": float(counts[group]),
            "billion_km": float(owner[group]) / BILLION,
            "involved_per_bn_km": float(counts[group]) / (float(owner[group]) / BILLION),
            "ratio_to_reference": float(counts[group]) / float(owner[group]) / reference_rate,
            "reference": REFERENCE,
        }
        for group in (*GROUPS, *OLDER)
    ]
    new = rates()
    new = new[new.method == CENTRAL_METHOD]
    rows += [
        {
            "denominator": "km driven by drivers of this age (EMEF profile, DGT total)",
            "group": group,
            "involved": involved,
            "billion_km": km,
            "involved_per_bn_km": rate,
            "ratio_to_reference": ratio,
            "reference": REFERENCE,
        }
        for group, involved, km, rate, ratio in zip(
            new.group, new.involved, new.billion_km, new.involved_per_bn_km, new.involved_ratio
        )
    ]
    return pd.DataFrame(rows)
