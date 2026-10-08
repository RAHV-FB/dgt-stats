"""Shared project paths and file-location helpers.

The data directory has four layers, each produced only from the one before it:

``data/raw/<source>/``  source files byte for byte, grouped by publisher and listed with their
                         SHA-256 in ``data/raw/manifest.csv``; never edited
``data/staging/<source>/`` parsed copies with harmonised column names and types; raw values kept
``data/processed/``     validated tables at a documented unit of observation
``data/features/``      the model matrices, one row per observation, with id, target and group

Every layer but ``raw`` is rebuilt by the scripts and ignored by Git.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
STAGING_DATA_DIR = DATA_DIR / "staging"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
FEATURES_DATA_DIR = DATA_DIR / "features"

# Raw files, grouped by the body that publishes them.
RAW_DGT_DIR = RAW_DATA_DIR / "dgt"
RAW_MICRODATA_DIR = RAW_DGT_DIR / "microdata"
RAW_TABLES_DIR = RAW_DGT_DIR / "tables"
RAW_CENSUS_DIR = RAW_DGT_DIR / "census"
RAW_REPORTS_DIR = RAW_DGT_DIR / "reports"
RAW_INE_DIR = RAW_DATA_DIR / "ine"
RAW_TRANSPORTES_DIR = RAW_DATA_DIR / "transportes"
RAW_CORES_DIR = RAW_DATA_DIR / "cores"
RAW_BARCELONA_DIR = RAW_DATA_DIR / "barcelona"
RAW_CATALONIA_DIR = RAW_DATA_DIR / "catalonia"
MANIFEST = RAW_DATA_DIR / "manifest.csv"

# The national DGT layer's staging files (formerly ``data/interim``).
DGT_STAGING_DIR = STAGING_DATA_DIR / "dgt"
STAGING_MICRODATA_DIR = DGT_STAGING_DIR / "microdata"
BARCELONA_STAGING_DIR = STAGING_DATA_DIR / "barcelona"
CATALONIA_STAGING_DIR = STAGING_DATA_DIR / "catalonia"

# The processed national crash table: one row per DGT injury crash, 2016-2024.
DGT_PROCESSED_CRASHES = PROCESSED_DATA_DIR / "dgt_accidentes.parquet"

REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
# The same figures drawn for a phone's column (``plots.narrow``), which the site serves to phones.
NARROW_FIGURES_DIR = FIGURES_DIR / "narrow"
TABLES_DIR = REPORTS_DIR / "tables"
DOCS_DIR = PROJECT_ROOT / "docs"

DICTIONARY_PATH = RAW_MICRODATA_DIR / "diccionario.xlsx"
SERIES_PATH = RAW_TABLES_DIR / "series_historicas_2024.xlsx"
TABLES_2024_PATH = RAW_TABLES_DIR / "tablas_estadisticas_2024.xlsx"
CENSUS_TABLES_2025_PATH = RAW_CENSUS_DIR / "censo_tablas_2025.xlsx"
KM_MEAN_2022_PATH = RAW_DGT_DIR / "km_itv_2022" / "media_km_antiguedad_tipo_2022.xlsx"
KM_ESTIMATED_2022_PATH = RAW_DGT_DIR / "km_itv_2022" / "km_recorridos_estimados_2022.xlsx"
POPULATION_PATH = RAW_INE_DIR / "ine_poblacion_provincias_edad_sexo.csv"
KM_BY_OWNER_AGE_2024_PATH = RAW_DGT_DIR / "km_itv_2024" / "km_edad_propietario_2024.xlsx"
KM_MEAN_BY_TYPE_2024_PATH = RAW_DGT_DIR / "km_itv_2024" / "km_medios_tipo_2024.xlsx"
CORES_FUEL_PATH = RAW_CORES_DIR / "cores_consumos_pp.xlsx"
TOLL_TRAFFIC_PATH = RAW_TRANSPORTES_DIR / "peaje_trafico_total.xls"
ROAD_TRAFFIC_PATH = RAW_TRANSPORTES_DIR / "anuario_carreteras_2023.pdf"

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


def microdata_staging_path(year: int) -> Path:
    """Harmonised Parquet file for one year of DGT crash microdata."""
    return STAGING_MICRODATA_DIR / f"accidentes_{year}.parquet"


def census_raw_path(year: int) -> Path:
    """Raw pipe-delimited driver census extract for one year."""
    return RAW_CENSUS_DIR / f"censo_conductores_{year}.txt"


def census_age_raw_path(year: int) -> Path:
    """Raw pipe-delimited driver census by province, sex and age band for one year."""
    return RAW_CENSUS_DIR / f"censo_conductores_edad_{year}.txt"


def census_tables_raw_path(year: int) -> Path:
    """Published driver-census tables workbook for one year (2014-2025)."""
    return RAW_CENSUS_DIR / f"censo_tablas_{year}.xlsx"


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
