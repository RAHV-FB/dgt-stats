import pandas as pd
import pytest

from dgt_stats import road_class
from dgt_stats.paths import DGT_PROCESSED_CRASHES, ROAD_TRAFFIC_PATH

processed = pytest.mark.skipif(
    not DGT_PROCESSED_CRASHES.exists(),
    reason="run `python scripts/build_tables.py` first",
)
traffic = pytest.mark.skipif(
    not (DGT_PROCESSED_CRASHES.exists() and ROAD_TRAFFIC_PATH.exists()),
    reason="the crash microdata and the Ministry's yearbook are needed",
)


def test_kind_of_road_follows_the_road_type_code() -> None:
    code = pd.Series([3, 1, 3, 5, 8, 2])
    kind = road_class.kind_of_road(code)
    assert kind.iloc[:4].tolist() == ["autovia", "autopista", "autovia", "conventional"]
    assert kind.iloc[4] is pd.NA
    assert kind.iloc[5] == "autopista"
    # The kilometres cover the State, regional and provincial networks only.
    assert road_class.KM_COVERAGE_OWNERS == (1, 2, 3)


@traffic
def test_risk_numerator_covers_the_owners_the_kilometres_cover() -> None:
    from dgt_stats import io_traffic

    risk = road_class.class_risk()
    km = io_traffic.read_road_traffic().set_index("year")
    assert set(risk.year) == set(km.index) & set(range(2016, 2025))
    for row in risk.itertuples():
        types = road_class.RISK_KM_TYPES[row.road_class]
        assert row.billion_vehicle_km == pytest.approx(
            sum(km.loc[row.year, t] for t in types) / 1e3
        )
        assert row.deaths_per_bn_km == pytest.approx(row.deaths / row.billion_vehicle_km)
    assert set(risk.columns) == {
        "year",
        "road_class",
        "road_class_label",
        "billion_vehicle_km",
        "deaths",
        "injury_crashes",
        "deaths_per_bn_km",
        "injury_crashes_per_bn_km",
    }


@traffic
def test_conventional_roads_carry_the_most_risk_per_kilometre() -> None:
    risk = road_class.class_risk().pivot(
        index="year", columns="road_class", values="deaths_per_bn_km"
    )
    assert ((risk.conventional / risk.motorway) > 2.5).all()


@processed
def test_owner_codes_inside_the_coverage_are_stable_across_the_recodings() -> None:
    # Codes 4 (municipal) and 5 (other) swap in 2021, 2023 and 2024; the covered codes do not.
    frame = road_class.crashes()
    interurban = frame[frame.zone == "interurban"]
    covered = interurban[interurban.in_km_coverage].groupby("ANYO").size()
    normal = covered.drop(index=[2020, 2021])
    assert normal.max() / normal.min() < 1.15
