"""How far the ratios between ages move under the alternative assumptions.

The published estimate (:func:`dgt_stats.exposure_risk.national.rates`, :func:`older_split`)
gives each age group's involvement per kilometre against drivers aged 45-64, with a 95%
sampling interval. :func:`ranges` adds the lowest and highest ratio under the alternative
assumptions, each computed around that estimate:

* the regional profile: the Barcelona-area survey alone, the Madrid survey alone, the Barcelona
  area carrying driving per licence holder instead of per resident, and each part of the province
  alone;
* the age mix of the kilometres the survey's working days do not cover (weekends and public
  holidays, and the remainder of DGT's total, :mod:`dgt_stats.exposure_risk.coverage`);
* the split of the 65-and-over kilometres between 65-74 and 75 and over
  (:data:`dgt_stats.exposure_risk.national.SPLITS`);
* the age of the drivers whose age is not recorded: all of them in one of the four age groups.

The first three are crossed (every combination); the unrecorded ages are varied alone, since
assigning all of them to one group in every combination would compound an extreme. A range is
the spread of the alternatives tried, not a confidence interval and not a bound: other
choices would widen it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dgt_stats.emef import exposure
from dgt_stats.exposure_risk import coverage, national

GROUPS = national.GROUPS
REFERENCE = national.REFERENCE
OLDER = national.OLDER
CENTRAL_PROFILE = "central average of the Barcelona and Madrid surveys"
MIX_LABELS = {
    coverage.WORKING_DAY_MIX: "working-day mix",
    national.EMEF_WEEKEND_PROXY: "EMEF weekend stays",
    national.MOVILIA_WEEKEND: "MOVILIA weekend trips",
    coverage.LONG_DISTANCE_MIX: "MOVILIA long journeys",
}
SPLIT_LABELS = {
    national.REFERENCE_SPLIT: "Madrid km per resident",
    national.LICENCE_SPLIT: "Madrid km per licence holder",
    national.EQUAL_SPLIT: "equal km per licence holder",
}


def profiles() -> dict[str, dict]:
    """The central profile and every alternative regional profile: each survey alone, the
    province carrying driving per licence holder instead of per resident, and each part of the
    province alone."""
    out = {
        CENTRAL_PROFILE: national.average_profile(),
        "Barcelona-area survey alone": national.emef_profile(),
        "Madrid survey alone": national.edm_profile(),
        "Barcelona area per licence holder": national.licence_calibrated(national.emef_profile()),
    }
    for area in exposure.AREAS:
        out[area[0].upper() + area[1:] + " alone"] = national.emef_profile(area)
    return out


def _ratios(
    counts: pd.DataFrame, shares: pd.Series, older: float, killed: bool = False
) -> dict[str, float]:
    """Ratios to 45-64 of involvement (or deaths) per km at every age, from the counts, the km
    shares of the four groups and the 75+ share of the 65+ km."""
    column = "killed" if killed else "involved"
    reference = float(counts.loc[REFERENCE, column]) / float(shares[REFERENCE])
    out = {
        group: float(counts.loc[group, column]) / float(shares[group]) / reference
        for group in GROUPS
    }
    for group, part in (("65-74", 1 - older), ("75+", older)):
        out[group] = float(counts.loc[group, column]) / (part * float(shares["65+"])) / reference
    return out


def _label(profile: str, non_working: str, remainder: str, split: str) -> str:
    """What differs from the central estimate in one combination."""
    parts = []
    if profile != CENTRAL_PROFILE:
        parts.append(profile)
    if non_working != coverage.WORKING_DAY_MIX:
        parts.append(f"weekends and holidays: {MIX_LABELS[non_working]}")
    if remainder != coverage.WORKING_DAY_MIX:
        parts.append(f"remainder: {MIX_LABELS[remainder]}")
    if split != national.REFERENCE_SPLIT:
        parts.append(f"split at 75: {SPLIT_LABELS[split]}")
    return "; ".join(parts) or "central"


def alternatives() -> pd.DataFrame:
    """Every combination of regional profile, age mix of the uncovered kilometres and split at
    75, and every placement of the unrecorded ages around the central estimate, with the
    ratios to 45-64 of involvement and deaths per km at every age."""
    counts = national.drivers_involved().set_index("group")
    splits = national._older_ratios()
    rows = []

    def record(label: str, shares: pd.Series, older: float, how: str, extra=None) -> None:
        involved = _ratios(extra if extra is not None else counts, shares, older)
        killed = _ratios(extra if extra is not None else counts, shares, older, killed=True)
        rows.append({"label": label, "how": how, "measure": "involved per km"} | involved)
        rows.append({"label": label, "how": how, "measure": "killed per km"} | killed)

    for name, profile in profiles().items():
        km, _ = national.national_km(profile)
        base = km / km.sum()
        for split, ratios in splits.items():
            older_km = national._split_older(profile, ratios)
            older = older_km["75+"] / sum(older_km.values())
            for non_working in coverage.NON_WORKING_MIXES:
                for remainder in coverage.REMAINDER_MIXES:
                    shares = coverage.structure_shares(base, non_working, remainder)
                    record(
                        _label(name, non_working, remainder, split),
                        shares,
                        float(older),
                        "combination",
                    )
    # The unrecorded ages, one assumption at a time, around the central estimate. Those put in
    # the 65-and-over group are split between 65-74 and 75+ as the recorded drivers are.
    profile = national.average_profile()
    km, _ = national.national_km(profile)
    base = km / km.sum()
    older_km = national._split_older(profile, splits[national.REFERENCE_SPLIT])
    older = float(older_km["75+"] / sum(older_km.values()))
    unknown = counts.loc["unknown", ["involved", "killed"]]
    for assigned in GROUPS:
        moved = counts.copy()
        moved.loc[assigned, ["involved", "killed"]] += unknown
        if assigned == "65+":
            for group in OLDER:
                part = (
                    counts.loc[group, ["involved", "killed"]]
                    / counts.loc["65+", ["involved", "killed"]]
                )
                moved.loc[group, ["involved", "killed"]] += unknown * part
        record(
            f"unrecorded ages all in {assigned.replace('16-29', '18-29')}",
            base,
            older,
            "unrecorded age",
            extra=moved,
        )
    return pd.DataFrame(rows)


def _end(frame: pd.DataFrame, group: str, which: str) -> tuple[float, str]:
    index = frame[group].idxmin() if which == "min" else frame[group].idxmax()
    return float(frame.loc[index, group]), str(frame.loc[index, "label"])


def ranges(rates: pd.DataFrame, older: pd.DataFrame, sex: pd.DataFrame) -> pd.DataFrame:
    """The compact table of ranges: for each measure and age group, the central ratio to
    drivers aged 45-64 (for ``men to women``, of men's rate to women's), its 95% sampling interval, and the lowest and highest ratio under the
    alternatives (with what produces each end), and the same for men against women.

    ``rates`` is :func:`national.rates`, ``older`` is :func:`national.older_split` and ``sex`` is
    :func:`national.sex_per_km`."""
    grid = alternatives()
    central = rates[rates.method == national.CENTRAL_METHOD].set_index("group")
    split = older[
        (older.profile == national.CENTRAL_METHOD) & (older.assumption == national.REFERENCE_SPLIT)
    ].set_index("group")
    rows = []
    for measure, column in (("involved per km", "involved"), ("killed per km", "killed")):
        part = grid[grid.measure == measure]
        for group in (*GROUPS, *OLDER):
            if column == "killed" and group in OLDER:
                continue
            if group in OLDER:
                ratio, low, high = (
                    split.loc[group, c] for c in ("ratio_to_45_64", "ratio_low", "ratio_high")
                )
            else:
                row = central.loc[group]
                ratio = row[f"{column}_ratio"]
                low, high = row[f"{column}_ratio_low"], row[f"{column}_ratio_high"]
            lowest, lowest_from = _end(part, group, "min")
            highest, highest_from = _end(part, group, "max")
            rows.append(
                {
                    "measure": measure,
                    "group": group,
                    "ratio": float(ratio),
                    "ratio_low": float(low),
                    "ratio_high": float(high),
                    "range_min": lowest,
                    "range_max": highest,
                    "range_min_from": lowest_from,
                    "range_max_from": highest_from,
                }
            )
    out = pd.DataFrame(rows)
    # Every ratio of the table lies inside its range, and the central combination is the
    # published estimate.
    inside = (out.range_min <= out.ratio + 1e-9) & (out.ratio <= out.range_max + 1e-9)
    if not inside.all():
        raise ValueError(f"ranges: central ratio outside its range:\n{out[~inside]}")
    centre = grid[grid.label == "central"]
    for measure, column in (("involved per km", "involved"), ("killed per km", "killed")):
        for group in GROUPS:
            published = float(out[(out.measure == measure) & (out.group == group)].ratio.iloc[0])
            found = float(centre[centre.measure == measure][group].iloc[0])
            if not np.isclose(found, published, rtol=1e-9):
                raise ValueError(f"ranges: central combination differs from the rates: {group}")
    men = pd.DataFrame(
        {
            "measure": sex.measure,
            "group": "men to women",
            "ratio": sex.ratio_men_to_women,
            "ratio_low": sex.ratio_low,
            "ratio_high": sex.ratio_high,
            "range_min": sex.range_low,
            "range_max": sex.range_high,
            "range_min_from": "other regional profiles",
            "range_max_from": "other regional profiles",
        }
    )
    return pd.concat([out, men], ignore_index=True)
