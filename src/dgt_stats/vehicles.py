"""Vehicle groups and the 2022 rates per kilometre driven (question Q6).

The yearbook tables list 22 unit types, the kilometre table 7 vehicle types, the series 9 columns and
the microdata 12 death columns. One dictionary maps all four onto the same groups so that a rate's
numerator and denominator always describe the same vehicles. The rates combine the 2022 yearbook
tables (vehicles involved, occupant deaths) with the 2022 kilometre estimates (fleet × mean km).
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import io_exposure, io_tables, rates

KM_YEAR = 2022
BILLION = 1_000_000_000
PER_VEHICLES = 100_000
AGE_BANDS = {
    "De 0 a 4 años": "0-4 years",
    "De 5 a 9 años": "5-9 years",
    "De 10 a 14 años": "10-14 years",
    "De 15 a 19 años": "15-19 years",
    "20 años y más": "20 years and over",
}
MEASURES = {
    "injury_involvement": "Vehicles involved in injury crashes",
    "fatal_involvement": "Vehicles involved in fatal crashes",
    "occupant_deaths": "Occupants killed (drivers and passengers)",
}

# Group -> the names it takes in each source. ``units`` are the row labels of TABLA 2.2 and 2.3
# (whitespace collapsed), ``km_type`` the vehicle type of the 2022 kilometre table (``None`` when the
# group has no kilometre denominator), ``microdata`` the 30-day death column, ``series`` the column of
# the ``Cond-Pasj_MU`` sheets (``None`` when the series merges the group with another).
VEHICLE_GROUPS: dict[str, dict[str, object]] = {
    "moped": {
        "label": "Mopeds",
        "units": ("Ciclomotor",),
        "km_type": "Ciclomotor",
        "microdata": "TOT_CICLO_MU30DF",
        "series": "Ciclomotores",
    },
    "motorcycle": {
        "label": "Motorcycles",
        "units": ("Motocicleta",),
        "km_type": "Motocicleta",
        "microdata": "TOT_MOTO_MU30DF",
        "series": "Motocicletas",
    },
    "car": {
        "label": "Cars",
        "units": ("Turismo sin remolque", "Turismo con remolque", "Turismo de SP hasta 9 plazas"),
        "km_type": "Turismo",
        "microdata": "TOT_TUR_MU30DF",
        "series": "Turismos",
    },
    "van": {
        "label": "Vans",
        "units": ("Furgoneta",),
        "km_type": "Furgoneta",
        "microdata": "TOT_FURG_MU30DF",
        "series": None,
    },
    "light_truck": {
        "label": "Trucks up to 3,500 kg",
        "units": ("Camión <=3.500 kg sin remolque", "Camión <=3.500 kg con remolque"),
        "km_type": "Camión hasta 3.500Kg",
        "microdata": "TOT_CAM_MENOS3500_MU30DF",
        "series": None,
    },
    "heavy_truck": {
        "label": "Trucks over 3,500 kg",
        "units": (
            "Camión >3.500 kg sin remolque",
            "Camión >3.500 kg con remolque",
            "Tractocamión (cabeza tractora)",
            "Vehículo articulado",
        ),
        "km_type": "Camión más de 3.500Kg",
        "microdata": "TOT_CAM_MAS3500_MU30DF",
        "series": "Camiones más de 3.500 kg",
    },
    "bus": {
        "label": "Buses",
        "units": ("Autobús (no escolar)", "Autobús escolar"),
        "km_type": "Autobús",
        "microdata": "TOT_BUS_MU30DF",
        "series": "Autobuses",
    },
    "pedestrian": {
        "label": "Pedestrians",
        "units": ("Peatón",),
        "km_type": None,
        "microdata": "TOT_PEAT_MU30DF",
        "series": None,
    },
    "bicycle": {
        "label": "Bicycles",
        "units": ("Bicicleta",),
        "km_type": None,
        "microdata": "TOT_BICI_MU30DF",
        "series": "Bicicletas",
    },
    "vmp": {
        "label": "Personal mobility vehicles",
        "units": ("VMP",),
        "km_type": None,
        "microdata": "TOT_VMP_MU30DF",
        "series": "VMP",
    },
    "other": {
        "label": "Other vehicles",
        "units": (
            "Maquinaria obras y agrícola y tractores agrícolas",
            "Cuadriciclo",
            "Tren/metro/tranvía",
            "Otro vehículo",
        ),
        "km_type": None,
        "microdata": "TOT_OTRO_MU30DF",
        "series": "Otros",
    },
    "unknown": {
        "label": "Unknown vehicle",
        "units": ("Se desconoce",),
        "km_type": None,
        "microdata": "TOT_SINESPECIF_MU30DF",
        "series": None,
    },
}

# What the reader must know about a group's sources, printed in the mapping table.
GROUP_NOTES = {
    "heavy_truck": (
        "the kilometre table's category is the union of the methodology note's 'camiones de más de "
        "3.500 kg' (272,157 vehicles, 6.9 bn km) and 'tractores industriales' (222,594 vehicles, "
        "19.7 bn km, the note's validation table; the estimation file places 936 of these vehicles "
        "in the light stratum instead, so the fleet total is unchanged), so tractor units and "
        "articulated vehicles belong in the numerator"
    ),
    "van": "one rate group with trucks up to 3,500 kg",
    "light_truck": "one rate group with vans",
    "other": (
        "agricultural-use vehicles and special vehicles are excluded from the ITV database "
        "(methodology note, p. 7), so the machinery row has no kilometre denominator and does not "
        "enter the heavy-truck rate; quadricycle involvement also sits here while the kilometre "
        "table counts light quadricycles (L6e) as mopeds and heavy ones (L7e) as motorcycles, so "
        "those two denominators include vehicles whose crashes are counted in this row"
    ),
}

# Groups with a kilometre denominator, in the order the page shows them.
KM_GROUPS = tuple(name for name, spec in VEHICLE_GROUPS.items() if spec["km_type"] is not None)

# The series merges vans with light trucks in one column, and so do the rates: the crash record
# codes most light commercial vehicles as "Furgoneta" while the register splits them into vans and
# trucks up to 3,500 kg, so only their sum has the same meaning in numerator and denominator.
SERIES_MERGED_COLUMN = "Camiones hasta 3.500 kg y furgonetas"
SERIES_MERGED_GROUPS = ("van", "light_truck")
MERGED_GROUP = "van_light_truck"
MERGED_LABEL = "Vans and trucks up to 3,500 kg"
RATE_GROUP_OF = {
    name: (MERGED_GROUP if name in SERIES_MERGED_GROUPS else name) for name in VEHICLE_GROUPS
}
RATE_GROUPS = tuple(dict.fromkeys(RATE_GROUP_OF[name] for name in KM_GROUPS))

UNIT_TO_GROUP: dict[str, str] = {
    unit: name
    for name, spec in VEHICLE_GROUPS.items()
    for unit in spec["units"]  # type: ignore[attr-defined]
}


def group_of(unit_type: str) -> str:
    """Group of a yearbook unit label; raises for a label the mapping does not know."""
    try:
        return UNIT_TO_GROUP[unit_type]
    except KeyError as error:
        raise KeyError(f"unit type {unit_type!r} is not in VEHICLE_GROUPS") from error


def label(group: str) -> str:
    if group == MERGED_GROUP:
        return MERGED_LABEL
    return str(VEHICLE_GROUPS[group]["label"])


# --------------------------------------------------------------------------- Q6 summaries


def _group_column(unit_type: pd.Series) -> pd.Series:
    return unit_type.map(UNIT_TO_GROUP)


def vehicle_groups_table() -> pd.DataFrame:
    """The mapping as a table for the site: one row per group with its names in every source."""
    records = []
    for name, spec in VEHICLE_GROUPS.items():
        records.append(
            {
                "group": name,
                "label": spec["label"],
                "yearbook_unit_types": "; ".join(spec["units"]),  # type: ignore[arg-type]
                "km_table_type": spec["km_type"] or "",
                "microdata_column": spec["microdata"],
                "series_column": spec["series"]
                or (SERIES_MERGED_COLUMN if name in SERIES_MERGED_GROUPS else ""),
                "has_km_denominator": spec["km_type"] is not None,
                "note": GROUP_NOTES.get(name, ""),
            }
        )
    return pd.DataFrame.from_records(records)


def km_by_age() -> pd.DataFrame:
    """Fleet, mean km and vehicle-km by group and vehicle age band, 2022."""
    km = io_exposure.read_exposure("km_medios_2022")
    type_to_group = {
        spec["km_type"]: name for name, spec in VEHICLE_GROUPS.items() if spec["km_type"]
    }
    unknown = set(km.vehicle_type) - set(type_to_group)
    if unknown:
        raise ValueError(f"km table vehicle types without a group: {sorted(unknown)}")
    out = pd.DataFrame(
        {
            "group": km.vehicle_type.map(type_to_group),
            "age_band": km.age_band.map(AGE_BANDS),
            "n_vehicles": km.n_vehicles.astype("int64"),
            "mean_km_year": km.mean_km_year.astype(float),
            "vehicle_km": km.vehicle_km.astype(float),
        }
    )
    if out.age_band.isna().any():
        raise ValueError("km table age band without a label")
    out["label"] = out.group.map(label)
    out["km_share_within_group"] = (
        out.vehicle_km / out.groupby("group").vehicle_km.transform("sum")
    ).round(4)
    order = {name: index for index, name in enumerate(KM_GROUPS)}
    bands = {name: index for index, name in enumerate(AGE_BANDS.values())}
    out = out.sort_values(
        ["group", "age_band"], key=lambda s: s.map(order if s.name == "group" else bands)
    )
    return out[
        [
            "group",
            "label",
            "age_band",
            "n_vehicles",
            "mean_km_year",
            "vehicle_km",
            "km_share_within_group",
        ]
    ].reset_index(drop=True)


def vehicle_km(by_rate_group: bool = False) -> pd.DataFrame:
    """Fleet, vehicle-km and km per vehicle by group for 2022, with shares and a total row.

    With ``by_rate_group`` vans and trucks up to 3,500 kg are one row, as in the rates.
    """
    by_age = km_by_age()
    groups = list(RATE_GROUPS) if by_rate_group else list(KM_GROUPS)
    if by_rate_group:
        by_age = by_age.assign(group=by_age.group.map(RATE_GROUP_OF))
    out = by_age.groupby("group", sort=False).agg(
        n_vehicles=("n_vehicles", "sum"), vehicle_km=("vehicle_km", "sum")
    )
    out = out.reindex(groups).reset_index()
    total = pd.DataFrame(
        {
            "group": ["total"],
            "n_vehicles": [out.n_vehicles.sum()],
            "vehicle_km": [out.vehicle_km.sum()],
        }
    )
    out = pd.concat([out, total], ignore_index=True)
    out["label"] = out.group.map(lambda g: "All seven types" if g == "total" else label(g))
    out["km_per_vehicle"] = (out.vehicle_km / out.n_vehicles).round(0)
    fleet, km = out.loc[out.group == "total", ["n_vehicles", "vehicle_km"]].iloc[0]
    out["fleet_share"] = (out.n_vehicles / fleet).round(4)
    out["km_share"] = (out.vehicle_km / km).round(4)
    return out[
        ["group", "label", "n_vehicles", "vehicle_km", "km_per_vehicle", "fleet_share", "km_share"]
    ]


def _counts(year: int) -> pd.DataFrame:
    """Vehicles involved (injury and fatal crashes) and occupant deaths by group, year and zone."""
    units = io_tables.read_table("tables_units_by_type")
    victims = io_tables.read_table("tables_victims_by_mode")
    units = units[(units.year == year) & ~units.is_total].assign(
        group=lambda d: _group_column(d.unit_type).map(RATE_GROUP_OF)
    )
    involved = (
        units[units.metric.isin(["crashes", "fatal_crashes"])]
        .groupby(["group", "zone", "metric"])
        .value.sum()
        .unstack("metric")
        .rename(columns={"crashes": "injury_involvement", "fatal_crashes": "fatal_involvement"})
    )
    victims = victims[(victims.year == year) & ~victims.is_total & (victims.metric == "deaths_30d")]
    victims = victims.assign(group=lambda d: _group_column(d.unit_type).map(RATE_GROUP_OF))
    occupants = (
        victims[victims.role.isin(["driver", "passenger"])]
        .groupby(["group", "zone"])
        .value.sum()
        .rename("occupant_deaths")
    )
    both = (
        occupants.groupby("group")
        .sum()
        .to_frame()
        .assign(zone="all")
        .set_index("zone", append=True)
    )
    occupants = pd.concat([occupants.to_frame(), both]).occupant_deaths
    out = involved.join(occupants, how="left").reset_index()
    out["year"] = year
    return out.rename_axis(columns=None)


def rates_2022() -> pd.DataFrame:
    """Long table: group × zone × measure with counts, denominators, rates and exact intervals.

    The kilometre and fleet denominators are national; zone rows share them and the
    ``denominator`` column says so.
    """
    counts = _counts(KM_YEAR)
    km = vehicle_km(by_rate_group=True).set_index("group")
    records = []
    for measure in MEASURES:
        block = counts[counts.group.isin(RATE_GROUPS)][["group", "zone", measure]].rename(
            columns={measure: "count"}
        )
        block = block.assign(
            measure=measure,
            n_vehicles=block.group.map(km.n_vehicles),
            vehicle_km=block.group.map(km.vehicle_km),
        )
        records.append(block)
    out = pd.concat(records, ignore_index=True)
    out = rates.add_rate(out, "count", "vehicle_km", "per_billion_km", per=BILLION)
    out = rates.add_rate(out, "count", "n_vehicles", "per_100k_vehicles", per=PER_VEHICLES)
    out["label"] = out.group.map(label)
    out["measure_label"] = out.measure.map(MEASURES)
    out["denominator"] = "national fleet and vehicle-km, 2022"
    order = {name: index for index, name in enumerate(RATE_GROUPS)}
    zones = {"all": 0, "interurban": 1, "urban": 2}
    measures = {name: index for index, name in enumerate(MEASURES)}
    out = out.sort_values(
        ["measure", "zone", "group"],
        key=lambda s: s.map({"measure": measures, "zone": zones, "group": order}[s.name]),
    )
    columns = [
        "year",
        "group",
        "label",
        "zone",
        "measure",
        "measure_label",
        "count",
        "n_vehicles",
        "vehicle_km",
        "per_billion_km",
        "per_billion_km_low",
        "per_billion_km_high",
        "per_100k_vehicles",
        "per_100k_vehicles_low",
        "per_100k_vehicles_high",
        "denominator",
    ]
    out["year"] = KM_YEAR
    out["count"] = out["count"].astype("int64")
    return out[columns].reset_index(drop=True)


def summary_2022() -> pd.DataFrame:
    """Wide table for the page: one row per group, all roads, with both rankings and the
    occupant-death share of fatal-crash involvements."""
    long = rates_2022()
    wide = long[long.zone == "all"].pivot(index="group", columns="measure", values="count")
    km = vehicle_km(by_rate_group=True).set_index("group")
    groups = list(RATE_GROUPS)
    out = pd.DataFrame(
        {
            "group": groups,
            "label": [label(g) for g in groups],
            "n_vehicles": km.n_vehicles.reindex(groups).values,
            "km_per_vehicle": km.km_per_vehicle.reindex(groups).values,
            "vehicle_km_bn": (km.vehicle_km.reindex(groups) / BILLION).round(2).values,
        }
    )
    for measure in MEASURES:
        out[measure] = wide[measure].reindex(groups).astype("int64").values
        rows = long[(long.zone == "all") & (long.measure == measure)].set_index("group")
        out[f"{measure}_per_bn_km"] = rows.per_billion_km.reindex(groups).round(2).values
        out[f"{measure}_per_100k_vehicles"] = rows.per_100k_vehicles.reindex(groups).round(2).values
    out["occupant_deaths_per_fatal_involvement"] = (
        out.occupant_deaths / out.fatal_involvement
    ).round(3)
    out["rank_fatal_per_100k_vehicles"] = out.fatal_involvement_per_100k_vehicles.rank(
        ascending=False, method="first"
    ).astype(int)
    out["rank_fatal_per_bn_km"] = out.fatal_involvement_per_bn_km.rank(
        ascending=False, method="first"
    ).astype(int)
    return out


def van_light_truck_split() -> pd.DataFrame:
    """Vans and trucks up to 3,500 kg taken separately for 2022: the evidence for merging them.

    The crash record codes most light commercial vehicles as vans while the register splits them,
    so the separate rates are not comparable; the page prints them to show the gap.
    """
    units = io_tables.read_table("tables_units_by_type")
    units = units[(units.year == KM_YEAR) & ~units.is_total & (units.zone == "all")]
    units = units.assign(group=lambda d: _group_column(d.unit_type))
    counts = (
        units[
            units.group.isin(SERIES_MERGED_GROUPS) & units.metric.isin(["crashes", "fatal_crashes"])
        ]
        .groupby(["group", "metric"])
        .value.sum()
        .unstack("metric")
        .rename(columns={"crashes": "injury_involvement", "fatal_crashes": "fatal_involvement"})
    )
    km = vehicle_km().set_index("group")
    out = counts.reindex(list(SERIES_MERGED_GROUPS)).reset_index()
    out["label"] = out.group.map(label)
    out["n_vehicles"] = out.group.map(km.n_vehicles).astype("int64")
    out["vehicle_km"] = out.group.map(km.vehicle_km)
    for measure in ("injury_involvement", "fatal_involvement"):
        out[measure] = out[measure].astype("int64")
        out[f"{measure}_per_bn_km"] = (out[measure] / out.vehicle_km * BILLION).round(2)
        out[f"{measure}_per_100k_vehicles"] = (out[measure] / out.n_vehicles * PER_VEHICLES).round(
            2
        )
    out["year"] = KM_YEAR
    columns = [
        "year",
        "group",
        "label",
        "n_vehicles",
        "vehicle_km",
        "injury_involvement",
        "injury_involvement_per_bn_km",
        "injury_involvement_per_100k_vehicles",
        "fatal_involvement",
        "fatal_involvement_per_bn_km",
        "fatal_involvement_per_100k_vehicles",
    ]
    return out[columns]


def involvement_by_year() -> pd.DataFrame:
    """Vehicles involved and occupant deaths by group, 2020–2024, all roads (counts only)."""
    frames = [_counts(year) for year in io_tables.VEHICLE_TABLE_YEARS]
    out = pd.concat(frames, ignore_index=True)
    out = out[out.zone == "all"].drop(columns="zone")
    for column in ("injury_involvement", "fatal_involvement", "occupant_deaths"):
        out[column] = out[column].fillna(0).astype("int64")
    out["label"] = out.group.map(label)
    vehicles_only = out[out.group != "pedestrian"]
    totals = vehicles_only.groupby("year").fatal_involvement.sum()
    share = vehicles_only.fatal_involvement / vehicles_only.year.map(totals)
    out["fatal_involvement_share_of_vehicles"] = share.round(4)  # NaN for pedestrians
    order = {name: index for index, name in enumerate(dict.fromkeys(RATE_GROUP_OF.values()))}
    out = out.sort_values(["year", "group"], key=lambda s: s.map(order) if s.name == "group" else s)
    columns = [
        "year",
        "group",
        "label",
        "injury_involvement",
        "fatal_involvement",
        "occupant_deaths",
        "fatal_involvement_share_of_vehicles",
    ]
    return out[columns].reset_index(drop=True)


def occupant_deaths_series() -> pd.DataFrame:
    """Drivers and passengers killed (30-day) by group, 1993–2024, all roads, from the series.

    Vans and light trucks are one column in the series and stay merged here.
    """
    users = io_tables.read_table("series_road_users")
    rows = users[
        (users.population == "drivers_and_passengers")
        & (users.severity == "deaths_30d")
        & (users.zone == "all")
        & ~users.is_total
    ]
    series_to_group = {
        spec["series"]: name for name, spec in VEHICLE_GROUPS.items() if spec["series"]
    }
    series_to_group[SERIES_MERGED_COLUMN] = MERGED_GROUP
    out = rows[["year", "vehicle_type", "value"]].rename(
        columns={"vehicle_type": "series_column", "value": "deaths_30d"}
    )
    out = out.assign(group=out.series_column.map(series_to_group))
    if out.group.isna().any():
        raise ValueError(
            f"series columns without a group: {sorted(out[out.group.isna()].series_column)}"
        )
    out["label"] = out.group.map(label)
    out["has_km_denominator"] = out.group.isin(RATE_GROUPS)
    return out[
        ["year", "group", "label", "series_column", "deaths_30d", "has_km_denominator"]
    ].reset_index(drop=True)
