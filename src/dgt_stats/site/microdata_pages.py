"""The crash-level microdata pages: Catalonia, Barcelona, the severity models and their transfer.

Every number is read from a committed table in ``reports/tables`` written by
``scripts/microdata.py``; qualitative sentences are guarded by checks that stop the build when the
tables no longer support them. Each major figure or table carries a closed "Source, coverage and
unit" block with its observation unit, N and main limitation.
"""

from __future__ import annotations

import re

import pandas as pd

from dgt_stats import layers
from dgt_stats.microdata.validation import decisions as decision_rules
from dgt_stats.site.components import (
    DOCS_URL,
    _fmt_int,
    _fmt_pct,
    conclusion,
    downloads,
    esc,
    figure,
    key_figures,
    limits,
    note,
    read_table,
    render_page,
    table,
)

MIN_N = 30
CAT_SOURCE = "Servei Català de Trànsit (export of crashes with a death or serious injury)"
BCN_SOURCE = "Ajuntament de Barcelona, Guàrdia Urbana (Open Data BCN)"
MODEL_NAMES = {
    "catalonia_crash_severity": "Catalonia: fatal or serious crash",
    "barcelona_person_severity": "Barcelona: serious or fatal injury of a person",
    "barcelona_crash_severity": "Barcelona: crash with a serious or fatal injury",
    "catalonia_common_dgt": "Catalonia, restricted to DGT-common variables",
    "catalonia_common_bcn": "Catalonia, restricted to Barcelona-common variables",
}
CARDS = {
    "catalonia_crash_severity": "models/catalonia_fatal_severity.md",
    "barcelona_person_severity": "models/barcelona_person_severity.md",
    "barcelona_crash_severity": "models/barcelona_crash_severity.md",
}
SHORT_NAMES = {
    "catalonia_crash_severity": "Catalonia",
    "barcelona_person_severity": "Barcelona person",
    "barcelona_crash_severity": "Barcelona crash",
}
SECTIONS = {
    "catalonia_crash_severity": (
        "Catalonia: which serious crashes were fatal",
        "Among recorded crashes with a death or serious injury, which road, crash and "
        "environmental characteristics go with a fatal outcome, beyond the crash type and zone?",
    ),
    "barcelona_person_severity": (
        "Barcelona: which people were seriously hurt",
        "Among people recorded in Barcelona crashes, which circumstances and road-user "
        "characteristics go with a serious or fatal injury, beyond road role and vehicle?",
    ),
    "barcelona_crash_severity": (
        "Barcelona: which crashes had a serious injury",
        "Which recorded crash circumstances distinguish crashes with a serious or fatal injury, "
        "beyond the accident type?",
    ),
}
# The rule's grouping column, and the descriptive-table dimension that shows the same grouping.
TABLE_DIMENSIONS = {"accident_type": "crash type"}
ESTIMATORS = {
    "baseline_prior": "Baseline (prevalence)",
    "logistic": "Logistic regression",
    "boosted_trees": "Boosted trees",
}


def about(source: str, coverage: str, unit: str, n: str, limitation: str) -> str:
    """The closed 'Source, coverage and unit' block under a figure or table."""
    items = (
        ("Source", source),
        ("Coverage", coverage),
        ("One row is", unit),
        ("N", n),
        ("Main limitation", limitation),
    )
    rows = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in items)
    return (
        f'<details class="about"><summary>Source, coverage and unit</summary>'
        f"<dl>{rows}</dl></details>"
    )


def _year_label(frame: pd.DataFrame) -> str:
    """The year (or years) a Barcelona table covers, from its own dataset label."""
    return re.search(r"\d{4}(-\d{4})?", str(frame.dataset.iloc[0])).group(0).replace("-", "–")


def ca(text: str) -> str:
    return f'<span lang="ca">{esc(text)}</span>'


def _check(condition: bool, page: str, claim: str) -> None:
    if not condition:
        raise ValueError(f"{page} page: '{claim}' no longer reads as described")


def _share_ci(row) -> str:
    return (
        f"{_fmt_pct(row.share)} ({_fmt_pct(row.ci_low)}–{_fmt_pct(row.ci_high)}, "
        f"n={_fmt_int(row.n)})"
    )


def _dimension(frame: pd.DataFrame, dimension: str) -> pd.DataFrame:
    return frame[(frame.dimension == dimension) & (frame.n >= MIN_N)].sort_values(
        "share", ascending=False
    )


def _share_table(frame: pd.DataFrame, dimensions: list[str], first: str) -> pd.DataFrame:
    rows = frame[frame.dimension.isin(dimensions) & (frame.n >= MIN_N)]
    out = pd.DataFrame(
        {
            first: rows.dimension.str.capitalize() + ": " + rows.label,
            "Crashes": rows.n,
            "Fatal": rows.events,
            "Fatal share": rows.share,
            "95% interval": [
                f"{_fmt_pct(lo)}–{_fmt_pct(hi)}" for lo, hi in zip(rows.ci_low, rows.ci_high)
            ],
        }
    )
    return out


