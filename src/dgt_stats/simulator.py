"""What a new speed law would do: Spanish baselines, published dose-response laws, compliance.

The simulator on the site is this module run in the reader's browser (``simulator.js`` is a line-
by-line port, and a test runs both on the same scenarios). Everything it computes is a chain of
four links, and each link names where its numbers come from:

1. **Baseline.** Deaths within 30 days, people admitted to hospital and other injured by road
   class, the mean of the three most recent years of the crash microdata, which reconcile exactly
   with DGT's yearbook (:func:`baseline`).
2. **Today's speeds.** The free-flow speeds of cars measured in Spain in 2022 for the EU's
   Baseline project, by road type: the mean, the share of cars within the limit and the 85th
   percentile, separately for autopistas, autovías, conventional roads and urban streets at 50
   and at 30 km/h. A log-normal distribution through the last two reproduces both exactly
   (:class:`SpeedDistribution`); its mean is checked against the measured one.
3. **From a law to a new mean speed.** Two levers. *A new limit*: drivers move their average speed
   by only part of the change, by the amount of the curve fitted to 143 before-and-after results
   in the Norwegian road-safety handbook (:func:`typical_response`), unless the reader sets the
   share themselves. *Compliance*: a share of the drivers above the limit slow to it; the mean
   then falls by that share of the expected excess over the limit, computed from the measured
   distribution (:meth:`SpeedDistribution.excess`).
4. **From mean speed to casualties: the Power Model.** When the mean speed of traffic changes from
   ``v0`` to ``v1`` a count changes by ``(v1 / v0) ** p``, with ``p`` larger for more severe
   outcomes. The exponents and their 95 % intervals are Elvik's 2009 meta-analysis, separately for
   rural roads and motorways and for urban streets.

Every number in links 2 to 4 is read from ``data/raw/evidence/simulator_parameters.csv``, one row
per value with its source, table and a verbatim quote. Nothing in the chain is fitted to Spanish
crash data, because Spanish crash data carry no speeds: the evidence that measured speeds supplies
the effect, the Spanish data say what it applies to, and :mod:`dgt_stats.forecast` says whether
the result could ever be seen in the counts.

A law sets one limit for autopistas and autovías together, as the Reglamento General de
Circulación does, one for conventional roads and one for urban streets now at 50 km/h; each
measured kind of road then responds from its own speeds (:data:`LEVERS`).

What is left out, deliberately: other interurban roads (service roads, local tracks), for which no
speed was measured; urban casualties as a national count, because DGT does not publish how many
happen on 30 and on 50 km/h streets, so the urban effect is given per street type; and the money
value of travel time, for which no Spanish official figure was found to cite. Time is reported in
vehicle-hours of cars and other light vehicles, the traffic the speeds were measured on.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd
from scipy import stats

from dgt_stats import forecast, io_traffic
from dgt_stats.paths import PROCESSED_DATA_DIR, SIMULATOR_EVIDENCE_PATH

PROCESSED_CRASHES = PROCESSED_DATA_DIR / "accidentes.parquet"
BASELINE_YEARS = (2022, 2023, 2024)

# Road classes, by DGT's zone and road-type code. Every class is stable across the 2021
# (interurban) and 2022–2024 (toll and free motorway) recodings because each groups the codes
# that were swapped: toll and free motorways (1 and 2) are both autopistas.
ROAD_CLASSES = {
    "autopista": "Autopistas",
    "autovia": "Autovías",
    "conventional": "Conventional roads",
    "other_interurban": "Other interurban roads",
    "urban": "Urban streets",
}
AUTOPISTA_CODES = (1, 2)
AUTOVIA_CODES = (3,)
CONVENTIONAL_CODES = (4, 5, 6)
# The evidence's road environments: Elvik's exponents are given for rural roads and motorways
# together, and for urban and residential streets.
ENVIRONMENT = {
    "autopista": "rural",
    "autovia": "rural",
    "conventional": "rural",
    "other_interurban": "rural",
    "urban": "urban",
}
# Where a speed was measured: the three interurban classes, and two kinds of urban street.
SITES = {
    "autopista": "Autopistas (120 km/h)",
    "autovia": "Autovías (120 km/h)",
    "conventional": "Conventional roads (90 km/h)",
    "urban_50": "Urban streets at 50 km/h",
    "urban_30": "Urban streets at 30 km/h",
}
INTERURBAN_SITES = ("autopista", "autovia", "conventional")
URBAN_SITES = ("urban_50", "urban_30")
# What a law sets, and the measured sites each limit applies to: the Reglamento gives autopistas
# and autovías one limit. Streets already at 30 km/h keep it.
LEVERS = {
    "motorway": ("autopista", "autovia"),
    "conventional": ("conventional",),
    "urban_50": ("urban_50",),
}
LEVER_LABELS = {
    "motorway": "Autopistas and autovías (120 km/h)",
    "conventional": "Conventional roads (90 km/h)",
    "urban_50": "Urban streets now at 50 km/h",
}
LEVER_OF = {site: lever for lever, sites in LEVERS.items() for site in sites}
# The limits the page offers, inside the range of limit changes the response curve was fitted on
# (−33 to +24 km/h).
LIMIT_OPTIONS = {
    "motorway": (100, 110, 120, 130, 140),
    "conventional": (70, 80, 90, 100),
    "urban_50": (30, 40, 50),
}
RESPONSE_RANGE = (-33, 24)

OUTCOMES = {
    "deaths": "Deaths within 30 days",
    "seriously_injured": "Admitted to hospital",
    "slightly_injured": "Other injured",
    "injury_crashes": "Injury crashes",
}
VALUE_PARAMETERS = {
    "deaths": "value_death",
    "seriously_injured": "value_serious_injury",
    "slightly_injured": "value_slight_injury",
}
Z85 = float(stats.norm.ppf(0.85))


# --------------------------------------------------------------------------- inputs


@cache
def evidence() -> pd.DataFrame:
    """The sourced parameter register, one row per published value."""
    frame = pd.read_csv(SIMULATOR_EVIDENCE_PATH)
    if frame.duplicated(["parameter", "applies_to"]).any():
        raise ValueError("simulator evidence: a parameter is listed twice for the same scope")
    return frame


@cache
def parameter(name: str, applies_to: str = "all", bound: str = "value") -> float:
    """One published value (``bound`` is ``value``, ``low`` or ``high``)."""
    rows = evidence()
    row = rows[(rows.parameter == name) & (rows.applies_to == applies_to)]
    if len(row) != 1:
        raise KeyError(f"simulator evidence: no single row for {name!r} / {applies_to!r}")
    value = row[bound].iloc[0]
    if pd.isna(value):
        raise KeyError(f"simulator evidence: {name!r} / {applies_to!r} has no {bound}")
    return float(value)


def road_class(zone: pd.Series, road_type: pd.Series) -> pd.Series:
    """The simulator's road class of each crash: urban by zone, interurban by road-type code."""
    out = np.select(
        [
            zone == "urban",
            road_type.isin(AUTOPISTA_CODES),
            road_type.isin(AUTOVIA_CODES),
            road_type.isin(CONVENTIONAL_CODES),
        ],
        ["urban", "autopista", "autovia", "conventional"],
        "other_interurban",
    )
    return pd.Series(out, index=zone.index, dtype="string")


