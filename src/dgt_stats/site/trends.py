"""2019 to 2024: the same deaths, crashes and admissions under five denominators."""

from __future__ import annotations

import pandas as pd

from dgt_stats.site.components import (
    _change,
    _fmt_int,
    _join,
    conclusion,
    downloads,
    figure,
    key_figures,
    limits,
    read_table,
    render_page,
    table,
)
from dgt_stats.site.numbers import _risk_numbers

DENOMINATOR_NOTES = {
    "count": "The outcome itself.",
    "residents": "Everyone living in Spain, most of whom are not driving at any moment.",
    "licence_holders": "Everyone allowed to drive, including those who rarely do.",
    "vehicles": "Every registered vehicle, including the many that are rarely used.",
    "road_fuel": "Petrol and diesel sold for road use: the closest annual measure of traffic.",
}
PER = {
    "count": "as a count",
    "residents": "per resident",
    "licence_holders": "per licence holder",
    "vehicles": "per vehicle",
    "road_fuel": "per tonne of fuel",
}


def _beyond(row: pd.Series) -> bool:
    """Whether a change lies outside the interval of an ordinary year."""
    return float(row.ratio_low_yty) > 1 or float(row.ratio_high_yty) < 1


def page_trends(captions: dict[str, str]) -> str:
    risk = _risk_numbers()
    latest, last = risk["latest"], risk["last"]
    efficiency = read_table("risk_fuel_efficiency")
    crosscheck = read_table("risk_km_crosscheck").set_index("measure")
    deaths = latest.xs("deaths_30d", level="outcome")
    hosp = latest.xs("hospitalised_30d", level="outcome")
    crashes = latest.xs("crashes", level="outcome")
    # The prose below states which changes lie beyond an ordinary year; stop if the tables move.
    if any(_beyond(deaths.loc[key]) for key in PER):
        raise ValueError("trends page: a change in deaths now lies beyond an ordinary year")
    hosp_beyond = [key for key in PER if _beyond(hosp.loc[key])]
    if hosp_beyond != ["count", "road_fuel"]:
        raise ValueError(f"trends page: hospital admissions beyond an ordinary year: {hosp_beyond}")
    shown = ("count", "residents", "vehicles", "road_fuel")
    crash_within = [key for key in shown if not _beyond(crashes.loc[key])]
    crash_beyond = [key for key in PER if _beyond(crashes.loc[key])]
    if crash_beyond != ["vehicles"] or (crashes.ratio_to_base >= 1).any():
        raise ValueError(f"trends page: crash changes beyond an ordinary year: {crash_beyond}")

    body = key_figures(
        [
            (
                f"Deaths, {last} against 2019",
                _change(float(deaths.loc["count", "ratio_to_base"])),
                "as a count",
            ),
            (
                "Per registered vehicle",
                _change(float(deaths.loc["vehicles", "ratio_to_base"])),
                "the same deaths",
            ),
            (
                "Per tonne of road fuel",
                _change(float(deaths.loc["road_fuel", "ratio_to_base"])),
                "the same deaths",
            ),
            (
                "Hospitalised, as a count",
                _change(float(hosp.loc["count", "ratio_to_base"])),
                "beyond an ordinary year's variation",
            ),
        ]
    )
    body += (
        '<p class="answer">Whether Spain\'s roads became more or less dangerous after 2019 '
        f"depends on what the deaths are divided by. In {last} there were "
        f"{_fmt_int(deaths.loc['count', 'count'])} deaths, "
        f"{_change(float(deaths.loc['count', 'ratio_to_base']))} on 2019. Per resident that is "
        f"{_change(float(deaths.loc['residents', 'ratio_to_base']))}, per licence holder "
        f"{_change(float(deaths.loc['licence_holders', 'ratio_to_base']))}, per registered "
        f"vehicle {_change(float(deaths.loc['vehicles', 'ratio_to_base']))} and per tonne of "
        f"road fuel {_change(float(deaths.loc['road_fuel', 'ratio_to_base']))}. The population "
        "and the fleet grew faster than the deaths; traffic did not. None of the five changes "
        "in deaths is larger than an ordinary year's variation. One outcome did move: people "
        "injured and admitted to hospital rose "
        f"{_change(float(hosp.loc['count', 'ratio_to_base']))} as a count and "
        f"{_change(float(hosp.loc['road_fuel', 'ratio_to_base']))} per tonne of road fuel, "
        "beyond that variation.</p>"
    )
    body += figure(
        "r1_risk_change",
        f"Deaths, hospitalised and injury crashes in {last} against 2019 under five denominators",
        captions,
    )

    rows = []
    for key, note_text in DENOMINATOR_NOTES.items():
        for outcome_frame, name in ((deaths, "Deaths"), (hosp, "Hospitalised")):
            row = outcome_frame.loc[key]
            rows.append(
                {
                    "Denominator": row.denominator_label,
                    "Outcome": name,
                    f"Change {last} on 2019": _change(float(row.ratio_to_base)),
                    "95% interval, ordinary year": f"{_change(float(row.ratio_low_yty))} to "
                    f"{_change(float(row.ratio_high_yty))}",
                    "What it counts": note_text,
                }
            )
    body += table(
        pd.DataFrame(rows),
        f"Deaths and hospitalised injured, {last} against 2019, under each denominator; the "
        "interval covers an ordinary year's variation around the 2013–2019 trend",
    )
    scatter = read_table("risk_dispersion").set_index("outcome")
    body += (
        "<h2>Chance, and an ordinary year</h2>"
        "<p>A Poisson interval assumes a year's count varies only by chance. Spain's annual "
        "counts vary more than that around their own trend: over the 2013–2019 plateau, deaths "
        f"by {float(scatter.loc['deaths_30d', 'dispersion']):.1f} times the Poisson variance, "
        "hospital admissions by "
        f"{float(scatter.loc['hospitalised_30d', 'dispersion']):.0f} times and injury crashes by "
        f"{float(scatter.loc['crashes', 'dispersion']):.0f} times, because how completely slight "
        "injuries are recorded changes from year to year. The intervals on this page are widened "
        "by the square root of that factor, the ratio of the spreads, so a change outside them "
        "is larger than an ordinary year, not only larger than chance. It matters most for "
        "crashes, whose spread is about "
        f"{float(scatter.loc['crashes', 'dispersion']) ** 0.5:.0f} times the Poisson one: with "
        "a pure Poisson interval the apparent fall per person and per vehicle looks certain; "
        "against an ordinary year only the fall per vehicle stays beyond it, and only just.</p>"
    )

    def crash_change(key: str) -> str:
        return f"{_change(float(crashes.loc[key, 'ratio_to_base']))} {PER[key]}"

    def crash_interval(key: str) -> str:
        row = crashes.loc[key]
        return f"{_change(float(row.ratio_low_yty))} to {_change(float(row.ratio_high_yty), 2)}"

    crash_text = (
        f"Injury crashes moved {_join([crash_change(k) for k in crash_within])}, "
        + ("all " if not crash_beyond else "")
        + "within an ordinary year's variation"
    )
    if crash_beyond:
        crash_text += "; " + "; ".join(
            f"{crash_change(k)}, just beyond it (interval {crash_interval(k)})"
            for k in crash_beyond
        )
    body += (
        f"<p>{crash_text}. Set beside the rise in hospital admissions, that means more people "
        "admitted per crash, which is either more serious crashes or more complete tracing of "
        "admissions. Against 2019 alone, the per-fuel rise in deaths is within an ordinary "
        "year. Against the direction the pre-2020 trend was taking it is outside the interval, "
        "but measured per kilometre on interurban roads it is inside; the "
        '<a href="long-run.html">long-run page</a> sets that out.</p>'
    )

    body += "<h2>Fuel is a proxy for kilometres, and it drifts</h2>"
    last_rows = efficiency[(efficiency.year == last) & (efficiency.outcome == "deaths_30d")]
    by_gain = last_rows.set_index("annual_efficiency_gain")
    body += (
        "<p>No Spanish source counts vehicle-kilometres every year. Road fuel is the closest "
        "substitute, and it is biased in one known direction: a fleet that burns less per "
        "kilometre each year, and a growing share of electric kilometres that burn none, drive "
        "further per tonne. If kilometres per tonne improved by 1% a year after 2019, deaths per "
        f"kilometre moved {_change(float(by_gain.loc[0.01, 'ratio_to_base']))} rather than "
        f"{_change(float(by_gain.loc[0.0, 'ratio_to_base']))}; at 2% a year, "
        f"{_change(float(by_gain.loc[0.02, 'ratio_to_base']))}. So per kilometre, deaths were "
        "roughly flat between 2019 and "
        f"{last}, while the population and the fleet both grew.</p>"
    )
    all_types = crosscheck.loc["All vehicle types"]
    cars_row = crosscheck.loc["Cars"]
    body += (
        "<p>DGT has published two estimates of vehicle-kilometres, for 2022 and for 2024. They "
        "cannot replace fuel as a series: they are built differently, and between them the "
        f"total moves {_change(float(all_types.km_ratio_2024_to_2022))} (cars "
        f"{_change(float(cars_row.km_ratio_2024_to_2022))}) while road fuel moves "
        f"{_change(float(all_types.fuel_ratio_2024_to_2022))}. They are used where a single "
        'year is enough: <a href="vehicles.html">vehicle types</a> and '
        '<a href="drivers.html">driver age</a>.</p>'
    )
    body += downloads(
        [
            ("risk_index", "every outcome, denominator and year"),
            ("risk_annual_panel", "outcomes and denominators, 1993 onwards"),
            ("risk_fuel_efficiency", "fuel-economy sensitivity"),
            ("risk_km_crosscheck", "DGT kilometre estimates against fuel"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        f"Measured as a count, road deaths in {last} were slightly above 2019. Measured per "
        "resident, per licence holder or per vehicle they were slightly below; measured per "
        "unit of traffic, slightly above, or flat once better fuel economy is allowed for. None "
        "of those differences is larger than an ordinary year's variation, so the honest "
        "summary is that death risk did not measurably change against 2019. Crash risk did "
        "not either, under most denominators"
        + (
            f"; the fall {_join([PER[k] for k in crash_beyond])} is only just beyond an "
            "ordinary year. "
            if crash_beyond
            else ". "
        )
        + "Serious injury rose: more people were admitted to hospital after a crash "
        f"in {last} than in 2019, beyond an ordinary year as a count and per unit of traffic."
    )
    body += limits(
        "The denominators are totals for Spain and treat every resident, licence, vehicle and "
        "tonne of fuel alike. Fuel sold is not fuel burnt on Spanish roads, and it mixes freight "
        "with private travel. The intervals cover each count's variation around its 2013–2019 "
        "trend and treat the denominators as exact. The "
        "hospitalised count depends on how completely admissions are traced back to crashes, and "
        "a change in that tracing would move the series without any change on the road; these "
        "tables cannot tell the two apart."
    )
    return render_page(
        "trends",
        "2019 to 2024: counts against risk",
        "Did the roads get safer or more dangerous after the pandemic? For deaths the count and "
        "four denominators disagree, all within an ordinary year's variation; injury crashes "
        "fell under all five, within that variation except per vehicle, just beyond it; "
        "hospital admissions rose beyond it as a "
        "count and per unit of traffic.",
        body,
    )
