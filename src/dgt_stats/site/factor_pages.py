"""The two factor models and the comparison: distraction, alcohol and drugs, and which enforcement.

Each page carries the model's parameters as a JSON block and loads ``factors.js``, a port of
:mod:`dgt_stats.factor_models`, which recomputes the deaths as the reader moves the sliders.
"""

from __future__ import annotations

import json
import math
import re

import pandas as pd

from dgt_stats import factor_models
from dgt_stats.site.components import (
    _fmt_int,
    _fmt_pct,
    _join,
    _signed_int,
    _signed_pct,
    conclusion,
    downloads,
    esc,
    key_figures,
    limits,
    read_table,
    render_page,
    table,
)

ROLE_LABELS = {"driver": "Drivers", "passenger": "Passengers", "pedestrian": "Pedestrians"}
ZONE_LABELS = {"interurban": "Interurban roads", "urban": "Urban streets"}
BOUND_LABELS = {"value": "central", "low": "low", "high": "high"}
# The police record gives each factor by crash, not by road user, so the model splits each zone's
# deaths avoided in proportion to who died there; every table by road user says so.
ROLE_NOTE = (
    ". The split by who died follows each zone's deaths: the police record gives each factor by "
    "crash, not by road user"
)
BOUNDS = factor_models.BOUNDS
# The enforcement comparison asks what share of each factor must go to save this many lives a year.
LIVES = 100
MOBILE_CHAPTER = (
    "https://www.tshandbok.no/del-2/8-kontroll-og-sanksjoner/"
    "8-14-forbud-mot-bruk-av-handholdt-mobiltelefon-i-bil/"
)
TRAFFIC_RULES = "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23514"
CAMERA_CHAPTER = "https://www.tshandbok.no/del-2/8-kontroll-og-sanksjoner/doc735/"
ALCOHOL_CHAPTER = "https://www.tshandbok.no/del-2/8-kontroll-og-sanksjoner/doc733/"
TABLES = (
    "factor_casualties",
    "factor_inputs",
    "factor_crashes",
    "factor_speed_curve",
)