def _crashes() -> pd.DataFrame:
    columns = ["ANYO", "zone", "TIPO_VIA", "TOTAL_MU30DF", "TOTAL_HG30DF", "TOTAL_HL30DF"]
    crashes = pd.read_parquet(PROCESSED_CRASHES, columns=columns)
    return crashes.assign(road_class=road_class(crashes.zone, crashes.TIPO_VIA))


def baseline(years: tuple[int, ...] = BASELINE_YEARS) -> pd.DataFrame:
    """Mean annual crashes and casualties by road class over ``years``, from the microdata."""
    crashes = _crashes()
    crashes = crashes[crashes.ANYO.isin(years)]
    out = crashes.groupby("road_class").agg(
        injury_crashes=("TOTAL_MU30DF", "size"),
        deaths=("TOTAL_MU30DF", "sum"),
        seriously_injured=("TOTAL_HG30DF", "sum"),
        slightly_injured=("TOTAL_HL30DF", "sum"),
    ).astype(float) / len(years)
    out = out.reindex(list(ROAD_CLASSES))
    out.insert(0, "road_class_label", [ROAD_CLASSES[key] for key in out.index])
    out["environment"] = [ENVIRONMENT[key] for key in out.index]
    out["first_year"], out["last_year"] = min(years), max(years)
    out.index.name = "road_class"
    return out.reset_index()