# ----------------------------------------------------------------------------- Catalonia
def page_catalonia(captions: dict[str, str]) -> str:
    shares = read_table("cat_fatal_share")
    frequency = read_table("cat_frequency")
    dgt = read_table("cat_vs_dgt_province_year")
    per_resident = read_table("cat_per_resident_province_year")
    artefacts = read_table("ml_recording_artefacts")
    checks = read_table("mq_cat_checks").set_index("check").value

    overall = shares[(shares.dimension == "unit type involved") & (shares.level == "all")].iloc[0]
    years = shares[shares.dimension == "year"].level.astype(int)
    first, last = int(years.min()), int(years.max())
    period = f"{first}–{last}"
    roads = _dimension(shares, "road type")
    top_road, low_road = roads.iloc[0], roads.iloc[-1]
    limits_ = shares[shares.dimension == "speed limit"].set_index("level")
    generic = limits_.loc["generic limit for the road (value not recorded)"]
    units = _dimension(shares, "unit type involved").set_index("level")
    heavy = units.loc["heavy vehicle"]
    motorcycle = units.loc["motorcycle"]
    _check(
        top_road.share > 2 * low_road.share,
        "catalonia",
        "the fatal share on the most deadly road type is more than twice the least",
    )
    _check(
        heavy.ci_low > overall.share,
        "catalonia",
        "crashes involving a heavy vehicle are more often fatal than average",
    )
    _check(
        motorcycle.ci_high < overall.share,
        "catalonia",
        "crashes involving a motorcycle are less often fatal than average",
    )
    equal_fatal_24h = int((dgt.ratio_fatal_24h == 1).sum())
    within_one = int(
        ((dgt.cat_crashes_fatal_or_serious - dgt.dgt_crashes_fatal_or_serious_24h).abs() <= 1).sum()
    )
    _check(
        equal_fatal_24h == len(dgt),
        "catalonia",
        "fatal counts equal DGT's 24-hour counts in every province-year",
    )
    outcome_dependent = artefacts[artefacts.verdict == "outcome-dependent recording"]

    body = layer_line("catalonia") + key_figures(
        [
            (
                "Crashes in the file",
                _fmt_int(overall.n),
                f"{period}, each with a death or serious injury",
            ),
            ("Fatal among them", _fmt_pct(overall.share), f"{_fmt_int(overall.events)} crashes"),
            ("Most often fatal", _fmt_pct(top_road.share), f"on {top_road.label}s"),
            (
                "Matches DGT, 24 h",
                f"{equal_fatal_24h} of {len(dgt)}",
                "province-years with equal fatal counts",
            ),
        ]
    )
    body += (
        '<p class="answer">Catalonia publishes one record for every crash with a death or a '
        f"serious injury: {_fmt_int(overall.n)} crashes from {first} to {last}. Because the file "
        "holds only serious and fatal crashes, it answers two questions: how many such crashes "
        "were recorded (frequency), and how often a serious crash was fatal (severity among "
        f"them). Overall {_fmt_pct(overall.share)} were fatal. That share ranges from "
        f"{_fmt_pct(low_road.share)} on {low_road.label}s to {_fmt_pct(top_road.share)} on "
        f"{top_road.label}s, is {_fmt_pct(heavy.share)} when a heavy vehicle was involved and "
        f"{_fmt_pct(motorcycle.share)} when a motorcycle was. It cannot say how likely a crash "
        "is to happen, or to become serious: the file has no minor crashes and no exposure.</p>"
    )
    body += note(
        "<strong>Severity among recorded serious crashes, not risk.</strong> A higher fatal share "
        "on a kind of road means that, once a crash with a death or serious injury happened "
        "there, it was more often fatal. It says nothing about how often crashes happen on that "
        "road, and the differences are associations, not effects."
    )
    body += figure("cat1_fatal_by_road", "Fatal share by road type with intervals", captions)
    body += about(
        CAT_SOURCE,
        f"{period}, Catalonia (four demarcations)",
        "one crash with at least one death or serious injury (surrogate id; the file has none)",
        _fmt_int(overall.n),
        "only serious and fatal crashes are recorded, so no rate of crashes and no "
        "comparison with minor crashes",
    )
    body += figure("cat3_fatal_by_unit", "Fatal share by type of unit involved", captions)
    body += figure("cat4_fatal_by_crash_type", "Fatal share by crash type", captions)
    body += table(
        _share_table(
            shares,
            [
                "road type",
                "unit type involved",
                "crash subtype",
                "lighting",
                "zone",
                "intersection",
            ],
            "Group",
        ),
        f"Fatal share among crashes with a death or serious injury, Catalonia {period} "
        "(groups with at least 30 crashes)",
        {"Crashes": "int", "Fatal": "int", "Fatal share": "pct"},
    )

    body += "<h2>The speed-limit field is not a speed</h2>"
    posted = shares[
        (shares.dimension == "speed limit")
        & shares.level.str.startswith("posted ")
        & (shares.n >= MIN_N)
    ]
    lowest, highest = posted.iloc[0], posted.sort_values("level").iloc[-1]
    body += (
        f"<p>{ca('C_VELOCITAT_VIA')} is the limit that applied to the road, not how fast "
        "anyone drove. It is a usable number only where the limit was signposted: under the "
        f"generic limit for the road ({ca('Genérica via')}, {_fmt_int(generic.n)} crashes) the "
        "field holds 100, 999 or NA whatever the road, 100 even on urban streets, so it is a "
        "code. Where a limit was posted, the fatal share rises with it, from "
        f"{_fmt_pct(lowest.share)} at {lowest.level.replace('posted ', '')} to "
        f"{_fmt_pct(highest.share)} at {highest.level.replace('posted ', '')}; posted limits "
        "differ by kind of road, so this mixes road and limit.</p>"
    )
    body += figure("cat2_fatal_by_speed_limit", "Fatal share by posted speed limit", captions)

    body += "<h2>How many serious crashes were recorded</h2>"
    by_year = frequency.groupby("year")[["crashes", "fatal_crashes", "deaths"]].sum()
    body += figure("cat6_crashes_by_year", "Serious and fatal crashes by year", captions)
    body += table(
        by_year.reset_index().rename(
            columns={
                "year": "Year",
                "crashes": "Crashes",
                "fatal_crashes": "Fatal crashes",
                "deaths": "Deaths",
            }
        ),
        f"Recorded crashes with a death or serious injury by year, Catalonia {period}",
        {"Year": "year", "Crashes": "int", "Fatal crashes": "int", "Deaths": "int"},
    )

    body += "<h2>How the file lines up with the national data</h2>"
    overlap = f"{int(dgt.year.min())}–{int(dgt.year.max())}"
    ratio30 = dgt.ratio_fatal_30d
    body += (
        "<p>No Catalan crash is matched to any other record: the file has no identifier that "
        "another source shares. The four demarcations are the four provinces, so counts can be "
        f"compared by province and year. Over {overlap} the number of fatal crashes equals the "
        "DGT microdata's crashes with a death within 24 hours in every one of the "
        f"{len(dgt)} province-years, and the number of crashes equals DGT's crashes with a "
        f"death or serious injury within 24 hours to within one crash in {within_one} of them. "
        "Against DGT's 30-day deaths the fatal count is "
        f"{_fmt_pct(ratio30.min(), 0)}–{_fmt_pct(ratio30.max(), 0)} as large. The file's "
        "severity therefore behaves as the 24-hour definition, and it is compared with "
        "national figures only on that basis.</p>"
    )
    latest = per_resident[per_resident.year == per_resident.year.max()]
    body += table(
        latest[
            [
                "demarcation",
                "crashes_fatal_or_serious",
                "population",
                "crashes_fatal_or_serious_per_100k_residents",
            ]
        ].rename(
            columns={
                "demarcation": "Demarcation",
                "crashes_fatal_or_serious": "Crashes",
                "population": "Residents (1 January)",
                "crashes_fatal_or_serious_per_100k_residents": "Per 100,000 residents",
            }
        ),
        f"Crashes with a death or serious injury per resident, {int(latest.year.max())} "
        "(INE residents of the province; a rate per resident, not a risk per trip or km)",
        {"Crashes": "int", "Residents (1 January)": "int", "Per 100,000 residents": "dec"},
    )
    body += about(
        f"{CAT_SOURCE}; DGT crash microdata; INE table 56947",
        f"{overlap} for the DGT comparison, {period} per resident",
        "one province-year (aggregated on both sides; no record is linked)",
        f"{len(dgt)} province-years",
        "the file does not state its death window; the 24-hour match is measured, not declared",
    )

    body += "<h2>What the file records unevenly</h2>"
    names = ", ".join(ca(c) for c in sorted(set(outcome_dependent.column)))
    worst = outcome_dependent.sort_values("ratio_fatal_to_serious").iloc[0]
    body += (
        '<p>Some fields are left "not specified" at very different rates for serious and for '
        f"fatal crashes. For {ca(worst.column)} the level "
        f'"{esc(worst.level)}" covers {_fmt_pct(worst.rate_serious)} of serious crashes and '
        f"{_fmt_pct(worst.rate_fatal)} of fatal ones. The file does not say why; whatever the "
        "reason, the placeholder itself carries information about the outcome, so the severity "
        f"model leaves these fields out of its main version: {names}. Recording also differs by "
        "place and year (see the "
        f'<a href="{DOCS_URL}/DATA_QUALITY_MICRODATA.md">data-quality report</a>).</p>'
    )
    body += downloads(
        [
            ("cat_fatal_share", "fatal share by group"),
            ("cat_frequency", "crashes by year, demarcation and zone"),
            ("cat_vs_dgt_province_year", "comparison with the DGT microdata"),
            ("cat_per_resident_province_year", "crashes per resident"),
            ("ml_recording_artefacts", "recording check"),
        ]
    )
    body += "<h2>Conclusion</h2>" + conclusion(
        f"Among Catalan crashes with a death or serious injury, {_fmt_pct(overall.share)} were "
        f"fatal, and the share varies more than twofold with the kind of road and with the "
        "vehicles involved. The file's fatal counts are the DGT's 24-hour counts, province by "
        "province. It measures severity among serious crashes; it does not measure risk."
    )
    body += limits(
        "Only crashes with a death or serious injury; no person records, no vehicle speeds, no "
        "alcohol or drug tests; no exposure, so no risk; the 100 km/h code; recording "
        f"differences between places and years. Checks: {int(checks.get('rows identical in every source column', 0))} "
        "duplicated rows, every severity label consistent with the casualty counts (see the "
        "data-quality report)."
    )
    return render_page(
        "catalonia",
        "Catalonia: crashes with a death or serious injury",
        f"Every crash with a death or serious injury in Catalonia, {first} to "
        f"{last}: how often such crashes were fatal, by road, vehicles and "
        "conditions, and how the file reconciles with the national data.",
        body,
    )


