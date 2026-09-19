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
POPULATION_PATH = RAW_EXPOSURE_DIR / "ine_poblacion_provincias_edad_sexo.csv"
DRIVING_ACTIVITY_PATH = RAW_EXPOSURE_DIR / "driving_activity_by_age.csv"
MOVILIA_2006_PATH = RAW_EXPOSURE_DIR / "movilia_2006.xls"
MOVILIA_2007_PATH = RAW_EXPOSURE_DIR / "movilia_2007.xls"
ECEPOV_2021_PATH = RAW_EXPOSURE_DIR / "ine_ecepov_2021_55378.xlsx"
EHMA_2008_KM_BY_FUEL_PATH = RAW_EXPOSURE_DIR / "ine_ehma_2008_10016.csv"
EHMA_2008_KM_BY_VEHICLE_AGE_PATH = RAW_EXPOSURE_DIR / "ine_ehma_2008_10019.csv"

MICRODATA_YEARS = tuple(range(2016, 2025))
CENSUS_YEARS = (2023, 2024, 2025)
CENSUS_AGE_YEARS = (2023, 2024, 2025)
CENSUS_TABLE_YEARS = tuple(range(2014, 2026))
TABLE_YEARS = tuple(range(2014, 2025))
# Years whose statistical tables are published as one workbook per chapter (grupo_N).
TABLE_CHAPTER_YEARS = tuple(range(2014, 2020))
TABLE_CHAPTERS = tuple(range(1, 9))


def microdata_raw_path(year: int) -> Path:
    """Raw DGT crash workbook for one year."""
    return RAW_MICRODATA_DIR / f"accidentes_{year}.xlsx"


def microdata_interim_path(year: int) -> Path:
    """Harmonised Parquet file for one year of crash microdata."""
    return INTERIM_MICRODATA_DIR / f"accidentes_{year}.parquet"


def census_raw_path(year: int) -> Path:
    """Raw pipe-delimited driver census extract for one year."""
    return RAW_EXPOSURE_DIR / f"censo_conductores_{year}.txt"


def census_age_raw_path(year: int) -> Path:
    """Raw pipe-delimited driver census by province, sex and age band for one year."""
    return RAW_EXPOSURE_DIR / f"censo_conductores_edad_{year}.txt"


def census_tables_raw_path(year: int) -> Path:
    """Published driver-census tables workbook for one year (2014-2025)."""
    return RAW_EXPOSURE_DIR / f"censo_tablas_{year}.xlsx"


def tables_raw_path(year: int, chapter: int | None = None) -> Path:
    """Published crash statistics workbook for one year.

    From 2020 the DGT publishes one workbook per year; 2014-2019 have one workbook per chapter
    (``grupo_1`` ... ``grupo_8``), so ``chapter`` is required for those years. 2014 is the only
    year still in the legacy ``.xls`` format.
    """
    if year in TABLE_CHAPTER_YEARS:
        if chapter is None:
            raise ValueError(f"{year} tables are split by chapter; pass chapter=1..8")
        suffix = "xls" if year == 2014 else "xlsx"
        return RAW_TABLES_DIR / "chapters" / str(year) / f"grupo_{chapter}.{suffix}"
    return RAW_TABLES_DIR / f"tablas_estadisticas_{year}.xlsx"
