"""The map of the project: its sections, its sources, and where every result table comes from.

Everything the study publishes is organised in five sections, and the same five names are used for
the code (``src/dgt_stats/<section>``), the pipeline stages (``scripts/run.py <section>``), the
result tables (``reports/tables/<section>``), the documents (``docs/<section>``) and the site's
navigation:

``national``  Spain's official statistics: DGT, INE, the Ministerio de Transportes and CORES
``drivers``   drivers by age and sex, with the travel surveys that measure how far each age drives
``regional``  the police crash records of Catalonia and of Barcelona
``models``    the crash-severity models trained on those records, and their tests elsewhere
``sources``   what every raw file holds and how each source came to exist

:data:`SOURCES` lists every source: the files it owns under ``data/raw`` (each raw file belongs to
exactly one source) or, for the figures typed from documents that are not archived, none. :data:`TABLES` lists every result table: the stage that writes it, and so its section and
folder, the sources it is computed from, and what it holds. ``tests/test_catalogue.py`` keeps the
three in step with the files: a table on disk that is not catalogued, a catalogued table that is
not on disk, a raw file no source owns and a source no table reads all fail the tests, and a table
cannot be written or read under a name the catalogue does not know (:func:`dgt_stats.paths.table_path`).
``python scripts/run.py sources.catalogue`` writes the catalogue out as ``docs/catalogue.md`` and
one ``README.md`` per table folder.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    # the label of the section's group in the site's navigation
    short: str
    question: str
    # site pages, in reading order; the interactive tools are listed under Explore as well
    pages: tuple[str, ...]


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    publisher: str
    coverage: str
    # what one record of the source is, or what it publishes
    record: str
    # glob patterns relative to data/raw; empty for figures typed from a document
    files: tuple[str, ...]
    # False for files kept as a record and read by no analysis
    read: bool = True
    note: str = ""


@dataclass(frozen=True)
class Table:
    name: str
    stage: str
    description: str
    sources: tuple[str, ...]

    @property
    def section(self) -> str:
        return self.stage.split(".")[0]


SECTIONS: tuple[Section, ...] = (
    Section(
        "national",
        "Spain: national statistics",
        "National statistics",
        "How road deaths and injuries in Spain have changed since 1993, and how they differ "
        "between vehicles, roads, months and the circumstances the police record, once each count "
        "is set against residents, licence holders, vehicles, road fuel or kilometres.",
        (
            "long-run",
            "trends",
            "seasons",
            "policy",
            "vehicles",
            "speed",
            "factors",
            "severity",
            "trends-explorer",
            "crash-explorer",
        ),
    ),
    Section(
        "drivers",
        "Drivers: risk by age and sex",
        "Drivers",
        "How often drivers of each age and sex are involved in injury crashes per licence holder "
        "and per kilometre driven, and how often a crash kills them. No national source measures "
        "kilometres by age, so travel surveys put them on ages.",
        ("drivers", "driver-risk"),
    ),
    Section(
        "regional",
        "Catalonia and Barcelona: crash records",
        "Catalonia and Barcelona",
        "What police crash records with more detail than the national file show: Catalonia's "
        "crashes with a death or serious injury (2010–2023) and every crash Barcelona's police "
        "attended in 2025, with its people.",
        ("catalonia", "barcelona"),
    ),
    Section(
        "models",
        "Crash-severity models and their tests",
        "Severity model",
        "Which severe crashes in Catalonia were fatal, as a model that is kept only if it beats a "
        "descriptive table on later records, and how far it and the other models hold in other "
        "years, places and recording sources.",
        ("severity-models", "validation", "calculator"),
    ),
    Section(
        "sources",
        "Data and methods: sources and how results are made",
        "Data and methods",
        "What every raw file holds, how each source came to exist, and how the results are made "
        "from them.",
        ("sources", "data"),
    ),
)
SECTION_BY_KEY = {section.key: section for section in SECTIONS}


SOURCES: tuple[Source, ...] = (
    # ---- national statistics
    Source(
        "dgt_microdata",
        "DGT crash microdata",
        "Dirección General de Tráfico (DGT)",
        "Spain, 2016–2024",
        "one police-recorded crash with at least one victim; no person or vehicle records",
        ("dgt/microdata/*",),
    ),
    Source(
        "dgt_series",
        "DGT yearbook historical series",
        "DGT",
        "Spain and its provinces, 1993–2024",
        "annual, monthly and provincial totals of crashes and casualties",
        ("dgt/tables/series_historicas_*.xlsx",),
    ),
    Source(
        "dgt_tables",
        "DGT statistical tables",
        "DGT",
        "Spain, 2014–2024",
        "yearly tables of crashes, vehicles and road users by age, sex, vehicle and infraction",
        ("dgt/tables/tablas_estadisticas_*.xlsx", "dgt/tables/chapters/*/*"),
    ),
    Source(
        "dgt_census",
        "DGT driver census",
        "DGT",
        "Spain by province, 2014–2025",
        "licence holders by province, sex, age band and licence class",
        ("dgt/census/*",),
        note="censo_tablas_2024.xlsx keeps the yearly series complete and is not read",
    ),
    Source(
        "dgt_km",
        "DGT kilometre estimates",
        "DGT",
        "Spain, 2022 and 2024",
        "fleet and mean annual kilometres by vehicle type and owner age, from inspection "
        "odometer readings",
        ("dgt/km_itv_2022/*", "dgt/km_itv_2024/*"),
    ),
    Source(
        "dgt_speed_report",
        "DGT speed-factor report",
        "DGT",
        "Spain without Catalonia and the Basque Country, 2014–2023",
        "injury crashes with each police-recorded concurrent factor, and deaths in those with "
        "speed",
        ("dgt/reports/dgt_factor_velocidad_2023.pdf",),
    ),
    Source(
        "ine_population",
        "INE resident population",
        "Instituto Nacional de Estadística (INE)",
        "Spain and its provinces, 2002–2025",
        "residents by province, five-year age group and sex, and of Spain by single year of age",
        ("ine/ine_poblacion_*.csv",),
    ),
    Source(
        "cores_fuel",
        "CORES road fuel",
        "Corporación de Reservas Estratégicas de Productos Petrolíferos (CORES)",
        "Spain, monthly",
        "tonnes of automotive petrol and diesel sold, biofuels included",
        ("cores/*",),
    ),
    Source(
        "transport_toll",
        "Toll-motorway traffic",
        "Ministerio de Transportes",
        "state toll motorways, monthly from 1990",
        "average daily traffic and vehicle-kilometres on the toll network",
        ("transportes/peaje_trafico_total.xls",),
    ),
    Source(
        "transport_road_km",
        "Interurban vehicle-kilometres",
        "Ministerio de Transportes",
        "state, regional and provincial road networks, 2004–2023",
        "vehicle-kilometres by road type, from the roads chapter of the Ministry's yearbook",
        ("transportes/anuario_carreteras_*.pdf",),
    ),
    # ---- travel surveys and other exposure by age
    Source(
        "emef",
        "EMEF working-day mobility survey",
        "Autoritat del Transport Metropolità (ATM), Idescat and Institut Metròpoli",
        "Barcelona area, working days, 2014–2024",
        "public-use microdata: one row per respondent aged 16 and over and per trip",
        ("emef/*/*",),
    ),
    Source(
        "emef_distance_2021",
        "EMEF 2021 distance report",
        "Institut Metròpoli for the ATM",
        "Barcelona area, 2021",
        "the road-to-straight-line distance ratio of driving trips (1.45) and the 2021 distance "
        "benchmarks, typed into src/dgt_stats/drivers/emef/distance.py",
        (),
        note="the report is not archived here and could not be found again",
    ),
    Source(
        "emef_technical",
        "EMEF technical document",
        "Autoritat del Transport Metropolità (ATM)",
        "Barcelona area, 2014–2024",
        "each year's population aged 16 and over and final sample, typed into "
        "src/dgt_stats/drivers/emef/variables.py as the totals the respondent files must match",
        (),
        note="a check target only, entering no estimate; the document is not archived here",
    ),
    Source(
        "edm2018",
        "Madrid household travel survey (EDM2018)",
        "Consorcio Regional de Transportes de Madrid (CRTM)",
        "Comunidad de Madrid, Monday to Thursday, 2018",
        "public microdata: respondents with exact age and sex, and their car-driver trips",
        ("crtm/edm2018/*",),
    ),
    Source(
        "movilia",
        "Mobility survey of Spain (MOVILIA)",
        "Ministerio de Transportes",
        "Spain, 2006 and 2007",
        "published tables of trips by age, main mode and type of day, and long car journeys",
        ("transportes/movilia_*.xls",),
    ),
    Source(
        "idescat_census",
        "Population census, relation with economic activity",
        "Idescat",
        "Catalonia, 1 January 2024",
        "employed residents aged 65 and over",
        ("idescat/*",),
    ),
    Source(
        "racc_2013",
        "Survey of older licence holders (Mayores al volante)",
        "Fundació RACC",
        "Spain, licence holders aged 65 and over, published 2013",
        "shares who do not drive and days a week the others drive, typed into "
        "src/dgt_stats/drivers/exposure_risk/national.py",
        (),
        note="quoted, not redistributed: RACC grants no reuse licence",
    ),
    # ---- regional crash records
    Source(
        "sct_catalonia",
        "Catalan crash records",
        "Servei Català de Trànsit",
        "Catalonia, 2010–2023",
        "one crash with at least one death or serious injury; no crash identifier",
        ("catalonia/*",),
    ),
    Source(
        "gu_barcelona",
        "Barcelona crash records",
        "Ajuntament de Barcelona, Guàrdia Urbana",
        "Barcelona city, 2025",
        "six tables sharing a case number: crashes, crash types, people, vehicles, mediate "
        "causes and driver causes",
        ("barcelona/*/*",),
    ),
    # ---- kept as a record, read by no analysis
    Source(
        "dgt_reports",
        "DGT thematic reports and yearbook errata",
        "DGT",
        "various",
        "the errata to the 2015–2019 yearbooks, consulted by hand during reconciliation; the "
        "report on road users aged 65 and over; provisional Easter 2026 figures",
        ("dgt/reports/Anuario-*", "dgt/reports/dgt_personas_mayores_*", "dgt/reports/dgt_semana_*"),
        read=False,
    ),
    Source(
        "ine_surveys",
        "INE ECEPOV 2021 and EHMA 2008 tables",
        "INE",
        "Spain",
        "commuters by vehicle, sex and age; kilometres per household vehicle by the household's "
        "age; checked as denominators and not used",
        ("ine/ine_ecepov_*", "ine/ine_ehma_*"),
        read=False,
    ),
    Source(
        "movilia_madrid",
        "MOVILIA extract for Madrid",
        "Comunidad de Madrid",
        "Comunidad de Madrid, 2006",
        "checked as a source of driving by age and not used: it gives no driver status by age",
        ("comunidad_madrid/*/*",),
        read=False,
    ),
    Source(
        "compiled_registers",
        "Registers typed from publications",
        "this project",
        "various",
        "values from external studies used by analyses that were withdrawn for relying on "
        "them; kept as the record, never read",
        ("compiled/*", "compiled/*/*"),
        read=False,
    ),
)
SOURCE_BY_KEY = {source.key: source for source in SOURCES}


def source_of_file(relative: str) -> Source:
    """The one source that owns a file, by its path relative to ``data/raw``."""
    owners = [
        source for source in SOURCES if any(fnmatch(relative, pattern) for pattern in source.files)
    ]
    if len(owners) != 1:
        raise KeyError(f"{relative}: owned by {[s.key for s in owners] or 'no source'}")
    return owners[0]


def table(name: str) -> Table:
    """A result table's catalogue entry; a clear error for a name the catalogue does not know."""
    try:
        return TABLE_BY_NAME[name]
    except KeyError:
        raise KeyError(
            f"{name!r} is not a catalogued result table: add it to TABLES in src/dgt_stats/catalogue.py"
        ) from None


