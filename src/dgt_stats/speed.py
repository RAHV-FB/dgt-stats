"""Speed status in DGT's driver tables: how the record of speed infractions moved.

No source measures speed. The yearbook tables 6.1 record a police judgement per driver ("speed
infraction", driving too slowly, none, or unknown). The share with no record jumps in 2016, so the
series shows no trend in speeding. The DGT speed report's own factor tables are read by
:mod:`dgt_stats.factors`.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import io_tables

ZONE_LABELS = {"all": "All roads", "interurban": "Interurban roads", "urban": "Urban streets"}


def _infractions() -> pd.DataFrame:
    return io_tables.read_table("tables_driver_infractions")


def _with_all_zones(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Append an ``all`` zone as the sum of interurban and urban."""
    both = frame.groupby([k for k in keys if k != "zone"], as_index=False).value.sum()
    both["zone"] = "all"
    return pd.concat([frame, both], ignore_index=True)


def infraction_shares() -> pd.DataFrame:
    """Drivers by speed status, year and zone, 2014–2024: counts and shares of all drivers,
    including the share with no status recorded."""
    speed = _infractions()
    speed = speed[(speed.block == "speed") & (speed.vehicle_group == "total")]
    speed = _with_all_zones(speed[["year", "zone", "item", "value"]], ["year", "zone", "item"])
    wide = speed.pivot_table(index=["year", "zone"], columns="item", values="value").reset_index()
    wide = wide.rename_axis(columns=None)
    for item in ("speed_infraction", "too_slow", "none", "unknown"):
        wide[f"share_{item}"] = wide[item] / wide.total
    wide["zone_label"] = wide.zone.map(ZONE_LABELS)
    order = {"all": 0, "interurban": 1, "urban": 2}
    wide = wide.sort_values(["year", "zone"], key=lambda s: s.map(order) if s.name == "zone" else s)
    columns = [
        "year",
        "zone",
        "zone_label",
        "total",
        "speed_infraction",
        "too_slow",
        "none",
        "unknown",
        "share_speed_infraction",
        "share_too_slow",
        "share_none",
        "share_unknown",
    ]
    return wide[columns].reset_index(drop=True)
