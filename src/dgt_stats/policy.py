"""Policy case study (question Q8): interrupted time series on monthly road deaths.

Two interventions, two designs. The points-based licence of 1 July 2006 is a segmented regression
on the yearbook's monthly death series (1993–2024). The 90 km/h limit on conventional roads of
29 January 2019 is a difference-in-differences interrupted series on the microdata: conventional
roads against motorways and dual carriageways, month by month, 2016–2024. Both are Poisson
regressions with Newey–West standard errors; the estimates are read as coincidences unless the
pre-trend, the placebo distribution and the sensitivity fits all agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from dgt_stats import io_tables
from dgt_stats.paths import PROCESSED_DATA_DIR

PROCESSED_CRASHES = PROCESSED_DATA_DIR / "accidentes.parquet"

TREATED = "conventional"
CONTROL = "motorway_dual"
CONTROL_GROUPS = ("motorway", "dual_carriageway")
GROUP_LABELS = {TREATED: "Conventional roads", CONTROL: "Motorways and dual carriageways"}


@dataclass(frozen=True)
class Intervention:
    """One policy change and the windows its fits use.

    ``date`` is the first month treated as post-intervention. ``pre_start`` opens the fitting
    window, ``post_end`` closes the clean post-period, ``long_post_end`` the extended one used in
    the sensitivity fit, and ``second_break`` marks a confounding change inside that extended
    window. ``placebo_pre`` and ``placebo_post`` are the months a placebo break needs on each side.
    """

    key: str
    label: str
    date: pd.Timestamp
    pre_start: pd.Timestamp
    post_end: pd.Timestamp
    design: str  # "segmented" or "did"
    long_post_end: pd.Timestamp | None = None
    second_break: pd.Timestamp | None = None
    second_break_label: str = ""
    exclude_from: pd.Timestamp | None = None
    exclude_label: str = ""
    placebo_pre: int = 24
    placebo_dates: tuple[pd.Timestamp, ...] = field(default_factory=tuple)

    @property
    def post_months(self) -> int:
        return _months_between(self.date, self.post_end) + 1


def _months_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


INTERVENTIONS: dict[str, Intervention] = {
    "points_licence": Intervention(
        key="points_licence",
        label="Points-based licence, 1 July 2006",
        date=pd.Timestamp("2006-07-01"),
        pre_start=pd.Timestamp("2000-01-01"),
        post_end=pd.Timestamp("2007-11-01"),
        design="segmented",
        long_post_end=pd.Timestamp("2009-12-01"),
        second_break=pd.Timestamp("2007-12-01"),
        second_break_label="Penal Code reform on driving offences, 2 December 2007",
    ),
    "speed_limit_90": Intervention(
        key="speed_limit_90",
        label="90 km/h limit on conventional roads, 29 January 2019",
        date=pd.Timestamp("2019-02-01"),
        pre_start=pd.Timestamp("2016-01-01"),
        post_end=pd.Timestamp("2020-02-01"),
        design="did",
        long_post_end=pd.Timestamp("2024-12-01"),
        exclude_from=pd.Timestamp("2020-03-01"),
        exclude_label="pandemic restrictions from March 2020",
        placebo_dates=(pd.Timestamp("2017-01-01"), pd.Timestamp("2018-01-01")),
    ),
}

# Pandemic periods for the extended 2019 fit: (start, end, label).
PANDEMIC_PERIODS = (
    (pd.Timestamp("2020-03-01"), pd.Timestamp("2020-06-01"), "lockdown"),
    (pd.Timestamp("2020-07-01"), pd.Timestamp("2021-12-01"), "restrictions"),
)


# --------------------------------------------------------------------------- data


def _period(year: pd.Series, month: pd.Series) -> pd.Series:
    return pd.to_datetime(
        pd.DataFrame({"year": year.astype(int), "month": month.astype(int), "day": 1})
    )


def monthly_series(metric: str = "deaths_30d", zone: str = "all") -> pd.DataFrame:
    """One row per month, 1993–2024, from the yearbook series: ``period``, ``deaths``."""
    monthly = io_tables.read_table("series_monthly")
    rows = monthly[(monthly.metric == metric) & (monthly.zone == zone)]
    out = pd.DataFrame(
        {"period": _period(rows.year, rows.month), "deaths": rows.value.astype(float)}
    ).sort_values("period")
    out = out.reset_index(drop=True)
    expected = pd.date_range(out.period.min(), out.period.max(), freq="MS")
    if len(out) != len(expected) or not out.period.eq(expected).all():
        raise ValueError(f"monthly series {metric}/{zone} has gaps or duplicates")
    if out.deaths.isna().any():
        raise ValueError(f"monthly series {metric}/{zone} has missing months")
    out["metric"] = metric
    out["zone"] = zone
    return out


def monthly_by_road_group(crashes: pd.DataFrame | None = None) -> pd.DataFrame:
    """Monthly 30-day deaths on conventional roads and on motorways + dual carriageways, 2016–2024.

    Long format: ``period``, ``group`` (treated or control), ``deaths``. Every month of every year
    is present, with zero deaths where a group had none.
    """
    if crashes is None:
        crashes = pd.read_parquet(
            PROCESSED_CRASHES, columns=["ANYO", "MES", "road_group", "TOTAL_MU30DF"]
        )
    group = pd.Series(pd.NA, index=crashes.index, dtype="string")
    group[crashes.road_group == TREATED] = TREATED
    group[crashes.road_group.isin(CONTROL_GROUPS)] = CONTROL
    rows = crashes[group.notna()].assign(group=group[group.notna()])
    counts = rows.groupby(["ANYO", "MES", "group"], observed=True).TOTAL_MU30DF.sum()
    years = sorted(crashes.ANYO.unique())
    index = pd.MultiIndex.from_product(
        [years, range(1, 13), [TREATED, CONTROL]], names=["ANYO", "MES", "group"]
    )
    counts = counts.reindex(index, fill_value=0).reset_index()
    out = pd.DataFrame(
        {
            "period": _period(counts.ANYO, counts.MES),
            "group": counts.group.astype("string"),
            "deaths": counts.TOTAL_MU30DF.astype(float),
        }
    )
    return out.sort_values(["group", "period"]).reset_index(drop=True)


def fleet_offset(periods: pd.Series) -> pd.Series:
    """Registered vehicles for each month, the annual series interpolated between mid-years."""
    annual = io_tables.read_table("series_annual")
    fleet = annual[(annual.metric == "vehicle_fleet") & (annual.zone == "all")]
    fleet = fleet.dropna(subset=["value"]).sort_values("year")
    knots = pd.to_datetime(fleet.year.astype(int).astype(str) + "-07-01")
    x = knots.astype("int64").to_numpy(dtype=float)
    y = fleet.value.to_numpy(dtype=float)
    target = pd.to_datetime(periods).astype("int64").to_numpy(dtype=float)
    return pd.Series(np.interp(target, x, y), index=periods.index, name="fleet")


def window(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Rows with ``period`` between ``start`` and ``end`` inclusive."""
    return frame[(frame.period >= start) & (frame.period <= end)].reset_index(drop=True)