def tables_reading(source: str) -> list[Table]:
    return [entry for entry in TABLES if source in entry.sources]


def sources_of(names) -> list[Source]:
    """The sources a set of tables is computed from, in the order of :data:`SOURCES`."""
    keys = {key for name in names for key in table(name).sources}
    return [source for source in SOURCES if source.key in keys]


# Every result table: its name, the stage that writes it (and so its section and folder), what it
# holds and the sources it is computed from. Grouped by stage, in pipeline order. A table with no
# source is written from definitions in the code; the raw-file inventory reads every file.
FILE_SOURCES = tuple(source.key for source in SOURCES if source.files)
TABLES: tuple[Table, ...] = (
    # national.reconcile
    Table(
        "missingness_by_year",
        "national.reconcile",
        "Share of empty, unspecified, not-applicable and unknown values per crash field and year, 2016–2024",
        ("dgt_microdata",),
    ),
    Table(
        "reconciliation",
        "national.reconcile",
        "Checks of the staged sources against DGT's published totals: expected, actual and pass per check",
        ("dgt_microdata", "dgt_series", "dgt_tables", "dgt_census", "dgt_speed_report"),
    ),
    # national.associations
    Table(
        "assoc_adverse_composition",
        "national.associations",
        "Where DGT injury crashes in hail, snow or rain happen: province, zone and road-type shares",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_adverse_conditions",
        "national.associations",
        "Weather, road-surface and junction odds ratios refitted under alternative model variants",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_adverse_exclusions",
        "national.associations",
        "Hail or snow odds ratio refitted with its most concentrated provinces left out, DGT crashes",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_calibration",
        "national.associations",
        "Predicted against observed fatal and serious shares by risk decile, held-out 2023–2024 crashes",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_groupings",
        "national.associations",
        "Each DGT record code and the predictor level it is grouped into in the crash association analysis",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_holdout_summary",
        "national.associations",
        "Associations fitted on 2016–2022 DGT crashes and scored on 2023–2024: Brier score and AUC",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_junction_coding",
        "national.associations",
        "Junction flag per year in Catalonia and the rest of Spain, as published and as corrected",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_junction_sensitivity",
        "national.associations",
        "Junction odds ratio under each way of reading the inverted Catalan junction flag, DGT crashes",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_location_contrasts",
        "national.associations",
        "Odds of a fatal or serious outcome by zone and road type against urban streets, DGT crashes",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_marginal_effects",
        "national.associations",
        "Average change in the chance of a fatal or serious outcome per crash characteristic, DGT crashes",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_model_coefficients",
        "national.associations",
        "Odds ratios of a fatal or serious outcome per crash characteristic, DGT injury crashes 2016–2024",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_period_refits",
        "national.associations",
        "Junction, surface, weather and crash-type odds ratios refitted on 2016–2022 and on 2023–2024",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_profiles",
        "national.associations",
        "Predicted chance of a fatal or serious outcome for six example crash profiles in 2024",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_recording_regime",
        "national.associations",
        "How missing-value levels of each predictor split between Catalonia and the rest of Spain",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_regime_sensitivity",
        "national.associations",
        "Every odds ratio of the DGT crash association models beside a refit without Catalonia",
        ("dgt_microdata",),
    ),
    Table(
        "assoc_year_stability",
        "national.associations",
        "Largest associations with a fatal or serious outcome refitted year by year, 2016–2024",
        ("dgt_microdata",),
    ),
    Table(
        "explore_dgt_crashes",
        "national.associations",
        "Injury crashes, fatal crashes and deaths by year, autonomous community, road type and crash type",
        ("dgt_microdata",),
    ),
    # national.results
    Table(
        "factor_changes",
        "national.results",
        "Year-to-year change in each concurrent factor's share of injury crashes, and whether it is a break",
        ("dgt_speed_report",),
    ),
    Table(
        "factor_shares",
        "national.results",
        "Injury crashes with each concurrent factor recorded and their share, by year and zone, 2014–2023",
        ("dgt_speed_report",),
    ),
    Table(
        "factor_windows",
        "national.results",
        "Runs of years without a recording break per factor and zone, with the change in share over each",
        ("dgt_speed_report",),
    ),
    Table(
        "longrun_efficiency",
        "national.results",
        "Deaths per tonne of road fuel against trend, 2020–2024, under hypothetical efficiency gains",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "longrun_fuel_bio",
        "national.results",
        "Road fuel sold and its biofuel share per year, 2007–2025",
        ("cores_fuel",),
    ),
    Table(
        "longrun_headline",
        "national.results",
        "Injury crashes, deaths, hospital admissions and other injured per year, 1993–2024, indexed to 2019",
        ("dgt_series",),
    ),
    Table(
        "longrun_km_check",
        "national.results",
        "Interurban deaths against trend per measured vehicle-km and per tonne of road fuel, 2008–2023",
        ("dgt_series", "cores_fuel", "transport_road_km"),
    ),
    Table(
        "longrun_km_coverage",
        "national.results",
        "Interurban deaths per year by road owner and the share outside the measured networks, 2016–2024",
        ("dgt_microdata", "dgt_series"),
    ),
    Table(
        "longrun_km_panel",
        "national.results",
        "Interurban deaths, measured interurban vehicle-km and road fuel per year, 2004–2023",
        ("dgt_series", "cores_fuel", "transport_road_km"),
    ),
    Table(
        "longrun_model_choice",
        "national.results",
        "Fit of 0 to 3 turning points for each long-run death trend to 2019, and which was chosen",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "longrun_projection_sensitivity",
        "national.results",
        "Deaths against trend, 2020–2024, under alternative projections of the pre-pandemic trend",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "longrun_segments",
        "national.results",
        "Turning points and annual change of each segment of the long-run death trends to 2019",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "longrun_series",
        "national.results",
        "Deaths against the pre-pandemic trend per year, 1993–2024: count, per vehicle and per fuel tonne",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "missingness_where_applicable",
        "national.results",
        "Crashes each audited field applies to and the share with a value recorded, per year, 2016–2024",
        ("dgt_microdata",),
    ),
    Table(
        "night_share",
        "national.results",
        "Share of injury crashes and of deaths in darkness, by year and zone, 2016–2024",
        ("dgt_microdata",),
    ),
    Table(
        "other_road_by_period",
        "national.results",
        "Crashes on roads coded as other, 2016–2023 against 2024 (streets recoded): street and fatal shares",
        ("dgt_microdata",),
    ),
    Table(
        "policy_points_calendar_placebo",
        "national.results",
        "Points-licence level change at July 2006 beside placebo breaks in July of other years",
        ("dgt_series",),
    ),
    Table(
        "policy_points_calibration",
        "national.results",
        "How often July placebo breaks exclude zero, and a placebo-calibrated interval for July 2006",
        ("dgt_series",),
    ),
    Table(
        "policy_points_death_definitions",
        "national.results",
        "Monthly ratio of 30-day to 24-hour deaths summarised per year, 1993–2024",
        ("dgt_series",),
    ),
    Table(
        "policy_points_fit",
        "national.results",
        "Coefficients of the main model of monthly deaths around the July 2006 points licence",
        ("dgt_series",),
    ),
    Table(
        "policy_points_forecast",
        "national.results",
        "Deaths in the 17 months after July 2006 and other Julys against a forecast from the 60 months before",
        ("dgt_series",),
    ),
    Table(
        "policy_points_placebo",
        "national.results",
        "Points-licence level change at July 2006 beside the same model with breaks at earlier months",
        ("dgt_series",),
    ),
    Table(
        "policy_points_sensitivity",
        "national.results",
        "Points-licence level and slope change under alternative trends, data, covariates and windows",
        ("dgt_series", "cores_fuel", "transport_toll"),
    ),
    Table(
        "policy_points_series",
        "national.results",
        "Monthly deaths around the 2006 points licence, 2000–2007, with fitted and counterfactual values",
        ("dgt_series",),
    ),
    Table(
        "policy_points_transitions",
        "national.results",
        "Summer month-to-month changes in deaths per year and the 12-month change across July, 1993–2024",
        ("dgt_series",),
    ),
    Table(
        "policy_points_trend_choice",
        "national.results",
        "Candidate pre-2006 trend shapes for the points-licence model, compared by fit",
        ("dgt_series",),
    ),
    Table(
        "policy_speed_placebo",
        "national.results",
        "Conventional-road against motorway death change at the 2019 90 km/h limit and at placebo dates",
        ("dgt_microdata",),
    ),
    Table(
        "policy_speed_sensitivity",
        "national.results",
        "Variants of the 2019 90 km/h limit comparison; not estimates, as the design fails its placebo",
        ("dgt_microdata",),
    ),
    Table(
        "road_class_baseline",
        "national.results",
        "Mean annual injury crashes and casualties by road class, 2022–2024, with share outside km coverage",
        ("dgt_microdata",),
    ),
    Table(
        "road_class_risk",
        "national.results",
        "Deaths, admissions and injury crashes per billion vehicle-km, motorways v conventional, 2016–2023",
        ("dgt_microdata", "transport_road_km"),
    ),
    Table(
        "season_lockdown",
        "national.results",
        "Each month of 2020 against its 2017–2019 average: deaths, road fuel, petrol and toll traffic",
        ("dgt_series", "cores_fuel", "transport_toll"),
    ),
    Table(
        "season_lockdown_long",
        "national.results",
        "Changes in 2020 against 2017–2019 by month for deaths and three traffic series, long format",
        ("dgt_series", "cores_fuel", "transport_toll"),
    ),
    Table(
        "season_month_effects",
        "national.results",
        "Month effects on deaths with and without road fuel as exposure, 2014–2019 and 2022–2024",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "season_profile",
        "national.results",
        "Monthly index of deaths and traffic (year average = 100), 2014–2019 and 2022–2024",
        ("dgt_series", "cores_fuel", "transport_toll"),
    ),
    Table(
        "season_profile_long",
        "national.results",
        "Monthly indices of deaths and three traffic series in long format, 2014–2019 and 2022–2024",
        ("dgt_series", "cores_fuel", "transport_toll"),
    ),
    Table(
        "speed_infraction_shares",
        "national.results",
        "Drivers in injury crashes by recorded speed status, year and zone, 2014–2024, with shares",
        ("dgt_tables",),
    ),
    Table(
        "speed_severity",
        "national.results",
        "Deaths per 100 injury crashes with and without recorded speed, by year and road type, 2014–2023",
        ("dgt_microdata", "dgt_speed_report"),
    ),
    Table(
        "speed_severity_pooled",
        "national.results",
        "Speed-related against other deaths per crash pooled over 2016–2023 by road type, and adjusted",
        ("dgt_microdata", "dgt_speed_report"),
    ),
    Table(
        "trends_annual_panel",
        "national.results",
        "Casualties, injury crashes and denominators per year, 1993–2024: residents, licences, fleet, fuel",
        ("dgt_series", "dgt_census", "ine_population", "cores_fuel"),
    ),
    Table(
        "trends_dispersion",
        "national.results",
        "How much each annual casualty count scatters around its 2013–2019 trend beyond chance",
        ("dgt_series",),
    ),
    Table(
        "trends_frequency_severity",
        "national.results",
        "Deaths per tonne of road fuel split into crash frequency and severity, 1996–2024, 1996 = 100",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "trends_fuel_efficiency",
        "national.results",
        "Deaths and admissions per tonne of road fuel against 2019 under hypothetical efficiency gains",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "trends_km_crosscheck",
        "national.results",
        "DGT km per car 2022–2024 and vehicle-km 2022 and 2024, beside road fuel and deaths, ratios to 2022",
        ("dgt_series", "dgt_km", "cores_fuel"),
    ),
    Table(
        "trends_risk_index",
        "national.results",
        "Deaths, admissions and crashes per resident, licence, vehicle and fuel, 2019–2024, as ratios to 2019",
        ("dgt_series", "dgt_census", "ine_population", "cores_fuel"),
    ),
    Table(
        "vehicles_groups",
        "national.results",
        "Vehicle groups and the names each takes in the yearbook tables, km table, microdata and series",
        (),
    ),
    Table(
        "vehicles_km_2022",
        "national.results",
        "Fleet, vehicle-km and km per vehicle by vehicle group, 2022, with shares and a total row",
        ("dgt_km",),
    ),
    Table(
        "vehicles_rates_2022",
        "national.results",
        "Vehicles in injury and fatal crashes and occupant deaths per vehicle-km and per vehicle, 2022",
        ("dgt_tables", "dgt_km"),
    ),
    Table(
        "vehicles_summary_2022",
        "national.results",
        "One row per vehicle group, all roads, 2022: counts, rates per km and per vehicle, and ranks",
        ("dgt_tables", "dgt_km"),
    ),
    Table(
        "vehicles_van_light_truck_split",
        "national.results",
        "Vans and trucks up to 3,500 kg rated separately for 2022, the evidence for merging them",
        ("dgt_tables", "dgt_km"),
    ),
    # regional.quality
    Table(
        "bcn_quality_coordinates",
        "regional.quality",
        "Barcelona coordinates per table: swapped UTM labels, agreement across tables and offset from WGS84",
        ("gu_barcelona",),
    ),
    Table(
        "bcn_quality_count_semantics",
        "regional.quality",
        "Checks that blank Barcelona crash counts mean zero and agree with the person records",
        ("gu_barcelona",),
    ),
    Table(
        "bcn_quality_null_rates",
        "regional.quality",
        "Blank cells per column of each Barcelona source table, as a count and a share",
        ("gu_barcelona",),
    ),
    Table(
        "bcn_quality_structure",
        "regional.quality",
        "Rows, columns, crash-id coverage and rows per crash of each Barcelona source table",
        ("gu_barcelona",),
    ),
    Table(
        "bcn_vehicle_audit_counts",
        "regional.quality",
        "Barcelona vehicle-record audit: records against vehicles reported, person records and duplicates",
        ("gu_barcelona",),
    ),
    Table(
        "cat_quality_checks",
        "regional.quality",
        "Checks on the Catalan severe-crash file: dates, duplicates, count totals and severity labels",
        ("sct_catalonia",),
    ),
    Table(
        "cat_quality_placeholders",
        "regional.quality",
        "Distinct values and blank, NA and 'Sense especificar' counts per Catalan source column",
        ("sct_catalonia",),
    ),
    # regional.analyse
    Table(
        "bcn_cause_profiles",
        "regional.analyse",
        "Barcelona crashes with or without an alcohol or speed cause: time, type and severity shares",
        ("gu_barcelona",),
    ),
    Table(
        "bcn_crash_severity_share",
        "regional.analyse",
        "Serious or fatal share of Barcelona crashes by type, place, time, vehicle and cause, with intervals",
        ("gu_barcelona",),
    ),
    Table(
        "bcn_frequency",
        "regional.analyse",
        "Barcelona crash, severe-crash, death and serious-injury counts by month, hour, weekday and district",
        ("gu_barcelona",),
    ),
    Table(
        "bcn_people_by_severity",
        "regional.analyse",
        "Barcelona person records by role (driver, passenger, pedestrian) and injury severity",
        ("gu_barcelona",),
    ),
    Table(
        "bcn_person_severity_share",
        "regional.analyse",
        "Serious or fatal injury share of Barcelona people by road user, age, sex and crash, with intervals",
        ("gu_barcelona",),
    ),
    Table(
        "cat_fatal_share",
        "regional.analyse",
        "Fatal share of Catalan severe crashes by road, speed limit, vehicle, crash type and other factors",
        ("sct_catalonia",),
    ),
    Table(
        "cat_frequency",
        "regional.analyse",
        "Catalan severe crashes, fatal crashes, deaths and serious injuries by year, demarcation and zone",
        ("sct_catalonia",),
    ),
    Table(
        "cat_per_resident_province_year",
        "regional.analyse",
        "Catalan severe and fatal crashes and deaths per 100,000 residents by province and year",
        ("ine_population", "sct_catalonia"),
    ),
    Table(
        "cat_vs_dgt_province_year",
        "regional.analyse",
        "Catalan severe and fatal crash counts against DGT microdata by province and year, with ratios",
        ("dgt_microdata", "sct_catalonia"),
    ),
    # drivers.tables
    Table(
        "drivers_company_km",
        "drivers.tables",
        "Car drivers killed per billion owner-age km by age, Spain 2024, with company km left out or spread",
        ("dgt_tables", "dgt_km"),
    ),
    Table(
        "drivers_denominator_contrast",
        "drivers.tables",
        "Car drivers killed by age, ratio to 35–54 under four denominators, from residents to km, Spain 2024",
        ("dgt_tables", "dgt_census", "dgt_km", "ine_population"),
    ),
    Table(
        "drivers_km_by_owner_age",
        "drivers.tables",
        "Cars and annual km by the registered owner's age band, plus company cars, Spain 2024",
        ("dgt_km",),
    ),
    Table(
        "drivers_km_rates",
        "drivers.tables",
        "Car drivers involved and killed per billion km of cars registered to owners of that age, Spain 2024",
        ("dgt_tables", "dgt_km"),
    ),
    Table(
        "drivers_km_ratio",
        "drivers.tables",
        "Car-driver rates per owner-age km and per driver involved by age, ratio to ages 35–54, Spain 2024",
        ("dgt_tables", "dgt_km"),
    ),
    Table(
        "drivers_km_ratio_65_74",
        "drivers.tables",
        "Car-driver rates per owner-age km and per driver involved by age, ratio to ages 65–74, Spain 2024",
        ("dgt_tables", "dgt_km"),
    ),
    Table(
        "drivers_owner_age_check",
        "drivers.tables",
        "Licence holders, cars and owner-age km per holder by age band, with transfer-scenario ratios, 2024",
        ("dgt_tables", "dgt_census", "dgt_km"),
    ),
    Table(
        "drivers_sex_b_licence",
        "drivers.tables",
        "Private-car drivers 18+ killed per licence holder, men vs women, any licence vs B licence, 2023–2024",
        ("dgt_tables", "dgt_census"),
    ),
    Table(
        "drivers_sex_rates",
        "drivers.tables",
        "Drivers involved and killed per licence holder and per driver involved, by sex and age, 2022–2024",
        ("dgt_tables", "dgt_census"),
    ),
    Table(
        "drivers_sex_ratios",
        "drivers.tables",
        "Men-to-women ratios of driver crash and death rates by age band, Spain 2022–2024",
        ("dgt_tables", "dgt_census"),
    ),
    Table(
        "drivers_sex_trend",
        "drivers.tables",
        "Crash and death rates of drivers aged 18 and over, by sex, vehicle scope and year, Spain 2014–2024",
        ("dgt_tables", "dgt_census"),
    ),
    # drivers.emef
    Table(
        "emef_checks",
        "drivers.emef",
        "EMEF file checks by year, 2014–2024: sample size, weights, keys and file consistency, passed or not",
        ("emef", "emef_technical"),
    ),
    Table(
        "emef_distance_validation",
        "drivers.emef",
        "Modelled EMEF trip distances against the 2021 distance report and 2024 summary benchmarks",
        ("emef", "emef_distance_2021"),
    ),
    Table(
        "emef_driving_frequency",
        "drivers.emef",
        "EMEF 2022–2024: how often residents drive a car, by age, and share who drove on the survey day",
        ("emef",),
    ),
    Table(
        "emef_employment_benchmark",
        "drivers.emef",
        "Employed share of residents aged 65+: EMEF 2019–2024 against the Catalonia census of 1 January 2024",
        ("ine_population", "emef", "idescat_census"),
    ),
    Table(
        "emef_exposure_area",
        "drivers.emef",
        "EMEF working-day car driving per resident by area of residence and age, 2022–2024",
        ("emef", "emef_distance_2021"),
    ),
    Table(
        "emef_exposure_contemporary",
        "drivers.emef",
        "EMEF working-day car driving per resident by sex and age, province of Barcelona, 2022–2024",
        ("emef", "emef_distance_2021"),
    ),
    Table(
        "emef_exposure_periods",
        "drivers.emef",
        "EMEF working-day car driving per resident by age, Barcelona metropolitan region, periods 2014–2024",
        ("emef", "emef_distance_2021"),
    ),
    Table(
        "emef_exposure_series",
        "drivers.emef",
        "EMEF working-day car driving per resident by year and age 2014–2024, survey area and metro region",
        ("emef", "emef_distance_2021"),
    ),
    Table(
        "emef_imputation_check",
        "drivers.emef",
        "EMEF banded car trips 2021–2024: duration-only distance estimates against the band, by duration",
        ("emef", "emef_distance_2021"),
    ),
    Table(
        "emef_inventory",
        "drivers.emef",
        "One row per EMEF year 2014–2024: files, counts, source variables, missing values and method notes",
        ("emef",),
    ),
    Table(
        "emef_km_by_band",
        "drivers.emef",
        "EMEF car-driver trips and km by straight-line distance band and age, 2022–2024",
        ("emef", "emef_distance_2021"),
    ),
    Table(
        "emef_reproduction",
        "drivers.emef",
        "Published EMEF 2024 headline figures beside the same figures computed from the microdata",
        ("emef",),
    ),
    Table(
        "emef_sensitivity",
        "drivers.emef",
        "EMEF car-driver km per resident and share of km by age under alternative choices, 2022–2024",
        ("ine_population", "emef", "emef_distance_2021", "idescat_census"),
    ),
    Table(
        "emef_weekend_2023",
        "drivers.emef",
        "EMEF 2023: residents who spent a recent weekend away, and drove there, by age",
        ("emef",),
    ),
    # drivers.exposure
    Table(
        "edm_older_split",
        "drivers.exposure",
        "Madrid 2018 survey, ages 65+: 75+ share of residents, licences and car km, and 75+/65–74 km ratio",
        ("edm2018",),
    ),
    Table(
        "edm_profile",
        "drivers.exposure",
        "Madrid 2018 survey: car-driver km per resident and licence holder by age and sex",
        ("edm2018",),
    ),
    Table(
        "emef_routing_older",
        "drivers.exposure",
        "Share aged 75+ among EMEF respondents 65+ found by questionnaire routing, vs INE, by sex, 2022–2024",
        ("ine_population", "emef"),
    ),
    Table(
        "risk_barcelona_day_type",
        "drivers.exposure",
        "Car drivers in Barcelona injury crashes 2025 by age and type of day, total and per day",
        ("gu_barcelona",),
    ),
    Table(
        "risk_barcelona_km",
        "drivers.exposure",
        "Working-day car-driver km inside and into Barcelona city per day by age, EMEF 2022–2024",
        ("emef", "emef_distance_2021"),
    ),
    Table(
        "risk_barcelona_older",
        "drivers.exposure",
        "Barcelona 2025 working-day crash ratios per km, 65–74 and 75+ vs 45–64, by 75+ split and denominator",
        (
            "dgt_census",
            "ine_population",
            "emef",
            "emef_distance_2021",
            "edm2018",
            "racc_2013",
            "gu_barcelona",
        ),
    ),
    Table(
        "risk_barcelona_rates",
        "drivers.exposure",
        "Car drivers in Barcelona injury crashes 2025 per billion working-day km, by age and definition",
        ("emef", "emef_distance_2021", "gu_barcelona"),
    ),
    Table(
        "risk_barcelona_unknown_age_bounds",
        "drivers.exposure",
        "Barcelona 2025 working-day ratios to ages 45–64 if all drivers of unrecorded age were in one group",
        ("emef", "emef_distance_2021", "gu_barcelona"),
    ),
    Table(
        "risk_coverage",
        "drivers.exposure",
        "Parts of DGT's 2024 car km explained by EMEF working days and other components, and the remainder",
        (
            "dgt_km",
            "ine_population",
            "cores_fuel",
            "transport_toll",
            "emef",
            "emef_distance_2021",
            "movilia",
        ),
    ),
    Table(
        "risk_coverage_evidence",
        "drivers.exposure",
        "Measured figures behind the km coverage decomposition: regional, seasonal, travel, calendar, fleet",
        ("dgt_km", "ine_population", "cores_fuel", "transport_toll", "emef", "movilia"),
    ),
    Table(
        "risk_coverage_mixes",
        "drivers.exposure",
        "Candidate age mixes for km outside EMEF working days: km shares and km per resident and holder",
        ("dgt_census", "dgt_km", "ine_population", "emef", "emef_distance_2021", "movilia"),
    ),
    Table(
        "risk_coverage_scenarios",
        "drivers.exposure",
        "Car-driver crash ratios to ages 45–64 by age under each coverage scenario, profile and 75+ split",
        (
            "dgt_tables",
            "dgt_census",
            "dgt_km",
            "ine_population",
            "cores_fuel",
            "transport_toll",
            "emef",
            "emef_distance_2021",
            "edm2018",
            "movilia",
            "racc_2013",
        ),
    ),
    Table(
        "risk_licence_prevalence",
        "drivers.exposure",
        "B-licence holders per resident by sex and age group, Spain and province of Barcelona, 2024",
        ("dgt_census", "ine_population"),
    ),
    Table(
        "risk_national_km_total",
        "drivers.exposure",
        "DGT 2024 car km in Spain: all cars, less taxis and ride-hailing, less car hire and driving schools",
        ("dgt_km",),
    ),
    Table(
        "risk_national_numerator",
        "drivers.exposure",
        "Private-car drivers involved in injury crashes and killed by age group, Spain 2024",
        ("dgt_tables",),
    ),
    Table(
        "risk_national_rates",
        "drivers.exposure",
        "Car drivers involved and killed per billion km by driver age, Spain 2024, by method and km total",
        (
            "dgt_tables",
            "dgt_census",
            "dgt_km",
            "ine_population",
            "emef",
            "emef_distance_2021",
            "edm2018",
        ),
    ),
    Table(
        "risk_national_sensitivity",
        "drivers.exposure",
        "Car-driver crash and death ratios to ages 45–64 by age, Spain 2024, under each alternative choice",
        (
            "dgt_tables",
            "dgt_census",
            "dgt_km",
            "ine_population",
            "cores_fuel",
            "transport_toll",
            "emef",
            "emef_distance_2021",
            "edm2018",
            "movilia",
            "idescat_census",
        ),
    ),
    Table(
        "risk_national_shares",
        "drivers.exposure",
        "Share of Spain's car-driving km by driver age group, 2024, by estimation method",
        ("dgt_census", "dgt_km", "ine_population", "emef", "emef_distance_2021", "edm2018"),
    ),
    Table(
        "risk_older_attribution",
        "drivers.exposure",
        "Share of the spread in the 75+ per-km crash ratio due to each choice in the coverage scenarios",
        (
            "dgt_tables",
            "dgt_census",
            "dgt_km",
            "ine_population",
            "cores_fuel",
            "transport_toll",
            "emef",
            "emef_distance_2021",
            "edm2018",
            "movilia",
            "racc_2013",
        ),
    ),
    Table(
        "risk_older_decomposition",
        "drivers.exposure",
        "Range of the 75+ per-km crash ratio when each choice is varied one at a time, Spain 2024",
        (
            "dgt_tables",
            "dgt_census",
            "dgt_km",
            "ine_population",
            "cores_fuel",
            "transport_toll",
            "emef",
            "emef_distance_2021",
            "edm2018",
            "movilia",
            "idescat_census",
            "racc_2013",
        ),
    ),
    Table(
        "risk_older_extremes",
        "drivers.exposure",
        "Sampling intervals at the ends of the 65–74 and 75+ per-km crash ratio ranges, Spain 2024",
        (
            "dgt_tables",
            "dgt_census",
            "dgt_km",
            "ine_population",
            "cores_fuel",
            "transport_toll",
            "emef",
            "emef_distance_2021",
            "edm2018",
            "movilia",
            "idescat_census",
            "racc_2013",
        ),
    ),
    Table(
        "risk_older_reference_checks",
        "drivers.exposure",
        "Checks on the 75+ estimate: licence holding, Madrid km per holder, owner km, crashes per holder",
        (
            "dgt_tables",
            "dgt_census",
            "dgt_km",
            "ine_population",
            "emef",
            "emef_distance_2021",
            "edm2018",
            "racc_2013",
        ),
    ),
    Table(
        "risk_older_sensitivity",
        "drivers.exposure",
        "65–74 and 75+ per-km crash ratios to ages 45–64 under every sensitivity variant and split, 2024",
        (
            "dgt_tables",
            "dgt_census",
            "dgt_km",
            "ine_population",
            "cores_fuel",
            "transport_toll",
            "emef",
            "emef_distance_2021",
            "edm2018",
            "movilia",
            "idescat_census",
            "racc_2013",
        ),
    ),
    Table(
        "risk_older_split",
        "drivers.exposure",
        "Drivers involved per billion km at 65–74 and 75+, ratio to 45–64, Spain 2024, by profile and split",
        (
            "dgt_tables",
            "dgt_census",
            "dgt_km",
            "ine_population",
            "emef",
            "emef_distance_2021",
            "edm2018",
            "racc_2013",
        ),
    ),
    Table(
        "risk_owner_age_comparison",
        "drivers.exposure",
        "Car drivers involved per billion km by age, Spain 2024: owner-age km against driver-age km",
        ("dgt_tables", "dgt_km", "ine_population", "emef", "emef_distance_2021", "edm2018"),
    ),
    Table(
        "risk_severity_and_licences",
        "drivers.exposure",
        "Car drivers killed per 1,000 involved and involved per 1,000 B-licence holders by age, Spain 2024",
        ("dgt_tables", "dgt_census"),
    ),
    Table(
        "risk_sex_per_km",
        "drivers.exposure",
        "Men-to-women ratio of private-car drivers 18+ involved and killed per km, Spain 2024",
        ("dgt_tables", "dgt_census", "ine_population", "emef", "emef_distance_2021", "edm2018"),
    ),
    Table(
        "risk_unknown_age_bounds",
        "drivers.exposure",
        "Spain 2024 crash ratios to ages 45–64 if all drivers of unrecorded age were in one group",
        ("dgt_tables", "ine_population", "emef", "emef_distance_2021", "edm2018"),
    ),
    Table(
        "risk_weekend_sensitivity",
        "drivers.exposure",
        "Car drivers involved per billion km by age, Spain 2024, if non-working days differ in km and age mix",
        ("dgt_tables", "dgt_km", "ine_population", "emef", "emef_distance_2021", "movilia"),
    ),
    # models.fit
    Table(
        "ml_calibration",
        "models.fit",
        "Observed against mean predicted outcome share by probability bin, each source model's test rows",
        ("dgt_microdata", "sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_feature_catalogue",
        "models.fit",
        "Every candidate column of the three feature tables with its leakage status and feature sets",
        (),
    ),
    Table(
        "ml_geography",
        "models.fit",
        "Train, validation and test ROC-AUC of each source model by geography: none, broad, comarca, granular",
        ("dgt_microdata", "sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_importance",
        "models.fit",
        "Permutation importance (fall in test ROC-AUC) of each feature in each selected source model",
        ("dgt_microdata", "sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_missingness",
        "models.fit",
        "Missing values of each candidate feature in each feature table and how they are treated",
        ("dgt_microdata", "sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_rare_causes",
        "models.fit",
        "Barcelona crashes with each recorded cause, and whether there are enough to model it",
        ("gu_barcelona",),
    ),
    Table(
        "ml_recording_artefacts",
        "models.fit",
        "Rate of each Catalan field's 'not specified' level by outcome, year and place, with a verdict",
        ("sct_catalonia",),
    ),
    Table(
        "ml_recording_check",
        "models.fit",
        "Outcome share where a categorical feature holds a placeholder value, against the other training rows",
        ("sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_rule_comparison",
        "models.fit",
        "Test ROC-AUC and PR-AUC of each source model against its descriptive lookup table, with the gain",
        ("sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_selected",
        "models.fit",
        "Test performance and calibration of the selected estimator for each source model and feature set",
        ("dgt_microdata", "sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_split_isolation",
        "models.fit",
        "Training, validation and test rows of each source model, and checks that no crash is on both sides",
        ("sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_stability",
        "models.fit",
        "Scores of each source model's selected estimator by rolling-origin year and cross-validation fold",
        ("dgt_microdata", "sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_variants",
        "models.fit",
        "Scores of every estimator, feature set and geography variant on training, validation and test rows",
        ("dgt_microdata", "sct_catalonia", "gu_barcelona"),
    ),
    # models.validate
    Table(
        "dgt_audit_artefacts",
        "models.validate",
        "Share of DGT records' fatality ranking that comes only from which fields were left unrecorded",
        ("dgt_microdata",),
    ),
    Table(
        "dgt_audit_checks",
        "models.validate",
        "The seven pre-declared checks on whether DGT microdata may train or test a severity model",
        ("dgt_microdata", "dgt_series"),
    ),
    Table(
        "dgt_audit_junction_coding",
        "models.validate",
        "DGT junction-flag use by province and year, beside the Catalan file's junction coding",
        ("dgt_microdata", "sct_catalonia"),
    ),
    Table(
        "dgt_audit_outcome_recording",
        "models.validate",
        "Unrecorded share of each DGT field in fatal and non-fatal crashes, Catalonia and rest of Spain",
        ("dgt_microdata",),
    ),
    Table(
        "dgt_audit_presence_coding",
        "models.validate",
        "How often DGT records fog and strong wind by province and year, beside the Catalan fog field",
        ("dgt_microdata", "sct_catalonia"),
    ),
    Table(
        "dgt_audit_regional",
        "models.validate",
        "Unrecorded share of each DGT candidate field and how much it varies between provinces",
        ("dgt_microdata",),
    ),
    Table(
        "dgt_audit_transfer",
        "models.validate",
        "Checks that the Catalonia-to-Spain transfer test on DGT crashes measures what it claims",
        ("dgt_microdata", "sct_catalonia"),
    ),
    Table(
        "gen_calculator_transfer",
        "models.validate",
        "Calculator model scored on held-out years and places of the Catalan file, beside in-domain scores",
        ("sct_catalonia",),
    ),
    Table(
        "gen_coding_by_region",
        "models.validate",
        "DGT crashes by year using road-type and junction-type codes whose use changed, Catalonia vs the rest",
        ("dgt_microdata",),
    ),
    Table(
        "gen_cross_source_register",
        "models.validate",
        "Each comparison across sources: key, units, definitions, transformation and compatibility",
        ("dgt_microdata", "sct_catalonia"),
    ),
    Table(
        "gen_outcomes",
        "models.validate",
        "Severe and fatal shares of DGT injury crashes, Catalonia and Barcelona city against the rest",
        ("dgt_microdata",),
    ),
    Table(
        "gen_population_context",
        "models.validate",
        "Residents and age-group shares of Barcelona province, Catalonia and the rest of Spain",
        ("ine_population",),
    ),
    Table(
        "gen_province_rates",
        "models.validate",
        "DGT severe crashes per 100,000 residents and fatal share of severe crashes, by province and year",
        ("dgt_microdata", "ine_population"),
    ),
    Table(
        "gen_representativeness",
        "models.validate",
        "Mix of each shared crash variable in DGT records, Catalonia and Barcelona city against the rest",
        ("dgt_microdata",),
    ),
    Table(
        "ml_barcelona_diagnosis",
        "models.validate",
        "ROC-AUC of each design used to explain why the Catalan model ranks Barcelona's crashes worse",
        ("sct_catalonia",),
    ),
    Table(
        "ml_barcelona_diagnosis_components",
        "models.validate",
        "Parts of the Catalan model's ROC-AUC drop on Barcelona (training size, intrinsic, transport)",
        ("sct_catalonia",),
    ),
    Table(
        "ml_barcelona_diagnosis_verdicts",
        "models.validate",
        "Which part makes up most of the Catalan model's ROC-AUC drop on Barcelona, per feature set",
        ("sct_catalonia",),
    ),
    Table(
        "ml_common_feature_validation",
        "models.validate",
        "Each DGT common field's Catalan-vs-DGT divergence on the same crashes, and whether it is used",
        ("dgt_microdata", "sct_catalonia"),
    ),
    Table(
        "ml_common_features",
        "models.validate",
        "Fields Catalonia shares with DGT or Barcelona: source columns, mapping, semantics and status",
        (),
    ),
    Table(
        "ml_domain_shift",
        "models.validate",
        "Feature and outcome differences between domains: Catalan file, DGT records and Barcelona 2025",
        ("dgt_microdata", "sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_domain_strategies",
        "models.validate",
        "Domain-specific, other-domain and pooled Catalan models scored on each target domain's crashes",
        ("sct_catalonia",),
    ),
    Table(
        "ml_model_decisions",
        "models.validate",
        "Keep, replace or drop decision for each model, with its test score, baseline and validated level",
        ("dgt_microdata", "dgt_series", "cores_fuel", "sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_outward_path",
        "models.validate",
        "Each model's result at each of five stages from its own held-out rows out to Spain, with evidence",
        ("dgt_microdata", "sct_catalonia", "gu_barcelona"),
    ),
    Table(
        "ml_subgroup_validation",
        "models.validate",
        "Out-of-fold scores of the Barcelona person model by role, vehicle, age band, sex and district",
        ("gu_barcelona",),
    ),
    Table(
        "ml_transport_provinces",
        "models.validate",
        "Catalan model on DGT-common features scored on each province's DGT crashes outside Catalonia",
        ("dgt_microdata", "sct_catalonia"),
    ),
    Table(
        "ml_transport_reweighting",
        "models.validate",
        "Zone x crash-type mix of Catalan training crashes against DGT crashes outside Catalonia, and weights",
        ("dgt_microdata", "sct_catalonia"),
    ),
    Table(
        "ml_transport_validation",
        "models.validate",
        "Source models scored outside their training domain (time, place, source) beside in-domain scores",
        ("dgt_microdata", "sct_catalonia", "gu_barcelona"),
    ),
    # models.calculator
    Table(
        "sev_calibration",
        "models.calculator",
        "Predicted against observed fatal share by tenth of predicted risk: calculator, trees and table",
        ("sct_catalonia",),
    ),
    Table(
        "sev_choices",
        "models.calculator",
        "Penalty, specification, through-town rule and provinces chosen for each rolling year and final model",
        ("sct_catalonia",),
    ),
    Table(
        "sev_coefficients",
        "models.calculator",
        "Each coefficient of the published calculator model with its bootstrap standard error",
        ("sct_catalonia",),
    ),
    Table(
        "sev_comparison",
        "models.calculator",
        "Bootstrap intervals for the scores of calculator, trees and table, and their gaps to the calculator",
        ("sct_catalonia",),
    ),
    Table(
        "sev_contrasts",
        "models.calculator",
        "Calculator's fatal probability at each input level against an urban or interurban base scenario",
        ("sct_catalonia",),
    ),
    Table(
        "sev_geography",
        "models.calculator",
        "Calculator and table scored on each demarcation, and Barcelona city, predicted from the rest",
        ("sct_catalonia",),
    ),
    Table(
        "sev_marginal_adjusted",
        "models.calculator",
        "Raw and model-standardised fatal share of crashes at each level of each calculator input",
        ("sct_catalonia",),
    ),
    Table(
        "sev_nested_steps",
        "models.calculator",
        "ROC-AUC gain over the road x crash table at each step from the previous design to the nested one",
        ("sct_catalonia",),
    ),
    Table(
        "sev_penalty",
        "models.calculator",
        "Validation log loss and ROC-AUC of each penalty and specification tried in each calculator fit",
        ("sct_catalonia",),
    ),
    Table(
        "sev_population",
        "models.calculator",
        "Crashes and fatal share in the calculator's fitted crashes against those left out for road owner",
        ("sct_catalonia",),
    ),
    Table(
        "sev_rolling_scores",
        "models.calculator",
        "Calculator, trees and table scored by nested rolling origin 2016–2023, by year, zone and province",
        ("sct_catalonia",),
    ),
    Table(
        "sev_stability",
        "models.calculator",
        "Calculator's scenario contrasts refitted on early and late years and on separate provinces",
        ("sct_catalonia",),
    ),
    # models.review
    Table(
        "review_barcelona",
        "models.review",
        "Independent refit of the two Barcelona models scored on months 10–12, against prevalence and table",
        ("gu_barcelona",),
    ),
    Table(
        "review_catalonia_2023",
        "models.review",
        "Independent refit of the Catalan model and its competitors, trained to 2020 and scored on 2023",
        ("sct_catalonia",),
    ),
    Table(
        "review_catalonia_rolling",
        "models.review",
        "Catalan model and its competitors predicted year by year from earlier years, 2016–2023",
        ("sct_catalonia",),
    ),
    Table(
        "review_forecast",
        "models.review",
        "Error, bias and estimation error of each monthly-deaths forecast variant and of last year's count",
        ("dgt_series", "cores_fuel"),
    ),
    # sources.inventory
    Table(
        "data_inventory",
        "sources.inventory",
        "One row per raw data file: size, hash, format, rows, columns, coverage, source and manifest status",
        FILE_SOURCES,
    ),
    # sources.profile
    Table(
        "source_comparison",
        "sources.profile",
        "How the DGT, INE, Catalan and Barcelona sources came to exist: one row per source and question",
        (
            "dgt_microdata",
            "dgt_series",
            "dgt_tables",
            "dgt_census",
            "dgt_km",
            "ine_population",
            "sct_catalonia",
            "gu_barcelona",
        ),
    ),
    # national.withdrawn
    Table(
        "forecast_backtest",
        "national.withdrawn",
        "Withdrawn forecast: each scored year's deaths beside the model, last-year and tree forecasts",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "forecast_coefficients",
        "national.withdrawn",
        "Withdrawn forecast: road-fuel, calendar and trend effects of the model fitted on 2021–2024",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "forecast_detectability",
        "national.withdrawn",
        "Withdrawn forecast: smallest change in deaths detectable by zone and horizon of 1–5 years",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "forecast_horizons",
        "national.withdrawn",
        "Withdrawn forecast: error of 1- to 5-year death totals by zone, split into chance and drift",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "forecast_selection",
        "national.withdrawn",
        "Withdrawn forecast: error of every method and window in selection, holdout and pandemic years",
        ("dgt_series", "cores_fuel"),
    ),
    Table(
        "forecast_validation",
        "national.withdrawn",
        "Withdrawn forecast: chosen model against naive forecasts and trees, by zone and kind of year",
        ("dgt_series", "cores_fuel"),
    ),
)
TABLE_BY_NAME = {entry.name: entry for entry in TABLES}
