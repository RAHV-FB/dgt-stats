"""The driver risk comparison: car drivers of two age groups, or men and women, side by side.

Question: how often private-car drivers of one group are involved in injury crashes, or die in
them, compared with another group. Population: drivers of private cars in Spain (taxis and
ride-hailing cars excluded). Unit: the driver involved in an injury crash.

Two kinds of result are kept apart. Rates per licence holder and deaths per 1,000 drivers
involved are observed: counts of drivers in DGT's crash records over licence holders or over the
drivers involved, with 95% intervals for chance variation in the counts. Rates per kilometre are
estimates: DGT records no distance by the driver's age, so the kilometres come from travel
surveys under assumptions (``risk_national_rates``, ``risk_older_split``), each shown with its
95% sampling interval and with the sensitivity range over every assumption tested
(``risk_national_sensitivity``, ``risk_older_sensitivity``). The reader can change the two
assumptions that matter most; the others stay at the central choice. Involvement counts every
driver in a crash, whoever caused it; it does not measure responsibility.
"""

from __future__ import annotations

import math

import pandas as pd
from scipy import stats

from dgt_stats import edm2018
from dgt_stats.exposure_risk import national
from dgt_stats.site.components import read_table
from dgt_stats.site.numbers import (
    CENTRAL_KM,
    OLDER_CONCLUSION,
    _older_numbers,
    joint_interval,
    mc_interval,
    rate_interval,
)
from dgt_stats.site.tool_frame import tool_page

Z = stats.norm.ppf(0.975)
AGE_LABELS = {
    "18-29": "18–29",
    "30-44": "30–44",
    "45-64": "45–64",
    "65+": "65 and over",
    "65-74": "65–74",
    "75+": "75 and over",
}
REFERENCE = "45-64"
PROFILE_GROUPS = ("18-29", "30-44", "45-64", "65+")
SPLIT_GROUPS = ("65-74", "75+")


def _profile_label(method: str) -> str:
    name = method.split(": ", 1)[1]
    if method.startswith("A:"):
        return f"{name} working-day survey (central)"
    if method.startswith("A2:"):
        return name.replace(", per licence holder", ", carried per licence holder")
    return name


def _split_labels() -> dict[str, str]:
    madrid = edm2018.SURVEY_YEAR
    return {
        national.REFERENCE_SPLIT: f"As much less than at 65–74 as in Madrid in {madrid} (central)",
        national.LICENCE_SPLIT: f"Madrid's {madrid} km per licence holder, applied to Spain's "
        "licence holders",
        national.RACC_SPLIT: "An upper limit for men from the days they drive; women as at 65–74",
        "equal km per licence holder": "Equal km per licence holder at 65–74 and 75 and over "
        "(at odds with surveys of men's driving)",
    }


def _poisson(count: float, exposure: float, scale: float) -> list[float]:
    """An exact 95% interval for a rate of ``count`` events over ``exposure``, times ``scale``."""
    low = stats.chi2.ppf(0.025, 2 * count) / 2 if count > 0 else 0.0
    high = stats.chi2.ppf(0.975, 2 * count + 2) / 2
    return [low / exposure * scale, high / exposure * scale]


def _ratio(a: float, b: float, se: float) -> list[float]:
    """A ratio and its 95% interval from the standard error of its logarithm."""
    value = a / b
    return [value, value * math.exp(-Z * se), value * math.exp(Z * se)]


def _per_km(rates: pd.DataFrame, ranges: pd.DataFrame, column: str) -> dict[str, object]:
    """One per-km measure for the four age groups, under each regional age profile."""
    groups = {}
    for group in PROFILE_GROUPS:
        rows = rates[rates.group == group]
        by_profile = {}
        for _, row in rows.iterrows():
            reference = group == REFERENCE
            by_profile[row.method] = {
                "value": float(row[column]),
                "low": None if reference else float(row[f"{column}_low"]),
                "high": None if reference else float(row[f"{column}_high"]),
                "interval": None if reference else rate_interval(row, column),
            }
        low, high = ranges.loc[group, "min"], ranges.loc[group, "max"]
        groups[group] = {
            "label": AGE_LABELS[group],
            "by_profile": by_profile,
            "range": None if group == REFERENCE else [float(low), float(high)],
        }
    return groups