# ----------------------------------------------------------------------------- Barcelona
def page_barcelona(captions: dict[str, str]) -> str:
    people = read_table("bcn_person_severity_share")
    crashes = read_table("bcn_crash_severity_share")
    frequency = read_table("bcn_frequency")
    structure = read_table("mq_bcn_structure")
    profiles = read_table("bcn_cause_profiles")
    vehicles = read_table("bcn_vehicle_audit_counts").set_index("measure").value
    coordinates = read_table("mq_bcn_coordinates").set_index("table")

    year = _year_label(people)
    n_crashes = int(structure.set_index("table").loc["bcn_accidents", "rows"])
    n_people = int(structure.set_index("table").loc["bcn_people", "rows"])
    road_users = _dimension(people, "road user").set_index("level")
    labelled = int(people[people.dimension == "road user"].n.sum())
    severe_people = int(people[people.dimension == "road user"].events.sum())
    pedestrian, car_driver = road_users.loc["pedestrian"], road_users.loc["car driver"]
    motorcycle = road_users.loc["motorcycle driver"]
    _check(
        pedestrian.ci_low > car_driver.ci_high,
        "barcelona",
        "pedestrians are more often seriously hurt than car drivers",
    )
    _check(
        motorcycle.ci_low > car_driver.ci_high,
        "barcelona",
        "motorcyclists are more often seriously hurt than car drivers",
    )
    crash_all = crashes[(crashes.dimension == "cause recorded") & (crashes.level == "all")].iloc[0]
    alcohol = profiles[(profiles.cause == "alcohol")].set_index(["group", "measure"])
    alc_night = alcohol.loc[("alcohol recorded", "night_shift")]
    other_night = alcohol.loc[("alcohol not recorded", "night_shift")]
    _check(
        alc_night.ci_low > other_night.ci_high,
        "barcelona",
        "alcohol-recorded crashes are more often at night",
    )

    body = layer_line("barcelona") + key_figures(
        [
            ("Crashes", _fmt_int(n_crashes), f"attended by the Guàrdia Urbana in {year}"),
            ("Person records", _fmt_int(n_people), "drivers, passengers and pedestrians"),
            (
                "Serious or fatal",
                _fmt_int(severe_people),
                f"of {_fmt_int(labelled)} people with a recorded outcome",
            ),
            ("Pedestrians", _fmt_pct(pedestrian.share), "seriously or fatally injured"),
        ]
    )
    body += (
        f'<p class="answer">Barcelona publishes six tables for {year} that share one crash '
        f"number: the crash itself, its type, the people involved, vehicle records and two "
        f"lists of recorded causes. Together they cover {_fmt_int(n_crashes)} crashes and "
        f"{_fmt_int(n_people)} person records, injured or not. Among people with a recorded "
        f"outcome, {_fmt_pct(severe_people / labelled)} were seriously or fatally injured: "
        f"{_fmt_pct(pedestrian.share)} of pedestrians and {_fmt_pct(motorcycle.share)} of "
        f"motorcycle drivers, against {_fmt_pct(car_driver.share)} of car drivers. These are "
        "shares among people involved in recorded crashes, not risks per trip.</p>"
    )
    joins = structure.assign(
        how=structure.table.map(
            {
                "bcn_accidents": "is the crash table",
                "bcn_accident_types": "one-to-one, validated",
                "bcn_mediate_causes": "aggregated to one row per crash first",
                "bcn_driver_causes": "aggregated to one row per crash first (no person key)",
                "bcn_people": "person level; crash context joined many-to-one",
                "bcn_vehicles": "type presence only (row meaning not established)",
            }
        )
    )
    body += table(
        joins[["table", "rows", "distinct_crash_ids", "max_rows_per_crash", "how"]].rename(
            columns={
                "table": "Table",
                "rows": "Rows",
                "distinct_crash_ids": "Crash ids",
                "max_rows_per_crash": "Most rows for one crash",
                "how": "Joined how",
            }
        ),
        "The six Barcelona tables and how each reaches the crash (key: Numero_expedient)",
        {"Rows": "int", "Crash ids": "int", "Most rows for one crash": "int"},
    )
    body += about(
        BCN_SOURCE,
        f"{year}, Barcelona city",
        "one crash, one person record, one recorded cause or one vehicle record, by table",
        f"{_fmt_int(n_crashes)} crashes",
        "the vehicle table has more rows than vehicles reported and no vehicle id; "
        "cause tables have no person key",
    )

    body += "<h2>Who is seriously hurt</h2>"
    body += figure("bcn1_severity_by_road_user", "Serious or fatal share by road user", captions)
    body += figure("bcn2_severity_by_age", "Serious or fatal share by age band", captions)
    rows = people[people.dimension.isin(["road user", "age band", "sex"]) & (people.n >= MIN_N)]
    body += table(
        pd.DataFrame(
            {
                "Group": rows.dimension.str.capitalize() + ": " + rows.label,
                "People": rows.n,
                "Serious or fatal": rows.events,
                "Share": rows.share,
                "95% interval": [
                    f"{_fmt_pct(lo)}–{_fmt_pct(hi)}" for lo, hi in zip(rows.ci_low, rows.ci_high)
                ],
            }
        ),
        f"Serious or fatal injury among person records with a recorded outcome, Barcelona {year} "
        "(groups with at least 30 records)",
        {"People": "int", "Serious or fatal": "int", "Share": "pct"},
    )
    body += about(
        BCN_SOURCE,
        year,
        "one person record (no source person id)",
        f"{_fmt_int(labelled)} records with a recorded victimisation",
        "the vehicle type on a pedestrian's record does not say which vehicle it is; "
        "a blank victimisation is left out, never counted as uninjured",
    )

    body += "<h2>Which crashes</h2>"
    body += figure(
        "bcn4_crash_severity_by_type", "Serious or fatal crashes by crash type", captions
    )
    body += figure("bcn3_crashes_by_hour", "Recorded crashes by hour of day", captions)
    hours = frequency[frequency.dimension == "hour"].assign(h=lambda d: d.level.astype(int))
    peak = hours.sort_values("crashes").iloc[-1]
    body += (
        f"<p>Crashes are most frequent at {int(peak.h)}:00 ({_fmt_int(peak.crashes)} crashes in "
        f"the year); {_fmt_pct(crash_all.share)} of all crashes had a serious or fatal injury. "
        "Counts by hour are frequency: they follow how much traffic there is, which the data do "
        "not measure.</p>"
    )

    body += "<h2>Recorded causes</h2>"
    causes = crashes[
        (crashes.dimension == "cause recorded") & (crashes.level != "all") & (crashes.n >= MIN_N)
    ].sort_values("n", ascending=False)
    body += (
        "<p>Each cause below was <em>recorded</em> by the police for the crash. A recorded cause "
        "is not a finding that it caused the crash, and the driver-cause list has no key to the "
        "person or vehicle concerned, so it is never attributed to anyone. Alcohol was recorded "
        f"as a mediate factor in {_fmt_int(alc_night.n)} crashes; {_fmt_pct(alc_night.share)} "
        f"of them were at night, against {_fmt_pct(other_night.share)} of the rest.</p>"
    )
    body += table(
        pd.DataFrame(
            {
                "Cause recorded in the crash": causes.label,
                "Crashes": causes.n,
                "Serious or fatal": causes.events,
                "Share": causes.share,
            }
        ),
        f"Crashes by recorded cause and share with a serious or fatal injury, Barcelona {year} "
        "(causes recorded in at least 30 crashes; a crash can have several)",
        {"Crashes": "int", "Serious or fatal": "int", "Share": "pct"},
    )

    body += "<h2>Two things the files needed</h2>"
    offset_e = float(coordinates.loc["bcn_people", "offset_east_median_m"])
    offset_n = float(coordinates.loc["bcn_people", "offset_north_median_m"])
    body += (
        "<p>The crash file lists its UTM columns as Y then X, and its X column holds northings: "
        "its two labels are exchanged. A UTM easting in Spain is always below 1,000,000 m and a "
        "northing above 3,000,000 m, so each value is placed by its size, in new columns beside "
        "the untouched source columns. Afterwards every file gives each crash the same position, "
        "and the UTM position sits a constant "
        f"{offset_e:.0f} m east and {offset_n:.0f} m north of the WGS84 position, the datum shift "
        "between ED50 and WGS84. Maps use WGS84.</p>"
        f"<p>The vehicle table has {_fmt_int(vehicles['vehicle records'])} rows for "
        f"{_fmt_int(vehicles['vehicles reported by the crash table (sum)'])} vehicles the crash "
        "table reports, with no vehicle identifier. Counting vehicles from it is therefore "
        "quarantined; only whether a type of vehicle appears in a crash is used (the types "
        "agree with the person records in every crash).</p>"
    )
    body += downloads(
        [
            ("bcn_person_severity_share", "severity by person group"),
            ("bcn_crash_severity_share", "severity by crash group and recorded cause"),
            ("bcn_frequency", "crashes by month, hour, weekday and district"),
            ("bcn_cause_profiles", "alcohol- and speed-recorded crashes"),
            ("mq_bcn_structure", "table structure"),
            ("bcn_vehicle_audit_counts", "vehicle-table audit"),
        ]
    )
    body += "<h2>Conclusion</h2>" + conclusion(
        "Barcelona's tables are relational: one crash number links the crash, its people and "
        "its recorded causes. Pedestrians and motorcyclists are much more often seriously "
        "injured than car occupants among the people involved in recorded crashes. Causes are "
        "recorded at crash level, and the vehicle table cannot be read as one row per vehicle."
    )
    body += limits(
        "One year of one city; frequency and severity only (no exposure); person severity "
        "excludes records with no recorded outcome and one natural death; no link to "
        "Catalonia's file or to DGT records exists or is attempted."
    )
    return render_page(
        "barcelona",
        f"Barcelona {year}: crashes, people and recorded causes",
        f"Barcelona's crash, person and cause tables for {year}, linked by their "
        "shared crash number: who is seriously hurt, in which crashes, and what "
        "the police recorded.",
        body,
    )


def layer_line(key: str) -> str:
    """The line under a page's lead that names its layer in the source hierarchy."""
    layer = layers.BY_KEY[key]
    return (
        f'<p class="level">Layer: <a href="sources.html">{esc(layer.title)}</a>. '
        f"Unit: {esc(layer.unit)}.</p>"
    )


