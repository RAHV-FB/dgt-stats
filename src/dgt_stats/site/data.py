"""Methodology: definitions, rates and denominators, the police crash records, the checks on the
data, reproduction, reuse and each page's technical notes.

What each source is, what it covers and what it cannot show is on the sources page; this page
says how the results are produced from them.
"""

from __future__ import annotations

import inspect
import re

import pandas as pd

from dgt_stats import codes, dgt_coding, features, io_exposure, risk_trends, severity_model
from dgt_stats import figures as figure_data
from dgt_stats.derive import ROAD_GROUP_BY_TYPE
from dgt_stats.microdata.ml import features as catalan_features
from dgt_stats.microdata.ml import recording
from dgt_stats.paths import RAW_DATA_DIR
from dgt_stats.site.components import (
    ALL_PAGES,
    DEFINITION_IDS,
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
# years after the scatter window opens.
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
        (
            "Sampling interval",
            "A 95% interval that allows only for chance: which people a survey happened to "
            "sample, and chance in the counts of crashes. It takes every other choice of the "
            "analysis as given, so the real uncertainty can be much wider.",
        ),
        (
            "Sensitivity range",
            "The span of an estimate across the alternative assumptions tested. It carries no "
            "probability, and it is not a limit: assumptions not tested, or tested ones combined "
            "differently, could fall outside it.",
        ),
        (
            "Conditional estimate",
            "An estimate that holds only if a stated assumption holds, and is always printed with "
            "it; its sampling interval holds the assumption fixed.",
        ),
    ]
    return '<h2 id="definitions">Definitions</h2>' + facts(items, "Definitions", DEFINITION_IDS)


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
    vehicles = "motorcycles, cars, vans, trucks and buses"
    denominators = [
        (
            "Per resident",
            "The burden of road deaths on a population, most of whom were not travelling at "
            "the time. A rate per resident falls when people travel less.",
        ),
        (
            "Per licence holder",
            "Counts only drivers: on the drivers page, car drivers involved in injury crashes, "
            "injured or not.",
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
    since_2019 = f'<a href="long-run.html#since-{risk_trends.BASE_YEAR}">{TITLES["long-run"]}</a>'
    return (
        '<h2 id="rates">Rates, denominators and intervals</h2>'
        "<p>Each rate pairs a count with a denominator meant to contain it:</p>"
        + facts(denominators, "Denominators")
        + "<p>Pedestrians and cyclists hold no licence for the trip in which they are hurt and "
        "travel in no registered vehicle, so they are counted against residents and road fuel "
        "only. Road fuel stands in for the kilometres driven on all roads, and the kilometres "
        "by driver age carry one region's survey to Spain; neither can be tested for Spain as "
        "a whole. Some rates do not fully meet the rule, and each page says "
        "so: rates per resident count visitors' deaths, rates per licence holder (by sex) "
        "count unlicensed and foreign drivers, rates per registered vehicle and "
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
        f"year's variation ({since_2019}).</p>"
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
    matched = dgt_coding.catalan_junction_years(junctions)
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
        "come from the records for the four Catalan provinces.</p>"
        f"<ul><li>Until {switch - 1} those records code almost every crash on a conventional "
        "road as a conventional road with a dual carriageway "
        f"({_fmt_int(cat_before.road_type_5_dual_carriageway)} such crashes in {switch - 1}, "
        f"{_fmt_int(cat_before.road_type_6_single_carriageway)} on single carriageways); from "
        f"{switch} they use the single-carriageway code instead. Elsewhere the dual-carriageway "
        f"code holds between {_fmt_int(rest_dual.min())} and {_fmt_int(rest_dual.max())} crashes "
        f"a year.</li><li>In {later.period} many crashes on urban streets begin to be coded in "
        f"the “other” road group (codes {_code_list(other_codes)}, service roads, slip roads, "
        "cycle paths and other minor roads): "
        f"{_fmt_pct(later.street_share, 0)} of that year's crashes in the group are on urban "
        f"streets, against {_fmt_pct(earlier.street_share, 0)} in "
        f"{str(earlier.period).replace('-', '–')}. Most of them carry code {other_codes[-1]}, "
        f"“other” itself, and {_fmt_int(cat_other)} of the {_fmt_int(all_other)} crashes with "
        f"that code in {later.period} are Catalan.</li><li>From {flip} the same records code the "
        "junction flag the wrong way round. The share of their crashes coded at a junction goes "
        f"from between {_fmt_pct(cat_share.loc[before].min(), 0)} and "
        f"{_fmt_pct(cat_share.loc[before].max(), 0)} a year in {cat_share.index.min()}–"
        f"{flip - 1} ("
        + _join([f"{_fmt_pct(cat_share.loc[y], 0)} in {y}" for y in narrow_years])
        + ", under the narrower definition below) to "
        + _join([f"{_fmt_pct(cat_share.loc[y], 0)} in {y}" for y in after_years])
        + ". Elsewhere it stays between "
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
        "junctions.</li><li>In "
        + _join([str(y) for y in narrow_years])
        + " the records use a narrower definition of a junction: DGT's count of these Catalan "
        "crashes at a junction matches the Catalan file's crashes within a junction, where in "
        + _runs(wider.year)
        + " it matches those within or within "
        + f"{dgt_coding.NEAR_JUNCTION_METRES} metres of one. That year "
        + _join([_fmt_int(near.loc[y]) for y in narrow_years])
        + " Catalan crashes coded away from a junction carry a junction type or a right-of-way "
        f"flag, against {_fmt_int(near_others.sum())} in all the other years before {flip}; "
        "counted at a junction, they bring that year's share to "
        + _join([_fmt_pct(narrow_with_near.loc[y], 0) for y in narrow_years])
        + ".</li></ul>"
        "<p>Road-type series are therefore read year by year and alongside zone, the two kinds "
        "of conventional road form one group, and no road-type trend is drawn. Comparisons of "
        "Catalonia with the rest of Spain group every conventional road together for the same "
        "reason.</p>"
        f"<p>Junction shares as published are not compared across {flip}. The association of "
        "junctions with fatal outcomes reads the flag the other way round in those "
        "province-years, which puts the Catalan share at a junction at "
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
    breaks = dgt_coding.presence_breaks(presence)
    if breaks.empty:
        return ""
    fog = breaks[breaks.field.eq("CONDICION_NIEBLA")]
    wind = breaks[breaks.field.eq("CONDICION_VIENTO")]
    flags = [f"{field}_coding_break" for field in dgt_coding.PRESENCE_NAMES]
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
        if str(spec["source"]) in dgt_coding.PRESENCE_NAMES
    }
    model_source = inspect.getsource(severity_model)
    _require(
        {
            "the presence fields are fog and strong wind": set(dgt_coding.PRESENCE_NAMES)
            == {c for c in dgt_coding.CANDIDATES if dgt_coding.presence_field(c)},
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
            "neither field enters the national association analysis or the severity model": not unread
            and not any(
                field in model_source for field in ("D_BOIRA", "D_VENT", "NIEBLA", "VIENTO")
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
        f"condition to more than {_fmt_pct(dgt_coding.MAX_PRESENCE_SHARE, 0)} of their crashes. "
        "Elsewhere fog or strong wind is recorded in at most "
        f"{_fmt_pct(max(float(others[f'{c}_share'].max()) for c in dgt_coding.PRESENCE_NAMES))} "
        "of a province-year's crashes.</p>"
        f"<p>From {min(fog_years)} the records for the province of "
        f"{fog_province.province_name} code fog in {_fmt_pct(fog_province.share_low, 0)} to "
        f"{_fmt_pct(fog_province.share_high, 0)} of crashes a year, against "
        f"{_fmt_pct(own_before.CONDICION_NIEBLA_share.max())} in "
        + _runs(own_before.index)
        + ". The Servei Català de Trànsit's file records fog in the same number of the "
        "province's crashes with a death or serious injury in each year of "
        f"{catalan_years[0]}–{catalan_years[-1]}. "
        + (f"Strong wind is recorded {wind_text}. " if not wind.empty else "")
        + "In those province-years the field is coded another way: neither a value nor a "
        "blank says whether there was fog or strong wind. Neither field enters the "
        "national association analysis or the severity model.</p>"
    )


def _missingness_alt(missing: pd.DataFrame) -> str:
    """The missing-values figure's alt text: what it shows, from the shares it draws."""
    years = missing.year
    shown = figure_data.recorded_where_applicable(missing)
    names = figure_data.MISSINGNESS_FIELDS
    core = shown.loc[[names[field] for field in CORE_FIELDS]]
    _require(
        {
            "the fields that describe every crash are recorded in nearly every crash": bool(
                (core > ALWAYS_RECORDED).all().all()
            ),
            "the pavement and island fields are recorded in most crashes they apply to": bool(
                (shown.loc[[names["ACERA"], names["ISLA"]]] > 0.5).all().all()
            ),
        }
    )
    return (
        "Share of DGT crash records with a value recorded, among the crashes each field applies "
        f"to, by field and year, {_span(years)}, from the most completely recorded field down. "
        f"The {_join(list(CORE_FIELDS.values()))} are recorded in nearly every crash. "
        "Fields that apply only to some crashes, such as the pavement and island fields, are "
        "recorded in most of the crashes they apply to. The fields that apply only at a "
        "junction are not drawn."
    )


def _records(captions: dict[str, str]) -> str:
    regional = read_table("dgt_audit_regional")
    artefacts = read_table("ml_recording_artefacts")
    semantics = read_table("mq_bcn_count_semantics").set_index("check").value
    missing = read_table("missingness_by_year")
    limit = recording.RATIO_LIMIT
    catalan = artefacts[artefacts.verdict == "outcome-dependent recording"]
    in_main = [
        feature.column
        for feature in catalan_features.CATALONIA_TABLE.catalogue
        if "context" in feature.sets
    ]
    model_source = inspect.getsource(severity_model)
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
            "the outcome-dependent Catalan fields stay out of the feature set the severity model reads": not set(
                catalan.column
            )
            & set(in_main),
            "the severity model reads none of the outcome-dependent Catalan fields": not any(
                re.search(rf"\b{re.escape(column)}\b", model_source)
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

    pavement_na = overall("ACERA", "share_not_applicable")
    island_empty = overall("ISLA", "share_empty")
    shown = figure_data.recorded_where_applicable(missing)
    names = figure_data.MISSINGNESS_FIELDS
    _require(
        {
            "the figure draws fog and wind recorded in every crash, an empty cell being the "
            "recorded “no”": bool(
                (shown.loc[[names["CONDICION_NIEBLA"], names["CONDICION_VIENTO"]]] == 1).all().all()
            ),
            "the right-of-way flags are unrecorded together": float(
                regional[priority].unrecorded_share.max()
                - regional[priority].unrecorded_share.min()
            )
            < 0.01,
            "unrecorded shares split into fields nearly always recorded and fields often not": 0
            < mostly_blank
            < len(questions) / 2,
            "the figure leaves “not applicable” and the island's empty cells out of its shares, "
            "and its caption says so": all(
                phrase in captions.get("d1_missingness", "")
                for phrase in (
                    "998 (not applicable)",
                    "among the crashes the field applies to",
                    "fog or strong wind field counts as recorded",
                    "not drawn",
                )
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
        "read as zero or as “no”, except in the fog and strong-wind fields. DGT fills those in "
        "only when there was fog or strong wind, apart from a few province-years that code them "
        'another way (<a href="#coding-breaks">coding breaks</a>). In Barcelona\'s crash table '
        "a blank count also means zero: no cell holds an explicit zero, and with blanks read as "
        "zero the victims add up in every crash.</p>"
        "<p>The audit of DGT's records counts a field as unrecorded when it is “not specified”, "
        "“unknown” or empty in a crash it applies to: the junction type and the right-of-way "
        "flags, for instance, do not apply to a crash away from a junction. Of the "
        f"{_fmt_int(len(questions))} fields it examines (the "
        f"{_fmt_int(int(priority.sum()))} right-of-way flags counted as one), "
        f"{_words(mostly_blank)} are unrecorded in more than {_fmt_pct(MOSTLY_BLANK, 0)} of "
        "the crashes they apply to"
        + (
            f", one of them only just ({_fmt_pct(closest)})"
            if closest - MOSTLY_BLANK < JUST_ABOVE
            else ""
        )
        + f". How unevenly the provinces record them is set out under {sources}.</p>"
        "<p>The figure leaves “not applicable” out of each field's share, so a field that "
        "applies only to some crashes is judged on the crashes it applies to. The pavement field "
        f"is “not applicable” in {_fmt_pct(pavement_na, 0)} of crashes, and the island field is "
        "empty, which DGT's dictionary defines as not applicable, in "
        f"{_fmt_pct(island_empty, 0)}. In the figure an empty fog or strong-wind field counts "
        "as recorded. The junction type, the right-of-way flags and the crossing road apply "
        "only at a junction, which this table cannot identify, so they are not drawn.</p>"
        + figure("d1_missingness", _missingness_alt(missing), captions)
        + "<p>Recording can also depend on the outcome. Fatal crashes may be investigated more "
        "fully, so fields left unspecified in non-fatal crashes are more often filled in for "
        f"fatal ones. In the Catalan file, {_words(levels)} placeholder levels in "
        f"{_words(fields)} fields (“not specified” or an unexplained blank) are recorded at "
        f"least {_fmt_dec(limit)} times as often in non-fatal crashes as in fatal ones; these "
        "fields are left out of the severity model. The road owner is the reverse case, "
        "blank far more often on fatal records, and the model leaves out the crashes it "
        f'affects (<a href="{DOCS_URL}/SEVERITY_MODEL.md">model note</a>).</p>' + _coding_breaks()
    )


# ----------------------------------------------------------------------------- checks
def _checks() -> str:
    validation = read_table("validation")
    failing = validation[~validation.passed.astype(bool)]
    _require({"every reconciliation check passes": failing.empty})
    return (
        '<h2 id="checks">Checks on the data</h2>'
        "<p>Before any analysis, reconciliation checks tie DGT's crash records, yearbook tables "
        "and driver census to DGT's published totals. Every check passes. On the crash records "
        "they confirm that every code is in DGT's dictionary and compare crashes, victims and "
        "deaths by year, province, month and vehicle type with the yearbook and DGT's "
        "statistical tables, and the crashes and deaths of the speed report's provinces with "
        "that report. The other checks compare the driver census and the yearbook's driver "
        "tables with DGT's published totals. The kilometre table by owner's age reconciles with "
        "the same release's published fleet to within "
        f"{_fmt_pct(io_exposure.KM_OWNER_TOLERANCE)}, the margin left by owners DGT could not "
        'classify. The <a href="tables/validation.csv">full list of checks</a> is published as '
        "a table.</p>"
    )


# ----------------------------------------------------------------------------- reproduction
def _reproduce() -> str:
    steps = (
        ("ingest.py all", "reads data/raw into data/staging and runs the reconciliation checks"),
        ("build_tables.py", "builds the processed table of DGT crash records"),
        ("model.py", "fits the associations in DGT's crash records"),
        ("analyse.py tables", "writes the national result tables, including the explorer's"),
        ("microdata.py build", "builds the Catalan and Barcelona tables"),
        ("microdata.py quality", "checks the Catalan and Barcelona files"),
        ("microdata.py features", "builds the model's features"),
        ("microdata.py analyse", "writes the Catalan and Barcelona result tables"),
        ("microdata.py sources", "compares the Catalan file with DGT's"),
        ("severity_model.py", "fits and evaluates the Catalan severity model"),
        ("emef.py all", "estimates car-driving distance by age from the EMEF survey"),
        ("exposure_risk.py all", "computes involvement per kilometre by driver age and its ranges"),
        ("analyse.py figures", "draws the figures and captions"),
        ("build_site.py", "writes this site and docs/FINDINGS.md"),
    )
    rows = "".join(
        f"<li><code>python scripts/{command}</code> {what}.</li>" for command, what in steps
    )
    return (
        '<h2 id="reproduce">Reproducing the results</h2>'
        "<p>Every result is computed by the code in the repository from the raw published "
        "files, which are kept with their checksums and, where recorded, their download "
        "addresses. The code also holds a few values typed from cited documents: definitions "
        "such as the public-holiday calendars that separate working days, figures read from "
        "archived files, and the road-to-straight-line ratio and benchmarks of the EMEF's 2021 "
        "distance report. Run in this order, from the repository root:</p>"
        f"<ol>{rows}</ol>"
        "<p>Each page reads its numbers from the result tables, and the build stops if a table "
        "no longer supports a sentence that describes it. Automated tests rerun the checks on "
        f'every change. The <a href="{REPO_URL}#reproduce">README</a> gives the set-up and the '
        f'running times; the <a href="{DOCS_URL}/methodology.md">implementation notes</a> name '
        f'the module behind each method and the <a href="{DOCS_URL}/data_sources.md">source '
        "register</a> gives each source's known coding breaks and terms of use.</p>"
        "<p>The research questions, the choice of sources, the statistical design, the "
        "interpretation and the decision to publish each result are the author's, and so is "
        "responsibility for them. AI coding assistants were used during implementation, "
        "debugging, data-processing work and review.</p>"
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
        "cited and the date of last update to be given. The files were last updated on "
        f"omc.cat between {_date(emef_dates[0])} and {_date(emef_dates[-1])}, and the register "
        "gives each file's date. As the survey's dictionaries require, no estimate resting on "
        f"fewer than {publication.MIN_SAMPLE_OBSERVATIONS} sample observations is published.</p>"
        "<p>The census count of employed people aged 65 and over in Catalonia comes from Idescat's "
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


# The analysis pages whose technical detail lives on this page: each module may define
# ``technical_notes(captions)``, which returns one or more sections (each opening with an h2), in
# the order of the navigation.
NOTE_MODULES = (
    "long_run",
    "seasons",
    "policy",
    "drivers",
    "vehicles",
    "factors",
    "severity",
    "regional",
    "models",
)


def _technical_notes(captions: dict[str, str]) -> str:
    import importlib

    parts = []
    for name in NOTE_MODULES:
        module = importlib.import_module(f"dgt_stats.site.{name}")
        notes = getattr(module, "technical_notes", None)
        if notes is not None:
            parts.append(notes(captions))
    return "".join(parts)


def page_data(captions: dict[str, str]) -> str:
    body = summary(
        "This page defines the terms the site uses, explains how each rate is built and how a "
        "change is judged against the variation of an ordinary year, and describes the police "
        "records' coding breaks and missing values. The checks on the data, how to reproduce "
        "the results and the terms of reuse follow; the technical notes of the analysis pages "
        "come last, page by page."
    )
    body += _definitions()
    body += _rates()
    body += _records(captions)
    body += _checks()
    body += _reproduce()
    body += _reuse()
    body += _technical_notes(captions)
    body += downloads(
        [
            ("validation", "reconciliation checks"),
            ("missingness_by_year", "missing values by field and year"),
            ("dgt_audit_presence_coding", "fog and wind coding by province and year"),
        ]
    )
    return render_page(
        "data",
        "Methodology",
        "How the study's results are produced: definitions, rates, police records, checks on "
        "the data, reproduction, reuse and each page's technical notes.",
        body,
    )
