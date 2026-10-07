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


def test_road_class_follows_zone_then_road_type() -> None:
    zone = pd.Series(["urban", "interurban", "interurban", "interurban", "interurban", "urban"])
    code = pd.Series([3, 1, 3, 5, 8, 6])
    assert road_class.road_class(zone, code).tolist() == [
        "urban",
        "autopista",
        "autovia",
        "conventional",
        "other_interurban",
        "urban",
    ]
    kind = road_class.kind_of_road(code)
    assert kind.iloc[:4].tolist() == ["autovia", "autopista", "autovia", "conventional"]
    assert kind.iloc[4] is pd.NA
    # The kilometres cover the State, regional and provincial networks only.
    assert road_class.KM_COVERAGE_OWNERS == (1, 2, 3)
    assert set(road_class.OWNERS) >= {1, 2, 3, 4, 5}


@processed
def test_the_baseline_reconciles_with_the_yearbook() -> None:
    from dgt_stats import io_tables

    base = road_class.baseline()
    annual = io_tables.read_table("series_annual")
    annual = annual[(annual.zone == "all") & annual.year.isin(road_class.BASELINE_YEARS)]
    yearbook = annual.pivot_table(index="year", columns="metric", values="value").mean()
    assert base.deaths.sum() == pytest.approx(yearbook["deaths_30d"])
    assert base.seriously_injured.sum() == pytest.approx(yearbook["hospitalised_30d"])
    assert base.injury_crashes.sum() == pytest.approx(yearbook["crashes"])
    assert list(base.road_class) == list(road_class.ROAD_CLASSES)
    # The outside-coverage deaths are part of each interurban class, and urban streets have none.
    base = base.set_index("road_class")
    interurban = base.loc[list(road_class.INTERURBAN_CLASSES)]
    assert (interurban.deaths_outside_km_coverage <= interurban.deaths).all()
    assert pd.isna(base.loc["urban", "deaths_outside_km_coverage"])
    assert (interurban.injury_crashes_outside_km_coverage <= interurban.injury_crashes).all()
    assert "environment" not in base.columns and "vehicle_km" not in base.columns


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
        assert row.deaths + row.deaths_outside_km_coverage == pytest.approx(row.deaths_all_owners)
    # About one interurban death in twenty is on roads the kilometres leave out, in both classes
    # (the module's docstring says never more than one in ten), but about one injury crash in
    # five: those roads carry many crashes that rarely kill.
    assert risk.outside_coverage_death_share.between(0.02, 0.10).all()
    assert risk.outside_coverage_crash_share.between(0.10, 0.30).all()
    assert (risk.outside_coverage_crash_share > risk.outside_coverage_death_share).all()
    assert risk.injury_crashes_all_owners_per_bn_km.gt(risk.injury_crashes_per_bn_km).all()
    # The restriction moves the conventional-to-motorway ratio by little.
    wide = risk.pivot(index="year", columns="road_class")
    restricted = wide.deaths_per_bn_km.conventional / wide.deaths_per_bn_km.motorway
    every_owner = (
        wide.deaths_all_owners_per_bn_km.conventional / wide.deaths_all_owners_per_bn_km.motorway
    )
    assert ((restricted / every_owner - 1).abs() < 0.06).all()
    # Deaths recorded in the urban zone on covered roads are counted, and are mostly conventional.
    urban = wide.urban_zone_deaths_on_covered_roads
    assert (urban.conventional > urban.motorway).all()
    assert (urban.conventional < 0.06 * wide.deaths.conventional).all()


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
