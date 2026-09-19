"""Descriptive summaries for the site: trends (Q1), timing (Q2), geography (Q4), road users (Q5),
exposure-adjusted rates for older drivers (Q7) and, through ``vehicles``, ``policy`` and ``speed``,
rates per kilometre (Q6), the interrupted time series (Q8) and the speed chapter (Q9).

Every function returns a tidy ``pandas.DataFrame`` built from the interim or processed layers. The
column names are stable because the site and the tests key on them.
"""

from __future__ import annotations

from functools import cache

import pandas as pd

from dgt_stats import (
    agebands,
    codes,
    io_activity,
    io_exposure,
    io_population,
    io_tables,
    labels,
    rates,
    policy,
    speed,
    validate,
    vehicles,
)
from dgt_stats.paths import PROCESSED_DATA_DIR, TABLES_DIR

PROCESSED_CRASHES = PROCESSED_DATA_DIR / "accidentes.parquet"

BASE_YEAR = 2019
LATEST_TABLE_YEAR = 2024
SEVERITY_METRICS = ("crashes", "deaths_30d", "hospitalised_30d", "non_hospitalised_30d")

CRASH_COLUMNS = [
    "ANYO",
    "MES",
    "DIA_SEMANA",
    "HORA",
    "zone",
    "road_group",
    "hour_band",
    "night",
    "fatal",
    "serious",
    "n_deaths",
    "n_vulnerable_deaths",
    "TOTAL_MU30DF",
    *labels.ROAD_USER_TYPES,
]


def read_crashes(columns: list[str] | None = None) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_CRASHES, columns=columns or CRASH_COLUMNS)


# --------------------------------------------------------------------------- Q1 trends


def annual_headline() -> pd.DataFrame:
    """Crashes, deaths, hospitalised and non-hospitalised per year, 1993–2024, with index 2019 = 100."""
    annual = io_tables.read_table("series_annual")
    wide = (
        annual[(annual.zone == "all") & annual.metric.isin(SEVERITY_METRICS)]
        .pivot(index="year", columns="metric", values="value")
        .reindex(columns=list(SEVERITY_METRICS))
        .reset_index()
    )
    for metric in SEVERITY_METRICS:
        base = wide.loc[wide.year == BASE_YEAR, metric].iloc[0]
        wide[f"{metric}_index"] = (wide[metric] / base * 100).round(1)
    wide["deaths_per_100_crashes"] = (wide.deaths_30d / wide.crashes * 100).round(2)
    return wide


def annual_rates() -> pd.DataFrame:
    """DGT's published rates: fleet and crashes/deaths per 10,000 vehicles, deaths per 10,000 people."""
    annual = io_tables.read_table("series_annual")
    published = annual[annual.source_sheet == "Tasas_Acc_Vic"]
    return published.pivot(index="year", columns="metric", values="value").reset_index()


def annual_by_zone() -> pd.DataFrame:
    """Crashes and deaths per year and zone from the microdata (2016–2024)."""
    crashes = read_crashes(["ANYO", "zone", "fatal", "n_deaths", "serious"])
    out = (
        crashes.groupby(["ANYO", "zone"], observed=True)
        .agg(
            crashes=("fatal", "size"),
            fatal_crashes=("fatal", "sum"),
            deaths_30d=("n_deaths", "sum"),
        )
        .reset_index()
        .rename(columns={"ANYO": "year"})
    )
    out["deaths_per_100_crashes"] = (out.deaths_30d / out.crashes * 100).round(2)
    return out


def monthly_deaths() -> pd.DataFrame:
    """30-day deaths per month, 1993–2024, all roads, with each year's share by month."""
    monthly = io_tables.read_table("series_monthly")
    deaths = monthly[(monthly.metric == "deaths_30d") & (monthly.zone == "all")]
    out = deaths[["year", "month", "value"]].rename(columns={"value": "deaths_30d"}).copy()
    out["share_of_year"] = (out.deaths_30d / out.groupby("year").deaths_30d.transform("sum")).round(
        4
    )
    out["month_label"] = out.month.map(labels.MONTHS)
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- Q2 timing


