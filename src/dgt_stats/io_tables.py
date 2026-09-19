"""Readers for the published DGT tables: the 1993–2024 historical series and the 2024 statistical tables.

Every function returns a tidy ``pandas.DataFrame`` and records the sheet it came from in a
``source_sheet`` column. Sheet layouts are located by the label in the first header cell rather than
by fixed row numbers so that small layout shifts in future releases are caught as parse errors.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import openpyxl
import pandas as pd

from dgt_stats.paths import INTERIM_DATA_DIR, SERIES_PATH, TABLES_2024_PATH

log = logging.getLogger(__name__)

MONTH_ABBREVIATIONS = (
    "Ene.",
    "Feb.",
    "Mar.",
    "Abr.",
    "May.",
    "Jun.",
    "Jul.",
    "Ago.",
    "Sep.",
    "Oct.",
    "Nov.",
    "Dic.",
)
MONTH_NAMES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)

# Monthly sheets in the series workbook: sheet -> (metric, zone).
MONTHLY_SHEETS: dict[str, tuple[str, str]] = {
    "M_I-U_Meses": ("deaths_30d", "all"),
    "M_I_Meses": ("deaths_30d", "interurban"),
    "M_U_Meses": ("deaths_30d", "urban"),
    "HG_I-U_Meses": ("hospitalised_30d", "all"),
    "HG_I_Meses": ("hospitalised_30d", "interurban"),
    "HG_U_Meses": ("hospitalised_30d", "urban"),
    "HL_I-U_Meses": ("non_hospitalised_30d", "all"),
    "HL_I_Meses": ("non_hospitalised_30d", "interurban"),
    "HL_U_Meses": ("non_hospitalised_30d", "urban"),
    "Vict_I-U_Meses": ("victims_30d", "all"),
    "Vict_I_Meses": ("victims_30d", "interurban"),
    "Vict_U_Meses": ("victims_30d", "urban"),
    "Fallec_24h_I_U": ("deaths_24h", "all"),
    "Fallec_24h_I": ("deaths_24h", "interurban"),
    "Fallec_24h_U": ("deaths_24h", "urban"),
}

# Province sheets: sheet -> (metric, zone).
PROVINCE_SHEETS: dict[str, tuple[str, str]] = {
    "Acc_Vict_I-U_Provincias": ("crashes", "all"),
    "Acc_Vict_I_Provincias": ("crashes", "interurban"),
    "Acc_Vict_U_Provincias": ("crashes", "urban"),
    "MU_I-U_Provincias": ("deaths_30d", "all"),
    "MU_I_Provincias": ("deaths_30d", "interurban"),
    "MU_U_Provincias": ("deaths_30d", "urban"),
    "HG_I-U-Provincias": ("hospitalised_30d", "all"),
    "HG_I_Provincias": ("hospitalised_30d", "interurban"),
    "HG_U_Provincias": ("hospitalised_30d", "urban"),
    "HL_I-U_Provincias": ("non_hospitalised_30d", "all"),
    "HL_I_Provincias": ("non_hospitalised_30d", "interurban"),
    "HL_U_Provincias": ("non_hospitalised_30d", "urban"),
    "VIC_I-U_Provincias": ("victims_30d", "all"),
    "VIC_I_Provincias": ("victims_30d", "interurban"),
    "VIC_U_Provincias": ("victims_30d", "urban"),
}

# Driver / occupant death sheets by vehicle type: sheet -> (population, severity, zone).
ROAD_USER_SHEETS: dict[str, tuple[str, str, str]] = {
    "Cond-Pasj_MU_I-U": ("drivers_and_passengers", "deaths_30d", "all"),
    "Cond-Pasj_MU_I": ("drivers_and_passengers", "deaths_30d", "interurban"),
    "Cond-Pasj_MU_U": ("drivers_and_passengers", "deaths_30d", "urban"),
    "Cond-Pasj_HG_I-U": ("drivers_and_passengers", "hospitalised_30d", "all"),
    "Cond-Pasj_HG_I": ("drivers_and_passengers", "hospitalised_30d", "interurban"),
    "Cond-Pasj_HG_U": ("drivers_and_passengers", "hospitalised_30d", "urban"),
    "Cond-Pasj_HL_I-U": ("drivers_and_passengers", "non_hospitalised_30d", "all"),
    "Cond-Pasj_HL_I": ("drivers_and_passengers", "non_hospitalised_30d", "interurban"),
    "Cond-Pasj_HL_U": ("drivers_and_passengers", "non_hospitalised_30d", "urban"),
    "Cond_MU_I-U": ("drivers", "deaths_30d", "all"),
    "Cond_MU_I": ("drivers", "deaths_30d", "interurban"),
    "Cond_MU_U": ("drivers", "deaths_30d", "urban"),
    "Cond_HG_I-U": ("drivers", "hospitalised_30d", "all"),
    "Cond_HG_I": ("drivers", "hospitalised_30d", "interurban"),
    "Cond_HG_U": ("drivers", "hospitalised_30d", "urban"),
    "Cond_HL_I-U": ("drivers", "non_hospitalised_30d", "all"),
    "Cond_HL_I": ("drivers", "non_hospitalised_30d", "interurban"),
    "Cond_HL_U": ("drivers", "non_hospitalised_30d", "urban"),
}

AGE_SHEETS: dict[str, str] = {"Vict_ED_I_U": "all", "Vict_ED_I": "interurban", "Vict_ED_U": "urban"}
SEX_SHEETS: dict[str, str] = {"Vict_SX_I_U": "all", "Vict_SX_I": "interurban", "Vict_SX_U": "urban"}
PEDESTRIAN_SHEETS: dict[str, str] = {
    "Pea_Vic_I-U": "all",
    "Pea_Vic_I": "interurban",
    "Pea_Vic_U": "urban",
}
PEDESTRIAN_AGE_SHEETS: dict[str, str] = {
    "Edad_Pea_VIC_I-U": "all",
    "Edad_Pea_VIC_I": "interurban",
    "Edad_Pea_VIC_U": "urban",
}

SEVERITY_LEVELS = ("deaths_30d", "hospitalised_30d", "non_hospitalised_30d")
SEVERITY_LABELS = {
    "Fallecidos": "deaths_30d",
    "Heridos hospitalizados": "hospitalised_30d",
    "Heridos no hospitalizados": "non_hospitalised_30d",
    "Total": "victims_30d",
    "TOTAL": "victims_30d",
}


# --------------------------------------------------------------------------- generic helpers


@lru_cache(maxsize=4)
def _workbook(path: Path) -> openpyxl.Workbook:
    return openpyxl.load_workbook(path, read_only=True, data_only=True)


def _rows(path: Path, sheet: str) -> list[tuple]:
    return [tuple(row) for row in _workbook(path)[sheet].iter_rows(values_only=True)]


def _text(value: object) -> str:
    return "" if value is None else " ".join(str(value).split())


def _find_header(rows: list[tuple], first_cell: str) -> int:
    for index, row in enumerate(rows):
        if row and _text(row[0]).lower() == first_cell.lower():
            return index
    raise ValueError(f"header row starting with {first_cell!r} not found")


def _number(value: object) -> float | None:
    """Numeric cell or ``None``; the series workbook uses '.' for not-available."""
    if value is None or (isinstance(value, str) and value.strip() in {"", ".", "-"}):
        return None
    return float(value)


def _year_rows(rows: list[tuple], header_index: int) -> list[tuple]:
    body = []
    for row in rows[header_index + 1 :]:
        if not row or row[0] is None:
            continue
        try:
            year = int(row[0])
        except (TypeError, ValueError):
            continue
        body.append((year, *row[1:]))
    return body


# --------------------------------------------------------------------------- series workbook


def read_series_annual() -> pd.DataFrame:
    """Annual national totals 1993–2024: crashes by zone, victims by severity, and DGT rate table."""
    frames: list[pd.DataFrame] = []

    rows = _rows(SERIES_PATH, "Acc_Vict")
    header = _find_header(rows, "Años")
    for year, total, _, interurban, _, urban, *_ in _year_rows(rows, header):
        frames.append(
            pd.DataFrame(
                {
                    "year": year,
                    "metric": "crashes",
                    "zone": ["all", "interurban", "urban"],
                    "value": [_number(total), _number(interurban), _number(urban)],
                    "source_sheet": "Acc_Vict",
                }
            )
        )

    rows = _rows(SERIES_PATH, "Vict_I-U")
    header = _find_header(rows, "Años")
    for year, total, deaths, hosp, non_hosp, *_ in _year_rows(rows, header):
        frames.append(
            pd.DataFrame(
                {
                    "year": year,
                    "metric": [
                        "victims_30d",
                        "deaths_30d",
                        "hospitalised_30d",
                        "non_hospitalised_30d",
                    ],
                    "zone": "all",
                    "value": [_number(total), _number(deaths), _number(hosp), _number(non_hosp)],
                    "source_sheet": "Vict_I-U",
                }
            )
        )

    rows = _rows(SERIES_PATH, "Tasas_Acc_Vic")
    header = _find_header(rows, "Años")
    rate_metrics = (
        "vehicle_fleet",
        "crashes_per_10k_vehicles",
        "deaths_per_10k_vehicles",
        "deaths_per_1k_crashes",
        "injured_per_1k_crashes",
        "deaths_per_10k_population",
    )
    for year, *values in _year_rows(rows, header):
        frames.append(
            pd.DataFrame(
                {
                    "year": year,
                    "metric": list(rate_metrics),
                    "zone": "all",
                    "value": [_number(v) for v in values[: len(rate_metrics)]],
                    "source_sheet": "Tasas_Acc_Vic",
                }
            )
        )

    out = pd.concat(frames, ignore_index=True)
    return out.astype(
        {"year": "int16", "metric": "string", "zone": "string", "source_sheet": "string"}
    )


def read_series_monthly() -> pd.DataFrame:
    """Every monthly sheet stacked: year × month × metric × zone."""
    frames: list[pd.DataFrame] = []
    for sheet, (metric, zone) in MONTHLY_SHEETS.items():
        rows = _rows(SERIES_PATH, sheet)
        header = _find_header(rows, "Años")
        labels = [_text(cell) for cell in rows[header][1:13]]
        if tuple(labels) != MONTH_ABBREVIATIONS:
            raise ValueError(f"{sheet}: unexpected month header {labels}")
        for year, *values in _year_rows(rows, header):
            months = [_number(v) for v in values[:12]]
            total = _number(values[12]) if len(values) > 12 else None
            frames.append(
                pd.DataFrame(
                    {
                        "year": year,
                        "month": range(1, 13),
                        "metric": metric,
                        "zone": zone,
                        "value": months,
                        "annual_total": total,
                        "source_sheet": sheet,
                    }
                )
            )
    out = pd.concat(frames, ignore_index=True)
    return out.astype(
        {
            "year": "int16",
            "month": "int8",
            "metric": "string",
            "zone": "string",
            "source_sheet": "string",
        }
    )


def read_series_province() -> pd.DataFrame:
    """Province × year for crashes and victims by severity and zone, 1993–2024."""
    frames: list[pd.DataFrame] = []
    for sheet, (metric, zone) in PROVINCE_SHEETS.items():
        rows = _rows(SERIES_PATH, sheet)
        header = _find_header(rows, "Provincias")
        years = [int(cell) for cell in rows[header][1:] if cell is not None]
        for row in rows[header + 1 :]:
            name = _text(row[0])
            if not name:
                continue
            values = [_number(v) for v in row[1 : 1 + len(years)]]
            frames.append(
                pd.DataFrame(
                    {
                        "province": name,
                        "is_total": name.upper() == "TOTAL",
                        "year": years,
                        "metric": metric,
                        "zone": zone,
                        "value": values,
                        "source_sheet": sheet,
                    }
                )
            )
    out = pd.concat(frames, ignore_index=True)
    return out.astype(
        {
            "province": "string",
            "year": "int16",
            "metric": "string",
            "zone": "string",
            "source_sheet": "string",
        }
    )


def _read_two_level_sheets(
    sheets: dict[str, str], group_field: str, sub_field: str
) -> pd.DataFrame:
    """Sheets with a group header row and a sub-header row (severity × age band, sex × severity).

    Whichever of the two fields is ``severity`` is normalised with :data:`SEVERITY_LABELS`.
    """
    frames: list[pd.DataFrame] = []
    for sheet, zone in sheets.items():
        rows = _rows(SERIES_PATH, sheet)
        header = _find_header(rows, "Años")
        groups = rows[header]
        subs = rows[header + 1]
        columns: list[tuple[str, str]] = []
        current = ""
        for group, sub in zip(groups[1:], subs[1:]):
            if group is not None and _text(group):
                current = _text(group)
            columns.append((current, _text(sub)))
        records: list[dict[str, object]] = []
        for year, *values in _year_rows(rows, header + 1):
            for (group, sub), value in zip(columns, values):
                if not sub:
                    continue
                record = {"year": year, group_field: group, sub_field: sub}
                record["severity"] = SEVERITY_LABELS.get(record["severity"], record["severity"])
                record.update({"zone": zone, "value": _number(value), "source_sheet": sheet})
                records.append(record)
        frames.append(pd.DataFrame.from_records(records))
    out = pd.concat(frames, ignore_index=True)
    return out.astype(
        {
            "year": "int16",
            group_field: "string",
            sub_field: "string",
            "zone": "string",
            "source_sheet": "string",
        }
    )


def read_series_age() -> pd.DataFrame:
    """Victims by age band × severity × zone, 1993–2024."""
    return _read_two_level_sheets(AGE_SHEETS, "severity", "age_band")


def read_series_sex() -> pd.DataFrame:
    """Victims by sex × severity × zone, 1993–2024."""
    return _read_two_level_sheets(SEX_SHEETS, "sex", "severity")


def read_series_road_users() -> pd.DataFrame:
    """Driver (and passenger) casualties by vehicle type × year × zone, 1993–2024."""
    frames: list[pd.DataFrame] = []
    for sheet, (population, severity, zone) in ROAD_USER_SHEETS.items():
        rows = _rows(SERIES_PATH, sheet)
        header = _find_header(rows, "Años")
        types = [_text(cell) for cell in rows[header][1:] if cell is not None]
        for year, *values in _year_rows(rows, header):
            for vehicle_type, value in zip(types, values):
                frames.append(
                    pd.DataFrame(
                        {
                            "year": [year],
                            "population": [population],
                            "severity": [severity],
                            "vehicle_type": [vehicle_type],
                            "is_total": [vehicle_type.upper() == "TOTAL"],
                            "zone": [zone],
                            "value": [_number(value)],
                            "source_sheet": [sheet],
                        }
                    )
                )
    out = pd.concat(frames, ignore_index=True)
    return out.astype(
        {
            "year": "int16",
            "population": "string",
            "severity": "string",
            "vehicle_type": "string",
            "zone": "string",
            "source_sheet": "string",
        }
    )


def read_series_pedestrians() -> pd.DataFrame:
    """Pedestrian victims by severity × zone and by age band × zone, 1993–2024."""
    frames: list[pd.DataFrame] = []
    for sheet, zone in PEDESTRIAN_SHEETS.items():
        rows = _rows(SERIES_PATH, sheet)
        header = _find_header(rows, "Años")
        labels = [_text(cell) for cell in rows[header][1:5]]
        for year, *values in _year_rows(rows, header):
            for label, value in zip(labels, values):
                frames.append(
                    pd.DataFrame(
                        {
                            "year": [year],
                            "breakdown": ["severity"],
                            "category": [SEVERITY_LABELS.get(label, label)],
                            "zone": [zone],
                            "value": [_number(value)],
                            "source_sheet": [sheet],
                        }
                    )
                )
    for sheet, zone in PEDESTRIAN_AGE_SHEETS.items():
        rows = _rows(SERIES_PATH, sheet)
        header = _find_header(rows, "Años")
        labels = [_text(cell) for cell in rows[header][1:] if cell is not None]
        for year, *values in _year_rows(rows, header):
            for label, value in zip(labels, values):
                frames.append(
                    pd.DataFrame(
                        {
                            "year": [year],
                            "breakdown": ["age_band"],
                            "category": [label],
                            "zone": [zone],
                            "value": [_number(value)],
                            "source_sheet": [sheet],
                        }
                    )
                )
    out = pd.concat(frames, ignore_index=True)
    return out.astype(
        {
            "year": "int16",
            "breakdown": "string",
            "category": "string",
            "zone": "string",
            "source_sheet": "string",
        }
    )


# --------------------------------------------------------------------------- 2024 statistical tables

PROVINCE_TABLE_METRICS = (
    "crashes",
    "fatal_crashes",
    "deaths_30d",
    "hospitalised_30d",
    "non_hospitalised_30d",
)


def read_table_1_1() -> pd.DataFrame:
    """TABLA 1.1: 2024 crashes and victims by province and zone."""
    rows = _rows(TABLES_2024_PATH, "TABLA 1.1")
    header = _find_header(rows, "PROVINCIAS")
    zones = ("interurban", "urban", "all")
    frames: list[pd.DataFrame] = []
    for row in rows[header + 2 :]:
        name = _text(row[0])
        if not name:
            continue
        values = [_number(v) for v in row[1:16]]
        for zone_index, zone in enumerate(zones):
            block = values[zone_index * 5 : zone_index * 5 + 5]
            frames.append(
                pd.DataFrame(
                    {
                        "province": name,
                        "is_total": name.upper() == "TOTAL",
                        "zone": zone,
                        "metric": list(PROVINCE_TABLE_METRICS),
                        "value": block,
                        "source_sheet": "TABLA 1.1",
                    }
                )
            )
    out = pd.concat(frames, ignore_index=True)
    return out.astype(
        {"province": "string", "zone": "string", "metric": "string", "source_sheet": "string"}
    )


MONTH_TABLE_METRICS = (
    "crashes",
    "fatal_crashes",
    "victims_30d",
    "deaths_30d",
    "hospitalised_30d",
    "non_hospitalised_30d",
)


def read_table_3_1() -> pd.DataFrame:
    """TABLA 3.1: 2024 crashes and victims by month and zone."""
    rows = _rows(TABLES_2024_PATH, "TABLA 3.1")
    header = _find_header(rows, "MES")
    zones = ("interurban", "urban", "all")
    frames: list[pd.DataFrame] = []
    for row in rows[header + 3 :]:
        name = _text(row[0])
        if not name:
            continue
        month = MONTH_NAMES.index(name) + 1 if name in MONTH_NAMES else None
        values = [_number(v) for v in row[1:19]]
        for zone_index, zone in enumerate(zones):
            block = values[zone_index * 6 : zone_index * 6 + 6]
            frames.append(
                pd.DataFrame(
                    {
                        "month_name": name,
                        "month": month,
                        "is_total": name.upper() == "TOTAL",
                        "zone": zone,
                        "metric": list(MONTH_TABLE_METRICS),
                        "value": block,
                        "source_sheet": "TABLA 3.1",
                    }
                )
            )
    out = pd.concat(frames, ignore_index=True)
    return out.astype(
        {
            "month_name": "string",
            "month": "Int8",
            "zone": "string",
            "metric": "string",
            "source_sheet": "string",
        }
    )


VEHICLE_TABLE_METRICS = ("crashes", "fatal_crashes", "injury_crashes")


def read_table_2_3() -> pd.DataFrame:
    """TABLA 2.3: 2024 units (vehicles and pedestrians) involved, by type, zone and crash severity."""
    rows = _rows(TABLES_2024_PATH, "TABLA 2.3")
    header = _find_header(rows, "TIPO VEHÍCULO")
    zones = ("all", "interurban", "urban")
    frames: list[pd.DataFrame] = []
    for row in rows[header + 2 :]:
        name = _text(row[0])
        if not name:
            continue
        values = [_number(v) for v in row[1:10]]
        for zone_index, zone in enumerate(zones):
            block = values[zone_index * 3 : zone_index * 3 + 3]
            frames.append(
                pd.DataFrame(
                    {
                        "unit_type": name,
                        "is_total": name.upper() == "TOTAL",
                        "zone": zone,
                        "metric": list(VEHICLE_TABLE_METRICS),
                        "value": block,
                        "source_sheet": "TABLA 2.3",
                    }
                )
            )
    out = pd.concat(frames, ignore_index=True)
    return out.astype(
        {"unit_type": "string", "zone": "string", "metric": "string", "source_sheet": "string"}
    )


def read_table_8_1_1() -> pd.DataFrame:
    """TABLA 8.1.1: 2024 crashes and victims by number of vehicles involved and zone."""
    rows = _rows(TABLES_2024_PATH, "TABLA 8.1.1")
    header = _find_header(rows, "VEHÍCULOS IMPLICADOS")
    zones = ("all", "interurban", "urban")
    frames: list[pd.DataFrame] = []
    for row in rows[header + 2 :]:
        name = _text(row[0])
        if not name:
            continue
        values = [_number(v) for v in row[1:16]]
        for zone_index, zone in enumerate(zones):
            block = values[zone_index * 5 : zone_index * 5 + 5]
            frames.append(
                pd.DataFrame(
                    {
                        "vehicles_involved": name,
                        "is_total": name.upper() == "TOTAL",
                        "zone": zone,
                        "metric": list(PROVINCE_TABLE_METRICS),
                        "value": block,
                        "source_sheet": "TABLA 8.1.1",
                    }
                )
            )
    out = pd.concat(frames, ignore_index=True)
    return out.astype(
        {
            "vehicles_involved": "string",
            "zone": "string",
            "metric": "string",
            "source_sheet": "string",
        }
    )


# --------------------------------------------------------------------------- interim layer

TABLE_BUILDERS = {
    "series_annual": read_series_annual,
    "series_monthly": read_series_monthly,
    "series_province": read_series_province,
    "series_age": read_series_age,
    "series_sex": read_series_sex,
    "series_road_users": read_series_road_users,
    "series_pedestrians": read_series_pedestrians,
    "tables_2024_province": read_table_1_1,
    "tables_2024_month": read_table_3_1,
    "tables_2024_units": read_table_2_3,
    "tables_2024_vehicles_involved": read_table_8_1_1,
}


def interim_path(name: str) -> Path:
    return INTERIM_DATA_DIR / f"{name}.parquet"


def build_tables(force: bool = False) -> list[Path]:
    """Write every published-table frame to ``data/interim`` as Parquet."""
    written: list[Path] = []
    INTERIM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, builder in TABLE_BUILDERS.items():
        target = interim_path(name)
        if target.exists() and not force:
            log.info("tables %s: exists, skipping", name)
            written.append(target)
            continue
        frame = builder()
        frame.to_parquet(target, index=False)
        log.info("tables %s: %s rows -> %s", name, f"{len(frame):,}", target.name)
        written.append(target)
    return written


def read_table(name: str) -> pd.DataFrame:
    return pd.read_parquet(interim_path(name))
