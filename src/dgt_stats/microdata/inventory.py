"""A reproducible inventory of every source file under ``data/``.

For each file: path, name, size, SHA-256, format, encoding, delimiter, rows, columns, column names
(or sheet names and sizes for workbooks), inferred unit of observation, coverage, likely source,
whether the manifest lists it, and whether another file holds the same bytes. The generated layers
(``staging``, ``processed``, ``features``) are not sources and are left out.

Rows and columns are counted from the files themselves. The unit, coverage and source of the
national files come from the rules in :data:`RULES`, written from the files' own headers and the
manifest's source URLs; the two regional sources are described by their :mod:`sources` role and
their coverage is read from their year column.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pandas as pd
import xlrd

from dgt_stats.microdata import sources
from dgt_stats.paths import DATA_DIR, DOCS_DIR, MANIFEST, RAW_DATA_DIR, TABLES_DIR

INVENTORY_TABLE = TABLES_DIR / "data_inventory.csv"
INVENTORY_DOC = DOCS_DIR / "RAW_FILE_INVENTORY.md"

DELIMITER_NAMES = {",": "comma", ";": "semicolon", "|": "pipe", "\t": "tab"}
GENERATED_LAYERS = ("staging", "processed", "features")
NOT_SOURCES = {"README.md", ".gitkeep", "manifest.csv"}


@dataclass(frozen=True)
class Rule:
    pattern: str
    source: str
    unit: str
    coverage: str


# path (relative to data/raw) -> what the file is. Years in "{year}" come from the file name.
RULES: tuple[Rule, ...] = (
    Rule(
        r"dgt/microdata/accidentes_(\d{4})",
        "DGT crash microdata (Spain)",
        "one crash with victims",
        "{year}, Spain",
    ),
    Rule(
        r"dgt/microdata/diccionario",
        "DGT crash microdata code dictionary",
        "one code of one coded variable",
        "2016-2024 layout",
    ),
    Rule(
        r"dgt/microdata/metadata",
        "datos.gob.es catalogue record",
        "catalogue metadata",
        "2024 release",
    ),
    Rule(
        r"dgt/tables/series_historicas",
        "DGT yearbook historical series",
        "published aggregate tables",
        "1993-2024, Spain",
    ),
    Rule(
        r"dgt/tables/chapters/(\d{4})/",
        "DGT statistical tables (chapter workbooks)",
        "published aggregate tables",
        "{year}, Spain",
    ),
    Rule(
        r"dgt/tables/tablas_estadisticas_(\d{4})",
        "DGT statistical tables",
        "published aggregate tables",
        "{year}, Spain",
    ),
    Rule(
        r"dgt/census/censo_conductores_edad_(\d{4})",
        "DGT driver census by age",
        "drivers per province x sex x age",
        "{year}, Spain",
    ),
    Rule(
        r"dgt/census/censo_conductores_(\d{4})",
        "DGT driver census by licence class",
        "drivers per province x sex x licence class x licence age",
        "{year}, Spain",
    ),
    Rule(
        r"dgt/census/censo_tablas_(\d{4})",
        "DGT driver census published tables",
        "published aggregate tables",
        "{year}, Spain",
    ),
    Rule(
        r"dgt/km_itv_(\d{4})/",
        "DGT kilometre estimates from ITV inspections",
        "published aggregate tables (vehicle type, age, owner age)",
        "{year}, Spain",
    ),
    Rule(r"dgt/reports/", "DGT published report (PDF)", "document", "see file name"),
    Rule(
        r"ine/ine_poblacion",
        "INE Estadística Continua de Población, table 56947",
        "residents per province x age group x sex x date",
        "2002-2025, Spain",
    ),
    Rule(r"ine/ine_ecepov_(\d{4})", "INE ECEPOV survey table", "published survey table", "{year}"),
    Rule(r"ine/ine_ehma_(\d{4})", "INE EHMA survey table", "published survey table", "{year}"),
    Rule(
        r"transportes/movilia_(\d{4})",
        "Ministerio de Fomento, MOVILIA survey",
        "published survey tables",
        "{year}, Spain",
    ),
    Rule(
        r"transportes/anuario_carreteras_(\d{4})",
        "Ministerio de Transportes, Anuario",
        "published tables (vehicle-km by road type)",
        "2004-{year}, Spain",
    ),
    Rule(
        r"transportes/peaje",
        "Ministerio de Transportes, toll motorway traffic",
        "month x toll network",
        "1990 onwards, Spain",
    ),
    Rule(r"cores/", "CORES road fuel consumption", "month x product", "1995 onwards, Spain"),
    Rule(
        r"comunidad_madrid/",
        "Comunidad de Madrid, MOVILIA 2007 tables",
        "published survey tables",
        "2007, Madrid region",
    ),
    Rule(
        r"compiled/evidence/",
        "values hand-typed from external studies (not observations)",
        "one published parameter",
        "various",
    ),
    Rule(
        r"compiled/driving_activity",
        "values hand-typed from travel surveys",
        "one published survey share",
        "various",
    ),
)


def _rule_for(relative: str) -> tuple[str, str, str]:
    for rule in RULES:
        match = re.search(rule.pattern, relative)
        if match:
            year = match.group(1) if match.groups() else ""
            return rule.source, rule.unit, rule.coverage.format(year=year)
    return "unknown", "unknown", "unknown"


def _text_table(path: Path) -> dict[str, object]:
    encoding = sources.detect_encoding(path)
    delimiter = sources.detect_delimiter(path, encoding)
    frame = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        encoding=encoding,
        sep=delimiter,
        on_bad_lines="skip",
    )
    return {
        "encoding": encoding,
        "delimiter": DELIMITER_NAMES.get(delimiter, delimiter),
        "rows": len(frame),
        "columns": frame.shape[1],
        "column_names": " | ".join(str(c).replace("﻿", "") for c in frame.columns),
    }


def _workbook(path: Path) -> dict[str, object]:
    sheets: list[tuple[str, int, int]] = []
    if path.suffix == ".xls":
        book = xlrd.open_workbook(path, on_demand=True)
        for index in range(book.nsheets):
            sheet = book.sheet_by_index(index)
            sheets.append((sheet.name, sheet.nrows, sheet.ncols))
        book.release_resources()
    else:
        book = openpyxl.load_workbook(path, read_only=True)
        for sheet in book.worksheets:
            sheets.append((sheet.title, sheet.max_row or 0, sheet.max_column or 0))
        book.close()
    described = "; ".join(f"{name} ({rows}x{cols})" for name, rows, cols in sheets[:12])
    if len(sheets) > 12:
        described += f"; ... {len(sheets) - 12} more sheets"
    largest = max(sheets, key=lambda s: s[1]) if sheets else ("", 0, 0)
    return {
        "encoding": "binary workbook",
        "delimiter": "",
        "rows": largest[1],
        "columns": largest[2],
        "column_names": f"{len(sheets)} sheets: {described}",
    }


def _pdf(path: Path) -> dict[str, object]:
    import pymupdf

    with pymupdf.open(path) as document:
        pages = document.page_count
    return {
        "encoding": "PDF",
        "delimiter": "",
        "rows": "",
        "columns": "",
        "column_names": f"{pages} pages",
    }


def describe(path: Path) -> dict[str, object]:
    """Structure of one file: encoding, delimiter, rows, columns and names (largest sheet)."""
    suffix = path.suffix.lower()
    if suffix in (".csv", ".txt"):
        return _text_table(path)
    if suffix in (".xlsx", ".xls"):
        return _workbook(path)
    if suffix == ".pdf":
        return _pdf(path)
    return {"encoding": "", "delimiter": "", "rows": "", "columns": "", "column_names": ""}


def source_files(root: Path = DATA_DIR) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in NOT_SOURCES:
            continue
        parts = path.relative_to(root).parts
        if parts[0] in GENERATED_LAYERS:
            continue
        files.append(path)
    return files


def build(root: Path = DATA_DIR) -> pd.DataFrame:
    """One row per source file under ``data/``, sorted by path."""
    listed = {row["path"]: row for row in sources.read_manifest(MANIFEST)}
    regional = {item.path: item for item in sources.discover()}
    records = []
    first_by_hash: dict[str, str] = {}
    for path in source_files(root):
        relative = str(path.relative_to(root))
        digest = sources.sha256(path)
        raw_relative = (
            str(path.relative_to(RAW_DATA_DIR)) if path.is_relative_to(RAW_DATA_DIR) else ""
        )
        if path in regional:
            item = regional[path]
            source, unit = item.role.description, item.role.unit
            low, high = (min(item.years), max(item.years)) if item.years else (None, None)
            coverage = "unknown" if low is None else str(low) if low == high else f"{low}-{high}"
            coverage += ", Barcelona city" if item.role.source == "barcelona" else ", Catalonia"
            role = item.role.name
        elif raw_relative:
            (source, unit, coverage), role = _rule_for(raw_relative), ""
        else:
            identified = sources.identify(sources.header(path)) if path.suffix == ".csv" else None
            role = identified.name if identified else ""
            source = "loose download outside data/raw: run `scripts/microdata.py organise`"
            unit = identified.unit if identified else "unknown"
            coverage = "unknown"
        duplicate = ""
        if digest in first_by_hash:
            duplicate = f"byte-identical to {first_by_hash[digest]}"
        else:
            first_by_hash[digest] = relative
        manifest_row = listed.get(raw_relative, {})
        record = {
            "path": relative,
            "filename": path.name,
            "bytes": path.stat().st_size,
            "sha256": digest,
            "format": path.suffix.lower().lstrip("."),
            **describe(path),
            "unit_of_observation": unit,
            "coverage": coverage,
            "likely_source": source,
            "role": role,
            "in_manifest": bool(manifest_row),
            "manifest_sha256_matches": manifest_row.get("sha256") == digest if manifest_row else "",
            "downloaded_as": manifest_row.get("downloaded_as", ""),
            "duplicate_status": duplicate or "unique",
        }
        records.append(record)
    return pd.DataFrame.from_records(records)


def render_markdown(frame: pd.DataFrame) -> str:
    duplicates = frame[frame.duplicate_status != "unique"]
    unlisted = frame[~frame.in_manifest]
    lines = [
        "# Raw file inventory",
        "",
        "Generated by `python scripts/microdata.py inventory` from the files under `data/`; do not",
        "edit by hand. The full table, with column names and SHA-256, is",
        "[`reports/tables/data_inventory.csv`](../reports/tables/data_inventory.csv).",
        "",
        f"- Files: {len(frame)}; bytes: {int(frame.bytes.sum()):,}",
        f"- Byte-identical duplicates: {len(duplicates)}"
        + ("" if duplicates.empty else " (" + ", ".join(duplicates.path) + ")"),
        f"- Files not in `data/raw/manifest.csv`: {len(unlisted)}"
        + ("" if unlisted.empty else " (" + ", ".join(unlisted.path) + ")"),
        "",
        "Duplicates are detected by SHA-256 over every file, and for the regional microdata also by",
        "content (same rows once column names are normalised); a duplicate is reported and never",
        "processed twice. Row counts for workbooks are those of the largest sheet.",
        "",
        "| Path | Format | Encoding | Delim. | Rows | Cols | Unit of observation | Coverage |"
        " Likely source | Duplicate |",
        "|---|---|---|---|---:|---:|---|---|---|---|",
    ]
    for row in frame.itertuples():
        lines.append(
            f"| `{row.path}` | {row.format} | {row.encoding} | {row.delimiter} | {row.rows} | "
            f"{row.columns} | {row.unit_of_observation} | {row.coverage} | {row.likely_source} | "
            f"{row.duplicate_status} |"
        )
    regional = frame[frame.role != ""]
    if not regional.empty:
        lines += ["", "## Columns of the regional microdata files", ""]
        for row in regional.itertuples():
            lines += [
                f"**`{row.path}`** ({row.role}, downloaded as `{row.downloaded_as}`):",
                "",
                f"{row.column_names}",
                "",
            ]
    return "\n".join(lines).rstrip() + "\n"


def write(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    frame = build() if frame is None else frame
    INVENTORY_TABLE.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(INVENTORY_TABLE, index=False)
    INVENTORY_DOC.write_text(render_markdown(frame), encoding="utf-8")
    return frame
