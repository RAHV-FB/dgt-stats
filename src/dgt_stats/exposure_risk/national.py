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
professionals' unrecorded work driving, the older sample's employment set to the census, the
age mix of non-working days, and the credible age mixes of the half of DGT's kilometres that the
survey's working days do not cover (:mod:`dgt_stats.exposure_risk.coverage`), alone and combined
with each regional profile. The spread is reported as a sensitivity range beside the sampling
interval, never as a confidence interval. It is not a bound: other choices taken together would
widen it further.

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
km between 65-74 and 75 and over under four splits (:data:`SPLITS`), by sex, using the
population of each age in the province of Barcelona and in Spain. The Madrid survey's ratio of km
per resident (:data:`REFERENCE_SPLIT`) gives a *conditional* estimate, reported beside the measured
65-and-over figure and never in its place, with a joint sampling interval over both surveys'
replicates. The other splits are the Madrid km per licence holder applied to Spain's licence
holders, an upper limit for men from RACC's driving days with women's km per licence holder
equal (:func:`racc_men_limit`), and equal km per licence holder at 65-74 and 75 and over.
:func:`older_sensitivity` repeats the four splits under every 65-and-over variant of
:func:`sensitivity` and a bound on the age mix of the EMEF's 65+ sample, and marks the rows at odds
with Spanish surveys of men's driving; :func:`older_extremes`, :func:`older_decomposition`,
:func:`older_attribution` and :func:`reference_checks` describe the ends of that range, what moves
it, and the checks the conditional estimate is read against.
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

# The four splits of the 65-and-over km between 65-74 and 75 and over. Each is a ratio of car-driver
# km per resident at 75 and over to 65-74, by sex, applied to Spain's population (and, to take the
# province's 65-and-over mean apart, to the province of Barcelona's).
REFERENCE_SPLIT = "Madrid survey: km per resident"
LICENCE_SPLIT = "Madrid km per licence holder, Spain's licence holders"
RACC_SPLIT = "RACC driving-days limit for men, equal km per licence holder for women"
EQUAL_SPLIT = "equal km per licence holder"
SPLITS = (REFERENCE_SPLIT, LICENCE_SPLIT, RACC_SPLIT, EQUAL_SPLIT)
# The splits whose ratios come from the Madrid survey, and so carry its sampling error.
EDM_SPLITS = (REFERENCE_SPLIT, LICENCE_SPLIT)
MADRID_METHOD = "C: Madrid survey 2018"

# Fundació RACC, "Mayores al volante. Estudio RACC sobre el envejecimiento y conducción en España"
# (slide dossier, published 29 May 2013; fieldwork dates not stated): 3,003 holders of a driving
# licence aged 65 and over in Spain, stratified by sex and age on DGT's census. The figures are
# quoted, not archived: the RACC site grants no licence to reuse its documents.
RACC_YEAR = 2013
# Slide 5: interviews by sex and age.
RACC_INTERVIEWS: dict[str, dict[str, int]] = {
    "male": {"65-69": 916, "70-74": 643, "75+": 926},
    "female": {"65-69": 295, "70-74": 96, "75+": 127},
}
# Slide 11: share of licence holders who do not drive at all, by sex and age, and for both sexes.
RACC_NOT_DRIVING: dict[str, dict[str, float]] = {
    "male": {"65-69": 0.141, "70-74": 0.202, "75+": 0.387},
    "female": {"65-69": 0.295, "70-74": 0.375, "75+": 0.630},
    "all": {"65-69": 0.178, "70-74": 0.225, "75+": 0.415},
}
# Slide 19: the days a week active drivers drive (fewer than 2, 2 or 3, 4 or 5, 6 or more), by
# age, both sexes; the survey does not give them by sex.
RACC_FREQUENCY: dict[str, tuple[float, float, float, float]] = {
    "65-69": (0.095, 0.300, 0.138, 0.467),
    "70-74": (0.144, 0.314, 0.137, 0.405),
    "75+": (0.144, 0.345, 0.138, 0.373),
}
RACC_MIDPOINT_DAYS = (1.0, 2.5, 4.5, 7.0)

# The bound on the age mix of the EMEF's 65-and-over sample (:func:`older_sensitivity`).
COMPOSITION_VARIANT = "share aged 75+ in the 65+ sample at the routing-identified share (bound)"
EMPLOYMENT_VARIANT = "65+ employed share set to the census"
# When the pages first gave the conditional estimate for 75 and over (their change note).
OLDER_ESTIMATE_CHANGED = "October 2026"
MARK_REASON = (
    "men aged 75 and over with a car licence implied to drive at least as far as men aged 65-74 "
    "with one"
)


def racc_men_limit(midpoints: tuple[float, ...] = RACC_MIDPOINT_DAYS) -> float:
    """Driving days per car-licence holder, men aged 75 and over over men aged 65-74, from the RACC
    survey: the share of male licence holders who drive at all (slide 11, the two younger bands
    weighted by their interviews, slide 5) times the mean days a week active drivers drive (slide
    19, both sexes, at ``midpoints`` of its four classes, the younger bands weighted by their
    active interviewees). Older drivers make shorter and slower trips, so the ratio of their
    kilometres is lower than this ratio of days: it is an upper limit for kilometres, not an
    estimate of them."""
    young = ("65-69", "70-74")
    days = {
        age: sum(p * m for p, m in zip(shares, midpoints)) for age, shares in RACC_FREQUENCY.items()
    }
    men = RACC_INTERVIEWS["male"]
    driving = {age: 1 - RACC_NOT_DRIVING["male"][age] for age in men}
    driving_young = sum(driving[a] * men[a] for a in young) / sum(men[a] for a in young)
    active = {
        a: sum(RACC_INTERVIEWS[s][a] for s in SEXES) * (1 - RACC_NOT_DRIVING["all"][a])
        for a in young
    }
    days_young = sum(days[a] * active[a] for a in young) / sum(active.values())
    return float((driving["75+"] / driving_young) * (days["75+"] / days_young))


@cache
def older_licence_prevalence(province_code: str | None = None) -> pd.DataFrame:
    """B-licence holders and residents at 65-74 and 75 and over, by sex (DGT driver census, INE 1
    July), for Spain or one province."""
    holders = io_exposure.b_permit_holders_by_age(YEAR, province_code)
    spain = population_by_group().set_index(["sex", "group"]).population
    rows = []
    for sex in SEXES:
        lic = holders[holders.sex == sex].set_index("band").n_b_permit_holders
        if province_code is None:
            residents = {group: float(spain[(sex, group)]) for group in OLDER}
        else:
            people = io_population.population(YEAR, REFERENCE_DATE, sex, province_code)
            residents = {
                "65-74": float(people[people.age_low.between(65, 74)].population.sum()),
                "75+": float(people[people.age_low >= 75].population.sum()),
            }
        licensed = {"65-74": float(lic["65-69"] + lic["70-74"]), "75+": float(lic["75+"])}
        for group in OLDER:
            rows.append(
                {
                    "place": province_code or "Spain",
                    "sex": sex,
                    "group": group,
                    "b_licence_holders": licensed[group],
                    "residents": residents[group],
                    "prevalence": licensed[group] / residents[group],
                }
            )
    return pd.DataFrame(rows)


