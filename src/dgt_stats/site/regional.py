"""The regional crash-record pages: Catalonia's serious and fatal crashes and Barcelona's crash
and person records."""

from __future__ import annotations

import re

import pandas as pd

from dgt_stats.microdata.charts import ROAD_USER_LABELS
from dgt_stats.site.components import (
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
    technical,
)
from dgt_stats.site.regional_common import (
    MIN_N,
    _check,
    _dimension,
    _year_label,
)

DATA_QUALITY = f'<a href="{DOCS_URL}/DATA_QUALITY_MICRODATA.md">data-quality report</a>'

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

    body = summary(
        f"The Catalan file holds {_fmt_int(overall.n)} crashes with a death or serious injury "
        f"recorded between {first} and {last}. It contains only such crashes, so the "
        "percentages on this page describe severity among crashes that were already serious, "
        "not the chance that a journey or an ordinary crash ends in a death. Of these crashes, "
        f"{_fmt_int(overall.events)} ({_fmt_pct(overall.share)}) were fatal, with a death within "
        f"24 hours. The fatal share was {_fmt_pct(interurban.share)} on interurban roads, almost "
        f"three times the {_fmt_pct(urban.share)} on urban streets, and it reached "
        f"{_fmt_pct(heavy.share)} when a heavy vehicle was involved and "
        f"{_fmt_pct(unlit.share)} at night on roads without street lighting."
    )

    body += "<h2>Fatal share by road, vehicle and circumstance</h2>"
    body += (
        "<p>Most fatal crashes were on conventional roads: "
        f"{_fmt_int(conventional.events)} of the file's {_fmt_int(overall.events)}, with "
        f"{_fmt_pct(conventional.share)} of the {_fmt_int(conventional.n)} serious crashes on "
        f"those roads fatal. {top_road.label.capitalize()}s have the highest fatal share of any "
        f"road type ({_fmt_pct(top_road.share)}), but it rests on only {_fmt_int(top_road.n)} "
        f"crashes and its 95% interval ({_interval(top_road.ci_low, top_road.ci_high)}) "
        "overlaps that of conventional roads. Crashes on roads through towns were fatal in "
        f"{_fmt_pct(through.share)} of cases, between interurban roads and urban streets. By "
        "type of crash, head-on collisions were the most often fatal "
        f"({_fmt_pct(top_type.share)}).</p>"
    )
    body += figure(
        "cat1_fatal_by_road",
        "Dot chart of the fatal share of crashes with a death or serious injury by road type, "
        "with 95% intervals; urban streets have the lowest share",
        captions,
    )
    body += (
        "<p>A fatal share can rank groups quite differently from their number of crashes. "
        f"Motorcycles were involved in {_fmt_int(motorcycle.n)} of the file's crashes, more than "
        "any other type of vehicle except light vehicles, yet only "
        f"{_fmt_pct(motorcycle.share)} of those crashes were fatal, below the average of "
        f"{_fmt_pct(overall.share)}. Heavy vehicles were involved in far fewer "
        f"({_fmt_int(heavy.n)}), but {_fmt_pct(heavy.share)} of them were fatal, more than "
        "twice the average.</p>"
    )
    body += figure(
        "cat3_fatal_by_unit",
        "Dot chart of the fatal share by type of vehicle or road user involved, with 95% "
        "intervals; crashes involving a heavy vehicle have the highest share",
        captions,
    )
    body += figure(
        "cat4_fatal_by_crash_type",
        "Dot chart of the fatal share by type of crash, with 95% intervals; head-on collisions "
        "have the highest share",
        captions,
    )
    body += (
        "<p>At night, crashes on roads without street lighting were fatal in "
        f"{_fmt_pct(unlit.share)} of cases and those under adequate street lighting in "
        f"{_fmt_pct(lit.share)}, the highest and lowest shares of any lighting condition. Away "
        f"from a junction, {_fmt_pct(between.share)} of crashes were fatal; inside a junction, "
        f"{_fmt_pct(inside.share)}. The groups overlap: a crash on an unlit interurban road "
        "involving a heavy vehicle belongs to several at once, so each fatal share describes "
        "the circumstances that go with a fatal outcome without separating the part played by "
        "any one of them.</p>"
    )
    body += technical(
        "Fatal share by zone, road type, vehicle, type of crash, lighting and junction",
        table(
            pd.concat(
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
                        shares,
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
            ),
            "Fatal share of crashes with a death or serious injury, Catalonia, "
            f"{period} (groups with at least {MIN_N} crashes; a crash involving several kinds of "
            "vehicle counts in each).",
            {"Crashes": "int", "Fatal": "int", "Fatal share": "pct"},
        ),
    )

    body += "<h2>Fatal share by posted speed limit</h2>"
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
    body += (
        "<p>The speed-limit field records the limit signposted on the road, not how fast "
        "anyone was driving; no file in the study records vehicle speeds. In "
        f"{_fmt_int(generic.n)} crashes ({_fmt_pct(generic.n / overall.n)} of the file) no "
        "specific limit was posted and the generic limit for the type of road applied. Where a "
        f"limit was posted, the fatal share rises with it, from {_fmt_pct(lowest.share)} at "
        f"{_dash(lowest.level.replace('posted ', ''))} to {_fmt_pct(highest.share)} at "
        f"{_dash(highest.level.replace('posted ', ''))}. Higher limits are posted on faster, "
        "mostly interurban roads, so the rise describes the roads as much as the limits.</p>"
    )
    body += figure(
        "cat2_fatal_by_speed_limit",
        "Dot chart of the fatal share by posted speed limit, with 95% intervals; the share "
        "rises with the limit",
        captions,
    )

    body += "<h2>Crashes by year and province</h2>"
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
    body += (
        "<p>The number of crashes with a death or serious injury fell from "
        f"{_fmt_int(by_year.crashes.loc[first])} in {first} to "
        f"{_fmt_int(by_year.crashes.loc[low_year])} in {low_year}, the lowest of the period, and "
        f"was {_fmt_int(by_year.crashes.loc[last])} in {last}. Relative to population, such "
        f"crashes were most frequent in the province of {esc(pooled.index[0])} in every year. "
        f"Over {period} it recorded {_fmt_dec(pooled.iloc[0])} a year per 100,000 residents, "
        f"followed by the provinces of {_join(rates)}. The crashes are counted where they "
        "happened and the residents where they live, so visitors and through traffic count in "
        "a province's crashes but not in its population. These are rates per resident; the "
        "file has no measure of how far people travel.</p>"
    )
    body += figure(
        "cat6_crashes_by_year",
        "Bar chart of crashes with a death or serious injury recorded each year",
        captions,
    )
    body += technical(
        "Crashes, fatal crashes and deaths by year",
        table(
            by_year.reset_index().rename(
                columns={
                    "year": "Year",
                    "crashes": "Crashes",
                    "fatal_crashes": "Fatal crashes",
                    "deaths": "Deaths within 24 hours",
                }
            ),
            f"Recorded crashes with a death or serious injury by year, Catalonia, {period}. A "
            "fatal crash is one in which someone died within 24 hours; later deaths are recorded "
            "as serious injuries.",
            {
                "Year": "year",
                "Crashes": "int",
                "Fatal crashes": "int",
                "Deaths within 24 hours": "int",
            },
        ),
    )

    body += '<h2 id="dgt-agreement">Agreement with DGT\'s national records</h2>'
    overlap = f"{int(dgt.year.min())}–{int(dgt.year.max())}"
    ratio30 = dgt.ratio_fatal_30d
    body += (
        "<p>The Catalan file shares no record identifier with DGT's national crash records, so "
        "the two are compared by year and province (the file's traffic demarcations). Over "
        f"{overlap}, the file's count of fatal crashes equals DGT's count of crashes with a "
        f"death within 24 hours in {equal_fatal_24h} of {len(dgt)} province-years, and its total "
        "count matches DGT's 24-hour count of crashes with a death or serious injury to within "
        "one crash in every province-year. Its fatal count is "
        f"{_fmt_pct(ratio30.min(), 0)}–{_fmt_pct(ratio30.max(), 0)} of DGT's 30-day count. The "
        "file does not state its definition, but the counts show that it treats a crash as "
        "fatal when someone died within 24 hours, and every comparison with national figures "
        "uses that definition.</p>"
    )

    body += "<h2>Fields recorded unevenly</h2>"
    outcome_dependent = artefacts[artefacts.verdict == "outcome-dependent recording"]
    # The recording check runs on the original model's training rows (its training and
    # choice years), never on its test year.
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
    body += (
        f"<p>In the crashes of {checked}, the years the original Catalan model was trained "
        f"on, {_count_word(len(set(outcome_dependent.column)))} fields are left blank or marked "
        "“not specified” much more often in non-fatal crashes than in fatal ones (the "
        f"recording check flags them). The {_field_phrase(worst.column)}, for example, is "
        f"{_blank_label(worst.level)} in {_fmt_pct(worst.rate_serious)} of non-fatal crashes "
        f"and {_fmt_pct(worst.rate_fatal)} of fatal ones. The file gives no reason, but the "
        "blank itself carries information about the outcome, so no published model uses these "
        "fields. "
        "On conventional roads the owner is recorded unevenly the other way: a blank owner is "
        "far commoner on "
        "fatal records, so the "
        '<a href="severity-models.html">crash-severity calculator</a> leaves out the crashes '
        "whose owner is blank or “other”. Otherwise the file is "
        "consistent: it has no "
        "duplicated rows, and every severity label agrees with the deaths and injuries recorded "
        f"on the same row. The repository's {DATA_QUALITY} documents these checks.</p>"
    )
    body += limitation(
        "The file describes crashes only. It has no records of the people involved and no "
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
        method=("data.html#records", "recorded crashes and severity"),
    )
    return render_page(
        "catalonia",
        f"Serious and fatal crashes in Catalonia, {period}",
        "Crashes in which someone was killed or seriously injured in Catalonia, from the "
        "Servei Català de Trànsit's file: how often they were fatal, and in which "
        "circumstances.",
        body,
        scope=f"Catalonia · serious or fatal crashes · {period}",
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


def _person_group(dimension: str, label: str) -> str:
    if dimension == "age band":
        return "Age: " + ("75 and over" if label == "75+" else _dash(label))
    if dimension == "road user":
        # The same names the road-user figure uses.
        label = ROAD_USER_LABELS.get(label, label)
    return f"{dimension.capitalize()}: {label}"


def page_barcelona(captions: dict[str, str]) -> str:
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
    _check(
        labelled == n_people - int(outcomes.get("not_recorded", 0)) - natural,
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
    # the Guàrdia Urbana's own rear-end codes.
    codes = crashes[crashes.dimension == "crash-type code as recorded"].set_index("level")
    catching_up = codes.loc["Encalç"]
    own_codes = codes.loc[["Abast", "Abast multiple"]]
    own_n, own_events = int(own_codes.n.sum()), int(own_codes.events.sum())
    _check(
        catching_up.n + codes.loc["Abast", "n"] == rear_end.n
        and catching_up.events + codes.loc["Abast", "events"] == rear_end.events
        and catching_up.share > 10 * crash_all.share
        and own_events / own_n < crash_all.share,
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

    body = summary(
        f"The Guàrdia Urbana, Barcelona's city police, recorded {_fmt_int(n_crashes)} crashes "
        f"in {year}, with every person involved. Among the {_fmt_int(labelled)} people whose "
        f"outcome was recorded, {_fmt_pct(severe_people / labelled)} were seriously or fatally "
        "injured. Pedestrians and motorcyclists were much more often seriously or fatally "
        f"injured than car drivers: {_fmt_pct(pedestrian.share)} of pedestrians and "
        f"{_fmt_pct(motorcycle.share)} of motorcyclists, against {_fmt_int(car_driver.events)} "
        f"of {_fmt_int(car_driver.n)} car drivers ({_fmt_pct(car_driver.share, 2)}). These shares "
        "are conditional on appearing in a recorded crash, and they are not rates per journey "
        "or per kilometre."
    )
    natural_deaths = (
        f", and {_count_word(natural)} death{'s' if natural > 1 else ''} the police recorded "
        "as natural,"
        if natural
        else ""
    )
    not_recorded = int(outcomes.get("not_recorded", 0))
    body += (
        "<p>Unlike the Catalan file, the records include crashes without a serious injury and "
        f"people who were not hurt. The {_fmt_int(not_recorded)} people whose outcome was not "
        f"recorded{natural_deaths} are left out of the shares; counted as uninjured, they would "
        f"lower the overall share to {_fmt_pct(severe_people / (labelled + not_recorded))}. The "
        "crash, person, vehicle and cause tables are linked by a crash number but share no "
        "identifier with the Catalan file or DGT's records.</p>"
    )

    body += "<h2>Serious injury by road user, age and sex</h2>"
    body += figure(
        "bcn1_severity_by_road_user",
        "Dot chart of the share of people seriously or fatally injured, by road user, with 95% "
        "intervals; pedestrians have the highest share",
        captions,
    )
    body += (
        f"<p>The shares for {_join(rider_shares)} lie between those of car drivers and "
        "motorcyclists. By age, the share is highest among people aged 75 and over "
        f"({_fmt_pct(oldest.share)}); in every younger age band it lies between "
        f"{_fmt_pct(younger.share.min())} and {_fmt_pct(younger.share.max())}. Women and men "
        f"differ little ({_fmt_pct(female.share)} and {_fmt_pct(male.share)}).</p>"
    )
    body += figure(
        "bcn2_severity_by_age",
        "Dot chart of the share of people seriously or fatally injured, by age band, with 95% "
        "intervals; the share is highest at 75 and over",
        captions,
    )
    rows = people[people.dimension.isin(["road user", "age band", "sex"]) & (people.n >= MIN_N)]
    body += technical(
        "Serious or fatal injury by road user, age and sex (counts and intervals)",
        table(
            pd.DataFrame(
                {
                    "Group": [
                        _person_group(d, label) for d, label in zip(rows.dimension, rows.label)
                    ],
                    "People": rows.n,
                    "Serious or fatal": rows.events,
                    "Share": rows.share,
                    "95% interval": [
                        _interval(lo, hi) for lo, hi in zip(rows.ci_low, rows.ci_high)
                    ],
                }
            ),
            f"Serious or fatal injury among people with a recorded outcome, Barcelona, {year} "
            f"(groups with at least {MIN_N} people).",
            {"People": "int", "Serious or fatal": "int", "Share": "pct"},
        ),
    )

    body += "<h2>Serious injury by type of crash</h2>"
    body += (
        f"<p>Of the {_fmt_int(n_crashes)} crashes the police attended, "
        f"{_fmt_pct(crash_all.share)} had at least one serious or fatal injury, more than the "
        "share of people because one seriously injured person is enough to place a crash in "
        f"that group. The police recorded no victim in {_fmt_int(no_victim)} of them; among the "
        f"crashes with a victim the share is {_fmt_pct(injury_share)}. Among crash types with at "
        f"least {MIN_N} "
        "crashes, the share is highest when a pedestrian was struck: "
        f"{_fmt_pct(struck.share)}, more than twice the average. Rear-end collisions had a "
        f"serious or fatal injury in {_fmt_pct(rear_end.share)} of {_fmt_int(rear_end.n)} "
        "crashes. They include the crashes coded with the Catalan file's term for a rear-end "
        f"collision: {_fmt_int(catching_up.events)} of those {_fmt_int(catching_up.n)} crashes "
        f"had a serious or fatal injury, against {_fmt_int(own_events)} of the "
        f"{_fmt_int(own_n)} under the Guàrdia Urbana's own rear-end codes. The term is used "
        "when a crash is serious, so it records the outcome rather than a kind of crash, and "
        "the site counts it with the other rear-end collisions. A model of these crashes "
        "ranked them no better than a table of shares by accident type; both were fitted on the "
        "crash type as recorded, the term above included "
        '(<a href="severity-models.html">predictive models</a>).</p>'
    )
    body += figure(
        "bcn4_crash_severity_by_type",
        "Dot chart of the share of crashes with a serious or fatal injury, by crash type, with "
        "95% intervals",
        captions,
    )

    body += "<h2>Causes recorded by the police</h2>"
    body += (
        "<p>For most crashes the Guàrdia Urbana records one or more causes or contributing "
        "factors, such as lack of attention, alcohol or the state of the road. No driver cause "
        f"is recorded for {_fmt_int(driver_status.get('blank', 0))} crashes and only “not "
        f"determined” for {_fmt_int(driver_status.get('not_determined', 0))}; contributing "
        f"factors are recorded for {_fmt_int(mediate_status.get('recorded', 0))}. They are "
        "classifications the police make after attending the crash, a crash can have several, "
        "and they are not causal estimates produced by this study. They are also recorded for "
        "the crash as a whole: no key links a cause to the driver or vehicle concerned, so a "
        "crash with alcohol recorded cannot be tied to the person who had been drinking, or to "
        "the person who was hurt.</p>"
        "<p>The cause recorded most often is "
        f"{esc(_cause(most_recorded.label)[0])} ({_fmt_int(most_recorded.n)} crashes). Among "
        f"causes recorded in at least {MIN_N} crashes, a serious or fatal injury was most often "
        f"recorded where {esc(_cause(most_serious.label)[0])} was: "
        f"{_fmt_pct(most_serious.share)} of {_fmt_int(most_serious.n)} crashes (95% interval "
        f"{_interval(most_serious.ci_low, most_serious.ci_high)}), against "
        f"{_fmt_pct(crash_all.share)} of all crashes. Alcohol was recorded in "
        f"{_fmt_int(alc_night.n)} crashes, {_fmt_pct(alc_night.share)} of them at night, against "
        f"{_fmt_pct(other_night.share)} of the other crashes.</p>"
    )
    body += table(
        _cause_rows(causes),
        f"Crashes by recorded cause and the share with a serious or fatal injury, Barcelona, "
        f"{year} (causes recorded in at least {MIN_N} crashes; a crash can have several).",
        {"Crashes": "int", "Serious or fatal": "int", "Share": "pct"},
    )
    body += limitation("The records cover one year in one city, so they show no change over time.")
    body += downloads(
        [
            ("bcn_person_severity_share", "injury by person group"),
            ("bcn_people_by_severity", "people by recorded outcome"),
            ("bcn_crash_severity_share", "crashes with a serious or fatal injury"),
            ("bcn_frequency", "crashes by month, hour, weekday and district"),
            ("bcn_cause_profiles", "alcohol- and speed-recorded crashes"),
            ("mq_bcn_structure", "record counts by table"),
        ],
        method=("data.html#records", "recorded crashes and police-recorded causes"),
    )
    return render_page(
        "barcelona",
        f"Crashes and casualties in Barcelona, {year}",
        f"Every crash Barcelona's city police attended in {year}, with each person involved: "
        "who was seriously hurt, in which kinds of crash, and the causes the police recorded.",
        body,
        scope=f"Barcelona · police-attended crashes · {year}",
    )
