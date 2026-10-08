"""How much of DGT's car kilometres the EMEF's working days account for, what the rest is made
of, and how far the national ratios move if the rest has another age mix.

Method A (:mod:`dgt_stats.exposure_risk.national`) carries the EMEF's working-day car-driver km
per resident, by age and sex, to Spain's population. Over the working days of 2024 that is about
half of DGT's 2024 car kilometres less taxis and ride-hailing cars. The central estimate spreads
DGT's whole total with the working-day age mix, so it assumes that the other half has the same
age mix. This module measures the pieces of that half with the data in the repository, and tests
the assumption with explicit allocations.

**Components** (:func:`components`), added in this order, each at the setting that explains least
and at the one that explains most:

1. *Working days*: Method A's km per working day times the working days of 2024 (weekdays less
   the fourteen paid public holidays a year that Spanish law allows, two of them local).
2. *Professionals' work driving*: the EMEF counts, but does not describe, the trips in the course
   of work of people who make eight or more a day; 25% or 50% of them as car trips of the age
   group's mean car-trip length (:data:`dgt_stats.emef.exposure.PROFESSIONAL_CAR_SHARES`).
3. *Regional level*: how much more Spain drives per resident than the province of Barcelona, from
   MOVILIA 2006 car trips per resident (province against Spain) and DGT's 2024 car km per resident
   by the owner's autonomous community (Catalonia against Spain, with and without Madrid, where
   many company fleets are registered). It scales components 1 and 2.
4. *Non-working days*: the other days of 2024, each carrying 60% or 100% of a working day's
   resident driving (:data:`NON_WORKING_RATIOS`, an assumption; MOVILIA 2006 is the evidence).
5. *Months outside the fieldwork*: the ratio of the year's mean daily petrol sales, road fuel
   sales or toll-motorway traffic to the mean over the days of the 2024 EMEF fieldwork.

The *remainder* is DGT's total less components 1-5; it is what no measured piece accounts for.
Company-registered cars and car hire without driver are reported beside the components and not
added: residents' driving of them on working days is already in component 1, and the rest
overlaps components 2 and 4 and the remainder. Non-residents' driving of Spanish-registered cars
is bounded by car hire without driver.

**Age mixes** (:func:`mixes`). The covered part keeps the EMEF working-day mix. Each other part
takes an explicit mix, labelled as an assumption. A mix is *credible* when it comes from a
measured age pattern of driving or car travel (the EMEF, DGT's kilometres by owner's age, MOVILIA
2006 and 2007), and a *bound* when it is constructed: equal km per B-licence holder at every age,
or no driving at 65 and over. Every measured pattern gives licence holders aged 65 and over less
driving than those aged 45-64, and gives residents aged 65 and over some, so both bounds lie
outside the evidence; they are reported, not used in the published ranges.

**Scenarios** (:func:`scenario_km`). The components are set to explain least: that gives the
remainder its largest share, and the non-working days and the remainder together, the two parts
that take other age mixes, a larger share of the total than any other setting does. Each
scenario gives the non-working days one of three mixes and
the remainder one of seven, and is computed with Method A's profile and with each other profile
of :func:`dgt_stats.exposure_risk.national.exposure_profiles` for the covered part, because the
regional profile and the uncovered half are separate uncertainties. The 65+ km are split between
65-74 and 75 and over under each assumption of :func:`national.older_split`, except in the mixes
that measure the two groups themselves (owners' km, licence holders).
"""

from __future__ import annotations

import datetime as dt
from functools import cache

import numpy as np
import pandas as pd

from dgt_stats import io_exposure, io_population, io_traffic
from dgt_stats.emef import exposure
from dgt_stats.exposure_risk import national
from dgt_stats.paths import RAW_DATA_DIR