def older_prevalence_ratio(province_code: str | None = None) -> dict[str, float]:
    """B-licence holders per resident at 75 and over over 65-74, by sex."""
    table = older_licence_prevalence(province_code).set_index(["sex", "group"]).prevalence
    return {sex: float(table[(sex, "75+")] / table[(sex, "65-74")]) for sex in SEXES}


@cache
def _older_ratios() -> dict[str, dict[str, float]]:
    """Ratio of km per resident at 75+ to 65-74, by sex, under each split. The result is cached:
    callers must not change it."""
    madrid = edm2018.older_ratio_replicates()
    spain = older_prevalence_ratio()
    limit = racc_men_limit()
    out: dict[str, dict[str, float]] = {split: {} for split in SPLITS}
    for sex in SEXES:
        out[REFERENCE_SPLIT][sex] = madrid[sex]["per_resident"][0]
        out[LICENCE_SPLIT][sex] = madrid[sex]["per_licence_holder"][0] * spain[sex]
        out[RACC_SPLIT][sex] = (limit if sex == "male" else 1.0) * spain[sex]
        out[EQUAL_SPLIT][sex] = spain[sex]
    return out


def _split_replicates(split: str) -> dict[str, float | np.ndarray]:
    """A split's ratio by sex as the Madrid survey's household-bootstrap replicates (the two
    Madrid splits), or as a fixed number (the RACC limit and the equal split)."""
    if split not in EDM_SPLITS:
        return dict(_older_ratios()[split])
    madrid = edm2018.older_ratio_replicates()
    spain = older_prevalence_ratio()
    if split == REFERENCE_SPLIT:
        return {sex: madrid[sex]["per_resident"][1] for sex in SEXES}
    return {sex: madrid[sex]["per_licence_holder"][1] * spain[sex] for sex in SEXES}


def public_split_labels() -> dict[str, str]:
    """The splits as the pages name them."""
    return {
        REFERENCE_SPLIT: "Madrid survey: km per resident (used for the estimate)",
        LICENCE_SPLIT: "Madrid km per licence holder, applied to Spain's licence holders (mixes "
        "two definitions of a licence)",
        RACC_SPLIT: f"Upper limit on men's kilometres from driving days (RACC survey published in "
        f"{RACC_YEAR}): men {racc_men_limit():.2f} of 65–74 per licence holder, women equal",
        EQUAL_SPLIT: "Equal km per licence holder at 65–74 and 75 and over (at odds with surveys "
        "of men's driving; kept in the range)",
    }


def _split_older_by_sex(profile: dict, ratios: dict[str, float]) -> dict[tuple[str, str], float]:
    """Spain's working-day km by sex at 65-74 and 75 and over from a 65+ profile and a 75+/65-74
    ratio of km per resident by sex. The profile's 65+ mean is taken apart with the province of
    Barcelona's population at each age and put back together with Spain's."""
    bcn = barcelona_older_population().set_index(["sex", "group"]).population
    spain = population_by_group().set_index(["sex", "group"]).population
    out = {}
    for sex in SEXES:
        k65 = profile[(sex, "65+")][0]
        r = ratios[sex]
        young, old = bcn[(sex, "65-74")], bcn[(sex, "75+")]
        k_young = k65 * (young + old) / (young + r * old)
        out[(sex, "65-74")] = k_young * spain[(sex, "65-74")]
        out[(sex, "75+")] = r * k_young * spain[(sex, "75+")]
    return out


def _split_older(profile: dict, ratios: dict[str, float]) -> dict[str, float]:
    """Spain's working-day km at 65-74 and 75 and over (:func:`_split_older_by_sex`, both sexes)."""
    by_sex = _split_older_by_sex(profile, ratios)
    return {group: sum(by_sex[(sex, group)] for sex in SEXES) for group in OLDER}


def implied_km_per_holder(ratios: dict[str, float]) -> dict[str, float]:
    """A split's km per B-licence holder at 75 and over over 65-74, by sex: the km it allocates to
    each sex and age in Spain divided by DGT's licence holders of that sex and age. Within a sex
    the profile's level cancels, so this is a property of the split alone."""
    holders = older_licence_prevalence().set_index(["sex", "group"]).b_licence_holders
    km = _split_older_by_sex(emef_profile(), ratios)
    return {
        sex: float(
            (km[(sex, "75+")] / holders[(sex, "75+")])
            / (km[(sex, "65-74")] / holders[(sex, "65-74")])
        )
        for sex in SEXES
    }


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


@cache
def composition_shares() -> dict[str, tuple[float, float]]:
    """By sex: the share aged 75 and over in the EMEF's 65-and-over sample as the questionnaire's
    routing identifies it (a lower limit), and among the province's residents (INE)."""
    from dgt_stats.emef import older_routing

    table = older_routing.routing_share(exposure.CONTEMPORARY_YEARS).set_index("sex")
    if table.routing_share_75_plus.isna().any():
        raise ValueError("routing share of the 65+ sample: a cell below the publication rule")
    return {
        sex: (
            float(table.loc[sex, "routing_share_75_plus"]),
            float(table.loc[sex, "ine_share_75_plus"]),
        )
        for sex in SEXES
    }


def composition_profile(profile: dict, ratios: dict[str, float]) -> dict:
    """``profile`` with each sex's 65+ km per resident corrected as if the EMEF's 65-and-over
    sample held people aged 75 and over at the routing-identified share s_r instead of their
    population share s_p: km65 x [s_p r + (1 - s_p)] / [s_r r + (1 - s_r)], with r the split's
    ratio of km per resident at 75+ to 65-74. The routing share is a lower limit on the sample's
    share, so this is an upper bound on the bias, not an estimate of it."""
    shares = composition_shares()
    out = dict(profile)
    for sex in SEXES:
        sample, population = shares[sex]
        r = ratios[sex]
        factor = (population * r + 1 - population) / (sample * r + 1 - sample)
        point, replicates = profile[(sex, "65+")]
        out[(sex, "65+")] = (point * factor, replicates * factor)
    return out


