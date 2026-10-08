"""Methodology: definitions, rates and denominators, crash records, models, checks, the
assumptions tested, reproduction and reuse.

What each source is, what it covers and what it cannot show is on the sources page; this page
says how the results are produced from them.
"""

from __future__ import annotations

import inspect
import re

import pandas as pd

from dgt_stats import codes, edm2018, features, io_exposure, risk_trends, severity_model
from dgt_stats import figures as figure_data
from dgt_stats.derive import ROAD_GROUP_BY_TYPE
from dgt_stats.exposure_risk import national as national_rates
from dgt_stats.microdata.ml import modelling, recording, rules
from dgt_stats.microdata.validation import dgt_audit, transport
from dgt_stats.paths import RAW_DATA_DIR, TABLES_DIR
from dgt_stats.site.components import (
    ALL_PAGES,
    DOCS_URL,
    REPO_URL,
    _fmt_dec,
    _fmt_int,
    _fmt_pct,
    _join,
    downloads,
    facts,
    figure,
    read_table,
    render_page,
    summary,
    table,
)
from dgt_stats.site.long_run import _where
from dgt_stats.site.numbers import (
    FAIL,
    INTERMEDIATE,
    PASS,
    _driver_numbers,
    _older_numbers,
    joint_interval,
)
from dgt_stats.site.regional_common import _year_label

TITLES = dict(ALL_PAGES)
# Harmonised variables, in words.
FIELD_LABELS = {"road_class": "road type", "hour_band": "hour"}
# A circumstance field unrecorded in more than this share of crashes counts as often unrecorded.
MOSTLY_BLANK = 0.3
# A field above that share by less than this is named as only just above it.
JUST_ABOVE = 0.01
# Two shares at a junction closer than this are "close" (the corrected Catalan share and the rest
# of Spain's, as on the severity page).
CLOSE_SHARE = 0.02
# A field recorded in more than this share of crashes in every year counts as always recorded.
ALWAYS_RECORDED = 0.99
# Fields of DGT's records that describe every crash, named in the missing-values figure's text.
CORE_FIELDS = {
    "DIA_SEMANA": "day",
    "ZONA": "zone",
    "TIPO_VIA": "road type",
    "TIPO_ACCIDENTE": "crash type",
}
# The step in recorded urban injury crashes that inflates the crash dispersion ends this many
# years after the scatter window opens (as on the trends page).
URBAN_STEP_YEARS = 3
NUMBER_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
}


def _fail(claim: str) -> None:
    raise ValueError(f"methodology page: the tables no longer support: {claim}")


def _require(checks: dict[str, bool]) -> None:
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        _fail(", ".join(failed))


def _span(years: pd.Series) -> str:
    return f"{int(years.min())}–{int(years.max())}"


def _runs(years) -> str:
    """Years as runs: '2016–2020 and 2022'."""
    runs: list[list[int]] = []
    for year in sorted({int(y) for y in years}):
        if runs and year == runs[-1][-1] + 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    return _join([f"{r[0]}–{r[-1]}" if len(r) > 1 else str(r[0]) for r in runs])


def _words(number: int) -> str:
    """A count under ten in words, as in running prose."""
    return NUMBER_WORDS.get(number, _fmt_int(number))


def _manifest() -> pd.DataFrame:
    return pd.read_csv(RAW_DATA_DIR / "manifest.csv")


def _path_year(prefix: str, contains: str) -> int:
    """The year in the name of the one raw file under ``prefix`` whose path contains ``contains``."""
    paths = _manifest().path
    found = paths[paths.str.startswith(prefix) & paths.str.contains(contains, regex=False)]
    years = {int(y) for path in found for y in re.findall(r"(?<!\d)(\d{4})(?!\d)", path)}
    _require({f"one year names the raw file {prefix}…{contains}": len(years) == 1})
    return years.pop()


# ----------------------------------------------------------------------------- definitions
def _definitions() -> str:
    semantics = read_table("mq_bcn_count_semantics").set_index("check").value
    no_victim = int(semantics["blank cells in Numero_victimes"])
    _require({"some Barcelona crashes record no victim": no_victim > 0})
    victims = read_table("validation")
    victims = victims[victims.check == "victim_total"].pivot_table(
        index="year", columns="unit", values="actual"
    )
    later = 1 - victims.deaths_24h.sum() / victims.deaths_30d.sum()
    _require({"some deaths within 30 days occur after the first day": later > 0})
    items = [
        (
            "Injury crash",
            "A crash on a public road in which at least one person is killed or injured. DGT's "
            "national records and series count only injury crashes, and a slight injury there "
            "needs medical care. Barcelona's crash table also holds crashes the Guàrdia Urbana "
            f"attended in which nobody was hurt ({_fmt_int(no_victim)} in its year), and it counts "
            "people who refused medical care as slightly injured.",
        ),
        (
            "Death",
            "A death within 30 days of the crash, DGT's consolidated definition, used for the "
            "national series and rates. The Catalan file counts deaths within 24 hours; "
            "Barcelona's records keep deaths within 24 hours apart from later deaths, and the "
            "analysis of people counts both. In DGT's national records for "
            f"{_span(victims.index.to_series())}, {_fmt_pct(later)} of the deaths within 30 days "
            "occurred after the first 24 hours, so the two definitions are never combined.",
        ),
        (
            "Serious injury",
            "Admission to hospital for more than 24 hours; any other injury is slight. The "
            "Catalan file and Barcelona's crash table classify at 24 hours, so a person who "
            "died later counts there as seriously injured. The Catalan file holds crashes with "
            "a death or serious injury (serious and fatal crashes); those in which nobody died "
            "within 24 hours are non-fatal.",
        ),
        (
            "Fatal share",
            "Among the serious and fatal crashes in Catalonia, the share in which someone died "
            "within 24 hours. For Barcelona the site gives a serious-or-fatal share instead: of "
            "the people whose outcome was recorded, or of the crashes the police attended, the "
            "share with a serious or fatal injury.",
        ),
        (
            "Zone",
            "DGT's grouping of roads into interurban roads, and urban streets and crossings. The "
            "Catalan file also distinguishes through-town roads, which count as urban in "
            "comparisons with DGT's records.",
        ),
        ("Driver involved", "The driver of a vehicle in an injury crash, injured or not."),
        (
            "Licence holder",
            "A holder of any driving permit in DGT's census; the B permit is the car licence.",
        ),
        (
            "Crash frequency",
            "How often a group appears in injury crashes relative to a measure of its exposure, "
            "such as kilometres driven, fuel sold or licence holders.",
        ),
        (
            "Severity",
            "How serious the outcome is once a crash, or a person in one, is already in the "
            "records: deaths per injury crash, deaths per driver involved, the fatal share of "
            "serious crashes. A death rate per unit of exposure is crash frequency multiplied "
            "by severity.",
        ),
        (
            "Recorded factor",
            "A circumstance the police record about a crash, such as alcohol, inappropriate speed "
            "or distraction (Barcelona's records call them causes). It is a police judgement, "
            "not a finding by this study that the circumstance caused the crash.",
        ),
        (
            "Association",
            "A statistical relationship in observed records. Every comparison on the site "
            "between an outcome and a circumstance is an association; none is an estimate of a "
            "causal effect, which would need a design that these records do not provide.",
        ),
        (
            "Predictive model",
            "A model judged only on records not used to fit it, and kept only if it ranks those "
            "records better than a simple table of the same data.",
        ),
    ]
    return '<h2 id="definitions">Definitions</h2>' + facts(items, "Definitions")


# ----------------------------------------------------------------------------- rates
def _rates() -> str:
    scatter = read_table("risk_dispersion").set_index("outcome")
    _require(
        {
            "deaths, admissions and crashes scatter more than Poisson chance": all(
                float(scatter.loc[key, "dispersion"]) > 1
                for key in ("deaths_30d", "hospitalised_30d", "crashes")
            ),
        }
    )
    vehicles = risk_trends.MOTOR_VEHICLES
    denominators = [
        (
            "Per resident",
            "The burden of road deaths on a population, most of whom were not travelling at "
            "the time. A rate per resident falls when people travel less.",
        ),
        (
            "Per licence holder",
            f"Counts only drivers: on the trend pages the drivers of {vehicles} killed or "
            "admitted to hospital, and on the drivers page car drivers involved in injury "
            "crashes, injured or not.",
        ),
        ("Per registered vehicle", f"Counts only the occupants of {vehicles}."),
        (
            "Per tonne of road fuel",
            "Tonnes of petrol and diesel sold: the only annual measure of traffic that covers "
            "every road.",
        ),
        (
            "Per vehicle-kilometre",
            "The Ministerio de Transportes' measurements on State, regional and provincial "
            "interurban roads, and DGT's estimates by vehicle type from inspection odometer "
            "readings. Kilometres by driver age are estimated from the EMEF working-day "
            "survey's age profile, applied to Spain's population and scaled to DGT's car "
            "kilometres.",
        ),
        (
            "Per driver involved",
            "Deaths among the drivers involved in injury crashes: how often involvement ends in "
            "death. It needs no measure of travel.",
        ),
    ]
    trends = f'<a href="trends.html">{TITLES["trends"]}</a>'
    assumptions = '<a href="#assumptions-tested">assumptions tested</a>'
    return (
        '<h2 id="rates">Rates, denominators and intervals</h2>'
        "<p>Each rate pairs a count with a denominator meant to contain it:</p>"
        + facts(denominators, "Denominators")
        + "<p>Pedestrians and cyclists hold no licence for the trip in which they are hurt and "
        "travel in no registered vehicle, so they are counted against residents and road fuel "
        "only. Road fuel stands in for the kilometres driven on all roads, and the kilometres "
        "by driver age carry one region's survey to Spain; neither can be tested for Spain as "
        f"a whole ({assumptions}). Some rates do not fully meet the rule, and each page says "
        "so: rates per resident count visitors' deaths, rates per licence holder (by sex, and "
        "on Since 2019) count unlicensed and foreign drivers, rates per registered vehicle and "
        "by vehicle type count foreign vehicles, and interurban deaths are compared with "
        "national road fuel only as a check.</p>"
        "<h3>How often crashes happen and how deadly they are</h3>"
        "<p>A death rate measured against traffic combines two quantities that can move "
        "separately: deaths per kilometre (or per tonne of fuel) equal injury crashes per "
        "kilometre multiplied by deaths per injury crash. The split depends on how completely "
        "slight-injury crashes are recorded: if fewer are recorded, crashes per kilometre fall "
        "and deaths per crash rise by the same factor, and their product does not move. "
        "Deaths are counted completely, so the death rate is the firmer measure and its split "
        f'the more fragile reading. The split is applied on <a href="long-run.html">'
        f'{TITLES["long-run"]}</a>, <a href="drivers.html">{TITLES["drivers"]}</a> and '
        f'<a href="vehicles.html">{TITLES["vehicles"]}</a>.</p>'
        "<h3>Intervals and ordinary year-to-year variation</h3>"
        "<p>Rates carry 95% intervals that treat counts as Poisson with a known denominator; "
        "ratios of two rates carry log-normal intervals. Spain's annual counts scatter around "
        "their trend more than Poisson chance allows, so changes against "
        f"{risk_trends.BASE_YEAR} are read against intervals widened to span an ordinary "
        f"year's variation ({trends}; {assumptions}).</p>"
    )


