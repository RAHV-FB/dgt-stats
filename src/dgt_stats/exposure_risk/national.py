"""Spain: car-driving kilometres by driver age, and car drivers involved in injury crashes per
kilometre (Tasks 14-17).

No national source measures kilometres by the driver's age, so four methods are compared.

* **A, demographic calibration.** The EMEF's working-day car-driver km per resident by age group
  and sex (province of Barcelona, 2022-2024) is applied to the population of Spain on 1 July 2024
  (INE, single years of age). This gives each age group's share of driving, assuming that, within
  an age group and sex, residents of Spain drive in the same proportion to one another as
  residents of the province of Barcelona.
* **B, kilometre scale.** Those shares are applied to DGT's 2024 total of car kilometres
  (inspection odometer readings, annualised), less taxi and ride-hailing cars, whose drivers drive
  for a living and are outside both the EMEF and the crash numerator used here. The level of the
  rates depends on B; their ratios between ages do not.
* **C, regional calibration.** Method A repeated with the age profile of each part of the province
  (Barcelona city, the rest of the metropolitan area, the rest of the metropolitan region and the
  rest of the province) and with the Madrid household survey of 2018 (:mod:`dgt_stats.edm2018`).
  The spread is the uncertainty of transferring one region's profile to Spain.
* **D, registered owners.** DGT's 2024 kilometres by the registered owner's age band, the
  denominator of the former driver-age figure. Cars are driven by people other than their owners
  and company cars carry no age, so D is a sensitivity comparison only.

**Numerator.** Car drivers involved in injury crashes in Spain in 2024 (DGT, tables 4.2 I and U),
private cars with and without trailer; drivers of public-service cars (taxi and ride-hailing) are
left out to match the denominator. The EMEF group 16-29 is matched to drivers aged 18-29: residents
aged 16 and 17 count in its population but cannot hold a car licence, and the 41 drivers aged
15-17 in the tables are left out. Drivers of unrecorded age (2.2%) are allocated across ages in
proportion for the absolute rates; the ratios between ages do not depend on that allocation.

**Uncertainty.** Each interval pairs the EMEF bootstrap replicates (sampling error of the
exposure shares) with gamma draws for the counts (Poisson error), replicate by replicate. The
spread between methods and variants is reported separately, as a sensitivity range.

**Ages 75 and over.** The EMEF stops at 65 and over. :func:`older_split` divides that group's
km between 65-74 and 75 and over using the ratio of their km per resident in the Madrid survey,
by sex, and the population of each age in the province of Barcelona and in Spain. It is a
*model-dependent* estimate, reported beside the measured 65-and-over figure and never in its
place, with three alternatives: equal km per licence holder at 65-74 and 75 and over (an upper
bound for 75 and over), the Madrid km per licence holder applied to Spain's licence holders, and
the registered owners' km.
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
def _emef_frame(area: str | None = None) -> tuple[pd.DataFrame, np.ndarray]:
    frame = exposure.person_day()
    frame = frame[frame.year.isin(exposure.CONTEMPORARY_YEARS)]
    if area is not None:
        frame = frame[frame.zone_code.isin(exposure.AREAS[area])]
    frame = frame.reset_index(drop=True)
    return frame, exposure.replicate_factors(frame)


def emef_profile(area: str | None = None, column: str = "car_km") -> dict:
    """Working-day car-driver km per resident by (sex, group), point and bootstrap replicates."""
    frame, factors = _emef_frame(area)
    out = {}
    for sex in SEXES:
        for group in GROUPS:
            mask = ((frame.sex == sex) & (frame.age4 == group)).to_numpy()
            w = frame.weight.to_numpy()[mask]
            km = frame[column].to_numpy()[mask]
            f = factors[mask]
            out[(sex, group)] = (float((w * km).sum() / w.sum()), ((w * km) @ f) / (w @ f))
    return out


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


def exposure_profiles() -> dict[str, tuple[pd.Series, np.ndarray]]:
    """National working-day km per day by group under Method A and each Method C profile."""
    out = {"A: EMEF, province of Barcelona": national_km(emef_profile())}
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


def older_split(km_variant: str = "less taxi and ride-hailing") -> pd.DataFrame:
    """Model-dependent kilometres and rates for 65-74 and 75 and over (Method A/B, central)."""
    profile = emef_profile()
    bcn = barcelona_older_population().set_index(["sex", "group"]).population
    spain = population_by_group().set_index(["sex", "group"]).population
    km, _ = national_km(profile)
    total_km = dgt_car_km()[km_variant]
    counts = drivers_involved().set_index("group")
    reference_rate = float(counts.loc[REFERENCE, "involved"]) / (
        float(km[REFERENCE] / km.sum()) * total_km / BILLION
    )
    # The split divides the measured 65+ kilometres of Method B; it never changes their total.
    km_65 = float(km["65+"] / km.sum()) * total_km
    rows = []
    for assumption, ratios in _older_ratios().items():
        national = {"65-74": 0.0, "75+": 0.0}
        for sex in SEXES:
            k65 = profile[(sex, "65+")][0]
            r = ratios[sex]
            young, old = bcn[(sex, "65-74")], bcn[(sex, "75+")]
            k_young = k65 * (young + old) / (young + r * old)
            national["65-74"] += k_young * spain[(sex, "65-74")]
            national["75+"] += r * k_young * spain[(sex, "75+")]
        for group in OLDER:
            billion_km = national[group] / sum(national.values()) * km_65 / BILLION
            rate = float(counts.loc[group, "involved"]) / billion_km
            rows.append(
                {
                    "assumption": assumption,
                    "group": group,
                    "ratio_75_to_65_74_male": ratios["male"],
                    "ratio_75_to_65_74_female": ratios["female"],
                    "share_of_65_plus_km": national[group] / sum(national.values()),
                    "billion_km": billion_km,
                    "involved": float(counts.loc[group, "involved"]),
                    "involved_per_bn_km": rate,
                    "ratio_to_45_64": rate / reference_rate,
                }
            )
    owner = owner_km_shares()
    owner_older = owner[["65-74", "75+"]]
    for group in OLDER:
        billion_km = float(owner_older[group] / owner_older.sum()) * km_65 / BILLION
        rate = float(counts.loc[group, "involved"]) / billion_km
        rows.append(
            {
                "assumption": "registered owners' split of the 65+ km",
                "group": group,
                "share_of_65_plus_km": float(owner_older[group] / owner_older.sum()),
                "billion_km": billion_km,
                "involved": float(counts.loc[group, "involved"]),
                "involved_per_bn_km": rate,
                "ratio_to_45_64": rate / reference_rate,
            }
        )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- weekends


# Non-working days (weekends and public holidays) are about 117 of 365 days. If a non-working
# day carries as much car driving as a working day they hold 32% of annual km; if it carries 60%
# as much, 22%. The two values bound the sensitivity analysis; neither is a measurement.
NON_WORKING_SHARES = (0.22, 0.32)


def weekend_weights() -> pd.Series:
    """How much more (or less) each group drives on weekends than on working days, relative to
    everyone aged 16 and over, as far as the EMEF 2023 shows it: the share of residents who drove
    away for at least one of the last four weekends, over the share who drove on the reference
    working day, each relative to all residents."""
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


def weekend_sensitivity(km_variant: str = "less taxi and ride-hailing") -> pd.DataFrame:
    """Method A/B rates if non-working days hold a different share of km and a different age mix."""
    km, _ = national_km(emef_profile())
    workday = km / km.sum()
    weights = weekend_weights()
    total_km = dgt_car_km()[km_variant]
    counts = drivers_involved().set_index("group").involved
    rows = []
    for mix in ("same age mix as working days", "EMEF 2023 weekend trips"):
        alpha = pd.Series(1.0, index=GROUPS) if mix.startswith("same") else weights
        weekend = alpha * workday / float((alpha * workday).sum())
        for share in NON_WORKING_SHARES:
            annual = (1 - share) * workday + share * weekend
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


# ----------------------------------------------------------------------------- old figure


def owner_age_comparison() -> pd.DataFrame:
    """The former figure (involvement per km of cars registered to owners of each age, all car
    types including public service) beside the driver-age estimate of Method A/B."""
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
    new = rates()
    new = new[new.method.str.startswith("A:")]
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