def _age_measures() -> list[dict[str, object]]:
    rates = read_table("risk_national_rates")
    rates = rates[rates.km_total == CENTRAL_KM]
    sensitivity = read_table("risk_national_sensitivity")
    older = _older_numbers()
    split = older["split"]
    involved_per_km = _per_km(
        rates, sensitivity.groupby("group").involved_ratio.agg(["min", "max"]), "involved_ratio"
    )
    killed_per_km = _per_km(
        rates, sensitivity.groupby("group").killed_ratio.agg(["min", "max"]), "killed_ratio"
    )
    # Ages 65-74 and 75 and over: the split of the 65-and-over kilometres between them.
    flagged = set(older["older"][older["older"].at_odds_with_mens_driving].assumption)
    for group in SPLIT_GROUPS:
        by_split = {}
        for _, row in split[split.group == group].iterrows():
            by_split[row.assumption] = {
                "value": float(row.ratio_to_45_64),
                "low": float(row.ratio_low),
                "high": float(row.ratio_high),
                "interval": joint_interval(row),
                "at_odds": row.assumption in flagged,
            }
        involved_per_km[group] = {
            "label": AGE_LABELS[group],
            "by_split": by_split,
            "range": list(older["range"][group]),
        }
    severity = read_table("risk_severity_and_licences").set_index("group")
    per_licence, killed_per_licence, killed_per_involved = {}, {}, {}
    for group, row in severity.iterrows():
        holders, involved, killed = (
            float(row.b_licence_holders),
            float(row.involved),
            float(row.killed),
        )
        per_licence[group] = {
            "label": AGE_LABELS[group],
            "value": involved / holders * 1000,
            "ci": _poisson(involved, holders, 1000),
            "counts": [involved, holders],
        }
        killed_per_licence[group] = {
            "label": AGE_LABELS[group],
            "value": killed / holders * 1_000_000,
            "ci": _poisson(killed, holders, 1_000_000),
            "counts": [killed, holders],
        }
        killed_per_involved[group] = {
            "label": AGE_LABELS[group],
            "value": float(row.killed_per_1000_involved),
            "ci": [
                float(row.killed_per_1000_involved_low),
                float(row.killed_per_1000_involved_high),
            ],
            "counts": [killed, involved],
        }
    return [
        {
            "id": "involved_per_km",
            "label": "Involved in injury crashes, per km driven",
            "kind": "estimate",
            "groups": involved_per_km,
        },
        {
            "id": "killed_per_km",
            "label": "Killed, per km driven",
            "kind": "estimate",
            "groups": killed_per_km,
        },
        {
            "id": "involved_per_licence",
            "label": "Involved in injury crashes, per 1,000 licence holders",
            "kind": "observed",
            "scale": "per 1,000 licence holders",
            "decimals": 2,
            "groups": per_licence,
            "pairs": _pairs(per_licence, poisson=True),
        },
        {
            "id": "killed_per_licence",
            "label": "Killed, per million licence holders",
            "kind": "observed",
            "scale": "per million licence holders",
            "decimals": 1,
            "groups": killed_per_licence,
            "pairs": _pairs(killed_per_licence, poisson=True),
        },
        {
            "id": "killed_per_involved",
            "label": "Killed, per 1,000 drivers involved in an injury crash",
            "kind": "observed",
            "scale": "per 1,000 drivers involved",
            "decimals": 1,
            "groups": killed_per_involved,
            "pairs": _pairs(killed_per_involved, poisson=False),
        },
    ]


def _pairs(groups: dict[str, dict], poisson: bool) -> dict[str, list[float]]:
    """The ratio of every group's rate to every other's, with a 95% interval: for rates over a
    fixed exposure (licence holders) from the event counts alone; for shares of the drivers
    involved from both counts of each share."""
    out = {}
    for a, ga in groups.items():
        for b, gb in groups.items():
            if a == b:
                continue
            (xa, na), (xb, nb) = ga["counts"], gb["counts"]
            if poisson:
                se = math.sqrt(1 / xa + 1 / xb)
            else:
                se = math.sqrt(1 / xa - 1 / na + 1 / xb - 1 / nb)
            out[f"{a}|{b}"] = _ratio(ga["value"], gb["value"], se)
    return out


def _sex_measures() -> dict[str, object]:
    rates = read_table("drivers_sex_rates")
    rates = rates[rates.scope == "car"]
    ratios = read_table("drivers_sex_ratios")
    ratios = ratios[ratios.scope == "car"].set_index(["band", "measure"])
    bands = list(dict.fromkeys(rates.band))
    bands = [band for band in bands if band == "18+"] + [band for band in bands if band != "18+"]
    columns = {
        "involved_per_licence": "involved_per_1000_licences",
        "killed_per_licence": "deaths_per_million_licences",
        "killed_per_involved": "deaths_per_1000_involved",
    }
    observed = {}
    for key, column in columns.items():
        by_band = {}
        for band in bands:
            pair = rates[rates.band == band].set_index("sex")
            ratio = ratios.loc[(band, column)]
            by_band[band] = {
                "label": str(pair.band_label.iloc[0]),
                "men": [
                    float(pair.loc["male", c]) for c in (column, f"{column}_low", f"{column}_high")
                ],
                "women": [
                    float(pair.loc["female", c])
                    for c in (column, f"{column}_low", f"{column}_high")
                ],
                "ratio": [float(ratio.ratio), float(ratio.low), float(ratio.high)],
            }
        observed[key] = by_band
    per_km = read_table("risk_sex_per_km").set_index("measure")
    km = {}
    for key, measure in (
        ("involved_per_km", "involved per km"),
        ("killed_per_km", "killed per km"),
    ):
        row = per_km.loc[measure]
        km[key] = {
            "ratio": float(row.ratio_men_to_women),
            "interval": mc_interval(row.ratio_low, row.ratio_high, row.mc_se_low, row.mc_se_high),
            "low": float(row.ratio_low),
            "high": float(row.ratio_high),
            "range": [float(row.range_low), float(row.range_high)],
        }
    years = str(rates.years.iloc[0]).replace("-", "–")
    return {"bands": bands, "observed": observed, "per_km": km, "years": years}


