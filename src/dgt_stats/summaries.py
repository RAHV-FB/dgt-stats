"""Result tables for the site, and the registry that names them.

``SUMMARIES`` is the whole published set: the context series, the kilometre-based driver-risk
tables (``driver_risk``), the per-kilometre vehicle rates (``vehicles``), the interrupted time
series (``policy``) and the speed-status shares (``speed``). The severity models are written
separately by ``scripts/model.py`` and read back with :func:`read_model_table`.

Every function returns a tidy ``pandas.DataFrame`` built from the interim or processed layers. The
column names are stable because the site and the tests key on them.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd

from dgt_stats import (
    agebands,
    driver_risk,
    io_exposure,
    io_population,
    io_tables,
    labels,
    policy,
    speed,
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


# --------------------------------------------------------------------------- Q2 timing


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


def other_road_by_period() -> pd.DataFrame:
    """The "other" road group before and from 2024, when Barcelona starts coding streets as "other".

    One row per period (``2016-2023`` and ``2024``): crashes, their share of the pooled row, the share
    on urban streets (``ZONA`` 3) and the fatal share. The timing page reads it beside the pooled
    hour-band table, whose "other" row mixes the two.
    """
    crashes = read_crashes(["ANYO", "road_group", "ZONA", "fatal"])
    other = crashes[crashes.road_group == "other"].copy()
    other["period"] = np.where(other.ANYO >= 2024, "2024", "2016-2023")
    out = (
        other.groupby("period")
        .agg(
            crashes=("fatal", "size"),
            fatal_crashes=("fatal", "sum"),
            street_crashes=("ZONA", lambda z: int((pd.to_numeric(z, errors="coerce") == 3).sum())),
        )
        .reset_index()
    )
    out["share_of_row"] = (out.crashes / out.crashes.sum()).round(4)
    out["street_share"] = (out.street_crashes / out.crashes).round(4)
    out["fatal_share"] = (out.fatal_crashes / out.crashes).round(4)
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


# ------------------------------------------------------------------- licence holders by age


def _to_analysis_band(fine: pd.Series) -> pd.Series:
    """Map fine DGT band keys to analysis band keys (children and unknown become NA)."""
    mapping = {
        key: agebands.band_for(low, high, agebands.ANALYSIS_BANDS)
        for key, (low, high) in agebands.DGT_BANDS.items()
    }
    return fine.map(mapping).astype("string")


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


# Written by scripts/model.py (the fits take a minute and a half); analyse.py and the site only
# read them.
MODEL_TABLES = (
    "q3_model_coefficients",
    "q3_marginal_effects",
    "q3_calibration",
    "q3_holdout_summary",
    "q3_year_stability",
    "q3_profiles",
    "q3_adverse_conditions",
    "q3_adverse_composition",
    "q3_adverse_exclusions",
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
    # Context
    "q1_annual_headline": annual_headline,
    "q1_annual_by_zone": annual_by_zone,
    "q2_night_share": night_share_by_year_zone,
    "q2_other_road_by_period": other_road_by_period,
    "q5_deaths_by_road_user": deaths_by_road_user,
    "q9_infraction_shares": speed.infraction_shares,
    # Age and driving exposure
    "q7_km_by_owner_age": driver_risk.car_kilometres,
    "q7_km_rates": driver_risk.km_rates,
    "q7_km_ratio": driver_risk.km_rate_ratios,
    "q7_company_km": driver_risk.company_km_sensitivity,
    "q7_denominator_contrast": driver_risk.denominator_contrast,
    "q7_licence_share": licence_share_by_age,
    # Vehicles per kilometre
    "q6_vehicle_groups": vehicles.vehicle_groups_table,
    "q6_vehicle_km_2022": vehicles.vehicle_km,
    "q6_rates_2022": vehicles.rates_2022,
    "q6_summary_2022": vehicles.summary_2022,
    "q6_van_light_truck_split": vehicles.van_light_truck_split,
    # Policy
    **{
        name: _policy_table(name)
        for name in (
            "q8_points_fit",
            "q8_points_series",
            "q8_points_sensitivity",
            "q8_points_trend_choice",
            "q8_points_placebo",
            "q8_points_calendar_placebo",
            "q8_points_transitions",
            "q8_points_forecast",
            "q8_speed_placebo",
            "q8_speed_sensitivity",
        )
    },
}
