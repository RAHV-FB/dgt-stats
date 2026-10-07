"""Data sources and scope: what each dataset is, how the sources meet, and what they leave out."""

from __future__ import annotations

import re

import pandas as pd

from dgt_stats.microdata.validation import dgt_audit
from dgt_stats.site.components import (
    ALL_PAGES,
    DOCS_URL,
    _fmt_int,
    _fmt_pct,
    _join,
    downloads,
    esc,
    read_table,
    render_page,
    summary,
    table,
)
from dgt_stats.site.regional_common import _check, _year_label

TITLES = dict(ALL_PAGES)

# What the files do not record, each with what they hold instead. The first item of each pair
# is the subject; the second says what the files contain.
SCOPE: tuple[tuple[str, str], ...] = (
    (
        "Vehicle speeds",
        "No file records how fast a vehicle was travelling; the Catalan file's speed field is "
        "the posted limit of the road.",
    ),
    (
        "People and vehicles in Catalan crashes",
        "Catalonia publishes one row per crash and no linked person or vehicle records.",
    ),
    (
        "Alcohol and drug tests",
        "Barcelona records alcohol and drugs as causes the police attributed to a crash; no "
        "source holds a test result.",
    ),
    (
        "Individual people across Spain",
        "Person records exist only for Barcelona, so a model of individual people is fitted "
        "there alone.",
    ),
    (
        "Who did what in a Barcelona crash",
        "The driver-cause and vehicle tables do not identify the person or vehicle concerned.",
    ),
    (
        "Road design and crash sites",
        "DGT's records locate a crash by road, kilometre point and municipality, without "
        "coordinates, detailed road geometry or traffic volume.",
    ),
    (
        "Risk per trip or per kilometre in Catalonia or Barcelona",
        "Neither source has a measure of travel; their only rates are per resident, at province "
        "level.",
    ),
)


def _words(number: int) -> str:
    """A count under ten in words, as in running prose."""
    words = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
    return words[number - 1] if 1 <= number <= len(words) else _fmt_int(number)


def _span(years: list[int]) -> str:
    """'a–b' for consecutive years, 'a and b' (or a list) otherwise."""
    years = sorted(set(years))
    if len(years) == 1:
        return str(years[0])
    if years == list(range(years[0], years[-1] + 1)):
        return f"{years[0]}–{years[-1]}"
    return _join([str(year) for year in years])


def _inventory_years(inventory: pd.DataFrame, prefix: str, contains: str = "") -> list[int]:
    """The years the raw files under ``prefix`` cover, read from the data inventory."""
    rows = inventory[
        inventory.path.str.startswith(prefix) & inventory.path.str.contains(contains, regex=False)
    ]
    found: set[int] = set()
    for text in rows.coverage.astype(str):
        for first, last in re.findall(r"(\d{4})-(\d{4})", text):
            found.update(range(int(first), int(last) + 1))
        found.update(int(year) for year in re.findall(r"\d{4}", text))
    years = sorted(found)
    _check(bool(years), "sources", f"the inventory dates the files under {prefix}")
    return years


def _span_of(values: pd.Series) -> str:
    years = pd.to_numeric(values, errors="coerce").dropna().astype(int)
    return _span(list(years))