def _older_draws(
    profile: dict,
    ratios: dict[str, float | np.ndarray],
    structure: tuple | None = None,
    matched: bool = False,
    seed: int = SEED,
) -> tuple[np.ndarray, np.ndarray]:
    """Joint replicates of the 75+ and 65-74 ratios to 45-64.

    ``profile`` maps (sex, group) to (point, replicates) of km per resident. ``ratios`` gives each
    sex's split ratio as a number or as replicates of another survey. The cells cross the
    profile's replicates (first axis) with the split's (second axis), every pairing of the two
    surveys' resamples, unless ``matched``, when profile and split come from the same survey's
    resample and are paired one to one. With a fixed split the profile's replicates are repeated
    along the second axis. Every cell gets its own gamma draws of the three counts.
    ``structure`` is ``None`` (all km at the profile's mix), ``("coverage", non_working_mix,
    remainder_mix, professional_mix)`` or ``("weekend", mix, share of km)``. The mixes' own
    weights are held fixed. Returns the two ratios, with the shape of the cells."""
    from dgt_stats.exposure_risk import coverage

    n = len(profile[("male", "65+")][1])

    def prof(sex: str, group: str) -> np.ndarray:
        values = np.asarray(profile[(sex, group)][1], dtype=float)
        return values if matched else values[:, None]

    def ratio(sex: str) -> np.ndarray | float:
        value = ratios[sex]
        if np.ndim(value) == 0:
            return float(value)
        values = np.asarray(value, dtype=float)
        return values if matched else values[None, :]

    population = population_by_group().set_index(["sex", "group"]).population
    bcn = barcelona_older_population().set_index(["sex", "group"]).population
    km = {g: sum(prof(s, g) * population[(s, g)] for s in SEXES) for g in GROUPS}
    young = old = 0.0
    for sex in SEXES:
        r = ratio(sex)
        y, o = bcn[(sex, "65-74")], bcn[(sex, "75+")]
        k_young = prof(sex, "65+") * (y + o) / (y + r * o)
        young = young + k_young * population[(sex, "65-74")]
        old = old + r * k_young * population[(sex, "75+")]
    q = old / (old + young)
    base = np.stack([km[g] for g in GROUPS])
    if structure is None:
        shares = base
    elif structure[0] == "coverage":
        shares, q = coverage.structure_shares(
            base / base.sum(axis=0), q, structure[1], structure[2], structure[3]
        )
    elif structure[0] == "weekend":
        mix, share = structure[1], structure[2]
        alpha = weekend_weights() if mix == EMEF_WEEKEND_PROXY else movilia_weekend_weights()
        alpha = np.asarray(alpha.reindex(list(GROUPS)), dtype=float).reshape(
            (len(GROUPS),) + (1,) * (base.ndim - 1)
        )
        workday = base / base.sum(axis=0)
        weekend = alpha * workday / (alpha * workday).sum(axis=0)
        shares = (1 - share) * workday + share * weekend
    else:
        raise ValueError(f"unknown structure {structure!r}")
    shape = (n,) if matched else (n, n)
    s45 = np.broadcast_to(shares[GROUPS.index(REFERENCE)], shape)
    s65 = np.broadcast_to(shares[GROUPS.index("65+")], shape)
    q = np.broadcast_to(q, shape)
    counts = drivers_involved().set_index("group").involved
    rng = np.random.default_rng(seed)
    g75 = rng.gamma(float(counts["75+"]) + 0.5, 1.0, shape)
    g65 = rng.gamma(float(counts["65-74"]) + 0.5, 1.0, shape)
    g45 = rng.gamma(float(counts[REFERENCE]) + 0.5, 1.0, shape)
    reference = g45 / s45
    return g75 / (q * s65) / reference, g65 / ((1 - q) * s65) / reference


MC_RESAMPLES = 200


def _interval(draws: np.ndarray, resamples: int = MC_RESAMPLES) -> dict[str, float]:
    """The 2.5th and 97.5th percentiles of ``draws``, with a Monte Carlo standard error of each:
    how far the endpoints would move with another set of the surveys' replicates and count
    draws.

    The cells of a two-dimensional ``draws`` share replicates along their rows (the profile's
    survey) and their columns (the split's survey, or only the count draws when the split is
    fixed), so blocks of cells are not independent and a batch standard error understates the
    error several times. The pigeonhole bootstrap (Owen 2007, *Annals of Applied Statistics*
    1:386-411) respects that crossed dependence: rows and columns are resampled independently
    with replacement, the percentiles recomputed, and the standard error is their standard
    deviation over ``resamples`` resamples. One-dimensional ``draws`` (profile and split from one
    survey's resample, paired) take an ordinary bootstrap. For the Madrid split at 75 and over,
    eight independent sets of 300 x 300 replicates gave endpoint standard deviations of about
    0.012 and 0.039, against pigeonhole errors of 0.014-0.019 and 0.023-0.039 within each set."""
    low, high = np.percentile(draws, [2.5, 97.5])
    rng = np.random.default_rng(SEED)
    ends = np.empty((resamples, 2))
    for b in range(resamples):
        if draws.ndim == 1:
            sample = draws[rng.integers(0, len(draws), len(draws))]
        else:
            rows = rng.integers(0, draws.shape[0], draws.shape[0])
            columns = rng.integers(0, draws.shape[1], draws.shape[1])
            sample = draws[np.ix_(rows, columns)]
        ends[b] = np.percentile(sample, [2.5, 97.5])
    se = ends.std(axis=0, ddof=1)
    return {
        "low": float(low),
        "high": float(high),
        "mc_se_low": float(se[0]),
        "mc_se_high": float(se[1]),
    }


def _sampling_sources(split: str, profile_source: str = "EMEF", fixed: tuple[str, ...] = ()) -> str:
    """Which sampling errors an interval includes, and what it holds fixed."""
    included = [profile_source]
    held = list(fixed)
    if split in EDM_SPLITS and "EDM2018" not in profile_source:
        included.append("EDM2018")
    included.append("counts")
    if split == RACC_SPLIT:
        held.append("RACC constant")
    if split in (RACC_SPLIT, EQUAL_SPLIT):
        held.append("DGT licence prevalence")
    text = ", ".join(included)
    return f"{text}; fixed: {', '.join(held)}" if held else text