# ----------------------------------------------------------------------------- models
def page_severity_models(captions: dict[str, str]) -> str:
    selected = read_table("ml_selected")
    variants = read_table("ml_variants")
    rare = read_table("ml_rare_causes")
    subgroups = read_table("ml_subgroup_validation")
    geography = read_table("ml_geography")
    rules = read_table("ml_rule_comparison").set_index("model")
    decisions = read_table("ml_model_decisions")
    crashes = read_table("bcn_crash_severity_share")
    primary = selected[selected.primary].set_index("model")
    retro = selected[~selected.primary].set_index("model")
    source_models = [m for m in MODEL_NAMES if m in rules.index]
    choice = decisions[decisions.variant.eq("context") | ~decisions.model.isin(source_models)]
    choice = choice.drop_duplicates("model").set_index("model")
    kept = [m for m in source_models if choice.loc[m, "decision"] in decision_rules.FEATURED]
    replaced = [m for m in source_models if choice.loc[m, "decision"] == decision_rules.REPLACE]
    for name in source_models:
        _check(primary.loc[name].roc_auc_low > 0.5, "severity models", f"{name} beats chance")
        _check(
            bool(rules.loc[name].model_adds_signal_over_table) == (name not in replaced),
            "severity models",
            f"{name}: the decision follows the table comparison",
        )

    def rule_sentence(model: str) -> str:
        r = rules.loc[model]
        verdict = (
            "The model adds signal over the table."
            if r.model_adds_signal_over_table
            else "The model adds no measurable signal over the table."
        )
        return (
            f"Against a table of outcome shares by {esc(r.rule.replace('_', ' '))} "
            f"({int(r.rule_groups_in_training)} groups, built on the training rows), on the same "
            f"test rows: ROC-AUC {r.model_roc_auc:.2f} for the model, {r.rule_roc_auc:.2f} for the "
            f"table, a gain of {r.roc_auc_gain:+.2f} ({r.roc_auc_gain_low:+.2f} to "
            f"{r.roc_auc_gain_high:+.2f}). {verdict}"
        )

    def metrics_table(model: str, row) -> str:
        test = variants[
            (variants.model == model)
            & (variants.evaluated_on == "test")
            & (variants.geography == row.geography)
        ]
        frame = pd.DataFrame(
            {
                "Variant": test.feature_set + ", " + test.estimator.map(ESTIMATORS),
                "ROC-AUC": test.roc_auc,
                "PR-AUC": test.pr_auc,
                "Brier": test.brier,
                "Balanced accuracy": test.balanced_accuracy,
                "Recall": test.recall,
                "Precision": test.precision,
            }
        )
        return table(
            frame,
            f"{MODEL_NAMES[model]}: test rows (n={_fmt_int(row.n)}, "
            f"{_fmt_int(row.positives)} positive, prevalence {_fmt_pct(row.prevalence)})",
            {
                "ROC-AUC": "dec2",
                "PR-AUC": "dec2",
                "Brier": "dec4",
                "Balanced accuracy": "dec2",
                "Recall": "pct",
                "Precision": "pct",
            },
        )

    def calibration_text(row) -> str:
        reading = (
            "its probabilities can be read as estimates for groups of similar cases."
            if row.probabilities_shown_as_estimates
            else "the probabilities are not reliable risk estimates, so the model is used only "
            "to rank profiles."
        )
        return (
            f"Calibration slope {row.calibration_slope:.2f} and mean prediction "
            f"{_fmt_pct(row.mean_predicted)} against {_fmt_pct(row.prevalence)} observed: "
            + reading
        )

    figures = [
        (
            SHORT_NAMES[m],
            f"{rules.loc[m].model_roc_auc:.2f} / {rules.loc[m].rule_roc_auc:.2f}",
            "ROC-AUC, model / table",
        )
        for m in source_models
    ]
    figures.append(("Kept as models", f"{len(kept)} of {len(source_models)}", "the rest: a table"))
    body = layer_line("validation") + key_figures(figures)
    body += (
        '<p class="answer">Every model here is asked one question before anything else: does '
        "it rank recorded crashes or people better than a plain table of outcome shares? "
        + (
            "The "
            + " and the ".join(SHORT_NAMES[m] + " model" for m in kept)
            + (" do" if len(kept) > 1 else " does")
            + ", on later records they never saw. "
            if kept
            else ""
        )
        + (
            "The "
            + " and the ".join(SHORT_NAMES[m] + " model" for m in replaced)
            + (" do" if len(replaced) > 1 else " does")
            + " not: "
            + ("their tables are" if len(replaced) > 1 else "its table is")
            + " shown instead. "
            if replaced
            else ""
        )
        + "None of them is causal, none predicts whether a crash happens, and none measures risk "
        "per trip or kilometre: the data have no exposure.</p>"
    )
    body += "<h2>Which models earn their place</h2>"
    shown_decisions = decisions.copy()
    body += table(
        pd.DataFrame(
            {
                "Model": [MODEL_NAMES.get(m, m.replace("_", " ")) for m in shown_decisions.model],
                "Variant": shown_decisions.variant.str.replace("_", " "),
                "Unit": shown_decisions.unit,
                "Target": shown_decisions.target,
                "Baseline": shown_decisions.baseline,
                "ML": shown_decisions.ml,
                "Usefulness": shown_decisions.usefulness,
                "Highest validated level": shown_decisions.highest_validated_level_name,
                "Decision": shown_decisions.decision,
            }
        ),
        "Model decisions (rules declared before the results were read)",
    )
    body += (
        f'<p class="level">Every row in full, with where each model works and fails: '
        f'<a href="{DOCS_URL}/MODEL_DECISIONS.md">MODEL_DECISIONS.md</a>.</p>'
    )
    body += figure("ml1_test_auc", "Test ROC-AUC of each model and the baseline", captions)
    body += figure("ml2_calibration", "Calibration of the selected models", captions)

    for model in kept:
        row = primary.loc[model]
        title, question = SECTIONS[model]
        body += f"<h2>{esc(title)}</h2><p><em>{esc(question)}</em></p>"
        body += (
            f"<p>{esc(row.design.capitalize())}. Selected on validation data: "
            f"{esc(ESTIMATORS[row.estimator].lower())}, ROC-AUC {row.roc_auc:.2f} "
            f"({row.roc_auc_low:.2f}–{row.roc_auc_high:.2f}) and PR-AUC {row.pr_auc:.2f} against "
            f"a prevalence of {row.prevalence:.2f}. {esc(calibration_text(row))}</p>"
        )
        body += f"<p>{rule_sentence(model)}</p>"
        if model in retro.index:
            other = retro.loc[model]
            label = (
                "adds the police's recorded causes (a retrospective classification, not a "
                "real-time prediction)"
                if model.startswith("barcelona")
                else "adds the police's influence judgements and the fields whose "
                "completeness follows the outcome (a retrospective administrative model)"
            )
            body += (
                f"<p>The second version {esc(label)}: ROC-AUC {other.roc_auc:.2f} on the "
                "same test rows. It is kept as a diagnostic of the record, never as a "
                "predictor.</p>"
            )
        geo = geography[
            (geography.model == model)
            & (geography.feature_set == row.feature_set)
            & (geography.estimator == row.estimator)
        ].set_index("geography")
        if "granular" in geo.index and "broad" in geo.index:
            g, b = geo.loc["granular"], geo.loc["broad"]
            body += (
                "<p>Finer geography: with the most granular place variable the training fit "
                f"is {g.training_fit_roc_auc:.2f} while the test score is "
                f"{g.test_roc_auc:.2f}, against {b.test_roc_auc:.2f} with the broad one.</p>"
            )
        body += metrics_table(model, row)
        body += figure(f"ml3_importance_{model}", f"Features the {model} model uses most", captions)
        body += (
            f'<p class="level">Model card: <a href="{DOCS_URL}/{CARDS[model]}">'
            f"{esc(CARDS[model])}</a>.</p>"
        )

    for model in replaced:
        title, question = SECTIONS[model]
        rule_column = rules.loc[model].rule
        body += f"<h2>{esc(title)}: a table, not a model</h2><p><em>{esc(question)}</em></p>"
        body += f"<p>{rule_sentence(model)} The table is the answer:</p>"
        dimension = TABLE_DIMENSIONS.get(rule_column, rule_column.replace("_", " "))
        shown = crashes[crashes.dimension.eq(dimension) & crashes.n.ge(MIN_N)].sort_values(
            "share", ascending=False
        )
        _check(not shown.empty, "severity models", f"the {dimension} table exists")
        body += table(
            pd.DataFrame(
                {
                    dimension.capitalize(): shown.label,
                    "Crashes": shown.n,
                    "Serious or fatal": shown.events,
                    "Share": shown.share,
                    "95% interval": [
                        f"{_fmt_pct(lo)}–{_fmt_pct(hi)}"
                        for lo, hi in zip(shown.ci_low, shown.ci_high)
                    ],
                }
            ),
            f"Barcelona {_year_label(crashes)}: share of crashes with a serious or fatal injury "
            f"by {dimension} (groups with at least {MIN_N} crashes)",
            {"Crashes": "int", "Serious or fatal": "int", "Share": "pct"},
        )
        body += (
            f'<p class="level">The model is kept in the repository as a diagnostic; model card: '
            f'<a href="{DOCS_URL}/{CARDS[model]}">{esc(CARDS[model])}</a>.</p>'
        )

    if "barcelona_person_severity" in kept:
        body += "<h2>Where the person model works, and where it does not</h2>"
        shown = subgroups[
            subgroups.dimension.isin(["all", "role", "associated vehicle", "age band", "sex"])
            & (subgroups.n >= MIN_N)
        ]
        reported = shown[shown.auc_reported]
        pedestrians = shown[(shown.dimension == "role") & (shown.level == "pedestrian")].iloc[0]
        body += (
            "<p>Every person is scored by a model that never saw their crash (grouped "
            "cross-validation over the year). Within groups the ranking is weaker than overall: "
            "a ROC-AUC is shown only where a group has at least 20 serious or fatal cases "
            f"({len(reported)} groups). Among pedestrians it is "
            f"{'not reportable' if pd.isna(pedestrians.roc_auc) else f'{pedestrians.roc_auc:.2f}'}"
            f" ({int(pedestrians.positives)} serious or fatal of {_fmt_int(pedestrians.n)}).</p>"
        )
        body += table(
            pd.DataFrame(
                {
                    "Group": shown.dimension + ": " + shown.level,
                    "People": shown.n,
                    "Serious or fatal": shown.positives,
                    "Observed": shown.observed,
                    "Mean predicted": shown.mean_predicted,
                    "ROC-AUC": shown.roc_auc,
                    "Recall at threshold": shown.recall_at_threshold,
                }
            ),
            "Barcelona person model by group (grouped out-of-fold scores; ROC-AUC only with at "
            "least 20 positive cases)",
            {
                "People": "int",
                "Serious or fatal": "int",
                "Observed": "pct",
                "Mean predicted": "pct",
                "ROC-AUC": "dec2",
                "Recall at threshold": "pct",
            },
        )

    body += "<h2>Spain: a national test, not a national model</h2>"
    transport = read_table("ml_transport_validation")
    audit = read_table("dgt_audit_checks")
    national = transport[
        transport.experiment.eq("Catalonia -> Spain outside Catalonia")
        & transport.estimator.eq(primary.loc["catalonia_common_dgt"].estimator)
        & transport.status.eq("reported")
    ].iloc[0]
    failed_checks = audit[~audit.passed & audit.check.str.match(r"\d")]
    forecast_decision = decisions[decisions.model.eq("dgt_monthly_deaths_forecast")].decision.iloc[
        0
    ]
    allowed = audit.decision.iloc[0].startswith("DGT microdata may train")
    _check(not allowed, "severity models", "the DGT audit keeps DGT records out of training")
    body += (
        "<p>No model on this page is trained on the national DGT crash records: their audit "
        f"fails {len(failed_checks)} of its checks ("
        + ", ".join(esc(c.split(" ", 1)[1]) for c in failed_checks.check)
        + '; <a href="sources.html">sources page</a>), so they describe Spain rather than train '
        "a model of it. They are used instead to test the Catalan model, restricted to the "
        "variables both sources record the same way, on DGT's crash records from outside "
        f"Catalonia, a separately published dataset: the target domain's own model scores "
        f"{national.in_domain_cv_roc_auc:.3f}, the transferred Catalan model "
        f"{national.roc_auc:.3f}, a gap of {national.transfer_gap:+.3f} on "
        f"{_fmt_int(national.test_n)} crashes ({_fmt_int(national.test_positives)} fatal), "
        f"calibration slope {national.calibration_slope:.2f}. How far that reaches is on the "
        '<a href="transport.html">generalisability page</a>. The DGT records also support an '
        '<a href="severity.html">association analysis</a>, a supporting analysis and not a '
        "predictive model. The monthly deaths series has "
        + (
            'a <a href="forecast.html">forecast</a> that does not beat repeating last year\'s '
            "count in ordinary years, so it is not featured as a model either.</p>"
            if forecast_decision not in decision_rules.FEATURED
            else 'a <a href="forecast.html">forecasting model</a>.</p>'
        )
    )

    body += "<h2>Models that were not built</h2>"
    insufficient = rare[rare.verdict.str.startswith("insufficient")]
    enough = rare[~rare.verdict.str.startswith("insufficient")]
    body += (
        "<p>Predicting whether a cause such as alcohol, drugs or speed was recorded is not a "
        f"defensible task here. {len(insufficient)} recorded causes have fewer than 100 crashes "
        "(insufficient data for a reliable model, and no synthetic oversampling is used to "
        f"pretend otherwise); the {len(enough)} with more are compared descriptively on the "
        "Barcelona page instead: a recorded cause is the police's coding after the event, and "
        "the files do not show how fully each crash was investigated or tested.</p>"
    )
    body += table(
        pd.DataFrame(
            {
                "Recorded cause": rare.label,
                "Table": rare.table,
                "Crashes": rare.crashes_recorded,
                "Prevalence": rare.prevalence,
                "Verdict": rare.verdict.str.split(";").str[0],
            }
        ).head(12),
        f"Recorded causes: positive cases and whether a model is possible (Barcelona "
        f"{_year_label(crashes)})",
        {"Crashes": "int", "Prevalence": "pct2"},
    )
    body += downloads(
        [
            ("ml_model_decisions", "model decisions"),
            ("ml_rule_comparison", "models against tables"),
            ("ml_selected", "selected models"),
            ("ml_variants", "every variant and estimator"),
            ("ml_calibration", "calibration bins"),
            ("ml_importance", "permutation importance"),
            ("ml_subgroup_validation", "person model by group"),
            ("ml_feature_catalogue", "feature catalogue and leakage status"),
            ("ml_split_isolation", "split isolation checks"),
            ("ml_rare_causes", "rare causes"),
        ]
    )
    body += "<h2>Conclusion</h2>" + conclusion(
        f"{len(kept)} of the {len(source_models)} models trained on regional records rank "
        "severity better than a table of outcome shares and hold on later records; "
        + (
            f"{len(replaced)} does not, and its table replaces it. "
            if len(replaced) == 1
            else (f"{len(replaced)} do not, and their tables replace them. " if replaced else "")
        )
        + "The rankings are associations for prioritising analysis, not causes and not risks."
    )
    body += limits(
        "Catalonia: serious and fatal crashes only. Barcelona: one year, few serious cases, "
        "intervals in the tables. No exposure anywhere, so no risk. How far the models travel "
        'is on the <a href="transport.html">next page</a>; full leakage audit in '
        f'<a href="{DOCS_URL}/ML_LEAKAGE_AUDIT.md">ML_LEAKAGE_AUDIT.md</a>.'
    )
    return render_page(
        "severity-models",
        "Severity models: which ones earn their place",
        "Models trained on individual crash and person records, each compared with a plain table "
        "of outcome shares and judged on later records it never saw. Only the ones that beat "
        "the table are kept.",
        body,
    )