def _source_table(numbers: dict[str, str], inventory: pd.DataFrame) -> str:
    stats_years = _inventory_years(inventory, "raw/dgt/tables/chapters/") + _inventory_years(
        inventory, "raw/dgt/tables/tablas_estadisticas"
    )
    census_years = _inventory_years(inventory, "raw/dgt/census/")
    census_text = min(_inventory_years(inventory, "raw/dgt/census/censo_conductores"))
    km_years = _inventory_years(inventory, "raw/dgt/km_itv_")
    km_owner = _span(_inventory_years(inventory, "raw/dgt/km_itv_", "edad_propietario"))
    km_type = _span_of(read_table("q6_rates_2022").year)
    _check(
        len(km_years) == 2 and km_type != km_owner,
        "sources",
        "two kilometre releases, one used by vehicle type and the other by owner's age",
    )
    residents = _span(_inventory_years(inventory, "raw/ine/ine_poblacion"))
    toll_from = min(_inventory_years(inventory, "raw/transportes/peaje"))
    rows = [
        (
            "National crash records",
            "DGT",
            f"Spain, every province, {numbers['dgt_span']}",
            f"One row per crash with at least one victim ({numbers['dgt_rows']} crashes).",
            "Counts and shares by zone and road type; the association analysis of crash "
            "circumstances; the external test of the Catalonia severity model.",
        ),
        (
            "Yearbook series",
            "DGT",
            f"Spain and its provinces, {numbers['yearbook_span']}",
            "Annual, monthly and provincial totals of crashes and casualties.",
            "National trends and seasons; the monthly deaths forecast; the points-licence "
            "study; the totals the crash records are checked against.",
        ),
        (
            "Statistical tables",
            "DGT",
            f"Spain, {_span(stats_years)}",
            "Drivers involved and killed by age, sex and vehicle; vehicles involved by type; "
            "drivers by recorded infraction.",
            "Drivers and vehicles in crashes; drivers recorded with a speed infraction.",
        ),
        (
            "Speed-factor report",
            "DGT",
            f"Spain outside Catalonia and the Basque Country, {numbers['factor_span']}",
            "Injury crashes with each recorded concurrent factor, and deaths in those with speed.",
            "Speed and the other recorded factors; never added to national totals.",
        ),
        (
            "Driver census",
            "DGT",
            f"Spain by province, {_span(census_years)}",
            "Licence holders by province, sex and age band; holders of a car licence (B permit) "
            f"by age and sex in the text files from {census_text}.",
            "Rates per licence holder; car-licence holders by age for the analysis of drivers.",
        ),
        (
            "Kilometre estimates",
            "DGT",
            f"Spain, {_span(km_years)}",
            "Circulating fleet and mean annual kilometres from the odometer readings of "
            "roadworthiness inspections, in two releases built by different methods; the "
            f"{km_owner} release also by the owner's age band.",
            f"Rates per kilometre by vehicle type ({km_type}) and by the owner's age band "
            f"({km_owner}).",
        ),
        (
            "Resident population",
            "INE",
            f"Spain by province, {residents}",
            "Residents by five-year age group and sex.",
            "Rates per resident.",
        ),
        (
            "Road fuel",
            "CORES",
            f"Spain, monthly; complete years {numbers['fuel_span']}",
            "Tonnes of automotive petrol and diesel sold, biofuels included.",
            "The traffic denominator of the national trends and seasons; an input of the monthly "
            "deaths forecast; a covariate in the points-licence study.",
        ),
        (
            "Toll-motorway traffic",
            "Ministerio de Transportes",
            f"State toll motorways, monthly from {toll_from}",
            "Average daily traffic and vehicle-kilometres on the toll network.",
            "A traffic index beside deaths by month; a covariate in the points-licence study; "
            "never a denominator.",
        ),
        (
            "Interurban vehicle-kilometres",
            "Ministerio de Transportes",
            f"State, regional and provincial road networks, {numbers['km_span']}",
            "Vehicle-kilometres by road type.",
            "Interurban deaths per measured kilometre, overall and by road type.",
        ),
        (
            "Catalan crash records",
            "Servei Català de Trànsit",
            f"Catalonia, {numbers['cat_span']}",
            "One row per crash with at least one death or serious injury "
            f"({numbers['cat_rows']} crashes).",
            "The analysis of Catalan crashes; the Catalonia severity model and its validation.",
        ),
        (
            "Barcelona crash records",
            "Ajuntament de Barcelona (Guàrdia Urbana)",
            f"Barcelona city, {numbers['bcn_year']}",
            f"Six linked tables: {numbers['bcn_crashes']} crashes, {numbers['bcn_people']} "
            "person records, vehicle records, crash types and recorded causes.",
            "The analysis of Barcelona crashes and people; the Barcelona person-severity model; "
            "tests of the Catalonia severity model.",
        ),
    ]
    frame = pd.DataFrame(
        rows, columns=["Source", "Published by", "Coverage", "Records", "Used for"]
    )
    policy = f'<a href="policy.html">{esc(TITLES["policy"])}</a>'
    return (
        table(frame, "Sources used in the study.")
        + "<p>The yearbook series, monthly as well as annual, and the statistical tables count "
        "deaths within 30 days; the yearbook's monthly 24-hour series is used only to check the "
        f"crash records and in one sensitivity test of {policy} "
        '(<a href="data.html#definitions">definitions</a>).</p>'
    )


