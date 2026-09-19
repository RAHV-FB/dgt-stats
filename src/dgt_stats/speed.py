"""Speed and context (question Q9): what the sources record about speed, and where it concentrates.

No source measures speed. The yearbook tables 6.1 record a police judgement per driver ("speed
infraction", none, or unknown); the DGT speed report records, per crash, whether "inappropriate
speed" was a concurrent factor, for Spain without Cataluña and País Vasco. The two are never added.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgt_stats import io_reports, io_tables, rates, vehicles

LATEST_YEAR = 2024
REPORT_LATEST = "2023"

ROAD_TYPE_LABELS = {
    "Autopista": "Motorways",
    "Autovía": "Dual carriageways",
    "Resto de vías interurbanas": "Other interurban roads",
    "Vías urbanas": "Urban streets",
    "Total": "Total",
}
FACTOR_LABELS = {
    "Conducción distraída o desatenta": "Distraction or inattention",
    "Velocidad inadecuada": "Inappropriate speed",
    "Maniobras antirreglamentarias*": "Illegal manoeuvres",
    "Alcohol": "Alcohol",
    "Drogas": "Drugs",
}
REPORT_VEHICLE_LABELS = {
    "Peatón": "Pedestrians",
    "Bicicleta": "Bicycles",
    "VMP": "Personal mobility vehicles",
    "Ciclomotor": "Mopeds",
    "Motocicleta": "Motorcycles",
    "Turismo": "Cars",
    "Furgoneta": "Vans",
    "Camión hasta 3.500 kg": "Trucks up to 3,500 kg",
    "Camión más 3.500 kg": "Trucks over 3,500 kg",
    "Autobús": "Buses",
    "Otro vehículo": "Other vehicles",
    "Se desconoce": "Unknown",
    "Total": "Total",
}
AGE_LABELS = {
    "De 0 a 14 años": "0-14",
    "De 15 a 24 años": "15-24",
    "De 25 a 34 años": "25-34",
    "De 35 a 44 años": "35-44",
    "De 45 a 54 años": "45-54",
    "De 55 a 64 años": "55-64",
    "De 65 a 74 años": "65-74",
    "De 75 a 84 años": "75-84",
    "De 85 y más años": "85+",
    "De 65 y más años": "65+ (all)",
    "Se desconoce": "Unknown",
    "Subtotal": "Subtotal",
}
SPEED_ITEM_LABELS = {
    "speed_infraction": "Speed infraction",
    "too_slow": "Driving too slowly",
    "none": "No speed infraction",
    "unknown": "Unknown",
}
ZONE_LABELS = {"all": "All roads", "interurban": "Interurban roads", "urban": "Urban streets"}


# --------------------------------------------------------------------------- yearbook tables 6.1


def _infractions() -> pd.DataFrame:
    return io_tables.read_table("tables_driver_infractions")


def _with_all_zones(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Append an ``all`` zone as the sum of interurban and urban."""
    both = frame.groupby([k for k in keys if k != "zone"], as_index=False).value.sum()
    both["zone"] = "all"
    return pd.concat([frame, both], ignore_index=True)


def infraction_shares() -> pd.DataFrame:
    """Drivers by speed status, year and zone, 2014–2024: counts, shares of all drivers, and the
    infraction share among drivers whose status is known (Wilson intervals)."""
    speed = _infractions()
    speed = speed[(speed.block == "speed") & (speed.vehicle_group == "total")]
    speed = _with_all_zones(speed[["year", "zone", "item", "value"]], ["year", "zone", "item"])
    wide = speed.pivot_table(index=["year", "zone"], columns="item", values="value").reset_index()
    wide = wide.rename_axis(columns=None)
    wide["known"] = wide.total - wide.unknown
    for item in ("speed_infraction", "too_slow", "none", "unknown"):
        wide[f"share_{item}"] = (wide[item] / wide.total).round(4)
    wide["share_among_known"] = (wide.speed_infraction / wide.known).round(4)
    intervals = [
        rates.wilson_interval(float(s) / float(k), float(k))
        for s, k in zip(wide.speed_infraction, wide.known)
    ]
    wide["share_among_known_low"] = [round(low, 4) for low, _ in intervals]
    wide["share_among_known_high"] = [round(high, 4) for _, high in intervals]
    wide["zone_label"] = wide.zone.map(ZONE_LABELS)
    order = {"all": 0, "interurban": 1, "urban": 2}
    wide = wide.sort_values(["year", "zone"], key=lambda s: s.map(order) if s.name == "zone" else s)
    columns = [
        "year",
        "zone",
        "zone_label",
        "total",
        "known",
        "speed_infraction",
        "too_slow",
        "none",
        "unknown",
        "share_speed_infraction",
        "share_too_slow",
        "share_none",
        "share_unknown",
        "share_among_known",
        "share_among_known_low",
        "share_among_known_high",
    ]
    return wide[columns].reset_index(drop=True)


