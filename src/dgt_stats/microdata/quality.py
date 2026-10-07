"""The data-quality report for the microdata layer, generated from the files on every build.

Writes ``docs/DATA_QUALITY_MICRODATA.md`` and the tables behind it (``reports/tables/mq_*.csv``).
Every number in the report is computed here from the staged and processed tables; the report
states what was checked, what holds, and what does not.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats.microdata import barcelona, catalonia, coordinates, vehicles
from dgt_stats.microdata.common import blank
from dgt_stats.paths import DOCS_DIR, TABLES_DIR

REPORT = DOCS_DIR / "DATA_QUALITY_MICRODATA.md"
KEY = barcelona.KEY
EXPLICIT_ZERO = "count cells holding an explicit zero (all five count columns)"

# Placeholders the Catalonia export uses for "not stated" (kept as categories, counted here).
CAT_PLACEHOLDERS = ("", "NA", "Sense especificar", "Sense Especificar")


def _md(frame: pd.DataFrame, index: bool = False) -> str:
    frame = frame.reset_index() if index else frame
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    shares = [
        any(word in str(c) for word in ("share", "rate", "prevalence")) for c in frame.columns
    ]
    rows = []
    for row in frame.itertuples(index=False):
        cells = []
        for value, is_share in zip(row, shares):
            if isinstance(value, float):
                cells.append(f"{value:.1%}" if is_share else f"{value:,.2f}")
            elif isinstance(value, int) and not isinstance(value, bool):
                cells.append(f"{value:,}")
            else:
                cells.append(str(value).replace("|", "/"))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, rule, *rows])


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


def bcn_null_rates(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for role, frame in tables.items():
        for column in frame.columns:
            if column in ("source_row", "source_file"):
                continue
            empty = blank(frame[column])
            rows.append(
                {
                    "table": role,
                    "column": column,
                    "blank_rows": int(empty.sum()),
                    "blank_share": float(empty.mean()),
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
        ("serious injuries in the crash table", int(c.n_serious_injuries.sum())),
        ("persons with a serious injury", int(sev.get("serious", 0).sum())),
    ]
    return pd.DataFrame(rows, columns=["check", "value"])


def bcn_context_consistency(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Do the place and time columns repeated in each table agree with the crash table?"""
    crashes = tables["bcn_accidents"].set_index(KEY)
    columns = [
        "Codi_districte",
        "Codi_barri",
        "Codi_carrer",
        "Mes_any",
        "Dia_mes",
        "Hora_dia",
        "Descripcio_torn",
        "Longitud_WGS84",
        "Latitud_WGS84",
    ]
    rows = []
    for role, frame in tables.items():
        if role == "bcn_accidents":
            continue
        joined = frame.join(crashes[columns], on=KEY, rsuffix="_crash")
        for column in columns:
            rows.append(
                {
                    "table": role,
                    "column": column,
                    "share_equal_to_crash_table": float(
                        (joined[column] == joined[f"{column}_crash"]).mean()
                    ),
                }
            )
    return pd.DataFrame(rows)


def bcn_people_profile(people: pd.DataFrame) -> dict[str, pd.DataFrame]:
    age = people["age"]
    return {
        "age": pd.DataFrame(
            [
                ("person records", len(people)),
                ("age recorded", int(age.notna().sum())),
                ("age not recorded", int(age.isna().sum())),
                ("minimum age", int(age.min())),
                ("maximum age", int(age.max())),
                ("ages above 100", int((age > 100).sum())),
                (
                    "drivers younger than 14",
                    int(((age < 14) & people.person_role.eq("driver")).sum()),
                ),
            ],
            columns=["measure", "value"],
        ),
        "victimisation": people.groupby(
            ["Descripcio_victimitzacio", "victimisation", "injury_severity"], dropna=False
        )
        .size()
        .rename("person_records")
        .reset_index()
        .assign(
            Descripcio_victimitzacio=lambda d: d.Descripcio_victimitzacio.replace("", "(blank)")
        )
        .sort_values("person_records", ascending=False),
        "target": people["serious_or_fatal"]
        .astype("object")
        .fillna("excluded (not recorded / natural death)")
        .value_counts()
        .rename("person_records")
        .rename_axis("serious_or_fatal")
        .reset_index(),
        "missing_by_role": people.assign(
            victimisation_blank=people.injury_severity.eq("not_recorded"),
            age_blank=people.age.isna(),
            sex_blank=people.sex.eq("not recorded"),
        )
        .groupby("person_role")[["victimisation_blank", "age_blank", "sex_blank"]]
        .sum()
        .reset_index(),
    }


