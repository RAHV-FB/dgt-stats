"""What if no driver were distracted, or no driver drank or took drugs? Deaths attributable to each.

The speed-law simulator (:mod:`dgt_stats.simulator`) answers the question for speed: what follows if
every driver above the limit kept to it. This module asks the same of distraction and of alcohol
and drugs, so that the three can be compared on the same deaths.

**The method: the attributable fraction among the crashes.** A factor causes only part of the
crashes it is present in: a distracted driver crashes twice as often as an attentive one, so half
of the crashes of distracted drivers would have happened anyway. If a factor is present in a share
``s`` of fatal crashes and multiplies the risk of a fatal crash by ``RR``, the share of all deaths
that would not happen without it is ``s · (1 − 1 / RR)`` (Miettinen's formula for the attributable
fraction among cases). Removing a share ``x`` of the factor, rather than all of it, removes ``x`` of
those deaths. For every zone and road user::

    deaths avoided = x · deaths · s_zone · (1 − 1 / RR)

**Where each number comes from.** Every published value is read from
``data/raw/evidence/factor_parameters.csv``, one row per value with its source, its place in the
source, the URL and a verbatim quote.

- *Deaths*: people killed within 30 days by zone and road user (driver, passenger, pedestrian), the
  mean of 2022–2024 in DGT's yearbook table 2.2 (:func:`casualties`).
- *How often each factor is present*: the share of fatal crashes in which the police recorded it,
  from DGT's yearly table of concurrent factors (Tabla 50) for distraction, alcohol and speed, all
  roads and interurban roads, Spain without Cataluña and País Vasco. Urban shares are the
  difference between the two (:func:`recorded_shares`). For alcohol the share counts only the
  fatal crashes in which every driver was tested. Drugs have no row in that table; their share is
  the killed drivers whose blood held a drug of abuse and no alcohol, from the national forensic
  toxicology reports (INTCF).
- *How much each factor multiplies the risk*: for alcohol and drugs, the EU DRUID project's risk
  bands for being seriously injured or killed, weighted by the blood alcohol INTCF measured in
  killed drivers and by the drugs the police found in them; for distraction, the naturalistic
  driving study of Dingus et al. (2016), 2.0 for any observable distraction and 3.6 for a handheld
  phone.

**The bounds.** ``low`` and ``high`` take the ends of the published risk ranges (DRUID's bands;
for distraction, any distraction against a handheld phone). They say how sensitive the answer is
to the risk, not how uncertain the police record is. Two cross-checks bound that instead: for
alcohol, the INTCF share of killed drivers over the limit, which agrees with the police record;
for distraction, the naturalistic study's own estimate that 36 % of crashes would not happen
without distraction, against the 15 % the police record implies (:func:`naturalistic_distraction`).

What is left out, deliberately: psychoactive medicines (11–16 % of killed drivers), which are
prescribed and not what roadside enforcement targets; the impairment of pedestrians themselves
(43 % of those killed tested positive); and any interaction between factors beyond what
:func:`combined` assumes.
"""

from __future__ import annotations

import math
from functools import cache

import pandas as pd

from dgt_stats import io_tables, simulator
from dgt_stats.paths import FACTOR_EVIDENCE_PATH

ZONES = ("interurban", "urban")
ROLES = ("driver", "passenger", "pedestrian")
BASELINE_YEARS = (2022, 2023, 2024)
# The years DGT publishes both the all-roads and the interurban denominators for, so that the
# urban share can be derived; 2023 gives the interurban share without its denominator.
SHARE_YEARS = (2022, 2024)
RECORDED_FACTORS = ("distraction", "alcohol", "speed")
FACTORS = {
    "distraction": "Distraction",
    "alcohol": "Alcohol",
    "drugs": "Drugs (without alcohol)",
}
GROUPS = {
    "distraction": ("distraction",),
    "alcohol_drugs": ("alcohol", "drugs"),
}
GROUP_LABELS = {"distraction": "Distraction", "alcohol_drugs": "Alcohol and drugs"}
BOUNDS = ("value", "low", "high")
DRUGS = ("cocaine", "cannabis", "amphetamine", "opiate")


# --------------------------------------------------------------------------- inputs


@cache
def evidence() -> pd.DataFrame:
    """The sourced parameter register, one row per published value."""
    frame = pd.read_csv(FACTOR_EVIDENCE_PATH)
    if frame.duplicated(["parameter", "applies_to"]).any():
        raise ValueError("factor evidence: a parameter is listed twice for the same scope")
    return frame