# ----------------------------------------------------------------------------- records
def _code_list(numbers: list[int]) -> str:
    """Codes as runs: '7, 8 and 10–14'."""
    runs: list[list[int]] = []
    for number in sorted(numbers):
        if runs and number == runs[-1][-1] + 1:
            runs[-1].append(number)
        else:
            runs.append([number])
    return _join([f"{r[0]}–{r[-1]}" if len(r) > 2 else ", ".join(map(str, r)) for r in runs])


def _pct_range(values: pd.Series) -> str:
    """'94%', or '92%–95%' when the values round apart."""
    low, high = _fmt_pct(values.min(), 0), _fmt_pct(values.max(), 0)
    return low if low == high else f"{low}–{high}"


def _coding_breaks() -> str:
    other = read_table("q2_other_road_by_period")
    earlier, later = other.iloc[0], other.iloc[-1]
    earlier_years = [int(year) for year in re.findall(r"\d{4}", str(earlier.period))]
    earlier_count = earlier_years[-1] - earlier_years[0] + 1
    coding = read_table("gen_coding_by_region").set_index(["region", "year"]).sort_index()
    cat, rest = coding.loc["Catalonia"], coding.loc["Spain outside Catalonia"]
    switch = int(cat[cat.road_type_5_dual_carriageway.eq(0)].index.min())
    cat_before = cat.loc[switch - 1]
    rest_dual = rest.road_type_5_dual_carriageway
    other_year = int(later.period)
    cat_other = int(cat.loc[other_year, "road_type_14_other"])
    all_other = cat_other + int(rest.loc[other_year, "road_type_14_other"])
    # The "other" road group of derive.py, and its last code, labelled "other" itself.
    other_codes = sorted(code for code, group in ROAD_GROUP_BY_TYPE.items() if group == "other")
    road_types = codes.labels_for("TIPO_VIA")
    _require(
        {
            "most of the later 'other' crashes are on urban streets": float(later.street_share)
            > 0.5
            > float(earlier.street_share),
            "far more urban-street crashes are coded 'other' in the later year": float(
                later.street_crashes
            )
            > 2 * float(earlier.street_crashes) / earlier_count,
            "the later road-type period is a single year": str(later.period).isdigit(),
            "the group's last code is DGT's 'other' and its first two service and slip roads": [
                road_types.get(str(code)) for code in (*other_codes[:2], other_codes[-1])
            ]
            == ["Vía de servicio", "Ramal de enlace", "Otro"]
            and any("ciclista" in road_types.get(str(code), "") for code in other_codes),
            "most of the group's crashes in the later year carry code 14": all_other
            > 0.5 * float(later.crashes),
            "until the switch the Catalan records use the dual-carriageway code for conventional "
            "roads": bool(
                (
                    cat.loc[: switch - 1].road_type_6_single_carriageway
                    < 0.01 * cat.loc[: switch - 1].road_type_5_dual_carriageway
                ).all()
            )
            and bool((cat.loc[switch:].road_type_5_dual_carriageway == 0).all()),
            "elsewhere the dual-carriageway code holds steady": float(
                rest_dual.max() / rest_dual.min()
            )
            < 1.5,
            "the later code-14 crashes are mostly Catalan": cat_other > 0.75 * all_other,
        }
    )
    # The junction flag, by province and year, from the DGT microdata audit.
    junctions = read_table("dgt_audit_junction_coding")
    inverted = junctions[junctions.junction_flag_inverted.astype(bool)]
    flip = int(inverted.year.min())
    catalan_rows = junctions.catalan.astype(bool)
    totals = [
        "crashes",
        "at_junction",
        "at_junction_type_not_specified",
        "away_from_junction",
        "away_with_junction_type",
    ]
    cat_j = junctions[catalan_rows].groupby("year")[totals].sum()
    rest_j = junctions[~catalan_rows].groupby("year")[totals].sum()
    cat_share = cat_j.at_junction / cat_j.crashes
    rest_share = rest_j.at_junction / rest_j.crashes
    blank_at = cat_j.at_junction_type_not_specified / cat_j.at_junction
    typed_away = cat_j.away_with_junction_type / cat_j.away_from_junction
    after_years = [int(year) for year in cat_share.loc[flip:].index]
    matched = dgt_audit.catalan_junction_years(junctions)
    flipped = matched[matched.junction_flag_inverted.astype(bool)]
    compared = flipped.iloc[0]
    # The years whose Catalan records count only crashes within a junction at one (2021), and the
    # earlier years, which count those within 50 m of one too, as the Catalan file's codes show.
    narrow = matched[matched.dgt_at_junction_matches.eq("within a junction")]
    narrow_years = [int(year) for year in narrow.year]
    wider = matched[~matched.junction_flag_inverted.astype(bool) & ~matched.year.isin(narrow_years)]
    before = [year for year in cat_share.loc[: flip - 1].index if int(year) not in narrow_years]
    # How the association analysis reads those province-years (``features.junction_codes``).
    read = read_table("q3_junction_coding").set_index(["region", "year"])
    read_cat = read.loc["Catalonia"]
    read_rest = read.loc["rest of Spain"]
    near = read_cat.near_junction_fields
    near_others = near.loc[: flip - 1].drop(index=narrow_years)
    narrow_with_near = (read_cat.flagged_at + near) / read_cat.crashes
    _require(
        {
            "the junction flag is inverted in the four Catalan provinces only, every year from "
            "the break": set(inverted.province) == set(junctions[catalan_rows].province)
            and set(inverted.year) == set(after_years)
            and len(inverted) == junctions[catalan_rows].province.nunique() * len(after_years),
            "the Catalan share coded at a junction jumps at the break, and elsewhere it stays "
            "put": float(cat_share.loc[flip:].min()) > float(cat_share.loc[: flip - 1].max()) + 0.1
            and float(rest_share.max() - rest_share.min()) < 0.03,
            "from the break the Catalan crashes coded at a junction carry no junction type, and "
            "most coded away from one carry one": float(blank_at.loc[flip:].min()) > 0.9
            and float(typed_away.loc[flip:].min()) > 0.5,
            "elsewhere a junction type away from a junction is rare": float(
                (rest_j.away_with_junction_type / rest_j.away_from_junction).max()
            )
            < 0.05,
            "the association analysis reads the flag the other way round in exactly the inverted "
            "province-years": int(read.recoded.sum()) == int(inverted.crashes.sum())
            and int(read.crashes_in_inverted_province_years.sum()) == int(inverted.crashes.sum())
            and [int(y) for y in read_cat.index[read_cat.recoded > 0]] == after_years,
            "read that way, the Catalan share at a junction is close to the rest of Spain's in "
            "the same years": float(
                (
                    read_cat.loc[after_years].share_at_junction
                    - read_rest.loc[after_years].share_at_junction
                )
                .abs()
                .max()
            )
            < CLOSE_SHARE,
            "in one earlier year DGT's Catalan junction count matches the Catalan file's crashes "
            "within a junction, in the others those within or near one": len(narrow_years) == 1
            and not wider.empty
            and bool((wider.dgt_at_junction_matches == "within or near a junction").all()),
            "that year more Catalan crashes coded away from a junction carry junction fields than "
            "in all the other years before the break together": float(near.loc[narrow_years].min())
            > float(near_others.sum()),
            "the share range named for the earlier years leaves that year out, and the year lies "
            "below it": float(cat_share.loc[narrow_years].max())
            < float(cat_share.loc[before].min()),
            "in the inverted years DGT's junction crashes are the Catalan file's crashes between "
            "junctions, and before them never": not flipped.empty
            and bool((flipped.dgt_at_junction_matches == "between junctions").all())
            and bool(
                (
                    matched[~matched.junction_flag_inverted.astype(bool)].dgt_at_junction_matches
                    != "between junctions"
                ).all()
            ),
        }
    )
    severity = f'<a href="severity.html">{TITLES["severity"]}</a>'
    return (
        '<h3 id="coding-breaks">Coding breaks in DGT\'s records</h3>'
        "<p>Four changes in DGT's coding affect series by road type and junction, and all four "
        "come from the records for the four Catalan provinces. Until "
        f"{switch - 1} those records code almost every crash on a conventional road as a "
        "conventional road with a dual carriageway "
        f"({_fmt_int(cat_before.road_type_5_dual_carriageway)} such crashes in {switch - 1}, "
        f"{_fmt_int(cat_before.road_type_6_single_carriageway)} on single carriageways); from "
        f"{switch} they use the single-carriageway code instead. Elsewhere the dual-carriageway "
        f"code holds between {_fmt_int(rest_dual.min())} and {_fmt_int(rest_dual.max())} crashes "
        f"a year. In {later.period} many crashes on urban streets begin to be coded in the "
        f"“other” road group (codes {_code_list(other_codes)}, service roads, slip roads, cycle "
        "paths and other minor roads): "
        f"{_fmt_pct(later.street_share, 0)} of that year's crashes in the group are on urban "
        f"streets, against {_fmt_pct(earlier.street_share, 0)} in "
        f"{str(earlier.period).replace('-', '–')}. Most of them carry code {other_codes[-1]}, "
        f"“other” itself, and {_fmt_int(cat_other)} of the {_fmt_int(all_other)} crashes with "
        f"that code in {later.period} are Catalan. From {flip} the same records code the junction "
        "flag the wrong way round. The share of their crashes coded at a junction goes from "
        f"between {_fmt_pct(cat_share.loc[before].min(), 0)} and "
        f"{_fmt_pct(cat_share.loc[before].max(), 0)} a year in {cat_share.index.min()}–"
        f"{flip - 1} ("
        + _join([f"{_fmt_pct(cat_share.loc[y], 0)} in {y}" for y in narrow_years])
        + ", under the narrower definition below) to "
        + _join([f"{_fmt_pct(cat_share.loc[y], 0)} in {y}" for y in after_years])
        + ", while elsewhere it stays between "
        f"{_fmt_pct(rest_share.min(), 0)} and {_fmt_pct(rest_share.max(), 0)}. From {flip}, "
        "their crashes coded at a junction carry no junction type (“not specified”) in "
        + (
            "every case"
            if float(blank_at.loc[flip:].min()) == 1
            else f"{_pct_range(blank_at.loc[flip:])} of cases"
        )
        + f", and {_pct_range(typed_away.loc[flip:])} "
        "of those coded away from a junction carry one, a field the rest of Spain leaves empty "
        "away from a junction. The Servei Català de Trànsit's file holds the same crashes with "
        f"a death or serious injury: in {int(compared.year)} DGT codes "
        f"{_fmt_pct(compared.dgt_share_at_junction)} of the Catalan ones at a junction, and the "
        f"Catalan file places {_fmt_pct(compared.cat_share_between_junctions)} of them between "
        "junctions. In "
        + _join([str(y) for y in narrow_years])
        + " the records use a narrower definition of a junction: DGT's count of these Catalan "
        "crashes at a junction matches the Catalan file's crashes within a junction, where in "
        + _runs(wider.year)
        + " it matches those within or within "
        + f"{dgt_audit.NEAR_JUNCTION_METRES} metres of one. That year "
        + _join([_fmt_int(near.loc[y]) for y in narrow_years])
        + " Catalan crashes coded away from a junction carry a junction type or a right-of-way "
        f"flag, against {_fmt_int(near_others.sum())} in all the other years before {flip}; "
        "counted at a junction, they bring that year's share to "
        + _join([_fmt_pct(narrow_with_near.loc[y], 0) for y in narrow_years])
        + ". Road-type series are therefore read year by year and alongside zone, the "
        "two kinds of conventional road form one group, and no road-type trend is drawn. "
        "Comparisons of Catalonia with the rest of Spain group every conventional road together "
        'for the same reason (<a href="validation.html">External validation</a>). Junction '
        f"shares as published are not compared across {flip}. The association of junctions "
        "with fatal outcomes reads the flag the other way round in those province-years, which "
        "puts the Catalan share at a junction at "
        + _join(
            [f"{_fmt_pct(read_cat.loc[y, 'share_at_junction'], 0)} in {y}" for y in after_years]
        )
        + ", against "
        + _pct_range(read_rest.loc[after_years].share_at_junction)
        + f" elsewhere in Spain in the same years ({severity}).</p>"
        + _presence_breaks()
    )


