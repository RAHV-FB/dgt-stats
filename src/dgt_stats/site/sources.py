"""Data sources and scope: what each source is, what it covers and what it cannot show.

How the results are produced from the sources, the checks on them and the assumptions tested are
on the methodology page (``data``).
"""

from __future__ import annotations

import re

import pandas as pd

from dgt_stats.microdata.ml import recording
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
        "Rates per kilometre from the regional crash records",
        "Neither regional crash file has a measure of travel, so Catalonia's rates are per "
        "resident, at province level. Barcelona has rates per kilometre for car drivers by age "
        "on working days only, from the EMEF survey's kilometres driven inside the city, matched "
        'to the crash records in total, not record by record (<a href="drivers.html">Drivers</a>).',
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
    residents = _span(_inventory_years(inventory, "raw/ine/ine_poblacion_provincias"))
    single_ages = _span(_inventory_years(inventory, "raw/ine/ine_poblacion_edad_simple"))
    emef_years = _span(_inventory_years(inventory, "raw/emef/"))
    edm_year = _span(_inventory_years(inventory, "raw/crtm/"))
    toll_from = min(_inventory_years(inventory, "raw/transportes/peaje"))
    # The weekend age mix and the employment benchmark of the rates per km by driver age.
    weekend = read_table("risk_weekend_sensitivity").non_working_age_mix.dropna()
    movilia = sorted({m for label in weekend for m in re.findall(r"MOVILIA (\d{4})", label)})
    benchmark = read_table("emef_employment_benchmark")
    census = benchmark[benchmark.source.str.startswith("census")]
    _check(
        len(movilia) == 1 and len(census) == 1,
        "sources",
        "one MOVILIA survey and one census benchmark enter the sensitivity range",
    )
    rows = [
        (
            "National crash records",
            "DGT",
            f"Spain, every province, {numbers['dgt_span']}",
            f"One row per crash with at least one victim ({numbers['dgt_rows']} crashes).",
            "Counts and shares by zone and road type; the association analysis of crash "
            "circumstances; the external test of a version of the original Catalan model "
            "restricted to the variables both record alike.",
        ),
        (
            "Yearbook series",
            "DGT",
            f"Spain and its provinces, {numbers['yearbook_span']}",
            "Annual, monthly and provincial totals of crashes and casualties.",
            "National trends and seasons; the points-licence study; the totals the crash records "
            "are checked against.",
        ),
        (
            "Statistical tables",
            "DGT",
            f"Spain, {_span(stats_years)}",
            "Drivers involved and killed by age, sex and vehicle; vehicles involved by type; "
            "drivers by recorded infraction.",
            "Drivers and vehicles in crashes, including the car drivers by age behind the rates "
            "per kilometre by driver age; drivers recorded with a speed infraction.",
        ),
        (
            "Speed-factor report",
            "DGT",
            f"Spain outside Catalonia and the Basque Country, {numbers['factor_span']}",
            "Injury crashes with each police-recorded factor, and deaths in those with speed.",
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
            "Circulating fleet and mean annual kilometres by vehicle type, from the odometer "
            "readings of roadworthiness inspections, in two releases; the later one gives every "
            "year since the earlier one as one series, and kilometres by the owner's age band.",
            f"The national car-kilometre total behind the rates per kilometre by driver age "
            f"({km_owner}); rates per kilometre by vehicle type ({km_type}); kilometres by the "
            "owner's age band, as a comparison only.",
        ),
        (
            "Resident population",
            "INE",
            f"Spain by province, {residents}",
            "Residents by five-year age group and sex.",
            "Rates per resident; crashes per resident by province.",
        ),
        (
            "Population by single year of age",
            "INE",
            f"Spain, {single_ages}",
            "Residents of Spain by single year of age and sex.",
            "The population the survey age profiles are applied to for the national rates per "
            "kilometre by driver age.",
        ),
        (
            "Working-day mobility survey (EMEF)",
            "Autoritat del Transport Metropolità, Idescat and Institut Metròpoli",
            f"Barcelona area, working days, {emef_years}",
            "Public-use microdata of residents aged 16 and over of the ATM's planning area: one "
            "row per respondent and per trip, with sex, age group, mode and distance.",
            "Car-driving kilometres by age: the age profile behind the national rates per "
            "kilometre by driver age, and the kilometres driven inside Barcelona city behind its "
            "working-day rates.",
        ),
        (
            "Madrid household travel survey (EDM2018)",
            "Consorcio Regional de Transportes de Madrid",
            f"Comunidad de Madrid, Monday to Thursday, {edm_year}",
            "Public microdata: respondents with exact age and sex, and their trips as car "
            "drivers with distance.",
            "The split of driving between ages 65 to 74 and 75 and over, and a second age profile "
            "for the national rates per kilometre by driver age.",
        ),
        (
            "Mobility survey of Spain (MOVILIA)",
            "Ministerio de Transportes",
            f"Spain, {movilia[0]}",
            "Published tables of trips by age, main mode and type of day.",
            "One of the two weekend age mixes in the sensitivity range of the rates per "
            "kilometre by driver age.",
        ),
        (
            "Population census, relation with economic activity",
            "Idescat",
            f"Catalonia, 1 January {int(census.year.iloc[0])}",
            "Employed residents aged 65 and over.",
            "A check on the share of the EMEF's older respondents in work, one of the choices "
            "in the sensitivity range of the rates per kilometre by driver age.",
        ),
        (
            "Road fuel",
            "CORES",
            f"Spain, monthly; the analysis uses {numbers['fuel_span']}",
            "Tonnes of automotive petrol and diesel sold, biofuels included.",
            "The traffic denominator of the national trends and seasons; a covariate in the "
            "points-licence study.",
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
            "The analysis of Catalan crashes; the crash-severity calculator's model and its "
            "tests; the original Catalan model, now retired.",
        ),
        (
            "Barcelona crash records",
            "Ajuntament de Barcelona (Guàrdia Urbana)",
            f"Barcelona city, {numbers['bcn_year']}",
            f"Six linked tables: {numbers['bcn_crashes']} crashes, {numbers['bcn_people']} "
            "person records, vehicle records, crash types and recorded causes.",
            "The analysis of Barcelona crashes and people; the Barcelona person-severity model "
            "(research); tests of a version of the original Catalan model; car drivers involved "
            "per kilometre by age on working days, with the EMEF.",
        ),
    ]
    frame = pd.DataFrame(
        rows, columns=["Source", "Published by", "Coverage", "Records", "Used for"]
    )
    pages = _join(
        [f'<a href="{slug}.html">{esc(TITLES[slug])}</a>' for slug in ("long-run", "policy")]
    )
    long_run = read_table("longrun_projection_sensitivity")
    policy = read_table("q8_points_sensitivity")
    _check(
        long_run.variant.eq("deaths_24h").any() and policy.variant.eq("24h").any(),
        "sources",
        "the long-run trends and the points-licence study each have a 24-hour sensitivity test",
    )
    return (
        table(frame, "Sources used in the study.")
        + "<p>The yearbook series and the statistical tables count deaths within 30 days. The "
        "yearbook's deaths within 24 hours are used only to check the crash records and in "
        f"sensitivity tests on {pages} "
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
        "were fatal. Deaths are counted within 24 hours, and there is no crash identifier. Its "
        "“influence” fields record whether the police judged that a condition, such as fog or "
        "wind, influenced the crash.</p>"
        f"<p>Barcelona's Guàrdia Urbana publishes six tables for {numbers['bcn_year']} that "
        f"share a case number: crashes ({numbers['bcn_crashes']}, of which "
        f"{numbers['bcn_no_victim']} record no victim), crash types, contributing factors, "
        f"driver causes, people ({numbers['bcn_people']} records) and vehicles "
        f"({numbers['bcn_vehicles']} records). The person table records each person's injury, "
        f"with deaths within 24 hours kept apart from later deaths: {numbers['bcn_dead_24h']} "
        f"people died within 24 hours and {numbers['bcn_dead_later']} later, and "
        f"{numbers['bcn_serious']} were seriously injured; {numbers['bcn_not_recorded']} person "
        "records carry no severity. The crash table classifies at 24 hours, so its "
        f"{numbers['bcn_serious_crash_table']} serious injuries include the "
        f"{numbers['bcn_dead_later']} later deaths. The vehicle table has more rows than the "
        f"crash table reports vehicles ({numbers['bcn_reported']}), so a vehicle row is not a unique "
        "vehicle; this and a correction to the crash table's coordinates are described in the "
        f"{quality}.</p>"
    )