def older_split(km_variant: str = "less taxi and ride-hailing") -> pd.DataFrame:
    """Kilometres and rates for 65-74 and 75 and over under each split (Method A/B, central), with
    joint 95% sampling intervals.

    The EMEF and the Madrid survey are independent samples, so the interval crosses all of the
    EMEF's replicates with all of the Madrid survey's (300 x 300 cells), each cell with its own
    gamma draws of the counts. It covers the sampling error of both surveys and chance in the
    crash counts, and holds every structural choice fixed. It may be too narrow or too wide:
    the EMEF bootstrap ignores clustering, the Madrid household bootstrap ignores stratification,
    and neither recalibrates the weights. ``ratio_low_split_fixed`` and ``ratio_high_split_fixed``
    are the earlier interval, which held the split's ratio at its point value and so left out the
    Madrid survey's sampling error."""
    profile = emef_profile()
    km, replicates = national_km(profile)
    total_km = dgt_car_km()[km_variant]
    counts = drivers_involved().set_index("group")
    rng = np.random.default_rng(SEED)
    n_rep = replicates.shape[1]
    draws = {g: rng.gamma(counts.loc[g, "involved"] + 0.5, 1.0, n_rep) for g in (*OLDER, REFERENCE)}
    holders = older_licence_prevalence().groupby("group").b_licence_holders.sum()
    rows = []
    for split in SPLITS:
        ratios = _older_ratios()[split]
        national = _split_older(profile, ratios)
        share = national["75+"] / sum(national.values())
        point = _older_ratios_to_reference(km, share)
        per_holder = implied_km_per_holder(ratios)
        pooled = (share / (1 - share)) / float(holders["75+"] / holders["65-74"])
        joint75, joint65 = _older_draws(profile, _split_replicates(split))
        intervals = {"75+": _interval(joint75), "65-74": _interval(joint65)}
        reference = GROUPS.index(REFERENCE)
        older_index = GROUPS.index("65+")
        for group in OLDER:
            part = share if group == "75+" else 1 - share
            billion_km = part * float(km["65+"] / km.sum()) * total_km / BILLION
            # The earlier interval: the split held at its point value.
            km_rep = part * replicates[older_index]
            rate_rep = draws[group] / km_rep
            ref_rep = draws[REFERENCE] / replicates[reference]
            joint = intervals[group]
            rows.append(
                {
                    "assumption": split,
                    "group": group,
                    "ratio_75_to_65_74_male": ratios["male"],
                    "ratio_75_to_65_74_female": ratios["female"],
                    "share_of_65_plus_km": part,
                    "billion_km": billion_km,
                    "involved": float(counts.loc[group, "involved"]),
                    "involved_per_bn_km": float(counts.loc[group, "involved"]) / billion_km,
                    "ratio_to_45_64": point[group],
                    "ratio_low": joint["low"],
                    "ratio_high": joint["high"],
                    "mc_se_low": joint["mc_se_low"],
                    "mc_se_high": joint["mc_se_high"],
                    "ratio_low_split_fixed": float(np.percentile(rate_rep / ref_rep, 2.5)),
                    "ratio_high_split_fixed": float(np.percentile(rate_rep / ref_rep, 97.5)),
                    "sampling_sources": _sampling_sources(split),
                    "men_km_per_holder_75_vs_65_74": per_holder["male"],
                    "women_km_per_holder_75_vs_65_74": per_holder["female"],
                    "pooled_km_per_holder_75_vs_65_74": pooled,
                }
            )
    return pd.DataFrame(rows)


def _profile_methods() -> dict[str, str]:
    """The method name of every profile, by the label the sensitivity tables give it."""
    methods = [CENTRAL_METHOD, LICENCE_METHOD]
    methods += [f"C: EMEF, {area}" for area in exposure.AREAS]
    methods.append(MADRID_METHOD)
    return {method.split(": ", 1)[1]: method for method in methods}


def older_sensitivity() -> pd.DataFrame:
    """The 65-74 and 75+ ratios under every split and every 65+ variant of :func:`sensitivity`:
    the profiles (EMEF areas, Madrid, licence-calibrated), the distance treatments, survey years,
    professionals' work driving, the older sample's employment, the weekend mixes, and the
    credible age mixes of the kilometres the survey does not cover
    (:mod:`dgt_stats.exposure_risk.coverage`), alone and with each other profile; and, under the
    central structure, the bound on too few people aged 75 and over in the EMEF's 65+ sample.

    No row is dropped. Each row carries diagnostics of what it implies: km per B-licence holder
    at 75 and over against 65-74 (men, women and pooled), at 65-74 against 45-64, and the km of
    drivers of each age against the km of cars registered to owners of that age. A row is marked
    ``at_odds_with_mens_driving`` when men aged 75 and over with a car licence are implied to
    drive at least as far as men aged 65-74 with one, which Spanish surveys of men's driving
    contradict; marked rows stay in the table and in the sensitivity range. Only the men's
    ratio marks a row: it is a property of the split, while the pooled ratio depends on the
    sex mix and the women's evidence does not rule out equal driving."""
    from dgt_stats.exposure_risk import coverage

    methods = _profile_methods()
    entries = []  # source, variant, profile method, non-working mix, remainder mix, km, profile
    for source, variant, profile, km in _variant_profiles():
        if profile is None:
            continue
        method = (
            methods[variant]
            if source in ("regional profile", "licence-calibrated transfer")
            else CENTRAL_METHOD
        )
        entries.append((source, variant, method, None, None, km, profile))
    # Weekend mixes change the age shares of the annual km, not the split within 65+.
    weekend = weekend_sensitivity()
    weekend = weekend[weekend.non_working_share_of_km.notna()]
    for (mix, share), part in weekend.groupby(["non_working_age_mix", "non_working_share_of_km"]):
        km = part.set_index("group").share_of_km
        entries.append(
            ("non-working days", f"{mix}, {share:.0%} of km", CENTRAL_METHOD, mix, None, km)
            + (emef_profile(),)
        )
    holders = licence_holders()
    owner = owner_km_by_group()
    total_km = dgt_car_km()["less taxi and ride-hailing"]
    rows = []

    def record(entry: tuple, split: str, older_share: float, km: pd.Series) -> None:
        source, variant, method, non_working, remainder = entry[:5]
        shares = km / km.sum()
        ratio = _older_ratios_to_reference(shares, older_share)
        per_holder = implied_km_per_holder(_older_ratios()[split])
        km_older = {"65-74": (1 - older_share) * shares["65+"], "75+": older_share * shares["65+"]}
        rows.append(
            {
                "source": source,
                "variant": variant,
                "assumption": split,
                "profile": method,
                "non_working_mix": non_working,
                "remainder_mix": remainder,
                "ratio_65_74": ratio["65-74"],
                "ratio_75_plus": ratio["75+"],
                "share_75_plus_of_65_plus": older_share,
                "men_km_per_holder_75_vs_65_74": per_holder["male"],
                "women_km_per_holder_75_vs_65_74": per_holder["female"],
                "pooled_km_per_holder_75_vs_65_74": float(
                    (km_older["75+"] / holders["75+"]) / (km_older["65-74"] / holders["65-74"])
                ),
                "km_per_holder_65_74_vs_45_64": float(
                    (km_older["65-74"] / holders["65-74"])
                    / (shares[REFERENCE] / holders[REFERENCE])
                ),
                "driver_over_owner_km_45_64": float(
                    shares[REFERENCE] * total_km / owner[REFERENCE]
                ),
                "driver_over_owner_km_65_74": float(km_older["65-74"] * total_km / owner["65-74"]),
                "driver_over_owner_km_75_plus": float(km_older["75+"] * total_km / owner["75+"]),
            }
        )

    for entry in entries:
        profile, km = entry[6], entry[5]
        for split in SPLITS:
            national = _split_older(profile, _older_ratios()[split])
            record(entry, split, national["75+"] / sum(national.values()), km)
    # The bound on the age mix of the older sample, under the central structure.
    for split in SPLITS:
        ratios = _older_ratios()[split]
        profile = composition_profile(emef_profile(), ratios)
        km, _ = national_km(profile)
        national = _split_older(profile, ratios)
        entry = ("older sample", COMPOSITION_VARIANT, CENTRAL_METHOD, None, None)
        record(entry, split, national["75+"] / sum(national.values()), km)
    # The kilometres the survey does not cover, given credible age mixes, with every profile.
    for scenario in coverage.scenario_km():
        if not scenario["credible"]:
            continue
        source, variant = _coverage_source(scenario)
        entry = (
            source,
            variant,
            scenario["profile"],
            scenario["non_working_mix"],
            scenario["remainder_mix"],
        )
        for split, share in scenario["share_75_plus_of_65_plus"].items():
            record(entry, split, share, scenario["shares"])
    out = pd.DataFrame(rows)
    out["at_odds_with_mens_driving"] = out.men_km_per_holder_75_vs_65_74 >= 1 - 1e-9
    out["flag_reason"] = np.where(out.at_odds_with_mens_driving, MARK_REASON, "")
    return out


