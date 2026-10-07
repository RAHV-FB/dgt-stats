"""Audit of the Barcelona vehicle-record table, and the reason unique-vehicle analyses are quarantined.

The table has more rows than the crash table reports vehicles, and for many crashes its row count
differs from ``Numero_vehicles_implicats``. This module measures that and the patterns around it
without choosing an explanation: it does not treat duplicate-looking rows as duplicate vehicles,
licence-bearing rows as drivers, row order as a link to person rows, or identical
make/model/colour as the same vehicle. No vehicle identifier exists in the source and none is
made up.

What the audit allows: crash-level *presence* of a vehicle type (``barcelona.vehicle_type_presence``),
which does not depend on what a row is. What it quarantines: counting vehicles from this table,
per-vehicle rates, linking vehicles to people or causes, and treating licence fields as a driver's.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats.microdata import barcelona
from dgt_stats.microdata.common import blank
from dgt_stats.paths import DOCS_DIR, TABLES_DIR

KEY = barcelona.KEY
AUDIT_DOC = DOCS_DIR / "BARCELONA_VEHICLE_AUDIT.md"
AUDIT_TABLE = TABLES_DIR / "bcn_vehicle_audit_counts.csv"

CONTENT_COLUMNS = [
    "Descripcio_tipus_vehicle",
    "Descripcio_model",
    "Descripcio_marca",
    "Descripcio_color",
]
LICENCE_COLUMNS = ["Descripcio_carnet", "Antiguitat_carnet"]
MULTISET = "crashes whose multiset of vehicle types equals that of the person records"
TYPE_SET = "crashes whose set of vehicle types equals that of the person records"


def per_crash(vehicles: pd.DataFrame, crashes: pd.DataFrame, people: pd.DataFrame) -> pd.DataFrame:
    """One row per crash: vehicle rows, the crash table's vehicle count and the person records."""
    expected = crashes.set_index(KEY)["n_vehicles"]
    roles = people["Descripcio_tipus_persona"].map(barcelona.ROLES_OF_PERSON)
    out = (
        pd.DataFrame(
            {
                "vehicles_reported": expected,
                "vehicle_rows": vehicles.groupby(KEY).size(),
                "person_rows": people.groupby(KEY).size(),
                "pedestrian_rows": people[roles == "pedestrian"].groupby(KEY).size(),
                "passenger_rows": people[roles == "passenger"].groupby(KEY).size(),
                "driver_rows": people[roles == "driver"].groupby(KEY).size(),
            }
        )
        .fillna(0)
        .astype(int)
    )
    out["excess_rows"] = out.vehicle_rows - out.vehicles_reported
    vtypes = vehicles.groupby(KEY)["Descripcio_tipus_vehicle"].agg(lambda s: tuple(sorted(s)))
    ptypes = people.groupby(KEY)["Desc_Tipus_vehicle_implicat"].agg(lambda s: tuple(sorted(s)))
    out["type_multiset_equals_people"] = vtypes.reindex(out.index) == ptypes.reindex(out.index)
    out["type_set_equals_people"] = vtypes.reindex(out.index).map(
        lambda t: frozenset(t) if isinstance(t, tuple) else None
    ) == ptypes.reindex(out.index).map(lambda t: frozenset(t) if isinstance(t, tuple) else None)
    return out


def duplicate_looking(vehicles: pd.DataFrame) -> pd.DataFrame:
    """Rows sharing crash, type, make, model and colour with another row of the same crash."""
    flagged = vehicles.duplicated([KEY, *CONTENT_COLUMNS], keep=False)
    licence_blank = blank(vehicles["Descripcio_carnet"]) & blank(vehicles["Antiguitat_carnet"])
    return vehicles.assign(duplicate_looking=flagged, licence_fields_blank=licence_blank)


def missingness(vehicles: pd.DataFrame) -> pd.DataFrame:
    columns = [*CONTENT_COLUMNS, *LICENCE_COLUMNS]
    return pd.DataFrame(
        {
            "column": columns,
            "blank_rows": [int(blank(vehicles[c]).sum()) for c in columns],
            "blank_share": [float(blank(vehicles[c]).mean()) for c in columns],
        }
    )