def _crash_records(numbers: dict[str, str]) -> str:
    quality = f'<a href="{DOCS_URL}/DATA_QUALITY_MICRODATA.md">data-quality report</a>'
    return (
        "<h2>The three sets of crash records</h2>"
        "<p>DGT's national file has one row per crash with at least one victim. It records the "
        "place, time, road and conditions, and counts the victims by severity, with deaths both "
        "within 24 hours and within 30 days. It has no rows for drivers, vehicles or people, so "
        "the analysis of drivers uses DGT's aggregate tables.</p>"
        "<p>The Catalan file has one row per crash with at least one death or serious injury: "
        f"{numbers['cat_fatal']} of its {numbers['cat_rows']} crashes ({numbers['cat_share']}) "
        "were fatal. Crashes with only slight injuries are not in the file. Deaths are counted "
        "within 24 hours, and there is no crash identifier. Its “influence” fields record "
        "whether the police judged that a condition, such as fog or wind, influenced the "
        "crash.</p>"
        f"<p>Barcelona's Guàrdia Urbana publishes six tables for {numbers['bcn_year']} that "
        f"share a case number: crashes ({numbers['bcn_crashes']}, of which "
        f"{numbers['bcn_no_victim']} record no victim), crash types, contributing factors, "
        f"driver causes, people ({numbers['bcn_people']} records) and vehicles "
        f"({numbers['bcn_vehicles']} records). Each person's injury is recorded, with deaths "
        f"within 24 hours kept apart from later deaths: {numbers['bcn_dead']} people died and "
        f"{numbers['bcn_serious']} were seriously injured, and {numbers['bcn_not_recorded']} "
        "person records carry no severity. The vehicle table has more rows than the crash table "
        f"reports vehicles ({numbers['bcn_reported']}), so a vehicle row is not a unique "
        "vehicle; this and a correction to the crash table's coordinates are described in the "
        f"{quality}.</p>"
    )


def _meeting(cat_dgt: pd.DataFrame) -> str:
    equal = int((cat_dgt.ratio_fatal_24h == 1).sum())
    _check(equal == len(cat_dgt), "sources", "fatal counts equal DGT's in every province-year")
    period = _span_of(cat_dgt.year)
    return (
        "<h2>How the sources meet</h2>"
        "<p>The files share no identifier, and crashes are not matched on date or place. The "
        "sources meet in two ways. At province-year totals, "
        "the Catalan file's fatal crashes equal DGT's crashes with a death within 24 hours in "
        f"every province-year of {period} "
        '(<a href="catalonia.html#dgt-agreement">Catalonia</a>). In '
        "held-out tests, versions of the Catalonia severity model restricted to the variables "
        "another source records in the same way score DGT's crash records elsewhere in Spain "
        "and Barcelona's crashes, without merging either with the Catalan file "
        '(<a href="validation.html">External validation</a>).</p>'
    )


