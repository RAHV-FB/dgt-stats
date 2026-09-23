"""Monthly road-traffic exposure series: CORES fuel consumption and state toll-motorway traffic.

The death series the policy case study fits is monthly, so an exposure control for it has to be
monthly too. Two published Spanish series are monthly and reach back past 2006:

* **CORES** (*Corporación de Reservas Estratégicas de Productos Petrolíferos*, the body that keeps
  Spain's compulsory oil stocks and publishes the official petroleum statistics under Ley 34/1998)
  reports consumption in tonnes by product and month from January 1996. Adding the two automotive
  subtotals, ``Subtotal gasolinas auto`` and ``Subtotal gasóleos auto``, gives national road-fuel
  consumption, which covers all roads and all vehicles.
* The **Ministerio de Transportes** publishes monthly average daily intensity and
  vehicle-kilometres on the network of state toll motorways from January 1990. That is a direct
  measurement of traffic, but on 1,400-2,500 km of motorway rather than on the roads where most
  deaths happen, and the network itself changes as concessions expire.

Neither is vehicle-kilometres on all Spanish roads by month, which does not exist. What each is
and is not is set out in ``docs/methodology.md`` §§4–6 and §12; here they are only parsed.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats.paths import CORES_FUEL_PATH, TOLL_TRAFFIC_PATH

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


def _text(value: object) -> str:
    return "" if pd.isna(value) else " ".join(str(value).split())


def _cores_sheet(sheet: str) -> pd.DataFrame:
    """One CORES sheet as ``year``, ``month``, tonnes of the automotive subtotal."""
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
    body = frame.iloc[header + 1 :].copy()
    body["month"] = body[1].map(lambda value: SPANISH_MONTHS.get(_text(value).lower()))
    body = body[body.month.notna() & body[0].notna()]
    out = pd.DataFrame(
        {
            "year": pd.to_numeric(body[0], errors="coerce").astype("Int64"),
            "month": body.month.astype("int8"),
            CORES_COLUMNS[sheet]: pd.to_numeric(body[column], errors="coerce"),
        }
    )
    out = out[out.year.notna()]
    return out.astype({"year": "int16"}).reset_index(drop=True)


def read_cores_fuel() -> pd.DataFrame:
    """Monthly Spanish road-fuel consumption in tonnes, from January 1996.

    Columns: ``year``, ``month``, ``period``, ``petrol_tonnes``, ``diesel_tonnes``,
    ``road_fuel_tonnes``. Months with an empty cell in either subtotal (the most recent month of
    one product before the other is published) are dropped, so the series ends where both do.
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
    return out[["period", "year", "month", "petrol_tonnes", "diesel_tonnes", "road_fuel_tonnes"]]


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
