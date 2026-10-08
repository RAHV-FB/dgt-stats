"""Download the Madrid household travel survey 2018 (EDM2018) and keep small extracts.

Source: Consorcio Regional de Transportes de Madrid (CRTM), Encuesta Domiciliaria de Movilidad
2018, public microdata published as Excel workbooks on the CRTM's ArcGIS open-data site. The
workbooks hold about 31 MB; the extracts keep what the exposure analysis reads (about 4 MB):

* ``edm2018_individuos.csv``: every respondent, with sex, exact age, driving licence, activity,
  the reference weekday, the reason for not travelling and the person weight;
* ``edm2018_viajes_conductor.csv``: every trip whose main mode is car driver (codes 11-13:
  private, company or rental car), with its distance and trip weight;
* ``edm2018_codebook.csv``: the "LIBRO DE CODIGOS" sheets of both workbooks.

Licence: CRTM open-data licence (https://www.crtm.es/licencia-de-uso): reuse, commercial or not,
is allowed if the CRTM is cited as the source, "Powered by CRTM" is shown with a link to
www.crtm.es on digital platforms, and derived data are distributed under the same licence.

Usage:
    python scripts/fetch_edm.py                  # download, extract
    python scripts/fetch_edm.py --from-dir DIR   # extract from workbooks already downloaded
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import tempfile
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dgt_stats.paths import RAW_DATA_DIR  # noqa: E402

log = logging.getLogger("fetch_edm")

TARGET_DIR = RAW_DATA_DIR / "crtm" / "edm2018"
ITEMS = {
    "EDM2018INDIVIDUOS.xlsx": "07dad41b543641d3964a68851fc9ad11",
    "EDM2018VIAJES.xlsx": "6afd4db8175d4902ada0803f08ccf50e",
}
PERSON_COLUMNS = (
    "ID_HOGAR",
    "ID_IND",
    "C2SEXO",
    "EDAD_FIN",
    "ELE_G_POND",
    "C6CARNE",
    "C8ACTIV",
    "DIASEM",
    "DNOVIAJO",
    "CPMR",
    "TIPO_ENCUESTA",
)
TRIP_COLUMNS = (
    "ID_HOGAR",
    "ID_IND",
    "ID_VIAJE",
    "MODO_PRIORITARIO",
    "MOTIVO_PRIORITARIO",
    "N_ETAPAS_POR_VIAJE",
    "DISTANCIA_VIAJE",
    "ELE_G_POND_ESC2",
)
CAR_DRIVER_MODES = (11, 12, 13)


def item_url(item: str) -> str:
    return f"https://www.arcgis.com/sharing/rest/content/items/{item}/data"


def download(directory: Path) -> None:
    for name, item in ITEMS.items():
        log.info("downloading %s", item_url(item))
        with urllib.request.urlopen(item_url(item), timeout=600) as response:
            (directory / name).write_bytes(response.read())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(directory: Path, target: Path = TARGET_DIR) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name in ITEMS:
        log.info("%s sha256 %s", name, sha256(directory / name))
    people = pd.read_excel(directory / "EDM2018INDIVIDUOS.xlsx", sheet_name="INDIVIDUOS")
    people = people[list(PERSON_COLUMNS)]
    people.to_csv(target / "edm2018_individuos.csv", index=False)
    log.info("respondents: %s", f"{len(people):,}")
    trips = pd.read_excel(directory / "EDM2018VIAJES.xlsx", sheet_name="VIAJES")
    trips = trips.loc[trips.MODO_PRIORITARIO.isin(CAR_DRIVER_MODES), list(TRIP_COLUMNS)]
    trips.to_csv(target / "edm2018_viajes_conductor.csv", index=False)
    log.info("car-driver trips: %s", f"{len(trips):,}")
    books = []
    for name in ITEMS:
        book = pd.read_excel(directory / name, sheet_name="LIBRO DE CODIGOS", header=None)
        books.append(book.assign(workbook=name))
    pd.concat(books, ignore_index=True).to_csv(target / "edm2018_codebook.csv", index=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--from-dir", type=Path, help="workbooks already downloaded here")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"
    )
    if args.from_dir:
        extract(args.from_dir)
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        download(Path(tmp))
        extract(Path(tmp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