YEAR = national.YEAR
GROUPS = national.GROUPS
REFERENCE = national.REFERENCE
BILLION = national.BILLION
CENTRAL_KM = "less taxi and ride-hailing"
PUBLIC_HOLIDAYS = national.PUBLIC_HOLIDAYS
NON_WORKING_RATIOS = national.NON_WORKING_RATIOS
working_days = national.working_days
# The EMEF 2024 fieldwork (executive summary, technical sheet): the reference days fall in these
# periods. The archived sources give the dates for 2024 only.
FIELDWORK_2024: tuple[tuple[dt.date, dt.date], ...] = (
    (dt.date(2024, 4, 1), dt.date(2024, 6, 21)),
    (dt.date(2024, 9, 26), dt.date(2024, 11, 27)),
)
KM_COMMUNITIES_PATH = RAW_DATA_DIR / "dgt" / "km_itv_2024" / "km_comunidades_2024.xlsx"
CATALONIA = ("08", "17", "25", "43")
MADRID = ("28",)
MOVILIA_2006 = national.MOVILIA_PATH
MOVILIA_2007 = RAW_DATA_DIR / "transportes" / "movilia_2007.xls"
# The surveys' names, for the pages: daily mobility (2006) and long-distance travel (2007).
MOVILIA_DAILY = "MOVILIA 2006"
MOVILIA_LONG = "MOVILIA 2007"
MOVILIA_BANDS = {
    "De 15 a 29": "15-29",
    "De 30 a 39": "30-39",
    "De 40 a 49": "40-49",
    "De 50 a 64": "50-64",
    "65 y más años": "65+",
}

WORKING_DAY_MIX = "working-day mix (EMEF)"
PROFESSIONAL_MIX = "professionals' work trips (EMEF)"
OWNER_MIX = "km of cars by the private owner's age (DGT 2024)"
LONG_DISTANCE_MIX = "car journeys over 50 km per resident (MOVILIA 2007, Spain)"
LICENCE_MIX = "B-licence holders: equal km per holder at every age (bound)"
UNDER_65_MIX = "under 65 only: working-day mix without 65 and over (bound)"
NON_WORKING_MIXES = (WORKING_DAY_MIX, national.EMEF_WEEKEND_PROXY, national.MOVILIA_WEEKEND)
REMAINDER_MIXES = (
    WORKING_DAY_MIX,
    OWNER_MIX,
    LONG_DISTANCE_MIX,
    national.EMEF_WEEKEND_PROXY,
    national.MOVILIA_WEEKEND,
    LICENCE_MIX,
    UNDER_65_MIX,
)
BOUNDS = (LICENCE_MIX, UNDER_65_MIX)


# ----------------------------------------------------------------------------- evidence


def _movilia_rows(path, sheet: str, column: int, labels: dict[str, str]) -> pd.Series:
    """The first (both sexes or all provinces) block's values of ``column`` for ``labels``."""
    table = pd.read_excel(path, sheet, header=None)
    names = table[0].astype(str).str.strip()
    return pd.Series(
        {
            key: float(table.loc[names[names == label].index[0], column])
            for label, key in labels.items()
        }
    )


def _check_title(path, sheet: str, start: str) -> None:
    titles = pd.read_excel(path, sheet, header=None, nrows=8)[0].astype(str).str.strip()
    if not titles.str.startswith(start).any():
        raise ValueError(f"{path.name} sheet {sheet}: expected a title starting {start!r}")