def _presence_breaks() -> str:
    """The fog and strong-wind fields where a province's records code them another way, from the
    DGT microdata audit's presence table."""
    presence = read_table("dgt_audit_presence_coding")
    breaks = dgt_audit.presence_breaks(presence)
    if breaks.empty:
        return ""
    fog = breaks[breaks.field.eq("CONDICION_NIEBLA")]
    wind = breaks[breaks.field.eq("CONDICION_VIENTO")]
    flags = [f"{field}_coding_break" for field in dgt_audit.PRESENCE_NAMES]
    others = presence[~presence[flags].astype(bool).any(axis=1)]
    _require({"one province's records code fog their own way": len(fog) == 1})
    fog_province = fog.iloc[0]
    fog_years = list(fog_province.years)
    own = presence[presence.province.eq(fog_province.province)].set_index("year")
    own_before = own.loc[own.index < min(fog_years)]
    overlap = own.loc[fog_years].dropna(subset=["cat_file_severe_crashes"])
    catalan_years = [int(y) for y in overlap.index]
    unread = {
        str(spec["source"])
        for spec in features.PREDICTORS.values()
        if str(spec["source"]) in dgt_audit.PRESENCE_NAMES
    }
    calculator_source = inspect.getsource(severity_model)
    _require(
        {
            "the presence fields are fog and strong wind": set(dgt_audit.PRESENCE_NAMES)
            == {c for c in dgt_audit.CANDIDATES if dgt_audit.presence_field(c)},
            "one province codes fog its own way, every year from its break to the last": len(fog)
            == 1
            and fog_years == list(range(min(fog_years), int(presence.year.max()) + 1))
            and not own_before.empty,
            "before the break that province records fog in under 1% of crashes": float(
                own_before.CONDICION_NIEBLA_share.max()
            )
            < 0.01,
            "the Catalan file records fog in the same crashes in every year both hold": len(
                catalan_years
            )
            > 0
            and bool((overlap.severe_CONDICION_NIEBLA_recorded == overlap.cat_file_fog).all()),
            "neither field enters the national association analysis or the calculator": not unread
            and not any(
                field in calculator_source for field in ("D_BOIRA", "D_VENT", "NIEBLA", "VIENTO")
            ),
        }
    )
    groups: dict[tuple, list[str]] = {}
    for row in wind.itertuples():
        key = (tuple(row.years), _fmt_pct(row.share_low, 0), _fmt_pct(row.share_high, 0))
        groups.setdefault(key, []).append(str(row.province_name))
    wind_text = _join(
        [
            (
                f"in every crash of {_join(names)} in {_runs(years)}"
                if low == high == _fmt_pct(1, 0)
                else f"in {low}"
                + ("" if low == high else f" to {high}")
                + f" of {_join(names)}'s crashes in {_runs(years)}"
            )
            for (years, low, high), names in groups.items()
        ]
    )
    return (
        "<p>The fog and strong-wind fields are filled in only when there was fog or strong "
        "wind, so a blank in them is read as none, except where a province's records give the "
        f"condition to more than {_fmt_pct(dgt_audit.MAX_PRESENCE_SHARE, 0)} of their crashes; "
        "elsewhere fog or strong wind is recorded in at most "
        f"{_fmt_pct(max(float(others[f'{c}_share'].max()) for c in dgt_audit.PRESENCE_NAMES))} "
        f"of a province-year's crashes. From {min(fog_years)} the records for the province of "
        f"{fog_province.province_name} code fog in {_fmt_pct(fog_province.share_low, 0)} to "
        f"{_fmt_pct(fog_province.share_high, 0)} of crashes a year, against "
        f"{_fmt_pct(own_before.CONDICION_NIEBLA_share.max())} in "
        + _runs(own_before.index)
        + ", and the Servei Català de Trànsit's file records fog in the same number of the "
        "province's crashes with a death or serious injury in each year of "
        f"{catalan_years[0]}–{catalan_years[-1]}. "
        + (f"Strong wind is recorded {wind_text}. " if not wind.empty else "")
        + "In those province-years the field is coded another way: neither a value nor a "
        "blank says whether there was fog or strong wind. Neither field enters the "
        "national association analysis or the calculator.</p>"
    )


def _missingness_alt(missing: pd.DataFrame, applicability: pd.DataFrame) -> str:
    """The missing-values figure's alt text: what it shows, from the shares it draws."""
    years = missing.year
    shown = figure_data.recorded_where_applicable(missing, applicability)
    names = figure_data.MISSINGNESS_FIELDS
    core = shown.loc[[names[field] for field in CORE_FIELDS]]
    priority = shown.loc[shown.index.str.startswith("Right of way")].iloc[0]
    junction_type = shown.loc[names["NUDO_INFO"]]
    # The years whose Catalan junction flag is inverted, read the other way round in the figure,
    # checked not to leave the junction fields recorded less often than in every other year.
    flipped = figure_data.inverted_junction_years(shown, read_table("dgt_audit_junction_coding"))
    _require(
        {
            "the fields that describe every crash are recorded in nearly every crash": bool(
                (core > ALWAYS_RECORDED).all().all()
            ),
            "every year the junction type is recorded in nine crashes at a junction in ten and "
            "the right-of-way flags in most": bool(
                (junction_type > 0.9).all() and (priority > 0.5).all()
            ),
            "the pavement and island fields are recorded in most crashes they apply to": bool(
                (shown.loc[[names["ACERA"], names["ISLA"]]] > 0.5).all().all()
            ),
        }
    )
    return (
        "Share of DGT crash records with a value recorded, among the crashes each field applies "
        f"to, by field and year, {_span(years)}, from the most completely recorded field down. "
        f"The {_join(list(CORE_FIELDS.values()))} are recorded in nearly every crash. Among "
        "crashes at a junction, the junction type is recorded in "
        f"{_pct_range(junction_type)} and the right-of-way flags in "
        f"{_pct_range(priority)} a year, with the junction flag of the Catalan provinces' "
        f"records for {_join([str(y) for y in flipped])} read the other way round. "
        "Fields that apply only to some crashes, such as the pavement and island fields, are "
        "recorded in most of the crashes they apply to."
    )


