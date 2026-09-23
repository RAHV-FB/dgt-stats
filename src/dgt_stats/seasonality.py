"""Seasonality and mobility: how much of a month's deaths is a month's traffic.

Road deaths in Spain peak in July and August and bottom out in February, and the 2020 lockdown cut
them by two thirds in April. Both are routinely read as changes in how dangerous the roads were.
This module asks how much of each is simply a change in how much people drove.

There is no monthly count of vehicle-kilometres on all Spanish roads. Three monthly series stand in
for it, and each is wrong in a known direction, which is why all three are kept:

* **road fuel** (CORES petrol plus diesel): every road and every vehicle, but diesel carries
  freight, which keeps moving in a lockdown and slows in the August industrial holiday. It
  understates the swings in private travel.
* **petrol** alone: in Spain overwhelmingly burnt by cars and motorcycles, so the closest monthly
  proxy for private light-vehicle traffic, but blind to diesel cars.
* **toll-motorway intensity** (average daily vehicles per kilometre of the state toll network):
  measured traffic rather than a proxy, but on long-distance motorways whose traffic is dominated
  by holiday travel. It overstates the summer swing for the network as a whole. Intensity rather
  than vehicle-kilometres is used because the network shrank from about 2,500 to 1,400 km as
  concessions expired in 2018–2021, which makes vehicle-kilometres fall for reasons that have
  nothing to do with traffic.

The seasonal profile is computed from 2014–2019 and 2022–2024, leaving out the two pandemic years;
each month's value is divided by the mean month of its own year, so the trend does not leak into the
season. A month's *risk index* is its deaths index divided by its traffic index: 100 means that
month's deaths are exactly what its share of the year's traffic would predict.
"""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from dgt_stats import io_tables, io_traffic

PROFILE_YEARS = (2014, 2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024)
LOCKDOWN_YEAR = 2020
LOCKDOWN_BASELINE = (2017, 2018, 2019)

EXPOSURES = {
    "road_fuel_tonnes": "Road fuel (petrol + diesel)",
    "petrol_tonnes": "Petrol only",
    "toll_intensity": "Toll-motorway traffic per km",
}
OUTCOMES = {
    "deaths_all": "Deaths, all roads",
    "deaths_interurban": "Deaths, interurban roads",
    "deaths_urban": "Deaths, urban streets",
}
MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


@cache
def monthly_panel() -> pd.DataFrame:
    """Monthly 30-day deaths by zone with the three traffic series, one row per month.

    Deaths come from the yearbook series (1993 onwards); fuel from January 1996; toll traffic from
    January 1990. Months where any series is missing keep NA in that column.
    """
    monthly = io_tables.read_table("series_monthly")
    deaths = monthly[monthly.metric == "deaths_30d"].pivot_table(
        index=["year", "month"], columns="zone", values="value", aggfunc="first"
    )
    deaths.columns = [f"deaths_{zone}" for zone in deaths.columns]
    deaths = deaths.reset_index()
    fuel = io_traffic.read_cores_fuel()[["year", "month", "road_fuel_tonnes", "petrol_tonnes"]]
    toll = io_traffic.read_toll_traffic()[["year", "month", "imd", "network_km"]]
    toll = toll.rename(columns={"imd": "toll_intensity", "network_km": "toll_network_km"})
    out = deaths.merge(fuel, on=["year", "month"], how="left").merge(
        toll, on=["year", "month"], how="left"
    )
    out = out.astype({"year": "int16", "month": "int8"})
    return out.sort_values(["year", "month"]).reset_index(drop=True)


def seasonal_profile(years: tuple[int, ...] = PROFILE_YEARS) -> pd.DataFrame:
    """Mean month index (the average month of each year = 100) for deaths and traffic.

    One row per month and series. ``risk_index`` columns divide a deaths index by a traffic index.
    """
    panel = monthly_panel()
    panel = panel[panel.year.isin(years)].copy()
    series = [*OUTCOMES, *EXPOSURES]
    for column in series:
        panel[column] = panel[column] / panel.groupby("year")[column].transform("mean") * 100
    profile = panel.groupby("month")[series].mean()
    records = []
    for month, row in profile.iterrows():
        record = {"month": int(month), "month_label": MONTH_NAMES[int(month) - 1]}
        for column in series:
            record[column] = float(row[column])
        for exposure in EXPOSURES:
            record[f"risk_{exposure}"] = float(row["deaths_all"] / row[exposure] * 100)
        records.append(record)
    return pd.DataFrame.from_records(records)