RISK_CLASSES = {
    "motorway": "Autopistas and autovías",
    "conventional": "Conventional roads",
}


def class_risk() -> pd.DataFrame:
    """Deaths, admissions and injury crashes per billion vehicle-km, motorways against conventional.

    The kilometres are the Ministry's measured interurban network (table 1.2.14): toll motorways
    plus autovías and free motorways against conventional plus multi-lane roads. They leave out
    the municipal interurban roads, so the rates are a little high, by the same factor for both.
    Autopistas and autovías are pooled here: the table puts free motorways with autovías and the
    crash data with toll motorways, and the crash data swap toll and free motorways in 2022 and
    2024.
    """
    traffic = io_traffic.read_road_traffic().set_index("year")
    km = {
        "motorway": traffic.toll_motorway + traffic.autovia_free_motorway,
        "conventional": traffic.multilane + traffic.conventional,
    }
    crashes = _crashes()
    crashes["road_class"] = crashes.road_class.replace(
        {"autopista": "motorway", "autovia": "motorway"}
    )
    crashes = crashes[crashes.road_class.isin(km) & crashes.ANYO.isin(traffic.index)]
    counts = crashes.groupby(["ANYO", "road_class"]).agg(
        deaths=("TOTAL_MU30DF", "sum"),
        seriously_injured=("TOTAL_HG30DF", "sum"),
        injury_crashes=("TOTAL_MU30DF", "size"),
    )
    records = []
    for (year, key), row in counts.iterrows():
        billion_km = float(km[key].loc[year]) / 1e3
        records.append(
            {
                "year": int(year),
                "road_class": key,
                "road_class_label": RISK_CLASSES[key],
                "billion_vehicle_km": billion_km,
                "deaths": float(row.deaths),
                "deaths_per_bn_km": float(row.deaths) / billion_km,
                "seriously_injured_per_bn_km": float(row.seriously_injured) / billion_km,
                "injury_crashes_per_bn_km": float(row.injury_crashes) / billion_km,
            }
        )
    return pd.DataFrame.from_records(records).sort_values(["year", "road_class"])


# --------------------------------------------------------------------------- speeds


@dataclass(frozen=True)
class SpeedDistribution:
    """Free-flow car speeds on one kind of road: log-normal through two measured points.

    The share of cars within the limit and the 85th percentile are two quantiles of the
    distribution; a log-normal through both is fixed by them. ``mean`` is the measured mean, kept
    as the reference for the Power Model; ``implied_mean`` is the log-normal's own, kept to check
    the shape.
    """

    limit: float
    mean: float
    v85: float
    share_within_limit: float

    @property
    def sigma(self) -> float:
        z_limit = stats.norm.ppf(self.share_within_limit)
        return (math.log(self.v85) - math.log(self.limit)) / (Z85 - z_limit)

    @property
    def mu(self) -> float:
        return math.log(self.limit) - stats.norm.ppf(self.share_within_limit) * self.sigma

    @property
    def implied_mean(self) -> float:
        return math.exp(self.mu + self.sigma**2 / 2)

    def excess(self, limit: float, scale: float = 1.0) -> float:
        """Expected speed above ``limit`` per car, E[(v − limit)+], after scaling every speed.

        A typical-response shift of the mean is applied as a scale on every speed, which keeps
        the distribution log-normal and moves its mean by the same proportion.
        """
        mu, sigma = self.mu + math.log(scale), self.sigma
        above = stats.norm.cdf((mu + sigma**2 - math.log(limit)) / sigma)
        beyond = stats.norm.cdf((mu - math.log(limit)) / sigma)
        return math.exp(mu + sigma**2 / 2) * above - limit * beyond


def speed_distribution(site: str) -> SpeedDistribution:
    return SpeedDistribution(
        limit=parameter("limit", site),
        mean=parameter("mean_speed", site),
        v85=parameter("v85", site),
        share_within_limit=parameter("share_within_limit", site),
    )