@cache
def regional_evidence() -> pd.DataFrame:
    """Spain's level of car driving per resident against the province of Barcelona (MOVILIA 2006)
    and against Catalonia (DGT 2024, by the owner's autonomous community)."""
    for sheet, start in (
        ("T61-1", "61. Desplazamientos según modo principal"),
        ("T61-5", "61. Desplazamientos según modo principal"),
        ("T9-1", "9.I. Personas según edad por provincia"),
    ):
        _check_title(MOVILIA_2006, sheet, start)
    places = {"Total": "Spain", "Barcelona": "Barcelona"}
    # Column 3 is car or motorcycle (drivers and passengers); column 1 is everyone.
    working = _movilia_rows(MOVILIA_2006, "T61-1", 3, places)
    weekend = _movilia_rows(MOVILIA_2006, "T61-5", 3, places)
    people = _movilia_rows(MOVILIA_2006, "T9-1", 1, places)
    per_resident = {
        "working day": working / people,
        "weekend day": weekend / people,
        "week (five working days, two weekend days)": (5 * working + 2 * weekend) / people,
    }
    rows = [
        {
            "evidence": "regional level",
            "measure": f"car or motorcycle trips per resident, {day}, Spain over the province of "
            "Barcelona (MOVILIA 2006; drivers and passengers)",
            "value": float(rate["Spain"] / rate["Barcelona"]),
            "used_as_regional_factor": day.startswith("week ("),
        }
        for day, rate in per_resident.items()
    ]
    km = pd.read_excel(KM_COMMUNITIES_PATH, "Detalle 2024", header=0)
    km.columns = ["category", "community", "cars", "km", "mean_km"]
    km = km[(km.category.str.strip() == "Turismos") & (km.community != "Extranjero")]
    km = km.set_index("community")
    spain_km, spain_cars = float(km.km.sum()), float(km.cars.sum())

    def residents(codes: tuple[str, ...] | None) -> float:
        total = 0.0
        for code in codes or (io_population.NATIONAL_CODE,):
            table = io_population.population(YEAR, national.REFERENCE_DATE, "total", code)
            total += float(table[table.age_low >= 15].population.sum())
        return total

    spain, catalonia, madrid = residents(None), residents(CATALONIA), residents(MADRID)
    cat_km, cat_cars = float(km.loc["Cataluña", "km"]), float(km.loc["Cataluña", "cars"])
    mad_km, mad_cars = float(km.loc["Madrid", "km"]), float(km.loc["Madrid", "cars"])
    dgt = {
        "car km per resident aged 15 and over, Spain over Catalonia": (
            (spain_km / spain) / (cat_km / catalonia),
            True,
        ),
        "car km per resident aged 15 and over, Spain without Madrid over Catalonia": (
            ((spain_km - mad_km) / (spain - madrid)) / (cat_km / catalonia),
            True,
        ),
        "cars per resident aged 15 and over, Spain over Catalonia": (
            (spain_cars / spain) / (cat_cars / catalonia),
            False,
        ),
        "mean km per car, Spain without Madrid over Catalonia": (
            ((spain_km - mad_km) / (spain_cars - mad_cars)) / (cat_km / cat_cars),
            False,
        ),
    }
    rows += [
        {
            "evidence": "regional level",
            "measure": f"{label} (DGT 2024, by the owner's autonomous community)",
            "value": float(value),
            "used_as_regional_factor": used,
        }
        for label, (value, used) in dgt.items()
    ]
    return pd.DataFrame(rows)


def regional_factors() -> tuple[float, float]:
    """The lowest and highest measured level of Spain's car driving per resident over the
    survey area's."""
    evidence = regional_evidence()
    values = evidence[evidence.used_as_regional_factor].value
    return float(values.min()), float(values.max())


def _fieldwork_day_weights() -> pd.Series:
    """How many days of the 2024 EMEF fieldwork fall in each month."""
    days = pd.Series(0, index=range(1, 13), dtype=float)
    for start, end in FIELDWORK_2024:
        for day in pd.date_range(start, end, freq="D"):
            days[day.month] += 1
    return days


@cache
def seasonal_evidence(year: int = YEAR) -> pd.DataFrame:
    """The year's mean daily fuel sales and toll-motorway traffic over their mean on the days of
    the EMEF 2024 fieldwork, each month weighted by its fieldwork days."""
    fuel = io_traffic.read_cores_fuel()
    toll = io_traffic.read_toll_traffic()
    weights = _fieldwork_day_weights()
    rows = []
    for label, frame, column in (
        ("petrol sales (CORES)", fuel, "petrol_tonnes"),
        ("petrol and diesel sales (CORES)", fuel, "road_fuel_tonnes"),
        ("vehicle-km on the state toll motorways", toll, "veh_km_millions"),
    ):
        part = frame[frame.year == year].set_index("month")[column].astype(float)
        if len(part) != 12:
            raise ValueError(f"seasonal evidence: {label} lacks months of {year}")
        days = pd.Series(
            {m: pd.Period(f"{year}-{m:02d}").days_in_month for m in range(1, 13)}, dtype=float
        )
        daily = part / days
        annual = float(part.sum() / days.sum())
        fieldwork = float((daily * weights).sum() / weights.sum())
        rows.append(
            {
                "evidence": "months outside the fieldwork",
                "measure": f"{label}: mean day of {year} over mean fieldwork day",
                "value": annual / fieldwork,
                "used_as_regional_factor": False,
            }
        )
    return pd.DataFrame(rows)


def seasonal_factors() -> tuple[float, float]:
    values = seasonal_evidence().value
    return float(values.min()), float(values.max())


