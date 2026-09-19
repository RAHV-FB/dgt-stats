"""Descriptive summaries for the site: long-run trends (Q1), timing (Q2) and road-user types (Q5).

Every function returns a tidy ``pandas.DataFrame`` built from the interim or processed layers. The
column names are stable because the site and the tests key on them.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import io_tables, labels
from dgt_stats.paths import PROCESSED_DATA_DIR

PROCESSED_CRASHES = PROCESSED_DATA_DIR / "accidentes.parquet"

BASE_YEAR = 2019
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
    rates = annual[annual.source_sheet == "Tasas_Acc_Vic"]
    return rates.pivot(index="year", columns="metric", values="value").reset_index()


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
    totals = crashes.groupby(["ANYO", "zone"], observed=True)[list(labels.ROAD_USER_TYPES)].sum()
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
    out = rows.pivot_table(index=["year", "zone"], columns="category", values="value").reset_index()
    return out.rename_axis(columns=None)


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
}