@cache
def parameter(name: str, applies_to: str, bound: str = "value") -> float:
    """One published value (``bound`` is ``value``, ``low`` or ``high``)."""
    rows = evidence()
    row = rows[(rows.parameter == name) & (rows.applies_to == applies_to)]
    if len(row) != 1:
        raise KeyError(f"factor evidence: no single row for {name!r} / {applies_to!r}")
    value = row[bound].iloc[0]
    if pd.isna(value):
        raise KeyError(f"factor evidence: {name!r} / {applies_to!r} has no {bound}")
    return float(value)


@cache
def _victims() -> pd.DataFrame:
    frames = [io_tables.read_table_2_2(year) for year in BASELINE_YEARS]
    io_tables.close_workbooks()
    return pd.concat(frames, ignore_index=True)


def casualties() -> pd.DataFrame:
    """Mean deaths, hospital admissions and other injured a year, 2022–2024, by zone and road user.

    DGT's yearbook table 2.2, the total row of each zone and role; 30-day definitions, all of
    Spain.
    """
    victims = _victims()
    totals = victims[victims.is_total & victims.role.isin(ROLES)]
    out = (
        totals.pivot_table(index=["zone", "role"], columns="metric", values="value", aggfunc="sum")
        .div(len(BASELINE_YEARS))
        .rename(
            columns={
                "deaths_30d": "deaths",
                "hospitalised_30d": "hospitalised",
                "non_hospitalised_30d": "other_injured",
            }
        )
    )
    out = out[["deaths", "hospitalised", "other_injured"]].reindex(
        pd.MultiIndex.from_product([ZONES, ROLES], names=["zone", "role"])
    )
    out["first_year"], out["last_year"] = min(BASELINE_YEARS), max(BASELINE_YEARS)
    return out.reset_index()


def recorded_shares() -> pd.DataFrame:
    """Share of fatal crashes with each factor in the police record, by zone and year.

    All roads are DGT's counts; interurban roads are DGT's rounded percentage times its
    interurban denominator; urban streets are the difference. ``pooled`` adds the counts of the
    years in :data:`SHARE_YEARS`. For alcohol every denominator is the fatal crashes in which all
    drivers were tested. The rounding of the interurban percentage (half a point) moves the urban
    count by about five crashes.
    """
    records = []
    for factor in RECORDED_FACTORS:
        tested = "fatal_crashes_tested" if factor == "alcohol" else "fatal_crashes"
        for year in SHARE_YEARS:
            all_with = parameter(f"fatal_crashes_{factor}", f"all_{year}")
            all_total = parameter(tested, f"all_{year}")
            inter_total = parameter(tested, f"interurban_{year}")
            inter_with = parameter(f"fatal_share_{factor}", f"interurban_{year}") * inter_total
            for zone, with_factor, total, derived in (
                ("all", all_with, all_total, False),
                ("interurban", inter_with, inter_total, True),
                ("urban", all_with - inter_with, all_total - inter_total, True),
            ):
                records.append(
                    {
                        "factor": factor,
                        "zone": zone,
                        "year": str(year),
                        "crashes_with_factor": with_factor,
                        "fatal_crashes": total,
                        "share": with_factor / total,
                        "derived": derived,
                    }
                )
        # 2023 gives the all-roads counts and the interurban share only: a check on stability.
        all_2023 = parameter(f"fatal_crashes_{factor}", "all_2023")
        total_2023 = parameter(tested, "all_2023")
        records.append(
            {
                "factor": factor,
                "zone": "all",
                "year": "2023",
                "crashes_with_factor": all_2023,
                "fatal_crashes": total_2023,
                "share": all_2023 / total_2023,
                "derived": False,
            }
        )
        records.append(
            {
                "factor": factor,
                "zone": "interurban",
                "year": "2023",
                "crashes_with_factor": math.nan,
                "fatal_crashes": math.nan,
                "share": parameter(f"fatal_share_{factor}", "interurban_2023"),
                "derived": False,
            }
        )
    out = pd.DataFrame.from_records(records)
    pooled = (
        out[out.year.isin([str(y) for y in SHARE_YEARS])]
        .groupby(["factor", "zone"], sort=False)[["crashes_with_factor", "fatal_crashes"]]
        .sum()
        .reset_index()
    )
    pooled["year"] = "pooled"
    pooled["share"] = pooled.crashes_with_factor / pooled.fatal_crashes
    pooled["derived"] = pooled.zone != "all"
    return pd.concat([out, pooled], ignore_index=True)