@cache
def travel_evidence() -> pd.DataFrame:
    """MOVILIA 2006: car trips and trip duration on a weekend day against a working day; MOVILIA
    2007: the share of car journeys over 50 km that start in July or August."""
    for sheet in ("T72-1", "T72-2"):
        _check_title(MOVILIA_2006, sheet, "72. Duración media de los desplazamientos")
    for sheet in ("T61-1", "T61-5"):
        _check_title(MOVILIA_2006, sheet, "61. Desplazamientos según modo principal")
    _check_title(MOVILIA_2007, "T18", "18. Número de viajes por mes de inicio")
    spain = {"Total": "Spain"}
    car_working = _movilia_rows(MOVILIA_2006, "T61-1", 3, spain)["Spain"]
    car_weekend = _movilia_rows(MOVILIA_2006, "T61-5", 3, spain)["Spain"]
    minutes_working = _movilia_rows(MOVILIA_2006, "T72-1", 1, spain)["Spain"]
    minutes_weekend = _movilia_rows(MOVILIA_2006, "T72-2", 1, spain)["Spain"]
    months = _movilia_rows(
        MOVILIA_2007, "T18", 2, {"Total": "year", "Julio": "July", "Agosto": "August"}
    )
    working, other = working_days()
    return pd.DataFrame(
        [
            {
                "evidence": "non-working days",
                "measure": "car or motorcycle trips on an average weekend day over a working day "
                "(MOVILIA 2006, Spain; drivers and passengers)",
                "value": float(car_weekend / car_working),
            },
            {
                "evidence": "non-working days",
                "measure": "mean trip duration on a weekend day over a working day, all modes "
                "(MOVILIA 2006, Spain)",
                "value": float(minutes_weekend / minutes_working),
            },
            {
                "evidence": "months outside the fieldwork",
                "measure": "share of car journeys over 50 km starting in July or August "
                "(MOVILIA 2007, Spain; drivers and passengers)",
                "value": float((months["July"] + months["August"]) / months["year"]),
            },
            {
                "evidence": "calendar",
                "measure": f"working days of {YEAR} (weekdays less {PUBLIC_HOLIDAYS} public "
                "holidays)",
                "value": float(working),
            },
            {
                "evidence": "calendar",
                "measure": f"non-working days of {YEAR}",
                "value": float(other),
            },
        ]
    ).assign(used_as_regional_factor=False)


@cache
def fleet_evidence() -> pd.DataFrame:
    """Kilometres of company-registered cars, car hire without driver and driving schools (DGT
    2024): reported beside the components, not added to them."""
    owner = national.owner_km_by_group()
    km = io_exposure.read_exposure("km_edad_propietario_2024")
    company = float(
        km[(km.vehicle_group == "car") & (km.year == YEAR) & km.is_company].total_km.sum()
    )
    table = pd.read_excel(national.KM_SERVICE_PATH, header=0)
    table.columns = ["category", "service", "description", "vehicles", "km", "mean_km"]
    cars = table[table.category.str.strip() == "TURISMOS"].set_index("service")
    rows = [
        ("cars registered to companies", company),
        ("car hire without driver", float(cars.loc["A01", "km"])),
        ("driving schools", float(cars.loc["A03", "km"])),
        ("cars registered to private owners", float(owner[list(GROUPS)].sum())),
    ]
    return pd.DataFrame(
        [{"evidence": "fleet", "measure": label, "value": value / BILLION} for label, value in rows]
    ).assign(used_as_regional_factor=False)


def evidence() -> pd.DataFrame:
    """Every measured value the decomposition rests on."""
    return pd.concat(
        [regional_evidence(), seasonal_evidence(), travel_evidence(), fleet_evidence()],
        ignore_index=True,
    )


# ----------------------------------------------------------------------------- components


@cache
def _daily_km() -> tuple[pd.Series, pd.Series]:
    """Method A's working-day km per day by group, and the professionals' extra km per working
    day at the lower car share of their work trips."""
    km, _ = national.national_km(national.emef_profile())
    fraction = min(exposure.PROFESSIONAL_CAR_SHARES)
    extra, _ = national.national_km(
        national.emef_profile(column=national._professional_column(fraction))
    )
    return km, extra - km


def _professional_daily(fraction: float) -> float:
    km, _ = _daily_km()
    extra, _ = national.national_km(
        national.emef_profile(column=national._professional_column(fraction))
    )
    return float(extra.sum() - km.sum())