def typical_response(limit_change: float) -> float:
    """Change in mean speed (km/h) that typically follows a change in the limit (km/h).

    Elvik's curve through 143 before-and-after results, without its intercept, so that no change
    in the limit means no change in speed. It is only defined over the range of changes it was
    fitted to.
    """
    if not RESPONSE_RANGE[0] <= limit_change <= RESPONSE_RANGE[1]:
        raise ValueError(f"limit change {limit_change} is outside the evidence, {RESPONSE_RANGE}")
    a = parameter("pass_through_a")
    b = parameter("pass_through_b")
    return a * limit_change**2 + b * limit_change


def new_mean_speed(
    site: str,
    new_limit: float | None = None,
    response_share: float | None = None,
    compliance: float = 0.0,
) -> float:
    """Mean speed after a law: a new limit (with a typical or set response) and compliance with it.

    ``response_share`` is the share of the limit change that reaches the mean; ``None`` uses the
    typical response. ``compliance`` is the share of drivers above the (new) limit who slow to
    it.
    """
    distribution = speed_distribution(site)
    limit = distribution.limit if new_limit is None else float(new_limit)
    change = limit - distribution.limit
    shift = typical_response(change) if response_share is None else response_share * change
    shifted = distribution.mean + shift
    excess = distribution.excess(limit, shifted / distribution.mean)
    return shifted - compliance * excess


# --------------------------------------------------------------------------- casualties


def power_ratio(v0: float, v1: float, exponent: float) -> float:
    return (v1 / v0) ** exponent


def exponent(outcome: str, environment: str, bound: str = "value") -> float:
    return parameter(f"exponent_{outcome}", environment, bound)


BOUNDS = ("low", "high")


def outcome_ratios(site: str, v1: float) -> dict[str, tuple[float, float, float]]:
    """Ratio of each outcome after to before: at the exponent's estimate and at its two 95 % ends.

    The ends are kept in exponent order (low, high), not sorted, so that sums across roads that
    share an exponent use the same end throughout; the tables sort them for display.
    """
    v0 = speed_distribution(site).mean
    environment = "urban" if site in URBAN_SITES else "rural"
    return {
        outcome: tuple(
            power_ratio(v0, v1, exponent(outcome, environment, bound))
            for bound in ("value", *BOUNDS)
        )
        for outcome in OUTCOMES
    }


@dataclass(frozen=True)
class Scenario:
    """A law: a limit per lever (:data:`LEVERS`), how drivers respond, and compliance."""

    key: str
    label: str
    limits: dict[str, float]
    response_share: float | None = None
    compliance: float = 0.0

    def limit(self, site: str) -> float | None:
        """The new limit on a measured site, or ``None`` where the law leaves it alone."""
        lever = LEVER_OF.get(site)
        return None if lever is None else self.limits.get(lever)


PRESETS = (
    Scenario("current", "Today's limits and today's driving", {}),
    Scenario("conventional_80", "Conventional roads 90 → 80 km/h", {"conventional": 80}),
    Scenario("motorway_130", "Autopistas and autovías 120 → 130 km/h", {"motorway": 130}),
    Scenario("motorway_110", "Autopistas and autovías 120 → 110 km/h", {"motorway": 110}),
    Scenario("urban_30", "Urban streets at 50 → 30 km/h", {"urban_50": 30}),
    Scenario("half_comply", "Half of today's speeders keep to the limit", {}, compliance=0.5),
    Scenario("all_comply", "Every speeder keeps to today's limits", {}, compliance=1.0),
)


def site_effects(scenario: Scenario) -> pd.DataFrame:
    """For each measured site: speeds before and after, and the ratio of each outcome."""
    records = []
    for site, label in SITES.items():
        distribution = speed_distribution(site)
        new_limit = scenario.limit(site)
        v1 = new_mean_speed(site, new_limit, scenario.response_share, scenario.compliance)
        record = {
            "scenario": scenario.key,
            "site": site,
            "site_label": label,
            "limit": distribution.limit,
            "new_limit": distribution.limit if new_limit is None else new_limit,
            "mean_speed": distribution.mean,
            "new_mean_speed": v1,
        }
        for outcome, (central, at_low, at_high) in outcome_ratios(site, v1).items():
            record[f"{outcome}_ratio"] = central
            record[f"{outcome}_ratio_low"] = min(at_low, at_high)
            record[f"{outcome}_ratio_high"] = max(at_low, at_high)
            record[f"{outcome}_ratio_at_low_exponent"] = at_low
            record[f"{outcome}_ratio_at_high_exponent"] = at_high
        records.append(record)
    return pd.DataFrame.from_records(records)