COVERAGE_SOURCE = "uncovered kilometres"
COVERAGE_PROFILE_SOURCE = "regional profile with the uncovered kilometres"


def _coverage_source(scenario: dict) -> tuple[str, str]:
    """The sensitivity source and variant of a coverage scenario: Method A's profile alone, or
    another profile combined with the scenario."""
    from dgt_stats.exposure_risk import coverage

    label = coverage.scenario_label(scenario)
    if scenario["profile"] == CENTRAL_METHOD:
        return COVERAGE_SOURCE, label
    return COVERAGE_PROFILE_SOURCE, f"{scenario['profile'].split(': ', 1)[1]}; {label}"


# ----------------------------------------------------------------------------- weekends


# Estatuto de los Trabajadores, art. 37.2: at most fourteen paid public holidays a year, two of
# them local. Holidays that fall on a Sunday are usually moved to a weekday, so the working days
# of a year are its weekdays less fourteen.
PUBLIC_HOLIDAYS = 14
# A non-working day's resident car driving relative to a working day's: 60% or as much. The two
# values bound the sensitivity analysis; neither is a measurement (MOVILIA 2006 counts 0.83
# times as many car trips on a weekend day, drivers and passengers, and longer trips).
NON_WORKING_RATIOS = (0.6, 1.0)


def working_days(year: int = YEAR) -> tuple[int, int]:
    """Working and non-working days of ``year`` in Spain."""
    weekdays = int(np.busday_count(f"{year}-01-01", f"{year + 1}-01-01"))
    days = int((pd.Timestamp(f"{year + 1}-01-01") - pd.Timestamp(f"{year}-01-01")).days)
    working = weekdays - PUBLIC_HOLIDAYS
    return working, days - working


def non_working_shares(year: int = YEAR) -> tuple[float, ...]:
    """Share of annual km driven on non-working days if each carries each ratio of
    :data:`NON_WORKING_RATIOS` of a working day's driving (about 22% and 32%)."""
    working, other = working_days(year)
    return tuple(other * r / (working + other * r) for r in NON_WORKING_RATIOS)


NON_WORKING_SHARES = non_working_shares()


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
    yield "older sample", EMPLOYMENT_VARIANT, profile, national_km(profile)[0]


def sensitivity() -> pd.DataFrame:
    """Every group's ratio to 45-64 (involved and killed per km) under each alternative choice,
    beside the central Method A; the weekend mixes come from :func:`weekend_sensitivity`, and the
    credible age mixes of the kilometres the survey does not cover from
    :func:`dgt_stats.exposure_risk.coverage.scenario_km`, with Method A's profile and with each
    other profile (the two largest uncertainties, taken together)."""
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
    # Too few people aged 75 and over in the older sample, at its bound, with the Madrid split.
    bound = composition_profile(emef_profile(), _older_ratios()[REFERENCE_SPLIT])
    record("older sample", COMPOSITION_VARIANT, national_km(bound)[0])
    weekend = weekend_sensitivity()
    weekend = weekend[weekend.non_working_share_of_km.notna()]
    for (mix, share), part in weekend.groupby(["non_working_age_mix", "non_working_share_of_km"]):
        km = part.set_index("group").share_of_km
        record("non-working days", f"{mix}, {share:.0%} of km", km)
    from dgt_stats.exposure_risk import coverage

    for scenario in coverage.scenario_km():
        if scenario["credible"]:
            record(*_coverage_source(scenario), scenario["shares"])
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


# ----------------------------------------------------------------------------- 75 and over: anatomy


def _row_profile(row: pd.Series) -> tuple[dict, str]:
    """The km-per-resident profile behind a row of :func:`older_sensitivity`, and the survey its
    replicates resample."""
    method = str(row.profile)
    if method == MADRID_METHOD:
        return edm_profile(), "EDM2018 (Madrid profile)"
    if method == LICENCE_METHOD:
        return licence_calibrated(emef_profile()), "EMEF (province of Barcelona)"
    if method.startswith("C: EMEF, "):
        area = method.removeprefix("C: EMEF, ")
        return emef_profile(area), f"EMEF ({area})"
    source, variant = str(row.source), str(row.variant)
    if source == "distance":
        profile = emef_profile(column=variant)
    elif source == "survey years":
        profile = emef_profile(years=tuple(int(y) for y in variant.split("-")))
    elif source == "professionals' work driving":
        fraction = float(variant.split("%")[0]) / 100
        profile = emef_profile(column=_professional_column(fraction))
    elif source == "older sample" and variant == EMPLOYMENT_VARIANT:
        profile = emef_profile(employment_reweighted=True)
    elif source == "older sample" and variant == COMPOSITION_VARIANT:
        profile = composition_profile(emef_profile(), _older_ratios()[str(row.assumption)])
    else:
        profile = emef_profile()
    return profile, "EMEF (province of Barcelona)"


def _row_structure(row: pd.Series) -> tuple[tuple | None, tuple[str, ...]]:
    """How a row allocates the km outside the survey's working days, and the external weights
    that allocation holds fixed."""
    from dgt_stats.exposure_risk import coverage

    named = {
        coverage.OWNER_MIX: "DGT owner-age km",
        coverage.LONG_DISTANCE_MIX: f"{coverage.MOVILIA_LONG} weights",
        EMEF_WEEKEND_PROXY: "EMEF 2023 weekend weights",
        MOVILIA_WEEKEND: f"{coverage.MOVILIA_DAILY} weekend weights",
    }
    if row.source in (COVERAGE_SOURCE, COVERAGE_PROFILE_SOURCE):
        structure = ("coverage", row.non_working_mix, row.remainder_mix, coverage.PROFESSIONAL_MIX)
        fixed = ["coverage weights", "professionals' age mix"]
        fixed += [named[m] for m in (row.non_working_mix, row.remainder_mix) if m in named]
        return structure, tuple(dict.fromkeys(fixed))
    if row.source == "non-working days":
        share = next(s for s in NON_WORKING_SHARES if f"{s:.0%} of km" in str(row.variant))
        return ("weekend", row.non_working_mix, share), (named[row.non_working_mix],)
    return None, ()