def _records(captions: dict[str, str]) -> str:
    regional = read_table("dgt_audit_regional")
    artefacts = read_table("ml_recording_artefacts")
    semantics = read_table("mq_bcn_count_semantics").set_index("check").value
    missing = read_table("missingness_by_year")
    applicability = read_table("missingness_where_applicable")
    limit = recording.RATIO_LIMIT
    catalan = artefacts[artefacts.verdict == "outcome-dependent recording"]
    catalogue = read_table("ml_feature_catalogue")
    catalogue = catalogue[catalogue.feature_table == "catalonia_crash_severity"]
    in_main = catalogue[catalogue.feature_sets.str.contains("context")].column
    calculator_source = inspect.getsource(severity_model)
    explicit_zeros = int(semantics.filter(like="explicit zero").iloc[0])
    adds_up = int(semantics["crashes where victims = deaths + serious + minor (blank read as 0)"])
    _require(
        {
            "Barcelona's blank counts mean zero": explicit_zeros == 0
            and adds_up == int(semantics["crashes"]),
            "the outcome-dependent Catalan placeholders are rarer among fatal crashes": bool(
                (catalan.ratio_fatal_to_serious <= 1 / limit).all()
            )
            and not catalan.empty,
            "the outcome-dependent Catalan fields stay out of the original model": not set(
                catalan.column
            )
            & set(in_main),
            "the calculator reads none of the outcome-dependent Catalan fields": not any(
                re.search(rf"\b{re.escape(column)}\b", calculator_source)
                for column in set(catalan.column)
            ),
        }
    )
    levels, fields = len(catalan), catalan.column.nunique()
    # The right-of-way flags answer one question (who had priority) in 13 columns that are
    # unrecorded together, so they count as one question here.
    priority = regional.field.str.startswith("PRIORI_")
    questions = pd.concat(
        [
            regional[~priority].set_index("field").unrecorded_share,
            pd.Series({"right of way": regional[priority].unrecorded_share.max()}),
        ]
    )
    mostly_blank = int((questions > MOSTLY_BLANK).sum())
    closest = float(questions[questions > MOSTLY_BLANK].min())

    def overall(column: str, share: str) -> float:
        rows = missing[missing.column == column]
        return float((rows[share] * rows.rows).sum() / rows.rows.sum())

    audited = applicability.groupby("column")[["rows", "applies", "recorded"]].sum()
    pavement_na = float(1 - audited.loc["ACERA"].applies / audited.loc["ACERA"].rows)
    junction_type_na = float(1 - audited.loc["NUDO_INFO"].applies / audited.loc["NUDO_INFO"].rows)
    island_empty = overall("ISLA", "share_empty")
    # What the figure draws: for the fields the audit examines, the share recorded among the
    # crashes the audit's rule says they apply to; for the island field, the share recorded among
    # the crashes left once "not applicable" and the empty cell are set aside.
    shown = figure_data.recorded_where_applicable(missing, applicability)
    by_year = missing.set_index(["column", "year"])
    audited_by_year = applicability.set_index(["column", "year"])
    island_applies = 1 - by_year.loc["ISLA"].share_not_applicable - by_year.loc["ISLA"].share_empty
    names = figure_data.MISSINGNESS_FIELDS

    def audit_share(column: str) -> pd.Series:
        rows = audited_by_year.loc[column]
        return rows.recorded / rows.applies

    leaves_out_not_applicable = bool(
        all(
            (shown.loc[names[column]] - audit_share(column)).abs().max() < 1e-9
            for column in ("ACERA", "NUDO_INFO", "CONDICION_NIEBLA")
        )
        and (shown.loc[names["ISLA"]] - by_year.loc["ISLA"].share_observed / island_applies)
        .abs()
        .max()
        < 1e-9
    )
    applies = regional.set_index("field").applies_share
    _require(
        {
            "the audit reads blank fog and wind fields as no fog or wind, and only those": [
                field for field in regional.field if dgt_audit.presence_field(field)
            ]
            == ["CONDICION_NIEBLA", "CONDICION_VIENTO"],
            "the junction type and right-of-way flags apply to some crashes only": set(
                dgt_audit.JUNCTION_FIELDS
            )
            == {"NUDO_INFO", *codes.PRIORI_COLUMNS}
            and bool((applies.loc[list(dgt_audit.JUNCTION_FIELDS)] < 1).all()),
            "the right-of-way flags are unrecorded together": float(
                regional[priority].unrecorded_share.max()
                - regional[priority].unrecorded_share.min()
            )
            < 0.01,
            "unrecorded shares split into fields nearly always recorded and fields often not": 0
            < mostly_blank
            < len(questions) / 2,
            "the figure reads the audited fields by the audit's rule and leaves “not "
            "applicable” and the island's empty cells out of its shares, and its caption says "
            "so": leaves_out_not_applicable
            and all(
                phrase in captions.get("d1_missingness", "")
                for phrase in (
                    "998 (not applicable)",
                    "among the crashes the field applies to",
                    "in a crash recorded away from a junction",
                    "fog or strong wind field counts as recorded",
                    "the flag is read the other way round",
                )
            ),
            "the junction type does not apply to most crashes": junction_type_na > 0.5,
            "the audit's fog and wind fields are recorded in every crash": bool(
                (shown.loc[[names["CONDICION_NIEBLA"], names["CONDICION_VIENTO"]]] == 1).all().all()
            ),
            "the pavement field is mostly not applicable": pavement_na > 0.5,
            "DGT's dictionary defines an empty island field as not applicable": codes.load_dictionary()
            .get("ISLA", {})
            .get("", "")
            .lower()
            == "no aplica"
            and island_empty > 0.5,
        }
    )
    sources = f'<a href="sources.html">{TITLES["sources"]}</a>'
    return (
        '<h2 id="records">Reading police crash records</h2>'
        "<p>Crash records contain only the crashes the police recorded, and the Catalan file "
        "only those with a death or serious injury. A share computed from such records, such as "
        "the fatal share on interurban roads, measures how severe crashes were once they had "
        "happened and been recorded. It does not measure how often crashes happen or how "
        "dangerous a road is per kilometre travelled, because the records contain no measure of "
        "travel. The severity models share this limit: they predict a severe outcome only among "
        "crashes that were recorded.</p>"
        "<p>The recorded factors on the site are DGT's, such as speed, alcohol or "
        "distraction, the Catalan file's “influence” fields, and Barcelona's contributing "
        "factors and driver causes. A crash can carry several, and how completely they are "
        "recorded varies by year and with the severity of the crash.</p>"
        "<p>Missing values keep their own categories. “Not specified”, “not applicable”, a "
        "field's own “unknown” code and an empty cell are four different states, and none is "
        "read as zero or as “no”, except in the fog and strong-wind fields, which DGT fills in "
        "only when there was fog or strong wind, apart from a few province-years that code them "
        'another way (<a href="#coding-breaks">coding breaks</a>). The audit of DGT\'s records '
        "counts a field as "
        "unrecorded when it is “not specified”, “unknown” or empty in a crash it applies to: "
        "the junction type and the right-of-way flags, for instance, do not apply to a crash "
        "away from a junction. Of the "
        f"{_fmt_int(len(questions))} fields it examines (the "
        f"{_fmt_int(int(priority.sum()))} right-of-way flags counted as one), "
        f"{_words(mostly_blank)} are unrecorded in more than {_fmt_pct(MOSTLY_BLANK, 0)} of "
        "the crashes they apply to"
        + (
            f", one of them only just ({_fmt_pct(closest)})"
            if closest - MOSTLY_BLANK < JUST_ABOVE
            else ""
        )
        + "; how unevenly the provinces record them is set out under "
        f"{sources}. The "
        "figure reads the fields the audit examines by the same rule and leaves “not applicable” "
        "out of each field's share, so a field that applies only to some crashes is judged on "
        "the crashes it applies to: the pavement field is “not applicable” in "
        f"{_fmt_pct(pavement_na, 0)} of crashes, the junction type in "
        f"{_fmt_pct(junction_type_na, 0)} (those away from a junction), and the island field is "
        "empty, which DGT's dictionary defines as not applicable, in "
        f"{_fmt_pct(island_empty, 0)}. In the figure an empty fog or strong-wind field counts as "
        "recorded. In Barcelona's crash table a blank count means zero: no cell holds an explicit zero, and "
        "with blanks read as zero the victims add up in every crash.</p>"
        + figure("d1_missingness", _missingness_alt(missing, applicability), captions)
        + "<p>Recording can also depend on the outcome. Fatal crashes may be investigated more "
        "fully, so fields left unspecified in non-fatal crashes are more often filled in for "
        f"fatal ones. In the Catalan file, {_words(levels)} placeholder levels in "
        f"{_words(fields)} fields (“not specified” or an unexplained blank) are recorded at "
        f"least {_fmt_dec(limit)} times as often in non-fatal crashes as in fatal ones; these "
        "fields are left out of every published model. The road owner is the reverse case, "
        "blank far more often on fatal records, and the calculator leaves out the crashes it "
        f'affects (<a href="{DOCS_URL}/research/ML_MODEL_REVIEW.md">model review</a>).</p>'
        + _coding_breaks()
    )


