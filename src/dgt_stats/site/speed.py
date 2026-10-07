"""Deaths per crash where the police recorded inappropriate speed, and the break in DGT's record
of drivers' speed infractions.

The page compares severity between crashes with and without speed recorded; it estimates no
effect of speed, since no file holds measured speeds. Every number is read from the speed tables
and every qualitative sentence is checked against them.
"""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats.site.components import (
    _fmt_pct,
    _ratio_ci,
    _times,
    downloads,
    figure,
    read_table,
    render_page,
    summary,
    table,
    technical,
)
from dgt_stats.site.numbers import _speed_numbers

REPORT = '<span lang="es">Informe temático Factor Velocidad</span>'


def page_speed(captions: dict[str, str]) -> str:
    numbers = _speed_numbers()
    pooled, all_roads = numbers["pooled"], numbers["all_roads"]
    adjusted = pooled.loc["adjusted"]
    last = int(all_roads.index.max())
    latest = all_roads.loc[last]
    shares = read_table("q9_infraction_shares")
    status = shares[shares.zone == "all"].set_index("year")
    first_status, last_status = int(status.index.min()), int(status.index.max())
    yearly = numbers["yearly"]
    by_type = yearly[yearly.totals_source == "microdata"]
    first_type, last_type = int(by_type.year.min()), int(by_type.year.max())
    types_span = f"{first_type}–{last_type}"
    status_jump = int(status.share_unknown.diff().idxmax())
    crude, rate = float(adjusted.crude_ratio), float(adjusted.rate_ratio)
    adjusted_ci = f"{float(adjusted.ratio_low):.2f}–{float(adjusted.ratio_high):.2f}"
    # The share of the crude ratio, on the log scale, that road type and year account for.
    where_share = 1 - math.log(rate) / math.log(crude)
    types = pooled.drop(index="adjusted")
    urban = pooled.loc["urban"]
    other = pooled.loc["other_interurban"]
    dual = pooled.loc["dual_carriageway"]
    unknown_after = status.share_unknown.loc[status_jump:]
    speed_changes = read_table("factor_changes")

    checks = {
        "speed crashes are a larger share of deaths than of crashes": float(latest.share_of_deaths)
        > float(latest.share_of_crashes),
        "the adjusted ratio is above one and below the crude one": 1 < rate < crude,
        "the adjusted ratio is about two": 1.8 <= rate <= 2.2,
        "the adjusted ratio's interval excludes no difference": float(adjusted.ratio_low) > 1,
        "speed crashes concentrate where every crash is more often fatal": bool(
            types.speed_crashes.idxmax() == "other_interurban"
            and types.loc["other_interurban", "speed_crashes"] / types.speed_crashes.sum()
            > types.loc["other_interurban", "other_crashes"] / types.other_crashes.sum()
            and types.other_deaths_per_100.idxmax() == "other_interurban"
        ),
        "every road type's interval lies above one": bool((types.ratio_low > 1).all()),
        "urban streets carry the largest ratio and the lowest ordinary death rate": bool(
            types.rate_ratio.idxmax() == "urban" and types.other_deaths_per_100.idxmin() == "urban"
        ),
        "dual carriageways carry the smallest ratio": types.rate_ratio.idxmin()
        == "dual_carriageway",
        "the adjusted model has extra variation to allow for": float(adjusted.dispersion) > 1,
        "the unknown speed status jumps and stays near half": bool(
            (unknown_after > 2 * status.share_unknown.loc[first_status]).all()
            and unknown_after.between(0.45, 0.55).all()
        ),
        "the two readings of the driver tables point in opposite directions": bool(
            status.loc[last_status, "share_speed_infraction"]
            < status.loc[first_status, "share_speed_infraction"]
            and status.loc[last_status, "share_among_known"]
            > status.loc[first_status, "share_among_known"]
        ),
        "the crash series with speed recorded has no break": not bool(
            speed_changes[speed_changes.factor == "Inappropriate speed"].is_break.any()
        ),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"speed page: the tables no longer support: {failed}")

    body = summary(
        "In Spain outside Catalonia and the Basque Country, police recorded inappropriate speed "
        f"in {_fmt_pct(float(latest.share_of_crashes))} of injury crashes in {last}, and those "
        f"crashes accounted for {_fmt_pct(float(latest.share_of_deaths))} of the deaths. Over "
        f"{types_span}, crashes with speed recorded had {crude:.2f} times as many deaths per "
        "crash as other injury crashes. Part of that difference is where they happen: they are "
        "concentrated on interurban roads other than motorways and dual carriageways, where any "
        "crash is more often fatal. Compared with other crashes on the same kind of road in the "
        f"same year, they had about twice as many deaths: {rate:.2f} times (95% interval "
        f"{adjusted_ci}). This is an association in police crash records. It does not estimate "
        "how many crashes or deaths speeding caused."
    )

    body += "<h2>Deaths per crash by road type</h2>"
    body += figure(
        "f1_speed_severity",
        "Dot chart of the ratio of deaths per 100 injury crashes with speed recorded to deaths "
        "per 100 other crashes, with 95% intervals, for urban streets, motorways, dual "
        "carriageways, other interurban roads and all roads adjusted for road type and year. "
        "Every ratio is above one; the urban ratio is far above the rest.",
        captions,
    )
    rows = []
    for key in ("urban", "motorway", "dual_carriageway", "other_interurban"):
        row = pooled.loc[key]
        rows.append(
            {
                "Road type": row.road_type_label,
                "Crashes with speed recorded": row.speed_crashes,
                "Deaths per 100 crashes with speed recorded": row.speed_deaths_per_100,
                "Deaths per 100 other crashes": row.other_deaths_per_100,
                "Ratio (95% interval)": _ratio_ci(
                    float(row.rate_ratio), float(row.ratio_low), float(row.ratio_high)
                ),
            }
        )
    body += table(
        pd.DataFrame(rows),
        f"Deaths per 100 injury crashes with and without speed recorded, by road type, Spain "
        f"outside Catalonia and the Basque Country, {types_span}.",
        {
            "Crashes with speed recorded": "int",
            "Deaths per 100 crashes with speed recorded": "dec2",
            "Deaths per 100 other crashes": "dec2",
        },
    )
    body += (
        "<p>Crashes with speed recorded had more deaths per crash on every road type. The "
        "difference was largest on urban streets, where an ordinary injury crash rarely kills "
        f"({float(urban.other_deaths_per_100):.2f} deaths per 100 crashes): there, crashes with "
        f"speed recorded had {float(urban.rate_ratio):.2f} times as many deaths. On interurban "
        "roads other than motorways and dual carriageways the ratio was "
        f"{float(other.rate_ratio):.2f}, and on dual carriageways {float(dual.rate_ratio):.2f}. "
        f"The figure of {rate:.2f} for all roads compares crashes within the same road type and "
        "year and summarises these ratios, with an interval widened to allow for how much they "
        "vary.</p>"
    )
    body += technical(
        "How the speed report and the crash records are combined",
        f"<p>DGT's speed report, the {REPORT}, leaves out Catalonia and the Basque Country, "
        "which keep their own crash records. It gives crashes and deaths with speed recorded by "
        "road type, but totals of all crashes only for all roads, interurban roads and urban "
        "streets. DGT's crash records for the same provinces reproduce those three totals "
        f"exactly in every year from {first_type} to {last_type}, and supply the totals for each "
        "interurban road type. The report's interurban categories are matched to the road types "
        "of the crash records by name (autopistas to motorways, autovías to dual carriageways, "
        "the rest to other interurban roads); that match is checked only through the interurban "
        "total, not road type by road type.</p>"
        "<p>The adjusted ratio comes from a quasi-Poisson model of deaths per crash with road "
        f"type and year. It brings the crude ratio of {_times(crude)} down to {_times(rate)}; "
        "on a logarithmic scale, road type and year account for "
        f"{_fmt_pct(where_share, 0)} of the crude ratio.</p>",
    )

    body += "<h2>What a speed record shows</h2>"
    body += (
        "<p>Inappropriate speed in these data is a judgement police officers record about a "
        "crash after it has happened, usually once the outcome is known; no file records how "
        "fast anyone was travelling. The record shows only that crashes in which the police "
        "recorded speed were deadlier than other crashes. It does not show that speed "
        "caused those crashes, or that it caused the deaths in them. A crash can carry several "
        "recorded factors, and this comparison does not separate speed from the others. The "
        "ratio could also be distorted in either direction: police may look harder for speed "
        "when someone has died, which would raise it, while speed that played a part but went "
        "unrecorded leaves those crashes among the others, which would lower it. The data "
        "measure neither effect.</p>"
    )

    body += f"<h2>The {status_jump} break in the driver tables</h2>"
    known_first = float(status.loc[first_status, "share_among_known"])
    known_last = float(status.loc[last_status, "share_among_known"])
    all_first = float(status.loc[first_status, "share_speed_infraction"])
    all_last = float(status.loc[last_status, "share_speed_infraction"])
    body += (
        "<p>DGT's yearbook tables also record, for each driver involved in an injury crash, "
        "whether the police noted a speed infraction. From "
        f"{status_jump}, about half of drivers have no speed status recorded "
        f"({_fmt_pct(status.loc[status_jump, 'share_unknown'], 0)} in {status_jump} and "
        f"{_fmt_pct(status.loc[last_status, 'share_unknown'], 0)} in {last_status}, against "
        f"{_fmt_pct(status.loc[first_status, 'share_unknown'], 0)} in {first_status}), so the "
        "driver tables cannot be used as a trend in speeding. The two obvious readings point "
        "in opposite directions: "
        "the share of all drivers with a speed infraction fell from "
        f"{_fmt_pct(all_first)} to {_fmt_pct(all_last)} between {first_status} and "
        f"{last_status}, while the share among drivers with a recorded status rose from "
        f"{_fmt_pct(known_first)} to {_fmt_pct(known_last)}. The crash series used above, from "
        'the speed report, shows no break of this kind (<a href="factors.html">recorded '
        "factors</a> tests each series for breaks).</p>"
    )
    body += figure(
        "c3_speed_status",
        f"Stacked bars of drivers in injury crashes by recorded speed status, "
        f"{first_status}–{last_status}: speed infraction, driving too slowly, no infraction and "
        f"no status recorded. The share with no status recorded rises sharply in {status_jump}.",
        captions,
    )
    body += downloads(
        [
            ("speed_severity", "by year and road type"),
            ("speed_severity_pooled", f"pooled {types_span}, and adjusted"),
            ("q9_infraction_shares", "speed status in the driver tables"),
        ],
        method=("data.html#records", "police-recorded factors"),
    )
    return render_page(
        "speed",
        "Police-recorded inappropriate speed and crash severity",
        "Deaths per injury crash where the police recorded inappropriate speed, compared with "
        "other crashes on the same kind of road, from DGT's speed report and crash records.",
        body,
    )
