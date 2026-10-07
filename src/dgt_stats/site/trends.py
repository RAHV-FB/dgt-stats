"""2019 to 2024: the same deaths, crashes and admissions under the denominators they fit."""

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
    "residents": "Everyone living in Spain, most of whom are not on the road at any moment.",
    "licence_holders": "Everyone allowed to drive, any permit class, including those who rarely do.",
    "vehicles": "Every registered vehicle, used or not.",
    "road_fuel": "Petrol and diesel sold for road use, every road and vehicle: a proxy for traffic.",
}
PER = {
    "count": "as a count",
    "residents": "per resident",
    "licence_holders": "per licence holder (drivers only)",
    "vehicles": "per registered vehicle (occupants only)",
    "road_fuel": "per tonne of road fuel",
}


def _beyond(row: pd.Series) -> bool:
    """Whether a change lies outside the interval of an ordinary year."""
    return float(row.ratio_low_yty) > 1 or float(row.ratio_high_yty) < 1


def _beyond_poisson(row: pd.Series) -> bool:
    """Whether a change lies outside the pure Poisson interval."""
    return float(row.ratio_low) > 1 or float(row.ratio_high) < 1


def page_trends(captions: dict[str, str]) -> str:
    risk = _risk_numbers()
    latest, base, last = risk["latest"], risk["base"], risk["last"]
    efficiency = read_table("risk_fuel_efficiency")
    crosscheck = read_table("risk_km_crosscheck").set_index("measure")
    scatter = read_table("risk_dispersion").set_index("outcome")
    scatter_years = (
        f"{int(scatter.loc['deaths_30d', 'first_year'])}–"
        f"{int(scatter.loc['deaths_30d', 'last_year'])}"
    )
    deaths = latest.xs("deaths_30d", level="outcome")
    hosp = latest.xs("hospitalised_30d", level="outcome")
    crashes = latest.xs("crashes", level="outcome")
    crash_keys = [key for key in PER if key in crashes.index]
    # The prose below states which changes lie beyond an ordinary year; stop if the tables move.
    if list(deaths.index) != list(PER) or list(hosp.index) != list(PER):
        raise ValueError("trends page: deaths and admissions no longer have every denominator")
    if crash_keys != ["count", "residents", "road_fuel"]:
        raise ValueError(f"trends page: injury crashes now have other denominators: {crash_keys}")
    if any(_beyond(deaths.loc[key]) for key in PER):
        raise ValueError("trends page: a change in deaths now lies beyond an ordinary year")
    hosp_beyond = [key for key in PER if _beyond(hosp.loc[key])]
    if hosp_beyond != ["count", "road_fuel"]:
        raise ValueError(f"trends page: hospital admissions beyond an ordinary year: {hosp_beyond}")
    if any(_beyond(crashes.loc[key]) for key in crash_keys):
        raise ValueError("trends page: a change in injury crashes now lies beyond an ordinary year")
    crash_poisson = [key for key in crash_keys if _beyond_poisson(crashes.loc[key])]
    if not float(hosp.loc["count", "ratio_to_base"]) > float(crashes.loc["count", "ratio_to_base"]):
        raise ValueError("trends page: admissions per crash no longer rose")
    series = read_table("longrun_series").set_index(["measure", "year"])
    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_last = int(km_check.index.get_level_values("year").max())
    km_row = km_check.loc[("per_km", km_last)]
    trend_flags = [
        bool(series.loc[("road_fuel", last - 1), "outside_interval"]),
        bool(series.loc[("road_fuel", last), "outside_interval"]),
        bool(km_row.outside_interval),
    ]
    if trend_flags != [True, True, False]:
        raise ValueError(
            f"trends page: the trend comparison no longer reads as described: {trend_flags}"
        )

    def change(frame: pd.DataFrame, key: str) -> str:
        return _change(float(frame.loc[key, "ratio_to_base"]))

    body = key_figures(
        [
            (f"Deaths, {last} against {base}", change(deaths, "count"), "as a count"),
            ("Per resident", change(deaths, "residents"), "the same deaths"),
            ("Per tonne of road fuel", change(deaths, "road_fuel"), "the same deaths"),
            (
                "Hospitalised, as a count",
                change(hosp, "count"),
                "beyond an ordinary year's variation",
            ),
        ]
    )
    body += (
        f'<p class="answer">Whether road deaths changed after {base} depends on what they are '
        "divided by, and each denominator fits only part of the count. In "
        f"{last} there were {_fmt_int(deaths.loc['count', 'count'])} deaths, "
        f"{change(deaths, 'count')} on {base}. Per resident that is "
        f"{change(deaths, 'residents')} and per tonne of road fuel sold "
        f"{change(deaths, 'road_fuel')}. Licence holders and registered vehicles can only be "
        "set against the people they could contain: deaths of drivers of motorcycles, cars, "
        f"vans, trucks and buses per licence holder moved {change(deaths, 'licence_holders')}, "
        "and deaths of the occupants of those vehicles per registered vehicle "
        f"{change(deaths, 'vehicles')}. None of these changes in deaths is larger than an "
        "ordinary year's variation. One outcome did move: people injured and admitted to "
        f"hospital rose {change(hosp, 'count')} as a count and {change(hosp, 'road_fuel')} per "
        "tonne of road fuel, beyond that variation.</p>"
    )
    body += figure(
        "r1_risk_change",
        f"Deaths, hospitalised and injury crashes in {last} against {base} under each "
        "denominator they can be paired with",
        captions,
    )

    rows = []
    for key, note_text in DENOMINATOR_NOTES.items():
        for outcome_frame in (deaths, hosp):
            row = outcome_frame.loc[key]
            rows.append(
                {
                    "Denominator": row.denominator_label,
                    "Counted": row.numerator_label,
                    f"Change {last} on {base}": _change(float(row.ratio_to_base)),
                    "95% interval, ordinary year": f"{_change(float(row.ratio_low_yty))} to "
                    f"{_change(float(row.ratio_high_yty))}",
                    "What the denominator counts": note_text,
                }
            )
    body += table(
        pd.DataFrame(rows),
        f"Deaths and hospitalised injured, {last} against {base}, under each denominator; the "
        f"interval covers an ordinary year's variation around the {scatter_years} trend",
    )

    def crash_change(key: str) -> str:
        return f"{change(crashes, key)} {PER[key]}"

    body += (
        "<h2>Chance, and an ordinary year</h2>"
        "<p>A Poisson interval assumes a year's count varies only by chance. Spain's annual "
        f"counts vary more than that around their own trend: over {scatter_years}, deaths "
        f"by {float(scatter.loc['deaths_30d', 'dispersion']):.1f} times the Poisson variance, "
        "hospital admissions by "
        f"{float(scatter.loc['hospitalised_30d', 'dispersion']):.0f} times and injury crashes by "
        f"{float(scatter.loc['crashes', 'dispersion']):.0f} times. The intervals on this page "
        "are widened by the square root of that factor, the ratio of the spreads, so a change "
        "outside them is larger than an ordinary year, not only larger than chance. It matters "
        "most for crashes, whose spread is about "
        f"{float(scatter.loc['crashes', 'dispersion']) ** 0.5:.0f} times the Poisson one. "
        f"Injury crashes moved {_join([crash_change(k) for k in crash_keys])}"
        + (
            f"; with a pure Poisson interval the change {_join([PER[k] for k in crash_poisson])} "
            "would look certain, but "
            if crash_poisson
            else "; "
        )
        + "against an ordinary year none of these changes stands out. The yearbook does not "
        "split injury crashes by vehicle type, so they are not set against licence holders or "
        "registered vehicles.</p>"
        "<p>Set beside the rise in hospital admissions, crashes within their ordinary variation "
        "mean more people admitted per crash, which is either more serious crashes or more "
        f"complete tracing of admissions. Against {base} alone, the per-fuel rise in deaths is "
        "within an ordinary year. Against the direction the pre-2020 per-fuel trend was taking, "
        f"{last - 1} and {last} are outside its interval. On interurban roads, where the "
        f"Ministry measures kilometres up to {km_last}, deaths per measured kilometre in "
        f"{km_last} were {_change(float(km_row.ratio), 0)} on their own pre-2020 trend, inside "
        'its interval; the <a href="long-run.html">long-run page</a> sets out both '
        "comparisons and why they cannot be merged.</p>"
    )

    body += "<h2>Fuel is a proxy for kilometres</h2>"
    last_rows = efficiency[(efficiency.year == last) & (efficiency.outcome == "deaths_30d")]
    by_gain = last_rows.set_index("hypothetical_annual_gain")
    body += (
        "<p>No Spanish source counts vehicle-kilometres on all roads every year. Road fuel sold "
        "is the only annual series that covers every road and every vehicle, but the kilometres "
        "a tonne stands for can change: fuel used per kilometre, electric kilometres, the mix "
        "of freight and cars, and fuel bought in Spain but burnt elsewhere. No series in the "
        "repository measures that drift on all roads, so the per-fuel change cannot be turned "
        "into a change per kilometre. As a hypothetical only, to show how much the per-fuel "
        "figure depends on it: had kilometres per tonne grown 1% a year since "
        f"{base}, the per-fuel change in deaths would read "
        f"{_change(float(by_gain.loc[0.01, 'ratio_to_base']))} instead of "
        f"{_change(float(by_gain.loc[0.0, 'ratio_to_base']))}; at 2% a year, "
        f"{_change(float(by_gain.loc[0.02, 'ratio_to_base']))}. These rates are assumptions, "
        "not estimates, and nothing on this page rests on them.</p>"
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
            ("risk_dispersion", "the year-to-year scatter of each count"),
            ("risk_fuel_efficiency", "the per-fuel change under hypothetical drifts"),
            ("risk_km_crosscheck", "DGT kilometre estimates against fuel"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        f"Road deaths in {last} were {change(deaths, 'count')} on {base} as a count, "
        f"{change(deaths, 'residents')} per resident and {change(deaths, 'road_fuel')} per "
        "tonne of road fuel; driver deaths per licence holder moved "
        f"{change(deaths, 'licence_holders')} and occupant deaths per registered vehicle "
        f"{change(deaths, 'vehicles')}. None of those differences is larger than an ordinary "
        f"year's variation, so these series show no change in deaths against {base} under any "
        "of the denominators. Injury crashes show none either. Recorded serious injury rose: "
        f"more people were recorded as admitted to hospital after a crash in {last} than in "
        f"{base}, beyond an ordinary year as a count and per tonne of road fuel. With crashes "
        "within their variation, that is more admissions per crash, and these tables cannot "
        "tell more serious crashes from more complete tracing of admissions."
    )
    body += limits(
        "The denominators are totals for Spain and treat every resident, licence, vehicle and "
        "tonne of fuel alike. A rate per resident is a population rate, not a risk of "
        "travelling. Licence holders include every permit class and people who rarely drive; "
        "the registered fleet includes vehicles that are rarely used. The driver and occupant "
        "counts cover motorcycles, cars, vans, trucks and buses only: mopeds, bicycles, "
        "personal mobility vehicles and the yearbook's other vehicles are left out, because "
        "they need no licence, are not certainly in the fleet, or changed category in 2020. "
        "Fuel sold is not fuel burnt on Spanish roads, and it mixes freight with private "
        f"travel. The intervals cover each count's variation around its {scatter_years} "
        "trend and treat the denominators as exact. The hospitalised count depends on how "
        "completely admissions are traced back to crashes, and a change in that tracing would "
        "move the series without any change on the road; these tables cannot tell the two "
        "apart."
    )
    return render_page(
        "trends",
        f"{base} to {last}: counts and rates",
        f"Did road deaths change after {base} once divided by residents, road fuel, licence "
        "holders or the registered fleet, each paired with the casualties it can contain? "
        "Under every denominator the change in deaths is within an ordinary year's variation, "
        "and so is the change in injury crashes; hospital admissions rose beyond it as a count "
        "and per tonne of road fuel.",
        body,
    )
