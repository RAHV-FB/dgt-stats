"""Read the yearly DGT crash workbooks and write a harmonised Parquet layer.

The nine raw workbooks (2016–2024) share one record layout with three differences that this module
absorbs: the identifier column was called ``SECUENCIAL`` until 2020 and ``ID_ACCIDENTE`` from 2021,
``TOT_VMP_MU30DF`` (personal-mobility-vehicle deaths) exists only from 2020, and ``TOT_VMP_MU24H``
exists only in 2020. Codes are kept as they are; decoding happens later with :mod:`dgt_stats.codes`.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import openpyxl
import pandas as pd

from dgt_stats.paths import (
    INTERIM_MICRODATA_DIR,
    MICRODATA_YEARS,
    microdata_interim_path,
    microdata_raw_path,
)

log = logging.getLogger(__name__)

ID_COLUMN = "ID_ACCIDENTE"
LEGACY_ID_COLUMN = "SECUENCIAL"

CANONICAL_COLUMNS: tuple[str, ...] = (
    "ID_ACCIDENTE",
    "ANYO",
    "MES",
    "DIA_SEMANA",
    "HORA",
    "COD_PROVINCIA",
    "COD_MUNICIPIO",
    "ISLA",
    "ZONA",
    "ZONA_AGRUPADA",
    "CARRETERA",
    "KM",
    "SENTIDO_1F",
    "TITULARIDAD_VIA",
    "TIPO_VIA",
    "TIPO_ACCIDENTE",
    "TOTAL_MU24H",
    "TOTAL_HG24H",
    "TOTAL_HL24H",
    "TOTAL_VICTIMAS_24H",
    "TOTAL_MU30DF",
    "TOTAL_HG30DF",
    "TOTAL_HL30DF",
    "TOTAL_VICTIMAS_30DF",
    "TOTAL_VEHICULOS",
    "TOT_PEAT_MU24H",
    "TOT_BICI_MU24H",
    "TOT_CICLO_MU24H",
    "TOT_MOTO_MU24H",
    "TOT_TUR_MU24H",
    "TOT_FURG_MU24H",
    "TOT_CAM_MENOS3500_MU24H",
    "TOT_CAM_MAS3500_MU24H",
    "TOT_BUS_MU24H",
    "TOT_VMP_MU24H",
    "TOT_OTRO_MU24H",
    "TOT_SINESPECIF_MU24H",
    "TOT_PEAT_MU30DF",
    "TOT_BICI_MU30DF",
    "TOT_CICLO_MU30DF",
    "TOT_MOTO_MU30DF",
    "TOT_TUR_MU30DF",
    "TOT_FURG_MU30DF",
    "TOT_CAM_MENOS3500_MU30DF",
    "TOT_CAM_MAS3500_MU30DF",
    "TOT_BUS_MU30DF",
    "TOT_VMP_MU30DF",
    "TOT_OTRO_MU30DF",
    "TOT_SINESPECIF_MU30DF",
    "NUDO",
    "NUDO_INFO",
    "CARRETERA_CRUCE",
    "PRIORI_NORMA",
    "PRIORI_AGENTE",
    "PRIORI_SEMAFORO",
    "PRIORI_VERT_STOP",
    "PRIORI_VERT_CEDA",
    "PRIORI_HORIZ_STOP",
    "PRIORI_HORIZ_CEDA",
    "PRIORI_MARCAS",
    "PRIORI_PEA_NO_ELEV",
    "PRIORI_PEA_ELEV",
    "PRIORI_MARCA_CICLOS",
    "PRIORI_CIRCUNSTANCIAL",
    "PRIORI_OTRA",
    "CONDICION_NIVEL_CIRCULA",
    "CONDICION_FIRME",
    "CONDICION_ILUMINACION",
    "CONDICION_METEO",
    "CONDICION_NIEBLA",
    "CONDICION_VIENTO",
    "VISIB_RESTRINGIDA_POR",
    "ACERA",
    "TRAZADO_PLANTA",
)

# Columns that only exist in some years; they are added as all-missing elsewhere.
OPTIONAL_COLUMNS: tuple[str, ...] = ("TOT_VMP_MU24H", "TOT_VMP_MU30DF")

STRING_COLUMNS: tuple[str, ...] = (
    "COD_MUNICIPIO",
    "CARRETERA",
    "CARRETERA_CRUCE",
    "CONDICION_VIENTO",
)
FLOAT_COLUMNS: tuple[str, ...] = ("KM",)
INT32_COLUMNS: tuple[str, ...] = ("ID_ACCIDENTE", "ANYO")

COUNT_COLUMNS: tuple[str, ...] = tuple(
    column for column in CANONICAL_COLUMNS if column.startswith(("TOTAL_", "TOT_"))
)
CODE_COLUMNS: tuple[str, ...] = tuple(
    column
    for column in CANONICAL_COLUMNS
    if column not in STRING_COLUMNS + FLOAT_COLUMNS + INT32_COLUMNS + COUNT_COLUMNS
)


def read_raw_year(year: int) -> pd.DataFrame:
    """Load one raw workbook as an object-dtype frame with the original column names."""
    path = microdata_raw_path(year)
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.worksheets[0]
    rows = sheet.iter_rows(values_only=True)
    header = [str(cell).strip() for cell in next(rows)]
    records = [row for row in rows if any(cell is not None for cell in row)]
    workbook.close()
    return pd.DataFrame.from_records(records, columns=header)


def _clean_text(series: pd.Series) -> pd.Series:
    """Trim text, turn blanks into missing and keep whole numbers free of a trailing '.0'."""
    values = series.map(
        lambda v: (
            str(int(v))
            if isinstance(v, (int, float)) and not pd.isna(v) and float(v).is_integer()
            else v
        )
    )
    text = values.astype("string").str.strip()
    return text.mask(text == "", pd.NA)


def harmonise(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Return ``df`` with canonical column names, order and dtypes for ``year``."""
    out = df.copy()
    if LEGACY_ID_COLUMN in out.columns:
        out = out.rename(columns={LEGACY_ID_COLUMN: ID_COLUMN})
    for column in OPTIONAL_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA
    unexpected = sorted(set(out.columns) - set(CANONICAL_COLUMNS))
    missing = sorted(set(CANONICAL_COLUMNS) - set(out.columns))
    if unexpected or missing:
        raise ValueError(f"{year}: unexpected columns {unexpected}, missing columns {missing}")
    out = out[list(CANONICAL_COLUMNS)]

    for column in STRING_COLUMNS:
        out[column] = _clean_text(out[column])
    for column in FLOAT_COLUMNS:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("float32")
    for column in INT32_COLUMNS:
        out[column] = pd.to_numeric(out[column]).astype("int32")
    for column in COUNT_COLUMNS:
        out[column] = pd.to_numeric(out[column]).astype("Int16")
    for column in CODE_COLUMNS:
        out[column] = pd.to_numeric(out[column]).astype("Int16")

    if not (out["ANYO"] == year).all():
        raise ValueError(f"{year}: ANYO column contains other years")
    return out.reset_index(drop=True)