# ----------------------------------------------------------------------------- transport
def page_transport(captions: dict[str, str]) -> str:
    transport = read_table("ml_transport_validation")
    path = read_table("ml_outward_path")
    provinces = read_table("ml_transport_provinces")
    validation = read_table("ml_common_feature_validation")
    outcomes = read_table("gen_outcomes")
    shares = read_table("gen_representativeness")
    components = read_table("ml_barcelona_diagnosis_components")
    verdicts = read_table("ml_barcelona_diagnosis_verdicts")
    strategies = read_table("ml_domain_strategies")
    national_checks = read_table("dgt_audit_transfer").set_index("check")
    selected = read_table("ml_selected")
    chosen_estimator = selected[selected.primary].set_index("model").estimator
    fitted = transport[transport.estimator.ne("baseline_prior")]
    # Each model is shown with the estimator chosen on its own validation data, never the better
    # of two after seeing the transfer results.
    reported = fitted[
        fitted.status.eq("reported")
        & (fitted.estimator == fitted.model.map(chosen_estimator).fillna(fitted.estimator))
    ]

    def test_row(prefix: str, model: str):
        part = reported[(reported.model == model) & reported.experiment.str.startswith(prefix)]
        return part.iloc[0]

    to_bcn = test_row("rest of Catalonia -> Barcelona municipality", "catalonia_crash_severity")
    from_bcn = test_row("Barcelona municipality -> rest of Catalonia", "catalonia_crash_severity")
    national = test_row("Catalonia -> Spain outside Catalonia", "catalonia_common_dgt")
    bcn2025 = fitted[fitted.experiment.str.match(r"Catalonia -> Barcelona \d")].iloc[0]
    bcn_year = _year_label(read_table("bcn_person_severity_share"))
    rates = read_table("gen_province_rates")
    dgt_period = f"{int(rates.year.min())}–{int(rates.year.max())}"
    cat_years = read_table("cat_frequency").year
    cat_period = f"{int(cat_years.min())}–{int(cat_years.max())}"
    shown_provinces = provinces[provinces.reported]
    full = verdicts[verdicts.features.str.startswith("full")]
    main = full.set_index("estimator").loc[to_bcn.estimator]
    # intrinsic_difference_against_urban = (other urban Catalan crashes, same training size)
    # minus Barcelona: negative means those urban crashes are harder to rank than Barcelona's.
    urban = main.intrinsic_difference_against_urban
    urban_reading = (
        f"other urban Catalan crashes at the same training size are as hard: {urban:+.2f}"
        if not main.urban_comparison_excludes_zero
        else (
            f"other urban Catalan crashes at the same training size are harder still: {urban:+.2f}"
            if urban < 0
            else f"harder than other urban Catalan crashes too: {urban:+.2f}"
        )
    )
    _check(main.intrinsic_difference > 0, "transport", "Barcelona's crashes are harder to rank")
    gap_reading = (
        ", an interval that includes zero"
        if not main.transport_cost_excludes_zero
        else ", an interval that excludes zero"
    )
    _check(
        bcn2025.status != "reported",
        "transport",
        "Barcelona has too few fatal crashes for a discrimination test",
    )
    _check(national.roc_auc_low > 0.5, "transport", "the national transfer beats chance")
    _check(
        abs(
            main.total_drop
            - (main.training_size_cost + main.intrinsic_difference + main.transport_cost)
        )
        < 1e-6,
        "transport",
        "the diagnosis components add up",
    )
    _check(
        bool(national_checks.loc["no Catalan records in the national test", "passed"]),
        "transport",
        "the national test holds no Catalan record",
    )

    body = layer_line("validation") + key_figures(
        [
            (
                "Rest of Catalonia → Barcelona",
                f"{to_bcn.roc_auc:.3f}",
                f"native {to_bcn.in_domain_cv_roc_auc:.3f}, gap {to_bcn.transfer_gap:+.3f}",
            ),
            (
                "Catalonia → rest of Spain",
                f"{national.roc_auc:.3f}",
                f"native {national.in_domain_cv_roc_auc:.3f}, gap {national.transfer_gap:+.3f}",
            ),
            (
                "Barcelona's intrinsic difference",
                f"{main.intrinsic_difference:+.2f}",
                "ROC-AUC, same features and training size",
            ),
            (
                f"Barcelona {bcn_year} fatal crashes",
                _fmt_int(bcn2025.test_positives),
                "too few for a benchmark",
            ),
        ]
    )
    body += (
        '<p class="answer">Two questions are kept apart here. <strong>Representativeness</strong>'
        ": how do Catalonia's and Barcelona's crashes differ from Spain's? That needs no model, "
        "only the DGT records, which use one definition everywhere. <strong>Transportability"
        "</strong>: does a model trained in one place keep its ranking on records from another? "
        "Every transferred score is shown beside a model trained inside the target domain. The "
        f"Catalan model ranks Barcelona's crashes at {to_bcn.roc_auc:.3f}, against a native "
        f"{to_bcn.in_domain_cv_roc_auc:.3f} for a model trained in Barcelona itself (gap "
        f"{to_bcn.transfer_gap:+.3f}). The fall "
        f"of {main.total_drop:.2f} from what it achieves inside the rest of Catalonia splits into "
        f"{main.training_size_cost:.2f} for Barcelona's smaller training set, "
        f"{main.intrinsic_difference:.2f} because Barcelona's crashes are harder to rank with "
        f"these variables ({urban_reading}), and {main.transport_cost:.2f} for the move itself"
        f"{gap_reading}. Restricted to the variables DGT records the same way, the model "
        f"ranks crashes elsewhere in Spain at {national.roc_auc:.3f}, against a native "
        f"{national.in_domain_cv_roc_auc:.3f} (gap {national.transfer_gap:+.3f}). Transfer "
        "shows that associations hold "
        "elsewhere; it does not make them causes.</p>"
    )

    body += "<h2>A. How the populations differ (no model)</h2>"
    body += table(
        pd.DataFrame(
            {
                "Comparison": outcomes.comparison,
                "Outcome": outcomes.outcome,
                "Share (first)": outcomes.share_a,
                "n (first)": outcomes.n_a,
                "Share (second)": outcomes.share_b,
                "n (second)": outcomes.n_b,
            }
        ),
        f"Outcome shares in the DGT microdata, {dgt_period} (one definition everywhere)",
        {"Share (first)": "pct", "n (first)": "int", "Share (second)": "pct", "n (second)": "int"},
    )
    divergence = (
        shares[
            shares.comparison.eq("Catalonia vs Spain outside Catalonia")
            & shares.universe.str.startswith("crashes with")
        ]
        .drop_duplicates("variable")
        .sort_values("variable_jsd", ascending=False)
    )
    body += table(
        pd.DataFrame(
            {"Variable": divergence.variable, "Divergence (JSD)": divergence.variable_jsd}
        ),
        "Catalonia against Spain outside Catalonia, crashes with a death or serious injury: how "
        "far each variable's mix differs (0 = identical)",
        {"Divergence (JSD)": "dec4"},
    )
    body += about(
        "DGT crash microdata",
        f"{dgt_period}, every province",
        "one crash with victims",
        f"{_fmt_int(int(outcomes.n_a.iloc[0] + outcomes.n_b.iloc[0]))} crashes in the first "
        "comparison",
        "a recording difference (such as an 'unknown' code used more in one region) shows up "
        "as a population difference",
    )

    body += "<h2>B. Do the models keep their ranking?</h2>"
    body += figure("tr1_catalonia_transfer", "Transfer of the full Catalan model", captions)
    shown = reported[reported.in_domain_cv_roc_auc.notna()].drop_duplicates(["model", "experiment"])
    body += table(
        pd.DataFrame(
            {
                "Test": shown.experiment,
                "Model": shown.model.map(MODEL_NAMES),
                "Train n": shown.train_n,
                "Test n": shown.test_n,
                "Test positives": shown.test_positives,
                "Native": shown.in_domain_cv_roc_auc.map("{:.3f}".format),
                "Transferred": shown.roc_auc.map("{:.3f}".format),
                "Gap": shown.transfer_gap.map("{:+.3f}".format),
                "Calibration slope": shown.calibration_slope,
            }
        ),
        "Every external test: the target domain's native score (a model trained and "
        "cross-validated inside it), the transferred score and the gap (transferred minus native; "
        "negative = ranking lost)",
        {
            "Train n": "int",
            "Test n": "int",
            "Test positives": "int",
            "Calibration slope": "dec2",
        },
    )
    body += (
        "<p>A positive gap means the transferred model, trained on many more crashes, beat a "
        "model trained on the small target domain: the training size outweighed the change of "
        f"place. Trained on Barcelona alone and tested on the rest of Catalonia the model scores "
        f"{from_bcn.roc_auc:.2f}: Barcelona is not a proxy for Catalonia.</p>"
    )

    body += "<h3>Why Barcelona is harder</h3>"
    shown_components = components[
        components.features.str.startswith("full Catalan")
        & components.estimator.eq(to_bcn.estimator)
    ]
    body += (
        "<p>The fall from the rest of Catalonia to Barcelona is split into parts that each have "
        "their own measurement: the cost of Barcelona's smaller training set, how much harder "
        "Barcelona's crashes are to rank with the same features and training size, and what is "
        "left, the true cost of moving the model. They add up to the total.</p>"
    )
    body += table(
        pd.DataFrame(
            {
                "Component": shown_components.component,
                "ROC-AUC": shown_components.value,
                "95% interval": [
                    "" if pd.isna(lo) else f"{lo:+.2f} to {hi:+.2f}"
                    for lo, hi in zip(shown_components.low, shown_components.high)
                ],
                "How it is measured": shown_components.definition,
            }
        ),
        f"Barcelona transfer diagnosis, full Catalan features, "
        f"{ESTIMATORS[to_bcn.estimator].lower()}",
        {"ROC-AUC": "dec2"},
    )
    loss = components[components.component.str.startswith("feature loss")]
    loss_bcn = loss[loss.component.str.endswith("Barcelona municipality")]
    if not loss_bcn.empty:
        lb = loss_bcn.sort_values("value").iloc[-1]
        body += (
            f"<p>Restricting the model to the variables Barcelona's own files record costs "
            f"{lb.value:.2f} of ROC-AUC inside Barcelona ({lb.low:+.2f} to {lb.high:+.2f}): "
            "part of the poor cross-source result is lost features, measured, not assumed.</p>"
        )

    body += "<h3>One model or several?</h3>"
    best_rows = []
    for domain, group in strategies.groupby("target_domain", sort=False):
        if group.estimator.eq(to_bcn.estimator).any():
            group = group[group.estimator.eq(to_bcn.estimator)]
        for r in group.itertuples():
            best_rows.append(
                {
                    "Target domain": domain,
                    "Trained on": r.strategy,
                    "ROC-AUC": r.roc_auc,
                    "Against domain-specific": ""
                    if r.strategy.startswith("domain-specific")
                    else f"{r.gain_over_specific:+.2f} ({r.gain_over_specific_low:+.2f} to "
                    f"{r.gain_over_specific_high:+.2f})",
                }
            )
    body += table(
        pd.DataFrame(best_rows),
        "Domain-specific, pooled and universal models scored on the same held-out crashes of "
        "each target domain",
        {"ROC-AUC": "dec2"},
    )

    body += "<h3>The national test</h3>"
    body += (
        "<p>DGT's crash records from outside Catalonia are a separately published dataset "
        "covering other regions, so they are an external test. Before reading the score, the "
        "test itself is checked:</p>"
    )
    body += table(
        national_checks.reset_index()[["check", "evidence"]].rename(
            columns={"check": "Check", "evidence": "Result"}
        ),
        "What the Catalonia to Spain test measures",
    )
    body += figure("tr2_dgt_transfer", "Transfer of the DGT-common Catalan model", captions)
    body += figure("tr3_province_auc", "Province by province outside Catalonia", captions)
    body += (
        f"<p>Across the {len(shown_provinces)} provinces with at least 30 fatal and 30 "
        f"non-fatal serious crashes, the ROC-AUC runs from {shown_provinces.roc_auc.min():.2f} "
        f"to {shown_provinces.roc_auc.max():.2f} (median "
        f"{shown_provinces.roc_auc.median():.2f}).</p>"
    )
    passed = validation[validation.enters_cross_source_tests]
    failed = validation[
        validation.a_priori_status.isin(["exact", "defensible"]) & ~validation.validated
    ]
    body += about(
        "DGT crash microdata (national) and the Catalan file",
        f"DGT {dgt_period}; Catalan file {cat_period}",
        "one crash with a death or serious injury within 24 hours",
        f"{_fmt_int(national.test_n)} test crashes outside Catalonia",
        f"only {len(passed)} harmonised variables; {', '.join(failed.field)} failed the mapping "
        "check on the crashes both sources hold",
    )
    body += (
        f"<p>Barcelona {bcn_year}: the compatible population (a death within 24 hours or a "
        f"hospital stay over 24 hours) is {_fmt_int(bcn2025.test_n)} crashes, of which "
        f"{_fmt_int(bcn2025.test_positives)} fatal: too few for a statistically useful "
        "fatal-against-serious benchmark, so no discrimination score is reported. The model "
        f"predicts a mean fatal share of {_fmt_pct(bcn2025.mean_predicted)} for them against "
        f"{_fmt_pct(bcn2025.test_prevalence)} observed ({_fmt_pct(bcn2025.observed_low)}–"
        f"{_fmt_pct(bcn2025.observed_high)}).</p>"
    )

    body += "<h2>C. The outward path toward Spain</h2>"
    body += (
        "<p>Five stages, in order: held-out rows of the same source; later years; another "
        "region inside the source; another independently recorded Spanish dataset; and national "
        "aggregates showing whether the training population resembles Spain. A model is called "
        "potentially nationally transferable only if it passes all five. No model jumps from "
        "Barcelona or Catalonia to Spain without the stages between.</p>"
    )
    wide = path.pivot_table(index="model", columns="stage", values="status", aggfunc="first")
    verdict = path.drop_duplicates("model").set_index("model").verdict
    order = [m for m in MODEL_NAMES if m in wide.index]
    frame = pd.DataFrame({"Model": [MODEL_NAMES[m] for m in order]})
    for stage in wide.columns:
        frame[f"Stage {stage}"] = wide.loc[order, stage].tolist()
    frame["Verdict"] = verdict.loc[order].tolist()
    body += table(frame, "The outward path, model by model (evidence in GENERALISABILITY.md)")
    transferable = verdict[verdict.eq("potentially nationally transferable")]
    body += downloads(
        [
            ("ml_transport_validation", "every transfer test"),
            ("ml_outward_path", "outward path with evidence"),
            ("ml_barcelona_diagnosis", "Barcelona diagnosis scores"),
            ("ml_barcelona_diagnosis_components", "diagnosis components"),
            ("ml_domain_strategies", "domain-specific and pooled models"),
            ("ml_transport_provinces", "province by province"),
            ("ml_domain_shift", "distribution shift"),
            ("ml_common_feature_validation", "mapping check"),
            ("dgt_audit_transfer", "national test checks"),
            ("gen_representativeness", "regions against Spain"),
            ("gen_outcomes", "outcome shares"),
            ("gen_province_rates", "severe crashes per resident by province"),
            ("gen_cross_source_register", "cross-source register"),
        ]
    )
    body += "<h2>Conclusion</h2>" + conclusion(
        "Inside Catalonia the severity associations travel between places and years. "
        "Barcelona's crashes are harder to rank than the rest of Catalonia's, "
        + (
            "as other urban crashes are, "
            if main.intrinsic_difference_against_urban <= 0
            or not main.urban_comparison_excludes_zero
            else "more than other urban crashes, "
        )
        + "and the move itself costs "
        + ("no measurable ranking. " if not main.transport_cost_excludes_zero else "some ranking. ")
        + "On the variables recorded alike, the Catalan model keeps its ranking on crashes "
        "recorded elsewhere in Spain. "
        + (
            "No model passes every stage of the outward path, so none is called nationally "
            "transferable. "
            if transferable.empty
            else f"{len(transferable)} model passes every stage of the outward path. "
        )
        + "None of this is causal."
    )
    body += limits(
        "Transfer is predictive evidence only; regions differ in how they record crashes; no "
        "person-level or full-feature national validation is possible with the data in the "
        f'repository. Full tables: <a href="{DOCS_URL}/GENERALISABILITY.md">GENERALISABILITY.md'
        "</a>."
    )
    return render_page(
        "transport",
        "How far the results reach",
        "How Catalonia and Barcelona differ from Spain, and whether the models keep their "
        "ranking on places, years and sources they never saw: two questions, measured "
        "separately.",
        body,
    )