# ----------------------------------------------------------------------------- models
def _models() -> str:
    split = read_table("ml_split_isolation").set_index("model")
    comparison = read_table("ml_rule_comparison").set_index("model")
    selected = read_table("ml_selected")
    primary = selected[selected.primary].set_index("model")
    common = read_table("ml_common_feature_validation")
    shared = read_table("ml_common_features")
    catalogue = read_table("ml_feature_catalogue")
    cat_checks = read_table("mq_cat_checks").set_index("check").value
    outward = read_table("ml_outward_path").set_index(["model", "stage"])
    bcn_year = _year_label(read_table("bcn_person_severity_share"))
    scores = read_table("sev_rolling_scores")
    choices = read_table("sev_choices")
    cells = scores[
        scores.subset.str.startswith("province and zone: ") & (scores.estimator == "calculator")
    ]
    pooled = scores[scores.subset.str.fullmatch(r"\d{4}-\d{4}")]
    rolling = _span(pd.Series([int(y) for y in re.findall(r"\d{4}", pooled.subset.iloc[0])]))
    pooled = pooled.set_index("estimator")
    calc, lookup = pooled.loc["calculator"], pooled.loc["road_x_crash_table"]
    gaps = read_table("sev_comparison").set_index(["estimator", "metric"])
    against = gaps.loc[("road_x_crash_table", "roc_auc_minus_calculator")]
    gain_low, gain_high = -float(against.high), -float(against.low)
    catalan_years = read_table("cat_frequency").year
    cat_years = re.findall(r"\d{4}", split.loc["catalonia_crash_severity", "design"])
    bcn_numbers = re.findall(r"\d+", split.loc["barcelona_person_severity", "design"])
    candidates = common[common.a_priori_status.isin(["exact", "defensible"])]
    used = candidates[candidates.enters_cross_source_tests.astype(bool)]
    dropped = candidates[~candidates.enters_cross_source_tests.astype(bool)]
    bcn_pair = shared[shared.pair.str.contains("Barcelona")]
    bcn_shared = bcn_pair[bcn_pair.enters_cross_source_tests.astype(bool)]
    mappable = bcn_pair.status.isin(["exact", "defensible"])
    catalan_last = int(catalan_years.max())
    main_sets = catalogue.feature_sets.str.contains("context")
    adds = comparison.model_adds_signal_over_table.astype(bool)
    low, high = modelling.CALIBRATION_SLOPE_RANGE
    tolerance = modelling.CALIBRATION_LARGE_TOLERANCE
    _require(
        {
            "the calculator's model beats its table by the rule": float(
                calc.roc_auc - lookup.roc_auc
            )
            >= rules.MIN_GAIN
            and gain_low > 0,
            "the calculator's estimates pass the calibration rule": low
            <= float(calc.calibration_slope)
            <= high
            and abs(float(calc.mean_predicted - calc.prevalence)) <= tolerance * calc.prevalence,
            "the original Catalan design names training, choice and test years": len(cat_years)
            == 5,
            "the Barcelona design names months and folds": len(bcn_numbers) == 5,
            "no crash or group straddles a split": bool(
                (split.shared_ids == 0).all() and (split.shared_groups == 0).all()
            ),
            "the Barcelona crash model does not beat its table": not bool(
                adds["barcelona_crash_severity"]
            ),
            "the Barcelona person-severity model is for ranking only": not bool(
                primary.loc["barcelona_person_severity", "probabilities_shown_as_estimates"]
            ),
            "the main models use only circumstances of the crash or person": bool(
                (catalogue[main_sets].status == "safe").all()
            ),
            "variables that encode the outcome are in no model": bool(
                (catalogue[catalogue.status == "direct_leakage"].feature_sets == "none").all()
            ),
            "some candidate variables fail the overlap check": not dropped.empty,
            "the Barcelona variables are exactly those that map exactly or defensibly": bool(
                (bcn_pair.enters_cross_source_tests.astype(bool) == mappable).all()
            ),
            "the Barcelona records share no year with the Catalan file": int(bcn_year[:4])
            > catalan_last,
            "the calculator's and the original model are tested on places left out": all(
                outward.loc[(model, 3), "status"] == "passed"
                for model in ("calculator", "catalonia_crash_severity")
            ),
            "the calculator's model has no test on another source": outward.loc[
                ("calculator", 4), "status"
            ]
            == "not run",
            "every choice of the calculator's model is nested in its test": bool(
                (choices.fit != "published model").sum() == len(severity_model.ROLLING_TEST_YEARS)
            )
            and bool((choices.c_bracketed | choices.c_at_weak_limit).all())
            and bool(choices[choices.fit == "published model"].c_bracketed.all()),
            "some province's estimates by kind of road miss the observed interval": bool(
                (
                    (cells.mean_predicted < cells.observed_low)
                    | (cells.mean_predicted > cells.observed_high)
                ).any()
            ),
        }
    )
    provinces = int(cat_checks["demarcations"])
    excluded = _join([FIELD_LABELS.get(field, field.replace("_", " ")) for field in dropped.field])
    overlap = read_table("cat_vs_dgt_province_year").year
    validation = '<a href="validation.html">External validation</a>'
    calculator = f'<a href="severity-models.html">{TITLES["severity-models"]}</a>'
    review = f'<a href="{DOCS_URL}/research/ML_MODEL_REVIEW.md">model review</a>'
    report = f'<a href="{DOCS_URL}/research/SEVERITY_CALCULATOR.md">calculator report</a>'
    published = choices[choices.fit == "published model"].iloc[0]
    return (
        '<h2 id="models">How the models were built and judged</h2>'
        "<p>The published model is the calculator's: a penalised logistic regression of whether "
        "a crash with a death or serious injury in Catalonia was fatal, with a death within 24 "
        f"hours, given circumstances a reader can describe ({calculator}). It is tested by "
        f"nested rolling origin. For each year of {rolling}, three settings are chosen by "
        "fitting on the earlier years except the last two and scoring those two: the strength "
        f"of the penalty, from {_words(len(severity_model.C_EXPONENTS))} values and more if the "
        "best lies at either end, whether each circumstance may count differently on urban "
        "streets and interurban roads, and whether roads through towns get the model's "
        "estimate or the average of such roads in the province. The model is then fitted on "
        "all the earlier years and predicts the year, beside a table of fatal shares by road "
        "and crash type fitted on the same years, so no choice sees the year it predicts. The "
        "published model was chosen by the same rule, scoring "
        f"{published.validation_years.replace('-', '–')} after fitting on "
        f"{published.train_years.replace('-', '–')}, and then fitted on every year. Its "
        f"intervals come from {_fmt_int(severity_model.N_BOOTSTRAP)} refits on resampled "
        "crashes. Crashes on conventional roads whose owner is recorded as “other” or left "
        f"blank are left out, because that field records how a crash was documented ({review}), "
        "so the model and its tests describe crashes on roads with a named owning network or "
        f"of another type. Its method is set out in the {report}.</p>"
        "<p>ROC-AUC measures how well a model ranks: it is the probability that the model "
        "places a randomly chosen case with the outcome above a randomly chosen case without "
        "it. A value of 0.5 is no better than chance and 1 is a perfect ranking. The site gives "
        f"it to two decimals: the Catalan severity model's ROC-AUC of {calc.roc_auc:.2f} over "
        f"{rolling} means that it ranks a fatal crash above a non-fatal one in "
        f"{calc.roc_auc * 100:.0f}% of such pairs. When the outcome is rare, as "
        "deaths are, ROC-AUC can be high while most of the cases ranked highest are still "
        "cases without it.</p>"
        "<p>A model that ranks well may still add nothing to what a simple table shows. Each "
        "model is therefore compared, on the same test records, with a table fixed before the "
        "test: the share of severe outcomes in each group of the training records. A model is "
        f"kept only if its ROC-AUC exceeds the table's by at least {rules.MIN_GAIN:.2f} and the "
        "95% interval of the difference excludes zero. Over "
        f"{rolling} the Catalan severity model scores {calc.roc_auc:.2f} against "
        f"{lookup.roc_auc:.2f} for its table, a gain of {calc.roc_auc - lookup.roc_auc:.2f} "
        f"(95% interval {gain_low:.2f}–{gain_high:.2f}).</p>"
        "<p>A model can rank well and still give probabilities that are too high or too low. "
        "Calibration compares the predicted probabilities with the observed shares in groups "
        "of test records; its slope is 1 when the predictions spread exactly as widely as the "
        "outcomes, and above 1 when they are not spread widely enough. Probabilities are shown "
        f"as estimates only if the slope lies between {low} and {high} and the mean predicted "
        f"probability is within {_fmt_pct(tolerance, 0)} of the observed share, a rule fixed in "
        "advance. Over all the test years the Catalan severity model passes it (slope "
        f"{_fmt_dec(calc.calibration_slope, 2)} and intercept "
        f"{_fmt_dec(calc.calibration_intercept, 2)} of the recalibration fit, 1 and 0 for "
        "estimates that match the outcomes, mean prediction "
        f"{_fmt_pct(calc.mean_predicted)} against {_fmt_pct(calc.prevalence)} observed), but "
        f"not in every province and kind of road ({calculator}). Intervals "
        f"for the scores come from {_fmt_int(modelling.N_BOOT)} bootstrap resamples of the test "
        f"records, {_fmt_int(transport.N_BOOT_TRANSPORT)} in the external tests.</p>"
        "<p>The project's earlier models used a single split by time. The original Catalan "
        f"model was trained on the crashes of {cat_years[0]}–{cat_years[1]}, its settings were "
        f"chosen on {cat_years[2]}–{cat_years[3]}, it was refitted on {cat_years[0]}–"
        f"{cat_years[3]} and tested once on {cat_years[4]}. It was replaced by the Catalan "
        "severity model, because its strongest predictor was the road's owner. The Barcelona models were "
        f"trained on months {bcn_numbers[0]}–{bcn_numbers[1]} of {bcn_year}, with settings "
        f"chosen by {bcn_numbers[2]}-fold cross-validation that keeps the people of one crash "
        f"in the same fold, and tested on months {bcn_numbers[3]}–{bcn_numbers[4]}; no crash "
        "appears on both sides of a split. The Barcelona crash-severity model ranked unseen "
        "crashes no better than its table of shares by accident type, so the study reports the "
        "table instead; the Barcelona person-severity model ranks people without giving "
        f"probabilities and is kept for research. Every model was re-evaluated in the {review}."
        "</p>"
        "<p>The external tests set each model beside a model of the same kind trained in the "
        "test population: the Catalan severity model and the original Catalan model with each of "
        f"the {_words(provinces)} provinces left out in turn and with Barcelona city against "
        "the rest of Catalonia, and the Barcelona models on one district at a time. No other "
        "source records the calculator's inputs, so it has no test outside the Catalan file. "
        "For DGT's records elsewhere in Spain, a harmonised version of the original model refits the "
        f"original model's specification on the {len(used)} of {len(candidates)} candidate "
        "variables whose mapped distributions match on the Catalan crashes of "
        f"{_span(overlap)}, which both files contain ({excluded} "
        + ("does" if len(dropped) == 1 else "do")
        + " not). Barcelona's records "
        f"share no crash with the Catalan file, so the {_words(len(bcn_shared))} variables "
        "used for Barcelona were chosen only because their codings map exactly or defensibly "
        f"({validation}).</p>"
        "<p>Before fitting, each variable was classified by how far the outcome could shape "
        "it. The models use only circumstances recorded about the crash or the person. "
        "Variables the outcome may shape, such as police causes and the Catalan influence "
        "fields, enter only separate comparison versions of the original models, and variables "
        "that encode the outcome enter none "
        f'(<a href="{DOCS_URL}/ML_LEAKAGE_AUDIT.md">audit of the variables</a>). The check for '
        "fields recorded differently when a crash was fatal looked only for placeholders rarer "
        "among fatal crashes, pooled over zones, and did not catch the road-owner field; the "
        "re-evaluation found it.</p>"
    )


# ----------------------------------------------------------------------------- checks
def _checks() -> str:
    validation = pd.read_csv(TABLES_DIR / "validation.csv")
    passed = int(validation.passed.astype(bool).sum())
    total = int(len(validation))
    tables_year = int(validation[validation.check.eq("table_1_1_province")].year.max())
    outcome = (
        "All of them pass, and the crash records match the yearbook exactly, year by year. "
        if passed == total
        else f"{_fmt_int(total - passed)} of them do not pass; the list says which. "
    )
    return (
        '<h2 id="checks">Checks on the data</h2>'
        f"<p>Before any analysis, {_fmt_int(total)} checks tie DGT's crash records, yearbook "
        "tables and driver census to DGT's published totals. On the crash records they check "
        "that each crash has one identifier and every code is in DGT's dictionary, and compare "
        "crashes and victims per year with the yearbook, crashes and deaths by province and by "
        f"month with DGT's {tables_year} tables, deaths and vehicles by type with DGT's "
        "statistical tables, and the crashes and deaths of the speed report's provinces with "
        "that report; the others compare the driver census and the yearbook's driver tables "
        f"with DGT's published totals. {outcome}The kilometre table by owner's age reconciles "
        "with the same release's published fleet to within "
        f"{_fmt_pct(io_exposure.KM_OWNER_TOLERANCE)}, the margin left by owners DGT could not "
        'classify. The <a href="tables/validation.csv">full list of checks</a> is published as '
        "a table.</p>"
    )