def _pooled_share(factor: str, zone: str) -> float:
    shares = recorded_shares()
    row = shares[(shares.factor == factor) & (shares.zone == zone) & (shares.year == "pooled")]
    return float(row.share.iloc[0])


def drug_share() -> float:
    """Share of killed drivers with a drug of abuse and no alcohol, mean of 2023 and 2024 (INTCF).

    2023: drug positives less those that also had alcohol, over the drivers analysed. 2024: the
    drug share less the alcohol-and-drug combinations, which INTCF gives as shares of the positive
    drivers.
    """
    shares = [
        (
            parameter("killed_drivers_drugs", "2023")
            - parameter("killed_drivers_alcohol_and_drugs", "2023")
        )
        / parameter("killed_drivers_analysed", "2023"),
        parameter("killed_drivers_drugs_share", "2024")
        - (
            parameter("positive_alcohol_and_drugs_share", "2024")
            + parameter("positive_alcohol_drugs_medicines_share", "2024")
        )
        * parameter("killed_drivers_positive", "2024")
        / parameter("killed_drivers_analysed", "2024"),
    ]
    return sum(shares) / len(shares)


def presence(factor: str, zone: str) -> float:
    """Share of fatal crashes (drugs: of killed drivers) in which the factor was present."""
    if factor == "drugs":
        return drug_share()
    return _pooled_share(factor, zone)


# --------------------------------------------------------------------------- risk


def _af(rr: float) -> float:
    """Share of the crashes with a factor that would not happen without it: 1 − 1/RR."""
    return 1 - 1 / rr


def _rr(scope: str, bound: str) -> float:
    """DRUID's relative risk for a substance group: the pooled estimate for seriously injured
    drivers as the value, and DRUID's own risk band as the low and high ends."""
    if bound == "value":
        return parameter("rr_druid_injured", scope)
    return parameter("rr_druid_band", scope, bound)


def alcohol_rr_bands(bound: str = "value") -> dict[str, tuple[float, float]]:
    """Weight and relative risk of each band of blood alcohol above the general limit (0.5 g/L).

    INTCF's killed drivers of 2023 by blood alcohol: 0.51–1.20 g/L, which spans DRUID's
    0.5–0.8 and 0.8–1.2 g/L groups (the value is the geometric mean of their two estimates, the
    ends the low end of the first band and the high end of the second), and over 1.20 g/L,
    DRUID's highest group.
    """
    middle = parameter("killed_drivers_bac", "0.51-1.20_2023")
    top = parameter("killed_drivers_bac", "1.21-2.00_2023") + parameter(
        "killed_drivers_bac", "over_2.00_2023"
    )
    rr_middle = {
        "value": math.sqrt(_rr("alcohol_0.5-0.8", "value") * _rr("alcohol_0.8-1.2", "value")),
        "low": _rr("alcohol_0.5-0.8", "low"),
        "high": _rr("alcohol_0.8-1.2", "high"),
    }[bound]
    total = middle + top
    return {
        "0.51-1.20": (middle / total, rr_middle),
        "over_1.20": (top / total, _rr("alcohol_over_1.2", bound)),
    }


def drug_rr_mix(bound: str = "value") -> dict[str, tuple[float, float]]:
    """Weight and relative risk of each drug, by the detections in killed drivers (DGT, 2023)."""
    counts = {drug: parameter("drug_detections", f"{drug}_2023") for drug in DRUGS}
    total = sum(counts.values())
    return {drug: (n / total, _rr(drug, bound)) for drug, n in counts.items()}


def attributable_fraction(factor: str, bound: str = "value") -> float:
    """Share of the crashes with the factor present that would not happen without it."""
    if factor == "alcohol":
        return sum(w * _af(rr) for w, rr in alcohol_rr_bands(bound).values())
    if factor == "drugs":
        return sum(w * _af(rr) for w, rr in drug_rr_mix(bound).values())
    if factor == "distraction":
        scope = "handheld_phone" if bound == "high" else "any_observable"
        return _af(parameter("or_distraction", scope))
    raise KeyError(factor)


# --------------------------------------------------------------------------- deaths


def deaths_avoided(factor: str, share_removed: float = 1.0, bound: str = "value") -> pd.DataFrame:
    """Deaths a year that would not happen if ``share_removed`` of the factor were removed."""
    base = casualties()
    af = attributable_fraction(factor, bound)
    base["presence"] = [presence(factor, zone) for zone in base.zone]
    base["attributable_fraction"] = af
    base["avoided"] = share_removed * base.deaths * base.presence * af
    base["factor"] = factor
    return base[
        ["factor", "zone", "role", "deaths", "presence", "attributable_fraction", "avoided"]
    ]