def driver_data() -> dict[str, object]:
    rates = read_table("risk_national_rates")
    rates = rates[rates.km_total == CENTRAL_KM]
    profiles = list(dict.fromkeys(rates.method))
    central = next(method for method in profiles if method.startswith("A:"))
    older = _older_numbers()
    madrid = edm2018.SURVEY_YEAR
    return {
        "year": national.YEAR,
        "reference": REFERENCE,
        "ages": list(AGE_LABELS),
        "age_labels": AGE_LABELS,
        "profiles": [{"value": m, "label": _profile_label(m)} for m in profiles],
        "central_profile": central,
        "splits": [{"value": k, "label": v} for k, v in _split_labels().items()],
        "central_split": national.REFERENCE_SPLIT,
        "condition": "This estimate holds only if people aged 75 and over drive as much less "
        f"than those aged 65–74 as in Madrid in {madrid}.",
        "older_conclusion": "The sensitivity range for 75 and over is "
        f"{older['range']['75+'][0]:.2f} to {older['range']['75+'][1]:.2f} times the 45–64 "
        f"rate{OLDER_CONCLUSION[older['tier']]}.",
        "age": _age_measures(),
        "sex": _sex_measures(),
    }


def describe() -> dict[str, str]:
    data = driver_data()
    return {
        "title": "Driver risk comparison",
        "what": "Two groups of car drivers side by side, by age or sex: involvement in injury "
        "crashes and deaths, per licence holder, per driver involved and per kilometre driven.",
        "coverage": f"Spain, {data['year']} (men and women: {data['sex']['years']})",
        "kind": "Observed rates with 95% intervals; per-kilometre figures are estimates that "
        "depend on assumptions about distance driven",
    }


def data_files() -> dict[str, object]:
    return {"driver-risk.json": driver_data()}


def _field(name: str, label: str, hidden: bool = False) -> str:
    return (
        f'<div class="tool-field" data-field="{name}"{" hidden" if hidden else ""}>'
        f'<label for="driver-{name}">{label}</label>'
        f'<select id="driver-{name}" name="{name}"></select></div>'
    )


def page_driver_risk(captions: dict[str, str]) -> str:
    del captions
    tool = (
        '<section class="tool" data-tool="driver-risk" data-src="tools/driver-risk.json" '
        'aria-label="Driver risk comparison" hidden><div class="tool-layout">'
        '<form class="tool-controls" data-controls>'
        '<fieldset><legend>Compare</legend><div class="tool-fields">'
        + _field("mode", "Compare")
        + _field("measure", "Measure")
        + "</div></fieldset>"
        '<fieldset><legend>Groups</legend><div class="tool-fields">'
        + _field("a", "Group A")
        + _field("b", "Group B")
        + _field("band", "Age band", hidden=True)
        + "</div></fieldset>"
        "<fieldset data-assumptions hidden><legend>Assumptions about distance driven</legend>"
        '<div class="tool-fields">'
        + _field("profile", "Age profile of the kilometres", hidden=True)
        + _field("split", "Split of the 65-and-over kilometres", hidden=True)
        + "</div></fieldset>"
        '<div class="tool-actions"><button type="button" data-reset>Reset</button></div>'
        "</form>"
        '<div class="tool-result" data-result>'
        '<p class="tool-headline" data-headline></p>'
        '<p class="tool-meaning" data-detail></p>'
        '<p class="tool-warning" data-condition hidden></p>'
        '<div class="tool-chart" data-chart></div>'
        '<p class="tool-note" data-note></p>'
        "</div></div>"
        '<p class="visually-hidden" role="status" aria-live="polite" data-status></p>'
        "</section>"
    )
    notes = (
        "<p>Involvement counts every driver in an injury crash, whoever caused it: it does not "
        "measure responsibility, which the public records do not hold. Deaths per driver "
        "involved say how often a crash kills the driver, not how often drivers crash.</p>"
        "<p>Rates per licence holder and per driver involved are observed counts, with 95% "
        "intervals for chance variation. Rates per kilometre are estimates: the kilometres "
        "driven by each age come from travel surveys, so each figure carries a 95% sampling "
        "interval and a sensitivity range, the span of every assumption tested; the range, not "
        "one assumption, says what the data establish. The assumptions are set out on the "
        '<a href="drivers.html">drivers</a> page and the <a href="data.html">methodology</a> '
        "page.</p>"
    )
    return tool_page(
        "driver-risk",
        "Driver risk comparison",
        "Car drivers of two age groups, or men and women, side by side: involvement in injury "
        "crashes and deaths per licence holder, per driver involved and per kilometre driven.",
        tool,
        notes,
        ("tools/driver-risk.js",),
    )
