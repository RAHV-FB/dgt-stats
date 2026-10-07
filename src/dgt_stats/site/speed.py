"""Recorded speed and crash severity, and the change in the speed-infraction record."""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats.site.components import (
    _fmt_pct,
    _ratio_ci,
    _times,
    downloads,
    figure,
    limitation,
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
    adjusted_ci = _ratio_ci(rate, float(adjusted.ratio_low), float(adjusted.ratio_high))
    # The share of the crude ratio, on the log scale, that the adjustment removes.
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
        "the concurrent-factor speed series has no break": not bool(
            speed_changes[speed_changes.factor == "Inappropriate speed"].is_break.any()
        ),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"speed page: the tables no longer support: {failed}")

    body = summary(
        "In Spain outside Catalonia and the Basque Country, injury crashes in which the police "
        "recorded inappropriate speed were "
        f"{_fmt_pct(float(latest.share_of_crashes))} of all injury crashes in {last} and "
        f"{_fmt_pct(float(latest.share_of_deaths))} of the deaths. Over {types_span} they "
        f"killed {_times(crude)} as many people per crash as other injury crashes. Part of that "
        "difference reflects location: such crashes concentrate on interurban roads other than "
        "motorways and dual carriageways, where any injury crash is more often fatal. Compared "
        "with other crashes on the same kind of road in the same year, a crash with speed "
        f"recorded had about twice as many deaths: {adjusted_ci}. A second source on speed, "
        f"DGT's tables of drivers involved in injury crashes, changed in {status_jump}: from "
        "that year about half the drivers have no speed status recorded."
    )
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
        "<p>On every road type, crashes with speed recorded were deadlier than other crashes, "
        "and every interval lies above one. The size of the difference varies widely. On urban "
        f"streets, where an ordinary injury crash rarely kills "
        f"({float(urban.other_deaths_per_100):.2f} deaths per 100), a crash with speed recorded "
        f"had {_times(float(urban.rate_ratio))} as many deaths; on other interurban roads the "
        f"ratio was {_times(float(other.rate_ratio))}, and on dual carriageways "
        f"{_times(float(dual.rate_ratio))}. The adjusted ratio summarises this variation in one "
        "figure, and its interval is widened to allow for it.</p>"
    )
    body += technical(
        "How the speed report and the crash records are combined",
        f"<p>DGT's speed report, the {REPORT}, leaves out Catalonia and the Basque Country, "
        "which keep their own crash records. It gives crashes and deaths with speed recorded by "
        "road type, but totals of all crashes only for all roads, interurban roads and urban "
        "streets. DGT's crash records restricted to the same provinces reproduce those three "
        f"totals exactly in every year from {first_type} to {last_type}, the years both sources "
        "cover, and they supply the totals for each interurban road type. Within interurban "
        "roads the report's categories are matched to the road types of the crash records by "
        "name (autopistas to motorways, autovías to dual carriageways, the rest to other "
        "interurban roads). That match is checked only through the interurban total and is not "
        "reconciled road type by road type: a mismatch would move crashes between the three "
        "interurban rows, and the ratios by interurban road type and the adjusted ratio depend "
        "on it.</p>"
        "<p>The adjusted ratio comes from a quasi-Poisson model of deaths per crash with road "
        f"type and year. It brings the crude ratio of {_times(crude)} down to {_times(rate)}; "
        "measured on a logarithmic scale, which splits a ratio into additive parts, road type "
        f"and year account for {_fmt_pct(where_share, 0)} of the crude ratio.</p>",
    )

    body += "<h2>A record written after the crash</h2>"
    body += (
        "<p>Inappropriate speed in these data is a judgement the police record after the "
        "crash, once the outcome is known. Two biases follow from that timing, and they pull in "
        "opposite directions. Fatal crashes may be investigated more thoroughly, so speed may "
        "be recorded more often when someone has died, which would inflate the ratio. Speed "
        "that played a part but went unrecorded leaves those crashes in the comparison group, "
        "which would deflate it. The tables measure neither effect, so their balance is "
        "unknown.</p>"
        "<p>The ratio is therefore an association in the police record and not an estimate of "
        "how many deaths speed caused. That estimate, like the effect of a change in speeds, "
        "would require measured travelling speeds, and the files record speed only as the "
        "police's judgement.</p>"
    )

    body += f"<h2>A change in the speed-infraction record in {status_jump}</h2>"
    body += figure(
        "c3_speed_status",
        f"Stacked bars of drivers in injury crashes by recorded speed status, "
        f"{first_status}–{last_status}: speed infraction, driving too slowly, no infraction and "
        f"no status recorded. The share with no status recorded rises sharply in {status_jump}.",
        captions,
    )
    known_first = float(status.loc[first_status, "share_among_known"])
    known_last = float(status.loc[last_status, "share_among_known"])
    all_first = float(status.loc[first_status, "share_speed_infraction"])
    all_last = float(status.loc[last_status, "share_speed_infraction"])
    body += (
        "<p>DGT's yearbook tables also record, for each driver involved in an injury crash, "
        f"whether the police noted a speed infraction. In {first_status}, "
        f"{_fmt_pct(status.loc[first_status, 'share_unknown'], 0)} of drivers had no speed "
        f"status recorded. In {status_jump} the share jumped to "
        f"{_fmt_pct(status.loc[status_jump, 'share_unknown'], 0)}, and it has stayed close to "
        f"half since ({_fmt_pct(status.loc[last_status, 'share_unknown'], 0)} in "
        f"{last_status}). As a result, the two obvious readings of the table point in opposite "
        "directions. The share of all drivers with a speed infraction fell from "
        f"{_fmt_pct(all_first)} to {_fmt_pct(all_last)} between {first_status} and "
        f"{last_status}, while the share among drivers with a recorded status rose from "
        f"{_fmt_pct(known_first)} to {_fmt_pct(known_last)}. With half the drivers "
        "unclassified, neither series measures a trend in speeding. The speed report's series "
        "of crashes with speed recorded, used above, shows no break of this kind "
        '(<a href="factors.html">Recorded factors</a> tests every factor series for breaks).</p>'
    )

    body += limitation(
        "A crash may carry several recorded factors, and the ratio does not separate speed from "
        "the others recorded with it."
    )
    body += downloads(
        [
            ("speed_severity", "by year and road type"),
            ("speed_severity_pooled", f"pooled {types_span}, and adjusted"),
            ("q9_infraction_shares", "speed status in the driver tables"),
        ],
        method=("data.html#records", "recorded factors and their limits"),
    )
    return render_page(
        "speed",
        "Recorded speed and crash severity",
        "Deaths per injury crash when the police recorded inappropriate speed, compared with "
        "other crashes on the same kind of road, and a change in how DGT records speed "
        "infractions.",
        body,
    )