def hour_weekday(years: tuple[int, ...] | None = None) -> pd.DataFrame:
    """Crashes and fatal share by hour of day × weekday (2016–2024 pooled unless ``years`` given)."""
    crashes = read_crashes(["ANYO", "HORA", "DIA_SEMANA", "fatal", "n_deaths"])
    if years:
        crashes = crashes[crashes.ANYO.isin(years)]
    out = (
        crashes.groupby(["DIA_SEMANA", "HORA"], observed=True)
        .agg(
            crashes=("fatal", "size"),
            fatal_crashes=("fatal", "sum"),
            deaths_30d=("n_deaths", "sum"),
        )
        .reset_index()
        .rename(columns={"DIA_SEMANA": "weekday", "HORA": "hour"})
    )
    out["fatal_share"] = (out.fatal_crashes / out.crashes).round(4)
    out["weekday_label"] = out.weekday.astype(int).map(labels.WEEKDAYS)
    return out


def month_zone() -> pd.DataFrame:
    """Crashes and deaths by month and zone, 2016–2024 pooled, with average per year."""
    crashes = read_crashes(["ANYO", "MES", "zone", "fatal", "n_deaths"])
    n_years = crashes.ANYO.nunique()
    out = (
        crashes.groupby(["MES", "zone"], observed=True)
        .agg(crashes=("fatal", "size"), deaths_30d=("n_deaths", "sum"))
        .reset_index()
        .rename(columns={"MES": "month"})
    )
    out["crashes_per_year"] = (out.crashes / n_years).round(1)
    out["deaths_per_year"] = (out.deaths_30d / n_years).round(1)
    out["month_label"] = out.month.astype(int).map(labels.MONTHS)
    return out


def night_share_by_year_zone() -> pd.DataFrame:
    """Share of crashes and of deaths that happen in darkness, by year and zone."""
    crashes = read_crashes(["ANYO", "zone", "night", "fatal", "n_deaths"])
    grouped = crashes.groupby(["ANYO", "zone"], observed=True)
    out = grouped.agg(crashes=("fatal", "size"), deaths_30d=("n_deaths", "sum")).reset_index()
    night = (
        crashes[crashes.night]
        .groupby(["ANYO", "zone"], observed=True)
        .agg(night_crashes=("fatal", "size"), night_deaths=("n_deaths", "sum"))
        .reset_index()
    )
    out = out.merge(night, on=["ANYO", "zone"], how="left").fillna(
        {"night_crashes": 0, "night_deaths": 0}
    )
    out["night_crash_share"] = (out.night_crashes / out.crashes).round(4)
    out["night_death_share"] = (out.night_deaths / out.deaths_30d).round(4)
    return out.rename(columns={"ANYO": "year"})


def hour_band_by_road_group() -> pd.DataFrame:
    """Crashes and fatal share by hour band × road group, 2016–2024 pooled."""
    crashes = read_crashes(["hour_band", "road_group", "fatal", "n_deaths"])
    crashes = crashes.dropna(subset=["hour_band", "road_group"])
    out = (
        crashes.groupby(["road_group", "hour_band"], observed=True)
        .agg(
            crashes=("fatal", "size"),
            fatal_crashes=("fatal", "sum"),
            deaths_30d=("n_deaths", "sum"),
        )
        .reset_index()
    )
    out["fatal_share"] = (out.fatal_crashes / out.crashes).round(4)
    out["road_group_label"] = out.road_group.map(labels.ROAD_GROUPS)
    out["hour_band_label"] = out.hour_band.map(labels.HOUR_BANDS)
    return out


# --------------------------------------------------------------------------- Q5 road users


