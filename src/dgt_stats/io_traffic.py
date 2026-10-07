"""Monthly road-traffic exposure series: CORES fuel consumption and state toll-motorway traffic.

The death series the policy case study fits is monthly, so an exposure control for it has to be
monthly too. Two published Spanish series are monthly and reach back past 2006:

* **CORES** (*Corporación de Reservas Estratégicas de Productos Petrolíferos*, the body that keeps
  Spain's compulsory oil stocks and publishes the official petroleum statistics under Ley 34/1998)
  reports consumption in tonnes by product and month from January 1996. Adding the two automotive
  subtotals, ``Subtotal gasolinas auto`` and ``Subtotal gasóleos auto``, gives national road-fuel
  consumption, which covers all roads and all vehicles. Each subtotal is the sum of its products,
  the bioethanol, biodiesel and blends among them, which the reader checks; the biofuel blended
  into ordinary petrol and diesel is inside those products, and CORES publishes its share of each
  subtotal by mass.
* The **Ministerio de Transportes** publishes monthly average daily intensity and
  vehicle-kilometres on the network of state toll motorways from January 1990. That is a direct
  measurement of traffic, but on 1,400-2,500 km of motorway rather than on the roads where most
  deaths happen, and the network itself changes as concessions expire.

Neither is vehicle-kilometres on all Spanish roads by month, which does not exist. What each is
and is not is set out in ``docs/methodology.md`` §§4–6, §11 (the forecasting model) and §15 (the
2006 case study); here they are only parsed.

A third series is annual and measured: the Ministerio de Transportes' yearbook table 1.2.14 gives
vehicle-kilometres on the whole interurban network of the State, the regions and the provincial
councils, by type of road, from 2004, built from the traffic-count plans of each network. It
leaves out interurban roads run by municipalities, which the Ministry puts at up to a tenth of
traffic, and it is not comparable across 2007–2008, when the road inventory was redone. It is
used in §5 (interurban deaths per measured kilometre) and by ``road_class`` (deaths per measured
kilometre on motorways and conventional roads).
"""

from __future__ import annotations

import re

import pandas as pd
import pymupdf

from dgt_stats.paths import CORES_FUEL_PATH, ROAD_TRAFFIC_PATH, TOLL_TRAFFIC_PATH

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
MONTH_ABBREVIATIONS = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}

CORES_SHEETS = {
    "Gasolinas": "Subtotal gasolinas auto",
    "Gasoleos": "Subtotal gasóleos auto",
}
CORES_COLUMNS = {"Gasolinas": "petrol_tonnes", "Gasoleos": "diesel_tonnes"}
CORES_BIO_LABELS = {"Gasolinas": "% biocomb. en gasolinas", "Gasoleos": "% biocomb. en gasóleos"}
CORES_BIO_COLUMNS = {"Gasolinas": "petrol_bio_share", "Gasoleos": "diesel_bio_share"}


def _text(value: object) -> str:
    return "" if pd.isna(value) else " ".join(str(value).split())