def _audit() -> str:
    checks = read_table("dgt_audit_checks")
    artefacts = read_table("dgt_audit_artefacts")
    regional = read_table("dgt_audit_regional")
    decision = str(checks.decision.iloc[0])
    numbered = checks[checks.check.str.match(r"\d")]
    failed = numbered[~numbered.passed.astype(bool)]
    _check(
        set(failed.check.str.split().str[0]) == {"6", "7"},
        "sources",
        "the audit finds the file complete and fails on regional comparability and blanks only",
    )
    _check(
        decision.startswith("DGT microdata stay")
        and not decision.startswith("DGT microdata may train")
        and "do not train" in decision,
        "sources",
        "the national records do not train a severity model",
    )
    comparable = int(regional.comparable_across_provinces.astype(bool).sum())
    priority = regional[regional.field.str.startswith("PRIORI_")]
    _check(
        not priority.empty and not priority.comparable_across_provinces.astype(bool).any(),
        "sources",
        "the right-of-way fields are not recorded alike across provinces",
    )
    _check(comparable < len(regional) / 2, "sources", "most fields are recorded unevenly")
    died_30 = artefacts[artefacts.target.str.contains("30 days")].iloc[0]
    died_24 = artefacts[artefacts.target.str.contains("24 hours")].iloc[0]
    _check(
        bool(died_30.artefacts_dominate) and not bool(died_24.artefacts_dominate),
        "sources",
        "blanks dominate for 30-day deaths and not among serious crashes",
    )
    _check(
        float(died_24.artefact_share_of_lift)
        < dgt_audit.MAX_ARTEFACT_SHARE
        < float(died_30.artefact_share_of_lift),
        "sources",
        "the artefact shares fall either side of the limit",
    )
    severity = f'<a href="severity.html">{esc(TITLES["severity"])}</a>'
    return (
        "<h2>Uneven recording in the national crash records</h2>"
        "<p>The national records reconcile with every published total, so they are the right "
        "source for counts, trends and comparisons between provinces. A model trained on them "
        "would also need each variable to mean the same everywhere. An audit with criteria "
        "fixed in advance found the file complete and consistent, but found two problems in "
        "what its variables mean.</p>"
        "<p>First, fields are recorded unevenly between provinces. Of the "
        f"{len(regional)} circumstance fields examined, {_words(comparable)} have a share of blanks "
        f"that varies by no more than {dgt_audit.MAX_REGIONAL_SPREAD * 100:.0f} percentage "
        "points across the provinces with at least "
        f"{_fmt_int(dgt_audit.MIN_PROVINCE_CRASHES)} crashes. The fields that record who had "
        f"right of way are blank in {_fmt_pct(priority.province_min.min(), 0)} of crashes in "
        f"one province and {_fmt_pct(priority.province_max.max(), 0)} in another.</p>"
        "<p>Second, the blanks themselves carry information about the outcome. A model that "
        "sees only which fields were left blank ranks crashes with a death within 30 days with "
        f"a ROC-AUC of {float(died_30.roc_auc_unrecorded_flags_only):.2f} "
        '(<a href="data.html#models">ranking measure</a>), against '
        f"{float(died_30.roc_auc_recorded_values):.2f} for a model that sees the recorded "
        f"values. The blanks alone give {_fmt_pct(float(died_30.artefact_share_of_lift), 0)} of "
        "the recorded model's gain over chance, above the "
        f"{_fmt_pct(dgt_audit.MAX_ARTEFACT_SHARE, 0)} limit set in advance; among crashes with "
        "a death or serious injury, the population of the external test, the share is "
        f"{_fmt_pct(float(died_24.artefact_share_of_lift), 0)}, below it. A model trained on all of Spain "
        "would learn, in part, how completely each province records its crashes.</p>"
        "<p>The national records are therefore used to describe Spain, including the "
        f"associations reported under {severity}, and, on the variables validated against the "
        "Catalan file, as an external test of the Catalonia severity model. They are not used "
        "to train a predictive severity model. The full audit is published as the "
        f'<a href="{DOCS_URL}/DGT_MICRODATA_AUDIT.md">DGT microdata audit</a>.</p>'
    )


def _scope() -> str:
    items = "".join(f"<li><strong>{esc(what)}.</strong> {esc(why)}</li>" for what, why in SCOPE)
    return (
        '<h2 id="scope">Scope of the data</h2>'
        f"<p>Several quantities lie outside what the files record:</p><ul>{items}</ul>"
        f'<p>The <a href="{DOCS_URL}/SOURCE_COMPARISON.md">source comparison</a> describes how '
        "each file is produced, and the "
        f'<a href="{DOCS_URL}/DATA_CONTRACT.md">usage rules</a> state how each may be used.</p>'
    )