def _assumption_rows() -> list[tuple[str, str, str]]:
    """Every assumption the methods document tests, with how and what the test found."""
    scatter = read_table("risk_dispersion").set_index("outcome")
    dispersion = {key: float(scatter.loc[key, "dispersion"]) for key in scatter.index}
    scatter_df = int(scatter.loc["deaths_30d", "df_resid"])

    def spread(outcome: str, bound: str = "") -> float:
        return float(scatter.loc[outcome, f"dispersion_{bound}" if bound else "dispersion"])

    panel = read_table("risk_annual_panel").set_index("year")
    km = read_table("longrun_km_panel").set_index("year")
    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_last = int(km.index.max())
    segments = read_table("longrun_segments")
    fuel_start = int(segments[segments.measure == "road_fuel"].start.max())
    count_start = int(segments[segments.measure == "count"].start.max())
    bio = read_table("longrun_fuel_bio").set_index("year").bio_share
    owner = read_table("q7_owner_age_check").set_index("band")
    owner_year = _path_year("dgt/km_itv_", "edad_propietario")
    drivers = _driver_numbers()
    ranges = drivers["ranges"]
    central = drivers["central"].involved_ratio
    licence = drivers["licence"].involved_ratio
    prevalence = read_table("risk_licence_prevalence")
    young_licensed = prevalence[prevalence.group == "15-29"].set_index(["place", "sex"]).prevalence
    city_older = drivers["city"][drivers["city"].age4 == "65+"].ratio_to_45_64
    oldest_numbers = _older_numbers()
    oldest = oldest_numbers["conditional"].loc["75+"]
    oldest_range = oldest_numbers["range"]["75+"]
    oldest_clear = oldest_numbers["clear"]["75+"][0]
    madrid_year = edm2018.SURVEY_YEAR
    oldest_tier = {
        PASS: "even at the lowest other combination sampling error alone does not reach the "
        "45–64 rate",
        INTERMEDIATE: "at the lowest other combination sampling error alone reaches the 45–64 rate",
        FAIL: "some other combinations are at or below the 45–64 rate",
    }[oldest_numbers["tier"]]
    _check_older = (
        float(oldest.ratio_low) > 1
        and oldest_range[0] <= 1 < oldest_range[1]
        and (oldest_clear > 1) == (oldest_numbers["tier"] != FAIL)
    )
    if not _check_older:
        raise ValueError("data page: the tables no longer support the 75+ assumptions row")
    covered = float(
        read_table("risk_coverage")
        .set_index("component")
        .loc["working days", "share_least_explained"]
    )
    weekend = read_table("risk_weekend_sensitivity")
    # The central estimate gives weekends the working-day age mix; the alternatives have shares.
    mixes = weekend[weekend.non_working_share_of_km.notna()]
    mix_labels = sorted(mixes.non_working_age_mix.unique())
    emef_mix = next(label for label in mix_labels if "EMEF" in label)
    movilia_mix = next(label for label in mix_labels if "MOVILIA" in label)
    emef_module = re.search(r"EMEF \d{4}", emef_mix).group(0)
    movilia_survey = re.search(r"MOVILIA \d{4}", movilia_mix).group(0)
    weekend_shares = sorted(mixes.non_working_share_of_km.astype(float).unique())
    weekend_older = mixes[mixes.group == "65+"].ratio_to_45_64
    weekend_young = mixes[mixes.group == "18-29"].ratio_to_45_64
    split = read_table("risk_frequency_severity").set_index("year")
    split_first, split_last = int(split.index.min()), int(split.index.max())
    end = split.loc[split_last]
    frequency = float(end.frequency_index) / 100
    severity = float(end.severity_index) / 100
    per_fuel = float(end.deaths_per_fuel_index) / 100
    admitted = float(end.hospitalised_per_fuel_index) / 100
    per_admission = float(end.deaths_per_hospitalised_index) / 100
    projection = read_table("longrun_projection_sensitivity").set_index(
        ["measure", "variant", "year"]
    )
    last = int(projection.index.get_level_values("year").max())
    recent = (last - 1, last)
    from_count = f"start_{count_start}"
    review = read_table("review_forecast")
    held_out = review[review.set.eq("holdout")]
    model = held_out[held_out.method.str.contains("published model")].sort_values("window")
    naive = held_out[held_out.method.str.startswith("naive")]
    model_error, naive_error = float(model.rmse.iloc[0]), float(naive.rmse.iloc[0])
    counted_from = risk_trends.DEATHS_30D_COUNTED_FROM
    ratio_30_24 = panel.deaths_30d / panel.deaths_24h
    # The ratio while DGT estimated 30-day deaths, the years after the change below the last
    # estimated year's ratio, and the years from the first one back at it.
    estimated = ratio_30_24.loc[: counted_from - 1]
    counted = ratio_30_24.loc[counted_from:]
    recovered = int(counted[counted >= float(estimated.iloc[-1])].index.min())
    dip, since = ratio_30_24.loc[counted_from : recovered - 1], ratio_30_24.loc[recovered:]
    reference = risk_trends.BASE_YEAR
    per_km_last = km_check.loc[("per_km", km_last)]
    scatter_first, scatter_last = risk_trends.SCATTER_YEARS
    step_end = scatter_first + URBAN_STEP_YEARS
    urban_step = (
        float(panel.loc[step_end, "crashes_urban"] / panel.loc[scatter_first, "crashes_urban"]) - 1
    )
    interurban_step = (
        float(
            panel.loc[step_end, "crashes_interurban"]
            / panel.loc[scatter_first, "crashes_interurban"]
        )
        - 1
    )

    def at(measure: str, variant: str, year: int) -> pd.Series:
        return projection.loc[(measure, variant, year)]

    def growth(a: int, b: int) -> float:
        ratio = float(km.loc[b, "km_per_tonne"] / km.loc[a, "km_per_tonne"])
        return ratio ** (1 / (b - a)) - 1

    early, later = growth(fuel_start, reference), growth(reference, km_last)
    young_band, middle_band, oldest_band = owner.index[0], owner.index[1], owner.index[-1]
    _require(
        {
            "deaths scatter least and injury crashes most around their trend": 1
            < dispersion["deaths_30d"]
            < dispersion["hospitalised_30d"]
            < dispersion["crashes"],
            "urban injury crashes stepped up early in the scatter window, interurban ones did "
            "not": urban_step > 0.2 and interurban_step < 0,
            "interurban km per tonne of national fuel rose, faster after the base year": later
            > early
            > 0,
            "per measured interurban km the last year is above trend and inside its range": not bool(
                per_km_last.outside_interval
            )
            and float(per_km_last.ratio) > 1,
            "the biofuel share rose, which lowers km per tonne": float(bio.loc[km_last])
            > float(bio.loc[reference]),
            "the young own few cars per car-licence holder and the oldest more than one": float(
                owner.loc[young_band, "cars_per_b_permit"]
            )
            < float(owner.loc[middle_band, "cars_per_b_permit"])
            < 1
            < float(owner.loc[oldest_band, "cars_per_b_permit"]),
            "young residents of the province hold car licences less often than Spain's": all(
                young_licensed[("08", sex)] < young_licensed[("Spain", sex)]
                for sex in ("male", "female")
            ),
            "carrying driving per licence holder lowers the young ratio": float(licence["18-29"])
            < float(central["18-29"]),
            "every assumption keeps the young above the middle-aged per km": float(
                ranges.loc["18-29", "min"]
            )
            > 1.2,
            "the survey's working days cover about half of DGT's car km": 0.45 < covered < 0.55,
            "the 65-and-over range spans the middle-aged rate": float(ranges.loc["65+", "min"])
            < 1.05
            and float(ranges.loc["65+", "max"]) > 1,
            "two weekend mixes, each lowering both ratios": len(mix_labels) == 2
            and float(weekend_older.max()) < float(central["65+"])
            and float(weekend_young.max()) < float(central["18-29"]),
            "the weekend mixes lie inside the sensitivity ranges": float(ranges.loc["65+", "min"])
            <= float(weekend_older.min())
            and float(ranges.loc["18-29", "min"]) <= float(weekend_young.min()),
            "by injury crashes most of the fall is severity": severity < frequency < 1,
            "by admissions all of the fall is frequency": admitted < per_fuel and per_admission > 1,
            "admissions and injury crashes scatter beyond Poisson chance; for deaths it is not "
            "established": spread("hospitalised_30d", "low") > 1
            and spread("crashes", "low") > 1
            and spread("deaths_30d", "low") < 1 < spread("deaths_30d", "high"),
            "the ratio of 30-day to 24-hour deaths dips to its lowest when the method changes, "
            "stays below the last estimated year until it recovers, and stays inside its earlier "
            "range from then on": float(ratio_30_24.loc[counted_from]) == float(ratio_30_24.min())
            and float(dip.max()) < float(ratio_30_24.loc[counted_from - 1])
            and bool(since.between(estimated.min(), estimated.max()).all()),
            "on 24-hour deaths the trends turn in the same years": all(
                str(at(measure, "deaths_24h", last).breaks) == str(at(measure, "main", last).breaks)
                for measure in ("count", "road_fuel")
            ),
            "on 24-hour deaths per fuel the last two years stay above the range": all(
                bool(at("road_fuel", "deaths_24h", y).outside_interval)
                and float(at("road_fuel", "deaths_24h", y).ratio) > 1
                for y in recent
            ),
            "per fuel from the main start the last two years lie above the range": all(
                bool(at("road_fuel", "main", y).outside_interval)
                and float(at("road_fuel", "main", y).ratio) > 1
                for y in recent
            ),
            "per fuel from the count's turning point the last two years are above trend, inside": all(
                not bool(at("road_fuel", from_count, y).outside_interval)
                and float(at("road_fuel", from_count, y).ratio) > 1
                for y in recent
            ),
            "the forecast loses to last year's count on the held-out years": len(naive) == 1
            and model_error > naive_error,
        }
    )
    fuel_pages = _join([TITLES[slug] for slug in ("trends", "long-run", "seasons")])
    drivers_page, long_run = TITLES["drivers"], TITLES["long-run"]

    def projected(variant: str) -> str:
        rows = [at("road_fuel", variant, year) for year in recent]
        return " and ".join(f"{_fmt_pct(float(row.ratio) - 1, 0)}" for row in rows)

    starts = [at("road_fuel", from_count, year) for year in recent]
    return [
        (
            f"A year's count varies around its trend only by chance ({TITLES['trends']})",
            f"The scatter of each annual count around its {scatter_first}–{scatter_last} trend, "
            "against the Poisson variance.",
            "Does not hold for hospital admissions or injury crashes: the 95% interval of each "
            "one's scatter, as a multiple of the Poisson variance, lies above 1. Not established "
            "for deaths: their scatter is the smallest of the three and its interval includes 1, "
            "so the data cannot tell whether deaths vary beyond chance. Intervals for changes "
            "against "
            f"{reference} are widened to match, with Student's t for the trend's "
            f"{_words(scatter_df)} residual degrees of freedom; {TITLES['trends']} gives the "
            "factors. The crash factor also carries a step in recorded urban crashes between "
            f"{scatter_first} and {step_end}, so the crash intervals are too wide to show "
            "whether a change is beyond an ordinary year.",
        ),
        (
            f"Road fuel tracks the kilometres driven ({fuel_pages})",
            "Measured vehicle-kilometres on State, regional and provincial interurban roads, set "
            "against national road fuel. The scopes differ, so this checks the proxy and gives "
            "no rate.",
            "Cannot be tested on all roads. Interurban kilometres per tonne of national fuel "
            f"grew {_fmt_pct(early)} a year over {fuel_start}–{reference} and "
            f"{_fmt_pct(later)} a year over {reference}–{km_last}, so part of the recent excess "
            "in deaths per tonne of fuel may reflect more driving per tonne. Per measured "
            f"interurban kilometre, deaths in {km_last} were "
            f"{_fmt_pct(float(per_km_last.ratio) - 1, 0)} above their "
            f"{int(per_km_last.projection_start)}–{reference} trend, within its range "
            f"({long_run}).",
        ),
        (
            f"A tonne of road fuel means the same every year ({fuel_pages})",
            "CORES subtotals against the sum of their products, biofuels included, every month; "
            "the published biofuel share.",
            "Holds. The subtotals equal their products every month. Biofuel was "
            f"{_fmt_pct(float(bio.loc[reference]))} of road fuel by mass in {reference} and "
            f"{_fmt_pct(float(bio.loc[km_last]))} in {km_last}; it carries less energy per "
            "tonne, so its rise would lower kilometres per tonne slightly and cannot explain "
            "the rise in interurban kilometres per tonne.",
        ),
        (
            f"The owner's age stands for the driver's ({drivers_page})",
            f"Cars and kilometres per car-licence holder in each owner's age band, {owner_year}.",
            "Does not hold at either end: "
            f"{_fmt_dec(owner.loc[young_band, 'cars_per_b_permit'], 2)} cars per car-licence "
            f"holder at {owner.loc[young_band, 'band_label']}, "
            f"{_fmt_dec(owner.loc[middle_band, 'cars_per_b_permit'], 2)} at "
            f"{owner.loc[middle_band, 'band_label']} and "
            f"{_fmt_dec(owner.loc[oldest_band, 'cars_per_b_permit'], 2)} at "
            f"{owner.loc[oldest_band, 'band_label']}. Kilometres driven by drivers of each age "
            "replace the owner-age kilometres, which are kept only as a comparison.",
        ),
        (
            f"One region's age profile of driving holds for Spain ({drivers_page})",
            "No source measures driving by age for Spain as a whole, so the transfer cannot be "
            "tested. Car-licence holding by age in the province of Barcelona is compared with "
            "Spain's, the survey's working days are set against DGT's car kilometres, and the "
            "ratios are recomputed under other regional profiles, distance treatments, survey "
            "years, weekend mixes and age mixes for the kilometres the survey does not cover.",
            "Not exact, and incomplete. The survey's working days account for "
            f"{_fmt_pct(covered, 0)} of DGT's car kilometres, and the central estimate gives the "
            "rest the same age mix. Young residents of the province hold car licences less often "
            "than Spain's: carried per licence holder instead of per resident, the survey puts "
            "involvement per km at 18–29 at "
            f"{float(licence['18-29']):.2f} times the 45–64 rate instead of "
            f"{float(central['18-29']):.2f}. Across every alternative, including other regional "
            "profiles combined with other age mixes for the uncovered kilometres, the "
            f"sensitivity range is {float(ranges.loc['18-29', 'min']):.2f}–"
            f"{float(ranges.loc['18-29', 'max']):.2f} at 18–29 and "
            f"{float(ranges.loc['65+', 'min']):.2f}–{float(ranges.loc['65+', 'max']):.2f} at 65 "
            "and over; the ratios are published with these ranges, and only the direction at "
            "18–29 is firm. They are ratios of involvement in injury crashes, not of "
            "responsibility for them, and say nothing of how often a crash kills the driver. "
            "Inside Barcelona on working days, with no transfer, the ratio at 65 and over is "
            f"{float(city_older.min()):.2f}–{float(city_older.max()):.2f} under "
            f"{_words(len(city_older))} versions of the city's kilometres.",
        ),
        (
            "People aged 75 and over drive as much less than those aged 65–74 as in Madrid in "
            f"{madrid_year} (the conditional estimate on {drivers_page})",
            "No source measures it for Spain. Compared with DGT licence holding by age in the "
            "province of Madrid, the province of Barcelona and Spain; with Spanish surveys of "
            "men's driving per licence holder; and replaced by three other splits under every "
            "other assumption, including an upper bound for too few people aged 75 and over in "
            "the Barcelona-area sample.",
            "Conditional. Licence holding falls alike in the three places, which is consistent "
            "with the assumption but does not test the kilometres. On the Madrid pattern, 75 and "
            f"over: {float(oldest.ratio_to_45_64):.2f} (95% sampling interval "
            f"{joint_interval(oldest)}). Sensitivity range "
            f"{oldest_range[0]:.2f}–{oldest_range[1]:.2f}; below about {oldest_clear:.1f} only "
            "with equal kilometres per licence holder, which surveys of men's driving in "
            f"Madrid ({madrid_year}) and by RACC ({national_rates.RACC_YEAR}) are at odds with, kept "
            f"in the range; {oldest_tier}. Rising licence holding since {madrid_year} would lower "
            "the figure; too few people aged 75 and over in the survey's sample would raise it.",
        ),
        (
            f"Working-day driving represents the year ({drivers_page})",
            "No source measures weekend kilometres by age. Instead, "
            f"{' or '.join(_fmt_pct(share, 0) for share in weekend_shares)} of annual kilometres "
            "are given one of two weekend age mixes: a proxy from the "
            f"{emef_module} module on overnight weekend stays, and car trips on weekend days in "
            f"{movilia_survey}.",
            "Cannot be tested directly. The weekend mixes lower the 65-and-over ratio from "
            f"{float(central['65+']):.2f} to {float(weekend_older.min()):.2f}–"
            f"{float(weekend_older.max()):.2f} and the 18–29 ratio from "
            f"{float(central['18-29']):.2f} to {float(weekend_young.min()):.2f}–"
            f"{float(weekend_young.max()):.2f}; both are inside the sensitivity range above.",
        ),
        (
            f"The fall in deaths per tonne of fuel was a fall in how deadly crashes are "
            f"({long_run})",
            "Deaths per tonne split exactly into casualties per tonne and deaths per casualty, "
            f"once by injury crashes and once by hospital admissions, {split_first}–{split_last}.",
            f"Not established. Deaths per tonne fell {_fmt_pct(1 - per_fuel, 0)}. By injury "
            f"crashes, crashes per tonne fell {_fmt_pct(1 - frequency, 0)} and deaths per crash "
            f"{_fmt_pct(1 - severity, 0)}; by admissions, admissions per tonne fell "
            f"{_fmt_pct(1 - admitted, 0)} and deaths per admission rose "
            f"{_fmt_pct(per_admission - 1, 0)}. The fall in deaths per tonne is firm; how it "
            "divides between how often and how deadly cannot be told from these series.",
        ),
        (
            f"The 30-day death series means the same throughout ({long_run})",
            f"DGT estimated 30-day deaths from 24-hour deaths until {counted_from - 1} and has "
            f"counted them since {counted_from}. The trends were refitted on 24-hour deaths, "
            "which the police count directly throughout.",
            "The change shows as a temporary dip in the ratio of 30-day to 24-hour deaths, not "
            f"a lasting step. The ratio fell from {float(estimated.iloc[-1]):.3f} in "
            f"{counted_from - 1} to {float(ratio_30_24.loc[counted_from]):.3f} in {counted_from}, "
            f"the lowest in the series, and stayed between {float(dip.min()):.3f} and "
            f"{float(dip.max()):.3f} until {recovered - 1}; from {recovered} it has been "
            f"{float(since.min()):.3f}–{float(since.max()):.3f}, inside its "
            f"{int(estimated.index.min())}–{counted_from - 1} range of "
            f"{float(estimated.min()):.3f}–{float(estimated.max()):.3f}. Refitted on 24-hour "
            "deaths, the trends turn in the same years, and deaths per tonne of fuel in "
            f"{recent[0]} and {recent[1]} still lie above their range, so the long-run results "
            "do not rest on the change.",
        ),
        (
            f"The excess of deaths per tonne of fuel in {recent[0]}–{recent[1]} does not depend "
            f"on where the trend starts ({long_run})",
            f"The trend's last segment refitted from {count_start}, the count's last turning "
            f"point, instead of from {fuel_start}.",
            f"It does. From {fuel_start}, deaths per tonne of fuel in {recent[0]} and "
            f"{recent[1]} were {projected('main')} above the trend, outside its range; from "
            f"{count_start}, {projected(from_count)} above it, "
            f"{_where(starts[0]).replace('the range', 'its range')} in {recent[0]} and "
            f"{_where(starts[1]).replace('the range', 'its range')} in {recent[1]}.",
        ),
        (
            "A forecast of monthly deaths can show whether a year's deaths changed",
            "The forecast model's error in a year's deaths on ordinary years held back from its "
            "choice, against repeating the same months of the year before.",
            f"Does not hold: its error was {_fmt_pct(model_error)} against "
            f"{_fmt_pct(naive_error)} for last year's count. The forecast, and the detectable "
            "changes computed from its errors, were withdrawn.",
        ),
    ]