def _cores_sheet(sheet: str) -> pd.DataFrame:
    """One CORES sheet as ``year``, ``month``, tonnes of the automotive subtotal, and bio share.

    The subtotal must equal the sum of the product columns before it (biofuels included) in every
    month, to one part in a million.
    """
    frame = pd.read_excel(CORES_FUEL_PATH, sheet_name=sheet, header=None)
    header_rows = frame.index[frame[0].map(_text) == "Año"]
    if len(header_rows) != 1:
        raise ValueError(f"CORES {sheet}: expected one 'Año' header row, found {len(header_rows)}")
    header = int(header_rows[0])
    labels = [_text(value) for value in frame.iloc[header]]
    wanted = CORES_SHEETS[sheet]
    if wanted not in labels:
        raise ValueError(f"CORES {sheet}: column {wanted!r} not found in {labels}")
    column = labels.index(wanted)
    above = [_text(value) for value in frame.iloc[header - 1]]
    if CORES_BIO_LABELS[sheet] not in above:
        raise ValueError(f"CORES {sheet}: column {CORES_BIO_LABELS[sheet]!r} not found")
    bio = above.index(CORES_BIO_LABELS[sheet])
    body = frame.iloc[header + 1 :].copy()
    body["month"] = body[1].map(lambda value: SPANISH_MONTHS.get(_text(value).lower()))
    body = body[body.month.notna() & body[0].notna()]
    subtotal = pd.to_numeric(body[column], errors="coerce")
    products = body[list(range(2, column))].apply(pd.to_numeric, errors="coerce")
    gap = ((products.fillna(0).sum(axis=1) - subtotal).abs() / subtotal)[subtotal.notna()]
    if (gap > 1e-6).any():
        raise ValueError(f"CORES {sheet}: {wanted!r} is not the sum of its products")
    out = pd.DataFrame(
        {
            "year": pd.to_numeric(body[0], errors="coerce").astype("Int64"),
            "month": body.month.astype("int8"),
            CORES_COLUMNS[sheet]: subtotal,
            CORES_BIO_COLUMNS[sheet]: pd.to_numeric(body[bio], errors="coerce"),
        }
    )
    out = out[out.year.notna()]
    return out.astype({"year": "int16"}).reset_index(drop=True)


def read_cores_fuel() -> pd.DataFrame:
    """Monthly Spanish road-fuel consumption in tonnes, from January 1996.

    Columns: ``year``, ``month``, ``period``, ``petrol_tonnes``, ``diesel_tonnes``,
    ``road_fuel_tonnes``, and ``petrol_bio_share`` and ``diesel_bio_share``, the published mass
    share of biofuel in each subtotal (empty before CORES reports it). Months with an empty cell in
    either subtotal (the most recent month of one product before the other is published) are
    dropped, so the series ends where both do.
    """
    petrol = _cores_sheet("Gasolinas")
    diesel = _cores_sheet("Gasoleos")
    out = petrol.merge(diesel, on=["year", "month"], how="inner", validate="one_to_one")
    out = out.dropna(subset=["petrol_tonnes", "diesel_tonnes"])
    out["road_fuel_tonnes"] = out.petrol_tonnes + out.diesel_tonnes
    out["period"] = pd.to_datetime(pd.DataFrame({"year": out.year, "month": out.month, "day": 1}))
    out = out.sort_values("period").reset_index(drop=True)
    expected = pd.date_range(out.period.min(), out.period.max(), freq="MS")
    if not out.period.equals(pd.Series(expected)):
        raise ValueError("CORES: the monthly series has gaps or duplicates")
    return out[
        [
            "period",
            "year",
            "month",
            "petrol_tonnes",
            "diesel_tonnes",
            "road_fuel_tonnes",
            "petrol_bio_share",
            "diesel_bio_share",
        ]
    ]


def read_toll_traffic() -> pd.DataFrame:
    """Monthly traffic on the state toll-motorway network, from January 1990.

    Columns: ``period``, ``year``, ``month``, ``network_km`` (the length in service that month),
    ``imd`` (average daily intensity, vehicles) and ``veh_km_millions``. The workbook lists annual
    rows first and then monthly rows, the year appearing only on each December; both are parsed and
    only the monthly block is returned.
    """
    frame = pd.read_excel(TOLL_TRAFFIC_PATH, sheet_name=0, header=None)
    records: list[dict[str, object]] = []
    year: int | None = None
    for row in frame.itertuples(index=False):
        label = _text(row[0])
        if not label:
            continue
        parts = label.split()
        month: int | None = None
        if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 4:
            year = int(parts[0])
            month = MONTH_ABBREVIATIONS.get(parts[1][:3].lower())
        elif len(parts) == 1:
            month = MONTH_ABBREVIATIONS.get(parts[0][:3].lower())
        if month is None or year is None:
            continue
        records.append(
            {
                "year": year,
                "month": month,
                "network_km": pd.to_numeric(row[1], errors="coerce"),
                "imd": pd.to_numeric(row[2], errors="coerce"),
                "veh_km_millions": pd.to_numeric(row[6], errors="coerce"),
            }
        )
    out = pd.DataFrame.from_records(records)
    if out.empty:
        raise ValueError("toll traffic: no monthly rows parsed")
    out = out.dropna(subset=["imd", "veh_km_millions"])
    out["period"] = pd.to_datetime(pd.DataFrame({"year": out.year, "month": out.month, "day": 1}))
    out = out.sort_values("period").drop_duplicates("period").reset_index(drop=True)
    expected = pd.date_range(out.period.min(), out.period.max(), freq="MS")
    if not out.period.equals(pd.Series(expected)):
        raise ValueError("toll traffic: the monthly series has gaps")
    return out.astype({"year": "int16", "month": "int8"})[
        ["period", "year", "month", "network_km", "imd", "veh_km_millions"]
    ]


