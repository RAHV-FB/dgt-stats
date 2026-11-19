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
    assert not any("known" in c.replace("unknown", "") for c in shares.columns)
    both = shares[shares.zone == "all"].set_index("year")
    assert both.loc[2024, "total"] == 61_318 + 108_869
    assert both.loc[2024, "unknown"] == 30_115 + 58_537
    assert both.loc[2014, "share_unknown"] < 0.2 and both.loc[2016, "share_unknown"] > 0.5
    zones = shares[shares.zone != "all"].groupby("year")[["total", "speed_infraction"]].sum()
    assert (zones.total == both.total.loc[zones.index]).all()
    assert (zones.speed_infraction == both.speed_infraction.loc[zones.index]).all()
