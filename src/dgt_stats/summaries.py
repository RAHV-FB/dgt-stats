"""Result tables for the site, and the registry that names them.

``SUMMARIES`` is the whole published set: the context series, the kilometre-based driver-risk
tables (``driver_risk``), the per-kilometre vehicle rates (``vehicles``), the interrupted time
series (``policy``) and the speed-status shares (``speed``). The severity models are written
separately by ``scripts/model.py`` and read back with :func:`read_model_table`.

Every function returns a tidy ``pandas.DataFrame`` built from the staging or processed layers. The
column names are stable because the site and the tests key on them.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd

from dgt_stats import (
    agebands,
    crash_cells,
    driver_risk,
    factors,
    io_exposure,
    io_population,
    labels,
    policy,
    risk_trends,
    road_class,
    seasonality,
    speed,
    vehicles,
)
from dgt_stats.paths import DGT_PROCESSED_CRASHES, TABLES_DIR

PROCESSED_CRASHES = DGT_PROCESSED_CRASHES

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


# --------------------------------------------------------------------------- context


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


# Written by scripts/model.py (the fits take several minutes); analyse.py and the site only
# read them.
MODEL_TABLES = (
    "q3_model_coefficients",
    "q3_calibration",
    "q3_holdout_summary",
    "q3_period_refits",
    "q3_location_contrasts",
    "q3_profiles",
    "q3_adverse_conditions",
    "q3_recording_regime",
    "q3_regime_sensitivity",
    "q3_junction_coding",
    "q3_junction_sensitivity",
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


def _policy_table(name: str):
    return lambda: _points_licence()[name].copy()


# --------------------------------------------------------------------------- registry

SUMMARIES = {
    # 2019 to 2024: counts against exposure
    "risk_annual_panel": risk_trends.annual_panel,
    "risk_index": risk_trends.risk_index,
    "risk_dispersion": risk_trends.year_to_year_dispersion,
    "risk_frequency_severity": risk_trends.frequency_severity,
    "risk_km_crosscheck": risk_trends.km_crosscheck,
    # The long run and the pandemic
    "longrun_series": risk_trends.long_run_series,
    "longrun_segments": risk_trends.long_run_segments,
    "longrun_model_choice": risk_trends.long_run_model_choice,
    "longrun_projection_sensitivity": risk_trends.long_run_projection_sensitivity,
    "longrun_efficiency": risk_trends.long_run_efficiency_sensitivity,
    "longrun_km_panel": risk_trends.interurban_km_panel,
    "longrun_km_check": risk_trends.km_trend_check,
    "longrun_km_coverage": risk_trends.interurban_network_coverage,
    "longrun_fuel_bio": risk_trends.fuel_bio_share,
    # Casualties by road class, and deaths per measured vehicle-km on interurban roads
    "road_class_risk": road_class.class_risk,
    # Seasonality and mobility
    "season_profile": seasonality.seasonal_profile,
    "season_month_effects": seasonality.month_effects,
    "season_lockdown": seasonality.lockdown_months,
    # Drivers by sex
    "drivers_sex_rates": driver_risk.sex_age_rates,
    "drivers_sex_ratios": driver_risk.sex_ratios,
    "drivers_sex_trend": driver_risk.sex_trend,
    "drivers_sex_b_licence": driver_risk.sex_b_licence,
    # Speed as a severity factor, and the other concurrent factors
    "speed_severity": factors.speed_severity,
    "speed_severity_pooled": factors.speed_severity_pooled,
    "factor_shares": factors.factor_shares_segmented,
    # Context: the 2024 road-type recoding
    "q2_other_road_by_period": other_road_by_period,
    # The crash statistics explorer's counts by year, region, road type and crash type
    crash_cells.NAME: crash_cells.crash_cells,
    "q9_infraction_shares": speed.infraction_shares,
    # Age and driving exposure
    "q7_km_by_owner_age": driver_risk.car_kilometres,
    "q7_km_rates": driver_risk.km_rates,
    "q7_km_ratio": driver_risk.km_rate_ratios,
    "q7_km_ratio_65_74": lambda: driver_risk.km_rate_ratios(reference_band="65-74"),
    "q7_company_km": driver_risk.company_km_sensitivity,
    "q7_owner_age_check": driver_risk.owner_age_check,
    "q7_denominator_contrast": driver_risk.denominator_contrast,
    "q7_licence_share": licence_share_by_age,
    # Vehicles per kilometre
    "q6_vehicle_km_2022": vehicles.vehicle_km,
    "q6_rates_2022": vehicles.rates_2022,
    "q6_summary_2022": vehicles.summary_2022,
    # Policy
    **{
        name: _policy_table(name)
        for name in (
            "q8_points_fit",
            "q8_points_series",
            "q8_points_sensitivity",
            "q8_points_trend_choice",
            "q8_points_calendar_placebo",
            "q8_points_calibration",
            "q8_points_transitions",
            "q8_points_forecast",
        )
    },
}
