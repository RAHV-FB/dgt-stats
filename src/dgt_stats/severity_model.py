"""The crash-severity calculator: P(fatal | a crash with a death or serious injury, its circumstances).

**Question.** Among crashes in Catalonia in which someone was killed or seriously injured, how
does the share that were fatal vary with the recorded road, conditions and crash? The model is
fitted on the Servei Català de Trànsit file (2010–2023, 24,478 crashes, 3,093 fatal). It is a model
of severity *given* a severe crash: it cannot say how likely a crash is to happen, because the
file holds only crashes, and its differences between scenarios are associations in these records,
not the effect of changing a road or a condition.

**Inputs.** Each input is a circumstance the police record about the road, the conditions or the
crash, grouped into categories a reader can choose:

* *road*: the zone, the type of road and, for conventional roads, the network that owns it
  (State, regional, provincial, local). Conventional roads whose owner is recorded as "other" or
  left blank are kept in training as two categories of their own (fatal in 3% and 54% of crashes
  against 15–26% for the named networks, a recording artefact) and are never offered as choices;
* *crash type*, *lighting*, *weather*, *surface*, *junction*, *posted speed limit* (the signposted
  limit where the record has one: never a vehicle's speed), *time of day*;
* *road users involved*: pedestrian, bicycle, moped, motorcycle, car or van, heavy vehicle,
  other, and the number of units (vehicles and pedestrians).

Police judgements of what influenced the crash, whether a driver fled, the province, the date and
the fog field (recorded present in a tenth of urban crashes) are left out.

**Model.** A logistic regression whose every effect may differ between urban streets, through-town
roads and interurban roads (each one-hot input is interacted with the zone), fitted with an L2
penalty whose strength is chosen on 2021–2022 after training on 2010–2020. It is compared, on the
same rolling origins, with gradient-boosted trees on the same inputs and with the table of fatal
shares by road and crash type. Its coefficients are exported to ``site/models/`` for the browser,
with the covariance of the coefficients from a bootstrap of the training crashes, so that the page
can give an interval for every prediction with the same arithmetic as :func:`predict`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from dgt_stats.paths import FEATURES_DATA_DIR

SEED = 20261008
FEATURES_PATH = FEATURES_DATA_DIR / "catalonia_crash_severity.parquet"
TRAIN_LAST_YEAR = 2020
VALIDATION_YEARS = (2021, 2022)
C_GRID: tuple[float, ...] = (0.03, 0.1, 0.3, 1.0, 3.0)
N_BOOTSTRAP = 200

# --------------------------------------------------------------------------- inputs

ZONES: dict[str, str] = {
    "urban": "Urban street",
    "through_town": "Road through a town",
    "interurban": "Interurban road",
}

# value -> (label, zone). The two "owner_*" values are recording categories used in training only.
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
    "conventional_owner_other": ("Conventional road, owner recorded as 'other'", "interurban"),
    "conventional_owner_blank": ("Conventional road, owner not recorded", "interurban"),
}
TRAINING_ONLY_ROADS = ("conventional_owner_other", "conventional_owner_blank")

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
    "overcast": "Daylight, dark sky",
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
    "not_recorded": "No posted limit recorded (the road's generic limit)",
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
#   road          road=<road>                 interurban roads, against the regional network
#   main          all:<input>=<level>, all:<user>
#                                             every other input, the same in every zone
#   deviation     urban:..., interurban:...   how an input's effect on urban streets or interurban
#                                             roads departs from the common effect
# Through-town roads (1,180 crashes, 149 fatal) take the common effects only. The penalty on the
# deviations is stronger than on the main effects (DEVIATION_SCALE), so a zone's effect departs
# from the common one only as far as its own crashes support; the intercepts are barely penalised.

DEVIATION_ZONES = ("urban", "interurban")


def zone_of(road: pd.Series) -> pd.Series:
    return road.map({key: zone for key, (_, zone) in ROADS.items()})


INTERCEPT_SCALE = 10.0
SCALE_GRID: tuple[float, ...] = (0.25, 0.5, 1.0)


def design_columns() -> list[str]:
    columns = [f"zone={zone}" for zone in ZONES]
    columns += [
        f"road={road}"
        for road, (_, zone) in ROADS.items()
        if zone == "interurban" and road != REFERENCE_INTERURBAN_ROAD
    ]
    for prefix in ("all", *DEVIATION_ZONES):
        for name, levels in CATEGORICAL.items():
            columns += [f"{prefix}:{name}={level}" for level in levels if level != REFERENCE[name]]
        columns += [f"{prefix}:{user}" for user in USERS]
    return columns


REFERENCE_INTERURBAN_ROAD = "conventional_regional"


def column_group(column: str) -> str:
    if column.startswith("zone="):
        return "intercept"
    if column.startswith("road="):
        return "road"
    return "main" if column.startswith("all:") else "deviation"


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
    deviation_scale: float

    def logit(self, scenarios: pd.DataFrame) -> np.ndarray:
        return design_matrix(scenarios, self.columns) @ self.coef

    def predict(self, scenarios: pd.DataFrame) -> np.ndarray:
        return expit(self.logit(scenarios))


def expit(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def column_scales(columns: list[str], deviation_scale: float) -> np.ndarray:
    scale = {"intercept": INTERCEPT_SCALE, "road": 1.0, "main": 1.0}
    return np.array([scale.get(column_group(c), deviation_scale) for c in columns], dtype=float)


def fit_logistic(
    x: np.ndarray, y: np.ndarray, c: float, deviation_scale: float, columns: list[str]
) -> Fitted:
    """L2-penalised logistic regression with a penalty that differs by column group.

    Multiplying a column by ``s`` before fitting and the fitted coefficient by ``s`` afterwards
    leaves the model unchanged but divides that coefficient's penalty by ``s**2``: the deviations
    (``s`` < 1) are shrunk harder than the main effects and the intercepts (``s`` = 10) hardly at
    all. The returned coefficients apply to the plain 0/1 design.
    """
    scales = column_scales(columns, deviation_scale)
    model = LogisticRegression(
        C=c, fit_intercept=False, solver="newton-cholesky", max_iter=1_000, tol=1e-10
    )
    model.fit(x * scales, y)
    return Fitted(
        columns=columns, coef=model.coef_[0] * scales, c=c, deviation_scale=deviation_scale
    )


def load() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    frame = pd.read_parquet(FEATURES_PATH)
    return frame, frame.year.astype(int).to_numpy(), frame.fatal.to_numpy().astype(int)


def choose_penalty() -> pd.DataFrame:
    """Validation log loss of each penalty and deviation scale: fit 2010-2020, score 2021-2022."""
    from sklearn.metrics import log_loss, roc_auc_score

    frame, years, y = load()
    columns = design_columns()
    x = design_matrix(scenarios_from_records(frame), columns)
    train = years <= TRAIN_LAST_YEAR
    valid = np.isin(years, VALIDATION_YEARS)
    rows = []
    for c in C_GRID:
        for scale in SCALE_GRID:
            fitted = fit_logistic(x[train], y[train], c, scale, columns)
            p = expit(x[valid] @ fitted.coef)
            rows.append(
                {
                    "c": c,
                    "deviation_scale": scale,
                    "validation_log_loss": log_loss(y[valid], p),
                    "validation_roc_auc": roc_auc_score(y[valid], p),
                }
            )
    out = pd.DataFrame(rows)
    out["chosen"] = out.validation_log_loss == out.validation_log_loss.min()
    return out


def chosen_penalty() -> tuple[float, float]:
    grid = choose_penalty()
    best = grid[grid.chosen].iloc[0]
    return float(best.c), float(best.deviation_scale)


# --------------------------------------------------------------------------- evaluation

ROLLING_TEST_YEARS: tuple[int, ...] = tuple(range(2016, 2024))
TABLE_KEYS = ("road", "crash_type")


def _trees(seed: int = SEED):
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OrdinalEncoder

    categorical = ["road", *CATEGORICAL]
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


def rolling_predictions(c: float | None = None, scale: float | None = None) -> pd.DataFrame:
    """Each year 2016-2023 predicted from the years before it: the calculator's model, gradient-
    boosted trees on the same inputs, and the fatal share of the crash's road and type."""
    if c is None or scale is None:
        c, scale = chosen_penalty()
    frame, years, y = load()
    scenarios = scenarios_from_records(frame)
    columns = design_columns()
    x = design_matrix(scenarios, columns)
    pieces = []
    for year in ROLLING_TEST_YEARS:
        train, test = years < year, years == year
        calculator = fit_logistic(x[train], y[train], c, scale, columns)
        trees = _trees().fit(scenarios[train], y[train])
        pieces.append(
            pd.DataFrame(
                {
                    "cat_crash_id": frame.cat_crash_id[test].to_numpy(),
                    "year": year,
                    "road": scenarios.road[test].to_numpy(),
                    "zone": zone_of(scenarios.road[test]).to_numpy(),
                    "fatal": y[test],
                    "calculator": expit(x[test] @ calculator.coef),
                    "boosted_trees": trees.predict_proba(scenarios[test])[:, 1],
                    "road_x_crash_table": _table(scenarios[train], y[train], scenarios[test]),
                }
            )
        )
    return pd.concat(pieces, ignore_index=True)