def deaths_by_road_user() -> pd.DataFrame:
    """30-day deaths by road-user type, year and zone (2016–2024), long format with shares."""
    columns = ["ANYO", "zone", *labels.ROAD_USER_TYPES]
    crashes = read_crashes(columns)
    totals = crashes.groupby(["ANYO", "zone"], observed=True)[list(labels.ROAD_USER_TYPES)].sum(
        min_count=1
    )
    long = (
        totals.reset_index()
        .melt(id_vars=["ANYO", "zone"], var_name="column", value_name="deaths_30d")
        .rename(columns={"ANYO": "year"})
    )
    long["road_user"] = long.column.map(labels.ROAD_USER_TYPES)
    long["vulnerable"] = long.column.isin(labels.VULNERABLE_TYPES)
    long["share"] = (
        long.deaths_30d / long.groupby(["year", "zone"]).deaths_30d.transform("sum")
    ).round(4)
    return long[["year", "zone", "column", "road_user", "vulnerable", "deaths_30d", "share"]]


def vulnerable_share_by_year() -> pd.DataFrame:
    """Share of all 30-day deaths that were pedestrians, cyclists, moped, motorcycle or PMV users."""
    crashes = read_crashes(["ANYO", "zone", "n_deaths", "n_vulnerable_deaths"])
    out = (
        crashes.groupby(["ANYO", "zone"], observed=True)
        .agg(deaths_30d=("n_deaths", "sum"), vulnerable_deaths=("n_vulnerable_deaths", "sum"))
        .reset_index()
        .rename(columns={"ANYO": "year"})
    )
    out["vulnerable_share"] = (out.vulnerable_deaths / out.deaths_30d).round(4)
    return out


def driver_deaths_series() -> pd.DataFrame:
    """Driver deaths (30-day) by vehicle type, 1993–2024, all roads, from the yearbook series."""
    users = io_tables.read_table("series_road_users")
    rows = users[
        (users.population == "drivers")
        & (users.severity == "deaths_30d")
        & (users.zone == "all")
        & (~users.is_total)
    ]
    out = rows[["year", "vehicle_type", "value"]].rename(columns={"value": "deaths_30d"}).copy()
    out["vehicle_type_label"] = out.vehicle_type.map(labels.SERIES_VEHICLE_TYPES)
    return out.reset_index(drop=True)


def pedestrian_series() -> pd.DataFrame:
    """Pedestrian victims by severity and zone, 1993–2024, from the yearbook series."""
    ped = io_tables.read_table("series_pedestrians")
    rows = ped[(ped.breakdown == "severity") & (ped.category != "victims_30d")]
    out = rows.pivot(index=["year", "zone"], columns="category", values="value").reset_index()
    return out.rename_axis(columns=None)


# --------------------------------------------------------------------------- Q4 geography


def province_codes() -> dict[str, str]:
    """Normalised DGT province name -> two-digit code, from the crash dictionary."""
    labels_by_code = codes.labels_for("COD_PROVINCIA")
    return {
        validate._normalise_province(name): code.zfill(2) for code, name in labels_by_code.items()
    }


def licence_holders_by_province(year: int) -> pd.Series:
    """Licensed drivers per province code for one census-by-age year (2023–2025)."""
    census = io_exposure.read_exposure("censo_edad")
    rows = census[census.census_year == year]
    return rows.groupby("province_code").n_drivers.sum()