@cache
def _baseline() -> pd.DataFrame:
    return baseline().set_index("road_class")


# The types of road in the Ministry's traffic table that make up each interurban site. Free
# motorways are autopistas in the crash data but sit with autovías in the table, so their
# kilometres are timed at the autovías' speeds.
TRAFFIC_TYPES = {
    "autopista": ("toll_motorway",),
    "autovia": ("autovia_free_motorway",),
    "conventional": ("multilane", "conventional"),
}


@cache
def _vehicle_km() -> dict[str, dict[str, float] | int]:
    """Vehicle-km a year on each interurban site, all vehicles and light vehicles only.

    The latest year of the Ministry's table 1.2.14; light vehicles are all traffic less the
    published share of heavy vehicles on each type of road.
    """
    traffic = io_traffic.read_road_traffic().set_index("year")
    last = traffic.iloc[-1]
    total = {key: sum(float(last[t]) for t in types) * 1e6 for key, types in TRAFFIC_TYPES.items()}
    light = {
        key: sum(float(last[t]) * (1 - float(last[f"{t}_heavy_share"])) for t in types) * 1e6
        for key, types in TRAFFIC_TYPES.items()
    }
    return {"all": total, "light": light, "year": int(traffic.index[-1])}


def interurban_effects(scenario: Scenario) -> pd.DataFrame:
    """Casualties a year on autopistas, autovías and conventional roads, with value and time.

    ``change`` is after minus before (negative is fewer); ``change_low`` and ``change_high`` span
    the exponent intervals, and the ``at_low_exponent`` and ``at_high_exponent`` columns keep the
    two ends unsorted for :func:`totals`. Value is the DGT's 2024 value of preventing each
    casualty, so a negative change in casualties is a positive ``value``. Time is vehicle-hours of
    light vehicles on the measured interurban network at free-flow speeds, positive when journeys
    take longer; heavy vehicles have their own limits, which the scenario leaves alone.
    """
    sites = site_effects(scenario).set_index("site")
    base = _baseline()
    km = _vehicle_km()
    records = []
    for key in INTERURBAN_SITES:
        site = sites.loc[key]
        record = {
            "scenario": scenario.key,
            "road_class": key,
            "road_class_label": ROAD_CLASSES[key],
            "mean_speed": float(site.mean_speed),
            "new_mean_speed": float(site.new_mean_speed),
        }
        values = [0.0, 0.0, 0.0]
        for outcome in OUTCOMES:
            before = float(base.loc[key, outcome])
            suffixes = ("", "_at_low_exponent", "_at_high_exponent")
            changes = [before * (float(site[f"{outcome}_ratio{s}"]) - 1) for s in suffixes]
            record[f"{outcome}_before"] = before
            record[f"{outcome}_change"] = changes[0]
            record[f"{outcome}_change_low"] = min(changes[1:])
            record[f"{outcome}_change_high"] = max(changes[1:])
            record[f"{outcome}_change_at_low_exponent"] = changes[1]
            record[f"{outcome}_change_at_high_exponent"] = changes[2]
            if outcome in VALUE_PARAMETERS:
                worth = parameter(VALUE_PARAMETERS[outcome])
                values = [v - c * worth for v, c in zip(values, changes)]
        record["value_euros"] = values[0]
        record["value_euros_low"] = min(values[1:])
        record["value_euros_high"] = max(values[1:])
        record["value_euros_at_low_exponent"] = values[1]
        record["value_euros_at_high_exponent"] = values[2]
        record["vehicle_hours_change"] = km["light"][key] * (
            1 / float(site.new_mean_speed) - 1 / float(site.mean_speed)
        )
        records.append(record)
    return pd.DataFrame.from_records(records)


def urban_effects(scenario: Scenario) -> pd.DataFrame:
    """Proportional change in each outcome on each kind of urban street; no national count."""
    sites = site_effects(scenario).set_index("site")
    records = []
    for key in URBAN_SITES:
        site = sites.loc[key]
        record = {
            "scenario": scenario.key,
            "site": key,
            "site_label": SITES[key],
            "mean_speed": float(site.mean_speed),
            "new_mean_speed": float(site.new_mean_speed),
        }
        for outcome in OUTCOMES:
            for suffix in ("", "_low", "_high"):
                record[f"{outcome}_change{suffix}"] = float(site[f"{outcome}_ratio{suffix}"]) - 1
        records.append(record)
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------------------------- detectability