# --------------------------------------------------------------------------- final model


def final_fit(c: float, scale: float) -> tuple[Fitted, np.ndarray]:
    """The calculator's model on every crash 2010-2023, and the training design matrix."""
    frame, _, y = load()
    columns = design_columns()
    x = design_matrix(scenarios_from_records(frame), columns)
    return fit_logistic(x, y, c, scale, columns), x


def bootstrap_draws(
    x: np.ndarray, y: np.ndarray, c: float, scale: float, n_boot: int = N_BOOTSTRAP
) -> np.ndarray:
    """Coefficients refitted on crashes resampled with replacement, one row per draw."""
    rng = np.random.default_rng(SEED)
    columns = design_columns()
    draws = np.empty((n_boot, x.shape[1]))
    for b in range(n_boot):
        index = rng.integers(0, len(y), len(y))
        draws[b] = fit_logistic(x[index], y[index], c, scale, columns).coef
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
    """Training crashes per zone and input level ("zone|input=level"), for the page's warnings."""
    zones = zone_of(scenarios.road)
    out: dict[str, int] = {}
    for name in CATEGORICAL:
        counts = pd.crosstab(zones, scenarios[name].astype(str))
        for zone in counts.index:
            for level in counts.columns:
                out[f"{zone}|{name}={level}"] = int(counts.loc[zone, level])
    for user in USERS:
        counts = scenarios[scenarios[user] == 1].groupby(zones).size()
        for zone, n in counts.items():
            out[f"{zone}|{user}"] = int(n)
    return out