def province_rates() -> pd.DataFrame:
    """Crashes, deaths and hospitalised per 100,000 residents and deaths per 100,000 licence holders,
    by province for the latest statistical-table year, with exact Poisson intervals and a rank on
    the resident death rate."""
    year = LATEST_TABLE_YEAR
    table = io_tables.read_table("tables_2024_province")
    table = table[table.zone == "all"]
    wide = table.pivot(index="province", columns="metric", values="value").reset_index()
    names = province_codes()
    wide["province_code"] = wide.province.map(lambda n: names.get(validate._normalise_province(n)))
    wide.loc[wide.province.str.lower() == "total", "province_code"] = io_population.NATIONAL_CODE
    if wide.province_code.isna().any():
        raise ValueError(f"province rates: unmapped provinces {wide[wide.province_code.isna()]}")
    population = io_population.population_by_province(year).set_index("province_code").population
    licences = licence_holders_by_province(year)
    licences[io_population.NATIONAL_CODE] = licences.sum()
    out = pd.DataFrame(
        {
            "province_code": wide.province_code.astype("string"),
            "province": wide.province.astype("string"),
            "is_total": wide.province_code == io_population.NATIONAL_CODE,
            "crashes": wide.crashes.astype("int64"),
            "deaths_30d": wide.deaths_30d.astype("int64"),
            "hospitalised_30d": wide.hospitalised_30d.astype("int64"),
            "population": wide.province_code.map(population).astype("int64"),
            "licence_holders": wide.province_code.map(licences).astype("int64"),
        }
    )
    out = rates.add_rate(out, "crashes", "population", "crashes_per_100k")
    out = rates.add_rate(out, "deaths_30d", "population", "deaths_per_100k")
    out = rates.add_rate(out, "hospitalised_30d", "population", "hospitalised_per_100k")
    out = rates.add_rate(out, "deaths_30d", "licence_holders", "deaths_per_100k_licence")
    out["deaths_rank"] = (
        out.deaths_per_100k.where(~out.is_total).rank(ascending=False, method="min").astype("Int16")
    )
    out["year"] = year
    return out.sort_values(["is_total", "deaths_per_100k"], ascending=[True, False]).reset_index(
        drop=True
    )


def national_rates_by_year() -> pd.DataFrame:
    """Deaths per 100,000 residents (2002–2024) and per 100,000 licence holders (2014–2024)."""
    annual = io_tables.read_table("series_annual")
    wide = (
        annual[(annual.zone == "all") & annual.metric.isin(SEVERITY_METRICS)]
        .pivot(index="year", columns="metric", values="value")
        .reset_index()
    )
    population = io_population.read_population()
    national = (
        population[
            (population.province_code == io_population.NATIONAL_CODE)
            & (population.sex == "total")
            & (population.reference == "1 July")
            & population.all_ages
        ]
        .set_index("year")
        .population
    )
    licences = io_exposure.read_exposure("conductores_por_edad")
    licence_total = licences[licences.sex == "total"].groupby("year").n_drivers.sum()
    wide["population"] = wide.year.map(national).astype("Int64")
    wide["licence_holders"] = wide.year.map(licence_total).astype("Int64")
    wide = wide[wide.population.notna()].reset_index(drop=True)
    wide = rates.add_rate(wide, "deaths_30d", "population", "deaths_per_100k_residents")
    wide = rates.add_rate(wide, "crashes", "population", "crashes_per_100k_residents")
    wide = rates.add_rate(wide, "deaths_30d", "licence_holders", "deaths_per_100k_licence")
    return wide.rename_axis(columns=None)


# --------------------------------------------------------------------------- Q7 older road users

LADDER_YEARS = tuple(range(2014, 2025))
REFERENCE_BAND = "35-64"
COMPARISON_BANDS = {"65-74": ("65-74",), "75+": ("75+",), "65+": ("65-74", "75+")}
REFERENCE_MEMBERS = ("35-44", "45-54", "55-64")
# The historical series groups victims into these bands (65 and over is not split).
VICTIM_BANDS: dict[str, agebands.Band] = {
    "15-24": (15, 24),
    "25-34": (25, 34),
    "35-44": (35, 44),
    "45-54": (45, 54),
    "55-64": (55, 64),
    "65+": (65, None),
}


def _to_analysis_band(fine: pd.Series) -> pd.Series:
    """Map fine DGT band keys to analysis band keys (children and unknown become NA)."""
    mapping = {
        key: agebands.band_for(low, high, agebands.ANALYSIS_BANDS)
        for key, (low, high) in agebands.DGT_BANDS.items()
    }
    return fine.map(mapping).astype("string")