def write_interim(year: int, force: bool = False) -> Path:
    """Convert one year to Parquet; skip when the file exists unless ``force``."""
    target = microdata_interim_path(year)
    if target.exists() and not force:
        log.info("microdata %s: exists, skipping (%s)", year, target.name)
        return target
    started = time.perf_counter()
    frame = harmonise(read_raw_year(year), year)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(target, index=False)
    log.info(
        "microdata %s: %s rows -> %s (%.1f MB, %.1f s)",
        year,
        f"{len(frame):,}",
        target.name,
        target.stat().st_size / 1e6,
        time.perf_counter() - started,
    )
    return target


def read_interim_year(year: int) -> pd.DataFrame:
    return pd.read_parquet(microdata_interim_path(year))


def all_years_path() -> Path:
    return INTERIM_MICRODATA_DIR / "accidentes_all.parquet"


def build_all(years: tuple[int, ...] = MICRODATA_YEARS, force: bool = False) -> Path:
    """Write the requested years, then stack every available year into ``accidentes_all.parquet``.

    The stacked file always covers all of :data:`MICRODATA_YEARS`, so rebuilding a single year with
    ``--years`` never drops the others; a year whose Parquet file is missing is built on the spot.
    """
    for year in years:
        write_interim(year, force=force)
    for year in MICRODATA_YEARS:
        if not microdata_interim_path(year).exists():
            write_interim(year)
    frames = [read_interim_year(year) for year in MICRODATA_YEARS]
    stacked = pd.concat(frames, ignore_index=True)
    target = all_years_path()
    stacked.to_parquet(target, index=False)
    log.info(
        "microdata all: %s rows, %s columns -> %s",
        f"{len(stacked):,}",
        stacked.shape[1],
        target.name,
    )
    return target


def read_all() -> pd.DataFrame:
    return pd.read_parquet(all_years_path())
