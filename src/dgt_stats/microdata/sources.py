"""Find, identify, de-duplicate and read the raw Barcelona and Catalonia microdata files.

A file is identified by its columns, never by its name: the downloads arrived as ``download.csv``,
``download(1).csv`` ... and ``export.csv``, names that say nothing about their content. Each
:class:`Role` lists the normalised columns that only its table carries. Byte-identical copies are
detected by SHA-256 and processed once; two different files claiming the same role and year are a
conflict that stops the pipeline rather than being silently merged.

Raw values are read as text exactly as published (``dtype=str``, no NA parsing); only the column
*names* are normalised (accents, stray spaces, one capitalisation variant), so ``Número_expedient``
and ``Numero_expedient`` become the same key while every cell keeps its source spelling.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import logging
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from dgt_stats.paths import (
    MANIFEST,
    RAW_BARCELONA_DIR,
    RAW_CATALONIA_DIR,
    RAW_DATA_DIR,
)

log = logging.getLogger(__name__)

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
class Role:
    """One kind of source table, recognised by columns only it carries."""

    name: str
    source: str
    signature: frozenset[str]
    unit: str
    cardinality: str
    description: str
    file_stem: str


ROLES: tuple[Role, ...] = (
    Role(
        name="bcn_accidents",
        source="barcelona",
        signature=frozenset(
            {
                BCN_ID,
                "Numero_morts",
                "Numero_lesionats_lleus",
                "Numero_lesionats_greus",
                "Numero_victimes",
                "Numero_vehicles_implicats",
            }
        ),
        unit="one crash (Numero_expedient)",
        cardinality="one row per crash",
        description=(
            "Barcelona, Guàrdia Urbana: crashes it attended, one row per crash with place, time, "
            "victim counts by severity and vehicles involved"
        ),
        file_stem="accidents_gu_bcn",
    ),
    Role(
        name="bcn_people",
        source="barcelona",
        signature=frozenset(
            {BCN_ID, "Descripcio_victimitzacio", "Edat", "Descripcio_tipus_persona"}
        ),
        unit="one person record in a crash",
        cardinality="one or more rows per crash",
        description=(
            "Barcelona, Guàrdia Urbana: people involved in the crashes (drivers, passengers, "
            "pedestrians, injured or not) with age, sex, role, associated vehicle type and "
            "victimisation"
        ),
        file_stem="accidents_persones_gu_bcn",
    ),
    Role(
        name="bcn_vehicles",
        source="barcelona",
        signature=frozenset(
            {BCN_ID, "Descripcio_tipus_vehicle", "Descripcio_marca", "Descripcio_model"}
        ),
        unit="one vehicle record (semantics audited; not proven to be one vehicle)",
        cardinality="one or more rows per crash",
        description=(
            "Barcelona, Guàrdia Urbana: vehicle records in the crashes (type, make, model, colour, "
            "licence class and age of licence); see docs/BARCELONA_VEHICLE_AUDIT.md"
        ),
        file_stem="accidents_vehicles_gu_bcn",
    ),
    Role(
        name="bcn_mediate_causes",
        source="barcelona",
        signature=frozenset({BCN_ID, "Descripcio_causa_mediata"}),
        unit="one recorded mediate cause of a crash (or a blank row)",
        cardinality="one or more rows per crash",
        description=(
            "Barcelona, Guàrdia Urbana: mediate causes recorded for each crash (alcohol, speed, "
            "drugs, road surface, signals, weather, objects or animals)"
        ),
        file_stem="accidents_causes_mediates_gu_bcn",
    ),
    Role(
        name="bcn_driver_causes",
        source="barcelona",
        signature=frozenset({BCN_ID, "Causa_conductor"}),
        unit="one recorded driver-related cause of a crash (no person or vehicle key)",
        cardinality="one or more rows per crash",
        description=(
            "Barcelona, Guàrdia Urbana: driver-related causes recorded for each crash, without a "
            "key to the person or vehicle concerned"
        ),
        file_stem="accidents_causa_conductor_gu_bcn",
    ),
    Role(
        name="bcn_accident_types",
        source="barcelona",
        signature=frozenset({BCN_ID, "Descripcio_tipus_accident"}),
        unit="one crash (Numero_expedient)",
        cardinality="one row per crash",
        description="Barcelona, Guàrdia Urbana: the type of each crash (collision, run-over, fall...)",
        file_stem="accidents_tipus_gu_bcn",
    ),
    Role(
        name="cat_severe_crashes",
        source="catalonia",
        signature=frozenset({"Any", "dat", "nomMun", "F_MORTS", "F_FERITS_GREUS", "D_GRAVETAT"}),
        unit="one crash with at least one death or serious injury (no source identifier)",
        cardinality="one row per crash",
        description=(
            "Catalonia, Servei Català de Trànsit export: crashes with at least one death or "
            "serious injury, with place, road, conditions, victims and units involved"
        ),
        file_stem="accidents_morts_ferits_greus_catalunya",
    ),
)
ROLE_BY_NAME = {role.name: role for role in ROLES}


class SourceConflict(RuntimeError):
    """Two different files claim the same role and coverage."""


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


def identify(columns: list[str]) -> Role | None:
    """The single role whose signature the (normalised) columns contain, or ``None``."""
    names = {normalise_column_name(column) for column in columns}
    matches = [role for role in ROLES if role.signature <= names]
    if len(matches) > 1:
        raise SourceConflict(f"columns match several roles: {[r.name for r in matches]}")
    return matches[0] if matches else None


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


def coverage_years(path: Path, role: Role) -> tuple[int, ...]:
    """The calendar years a file covers, read from its own year column."""
    column = "NK_Any" if role.source == "barcelona" else "Any"
    years = pd.to_numeric(read_raw(path)[column], errors="coerce").dropna().astype(int)
    return tuple(sorted(set(years)))


@dataclass
class SourceFile:
    path: Path
    sha256: str
    role: Role
    years: tuple[int, ...]
    duplicate_of: Path | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def relative(self) -> str:
        return str(self.path.relative_to(RAW_DATA_DIR))


def discover(roots: tuple[Path, ...] = (RAW_BARCELONA_DIR, RAW_CATALONIA_DIR)) -> list[SourceFile]:
    """Every recognised CSV under ``roots``; byte-identical copies point at the first copy."""
    found: list[SourceFile] = []
    first_by_hash: dict[str, Path] = {}
    for root in roots:
        for path in sorted(root.rglob("*.csv")):
            role = identify(header(path))
            if role is None:
                log.warning("unrecognised file, not processed: %s", path)
                continue
            digest = sha256(path)
            item = SourceFile(path, digest, role, coverage_years(path, role))
            if digest in first_by_hash:
                item.duplicate_of = first_by_hash[digest]
                item.notes.append(f"byte-identical to {first_by_hash[digest].name}; not processed")
            else:
                first_by_hash[digest] = path
            found.append(item)
    return found


def same_content(a: Path, b: Path) -> bool:
    """Two files hold the same rows once column names are normalised and row order ignored."""
    left, right = read_raw(a).drop(columns="source_row"), read_raw(b).drop(columns="source_row")
    if sorted(left.columns) != sorted(right.columns) or len(left) != len(right):
        return False
    columns = sorted(left.columns)
    left = left[columns].sort_values(columns).reset_index(drop=True)
    right = right[columns].sort_values(columns).reset_index(drop=True)
    return left.equals(right)


def resolve(role_name: str, files: list[SourceFile] | None = None) -> list[SourceFile]:
    """The distinct files for a role, at most one per year; copies are dropped, conflicts raise."""
    files = discover() if files is None else files
    chosen: list[SourceFile] = []
    for item in files:
        if item.role.name != role_name or item.duplicate_of is not None:
            continue
        clash = [other for other in chosen if set(other.years) & set(item.years)]
        for other in clash:
            if same_content(other.path, item.path):
                item.duplicate_of = other.path
                item.notes.append(f"same rows as {other.path.name}; not processed")
                break
        else:
            if clash:
                raise SourceConflict(
                    f"{role_name}: {item.path} and {clash[0].path} cover the same years with "
                    "different rows; keep one of them under data/raw"
                )
            chosen.append(item)
    if not chosen:
        raise FileNotFoundError(f"no raw file found for {role_name}")
    return chosen


def resolve_one(role_name: str, files: list[SourceFile] | None = None) -> SourceFile:
    chosen = resolve(role_name, files)
    if len(chosen) != 1:
        raise SourceConflict(
            f"{role_name}: expected one file, found {[c.relative for c in chosen]}; "
            "the pipeline handles one Barcelona year at a time"
        )
    return chosen[0]


# --------------------------------------------------------------------------- manifest
def read_manifest(path: Path = MANIFEST) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for name in MANIFEST_FIELDS:
            row.setdefault(name, "")
    return rows


def write_manifest(rows: list[dict[str, str]], path: Path = MANIFEST) -> None:
    rows = sorted(rows, key=lambda row: row["path"])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({name: row.get(name, "") for name in MANIFEST_FIELDS} for row in rows)


def canonical_path(role: Role, years: tuple[int, ...]) -> Path:
    if role.source == "barcelona":
        if len(years) != 1:
            raise SourceConflict(f"a Barcelona {role.name} file must cover one year, got {years}")
        return RAW_BARCELONA_DIR / str(years[0]) / f"{role.file_stem}_{years[0]}.csv"
    return RAW_CATALONIA_DIR / f"{role.file_stem}_{years[0]}_{years[-1]}.csv"


@dataclass
class OrganiseResult:
    moved: list[tuple[Path, Path]] = field(default_factory=list)
    registered: list[Path] = field(default_factory=list)
    duplicates: list[tuple[Path, str]] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)


def organise(
    loose_dirs: tuple[Path, ...] | None = None,
    downloaded_as: dict[str, str] | None = None,
    today: dt.date | None = None,
    raw_dir: Path | None = None,
    manifest: Path | None = None,
) -> OrganiseResult:
    """File loose downloads under ``data/raw/<source>/`` by their content and register them.

    A loose CSV whose SHA-256 is already in the manifest is a duplicate copy: it is reported and
    left where it is (never deleted, never processed). A recognised new file is moved to its
    canonical path and added to the manifest with the name it was downloaded under. Files already
    under ``data/raw/barcelona`` or ``data/raw/catalonia`` but missing from the manifest are
    registered (``downloaded_as`` maps their current names to the original download names).
    """
    today = today or dt.date.today()
    downloaded_as = downloaded_as or {}
    raw_dir = raw_dir or RAW_DATA_DIR
    manifest = manifest or MANIFEST
    if loose_dirs is None:
        loose_dirs = (raw_dir.parent, raw_dir.parent / "incoming")
    roots = (raw_dir / "barcelona", raw_dir / "catalonia")
    result = OrganiseResult()
    rows = read_manifest(manifest)
    by_hash = {row["sha256"]: row["path"] for row in rows}
    listed = {row["path"] for row in rows}

    def register(path: Path, role: Role, digest: str, original: str) -> None:
        relative = str(path.relative_to(raw_dir))
        rows.append(
            {
                "path": relative,
                "bytes": str(path.stat().st_size),
                "sha256": digest,
                "source_url": "not recorded at download",
                "description": role.description,
                "added": today.isoformat(),
                "downloaded_as": original,
            }
        )
        by_hash[digest] = relative
        listed.add(relative)
        result.registered.append(path)

    for directory in loose_dirs:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.csv")):
            role = identify(header(path))
            if role is None:
                result.skipped.append((path, "columns match no known source table"))
                continue
            digest = sha256(path)
            if digest in by_hash:
                result.duplicates.append((path, by_hash[digest]))
                log.warning(
                    "%s is a byte-identical copy of raw/%s; left in place",
                    path.name,
                    by_hash[digest],
                )
                continue
            target = raw_dir / canonical_path(role, coverage_years(path, role)).relative_to(
                RAW_DATA_DIR
            )
            if target.exists():
                result.skipped.append((path, f"{target} exists with different content"))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            result.moved.append((path, target))
            register(target, role, digest, path.name)

    for root in roots:
        for path in sorted(root.rglob("*.csv")) if root.is_dir() else []:
            relative = str(path.relative_to(raw_dir))
            if relative in listed:
                continue
            role = identify(header(path))
            if role is None:
                result.skipped.append((path, "columns match no known source table"))
                continue
            register(path, role, sha256(path), downloaded_as.get(relative, path.name))

    write_manifest(rows, manifest)
    return result
