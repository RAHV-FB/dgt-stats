"""Reader for the DGT speed-factor report (``dgt_factor_velocidad_2023.pdf``).

The report's annex tables are transcribed from the PDF text: each table is a caption, a header of
years (or weekdays), and rows of a label followed by one value per header cell. Every row carries
the report's regional scope, which excludes Cataluña and País Vasco, so the figures are never added
to the yearbook tables.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from dgt_stats.paths import INTERIM_DATA_DIR, RAW_REPORTS_DIR

log = logging.getLogger(__name__)

SPEED_REPORT_PATH = RAW_REPORTS_DIR / "dgt_factor_velocidad_2023.pdf"
SPEED_REPORT_INTERIM = INTERIM_DATA_DIR / "speed_report.parquet"
REGION_SCOPE = "Spain without Cataluña and País Vasco"

WEEKDAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo", "Total")
WEEKDAY_LABELS = {
    "Lunes": "Monday",
    "Martes": "Tuesday",
    "Miércoles": "Wednesday",
    "Jueves": "Thursday",
    "Viernes": "Friday",
    "Sábado": "Saturday",
    "Domingo": "Sunday",
    "Total": "Total",
}

METRICS = (
    ("personas conductoras fallecidas", "driver_deaths"),
    ("personas conductoras heridas hospitalizadas", "driver_hospitalised"),
    ("personas conductoras heridas no hospitalizadas", "driver_non_hospitalised"),
    ("personas fallecidas", "deaths"),
    ("personas heridas hospitalizadas", "hospitalised"),
    ("personas heridas no hospitalizadas", "non_hospitalised"),
    ("porcentaje de siniestros", "crash_share"),
    ("siniestros con víctimas", "crashes"),
)
BREAKDOWNS = (
    ("factores concurrentes", "factors"),
    ("tipo de vía", "road_type"),
    ("velocidad máxima", "speed_limit"),
    ("característica funcional", "functional_class"),
    ("medio de desplazamiento", "vehicle"),
    ("caballos fiscales", "car_power"),
    ("cilindrada", "engine_size"),
    ("clase de permiso", "licence_class"),
    ("día y hora", "day_hour"),
    ("edad y sexo (hombres)", "driver_age_men"),
    ("edad y sexo (mujeres)", "driver_age_women"),
    ("edad", "driver_age"),
)
ZONES = (
    ("vías urbanas e interurbanas", "all"),
    ("vías interurbanas", "interurban"),
    ("vías urbanas", "urban"),
)

_NUMBER = re.compile(r"^-?\d{1,3}(\.\d{3})*$|^-?\d+$")
_PERCENT = re.compile(r"^-?\d+(,\d+)?%$")
_YEAR = re.compile(r"^(19|20)\d{2}$")
_CAPTION = re.compile(r"^Tabla\s+(\d+):\s*(.*)$")


@dataclass
class _Table:
    number: int
    caption: str
    header: list[str] = field(default_factory=list)
    rows: list[tuple[str, list[float | None]]] = field(default_factory=list)
    unit: str = "count"
    sex: str = ""  # "men" or "women" when the header cell glued to the first label says so


def _value(token: str) -> float | None:
    if token in {"n.d.", "n.d", "-", "–"}:
        return None
    if _PERCENT.match(token):
        return float(token.rstrip("%").replace(",", ".")) / 100
    return float(token.replace(".", ""))


def _is_value(token: str) -> bool:
    return bool(_NUMBER.match(token) or _PERCENT.match(token)) or token in {"n.d.", "n.d"}


LABEL_PREFIXES = ("Hombres ", "Mujeres ", "Velocidad máxima ")


def _clean_label(label: str) -> str:
    """Drop the header cell the text extraction glues to the first row label of some tables."""
    for prefix in LABEL_PREFIXES:
        if label.startswith(prefix):
            label = label[len(prefix) :]
    return "Total" if label == "Total*" else label


def _is_prose(token: str) -> bool:
    return (
        len(token) > 45
        or token.startswith("(")
        or token.startswith("Tabla ")
        or token.startswith("Factor Velocidad")
        or token.startswith("Gráfico")
    )


def _classify(caption: str, patterns: tuple[tuple[str, str], ...], default: str) -> str:
    text = caption.lower()
    for pattern, name in patterns:
        if pattern in text:
            return name
    return default


def _parse_table(lines: list[str], start: int) -> tuple[_Table | None, int]:
    """Parse the table whose caption starts at ``lines[start]``; return it and the next index."""
    match = _CAPTION.match(lines[start])
    if match is None:
        return None, start + 1
    number = int(match.group(1))
    caption = [match.group(2).strip()]
    index = start + 1
    while index < len(lines) and not (
        _YEAR.match(lines[index]) or lines[index] in WEEKDAYS or lines[index] == ""
    ):
        caption.append(lines[index])
        index += 1
        if caption[-1].endswith(".") and "Periodo" in caption[-1]:
            break
    table = _Table(number, " ".join(caption))
    while index < len(lines) and lines[index] == "":
        index += 1
    while index < len(lines) and (_YEAR.match(lines[index]) or lines[index] in WEEKDAYS):
        table.header.append(lines[index])
        index += 1
    if not table.header:
        return None, index
    width = len(table.header)
    label: list[str] = []
    values: list[float | None] = []
    while index < len(lines):
        token = lines[index]
        if token == "" or (token == "Total*" and not table.rows and not label):
            index += 1  # a blank, or the "both sexes" header cell of the age tables
            continue
        if _is_value(token) and label:
            values.append(_value(token))
            if _PERCENT.match(token):
                table.unit = "share"
            if len(values) == width:
                raw = " ".join(label)
                if raw.startswith("Hombres "):
                    table.sex = "men"
                elif raw.startswith("Mujeres "):
                    table.sex = "women"
                table.rows.append((_clean_label(raw), values))
                finished = label[-1].lower().startswith(("total", "subtotal"))
                label, values = [], []
                index += 1
                if finished:
                    break
                continue
            index += 1
            continue
        if values:  # a label interrupted a row of values: the table is over
            break
        if _is_prose(token) or _YEAR.match(token):
            break
        label.append(token)
        index += 1
    return table, index


def parse_speed_report(path: Path = SPEED_REPORT_PATH) -> list[_Table]:
    """Every annex table of the report in document order."""
    import pymupdf  # imported here: only the ingest step needs it

    document = pymupdf.open(path)
    text = "\n".join(page.get_text() for page in document)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    tables: list[_Table] = []
    index = 0
    while index < len(lines):
        if _CAPTION.match(lines[index]):
            table, index = _parse_table(lines, index)
            if table is not None and table.rows:
                tables.append(table)
            continue
        index += 1
    return tables


def read_speed_report(path: Path = SPEED_REPORT_PATH) -> pd.DataFrame:
    """The report's tables as one long frame.

    Columns: ``table_index`` (document order), ``table_number`` (as printed; the report repeats
    some numbers), ``caption``, ``metric``, ``zone``, ``breakdown``, ``category``, ``column``
    (a year, or a weekday for the day × hour grids), ``value``, ``unit``, ``region_scope``.
    """
    records: list[dict[str, object]] = []
    for position, table in enumerate(parse_speed_report(path), start=1):
        zone = _classify(table.caption, ZONES, "all")
        breakdown = _classify(table.caption, BREAKDOWNS, "series")
        metric = "series" if breakdown == "series" else _classify(table.caption, METRICS, "unknown")
        if breakdown == "driver_age" and table.sex:
            breakdown = f"driver_age_{table.sex}"
        header = [WEEKDAY_LABELS.get(h, h) for h in table.header]
        for label, values in table.rows:
            for column, value in zip(header, values):
                records.append(
                    {
                        "table_index": position,
                        "table_number": table.number,
                        "caption": table.caption,
                        "metric": metric,
                        "zone": zone,
                        "breakdown": breakdown,
                        "category": label,
                        "column": column,
                        "value": value,
                        "unit": table.unit,
                        "region_scope": REGION_SCOPE,
                    }
                )
    out = pd.DataFrame.from_records(records)
    return out.astype(
        {
            "table_index": "int16",
            "table_number": "int16",
            "caption": "string",
            "metric": "string",
            "zone": "string",
            "breakdown": "string",
            "category": "string",
            "column": "string",
            "value": "float64",
            "unit": "string",
            "region_scope": "string",
        }
    )


def build_reports(force: bool = False) -> list[Path]:
    """Write the parsed report to ``data/interim``."""
    INTERIM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = SPEED_REPORT_INTERIM
    if target.exists() and not force:
        log.info("reports %s: exists, skipping", target.stem)
        return [target]
    frame = read_speed_report()
    frame.to_parquet(target, index=False)
    log.info(
        "reports %s: %s rows from %d tables -> %s",
        target.stem,
        f"{len(frame):,}",
        frame.table_index.nunique(),
        target.name,
    )
    return [target]


def read_report(name: str = "speed_report") -> pd.DataFrame:
    return pd.read_parquet(INTERIM_DATA_DIR / f"{name}.parquet")
