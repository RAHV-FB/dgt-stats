"""Speed status in DGT's driver tables: how the record of speed infractions moved.

No source measures speed. The yearbook tables 6.1 record a police judgement per driver ("speed
infraction", driving too slowly, none, or unknown). The speed page shows the share with no record
beside the share with one, because the unrecorded share jumped in 2016 and a single share would
hide it. The DGT speed report's own factor tables are read by :mod:`dgt_stats.factors`.
"""

from __future__ import annotations

import pandas as pd

from dgt_stats import io_tables, rates

ZONE_LABELS = {"all": "All roads", "interurban": "Interurban roads", "urban": "Urban streets"}


def _infractions() -> pd.DataFrame:
    return io_tables.read_table("tables_driver_infractions")


def _with_all_zones(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Append an ``all`` zone as the sum of interurban and urban."""
    both = frame.groupby([k for k in keys if k != "zone"], as_index=False).value.sum()
    both["zone"] = "all"
    return pd.concat([frame, both], ignore_index=True)


def infraction_shares() -> pd.DataFrame:
    """Drivers by speed status, year and zone, 2014–2024: counts, shares of all drivers, and the
    infraction share among drivers whose status is known (Wilson intervals)."""
    speed = _infractions()
    speed = speed[(speed.block == "speed") & (speed.vehicle_group == "total")]
    speed = _with_all_zones(speed[["year", "zone", "item", "value"]], ["year", "zone", "item"])
    wide = speed.pivot_table(index=["year", "zone"], columns="item", values="value").reset_index()
    wide = wide.rename_axis(columns=None)
    wide["known"] = wide.total - wide.unknown
    for item in ("speed_infraction", "too_slow", "none", "unknown"):
        wide[f"share_{item}"] = wide[item] / wide.total
    wide["share_among_known"] = wide.speed_infraction / wide.known
    intervals = [
        rates.wilson_interval(float(s) / float(k), float(k))
        for s, k in zip(wide.speed_infraction, wide.known)
    ]
    wide["share_among_known_low"] = [low for low, _ in intervals]
    wide["share_among_known_high"] = [high for _, high in intervals]
    wide["zone_label"] = wide.zone.map(ZONE_LABELS)
    order = {"all": 0, "interurban": 1, "urban": 2}
    wide = wide.sort_values(["year", "zone"], key=lambda s: s.map(order) if s.name == "zone" else s)
    columns = [
        "year",
        "zone",
        "zone_label",
        "total",
        "known",
        "speed_infraction",
        "too_slow",
        "none",
        "unknown",
        "share_speed_infraction",
        "share_too_slow",
        "share_none",
        "share_unknown",
        "share_among_known",
        "share_among_known_low",
        "share_among_known_high",
    ]
    return wide[columns].reset_index(drop=True)
