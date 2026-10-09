"""The crash-severity calculator: P(fatal | a crash with a death or serious injury, its circumstances).

**Question.** Among crashes in Catalonia in which someone was killed or seriously injured, how
does the share that were fatal vary with the recorded road, conditions and crash? "Fatal" is the
file's definition: someone died within 24 hours (the file's fatal crashes equal DGT's 24-hour
counts for the four Catalan provinces in every year). The model is fitted on the Servei Català de
Trànsit file, 2010–2023. It is a model of severity *given* a severe crash: it cannot say how likely
a crash is to happen, because the file holds only crashes, and its differences between scenarios
are associations in these records, not the effect of changing a road or a condition.

**Inputs.** Each input is a circumstance the police record about the road, the conditions or the
crash, grouped into categories a reader can choose:

* *road*: the zone, the type of road and, for conventional roads, the network that owns it
  (State, regional, provincial, local). Crashes on conventional roads whose owner is recorded as
  "other" or left blank (``EXCLUDED_ROADS``) are left out of the model altogether: they were fatal
  in 3% and 53% of cases against 15–26% for the named networks, so the field records how a crash
  was documented rather than the road, and a reader could not choose them anyway;
* *crash type*, *lighting*, *weather*, *surface*, *junction*, *posted speed limit* (the signposted
  limit where the record has one: never a vehicle's speed), *time of day*;
* *road users involved*: pedestrian, bicycle, moped, motorcycle, car or van, heavy vehicle,
  other, and the number of units (vehicles and pedestrians);
* *province*: Barcelona, Girona, Lleida or Tarragona.

Police judgements of what influenced the crash, whether a driver fled, the date and the fog field
(recorded present in a tenth of urban crashes) are left out.

**Model.** A logistic regression with one intercept per zone (urban street, road through a town,
interurban road) and province, an effect for each interurban road type, and an effect for each
other input, either common to all zones or allowed to differ on urban streets and on interurban
roads. Three choices are made on data: the strength of the L2 penalty, which of the two
specifications, and whether roads through towns get the model's estimate or the average fatal
share of such roads in the province. :func:`select` makes all three with the crashes it is given
only: it fits on all but their last two years and scores those two years by log loss, on a grid of
penalties extended until the best value lies inside it. The evaluation is nested: each year
2016-2023 is predicted by a model whose three choices were made, and whose coefficients were
fitted, on the years before it (:func:`nested_rolling`), and the table of fatal shares by road
and crash type is fitted on the same years. The published model is chosen by the same rule on
every year (validation on the last two) and refitted on all of them (:func:`final_choice`). Its
coefficients are exported to ``site/models/`` for the browser, with the covariance of the
coefficients from a bootstrap of the training crashes. Every interval, in the browser and in the
tables, is ``expit(x'b +- 1.96 sqrt(x'Vx))`` or its delta-method extension to a ratio or difference
of two scenarios, so a worked example and the calculator always agree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from dgt_stats.paths import FEATURES_DATA_DIR

SEED = 20261008
FEATURES_PATH = FEATURES_DATA_DIR / "catalonia_crash_severity.parquet"
# The inner validation: the last two years of the crashes a choice may use.
VALIDATION_SPAN = 2
# The penalty grid: C = 10 ** (k / 2), half-decades from 0.001 to about 32. While the best value
# is at either end, the grid is extended by a half-decade on that side, within C_LIMITS, so that
# the chosen penalty is bracketed by worse ones.
C_EXPONENTS: tuple[int, ...] = tuple(range(-6, 4))
C_LIMITS = (1e-4, 1e3)
N_BOOTSTRAP = 500
# The design published before the nested evaluation, kept only to show what nesting changed: one
# penalty from these six, chosen by fitting on 2010-2020 and scoring 2021-2022, common effects,
# and the model's estimate on every road. Its rolling-origin score is not a test on untouched
# years: 2021 and 2022 chose the penalty, and the specification and the through-town rule were
# decided on the rolling scores themselves.
PREVIOUS_C_GRID: tuple[float, ...] = (0.1, 0.3, 1.0, 3.0, 10.0, 30.0)
PREVIOUS_TRAIN_LAST_YEAR = 2020
PREVIOUS_VALIDATION_YEARS = (2021, 2022)

# --------------------------------------------------------------------------- inputs

ZONES: dict[str, str] = {
    "urban": "Urban street",
    "through_town": "Road through a town",
    "interurban": "Interurban road",
}

# value -> (label, zone): the roads a reader can choose, and the only ones the model is fitted on.
ROADS: dict[str, tuple[str, str]] = {
    "urban_street": ("Urban street", "urban"),
    "through_town": ("Road through a town (travessera)", "through_town"),
    "motorway": ("Motorway (autopista)", "interurban"),
    "dual_carriageway": ("Dual carriageway (autovia)", "interurban"),
    "conventional_state": ("Conventional road, State network", "interurban"),
    "conventional_regional": ("Conventional road, regional network", "interurban"),
    "conventional_provincial": ("Conventional road, provincial network", "interurban"),
    "conventional_local": ("Conventional road, local (municipal)", "interurban"),
    "rural_track": ("Rural or forest track", "interurban"),
    "other_interurban": ("Other interurban road", "interurban"),
}
# The four provinces (the file's demarcations). The share of severe crashes that were fatal differs
# between them within each zone, so the model may have one intercept per province and zone
# (Barcelona the reference); whether it does is chosen on the training years, like the penalty
# (:func:`select`).
PROVINCES: dict[str, str] = {
    "Barcelona": "Barcelona",
    "Girona": "Girona",
    "Lleida": "Lleida",
    "Tarragona": "Tarragona",
}
REFERENCE_PROVINCE = "Barcelona"

# Conventional roads whose owner is recorded as "other" or left blank: a recording artefact (the
# blank is far commoner on fatal records), excluded from fitting, evaluation and every count shown.
EXCLUDED_ROADS = ("conventional_owner_other", "conventional_owner_blank")

CRASH_TYPES: dict[str, str] = {
    "pedestrian_struck": "Pedestrian struck",
    "head_on": "Head-on collision",
    "side_impact": "Side or angle collision",
    "rear_end": "Rear-end collision",
    "sideswipe": "Sideswipe",
    "run_off_road": "Ran off the road",
    "fixed_object": "Hit an object on the road",
    "fall": "Rider or occupant fell (no collision)",
    "other": "Other (including animals)",
}
LIGHTING: dict[str, str] = {
    "day": "Daylight",
    "overcast": "Daylight, overcast",
    "dawn_dusk": "Dawn or dusk",
    "night_lit": "Night, adequate street lighting",
    "night_poorly_lit": "Night, poor street lighting",
    "night_unlit": "Night, no street lighting",
}
WEATHER: dict[str, str] = {
    "fine": "Fine",
    "light_rain": "Light rain",
    "heavy_rain_snow": "Heavy rain, hail or snow",
}
SURFACE: dict[str, str] = {
    "dry": "Dry and clean",
    "wet": "Wet",
    "slippery": "Slippery, flooded, icy or snowy",
}
JUNCTION: dict[str, str] = {
    "section": "Between junctions",
    "junction": "Within a junction",
    "approach": "Within 50 m of a junction",
}
SPEED_LIMITS: dict[str, str] = {
    "not_recorded": "None recorded (generic limit)",
    "10_30": "Posted 10–30 km/h",
    "40_50": "Posted 40–50 km/h",
    "60_70": "Posted 60–70 km/h",
    "80_90": "Posted 80–90 km/h",
    "100_120": "Posted 100–120 km/h",
}
HOURS: dict[str, str] = {
    "00-05": "00:00–05:59",
    "06-09": "06:00–09:59",
    "10-13": "10:00–13:59",
    "14-17": "14:00–17:59",
    "18-21": "18:00–21:59",
    "22-23": "22:00–23:59",
}
UNITS: dict[str, str] = {"1": "One", "2": "Two", "3": "Three", "4+": "Four or more"}
USERS: dict[str, str] = {
    "pedestrian": "A pedestrian",
    "bicycle": "A bicycle",
    "moped": "A moped",
    "motorcycle": "A motorcycle",
    "light_vehicle": "A car or van",
    "heavy_vehicle": "A heavy vehicle (lorry, bus)",
    "other_unit": "Another vehicle (tram, tractor, other)",
}

CATEGORICAL: dict[str, dict[str, str]] = {
    "crash_type": CRASH_TYPES,
    "lighting": LIGHTING,
    "weather": WEATHER,
    "surface": SURFACE,
    "junction": JUNCTION,
    "speed_limit": SPEED_LIMITS,
    "hour": HOURS,
    "units": UNITS,
}
# The reference (omitted) level of every categorical input, and the calculator's defaults.
REFERENCE: dict[str, str] = {
    "road": "urban_street",
    "crash_type": "side_impact",
    "lighting": "day",
    "weather": "fine",
    "surface": "dry",
    "junction": "section",
    "speed_limit": "not_recorded",
    "hour": "10-13",
    "units": "2",
}

# --------------------------------------------------------------------------- recoding

_ROAD_TYPE = {
    "Autopista": "motorway",
    "Autovia": "dual_carriageway",
    "Camí rural/pista forestal": "rural_track",
    "Altres": "other_interurban",
}
_OWNER = {
    "Estatal": "conventional_state",
    "Autonòmica": "conventional_regional",
    "Provincial": "conventional_provincial",
    "Municipal": "conventional_local",
    "Altres": "conventional_owner_other",
}
_CRASH = {
    "Atropellament": "pedestrian_struck",
    "Sortida de via amb atropellament": "pedestrian_struck",
    "Col·lisió frontal": "head_on",
    "Envestida (frontal lateral)": "side_impact",
    "Encalç": "rear_end",
    "Fregament o col·lisió lateral": "sideswipe",
    "Resta sortides de via": "run_off_road",
    "Sortida de via amb bolcada": "run_off_road",
    "Sortida de via amb xoc o col·lisió": "run_off_road",
    "Xoc contra objecte/obstacle sense sortida prèvia de via": "fixed_object",
    "Caiguda en la via": "fall",
    "Altres": "other",
    "Xoc amb animal a la calçada": "other",
    "Sense Especificar": "other",
}
_LIGHT = {
    "De dia, dia clar": "day",
    "De dia, dia fosc": "overcast",
    "Alba o capvespre": "dawn_dusk",
    "De nit, il·luminació artificial suficient": "night_lit",
    "De nit, il·luminació artificial insuficient": "night_poorly_lit",
    "De nit, sense llum artificial": "night_unlit",
    "Sense especificar": "day",
}
_WEATHER = {
    "Bon temps": "fine",
    "Pluja dèbil": "light_rain",
    "Pluja forta": "heavy_rain_snow",
    "Calamarsa": "heavy_rain_snow",
    "Nevant": "heavy_rain_snow",
    "Sense especificar": "fine",
}
_SURFACE = {
    "Sec i net": "dry",
    "Mullat": "wet",
    "Relliscós": "slippery",
    "Inundat": "slippery",
    "Gelat": "slippery",
    "Nevat": "slippery",
    "Sense especificar": "dry",
}
_JUNCTION = {
    "En secció": "section",
    "Dintre intersecció": "junction",
    "Arribant o eixint intersecció fins 50m": "approach",
}
_LIMIT = {
    "generic limit for the road (value not recorded)": "not_recorded",
    "posted, implausible value": "not_recorded",
    "posted 10-30 km/h": "10_30",
    "posted 40-50 km/h": "40_50",
    "posted 60-70 km/h": "60_70",
    "posted 80-90 km/h": "80_90",
    "posted 100-120 km/h": "100_120",
}
_USER_COLUMNS = {
    "pedestrian": "involves_pedestrian",
    "bicycle": "involves_bicycle",
    "moped": "involves_moped",
    "motorcycle": "involves_motorcycle",
    "light_vehicle": "involves_light_vehicle",
    "heavy_vehicle": "involves_heavy_vehicle",
    "other_unit": "involves_other_unit",
}


def _recode(series: pd.Series, mapping: dict[str, str], name: str) -> pd.Series:
    out = series.map(mapping)
    if out.isna().any():
        unknown = sorted(series[out.isna()].astype(str).unique())
        raise ValueError(f"{name}: unmapped source values {unknown}")
    return out


def road_of(frame: pd.DataFrame) -> pd.Series:
    zone = frame.D_SUBZONA
    road = pd.Series("conventional_owner_blank", index=frame.index, dtype=object)
    road[zone == "Zona urbana"] = "urban_street"
    road[zone == "Travessera"] = "through_town"
    interurban = zone == "Carretera"
    typed = frame.D_TIPUS_VIA.map(_ROAD_TYPE)
    road[interurban & typed.notna()] = typed[interurban & typed.notna()]
    conventional = interurban & typed.isna()
    owner = frame.D_TITULARITAT_VIA.map(_OWNER)
    road[conventional & owner.notna()] = owner[conventional & owner.notna()]
    return road


def scenarios_from_records(frame: pd.DataFrame) -> pd.DataFrame:
    """The Catalan feature table recoded to the calculator's inputs, one row per crash."""
    units = frame.n_units.astype(int).clip(upper=4).astype(str).replace({"4": "4+"})
    out = pd.DataFrame(
        {
            "road": road_of(frame),
            "province": frame.demarcation.astype(str),
            "crash_type": _recode(frame.D_SUBTIPUS_ACCIDENT, _CRASH, "crash type"),
            "lighting": _recode(frame.D_LLUMINOSITAT, _LIGHT, "lighting"),
            "weather": _recode(frame.D_CLIMATOLOGIA, _WEATHER, "weather"),
            "surface": _recode(frame.D_SUPERFICIE, _SURFACE, "surface"),
            "junction": _recode(frame.D_INTER_SECCIO, _JUNCTION, "junction"),
            "speed_limit": _recode(frame.speed_limit_category, _LIMIT, "speed limit"),
            "hour": frame.hour_band.astype(str),
            "units": units,
        },
        index=frame.index,
    )
    for user, column in _USER_COLUMNS.items():
        out[user] = frame[column].fillna(0).astype(int)
    return out