def factor_deaths() -> pd.DataFrame:
    """Every factor and group, by zone and road user, at the three bounds, with everything removed."""
    records = []
    for name, members in {
        **{f: (f,) for f in FACTORS},
        "alcohol_drugs": GROUPS["alcohol_drugs"],
    }.items():
        frames = {
            bound: sum(
                deaths_avoided(f, 1.0, bound).set_index(["zone", "role"]).avoided for f in members
            )
            for bound in BOUNDS
        }
        base = casualties().set_index(["zone", "role"]).deaths
        for (zone, role), deaths in base.items():
            records.append(
                {
                    "factor": name,
                    "zone": zone,
                    "role": role,
                    "deaths": float(deaths),
                    "avoided": float(frames["value"].loc[(zone, role)]),
                    "avoided_low": float(frames["low"].loc[(zone, role)]),
                    "avoided_high": float(frames["high"].loc[(zone, role)]),
                }
            )
    out = pd.DataFrame.from_records(records)
    totals = out.groupby(["factor", "zone"], sort=False)[
        ["deaths", "avoided", "avoided_low", "avoided_high"]
    ].sum()
    totals = totals.reset_index().assign(role="all")
    everywhere = out.groupby("factor", sort=False)[
        ["deaths", "avoided", "avoided_low", "avoided_high"]
    ].sum()
    everywhere = everywhere.reset_index().assign(zone="all", role="all")
    return pd.concat([out, totals, everywhere], ignore_index=True)


def factor_inputs() -> pd.DataFrame:
    """The inputs of each factor's chain: presence by zone, relative risk and attributable fraction."""
    records = []
    for factor, label in FACTORS.items():
        for zone in ZONES:
            records.append(
                {
                    "factor": factor,
                    "factor_label": label,
                    "quantity": f"presence_{zone}",
                    "value": presence(factor, zone),
                    "low": presence(factor, zone),
                    "high": presence(factor, zone),
                }
            )
        records.append(
            {
                "factor": factor,
                "factor_label": label,
                "quantity": "attributable_fraction",
                **{bound: attributable_fraction(factor, bound) for bound in BOUNDS},
            }
        )
    return pd.DataFrame.from_records(records)


def naturalistic_distraction() -> pd.DataFrame:
    """The upper cross-check: distraction as common in Spanish fatal crashes as in observed crashes.

    The naturalistic study saw distraction in 68.3 % of crashes and estimated that 36 % would not
    have happened without it. Applied to every death, that is the most distraction could account
    for if the police record misses most of it; it is a sensitivity, not a second estimate.
    """
    base = casualties()
    par = parameter("par_distraction", "naturalistic")
    base["avoided"] = base.deaths * par
    out = base.groupby("zone")[["deaths", "avoided"]].sum().reset_index()
    out.loc[len(out)] = ["all", out.deaths.sum(), out.avoided.sum()]
    out["par"] = par
    out["police_share_all"] = _pooled_share("distraction", "all")
    out["naturalistic_share_of_crashes"] = parameter("distraction_share_of_crashes", "naturalistic")
    return out


def factor_crashes() -> pd.DataFrame:
    """Injury crashes in which the police recorded each factor in 2024, and those it caused.

    Spain without Cataluña and País Vasco. Alcohol is recorded only where drivers were tested
    (about two crashes in five), so its count is a floor. Drugs are recorded too rarely to count.
    """
    records = []
    total = parameter("injury_crashes", "all_2024")
    for factor in ("distraction", "alcohol"):
        recorded = parameter(f"injury_crashes_{factor}", "all_2024")
        records.append(
            {
                "factor": factor,
                "injury_crashes": total,
                "recorded": recorded,
                "tested": parameter("injury_crashes_tested", "all_2024")
                if factor == "alcohol"
                else total,
                **{
                    f"avoided{'' if bound == 'value' else '_' + bound}": recorded
                    * attributable_fraction(factor, bound)
                    for bound in BOUNDS
                },
            }
        )
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------------------------- the three levers

LEVERS = {
    "speed": "Speeding",
    "alcohol_drugs": "Alcohol and drugs",
    "distraction": "Distraction",
}
SPEED_STEPS = 101