# ----------------------------------------------------------------------------- sources
def page_sources(captions: dict[str, str]) -> str:
    comparison = read_table("source_comparison")
    checks = read_table("dgt_audit_checks")
    artefacts = read_table("dgt_audit_artefacts")
    decision = checks.decision.iloc[0]
    failed = checks[~checks.passed & checks.check.str.match(r"\d")]
    _check(not comparison.empty, "sources", "the source comparison exists")
    body = layer_line("validation")
    body += (
        '<p class="answer">The project reads four kinds of data, and each answers a different '
        "kind of question. DGT and INE are the national context: trends, denominators and "
        "province comparisons. The Catalan file is the crash microdata the severity model is "
        "trained on. The Barcelona files are the richest records, of one city and one year. "
        "Validation tests models across them. No record is ever linked across sources and no "
        "source is merged into another.</p>"
    )
    body += table(
        pd.DataFrame(
            {
                "Layer": [layer.title for layer in layers.LAYERS],
                "Unit": [layer.unit for layer in layers.LAYERS],
                "Answers": ["; ".join(layer.answers) for layer in layers.LAYERS],
                "Not for": ["; ".join(layer.not_for) for layer in layers.LAYERS],
            }
        ),
        "The four layers",
    )
    body += "<h2>How each source came to exist</h2>"
    wide = comparison.pivot_table(
        index="question", columns="source", values="answer", aggfunc="first"
    )
    order = [q for q in comparison.question.drop_duplicates() if q in wide.index]
    sources = list(comparison.source.drop_duplicates())
    frame = pd.DataFrame({"Question": order})
    for source in sources:
        frame[source] = wide.loc[order, source].tolist()
    body += table(frame, "The data-generating process of each source, against the same questions")
    body += (
        f'<p class="level">With the basis of every answer (measured, reconciled, read off the '
        f'file, or documentation): <a href="{DOCS_URL}/SOURCE_COMPARISON.md">'
        "SOURCE_COMPARISON.md</a>.</p>"
    )
    body += "<h2>Do the DGT crash records belong in a model?</h2>"
    a = artefacts.iloc[0]
    body += (
        "<p>The DGT microdata are complete and reconcile with every published total, so they "
        "are the right source for national counts and comparisons. Training a severity model on "
        "them is a different claim, tested by seven checks declared in advance. "
        + (
            f"{len(failed)} fail: " + ", ".join(esc(c) for c in failed.check) + ". "
            if not failed.empty
            else "All pass. "
        )
        + f"A model that sees only which fields were left unrecorded reaches a ROC-AUC of "
        f"{a.roc_auc_unrecorded_flags_only:.2f} for {esc(a.target)}, against "
        f"{a.roc_auc_recorded_values:.2f} for one that sees the recorded values. Decision: "
        f"{esc(decision)}.</p>"
    )
    body += table(
        checks[["check", "criterion", "evidence", "passed"]].rename(
            columns={
                "check": "Check",
                "criterion": "Criterion",
                "evidence": "Evidence",
                "passed": "Passed",
            }
        ),
        "DGT microdata audit",
    )
    body += downloads(
        [
            ("source_comparison", "source comparison"),
            ("dgt_audit_checks", "DGT audit checks"),
            ("dgt_audit_regional", "unrecorded shares by field and province"),
            ("dgt_audit_artefacts", "recording-artefact strength"),
            ("dgt_audit_outcome_recording", "unrecorded shares by outcome"),
        ]
    )
    body += "<h2>Conclusion</h2>" + conclusion(
        "Each source keeps its own unit and its own role: national context from DGT and INE, "
        "the severity model from the Catalan file, the richest detail from Barcelona. "
        "Cross-source data test models and meet at published aggregates; they never create "
        "observations."
    )
    body += limits(
        "Who records each source is taken from the publishers' documentation; everything else "
        f'on this page is measured. The rules for each source: <a href="{DOCS_URL}/'
        'DATA_CONTRACT.md">DATA_CONTRACT.md</a>.'
    )
    return render_page(
        "sources",
        "Four layers of data",
        "Which dataset answers which question, how each one came to exist, and why the "
        "national crash records describe Spain but do not train a model.",
        body,
    )