EXTREMES = (
    ("full minimum", "min", False),
    ("full maximum", "max", False),
    ("lowest unmarked", "min", True),
    ("highest unmarked", "max", True),
)


def older_extremes(table: pd.DataFrame | None = None) -> pd.DataFrame:
    """Joint 95% sampling intervals at the ends of the sensitivity range: the lowest and highest
    of all rows of :func:`older_sensitivity`, and of the rows not marked as at odds with men's
    driving, for 75 and over and for 65-74.

    The replicates are those of the row's profile (the EMEF area's, or the Madrid survey's for the
    Madrid profile), crossed with the Madrid survey's for a Madrid split when the profile comes
    from the EMEF, and paired one to one when profile and split both come from the Madrid survey,
    with gamma draws of the counts. The mixes' external weights, the coverage weights and the
    RACC constant are held fixed and named in ``sampling_sources``, so these intervals are too
    narrow if anything. The sensitivity range joins point values; these intervals say how far
    sampling error alone could move its ends."""
    table = older_sensitivity() if table is None else table
    unmarked = table[~table.at_odds_with_mens_driving]
    rows = []
    for group, column in (("75+", "ratio_75_plus"), ("65-74", "ratio_65_74")):
        for kind, end, clear in EXTREMES:
            pool = unmarked if clear else table
            row = pool.loc[pool[column].idxmin() if end == "min" else pool[column].idxmax()]
            split = str(row.assumption)
            profile, profile_source = _row_profile(row)
            structure, fixed = _row_structure(row)
            matched = str(row.profile) == MADRID_METHOD and split in EDM_SPLITS
            draws75, draws65 = _older_draws(
                profile, _split_replicates(split), structure, matched=matched
            )
            interval = _interval(draws75 if group == "75+" else draws65)
            replicates = (
                "paired one to one (profile and split from the same resample)"
                if matched
                else "crossed"
                if split in EDM_SPLITS
                else "profile only"
            )
            rows.append(
                {
                    "group": group,
                    "end": kind,
                    "source": row.source,
                    "variant": row.variant,
                    "assumption": split,
                    "profile": row.profile,
                    "non_working_mix": row.non_working_mix,
                    "remainder_mix": row.remainder_mix,
                    "at_odds_with_mens_driving": bool(row.at_odds_with_mens_driving),
                    "value": float(row[column]),
                    "ratio_low": interval["low"],
                    "ratio_high": interval["high"],
                    "mc_se_low": interval["mc_se_low"],
                    "mc_se_high": interval["mc_se_high"],
                    "replicates": replicates,
                    "sampling_sources": _sampling_sources(split, profile_source, fixed),
                }
            )
    return pd.DataFrame(rows)


# One-at-a-time factors of the 75+ figure, each a source of :func:`older_sensitivity` (or a
# computation of its own), with the label of the research table and the short label of the chart.
# A short label names the assumption that changes, not a cause of crashes, and keeps its long
# label's subject: the remainder is the km no measured part explains, not the km outside working
# days, which also hold the weekends of the separate "non-working days" bar.
DECOMPOSITION_FACTORS: dict[str, tuple[str, str]] = {
    "regional profile": (
        "Region whose age profile stands in for Spain (four parts of the province of Barcelona, "
        "and Madrid)",
        "Region used for the age profile",
    ),
    "split": ("Split of the 65-and-over km between 65–74 and 75 and over", "Split of the 65+ km"),
    "remainder": (
        "Age mix of the km that no measured part of DGT's total explains (the unexplained km)",
        "Age mix of the unexplained km",
    ),
    "distance": ("Conversion of trips to kilometres", "Trip-to-km conversion"),
    "non-working days": (
        "Weekends and holidays at a share of the km with a weekend age mix",
        "Weekend and holiday age mix",
    ),
    "professionals' work driving": (
        "Professional drivers' work driving added",
        "Professionals' km added",
    ),
    "composition": (
        "Share aged 75 and over in the survey's 65+ sample at the routing-identified share (bound)",
        "75+ share of the sample at its bound",
    ),
    "licence-calibrated transfer": (
        "Survey's driving carried to Spain per licence holder instead of per resident",
        "carried to Spain per licence holder",
    ),
    "employment": (
        "Share in work among the survey's older respondents set to the census",
        "share in work among older respondents",
    ),
    "survey years": ("Other survey years", "survey years"),
}


def _remainder_only(split: str = REFERENCE_SPLIT) -> pd.Series:
    """The 75+ ratio with each credible age mix for the km no measured part explains, and every
    other part (the non-working days and the professionals' work driving included) at the
    survey's working-day mix, so that only this one choice varies."""
    from dgt_stats.exposure_risk import coverage

    profile = emef_profile()
    km, _ = national_km(profile)
    base = km / km.sum()
    national = _split_older(profile, _older_ratios()[split])
    q = national["75+"] / sum(national.values())
    out = {}
    for remainder in coverage.REMAINDER_MIXES:
        if remainder in coverage.BOUNDS:
            continue
        shares, older = coverage.structure_shares(
            base, q, coverage.WORKING_DAY_MIX, remainder, coverage.WORKING_DAY_MIX
        )
        out[remainder] = _older_ratios_to_reference(shares, older)["75+"]
    return pd.Series(out)


