"""Speed as a severity factor, and the recording discontinuity in the speed-status record."""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats.site.components import (
    _fmt_pct,
    _ratio_ci,
    _times,
    conclusion,
    downloads,
    figure,
    key_figures,
    limits,
    read_table,
    render_page,
    table,
)
from dgt_stats.site.numbers import _speed_numbers


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
    # The share of the crude ratio, on the log scale, that the road type accounts for.
    where_share = 1 - math.log(rate) / math.log(crude)
    checks = {
        "the adjusted ratio is above one and below the crude one": 1 < rate < crude,
        "the adjusted ratio's interval excludes no difference": float(adjusted.ratio_low) > 1,
        "urban streets carry the largest ratio": float(pooled.loc["urban"].rate_ratio)
        == float(pooled.rate_ratio.drop(index="adjusted").max()),
        "the speed status jump is a lasting one": bool(
            (
                status.share_unknown.loc[status_jump:] > 2 * status.share_unknown.loc[first_status]
            ).all()
        ),
    }
    types = pooled.drop(index="adjusted")
    checks["speed crashes concentrate where every crash is more often fatal"] = bool(
        types.speed_crashes.idxmax() == "other_interurban"
        and types.loc["other_interurban", "speed_crashes"] / types.speed_crashes.sum()
        > types.loc["other_interurban", "other_crashes"] / types.other_crashes.sum()
        and types.other_deaths_per_100.idxmax() == "other_interurban"
    )
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"speed page: the tables no longer support: {failed}")

    body = key_figures(
        [
            (
                f"Share of crashes, {last}",
                _fmt_pct(float(latest.share_of_crashes), 0),
                "with inappropriate speed recorded",
            ),
            (
                f"Share of deaths, {last}",
                _fmt_pct(float(latest.share_of_deaths), 0),
                "in those crashes",
            ),
            (
                "Deaths per crash, same road",
                _times(float(adjusted.rate_ratio)),
                f"{_times(float(adjusted.crude_ratio))} before road type is allowed for",
            ),
            (
                "Drivers with no speed record",
                _fmt_pct(float(status.loc[last_status, "share_unknown"]), 0),
                f"{_fmt_pct(float(status.loc[first_status, 'share_unknown']), 0)} in "
                f"{first_status}",
            ),
        ]
    )
    urban = pooled.loc["urban"]
    other = pooled.loc["other_interurban"]
    dual = pooled.loc["dual_carriageway"]
    body += (
        '<p class="answer">Crashes in which the police recorded inappropriate speed are a small '
        f"share of injury crashes, {_fmt_pct(float(latest.share_of_crashes), 0)} in {last}, and "
        f"a large share of deaths, {_fmt_pct(float(latest.share_of_deaths), 0)}. Per crash they "
        f"kill {_times(crude)} as many people as the rest. On a log scale "
        f"{_fmt_pct(where_share, 0)} of that ratio goes with where they happen: speed crashes "
        "concentrate on interurban roads other than autopistas and autovías, where every crash "
        "is more often fatal. "
        "Compared on the same kind of road in the same "
        f"year the ratio is {_ratio_ci(float(adjusted.rate_ratio), float(adjusted.ratio_low), float(adjusted.ratio_high))}.</p>"
    )
    body += figure(
        "f1_speed_severity",
        "Ratio of deaths per 100 injury crashes, speed recorded against not, by road type",
        captions,
    )
    rows = []
    for key in ("urban", "motorway", "dual_carriageway", "other_interurban"):
        row = pooled.loc[key]
        rows.append(
            {
                "Road type": row.road_type_label,
                "Speed crashes": row.speed_crashes,
                "Deaths per 100, speed recorded": row.speed_deaths_per_100,
                "Deaths per 100, other crashes": row.other_deaths_per_100,
                "Ratio": _ratio_ci(
                    float(row.rate_ratio), float(row.ratio_low), float(row.ratio_high)
                ),
            }
        )
    body += table(
        pd.DataFrame(rows),
        f"Injury crashes {types_span} in Spain without Cataluña and País Vasco. Sources: DGT "
        "Informe temático Factor Velocidad and crash microdata for the same provinces",
        {
            "Speed crashes": "int",
            "Deaths per 100, speed recorded": "dec2",
            "Deaths per 100, other crashes": "dec2",
        },
    )
    body += (
        "<p>The ratio is not the same everywhere. On urban streets, where an ordinary injury "
        "crash rarely kills, a crash with speed recorded kills "
        f"{_times(float(urban.rate_ratio))} as often; on other interurban roads "
        f"{_times(float(other.rate_ratio))}; on dual carriageways "
        f"{_times(float(dual.rate_ratio))}. The single adjusted ratio averages over that "
        "variation, and the page leads with it only because it is the fairest one-number "
        "answer.</p>"
    )

    body += "<h2>What the ratio can and cannot mean</h2>"
    body += (
        "<p>Speed here is a concurrent factor written by a police officer after the crash, not a "
        "measured speed. Two biases pull on the ratio in opposite directions. A fatal crash is "
        "investigated more thoroughly, so speed is more likely to be found and recorded when "
        "someone has died: that inflates the ratio. Speed that was present but not recorded "
        "sits in the comparison group: that deflates it. Neither can be measured from these "
        "tables. What the data do support is the direction and rough size: where speed is "
        f"judged to have played a part, a crash is about {_times(rate)} as likely to kill, on the "
        "same kind of road. It is an association in the police record, not an estimate of how "
        "many deaths speed caused.</p>"
    )
    body += (
        "<p>The report covers Spain without Cataluña and País Vasco, which keep their own "
        "records. Its totals for that scope, all roads, interurban roads and urban streets, are "
        "reproduced exactly by the crash microdata restricted to the same provinces, every year "
        f"from {first_type} to {last_type}; that check is what allows the report's "
        "speed-related crashes to be set against microdata totals for road types the report "
        "does not total. The check is on those three zone totals only. Within interurban roads "
        "the report's road types are matched to DGT's road-type codes by name (autopistas to "
        "codes 1 and 2, autovías to code 3, the rest to other interurban roads), and that match "
        "is not reconciled road type by road type: the three interurban rows add up to the "
        "checked interurban total, so a mismatch would move crashes between them, and the "
        "ratios by interurban road type and the adjusted ratio rest on it.</p>"
    )

    body += "<h2>A published series that changes meaning in 2016</h2>"
    body += figure(
        "c3_speed_status",
        f"Drivers in injury crashes by recorded speed status, {first_status}–{last_status}",
        captions,
    )
    known_first = float(status.loc[first_status, "share_among_known"])
    known_last = float(status.loc[last_status, "share_among_known"])
    all_first = float(status.loc[first_status, "share_speed_infraction"])
    all_last = float(status.loc[last_status, "share_speed_infraction"])
    body += (
        "<p>DGT's driver tables record, for each driver in an injury crash, whether the police "
        f"noted a speed infraction. In {first_status}, "
        f"{_fmt_pct(status.loc[first_status, 'share_unknown'], 0)} of drivers had no speed "
        f"status recorded. In {status_jump} that jumped to "
        f"{_fmt_pct(status.loc[status_jump, 'share_unknown'], 0)} "
        "and it has stayed there. The two obvious readings of the table now point in opposite "
        "directions: the share of <em>all</em> drivers with a speed infraction fell from "
        f"{_fmt_pct(all_first)} to {_fmt_pct(all_last)}, while the share among drivers with a "
        f"record <em>rose</em> from {_fmt_pct(known_first)} to {_fmt_pct(known_last)}. Neither is "
        "a trend in speeding. The report's concurrent-factor series, used above, shows no break "
        'of that kind; the <a href="factors.html">factors page</a> tests it.</p>'
    )
    body += downloads(
        [
            ("speed_severity", "by year and road type"),
            ("speed_severity_pooled", f"pooled {types_span} and adjusted"),
            ("q9_infraction_shares", "speed status in the driver tables"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Speed is recorded in a small share of injury crashes and a large share of deaths. On "
        f"the same kind of road in the same year, a crash with speed recorded kills about "
        f"{_times(rate)} as often as one without, and on urban streets "
        f"{_times(float(urban.rate_ratio))}. The data support speed as a recorded circumstance "
        "associated with severity, of that order. They do not support a count of deaths caused "
        "by speed, because the record is a judgement made after the fact, and they do not "
        "support a trend in speeding from DGT's driver tables, which change meaning in "
        f"{status_jump}. The crash records carry no measured speed, so how much a change in "
        "speeds would change deaths cannot be estimated from them."
    )
    body += limits(
        "The concurrent-factor record is the police's judgement, may name several factors for "
        "one crash, and is not a measured speed. The report excludes Cataluña and País Vasco. "
        f"The road-type comparison starts in {first_type}, where the microdata start; its "
        "interurban road types rest on a name match between the report and DGT's codes that is "
        "checked only through the interurban total; and the adjusted ratio is overdispersed "
        "because the urban ratio is so different from the rest."
    )
    return render_page(
        "speed",
        "Speed as a severity factor",
        "How much deadlier is a crash when speed is recorded, on the same kind of road? About "
        f"{_times(rate)}, with two biases the data cannot measure pulling in opposite directions.",
        body,
    )