def infractions_by_vehicle(year: int = LATEST_YEAR) -> pd.DataFrame:
    """Speed status by vehicle group and zone for one year, with the share among known."""
    speed = _infractions()
    speed = speed[(speed.block == "speed") & (speed.year == year)]
    speed = _with_all_zones(
        speed[["zone", "item", "vehicle_group", "value"]], ["zone", "item", "vehicle_group"]
    )
    wide = speed.pivot_table(
        index=["zone", "vehicle_group"], columns="item", values="value"
    ).reset_index()
    wide = wide.rename_axis(columns=None)
    wide["known"] = wide.total - wide.unknown
    wide["share_unknown"] = (wide.unknown / wide.total).round(4)
    wide["share_among_known"] = (wide.speed_infraction / wide.known).round(4)
    intervals = [
        rates.wilson_interval(float(s) / float(k), float(k)) if k > 0 else (np.nan, np.nan)
        for s, k in zip(wide.speed_infraction, wide.known)
    ]
    wide["share_among_known_low"] = [round(low, 4) for low, _ in intervals]
    wide["share_among_known_high"] = [round(high, 4) for _, high in intervals]
    wide["year"] = year
    labels = {name: vehicles.label(name) for name in vehicles.VEHICLE_GROUPS} | {
        "total": "All drivers"
    }
    wide["vehicle_label"] = wide.vehicle_group.map(labels)
    wide["zone_label"] = wide.zone.map(ZONE_LABELS)
    group_order = {name: index for index, name in enumerate([*vehicles.VEHICLE_GROUPS, "total"])}
    zone_order = {"all": 0, "interurban": 1, "urban": 2}
    wide = wide.sort_values(
        ["zone", "vehicle_group"],
        key=lambda s: s.map(zone_order if s.name == "zone" else group_order),
    )
    columns = [
        "year",
        "zone",
        "zone_label",
        "vehicle_group",
        "vehicle_label",
        "total",
        "known",
        "speed_infraction",
        "unknown",
        "share_unknown",
        "share_among_known",
        "share_among_known_low",
        "share_among_known_high",
    ]
    return wide[columns].reset_index(drop=True)


def other_infractions(year: int = LATEST_YEAR) -> pd.DataFrame:
    """Every infraction item of the driver and speed blocks for one year, by zone, as a share of the
    drivers whose status in that block is known. Blocks without a total row (2014–2015) are left
    out."""
    frame = _infractions()
    frame = frame[(frame.year == year) & (frame.vehicle_group == "total")]
    frame = frame[frame.block.isin(["speed", "driver"])]
    frame = _with_all_zones(frame[["zone", "block", "item", "value"]], ["zone", "block", "item"])
    totals = frame[frame.item == "total"].set_index(["zone", "block"]).value
    unknown = frame[frame.item == "unknown"].set_index(["zone", "block"]).value
    items = frame[~frame.item.isin(["total", "unknown", "none", "too_slow"])].copy()
    keys = list(zip(items.zone, items.block))
    has_total = [k in totals.index and k in unknown.index for k in keys]
    items, keys = items[has_total].copy(), [k for k, ok in zip(keys, has_total) if ok]
    items["drivers"] = [totals[k] for k in keys]
    items["known"] = [totals[k] - unknown[k] for k in keys]
    items["share_of_known"] = (items.value / items.known).round(4)
    items["label"] = items.item.map(io_tables.INFRACTION_ITEM_LABELS)
    items["zone_label"] = items.zone.map(ZONE_LABELS)
    items["year"] = year
    items = items.sort_values(["zone", "value"], ascending=[True, False])
    columns = [
        "year",
        "zone",
        "zone_label",
        "block",
        "item",
        "label",
        "value",
        "drivers",
        "known",
        "share_of_known",
    ]
    return (
        items[columns].rename(columns={"value": "drivers_with_infraction"}).reset_index(drop=True)
    )