def input_specification() -> dict[str, object]:
    """Every input, its type, its levels with labels, its default, and the rules between them."""
    selectable_roads = [r for r in ROADS if r not in TRAINING_ONLY_ROADS]
    inputs: dict[str, object] = {
        "road": {
            "label": "Road",
            "type": "categorical",
            "levels": [
                {"value": r, "label": ROADS[r][0], "zone": ROADS[r][1]} for r in selectable_roads
            ],
            "default": REFERENCE["road"],
        }
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
            "text": "A collision between road users with only one vehicle or pedestrian is "
            "rare in the records (36 of 24,478 crashes).",
        },
        {
            "id": "pedestrian_without_vehicle",
            "kind": "warning",
            "text": "A crash involving a pedestrian and no vehicle is rare in the records "
            "(46 of 24,478 crashes).",
        },
        {
            "id": "few_similar",
            "kind": "warning",
            "threshold": SUPPORT_FEW,
            "text": "Fewer than {threshold} recorded crashes share this zone, crash type, road "
            "users and number involved: the estimate rests on the model's assumptions more "
            "than on similar crashes.",
        },
        {
            "id": "rare_level",
            "kind": "warning",
            "threshold": SUPPORT_FEW,
            "text": "Fewer than {threshold} recorded crashes in this zone have this value of "
            "{input}: the estimate for it is extrapolated.",
        },
        {
            "id": "through_town",
            "kind": "warning",
            "text": "On roads through towns the model barely separates fatal from serious "
            "crashes (ROC-AUC about 0.6 on later years); treat its estimate as the average for "
            "such roads.",
        },
    ]
    return {"inputs": inputs, "rules": rules, "collision_types": list(COLLISION_TYPES)}


COLLISION_TYPES = ("head_on", "side_impact", "rear_end", "sideswipe", "pedestrian_struck")


def check_scenario(scenario: dict[str, object]) -> list[str]:
    """The ids of the rules a scenario breaks (errors and the scenario-level warnings)."""
    users = [u for u in USERS if scenario.get(u)]
    units = {"1": 1, "2": 2, "3": 3, "4+": 4}[str(scenario["units"])]
    broken = []
    if not users:
        broken.append("at_least_one_user")
    if units < len(users):
        broken.append("units_cover_users")
    if scenario["crash_type"] == "pedestrian_struck" and not scenario.get("pedestrian"):
        broken.append("pedestrian_struck_needs_pedestrian")
    if scenario["crash_type"] in COLLISION_TYPES and units == 1:
        broken.append("collision_with_one_unit")
    if users == ["pedestrian"]:
        broken.append("pedestrian_without_vehicle")
    if ROADS[str(scenario["road"])][1] == "through_town":
        broken.append("through_town")
    return broken


def export(
    fitted: Fitted,
    covariance: np.ndarray,
    scenarios: pd.DataFrame,
    y: np.ndarray,
    evaluation: dict[str, object],
) -> dict[str, object]:
    """Everything the page needs to reproduce :func:`prediction_interval` for any scenario."""
    k = len(fitted.columns)
    lower = [
        round(float(covariance[i, j]), EXPORT_DECIMALS + 2) for i in range(k) for j in range(i + 1)
    ]
    return {
        "model": "catalonia_crash_severity_calculator",
        "question": "Of crashes in Catalonia with a death or a serious injury, the share that "
        "were fatal, given the recorded road, conditions and crash",
        "source": "Servei Català de Trànsit, crashes with a death or serious injury, 2010-2023",
        "training": {
            "years": [2010, 2023],
            "crashes": int(len(y)),
            "fatal": int(y.sum()),
        },
        "estimator": "logistic regression, L2 penalty, effects common to all zones plus "
        "deviations for urban streets and interurban roads",
        "penalty": {"C": fitted.c, "deviation_scale": fitted.deviation_scale},
        "columns": fitted.columns,
        "coefficients": [round(float(b), EXPORT_DECIMALS) for b in fitted.coef],
        "covariance_lower": lower,
        "interval": "95% interval: logit +- 1.96 * sqrt(x' V x), V the covariance of the "
        f"coefficients over {N_BOOTSTRAP} bootstrap refits",
        **input_specification(),
        "support": support_table(scenarios, y),
        "level_support": level_support(scenarios),
        "evaluation": evaluation,
    }