# ----------------------------------------------------------------------------- limits of the data
UNANSWERABLE: tuple[tuple[str, str], ...] = (
    (
        "How fast vehicles were going before a crash",
        "No file records a vehicle's speed; the Catalan speed field is the road's limit.",
    ),
    (
        "Driver, vehicle and person links across Catalonia",
        "The Catalan file is one row per crash with no people or vehicles; SIDAT-style linked "
        "records are not public.",
    ),
    (
        "Alcohol or drug test results by person",
        "Barcelona records alcohol and drugs as causes of a crash, not as test results, and "
        "Catalonia not at all.",
    ),
    (
        "Person-level analysis for Spain",
        "The national microdata have no person records (RNVAT-style data are not in the "
        "repository), so no person-level model can be validated nationally.",
    ),
    (
        "Who, in a Barcelona crash, did what",
        "The driver-cause and vehicle tables have no key to a person or vehicle.",
    ),
    (
        "The causal effect of alcohol, speed or any road feature",
        "Every result is observational; the models rank and associate, they do not estimate effects.",
    ),
    (
        "Risk per road user, trip or kilometre in Catalonia or Barcelona",
        "Neither source has an exposure denominator; only rates per resident at province level.",
    ),
    (
        "How a crash in one source corresponds to a record in another",
        "No shared identifier exists, and matching on date or place is not attempted.",
    ),
)