def seasonal_profile_long(years: tuple[int, ...] = PROFILE_YEARS) -> pd.DataFrame:
    """The deaths and traffic indices of ``seasonal_profile`` stacked for plotting."""
    profile = seasonal_profile(years)
    labels = {"deaths_all": "Deaths, all roads", **EXPOSURES}
    out = profile.melt(
        id_vars=["month", "month_label"],
        value_vars=list(labels),
        var_name="series",
        value_name="index",
    )
    out["series_label"] = out.series.map(labels)
    return out


def month_effects(years: tuple[int, ...] = PROFILE_YEARS) -> pd.DataFrame:
    """Month effects on deaths from quasi-Poisson models with year effects, with and without traffic.

    ``deaths ~ year + month`` gives the raw seasonality; adding ``log(traffic)`` as an offset gives
    the seasonality of deaths *per unit of traffic*. Effects are rate ratios against the average
    month (sum-to-zero contrasts), with 95 % intervals on the overdispersed scale. A month whose
    interval straddles 1 under an exposure is not distinguishable from an ordinary month once
    that exposure is allowed for.
    """
    panel = monthly_panel()
    panel = panel[panel.year.isin(years)].copy()
    variants = {"none": None, **{key: key for key in EXPOSURES}}
    labels = {"none": "No exposure (raw deaths)", **EXPOSURES}
    records = []
    for key, exposure in variants.items():
        kwargs = {} if exposure is None else {"offset": np.log(panel[exposure].astype(float))}
        result = smf.glm(
            "deaths_all ~ C(year) + C(month, Sum)",
            data=panel,
            family=sm.families.Poisson(),
            **kwargs,
        ).fit(scale="X2")
        names = [name for name in result.params.index if name.startswith("C(month, Sum)")]
        params = result.params[names].to_numpy()
        cov = result.cov_params().loc[names, names].to_numpy()
        # The twelfth month is minus the sum of the other eleven.
        weights = np.vstack([np.eye(11), -np.ones((1, 11))])
        effects = weights @ params
        ses = np.sqrt(np.einsum("ij,jk,ik->i", weights, cov, weights))
        for month in range(12):
            records.append(
                {
                    "exposure": key,
                    "exposure_label": labels[key],
                    "month": month + 1,
                    "month_label": MONTH_NAMES[month],
                    "rate_ratio": float(np.exp(effects[month])),
                    "low": float(np.exp(effects[month] - 1.96 * ses[month])),
                    "high": float(np.exp(effects[month] + 1.96 * ses[month])),
                    "dispersion": float(result.scale),
                }
            )
    return pd.DataFrame.from_records(records)


def lockdown_months(
    year: int = LOCKDOWN_YEAR, baseline: tuple[int, ...] = LOCKDOWN_BASELINE
) -> pd.DataFrame:
    """Each month of 2020 against the same month's 2017–2019 mean: deaths and the three traffic series.

    ``change`` is the proportional change; for deaths the interval is exact Poisson on the 2020
    count, scaled by the baseline mean (treated as known). ``risk_change_*`` is the change in
    deaths per unit of each traffic series.
    """
    panel = monthly_panel()
    base = panel[panel.year.isin(baseline)].groupby("month").mean(numeric_only=True)
    current = panel[panel.year == year].set_index("month")
    records = []
    for month in range(1, 13):
        record = {"month": month, "month_label": MONTH_NAMES[month - 1]}
        deaths, reference = (
            float(current.loc[month, "deaths_all"]),
            float(base.loc[month, "deaths_all"]),
        )
        record["deaths"] = deaths
        record["deaths_baseline"] = reference
        record["deaths_change"] = deaths / reference - 1
        for key in EXPOSURES:
            change = float(current.loc[month, key] / base.loc[month, key])
            record[f"{key}_change"] = change - 1
            record[f"risk_change_{key}"] = (deaths / reference) / change - 1
        records.append(record)
    return pd.DataFrame.from_records(records)


def lockdown_long(year: int = LOCKDOWN_YEAR) -> pd.DataFrame:
    """The 2020 changes stacked for plotting: deaths and the three traffic series by month."""
    frame = lockdown_months(year)
    labels = {"deaths_change": "Deaths, all roads"} | {
        f"{key}_change": label for key, label in EXPOSURES.items()
    }
    out = frame.melt(
        id_vars=["month", "month_label"],
        value_vars=list(labels),
        var_name="series",
        value_name="change",
    )
    out["series_label"] = out.series.map(labels)
    return out
