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
    motorway = pooled.loc["motorway"]
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
        # The prose calls the adjusted ratio a weighted summary of unequal ratios, not a ratio
        # that holds on every road.
        "the road-type ratios differ by more than chance": float(adjusted.heterogeneity_p) < 0.001,
        "letting the ratio differ by road type removes most of the extra variation": float(
            adjusted.dispersion_by_road_type
        )
        < float(adjusted.dispersion) / 2,
        "the adjusted ratio lies between the road-type ratios": float(types.rate_ratio.min())
        < rate
        < float(types.rate_ratio.max()),
        "most deaths in speed crashes are on other interurban roads": float(
            types.loc["other_interurban", "speed_deaths"]
        )
        > types.speed_deaths.sum() / 2,
        "the road-type intervals allow for year-to-year variation": bool(
            (types.dispersion >= 1).all()
        ),
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
        "driving too slowly is under one driver in a thousand": float(status.share_too_slow.max())
        < 0.001,
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
        "crash as other injury crashes. Part of that gap reflects where they happen: they are "
        "concentrated on interurban roads other than motorways and dual carriageways, where any "
        "crash is more often fatal. Compared with other crashes on the same kind of road, they "
        f"had more deaths per crash on every road type, from {float(dual.rate_ratio):.2f} times "
        f"on dual carriageways to {float(urban.rate_ratio):.2f} times on urban streets; the "
        f"weighted summary across road types, with the year allowed for, is {rate:.2f} times "
        f"(95% interval {adjusted_ci}). These are associations in police records, not "
        "estimates of what speed causes."
    )

    body += '<h2 id="road-types">More deaths per crash on every road type</h2>'
    body += figure(
        "f1_speed_severity",
        "Dot chart, on a logarithmic scale, of the ratio of deaths per 100 injury crashes with "
        "speed recorded to deaths per 100 other crashes, with 95% intervals, for four road types "
        "and for all roads adjusted for road type and year. Every interval lies above one. "
        f"Urban streets have the largest ratio, {float(urban.rate_ratio):.1f}, and the adjusted "
        f"ratio is {rate:.1f}.",
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
        f"outside Catalonia and the Basque Country, {types_span}. The intervals allow for the "
        "ratio varying from year to year more than chance alone would make it.",
        {
            "Crashes with speed recorded": "int",
            "Deaths per 100 crashes with speed recorded": "dec2",
            "Deaths per 100 other crashes": "dec2",
        },
    )
    body += (
        "<p>The ratio was largest on urban streets, where an ordinary injury crash rarely kills "
        f"({float(urban.other_deaths_per_100):.2f} deaths per 100 crashes, against "
        f"{float(urban.speed_deaths_per_100):.2f} with speed recorded). On interurban roads "
        f"other than motorways and dual carriageways it was {float(other.rate_ratio):.2f}, and "
        f"on motorways {float(motorway.rate_ratio):.2f}. The all-roads summary compares crashes "
        "within the same road type and year and is weighted towards other interurban roads, "
        "where most deaths in crashes with speed recorded occur. The road-type ratios differ by "
        "more than chance, so the summary describes no single kind of road, and its interval is "
        "widened to allow for how much they differ.</p>"
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
        f"type and year. It brings the crude ratio of {crude:.2f} down to {rate:.2f}; "
        "on a logarithmic scale, road type and year account for "
        f"{_fmt_pct(where_share, 0)} of the crude ratio. The model assumes one ratio for every "
        "road type. Letting the ratio differ by road type improves the fit by a "
        f"likelihood-ratio statistic of {float(adjusted.heterogeneity_lr):.0f} on "
        f"{int(adjusted.heterogeneity_df)} degrees of freedom and lowers the Pearson dispersion "
        f"from {float(adjusted.dispersion):.1f} to "
        f"{float(adjusted.dispersion_by_road_type):.1f}: most of the extra variation the "
        "summary's interval allows for is the difference between road types. The road-type "
        "intervals are Poisson intervals widened by the square root of each road type's own "
        f"dispersion across years ({float(types.dispersion.min()):.1f} to "
        f"{float(types.dispersion.max()):.1f}).</p>",
    )

    body += '<h2 id="what-it-shows">The ratio describes police records, not measured speeds</h2>'
    body += (
        "<p>Inappropriate speed is a recorded factor: a judgement the police record about a "
        "crash, usually once its outcome is known "
        '(<a href="factors.html#recorded-factors">Recorded factors</a> explains these records). '
        "No file records how fast anyone was travelling. The ratio shows that crashes with "
        "speed recorded were deadlier than other crashes on the same kind of road. It does not "
        "show that speed caused those crashes or the deaths in them, and it does not separate "
        "speed from other factors recorded in the same crash. Recording could bias the ratio "
        "either way: police may look harder for speed when someone has died, which would raise "
        "it, while speed that played a part but went unrecorded leaves those crashes among the "
        "others, which would lower it. The data cannot measure either bias.</p>"
    )

    body += '<h2 id="driver-tables">The driver tables cannot show a trend in speeding</h2>'
    known_first = float(status.loc[first_status, "share_among_known"])
    known_last = float(status.loc[last_status, "share_among_known"])
    all_first = float(status.loc[first_status, "share_speed_infraction"])
    all_last = float(status.loc[last_status, "share_speed_infraction"])
    before_jump = status_jump - 1
    body += (
        "<p>DGT's yearbook tables cover all of Spain, including Catalonia and the Basque "
        "Country, and record for each driver in an injury crash whether the police noted a "
        f"speed infraction. From {status_jump}, about half of drivers have no speed status "
        f"recorded ({_fmt_pct(status.loc[status_jump, 'share_unknown'], 0)} in {status_jump} "
        f"and {_fmt_pct(status.loc[last_status, 'share_unknown'], 0)} in {last_status}, against "
        f"{_fmt_pct(status.loc[first_status, 'share_unknown'], 0)} in {first_status}). The two "
        "obvious readings of the tables therefore point in opposite directions: the share of "
        f"all drivers with a speed infraction fell from {_fmt_pct(all_first)} in {first_status} "
        f"to {_fmt_pct(all_last)} in {last_status}, while the share among drivers with a "
        f"recorded status rose from {_fmt_pct(known_first)} to {_fmt_pct(known_last)}. The speed "
        "report's crash series, used above, has no break of this kind; "
        '<a href="factors.html">Recorded factors</a> follows its trend.</p>'
    )
    body += figure(
        "c3_speed_status",
        "Stacked bars of drivers in injury crashes by recorded speed status, "
        f"{first_status}–{last_status}: speed infraction, no infraction and no status recorded; "
        "driving too slowly, under one driver in a thousand, is too rare to show. The share "
        "with no status recorded jumps from "
        f"{_fmt_pct(status.loc[before_jump, 'share_unknown'], 0)} in {before_jump} to "
        f"{_fmt_pct(status.loc[status_jump, 'share_unknown'], 0)} in {status_jump} and stays "
        "near half.",
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