def _parameters_head() -> str:
    parameters = factor_models.browser_parameters({name: read_table(name) for name in TABLES})
    block = json.dumps(parameters, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return (
        f'\n<script type="application/json" id="factor-parameters">{block}</script>'
        '\n<script src="factors.js" defer></script>'
    )


def _source(name: str, applies_to: str, text: str) -> str:
    rows = factor_models.evidence()
    row = rows[(rows.parameter == name) & (rows.applies_to == applies_to)].iloc[0]
    return f'<a href="{esc(row.url)}">{esc(text)}</a>'


def _chain(steps: list[tuple[str, str]]) -> str:
    items = "".join(f"<li><strong>{esc(title)}.</strong> {text}</li>" for title, text in steps)
    return f'<ol class="chain">{items}</ol>'


def _try(label: str, text: str) -> str:
    return (
        f'<a class="try" href="#try-it"><strong>{esc(label)}</strong><span>{esc(text)}</span>'
        '<span class="arrow" aria-hidden="true">↓</span></a>'
    )


def _deaths_frame() -> pd.DataFrame:
    return read_table("factor_deaths")


def _row(frame: pd.DataFrame, factor: str, zone: str = "all", role: str = "all") -> pd.Series:
    return frame[(frame.factor == factor) & (frame.zone == zone) & (frame.role == role)].iloc[0]


def _range(row: pd.Series) -> str:
    return f"{_signed_int(-row.avoided_low)} to {_signed_int(-row.avoided_high)}"


def _role_table(frame: pd.DataFrame, factor: str, caption: str) -> str:
    rows = []
    for zone in factor_models.ZONES:
        for role, label in ROLE_LABELS.items():
            row = _row(frame, factor, zone, role)
            rows.append(
                {
                    "Where": ZONE_LABELS[zone],
                    "Who died": label,
                    "Deaths a year, 2022–2024": _fmt_int(row.deaths),
                    "Avoided, central": _signed_int(-row.avoided),
                    "Range": _range(row),
                }
            )
    total = _row(frame, factor)
    rows.append(
        {
            "Where": "All roads",
            "Who died": "Everyone",
            "Deaths a year, 2022–2024": _fmt_int(total.deaths),
            "Avoided, central": _signed_int(-total.avoided),
            "Range": _range(total),
        }
    )
    return table(pd.DataFrame(rows), caption + ROLE_NOTE)


def _live_table(factor_group: str) -> str:
    """The table the sliders fill: deaths avoided by zone, and within it by road user."""
    rows = ""
    for zone in factor_models.ZONES:
        rows += (
            f'<tr class="group"><th scope="rowgroup" colspan="2">{esc(ZONE_LABELS[zone])}</th></tr>'
        )
        for role, label in ROLE_LABELS.items():
            rows += (
                f'<tr><th scope="row">{esc(label)}</th>'
                f'<td data-out="avoided-{zone}-{role}"></td></tr>'
            )
        rows += (
            f'<tr class="total"><th scope="row">All</th><td data-out="avoided-{zone}"></td></tr>'
        )
    return (
        '<div class="table-wrap" role="region" tabindex="0" aria-label="Deaths avoided a year">'
        '<table class="live"><caption>Deaths a year avoided at the settings above, by zone and by '
        f"who died{esc(ROLE_NOTE)}</caption>"
        '<thead><tr><th scope="col">Who died</th>'
        '<th scope="col">Deaths avoided a year</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )


def _bound_choices(labels: dict[str, str]) -> str:
    choices = "".join(
        f'<label><input type="radio" name="bound" value="{bound}"'
        f"{' checked' if bound == 'value' else ''}> {esc(text)}</label>"
        for bound, text in labels.items()
    )
    return (
        '<div class="setting"><span class="setting-label" id="bound-label">How much the factor '
        "raises the risk</span>"
        f'<div class="choices" role="radiogroup" aria-labelledby="bound-label">{choices}</div></div>'
    )


def _slider(name: str, label: str, hint: str, value: int = 100) -> str:
    return (
        f'<div class="setting"><label class="setting-label" for="slider-{name}">{esc(label)}</label>'
        f'<div class="slider"><input type="range" id="slider-{name}" data-slider="{name}" min="0" '
        f'max="100" step="5" value="{value}"><output data-out="share-{name}" for="slider-{name}">'
        f"{value}%</output></div>"
        f'<p class="hint">{esc(hint)}</p></div>'
    )


def _panel(
    mode: str,
    title: str,
    controls: str,
    results: str,
    fallback: str = "the table below gives its results with each factor removed entirely",
) -> str:
    return (
        '<div id="factor-panel" hidden>'
        f'<form id="factor-model" class="simulator" data-mode="{mode}" autocomplete="off">'
        f'<p class="simulator-title">{esc(title)}</p>'
        f'<fieldset class="road" data-state="settings"><legend>Settings</legend>{controls}'
        "</fieldset></form>"
        f"{results}</div>"
        f'<noscript><p class="note">The model needs JavaScript; {esc(fallback)}.</p></noscript>'
    )


# --------------------------------------------------------------------------- distraction


def page_distraction(captions: dict[str, str]) -> str:
    frame = _deaths_frame()
    inputs = read_table("factor_inputs").set_index(["factor", "quantity"])
    crashes = read_table("factor_crashes").set_index("factor").loc["distraction"]
    natural = read_table("factor_naturalistic").set_index("zone")
    shares = read_table("factor_recorded_shares")
    total = _row(frame, "distraction")
    inter, urban = _row(frame, "distraction", "interurban"), _row(frame, "distraction", "urban")
    presence_i = float(inputs.loc[("distraction", "presence_interurban"), "value"])
    presence_u = float(inputs.loc[("distraction", "presence_urban"), "value"])
    af = inputs.loc[("distraction", "attributable_fraction")]
    any_or = factor_models.parameter("or_distraction", "any_observable")
    any_low = factor_models.parameter("or_distraction", "any_observable", "low")
    any_high = factor_models.parameter("or_distraction", "any_observable", "high")
    phone_or = factor_models.parameter("or_distraction", "handheld_phone")
    phone_fatal = factor_models.parameter("rr_phone_use", "fatal_crashes")
    phone_fatal_low = factor_models.parameter("rr_phone_use", "fatal_crashes", "low")
    phone_fatal_high = factor_models.parameter("rr_phone_use", "fatal_crashes", "high")
    phone_damage = factor_models.parameter("rr_phone_use", "property_damage_crashes")
    injury_crashes = factor_models.parameter("injury_crashes", "all_2024")
    par = factor_models.parameter("par_distraction", "naturalistic")
    seen = factor_models.parameter("distraction_share_of_crashes", "naturalistic")
    all_share = shares[
        (shares.factor == "distraction") & (shares.zone == "all") & (shares.year == "pooled")
    ].share.iloc[0]
    by_year = shares[(shares.factor == "distraction") & (shares.zone == "all")].set_index("year")
    upper = float(natural.loc["all", "avoided"])
    as_cause = float(natural.loc["all", "record_as_cause"])
    crash_share = float(crashes.avoided) / injury_crashes
    injury_presence = float(crashes.recorded) / injury_crashes
    if not (
        inter.avoided > urban.avoided
        and total.avoided_high < as_cause < upper
        and crash_share < total.avoided / total.deaths
        and injury_presence < all_share
    ):
        raise ValueError("distraction page: the results no longer read as described")

    body = key_figures(
        [
            (
                "If no driver were distracted",
                _signed_int(-total.avoided),
                f"deaths a year, of {_fmt_int(total.deaths)}, on the police record "
                f"({_signed_int(-total.avoided_low)} to {_signed_int(-total.avoided_high)})",
            ),
            (
                "Fatal crashes with distraction",
                _fmt_pct(presence_i, 0),
                f"on interurban roads in the police record; {_fmt_pct(presence_u, 0)} in towns",
            ),
            (
                "Injury crashes it causes",
                _signed_int(-crashes.avoided),
                f"a year, of the {_fmt_int(crashes.recorded)} with distraction recorded (2024, "
                "Spain without Cataluña and País Vasco)",
            ),
            (
                "Ceiling",
                _signed_int(-upper),
                f"deaths a year if distraction caused the {_fmt_pct(par, 0)} of crashes a camera "
                f"study attributes to it (it was present in {_fmt_pct(seen, 0)})",
            ),
        ]
    )
    body += (
        '<p class="answer">If no driver on Spain\'s roads were distracted, about '
        f"{_fmt_int(total.avoided)} fewer people a year would die, "
        f"{_fmt_pct(total.avoided / total.deaths, 0)} of the {_fmt_int(total.deaths)}; "
        f"{_fmt_int(inter.avoided)} of them on interurban roads, where the police record "
        f"distraction in {_fmt_pct(presence_i, 0)} of fatal crashes, against "
        f"{_fmt_int(urban.avoided)} in towns, where they record it in "
        f"{_fmt_pct(presence_u, 0)}. Distraction is in more fatal crashes than any other recorded "
        "factor, but cameras in cars found a distracted driver only about twice as likely to "
        "crash as an attentive one, so the model counts half of those crashes as caused by it. "
        "That figure is the low end. Read the police record as a judgement that distraction "
        f"caused the crash and it is {_fmt_int(as_cause)}; if the record misses as much "
        f"distraction as the cameras saw, up to {_fmt_int(upper)}; and the risk of phone use "
        f"rises with the severity of the crash, to {phone_fatal:g} times in fatal crashes. Of the "
        "three factors on this site, distraction is the one whose toll is least certain.</p>"
    )
    body += _try("Try the model", "Choose how much distraction is removed and how risky it is.")

    body += "<h2>What the model is</h2>"
    body += _chain(
        [
            (
                "Deaths",
                "People killed within 30 days on each kind of road, as drivers, passengers and "
                "pedestrians, the mean of 2022–2024 in DGT's yearbook.",
            ),
            (
                "How often distraction is there",
                "The share of fatal crashes in which the police recorded distraction as a "
                f"concurrent factor: {_fmt_pct(all_share, 0)} on all roads in 2022 and 2024 "
                "pooled ("
                + _join(
                    [
                        f"{_fmt_pct(float(by_year.loc[y, 'share']), 0)} in {y}"
                        for y in sorted(y for y in by_year.index if y.isdigit())
                    ]
                )
                + f"), {_fmt_pct(presence_i, 0)} on interurban roads and {_fmt_pct(presence_u, 0)} "
                "on urban streets, from "
                + _source(
                    "fatal_crashes_distraction", "all_2024", "DGT's table of concurrent factors"
                )
                + ".",
            ),
            (
                "How much it raises the risk",
                "In the "
                + _source("or_distraction", "any_observable", "largest naturalistic driving study")
                + ", with cameras in drivers' own cars, a driver doing anything that took "
                f"attention off the road was {any_or:g} times as likely to crash ({any_low:g} to "
                f"{any_high:g}); on a handheld phone, {phone_or:g} times. Most of its crashes "
                "caused damage only.",
            ),
            (
                "The deaths it causes",
                f"A factor that multiplies the risk by {any_or:g} causes 1 − 1/{any_or:g} = "
                f"{_fmt_pct(float(af.value), 0)} of the crashes it is present in. Deaths × share "
                f"with distraction × {_fmt_pct(float(af.value), 0)} gives the deaths that would not "
                "happen without it.",
            ),
        ]
    )

    body += '<h2 id="try-it">Try it</h2>'
    controls = _slider(
        "distraction",
        "Share of distracted driving removed",
        "100% is the case asked about: no driver distracted. 50% is half as much distraction.",
    )
    controls += _bound_choices(
        {
            "value": f"Any distraction, {any_or:g}× (central)",
            "low": f"The low end of that risk, {any_low:g}×",
            "high": f"Every distraction a handheld phone, {phone_or:g}× (high)",
        }
    )
    results = (
        '<div class="result-head" aria-live="polite"><p class="headline">'
        '<span class="big" data-out="avoided-total"></span> deaths a year on all roads, of '
        f"{_fmt_int(total.deaths)}</p>"
        '<ul class="also"><li>Injury crashes <strong data-out="crashes-distraction"></strong> of '
        f"the {_fmt_int(crashes.recorded)} a year with distraction recorded</li></ul></div>"
        + _live_table("distraction")
    )
    body += _panel("distraction", "Remove distraction", controls, results)
    body += _role_table(
        frame,
        "distraction",
        "Deaths a year avoided if no driver were distracted, by zone and by who died; the range "
        f"runs from the low end of the risk of any distraction ({any_low:g}×) to every "
        f"distraction a handheld phone ({phone_or:g}×)",
    )

    body += "<h2>Two ways to count distraction</h2>"
    body += (
        "<p>The police record distraction in "
        f"{_fmt_pct(all_share, 0)} of fatal crashes. In the naturalistic study, where cameras "
        f"watched the driver, it was present in {_fmt_pct(seen, 0)} of crashes, and the authors "
        f"estimate that {_fmt_pct(par, 0)} of all crashes would not happen without it. The two "
        "differ because a police officer reconstructs a crash afterwards and can record "
        "distraction only when a witness, a phone record or the driver establishes it, while a "
        "camera sees every glance away. The naturalistic figure is American and counts mostly "
        "minor crashes, so the page does not use it as its estimate. It uses it as a ceiling: if "
        "the police record misses as much distraction as the cameras suggest, distraction "
        f"would account for up to {_fmt_int(upper)} deaths a year, "
        f"{_fmt_int(float(natural.loc['interurban', 'avoided']))} of them on interurban roads.</p>"
        "<p>Two more things push the police-record figure up. Officers may record distraction "
        "only where they judge it caused the crash; then none of those crashes would have "
        "happened anyway, the halving does not apply, and the figure is "
        f"{_fmt_int(as_cause)}. And the risk was measured in crashes most of which caused damage "
        "only, while "
        + _source("rr_phone_use", "fatal_crashes", "TØI's review")
        + f" puts the risk of phone use at {phone_damage:g} times in damage-only crashes and "
        f"{phone_fatal:g} times ({phone_fatal_low:g} to {phone_fatal_high:g}) in fatal ones. "
        f"So {_fmt_int(total.avoided)} is the low end of what distraction costs, and the "
        f"evidence allows anything up to about {_fmt_int(upper)}.</p>"
    )

    body += "<h2>What the model concludes</h2>"
    findings = [
        (
            "On the police record, distraction causes about one road death in "
            f"{round(total.deaths / total.avoided)}.",
            f"{_fmt_int(total.avoided)} a year ({_fmt_int(total.avoided_low)} to "
            f"{_fmt_int(total.avoided_high)}), {_fmt_pct(total.avoided / total.deaths, 0)} of "
            f"{_fmt_int(total.deaths)}; {_fmt_int(as_cause)} if the record is read as a judgement "
            f"of cause, and up to {_fmt_int(upper)} on what the cameras saw.",
        ),
        (
            "Most of the gain is on interurban roads.",
            f"{_fmt_int(inter.avoided)} of the {_fmt_int(total.avoided)}: the police record "
            f"distraction in {_fmt_pct(presence_i, 0)} of fatal crashes there, twice the share in "
            f"towns ({_fmt_pct(presence_u, 0)}), and interurban roads carry "
            f"{_fmt_pct(inter.deaths / total.deaths, 0)} of the deaths.",
        ),
        (
            "Deaths fall more than crashes, in proportion.",
            f"About {_fmt_int(crashes.avoided)} of the {_fmt_int(injury_crashes)} injury crashes "
            f"of 2024 ({_fmt_pct(crash_share, 0)}; Spain without Cataluña and País Vasco) would "
            f"not happen, against {_fmt_pct(total.avoided / total.deaths, 0)} of deaths: the "
            f"police record distraction in {_fmt_pct(injury_presence, 0)} of injury crashes but "
            f"{_fmt_pct(all_share, 0)} of fatal ones.",
        ),
    ]
    body += (
        '<ol class="conclusions">'
        + "".join(f"<li><strong>{esc(h)}</strong> {esc(t)}</li>" for h, t in findings)
        + "</ol>"
    )
    body += (
        "<p>How this compares with speed and with alcohol and drugs, and what enforcement can "
        'reach, is on the <a href="enforcement.html">enforcement page</a>.</p>'
    )
    body += downloads(
        [
            ("factor_deaths", "deaths avoided by factor, zone and road user"),
            ("factor_recorded_shares", "the police record of each factor"),
            ("factor_inputs", "the model's inputs"),
            ("factor_naturalistic", "the naturalistic ceiling"),
            ("factor_crashes", "injury crashes"),
            ("factor_evidence", "every published value, its URL and a quote"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "On the police record and the risk measured in cars, removing distraction would save "
        f"about {_fmt_int(total.avoided)} lives a year in Spain ({_fmt_int(total.avoided_low)} to "
        f"{_fmt_int(total.avoided_high)}), {_fmt_int(inter.avoided)} of them on interurban "
        f"roads, and avoid about {_fmt_int(crashes.avoided)} injury crashes. That is the low end: "
        f"read as a judgement of cause the record gives {_fmt_int(as_cause)}, the camera study "
        f"{_fmt_int(upper)}, and phone use is riskier in fatal crashes than the risk the model "
        "uses. Distraction may therefore cost as many lives as drink-driving; the evidence only "
        f"establishes that it costs at least about {_fmt_int(total.avoided_low)}."
    )
    body += limits(
        "The police record is a judgement made after the crash and covers Spain without Cataluña "
        "and País Vasco; the urban share is the difference between all roads and interurban "
        "roads, whose percentage DGT rounds. The risk comes from one American naturalistic study "
        "whose crashes mostly caused damage only; the risk of phone use is higher in fatal "
        "crashes, so the figure is if anything low. Removing a share of distraction "
        "is taken to remove the same share of its crashes. A crash with several factors counts "
        "fully here and on the other factor pages, so the factors cannot be added; the "
        "enforcement page combines them."
    )
    return render_page(
        "distraction",
        "What if no driver were distracted",
        "If nobody drove distracted, how many fewer people would die on Spain's roads, and "
        "where? The police record of fatal crashes and the risk measured with cameras in cars "
        "give the answer.",
        body,
        head=_parameters_head(),
    )


# --------------------------------------------------------------------------- alcohol and drugs


def page_impairment(captions: dict[str, str]) -> str:
    frame = _deaths_frame()
    inputs = read_table("factor_inputs").set_index(["factor", "quantity"])
    crashes = read_table("factor_crashes").set_index("factor").loc["alcohol"]
    both = _row(frame, "alcohol_drugs")
    alcohol, drugs = _row(frame, "alcohol"), _row(frame, "drugs")
    inter = _row(frame, "alcohol_drugs", "interurban")
    urban = _row(frame, "alcohol_drugs", "urban")
    presence_i = float(inputs.loc[("alcohol", "presence_interurban"), "value"])
    presence_u = float(inputs.loc[("alcohol", "presence_urban"), "value"])
    drug_share = float(inputs.loc[("drugs", "presence_interurban"), "value"])
    af_alcohol = inputs.loc[("alcohol", "attributable_fraction")]
    af_drugs = inputs.loc[("drugs", "attributable_fraction")]
    weights = factor_models.alcohol_rr_bands()
    top_weight = weights["over_1.20"][0]
    mix = factor_models.drug_rr_mix()
    analysed = factor_models.parameter("killed_drivers_analysed", "2023")
    over_limit = sum(
        factor_models.parameter("killed_drivers_bac", f"{band}_2023")
        for band in ("0.51-1.20", "1.21-2.00", "over_2.00")
    )
    pedestrians = factor_models.parameter("killed_pedestrians_positive_share", "2024")
    comparison = read_table("factor_comparison").set_index(["lever", "zone"])
    speed = comparison.loc[("speed", "all")]
    distraction = comparison.loc[("distraction", "all")]
    distraction_ceiling = float(
        read_table("factor_naturalistic").set_index("zone").loc["all", "avoided"]
    )
    if not (
        alcohol.avoided > drugs.avoided
        and inter.avoided > urban.avoided
        and alcohol.avoided > speed.avoided > distraction.avoided
        and speed.avoided_high > alcohol.avoided
    ):
        raise ValueError("alcohol page: the results no longer read as described")

    body = key_figures(
        [
            (
                "If no driver drank or took drugs",
                _signed_int(-both.avoided),
                f"deaths a year, of {_fmt_int(both.deaths)} ({_signed_int(-both.avoided_low)} to "
                f"{_signed_int(-both.avoided_high)})",
            ),
            (
                "Of which alcohol",
                _signed_int(-alcohol.avoided),
                f"and drugs without alcohol {_signed_int(-drugs.avoided)}",
            ),
            (
                "Fatal crashes with a driver over the limit",
                _fmt_pct(presence_i, 0),
                f"on interurban roads, tested crashes; {_fmt_pct(presence_u, 0)} in towns",
            ),
            (
                "Drunk drivers killed, over 1.2 g/L",
                _fmt_pct(top_weight, 0),
                "of those over the limit: most are far over it",
            ),
        ]
    )
    body += (
        '<p class="answer">If no driver on Spain\'s roads drank or took drugs, about '
        f"{_fmt_int(both.avoided)} fewer people a year would die, "
        f"{_fmt_pct(both.avoided / both.deaths, 0)} of the {_fmt_int(both.deaths)}: "
        f"{_fmt_int(alcohol.avoided)} from alcohol and {_fmt_int(drugs.avoided)} from drugs. "
        "Alcohol is present in fewer fatal crashes than distraction, "
        f"{_fmt_pct(presence_i, 0)} on interurban roads, but almost all of those deaths are "
        "caused by it, because the drunk drivers in fatal crashes are very drunk: "
        f"{_fmt_pct(top_weight, 0)} of the killed drivers over the limit had more than 1.2 g/L "
        "of alcohol in their blood, a level at which the risk of a serious crash is about "
        f"{factor_models.parameter('rr_druid_injured', 'alcohol_over_1.2'):.0f} times that of a "
        f"sober driver. {_fmt_int(inter.avoided)} of the deaths avoided are on "
        f"interurban roads and {_fmt_int(urban.avoided)} in towns.</p>"
    )
    body += _try("Try the model", "Choose how much drink- and drug-driving is removed.")

    body += "<h2>What the model is</h2>"
    body += _chain(
        [
            (
                "Deaths",
                "People killed within 30 days on each kind of road, as drivers, passengers and "
                "pedestrians, the mean of 2022–2024 in DGT's yearbook.",
            ),
            (
                "How often alcohol is there",
                "The share of fatal crashes in which a driver tested over the limit, among the "
                "crashes in which every driver was tested: "
                f"{_fmt_pct(presence_i, 0)} on interurban roads and {_fmt_pct(presence_u, 0)} on "
                "urban streets in 2022 and 2024, from "
                + _source("fatal_crashes_alcohol", "all_2024", "DGT's table of concurrent factors")
                + ". The forensic toxicology of killed drivers agrees: "
                + _source("killed_drivers_bac", "0.51-1.20_2023", "INTCF")
                + f" found {_fmt_int(over_limit)} of {_fmt_int(analysed)} killed drivers in 2023 "
                f"over 0.5 g/L, {_fmt_pct(over_limit / analysed, 0)}.",
            ),
            (
                "How much it raises the risk",
                "The "
                + _source("rr_druid_injured", "alcohol_over_1.2", "EU DRUID project")
                + " measured the risk of being seriously injured at each blood alcohol: "
                f"{factor_models.parameter('rr_druid_injured', 'alcohol_0.5-0.8'):g} times a sober "
                f"driver's at 0.5–0.8 g/L, {factor_models.parameter('rr_druid_injured', 'alcohol_0.8-1.2'):g} "
                f"at 0.8–1.2 and {factor_models.parameter('rr_druid_injured', 'alcohol_over_1.2'):g} "
                f"above 1.2. Weighted by the blood alcohol of the killed drivers, "
                f"{_fmt_pct(float(af_alcohol.value), 0)} of the fatal crashes with a drunk driver "
                "are caused by the alcohol.",
            ),
            (
                "Drugs",
                f"{_fmt_pct(drug_share, 0)} of killed drivers had a drug of abuse and no alcohol "
                "(INTCF, 2023 and 2024). Weighted by the drugs the police found in killed drivers "
                f"({_join([f'{name} {_fmt_pct(w, 0)}' for name, (w, _) in mix.items()])}) and "
                "DRUID's risk for each, "
                f"{_fmt_pct(float(af_drugs.value), 0)} of those crashes are caused by the drug.",
            ),
        ]
    )

    body += '<h2 id="try-it">Try it</h2>'
    controls = _slider(
        "alcohol",
        "Share of drink-driving removed",
        "100% is no driver over the limit; 50% is half as many.",
    )
    controls += _slider(
        "drugs",
        "Share of drug-driving removed",
        "Drugs of abuse in drivers with no alcohol. Drivers with drugs and alcohol count under "
        "alcohol if they were over the limit, and under neither if they were below it, so drugs "
        "are if anything understated.",
    )
    controls += _bound_choices(
        {
            "value": "DRUID's estimates (central)",
            "low": "The low end of DRUID's risk bands",
            "high": "The high end of DRUID's risk bands",
        }
    )
    results = (
        '<div class="result-head" aria-live="polite"><p class="headline">'
        '<span class="big" data-out="avoided-total"></span> deaths a year on all roads, of '
        f"{_fmt_int(both.deaths)}</p>"
        '<ul class="also"><li>Alcohol <strong data-out="avoided-factor-alcohol"></strong></li>'
        '<li>Drugs <strong data-out="avoided-factor-drugs"></strong></li>'
        '<li>Injury crashes with alcohol <strong data-out="crashes-alcohol"></strong> of the '
        f"{_fmt_int(crashes.recorded)} recorded</li></ul></div>" + _live_table("alcohol_drugs")
    )
    body += _panel("alcohol_drugs", "Remove drink- and drug-driving", controls, results)
    body += _role_table(
        frame,
        "alcohol_drugs",
        "Deaths a year avoided if no driver drank or took drugs, by zone and by who died; the "
        "range runs between the ends of DRUID's risk bands. In 2024, "
        f"{_fmt_int(factor_models.parameter('killed_drivers_alcohol_positive', 'all_2024'))} of "
        f"the {_fmt_int(factor_models.parameter('deaths_in_alcohol_crashes', 'all_2024'))} "
        "people killed in crashes with a drunk driver were drunk drivers themselves (DGT), so "
        "this split gives too many to the other road users",
    )

    rows = []
    for factor, label in (("alcohol", "Alcohol"), ("drugs", "Drugs without alcohol")):
        row = _row(frame, factor)
        rows.append(
            {
                "Substance": label,
                "Present": (
                    f"{_fmt_pct(presence_i, 0)} of interurban and {_fmt_pct(presence_u, 0)} of "
                    "urban fatal crashes (where every driver was tested)"
                    if factor == "alcohol"
                    else f"{_fmt_pct(drug_share, 0)} of killed drivers"
                ),
                "Share caused by it": _fmt_pct(
                    float(inputs.loc[(factor, "attributable_fraction"), "value"]), 0
                ),
                "Deaths avoided a year": _signed_int(-row.avoided),
                "Range": _range(row),
            }
        )
    body += table(pd.DataFrame(rows), "Alcohol and drugs taken apart")

    body += "<h2>What the model concludes</h2>"
    findings = [
        (
            "Alcohol is the deadliest single factor on the central estimates.",
            f"{_fmt_int(alcohol.avoided)} deaths a year ({_fmt_int(alcohol.avoided_low)} to "
            f"{_fmt_int(alcohol.avoided_high)}), against {_fmt_int(speed.avoided)} for speeding, "
            f"whose range ({_fmt_int(speed.avoided_low)} to {_fmt_int(speed.avoided_high)}) "
            f"overlaps it, and {_fmt_int(distraction.avoided)} for distraction on the police "
            f"record, which could be as high as {_fmt_int(distraction_ceiling)}. It is present in "
            "fewer fatal crashes than distraction, but nearly every one "
            f"of those deaths is caused by it, because {_fmt_pct(top_weight, 0)} of the drunk "
            "drivers killed were over 1.2 g/L.",
        ),
        (
            "Drugs add less, and less certainly.",
            f"{_fmt_int(drugs.avoided)} ({_fmt_int(drugs.avoided_low)} to "
            f"{_fmt_int(drugs.avoided_high)}): cocaine, the drug found most often, multiplies "
            f"the risk {factor_models.parameter('rr_druid_injured', 'cocaine'):g} times, but "
            f"cannabis only {factor_models.parameter('rr_druid_injured', 'cannabis'):g} times, "
            "and a positive test does not always mean impairment at the wheel.",
        ),
        (
            "Interurban roads carry most of it.",
            f"{_fmt_int(inter.avoided)} of the {_fmt_int(both.avoided)}, on {_fmt_int(inter.deaths)} "
            f"interurban deaths; {_fmt_int(urban.avoided)} on {_fmt_int(urban.deaths)} urban "
            "deaths. In towns the share of fatal crashes with a drunk driver is similar, "
            f"{_fmt_pct(presence_u, 0)}, but there are fewer deaths.",
        ),
        (
            "Removing drink-driving would also avoid about "
            f"{_fmt_int(round(float(crashes.avoided), -2))} recorded injury crashes a year.",
            f"{_fmt_int(crashes.avoided)} ({_fmt_int(crashes.avoided_low)} to "
            f"{_fmt_int(crashes.avoided_high)}) of the {_fmt_int(crashes.recorded)} injury crashes "
            "with alcohol recorded in 2024, Spain without Cataluña and País Vasco. The count is a "
            "floor, since only crashes in which drivers were tested, about two in five, can record "
            "alcohol; the share caused is taken from killed drivers, who are drunker than those in "
            "minor crashes, so it is high for those.",
        ),
    ]
    body += (
        '<ol class="conclusions">'
        + "".join(f"<li><strong>{esc(h)}</strong> {esc(t)}</li>" for h, t in findings)
        + "</ol>"
    )
    body += (
        "<p>How this compares with speed and distraction, and what enforcement can reach, is on "
        'the <a href="enforcement.html">enforcement page</a>.</p>'
    )
    body += downloads(
        [
            ("factor_deaths", "deaths avoided by factor, zone and road user"),
            ("factor_recorded_shares", "the police record of each factor"),
            ("factor_inputs", "the model's inputs"),
            ("factor_crashes", "injury crashes"),
            ("factor_evidence", "every published value, its URL and a quote"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        f"If no driver drank or took drugs, about {_fmt_int(both.avoided)} fewer people a year "
        f"would die in Spain ({_fmt_int(both.avoided_low)} to {_fmt_int(both.avoided_high)}), "
        f"{_fmt_pct(both.avoided / both.deaths, 0)} of all road deaths: "
        f"{_fmt_int(alcohol.avoided)} from alcohol and {_fmt_int(drugs.avoided)} from drugs, "
        f"{_fmt_int(inter.avoided)} of them on interurban roads. On the central estimates that "
        f"is more than speeding ({_fmt_int(speed.avoided)}, whose range reaches "
        f"{_fmt_int(speed.avoided_high)}) or distraction on the police record "
        f"({_fmt_int(distraction.avoided)}), because the drivers involved are so far over the "
        "limit that almost every one of their fatal crashes is caused by it."
    )
    body += limits(
        "The police record of alcohol covers only the fatal crashes in which every driver was "
        "tested, in Spain without Cataluña and País Vasco; the urban share is derived from the "
        "rounded interurban percentage. DRUID measured the risk of serious injury, which is "
        "lower than the risk of death it also reports, so the attributable share is if anything "
        "low. Drug positives count any detection, which overstates impairment, most for "
        "cannabis; drivers with drugs and alcohol below the limit are counted nowhere, which "
        "understates drugs; and the drug share is measured on killed drivers and applied to "
        "every death, pedestrians included, which likely overstates it for pedestrians struck by "
        "drivers who survived. Psychoactive medicines, found in "
        f"{_fmt_pct(factor_models.parameter('killed_drivers_medicines_share', '2024'), 0)} "
        "of killed drivers in 2024, are left out, as is the impairment of pedestrians "
        f"themselves ({_fmt_pct(pedestrians, 0)} of those killed tested positive), which "
        "enforcement on drivers does not reach."
    )
    return render_page(
        "alcohol-drugs",
        "What if no driver drank or took drugs",
        "If nobody drove after drinking or taking drugs, how many fewer people would die on "
        "Spain's roads, and where? The police record, the forensic toxicology of killed drivers "
        "and the EU's measured risks give the answer.",
        body,
        head=_parameters_head(),
    )


# --------------------------------------------------------------------------- which enforcement

# The enforcement studies the comparison cites, by the register's scope: the lever each acts on,
# the measure, and what was counted.
ENFORCEMENT_STUDIES: dict[str, tuple[str, str, str]] = {
    "fixed_cameras": ("Speeding", "Fixed speed cameras", "Fatal crashes near the camera"),
    "section_control": (
        "Speeding",
        "Section control: the average speed over a stretch",
        "Crashes killing or seriously injuring someone on the stretch",
    ),
    "mobile_cameras": (
        "Speeding",
        "Mobile speed cameras",
        "Crashes killing or seriously injuring someone where they operate",
    ),
    "manned_speed_checks": (
        "Speeding",
        "Police speed checks at the roadside",
        "Crashes killing or seriously injuring someone",
    ),
    "more_speed_enforcement": (
        "Speeding",
        "More of the speed enforcement already in place",
        "People killed or seriously injured",
    ),
    "barcelona_cameras": (
        "Speeding",
        "Fixed cameras on Barcelona's ring roads (Spain)",
        "All injury crashes on the ring roads; no change on the city's arterial streets",
    ),
    "checkpoints_alcohol_crashes": (
        "Alcohol and drugs",
        "Breath-test checkpoints",
        "Alcohol-related crashes",
    ),
    "checkpoints_all_crashes": (
        "Alcohol and drugs",
        "Breath-test checkpoints, studies with a control group",
        "All crashes",
    ),
    "us_checkpoints_deaths": (
        "Alcohol and drugs",
        "Publicised sobriety checkpoints (US): median and middle half of ten studies",
        "Deaths in alcohol-involved crashes",
    ),
    "dui_patrols": (
        "Alcohol and drugs",
        "Patrols stopping drivers the police suspect",
        "Fatal crashes",
    ),
    "breath_tests_tripled": (
        "Alcohol and drugs",
        "Three times as many random breath tests: Norway's planning assumption, not a measurement",
        "Fatal crashes",
    ),
    "drug_detection_risk": (
        "Alcohol and drugs",
        "A 60% higher chance that a drug-driver is caught (Norway): the prediction of a curve "
        "fitted to two roadside surveys",
        "Drug-impaired driving, not crashes: no study has measured random drug tests on crashes",
    ),
    "handheld_ban_crashes": ("Distraction", "Bans on handheld phones (US)", "All crashes"),
    "texting_ban_crashes": ("Distraction", "Bans on texting (US)", "All crashes"),
    "phone_ban_driver_deaths": (
        "Distraction",
        "Handheld bans the police can enforce on their own (US)",
        "Driver deaths",
    ),
    "phone_ban_total_deaths": (
        "Distraction",
        "Comprehensive handheld bans (US)",
        "All deaths in crashes involving passenger vehicles",
    ),
    "texting_ban_primary_deaths": (
        "Distraction",
        "Texting bans for all drivers the police can enforce on their own (US)",
        "All deaths",
    ),
}


def _comparison_table(comparison: pd.DataFrame) -> str:
    rows = []
    for lever, label in {**factor_models.LEVERS, "combined": "All three together"}.items():
        row = {"Lever": label}
        for zone, zone_label in (
            ("interurban", "Interurban"),
            ("urban", "Urban"),
            ("all", "All roads"),
        ):
            r = comparison[(comparison.lever == lever) & (comparison.zone == zone)].iloc[0]
            row[zone_label] = (
                f"{_signed_int(-r.avoided)} ({_signed_int(-r.avoided_low)} to {_signed_int(-r.avoided_high)})"
            )
        row["Share of deaths"] = _fmt_pct(
            float(
                comparison[(comparison.lever == lever) & (comparison.zone == "all")].share.iloc[0]
            ),
            0,
        )
        rows.append(row)
    return table(
        pd.DataFrame(rows),
        "Deaths a year avoided if each factor were removed entirely, with the range from the "
        "risk evidence: speeding is every driver above the limit slowing to it (urban streets "
        "between none and all at 30 km/h); alcohol and drugs, and distraction, are no driver "
        "affected; all three together removes the overlap",
    )


def _live_comparison() -> str:
    rows = ""
    for lever, label in {**factor_models.LEVERS, "combined": "All three together"}.items():
        cls = ' class="total"' if lever == "combined" else ""
        rows += (
            f'<tr{cls}><th scope="row">{esc(label)}</th>'
            + "".join(
                f'<td data-out="lever-{lever}-{zone}"></td>'
                for zone in ("interurban", "urban", "all")
            )
            + "</tr>"
        )
    return (
        '<div class="table-wrap" role="region" tabindex="0" aria-label="Deaths avoided by lever">'
        '<table class="live"><caption>Deaths a year avoided at the settings above</caption>'
        '<thead><tr><th scope="col">Lever</th><th scope="col">Interurban roads</th>'
        '<th scope="col">Urban streets</th><th scope="col">All roads</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )


def page_enforcement(captions: dict[str, str]) -> str:
    comparison = read_table("factor_comparison")
    curve = read_table("factor_speed_curve")
    presets = read_table("simulator_presets").set_index("scenario")
    speeds = read_table("simulator_speed_sites").set_index("site")
    baseline = read_table("simulator_baseline").set_index("road_class")
    natural = read_table("factor_naturalistic").set_index("zone")

    def cell(lever: str, zone: str = "all") -> pd.Series:
        return comparison[(comparison.lever == lever) & (comparison.zone == zone)].iloc[0]

    speed, impaired, distracted, together = (
        cell("speed"),
        cell("alcohol_drugs"),
        cell("distraction"),
        cell("combined"),
    )
    conventional = presets.loc["conventional_comply"]
    over_limit = factor_models.parameter("drivers_over_limit_share", "roadside_2024")
    handheld = 1 - factor_models.parameter("drivers_not_using_handheld_share", "baseline_2021")
    speeders = 1 - float(speeds.loc["conventional", "share_within_limit"])
    fastest = float(speeds.loc["conventional", "v85"])
    alcohol_share = factor_models.presence("alcohol", "interurban")
    distraction_share = factor_models.presence("distraction", "interurban")
    breath_tests = factor_models.parameter("alcohol_tests", "atgc_2024")
    breath_positive = factor_models.parameter(
        "alcohol_tests_preventive_positive_share", "atgc_2024"
    )
    drug_tests = factor_models.parameter("drug_tests", "atgc_2024")
    fines = factor_models.parameter("traffic_fines", "dgt_2024")
    checkpoint_studies = factor_models.parameter("checkpoint_studies", "alcohol")
    level_studies = factor_models.parameter("enforcement_level_studies", "alcohol")
    speed_fines = factor_models.parameter("traffic_fines_speed_share", "dgt_2024")
    killed_over_limit = sum(
        factor_models.parameter("killed_drivers_bac", f"{band}_2023")
        for band in ("0.51-1.20", "1.21-2.00", "over_2.00")
    ) / factor_models.parameter("killed_drivers_analysed", "2023")
    killed_drugs = factor_models.drug_share()
    ceiling = float(natural.loc["all", "avoided"])
    other_roads = float(baseline.loc["other_interurban", "deaths"])
    urban_alcohol = cell("alcohol_drugs", "urban")
    urban_speed = cell("speed", "urban")
    # The share of urban deaths on 30 km/h streets at which speed would overtake alcohol and drugs
    # in towns: the urban speed figure runs from all deaths at 50 (central) to all at 30 (high).
    urban_30_tipping = (urban_alcohol.avoided - urban_speed.avoided) / (
        urban_speed.avoided_high - urban_speed.avoided
    )
    if not (impaired.avoided > speed.avoided > distracted.avoided):
        raise ValueError("enforcement page: the ranking no longer reads as described")
    if not (speed.avoided_high > impaired.avoided_low and ceiling > impaired.avoided):
        raise ValueError("enforcement page: the overlaps the page describes have changed")
    if not all(
        cell(lever, "interurban").avoided > cell(lever, "urban").avoided
        for lever in factor_models.LEVERS
    ):
        raise ValueError("enforcement page: interurban roads no longer lead for every lever")
    if not 0 < urban_30_tipping < 1:
        raise ValueError("enforcement page: the town ranking no longer depends on the street mix")
    interurban_shares = [
        float(cell(lever, "interurban").avoided / cell(lever, "all").avoided)
        for lever in factor_models.LEVERS
    ]

    body = key_figures(
        [
            (
                "No drink- or drug-driving",
                _signed_int(-impaired.avoided),
                f"deaths a year ({_signed_int(-impaired.avoided_low)} to "
                f"{_signed_int(-impaired.avoided_high)})",
            ),
            (
                "Every driver at the limit",
                _signed_int(-speed.avoided),
                f"deaths a year ({_signed_int(-speed.avoided_low)} to "
                f"{_signed_int(-speed.avoided_high)}); "
                f"{_signed_int(-cell('speed', 'interurban').avoided)} on interurban roads",
            ),
            (
                "No distracted driving",
                _signed_int(-distracted.avoided),
                f"deaths a year on the police record ({_signed_int(-distracted.avoided_low)} to "
                f"{_signed_int(-distracted.avoided_high)}); up to {_signed_int(-ceiling)}",
            ),
            (
                "All three together",
                _signed_int(-together.avoided),
                f"deaths a year, {_fmt_pct(float(together.share), 0)} of "
                f"{_fmt_int(together.deaths)}; not the sum, because crashes share factors",
            ),
        ]
    )
    body += (
        '<p class="answer">On the central estimates, removing drink- and drug-driving would save '
        f"the most lives, about {_fmt_int(impaired.avoided)} a year, then every driver keeping to "
        f"the limit, about {_fmt_int(speed.avoided)}, then ending distraction, about "
        f"{_fmt_int(distracted.avoided)} on the police record. The first two overlap within their "
        "ranges, and distraction's figure is the least certain: it could be as high as "
        f"{_fmt_int(ceiling)}. For both drink-driving and speeding, more enforcement goes with "
        "fewer crashes, but the evidence is more consistent for drink-driving: breath-test "
        f"checkpoints, the most studied measure here ({checkpoint_studies:.0f} studies), cut "
        f"alcohol-related crashes by {_fall('checkpoints_alcohol_crashes')} across the areas "
        "where they run, and work better the more often they run. Automatic speed cameras show "
        f"larger effects, {_point('section_control')} to {_point('fixed_cameras')} fewer fatal or "
        "serious crashes in international reviews, but only on the stretches they cover. Phone "
        "bans have not "
        "measurably changed total deaths. So higher enforcement against drink- and drug-driving "
        "has the strongest case for cutting total deaths, with speed cameras close behind; for "
        f"every lever {_fmt_pct(min(interurban_shares), 0)} to "
        f"{_fmt_pct(max(interurban_shares), 0)} of the gain is on interurban roads.</p>"
    )
    body += _try("Compare the levers", "Remove a share of each factor and see the deaths saved.")

    body += '<h2 id="ceiling">The ceiling: each factor removed</h2>'
    body += (
        "<p>Each lever is taken to its limit with its own model: the "
        '<a href="simulator.html">speed-law simulator</a> with every driver above the limit '
        'slowing to it, and the <a href="alcohol-drugs.html">alcohol and drugs</a> and '
        '<a href="distraction.html">distraction</a> models with no driver affected. The ranges '
        "come from each model's risk evidence; distraction's police-record figure is its low "
        f"end, and a camera study puts its ceiling at {_fmt_int(ceiling)}. The three cannot be "
        "added: a crash with a drunk, speeding driver is avoided once, not twice. Removing all "
        "three together, if they act independently, avoids "
        f"{_fmt_int(together.avoided)} deaths a year, {_fmt_pct(float(together.share), 0)} of "
        "the total; alcohol and speed often go together, so the true combined figure is if "
        "anything lower.</p>"
    )
    body += _comparison_table(comparison)

    body += '<h2 id="try-it">Try it</h2>'
    controls = _slider(
        "speed",
        "Speeding: share of drivers above the limit who slow to it",
        "On every kind of road, at today's limits. The simulator sets each road apart.",
    )
    controls += _slider(
        "alcohol_drugs",
        "Alcohol and drugs: share of drink- and drug-driving removed",
        "The same share of each.",
    )
    controls += _slider("distraction", "Distraction: share of distracted driving removed", "")
    controls += _bound_choices(
        {
            "value": "Central estimates",
            "low": "Low ends of the risk evidence",
            "high": "High ends (for distraction, every distraction a handheld phone)",
        }
    )
    controls += (
        '<div class="setting"><span class="setting-label">Set all three</span>'
        '<div class="choices">'
        '<button type="button" class="preset-like" data-set="100">Each removed entirely</button>'
        '<button type="button" class="preset-like" data-set="50">Each halved</button>'
        '<button type="button" class="preset-like" data-set="25">A quarter of each</button>'
        "</div></div>"
    )
    results = (
        '<div class="result-head" aria-live="polite"><p class="headline">'
        '<span class="big" data-out="lever-combined-all"></span> deaths a year with all three, '
        f"of {_fmt_int(together.deaths)}</p>"
        '<p class="also-line">Largest first: <strong data-out="ranking"></strong></p></div>'
        + _live_comparison()
    )
    body += _panel(
        "compare",
        "Compare the three levers",
        controls,
        results,
        fallback="the table above, under 'The ceiling: each factor removed', gives its results "
        "with each factor removed entirely",
    )

    body += "<h2>How concentrated each problem is</h2>"
    rows = [
        {
            "Factor": "Alcohol",
            "Drivers on the road": f"{_fmt_pct(over_limit, 1)} over the limit (random roadside "
            "tests, 2024)",
            "Interurban fatal crashes": f"{_fmt_pct(alcohol_share, 0)} (where every driver was "
            "tested)",
            "Risk once present": f"about "
            f"{factor_models.parameter('rr_druid_injured', 'alcohol_over_1.2'):.0f}× above 1.2 g/L",
        },
        {
            "Factor": "Speeding",
            "Drivers on the road": f"{_fmt_pct(speeders, 0)} of cars above 90 km/h on "
            f"conventional roads, the fastest 15% at {fastest:.0f} km/h or more (radar, 2022)",
            "Interurban fatal crashes": _fmt_pct(factor_models.presence("speed", "interurban"), 0)
            + " recorded as inappropriate speed",
            "Risk once present": "rises with every km/h (Power Model)",
        },
        {
            "Factor": "Distraction",
            "Drivers on the road": f"{_fmt_pct(handheld, 0)} holding a phone or device "
            "(roadside observation, 2021)",
            "Interurban fatal crashes": _fmt_pct(distraction_share, 0),
            "Risk once present": f"{factor_models.parameter('or_distraction', 'any_observable'):g}×; "
            f"{factor_models.parameter('or_distraction', 'handheld_phone'):g}× on a handheld "
            "phone, more in fatal crashes",
        },
    ]
    body += table(
        pd.DataFrame(rows),
        "How common each behaviour is on the road, how often it is found in fatal crashes, and "
        "how much it raises the risk",
    )
    body += (
        "<p>The three problems have different shapes. Drink-driving is rare on the road, "
        f"{_fmt_pct(over_limit, 1)} of drivers stopped at random, but each drunk driver is very "
        "dangerous, so a small group causes a large share of deaths. The Guardia Civil carried "
        f"out {breath_tests / 1e6:.1f} million breath tests in 2024 on the roads it polices, "
        "which leave out Cataluña, País Vasco and towns with their own police "
        + _source("alcohol_tests", "atgc_2024", "(DGT)")
        + f"; {_fmt_pct(breath_positive, 0)} of its routine tests were positive. Drug tests are "
        f"far rarer, {_fmt_int(drug_tests)}, one for every "
        f"{round(breath_tests / drug_tests)} breath tests, although drugs without alcohol were "
        f"found in {_fmt_pct(killed_drugs, 0)} of killed drivers against "
        f"{_fmt_pct(killed_over_limit, 0)} over the alcohol limit (INTCF). Speeding is "
        f"widespread: {_fmt_pct(speeders, 0)} of cars on conventional roads are over 90 km/h and "
        f"the fastest 15% go at {fastest:.0f} km/h or more, and under the Power Model the "
        "fastest carry most of the gain. Distraction is common, "
        f"{_fmt_pct(handheld, 0)} of drivers are seen holding a device, and it is the hardest "
        "of the three to detect from outside the car.</p>"
    )

    needed = {
        lever: {bound: factor_models.share_needed(curve, lever, LIVES, bound) for bound in BOUNDS}
        for lever in factor_models.LEVERS
    }

    if any(math.isnan(share) for shares in needed.values() for share in shares.values()):
        raise ValueError(f"enforcement page: some lever cannot save {LIVES} lives a year")

    def need(lever: str) -> str:
        shares = needed[lever]
        low, high = sorted((shares["low"], shares["high"]))
        ends = (_fmt_pct(low, 0), _fmt_pct(high, 0))
        spread = f" ({ends[0]} to {ends[1]})" if ends[0] != ends[1] else ""
        return f"about {_fmt_pct(shares['value'], 0)}{spread}"

    body += "<h2>How far enforcement reaches each</h2>"
    body += (
        f"<p>To save {LIVES} lives a year, enforcement would have to remove "
        f"{need('alcohol_drugs')} of drink- and drug-driving, {need('speed')} of speeding (that "
        f"share of the drivers above the limit slowing to it), or {need('distraction')} of "
        "distracted driving on the police record; the ranges come from the risk evidence. The "
        "studies below are the best available on each lever. They measure what an enforcement "
        "measure did to crashes where it was tried, not how much of the behaviour it removed, "
        "and all but one are from outside Spain.</p>"
    )
    body += _enforcement_evidence()
    body += (
        "<p><strong>Speed.</strong> Automatic cameras show the largest effects, where they "
        f"stand: fatal crashes fall by {_fall('fixed_cameras')} near fixed cameras, mostly "
        "measured within half a kilometre to a kilometre of them, and crashes killing or "
        f"seriously injuring someone by {_fall('section_control')} on section-controlled "
        f'stretches (<a href="{esc(CAMERA_CHAPTER)}">TØI, ch. 8.2</a>). Two Spanish studies from '
        "Barcelona (Pérez et al. 2007; Novoa et al. 2010) are among those pooled; the later "
        f"found crashes on the city's ring roads fell by {_fall('barcelona_cameras')}, with no "
        "change on its arterial streets. Spain already has fixed and section cameras: "
        f"{_fmt_pct(speed_fines, 0)} of DGT's {fines / 1e6:.1f} million fines in 2024 were for "
        "speed, issued by the Guardia Civil, fixed and section cameras and helicopters "
        + _source("traffic_fines_speed_share", "dgt_2024", "(DGT)")
        + ". How much more a new camera would save depends on how many deaths happen on the "
        "stretches it covers, which DGT's public data do not show. More hours of speed checks go "
        "with fewer crashes, more so for fatal crashes, in TØI's dose-response curves, but the "
        "studies vary widely: pooled, more of the enforcement already in place changed the "
        f"number killed or seriously injured by {_change('more_speed_enforcement')}.</p>"
        "<p><strong>Alcohol and drugs.</strong> Breath-test checkpoints are the most studied "
        f"measure on this page: across {checkpoint_studies:.0f} studies, alcohol-related crashes "
        "fell by "
        f"{_fall('checkpoints_alcohol_crashes')} in the areas where they ran, and all crashes by "
        f"{_fall('checkpoints_all_crashes')} in the studies with a control group. More is "
        "better: the effect grows with how often checkpoints run, testing every driver stopped "
        f"works better than testing only on suspicion, and of {level_studies:.0f} studies of how "
        "much enforcement there was, most of them American, all but one found more enforcement "
        "went with fewer crashes "
        f'(<a href="{esc(ALCOHOL_CHAPTER)}">TØI, ch. 8.7</a>). How much more Spain would gain '
        f"from its {breath_tests / 1e6:.1f} million tests a year has not been measured; "
        "Norway's planners assume that three times as many random tests would cut fatal crashes "
        f"by {_fall('breath_tests_tripled')}, an assumption rather than a measurement. Patrols "
        "stopping only the drivers the police suspect showed no clear effect, "
        f"{_change('dui_patrols')} in fatal crashes. For drugs no study has measured what random "
        "testing does to crashes; a curve fitted to two Norwegian roadside surveys predicts that "
        "a 60% higher chance of being caught would cut drug-impaired driving by "
        f"{_fall('drug_detection_risk')}.</p>"
        "<p><strong>Distraction.</strong> Bans on handheld phones changed crashes by "
        f"{_change('handheld_ban_crashes')}, not a significant change, and bans on texting went "
        f"with {_change('texting_ban_crashes')}. Comprehensive handheld bans went with "
        f"{_fall('phone_ban_driver_deaths')} fewer driver deaths, also where the police could "
        "enforce them on their own, but total deaths changed by "
        f"{_change('phone_ban_total_deaths')}, and after texting bans the police could enforce "
        f"on their own by {_change('texting_ban_primary_deaths')}: both intervals include no "
        "change. Police enforcement of a ban has been shown to reduce handheld phone use, but "
        "its effect on crashes varies between studies and is uncertain "
        f'(<a href="{esc(MOBILE_CHAPTER)}">TØI, ch. 8.14</a>). Spain already bans using a '
        "phone at the wheel unless hands-free "
        f'(<a href="{esc(TRAFFIC_RULES)}">Reglamento General de Circulación, art. 18.2</a>).</p>'
    )

    body += "<h2>Where the gains are</h2>"
    zone_rows = []
    for lever, label in factor_models.LEVERS.items():
        inter, urb = cell(lever, "interurban"), cell(lever, "urban")
        zone_rows.append(
            {
                "Lever": label,
                "Interurban roads": _signed_int(-inter.avoided),
                "Urban streets": _signed_int(-urb.avoided),
                "Interurban share of the gain": _fmt_pct(
                    float(inter.avoided / (inter.avoided + urb.avoided)), 0
                ),
            }
        )
    body += table(pd.DataFrame(zone_rows), "Deaths a year avoided, factor removed, by zone")
    body += (
        f"<p>For every lever {_fmt_pct(min(interurban_shares), 0)} to "
        f"{_fmt_pct(max(interurban_shares), 0)} of the gain is on interurban roads, which carry "
        f"{_fmt_pct(float(cell('speed', 'interurban').deaths / together.deaths), 0)} of deaths. "
        "For speed the prize there is on conventional roads: everyone keeping to 90 km/h on them "
        f"saves {_fmt_int(-conventional.deaths_change)} of the "
        f"{_fmt_int(cell('speed', 'interurban').avoided)} interurban lives full compliance saves. "
        "Cameras reach it only on the stretches they cover: section control along whole "
        "stretches, a fixed camera about a kilometre. The speed figure leaves out the "
        f"{_fmt_int(other_roads)} deaths a year on other interurban roads, where no speeds were "
        "measured. In towns alcohol and drugs lead on the central estimates, "
        f"{_fmt_int(urban_alcohol.avoided)} lives against {_fmt_int(urban_speed.avoided)} for "
        f"speed and {_fmt_int(cell('distraction', 'urban').avoided)} for distraction. But the "
        "urban speed figure takes every urban death to be on a street at 50 km/h, the smaller "
        "effect, because DGT does not say on which streets they happen: if "
        f"{_fmt_pct(urban_30_tipping, 0)} or more were on streets at 30 km/h, speed would lead "
        "in towns too. At the low end of the evidence the urban speed effect is 0.</p>"
    )
    body += downloads(
        [
            ("factor_comparison", "the three levers by zone"),
            ("factor_speed_curve", "speed compliance from none to everyone"),
            ("factor_deaths", "alcohol, drugs and distraction by zone and road user"),
            ("factor_evidence", "every published value and study, its URL and a quote"),
        ]
    )

    body += "<h2>Conclusion</h2>"
    body += conclusion(
        _enforcement_conclusion(
            impaired,
            speed,
            distracted,
            ceiling,
            needed,
            {
                "over_limit": over_limit,
                "breath_tests": breath_tests,
                "drug_tests": drug_tests,
                "killed_drugs": killed_drugs,
                "killed_over_limit": killed_over_limit,
            },
        )
    )
    body += limits(
        "Each lever uses its own model, so the comparison inherits each one's limits: the speed "
        "model applies international dose-response evidence to measured Spanish speeds on "
        "autopistas, autovías and conventional roads; the alcohol, drug and distraction models "
        "apply measured risks to the police record of fatal crashes. Urban speed is a range "
        "because DGT does not split urban deaths by the limit of the street. The combined "
        "figure assumes the factors act independently. Removing a share of a factor is not the "
        "same as an enforcement measure: the studies above report how crashes changed where a "
        "measure was tried, mostly outside Spain, not how much of the factor it removed, so the "
        "two are set side by side rather than combined."
    )
    return render_page(
        "enforcement",
        "Which enforcement would save most",
        "Speed, alcohol and drugs, distraction: how many deaths each would save if enforcement "
        "removed it, how far enforcement can actually reach each, and where the gains are.",
        body,
        head=_parameters_head(),
    )


def _short_source(source: str) -> str:
    """A citation short enough for a table cell: 'TØI handbook, ch. 8.2 (2023)', 'Novoa et al. 2010'."""
    handbook = re.search(r"ch\. (\d+\.\d+).*revision (\d{4})", source)
    if "Trafikksikkerhetshåndboken" in source and handbook:
        return f"TØI handbook, ch. {handbook[1]} ({handbook[2]})"
    paper = re.match(r"([^\s,]+)[^(]*\((\d{4})\)", source)
    if paper:
        return f"{paper[1]} et al. {paper[2]}"
    raise ValueError(f"no short form for the source {source!r}")


def _enforcement_evidence() -> str:
    rows = factor_models.evidence()
    rows = rows[rows.parameter == "enforcement_effect"]
    if rows.empty:
        return ""
    missing = set(rows.applies_to) ^ set(ENFORCEMENT_STUDIES)
    if missing:
        raise ValueError(f"enforcement studies without a description or a register row: {missing}")
    body = ""
    current = None
    for row in rows.itertuples():
        lever, measure, outcome = ENFORCEMENT_STUDIES[row.applies_to]
        if lever != current:
            body += f'<tr class="group"><th scope="rowgroup" colspan="4">{esc(lever)}</th></tr>'
            current = lever
        # A rate ratio of 0.93 is a 7% fall: every effect is shown as a change.
        shift = 1.0 if row.unit == "rate_ratio" else 0.0
        interval = (
            ""
            if pd.isna(row.low)
            else f" ({_signed_pct_plain(row.low - shift)} to {_signed_pct_plain(row.high - shift)})"
        )
        body += (
            f'<tr><th scope="row" class="wrap">{esc(measure)}</th>'
            f"<td>{_signed_pct_plain(row.value - shift)}{interval}</td>"
            f'<td class="wrap">{esc(outcome)}</td>'
            f'<td class="wrap"><a href="{esc(row.url)}" title="{esc(row.source)}">'
            f"{esc(_short_source(row.source))}</a></td></tr>"
        )
    head = (
        '<th scope="col">Measure</th><th scope="col">Change</th>'
        '<th scope="col" class="wrap">In</th><th scope="col" class="wrap">Source</th>'
    )
    return (
        '<div class="table-wrap" role="region" tabindex="0" aria-label="Enforcement studies">'
        "<table><caption>What enforcement measures achieved where they were evaluated: the change "
        "in crashes or deaths, with its interval</caption>"
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _signed_pct_plain(value: float) -> str:
    return _signed_pct(float(value), 0)


def _study(name: str) -> tuple[float, float, float]:
    """An enforcement study's change, low and high from the register; a rate ratio as a change."""
    rows = factor_models.evidence()
    row = rows[(rows.parameter == "enforcement_effect") & (rows.applies_to == name)].iloc[0]
    shift = 1.0 if row.unit == "rate_ratio" else 0.0
    return tuple(float(v) - shift for v in (row.value, row.low, row.high))


def _change(name: str) -> str:
    """A study's signed change with its interval: '−47% (−63% to −23%)'."""
    value, low, high = _study(name)
    if math.isnan(low):
        return _signed_pct_plain(value)
    return f"{_signed_pct_plain(value)} ({_signed_pct_plain(low)} to {_signed_pct_plain(high)})"


def _fall(name: str) -> str:
    """A study's fall in words, smaller end first: '47% (23% to 63%)'."""
    value, low, high = _study(name)
    if value > 0 or (not math.isnan(low) and high > 0):
        raise ValueError(f"{name}: not a fall; use _change")
    text = _fmt_pct(abs(value), 0)
    if math.isnan(low):
        return text
    return f"{text} ({_fmt_pct(abs(high), 0)} to {_fmt_pct(abs(low), 0)})"


def _point(name: str) -> str:
    """A study's fall without its interval: '47%'."""
    return _fall(name).split(" (")[0]


def _enforcement_conclusion(impaired, speed, distracted, ceiling, needed, facts) -> str:
    return (
        "Higher enforcement against drink- and drug-driving has the strongest case for cutting "
        "total deaths. It is the largest prize on the central estimates, about "
        f"{_fmt_int(impaired.avoided)} deaths a year, and saving {LIVES} takes removing about "
        f"{_fmt_pct(needed['alcohol_drugs']['value'], 0)} of it; it is concentrated in a few "
        f"drivers, {_fmt_pct(facts['over_limit'], 1)} of those stopped at random; and the "
        "evidence that more enforcement brings fewer crashes is the most consistent, from "
        "checkpoints that work across the areas where they run and work better the more often "
        "they run. Drug testing is the thinnest part of it, one test for every "
        f"{round(facts['breath_tests'] / facts['drug_tests'])} breath tests although drugs "
        f"without alcohol were found in {_fmt_pct(facts['killed_drugs'], 0)} of killed drivers, "
        "but no study has measured what more of it would do to crashes. Speed is close behind: "
        f"{_fmt_int(speed.avoided)} a year ({_fmt_int(speed.avoided_low)} to "
        f"{_fmt_int(speed.avoided_high)}), {_fmt_pct(needed['speed']['value'], 0)} of speeding to "
        f"save {LIVES}, and automatic cameras have the largest effects of any measure here, "
        f"{_point('section_control')} to {_point('fixed_cameras')} fewer fatal or serious "
        "crashes near them, but only on the stretches they cover, so the gain depends on placing "
        "them where people die: interurban and above all conventional roads. Distraction is the "
        "least certain on both counts: its toll could be anywhere from about "
        f"{_fmt_int(distracted.avoided_low)} to {_fmt_int(ceiling)} deaths a year, and phone bans "
        "have not measurably changed total deaths. For all three, most of the gain is on "
        "interurban roads; in towns, on the central estimates, it is drink- and drug-driving."
    )