def detectability_inputs() -> dict[str, float]:
    """The validated forecast error, one year after a law, for interurban and urban deaths."""
    table = forecast.detectability()
    one = table[table.horizon == 1].set_index("outcome")
    return {
        "tau_interurban": float(one.loc["deaths_interurban", "tau"]),
        "tau_urban": float(one.loc["deaths_urban", "tau"]),
        "tau_all": float(one.loc["deaths_all", "tau"]),
    }


def power_in_one_year(change: float, expected: float, tau: float) -> float:
    """Chance that the first year's count shows a change of ``change`` deaths; NaN for none.

    A change under half a death a year is no change: the count has nothing to show.
    """
    if abs(change) < 0.5:
        return math.nan
    return forecast.detection_power(change, expected, tau)


# --------------------------------------------------------------------------- tables


def totals(effects: pd.DataFrame) -> pd.Series:
    """Sum of :func:`interurban_effects` over the roads, with each range built at one exponent end.

    Every interurban road takes the rural exponent, so the ends of a total are the sums at the low
    exponent and at the high exponent, sorted; adding each road's sorted ends instead would mix
    the two whenever one road's casualties rise and another's fall.
    """
    total = effects.sum(numeric_only=True)
    for stem in [f"{outcome}_change" for outcome in OUTCOMES] + ["value_euros"]:
        ends = (total[f"{stem}_at_low_exponent"], total[f"{stem}_at_high_exponent"])
        total[f"{stem}_low"], total[f"{stem}_high"] = min(ends), max(ends)
    return total


def presets() -> pd.DataFrame:
    """Every preset scenario: interurban casualties, value, time and the chance a count shows it.

    ``mde_deaths`` is the change the first year's count picks up four times in five (80 % power,
    two-sided 5 % test); ``power_in_one_year`` is the chance it picks up this scenario's change.
    """
    tau = detectability_inputs()["tau_interurban"]
    frames = []
    for scenario in PRESETS:
        total = totals(interurban_effects(scenario))
        expected = float(total.deaths_before)
        frames.append(
            {
                "scenario": scenario.key,
                "scenario_label": scenario.label,
                "deaths_before": expected,
                "deaths_change": float(total.deaths_change),
                "deaths_change_low": float(total.deaths_change_low),
                "deaths_change_high": float(total.deaths_change_high),
                "seriously_injured_change": float(total.seriously_injured_change),
                "slightly_injured_change": float(total.slightly_injured_change),
                "value_euros": float(total.value_euros),
                "value_euros_low": float(total.value_euros_low),
                "value_euros_high": float(total.value_euros_high),
                "vehicle_hours_change": float(total.vehicle_hours_change),
                "mde_deaths": forecast.minimum_detectable_effect(expected, tau) * expected,
                "power_in_one_year": power_in_one_year(float(total.deaths_change), expected, tau),
            }
        )
    return pd.DataFrame.from_records(frames)


def limit_grid() -> pd.DataFrame:
    """Every pair of interurban limits the page offers, with drivers responding as they typically do.

    ``levers_changed`` counts the limits that differ from today's, so that a page can compare
    one new limit against two; ``power_in_one_year`` is as in :func:`presets`.
    """
    tau = detectability_inputs()["tau_interurban"]
    records = []
    for motorway in LIMIT_OPTIONS["motorway"]:
        for conventional in LIMIT_OPTIONS["conventional"]:
            limits = {"motorway": motorway, "conventional": conventional}
            scenario = Scenario("grid", "grid", limits)
            total = totals(interurban_effects(scenario))
            records.append(
                {
                    "motorway_limit": motorway,
                    "conventional_limit": conventional,
                    "levers_changed": sum(
                        limits[lever] != parameter("limit", LEVERS[lever][0]) for lever in limits
                    ),
                    "deaths_change": float(total.deaths_change),
                    "deaths_change_low": float(total.deaths_change_low),
                    "deaths_change_high": float(total.deaths_change_high),
                    "value_euros": float(total.value_euros),
                    "vehicle_hours_change": float(total.vehicle_hours_change),
                    "power_in_one_year": power_in_one_year(
                        float(total.deaths_change), float(total.deaths_before), tau
                    ),
                }
            )
    return pd.DataFrame.from_records(records)