def scenario_frame(scenario: dict[str, object]) -> pd.DataFrame:
    row = {name: scenario[name] for name in ("road", *CATEGORICAL)}
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
    """``base`` with one input changed at a time (only changes that keep the scenario valid)."""
    out = []
    zone = ROADS[str(base["road"])][1]
    for road, (_, road_zone) in ROADS.items():
        if road in TRAINING_ONLY_ROADS or road == base["road"]:
            continue
        if zone == "urban" and road_zone == "interurban":
            continue
        out.append(("road", road, base | {"road": road}))
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
    return [(n, level, s) for n, level, s in out if not set(check_scenario(s)) & ERRORS]


ERRORS = {"at_least_one_user", "units_cover_users", "pedestrian_struck_needs_pedestrian"}


def scenario_contrasts(fitted: Fitted, draws: np.ndarray, base: dict[str, object]) -> pd.DataFrame:
    """Predicted fatal share of ``base`` and of each one-input change, with bootstrap intervals,
    and the ratio of the two. Associations between modelled scenarios, not effects."""
    variants = _variants(base)
    frames = [scenario_frame(base)] + [scenario_frame(s) for _, _, s in variants]
    x = design_matrix(pd.concat(frames, ignore_index=True), fitted.columns)
    point = expit(x @ fitted.coef)
    boot = expit(x @ draws.T)  # scenarios x draws
    rows = []
    for i, (name, level, _) in enumerate(variants, start=1):
        ratio = boot[i] / boot[0]
        rows.append(
            {
                "input": name,
                "level": level,
                "probability": point[i],
                "probability_low": np.percentile(boot[i], 2.5),
                "probability_high": np.percentile(boot[i], 97.5),
                "base_probability": point[0],
                "ratio": point[i] / point[0],
                "ratio_low": np.percentile(ratio, 2.5),
                "ratio_high": np.percentile(ratio, 97.5),
            }
        )
    return pd.DataFrame(rows)


def marginal_and_adjusted(fitted: Fitted, draws: np.ndarray) -> pd.DataFrame:
    """For each input level: the raw fatal share of the crashes with it, and the model's average
    predicted share when every crash is given that level (standardised to the observed mix)."""
    frame, _, y = load()
    scenarios = scenarios_from_records(frame)
    rows = []
    for name in ("road", *CATEGORICAL):
        levels = (
            [r for r in ROADS if r not in TRAINING_ONLY_ROADS]
            if name == "road"
            else list(CATEGORICAL[name])
        )
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
            boot = expit(x @ draws[:50].T).mean(axis=0)
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


def stability(c: float, scale: float) -> pd.DataFrame:
    """Key contrasts from models fitted separately on two periods and on two areas."""
    frame, years, y = load()
    scenarios = scenarios_from_records(frame)
    columns = design_columns()
    x = design_matrix(scenarios, columns)
    splits = {
        "2010-2016": years <= 2016,
        "2017-2023": years >= 2017,
        "Barcelona province": (frame.demarcation == "Barcelona").to_numpy(),
        "Girona, Lleida, Tarragona": (frame.demarcation != "Barcelona").to_numpy(),
    }
    rows = []
    for label, mask in splits.items():
        fitted = fit_logistic(x[mask], y[mask], c, scale, columns)
        draws = bootstrap_draws(x[mask], y[mask], c, scale, n_boot=60)
        for base_name, base in (("interurban", REFERENCE_SCENARIO), ("urban", URBAN_REFERENCE)):
            table = scenario_contrasts(fitted, draws, base)
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
    """The page's two-scenario comparison: the first scenario's predicted fatal share against
    the second's, as a ratio and as a difference in percentage points, each with a 95% interval
    from the delta method on the same coefficient covariance. An association between two
    modelled scenarios, not the effect of changing one circumstance."""
    columns = list(model["columns"])
    coef = np.array(model["coefficients"], dtype=float)
    covariance = _covariance(model)
    xa = design_matrix(scenario_frame(first), columns)[0]
    xb = design_matrix(scenario_frame(second), columns)[0]
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
