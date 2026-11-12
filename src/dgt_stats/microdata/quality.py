"""Structure and consistency checks of the regional crash files, written to ``reports/tables``.

``mq_bcn_structure`` (the six Barcelona tables and how they key to the crash table),
``mq_bcn_count_semantics`` (the evidence for reading a blank count as zero) and ``mq_cat_checks``
(consistency of the Catalan file). Every number is computed from the staged and processed tables.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats.microdata import barcelona, catalonia
from dgt_stats.microdata.common import blank
from dgt_stats.paths import TABLES_DIR

KEY = barcelona.KEY
EXPLICIT_ZERO = "count cells holding an explicit zero (all five count columns)"


# ----------------------------------------------------------------------------- Barcelona
def bcn_tables() -> dict[str, pd.DataFrame]:
    barcelona.stage()
    return {role: barcelona.load(role) for role in barcelona.ROLES}


def bcn_structure(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    crash_ids = set(tables["bcn_accidents"][KEY])
    rows = []
    for role, frame in tables.items():
        per = frame.groupby(KEY).size()
        ids = set(frame[KEY])
        rows.append(
            {
                "table": role,
                "rows": len(frame),
                "source_columns": frame.shape[1] - 2,
                "distinct_crash_ids": len(ids),
                "ids_not_in_crash_table": len(ids - crash_ids),
                "crashes_missing_from_table": len(crash_ids - ids),
                "min_rows_per_crash": int(per.min()),
                "max_rows_per_crash": int(per.max()),
                "crashes_with_more_than_one_row": int((per > 1).sum()),
            }
        )
    return pd.DataFrame(rows)


def bcn_count_semantics(crashes: pd.DataFrame, people: pd.DataFrame) -> pd.DataFrame:
    """The evidence for reading a blank count as zero, and the crash-person reconciliation."""
    raw = crashes
    count_columns = [
        "Numero_morts",
        "Numero_lesionats_greus",
        "Numero_lesionats_lleus",
        "Numero_victimes",
        "Numero_vehicles_implicats",
    ]
    explicit_zero = {c: int(raw[c].astype(str).str.strip().eq("0").sum()) for c in count_columns}
    blanks = {c: int(blank(raw[c]).sum()) for c in count_columns}
    identity = (
        crashes.n_victims
        == crashes.n_deaths + crashes.n_serious_injuries + crashes.n_minor_injuries
    )
    sev = people.groupby(KEY)["injury_severity"].value_counts().unstack(fill_value=0)
    sev = sev.reindex(crashes[KEY]).fillna(0)
    detail = people.groupby(KEY)["victimisation"].value_counts().unstack(fill_value=0)
    detail = detail.reindex(crashes[KEY]).fillna(0)
    c = crashes.set_index(KEY)
    serious_match = sev.get("serious", 0) == c.n_serious_injuries
    minor_match = sev.get("minor", 0) == c.n_minor_injuries
    deaths_all = sev.get("fatal", 0)
    deaths_24h = detail.get("died_within_24h", 0)
    rows = [
        (EXPLICIT_ZERO, sum(explicit_zero.values())),
        ("blank cells in Numero_morts", blanks["Numero_morts"]),
        ("blank cells in Numero_lesionats_greus", blanks["Numero_lesionats_greus"]),
        ("blank cells in Numero_lesionats_lleus", blanks["Numero_lesionats_lleus"]),
        ("blank cells in Numero_victimes", blanks["Numero_victimes"]),
        ("blank cells in Numero_vehicles_implicats", blanks["Numero_vehicles_implicats"]),
        ("crashes where victims = deaths + serious + minor (blank read as 0)", int(identity.sum())),
        ("crashes", len(crashes)),
        ("crashes where serious-injury persons = Numero_lesionats_greus", int(serious_match.sum())),
        ("crashes where minor-injury persons = Numero_lesionats_lleus", int(minor_match.sum())),
        (
            "crashes where persons died within 24 h = Numero_morts",
            int((deaths_24h == c.n_deaths).sum()),
        ),
        (
            "crashes where persons died (any time) = Numero_morts",
            int((deaths_all == c.n_deaths).sum()),
        ),
        ("persons recorded as died within 24 h", int(deaths_24h.sum())),
        ("persons recorded as died after 24 h", int(detail.get("died_after_24h", 0).sum())),
        ("persons recorded as natural death", int(detail.get("natural_death", 0).sum())),
        ("deaths in the crash table (Numero_morts)", int(c.n_deaths.sum())),
        ("vehicles reported by the crash table (sum)", int(c.n_vehicles.sum())),
        ("serious injuries in the crash table", int(c.n_serious_injuries.sum())),
        ("persons with a serious injury", int(sev.get("serious", 0).sum())),
    ]
    return pd.DataFrame(rows, columns=["check", "value"])


# ----------------------------------------------------------------------------- Catalonia
def cat_checks(frame: pd.DataFrame) -> pd.DataFrame:
    """Consistency of the Catalan file. No row repeats another in every source column; the rows
    that repeat another in everything but the time are counted and kept, since two crashes on the
    same day, road and place with the same victims are possible."""
    source_columns = [c for c in frame.columns if c[:2] in ("D_", "F_", "C_")] + [
        "zona",
        "via",
        "pk",
        "nomMun",
        "nomCom",
        "nomDem",
        "grupDiaLab",
        "hor",
        "grupHor",
        "tipAcc",
        "tipDia",
        "Any",
        "dat",
    ]
    identity = frame.n_victims == frame.n_deaths + frame.n_serious_injuries + frame.n_minor_injuries
    unit_parts = [
        c
        for c in catalonia.COUNT_COLUMNS.values()
        if c not in ("n_deaths", "n_serious_injuries", "n_minor_injuries", "n_victims", "n_units")
    ]
    units = frame[unit_parts].sum(axis=1) == frame.n_units
    duplicates_ignoring_time = frame.duplicated(
        [c for c in source_columns if c != "hor"], keep=False
    )
    return pd.DataFrame(
        [
            ("rows (crashes)", len(frame)),
            (
                "source columns",
                len(
                    [
                        c
                        for c in frame.columns
                        if c not in ("source_row", "source_file") and c in source_columns
                    ]
                ),
            ),
            ("first date", str(frame.date.min().date())),
            ("last date", str(frame.date.max().date())),
            ("dates that do not parse", int(frame.date.isna().sum())),
            (
                "rows whose date year differs from Any",
                int((frame.date.dt.year != frame.year).sum()),
            ),
            ("hours that do not parse as H,MM", int(frame.hour.isna().sum())),
            ("rows identical in every source column", int(frame.row_sha1.duplicated().sum())),
            (
                "rows identical in every source column except the time",
                int(duplicates_ignoring_time.sum()),
            ),
            ("rows where victims = deaths + serious + minor", int(identity.sum())),
            (
                "rows where units = the sum of the unit types (pedestrians included)",
                int(units.sum()),
            ),
            (
                "fatal label with no death recorded",
                int(((frame.fatal == 1) & (frame.n_deaths == 0)).sum()),
            ),
            (
                "serious label with a death recorded",
                int(((frame.fatal == 0) & (frame.n_deaths > 0)).sum()),
            ),
            (
                "serious label with no serious injury recorded",
                int(((frame.fatal == 0) & (frame.n_serious_injuries == 0)).sum()),
            ),
            ("fatal crashes", int(frame.fatal.sum())),
            ("serious (non-fatal) crashes", int((frame.fatal == 0).sum())),
            ("municipalities", int(frame.municipality.nunique())),
            ("comarques", int(frame.comarca.nunique())),
            ("demarcations", int(frame.demarcation.nunique())),
        ],
        columns=["check", "value"],
    )


def build() -> dict[str, pd.DataFrame]:
    tables = bcn_tables()
    out = {
        "mq_bcn_structure": bcn_structure(tables),
        "mq_bcn_count_semantics": bcn_count_semantics(
            barcelona.read_crashes(), barcelona.read_people()
        ),
        "mq_cat_checks": cat_checks(catalonia.read()),
    }
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, frame in out.items():
        frame.to_csv(TABLES_DIR / f"{name}.csv", index=False)
    return out