def _meeting(cat_dgt: pd.DataFrame) -> str:
    equal = int((cat_dgt.ratio_fatal_24h == 1).sum())
    _check(equal == len(cat_dgt), "sources", "fatal counts equal DGT's in every province-year")
    outward = read_table("ml_outward_path").set_index(["model", "stage"]).status
    _check(
        outward[("calculator", 4)] == "not run"
        and outward[("catalonia_common_dgt", 4)] == "passed"
        and outward[("catalonia_common_bcn", 4)] != "not run",
        "sources",
        "restricted versions of the original Catalan model meet DGT's and Barcelona's records; "
        "the calculator's model meets no other source",
    )
    period = _span_of(cat_dgt.year)
    return (
        "<h2>No record is linked across sources</h2>"
        "<p>The files share no identifier, and crashes are not matched on date or place. The "
        "Catalan file's fatal crashes equal DGT's crashes with a death within 24 hours in every "
        f"province and year of {period} "
        '(<a href="catalonia.html#dgt-agreement">Catalonia</a>). Versions of the original '
        "Catalan model restricted to variables another source records in the same way are "
        "applied to DGT's records elsewhere in Spain and to Barcelona's records, without "
        "merging either with the Catalan file; the calculator's model, whose inputs no other "
        'source records, has no such test (<a href="validation.html">External '
        "validation</a>). The rates per kilometre by driver age divide counts of drivers by age "
        "by the travel surveys' kilometres by age, in total "
        '(<a href="drivers.html">Drivers</a>).</p>'
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
    # The right-of-way flags answer one question in several columns unrecorded together,
    # so they count as one field.
    fields = len(regional) - len(priority) + 1
    _check(
        float(priority.unrecorded_share.max() - priority.unrecorded_share.min()) < 0.01,
        "sources",
        "the right-of-way flags are unrecorded together",
    )
    _check(comparable <= fields / 2, "sources", "at most half the fields are recorded alike")
    coding = read_table("gen_coding_by_region").set_index(["region", "year"]).sort_index()
    cat_codes, rest_codes = coding.loc["Catalonia"], coding.loc["Spain outside Catalonia"]
    switch = int(cat_codes[cat_codes.road_type_5_dual_carriageway.eq(0)].index.min())
    cat_unspecified = cat_codes.junction_type_not_specified / cat_codes.crashes
    rest_unspecified = rest_codes.junction_type_not_specified / rest_codes.crashes
    junction_year = int(cat_unspecified[cat_unspecified > 0.5].index.min())
    _check(
        bool(
            (
                cat_codes.loc[: switch - 1].road_type_6_single_carriageway
                < 0.01 * cat_codes.loc[: switch - 1].road_type_5_dual_carriageway
            ).all()
        )
        and float(rest_unspecified.loc[junction_year:].max()) < 0.05,
        "sources",
        "the Catalan records code conventional roads and missing junction types their own way",
    )
    died_30 = artefacts[artefacts.target.str.contains("30 days")].iloc[0]
    died_24 = artefacts[artefacts.target.str.contains("24 hours")].iloc[0]
    _check(
        bool(died_30.artefacts_dominate) and not bool(died_24.artefacts_dominate),
        "sources",
        "unrecorded fields dominate for 30-day deaths and not among serious crashes",
    )
    _check(
        float(died_24.artefact_share_of_lift)
        < dgt_audit.MAX_ARTEFACT_SHARE
        < float(died_30.artefact_share_of_lift),
        "sources",
        "the artefact shares fall either side of the limit",
    )
    # Fields whose unrecorded share differs between fatal and other crashes by the recording
    # check's factor, in DGT's records for Catalonia or for the rest of Spain.
    outcome = read_table("dgt_audit_outcome_recording")
    limit = recording.RATIO_LIMIT
    dependent = outcome[
        (outcome.unrecorded_share_not_fatal >= recording.MIN_RATE)
        & (
            (outcome.ratio_fatal_to_not_fatal >= limit)
            | (outcome.ratio_fatal_to_not_fatal <= 1 / limit)
        )
    ]
    lower_when_fatal = dependent.groupby("field").ratio_fatal_to_not_fatal.max() <= 1 / limit
    _check(
        not dependent.empty and lower_when_fatal.sum() > len(lower_when_fatal) / 2,
        "sources",
        "in most fields recorded differently by outcome, fatal crashes are unrecorded less often",
    )
    severity = f'<a href="severity.html">{esc(TITLES["severity"])}</a>'
    return (
        "<h2>Uneven recording in the national crash records</h2>"
        "<p>DGT's national crash file matches every published total it was checked against "
        '(<a href="data.html#checks">checks on the data</a>), which makes it the source for '
        "national counts and trends. Comparing provinces, or training a model on the file, also "
        "needs each field to mean the same everywhere. An audit with criteria fixed in advance "
        "found three problems: provinces leave fields unrecorded at very different rates, "
        "the records for the Catalan provinces code some fields their own way, and which fields "
        "are unrecorded carries information about the outcome. A field counts as unrecorded "
        "when it is “not specified”, “unknown” or left blank.</p>"
        f"<p>Of the {_fmt_int(fields)} fields examined (the {_fmt_int(len(priority))} that "
        f"record who had right of way counted as one), {_words(comparable)} have an unrecorded "
        f"share that varies by no more than {dgt_audit.MAX_REGIONAL_SPREAD * 100:.0f} "
        "percentage points across the provinces with at least "
        f"{_fmt_int(dgt_audit.MIN_PROVINCE_CRASHES)} crashes. The right-of-way fields are "
        f"unrecorded in {_fmt_pct(priority.province_min.min(), 0)} of crashes in one province "
        f"and {_fmt_pct(priority.province_max.max(), 0)} in another. Fields that are always "
        "filled in can still be coded differently: the records for the four Catalan provinces "
        f"code conventional roads as dual carriageways until {switch - 1}, and from "
        f"{junction_year} mark a missing junction type as “not specified” instead of leaving it "
        'blank, while the rest of Spain does neither (<a href="data.html#coding-breaks">coding '
        "breaks</a>).</p>"
        f"<p>Recording also depends on the outcome. In {_words(dependent.field.nunique())} "
        f"fields the unrecorded share differs by a factor of {limit:.1f} or more between fatal "
        "and other crashes, in Catalonia or in the rest of Spain, and in most of them it is "
        "lower when someone died. A model that sees only which fields were unrecorded ranks "
        "crashes with a death within 30 days with "
        f"a ROC-AUC of {float(died_30.roc_auc_unrecorded_flags_only):.2f} "
        '(<a href="data.html#models">ranking measure</a>), against '
        f"{float(died_30.roc_auc_recorded_values):.2f} for a model that sees the recorded "
        "values: which fields are unrecorded gives "
        f"{_fmt_pct(float(died_30.artefact_share_of_lift), 0)} of the recorded model's gain over "
        f"chance, above the {_fmt_pct(dgt_audit.MAX_ARTEFACT_SHARE, 0)} limit set in advance. "
        "Among crashes with a death or serious injury, the population of the external test, "
        f"the share is {_fmt_pct(float(died_24.artefact_share_of_lift), 0)}, below it. A model "
        "trained on all of Spain would partly be ranking crashes by how completely each "
        "province records them.</p>"
        "<p>The national records are therefore used to describe Spain, including the "
        f"associations reported under {severity}, and, on the variables validated against the "
        "Catalan file, as an external test of a version of the original Catalan model. They "
        "train reference and diagnostic models for those tests, but no published predictive "
        "model. The full audit is published as the "
        f'<a href="{DOCS_URL}/DGT_MICRODATA_AUDIT.md">DGT microdata audit</a>.</p>'
    )


def _scope() -> str:
    # The second item of each pair may carry a link, so it is written as HTML.
    items = "".join(f"<li>{esc(what)}. {why}</li>" for what, why in SCOPE)
    return (
        f'<h2 id="scope">What the files do not record</h2><ul>{items}</ul>'
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
        "every reconciliation check passes",
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
    dead_24h = int(semantics["persons recorded as died within 24 h"])
    dead_later = int(semantics["persons recorded as died after 24 h"])
    serious_crash_table = int(semantics["serious injuries in the crash table"])
    _check(
        dead_24h + dead_later == int(people["fatal"])
        and dead_24h == int(semantics["deaths in the crash table (Numero_morts)"])
        and serious_crash_table == int(people["serious"]) + dead_later,
        "sources",
        "the crash table counts deaths within 24 hours and puts later deaths among the serious",
    )
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
        "bcn_dead_24h": _fmt_int(dead_24h),
        "bcn_dead_later": _fmt_int(dead_later),
        "bcn_serious_crash_table": _fmt_int(serious_crash_table),
        "bcn_serious": _fmt_int(people["serious"]),
        "bcn_not_recorded": _fmt_int(people["not_recorded"]),
    }
    body = summary(
        "The study uses DGT's national statistics and three sets of police crash records: "
        "DGT's national file of injury crashes, the Servei Català de Trànsit's file of crashes "
        "with a death or serious injury in Catalonia, and the Guàrdia Urbana's records for "
        "Barcelona city. Two travel surveys, of the Barcelona area and of Madrid, supply the "
        "kilometres driven by age. No record is linked across sources; they meet only in totals "
        "and in tests of the models. The national crash records describe Spain but train no "
        "published model, because provinces record their fields unevenly and which fields are "
        "left unrecorded carries information about the outcome."
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
            ("dgt_audit_regional", "unrecorded shares by field and province"),
            ("dgt_audit_artefacts", "ranking from unrecorded fields alone"),
            ("dgt_audit_outcome_recording", "unrecorded shares by outcome"),
        ],
        method=("data.html#records", "reading police crash records"),
    )
    return render_page(
        "sources",
        "Data sources and scope",
        "What each source behind the study is, what it covers and what it cannot show.",
        body,
    )
