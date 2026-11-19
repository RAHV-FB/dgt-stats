"""Spain: car-driving kilometres by driver age, and car drivers involved in injury crashes per
kilometre.

No national source measures kilometres by the driver's age, so they are estimated.

* **Profiles.** The EMEF's working-day car-driver km per resident by age group and sex (province
  of Barcelona, 2022-2024; :func:`emef_profile`) and the Madrid household survey of 2018 (km per
  resident by exact age; :func:`edm_profile`) are each applied to the population of Spain on 1
  July 2024 (INE, single years of age), which gives each age group's share of driving. This
  assumes that, within an age group and sex, residents of Spain drive in the same proportion to
  one another as the survey's residents. The Madrid survey gives exact ages, so its 65+ km per
  resident is standardised to Spain's population at 65-74 and 75 and over.
* **Licence-calibrated transfer (A2).** The Barcelona profile carrying km per B-licence holder
  instead of per resident: each group's km per resident is scaled by the ratio of Spain's
  B-licence prevalence to the province's (DGT driver census 2024, INE population), by sex.
* **Kilometre scale.** The shares are applied to DGT's 2024 total of car kilometres (inspection
  odometer readings, annualised), less taxi and ride-hailing cars, whose drivers drive for a
  living and are outside both the EMEF and the crash numerator used here. The level of the rates
  depends on it; their ratios between ages do not.

**Central estimate.** The published rates use the mean of the Barcelona and Madrid profiles
(:func:`average_profile`): each group's share of the kilometres is the mean of its shares under
the two surveys. Every other profile is an alternative in the ranges
(:mod:`dgt_stats.exposure_risk.ranges`).

**Numerator.** Car drivers involved in injury crashes in Spain in 2024 (DGT, tables 4.2 I and U),
private cars with and without trailer; drivers of public-service cars (taxi and ride-hailing) are
left out to match the denominator. The EMEF group 16-29 is matched to drivers aged 18-29:
residents aged 16 and 17 count in its population but cannot hold a car licence, and the 41 drivers
aged 15-17 in the tables are left out. Drivers of unrecorded age (2.3% of those involved) are left
out of every rate; the ratios between ages are unchanged by that only if their ages follow the
recorded mix.

**Uncertainty.** Each interval crosses the EMEF bootstrap replicates (sampling error of the
exposure shares) with :data:`COUNT_DRAWS` gamma draws of the counts (Poisson error) per replicate,
and carries the Monte Carlo standard error of each end (:func:`_interval`). The spread between
alternative assumptions is reported separately, as a range.

**Ages 75 and over.** The EMEF stops at 65 and over. :func:`older_split` divides that group's
km between 65-74 and 75 and over under three splits (:data:`SPLITS`), by sex, using the
population of each age in the province of Barcelona and in Spain. The Madrid survey's ratio of km
per resident (:data:`REFERENCE_SPLIT`) gives a *conditional* estimate, reported beside the measured
65-and-over figure and never in its place, with a joint sampling interval over both surveys'
replicates. The other splits are the Madrid km per licence holder on DGT's register applied to
Spain's licence holders, and equal km per licence holder at 65-74 and 75 and over.
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
# schools (A03) are driven by ordinary drivers and learners, and stay in.
PROFESSIONAL_SERVICES = ("A04", "A02")


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
    """Every EMEF respondent with the reference day's car-driver km, and with the work driving of
    mobility professionals added at each assumed car share."""
    frame = exposure.person_day()
    for fraction in exposure.PROFESSIONAL_CAR_SHARES:
        frame[_professional_column(fraction)] = frame.car_km + exposure.professional_km(fraction)
    return frame


def _professional_column(fraction: float) -> str:
    return f"professionals: {fraction:.0%} of work trips by car"


@cache
def _emef_frame(
    area: str | None = None,
    years: tuple[int, ...] = exposure.CONTEMPORARY_YEARS,
) -> tuple[pd.DataFrame, np.ndarray]:
    frame = _person_frame()
    frame = frame[frame.year.isin(years)]
    if area is not None:
        frame = frame[frame.zone_code.isin(exposure.AREAS[area])]
    frame = frame.reset_index(drop=True)
    return frame, exposure.replicate_factors(frame)


def emef_profile(
    area: str | None = None,
    column: str = "car_km",
    years: tuple[int, ...] = exposure.CONTEMPORARY_YEARS,
) -> dict:
    """Working-day car-driver km per resident by (sex, group), point and bootstrap replicates."""
    frame, factors = _emef_frame(area, years)
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
    """The Madrid survey's car-driver km per resident by (sex, group), point and household
    replicates, with its own cells at 65-74 and 75 and over (exact ages).

    The 65+ cell is standardised to Spain's population: Madrid's km per resident at 65-74 and at
    75 and over, weighted by Spain's residents of those ages and sex on 1 July 2024, replicate by
    replicate. Madrid's own 65+ mean would carry the age mix of Madrid's 65-and-over residents,
    fewer of them aged 75 and over than Spain's, to Spain's older population. The EMEF profiles
    are not standardised: the survey's public files group everyone aged 65 and over, so their
    65+ km per resident is a mean over the residents of those ages in the profile's area (the
    province of Barcelona for profiles A and A2, slightly older than Spain's), carried to Spain
    as it stands. Standardising it would need the 75+/65-74 ratio that each split assumes and
    would no longer give 65-74 and 75+ km that add up to the unsplit 65+ km; for profile A,
    under the Madrid split, it would lower the 65+, 65-74 and 75+ ratios by under 1%. The
    four sub-area profiles are split between 65-74 and 75+ with the province's population
    (:func:`_older_mean_population`), an approximation: no population by single age is
    archived for Barcelona city or the other sub-areas. The drivers page says which profile is
    standardised."""
    frame = edm2018.person_day()
    factors = edm2018.replicate_factors()
    spain = population_by_group().set_index(["sex", "group"]).population
    out = {}
    for sex in SEXES:
        for group in (*GROUPS[:-1], *OLDER):
            low, high = GROUP_AGES[group]
            mask = ((frame.sex == sex) & frame.EDAD_FIN.between(low, high)).to_numpy()
            w = frame.weight.to_numpy()[mask]
            km = frame.car_km.to_numpy()[mask]
            f = factors[mask]
            out[(sex, group)] = (float((w * km).sum() / w.sum()), ((w * km) @ f) / (w @ f))
        young, old = spain[(sex, "65-74")], spain[(sex, "75+")]
        (k_young, rep_young), (k_old, rep_old) = out[(sex, "65-74")], out[(sex, "75+")]
        out[(sex, "65+")] = (
            float((k_young * young + k_old * old) / (young + old)),
            (rep_young * young + rep_old * old) / (young + old),
        )
    return out


def _older_mean_population(profile: dict) -> pd.Series:
    """The residents aged 65-74 and 75 and over, by sex, over whom ``profile``'s 65+ km per
    resident is a mean: Spain's for a profile standardised from exact ages (it carries its own
    65-74 and 75+ cells, as the Madrid survey's does), the province of Barcelona's for an EMEF
    profile."""
    if all((sex, group) in profile for sex in SEXES for group in OLDER):
        return population_by_group().set_index(["sex", "group"]).population
    return barcelona_older_population().set_index(["sex", "group"]).population


@cache
def average_profile() -> dict:
    """The central profile: the Barcelona (EMEF, Method A) and Madrid (2018 survey) profiles,
    each scaled to the same national total and averaged cell by cell, so that every age group's
    share of Spain's kilometres is the mean of its shares under the two surveys. Neither survey
    covers Spain; the two largest metropolitan areas differ most at 65 and over, and the mean
    gives them equal weight. The result is cached: callers must not change it.

    The EMEF's 65+ km per resident is a mean over the province of Barcelona's older residents. It
    is first split at 75 with the Madrid survey's ratio of km per resident, replicate by
    replicate, so that both profiles carry 65-74 and 75+ cells and a 65+ mean over Spain's older
    residents (as :func:`edm_profile` does). Replicate b pairs the EMEF's bootstrap b with the
    Madrid survey's household bootstrap b (independent surveys); :func:`_average_profile_crossed`
    crosses them instead, for the 75+ interval."""
    emef, madrid = emef_profile(), edm_profile()
    ratios = edm2018.older_ratio_replicates()
    spain = population_by_group().set_index(["sex", "group"]).population
    barcelona = barcelona_older_population().set_index(["sex", "group"]).population
    cells = (*GROUPS[:-1], *OLDER)
    standard = {key: emef[key] for key in emef if key[1] != "65+"}
    for sex in SEXES:
        young, old = barcelona[(sex, "65-74")], barcelona[(sex, "75+")]
        for index in (0, 1):
            k65 = emef[(sex, "65+")][index]
            r = ratios[sex]["per_resident"][index]
            k_young = k65 * (young + old) / (young + r * old)
            standard.setdefault((sex, "65-74"), [None, None])[index] = k_young
            standard.setdefault((sex, "75+"), [None, None])[index] = r * k_young

    def total(profile: dict, index: int):
        return sum(profile[(sex, g)][index] * spain[(sex, g)] for sex in SEXES for g in cells)

    out = {}
    for sex in SEXES:
        for g in cells:
            out[(sex, g)] = tuple(
                0.5 * standard[(sex, g)][i] / total(standard, i)
                + 0.5 * madrid[(sex, g)][i] / total(madrid, i)
                for i in (0, 1)
            )
        young, old = spain[(sex, "65-74")], spain[(sex, "75+")]
        out[(sex, "65+")] = tuple(
            (out[(sex, "65-74")][i] * young + out[(sex, "75+")][i] * old) / (young + old)
            for i in (0, 1)
        )
    return out


@cache
def _average_profile_crossed() -> dict:
    """:func:`average_profile` with two-dimensional replicates: cell (i, j) averages the EMEF's
    bootstrap i with the Madrid survey's household bootstrap j, the EMEF's 65+ km being split at
    75 with Madrid resample j's ratio. Crossing the two independent surveys gives 300 x 300
    cells instead of 300 pairs, so the interval ends of the 75+ estimate carry Monte Carlo errors
    as small as Method A's; a Madrid split drawn along the second axis then uses the same
    households as the Madrid half of the profile in every cell."""
    emef, madrid = emef_profile(), edm_profile()
    ratios = edm2018.older_ratio_replicates()
    spain = population_by_group().set_index(["sex", "group"]).population
    barcelona = barcelona_older_population().set_index(["sex", "group"]).population
    cells = (*GROUPS[:-1], *OLDER)
    a = {key: value[1][:, None] for key, value in emef.items() if key[1] != "65+"}
    m = {key: value[1][None, :] for key, value in madrid.items()}
    for sex in SEXES:
        young, old = barcelona[(sex, "65-74")], barcelona[(sex, "75+")]
        k65 = emef[(sex, "65+")][1][:, None]
        r = np.asarray(ratios[sex]["per_resident"][1])[None, :]
        k_young = k65 * (young + old) / (young + r * old)
        a[(sex, "65-74")], a[(sex, "75+")] = k_young, r * k_young
    total_a = sum(a[(sex, g)] * spain[(sex, g)] for sex in SEXES for g in cells)
    total_m = sum(m[(sex, g)] * spain[(sex, g)] for sex in SEXES for g in cells)
    point = average_profile()
    out = {}
    for sex in SEXES:
        for g in cells:
            out[(sex, g)] = (
                point[(sex, g)][0],
                0.5 * a[(sex, g)] / total_a + 0.5 * m[(sex, g)] / total_m,
            )
        young, old = spain[(sex, "65-74")], spain[(sex, "75+")]
        out[(sex, "65+")] = (
            point[(sex, "65+")][0],
            (out[(sex, "65-74")][1] * young + out[(sex, "75+")][1] * old) / (young + old),
        )
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
def dgt_car_km() -> float:
    """DGT's 2024 car kilometres less taxi and ride-hailing cars."""
    table = pd.read_excel(KM_SERVICE_PATH, header=0)
    table.columns = ["category", "service", "description", "vehicles", "km", "mean_km"]
    cars = table[table.category.str.strip() == "TURISMOS"]
    professional = float(cars[cars.service.isin(PROFESSIONAL_SERVICES)].km.sum())
    return float(cars.km.sum()) - professional


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