# --------------------------------------------------------------------------- design
#
# Columns, by group:
#   intercept     zone=<zone>                 one per zone (urban, through_town, interurban)
#   province      zone_province=<zone>|<prov> each zone's departure in Girona, Lleida and Tarragona
#                                             from Barcelona province
#   road          road=<road>                 interurban roads, against the regional network
#   main          all:<input>=<level>, all:<user>
#                                             every other input, the same in every zone
#   zone effects  urban:<input>=<level>, interurban:<input>=<level>, urban:<user>, ...
#                                             (specification "by_zone" only) how each input's
#                                             association departs from the common one on urban
#                                             streets and on interurban roads
# The intercepts are barely penalised (INTERCEPT_SCALE); every other column takes the same L2
# penalty. Which specification is used is chosen on data (:func:`select`).

SPECIFICATIONS: dict[str, str] = {
    "common": "effects common to all zones",
    "by_zone": "effects that may differ on urban streets and on interurban roads",
}
DEVIATION_ZONES = ("urban", "interurban")


def zone_of(road: pd.Series) -> pd.Series:
    return road.map({key: zone for key, (_, zone) in ROADS.items()})


INTERCEPT_SCALE = 10.0


def design_columns(provinces: bool = True) -> list[str]:
    columns = [f"zone={zone}" for zone in ZONES]
    if provinces:
        columns += [
            f"zone_province={zone}|{province}"
            for zone in ZONES
            for province in PROVINCES
            if province != REFERENCE_PROVINCE
        ]
    columns += [
        f"road={road}"
        for road, (_, zone) in ROADS.items()
        if zone == "interurban" and road != REFERENCE_INTERURBAN_ROAD
    ]
    for name, levels in CATEGORICAL.items():
        columns += [f"all:{name}={level}" for level in levels if level != REFERENCE[name]]
    columns += [f"all:{user}" for user in USERS]
    return columns