def _driver_counts(sex: str) -> pd.DataFrame:
    """Driver deaths, hospitalised and involved drivers per year × analysis band (both zones)."""
    victims = io_tables.read_table("tables_driver_victims")
    involved = io_tables.read_table("tables_drivers_involved")
    victims = victims[victims.is_total]
    involved = involved[involved.is_total]
    if sex != "total":
        victims = victims[victims.sex == sex]
        involved = involved[involved.sex == sex]
    victims = victims.assign(band=_to_analysis_band(victims.band)).dropna(subset=["band"])
    involved = involved.assign(band=_to_analysis_band(involved.band)).dropna(subset=["band"])
    deaths = victims[victims.severity == "deaths_30d"].groupby(["year", "band"]).value.sum()
    hospitalised = (
        victims[victims.severity == "hospitalised_30d"].groupby(["year", "band"]).value.sum()
    )
    drivers = involved.groupby(["year", "band"]).value.sum()
    out = pd.DataFrame(
        {
            "driver_deaths": deaths,
            "driver_hospitalised": hospitalised,
            "drivers_involved": drivers,
        }
    ).reset_index()
    return out.astype({"year": "int16", "band": "string"})


def _licence_holders(sex: str) -> pd.DataFrame:
    licences = io_exposure.read_exposure("conductores_por_edad")
    rows = licences[licences.sex == sex]
    rows = rows.assign(band=_to_analysis_band(rows.band)).dropna(subset=["band"])
    out = rows.groupby(["year", "band"]).n_drivers.sum().reset_index()
    return out.rename(columns={"n_drivers": "licence_holders"}).astype(
        {"year": "int16", "band": "string"}
    )


def _residents(years: tuple[int, ...], sex: str) -> pd.DataFrame:
    frames = [io_population.population_by_band(year, sex=sex).assign(year=year) for year in years]
    out = pd.concat(frames, ignore_index=True).rename(columns={"population": "residents"})
    return out.astype({"year": "int16", "band": "string"})


@cache
def _movilia_intensity(sex: str) -> dict[str, float]:
    """Weekday car-or-motorcycle trips per resident in 2006, by MOVILIA band."""
    trips = io_activity.read_movilia_trips()
    weekday = (
        trips[
            (trips.day_type == "weekday")
            & (trips.sex == sex)
            & (trips.transport_mode == "car_or_motorcycle")
            & (trips.band != "all")
        ]
        .set_index("band")
        .trips_thousands
    )
    pop_2006 = io_population.population_by_band(2006, agebands.MOVILIA_BANDS, sex=sex)
    return (weekday * 1000 / pop_2006.set_index("band").population).to_dict()


def car_travel_profile(year: int, sex: str = "total") -> pd.Series:
    """Relative car-travel intensity by analysis band, from MOVILIA 2006 trips per resident.

    Trips by "coche o moto" per resident are computed for the MOVILIA bands (2006 population), given
    to every five-year INE group inside them, averaged into the analysis bands with ``year``'s
    population, and scaled so the population-weighted mean over 15–74 is 1 (the ESRA age range).
    The 75+ band inherits the 65+ intensity.
    """
    intensity = _movilia_intensity(sex)
    groups = io_population.population(year, sex=sex)
    groups = groups[groups.age_low >= 15].copy()
    groups["movilia_band"] = [
        agebands.band_for(int(low), None if pd.isna(high) else int(high), agebands.MOVILIA_BANDS)
        for low, high in zip(groups.age_low, groups.age_high)
    ]
    groups["band"] = [
        agebands.band_for(int(low), None if pd.isna(high) else int(high))
        for low, high in zip(groups.age_low, groups.age_high)
    ]
    groups["intensity"] = groups.movilia_band.map(intensity)
    groups["weighted"] = groups.intensity * groups.population
    by_band = groups.groupby("band").agg(
        weighted=("weighted", "sum"), population=("population", "sum")
    )
    profile = by_band.weighted / by_band.population
    esra_range = [band for band in agebands.ANALYSIS_BANDS if band != "75+"]
    mean = by_band.loc[esra_range].weighted.sum() / by_band.loc[esra_range].population.sum()
    return (profile / mean).reindex(list(agebands.ANALYSIS_BANDS))


