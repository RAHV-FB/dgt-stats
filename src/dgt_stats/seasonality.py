"""Seasonality and mobility: deaths by month, beside monthly traffic series.

Road deaths in Spain peak in July and August and bottom out in February, and the 2020 lockdown cut
them by two thirds in April. This module sets each month's deaths beside the monthly series that
measure or stand in for traffic.

There is no monthly count of vehicle-kilometres on all Spanish roads. Three monthly series are
read, and only one of them is used as a denominator:

* **road fuel** (CORES automotive petrol plus diesel sold): every road and every vehicle, so it
  is the one exposure whose scope matches deaths on all roads. It is fuel sold, not kilometres
  driven, and it mixes freight with private travel, so deaths per tonne of road fuel are a proxy
  rate and are labelled as one.
* **petrol** sold alone: it leaves out every diesel vehicle, so it is not the exposure of all-road
  deaths. It is kept as a traffic index shown beside deaths, never as a denominator or offset.
* **toll-motorway intensity** (average daily vehicles per kilometre of the state toll network):
  measured traffic, but on a small part of the network, so it is not the exposure of all-road
  deaths either and is kept, like petrol, only as a traffic index. Intensity rather than
  vehicle-kilometres is read because the network shrank as concessions expired (``network_km``
  in the panel), which makes vehicle-kilometres fall for reasons that have nothing to do with
  traffic.

The seasonal profile is computed from 2014–2019 and 2022–2024, leaving out the two pandemic years;
each month's value is divided by the mean month of its own year, so the trend does not leak into the
season. ``deaths_per_road_fuel_tonnes`` in the profile is the deaths index divided by the road-fuel
index: 100 means that month's deaths are what its share of the year's fuel sales would predict.
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

# The monthly traffic series read beside deaths.
TRAFFIC_SERIES = {
    "road_fuel_tonnes": "Road fuel sold (petrol + diesel)",
    "petrol_tonnes": "Petrol sold only",
    "toll_intensity": "Toll-motorway traffic per km",
}
# The one series whose scope matches deaths on all roads, and so the only one used as exposure.
EXPOSURES = {"road_fuel_tonnes": TRAFFIC_SERIES["road_fuel_tonnes"]}
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

    One row per month: the deaths indices, the three traffic indices, and for each exposure in
    ``EXPOSURES`` the deaths index divided by its index (``deaths_per_<exposure>``).
    """
    panel = monthly_panel()
    panel = panel[panel.year.isin(years)].copy()
    series = [*OUTCOMES, *TRAFFIC_SERIES]
    for column in series:
        panel[column] = panel[column] / panel.groupby("year")[column].transform("mean") * 100
    profile = panel.groupby("month")[series].mean()
    records = []
    for month, row in profile.iterrows():
        record = {"month": int(month), "month_label": MONTH_NAMES[int(month) - 1]}
        for column in series:
            record[column] = float(row[column])
        for exposure in EXPOSURES:
            record[f"deaths_per_{exposure}"] = float(row["deaths_all"] / row[exposure] * 100)
        records.append(record)
    return pd.DataFrame.from_records(records)


def seasonal_profile_long(years: tuple[int, ...] = PROFILE_YEARS) -> pd.DataFrame:
    """The deaths and traffic indices of ``seasonal_profile`` stacked for plotting."""
    profile = seasonal_profile(years)
    labels = {"deaths_all": "Deaths, all roads", **TRAFFIC_SERIES}
    out = profile.melt(
        id_vars=["month", "month_label"],
        value_vars=list(labels),
        var_name="series",
        value_name="index",
    )
    out["series_label"] = out.series.map(labels)
    return out


def month_effects(years: tuple[int, ...] = PROFILE_YEARS) -> pd.DataFrame:
    """Month effects on deaths from quasi-Poisson models with year effects, with and without fuel.

    ``deaths ~ year + month`` gives the raw seasonality; adding ``log(road fuel)`` as an offset
    gives the seasonality of deaths *per tonne of road fuel sold*, the only exposure in
    ``EXPOSURES``. Effects are rate ratios against the average month (sum-to-zero contrasts), with
    95 % intervals on the overdispersed scale. A month whose interval straddles 1 under an exposure
    is not distinguishable from an ordinary month once that exposure is allowed for.
    ``first_year``, ``last_year``, ``n_years`` and ``years`` describe the pooled years.
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
                    "first_year": int(min(years)),
                    "last_year": int(max(years)),
                    "n_years": len(set(years)),
                    "years": " ".join(str(year) for year in sorted(set(years))),
                }
            )
    return pd.DataFrame.from_records(records)


def lockdown_months(
    year: int = LOCKDOWN_YEAR, baseline: tuple[int, ...] = LOCKDOWN_BASELINE
) -> pd.DataFrame:
    """Each month of 2020 against the same month's 2017–2019 mean: deaths and the three traffic series.

    ``<series>_change`` is the proportional change in deaths or in each traffic series.
    ``deaths_per_<exposure>_change`` is the change in deaths per unit of each exposure in
    ``EXPOSURES`` (road fuel only); petrol and toll-motorway traffic are changes in traffic, shown
    beside deaths, and are not used as denominators.
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
        for key in TRAFFIC_SERIES:
            change = float(current.loc[month, key] / base.loc[month, key])
            record[f"{key}_change"] = change - 1
            if key in EXPOSURES:
                record[f"deaths_per_{key}_change"] = (deaths / reference) / change - 1
        records.append(record)
    return pd.DataFrame.from_records(records)


def lockdown_long(year: int = LOCKDOWN_YEAR) -> pd.DataFrame:
    """The 2020 changes stacked for plotting: deaths and the three traffic series by month."""
    frame = lockdown_months(year)
    labels = {"deaths_change": "Deaths, all roads"} | {
        f"{key}_change": label for key, label in TRAFFIC_SERIES.items()
    }
    out = frame.melt(
        id_vars=["month", "month_label"],
        value_vars=list(labels),
        var_name="series",
        value_name="change",
    )
    out["series_label"] = out.series.map(labels)
    return out
