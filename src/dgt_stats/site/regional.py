"""The regional crash-record pages: Catalonia's serious and fatal crashes and Barcelona's crash
and person records. Each page states its results with the qualification they need; the full
tables, the checks on each file and the detail behind the results are technical notes on the
methodology page (``technical_notes``)."""

from __future__ import annotations

import re
from types import SimpleNamespace

import pandas as pd

from dgt_stats.microdata.charts import ROAD_USER_LABELS
from dgt_stats.microdata.validation import decisions as rules
from dgt_stats.site.components import (
    ALL_PAGES,
    DOCS_URL,
    _fmt_dec,
    _fmt_int,
    _fmt_pct,
    _join,
    downloads,
    esc,
    figure,
    limitation,
    read_table,
    render_page,
    summary,
    table,
)
from dgt_stats.site.regional_common import (
    MIN_N,
    _check,
    _dimension,
    _year_label,
)

DATA_QUALITY = f'<a href="{DOCS_URL}/DATA_QUALITY_MICRODATA.md">data-quality report</a>'
TITLES = dict(ALL_PAGES)
# The sections of the methodology page that hold each page's technical notes.
CAT_NOTES = "catalonia-method"
BCN_NOTES = "barcelona-method"

# How the Catalan breakdowns are named in tables, and the few category labels that read better
# in another form. Only labels are changed; every number comes from the result table.
CAT_DIMENSIONS = {
    "zone": "Zone",
    "lighting": "Lighting",
    "intersection": "Junction",
    "road type": "Road type",
    "unit type involved": "Involving",
    "crash subtype": "Crash type",
}
CAT_LABELS = {"road section": "away from a junction", "other unit": "other"}

# The Catalan fields whose blanks depend on the outcome, by their human names. Fields that record
# whether a condition influenced the crash are named by the condition.
CAT_FIELDS = {
    "D_CARACT_ENTORN": "the surroundings",
    "D_CARRIL_ESPECIAL": "special lanes",
    "D_SENTITS_VIA": "the number of traffic directions",
    "D_TRACAT_ALTIMETRIC": "gradient",
}
CAT_INFLUENCES = {
    "D_INFLUIT_BOIRA": "fog",
    "D_INFLUIT_CARACT_ENTORN": "the surroundings",
    "D_INFLUIT_INTEN_VENT": "wind",
    "D_INFLUIT_VISIBILITAT": "visibility",
}

NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")

# Barcelona's two cause lists: causes attached to a driver's action, and contributing factors.
BCN_CAUSE_KINDS = {" (driver)": "driver cause", " (mediate)": "contributing factor"}


def _count_word(value: int) -> str:
    return NUMBER_WORDS[value] if 0 <= value < len(NUMBER_WORDS) else _fmt_int(value)


def _dash(text: str) -> str:
    """A range written with a hyphen in the tables ('10-30') shown with an en dash."""
    return str(text).replace("-", "–")


def _interval(low: float, high: float) -> str:
    """A 95% interval of two shares, with an en dash and the per cent sign written once."""
    return f"{_fmt_pct(low).removesuffix('%')}–{_fmt_pct(high)}"