def _settings() -> dict[str, dict[str, float]]:
    regional, seasonal = regional_factors(), seasonal_factors()
    shares = exposure.PROFESSIONAL_CAR_SHARES
    return {
        "least explained": {
            "professional": min(shares),
            "regional": regional[0],
            "non_working": NON_WORKING_RATIOS[0],
            "seasonal": seasonal[0],
        },
        "most explained": {
            "professional": max(shares),
            "regional": regional[1],
            "non_working": NON_WORKING_RATIOS[1],
            "seasonal": seasonal[1],
        },
    }


def _cumulative(setting: dict[str, float]) -> dict[str, float]:
    """Annual km of each component, added in order, at one setting."""
    km, _ = _daily_km()
    working, other = working_days()
    daily = float(km.sum())
    professional = _professional_daily(setting["professional"])
    steps = {"working days": daily * working}
    steps["professionals' work driving"] = professional * working
    covered = (daily + professional) * working
    steps["regional level"] = covered * (setting["regional"] - 1)
    steps["non-working days"] = daily * setting["regional"] * other * setting["non_working"]
    subtotal = sum(steps.values())
    steps["months outside the fieldwork"] = subtotal * (setting["seasonal"] - 1)
    return steps


def components() -> pd.DataFrame:
    """The decomposition of DGT's 2024 car km less taxis and ride-hailing cars."""
    total = national.dgt_car_km()[CENTRAL_KM]
    km, professional = _daily_km()
    working_mix = km / km.sum()
    professional_mix = professional / professional.sum()
    settings = _settings()
    steps = {name: _cumulative(setting) for name, setting in settings.items()}
    mixes_of = {
        "working days": working_mix,
        "professionals' work driving": professional_mix,
        "regional level": working_mix,
        "non-working days": working_mix,
        "months outside the fieldwork": working_mix,
    }
    rows = []
    for component, mix in mixes_of.items():
        low = steps["least explained"][component]
        high = steps["most explained"][component]
        rows.append(
            {
                "component": component,
                "additive": True,
                "bn_km_least_explained": low / BILLION,
                "bn_km_most_explained": high / BILLION,
                "share_least_explained": low / total,
                "share_most_explained": high / total,
                "mix": PROFESSIONAL_MIX
                if component.startswith("professional")
                else WORKING_DAY_MIX,
                "mix_share_18_29": float(mix["16-29"]),
                "mix_share_65_plus": float(mix["65+"]),
            }
        )
    remainder = {name: total - sum(parts.values()) for name, parts in steps.items()}
    rows.append(
        {
            "component": "remainder (not explained)",
            "additive": True,
            "bn_km_least_explained": remainder["least explained"] / BILLION,
            "bn_km_most_explained": remainder["most explained"] / BILLION,
            "share_least_explained": remainder["least explained"] / total,
            "share_most_explained": remainder["most explained"] / total,
            "mix": "unknown: see the scenarios",
        }
    )
    fleet = fleet_evidence().set_index("measure").value
    for label in ("cars registered to companies", "car hire without driver"):
        rows.append(
            {
                "component": label,
                "additive": False,
                "bn_km_least_explained": float(fleet[label]),
                "bn_km_most_explained": float(fleet[label]),
                "share_least_explained": float(fleet[label]) * BILLION / total,
                "share_most_explained": float(fleet[label]) * BILLION / total,
                "mix": "no age recorded",
            }
        )
    out = pd.DataFrame(rows)
    out["dgt_total_bn_km"] = total / BILLION
    return out


@cache
def scenario_weights() -> dict[str, float]:
    """Shares of DGT's total held by each part at the setting that explains least. The regional
    level and the months outside the fieldwork scale the parts they apply to, so they keep those
    parts' mixes."""
    total = national.dgt_car_km()[CENTRAL_KM]
    setting = _settings()["least explained"]
    working, other = working_days()
    km, _ = _daily_km()
    scale = setting["regional"] * setting["seasonal"] / total
    weights = {
        "covered": float(km.sum()) * working * scale,
        "professional": _professional_daily(setting["professional"]) * working * scale,
        "non_working": float(km.sum()) * other * setting["non_working"] * scale,
    }
    weights["remainder"] = 1 - sum(weights.values())
    return weights


# ----------------------------------------------------------------------------- age mixes


