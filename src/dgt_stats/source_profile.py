"""How each source came to exist: a data-generating-process comparison, computed where it can be.

For every source the project reads, the same questions: who records it, what one row is, what
gets a row (the inclusion rule), how severity is defined, which places and years it covers, when
each kind of variable becomes known, what is observed directly and what is coded afterwards, how
missing and "not specified" values behave, which identifiers exist, and which recording artefacts
are known. Each answer carries its basis:

* ``measured``: computed from the file by this module;
* ``reconciled``: measured against another source on the cases both hold;
* ``file``: read off the file's own columns or codes (a label, a coding);
* ``documentation``: the publisher's dictionary, catalogue record or download page (in the
  manifest), used for definitions only, never for observations.

Writes ``reports/tables/source_comparison.csv`` (one row per source and question) and
``docs/SOURCE_COMPARISON.md``. The layer each source belongs to is :mod:`dgt_stats.layers`.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import io_population, layers
from dgt_stats.paths import DGT_PROCESSED_CRASHES, DOCS_DIR, PROCESSED_DATA_DIR, TABLES_DIR

DOC = DOCS_DIR / "SOURCE_COMPARISON.md"
TABLE = TABLES_DIR / "source_comparison.csv"
QUESTIONS = (
    "layer",
    "who records",
    "unit of observation",
    "inclusion rule",
    "severity definition",
    "geography",
    "time coverage",
    "when variables are known",
    "observed or coded afterwards",
    "missing and not specified",
    "identifiers",
    "known recording artefacts",
    "used for",
    "never used for",
)


def _table(name: str) -> pd.DataFrame | None:
    path = TABLES_DIR / f"{name}.csv"
    return pd.read_csv(path) if path.exists() else None


def _years(values: pd.Series) -> str:
    years = pd.to_numeric(values, errors="coerce").dropna().astype(int)
    return f"{years.min()}-{years.max()}" if years.min() != years.max() else str(years.min())


# ----------------------------------------------------------------------------- DGT
def dgt_microdata() -> list[tuple[str, str, str]]:
    frame = pd.read_parquet(
        DGT_PROCESSED_CRASHES,
        columns=[
            "ANYO",
            "ID_ACCIDENTE",
            "COD_PROVINCIA",
            "TOTAL_MU24H",
            "TOTAL_MU30DF",
            "TOTAL_HG24H",
        ],
    )
    d24 = pd.to_numeric(frame.TOTAL_MU24H, errors="coerce").fillna(0)
    d30 = pd.to_numeric(frame.TOTAL_MU30DF, errors="coerce").fillna(0)
    later = (d30.sum() - d24.sum()) / d30.sum()
    duplicates = int(frame.duplicated(["ANYO", "ID_ACCIDENTE"]).sum())
    regional = _table("dgt_audit_regional")
    outcome = _table("dgt_audit_outcome_recording")
    checks = _table("dgt_audit_checks")
    if regional is not None:
        missing = (
            f"median share unrecorded (not specified, unknown or blank) over "
            f"{len(regional)} circumstance fields {regional.unrecorded_share.median():.1%}, "
            f"highest {regional.unrecorded_share.max():.0%} "
            f"({regional.loc[regional.unrecorded_share.idxmax(), 'field']}); "
            f"{int((~regional.comparable_across_provinces).sum())} fields vary by more than 10 "
            "points between provinces"
        )
    else:
        missing = "run `scripts/microdata.py validate` for the measured shares"
    if outcome is not None:
        dependent = outcome[
            (outcome.unrecorded_share_not_fatal >= 0.01)
            & (
                (outcome.ratio_fatal_to_not_fatal >= 1.5)
                | (outcome.ratio_fatal_to_not_fatal <= 1 / 1.5)
            )
        ]
        artefacts = (
            f"{dependent.field.nunique()} fields whose unrecorded share differs by a factor of "
            "1.5 or more between fatal and non-fatal crashes in at least one region "
            f"({', '.join(sorted(dependent.field.unique())[:6])}"
            + (", ..." if dependent.field.nunique() > 6 else "")
            + "); unrecorded shares differ between provinces (see the DGT microdata audit)"
        )
    else:
        artefacts = "see the DGT microdata audit"
    decision = checks.decision.iloc[0] if checks is not None else "see the DGT microdata audit"
    return [
        (
            "who records",
            "compiled and published by the Dirección General de Tráfico (catalogue "
            "record); the recording police force is not a column of the file",
            "documentation",
        ),
        (
            "unit of observation",
            f"one crash with victims; {len(frame):,} rows, {duplicates} "
            "duplicate keys (year, ID_ACCIDENTE)",
            "measured",
        ),
        (
            "inclusion rule",
            "every crash with at least one victim on a public road, urban or "
            "interurban; rows reproduce the yearbook's annual crash totals",
            "reconciled",
        ),
        (
            "severity definition",
            "deaths within 24 hours and within 30 days, hospitalised over "
            f"24 hours, slight injuries, as separate counts; {later:.1%} of 30-day deaths occur "
            "after the first 24 hours",
            "measured",
        ),
        (
            "geography",
            f"{frame.COD_PROVINCIA.nunique()} provinces and municipality codes; urban "
            "or interurban zone",
            "measured",
        ),
        ("time coverage", _years(frame.ANYO), "measured"),
        (
            "when variables are known",
            "time, place, road and conditions at the scene; 30-day "
            "deaths after a follow-up of a month",
            "file",
        ),
        (
            "observed or coded afterwards",
            "circumstance codes describe the scene; no cause or "
            "contributory-factor field in the crash file",
            "file",
        ),
        ("missing and not specified", missing, "measured"),
        (
            "identifiers",
            "ID_ACCIDENTE unique within a year; no person or vehicle file in the "
            "repository; no key shared with the regional files",
            "measured",
        ),
        ("known recording artefacts", artefacts, "measured"),
        (
            "used for",
            "national trends, province and year comparisons, shares by zone and road; "
            "an external test domain for fields validated against the Catalan file (audit decision: "
            + decision
            + ")",
            "measured",
        ),
        (
            "never used for",
            "linking records to the Catalan or Barcelona files; denominators for "
            "individual crashes",
            "documentation",
        ),
    ]


def dgt_aggregates() -> list[tuple[str, str, str]]:
    inventory = _table("data_inventory")
    tables = (
        inventory[inventory.path.str.startswith(("raw/dgt/tables", "raw/dgt/census", "raw/dgt/km"))]
        if inventory is not None
        else pd.DataFrame()
    )
    population = io_population.read_population()
    return [
        (
            "who records",
            "DGT (yearbook series, statistical tables, driver census, kilometre "
            "estimates from vehicle inspections); INE (resident population)",
            "documentation",
        ),
        (
            "unit of observation",
            "published aggregates: a count for a year (and province, age, "
            f"sex or vehicle type); {len(tables)} DGT files; INE residents by province, age and sex "
            f"({len(population):,} rows)",
            "measured",
        ),
        (
            "inclusion rule",
            "as published; the crash series reconcile with the crash microdata year by year",
            "reconciled",
        ),
        (
            "severity definition",
            "deaths within 30 days (24 hours in the monthly series); hospitalised injuries",
            "documentation",
        ),
        (
            "geography",
            f"Spain and its {population.loc[population.province_code.str.isdigit(), 'province_code'].nunique()} provinces",
            "measured",
        ),
        (
            "time coverage",
            f"yearbook series from 1993; residents {_years(population.year)}",
            "measured",
        ),
        ("when variables are known", "after the year closes", "documentation"),
        (
            "observed or coded afterwards",
            "aggregated from records; kilometres are model "
            "estimates from inspection odometer readings, by owner age not driver age",
            "documentation",
        ),
        (
            "missing and not specified",
            "a published table has no missing cells; categories such "
            "as 'unknown age' are reported as their own rows",
            "file",
        ),
        ("identifiers", "none below the published cell", "file"),
        (
            "known recording artefacts",
            "category changes between yearbook editions (for example "
            "personal mobility vehicles get their own column from 2020)",
            "file",
        ),
        (
            "used for",
            "trends, exposure and denominators at the level they are published "
            "(Spain or province, year)",
            "documentation",
        ),
        (
            "never used for",
            "rates for individual crashes; per-km rates by driver age (the "
            "kilometres are by owner age)",
            "documentation",
        ),
    ]


# ----------------------------------------------------------------------------- Catalonia
def catalonia_file() -> list[tuple[str, str, str]]:
    frame = pd.read_parquet(
        PROCESSED_DATA_DIR / "catalonia_severe_crashes.parquet",
        columns=["Any", "nomMun", "nomDem", "D_GRAVETAT"],
    )
    comparison = _table("cat_vs_dgt_province_year")
    artefacts = _table("ml_recording_artefacts")
    if comparison is not None:
        equal = int((comparison.ratio_fatal_24h == 1).sum())
        severe = (
            comparison.cat_crashes_fatal_or_serious / comparison.dgt_crashes_fatal_or_serious_24h
        )
        reconciliation = (
            f"fatal crashes equal DGT's crashes with a death within 24 hours in {equal} of "
            f"{len(comparison)} province-years; all crashes within "
            f"{(severe - 1).abs().max():.1%} of DGT's crashes with a death or serious injury "
            "within 24 hours"
        )
    else:
        reconciliation = "run `scripts/microdata.py analyse` for the reconciliation"
    if artefacts is not None:
        dependent = artefacts[artefacts.verdict.eq("outcome-dependent recording")]
        artefact_text = (
            f"{len(dependent)} placeholder levels ('Sense especificar' or an unexplained NA) are "
            "much rarer among fatal crashes (outcome-dependent recording): "
            + ", ".join(sorted(dependent.column.unique()))
            + "; these fields enter only the retrospective administrative model"
        )
    else:
        artefact_text = "see docs/ML_LEAKAGE_AUDIT.md"
    fatal = frame.D_GRAVETAT.astype(str).str.contains("mortal", case=False).sum()
    return [
        (
            "who records",
            "published by the Servei Català de Trànsit; the recording body is not a "
            "column of the file",
            "documentation",
        ),
        (
            "unit of observation",
            f"one crash; {len(frame):,} rows; no identifier in the source "
            "(a surrogate cat_crash_id is assigned)",
            "measured",
        ),
        (
            "inclusion rule",
            "crashes with at least one death or serious injury; " + reconciliation,
            "reconciled",
        ),
        (
            "severity definition",
            f"D_GRAVETAT 'Accident mortal' ({fatal:,} crashes) or 'Accident "
            "greu'; the death count matches DGT's 24-hour definition (see the inclusion rule)",
            "reconciled",
        ),
        (
            "geography",
            f"{frame.nomDem.nunique()} demarcations, {frame.nomMun.nunique()} "
            "municipalities, road and kilometre point",
            "measured",
        ),
        ("time coverage", _years(frame.Any), "measured"),
        (
            "when variables are known",
            "place, road, conditions and units involved at the scene; "
            "the D_INFLUIT_* 'influence' fields and several road descriptors after the report is "
            "completed",
            "file",
        ),
        (
            "observed or coded afterwards",
            "the D_INFLUIT_* fields record whether a condition "
            "'influenced' the crash: a judgement coded afterwards, not an observation",
            "file",
        ),
        (
            "missing and not specified",
            "'Sense especificar' and NA placeholders; NA is structural "
            "for some fields (no road owner on urban streets)",
            "measured",
        ),
        ("identifiers", "none; no person or vehicle rows", "file"),
        ("known recording artefacts", artefact_text, "measured"),
        (
            "used for",
            "the fatal-against-serious crash model, its temporal and geographic "
            "validation, the training domain of the transfer tests",
            "documentation",
        ),
        (
            "never used for",
            "crash frequency (no slight-injury crashes); driving speed (the speed "
            "field is the road's limit); linking records to DGT or Barcelona",
            "documentation",
        ),
    ]


# ----------------------------------------------------------------------------- Barcelona
def barcelona_files() -> list[tuple[str, str, str]]:
    crashes = pd.read_parquet(PROCESSED_DATA_DIR / "barcelona_accidents.parquet")
    people = pd.read_parquet(PROCESSED_DATA_DIR / "barcelona_people.parquet")
    structure = _table("mq_bcn_structure")
    vehicles = _table("bcn_vehicle_audit_counts")
    victim = people.victimisation.astype(str).value_counts()
    vehicle_text = ""
    if vehicles is not None:
        v = vehicles.set_index("measure").value
        vehicle_text = (
            f"; {int(v['vehicle records']):,} vehicle rows against "
            f"{int(v['vehicles reported by the crash table (sum)']):,} vehicles the crash table "
            "reports, so vehicle rows are not unique vehicles"
        )
    tables_text = (
        ", ".join(f"{r.table} {r.rows:,}" for r in structure.itertuples())
        if structure is not None
        else ""
    )
    return [
        (
            "who records",
            "the Guàrdia Urbana (municipal police); published by the Ajuntament de Barcelona",
            "documentation",
        ),
        ("unit of observation", f"six tables keyed by Numero_expedient: {tables_text}", "measured"),
        (
            "inclusion rule",
            "crashes the Guàrdia Urbana handled in the city, with or without "
            f"injury: {int(crashes.n_victims.eq(0).sum()):,} of {len(crashes):,} crashes have no "
            "victim",
            "measured",
        ),
        (
            "severity definition",
            "per person: died within 24 hours "
            f"({victim.get('died_within_24h', 0)}), died after 24 hours "
            f"({victim.get('died_after_24h', 0)}), hospitalised over 24 hours "
            f"({victim.get('serious_hospital_over_24h', 0)}), slight injuries in three kinds, "
            f"uninjured; not recorded for {victim.get('not_recorded', 0):,} person records",
            "measured",
        ),
        (
            "geography",
            f"{crashes.district.nunique()} districts, "
            f"{crashes.neighbourhood.nunique()} neighbourhoods, street and coordinates",
            "measured",
        ),
        (
            "time coverage",
            f"{_years(crashes.year)}, months {crashes.month.min()}-{crashes.month.max()}",
            "measured",
        ),
        (
            "when variables are known",
            "time, place, people, vehicles at the scene; causes "
            "(mediate, driver, pedestrian) after the police report",
            "file",
        ),
        (
            "observed or coded afterwards",
            f"causes are the police's coding: a mediate cause is "
            f"recorded for {crashes.mediate_cause_status.eq('recorded').mean():.1%} of crashes, a "
            f"pedestrian cause for {crashes.pedestrian_cause_recorded.mean():.1%}",
            "measured",
        ),
        (
            "missing and not specified",
            "blank count cells mean zero (no explicit zero appears "
            "and the counts add up in every crash); blank cause rows mean none recorded",
            "measured",
        ),
        (
            "identifiers",
            "Numero_expedient links the six tables one crash to many rows; no "
            "person or vehicle key" + vehicle_text,
            "measured",
        ),
        (
            "known recording artefacts",
            "the crash file's UTM columns carry exchanged labels "
            "(corrected, offset measured against WGS84); driver causes have no key to the driver "
            "concerned",
            "measured",
        ),
        (
            "used for",
            "person and crash severity, road users, recorded causes; diagnostics and "
            "external checks of the Catalan model",
            "documentation",
        ),
        (
            "never used for",
            "trends (one year); unique-vehicle analysis; linking to Catalan or DGT records",
            "documentation",
        ),
    ]


SOURCES = (
    ("DGT crash microdata", layers.NATIONAL, dgt_microdata),
    ("DGT and INE published aggregates", layers.NATIONAL, dgt_aggregates),
    ("Catalonia, Servei Català de Trànsit", layers.CATALONIA, catalonia_file),
    ("Barcelona, Guàrdia Urbana", layers.BARCELONA, barcelona_files),
)


def build() -> pd.DataFrame:
    rows = []
    for name, layer, facts in SOURCES:
        rows.append({"source": name, "question": "layer", "answer": layer.title, "basis": "file"})
        for question, answer, basis in facts():
            rows.append({"source": name, "question": question, "answer": answer, "basis": basis})
    frame = pd.DataFrame(rows)
    unknown = set(frame.question) - set(QUESTIONS)
    if unknown:
        raise ValueError(f"questions outside the declared list: {unknown}")
    return frame


def document(frame: pd.DataFrame) -> str:
    lines = [
        "# How each source came to exist",
        "",
        "Generated by `src/dgt_stats/source_profile.py`; measured answers are computed from the "
        "files each time the pipeline runs. Do not edit by hand.",
        "",
        "Every source is described against the same questions. The *basis* says where each "
        "answer comes from: measured from the file, reconciled against another source, read off "
        "the file's own columns, or taken from the publisher's documentation (definitions only).",
        "",
        "## Layers",
        "",
        "| Layer | Unit | Answers | Not for |",
        "|---|---|---|---|",
    ]
    for layer in layers.LAYERS:
        lines.append(
            f"| {layer.title} | {layer.unit} | {'; '.join(layer.answers)} | "
            f"{'; '.join(layer.not_for)} |"
        )
    lines += [
        "",
        "No layer is merged into another and no record is linked across sources. Cross-source "
        "data test models (a model trained in one source scored on another's real records) or "
        "meet at a shared published aggregate (province and year); they never create "
        "observations.",
        "",
    ]
    for source, group in frame.groupby("source", sort=False):
        lines += [f"## {source}", "", "| Question | Answer | Basis |", "|---|---|---|"]
        for row in group.itertuples():
            lines.append(f"| {row.question} | {row.answer.replace('|', '/')} | {row.basis} |")
        lines.append("")
    return "\n".join(lines)


def write() -> pd.DataFrame:
    frame = build()
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLE, index=False)
    DOC.write_text(document(frame), encoding="utf-8")
    return frame