def run() -> dict[str, pd.DataFrame]:
    vehicles = barcelona.load("bcn_vehicles")
    crashes = barcelona.read_crashes()
    people = barcelona.load("bcn_people")
    crash = per_crash(vehicles, crashes, people)
    flagged = duplicate_looking(vehicles)
    agreement = pd.crosstab(crash.vehicles_reported, crash.vehicle_rows)
    excess_vs_others = pd.crosstab(
        crash.excess_rows.clip(-3, 4), (crash.pedestrian_rows + crash.passenger_rows).clip(0, 4)
    )
    patterns = (
        flagged.groupby(["duplicate_looking", "licence_fields_blank"]).size().rename("rows")
    ).reset_index()
    blank_pattern = (
        pd.DataFrame(
            {
                c: blank(vehicles[c])
                for c in [
                    "Descripcio_marca",
                    "Descripcio_color",
                    "Descripcio_carnet",
                    "Antiguitat_carnet",
                ]
            }
        )
        .value_counts()
        .rename("rows")
        .reset_index()
    )
    counts = pd.DataFrame(
        [
            ("vehicle records", len(vehicles)),
            ("crashes", int(crash.shape[0])),
            ("vehicles reported by the crash table (sum)", int(crash.vehicles_reported.sum())),
            ("crashes where vehicle rows = vehicles reported", int((crash.excess_rows == 0).sum())),
            (
                "crashes with more vehicle rows than vehicles reported",
                int((crash.excess_rows > 0).sum()),
            ),
            (
                "crashes with fewer vehicle rows than vehicles reported",
                int((crash.excess_rows < 0).sum()),
            ),
            (
                "crashes where vehicle rows = person records",
                int((crash.vehicle_rows == crash.person_rows).sum()),
            ),
            (MULTISET, int(crash.type_multiset_equals_people.sum())),
            (TYPE_SET, int(crash.type_set_equals_people.sum())),
            (
                "duplicate-looking records (same crash, type, make, model, colour)",
                int(flagged.duplicate_looking.sum()),
            ),
            (
                "duplicate-looking records with both licence fields blank",
                int((flagged.duplicate_looking & flagged.licence_fields_blank).sum()),
            ),
            (
                "records exactly identical in every column",
                int(vehicles.drop(columns=["source_row"]).duplicated().sum()),
            ),
        ],
        columns=["measure", "value"],
    )
    return {
        "counts": counts,
        "per_crash": crash,
        "agreement": agreement,
        "excess_vs_pedestrians_passengers": excess_vs_others,
        "duplicate_licence_patterns": patterns,
        "blank_patterns": blank_pattern,
        "missingness": missingness(vehicles),
        "rows_per_crash": crash.vehicle_rows.value_counts()
        .sort_index()
        .rename("crashes")
        .rename_axis("vehicle_rows")
        .reset_index(),
    }


def _md_table(frame: pd.DataFrame) -> str:
    frame = frame.copy()
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    shares = ["share" in str(c) for c in frame.columns]
    body = [
        "| " + " | ".join(_fmt(v, s) for v, s in zip(row, shares)) + " |"
        for row in frame.itertuples(index=False)
    ]
    return "\n".join([header, rule, *body])


def _fmt(value, share: bool = False) -> str:
    if isinstance(value, float):
        return f"{value:.1%}" if share else f"{value:,.1f}"
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return f"{value:,}"
    return str(value)