REFERENCE_INTERURBAN_ROAD = "conventional_regional"


def column_group(column: str) -> str:
    if column.startswith("zone="):
        return "intercept"
    if column.startswith("zone_province="):
        return "province"
    if column.startswith("road="):
        return "road"
    return "main" if column.startswith("all:") else "zone effect"


def specification_columns(specification: str = "common", provinces: bool = True) -> list[str]:
    """The design of a specification: ``design_columns`` and, for "by_zone", every input's
    departure on urban streets and on interurban roads."""
    if specification not in SPECIFICATIONS:
        raise ValueError(f"unknown specification: {specification}")
    columns = design_columns(provinces)
    if specification == "by_zone":
        for zone in DEVIATION_ZONES:
            for name, levels in CATEGORICAL.items():
                columns += [
                    f"{zone}:{name}={level}" for level in levels if level != REFERENCE[name]
                ]
            columns += [f"{zone}:{user}" for user in USERS]
    return columns


def design_matrix(scenarios: pd.DataFrame, columns: list[str] | None = None) -> np.ndarray:
    """The 0/1 design of each scenario; the browser builds exactly the same vector."""
    columns = columns or design_columns()
    zones = zone_of(scenarios.road).to_numpy()
    roads = scenarios.road.astype(str).to_numpy()
    x = np.zeros((len(scenarios), len(columns)))
    for j, column in enumerate(columns):
        if column.startswith("zone="):
            x[:, j] = zones == column[5:]
            continue
        if column.startswith("zone_province="):
            zone, province = column[len("zone_province=") :].split("|")
            x[:, j] = (zones == zone) & (scenarios.province.astype(str).to_numpy() == province)
            continue
        if column.startswith("road="):
            x[:, j] = roads == column[5:]
            continue
        prefix, term = column.split(":", 1)
        in_zone = np.ones(len(scenarios), bool) if prefix == "all" else zones == prefix
        if "=" in term:
            name, level = term.split("=", 1)
            x[:, j] = in_zone & (scenarios[name].astype(str).to_numpy() == level)
        else:
            x[:, j] = in_zone & (scenarios[term].to_numpy() == 1)
    return x


# --------------------------------------------------------------------------- fitting


@dataclass(frozen=True)
class Fitted:
    columns: list[str]
    coef: np.ndarray
    c: float

    def logit(self, scenarios: pd.DataFrame) -> np.ndarray:
        return design_matrix(scenarios, self.columns) @ self.coef

    def predict(self, scenarios: pd.DataFrame) -> np.ndarray:
        return expit(self.logit(scenarios))