@cache
def long_distance_rates() -> pd.Series:
    """MOVILIA 2007 table 13: car journeys over 50 km per resident a year by group (drivers and
    passengers); half of the 40-49 band goes to each neighbouring group."""
    _check_title(MOVILIA_2007, "T13", "13. Número de viajes por sexo y edad")
    persons = _movilia_rows(MOVILIA_2007, "T13", 1, MOVILIA_BANDS)
    car = _movilia_rows(MOVILIA_2007, "T13", 3, MOVILIA_BANDS)

    def rate(parts: dict[str, float]) -> float:
        return sum(car[b] * w for b, w in parts.items()) / sum(
            persons[b] * w for b, w in parts.items()
        )

    return pd.Series(
        {
            "16-29": rate({"15-29": 1}),
            "30-44": rate({"30-39": 1, "40-49": 0.5}),
            "45-64": rate({"40-49": 0.5, "50-64": 1}),
            "65+": rate({"65+": 1}),
        }
    )


@cache
def _absolute_mixes() -> dict[str, tuple[pd.Series, float | None]]:
    """Mixes that are national km shares by group in their own right, with the 75+ share of their
    65+ km when they measure it."""
    owner = national.owner_km_by_group()
    licences = national.licence_holders()
    people = national.population_by_group().groupby("group").population.sum()
    distance = long_distance_rates() * people[list(GROUPS)]
    groups = list(GROUPS)
    return {
        OWNER_MIX: (owner[groups] / owner[groups].sum(), float(owner["75+"] / owner["65+"])),
        LONG_DISTANCE_MIX: (distance / distance.sum(), None),
        LICENCE_MIX: (
            licences[groups] / licences[groups].sum(),
            float(licences["75+"] / licences["65+"]),
        ),
    }


@cache
def _relative_weights() -> dict[str, pd.Series]:
    """Mixes defined as weights on the covered part's own mix."""
    ones = pd.Series(1.0, index=list(GROUPS))
    return {
        WORKING_DAY_MIX: ones,
        national.EMEF_WEEKEND_PROXY: national.weekend_weights(),
        national.MOVILIA_WEEKEND: national.movilia_weekend_weights(),
        UNDER_65_MIX: ones.where(ones.index != "65+", 0.0),
    }


def mix_shares(name: str, base: pd.Series) -> tuple[pd.Series, float | None]:
    """A mix's km shares by group given the covered part's shares ``base``, and its own 75+ share
    of 65+ km if it measures one."""
    weights = _relative_weights()
    if name in weights:
        shares = weights[name] * base
        return shares / shares.sum(), None
    return _absolute_mixes()[name]


def mixes() -> pd.DataFrame:
    """Each mix with Method A's profile as the covered part: km shares by group, km per resident
    and per B-licence holder relative to 45-64, and whether it is credible or a bound."""
    km, professional = _daily_km()
    base = km / km.sum()
    people = national.population_by_group().groupby("group").population.sum()
    licences = national.licence_holders()
    candidates = {PROFESSIONAL_MIX: (professional / professional.sum(), None)}
    for name in REMAINDER_MIXES:
        candidates[name] = mix_shares(name, base)
    roles = {
        WORKING_DAY_MIX: "covered part; non-working days; remainder",
        PROFESSIONAL_MIX: "professionals' work driving",
        national.EMEF_WEEKEND_PROXY: "non-working days; remainder",
        national.MOVILIA_WEEKEND: "non-working days; remainder",
    }
    rows = []
    for name, (shares, older) in candidates.items():
        per_resident = shares / people[list(GROUPS)]
        per_holder = shares / licences[list(GROUPS)]
        for group in GROUPS:
            rows.append(
                {
                    "mix": name,
                    "role": roles.get(name, "remainder"),
                    "credible": name not in BOUNDS,
                    "group": group,
                    "share_of_km": float(shares[group]),
                    "km_per_resident_relative_to_45_64": float(
                        per_resident[group] / per_resident[REFERENCE]
                    ),
                    "km_per_licence_holder_relative_to_45_64": float(
                        per_holder[group] / per_holder[REFERENCE]
                    ),
                    "share_75_plus_of_65_plus": older if group == "65+" else np.nan,
                }
            )
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- scenarios


