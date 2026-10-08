"""Download INE resident population tables and keep small extracts under data/raw/ine.

Sources: INE, Estadística Continua de Población.

* ``provinces``: table 56947 "Población residente por fecha, sexo, grupo de edad y nacionalidad
  (agrupación de países)", provincial level, 2002 onwards, quarterly reference dates. The full
  CSV is about 330 MB; the extract keeps nationality = Total and the 1 January and 1 July
  reference dates only (about 11 MB).
* ``single_age``: table 56934 "Población residente por fecha, sexo y edad", Spain, single years
  of age, 1971 onwards, quarterly. The extract keeps the 1 January and 1 July reference dates
  from 2002 (about 1 MB). It lets an age group start at 16 or 18 without splitting a five-year
  group.

Usage:
    python scripts/fetch_ine.py                                  # download and extract both
    python scripts/fetch_ine.py --table single_age               # one table
    python scripts/fetch_ine.py --table provinces --from-file X  # filter a downloaded CSV
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dgt_stats.paths import RAW_INE_DIR  # noqa: E402

log = logging.getLogger("fetch_ine")

TABLE_ID = 56947
SINGLE_AGE_TABLE_ID = 56934
TARGET = RAW_INE_DIR / "ine_poblacion_provincias_edad_sexo.csv"
SINGLE_AGE_TARGET = RAW_INE_DIR / "ine_poblacion_edad_simple_sexo.csv"
REFERENCES = {"1 de enero": "1 January", "1 de julio": "1 July"}
FIRST_SINGLE_AGE_YEAR = 2002


def source_url(table_id: int) -> str:
    return f"https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/{table_id}.csv?nocab=1"


def download(target: Path, table_id: int = TABLE_ID) -> Path:
    url = source_url(table_id)
    log.info("downloading %s", url)
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=600) as response, target.open("wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    log.info(
        "downloaded %.0f MB in %.0f s", target.stat().st_size / 1e6, time.perf_counter() - started
    )
    return target


def extract(source: Path, target: Path = TARGET) -> pd.DataFrame:
    kept = []
    for chunk in pd.read_csv(source, sep=";", encoding="utf-8-sig", dtype=str, chunksize=500_000):
        mask = (chunk["Nacionalidad"] == "Total") & chunk["Periodo"].str.startswith(
            tuple(REFERENCES)
        )
        kept.append(chunk[mask])
    frame = pd.concat(kept, ignore_index=True)
    frame["population"] = frame["Total"].str.replace(".", "", regex=False).astype("int64")
    frame["year"] = frame["Periodo"].str.extract(r"(\d{4})").astype(int)
    frame["reference"] = frame["Periodo"].str.extract(r"^(1 de \w+)")[0].map(REFERENCES)
    out = frame.rename(
        columns={"Provincias": "province", "Grupo quinquenal de edad": "age_group", "Sexo": "sex"}
    )[["province", "age_group", "sex", "reference", "year", "Periodo", "population"]]
    out = out.sort_values(["reference", "year", "province", "age_group", "sex"]).reset_index(
        drop=True
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(target, index=False)
    log.info("wrote %s rows to %s", f"{len(out):,}", target)
    return out


def extract_single_age(source: Path, target: Path = SINGLE_AGE_TARGET) -> pd.DataFrame:
    frame = pd.read_csv(source, sep=";", encoding="utf-8-sig", dtype=str)
    frame = frame[frame["Periodo"].str.startswith(tuple(REFERENCES))].copy()
    frame["year"] = frame["Periodo"].str.extract(r"(\d{4})")[0].astype(int)
    frame = frame[frame.year >= FIRST_SINGLE_AGE_YEAR].copy()
    # INE leaves "105 y más años" blank before 2012; it stays blank (missing) here.
    digits = frame["Total"].str.replace(".", "", regex=False)
    frame["population"] = pd.to_numeric(digits, errors="raise").astype("Int64")
    frame["reference"] = frame["Periodo"].str.extract(r"^(1 de \w+)")[0].map(REFERENCES)
    out = frame.rename(columns={"Edad simple": "age", "Sexo": "sex"})[
        ["age", "sex", "reference", "year", "Periodo", "population"]
    ]
    out = out.sort_values(["reference", "year", "sex", "age"]).reset_index(drop=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(target, index=False)
    log.info("wrote %s rows to %s", f"{len(out):,}", target)
    return out


TABLES = {"provinces": (TABLE_ID, extract), "single_age": (SINGLE_AGE_TABLE_ID, extract_single_age)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", choices=tuple(TABLES), help="one table only (default: both)")
    parser.add_argument("--from-file", type=Path, help="filter this CSV instead of downloading")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    names = [args.table] if args.table else list(TABLES)
    if args.from_file:
        if len(names) != 1:
            parser.error("--from-file needs --table")
        TABLES[names[0]][1](args.from_file)
        return 0
    for name in names:
        table_id, extractor = TABLES[name]
        with tempfile.TemporaryDirectory() as tmp:
            extractor(download(Path(tmp) / f"ine_{table_id}.csv", table_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