def unanswerable_section(heading_level: int = 2) -> str:
    """The short list of questions the data in the repository cannot answer."""
    items = "".join(f"<li><strong>{esc(q)}.</strong> {esc(why)}</li>" for q, why in UNANSWERABLE)
    return (
        f'<h{heading_level} id="cannot-answer">What the current data still cannot answer'
        f"</h{heading_level}><ul>{items}</ul>"
    )


# ----------------------------------------------------------------------------- overview sections
def overview_sections() -> str:
    """Questions 2-4 of the overview: what the crash records show (descriptive), which models
    earn their place (predictive) and how far they reach (transportability), kept apart."""
    shares = read_table("cat_fatal_share")
    people = read_table("bcn_person_severity_share")
    decisions = read_table("ml_model_decisions")
    transport = read_table("ml_transport_validation")
    path = read_table("ml_outward_path")
    verdicts = read_table("ml_barcelona_diagnosis_verdicts")
    selected = read_table("ml_selected")
    chosen = selected[selected.primary].set_index("model").estimator
    cat_years = read_table("cat_frequency").year
    period = f"{int(cat_years.min())}–{int(cat_years.max())}"
    bcn_year = _year_label(people)

    def share(frame, dimension, level):
        return frame[(frame.dimension == dimension) & (frame.level == level)].iloc[0]

    overall = share(shares, "unit type involved", "all")
    interurban = share(shares, "zone", "Carretera")
    urban = share(shares, "zone", "Zona urbana")
    heavy = share(shares, "unit type involved", "heavy vehicle")
    pedestrian = share(people, "road user", "pedestrian")
    motorcycle = share(people, "road user", "motorcycle driver")
    car = share(people, "road user", "car driver")
    _check(interurban.ci_low > urban.ci_high, "overview", "interurban crashes more often fatal")
    _check(pedestrian.share > motorcycle.share > car.share, "overview", "road-user ordering")

    def external(prefix: str, model: str):
        part = transport[
            transport.experiment.str.startswith(prefix)
            & transport.model.eq(model)
            & transport.estimator.eq(chosen[model])
            & transport.status.eq("reported")
        ]
        return part.iloc[0]

    national = external("Catalonia -> Spain outside Catalonia", "catalonia_common_dgt")
    to_bcn = external("rest of Catalonia -> Barcelona municipality", "catalonia_crash_severity")
    main = (
        verdicts[verdicts.features.str.startswith("full")]
        .set_index("estimator")
        .loc[chosen["catalonia_crash_severity"]]
    )
    transferable = path.drop_duplicates("model").verdict.eq("potentially nationally transferable")

    body = "<h2>2. What individual crash records show</h2>"
    body += (
        f"<p>Catalonia records every crash with a death or serious injury: {_fmt_int(overall.n)} "
        f"in {period}, of which {_fmt_pct(overall.share)} were fatal. The fatal share was "
        f"{_fmt_pct(interurban.share)} on interurban roads against {_fmt_pct(urban.share)} on "
        f"urban streets, and {_fmt_pct(heavy.share)} when a heavy vehicle was involved. In "
        f"Barcelona in {bcn_year}, {_fmt_pct(pedestrian.share)} of the pedestrians recorded in "
        f"crashes were seriously or fatally injured, against {_fmt_pct(motorcycle.share)} of "
        f"motorcycle drivers and {_fmt_pct(car.share, 2)} of car drivers. These are shares among "
        "recorded crashes and people, not risks: neither source has trips or kilometres. "
        'Details: <a href="catalonia.html">Catalonia</a>, <a href="barcelona.html">Barcelona'
        "</a>.</p>"
    )

    body += "<h2>3. Which models earn their place</h2>"
    main_rows = decisions[
        ~decisions.variant.isin(["retrospective", "retrospective_administrative"])
    ]
    featured = main_rows[main_rows.decision.isin(decision_rules.FEATURED)]
    body += (
        "<p>Every model is first compared with a plain table of outcome shares on records it "
        f"never saw. {len(featured)} of the {len(main_rows)} models pass and are shown as models; "
        "the rest are kept for research or replaced by their table. They rank recorded cases by "
        "how severe the outcome was; none predicts whether a crash happens or estimates a "
        'causal effect. Details: <a href="severity-models.html">models page</a>.</p>'
    )
    body += table(
        pd.DataFrame(
            {
                "Model": [MODEL_NAMES.get(m, m.replace("_", " ")) for m in main_rows.model],
                "One row is": main_rows.unit,
                "Against a descriptive table": main_rows.usefulness,
                "Decision": main_rows.decision,
            }
        ),
        "Model decisions (details on the models page)",
    )

    body += "<h2>4. How far the models reach</h2>"
    body += (
        "<p>A transferred score is read only beside the target domain's own model. Restricted to "
        "the variables both sources record alike, the Catalan model on crashes recorded outside "
        f"Catalonia: native {national.in_domain_cv_roc_auc:.3f}, transferred "
        f"{national.roc_auc:.3f}, gap {national.transfer_gap:+.3f} "
        f"({_fmt_int(national.test_n)} crashes, {_fmt_int(national.test_positives)} fatal). "
        f"The full Catalan model on Barcelona: native {to_bcn.in_domain_cv_roc_auc:.3f}, "
        f"transferred {to_bcn.roc_auc:.3f}, gap {to_bcn.transfer_gap:+.3f}; most of the fall from "
        f"the rest of Catalonia is that Barcelona's crashes are harder to rank "
        f"({main.intrinsic_difference:.2f}), "
        + (
            "as other urban Catalan crashes are, "
            if main.intrinsic_difference_against_urban <= 0
            or not main.urban_comparison_excludes_zero
            else ""
        )
        + f"and its smaller training set ({main.training_size_cost:.2f}), not the move "
        f"({main.transport_cost:.2f}). "
        + (
            "No model passes every stage of the outward path, so none is called nationally "
            "transferable. "
            if not transferable.any()
            else ""
        )
        + 'Details: <a href="transport.html">how far the results reach</a>.</p>'
    )
    _check(
        main.intrinsic_difference + main.training_size_cost > main.transport_cost,
        "overview",
        "most of the Barcelona fall is difficulty and training size, not the move",
    )
    body += unanswerable_section()
    return body