# --------------------------------------------------------------------------- the speed report


def _report() -> pd.DataFrame:
    return io_reports.read_report("speed_report")


def _report_grid(breakdown: str, metric: str, zone: str = "all") -> pd.DataFrame:
    report = _report()
    rows = report[
        (report.breakdown == breakdown) & (report.metric == metric) & (report.zone == zone)
    ]
    return rows[["category", "column", "value"]].rename(columns={"column": "year"})


def report_factors() -> pd.DataFrame:
    """Crashes with each concurrent factor and their share of all crashes, by zone and year."""
    counts = pd.concat(
        [_report_grid("factors", "crashes", zone).assign(zone=zone) for zone in ZONE_LABELS]
    ).rename(columns={"value": "crashes"})
    shares = pd.concat(
        [_report_grid("factors", "crash_share", zone).assign(zone=zone) for zone in ZONE_LABELS]
    ).rename(columns={"value": "share_of_crashes"})
    out = counts.merge(shares, on=["zone", "category", "year"], how="left")
    out["factor"] = out.category.map(FACTOR_LABELS)
    out["zone_label"] = out.zone.map(ZONE_LABELS)
    out["year"] = out.year.astype(int)
    out["region_scope"] = io_reports.REGION_SCOPE
    columns = [
        "year",
        "zone",
        "zone_label",
        "factor",
        "crashes",
        "share_of_crashes",
        "region_scope",
    ]
    return out[columns].sort_values(["zone", "factor", "year"]).reset_index(drop=True)


def _breakdown_with_shares(breakdown: str, labels: dict[str, str] | None) -> pd.DataFrame:
    frames = []
    for metric in ("crashes", "deaths"):
        grid = _report_grid(breakdown, metric).rename(columns={"value": metric})
        frames.append(grid.set_index(["category", "year"])[metric])
    out = pd.concat(frames, axis=1).reset_index()
    total_rows = out[out.category == "Total"].set_index("year")
    if not total_rows.empty:
        out["share_of_crashes"] = (out.crashes / out.year.map(total_rows.crashes)).round(4)
        out["share_of_deaths"] = (out.deaths / out.year.map(total_rows.deaths)).round(4)
    out["label"] = out.category.map(labels) if labels else out.category
    out["label"] = out.label.fillna(out.category)
    out["year"] = out.year.astype(int)
    out["region_scope"] = io_reports.REGION_SCOPE
    return out.sort_values(["year", "category"]).reset_index(drop=True)


def report_road_type() -> pd.DataFrame:
    """Crashes and deaths with the speed factor by road type and year, with shares of the total."""
    order = list(ROAD_TYPE_LABELS)
    out = _breakdown_with_shares("road_type", ROAD_TYPE_LABELS)
    return out.sort_values(
        ["year", "category"],
        key=lambda s: s.map({c: i for i, c in enumerate(order)}) if s.name == "category" else s,
    ).reset_index(drop=True)


def report_speed_limit() -> pd.DataFrame:
    """Crashes and deaths with the speed factor by the road's speed limit and year."""
    out = _breakdown_with_shares("speed_limit", None)
    out["label"] = out.category.replace(
        {"Otra velocidad máxima": "Other limit", "Se desconoce *": "Unknown"}
    )
    limit = out.category.str.extract(r"^(\d+) km/h")[0].astype(float)
    out["limit_km_h"] = limit
    out["order"] = limit.fillna(900) + out.category.eq("Total").astype(float) * 100
    out = out.sort_values(["year", "order"]).drop(columns="order")
    return out.reset_index(drop=True)