def _cat_share_rows(shares: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    """Fatal share by group, the groups of each breakdown ordered from most to least often fatal."""
    rows = shares[shares.dimension.isin(dimensions) & (shares.n >= MIN_N) & (shares.level != "all")]
    rows = rows.assign(order=rows.dimension.map(dimensions.index)).sort_values(
        ["order", "share"], ascending=[True, False]
    )
    return pd.DataFrame(
        {
            "Group": [
                f"{CAT_DIMENSIONS[d]}: {CAT_LABELS.get(label, label)}"
                for d, label in zip(rows.dimension, rows.label)
            ],
            "Crashes": rows.n,
            "Fatal": rows.events,
            "Fatal share": rows.share,
            "95% interval": [_interval(lo, hi) for lo, hi in zip(rows.ci_low, rows.ci_high)],
        }
    )


def _field_phrase(column: str) -> str:
    """One Catalan field named in words, as the subject of a sentence."""
    if column in CAT_INFLUENCES:
        return f"field recording the influence of {CAT_INFLUENCES[column]}"
    if column in CAT_FIELDS:
        return f"field for {CAT_FIELDS[column]}"
    raise ValueError(f"catalonia page: no human name for the field {column}")


def _blank_label(level: object) -> str:
    if pd.isna(level):
        return "blank"
    if str(level).strip().lower() == "sense especificar":
        return "marked “not specified”"
    raise ValueError(f"catalonia page: no human name for the recorded level {level!r}")


# ----------------------------------------------------------------------------- Catalonia
def _catalonia_facts() -> SimpleNamespace:
    """Every figure the Catalonia page and its technical notes quote, read from the tables, with
    the checks that the sentences built on them still hold."""
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
    top_road = roads.iloc[0]
    zones = _dimension(shares, "zone").set_index("label")
    interurban, urban = zones.loc["interurban road"], zones.loc["urban street"]
    units = _dimension(shares, "unit type involved")
    units = units[units.level != "all"].set_index("level")
    heavy, motorcycle = units.loc["heavy vehicle"], units.loc["motorcycle"]
    through = zones.loc["through-town road"]
    conventional = roads.set_index("level").loc["Carretera convencional"]
    crash_types = _dimension(shares, "crash subtype")
    top_type = crash_types.iloc[0]
    lighting = _dimension(shares, "lighting").set_index("label")
    unlit = lighting.loc["night, no street lighting"]
    lit = lighting.loc["night, adequate street lighting"]
    junctions = _dimension(shares, "intersection").set_index("label")
    between, inside = junctions.loc["road section"], junctions.loc["inside a junction"]
    _check(
        interurban.ci_low > urban.ci_high,
        "catalonia",
        "crashes on interurban roads are more often fatal than on urban streets",
    )
    _check(
        2.5 <= interurban.share / urban.share < 3
        and urban.share < through.share < interurban.share,
        "catalonia",
        "interurban crashes are almost three times as often fatal as urban ones, through-town "
        "roads in between",
    )
    _check(
        conventional.events > overall.events / 2,
        "catalonia",
        "conventional roads account for most fatal crashes",
    )
    _check(
        top_road.level != conventional.name
        and top_road.n < 0.05 * overall.n
        and top_road.ci_low <= conventional.ci_high
        and conventional.ci_low <= top_road.ci_high,
        "catalonia",
        "the road type with the highest point estimate has few crashes, and its interval "
        "overlaps that of conventional roads",
    )
    _check(
        roads.iloc[-1].label == "urban street" and units.share.idxmax() == "heavy vehicle",
        "catalonia",
        "urban streets have the lowest fatal share of any road type, and crashes involving a "
        "heavy vehicle the highest of any vehicle",
    )
    _check(
        top_type.label == "head-on collision",
        "catalonia",
        "head-on collisions are the most often fatal type of crash",
    )
    _check(
        heavy.ci_low > overall.share and heavy.share > 2 * overall.share,
        "catalonia",
        "crashes involving a heavy vehicle are fatal more than twice as often as average",
    )
    _check(
        motorcycle.ci_high < overall.share,
        "catalonia",
        "crashes involving a motorcycle are less often fatal than average",
    )
    by_count = units.n.sort_values(ascending=False)
    _check(
        list(by_count.index[:2]) == ["light vehicle", "motorcycle"] and heavy.n < motorcycle.n / 2,
        "catalonia",
        "motorcycles are involved in more crashes than any vehicle but light vehicles, heavy "
        "vehicles in far fewer",
    )
    _check(
        unlit.share == lighting.share.max()
        and lit.share == lighting.share.min()
        and unlit.ci_low > lit.ci_high,
        "catalonia",
        "unlit night crashes are the most often fatal and adequately lit night crashes the least",
    )
    _check(
        between.ci_low > inside.ci_high,
        "catalonia",
        "crashes away from a junction are more often fatal than crashes inside one",
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
    _check(
        within_one == len(dgt),
        "catalonia",
        "serious and fatal counts match DGT's 24-hour counts to within one crash in every "
        "province-year",
    )
    overlap = f"{int(dgt.year.min())}–{int(dgt.year.max())}"
    ratio30 = dgt.ratio_fatal_30d

    limits_ = shares[shares.dimension == "speed limit"].set_index("level")
    generic = limits_.loc["generic limit for the road (value not recorded)"]
    posted = shares[
        (shares.dimension == "speed limit")
        & shares.level.str.startswith("posted ")
        & (shares.n >= MIN_N)
    ]
    posted = posted.assign(
        limit=posted.level.str.extract(r"(\d+)", expand=False).astype(float)
    ).sort_values("limit")
    _check(
        posted.share.is_monotonic_increasing,
        "catalonia",
        "the fatal share rises with the posted limit",
    )
    _check(
        generic.n > overall.n / 2,
        "catalonia",
        "most crashes carry the generic limit for the type of road",
    )
    lowest, highest = posted.iloc[0], posted.iloc[-1]

    by_year = frequency.groupby("year")[["crashes", "fatal_crashes", "deaths"]].sum()
    low_year = int(by_year.crashes.idxmin())
    _check(
        first < low_year < last,
        "catalonia",
        "the yearly count falls to its lowest inside the period",
    )
    # Over the whole file, so that one year's chance variation does not set the order.
    pooled = per_resident.groupby("demarcation")[["crashes_fatal_or_serious", "population"]].sum()
    pooled = (pooled.crashes_fatal_or_serious / pooled.population * 1e5).sort_values(
        ascending=False
    )
    yearly_top = per_resident.loc[
        per_resident.groupby("year").crashes_fatal_or_serious_per_100k_residents.idxmax(),
        "demarcation",
    ]
    _check(
        yearly_top.nunique() == 1 and yearly_top.iloc[0] == pooled.index[0],
        "catalonia",
        "the same province has the highest rate per resident in every year",
    )
    rates = [f"{esc(name)} ({_fmt_dec(rate)})" for name, rate in pooled.iloc[1:].items()]

    outcome_dependent = artefacts[artefacts.verdict == "outcome-dependent recording"]
    # The recording check runs on the training and choice years of the first Catalan model,
    # never on its test year.
    design = read_table("ml_split_isolation").set_index("model").design
    design_years = re.findall(r"\d{4}", design["catalonia_crash_severity"])
    checked = f"{design_years[0]}–{design_years[3]}"
    _check(
        bool((outcome_dependent.ratio_fatal_to_serious < 1).all()),
        "catalonia",
        "the outcome-dependent blanks are more common in non-fatal than in fatal crashes",
    )
    worst = outcome_dependent.sort_values("ratio_fatal_to_serious").iloc[0]
    clean = int(checks.get("rows identical in every source column", 1)) == 0 and all(
        int(checks.get(name, 1)) == 0
        for name in (
            "fatal label with no death recorded",
            "serious label with a death recorded",
            "serious label with no serious injury recorded",
        )
    )
    _check(
        clean,
        "catalonia",
        "no duplicated rows, and every severity label agrees with the casualty counts",
    )
    return SimpleNamespace(**locals())


def page_catalonia(captions: dict[str, str]) -> str:
    f = _catalonia_facts()
    overall = f.overall
    notes = f'<a href="data.html#{CAT_NOTES}">technical notes</a>'

    def limit(row: pd.Series) -> str:
        return _dash(row.level.replace("posted ", ""))

    body = summary(
        f"In {f.period} the Servei Català de Trànsit recorded {_fmt_int(overall.n)} crashes in "
        "Catalonia that killed or seriously injured someone. In "
        f"{_fmt_int(overall.events)} ({_fmt_pct(overall.share)}) someone died within 24 hours. "
        f"The fatal share was {_fmt_pct(f.interurban.share)} on interurban roads, almost three "
        f"times the {_fmt_pct(f.urban.share)} on urban streets, and {_fmt_pct(f.heavy.share)} "
        "when a heavy vehicle was involved. These shares measure how often serious crashes were "
        "fatal, not how often crashes happen. "
        '<a href="severity.html">Spain\'s injury crashes</a> (deaths within 30 days) and '
        '<a href="barcelona.html">Barcelona\'s records</a> cover other crashes, so their shares '
        "differ."
    )

    body += (
        "<h2>Crashes were most often fatal on interurban roads, with a heavy vehicle and on "
        "unlit roads at night</h2>"
    )
    body += (
        "<p>Each share looks at one circumstance at a time, and the groups overlap: a crash on "
        "an unlit interurban road involving a heavy vehicle belongs to all three, so no share "
        "isolates the part one circumstance plays. The "
        '<a href="calculator.html">crash severity calculator</a>, built on this file, estimates '
        "the fatal share for a combination of circumstances, each adjusted for the others.</p>"
    )
    body += (
        "<p>Most fatal crashes were on conventional roads: "
        f"{_fmt_int(f.conventional.events)} of the {_fmt_int(overall.events)}, with "
        f"{_fmt_pct(f.conventional.share)} of the {_fmt_int(f.conventional.n)} serious crashes "
        "on those roads fatal. Roads through towns lay between interurban roads and urban "
        f"streets, at {_fmt_pct(f.through.share)}. {f.top_road.label.capitalize()}s had the "
        f"highest share of any road type ({_fmt_pct(f.top_road.share)}), but from only "
        f"{_fmt_int(f.top_road.n)} crashes, and its 95% interval "
        f"({_interval(f.top_road.ci_low, f.top_road.ci_high)}) overlaps that of conventional "
        "roads.</p>"
    )
    body += figure(
        "cat1_fatal_by_road",
        "Dot chart of the fatal share of crashes with a death or serious injury by road type, "
        "with 95% intervals; urban streets have the lowest share",
        captions,
    )
    body += (
        "<p>A share can rank groups differently from their number of crashes. Motorcycles were "
        f"involved in {_fmt_int(f.motorcycle.n)} crashes, more than any vehicle but light "
        f"vehicles, yet only {_fmt_pct(f.motorcycle.share)} were fatal, below the average of "
        f"{_fmt_pct(overall.share)}. Heavy vehicles were involved in far fewer "
        f"({_fmt_int(f.heavy.n)}), but {_fmt_pct(f.heavy.share)} of those crashes were fatal, "
        "more than twice the average.</p>"
    )
    body += figure(
        "cat3_fatal_by_unit",
        "Dot chart of the fatal share by type of vehicle or road user involved, with 95% "
        "intervals; crashes involving a heavy vehicle have the highest share",
        captions,
    )
    body += (
        "<p>At night, crashes on roads without street lighting were fatal in "
        f"{_fmt_pct(f.unlit.share)} of cases and those under adequate street lighting in "
        f"{_fmt_pct(f.lit.share)}, the highest and lowest shares of any lighting condition. "
        "Head-on collisions were the most often fatal type of crash "
        f"({_fmt_pct(f.top_type.share)}). Away from a junction {_fmt_pct(f.between.share)} of "
        f"crashes were fatal, inside one {_fmt_pct(f.inside.share)}. Every share, with its count "
        f"and interval, is in the {notes}.</p>"
    )

    body += "<h2>The fatal share rises with the posted speed limit</h2>"
    body += (
        "<p>The speed-limit field records the limit signposted on the road, not how fast anyone "
        "was driving; no file in the study records vehicle speeds. Where a limit was posted, "
        f"the fatal share rises with it, from {_fmt_pct(f.lowest.share)} at {limit(f.lowest)} "
        f"to {_fmt_pct(f.highest.share)} at {limit(f.highest)}. Higher limits are posted on "
        "faster, mostly interurban roads, so the rise describes the roads as much as the limits. "
        f"In {_fmt_int(f.generic.n)} crashes ({_fmt_pct(f.generic.n / overall.n)}) no limit was "
        "posted and the generic limit for the type of road applied.</p>"
    )
    body += figure(
        "cat2_fatal_by_speed_limit",
        "Dot chart of the fatal share by posted speed limit, with 95% intervals; the share "
        "rises with the limit, and most crashes have no posted limit recorded",
        captions,
    )

    crashes = f.by_year.crashes
    body += (
        f"<h2>Fewest crashes in {f.low_year}, most per resident in {esc(f.pooled.index[0])}</h2>"
    )
    body += (
        "<p>The number of crashes with a death or serious injury fell from "
        f"{_fmt_int(crashes.loc[f.first])} in {f.first} to {_fmt_int(crashes.loc[f.low_year])} "
        f"in {f.low_year}, the lowest of the period, and was {_fmt_int(crashes.loc[f.last])} in "
        f"{f.last}.</p>"
        '<p id="dgt-agreement">These counts agree with DGT\'s national records, compared by '
        f"province and year: in all {len(f.dgt)} province-years of {f.overlap} the file's fatal "
        "crashes equal DGT's crashes with a death within 24 hours. The file does not state its "
        "definition of a fatal crash; this agreement shows it.</p>"
        "<p>Relative to population, such crashes were most frequent in the province of "
        f"{esc(f.pooled.index[0])} in every year: {_fmt_dec(f.pooled.iloc[0])} a year per "
        f"100,000 residents over {f.period}, followed by {_join(f.rates)}. Crashes are counted "
        "where they happened and residents where they live, so visitors and through traffic "
        "count in a province's crashes but not in its population. The file has no measure of "
        "how far people travel.</p>"
    )
    body += limitation(
        "The file describes crashes only: it has no records of the people involved and no "
        "alcohol or drug test results."
    )
    body += downloads(
        [
            ("cat_fatal_share", "fatal share by group"),
            ("cat_frequency", "crashes by year, province and zone"),
            ("cat_vs_dgt_province_year", "comparison with DGT's crash records"),
            ("cat_per_resident_province_year", "crashes per resident"),
            ("ml_recording_artefacts", "recording check"),
        ],
        method=(f"data.html#{CAT_NOTES}", "every fatal share and the checks on the file"),
    )
    return render_page(
        "catalonia",
        f"Serious and fatal crashes in Catalonia, {f.period}",
        "Crashes in which someone was killed or seriously injured in Catalonia, from the "
        "Servei Català de Trànsit's file: how often they were fatal, and in which "
        "circumstances.",
        body,
    )


def _catalonia_notes(captions: dict[str, str]) -> str:
    """Every fatal share with its count and interval, the counts by year, the comparison with
    DGT's records and the recording check on the Catalan file."""
    f = _catalonia_facts()
    overall = f.overall
    page = f'<a href="catalonia.html">{TITLES["catalonia"]}</a>'
    every_share = pd.concat(
        [
            pd.DataFrame(
                {
                    "Group": ["All crashes with a death or serious injury"],
                    "Crashes": [overall.n],
                    "Fatal": [overall.events],
                    "Fatal share": [overall.share],
                    "95% interval": [_interval(overall.ci_low, overall.ci_high)],
                }
            ),
            _cat_share_rows(
                f.shares,
                [
                    "zone",
                    "road type",
                    "unit type involved",
                    "crash subtype",
                    "lighting",
                    "intersection",
                ],
            ),
        ]
    )
    years = f.by_year.reset_index().rename(
        columns={
            "year": "Year",
            "crashes": "Crashes",
            "fatal_crashes": "Fatal crashes",
            "deaths": "Deaths within 24 hours",
        }
    )
    return (
        f'<h2 id="{CAT_NOTES}">{TITLES["catalonia"]}: every fatal share and the checks on the '
        "file</h2>"
        f"<p>These notes support {page}. How a share computed from crash records is read is set "
        'out under <a href="#records">Reading police crash records</a>; the repository\'s '
        f"{DATA_QUALITY} documents every check on the file.</p>"
        '<h3 id="catalonia-shares">Fatal share by zone, road, vehicle, crash type, lighting and '
        "junction</h3>"
        "<p>Each group is one circumstance at a time, so the groups overlap. A crash involving "
        "several kinds of vehicle or road user counts in each, and zone and road type are "
        "separate fields of the file, so their urban-street groups differ slightly.</p>"
        + table(
            every_share,
            "Fatal share of crashes with a death or serious injury, Catalonia, "
            f"{f.period} (groups with at least {MIN_N} crashes).",
            {"Crashes": "int", "Fatal": "int", "Fatal share": "pct"},
        )
        + figure(
            "cat4_fatal_by_crash_type",
            "Dot chart of the fatal share by type of crash, with 95% intervals; head-on "
            "collisions have the highest share",
            captions,
        )
        + '<h3 id="catalonia-years">Crashes, fatal crashes and deaths by year</h3>'
        + table(
            years,
            f"Recorded crashes with a death or serious injury by year, Catalonia, {f.period}. A "
            "fatal crash is one in which someone died within 24 hours; later deaths are recorded "
            "as serious injuries.",
            {
                "Year": "year",
                "Crashes": "int",
                "Fatal crashes": "int",
                "Deaths within 24 hours": "int",
            },
        )
        + "<h3 id=\"catalonia-dgt\">How the file's counts compare with DGT's national "
        "records</h3>"
        "<p>The Catalan file shares no record identifier with DGT's national crash records, so "
        "the two are compared by year and province (the file's traffic demarcations). Over "
        f"{f.overlap}, the file's fatal crashes equal DGT's crashes with a death within 24 hours "
        f"in all {len(f.dgt)} province-years, and its total count matches DGT's 24-hour count of "
        "crashes with a death or serious injury to within one crash in every province-year. "
        f"Its fatal count is {_fmt_pct(f.ratio30.min(), 0).removesuffix('%')}–"
        f"{_fmt_pct(f.ratio30.max(), 0)} of DGT's count of crashes with a death within 30 days. "
        "The file does not state its definition; the counts show that it is the 24-hour "
        "one.</p>"
        '<h3 id="catalonia-recording">Fields left blank more often in non-fatal crashes</h3>'
        f"<p>The recording check, run on the crashes of {f.checked}, finds "
        f"{_count_word(len(set(f.outcome_dependent.column)))} fields that are left blank or "
        "marked “not specified” much more often in non-fatal crashes than in fatal ones. The "
        f"{_field_phrase(f.worst.column)}, for example, is {_blank_label(f.worst.level)} in "
        f"{_fmt_pct(f.worst.rate_serious)} of non-fatal crashes and "
        f"{_fmt_pct(f.worst.rate_fatal)} of fatal ones. The file gives no reason, but the blank "
        "itself carries information about the outcome, and none of these fields is used on the "
        "Catalonia page. Otherwise the file is consistent: it has no duplicated rows, and every "
        "severity label agrees with the deaths and injuries recorded on the same row.</p>"
    )


# ----------------------------------------------------------------------------- Barcelona
def _cause(label: str) -> tuple[str, str]:
    """A recorded cause's name without its list marker, and which list it comes from."""
    suffix = next((s for s in BCN_CAUSE_KINDS if label.endswith(s)), None)
    if suffix is None:
        raise ValueError(f"barcelona page: unknown kind of recorded cause {label!r}")
    return label.removesuffix(suffix), BCN_CAUSE_KINDS[suffix]


def _cause_rows(causes: pd.DataFrame) -> pd.DataFrame:
    named = [_cause(label) for label in causes.label]
    return pd.DataFrame(
        {
            "Recorded cause": [name[:1].upper() + name[1:] for name, _ in named],
            "Recorded as": [kind for _, kind in named],
            "Crashes": causes.n.to_numpy(),
            "Serious or fatal": causes.events.to_numpy(),
            "Share": causes.share.to_numpy(),
        }
    )


def _person_label(dimension: str, label: str) -> str:
    """A group of people as its table row names it; the column already names the breakdown."""
    if dimension == "age band":
        label = "75 and over" if label == "75+" else _dash(label)
    elif dimension == "road user":
        # The same names the road-user figure uses.
        label = ROAD_USER_LABELS.get(label, label)
    return label[:1].upper() + label[1:]


def _person_table(people: pd.DataFrame, dimension: str, column: str, caption: str) -> str:
    """Serious or fatal injury for one breakdown of the people. Road users are ordered as in
    their figure, from the highest share; age bands and sexes keep the table's order."""
    rows = people[(people.dimension == dimension) & (people.n >= MIN_N)]
    if dimension == "road user":
        rows = rows.sort_values(["share", "n"], ascending=False, kind="stable")
    return table(
        pd.DataFrame(
            {
                column: [_person_label(dimension, label) for label in rows.label],
                "People": rows.n,
                "Serious or fatal": rows.events,
                "Share": rows.share,
                "95% interval": [_interval(lo, hi) for lo, hi in zip(rows.ci_low, rows.ci_high)],
            }
        ),
        caption,
        {"People": "int", "Serious or fatal": "int", "Share": "pct"},
    )


def _barcelona_facts() -> SimpleNamespace:
    """Every figure the Barcelona page and its technical notes quote, read from the tables, with
    the checks that the sentences built on them still hold."""
    people = read_table("bcn_person_severity_share")
    crashes = read_table("bcn_crash_severity_share")
    structure = read_table("mq_bcn_structure").set_index("table")
    profiles = read_table("bcn_cause_profiles")
    outcomes = read_table("bcn_people_by_severity").groupby("injury_severity").person_records.sum()

    year = _year_label(people)
    n_crashes = int(structure.loc["bcn_accidents", "rows"])
    n_people = int(structure.loc["bcn_people", "rows"])
    road_users = _dimension(people, "road user").set_index("level")
    labelled = int(people[people.dimension == "road user"].n.sum())
    severe_people = int(people[people.dimension == "road user"].events.sum())
    natural = int(outcomes.get("excluded_natural_death", 0))
    not_recorded = int(outcomes.get("not_recorded", 0))
    _check(
        labelled == n_people - not_recorded - natural,
        "barcelona",
        "the person shares leave out only people with no recorded outcome and natural deaths",
    )
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
    _check(
        pedestrian.share > 10 * car_driver.share and motorcycle.share > 10 * car_driver.share,
        "barcelona",
        "pedestrians and motorcyclists are far more often seriously hurt than car drivers",
    )
    _check(
        road_users.share.idxmax() == "pedestrian",
        "barcelona",
        "pedestrians have the highest share of any road user",
    )
    _check(
        car_driver.n == road_users.n.max(),
        "barcelona",
        "car drivers are the largest group of road users in the person records",
    )
    riders = road_users.loc[["bicycle driver", "moped driver", "personal mobility vehicle driver"]]
    _check(
        bool(riders.share.between(car_driver.share, motorcycle.share, inclusive="neither").all()),
        "barcelona",
        "cyclists, moped riders and personal mobility vehicle riders fall between car drivers "
        "and motorcyclists",
    )
    rider_shares = [
        f"{ROAD_USER_LABELS[level]}s ({_fmt_pct(row.share)})" for level, row in riders.iterrows()
    ]
    ages = _dimension(people, "age band")
    ages = ages[ages.level != "not recorded"].set_index("level")
    oldest = ages.loc["75+"]
    younger = ages.drop(index="75+")
    _check(
        oldest.ci_low > younger.share.max(),
        "barcelona",
        "people aged 75 and over are the most often seriously hurt age band",
    )
    sexes = _dimension(people, "sex").set_index("level")
    female, male = sexes.loc["female"], sexes.loc["male"]
    _check(
        female.ci_low <= male.ci_high and male.ci_low <= female.ci_high,
        "barcelona",
        "women and men differ little in the share seriously hurt",
    )

    crash_all = crashes[(crashes.dimension == "cause recorded") & (crashes.level == "all")].iloc[0]
    _check(
        crash_all.share > severe_people / labelled,
        "barcelona",
        "the share of crashes with a serious injury exceeds the share of people seriously hurt",
    )
    crash_types = _dimension(crashes, "crash type").set_index("level")
    struck = crash_types.loc["pedestrian struck"]
    rear_end = crash_types.loc["rear-end collision"]
    # The codes as recorded: "Encalç", the Catalan file's term for a rear-end collision, against
    # the Guàrdia Urbana's own rear-end code ("Abast"); together they make the rear-end group.
    # Multiple rear-end collisions ("Abast multiple") are a crash type of their own.
    codes = crashes[crashes.dimension == "crash-type code as recorded"].set_index("level")
    catching_up = codes.loc["Encalç"]
    own_n, own_events = int(codes.loc["Abast", "n"]), int(codes.loc["Abast", "events"])
    multiple = codes.loc["Abast multiple"]
    _check(
        catching_up.n + codes.loc["Abast", "n"] == rear_end.n
        and catching_up.events + codes.loc["Abast", "events"] == rear_end.events
        and catching_up.share > 10 * crash_all.share
        and own_events / own_n < crash_all.share
        and int(multiple.events) == 0,
        "barcelona",
        "the term for a catching-up rear collision marks mostly serious crashes, the force's own "
        "rear-end codes almost none, and the two together make the rear-end group",
    )
    _check(
        rear_end.ci_high < crash_all.share,
        "barcelona",
        "rear-end collisions are less often serious than the average crash",
    )
    _check(
        crash_types.share.idxmax() == "pedestrian struck"
        and struck.ci_low > crash_all.share
        and struck.share > 2 * crash_all.share,
        "barcelona",
        "among crash types with enough crashes, a pedestrian struck has the highest share, more "
        "than twice the average",
    )
    rule = read_table("ml_rule_comparison").set_index("model").loc["barcelona_crash_severity"]
    _check(
        not bool(rule.model_adds_signal_over_table) and rule.rule == "accident_type",
        "barcelona",
        "a model of the crashes ranks them no better than the table by accident type",
    )
    decisions = read_table("ml_model_decisions")
    decisions = decisions[decisions.variant == "context"].set_index("model").decision
    _check(
        decisions["barcelona_crash_severity"] == rules.REPLACE
        and decisions["barcelona_person_severity"] == rules.KEEP_RANKING
        and rules.STATUS["barcelona_person_severity"] == "research only",
        "barcelona",
        "the crash model gave way to its table, and the person model only ranks people and is "
        "kept for research only",
    )
    semantics = read_table("mq_bcn_count_semantics").set_index("check").value
    no_victim = int(semantics["blank cells in Numero_victimes"])
    injury_share = crash_all.events / (crash_all.n - no_victim)
    _check(
        0 < no_victim < crash_all.n and crash_all.n == n_crashes,
        "barcelona",
        "some of the crashes the police attended had no victim",
    )
    alcohol = profiles[(profiles.cause == "alcohol")].set_index(["group", "measure"])
    alc_night = alcohol.loc[("alcohol recorded", "night_shift")]
    other_night = alcohol.loc[("alcohol not recorded", "night_shift")]
    _check(
        alc_night.ci_low > other_night.ci_high,
        "barcelona",
        "alcohol-recorded crashes are more often at night",
    )
    # "Not determined" says that no driver cause was established; it is not a cause.
    causes = crashes[
        (crashes.dimension == "cause recorded")
        & (crashes.level != "all")
        & (crashes.n >= MIN_N)
        & ~crashes.level.str.startswith("not determined")
    ].sort_values("n", ascending=False)
    driver_status = crashes[crashes.dimension == "driver causes recorded"].set_index("level").n
    mediate_status = crashes[crashes.dimension == "mediate causes recorded"].set_index("level").n
    _check(
        int(driver_status.sum()) == n_crashes and int(mediate_status.sum()) == n_crashes,
        "barcelona",
        "every crash has one driver-cause and one contributing-factor status",
    )
    most_recorded = causes.iloc[0]
    most_serious = causes.sort_values("share").iloc[-1]
    _check(
        most_serious.ci_low > crash_all.share,
        "barcelona",
        "the most often serious recorded cause is above the all-crash share",
    )
    _check(
        int(driver_status.get("blank", 0)) + int(driver_status.get("not_determined", 0))
        < n_crashes / 2,
        "barcelona",
        "most crashes have a driver cause recorded",
    )
    return SimpleNamespace(**locals())


def page_barcelona(captions: dict[str, str]) -> str:
    f = _barcelona_facts()
    crash_all, rear_end, catching_up = f.crash_all, f.rear_end, f.catching_up
    notes = f'<a href="data.html#{BCN_NOTES}">technical notes</a>'
    body = summary(
        f"The Guàrdia Urbana, Barcelona's city police, recorded {_fmt_int(f.n_crashes)} crashes "
        f"in {f.year}: every crash it attended, with every person involved. Of the "
        f"{_fmt_int(f.labelled)} people whose outcome was recorded, "
        f"{_fmt_pct(f.severe_people / f.labelled)} were seriously injured (more than 24 hours in "
        f"hospital) or killed. Pedestrians ({_fmt_pct(f.pedestrian.share)}) and motorcyclists "
        f"({_fmt_pct(f.motorcycle.share)}) were far more often seriously hurt than car drivers "
        f"({_fmt_int(f.car_driver.events)} of {_fmt_int(f.car_driver.n)}, "
        f"{_fmt_pct(f.car_driver.share, 2)}). These are shares of people in recorded crashes, "
        'not rates per journey. <a href="severity.html">Spain\'s '
        'figures</a> (deaths within 30 days) and <a href="catalonia.html">Catalonia\'s</a> '
        "(deaths within 24 hours) cover other crashes."
    )

    body += "<h2>Pedestrians and people aged 75 and over were most often seriously hurt</h2>"
    body += figure(
        "bcn1_severity_by_road_user",
        "Dot chart of the share of people seriously or fatally injured, by road user, with 95% "
        "intervals; pedestrians have the highest share",
        captions,
    )
    body += (
        f"<p>The shares for {_join(f.rider_shares)} lie between those of car drivers and "
        "motorcyclists. By age, the share is highest among people aged 75 and over "
        f"({_fmt_pct(f.oldest.share)}); in every younger age band it lies between "
        f"{_fmt_pct(f.younger.share.min())} and {_fmt_pct(f.younger.share.max())}. Women and "
        f"men differ little ({_fmt_pct(f.female.share)} and {_fmt_pct(f.male.share)}).</p>"
    )
    body += figure(
        "bcn2_severity_by_age",
        "Dot chart of the share of people seriously or fatally injured, by age band, with 95% "
        "intervals; the share is highest at 75 and over",
        captions,
    )

    body += (
        '<h2 id="serious-injury-by-type-of-crash">Crashes in which a pedestrian was struck were '
        "most often serious</h2>"
    )
    body += (
        f"<p>Of the {_fmt_int(f.n_crashes)} crashes, including those in which nobody was hurt, "
        f"{_fmt_pct(crash_all.share)} had at least one serious or fatal injury. That is more than "
        "the share of people, because one seriously injured person places a crash in the group. "
        f"Among crash types with at least {MIN_N} crashes, the share is highest when a "
        f"pedestrian was struck: {_fmt_pct(f.struck.share)}, more than twice the average.</p>"
    )
    body += figure(
        "bcn4_crash_severity_by_type",
        "Dot chart of the share of crashes with a serious or fatal injury, by crash type, with "
        "95% intervals; crashes in which a pedestrian was struck have the highest share",
        captions,
    )
    body += (
        "<p>One crash-type code records the outcome rather than a kind of crash. The Guàrdia "
        "Urbana codes rear-end collisions with its own term, but in "
        f"{_fmt_int(catching_up.n)} crashes it used the Catalan file's term for one, and "
        f"{_fmt_int(catching_up.events)} of those had a serious or fatal injury, against "
        f"{_fmt_int(f.own_events)} of the {_fmt_int(f.own_n)} with its own code. The page counts "
        "both as rear-end collisions, which had a serious or fatal injury in "
        f"{_fmt_pct(rear_end.share)} of {_fmt_int(rear_end.n)} crashes.</p>"
        "<p>Two models were fitted on these records, and neither gives probabilities on this "
        "site. The crash model ranked crashes no better than the shares by crash type, which "
        "the site gives instead; model and shares alike read the crash type as recorded, the "
        "code above included. The person model can only rank people and is kept for research "
        'only (<a href="data.html#models">how the models were judged</a>).</p>'
    )

    most_recorded = _cause(f.most_recorded.label)[0]
    most_serious = f.most_serious
    body += f"<h2>The police recorded {esc(most_recorded)} more often than any other cause</h2>"
    body += (
        "<p>For most crashes the Guàrdia Urbana records one or more causes or contributing "
        "factors, such as lack of attention, alcohol or the state of the road. They are the "
        "police's classification after attending the crash, not causal estimates. They are "
        "also recorded for the crash as a whole, so a cause cannot be tied to the driver or "
        "vehicle concerned, or to the person who was hurt.</p>"
        f"<p>{esc(most_recorded[:1].upper() + most_recorded[1:])} was recorded in "
        f"{_fmt_int(f.most_recorded.n)} crashes. Among causes recorded in at least {MIN_N} "
        "crashes, a serious or fatal injury was most often recorded where "
        f"{esc(_cause(most_serious.label)[0])} was: {_fmt_pct(most_serious.share)} of "
        f"{_fmt_int(most_serious.n)} crashes (95% interval "
        f"{_interval(most_serious.ci_low, most_serious.ci_high)}), against "
        f"{_fmt_pct(crash_all.share)} of all crashes. Alcohol was recorded in "
        f"{_fmt_int(f.alc_night.n)} crashes, {_fmt_pct(f.alc_night.share)} of them at night, "
        f"against {_fmt_pct(f.other_night.share)} of the other crashes. Every recorded cause is "
        f"listed in the {notes}.</p>"
    )
    body += limitation(
        "The records cover one year in one city, so they show no change over time, and they "
        "share no identifier with the Catalan file or DGT's records."
    )
    body += downloads(
        [
            ("bcn_person_severity_share", "injury by person group"),
            ("bcn_people_by_severity", "people by recorded outcome"),
            ("bcn_crash_severity_share", "crashes with a serious or fatal injury"),
            ("bcn_frequency", "crashes by month, hour, weekday and district"),
            ("bcn_cause_profiles", "alcohol- and speed-recorded crashes"),
            ("mq_bcn_structure", "record counts by table"),
        ],
        method=(f"data.html#{BCN_NOTES}", "people left out, rear-end codes and recorded causes"),
    )
    return render_page(
        "barcelona",
        f"Crashes and casualties in Barcelona, {f.year}",
        f"Every crash Barcelona's city police attended in {f.year}, with each person involved: "
        "who was seriously hurt, in which kinds of crash, and the causes the police recorded.",
        body,
    )


def _barcelona_notes() -> str:
    """The people the shares leave out, the counts by road user, age and sex, the crashes
    without a victim, the two rear-end codes and every recorded cause."""
    f = _barcelona_facts()
    page = f'<a href="barcelona.html">{TITLES["barcelona"]}</a>'
    left_out = f"the {_fmt_int(f.not_recorded)} people whose outcome was not recorded" + (
        f" and {_count_word(f.natural)} death{'s' if f.natural > 1 else ''} the police recorded "
        "as natural"
        if f.natural
        else ""
    )
    note = (
        f"People with a recorded outcome, Barcelona, {f.year}, in groups of at least {MIN_N} "
        "people."
    )
    driver_status, mediate_status = f.driver_status, f.mediate_status
    return (
        f'<h2 id="{BCN_NOTES}">{TITLES["barcelona"]}: the people left out, the rear-end codes '
        "and every recorded cause</h2>"
        f"<p>These notes support {page}. How the records' blank counts and recorded causes are "
        'read is set out under <a href="#records">Reading police crash records</a>. The Guàrdia '
        "Urbana's crash, person, vehicle and cause tables are linked by a crash number; the "
        f"repository's {DATA_QUALITY} documents their keys, counts and blank cells.</p>"
        '<h3 id="barcelona-people">Serious or fatal injury by road user, age and sex</h3>'
        "<p>A person counts as seriously injured after more than 24 hours in hospital, and the "
        f"shares put serious and fatal injuries together. They leave out {left_out}. Counted as "
        "uninjured, the people without a recorded outcome would lower the overall share from "
        f"{_fmt_pct(f.severe_people / f.labelled)} to "
        f"{_fmt_pct(f.severe_people / (f.labelled + f.not_recorded))}.</p>"
        + _person_table(
            f.people, "road user", "Road user", f"Serious or fatal injury by road user. {note}"
        )
        + _person_table(f.people, "age band", "Age", f"Serious or fatal injury by age. {note}")
        + _person_table(f.people, "sex", "Sex", f"Serious or fatal injury by sex. {note}")
        + '<h3 id="barcelona-crashes">Crashes without a victim, and the two rear-end codes</h3>'
        f"<p>The police recorded no victim in {_fmt_int(f.no_victim)} of the "
        f"{_fmt_int(f.n_crashes)} crashes they attended. Among the crashes with a victim, "
        f"{_fmt_pct(f.injury_share)} had a serious or fatal injury, against "
        f"{_fmt_pct(f.crash_all.share)} of all crashes.</p>"
        "<p>The rear-end group joins two codes: the Guàrdia Urbana's own code for a rear-end "
        f"collision ({_fmt_int(f.own_events)} of {_fmt_int(f.own_n)} crashes with a serious or "
        "fatal injury) and the Catalan file's term for one "
        f"({_fmt_int(f.catching_up.events)} of {_fmt_int(f.catching_up.n)}). The term is used "
        "when a crash is serious, so it records the outcome rather than a kind of crash. The "
        f"{_fmt_int(int(f.multiple.n))} multiple rear-end collisions are a crash type of their "
        "own, and none had a serious or fatal injury.</p>"
        '<h3 id="barcelona-causes">Every recorded cause</h3>'
        f"<p>No driver cause is recorded for {_fmt_int(driver_status.get('blank', 0))} crashes "
        f"and only “not determined” for {_fmt_int(driver_status.get('not_determined', 0))}; "
        f"contributing factors are recorded for {_fmt_int(mediate_status.get('recorded', 0))}. "
        "A crash can have several causes, recorded for the crash as a whole.</p>"
        + table(
            _cause_rows(f.causes),
            f"Crashes by recorded cause and the share with a serious or fatal injury, Barcelona, "
            f"{f.year} (causes recorded in at least {MIN_N} crashes; a crash can have several).",
            {"Crashes": "int", "Serious or fatal": "int", "Share": "pct"},
        )
    )


def technical_notes(captions: dict[str, str]) -> str:
    """The two regional pages' technical notes, one section each, for the methodology page."""
    return _catalonia_notes(captions) + _barcelona_notes()