@cache
def _profiles() -> dict[str, dict]:
    """The profile of the covered part: Method A's and every other of
    :func:`national.exposure_profiles`."""
    out = {
        national.CENTRAL_METHOD: national.emef_profile(),
        national.LICENCE_METHOD: national.licence_calibrated(national.emef_profile()),
    }
    for area in exposure.AREAS:
        out[f"C: EMEF, {area}"] = national.emef_profile(area)
    out["C: Madrid survey 2018"] = national.edm_profile()
    return out


@cache
def scenario_km() -> tuple[dict, ...]:
    """Every scenario's annual km shares by group, and its 75+ share of the 65+ km under each
    split assumption. The result is cached: callers must not change it."""
    weights = scenario_weights()
    _, professional = _daily_km()
    professional_mix = professional / professional.sum()
    splits = national._older_ratios()
    out = []
    for profile_name, profile in _profiles().items():
        km, _ = national.national_km(profile)
        base = km / km.sum()
        older = {}
        for assumption, ratios in splits.items():
            split = national._split_older(profile, ratios)
            older[assumption] = split["75+"] / (split["75+"] + split["65-74"])
        for non_working in NON_WORKING_MIXES:
            other, _ = mix_shares(non_working, base)
            for remainder in REMAINDER_MIXES:
                rest, rest_older = mix_shares(remainder, base)
                shares = (
                    weights["covered"] * base
                    + weights["professional"] * professional_mix
                    + weights["non_working"] * other
                    + weights["remainder"] * rest
                )
                inherited = (
                    weights["covered"] * base["65+"]
                    + weights["professional"] * professional_mix["65+"]
                    + weights["non_working"] * other["65+"]
                )
                own = weights["remainder"] * rest["65+"]
                oldest = {
                    assumption: (inherited * q + own * (q if rest_older is None else rest_older))
                    / float(shares["65+"])
                    for assumption, q in older.items()
                }
                out.append(
                    {
                        "profile": profile_name,
                        "non_working_mix": non_working,
                        "remainder_mix": remainder,
                        "credible": remainder not in BOUNDS,
                        "shares": shares,
                        "share_75_plus_of_65_plus": oldest,
                    }
                )
    return tuple(out)


@cache
def _counts() -> pd.DataFrame:
    return national.drivers_involved().set_index("group")


def ratios(shares: pd.Series, older_share: float | None = None) -> dict[str, float]:
    """Involvement (and deaths) per km over 45-64's for each group, from km shares; with the 75+
    share of the 65+ km, also for 65-74 and 75 and over."""
    counts = _counts()
    out = {}
    for measure in ("involved", "killed"):
        reference = float(counts.loc[REFERENCE, measure]) / float(shares[REFERENCE])
        for group in GROUPS:
            out[f"{measure}:{group}"] = (
                float(counts.loc[group, measure]) / float(shares[group]) / reference
            )
        if older_share is not None:
            parts = {"65-74": 1 - older_share, "75+": older_share}
            for group, part in parts.items():
                out[f"{measure}:{group}"] = (
                    float(counts.loc[group, measure]) / (part * float(shares["65+"])) / reference
                )
    return out


def scenarios() -> pd.DataFrame:
    """Every scenario under every split assumption: shares and involvement ratios to 45-64."""
    rows = []
    for scenario in scenario_km():
        shares = scenario["shares"]
        for assumption, older in scenario["share_75_plus_of_65_plus"].items():
            ratio = ratios(shares, older)
            rows.append(
                {
                    "profile": scenario["profile"],
                    "non_working_mix": scenario["non_working_mix"],
                    "remainder_mix": scenario["remainder_mix"],
                    "credible": scenario["credible"],
                    "assumption": assumption,
                    "share_18_29": float(shares["16-29"]),
                    "share_65_plus": float(shares["65+"]),
                    "share_75_plus_of_65_plus": older,
                    "ratio_18_29": ratio["involved:16-29"],
                    "ratio_30_44": ratio["involved:30-44"],
                    "ratio_65_plus": ratio["involved:65+"],
                    "ratio_65_74": ratio["involved:65-74"],
                    "ratio_75_plus": ratio["involved:75+"],
                }
            )
    return pd.DataFrame(rows)


def scenario_label(scenario: dict) -> str:
    return (
        f"remainder: {scenario['remainder_mix']}; non-working days: {scenario['non_working_mix']}"
    )
