"""Figure recipes: which summary feeds which chart, with the caption each figure carries."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dgt_stats import labels, plots, summaries
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR

CAPTIONS_PATH = FIGURES_DIR / "captions.json"

SERIES_SOURCE = "DGT, Series históricas del Anuario de Accidentes 2024"
MICRODATA_SOURCE = "DGT, Ficheros de microdatos de accidentes con víctimas 2016–2024"
THIRTY_DAY = "deaths within 30 days of the crash"

METRIC_LABELS = {
    "crashes": "Injury crashes",
    "deaths_30d": "Deaths (30 days)",
    "hospitalised_30d": "Hospitalised",
    "non_hospitalised_30d": "Non-hospitalised injured",
}

RATE_LABELS = {
    "crashes_per_10k_vehicles": "Crashes per 10,000 vehicles",
    "deaths_per_10k_vehicles": "Deaths per 10,000 vehicles",
    "deaths_per_10k_population": "Deaths per 10,000 inhabitants",
}

# Twelve road-user death columns folded to eight series (the fixed categorical limit).
ROAD_USER_FOLD = {
    "Pedestrians": "Pedestrians",
    "Cyclists": "Cyclists",
    "Moped riders": "Moped riders",
    "Motorcyclists": "Motorcyclists",
    "Personal mobility vehicles": "Personal mobility vehicles",
    "Car occupants": "Car occupants",
    "Van occupants": "Van occupants",
    "Light truck occupants (≤3.5 t)": "Trucks, buses and other",
    "Heavy truck occupants (>3.5 t)": "Trucks, buses and other",
    "Bus occupants": "Trucks, buses and other",
    "Other vehicles": "Trucks, buses and other",
    "Unspecified vehicle": "Trucks, buses and other",
}
ROAD_USER_ORDER = [
    "Pedestrians",
    "Cyclists",
    "Moped riders",
    "Motorcyclists",
    "Personal mobility vehicles",
    "Car occupants",
    "Van occupants",
    "Trucks, buses and other",
]


def _zone_label(series: pd.Series) -> pd.Series:
    return series.map(labels.ZONES)


def build_all(figures_dir: Path = FIGURES_DIR) -> dict[str, str]:
    """Write every figure as SVG and return ``{figure name: caption}``; also saves captions.json."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    captions: dict[str, str] = {}
    n_crashes = 875_013

    # ------------------------------------------------------------------ Q1 trends
    headline = summaries.annual_headline()
    indexed = headline.melt(
        id_vars="year",
        value_vars=[f"{m}_index" for m in METRIC_LABELS],
        var_name="metric",
        value_name="index",
    )
    indexed["metric"] = indexed.metric.str.replace("_index", "").map(METRIC_LABELS)
    plots.line_series(
        indexed,
        "year",
        "index",
        figures_dir / "q1_indexed_trend.svg",
        "Injury crashes and victims, index 2019 = 100",
        series="metric",
        ylabel="Index (2019 = 100)",
        reference=100,
        height=4.6,
        end_labels=False,
    )
    captions["q1_indexed_trend"] = plots.caption(
        SERIES_SOURCE,
        "1993–2024, all roads",
        "30-day counts; each series divided by its 2019 value",
    )

    plots.line_series(
        headline,
        "year",
        "deaths_30d",
        figures_dir / "q1_deaths_30d.svg",
        "Road deaths per year",
        ylabel="Deaths (30 days)",
    )
    captions["q1_deaths_30d"] = plots.caption(SERIES_SOURCE, "1993–2024, all roads", THIRTY_DAY)

    rates = summaries.annual_rates().melt(id_vars="year", var_name="metric", value_name="value")
    rates = rates[rates.metric.isin(RATE_LABELS)]
    rates["metric"] = rates.metric.map(RATE_LABELS)
    plots.small_multiples(
        rates,
        "metric",
        "year",
        "value",
        figures_dir / "q1_rates.svg",
        "Crashes and deaths relative to fleet and population",
        ncols=3,
        order=list(RATE_LABELS.values()),
    )
    captions["q1_rates"] = plots.caption(
        SERIES_SOURCE,
        "1993–2024",
        "DGT published rates; fleet = registered vehicles, 30-day deaths",
    )

    monthly = summaries.monthly_deaths()
    matrix = monthly.pivot(index="year", columns="month_label", values="share_of_year")
    matrix = matrix.reindex(columns=list(labels.MONTHS.values()))
    plots.heatmap(
        matrix,
        figures_dir / "q1_monthly_heatmap.svg",
        "Share of each year's road deaths by month",
        percent=True,
        annotate=False,
        height=7.5,
        xlabel="Month",
        ylabel="Year",
    )
    captions["q1_monthly_heatmap"] = plots.caption(
        SERIES_SOURCE, "1993–2024, all roads", "30-day deaths in the month as a share of the year"
    )

    by_zone = summaries.annual_by_zone()
    by_zone["zone"] = _zone_label(by_zone.zone)
    plots.line_series(
        by_zone,
        "year",
        "deaths_30d",
        figures_dir / "q1_deaths_by_zone.svg",
        "Road deaths by zone",
        series="zone",
        ylabel="Deaths (30 days)",
    )
    captions["q1_deaths_by_zone"] = plots.caption(
        MICRODATA_SOURCE, "2016–2024", THIRTY_DAY, n_crashes
    )

    # ------------------------------------------------------------------ Q2 timing
    grid = summaries.hour_weekday()
    crashes_matrix = grid.pivot(index="weekday_label", columns="hour", values="crashes")
    crashes_matrix = crashes_matrix.reindex(index=list(labels.WEEKDAYS.values()))
    plots.heatmap(
        crashes_matrix,
        figures_dir / "q2_hour_weekday_crashes.svg",
        "Injury crashes by weekday and hour",
        annotate=False,
        height=3.2,
        xlabel="Hour of day",
    )
    captions["q2_hour_weekday_crashes"] = plots.caption(
        MICRODATA_SOURCE, "2016–2024 pooled", "count of injury crashes", n_crashes
    )
    fatal_matrix = grid.pivot(index="weekday_label", columns="hour", values="fatal_share")
    fatal_matrix = fatal_matrix.reindex(index=list(labels.WEEKDAYS.values()))
    plots.heatmap(
        fatal_matrix,
        figures_dir / "q2_hour_weekday_fatal_share.svg",
        "Share of crashes with at least one death, by weekday and hour",
        percent=True,
        annotate=False,
        height=3.2,
        xlabel="Hour of day",
    )
    captions["q2_hour_weekday_fatal_share"] = plots.caption(
        MICRODATA_SOURCE,
        "2016–2024 pooled",
        "fatal crashes (30 days) divided by all injury crashes",
        n_crashes,
    )

    night = summaries.night_share_by_year_zone()
    night["zone"] = _zone_label(night.zone)
    plots.line_series(
        night,
        "year",
        "night_death_share",
        figures_dir / "q2_night_share.svg",
        "Share of road deaths that occur in darkness",
        series="zone",
        ylabel="Share of deaths",
        percent=True,
    )
    captions["q2_night_share"] = plots.caption(
        MICRODATA_SOURCE,
        "2016–2024",
        "darkness = lighting codes 4–6 (no daylight, with or without street lighting); 30-day deaths",
        n_crashes,
    )

    bands = summaries.hour_band_by_road_group()
    band_matrix = bands.pivot(
        index="road_group_label", columns="hour_band_label", values="fatal_share"
    )
    band_matrix = band_matrix.reindex(
        index=list(labels.ROAD_GROUPS.values()), columns=list(labels.HOUR_BANDS.values())
    )
    plots.heatmap(
        band_matrix,
        figures_dir / "q2_hour_band_road_group.svg",
        "Share of crashes with at least one death, by road type and time of day",
        percent=True,
        height=3.4,
        xlabel="Time of day",
    )
    captions["q2_hour_band_road_group"] = plots.caption(
        MICRODATA_SOURCE,
        "2016–2024 pooled",
        "fatal crashes (30 days) divided by all injury crashes",
        n_crashes,
    )

    # ------------------------------------------------------------------ Q5 road users
    users = summaries.deaths_by_road_user()
    users["group"] = users.road_user.map(ROAD_USER_FOLD)
    folded = users.groupby(["year", "group"], observed=True).deaths_30d.sum().reset_index()
    plots.bar_shares(
        folded,
        "year",
        "group",
        "deaths_30d",
        figures_dir / "q5_road_user_shares.svg",
        "Road deaths by type of road user",
        order=ROAD_USER_ORDER,
    )
    captions["q5_road_user_shares"] = plots.caption(
        MICRODATA_SOURCE,
        "2016–2024, all roads",
        "30-day deaths by the vehicle the person was using; trucks, buses, other and unspecified folded together",
        n_crashes,
    )

    drivers = summaries.driver_deaths_series()
    plots.small_multiples(
        drivers,
        "vehicle_type_label",
        "year",
        "deaths_30d",
        figures_dir / "q5_driver_deaths.svg",
        "Driver deaths by vehicle type",
        ncols=3,
    )
    captions["q5_driver_deaths"] = plots.caption(
        SERIES_SOURCE,
        "1993–2024, all roads",
        "drivers only, 30-day deaths; PMV series starts in 2020",
    )

    pedestrians = summaries.pedestrian_series()
    pedestrians = pedestrians[pedestrians.zone != "all"].copy()
    pedestrians["zone"] = _zone_label(pedestrians.zone)
    plots.line_series(
        pedestrians,
        "year",
        "deaths_30d",
        figures_dir / "q5_pedestrian_deaths.svg",
        "Pedestrian deaths by zone",
        series="zone",
        ylabel="Deaths (30 days)",
    )
    captions["q5_pedestrian_deaths"] = plots.caption(SERIES_SOURCE, "1993–2024", THIRTY_DAY)

    # ------------------------------------------------------------------ data quality
    profile = pd.read_csv(TABLES_DIR / "missingness_by_year.csv")
    plots.missingness_heatmap(
        profile,
        figures_dir / "data_missingness.svg",
        "Share of crashes with an observed value, by field and year",
    )
    captions["data_missingness"] = plots.caption(
        MICRODATA_SOURCE,
        "2016–2024",
        "observed = not empty, not 999 (not specified), not 998 (not applicable) and not an explicit unknown code",
        n_crashes,
    )

    with (figures_dir / CAPTIONS_PATH.name).open("w", encoding="utf-8") as handle:
        json.dump(captions, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return captions