def _assumptions() -> str:
    """The assumptions behind the results that the data can test, each with what testing found."""
    frame = pd.DataFrame(_assumption_rows(), columns=["Assumption", "Check", "Result"])
    review = f'<a href="{DOCS_URL}/research/ML_MODEL_REVIEW.md">model review</a>'
    return (
        '<h2 id="assumptions-tested">Assumptions tested</h2>'
        "<p>Several results rest on assumptions that the data can test in full or in part. "
        "Each assumption names the pages whose results rest on it; the withdrawn forecast is "
        f"documented in the {review}.</p>"
        + table(frame, "Assumptions behind the results, how each was checked, and what was found.")
    )


# ----------------------------------------------------------------------------- reproduction
def _reproduce() -> str:
    return (
        '<h2 id="reproduce">Reproducing the results</h2>'
        "<p>Every result in the study is computed from the raw published files by the code in "
        "the repository. The raw files are kept with their checksums and, "
        "where recorded, their download addresses, and one command sequence in the "
        f'<a href="{REPO_URL}#reproduce">README</a> rebuilds the checks, tables, models, '
        "figures and pages in order. Each page reads its numbers from the result tables, and "
        "the build stops if a table no longer supports a sentence that describes it. Automated "
        "tests rerun the checks on every change.</p>"
        f'<p>The repository also holds the <a href="{DOCS_URL}/methodology.md">implementation '
        "notes</a>, with the module behind each method, the "
        f'<a href="{DOCS_URL}/data_sources.md">source register</a>, with what each source is '
        "and its terms of use, the manifest of the "
        f'<a href="{REPO_URL}/tree/main/data/raw">raw files</a>, with each file\'s checksum '
        "and, where recorded, its download address, and the "
        f'<a href="{DOCS_URL}/data_inventory.md">data inventory</a>.</p>'
        "<p>The project was developed through a reproducible, source-driven workflow. The "
        "research questions, the choice of sources, the statistical design, the interpretation "
        "and the decision to publish each result are the author's, and so is responsibility for "
        "them. AI coding assistants were used during implementation, debugging, data-processing "
        "work and review.</p>"
    )