BARCELONA_METHOD = "A: EMEF, province of Barcelona"
LICENCE_METHOD = "A2: EMEF, province of Barcelona, per licence holder"
AVERAGE_METHOD = "Average of Barcelona and Madrid"
# The published estimate: each age group's share of Spain's kilometres is the mean of its shares
# under the Barcelona (EMEF) and Madrid (2018) profiles (:func:`average_profile`). Every other
# profile, Barcelona's and Madrid's alone included, is an alternative in the sensitivity range.
CENTRAL_METHOD = AVERAGE_METHOD


def exposure_profiles() -> dict[str, tuple[pd.Series, np.ndarray]]:
    """National working-day km per day by group under the central average, Methods A and A2 and
    each Method C profile."""
    out = {
        CENTRAL_METHOD: national_km(average_profile()),
        BARCELONA_METHOD: national_km(emef_profile()),
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
    return pd.DataFrame(rows)


# Gamma draws of each crash count per survey replicate. The draws form a crossed array, the
# survey's replicates along the rows and the count draws along the columns, and every cell has
# its own draw; :func:`_interval` gives the Monte Carlo error of each end over that array. One
# draw per replicate, as until October 2026, left the death ratios' ends with Monte Carlo errors
# of up to 0.07.
COUNT_DRAWS = 50


def _count_draws(rng: np.random.Generator, n: float, replicates: int) -> np.ndarray:
    """Gamma draws of a count ``n`` (Jeffreys prior), :data:`COUNT_DRAWS` per replicate."""
    return rng.gamma(float(n) + 0.5, 1.0, (replicates, COUNT_DRAWS))


def rates() -> pd.DataFrame:
    """Car drivers involved and killed per billion km, by group and method, with each group's
    ratio to drivers aged 45-64. Intervals combine exposure and count uncertainty: the survey's
    replicates crossed with :data:`COUNT_DRAWS` gamma draws of the counts each, with the Monte
    Carlo standard error of every end."""
    total_km = dgt_car_km()
    counts = drivers_involved().set_index("group")
    unknown_share = drivers_involved().attrs["unknown_share"]
    rng = np.random.default_rng(SEED)
    rows = []
    for method, (km, replicates) in exposure_profiles().items():
        n_rep = replicates.shape[1]
        share = km / km.sum()
        share_rep = replicates / replicates.sum(axis=0)
        draws = {
            (group, measure): _count_draws(rng, counts.loc[group, measure], n_rep)
            for group in GROUPS
            for measure in ("involved", "killed")
        }
        reference = GROUPS.index(REFERENCE)
        for i, group in enumerate(GROUPS):
            billion_km = float(share[group]) * total_km / BILLION
            row = {
                "method": method,
                "group": group,
                "billion_km": billion_km,
                "share_of_km": float(share[group]),
            }
            for measure in ("involved", "killed"):
                n = float(counts.loc[group, measure])
                km_rep = (share_rep[i] * total_km / BILLION)[:, None]
                ref_km_rep = (share_rep[reference] * total_km / BILLION)[:, None]
                rate_rep = draws[(group, measure)] / km_rep
                ref_rep = draws[(REFERENCE, measure)] / ref_km_rep
                point = n / billion_km
                ref_point = float(counts.loc[REFERENCE, measure]) / (
                    float(share[REFERENCE]) * total_km / BILLION
                )
                rate = _interval(rate_rep)
                ratio = _interval(rate_rep / ref_rep)
                row |= {
                    measure: n,
                    f"{measure}_per_bn_km": point,
                    f"{measure}_per_bn_km_low": rate["low"],
                    f"{measure}_per_bn_km_high": rate["high"],
                    f"{measure}_ratio": point / ref_point,
                    f"{measure}_ratio_low": ratio["low"],
                    f"{measure}_ratio_high": ratio["high"],
                    # How far another set of replicates and count draws would move each end.
                    f"{measure}_per_bn_km_mc_se_low": rate["mc_se_low"],
                    f"{measure}_per_bn_km_mc_se_high": rate["mc_se_high"],
                    f"{measure}_ratio_mc_se_low": ratio["mc_se_low"],
                    f"{measure}_ratio_mc_se_high": ratio["mc_se_high"],
                }
            row["involved_per_bn_km_allocated"] = row["involved_per_bn_km"] / (1 - unknown_share)
            rows.append(row)
    return pd.DataFrame(rows)


# Beta draws behind each interval of deaths once involved: with 4,000, as until October 2026, the
# ends at 75 and over carried Monte Carlo errors of up to 0.08 per 1,000.
SEVERITY_DRAWS = 100_000


def severity_and_licences() -> pd.DataFrame:
    """Measures that need no kilometres: drivers killed per 1,000 drivers involved, with a 95%
    interval from Beta draws (Jeffreys prior) and the Monte Carlo error of each end, and drivers
    involved per 1,000 B-licence holders, by group. ``killed_ratio_to_45_64`` is each group's
    deaths once involved over drivers aged 45-64's, with a 95% interval from the log-normal
    approximation to a ratio of two Poisson rates (the variance of the log ratio is the sum of
    the reciprocals of the two death counts)."""
    counts = drivers_involved().set_index("group")
    licences = licence_holders()
    rng = np.random.default_rng(SEED)
    rows = []
    reference_rate = float(counts.loc[REFERENCE, "killed"]) / float(
        counts.loc[REFERENCE, "involved"]
    )
    for group in (*GROUPS, *OLDER):
        involved = float(counts.loc[group, "involved"])
        killed = float(counts.loc[group, "killed"])
        draws = rng.beta(killed + 0.5, involved - killed + 0.5, SEVERITY_DRAWS)
        interval = _interval(1000 * draws)
        ratio = (killed / involved) / reference_rate
        spread = 1.96 * np.sqrt(1 / killed + 1 / float(counts.loc[REFERENCE, "killed"]))
        rows.append(
            {
                "group": group,
                "involved": involved,
                "killed": killed,
                "killed_per_1000_involved": 1000 * killed / involved,
                "killed_per_1000_involved_low": interval["low"],
                "killed_per_1000_involved_high": interval["high"],
                "killed_per_1000_involved_mc_se_low": interval["mc_se_low"],
                "killed_per_1000_involved_mc_se_high": interval["mc_se_high"],
                "killed_ratio_to_45_64": ratio,
                "killed_ratio_low": ratio * np.exp(-spread) if group != REFERENCE else 1.0,
                "killed_ratio_high": ratio * np.exp(spread) if group != REFERENCE else 1.0,
                "b_licence_holders": float(licences[group]),
                "involved_per_1000_licence_holders": 1000 * involved / float(licences[group]),
            }
        )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- ages 75 and over

# The three splits of the 65-and-over km between 65-74 and 75 and over. Each is a ratio of car-driver
# km per resident at 75 and over to 65-74, by sex, applied to Spain's population (and, to take a
# profile's 65-and-over mean apart, to the population it is a mean over: the province of
# Barcelona's for the EMEF, Spain's for the standardised Madrid profile).
REFERENCE_SPLIT = "Madrid survey: km per resident"
LICENCE_SPLIT = "Madrid km per DGT licence holder, Spain's licence holders"
EQUAL_SPLIT = "equal km per licence holder"
SPLITS = (REFERENCE_SPLIT, LICENCE_SPLIT, EQUAL_SPLIT)
# The splits whose ratios come from the Madrid survey, and so carry its sampling error.
EDM_SPLITS = (REFERENCE_SPLIT, LICENCE_SPLIT)
MADRID_METHOD = "C: Madrid survey 2018"


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


def _licence_transfer() -> dict[str, float]:
    """By sex, Spain's B-licence holders per resident at 75 and over against 65-74 over the
    province of Madrid's (DGT census and INE, both 2024): the factor that carries Madrid's ratio
    of km per resident to Spain as a ratio of km per licence holder, with one definition of a
    licence holder (DGT's register) in both places."""
    spain = older_prevalence_ratio()
    madrid = older_prevalence_ratio(MADRID_PROVINCE)
    return {sex: spain[sex] / madrid[sex] for sex in SEXES}


@cache
def _older_ratios() -> dict[str, dict[str, float]]:
    """Ratio of km per resident at 75+ to 65-74, by sex, under each split. The result is cached:
    callers must not change it.

    The licence split is Madrid's km per DGT licence holder (the survey's km per resident over
    the province's DGT licence holding) times Spain's DGT licence holding."""
    madrid = edm2018.older_ratio_replicates()
    spain = older_prevalence_ratio()
    transfer = _licence_transfer()
    out: dict[str, dict[str, float]] = {split: {} for split in SPLITS}
    for sex in SEXES:
        out[REFERENCE_SPLIT][sex] = madrid[sex]["per_resident"][0]
        out[LICENCE_SPLIT][sex] = madrid[sex]["per_resident"][0] * transfer[sex]
        out[EQUAL_SPLIT][sex] = spain[sex]
    return out


def _split_replicates(split: str) -> dict[str, float | np.ndarray]:
    """A split's ratio by sex as the Madrid survey's household-bootstrap replicates (the two
    Madrid splits), or as a fixed number (the equal split)."""
    if split not in EDM_SPLITS:
        return dict(_older_ratios()[split])
    madrid = edm2018.older_ratio_replicates()
    if split == REFERENCE_SPLIT:
        return {sex: madrid[sex]["per_resident"][1] for sex in SEXES}
    transfer = _licence_transfer()
    return {sex: madrid[sex]["per_resident"][1] * transfer[sex] for sex in SEXES}


def _split_older_by_sex(profile: dict, ratios: dict[str, float]) -> dict[tuple[str, str], float]:
    """Spain's working-day km by sex at 65-74 and 75 and over from a 65+ profile and a 75+/65-74
    ratio of km per resident by sex. The profile's 65+ mean is taken apart with the population it
    is a mean over (:func:`_older_mean_population`: the province of Barcelona's for an EMEF
    profile, Spain's for the Madrid profile, already standardised to it) and put back together
    with Spain's. For the Madrid profile under the Madrid split this gives back the survey's own
    km per resident at 65-74 and at 75 and over, times Spain's residents of those ages."""
    mean_over = _older_mean_population(profile)
    spain = population_by_group().set_index(["sex", "group"]).population
    out = {}
    for sex in SEXES:
        k65 = profile[(sex, "65+")][0]
        r = ratios[sex]
        young, old = mean_over[(sex, "65-74")], mean_over[(sex, "75+")]
        k_young = k65 * (young + old) / (young + r * old)
        out[(sex, "65-74")] = k_young * spain[(sex, "65-74")]
        out[(sex, "75+")] = r * k_young * spain[(sex, "75+")]
    return out


def _split_older(profile: dict, ratios: dict[str, float]) -> dict[str, float]:
    """Spain's working-day km at 65-74 and 75 and over (:func:`_split_older_by_sex`, both sexes)."""
    by_sex = _split_older_by_sex(profile, ratios)
    return {group: sum(by_sex[(sex, group)] for sex in SEXES) for group in OLDER}


def _older_draws(
    profile: dict, ratios: dict[str, float | np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    """Joint replicates of the 75+ and 65-74 ratios to 45-64.

    ``profile`` maps (sex, group) to (point, replicates) of km per resident. ``ratios`` gives each
    sex's split ratio as a number or as replicates of another survey. The cells cross the
    profile's replicates (first axis) with the split's (second axis), every pairing of the two
    surveys' resamples. With a fixed split the profile's replicates are repeated along the second
    axis. Every cell gets its own gamma draws of the three counts. A profile whose replicates are
    already two-dimensional (the central average's, :func:`_average_profile_crossed`) is used as
    it is, its second axis being the split's survey. Returns the two ratios, with the shape of
    the cells."""
    n = len(profile[("male", "65+")][1])

    def prof(sex: str, group: str) -> np.ndarray:
        values = np.asarray(profile[(sex, group)][1], dtype=float)
        return values if values.ndim == 2 else values[:, None]

    def ratio(sex: str) -> np.ndarray | float:
        value = ratios[sex]
        if np.ndim(value) == 0:
            return float(value)
        return np.asarray(value, dtype=float)[None, :]

    population = population_by_group().set_index(["sex", "group"]).population
    mean_over = _older_mean_population(profile)
    shares = {g: sum(prof(s, g) * population[(s, g)] for s in SEXES) for g in GROUPS}
    young = old = 0.0
    for sex in SEXES:
        r = ratio(sex)
        y, o = mean_over[(sex, "65-74")], mean_over[(sex, "75+")]
        k_young = prof(sex, "65+") * (y + o) / (y + r * o)
        young = young + k_young * population[(sex, "65-74")]
        old = old + r * k_young * population[(sex, "75+")]
    q = old / (old + young)
    base = np.stack([shares[g] for g in GROUPS])
    shape = (n, n)
    s45 = np.broadcast_to(base[GROUPS.index(REFERENCE)], shape)
    s65 = np.broadcast_to(base[GROUPS.index("65+")], shape)
    q = np.broadcast_to(q, shape)
    counts = drivers_involved().set_index("group").involved
    rng = np.random.default_rng(SEED)
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


def older_split() -> pd.DataFrame:
    """Kilometres and rates for 65-74 and 75 and over under each split, for the central average
    profile and for the Barcelona profile alone (``profile``), with joint 95% sampling intervals.

    The EMEF and the Madrid survey are independent samples, so the interval crosses all of the
    EMEF's replicates with all of the Madrid survey's (300 x 300 cells), each cell with its own
    gamma draws of the counts. It covers the sampling error of both surveys and chance in the
    crash counts, and holds every structural choice fixed. It may be too narrow or too wide:
    the EMEF bootstrap ignores clustering, the Madrid household bootstrap ignores stratification,
    and neither recalibrates the weights.

    For the central average, half of whose profile is the Madrid survey's, the interval's cells
    cross the EMEF's replicates with the Madrid survey's (:func:`_average_profile_crossed`): the
    Madrid half of the profile and a Madrid split use the same household resample in each cell."""
    total_km = dgt_car_km()
    counts = drivers_involved().set_index("group")
    rows = []
    profiles = (
        (CENTRAL_METHOD, average_profile(), _average_profile_crossed()),
        (BARCELONA_METHOD, emef_profile(), emef_profile()),
    )
    for method, profile, draws_profile in profiles:
        rows += _older_split_rows(method, profile, draws_profile, total_km, counts)
    return pd.DataFrame(rows)


def older_point_ratios(km: pd.Series, older_share: float) -> dict[str, float]:
    """65-74 and 75+ involvement per km over 45-64's, from national km by group and the 75+
    share of the 65+ km (the km total cancels)."""
    counts = drivers_involved().set_index("group").involved
    reference = float(counts[REFERENCE]) / float(km[REFERENCE])
    km_65 = float(km["65+"])
    return {
        "65-74": float(counts["65-74"]) / ((1 - older_share) * km_65) / reference,
        "75+": float(counts["75+"]) / (older_share * km_65) / reference,
    }


def _older_split_rows(
    method: str, profile: dict, draws_profile: dict, total_km: float, counts: pd.DataFrame
) -> list[dict]:
    """:func:`older_split`'s rows for one profile; ``draws_profile`` gives the replicates its
    joint interval is drawn from."""
    km, _ = national_km(profile)
    rows = []
    for split in SPLITS:
        ratios = _older_ratios()[split]
        national = _split_older(profile, ratios)
        share = national["75+"] / sum(national.values())
        point = older_point_ratios(km, share)
        joint75, joint65 = _older_draws(draws_profile, _split_replicates(split))
        intervals = {"75+": _interval(joint75), "65-74": _interval(joint65)}
        for group in OLDER:
            part = share if group == "75+" else 1 - share
            billion_km = part * float(km["65+"] / km.sum()) * total_km / BILLION
            joint = intervals[group]
            rows.append(
                {
                    "profile": method,
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
                }
            )
    return rows


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


# ----------------------------------------------------------------------------- sensitivity


def sex_per_km() -> pd.DataFrame:
    """Men against women aged 18 and over: private-car drivers involved and killed per km, with
    the km split by sex from the central average profile (the same transfer as for age), and the
    ratio under each other profile as a sensitivity range."""
    out = _sex_per_km(average_profile()).assign(profile=CENTRAL_METHOD)
    others = {
        BARCELONA_METHOD: emef_profile(),
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
        # The survey's replicates crossed with COUNT_DRAWS count draws each.
        male = _count_draws(rng, out.loc["male", measure], n_rep) / km_rep["male"][:, None]
        female = _count_draws(rng, out.loc["female", measure], n_rep) / km_rep["female"][:, None]
        interval = _interval(male / female)
        result.append(
            {
                "measure": f"{measure} per km",
                "men_share_of_km": float(out.loc["male", "share_of_km"]),
                "men": float(out.loc["male", measure]),
                "women": float(out.loc["female", measure]),
                "ratio_men_to_women": float(point),
                "ratio_low": interval["low"],
                "ratio_high": interval["high"],
                "mc_se_low": interval["mc_se_low"],
                "mc_se_high": interval["mc_se_high"],
            }
        )
    return pd.DataFrame(result)


# ----------------------------------------------------------------------------- old figure


# ----------------------------------------------------------------------------- 75 and over: anatomy


MADRID_PROVINCE = "28"