ROAD_TRAFFIC_TABLE = "TABLA 1.2.14"
ROAD_TRAFFIC_TITLE = "TRÁFICO EN EL CONJUNTO DE LAS REDES DE CARRETERAS POR TIPO DE VÍA"
ROAD_TRAFFIC_COLUMNS = (
    "toll_motorway",
    "autovia_free_motorway",
    "multilane",
    "conventional",
)
# The yearbook's footnote (3): the 2008 figures follow a new road inventory and are not
# comparable with the years before.
ROAD_TRAFFIC_BREAK_YEAR = 2008
_ROW = re.compile(r"^(\d{4})(?: \(3\))?$")


def _spanish_number(text: str) -> float:
    return float(text.replace(".", "").replace(",", "."))


def read_road_traffic() -> pd.DataFrame:
    """Annual vehicle-kilometres on the interurban network by type of road, from 2004.

    Columns: ``year``, one column per road type in millions of vehicle-km (toll motorways;
    autovías and free motorways; multi-lane roads; conventional roads), the share of heavy
    vehicles on each type (``<type>_heavy_share``), ``total`` and the heavy share of the whole
    network. Every year from the first to the last must be present,
    and the four types must add up to the published total within one part in ten thousand: more
    than the table's rounding, because the published 2009 row is itself 5 million short.
    """
    document = pymupdf.open(ROAD_TRAFFIC_PATH)
    lines: list[str] | None = None
    for page in document:
        text = page.get_text()
        if ROAD_TRAFFIC_TITLE in text and ROAD_TRAFFIC_TABLE in text:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            break
    if lines is None:
        raise ValueError(f"road traffic: {ROAD_TRAFFIC_TABLE} not found in {ROAD_TRAFFIC_PATH}")
    records = []
    for index, line in enumerate(lines):
        match = _ROW.match(line)
        if not match:
            continue
        cells = lines[index + 1 : index + 11]
        try:
            values = [_spanish_number(cell) for cell in cells]
        except ValueError:
            continue
        records.append(
            {
                "year": int(match.group(1)),
                **{name: values[2 * i] for i, name in enumerate(ROAD_TRAFFIC_COLUMNS)},
                **{
                    f"{name}_heavy_share": values[2 * i + 1] / 100
                    for i, name in enumerate(ROAD_TRAFFIC_COLUMNS)
                },
                "total": values[8],
                "heavy_share": values[9] / 100,
            }
        )
    out = pd.DataFrame.from_records(records).drop_duplicates("year").sort_values("year")
    if out.empty:
        raise ValueError("road traffic: no rows parsed")
    if list(out.year) != list(range(int(out.year.min()), int(out.year.max()) + 1)):
        raise ValueError("road traffic: the annual series has gaps")
    gap = (out[list(ROAD_TRAFFIC_COLUMNS)].sum(axis=1) - out.total).abs() / out.total
    if (gap > 1e-4).any():
        bad = list(out.year[gap > 1e-4])
        raise ValueError(f"road traffic: types do not add up to the total in {bad}")
    return out.reset_index(drop=True)
