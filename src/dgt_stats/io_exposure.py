"""Readers for exposure denominators: the driver census and the ITV kilometre estimates."""

from __future__ import annotations

import logging
from pathlib import Path

import openpyxl
import pandas as pd

from dgt_stats.paths import (
    CENSUS_TABLES_2025_PATH,
    CENSUS_YEARS,
    INTERIM_DATA_DIR,
    KM_ESTIMATED_2022_PATH,
    KM_MEAN_2022_PATH,
    census_raw_path,
)

log = logging.getLogger(__name__)

SEX_CODES = {"V": "male", "M": "female"}

KM_VEHICLE_TYPES = (
    "Ciclomotor",
    "Motocicleta",
    "Turismo",
    "Furgoneta",
    "Camión hasta 3.500Kg",
    "Camión más de 3.500Kg",
    "Autobús",
)


def read_census_year(year: int) -> pd.DataFrame:
    """One census extract: drivers by province, sex, highest licence class and year of issue.

    ``CLASE_PERMISO`` is the driver's single highest class, so the file sums to the number of
    licensed drivers, not to the number of permits.
    """
    raw = pd.read_csv(census_raw_path(year), sep="|", dtype=str, encoding="utf-8-sig")
    raw.columns = [column.strip() for column in raw.columns]
    for column in raw.columns:
        raw[column] = raw[column].str.strip()
    out = pd.DataFrame(
        {
            "census_year": year,
            "province_code": raw["COD_PROVINCIA"],
            "sex_code": raw["IND_SEXO"],
            "sex": raw["IND_SEXO"].map(SEX_CODES),
            "licence_class": raw["CLASE_PERMISO"],
            "licence_year": raw["DESC_ANTIG_PERMISO"],
            "n_drivers": pd.to_numeric(raw["NUM_CONDUCTORES"]).astype("int32"),
        }
    )
    if out["sex"].isna().any():
        raise ValueError(f"census {year}: unexpected sex code")
    return out.astype(
        {
            "census_year": "int16",
            "province_code": "string",
            "sex_code": "string",
            "sex": "string",
            "licence_class": "string",
            "licence_year": "string",
        }
    )


def read_census_all(years: tuple[int, ...] = CENSUS_YEARS) -> pd.DataFrame:
    return pd.concat([read_census_year(year) for year in years], ignore_index=True)


def read_census_province_totals_2025() -> pd.DataFrame:
    """Published 2025 census by province of residence and sex (sheet P_6_1_1_10)."""
    workbook = openpyxl.load_workbook(CENSUS_TABLES_2025_PATH, read_only=True, data_only=True)
    rows = [tuple(row) for row in workbook["P_6_1_1_10"].iter_rows(values_only=True)]
    workbook.close()
    header = next(i for i, row in enumerate(rows) if row and str(row[0]).strip() == "PROVINCIAS")
    records = []
    for row in rows[header + 1 :]:
        if not row or row[0] is None:
            continue
        name = " ".join(str(row[0]).split())
        records.append(
            {
                "province": name,
                "is_total": name.lower() == "total",
                "drivers_excluding_licences": row[3],
                "licence_only": row[6],
                "men": row[7],
                "women": row[8],
                "total": row[9],
                "source_sheet": "P_6_1_1_10",
            }
        )
    out = pd.DataFrame.from_records(records)
    for column in ("drivers_excluding_licences", "licence_only", "men", "women", "total"):
        out[column] = pd.to_numeric(out[column]).astype("int64")
    return out.astype({"province": "string", "source_sheet": "string"})


def read_km_mean_2022() -> pd.DataFrame:
    """Fleet size and mean annual km by vehicle type and age band for 2022, plus vehicle-km."""
    workbook = openpyxl.load_workbook(KM_MEAN_2022_PATH, read_only=True, data_only=True)
    rows = [tuple(row) for row in workbook["Hoja1"].iter_rows(values_only=True)]
    workbook.close()
    band_row = next(i for i, row in enumerate(rows) if row and row[1] == "De 0 a 4 años")
    bands = [cell for cell in rows[band_row][1:] if cell is not None]
    records = []
    for row in rows[band_row + 1 :]:
        if not row or row[0] not in KM_VEHICLE_TYPES:
            continue
        for index, band in enumerate(bands):
            n_vehicles = row[1 + 2 * index]
            mean_km = row[2 + 2 * index]
            records.append(
                {
                    "year": 2022,
                    "vehicle_type": row[0],
                    "age_band": band,
                    "n_vehicles": int(n_vehicles),
                    "mean_km_year": float(mean_km),
                    "vehicle_km": int(n_vehicles) * float(mean_km),
                    "source_sheet": "Hoja1",
                }
            )
    out = pd.DataFrame.from_records(records)
    if len(out) != len(KM_VEHICLE_TYPES) * len(bands):
        raise ValueError("km mean table: unexpected number of strata")
    return out.astype(
        {"year": "int16", "vehicle_type": "string", "age_band": "string", "source_sheet": "string"}
    )


def read_km_estimated_2022() -> pd.DataFrame:
    """Estimated annual km per vehicle by stratum, all six vehicle-type sheets stacked."""
    workbook = openpyxl.load_workbook(KM_ESTIMATED_2022_PATH, read_only=True, data_only=True)
    frames = []
    for sheet in workbook.worksheets:
        rows = sheet.iter_rows(values_only=True)
        header = [str(cell).strip() for cell in next(rows)]
        records = [row for row in rows if any(cell is not None for cell in row)]
        frame = pd.DataFrame.from_records(records, columns=header)
        frame["source_sheet"] = sheet.title
        frames.append(frame)
    workbook.close()
    out = pd.concat(frames, ignore_index=True)
    out = out.rename(
        columns={
            "FECHA PARQUE": "year",
            "TIPO_VEHICULO": "vehicle_type",
            "EMISIONES_NORM": "emission_standard",
            "ANTIGUEDAD": "age_band",
            "CILINDRADA": "engine_size",
            "CARGA": "payload",
            "DESC_PROPULSION": "fuel",
            "kmRecorridos": "km_year",
        }
    )
    out["year"] = pd.to_numeric(out["year"]).astype("int16")
    out["km_year"] = pd.to_numeric(out["km_year"]).astype("float64")
    for column in (
        "vehicle_type",
        "emission_standard",
        "age_band",
        "engine_size",
        "payload",
        "fuel",
    ):
        out[column] = out[column].astype("string").str.strip()
    return out


EXPOSURE_BUILDERS = {
    "censo_conductores": read_census_all,
    "censo_provincias_2025": read_census_province_totals_2025,
    "km_medios_2022": read_km_mean_2022,
    "km_estimados_2022": read_km_estimated_2022,
}


def interim_path(name: str) -> Path:
    return INTERIM_DATA_DIR / f"{name}.parquet"


def build_exposure(force: bool = False) -> list[Path]:
    written: list[Path] = []
    INTERIM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, builder in EXPOSURE_BUILDERS.items():
        target = interim_path(name)
        if target.exists() and not force:
            log.info("exposure %s: exists, skipping", name)
            written.append(target)
            continue
        frame = builder()
        frame.to_parquet(target, index=False)
        log.info("exposure %s: %s rows -> %s", name, f"{len(frame):,}", target.name)
        written.append(target)
    return written


def read_exposure(name: str) -> pd.DataFrame:
    return pd.read_parquet(interim_path(name))