def _manifest_note(path_prefix: str, pattern: str) -> str:
    """A date or phrase the source register records in the manifest description of a file."""
    return _manifest_notes(path_prefix, pattern)[-1]


def _manifest_notes(path_prefix: str, pattern: str) -> list:
    """Every distinct match of ``pattern`` (a tuple if it has several groups) in the manifest
    descriptions under ``path_prefix``, sorted."""
    manifest = _manifest()
    rows = manifest[manifest.path.str.startswith(path_prefix)]
    found = sorted({m for text in rows.description for m in re.findall(pattern, str(text))})
    _require({f"the manifest records {pattern!r} for {path_prefix}": len(found) >= 1})
    return found


def _date(text: str, dayfirst: bool = False) -> str:
    """A date as the page writes it: 5 November 2025."""
    stamp = pd.to_datetime(text, dayfirst=dayfirst)
    return f"{stamp.day} {stamp:%B %Y}"


def _downloaded(paths: tuple[str, ...]) -> str:
    """When the files under ``paths`` (path prefixes) were downloaded, from the manifest's
    ``added`` column: one date, or the first and the last. A file recorded only as added before a
    date counts as added on it, and the text then says the first date may be earlier."""
    manifest = _manifest()
    added = manifest[manifest.path.str.startswith(paths)].added.astype(str)
    _require({f"the manifest dates the files {paths}": len(added) >= 1})
    dates = pd.to_datetime(added.str.removeprefix("before "))
    first, last = dates.min(), dates.max()
    earlier = bool((dates[added.str.startswith("before ")] == first).any())
    if first == last and not earlier:
        return f"on {_date(str(first))}"
    or_earlier = " or earlier" if earlier else ""
    return f"from {_date(str(first))}{or_earlier} to {_date(str(last))}"


def _reuse() -> str:
    from dgt_stats.emef import publication

    catalan_update = _date(
        _manifest_note("catalonia/", r"rows last updated on the portal (\d{4}-\d{2}-\d{2})")
    )
    barcelona_update = _date(_manifest_note("barcelona/", r"last modified (\d{4}-\d{2}-\d{2})"))
    barcelona_year = _year_label(read_table("bcn_person_severity_share"))
    manifest = _manifest()
    emef_years = sorted(
        {int(y) for y in manifest.path.str.extract(r"^emef/(\d{4})/", expand=False).dropna()}
    )
    _require(
        {
            "the EMEF files cover consecutive years": emef_years
            == list(range(emef_years[0], emef_years[-1] + 1))
        }
    )
    emef_span = f"{emef_years[0]}–{emef_years[-1]}"
    emef_dates = _manifest_notes("emef/", r"file date on omc\.cat (\d{4}-\d{2}-\d{2})")
    microdata_year, microdata_update = _manifest_notes(
        "dgt/microdata/", r"víctimas (\d{4}), last updated (\d{4}-\d{2}-\d{2})"
    )[-1]
    dgt_downloaded = _downloaded(("dgt/",))
    ine_downloaded = _downloaded(
        ("ine/ine_poblacion_provincias_edad_sexo.csv", "ine/ine_poblacion_edad_simple_sexo.csv")
    )
    yearbook_modified = _date(
        _manifest_note("transportes/anuario_", r"por última vez el (\d{2}-\d{2}-\d{4})"),
        dayfirst=True,
    )
    transport_downloaded = _downloaded(("transportes/peaje_", "transportes/movilia_2006"))
    cores_update = _date(
        _manifest_note("cores/", r"Actualizado el (\d{2}-\d{2}-\d{4})"), dayfirst=True
    )
    idescat_release = _date(_manifest_note("idescat/", r"\((\d{1,2} [A-Z][a-z]+ \d{4})\)"))
    return (
        '<h2 id="reuse">Reuse</h2>'
        f'<p>The code is under the <a href="{REPO_URL}/blob/main/LICENSE">MIT licence</a>. The '
        "data keep the terms of the bodies that publish them, and most of those terms require "
        "the date of the data's last update to be given. Where a provider publishes that date, "
        "it is given below. Where it does not, the date given is the one the file itself "
        "records or, failing that, the day it was downloaded, as the source register records "
        "it, and the text says which.</p>"
        "<p>DGT's crash microdata are catalogued on datos.gob.es, whose "
        '<a href="https://datos.gob.es/avisolegal">legal notice</a> allows reuse if the source '
        "is named, the meaning is not distorted, the date of last update is kept, no "
        "endorsement is implied and the metadata are kept. DGT's other statistics name no "
        "licence. They are reused as public-sector information under Ley 37/2007 on the reuse "
        "of public-sector information, on the same conditions. Source: Dirección General de "
        f"Tráfico. The crash microdata of {microdata_year} were last updated on "
        f"{_date(microdata_update)}. DGT publishes no date of last update for the earlier "
        "microdata or its other files, so the register gives the date each was downloaded, "
        f"{dgt_downloaded}.</p>"
        "<p>INE's population tables are under the "
        '<a href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution '
        '4.0</a> licence (<a href="https://www.ine.es/aviso_legal/">INE legal notice</a>): '
        '<span lang="es">Elaboración propia con datos extraídos del sitio web del INE: '
        "www.ine.es</span>. The tables as downloaded carry no date of last update; they were "
        f"downloaded {ine_downloaded}.</p>"
        "<p>The files of the Ministerio de Transportes y Movilidad Sostenible are reused under "
        'its <a href="https://www.transportes.gob.es/ministerio/aviso-legal">legal notice</a>, '
        "which allows commercial and non-commercial reuse if the origin is cited, the date of "
        "last update is kept, the content is not distorted, no endorsement is implied and the "
        'metadata are kept: <span lang="es">Origen de los datos: Ministerio de Transportes y '
        "Movilidad Sostenible</span>. The roads chapter of its statistical yearbook carries no "
        "published date of last update; by its own metadata the file was last modified on "
        f"{yearbook_modified}. The toll-motorway series and "
        "the MOVILIA tables carry no date of last update; they were downloaded "
        f"{transport_downloaded}.</p>"
        "<p>CORES, the corporation of public law that publishes Spain's petroleum statistics, "
        "names no licence for them. They are reused as public-sector information under Ley "
        "37/2007, on the datos.gob.es conditions above. Source: Corporación de Reservas "
        "Estratégicas de Productos Petrolíferos; the file states that it was updated on "
        f"{cores_update}.</p>"
        "<p>The Catalan crash file is reused under the "
        '<a href="https://administraciodigital.gencat.cat/ca/dades/dades-obertes/informacio-'
        "practica/llicencies/\">Llicència oberta d'ús d'informació - Catalunya</a>. Source: "
        "Generalitat de Catalunya. Departament d'Interior i Seguretat Pública. Servei Català "
        f"de Trànsit; data last updated on {catalan_update}. The Barcelona crash records are "
        "published by the Ajuntament de Barcelona on Open Data BCN under the "
        '<a href="https://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution '
        f"4.0</a> licence ({barcelona_year} files last modified on {barcelona_update}); the "
        "site reads them into its own tables and does not alter the files.</p>"
        "<p>The EMEF figures are this study's own calculations from the public-use microdata "
        f"(ATM, Idescat and Institut Metròpoli, Enquesta de mobilitat en dia feiner {emef_span}, "
        "Autoritat del Transport Metropolità); they are not official results. They are reused "
        'under the open-data clause of the <a href="https://www.omc.cat/ca/avis-legal">legal '
        "notice</a> of the Observatori de la Mobilitat de Catalunya, which requires the rights "
        "holder, the Consorci de l'Autoritat del Transport Metropolità, and the source to be "
        "cited and the date of last update to be given: the files were last updated on "
        f"omc.cat between {_date(emef_dates[0])} and {_date(emef_dates[-1])}, and the register "
        "gives each file's date. As the survey's dictionaries require, no estimate resting on "
        f"fewer than {publication.MIN_SAMPLE_OBSERVATIONS} sample observations is published. The "
        "census count of employed people aged 65 and over in Catalonia comes from Idescat's "
        f"release of {idescat_release}, reused under Idescat's "
        '<a href="https://www.idescat.cat/institut/web/?lang=en">legal notice</a>, which allows '
        "reuse if the source is cited, the content is not altered and the date of the latest "
        "update is given. Source: created upon the basis of Idescat's own data.</p>"
        "<p>The Madrid survey figures use the Consorcio Regional de Transportes de Madrid's "
        'EDM2018 data (<a href="https://www.crtm.es">Powered by CRTM</a>), and the tables '
        "derived from them are distributed under the CRTM's licence, as it requires.</p>"
        "<p>Every published figure is an aggregate, and nothing identifies a person. The "
        f'file-by-file terms and dates are in the <a href="{DOCS_URL}/data_sources.md">source '
        "register</a>.</p>"
    )


def page_data(captions: dict[str, str]) -> str:
    body = summary(
        "Each count is divided by a denominator meant to contain it, with the exceptions named "
        "below, and a change is read against the variation of an ordinary year. Severity "
        "among recorded crashes is kept apart from how often crashes happen, police-recorded "
        "factors are treated as judgements, and missing values stay missing. A predictive model "
        "is kept only if it ranks unseen records better than a simple table fixed in advance. "
        "Every assumption the data can test is listed with what the test found."
    )
    body += _definitions()
    body += _rates()
    body += _records(captions)
    body += _models()
    body += _checks()
    body += _assumptions()
    body += _reproduce()
    body += _reuse()
    body += downloads(
        [
            ("validation", "reconciliation checks"),
            ("risk_dispersion", "year-to-year dispersion"),
            ("missingness_by_year", "missing values by field and year"),
            ("missingness_where_applicable", "values recorded where each field applies"),
            ("dgt_audit_presence_coding", "fog and wind coding by province and year"),
            ("ml_split_isolation", "training and test splits"),
            ("ml_rule_comparison", "models against their tables"),
            ("ml_common_feature_validation", "harmonised variables"),
            ("ml_feature_catalogue", "variable classification"),
        ]
    )
    return render_page(
        "data",
        "Methodology",
        "How the study's results are produced: definitions, rates, police records, models, "
        "checks on the data and the assumptions tested.",
        body,
    )