def report_vehicle() -> pd.DataFrame:
    """Crashes and deaths with the speed factor by means of transport and year. The crash total
    counts a crash once per vehicle type involved, so it exceeds the number of crashes."""
    out = _breakdown_with_shares("vehicle", REPORT_VEHICLE_LABELS)
    total_deaths = out[out.category == "Total"].set_index("year").deaths
    out["share_of_deaths"] = (out.deaths / out.year.map(total_deaths)).round(4)
    out = out.drop(columns=["share_of_crashes"], errors="ignore")
    order = {name: index for index, name in enumerate(REPORT_VEHICLE_LABELS)}
    out = out.sort_values(
        ["year", "category"], key=lambda c: c.map(order) if c.name == "category" else c
    )
    return out.reset_index(drop=True)


def report_age() -> pd.DataFrame:
    """Crashes with the speed factor and driver deaths by the driver's age band, all, men and
    women, for the latest report year and 2014."""
    frames = []
    for breakdown, sex in (
        ("driver_age", "all"),
        ("driver_age_men", "men"),
        ("driver_age_women", "women"),
    ):
        crashes = _report_grid(breakdown, "crashes").rename(columns={"value": "crashes"})
        deaths = _report_grid(breakdown, "driver_deaths").rename(columns={"value": "driver_deaths"})
        merged = crashes.merge(deaths, on=["category", "year"], how="outer").assign(sex=sex)
        frames.append(merged)
    out = pd.concat(frames, ignore_index=True)
    out = out[out.year.isin(["2014", REPORT_LATEST])]
    out["age_band"] = out.category.map(AGE_LABELS).fillna(out.category)
    out["year"] = out.year.astype(int)
    subtotal = out[out.category == "Subtotal"].set_index(["sex", "year"])
    keys = list(zip(out.sex, out.year))
    out["share_of_crashes"] = (
        out.crashes / np.array([subtotal.crashes.get(k, np.nan) for k in keys])
    ).round(4)
    out["region_scope"] = io_reports.REGION_SCOPE
    columns = [
        "year",
        "sex",
        "category",
        "age_band",
        "crashes",
        "driver_deaths",
        "share_of_crashes",
        "region_scope",
    ]
    return out[columns].reset_index(drop=True)


def report_day_hour() -> pd.DataFrame:
    """Crashes and deaths with the speed factor by weekday and hour, 2014–2023 pooled, all roads."""
    frames = []
    for metric in ("crashes", "deaths"):
        grid = _report_grid("day_hour", metric).rename(columns={"year": "weekday", "value": metric})
        frames.append(grid.set_index(["category", "weekday"])[metric])
    out = pd.concat(frames, axis=1).reset_index().rename(columns={"category": "hour"})
    out = out[(out.hour != "Total") & (out.weekday != "Total")].copy()
    out["hour_start"] = out.hour.str.slice(0, 2).astype(int)
    weekday_order = {
        d: i
        for i, d in enumerate(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        )
    }
    out["weekday_index"] = out.weekday.map(weekday_order)
    out["share_of_crashes"] = (out.crashes / out.crashes.sum()).round(5)
    out["region_scope"] = io_reports.REGION_SCOPE
    columns = [
        "weekday",
        "weekday_index",
        "hour",
        "hour_start",
        "crashes",
        "deaths",
        "share_of_crashes",
        "region_scope",
    ]
    return out[columns].sort_values(["weekday_index", "hour_start"]).reset_index(drop=True)


def report_licence() -> pd.DataFrame:
    """Crashes with the speed factor and driver deaths by licence class, latest year and 2014."""
    crashes = _report_grid("licence_class", "crashes").rename(columns={"value": "crashes"})
    deaths = _report_grid("licence_class", "driver_deaths").rename(
        columns={"value": "driver_deaths"}
    )
    out = crashes.merge(deaths, on=["category", "year"], how="outer")
    out = out[out.year.isin(["2014", REPORT_LATEST])].copy()
    out["year"] = out.year.astype(int)
    totals = out[out.category == "Total"].set_index("year")
    out["share_of_crashes"] = (out.crashes / out.year.map(totals.crashes)).round(4)
    out["share_of_driver_deaths"] = (out.driver_deaths / out.year.map(totals.driver_deaths)).round(
        4
    )
    out["region_scope"] = io_reports.REGION_SCOPE
    return out.rename(columns={"category": "licence_class"}).reset_index(drop=True)