@cache
def _ladder(sex: str) -> pd.DataFrame:
    """The denominator ladder: year × band with residents, licence holders, travel-weighted
    drivers (driver-equivalents), involved drivers, driver deaths and the rate against each."""
    residents = _residents(LADDER_YEARS, sex)
    licences = _licence_holders(sex)
    counts = _driver_counts(sex)
    out = residents.merge(licences, on=["year", "band"], how="left").merge(
        counts, on=["year", "band"], how="left"
    )
    out["licence_share"] = out.licence_holders / out.residents
    waves = io_activity.esra_shares()
    travel_frames = []
    for year in LADDER_YEARS:
        profile = car_travel_profile(year, sex)
        licence_share = out[out.year == year].set_index("band").licence_share
        share = rates.travel_weighted_share(year, waves, profile, licence_share).assign(year=year)
        travel_frames.append(share)
    travel = pd.concat(travel_frames, ignore_index=True).astype({"year": "int16"})
    out = out.merge(travel, on=["year", "band"], how="left")
    out = out.rename(
        columns={
            "share": "travel_share",
            "share_low": "travel_share_low",
            "share_high": "travel_share_high",
            "national_share": "esra_national_share",
            "capped": "travel_capped",
        }
    )
    out["travel_weighted_drivers"] = out.residents * out.travel_share
    out["travel_weighted_drivers_low"] = out.residents * out.travel_share_low
    out["travel_weighted_drivers_high"] = out.residents * out.travel_share_high
    out = rates.add_rate(out, "driver_deaths", "residents", "deaths_per_million_residents", 1e6)
    out = rates.add_rate(out, "driver_deaths", "licence_holders", "deaths_per_100k_licence")
    out["deaths_per_100k_travel"] = out.driver_deaths / out.travel_weighted_drivers * 1e5
    # Envelope for the travel-weighted rate: Poisson bounds combined with the survey band.
    poisson = [rates.poisson_interval(c) for c in out.driver_deaths.astype(float)]
    out["deaths_per_100k_travel_low"] = [
        low / high_exposure * 1e5 if high_exposure else float("nan")
        for (low, _), high_exposure in zip(poisson, out.travel_weighted_drivers_high)
    ]
    out["deaths_per_100k_travel_high"] = [
        high / low_exposure * 1e5 if low_exposure else float("nan")
        for (_, high), low_exposure in zip(poisson, out.travel_weighted_drivers_low)
    ]
    out = rates.add_rate(
        out, "drivers_involved", "licence_holders", "involved_per_10k_licence", 1e4
    )
    out = rates.add_rate(out, "driver_deaths", "drivers_involved", "deaths_per_1k_involved", 1e3)
    out["sex"] = sex
    return out.astype({"sex": "string"})


def driver_ladder(sex: str = "total") -> pd.DataFrame:
    """The denominator ladder (see :func:`_ladder`); computed once per sex and copied out."""
    return _ladder(sex).copy()


def _band_group(frame: pd.DataFrame, members: tuple[str, ...]) -> pd.DataFrame:
    rows = frame[frame.band.isin(members)]
    return rows.groupby("year")[
        [
            "residents",
            "licence_holders",
            "travel_weighted_drivers",
            "drivers_involved",
            "driver_deaths",
        ]
    ].sum()


LADDER_DENOMINATORS = {
    "residents": ("driver_deaths", "residents"),
    "licence_holders": ("driver_deaths", "licence_holders"),
    "travel_weighted": ("driver_deaths", "travel_weighted_drivers"),
    "drivers_involved": ("driver_deaths", "drivers_involved"),
    "involvement_per_licence": ("drivers_involved", "licence_holders"),
}


