"""Download INE resident population by province, five-year age group and sex, and keep a small extract.

Source: INE, Estadística Continua de Población, table 56947 "Población residente por fecha, sexo,
grupo de edad y nacionalidad (agrupación de países)", provincial level, 2002 onwards, quarterly
reference dates. The full CSV is about 330 MB; the extract keeps nationality = Total and the
1 January and 1 July reference dates only (about 11 MB) and is committed under data/raw/exposure.

Usage:
    python scripts/fetch_ine.py                   # download, filter, write the extract
    python scripts/fetch_ine.py --from-file X.csv # filter an already downloaded CSV
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

from dgt_stats.paths import RAW_EXPOSURE_DIR  # noqa: E402

log = logging.getLogger("fetch_ine")

TABLE_ID = 56947
SOURCE_URL = f"https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/{TABLE_ID}.csv?nocab=1"
TARGET = RAW_EXPOSURE_DIR / "ine_poblacion_provincias_edad_sexo.csv"
REFERENCES = {"1 de enero": "1 January", "1 de julio": "1 July"}


def download(target: Path) -> Path:
    log.info("downloading %s", SOURCE_URL)
    started = time.perf_counter()
    with urllib.request.urlopen(SOURCE_URL, timeout=600) as response, target.open("wb") as out:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-file", type=Path, help="filter this CSV instead of downloading")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    if args.from_file:
        extract(args.from_file)
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        extract(download(Path(tmp) / f"ine_{TABLE_ID}.csv"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
