"""Speed as a severity factor, and the recording discontinuity in the speed-status record."""

from __future__ import annotations

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
        f"kill {_times(float(adjusted.crude_ratio))} as many people as the rest. About half of "
        "that is where they happen: speed crashes concentrate on conventional interurban roads, "
        "where every crash is more often fatal. Compared on the same kind of road in the same "
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
        "Injury crashes 2016–2023 in Spain without Cataluña and País Vasco. Sources: DGT "
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
        f"{_times(float(urban.rate_ratio))} as often; on conventional interurban roads "
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
        "judged to have played a part, a crash is about twice as likely to kill, on the same "
        "kind of road. That is consistent with what the physics of impact energy predicts. It is "
        "not an estimate of how many deaths speed caused.</p>"
    )
    body += (
        "<p>The report covers Spain without Cataluña and País Vasco, which keep their own "
        "records. Its totals for that scope are reproduced exactly by the crash microdata "
        "restricted to the same provinces, every year from 2016 to 2023; that check is what "
        "allows the report's speed-related crashes to be set against microdata totals for road "
        "types the report does not total.</p>"
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
        f"status recorded. In 2016 that jumped to {_fmt_pct(status.loc[2016, 'share_unknown'], 0)} "
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
            ("speed_severity_pooled", "pooled 2016–2023 and adjusted"),
            ("q9_infraction_shares", "speed status in the driver tables"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Speed is recorded in a small share of injury crashes and a large share of deaths. On "
        "the same kind of road in the same year, a crash with speed recorded kills about twice "
        "as often as one without, and on urban streets far more. The data support speed as a "
        "severity factor of that order. They do not support a count of deaths caused by speed, "
        "because the record is a judgement made after the fact, and they do not support a "
        "trend in speeding from DGT's driver tables, which change meaning in 2016."
    )
    body += limits(
        "The concurrent-factor record is the police's judgement, may name several factors for "
        "one crash, and is not a measured speed. The report excludes Cataluña and País Vasco. "
        "The road-type comparison starts in 2016, where the microdata start, and the adjusted "
        "ratio is overdispersed because the urban ratio is so different from the rest."
    )
    return render_page(
        "speed",
        "Speed as a severity factor",
        "How much deadlier is a crash when speed is involved, on the same kind of road? About "
        "twice, with two biases the data cannot measure pulling in opposite directions.",
        body,
    )