def speed_curve() -> pd.DataFrame:
    return _speed_curve().copy()


@cache
def _speed_curve() -> pd.DataFrame:
    """Deaths avoided by speed compliance, from none to everyone, on the simulator's evidence.

    ``compliance`` is the share of the drivers above today's limit who slow to it, on every kind
    of road at once. Interurban deaths are the simulator's three road classes (autopistas,
    autovías and conventional roads, 1,200 of the 1,284 interurban deaths); urban streets are a
    proportional change on streets at 50 and at 30 km/h, since DGT publishes no split of urban
    deaths by the limit of the street.
    """
    records = []
    for step in range(SPEED_STEPS):
        compliance = step / (SPEED_STEPS - 1)
        scenario = simulator.Scenario("c", "c", {}, None, compliance)
        total = simulator.totals(simulator.interurban_effects(scenario))
        sites = simulator.site_effects(scenario).set_index("site")
        records.append(
            {
                "compliance": compliance,
                "interurban_avoided": -float(total.deaths_change),
                "interurban_avoided_low": -float(total.deaths_change_high),
                "interurban_avoided_high": -float(total.deaths_change_low),
                "urban_50_fall": 1 - float(sites.loc["urban_50", "deaths_ratio"]),
                "urban_30_fall": 1 - float(sites.loc["urban_30", "deaths_ratio"]),
            }
        )
    return pd.DataFrame.from_records(records)


def _speed_avoided(curve: pd.DataFrame, deaths: pd.Series, compliance: float = 1.0) -> dict:
    """Speed's deaths avoided by zone at a compliance on the curve: central, low, high.

    Urban streets: the central value takes every urban death to be on a street at 50 km/h, the
    smaller fall; the high end every one on a street at 30; the low end none, because the
    evidence for urban deaths includes no effect.
    """
    row = curve.iloc[(curve.compliance - compliance).abs().idxmin()]
    urban = float(deaths["urban"])
    return {
        "interurban": (
            float(row.interurban_avoided),
            float(row.interurban_avoided_low),
            float(row.interurban_avoided_high),
        ),
        "urban": (urban * float(row.urban_50_fall), 0.0, urban * float(row.urban_30_fall)),
    }


def combined(shares: list[float]) -> float:
    """Share of deaths avoided by removing several factors, if they act independently.

    A death avoided by one factor cannot be avoided again by another, so the shares combine as
    ``1 − Π(1 − a_i)`` rather than adding up. Factors that occur together (alcohol and speed
    often do) overlap more than independence assumes, so the combined figure is if anything high.
    """
    remaining = 1.0
    for share in shares:
        remaining *= 1 - share
    return 1 - remaining


def comparison(curve: pd.DataFrame | None = None) -> pd.DataFrame:
    """Each lever with its factor removed entirely, by zone, and all three together."""
    curve = speed_curve() if curve is None else curve
    deaths = casualties().groupby("zone").deaths.sum()
    table = factor_deaths()
    table = table[table.role == "all"].set_index(["factor", "zone"])
    speed = _speed_avoided(curve, deaths)
    values: dict[str, dict[str, tuple[float, float, float]]] = {"speed": speed}
    for lever in ("alcohol_drugs", "distraction"):
        values[lever] = {
            zone: tuple(
                float(table.loc[(lever, zone), column])
                for column in ("avoided", "avoided_low", "avoided_high")
            )
            for zone in ZONES
        }
    records = []
    for lever, label in LEVERS.items():
        for zone in ZONES:
            central, low, high = values[lever][zone]
            records.append(
                {
                    "lever": lever,
                    "lever_label": label,
                    "zone": zone,
                    "deaths": float(deaths[zone]),
                    "avoided": central,
                    "avoided_low": low,
                    "avoided_high": high,
                }
            )
    for zone in ZONES:
        d = float(deaths[zone])
        records.append(
            {
                "lever": "combined",
                "lever_label": "All three together",
                "zone": zone,
                "deaths": d,
                **{
                    column: d * combined([values[lever][zone][i] / d for lever in LEVERS])
                    for i, column in enumerate(("avoided", "avoided_low", "avoided_high"))
                },
            }
        )
    out = pd.DataFrame.from_records(records)
    everywhere = out.groupby(["lever", "lever_label"], sort=False)[
        ["deaths", "avoided", "avoided_low", "avoided_high"]
    ].sum()
    out = pd.concat([out, everywhere.reset_index().assign(zone="all")], ignore_index=True)
    out["share"] = out.avoided / out.deaths
    return out


