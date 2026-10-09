"""The crash explorer's table: DGT's injury crashes counted by year, region, road type and crash type.

One row per cell of year x autonomous community x road type x crash type that holds at least one
recorded injury crash (``reports/tables/explore_dgt_crashes.csv``, written by ``scripts/model.py``
beside the association analysis, from the same processed records). Each row counts the injury
crashes, the crashes with at least one death within 30 days and those deaths, in total and by
road-user type. No cell is filled with zeros and nothing is interpolated: a combination with no
recorded crash has no row.

The groupings:

* region: the province's autonomous community (:mod:`dgt_stats.regions`);
* road type: ``derive.road_group``, the grouping the data page's coding breaks describe;
* crash type: DGT's ``TIPO_ACCIDENTE`` as labelled, except that its nine run-off-road codes
  (11-19, by side and outcome) form one type, so the list stays readable;
* road user: DGT's twelve per-crash death counts in eight groups. Personal mobility vehicles
  (e-scooters) have their own count only from 2020; before, such deaths are under other
  vehicles or not specified, so they are kept in that group throughout.

A record without a road type or a crash type counts under "Not recorded", so the yearly totals
equal the published ones.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import labels, regions
from dgt_stats.paths import DGT_PROCESSED_CRASHES

NAME = "explore_dgt_crashes"
NOT_RECORDED = "Not recorded"
DIMENSIONS = ("year", "community", "road_type", "crash_type")

# ``derive.road_group`` keys, in the order the explorer lists them, with the site's labels.
ROAD_TYPES: dict[str, str] = {
    "urban_street": "Urban streets",
    "conventional": "Conventional roads",
    "dual_carriageway": "Dual carriageways",
    "motorway": "Motorways",
    "other": "Other roads",
}
# DGT's run-off-road codes, grouped into one crash type.
RUN_OFF_CODES = tuple(range(11, 20))
RUN_OFF = "Run-off road"


def _crash_types() -> dict[int, str]:
    english = labels.ENGLISH["TIPO_ACCIDENTE"]
    return {
        int(code): RUN_OFF if int(code) in RUN_OFF_CODES else label
        for code, label in english.items()
    }


CRASH_TYPE_BY_CODE: dict[int, str] = _crash_types()
CRASH_TYPES: tuple[str, ...] = tuple(dict.fromkeys(CRASH_TYPE_BY_CODE.values()))

# Deaths within 30 days by road-user type: the table's column, its label, DGT's columns.
ROAD_USERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "deaths_pedestrians": ("Pedestrians", ("TOT_PEAT_MU30DF",)),
    "deaths_cyclists": ("Cyclists", ("TOT_BICI_MU30DF",)),
    "deaths_moped_riders": ("Moped riders", ("TOT_CICLO_MU30DF",)),
    "deaths_motorcyclists": ("Motorcyclists", ("TOT_MOTO_MU30DF",)),
    "deaths_car_occupants": ("Car occupants", ("TOT_TUR_MU30DF",)),
    "deaths_van_light_truck": (
        "Van and light-truck occupants",
        ("TOT_FURG_MU30DF", "TOT_CAM_MENOS3500_MU30DF"),
    ),
    "deaths_heavy_vehicle": (
        "Heavy lorry and bus occupants",
        ("TOT_CAM_MAS3500_MU30DF", "TOT_BUS_MU30DF"),
    ),
    "deaths_other": (
        "Others and not specified",
        ("TOT_VMP_MU30DF", "TOT_OTRO_MU30DF", "TOT_SINESPECIF_MU30DF"),
    ),
}
COUNTS = ("injury_crashes", "fatal_crashes", "deaths_30d", *ROAD_USERS)
COLUMNS = (
    "ANYO",
    "COD_PROVINCIA",
    "road_group",
    "TIPO_ACCIDENTE",
    "fatal",
    "n_deaths",
    *labels.ROAD_USER_TYPES,
)


def _mapped(values: pd.Series, mapping: dict, name: str) -> pd.Series:
    """Each code's group; a missing code is "Not recorded", a code with no group raises."""
    out = values.map(mapping)
    stray = values.notna() & out.isna()
    if stray.any():
        raise ValueError(f"{name} codes with no group: {sorted(set(values[stray]))}")
    return out.fillna(NOT_RECORDED).astype(str)


def crash_cells(crashes: pd.DataFrame | None = None) -> pd.DataFrame:
    """The explorer's table from the processed DGT crash records."""
    if crashes is None:
        crashes = pd.read_parquet(DGT_PROCESSED_CRASHES, columns=list(COLUMNS))
    grouped = [column for _, (_, columns) in ROAD_USERS.items() for column in columns]
    if sorted(grouped) != sorted(labels.ROAD_USER_TYPES):
        raise ValueError("the road-user groups must hold each of DGT's death counts once")
    frame = pd.DataFrame(
        {
            "year": pd.to_numeric(crashes["ANYO"]).astype(int),
            "community": regions.community(crashes["COD_PROVINCIA"]).astype(str),
            "road_type": _mapped(crashes["road_group"].astype(object), ROAD_TYPES, "road_group"),
            "crash_type": _mapped(
                pd.to_numeric(crashes["TIPO_ACCIDENTE"]).astype("Int64").astype(object),
                CRASH_TYPE_BY_CODE,
                "TIPO_ACCIDENTE",
            ),
            "injury_crashes": 1,
            "fatal_crashes": crashes["fatal"].astype(int),
            "deaths_30d": crashes["n_deaths"].astype(int),
        },
        index=crashes.index,
    )
    for column, (_, columns) in ROAD_USERS.items():
        frame[column] = sum(crashes[c].fillna(0).astype(int) for c in columns)
    by_user = frame[list(ROAD_USERS)].sum(axis=1)
    if not by_user.eq(frame.deaths_30d).all():
        raise ValueError("the road-user deaths of some crashes do not add up to their deaths")
    order = {
        "community": list(regions.COMMUNITIES),
        "road_type": [*ROAD_TYPES.values(), NOT_RECORDED],
        "crash_type": [*CRASH_TYPES, NOT_RECORDED],
    }
    for column, levels in order.items():
        frame[column] = pd.Categorical(frame[column], categories=levels, ordered=True)
    out = (
        frame.groupby(list(DIMENSIONS), observed=True, sort=True)[list(COUNTS)].sum().reset_index()
    )
    for column in order:
        out[column] = out[column].astype(str)
    return out[[*DIMENSIONS, *COUNTS]].astype({column: "int64" for column in COUNTS})