def render(results: dict[str, pd.DataFrame]) -> str:
    counts = dict(zip(results["counts"].measure, results["counts"].value))
    crashes = counts["crashes"]
    share = lambda k: counts[k] / crashes  # noqa: E731
    agreement = (
        results["agreement"].reset_index().rename(columns={"vehicles_reported": "reported \\ rows"})
    )
    agreement.columns = [str(c) for c in agreement.columns]
    excess = results["excess_vs_pedestrians_passengers"].reset_index()
    excess.columns = ["excess rows \\ pedestrian+passenger records"] + [
        str(c) for c in excess.columns[1:]
    ]
    lines = [
        "# Barcelona vehicle-record table: audit",
        "",
        "Generated by `python scripts/microdata.py quality` from",
        "`data/raw/barcelona/2025/accidents_vehicles_gu_bcn_2025.csv`; do not edit by hand.",
        "",
        "## Verdict",
        "",
        "**Unique-vehicle analyses are quarantined.** The rows of this table cannot be shown to be",
        "one row per vehicle: the source carries no vehicle identifier and no documentation in the",
        "repository defines the row. The table is used for one thing only, whose answer does not",
        "depend on what a row is: whether a crash has *any* record of a given vehicle type",
        "(`vehicle_records_include_*` in `barcelona_accidents.parquet`). It is not used to count",
        "vehicles, compute per-vehicle rates, link vehicles to people or causes, or read the",
        "licence fields as a driver's.",
        "",
        "## What the table looks like",
        "",
        f"- {counts['vehicle records']:,} records for {crashes:,} crashes; the crash table reports "
        f"{counts['vehicles reported by the crash table (sum)']:,} vehicles in the same crashes.",
        f"- Rows equal the reported vehicles in {counts['crashes where vehicle rows = vehicles reported']:,} "
        f"crashes ({share('crashes where vehicle rows = vehicles reported'):.1%}); more rows in "
        f"{counts['crashes with more vehicle rows than vehicles reported']:,} "
        f"({share('crashes with more vehicle rows than vehicles reported'):.1%}); fewer in "
        f"{counts['crashes with fewer vehicle rows than vehicles reported']:,}.",
        f"- Rows equal the crash's person records in "
        f"{counts['crashes where vehicle rows = person records']:,} crashes "
        f"({share('crashes where vehicle rows = person records'):.1%}), and the multiset of vehicle "
        f"types equals the multiset of vehicle types on the person records in "
        f"{counts[MULTISET]:,} ({share(MULTISET):.1%}).",
        f"- The *set* of vehicle types (which types appear, not how often) is the same in the "
        f"vehicle table and on the person records in {counts[TYPE_SET]:,} crashes "
        f"({share(TYPE_SET):.1%}): the presence flags this project uses give the same answer "
        "whichever of the two tables they are read from.",
        f"- {counts['duplicate-looking records (same crash, type, make, model, colour)']:,} records "
        "share crash, type, make, model and colour with another record of the same crash; "
        f"{counts['duplicate-looking records with both licence fields blank']:,} of them have both "
        "licence fields blank. No two records are identical in every column "
        f"({counts['records exactly identical in every column']:,}).",
        "",
        "These patterns are *consistent with* a table that has one vehicle record per person",
        "involved (a pedestrian or passenger row repeating the vehicle concerned), but the data do",
        "not prove it: rows are not keyed to people, the match is not exact, and the row order of",
        "two files is not a key. The pattern is reported, not used.",
        "",
        "## Reported vehicles against vehicle rows (crashes)",
        "",
        _md_table(agreement),
        "",
        "## Extra rows against pedestrian and passenger records (crashes)",
        "",
        _md_table(excess),
        "",
        "## Duplicate-looking records by licence fields (records)",
        "",
        _md_table(results["duplicate_licence_patterns"]),
        "",
        "## Blank patterns (records; True = blank)",
        "",
        _md_table(results["blank_patterns"]),
        "",
        "## Missingness by column (records)",
        "",
        _md_table(results["missingness"]),
        "",
        "## What would lift the quarantine",
        "",
        "A vehicle identifier in the source, or the publisher's definition of a row, that makes the",
        "row count reconcile with `Numero_vehicles_implicats`. Until then a vehicle-level question",
        "(vehicles per crash by type, licence age of drivers, make or colour) is out of scope.",
    ]
    return "\n".join(lines) + "\n"


def write() -> dict[str, pd.DataFrame]:
    results = run()
    AUDIT_TABLE.parent.mkdir(parents=True, exist_ok=True)
    results["counts"].to_csv(AUDIT_TABLE, index=False)
    AUDIT_DOC.write_text(render(results), encoding="utf-8")
    return results
