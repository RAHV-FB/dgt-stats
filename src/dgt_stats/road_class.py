"""Casualties by road class, and deaths per measured vehicle-kilometre on interurban roads.

Two tables, both built only from DGT's crash microdata and the Ministerio de Transportes' yearbook:

* :func:`baseline` is the mean number of injury crashes, deaths within 30 days, people admitted
  to hospital and other injured a year by road class over :data:`BASELINE_YEARS`. Summed over the
  classes it reconciles exactly with DGT's yearbook totals for the same years.
* :func:`class_risk` divides deaths, admissions and injury crashes on autopistas and autovías
  (pooled) and on conventional roads by the vehicle-kilometres the Ministry measures on the same
  kinds of road (yearbook table 1.2.14), year by year.

**Road classes.** Urban crashes are classed by DGT's grouped zone (``ZONA_AGRUPADA`` 2); interurban
crashes by road-type code (``TIPO_VIA``): autopistas are toll and free motorways (1 and 2), autovías
are code 3, conventional roads are codes 4 to 6 (roads for motor vehicles and conventional roads of
one or two carriageways) and every other code is "other interurban". Each class groups the codes
DGT swapped in its recodings (toll and free motorways in 2022 and 2024; codes 5 and 6 in 2021), so
the classes are stable across them. ``policy.py`` leaves code 4 (a handful of deaths a year) out
of its conventional group; here it is kept with conventional roads.

**Which roads the kilometres cover.** Footnote (1) of table 1.2.14 says the kilometres are those of
the networks of the State, the autonomous communities and the provincial councils, and leave out
roads run by municipalities and other bodies. The crash records carry the owner of the road
(``TITULARIDAD_VIA``: 1 State, 2 autonomous community, 3 provincial council, cabildo or consell,
4 municipal, 5 other, 999 not specified), so the numerator of every rate is restricted to the
owners the kilometres cover (:data:`KM_COVERAGE_OWNERS`). What the restriction removes is
published beside the rate, year by year and class by class, with the rate every owner would give
(``*_all_owners_per_bn_km``). It removes about one death in twenty in each class
(``deaths_outside_km_coverage``; never more than one in ten, which a test holds) but about one
injury crash in five (``outside_coverage_crash_share``): roads of municipal and other owners
carry many crashes that rarely kill, so the restriction matters little for deaths per kilometre
and much more for injury crashes per kilometre, and it is made because the numerator has to cover
the roads the kilometres cover. Codes 4 and 5 swap in 2021, 2023 and 2024 (the "other" code takes
most of the municipal rows); both are outside the coverage, so the swap does not move the
restricted numerator, and codes 1 to 3 are stable across those years.

One mismatch is left and counted rather than corrected: crashes on these kinds of road owned by
the State, a region or a province but recorded in the urban zone (urban crossings, *travesías*, and
urban autovías) are urban crashes, so they are in neither numerator, while whether their
kilometres are in table 1.2.14 is not stated. ``urban_zone_deaths_on_covered_roads`` gives how many
deaths that is each year (a few dozen, almost all on conventional roads), so a reader can see the
most it could change the conventional rate.

Autopistas and autovías are pooled in :func:`class_risk` because the table puts free motorways
with autovías and the crash data put them with toll motorways, and the crash data swap toll and
free motorways in 2022 and 2024.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgt_stats import io_traffic
from dgt_stats.paths import DGT_PROCESSED_CRASHES

PROCESSED_CRASHES = DGT_PROCESSED_CRASHES
BASELINE_YEARS = (2022, 2023, 2024)

ROAD_CLASSES = {
    "autopista": "Autopistas",
    "autovia": "Autovías",
    "conventional": "Conventional roads",
    "other_interurban": "Other interurban roads",
    "urban": "Urban streets",
}
INTERURBAN_CLASSES = ("autopista", "autovia", "conventional", "other_interurban")
AUTOPISTA_CODES = (1, 2)
AUTOVIA_CODES = (3,)
CONVENTIONAL_CODES = (4, 5, 6)

# DGT's road owner codes (``TITULARIDAD_VIA``), as the microdata dictionary labels them.
OWNERS = {
    1: "State",
    2: "Autonomous community",
    3: "Provincial council, cabildo or consell",
    4: "Municipal",
    5: "Other",
    999: "Not specified",
}
# The owners whose interurban networks table 1.2.14 measures.
KM_COVERAGE_OWNERS = (1, 2, 3)

# The two classes with measured kilometres, and the kinds of road in table 1.2.14 that make each.
RISK_CLASSES = {
    "motorway": "Autopistas and autovías",
    "conventional": "Conventional roads",
}
RISK_KM_TYPES = {
    "motorway": ("toll_motorway", "autovia_free_motorway"),
    "conventional": ("multilane", "conventional"),
}
RISK_CLASS_OF = {"autopista": "motorway", "autovia": "motorway", "conventional": "conventional"}

CRASH_COLUMNS = [
    "ANYO",
    "zone",
    "TIPO_VIA",
    "TITULARIDAD_VIA",
    "TOTAL_MU30DF",
    "TOTAL_HG30DF",
    "TOTAL_HL30DF",
]


def road_class(zone: pd.Series, road_type: pd.Series) -> pd.Series:
    """The road class of each crash: urban by zone, interurban by road-type code."""
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


def kind_of_road(road_type: pd.Series) -> pd.Series:
    """The kind of road by road-type code alone, whatever the zone (NA outside the four classes)."""
    out = np.select(
        [
            road_type.isin(AUTOPISTA_CODES),
            road_type.isin(AUTOVIA_CODES),
            road_type.isin(CONVENTIONAL_CODES),
        ],
        ["autopista", "autovia", "conventional"],
        "",
    )
    return pd.Series(out, index=road_type.index, dtype="string").replace("", pd.NA)


def crashes() -> pd.DataFrame:
    """One row per injury crash: year, zone, road class, owner coverage and casualties."""
    frame = pd.read_parquet(PROCESSED_CRASHES, columns=CRASH_COLUMNS)
    owner = pd.to_numeric(frame.TITULARIDAD_VIA, errors="coerce")
    return frame.assign(
        road_class=road_class(frame.zone, frame.TIPO_VIA),
        kind_of_road=kind_of_road(frame.TIPO_VIA),
        in_km_coverage=owner.isin(KM_COVERAGE_OWNERS).to_numpy(),
    )


def baseline(years: tuple[int, ...] = BASELINE_YEARS) -> pd.DataFrame:
    """Mean annual crashes and casualties by road class over ``years``, from the microdata.

    ``deaths_outside_km_coverage`` and ``injury_crashes_outside_km_coverage`` are the mean annual
    deaths and injury crashes of an interurban class on roads of owners table 1.2.14 does not
    measure (municipal, other or not specified), and the two ``outside_coverage_*_share`` columns
    their shares of the class; all are empty for urban streets, which have no measured
    kilometres.
    """
    frame = crashes()
    frame = frame[frame.ANYO.isin(years)]
    grouped = frame.groupby("road_class")
    out = grouped.agg(
        injury_crashes=("TOTAL_MU30DF", "size"),
        deaths=("TOTAL_MU30DF", "sum"),
        seriously_injured=("TOTAL_HG30DF", "sum"),
        slightly_injured=("TOTAL_HL30DF", "sum"),
    ).astype(float) / len(years)
    outside = frame[~frame.in_km_coverage].groupby("road_class").TOTAL_MU30DF.sum().astype(
        float
    ) / len(years)
    out = out.reindex(list(ROAD_CLASSES))
    outside_crashes = frame[~frame.in_km_coverage].groupby("road_class").size().astype(float) / len(
        years
    )
    out["deaths_outside_km_coverage"] = outside.reindex(out.index).fillna(0.0)
    out["injury_crashes_outside_km_coverage"] = outside_crashes.reindex(out.index).fillna(0.0)
    out.loc["urban", ["deaths_outside_km_coverage", "injury_crashes_outside_km_coverage"]] = np.nan
    out["outside_coverage_death_share"] = out.deaths_outside_km_coverage / out.deaths
    out["outside_coverage_crash_share"] = (
        out.injury_crashes_outside_km_coverage / out.injury_crashes
    )
    out.insert(0, "road_class_label", [ROAD_CLASSES[key] for key in out.index])
    out["first_year"], out["last_year"] = min(years), max(years)
    out.index.name = "road_class"
    return out.reset_index()


def class_risk() -> pd.DataFrame:
    """Deaths, admissions and injury crashes per billion vehicle-km, motorways against conventional.

    One row per year and class. The kilometres are table 1.2.14's: toll motorways plus autovías
    and free motorways against multi-lane plus conventional roads. The numerator of the rates
    (``deaths``, ``seriously_injured``, ``injury_crashes``) is the interurban crashes of the class
    on roads of the owners those kilometres cover (:data:`KM_COVERAGE_OWNERS`). Beside it:

    * ``deaths_all_owners``, ``injury_crashes_all_owners`` and their ``*_per_bn_km`` rates: every
      interurban crash of the class whatever the owner, the numerator the rate would have without
      the restriction;
    * ``deaths_outside_km_coverage``, ``outside_coverage_death_share`` and
      ``outside_coverage_crash_share``: what the restriction removed (municipal, other and
      unspecified owners);
    * ``urban_zone_deaths_on_covered_roads``: deaths on the same kinds of road of covered owners
      recorded in the urban zone, which are in no numerator here although their kilometres may be
      in the denominator.
    """
    traffic = io_traffic.read_road_traffic().set_index("year")
    frame = crashes()
    frame = frame[frame.ANYO.isin(traffic.index) & frame.kind_of_road.notna()].copy()
    frame["risk_class"] = frame.kind_of_road.map(RISK_CLASS_OF)
    interurban = frame[frame.zone == "interurban"]
    covered = interurban[interurban.in_km_coverage]
    urban_covered = frame[(frame.zone == "urban") & frame.in_km_coverage]
    keys = ["ANYO", "risk_class"]
    counts = covered.groupby(keys).agg(
        deaths=("TOTAL_MU30DF", "sum"),
        seriously_injured=("TOTAL_HG30DF", "sum"),
        injury_crashes=("TOTAL_MU30DF", "size"),
    )
    every_owner = interurban.groupby(keys).TOTAL_MU30DF.agg(["sum", "size"])
    urban_zone = urban_covered.groupby(keys).TOTAL_MU30DF.sum()
    records = []
    for (year, key), row in counts.iterrows():
        billion_km = sum(float(traffic.loc[year, t]) for t in RISK_KM_TYPES[key]) / 1e3
        deaths = float(row.deaths)
        all_owners = float(every_owner.loc[(year, key), "sum"])
        all_crashes = float(every_owner.loc[(year, key), "size"])
        records.append(
            {
                "year": int(year),
                "road_class": key,
                "road_class_label": RISK_CLASSES[key],
                "billion_vehicle_km": billion_km,
                "deaths": deaths,
                "seriously_injured": float(row.seriously_injured),
                "injury_crashes": float(row.injury_crashes),
                "deaths_per_bn_km": deaths / billion_km,
                "seriously_injured_per_bn_km": float(row.seriously_injured) / billion_km,
                "injury_crashes_per_bn_km": float(row.injury_crashes) / billion_km,
                "deaths_all_owners": all_owners,
                "deaths_all_owners_per_bn_km": all_owners / billion_km,
                "deaths_outside_km_coverage": all_owners - deaths,
                "outside_coverage_death_share": (all_owners - deaths) / all_owners,
                "injury_crashes_all_owners": all_crashes,
                "injury_crashes_all_owners_per_bn_km": all_crashes / billion_km,
                "outside_coverage_crash_share": (all_crashes - float(row.injury_crashes))
                / all_crashes,
                "urban_zone_deaths_on_covered_roads": float(urban_zone.get((year, key), 0)),
            }
        )
    return pd.DataFrame.from_records(records).sort_values(["year", "road_class"])