def speed_at(curve: pd.DataFrame, compliance: float, bound: str = "value") -> dict[str, float]:
    """Speed's deaths avoided by zone at any compliance, by straight lines between the curve's
    points, exactly as the browser reads it."""
    last = len(curve) - 1
    position = min(max(compliance, 0.0), 1.0) * last
    i = min(math.floor(position), last - 1)
    t = position - i

    def at(column: str) -> float:
        a, b = float(curve[column].iloc[i]), float(curve[column].iloc[i + 1])
        return a + t * (b - a)

    suffix = "" if bound == "value" else f"_{bound}"
    urban_deaths = float(casualties().groupby("zone").deaths.sum()["urban"])
    urban = {
        "value": urban_deaths * at("urban_50_fall"),
        "low": 0.0,
        "high": urban_deaths * at("urban_30_fall"),
    }[bound]
    return {"interurban": at(f"interurban_avoided{suffix}"), "urban": urban}


def lever_deaths(
    curve: pd.DataFrame, settings: dict[str, float], bound: str = "value"
) -> dict[str, dict[str, float]]:
    """Deaths avoided by zone for each lever at the shares in ``settings``, and all three together.

    ``settings`` maps each lever of :data:`LEVERS` to the share of its factor removed (for speed,
    the share of the drivers above the limit who slow to it).
    """
    deaths = casualties().groupby("zone").deaths.sum()
    out: dict[str, dict[str, float]] = {"speed": speed_at(curve, settings["speed"], bound)}
    for lever in ("alcohol_drugs", "distraction"):
        frames = [deaths_avoided(factor, settings[lever], bound) for factor in GROUPS[lever]]
        out[lever] = {
            zone: float(sum(frame[frame.zone == zone].avoided.sum() for frame in frames))
            for zone in ZONES
        }
    out["combined"] = {
        zone: float(deaths[zone])
        * combined([out[lever][zone] / float(deaths[zone]) for lever in LEVERS])
        for zone in ZONES
    }
    return out


def share_needed(curve: pd.DataFrame, lever: str, lives: float, bound: str = "value") -> float:
    """The share of one lever's factor that must go to save ``lives`` deaths a year, the other two
    left as they are; NaN if removing all of it saves fewer.

    Alcohol, drugs and distraction are linear in the share, so it is ``lives`` over the deaths the
    whole factor causes; speed is read off its curve by straight lines between the points.
    """
    if lever != "speed":
        idle = dict.fromkeys(LEVERS, 0.0)
        full = sum(lever_deaths(curve, {**idle, lever: 1.0}, bound)[lever].values())
        return lives / full if lives <= full else math.nan
    steps = [i / (len(curve) - 1) for i in range(len(curve))]
    saved = [sum(speed_at(curve, s, bound).values()) for s in steps]
    if lives > saved[-1]:
        return math.nan
    for i in range(1, len(steps)):
        if saved[i] >= lives:
            return steps[i - 1] + (lives - saved[i - 1]) / (saved[i] - saved[i - 1]) * (
                steps[i] - steps[i - 1]
            )
    return 1.0


# --------------------------------------------------------------------------- the browser


def browser_parameters(tables: dict[str, pd.DataFrame]) -> dict[str, object]:
    """Everything the model pages need, from the committed result tables."""
    base = tables["factor_casualties"].set_index(["zone", "role"])
    inputs = tables["factor_inputs"].set_index(["factor", "quantity"])
    return {
        "deaths": {
            zone: {role: float(base.loc[(zone, role), "deaths"]) for role in ROLES}
            for zone in ZONES
        },
        "factors": {
            factor: {
                "label": label,
                "presence": {
                    zone: float(inputs.loc[(factor, f"presence_{zone}"), "value"]) for zone in ZONES
                },
                "af": {
                    bound: float(inputs.loc[(factor, "attributable_fraction"), bound])
                    for bound in BOUNDS
                },
            }
            for factor, label in FACTORS.items()
        },
        "groups": {name: list(members) for name, members in GROUPS.items()},
        "groupLabels": GROUP_LABELS,
        "levers": LEVERS,
        "crashes": {
            row.factor: float(row.recorded) for row in tables["factor_crashes"].itertuples()
        },
        "speed": {
            column: [float(v) for v in tables["factor_speed_curve"][column]]
            for column in (
                "interurban_avoided",
                "interurban_avoided_low",
                "interurban_avoided_high",
                "urban_50_fall",
                "urban_30_fall",
            )
        },
    }
