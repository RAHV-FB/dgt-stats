"""Shared project paths and file-location helpers."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

RAW_MICRODATA_DIR = RAW_DATA_DIR / "microdata"
RAW_TABLES_DIR = RAW_DATA_DIR / "tables"
RAW_EXPOSURE_DIR = RAW_DATA_DIR / "exposure"
RAW_REPORTS_DIR = RAW_DATA_DIR / "reports"
MANIFEST = RAW_DATA_DIR / "manifest.csv"

INTERIM_MICRODATA_DIR = INTERIM_DATA_DIR / "microdata"

REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
TABLES_DIR = REPORTS_DIR / "tables"

DICTIONARY_PATH = RAW_MICRODATA_DIR / "diccionario.xlsx"
SERIES_PATH = RAW_TABLES_DIR / "series_historicas_2024.xlsx"
TABLES_2024_PATH = RAW_TABLES_DIR / "tablas_estadisticas_2024.xlsx"
CENSUS_TABLES_2025_PATH = RAW_EXPOSURE_DIR / "censo_tablas_2025.xlsx"
KM_MEAN_2022_PATH = RAW_EXPOSURE_DIR / "km_itv_2022" / "media_km_antiguedad_tipo_2022.xlsx"
KM_ESTIMATED_2022_PATH = RAW_EXPOSURE_DIR / "km_itv_2022" / "km_recorridos_estimados_2022.xlsx"

MICRODATA_YEARS = tuple(range(2016, 2025))
CENSUS_YEARS = (2023, 2024, 2025)


def microdata_raw_path(year: int) -> Path:
    """Raw DGT crash workbook for one year."""
    return RAW_MICRODATA_DIR / f"accidentes_{year}.xlsx"


def microdata_interim_path(year: int) -> Path:
    """Harmonised Parquet file for one year of crash microdata."""
    return INTERIM_MICRODATA_DIR / f"accidentes_{year}.parquet"


def census_raw_path(year: int) -> Path:
    """Raw pipe-delimited driver census extract for one year."""
    return RAW_EXPOSURE_DIR / f"censo_conductores_{year}.txt"
