"""Helpers shared by the microdata modules: provenance-stamped Parquet, slugs, intervals."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Bumped when a change to the cleaning or feature code changes what the outputs contain.
PIPELINE_VERSION = "microdata-1.0"


def slug(text: str) -> str:
    """ASCII snake_case for a category label: ``"Excés de velocitat"`` -> ``"exces_de_velocitat"``."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "blank"


def blank(series: pd.Series) -> pd.Series:
    """True where a text cell is empty or only whitespace (the sources' way of leaving a field out)."""
    return series.fillna("").astype(str).str.strip().eq("")


def to_int(series: pd.Series) -> pd.Series:
    """Text digits to nullable integers; a blank cell becomes ``<NA>``."""
    return pd.to_numeric(series.where(~blank(series)), errors="coerce").astype("Int64")


def to_float(series: pd.Series, decimal_comma: bool = False) -> pd.Series:
    text = series.where(~blank(series))
    if decimal_comma:
        text = text.str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce").astype("Float64")


def wilson(successes: np.ndarray | pd.Series, totals: np.ndarray | pd.Series, z: float = 1.96):
    """Wilson score interval for a proportion; returns (low, high) arrays."""
    k = np.asarray(successes, dtype=float)
    n = np.asarray(totals, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = k / n
        centre = (p + z * z / (2 * n)) / (1 + z * z / n)
        half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def write_parquet(frame: pd.DataFrame, path: Path, provenance: dict) -> Path:
    """Write ``frame`` with a JSON provenance record in the file's schema metadata and beside it.

    The record names the pipeline version, the source files and their SHA-256, the unit of
    observation and the key; it carries no timestamp, so a rebuild from the same raw files gives
    the same record.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"pipeline_version": PIPELINE_VERSION, "rows": int(len(frame)), **provenance}
    table = pa.Table.from_pandas(frame, preserve_index=False)
    metadata = dict(table.schema.metadata or {})
    metadata[b"dgt_stats.provenance"] = json.dumps(record, ensure_ascii=False).encode("utf-8")
    pq.write_table(table.replace_schema_metadata(metadata), path)
    path.with_suffix(".json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def read_provenance(path: Path) -> dict:
    metadata = pq.read_schema(path).metadata or {}
    return json.loads(metadata[b"dgt_stats.provenance"].decode("utf-8"))


def assert_unique(frame: pd.DataFrame, key: str | list[str], what: str) -> None:
    duplicated = frame.duplicated(key, keep=False)
    if duplicated.any():
        sample = frame.loc[duplicated, key].head(5).values.tolist()
        raise ValueError(f"{what}: {int(duplicated.sum())} rows share a key {key}, e.g. {sample}")