def ladder_ratio(ladder: pd.DataFrame | None = None) -> pd.DataFrame:
    """Older bands relative to 35–64: the rate ratio under every denominator, by year."""
    ladder = ladder if ladder is not None else driver_ladder()
    reference = _band_group(ladder, REFERENCE_MEMBERS)
    records = []
    for band, members in COMPARISON_BANDS.items():
        group = _band_group(ladder, members)
        for year in group.index:
            for denominator, (count, exposure) in LADDER_DENOMINATORS.items():
                ratio, low, high = rates.rate_ratio(
                    group.loc[year, count],
                    group.loc[year, exposure],
                    reference.loc[year, count],
                    reference.loc[year, exposure],
                )
                records.append(
                    {
                        "year": int(year),
                        "band": band,
                        "reference": REFERENCE_BAND,
                        "denominator": denominator,
                        "ratio": ratio,
                        "ratio_low": low,
                        "ratio_high": high,
                    }
                )
    out = pd.DataFrame.from_records(records)
    return out.astype(
        {"year": "int16", "band": "string", "reference": "string", "denominator": "string"}
    )


def licence_share_by_age(years: tuple[int, ...] = (2014, 2019, 2024)) -> pd.DataFrame:
    """Share of residents holding a licence, by analysis band and sex, for a few years."""
    frames = []
    for sex in ("total", "male", "female"):
        residents = _residents(years, sex)
        licences = _licence_holders(sex)
        merged = residents.merge(licences, on=["year", "band"], how="left")
        merged["licence_share"] = merged.licence_holders / merged.residents
        merged["sex"] = sex
        frames.append(merged)
    out = pd.concat(frames, ignore_index=True)
    return out.astype({"sex": "string"})


def victims_by_age_rates() -> pd.DataFrame:
    """All road deaths (any road user) per million residents by age band, 2002–2024, from the series."""
    ages = io_tables.read_table("series_age")
    deaths = ages[(ages.zone == "all") & (ages.severity == "deaths_30d")].copy()
    deaths = deaths[deaths.year >= 2002]
    keys = []
    for label in deaths.age_band:
        if str(label).strip().lower() == "total":
            keys.append(None)
            continue
        parsed = agebands.parse_age_label(label)
        keys.append(None if parsed is None else agebands.band_for(*parsed, VICTIM_BANDS))
    deaths["band"] = pd.Series(keys, index=deaths.index, dtype="string")
    deaths = deaths.dropna(subset=["band"])
    frames = []
    for year in sorted(deaths.year.unique()):
        population = io_population.population_by_band(int(year), VICTIM_BANDS)
        frames.append(population.assign(year=int(year)))
    residents = pd.concat(frames, ignore_index=True).rename(columns={"population": "residents"})
    out = residents.merge(
        deaths[["year", "band", "value"]].rename(columns={"value": "deaths_30d"}),
        on=["year", "band"],
        how="left",
    )
    out = rates.add_rate(out, "deaths_30d", "residents", "deaths_per_million", 1e6)
    return out.astype({"year": "int16", "band": "string"})


def movilia_car_travel() -> pd.DataFrame:
    """MOVILIA 2006: trips by car or motorcycle per resident and their share of all trips, by band."""
    trips = io_activity.read_movilia_trips()
    trips = trips[trips.band != "all"]
    wide = trips.pivot_table(
        index=["day_type", "sex", "band"], columns="transport_mode", values="trips_thousands"
    ).reset_index()
    frames = []
    for sex in ("total", "male", "female"):
        population = io_population.population_by_band(2006, agebands.MOVILIA_BANDS, sex=sex)
        frames.append(population.assign(sex=sex))
    population = pd.concat(frames, ignore_index=True)
    out = wide.merge(population, on=["sex", "band"], how="left")
    out["car_trips_per_resident"] = out.car_or_motorcycle * 1000 / out.population
    out["trips_per_resident"] = out.all_modes * 1000 / out.population
    out["car_share_of_trips"] = out.car_or_motorcycle / out.all_modes
    return out[
        [
            "day_type",
            "sex",
            "band",
            "population",
            "all_modes",
            "car_or_motorcycle",
            "trips_per_resident",
            "car_trips_per_resident",
            "car_share_of_trips",
        ]
    ].rename_axis(columns=None)


