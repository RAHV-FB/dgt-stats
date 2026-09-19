"""Figure recipes: which summary feeds which chart, with the caption each figure carries."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from dgt_stats import agebands, labels, plots, summaries, vehicles
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR

CAPTIONS_PATH = FIGURES_DIR / "captions.json"
log = logging.getLogger(__name__)

SERIES_SOURCE = "DGT, Series históricas del Anuario de Accidentes 2024"
MICRODATA_SOURCE = "DGT, Ficheros de microdatos de accidentes con víctimas 2016–2024"
TABLES_SOURCE = "DGT, Accidentes con víctimas, tablas estadísticas 2014–2024"
INE_SOURCE = "INE, Estadística Continua de Población"
CENSUS_SOURCE = "DGT, Censo de conductores 2014–2025"
ACTIVITY_SOURCE = "ESRA 2018 and 2023 (Spain), MOVILIA 2006"
KM_SOURCE = "DGT, Kilómetros recorridos estimados a partir de la ITV 2022"
RATE_PANELS = {
    "injury_involvement": "In injury crashes",
    "fatal_involvement": "In fatal crashes",
    "occupant_deaths": "Occupants killed",
}
THIRTY_DAY = "deaths within 30 days of the crash"

LADDER_LABELS = {
    "residents": "per resident",
    "licence_holders": "per licence holder",
    "travel_weighted": "per travel-weighted driver",
    "drivers_involved": "per driver involved in a crash",
}

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


def build_all(
    figures_dir: Path = FIGURES_DIR, frames: dict[str, pd.DataFrame] | None = None
) -> dict[str, str]:
    """Write every figure as SVG and return ``{figure name: caption}``; also saves captions.json.

    ``frames`` are the summaries by registry name; when omitted they are computed here.
    """
    frames = frames if frames is not None else {}

    def summary(name: str) -> pd.DataFrame:
        if name not in frames:
            frames[name] = summaries.SUMMARIES[name]()
        return frames[name].copy()

    figures_dir.mkdir(parents=True, exist_ok=True)
    captions: dict[str, str] = {}
    grid = summary("q2_hour_weekday")
    n_crashes = int(grid.crashes.sum())

    # ------------------------------------------------------------------ Q1 trends
    headline = summary("q1_annual_headline")
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

    rates = summary("q1_annual_rates").melt(id_vars="year", var_name="metric", value_name="value")
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

    monthly = summary("q1_monthly_deaths")
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

    by_zone = summary("q1_annual_by_zone")
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

    night = summary("q2_night_share")
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

    bands = summary("q2_hour_band_road_group")
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
    users = summary("q5_deaths_by_road_user")
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
        "30-day deaths by the vehicle the person was using; trucks, buses, other and unspecified folded together; personal mobility vehicles counted separately only from 2020",
        n_crashes,
    )

    drivers = summary("q5_driver_deaths_series")
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

    pedestrians = summary("q5_pedestrian_series")
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

    # ------------------------------------------------------------------ Q4 geography
    provinces = summary("q4_province_rates")
    latest_year = int(provinces.year.iloc[0])
    national = provinces[provinces.is_total].iloc[0]
    plots.dot_interval(
        provinces[~provinces.is_total],
        "province",
        "deaths_per_100k",
        "deaths_per_100k_low",
        "deaths_per_100k_high",
        figures_dir / "q4_province_deaths.svg",
        f"Road deaths per 100,000 residents by province, {latest_year}",
        xlabel="Deaths per 100,000 residents (95% interval)",
        reference=float(national.deaths_per_100k),
        reference_label=f"Spain {national.deaths_per_100k:.1f}",
    )
    captions["q4_province_deaths"] = plots.caption(
        f"{TABLES_SOURCE}; {INE_SOURCE}",
        str(latest_year),
        "30-day deaths in the province where the crash happened, divided by residents on 1 July; "
        "exact Poisson 95% intervals, wide where deaths are few",
        int(national.deaths_30d),
    )

    national_rates = summary("q4_national_rates")
    rate_long = national_rates.melt(
        id_vars="year",
        value_vars=["deaths_per_100k_residents", "deaths_per_100k_licence"],
        var_name="denominator",
        value_name="rate",
    ).dropna(subset=["rate"])
    rate_long["denominator"] = rate_long.denominator.map(
        {
            "deaths_per_100k_residents": "per 100,000 residents",
            "deaths_per_100k_licence": "per 100,000 licence holders",
        }
    )
    plots.line_series(
        rate_long,
        "year",
        "rate",
        figures_dir / "q4_national_rates.svg",
        "Road deaths per 100,000 residents and per 100,000 licence holders",
        series="denominator",
        ylabel="Deaths per 100,000",
    )
    captions["q4_national_rates"] = plots.caption(
        f"{SERIES_SOURCE}; {INE_SOURCE}; {CENSUS_SOURCE}",
        "2002–2024 (residents), 2014–2024 (licence holders)",
        "30-day deaths of all road users; residents on 1 July; licence holders at the census date",
    )

    # ------------------------------------------------------------------ Q7 older drivers
    ratio = summary("q7_ladder_ratio")
    ratio_65 = ratio[ratio.band == "65+"].copy()
    ratio_65 = ratio_65[ratio_65.denominator.isin(LADDER_LABELS)]
    ratio_65["denominator"] = ratio_65.denominator.map(LADDER_LABELS)
    plots.line_series(
        ratio_65,
        "year",
        "ratio",
        figures_dir / "q7_ladder_ratio.svg",
        "Driver death rate, 65 and over relative to 35–64, under each denominator",
        series="denominator",
        ylabel="Rate ratio (35–64 = 1)",
        reference=1.0,
        band=("ratio_low", "ratio_high"),
        end_labels=False,
        height=4.8,
    )
    captions["q7_ladder_ratio"] = plots.caption(
        f"{TABLES_SOURCE}; {INE_SOURCE}; {CENSUS_SOURCE}; {ACTIVITY_SOURCE}",
        "2014–2024",
        "driver deaths (30 days) per unit of each denominator, 65+ divided by 35–64; shaded bands "
        "are 95% intervals from the death counts; drivers with unknown age excluded",
    )

    ladder = summary("q7_driver_ladder")
    ladder["band_label"] = ladder.band.map(agebands.band_label)
    latest = ladder[ladder.year == ladder.year.max()]
    shares = latest.melt(
        id_vars="band_label",
        value_vars=["licence_share", "travel_share"],
        var_name="measure",
        value_name="share",
    )
    shares["measure"] = shares.measure.map(
        {"licence_share": "Hold a licence", "travel_share": "Travel-weighted driver share"}
    )
    plots.grouped_bars(
        shares,
        "band_label",
        "measure",
        "share",
        figures_dir / "q7_licence_travel_share.svg",
        f"Share of residents with a licence and travel-weighted driver share, {int(latest.year.iloc[0])}",
        order=[agebands.band_label(b) for b in agebands.ANALYSIS_BANDS],
        percent=True,
        ylabel="Share of residents",
    )
    captions["q7_licence_travel_share"] = plots.caption(
        f"{CENSUS_SOURCE}; {INE_SOURCE}; {ACTIVITY_SOURCE}",
        str(int(latest.year.iloc[0])),
        "licence holders divided by residents; travel-weighted share = ESRA national share of "
        "adults who drive spread by the MOVILIA 2006 car-travel profile, capped at the licence share",
    )

    rate_long = ladder.melt(
        id_vars=["year", "band_label"],
        value_vars=["deaths_per_100k_licence", "deaths_per_100k_travel"],
        var_name="denominator",
        value_name="rate",
    )
    rate_long["denominator"] = rate_long.denominator.map(
        {
            "deaths_per_100k_licence": "per 100,000 licence holders",
            "deaths_per_100k_travel": "per 100,000 travel-weighted drivers",
        }
    )
    plots.small_multiples(
        rate_long,
        "band_label",
        "year",
        "rate",
        figures_dir / "q7_death_rates_by_band.svg",
        "Driver deaths per 100,000, by age band and denominator",
        ncols=4,
        order=[agebands.band_label(b) for b in agebands.ANALYSIS_BANDS],
        series="denominator",
        shared_y=True,
    )
    captions["q7_death_rates_by_band"] = plots.caption(
        f"{TABLES_SOURCE}; {CENSUS_SOURCE}; {ACTIVITY_SOURCE}",
        "2014–2024",
        "driver deaths within 30 days (interurban and urban) divided by licence holders and by "
        "travel-weighted drivers of the same age band; same scale on every panel",
    )

    decomposition = ladder.melt(
        id_vars=["year", "band_label"],
        value_vars=["involved_per_10k_licence", "deaths_per_1k_involved"],
        var_name="measure",
        value_name="value",
    )
    decomposition["measure"] = decomposition.measure.map(
        {
            "involved_per_10k_licence": "Drivers involved per 10,000 licence holders",
            "deaths_per_1k_involved": "Driver deaths per 1,000 drivers involved",
        }
    )
    plots.small_multiples(
        decomposition,
        "measure",
        "year",
        "value",
        figures_dir / "q7_involvement_fragility.svg",
        "Crash involvement and fatality given involvement, by age band",
        ncols=2,
        series="band_label",
        series_order=[agebands.band_label(b) for b in agebands.ANALYSIS_BANDS],
    )
    captions["q7_involvement_fragility"] = plots.caption(
        f"{TABLES_SOURCE}; {CENSUS_SOURCE}",
        "2014–2024",
        "left: drivers involved in injury crashes per 10,000 licence holders of the band; right: "
        "driver deaths per 1,000 drivers involved (fragility and crash severity)",
    )

    victims = summary("q7_victims_by_age")
    victims["band_label"] = victims.band.map(agebands.band_label)
    plots.line_series(
        victims,
        "year",
        "deaths_per_million",
        figures_dir / "q7_victims_by_age.svg",
        "Road deaths per million residents by age band, all road users",
        series="band_label",
        ylabel="Deaths per million residents",
        end_labels=False,
    )
    captions["q7_victims_by_age"] = plots.caption(
        f"{SERIES_SOURCE}; {INE_SOURCE}",
        "2002–2024",
        "all road users killed within 30 days, by age band, divided by residents on 1 July",
    )

    # ------------------------------------------------------------------ Q6 vehicles per km
    _vehicle_figures(figures_dir, captions, summary)

    # ------------------------------------------------------------------ Q3 severity models
    if summaries.model_tables_present():
        _severity_figures(figures_dir, captions)
    else:
        log.warning("model tables missing: run scripts/model.py to get the severity figures")

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


def _vehicle_figures(figures_dir: Path, captions: dict[str, str], summary) -> None:
    rates = summary("q6_rates_2022")
    rates = rates[rates.zone == "all"]
    fatal = rates[rates.measure == "fatal_involvement"].sort_values(
        "per_billion_km", ascending=False
    )
    order = list(fatal.label)
    rates["panel"] = rates.measure.map(RATE_PANELS)
    plots.dot_interval_panels(
        rates,
        "panel",
        "label",
        "per_billion_km",
        "per_billion_km_low",
        "per_billion_km_high",
        figures_dir / "q6_rates_per_km.svg",
        "Vehicles per billion kilometres driven, 2022",
        order=order,
        panel_order=list(RATE_PANELS.values()),
        xlabel="per billion km",
    )
    captions["q6_rates_per_km"] = plots.caption(
        f"{TABLES_SOURCE}; {KM_SOURCE}",
        "2022",
        "vehicles of each type involved in injury crashes and in 30-day fatal crashes, and their "
        "drivers and passengers killed within 30 days, divided by the type's estimated "
        "vehicle-kilometres (registered fleet × mean annual km from ITV odometer readings); "
        "whiskers are exact 95% Poisson intervals; rows ordered by fatal-crash involvement",
        f"{int(rates[rates.measure == 'injury_involvement']['count'].sum()):,} vehicles involved",
    )

    table = summary("q6_summary_2022")
    plots.slope(
        table,
        "label",
        "fatal_involvement_per_100k_vehicles",
        "fatal_involvement_per_bn_km",
        figures_dir / "q6_per_vehicle_vs_per_km.svg",
        "Vehicles in fatal crashes: ranking per registered vehicle and per kilometre, 2022",
        "per 100,000 vehicles",
        "per billion km",
    )
    captions["q6_per_vehicle_vs_per_km"] = plots.caption(
        f"{TABLES_SOURCE}; {KM_SOURCE}",
        "2022",
        "vehicles of each type involved in 30-day fatal crashes per 100,000 registered vehicles "
        "(left) and per billion vehicle-km (right); the lines show how each type's rank moves when "
        "distance driven replaces fleet size as the denominator",
    )

    by_age = summary("q6_km_by_age_2022")
    matrix = by_age.pivot(index="label", columns="age_band", values="mean_km_year")
    matrix = matrix.reindex(index=[vehicles.label(g) for g in vehicles.KM_GROUPS])
    matrix = matrix.reindex(columns=list(vehicles.AGE_BANDS.values()))
    plots.heatmap(
        matrix,
        figures_dir / "q6_km_by_age.svg",
        "Mean annual kilometres per vehicle by type and vehicle age, 2022",
        value_format="{:,.0f}",
        xlabel="Vehicle age",
    )
    captions["q6_km_by_age"] = plots.caption(
        KM_SOURCE,
        "2022",
        "mean annual km per vehicle, modelled from annualised ITV odometer readings and imputed "
        "to the registered fleet; valid for aggregates, not for individual vehicles",
        f"{int(by_age.n_vehicles.sum()):,} vehicles",
    )

    series = summary("q6_occupant_deaths_series")
    order = [
        vehicles.label(g)
        for g in (
            "car",
            "motorcycle",
            vehicles.MERGED_GROUP,
            "heavy_truck",
            "bus",
            "moped",
            "bicycle",
            "vmp",
            "other",
        )
    ]
    plots.small_multiples(
        series,
        "label",
        "year",
        "deaths_30d",
        figures_dir / "q6_occupant_deaths.svg",
        "Drivers and passengers killed by vehicle type, 1993–2024",
        ncols=3,
        order=order,
    )
    captions["q6_occupant_deaths"] = plots.caption(
        SERIES_SOURCE,
        "1993–2024, all roads",
        f"{THIRTY_DAY}, drivers and passengers of each vehicle type; panels have their own scales; "
        "personal mobility vehicles are counted from 2020",
    )


def _severity_figures(figures_dir: Path, captions: dict[str, str]) -> None:
    coefficients = summaries.read_model_table("q3_model_coefficients")
    n_model = int(coefficients.n.iloc[0])
    for outcome, title in (
        ("fatal", "at least one death"),
        ("serious", "death or hospitalisation"),
    ):
        table = coefficients[(coefficients.outcome == outcome) & (coefficients.predictor != "year")]
        plots.forest(
            table,
            "predictor_label",
            "level",
            "odds_ratio",
            "or_low",
            "or_high",
            figures_dir / f"q3_forest_{outcome}.svg",
            f"Odds of {title}, by crash circumstance",
            reference_flag="is_reference",
        )
        captions[f"q3_forest_{outcome}"] = plots.caption(
            MICRODATA_SOURCE,
            "2016–2024",
            f"logistic regression of {title} on the circumstances shown plus year; odds ratios "
            "against the reference level (hollow marker) with 95% intervals clustered by province",
            n_model,
        )

    cal = summaries.read_model_table("q3_calibration")
    cal["outcome"] = cal.outcome.map({"fatal": "Fatal", "serious": "Serious"})
    plots.calibration(
        cal,
        "predicted",
        "observed",
        figures_dir / "q3_calibration.svg",
        "Predicted against observed severity, crashes of 2023–2024 scored by a 2016–2022 fit",
        series="outcome",
    )
    captions["q3_calibration"] = plots.caption(
        MICRODATA_SOURCE,
        "fitted on 2016–2022, scored on 2023–2024",
        "crashes grouped into ten equal bands of predicted probability; the dotted line is perfect "
        "calibration",
        int(cal[cal.outcome == "Fatal"].crashes.sum()),
    )

    stability = summaries.read_model_table("q3_year_stability")
    stability = stability[stability.outcome == "fatal"].copy()
    stability["term"] = stability.level.str.capitalize()
    pairs = stability[["term", "predictor"]].drop_duplicates()
    duplicated = set(pairs[pairs.term.duplicated(keep=False)].term)
    stability.loc[stability.term.isin(duplicated), "term"] = (
        stability.term + " (" + stability.predictor_label.str.lower() + ")"
    )
    plots.small_multiples(
        stability,
        "term",
        "year",
        "odds_ratio",
        figures_dir / "q3_year_stability.svg",
        "Odds ratios for a fatal outcome, refitted year by year",
        ncols=3,
        band=("or_low", "or_high"),
    )
    captions["q3_year_stability"] = plots.caption(
        MICRODATA_SOURCE,
        "2016–2024, one fit per year",
        "the ten largest effects of the full fatal-outcome model, each refitted on one year of "
        "crashes; shaded bands are 95% intervals",
    )

    grid = summaries.read_model_table("q3_predicted_grid")
    matrix = grid.pivot(index="road", columns="lighting", values="probability")
    matrix = matrix.reindex(
        index=[
            r
            for r in [
                "urban street",
                "conventional",
                "dual carriageway",
                "motorway",
                "other road",
                "not specified",
            ]
            if r in matrix.index
        ],
        columns=[
            c
            for c in [
                "daylight",
                "dusk or dawn",
                "dark, street lighting",
                "dark, no lighting",
                "not specified",
            ]
            if c in matrix.columns
        ],
    )
    plots.heatmap(
        matrix,
        figures_dir / "q3_predicted_grid.svg",
        "Predicted probability that a crash is fatal, by road type and lighting",
        percent=True,
        height=3.4,
        xlabel="Lighting",
    )
    captions["q3_predicted_grid"] = plots.caption(
        MICRODATA_SOURCE,
        "model of 2016–2024, predictions for 2024",
        "every other circumstance at its reference level (side collision, two vehicles, not at a "
        "junction, clear, dry, weekday, 10:00–13:59; interurban zone for interurban road types)",
    )