# ----------------------------------------------------------------------------- sources
def page_sources(captions: dict[str, str]) -> str:
    validation = read_table("validation")
    inventory = read_table("data_inventory")
    rows = validation[validation.check == "row_count"]
    _check(
        bool(validation.passed.astype(bool).all()),
        "sources",
        "the national records reconcile with every published total",
    )
    shares = read_table("cat_fatal_share")
    overall = shares[(shares.dimension == "unit type involved") & (shares.level == "all")].iloc[0]
    structure = read_table("mq_bcn_structure").set_index("table")
    semantics = read_table("mq_bcn_count_semantics").set_index("check").value
    vehicles = read_table("bcn_vehicle_audit_counts").set_index("measure").value
    people = read_table("bcn_people_by_severity").groupby("injury_severity").person_records.sum()
    person_shares = read_table("bcn_person_severity_share")
    crashes = int(structure.loc["bcn_accidents", "rows"])
    explicit_zeros = int(semantics.filter(like="explicit zero").iloc[0])
    no_victim = int(semantics["blank cells in Numero_victimes"])
    reported = int(vehicles["vehicles reported by the crash table (sum)"])
    _check(explicit_zeros == 0 and no_victim > 0, "sources", "blank counts mean no victim")
    _check(int(structure.loc["bcn_vehicles", "rows"]) > reported, "sources", "vehicle rows")
    numbers = {
        "dgt_rows": _fmt_int(rows.actual.sum()),
        "dgt_span": _span_of(rows.year),
        "yearbook_span": _span_of(read_table("q1_annual_headline").year),
        "factor_span": _span_of(read_table("factor_shares").year),
        "fuel_span": _span_of(read_table("risk_frequency_severity").year),
        "km_span": _span_of(read_table("longrun_km_panel").year),
        "cat_span": _span_of(read_table("cat_frequency").year),
        "cat_rows": _fmt_int(overall.n),
        "cat_fatal": _fmt_int(overall.events),
        "cat_share": _fmt_pct(overall.share),
        "bcn_year": _year_label(person_shares),
        "bcn_crashes": _fmt_int(crashes),
        "bcn_people": _fmt_int(structure.loc["bcn_people", "rows"]),
        "bcn_vehicles": _fmt_int(structure.loc["bcn_vehicles", "rows"]),
        "bcn_reported": _fmt_int(reported),
        "bcn_no_victim": _fmt_int(no_victim),
        "bcn_dead": _fmt_int(people["fatal"]),
        "bcn_serious": _fmt_int(people["serious"]),
        "bcn_not_recorded": _fmt_int(people["not_recorded"]),
    }
    body = summary(
        "Beside DGT's national statistics, the study uses three sets of police crash records: "
        "DGT's national file of injury crashes, the Servei Català de Trànsit's file of crashes "
        "with a death or serious injury in Catalonia, and the Guàrdia Urbana's records for "
        "Barcelona city. Each is analysed separately. No record is linked across sources; they "
        "meet only at aggregate totals and in held-out tests of the models. The national crash "
        "records describe Spain but do not train a model, because their fields are recorded "
        "unevenly between provinces and their blanks carry information about the outcome."
    )
    body += "<h2>The sources</h2>"
    body += _source_table(numbers, inventory)
    body += _crash_records(numbers)
    body += _meeting(read_table("cat_vs_dgt_province_year"))
    body += _audit()
    body += _scope()
    body += downloads(
        [
            ("source_comparison", "source comparison"),
            ("data_inventory", "raw-file inventory"),
            ("dgt_audit_checks", "audit checks"),
            ("dgt_audit_regional", "blank shares by field and province"),
            ("dgt_audit_artefacts", "ranking from blanks alone"),
            ("dgt_audit_outcome_recording", "blank shares by outcome"),
        ],
        method=("data.html#records", "reading police crash records"),
    )
    return render_page(
        "sources",
        "Data sources and scope",
        "The published sources behind the study, from DGT's national yearbook to the police "
        "records of individual crashes in Barcelona.",
        body,
    )