def older_decomposition(
    table: pd.DataFrame | None = None, split_table: pd.DataFrame | None = None
) -> pd.DataFrame:
    """What moves the 75+ figure: the whole sensitivity range (``kind`` = ``all``), and each
    choice varied one at a time with every other choice as in the conditional estimate (the
    Madrid split per resident, Method A, the central treatments), the estimate's own choice
    included. ``clear_low`` and ``clear_high`` span the values reached by rows not marked as at
    odds with men's driving; ``hatched_low`` to ``hatched_high`` is the part reached only by
    marked rows. A bar's length depends on which alternatives were tried, not on how likely
    they are, and it carries no sampling error."""
    table = older_sensitivity() if table is None else table
    split_table = older_split() if split_table is None else split_table
    oldest = split_table[split_table.group == "75+"].set_index("assumption").ratio_to_45_64
    estimate = float(oldest[REFERENCE_SPLIT])
    reference = table[table.assumption == REFERENCE_SPLIT]
    values: dict[str, pd.Series] = {}
    marked: dict[str, pd.Series] = {}
    for source in (
        "regional profile",
        "distance",
        "non-working days",
        "professionals' work driving",
        "licence-calibrated transfer",
        "survey years",
    ):
        values[source] = reference[reference.source == source].set_index("variant").ratio_75_plus
    older = reference[reference.source == "older sample"].set_index("variant").ratio_75_plus
    values["composition"] = older[[COMPOSITION_VARIANT]]
    values["employment"] = older[[EMPLOYMENT_VARIANT]]
    values["remainder"] = _remainder_only()
    values["split"] = oldest
    marked["split"] = pd.Series({split: split == EQUAL_SPLIT for split in oldest.index}, dtype=bool)
    rows = []
    unmarked = table[~table.at_odds_with_mens_driving].ratio_75_plus
    low, high = float(table.ratio_75_plus.min()), float(table.ratio_75_plus.max())
    rows.append(
        {
            "kind": "all",
            "factor": "all",
            "label": "All combinations tested (the sensitivity range)",
            "short_label": "All combinations tested",
            "n_variants": len(table),
            "low": low,
            "high": high,
            "clear_low": float(unmarked.min()),
            "clear_high": float(unmarked.max()),
            "one_at_a_time": False,
        }
    )
    for factor, series in values.items():
        flags = marked.get(factor, pd.Series(False, index=series.index))
        with_estimate = pd.concat([series, pd.Series({"estimate": estimate})])
        clear = pd.concat([series[~flags], pd.Series({"estimate": estimate})])
        label, short = DECOMPOSITION_FACTORS[factor]
        rows.append(
            {
                "kind": "factor",
                "factor": factor,
                "label": label,
                "short_label": short,
                "n_variants": len(series) + int(not np.isclose(series, estimate).any()),
                "low": float(with_estimate.min()),
                "high": float(with_estimate.max()),
                "clear_low": float(clear.min()),
                "clear_high": float(clear.max()),
                "one_at_a_time": True,
            }
        )
    out = pd.DataFrame(rows)
    out["log_width"] = np.log(out.high / out.low)
    hatched = out.low < out.clear_low - 1e-12
    out["hatched_low"] = np.where(hatched, out.low, np.nan)
    out["hatched_high"] = np.where(hatched, out.clear_low, np.nan)
    if bool((out.high > out.clear_high + 1e-12).any()):
        raise ValueError("75+ decomposition: a marked row above the unmarked ones")
    out["estimate"] = estimate
    factors = out[out.kind == "factor"].sort_values("log_width", ascending=False)
    return pd.concat([out[out.kind == "all"], factors], ignore_index=True)


ATTRIBUTION_FACTORS = {
    "profile": "profile",
    "non_working_mix": "non-working days",
    "remainder_mix": "remainder",
    "assumption": "split",
}


def _shapley_variance(cube: np.ndarray) -> np.ndarray:
    """Shapley shares of the variance of ``cube`` (a full factorial, one axis per factor, levels
    equally weighted) among its axes."""
    import itertools
    import math

    d = cube.ndim
    total = float(cube.var())

    def closed(subset: frozenset) -> float:
        if not subset:
            return 0.0
        axes = tuple(i for i in range(d) if i not in subset)
        return float((cube.mean(axis=axes) if axes else cube).var())

    shares = np.zeros(d)
    for i in range(d):
        others = [j for j in range(d) if j != i]
        for k in range(d):
            for subset in itertools.combinations(others, k):
                weight = math.factorial(k) * math.factorial(d - k - 1) / math.factorial(d)
                shares[i] += weight * (closed(frozenset(subset) | {i}) - closed(frozenset(subset)))
    return shares / total


def older_attribution(table: pd.DataFrame | None = None) -> pd.DataFrame:
    """Shapley shares of the variance of the log 75+ ratio over the one full factorial the
    sensitivity table holds: profile x non-working-day mix x remainder mix x split (the rows of
    the two coverage sources), with all four splits and without the equal split.

    Descriptive only. The shares depend on which alternatives were tried and how many levels each
    factor has: adding or dropping one split moves them a lot. They are not evidence of which
    data would narrow the range most."""
    table = older_sensitivity() if table is None else table
    cells = table[table.source.isin([COVERAGE_SOURCE, COVERAGE_PROFILE_SOURCE])]
    factors = list(ATTRIBUTION_FACTORS)
    out = {}
    for name, part in (
        ("all_splits", cells),
        ("without_equal_split", cells[cells.assumption != EQUAL_SPLIT]),
    ):
        if part.groupby(factors).size().ne(1).any():
            raise ValueError("75+ attribution: the coverage rows are not one full factorial")
        levels = [sorted(part[f].unique()) for f in factors]
        cube = (
            part.set_index(factors)
            .ratio_75_plus.reindex(pd.MultiIndex.from_product(levels, names=factors))
            .to_numpy()
        )
        if np.isnan(cube).any():
            raise ValueError("75+ attribution: missing cells in the factorial")
        cube = np.log(cube.reshape([len(level) for level in levels]))
        out[name] = (_shapley_variance(cube), float(cube.std()))
    return pd.DataFrame(
        {
            "factor": [ATTRIBUTION_FACTORS[f] for f in factors],
            "share_all_splits": out["all_splits"][0],
            "share_without_equal_split": out["without_equal_split"][0],
            "sd_log_all": out["all_splits"][1],
            "sd_log_without_equal": out["without_equal_split"][1],
        }
    )


MADRID_PROVINCE = "28"
# The names of the checks in :func:`reference_checks`, read by the pages.
CHECK_PREVALENCE = f"B-licence holders per resident, 75 and over over 65-74 (DGT {YEAR})"
CHECK_MADRID_PER_HOLDER = (
    f"Madrid {edm2018.SURVEY_YEAR} car-driver km per DGT licence holder, 75 and over over 65-74"
)
CHECK_TRANSFER = "Working-day car-driver km per resident in Spain, 65 and over over 45-64"
CHECK_PER_HOLDER = "Car drivers involved in injury crashes per 1,000 B-licence holders"
CHECK_HOLDER_RATIO = "Car drivers involved per B-licence holder, 75 and over over 45-64"
CHECK_LICENCE_TREND = (
    f"Licence holders of any class per resident aged 75 and over, {YEAR} over "
    f"{edm2018.SURVEY_YEAR} (DGT census, INE)"
)
CHECK_LICENCE_GRADIENT_TREND = (
    "Licence holders of any class per resident, 75 and over over 65-74, "
    f"{YEAR} over {edm2018.SURVEY_YEAR} (DGT census, INE)"
)
CHECK_COHORT_UPDATE = (
    "Conditional estimate, 75 and over over 45-64, with the Madrid ratios scaled by that change "
    f"in licence holding (driving per holder as in {edm2018.SURVEY_YEAR}; exploratory)"
)