def expit(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def column_scales(columns: list[str]) -> np.ndarray:
    return np.array(
        [INTERCEPT_SCALE if column_group(c) == "intercept" else 1.0 for c in columns], dtype=float
    )


def fit_logistic(x: np.ndarray, y: np.ndarray, c: float, columns: list[str]) -> Fitted:
    """L2-penalised logistic regression whose intercepts are barely penalised.

    Multiplying a column by ``s`` before fitting and the fitted coefficient by ``s`` afterwards
    leaves the model unchanged but divides that coefficient's penalty by ``s**2``: the zone
    intercepts (``s`` = 10) are shrunk hardly at all. The returned coefficients apply to the plain
    0/1 design.
    """
    scales = column_scales(columns)
    model = LogisticRegression(
        C=c, fit_intercept=False, solver="newton-cholesky", max_iter=1_000, tol=1e-10
    )
    model.fit(x * scales, y)
    return Fitted(columns=columns, coef=model.coef_[0] * scales, c=c)


def load_all() -> pd.DataFrame:
    """Every crash of the feature table, the excluded roads included (for counting them)."""
    return pd.read_parquet(FEATURES_PATH)


def load() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """The crashes the model is fitted and evaluated on: every road but ``EXCLUDED_ROADS``."""
    frame = load_all()
    frame = frame[~road_of(frame).isin(EXCLUDED_ROADS).to_numpy()].reset_index(drop=True)
    return frame, frame.year.astype(int).to_numpy(), frame.fatal.to_numpy().astype(int)


@dataclass
class Records:
    """The fitted crashes, recoded, with their design matrices built once per specification."""

    frame: pd.DataFrame
    scenarios: pd.DataFrame
    years: np.ndarray
    y: np.ndarray
    _designs: dict[tuple[str, bool], np.ndarray] = field(default_factory=dict, repr=False)

    @property
    def zones(self) -> np.ndarray:
        return zone_of(self.scenarios.road).to_numpy()

    def design(self, specification: str, provinces: bool = True) -> tuple[list[str], np.ndarray]:
        columns = specification_columns(specification, provinces)
        key = (specification, provinces)
        if key not in self._designs:
            self._designs[key] = design_matrix(self.scenarios, columns)
        return columns, self._designs[key]


def records() -> Records:
    frame, years, y = load()
    return Records(frame, scenarios_from_records(frame), years, y)


def penalty(exponent: int) -> float:
    """The penalty C of a grid point: 10 ** (exponent / 2)."""
    return float(10.0 ** (exponent / 2))


def _log_loss(y: np.ndarray, p: np.ndarray) -> float:
    from sklearn.metrics import log_loss

    return float(log_loss(y, np.clip(p, 1e-12, 1 - 1e-12), labels=[0, 1]))


def zone_average_predictions(
    rec: Records, train: np.ndarray, test: np.ndarray, provinces: bool = True
) -> np.ndarray:
    """Each test crash given the fatal share of the training crashes in its zone and, with
    ``provinces``, its province (the zone's share where the training has none there)."""
    zones = rec.zones
    keys = pd.Series(zones)
    if provinces:
        keys = keys + "|" + rec.scenarios.province.astype(str).reset_index(drop=True)
    by_key = pd.Series(rec.y[train]).groupby(keys[train].to_numpy()).mean()
    by_zone = pd.Series(rec.y[train]).groupby(zones[train]).mean()
    out = keys[test].map(by_key).to_numpy(dtype=float, copy=True)
    missing = np.isnan(out)
    out[missing] = pd.Series(zones[test][missing]).map(by_zone).fillna(rec.y[train].mean())
    return out


# --------------------------------------------------------------------------- choices


@dataclass(frozen=True)
class Choice:
    """The three choices made on data, and the years they were made with."""

    specification: str  # a key of SPECIFICATIONS
    c: float
    through_town: str  # "average": roads through towns get the training average; "model"
    provinces: bool
    train_years: tuple[int, int]  # the inner fit
    validation_years: tuple[int, int]  # the inner validation
    c_bracketed: bool  # the chosen penalty has a worse value on each side in the grid

    @property
    def columns(self) -> list[str]:
        return specification_columns(self.specification, self.provinces)


def select(
    rec: Records, rows: np.ndarray, provinces: bool | None = None, label: str = ""
) -> tuple[Choice, pd.DataFrame]:
    """The penalty, the specification, the through-town rule and whether the model has one
    intercept per province and zone, chosen from ``rows`` alone.

    With ``provinces`` None (every test year and the published model), both designs are chosen
    as in :func:`_select_given` and the one whose chosen fit has the lower validation log loss is
    kept; the grid returned is the kept design's, with both losses. A fixed ``provinces`` is for
    tests that leave a province out, where it has no intercept of its own to learn."""
    if provinces is not None:
        return _select_given(rec, rows, provinces, label)
    candidates = {flag: _select_given(rec, rows, flag, label) for flag in (True, False)}
    losses = {
        flag: float(grid[grid.chosen].validation_log_loss.iloc[0])
        for flag, (_, grid) in candidates.items()
    }
    kept = min(losses, key=losses.get)
    choice, grid = candidates[kept]
    return choice, grid.assign(
        validation_log_loss_with_provinces=losses[True],
        validation_log_loss_without_provinces=losses[False],
    )


def _select_given(
    rec: Records, rows: np.ndarray, provinces: bool, label: str = ""
) -> tuple[Choice, pd.DataFrame]:
    """The penalty, the specification and the through-town rule, chosen from ``rows`` alone for
    a given choice of province intercepts.

    Each specification is fitted on all but the last ``VALIDATION_SPAN`` years of ``rows`` at
    every penalty of the grid (extended while its best value is at an end), and scored by log
    loss on those last years. The specification and penalty with the lowest loss are chosen.
    Roads through towns then get the average fatal share of the inner training crashes on such
    roads in the same province if that average has a lower log loss on the validation crashes
    on such roads than the chosen model's estimates; otherwise the model's estimates. Returns
    the choice and every grid point's validation scores.
    """
    from sklearn.metrics import roc_auc_score

    available = np.unique(rec.years[rows])
    validation_years = available[-VALIDATION_SPAN:]
    inner_train = rows & (rec.years < validation_years[0])
    inner_valid = rows & np.isin(rec.years, validation_years)
    y_valid = rec.y[inner_valid]
    grid = []
    best: dict[str, tuple[int, float, np.ndarray, bool]] = {}
    for specification in SPECIFICATIONS:
        columns, x = rec.design(specification, provinces)
        scored: dict[int, tuple[float, float, np.ndarray]] = {}

        def score(exponent: int) -> None:
            fitted = fit_logistic(x[inner_train], rec.y[inner_train], penalty(exponent), columns)
            p = expit(x[inner_valid] @ fitted.coef)
            scored[exponent] = (_log_loss(y_valid, p), float(roc_auc_score(y_valid, p)), p)

        for exponent in C_EXPONENTS:
            score(exponent)
        while True:
            tried = sorted(scored)
            winner = min(tried, key=lambda e: scored[e][0])
            if winner == tried[0] and penalty(tried[0] - 1) >= C_LIMITS[0]:
                score(tried[0] - 1)
            elif winner == tried[-1] and penalty(tried[-1] + 1) <= C_LIMITS[1]:
                score(tried[-1] + 1)
            else:
                break
        tried = sorted(scored)
        bracketed = tried[0] < winner < tried[-1]
        best[specification] = (winner, scored[winner][0], scored[winner][2], bracketed)
        for exponent in tried:
            grid.append(
                {
                    "fit": label,
                    "specification": specification,
                    "c": penalty(exponent),
                    "validation_log_loss": scored[exponent][0],
                    "validation_roc_auc": scored[exponent][1],
                    "best_for_specification": exponent == winner,
                }
            )
    specification = min(best, key=lambda s: best[s][1])
    exponent, _, p_valid, bracketed = best[specification]
    town = rec.zones[inner_valid] == "through_town"
    average = zone_average_predictions(rec, inner_train, inner_valid, provinces)
    town_model = _log_loss(y_valid[town], p_valid[town]) if town.any() else np.nan
    town_average = _log_loss(y_valid[town], average[town]) if town.any() else np.nan
    through_town = "average" if town.any() and town_average <= town_model else "model"
    first_train = int(rec.years[inner_train].min())
    choice = Choice(
        specification=specification,
        c=penalty(exponent),
        through_town=through_town,
        provinces=provinces,
        train_years=(first_train, int(validation_years[0]) - 1),
        validation_years=(int(validation_years[0]), int(validation_years[-1])),
        c_bracketed=bool(bracketed),
    )
    grid = pd.DataFrame(grid)
    grid["chosen"] = (grid.specification == specification) & grid.best_for_specification
    summary = {
        "through_town_validation_crashes": int(town.sum()),
        "through_town_validation_fatal": int(y_valid[town].sum()),
        "through_town_log_loss_model": town_model,
        "through_town_log_loss_average": town_average,
    }
    return choice, grid.assign(**{k: v for k, v in summary.items()})


def at_weak_limit(grid: pd.DataFrame, specification: str) -> bool:
    """The best penalty of a specification is the weakest the grid allows (C_LIMITS) and the
    validation loss had stopped changing there (by less than FLAT_LOSS over the last
    half-decade): the best model is, in effect, the unpenalised one, which no finite grid can
    bracket."""
    part = grid[grid.specification == specification].sort_values("c")
    best = part[part.best_for_specification]
    return bool(
        float(best.c.iloc[0]) == float(part.c.max()) >= C_LIMITS[1] * (1 - 1e-9)
        and abs(float(part.validation_log_loss.iloc[-1] - part.validation_log_loss.iloc[-2]))
        < FLAT_LOSS
    )


FLAT_LOSS = 1e-5


def choice_row(choice: Choice, grid: pd.DataFrame, label: str) -> dict[str, object]:
    """One row of ``sev_choices``: what was chosen for a fit, on which years, and why."""
    best = grid[grid.best_for_specification].set_index("specification")
    tried = grid[grid.specification == choice.specification].c
    return {
        "fit": label,
        "train_years": f"{choice.train_years[0]}-{choice.train_years[1]}",
        "validation_years": f"{choice.validation_years[0]}-{choice.validation_years[1]}",
        "specification": choice.specification,
        "c": choice.c,
        "c_bracketed": choice.c_bracketed,
        "c_at_weak_limit": at_weak_limit(grid, choice.specification),
        "c_lowest_tried": float(tried.min()),
        "c_highest_tried": float(tried.max()),
        **{
            f"validation_log_loss_{spec}": float(best.loc[spec, "validation_log_loss"])
            for spec in SPECIFICATIONS
        },
        **{f"c_best_{spec}": float(best.loc[spec, "c"]) for spec in SPECIFICATIONS},
        **{
            f"c_bracketed_{spec}": bool(
                grid[grid.specification == spec].c.min()
                < best.loc[spec, "c"]
                < grid[grid.specification == spec].c.max()
            )
            for spec in SPECIFICATIONS
        },
        "through_town": choice.through_town,
        "provinces": choice.provinces,
        **{
            column: float(grid[column].iloc[0])
            for column in (
                "validation_log_loss_with_provinces",
                "validation_log_loss_without_provinces",
            )
            if column in grid
        },
        **{
            column: grid[column].iloc[0]
            for column in (
                "through_town_validation_crashes",
                "through_town_validation_fatal",
                "through_town_log_loss_model",
                "through_town_log_loss_average",
            )
        },
    }


def fit_chosen(rec: Records, choice: Choice, train: np.ndarray) -> Fitted:
    columns, x = rec.design(choice.specification, choice.provinces)
    return fit_logistic(x[train], rec.y[train], choice.c, columns)


def predict_chosen(rec: Records, choice: Choice, train: np.ndarray, test: np.ndarray) -> np.ndarray:
    """What the calculator would show for each test crash, fitted on ``train`` with ``choice``:
    the model's estimate, or on roads through towns the training average if the choice says so."""
    _, x = rec.design(choice.specification, choice.provinces)
    p = expit(x[test] @ fit_chosen(rec, choice, train).coef)
    if choice.through_town == "average":
        town = rec.zones[test] == "through_town"
        p[town] = zone_average_predictions(rec, train, test, choice.provinces)[town]
    return p


def previous_choice(rec: Records) -> Choice:
    """The design published before the nested evaluation (``PREVIOUS_C_GRID``): the penalty with
    the lowest log loss on 2021-2022 after fitting 2010-2020, common effects, the model's estimate
    on every road. Kept only to show what nesting changed."""
    columns, x = rec.design("common")
    train = rec.years <= PREVIOUS_TRAIN_LAST_YEAR
    valid = np.isin(rec.years, PREVIOUS_VALIDATION_YEARS)
    losses = {
        c: _log_loss(
            rec.y[valid], expit(x[valid] @ fit_logistic(x[train], rec.y[train], c, columns).coef)
        )
        for c in PREVIOUS_C_GRID
    }
    return Choice(
        specification="common",
        c=min(losses, key=losses.get),
        through_town="model",
        provinces=True,
        train_years=(int(rec.years.min()), PREVIOUS_TRAIN_LAST_YEAR),
        validation_years=(PREVIOUS_VALIDATION_YEARS[0], PREVIOUS_VALIDATION_YEARS[-1]),
        c_bracketed=False,
    )


# --------------------------------------------------------------------------- evaluation

ROLLING_TEST_YEARS: tuple[int, ...] = tuple(range(2016, 2024))
TABLE_KEYS = ("road", "crash_type")
# The steps from the previous design to the nested one, as columns of the rolling predictions:
# each adds one choice made on the years before the test year.
STEPS: dict[str, str] = {
    "previous_design": "previous design: penalty chosen once on 2021-2022, common effects, the "
    "model's estimate on roads through towns (not nested)",
    "nested_penalty": "penalty chosen on the years before each test year; common effects; the "
    "model's estimate on roads through towns",
    "nested_penalty_specification": "penalty and specification chosen on the years before each "
    "test year; the model's estimate on roads through towns",
    "nested_with_provinces": "penalty, specification and through-town rule chosen on the years "
    "before each test year; one intercept per province and zone kept in every year",
    "calculator": "nested: penalty, specification, through-town rule and province intercepts "
    "chosen on the years before each test year (published)",
}


def _trees(seed: int = SEED):
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OrdinalEncoder

    categorical = ["road", "province", *CATEGORICAL]
    prep = ColumnTransformer(
        [
            (
                "cat",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                categorical,
            ),
            ("num", "passthrough", list(USERS)),
        ]
    )
    model = HistGradientBoostingClassifier(
        categorical_features=[True] * len(categorical) + [False] * len(USERS),
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=40,
        l2_regularization=1.0,
        max_iter=250,
        random_state=seed,
    )
    return Pipeline([("prep", prep), ("model", model)])


def _table(train: pd.DataFrame, y: np.ndarray, test: pd.DataFrame) -> np.ndarray:
    prior = y.mean()
    grouped = train[list(TABLE_KEYS)].assign(y=y).groupby(list(TABLE_KEYS)).y
    rates = grouped.agg(["sum", "size"])
    rates["rate"] = (rates["sum"] + 20 * prior) / (rates["size"] + 20)
    merged = test[list(TABLE_KEYS)].merge(rates.rate.reset_index(), on=list(TABLE_KEYS), how="left")
    return merged.rate.fillna(prior).to_numpy()


@dataclass(frozen=True)
class Nested:
    predictions: pd.DataFrame  # one row per test crash, one column per estimator or step
    choices: pd.DataFrame  # sev_choices: one row per test year
    grid: pd.DataFrame  # sev_penalty: every grid point of every test year's inner validation


def nested_rolling(rec: Records | None = None, comparators: bool = True) -> Nested:
    """Each year 2016-2023 predicted from the years before it, every choice nested.

    For test year ``t`` the penalty, the specification, the through-town rule and the province
    intercepts are chosen by :func:`select` on the years before ``t`` (fit on all but the last two, score those two), the
    model is refitted on all years before ``t`` and predicts ``t``. The table of fatal shares by
    road and crash type is fitted on the same years. With ``comparators``, also gradient-boosted
    trees on the same inputs (fixed settings, fitted on the same years) and the steps from the
    previous design (``STEPS``)."""
    rec = rec or records()
    previous = previous_choice(rec) if comparators else None
    pieces, choices, grids = [], [], []
    for year in ROLLING_TEST_YEARS:
        train, test = rec.years < year, rec.years == year
        choice, grid = select(rec, train, label=str(year))
        choices.append(choice_row(choice, grid, str(year)) | {"test_year": year})
        grids.append(grid.assign(test_year=year))
        frame = {
            "cat_crash_id": rec.frame.cat_crash_id[test].to_numpy(),
            "year": year,
            "road": rec.scenarios.road[test].to_numpy(),
            "zone": rec.zones[test],
            "province": rec.scenarios.province[test].astype(str).to_numpy(),
            "barcelona_city": (rec.frame.municipality[test] == "Barcelona").to_numpy(),
            "fatal": rec.y[test],
            "calculator": predict_chosen(rec, choice, train, test),
            "road_x_crash_table": _table(rec.scenarios[train], rec.y[train], rec.scenarios[test]),
        }
        if comparators:
            # The earlier steps keep one intercept per province and zone, as the previous design
            # did, so their choices come from the selection with province intercepts.
            kept, kept_grid = (
                (choice, grid)
                if choice.provinces
                else _select_given(rec, train, True, label=str(year))
            )
            best = kept_grid[kept_grid.best_for_specification].set_index("specification").c
            common = Choice(
                "common",
                float(best["common"]),
                "model",
                True,
                kept.train_years,
                kept.validation_years,
                kept.c_bracketed,
            )
            frame["previous_design"] = predict_chosen(rec, previous, train, test)
            frame["nested_penalty"] = predict_chosen(rec, common, train, test)
            frame["nested_penalty_specification"] = predict_chosen(
                rec,
                Choice(
                    kept.specification,
                    kept.c,
                    "model",
                    True,
                    kept.train_years,
                    kept.validation_years,
                    kept.c_bracketed,
                ),
                train,
                test,
            )
            frame["nested_with_provinces"] = predict_chosen(rec, kept, train, test)
            trees = _trees().fit(rec.scenarios[train], rec.y[train])
            frame["boosted_trees"] = trees.predict_proba(rec.scenarios[test])[:, 1]
        pieces.append(pd.DataFrame(frame))
    return Nested(
        predictions=pd.concat(pieces, ignore_index=True),
        choices=pd.DataFrame(choices),
        grid=pd.concat(grids, ignore_index=True),
    )


# --------------------------------------------------------------------------- final model


def geography(rec: Records | None = None) -> pd.DataFrame:
    """How the calculator's model and the road x crash-type table hold in places they were not
    fitted on: each demarcation predicted from the other three, and Barcelona city's urban
    streets predicted from the urban streets of the rest of Catalonia (all years). Every choice
    is made by :func:`select` on the training crashes alone."""
    from dgt_stats.model_review import scores, wilson

    rec = rec or records()
    urban = rec.zones == "urban"
    city = (rec.frame.municipality == "Barcelona").to_numpy()
    rows = [
        (f"{name} from the other demarcations", ~test, test)
        for name, test in (
            (name, (rec.frame.demarcation == name).to_numpy())
            for name in sorted(rec.frame.demarcation.unique())
        )
    ]
    rows.append(
        ("Barcelona city's urban streets from the rest of Catalonia's", urban & ~city, urban & city)
    )
    out = []
    for label, train, test in rows:
        # A province left out has no intercept of its own to learn, so the test uses none.
        choice, _ = select(rec, train, provinces=False, label=label)
        predictions = {
            "calculator": predict_chosen(rec, choice, train, test),
            "road_x_crash_table": _table(rec.scenarios[train], rec.y[train], rec.scenarios[test]),
        }
        low, high = wilson(rec.y[test].sum(), test.sum())
        for name, p in predictions.items():
            out.append(
                {"test": label, "estimator": name}
                | scores(rec.y[test], p)
                | {
                    "observed_low": low,
                    "observed_high": high,
                    "specification": choice.specification,
                    "c": choice.c,
                    "through_town": choice.through_town,
                }
            )
    return pd.DataFrame(out)


def final_choice(rec: Records | None = None) -> tuple[Choice, pd.DataFrame]:
    """The published model's choices, by the rule of every test year: :func:`select` on all the
    crashes, so the last two years validate a fit on the years before them."""
    rec = rec or records()
    return select(rec, np.ones(len(rec.y), dtype=bool), label="published model")


def final_fit(choice: Choice, rec: Records | None = None) -> tuple[Fitted, np.ndarray]:
    """The calculator's model on every crash, and the training design matrix."""
    rec = rec or records()
    columns, x = rec.design(choice.specification, choice.provinces)
    return fit_logistic(x, rec.y, choice.c, columns), x


def bootstrap_draws(
    x: np.ndarray, y: np.ndarray, c: float, columns: list[str], n_boot: int = N_BOOTSTRAP
) -> np.ndarray:
    """Coefficients refitted on crashes resampled with replacement, one row per draw."""
    rng = np.random.default_rng(SEED)
    draws = np.empty((n_boot, x.shape[1]))
    for b in range(n_boot):
        index = rng.integers(0, len(y), len(y))
        draws[b] = fit_logistic(x[index], y[index], c, columns).coef
    return draws


def prediction_interval(
    x: np.ndarray, coef: np.ndarray, covariance: np.ndarray, z: float = 1.959964
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Point prediction and 95% interval: logit +- z * sqrt(x' V x), mapped to probabilities."""
    logit = x @ coef
    se = np.sqrt(np.einsum("ij,jk,ik->i", x, covariance, x))
    return expit(logit), expit(logit - z * se), expit(logit + z * se)


# --------------------------------------------------------------------------- export

EXPORT_DECIMALS = 8
SUPPORT_FEW = 20  # fewer similar training crashes than this: the page warns


def support_key(zone: str, crash_type: str, users: list[str], units: str) -> str:
    """The key of "similar crashes": same zone, crash type, road users and number of units."""
    return f"{zone}|{crash_type}|{'+'.join(sorted(users)) or 'none'}|{units}"


def support_table(scenarios: pd.DataFrame, y: np.ndarray) -> dict[str, list[int]]:
    zones = zone_of(scenarios.road).to_numpy()
    flags = scenarios[list(USERS)].to_numpy()
    keys = [
        support_key(zone, crash, [u for u, f in zip(USERS, row) if f], units)
        for zone, crash, row, units in zip(
            zones, scenarios.crash_type, flags, scenarios.units.astype(str)
        )
    ]
    counts = pd.DataFrame({"key": keys, "y": y}).groupby("key").y.agg(["size", "sum"])
    return {key: [int(n), int(k)] for key, (n, k) in counts.iterrows()}


def level_support(scenarios: pd.DataFrame) -> dict[str, int]:
    """Training crashes per road and input level ("road|input=level", "road|user"), for the
    page's warnings: an input level rarely or never recorded on the chosen road is flagged."""
    roads = scenarios.road.astype(str)
    out: dict[str, int] = {}
    for name in CATEGORICAL:
        counts = pd.crosstab(roads, scenarios[name].astype(str))
        for road in counts.index:
            for level in counts.columns:
                out[f"{road}|{name}={level}"] = int(counts.loc[road, level])
    for user in USERS:
        counts = scenarios[scenarios[user] == 1].groupby(roads).size()
        for road, n in counts.items():
            out[f"{road}|{user}"] = int(n)
    return out


def _zone_masks(scenarios: pd.DataFrame) -> dict[str, np.ndarray]:
    zones = zone_of(scenarios.road).to_numpy()
    provinces = scenarios.province.astype(str).to_numpy()
    out = {zone: zones == zone for zone in ZONES}
    for zone in ZONES:
        for province in PROVINCES:
            out[f"{zone}|{province}"] = (zones == zone) & (provinces == province)
    return out | {"all": np.ones(len(scenarios), dtype=bool)}


def zone_average(scenarios: pd.DataFrame, y: np.ndarray) -> dict[str, float]:
    """The share of the fitted crashes that were fatal: overall, in each zone, and in each zone of
    each province ("zone|province")."""
    return {key: float(y[mask].mean()) for key, mask in _zone_masks(scenarios).items()}


def zone_counts(scenarios: pd.DataFrame, y: np.ndarray) -> dict[str, list[float]]:
    """For the same keys as :func:`zone_average`: the fitted crashes, the fatal ones, and the
    Wilson 95% interval of their fatal share, ``[crashes, fatal, low, high]``."""
    from dgt_stats.model_review import wilson

    out: dict[str, list[float]] = {}
    for key, mask in _zone_masks(scenarios).items():
        n, k = int(mask.sum()), int(y[mask].sum())
        low, high = wilson(k, n)
        out[key] = [n, k, round(float(low), EXPORT_DECIMALS), round(float(high), EXPORT_DECIMALS)]
    return out


def _broken_counts(scenarios: pd.DataFrame, through_town: str = "average") -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in scenarios.to_dict("records"):
        for rule in check_scenario(record, through_town):
            counts[rule] = counts.get(rule, 0) + 1
    return counts


def input_specification(
    scenarios: pd.DataFrame | None = None,
    y: np.ndarray | None = None,
    choice: Choice | None = None,
) -> dict[str, object]:
    """Every input, its type, its levels with labels, its default, and the rules between them.

    With the training records, the rule texts quote how many records each rare combination has.
    With the published ``choice``, roads through towns get the "average" rule only if the choice
    gives them the average, and its text names the years the choice was made on."""
    inputs: dict[str, object] = {
        "road": {
            "label": "Road",
            "type": "categorical",
            "levels": [
                {"value": road, "label": label, "zone": zone}
                for road, (label, zone) in ROADS.items()
            ],
            # The calculator opens on the worked examples' reference crash.
            "default": REFERENCE_INTERURBAN_ROAD,
        }
    }
    inputs["province"] = {
        "label": "Province",
        "type": "place",
        "levels": [{"value": key, "label": label} for key, label in PROVINCES.items()],
        "default": REFERENCE_PROVINCE,
    }
    labels = {
        "crash_type": "Type of crash",
        "lighting": "Lighting",
        "weather": "Weather",
        "surface": "Road surface",
        "junction": "Junction",
        "speed_limit": "Posted speed limit",
        "hour": "Time of day",
        "units": "Vehicles and pedestrians involved",
    }
    for name, levels in CATEGORICAL.items():
        inputs[name] = {
            "label": labels[name],
            "type": "categorical",
            "levels": [{"value": v, "label": label} for v, label in levels.items()],
            "default": REFERENCE[name],
        }
    inputs["users"] = {
        "label": "Road users involved",
        "type": "flags",
        "levels": [{"value": u, "label": label} for u, label in USERS.items()],
        "default": ["light_vehicle"],
    }
    through_town = choice.through_town if choice is not None else "average"
    total = len(scenarios) if scenarios is not None else None
    counts = _broken_counts(scenarios, through_town) if scenarios is not None else {}

    def records(rule: str) -> str:
        if total is None:
            return ""
        return f" ({counts.get(rule, 0):,} of {total:,} crashes)"

    rules = [
        {
            "id": "at_least_one_user",
            "kind": "error",
            "text": "Tick at least one road user involved.",
        },
        {
            "id": "units_cover_users",
            "kind": "error",
            "text": "The number of vehicles and pedestrians must be at least the number of "
            "kinds of road user ticked.",
        },
        {
            "id": "pedestrian_struck_needs_pedestrian",
            "kind": "error",
            "text": "A crash in which a pedestrian was struck must involve a pedestrian.",
        },
        {
            "id": "collision_with_one_unit",
            "kind": "warning",
            "text": "A collision with only one vehicle or pedestrian involved is rare in the "
            f"records{records('collision_with_one_unit')}.",
        },
        {
            "id": "pedestrian_without_vehicle",
            "kind": "warning",
            "text": "A crash involving a pedestrian and no vehicle is rare in the records"
            f"{records('pedestrian_without_vehicle')}.",
        },
        {
            "id": "few_similar",
            "kind": "warning",
            "threshold": SUPPORT_FEW,
            "text": "Fewer than {threshold} recorded crashes share this zone, crash type, road "
            "users and number involved: the estimate rests on the model's assumptions more than "
            "on similar crashes.",
        },
        {
            "id": "rare_level",
            "kind": "warning",
            "threshold": SUPPORT_FEW,
            "text": "Fewer than {threshold} recorded crashes on this road {input}: the estimate "
            "for it is extrapolated, and its interval does not show how few records there are.",
        },
    ]
    if through_town == "average":
        when = (
            f", on {choice.validation_years[0]}–{choice.validation_years[1]} with the model "
            f"fitted on {choice.train_years[0]}–{choice.train_years[1]}"
            if choice is not None
            else ""
        )
        rules.append(
            {
                "id": "through_town",
                "kind": "average",
                "text": "On roads through towns the average fatal share of such roads in the "
                "province predicted later crashes better than the model's estimates did"
                f"{when}, so the average is shown instead of an estimate.",
            }
        )
    return {
        "inputs": inputs,
        "rules": rules,
        "collision_types": list(COLLISION_TYPES),
        "through_town": through_town,
    }


COLLISION_TYPES = ("head_on", "side_impact", "rear_end", "sideswipe", "pedestrian_struck")
UNIT_COUNTS = {"1": 1, "2": 2, "3": 3, "4+": None}  # None: four or more, no upper bound
# The conditions rules use time bands that hold all year in Catalonia: no daylight before 06:00
# or from 22:00, and neither dawn, dusk nor night between 10:00 and 13:59. The other bands can
# have every lighting at some time of year.
DAYLIGHT = ("day", "overcast")
HOURS_WITHOUT_DAYLIGHT = ("00-05", "22-23")
HOURS_OF_DAYLIGHT_ONLY = ("10-13",)


def check_scenario(scenario: dict[str, object], through_town: str = "average") -> list[str]:
    """The ids of the rules a scenario breaks (errors and the scenario-level warnings).
    ``through_town`` is the published choice for roads through towns ("average" or "model").
    The browser engine's ``check`` applies the same rules (``assets/severity-engine.js``)."""
    users = [u for u in USERS if scenario.get(u)]
    units = UNIT_COUNTS[str(scenario["units"])]
    broken = []
    if not users:
        broken.append("at_least_one_user")
    if units is not None and units < len(users):
        broken.append("units_cover_users")
    if scenario["crash_type"] == "pedestrian_struck" and not scenario.get("pedestrian"):
        broken.append("pedestrian_struck_needs_pedestrian")
    if scenario["weather"] == "heavy_rain_snow" and scenario["surface"] == "dry":
        broken.append("heavy_rain_on_dry_surface")
    daylight = scenario["lighting"] in DAYLIGHT
    if (scenario["hour"] in HOURS_WITHOUT_DAYLIGHT and daylight) or (
        scenario["hour"] in HOURS_OF_DAYLIGHT_ONLY and not daylight
    ):
        broken.append("lighting_outside_hours")
    if scenario["crash_type"] in COLLISION_TYPES and units == 1:
        broken.append("collision_with_one_unit")
    if users == ["pedestrian"]:
        broken.append("pedestrian_without_vehicle")
    if through_town == "average" and ROADS[str(scenario["road"])][1] == "through_town":
        broken.append("through_town")
    return broken


def model_id(columns: list[str], coefficients: list[float]) -> str:
    """A short hash of the exported model, so the page can tell that its parts belong together."""
    import hashlib

    digest = hashlib.sha256(json.dumps([columns, coefficients]).encode()).hexdigest()
    return digest[:12]


def export(
    fitted: Fitted,
    covariance: np.ndarray,
    scenarios: pd.DataFrame,
    y: np.ndarray,
    evaluation: dict[str, object],
    excluded: dict[str, int],
    years: tuple[int, int],
    choice: Choice,
) -> dict[str, object]:
    """Everything the page needs to reproduce :func:`prediction_interval` for any scenario.

    ``years`` is the first and last year of the fitted crashes, read from the data; ``excluded``
    the crashes left out (``EXCLUDED_ROADS``) and how many of them were fatal; ``choice`` the
    published model's choices."""
    k = len(fitted.columns)
    lower = [
        round(float(covariance[i, j]), EXPORT_DECIMALS + 2) for i in range(k) for j in range(i + 1)
    ]
    coefficients = [round(float(b), EXPORT_DECIMALS) for b in fitted.coef]
    return {
        "model": "catalonia_crash_severity_calculator",
        "model_id": model_id(fitted.columns, coefficients),
        "question": "Of crashes in Catalonia with a death or a serious injury, the share that "
        "were fatal (someone died within 24 hours), given the recorded road, conditions and "
        "crash",
        "source": "Servei Català de Trànsit, crashes with a death or serious injury, "
        f"{years[0]}-{years[1]}",
        "training": {
            "years": [int(years[0]), int(years[1])],
            "crashes": int(len(y)),
            "fatal": int(y.sum()),
            "excluded_owner_not_recorded": int(excluded["crashes"]),
            "excluded_fatal": int(excluded["fatal"]),
        },
        "zone_average": zone_average(scenarios, y),
        "zone_counts": zone_counts(scenarios, y),
        "estimator": "logistic regression, L2 penalty, one intercept per zone"
        + (" and province, " if choice.provinces else ", ")
        + SPECIFICATIONS[choice.specification],
        "penalty": {"C": fitted.c},
        "choice": {
            "specification": choice.specification,
            "C": choice.c,
            "through_town": choice.through_town,
            "provinces": choice.provinces,
            "train_years": list(choice.train_years),
            "validation_years": list(choice.validation_years),
            "c_bracketed": choice.c_bracketed,
        },
        "columns": fitted.columns,
        "coefficients": coefficients,
        "covariance_lower": lower,
        "interval": "95% confidence interval for the share among crashes like this one: "
        "logit +- 1.96 * sqrt(x' V x), V the covariance of the coefficients over "
        f"{N_BOOTSTRAP} bootstrap refits",
        **input_specification(scenarios, y, choice),
        "support": support_table(scenarios, y),
        "level_support": level_support(scenarios),
        "evaluation": evaluation,
    }


def scenario_frame(scenario: dict[str, object]) -> pd.DataFrame:
    """One scenario as a one-row frame; an unknown road or input level is an error, as in the
    browser, never silently the reference level."""
    if str(scenario["road"]) not in ROADS:
        raise ValueError(f"unknown road: {scenario['road']}")
    if str(scenario["province"]) not in PROVINCES:
        raise ValueError(f"unknown province: {scenario['province']}")
    for name, levels in CATEGORICAL.items():
        if str(scenario[name]) not in levels:
            raise ValueError(f"unknown {name}: {scenario[name]}")
    row = {name: scenario[name] for name in ("road", "province", *CATEGORICAL)}
    row |= {user: int(bool(scenario.get(user))) for user in USERS}
    return pd.DataFrame([row])


def predict_exported(model: dict[str, object], scenario: dict[str, object]) -> dict[str, float]:
    """The prediction the page shows, computed from the exported JSON (the parity reference)."""
    columns = list(model["columns"])
    coef = np.array(model["coefficients"], dtype=float)
    x = design_matrix(scenario_frame(scenario), columns)
    p, low, high = prediction_interval(x, coef, _covariance(model))
    return {"probability": float(p[0]), "low": float(low[0]), "high": float(high[0])}


# --------------------------------------------------------------------------- findings

# A reference crash: two vehicles colliding side-on on a regional conventional road, in daylight,
# fine and dry, between junctions, no posted limit recorded, late morning, a car or van involved.
REFERENCE_SCENARIO: dict[str, object] = {
    "road": "conventional_regional",
    "province": REFERENCE_PROVINCE,
    "crash_type": "side_impact",
    "lighting": "day",
    "weather": "fine",
    "surface": "dry",
    "junction": "section",
    "speed_limit": "not_recorded",
    "hour": "10-13",
    "units": "2",
    "light_vehicle": 1,
}
URBAN_REFERENCE: dict[str, object] = REFERENCE_SCENARIO | {"road": "urban_street"}


def _variants(base: dict[str, object]) -> list[tuple[str, str, dict[str, object]]]:
    """``base`` with one input changed at a time (only changes that keep the crash itself
    possible). The conditions rules are not applied: the worked examples compare the model's
    terms one at a time from the reference crash (a lighting term is the same at every time of
    day), so a change such as night at 10:00–13:59 keeps its row although the calculator would
    ask for another time."""
    out = []
    zone = ROADS[str(base["road"])][1]
    for road, (_, road_zone) in ROADS.items():
        if road == base["road"]:
            continue
        if zone == "urban" and road_zone == "interurban":
            continue
        out.append(("road", road, base | {"road": road}))
    for province in PROVINCES:
        if province != base["province"]:
            out.append(("province", province, base | {"province": province}))
    for name, levels in CATEGORICAL.items():
        for level in levels:
            if level == base[name] or name == "units":
                continue
            scenario = base | {name: level}
            if level == "pedestrian_struck":
                scenario = scenario | {"pedestrian": 1}
            out.append((name, level, scenario))
    for user in USERS:
        if user == "light_vehicle":
            continue
        out.append(("users", user, base | {user: 1}))
    return [(n, level, s) for n, level, s in out if not set(check_scenario(s)) & CRASH_ERRORS]


# The rules the calculator refuses: those of the crash itself (at most one recorded crash breaks
# each) and those of the conditions (a few recorded crashes break them, recording
# inconsistencies kept in the fit).
CRASH_ERRORS = {"at_least_one_user", "units_cover_users", "pedestrian_struck_needs_pedestrian"}
CONDITION_ERRORS = {"heavy_rain_on_dry_surface", "lighting_outside_hours"}
ERRORS = CRASH_ERRORS | CONDITION_ERRORS


def scenario_contrasts(
    fitted: Fitted, covariance: np.ndarray, base: dict[str, object]
) -> pd.DataFrame:
    """Predicted fatal share of ``base`` and of each one-input change, and the ratio of the two,
    with the intervals the calculator gives (:func:`prediction_interval`, :func:`contrast`).
    Associations between modelled scenarios, not effects."""
    variants = _variants(base)
    frames = [scenario_frame(base)] + [scenario_frame(s) for _, _, s in variants]
    x = design_matrix(pd.concat(frames, ignore_index=True), fitted.columns)
    point, low, high = prediction_interval(x, fitted.coef, covariance)
    rows = []
    for i, (name, level, _) in enumerate(variants, start=1):
        compared = contrast(x[i], x[0], fitted.coef, covariance)
        rows.append(
            {
                "input": name,
                "level": level,
                "probability": point[i],
                "probability_low": low[i],
                "probability_high": high[i],
                "base_probability": point[0],
                "ratio": compared["ratio"],
                "ratio_low": compared["ratio_low"],
                "ratio_high": compared["ratio_high"],
            }
        )
    return pd.DataFrame(rows)


def marginal_and_adjusted(
    fitted: Fitted, draws: np.ndarray, rec: Records | None = None
) -> pd.DataFrame:
    """For each input level: the raw fatal share of the crashes with it, and the model's average
    predicted share when every crash is given that level (standardised to the observed mix)."""
    rec = rec or records()
    scenarios, y = rec.scenarios, rec.y
    rows = []
    for name in ("road", *CATEGORICAL):
        levels = list(ROADS) if name == "road" else list(CATEGORICAL[name])
        for level in levels:
            has = (scenarios[name].astype(str) == level).to_numpy()
            if has.sum() == 0:
                continue
            if name == "road":
                # Standardise within the level's own zone: a road is only compared with roads
                # of the zones it can be.
                zone = ROADS[level][1]
                pool = scenarios[(zone_of(scenarios.road) == zone).to_numpy()].copy()
            else:
                pool = scenarios.copy()
            pool[name] = level
            if level == "pedestrian_struck":
                pool["pedestrian"] = 1
            x = design_matrix(pool, fitted.columns)
            standardised = expit(x @ fitted.coef).mean()
            boot = expit(x @ draws[:100].T).mean(axis=0)
            rows.append(
                {
                    "input": name,
                    "level": level,
                    "crashes": int(has.sum()),
                    "fatal": int(y[has].sum()),
                    "raw_share": float(y[has].mean()),
                    "standardised_share": float(standardised),
                    "standardised_low": float(np.percentile(boot, 2.5)),
                    "standardised_high": float(np.percentile(boot, 97.5)),
                }
            )
    return pd.DataFrame(rows)


def stability(choice: Choice, rec: Records | None = None) -> pd.DataFrame:
    """Key contrasts from models fitted separately on two periods and on two areas, with the
    published model's specification and penalty."""
    rec = rec or records()
    years, y, frame = rec.years, rec.y, rec.frame
    columns, x = rec.design(choice.specification, choice.provinces)
    c = choice.c
    splits = {
        "2010-2016": years <= 2016,
        "2017-2023": years >= 2017,
        "Barcelona province": (frame.demarcation == "Barcelona").to_numpy(),
        "Girona, Lleida, Tarragona": (frame.demarcation != "Barcelona").to_numpy(),
    }
    rows = []
    for label, mask in splits.items():
        fitted = fit_logistic(x[mask], y[mask], c, columns)
        covariance = np.cov(bootstrap_draws(x[mask], y[mask], c, columns, n_boot=200), rowvar=False)
        for base_name, base in (("interurban", REFERENCE_SCENARIO), ("urban", URBAN_REFERENCE)):
            table = scenario_contrasts(fitted, covariance, base)
            table.insert(0, "base", base_name)
            table.insert(0, "subset", label)
            table["crashes"] = int(mask.sum())
            rows.append(table)
    return pd.concat(rows, ignore_index=True)


def _covariance(model: dict[str, object]) -> np.ndarray:
    k = len(model["columns"])
    covariance = np.zeros((k, k))
    position = 0
    for i in range(k):
        for j in range(i + 1):
            covariance[i, j] = covariance[j, i] = model["covariance_lower"][position]
            position += 1
    return covariance


def compare_exported(
    model: dict[str, object], first: dict[str, object], second: dict[str, object]
) -> dict[str, float]:
    """The page's two-scenario comparison, computed from the exported JSON (the parity
    reference): :func:`contrast` on the exported coefficients and covariance."""
    columns = list(model["columns"])
    coef = np.array(model["coefficients"], dtype=float)
    xa = design_matrix(scenario_frame(first), columns)[0]
    xb = design_matrix(scenario_frame(second), columns)[0]
    return contrast(xa, xb, coef, _covariance(model))


def contrast(
    xa: np.ndarray, xb: np.ndarray, coef: np.ndarray, covariance: np.ndarray
) -> dict[str, float]:
    """The first scenario's predicted fatal share against the second's, as a ratio and as a
    difference in percentage points, each with a 95% interval from the delta method on the
    coefficient covariance. An association between two modelled scenarios, not the effect of
    changing one circumstance."""
    pa, pb = expit(xa @ coef), expit(xb @ coef)
    z = 1.959964
    gradient_ratio = (1 - pa) * xa - (1 - pb) * xb  # of log(pa / pb)
    se_ratio = float(np.sqrt(gradient_ratio @ covariance @ gradient_ratio))
    log_ratio = float(np.log(pa / pb))
    gradient_difference = pa * (1 - pa) * xa - pb * (1 - pb) * xb
    se_difference = float(np.sqrt(gradient_difference @ covariance @ gradient_difference))
    return {
        "ratio": float(pa / pb),
        "ratio_low": float(np.exp(log_ratio - z * se_ratio)),
        "ratio_high": float(np.exp(log_ratio + z * se_ratio)),
        "difference": float(pa - pb),
        "difference_low": float(pa - pb - z * se_difference),
        "difference_high": float(pa - pb + z * se_difference),
    }
