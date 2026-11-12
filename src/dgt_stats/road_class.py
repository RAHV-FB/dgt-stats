"""Deaths per measured vehicle-kilometre on interurban roads, motorways against conventional roads.

:func:`class_risk` divides deaths and injury crashes on autopistas and autovías (pooled) and on
conventional roads by the vehicle-kilometres the Ministry of Transport measures on the same kinds of
road (yearbook table 1.2.14), year by year. Both numerator and denominator come from DGT's crash
microdata and the Ministry's yearbook.

**Kinds of road.** Interurban crashes are classed by road-type code (``TIPO_VIA``): autopistas are
toll and free motorways (1 and 2), autovías are code 3 and conventional roads are codes 4 to 6 (roads
for motor vehicles and conventional roads of one or two carriageways). Each class groups the codes
DGT swapped in its recodings (toll and free motorways in 2022 and 2024; codes 5 and 6 in 2021), so
the classes are stable across them. Autopistas and autovías are pooled because the table puts free
motorways with autovías and the crash data put them with toll motorways.

**Which roads the kilometres cover.** Footnote (1) of table 1.2.14 says the kilometres are those of
the networks of the State, the autonomous communities and the provincial councils, and leave out
roads run by municipalities and other bodies. The crash records carry the owner of the road
(``TITULARIDAD_VIA``: 1 State, 2 autonomous community, 3 provincial council, cabildo or consell,
4 municipal, 5 other, 999 not specified), so the numerator is restricted to the owners the
kilometres cover (:data:`KM_COVERAGE_OWNERS`). That removes about one death in twenty in each class
but about one injury crash in five, so it matters little for deaths per kilometre and more for
injury crashes per kilometre. One mismatch is left: crashes on these kinds of road recorded in the
urban zone (urban crossings) are in neither numerator, while whether their kilometres are in the
table is not stated; they are a few dozen deaths a year, almost all on conventional roads.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgt_stats import io_traffic
from dgt_stats.paths import DGT_PROCESSED_CRASHES

PROCESSED_CRASHES = DGT_PROCESSED_CRASHES

AUTOPISTA_CODES = (1, 2)
AUTOVIA_CODES = (3,)
CONVENTIONAL_CODES = (4, 5, 6)

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

CRASH_COLUMNS = ["ANYO", "zone", "TIPO_VIA", "TITULARIDAD_VIA", "TOTAL_MU30DF"]


def kind_of_road(road_type: pd.Series) -> pd.Series:
    """The kind of road by road-type code alone, whatever the zone (NA outside the three kinds)."""
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
    """One row per injury crash: year, zone, kind of road, owner coverage and deaths."""
    frame = pd.read_parquet(PROCESSED_CRASHES, columns=CRASH_COLUMNS)
    owner = pd.to_numeric(frame.TITULARIDAD_VIA, errors="coerce")
    return frame.assign(
        kind_of_road=kind_of_road(frame.TIPO_VIA),
        in_km_coverage=owner.isin(KM_COVERAGE_OWNERS).to_numpy(),
    )


def class_risk() -> pd.DataFrame:
    """Deaths and injury crashes per billion vehicle-km, motorways against conventional roads.

    One row per year and class. The kilometres are table 1.2.14's: toll motorways plus autovías
    and free motorways against multi-lane plus conventional roads. The numerator (``deaths``,
    ``injury_crashes``) is the interurban crashes of the class on roads of the owners those
    kilometres cover (:data:`KM_COVERAGE_OWNERS`).
    """
    traffic = io_traffic.read_road_traffic().set_index("year")
    frame = crashes()
    frame = frame[frame.ANYO.isin(traffic.index) & frame.kind_of_road.notna()].copy()
    frame["risk_class"] = frame.kind_of_road.map(RISK_CLASS_OF)
    covered = frame[(frame.zone == "interurban") & frame.in_km_coverage]
    counts = covered.groupby(["ANYO", "risk_class"]).agg(
        deaths=("TOTAL_MU30DF", "sum"), injury_crashes=("TOTAL_MU30DF", "size")
    )
    records = []
    for (year, key), row in counts.iterrows():
        billion_km = sum(float(traffic.loc[year, t]) for t in RISK_KM_TYPES[key]) / 1e3
        deaths = float(row.deaths)
        records.append(
            {
                "year": int(year),
                "road_class": key,
                "road_class_label": RISK_CLASSES[key],
                "billion_vehicle_km": billion_km,
                "deaths": deaths,
                "injury_crashes": float(row.injury_crashes),
                "deaths_per_bn_km": deaths / billion_km,
                "injury_crashes_per_bn_km": float(row.injury_crashes) / billion_km,
            }
        )
    return pd.DataFrame.from_records(records).sort_values(["year", "road_class"])