def reference_checks() -> pd.DataFrame:
    """The checks the conditional estimate is read against, in one long table: licence holding
    at 75 and over against 65-74 by place, the Madrid survey's km per registered licence holder,
    what each split implies per licence holder, the 65+ km per resident after transfer under the
    EMEF and Madrid profiles, DGT's owner km, and involvement per licence holder by age with a
    count-only interval. None of these is used to compute the estimate."""
    rows = []

    def add(check: str, subject: str, value: float, low=np.nan, high=np.nan, note: str = ""):
        rows.append(
            {
                "check": check,
                "subject": subject,
                "value": float(value),
                "low": float(low),
                "high": float(high),
                "note": note,
            }
        )

    places = {MADRID_PROVINCE: "province of Madrid", BARCELONA_PROVINCE: "province of Barcelona"}
    for code, place in (*places.items(), (None, "Spain")):
        for sex, ratio in older_prevalence_ratio(code).items():
            add(
                CHECK_PREVALENCE,
                f"{place}, {sex}",
                ratio,
            )
    madrid = edm2018.like_for_like_per_holder(older_prevalence_ratio(MADRID_PROVINCE))
    for row in madrid.itertuples():
        add(
            CHECK_MADRID_PER_HOLDER,
            row.sex,
            row.ratio_per_dgt_holder,
            row.ratio_low,
            row.ratio_high,
            "EDM2018 ratio per resident over DGT 2024 licence holding in the province of Madrid",
        )
    holders = older_licence_prevalence().groupby("group").b_licence_holders.sum()
    for split in SPLITS:
        ratios = _older_ratios()[split]
        per_holder = implied_km_per_holder(ratios)
        national = _split_older(emef_profile(), ratios)
        pooled = (national["75+"] / holders["75+"]) / (national["65-74"] / holders["65-74"])
        for sex, value in (*per_holder.items(), ("both sexes", pooled)):
            add(
                "Implied km per DGT licence holder, 75 and over over 65-74",
                f"{split}; {sex}",
                value,
            )
    people = population_by_group().groupby("group").population.sum()
    for method, profile in ((CENTRAL_METHOD, emef_profile()), (MADRID_METHOD, edm_profile())):
        km, _ = national_km(profile)
        add(
            CHECK_TRANSFER,
            method,
            (km["65+"] / people["65+"]) / (km[REFERENCE] / people[REFERENCE]),
        )
    owner = io_exposure.read_exposure("km_edad_propietario_2024")
    cars = owner[(owner.vehicle_group == "car") & (owner.year == YEAR) & ~owner.is_company]
    by_band = cars.groupby("band")[["total_km", "n_vehicles"]].sum()
    lic = licence_holders()
    owned = {
        "65-74": by_band.loc[["65-69", "70-74"]].sum(),
        "75+": by_band.loc["75+"],
    }
    note = "owner km cannot say who drove"
    add(
        "Km of cars registered to private owners, 75 and over over 65-74",
        "per resident",
        (owned["75+"].total_km / people["75+"]) / (owned["65-74"].total_km / people["65-74"]),
        note=note,
    )
    add(
        "Km of cars registered to private owners, 75 and over over 65-74",
        "per car",
        (owned["75+"].total_km / owned["75+"].n_vehicles)
        / (owned["65-74"].total_km / owned["65-74"].n_vehicles),
        note=note,
    )
    add(
        "Km of cars registered to private owners, 75 and over over 65-74",
        "per B-licence holder",
        (owned["75+"].total_km / lic["75+"]) / (owned["65-74"].total_km / lic["65-74"]),
        note=note,
    )
    for group in OLDER:
        add(
            "Cars registered to private owners per B-licence holder",
            group,
            owned[group].n_vehicles / lic[group],
        )
    # Licence holding at 75 and over since the Madrid survey's year, alone and against 65-74
    # (holders of any class, Spain: the 2018 census tables give licences by age for all classes
    # together; B licences by age come only from the text files of later years).
    census = io_exposure.licence_holders_by_age().set_index(["year", "sex", "band"]).n_drivers
    older_bands = {"65-74": ("65-69", "70-74"), "75+": ("75+",)}
    gradient_change = {}
    for sex in SEXES:
        per_resident: dict[tuple[int, str], float] = {}
        for year in (edm2018.SURVEY_YEAR, YEAR):
            people = io_population.population(year, REFERENCE_DATE, sex)
            for group, bands in older_bands.items():
                low, high = GROUP_AGES[group]
                residents = float(people[people.age_low.between(low, high)].population.sum())
                licensed = sum(float(census[(year, sex, band)]) for band in bands)
                per_resident[(year, group)] = licensed / residents
        add(
            CHECK_LICENCE_TREND,
            sex,
            per_resident[(YEAR, "75+")] / per_resident[(edm2018.SURVEY_YEAR, "75+")],
        )
        gradient = {
            year: per_resident[(year, "75+")] / per_resident[(year, "65-74")]
            for year in (edm2018.SURVEY_YEAR, YEAR)
        }
        gradient_change[sex] = gradient[YEAR] / gradient[edm2018.SURVEY_YEAR]
        add(CHECK_LICENCE_GRADIENT_TREND, sex, gradient_change[sex])
    # If driving per licence holder at each age stayed as in the Madrid survey's year, the ratio
    # per resident moves with the ratio of licence holding: an extrapolation, not a measurement.
    profile = emef_profile()
    km, _ = national_km(profile)
    madrid_ratios = _older_ratios()[REFERENCE_SPLIT]
    updated = _split_older(
        profile, {sex: madrid_ratios[sex] * gradient_change[sex] for sex in SEXES}
    )
    add(
        CHECK_COHORT_UPDATE,
        "both sexes",
        _older_ratios_to_reference(km, updated["75+"] / sum(updated.values()))["75+"],
        note="assumes km per licence holder at 65-74 and at 75 and over as in Madrid in "
        f"{edm2018.SURVEY_YEAR}",
    )
    counts = drivers_involved().set_index("group").involved
    for group in ("75+", "65-74", REFERENCE):
        add(
            CHECK_PER_HOLDER,
            group,
            1000 * float(counts[group]) / float(lic[group]),
        )
    rng = np.random.default_rng(SEED)
    draws = rng.gamma(float(counts["75+"]) + 0.5, 1.0, 100_000) / rng.gamma(
        float(counts[REFERENCE]) + 0.5, 1.0, 100_000
    )
    scale = float(lic[REFERENCE]) / float(lic["75+"])
    add(
        CHECK_HOLDER_RATIO,
        "count-only 95% interval",
        float(counts["75+"]) / float(counts[REFERENCE]) * scale,
        float(np.percentile(draws, 2.5)) * scale,
        float(np.percentile(draws, 97.5)) * scale,
        "Poisson error in the two counts only",
    )
    return pd.DataFrame(rows)