def preset_sites() -> pd.DataFrame:
    """Every preset scenario, site by site: speeds and outcome ratios (urban streets included)."""
    return pd.concat([site_effects(s) for s in PRESETS], ignore_index=True)


def speed_sites() -> pd.DataFrame:
    """The measured speeds and the log-normal fitted to them, with the check on the mean."""
    records = []
    for site, label in SITES.items():
        d = speed_distribution(site)
        records.append(
            {
                "site": site,
                "site_label": label,
                "limit": d.limit,
                "mean_speed": d.mean,
                "v85": d.v85,
                "share_within_limit": d.share_within_limit,
                "lognormal_mu": d.mu,
                "lognormal_sigma": d.sigma,
                "implied_mean": d.implied_mean,
                "excess_over_limit": d.excess(d.limit),
            }
        )
    return pd.DataFrame.from_records(records)


def baseline_table() -> pd.DataFrame:
    """The baseline by road class with the measured interurban vehicle-km beside it."""
    out = baseline()
    km = _vehicle_km()
    out["vehicle_km"] = [km["all"].get(key, np.nan) for key in out.road_class]
    out["light_vehicle_km"] = [km["light"].get(key, np.nan) for key in out.road_class]
    out["vehicle_km_year"] = km["year"]
    return out


def browser_parameters(tables: dict[str, pd.DataFrame]) -> dict[str, object]:
    """Everything the browser needs, from committed result tables and the evidence register.

    ``tables`` holds ``simulator_baseline``, ``simulator_speed_sites`` and
    ``forecast_detectability`` as written to ``reports/tables``, so the page can be built where
    only the committed tables exist.
    """
    base = tables["simulator_baseline"].set_index("road_class")
    sites = tables["simulator_speed_sites"].set_index("site")
    detect = tables["forecast_detectability"]
    one = detect[detect.horizon == 1].set_index("outcome").tau
    return {
        "baseline": {
            key: {outcome: float(base.loc[key, outcome]) for outcome in OUTCOMES}
            for key in INTERURBAN_SITES
        },
        "baselineYears": [int(base.first_year.iloc[0]), int(base.last_year.iloc[0])],
        "vehicleKm": {key: float(base.loc[key, "light_vehicle_km"]) for key in INTERURBAN_SITES},
        "vehicleKmYear": int(base.vehicle_km_year.iloc[0]),
        "sites": {
            site: {
                "label": label,
                "lever": LEVER_OF.get(site),
                "limit": float(sites.loc[site, "limit"]),
                "mean": float(sites.loc[site, "mean_speed"]),
                "mu": float(sites.loc[site, "lognormal_mu"]),
                "sigma": float(sites.loc[site, "lognormal_sigma"]),
                "environment": "urban" if site in URBAN_SITES else "rural",
            }
            for site, label in SITES.items()
        },
        "levers": {
            lever: {
                "label": LEVER_LABELS[lever],
                "limit": float(sites.loc[LEVERS[lever][0], "limit"]),
                "options": list(LIMIT_OPTIONS[lever]),
            }
            for lever in LEVERS
        },
        "exponents": {
            f"{outcome}|{environment}": [
                parameter(f"exponent_{outcome}", environment, bound)
                for bound in ("value", "low", "high")
            ]
            for outcome in OUTCOMES
            for environment in ("rural", "urban")
        },
        "response": {
            "a": parameter("pass_through_a"),
            "b": parameter("pass_through_b"),
            "range": list(RESPONSE_RANGE),
        },
        "values": {outcome: parameter(name) for outcome, name in VALUE_PARAMETERS.items()},
        "detect": {
            "tauInterurban": float(one["deaths_interurban"]),
            "zAlpha": float(stats.norm.ppf(1 - forecast.ALPHA / 2)),
            "zPower": float(stats.norm.ppf(forecast.POWER)),
        },
        "presets": [
            {
                "key": scenario.key,
                "label": scenario.label,
                "limits": scenario.limits,
                "responseShare": scenario.response_share,
                "compliance": scenario.compliance,
            }
            for scenario in PRESETS
        ],
    }


def browser_parameters_json(tables: dict[str, pd.DataFrame]) -> str:
    return json.dumps(browser_parameters(tables), ensure_ascii=False, sort_keys=True)