def cause_domains(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out = {}
    for role, column in (
        ("bcn_mediate_causes", "Descripcio_causa_mediata"),
        ("bcn_driver_causes", "Causa_conductor"),
    ):
        frame = tables[role]
        rows = frame[column].replace("", "(blank)").value_counts().rename("rows")
        crashes = frame.drop_duplicates([KEY, column])[column].replace("", "(blank)")
        out[role] = (
            pd.concat([rows, crashes.value_counts().rename("crashes")], axis=1)
            .rename_axis("category")
            .reset_index()
        )
    return out


# ----------------------------------------------------------------------------- Catalonia
def cat_profile(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
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
    placeholders = []
    for column in source_columns:
        text = frame[column].astype(str).str.strip()
        row = {"column": column, "distinct_values": int(text.nunique())}
        for value in CAT_PLACEHOLDERS:
            row[f"'{value}'" if value else "blank"] = int(text.eq(value).sum())
        placeholders.append(row)
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
    checks = pd.DataFrame(
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
    speed = pd.crosstab(frame["C_VELOCITAT_VIA"], [frame["D_LIMIT_VELOCITAT"], frame["zona"]])
    speed.columns = [f"{a} / {b}" for a, b in speed.columns]
    by_year = frame.groupby("year").agg(crashes=("fatal", "size"), fatal=("fatal", "sum"))
    by_year["fatal_share"] = by_year.fatal / by_year.crashes
    geography = frame.groupby("demarcation").agg(
        crashes=("fatal", "size"),
        comarques=("comarca", "nunique"),
        municipalities=("municipality", "nunique"),
    )
    domains = []
    for column in [c for c in frame.columns if c.startswith("D_")] + ["tipAcc", "zona"]:
        counts = frame[column].value_counts()
        domains.append(
            {
                "column": column,
                "categories": int(len(counts)),
                "values": "; ".join(f"{k} ({v:,})" for k, v in counts.items()),
            }
        )
    return {
        "checks": checks,
        "placeholders": pd.DataFrame(placeholders),
        "speed": speed,
        "by_year": by_year.reset_index(),
        "geography": geography.reset_index(),
        "domains": pd.DataFrame(domains),
    }


# ----------------------------------------------------------------------------- report
def build() -> str:
    tables = bcn_tables()
    crashes = barcelona.read_crashes()
    people = barcelona.read_people()
    structure = bcn_structure(tables)
    nulls = bcn_null_rates(tables)
    semantics = bcn_count_semantics(crashes, people)
    context = bcn_context_consistency(tables)
    profile = bcn_people_profile(people)
    causes = cause_domains(tables)
    coords = coordinates.audit(tables, KEY, "bcn_people")
    vehicle = vehicles.write()
    cat = catalonia.read()
    catp = cat_profile(cat)

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, frame in {
        "mq_bcn_structure": structure,
        "mq_bcn_null_rates": nulls,
        "mq_bcn_count_semantics": semantics,
        "mq_bcn_coordinates": coords,
        "mq_cat_checks": catp["checks"],
        "mq_cat_placeholders": catp["placeholders"],
    }.items():
        frame.to_csv(TABLES_DIR / f"{name}.csv", index=False)

    sem = dict(zip(semantics.check, semantics.value))
    context_min = context.groupby("table").share_equal_to_crash_table.min().reset_index()
    nulls_shown = nulls[nulls.blank_rows > 0].sort_values(
        ["table", "blank_share"], ascending=[True, False]
    )
    coords_shown = coords[
        [
            "table",
            "header_order",
            "rows_x_label_holds_easting",
            "rows_x_label_holds_northing",
            "share_matching_reference_after_correction",
            "offset_east_median_m",
            "offset_north_median_m",
            "offset_spread_max_m",
        ]
    ]
    lines = [
        "# Data quality: the crash-level microdata",
        "",
        "Generated by `python scripts/microdata.py quality`; do not edit by hand. Every figure below",
        "is computed from `data/raw/barcelona/2025/` and `data/raw/catalonia/` on each build. The",
        "rules these checks enforce are in [`DATA_CONTRACT.md`](DATA_CONTRACT.md).",
        "",
        "## Barcelona 2025 (Guàrdia Urbana)",
        "",
        "### Tables, keys and cardinality",
        "",
        "The six files share `Numero_expedient` (spelt `Número_expedient` in the driver-cause file;",
        "only the column *name* is normalised). Every table holds exactly the same set of crash ids",
        "as the crash table: none is missing and none is extra.",
        "",
        _md(structure),
        "",
        "- One-to-one: the crash table and the accident-type table each have one row per id, and",
        '  their merge is run with `validate="one_to_one"` on every build.',
        "- One-to-many: mediate causes, driver causes, people and vehicle records have more than one",
        "  row for some crashes; the cause tables are aggregated to one row per crash *before* any",
        "  join, and people stay at person level with crash context joined `many_to_one`.",
        "",
        "### Counts: what a blank means",
        "",
        f"No count cell in the crash table holds an explicit `0` "
        f"({sem[EXPLICIT_ZERO]:,} cells); zeros are left blank. "
        "Reading a blank as zero is checked, not assumed:",
        "",
        _md(semantics),
        "",
        "The serious and minor injury counts agree with the person table crash by crash where the",
        "rows above say so; deaths in the crash table match persons who died *within 24 hours*",
        "(the person table also records deaths after 24 hours and one natural death, which the",
        "crash table does not count). The crash-level target `serious_or_fatal_crash` uses the",
        "crash table's counts; the person-level target uses the person's own victimisation.",
        "",
        "### Repeated place and time columns",
        "",
        "Each table repeats the crash's place and time. The lowest agreement with the crash table,",
        "over district, neighbourhood, street, month, day, hour, shift and WGS84 position:",
        "",
        _md(context_min),
        "",
        "### People",
        "",
        _md(profile["age"]),
        "",
        "Victimisation categories exactly as published, with the project's grouping. `Mort",
        "natural` (a natural death) is not an injury outcome and is excluded from every injury",
        "target; a blank is *not recorded*, never *uninjured*:",
        "",
        _md(profile["victimisation"]),
        "",
        "The person-level target `serious_or_fatal`:",
        "",
        _md(profile["target"]),
        "",
        "Missing fields by role (person records):",
        "",
        _md(profile["missing_by_role"]),
        "",
        "The pedestrian-cause column of the person table (`Descripcio_causa_vianant`) holds the same",
        "value on every person record of a crash: it is crash-level, not the person's own, and is",
        "used only as crash context.",
        "",
        "### Recorded causes",
        "",
        "Mediate causes (rows, and crashes with the category). A blank row is the only row of its",
        "crash: it means no mediate cause was recorded. The file has no category for an explicitly",
        "absent cause, so a cause flag that is `False` means *not recorded*.",
        "",
        _md(causes["bcn_mediate_causes"]),
        "",
        "Driver-related causes. `No determinada` (not determined) is kept as its own status; the",
        "table has no key to a person or vehicle, so a cause is attached to the crash only.",
        "",
        _md(causes["bcn_driver_causes"]),
        "",
        "### Coordinates",
        "",
        "In Spain a UTM easting is below 1,000,000 m and a northing above 3,000,000 m, so the size",
        "of a value says which it is. The crash file lists `Coordenada_UTM_Y_ED50` before",
        "`Coordenada_UTM_X_ED50` and its `X` column holds northings: its two labels are exchanged.",
        "The other five files are labelled correctly. After exchanging them back (in new columns",
        "`utm_x_ed50`/`utm_y_ed50`, with `utm_labels_swapped_in_source`; the source columns are",
        "untouched), every file gives the crash the same position as the person table, and the",
        "UTM position differs from the WGS84 longitude and latitude projected to UTM 31N by one",
        "constant offset, the ED50 datum shift, with a spread of centimetres. Maps use WGS84.",
        "",
        _md(coords_shown),
        "",
        "### Vehicle records",
        "",
        "See [`BARCELONA_VEHICLE_AUDIT.md`](BARCELONA_VEHICLE_AUDIT.md): "
        f"{int(vehicle['counts'].value.iloc[0]):,} records against "
        f"{int(vehicle['counts'].value.iloc[2]):,} vehicles reported. Unique-vehicle analyses are",
        "quarantined; only the presence of a vehicle type in a crash is used.",
        "",
        "### Blank cells by column",
        "",
        _md(nulls_shown),
        "",
        "## Catalonia 2010–2023 (crashes with a death or serious injury)",
        "",
        "The universe is conditioned on severity: every row has at least one death or serious",
        "injury. The file has no crash identifier; `cat_crash_id` is the data row of the",
        "hash-pinned file.",
        "",
        _md(catp["checks"]),
        "",
        "No row is a full duplicate. The rows identical in everything but the time are reported",
        "and kept: two crashes on the same day, road and place with the same victims are possible,",
        "and nothing in the file says they are one.",
        "",
        "### By year",
        "",
        _md(catp["by_year"]),
        "",
        "### Geography",
        "",
        _md(catp["geography"]),
        "",
        "### The speed-limit field",
        "",
        "`C_VELOCITAT_VIA` is the road's limit, not a vehicle's speed. It is a number only when",
        "`D_LIMIT_VELOCITAT` is `Senyal velocitat` (a posted limit). Under `Genérica via` it holds",
        "100, 999 or `NA` whatever the road (100 on urban streets as on interurban roads), so there",
        "it is a code: `speed_limit_kmh` is kept only for posted limits and the generic case is its",
        "own category. Crashes by value, kind of limit and zone:",
        "",
        _md(catp["speed"], index=True),
        "",
        "### Placeholders by column",
        "",
        '`NA` and `Sense especificar` are kept as categories of their own, never read as "no".',
        "",
        _md(catp["placeholders"][catp["placeholders"].iloc[:, 2:].sum(axis=1) > 0]),
        "",
        "### Category domains",
        "",
        _md(catp["domains"]),
        "",
    ]
    text = "\n".join(lines)
    REPORT.write_text(text, encoding="utf-8")
    return text
