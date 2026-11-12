"""The raw Barcelona and Catalonia microdata files and how they are read.

Each table is a fixed file under ``data/raw`` (:data:`SOURCES`), listed with its checksum in the
manifest. Raw values are read as text exactly as published (``dtype=str``, no NA parsing); only
the column *names* are normalised (accents, stray spaces, one capitalisation variant), so
``Número_expedient`` and ``Numero_expedient`` become the same key while every cell keeps its
source spelling.
"""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from dgt_stats.paths import MANIFEST, RAW_BARCELONA_DIR, RAW_CATALONIA_DIR, RAW_DATA_DIR

# The crash identifier the six Barcelona tables share (normalised spelling).
BCN_ID = "Numero_expedient"

# Column-name spellings that differ between the Barcelona files beyond accents and spacing.
COLUMN_ALIASES = {"Nk_Any": "NK_Any"}

MANIFEST_FIELDS = ("path", "bytes", "sha256", "source_url", "description", "added", "downloaded_as")


def normalise_column_name(name: str) -> str:
    """Column name without accents, byte-order mark or stray spaces; cell values are untouched.

    ``"Número_expedient"`` -> ``"Numero_expedient"``, ``"NK_ Any"`` -> ``"NK_Any"``,
    ``"Num_postal "`` -> ``"Num_postal"``, ``"Causa conductor"`` -> ``"Causa_conductor"``.
    """
    text = name.replace("﻿", "").strip()
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )
    text = re.sub(r"\s*_\s*", "_", text)
    text = re.sub(r"\s+", "_", text)
    return COLUMN_ALIASES.get(text, text)


@dataclass(frozen=True)
class Source:
    """One raw table: where it is, what a row is."""

    name: str
    path: Path
    unit: str
    cardinality: str

    @property
    def relative(self) -> str:
        return str(self.path.relative_to(RAW_DATA_DIR))

    @property
    def sha256(self) -> str:
        return sha256(self.path)


_BCN = RAW_BARCELONA_DIR / "2025"

SOURCES: dict[str, Source] = {
    source.name: source
    for source in (
        Source(
            "bcn_accidents",
            _BCN / "accidents_gu_bcn_2025.csv",
            "one crash (Numero_expedient)",
            "one row per crash",
        ),
        Source(
            "bcn_people",
            _BCN / "accidents_persones_gu_bcn_2025.csv",
            "one person record in a crash",
            "one or more rows per crash",
        ),
        Source(
            "bcn_vehicles",
            _BCN / "accidents_vehicles_gu_bcn_2025.csv",
            "one vehicle record (not proven to be one vehicle)",
            "one or more rows per crash",
        ),
        Source(
            "bcn_mediate_causes",
            _BCN / "accidents_causes_mediates_gu_bcn_2025.csv",
            "one recorded mediate cause of a crash (or a blank row)",
            "one or more rows per crash",
        ),
        Source(
            "bcn_driver_causes",
            _BCN / "accidents_causa_conductor_gu_bcn_2025.csv",
            "one recorded driver-related cause of a crash (no person or vehicle key)",
            "one or more rows per crash",
        ),
        Source(
            "bcn_accident_types",
            _BCN / "accidents_tipus_gu_bcn_2025.csv",
            "one crash (Numero_expedient)",
            "one row per crash",
        ),
        Source(
            "cat_severe_crashes",
            RAW_CATALONIA_DIR / "accidents_morts_ferits_greus_catalunya_2010_2023.csv",
            "one crash with at least one death or serious injury (no source identifier)",
            "one row per crash",
        ),
    )
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def detect_encoding(path: Path) -> str:
    """``utf-8-sig`` when the file starts with a byte-order mark, else ``utf-8`` or ``latin-1``."""
    head = path.read_bytes()[: 1 << 16]
    if head.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return "latin-1"
    return "utf-8"


def detect_delimiter(path: Path, encoding: str) -> str:
    with path.open(encoding=encoding, newline="") as handle:
        sample = handle.read(1 << 14)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|\t").delimiter
    except csv.Error:
        return ","


def header(path: Path) -> list[str]:
    """The file's column names as published (not normalised)."""
    encoding = detect_encoding(path)
    with path.open(encoding=encoding, newline="") as handle:
        return next(csv.reader(handle, delimiter=detect_delimiter(path, encoding)))


def read_raw(path: Path) -> pd.DataFrame:
    """Every cell as published text, normalised column names, and the 1-based source data row."""
    encoding = detect_encoding(path)
    frame = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        encoding=encoding,
        sep=detect_delimiter(path, encoding),
    )
    renamed = {column: normalise_column_name(column) for column in frame.columns}
    if len(set(renamed.values())) != len(renamed):
        raise ValueError(f"{path.name}: two columns normalise to the same name")
    frame = frame.rename(columns=renamed)
    frame.insert(0, "source_row", range(1, len(frame) + 1))
    return frame


# --------------------------------------------------------------------------- manifest
def read_manifest(path: Path = MANIFEST) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for name in MANIFEST_FIELDS:
            row.setdefault(name, "")
    return rows
