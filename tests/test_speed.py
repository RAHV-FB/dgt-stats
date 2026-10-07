import numpy as np
import pytest

from dgt_stats import io_tables, speed

pytestmark = pytest.mark.skipif(
    not io_tables.staging_path("tables_driver_infractions").exists(),
    reason="run `python scripts/ingest.py tables` first",
)


def test_infraction_shares_add_up_and_show_the_unknown_jump() -> None:
    shares = speed.infraction_shares()
    assert sorted(shares.year.unique()) == list(range(2014, 2025))
    assert set(shares.zone) == {"all", "interurban", "urban"}
    parts = shares[["share_speed_infraction", "share_too_slow", "share_none", "share_unknown"]]
    assert np.allclose(parts.sum(axis=1), 1, atol=1e-12)
    assert (shares.known == shares.speed_infraction + shares.too_slow + shares.none).all()
    assert (shares.share_among_known_low < shares.share_among_known).all()
    assert (shares.share_among_known < shares.share_among_known_high).all()
    both = shares[shares.zone == "all"].set_index("year")
    assert both.loc[2024, "total"] == 61_318 + 108_869
    # The share among known drivers, anchored to the published counts rather than to its own column.
    known_2024 = 61_318 + 108_869 - (30_115 + 58_537)
    assert both.loc[2024, "known"] == known_2024
    assert both.loc[2024, "share_among_known"] == pytest.approx(
        (4_473 + 2_920) / known_2024, abs=1e-12
    )
    assert both.loc[2014, "share_unknown"] < 0.2 and both.loc[2016, "share_unknown"] > 0.5
    zones = shares[shares.zone != "all"].groupby("year")[["total", "speed_infraction"]].sum()
    assert (zones.total == both.total.loc[zones.index]).all()
    assert (zones.speed_infraction == both.speed_infraction.loc[zones.index]).all()