# --------------------------------------------------------------------------- Q3 severity models

# Written by scripts/model.py (the fits take minutes); analyse.py and the site only read them.
MODEL_TABLES = (
    "q3_model_coefficients",
    "q3_marginal_effects",
    "q3_calibration",
    "q3_holdout_summary",
    "q3_year_stability",
    "q3_profiles",
    "q3_predicted_grid",
    "q3_groupings",
)


def model_tables_present() -> bool:
    return all((TABLES_DIR / f"{name}.csv").exists() for name in MODEL_TABLES)


def read_model_table(name: str) -> pd.DataFrame:
    """One of the Q3 result tables; a clear error when the models have not been fitted yet."""
    if name not in MODEL_TABLES:
        raise KeyError(f"not a model table: {name}")
    path = TABLES_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path.name} missing: run `python scripts/model.py` first")
    return pd.read_csv(path)


# --------------------------------------------------------------------------- Q8 policy

_points_licence = cache(policy.points_licence_fits)
_speed_limit = cache(policy.speed_limit_fits)


def _policy_table(name: str):
    source = _points_licence if name.startswith("q8_points") else _speed_limit
    return lambda: source()[name].copy()


# --------------------------------------------------------------------------- registry

SUMMARIES = {
    "q1_annual_headline": annual_headline,
    "q1_annual_rates": annual_rates,
    "q1_annual_by_zone": annual_by_zone,
    "q1_monthly_deaths": monthly_deaths,
    "q2_hour_weekday": hour_weekday,
    "q2_month_zone": month_zone,
    "q2_night_share": night_share_by_year_zone,
    "q2_hour_band_road_group": hour_band_by_road_group,
    "q5_deaths_by_road_user": deaths_by_road_user,
    "q5_vulnerable_share": vulnerable_share_by_year,
    "q5_driver_deaths_series": driver_deaths_series,
    "q5_pedestrian_series": pedestrian_series,
    "q4_province_rates": province_rates,
    "q4_national_rates": national_rates_by_year,
    "q7_driver_ladder": driver_ladder,
    "q7_ladder_ratio": ladder_ratio,
    "q7_licence_share": licence_share_by_age,
    "q7_victims_by_age": victims_by_age_rates,
    "q7_movilia_car_travel": movilia_car_travel,
    "q6_vehicle_groups": vehicles.vehicle_groups_table,
    "q6_vehicle_km_2022": vehicles.vehicle_km,
    "q6_km_by_age_2022": vehicles.km_by_age,
    "q6_rates_2022": vehicles.rates_2022,
    "q6_summary_2022": vehicles.summary_2022,
    "q6_van_light_truck_split": vehicles.van_light_truck_split,
    "q6_involvement_by_year": vehicles.involvement_by_year,
    "q6_occupant_deaths_series": vehicles.occupant_deaths_series,
    "q9_infraction_shares": speed.infraction_shares,
    "q9_infractions_by_vehicle": speed.infractions_by_vehicle,
    "q9_other_infractions": speed.other_infractions,
    "q9_report_factors": speed.report_factors,
    "q9_report_road_type": speed.report_road_type,
    "q9_report_speed_limit": speed.report_speed_limit,
    "q9_report_vehicle": speed.report_vehicle,
    "q9_report_age": speed.report_age,
    "q9_report_day_hour": speed.report_day_hour,
    "q9_report_licence": speed.report_licence,
    **{
        name: _policy_table(name)
        for name in (
            "q8_points_fit",
            "q8_points_series",
            "q8_points_placebo",
            "q8_points_sensitivity",
            "q8_speed_fit",
            "q8_speed_series",
            "q8_speed_placebo",
            "q8_speed_sensitivity",
        )
    },
}
