"""1993 to 2024: structural change, the pandemic, and the trend re-run on measured kilometres."""

from __future__ import annotations

import pandas as pd

from dgt_stats.site.components import (
    _change,
    _fmt_pct,
    _join,
    _signed_pct,
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
from dgt_stats.site.numbers import _long_run_numbers

MEASURE_SHORT = {
    "count": "Deaths",
    "occupants_per_vehicle": "Occupant deaths per vehicle",
    "road_fuel": "Deaths per tonne of fuel",
}


def _years(values: list[int]) -> str:
    """'2003' when every value is the same year, '2002–2003' otherwise."""
    low, high = min(values), max(values)
    return str(low) if low == high else f"{low}–{high}"


def _within(row: pd.Series) -> str:
    return "outside its interval" if bool(row.outside_interval) else "inside its interval"


def page_long_run(captions: dict[str, str]) -> str:
    numbers = _long_run_numbers()
    segments, projected = numbers["segments"], numbers["projected"]
    efficiency, last = numbers["efficiency"], numbers["last"]
    headline = read_table("q1_annual_headline").set_index("year")
    panel = read_table("risk_annual_panel").set_index("year")
    peak = int(headline.deaths_30d.idxmax())
    by_measure = {
        measure: segments[segments.measure == measure].reset_index(drop=True)
        for measure in MEASURE_SHORT
    }
    if any(len(frame) != 3 for frame in by_measure.values()):
        raise ValueError("long-run page: a measure no longer has three segments")
    count_segments, fuel_segments = by_measure["count"], by_measure["road_fuel"]
    steep, flat = count_segments.iloc[1], count_segments.iloc[2]
    fuel_flat = fuel_segments.iloc[-1]
    first_breaks = [int(frame.start.iloc[1]) for frame in by_measure.values()]
    second_breaks = [int(frame.start.iloc[2]) for frame in by_measure.values()]
    middle = [float(frame.annual_change.iloc[1]) for frame in by_measure.values()]
    decade = [b - a for a, b in zip(first_breaks, second_breaks)]
    gap = max(max(first_breaks) - min(first_breaks), max(second_breaks) - min(second_breaks))
    last_segments = {measure: frame.iloc[-1] for measure, frame in by_measure.items()}
    plateau_start = int(flat.start)

    count_2020 = projected.loc[("count", 2020)]
    count_last = projected.loc[("count", last)]
    occupants = {
        year: projected.loc[("occupants_per_vehicle", year)] for year in range(2020, last + 1)
    }
    fuel = {year: projected.loc[("road_fuel", year)] for year in range(2020, last + 1)}
    back_inside = min(
        year
        for year in range(2020, last + 1)
        if not any(
            bool(projected.loc[(measure, later), "outside_interval"])
            for measure in ("count", "occupants_per_vehicle")
            for later in range(year, last + 1)
        )
    )

    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_panel = read_table("longrun_km_panel").set_index("year")
    coverage = read_table("longrun_km_coverage").set_index("year")
    km_last = int(km_panel.index.max())
    km_first = int(km_check.index.get_level_values("year").min())
    km_row = km_check.loc[("per_km", km_last)]
    km_low, km_high = (
        float(km_row.observed) / float(km_row.high),
        float(km_row.observed) / float(km_row.low),
    )
    fuel_km_row = km_check.loc[("per_fuel", km_last)]
    km_base = int(km_row.last_segment_start)
    share = coverage.outside_share
    share_shift = (1 - float(share.loc[km_last])) / (1 - float(share.loc[2019])) - 1
    per_tonne = km_panel.km_per_tonne

    # The prose below states each of these; stop if the tables stop supporting them.
    checks = {
        "count 2020 below its interval": bool(count_2020.outside_interval)
        and float(count_2020.ratio) < 1,
        "per fuel 2020 and 2021 inside": not bool(fuel[2020].outside_interval)
        and not bool(fuel[2021].outside_interval),
        "per fuel last two years above": all(
            bool(fuel[y].outside_interval) and float(fuel[y].ratio) > 1 for y in (last - 1, last)
        ),
        "occupants 2020 and 2021 below": all(
            bool(occupants[y].outside_interval) and float(occupants[y].ratio) < 1
            for y in (2020, 2021)
        ),
        "fleet grew in 2020": float(panel.loc[2020, "vehicle_fleet"])
        > float(panel.loc[2019, "vehicle_fleet"]),
        "plateau flat as a count and per vehicle": all(
            float(last_segments[m].low) < 0 < float(last_segments[m].high)
            for m in ("count", "occupants_per_vehicle")
        ),
        "per fuel last segment falls": float(last_segments["road_fuel"].high) < 0,
        "the first count segment is slow beside the steep one": -0.03
        < float(count_segments.annual_change.iloc[0])
        and float(steep.annual_change) < -0.08,
        "per km inside": not bool(km_row.outside_interval),
        "microdata reproduce the interurban series": bool(
            (coverage.deaths_microdata == coverage.deaths_series).all()
        ),
        "coverage shift under a point": abs(share_shift) < 0.01,
        "exposures diverge after 2019": float(per_tonne.loc[km_last]) > float(per_tonne.loc[2019]),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"long-run page: the tables no longer support: {failed}")

    body = key_figures(
        [
            (
                f"Deaths, {peak} to {plateau_start}",
                _fmt_pct(
                    1
                    - float(headline.loc[plateau_start, "deaths_30d"])
                    / float(headline.loc[peak, "deaths_30d"]),
                    0,
                ),
                "fewer",
            ),
            (
                f"Annual change, {int(steep.start)}–{int(steep.end)}",
                _signed_pct(float(steep.annual_change), 1),
                "deaths per year, the steep segment",
            ),
            (
                f"Annual change, {int(flat.start)}–{int(flat.end)}",
                _signed_pct(float(flat.annual_change), 1),
                "the plateau",
            ),
            (
                f"Per measured kilometre, {km_last}",
                _change(float(km_row.ratio), 0),
                f"interurban deaths against the {km_base}–2019 trend, inside its interval",
            ),
        ]
    )
    body += (
        '<p class="answer">Spain\'s road deaths fell slowly until '
        f"{int(steep.start)}, steeply for {int(steep.end) - int(steep.start)} years, and have "
        "not fallen since "
        f"{plateau_start}. As a count, 2020 was {_change(float(count_2020.ratio), 0)} against "
        "the pre-pandemic trend, below its interval. Divided by road fuel sold, 2020 and 2021 "
        f"were {_change(float(fuel[2020].ratio), 0)} and {_change(float(fuel[2021].ratio), 0)} "
        "against the pre-2020 per-fuel trend, inside its interval: deaths fell in line with the "
        f"fuel sold. By {last - 1} and {last}, deaths per tonne of road fuel were "
        f"{_change(float(fuel[last - 1].ratio), 0)} and {_change(float(fuel[last].ratio), 0)} "
        "above where that trend was heading, outside its interval. Road fuel is a proxy for "
        "kilometres that no series here calibrates on all roads, so that is an excess per tonne "
        "of fuel sold, not per kilometre. On interurban roads, where the Ministerio de "
        "Transportes measures the kilometres driven, deaths per measured kilometre in "
        f"{km_last} were {_change(float(km_row.ratio), 0)} on their own pre-2020 trend, inside "
        f"its interval, which runs from {_change(km_low, 0)} to {_change(km_high, 0)}.</p>"
    )
    body += figure(
        "l1_trend_projection",
        "Deaths, 1993–2024, against segmented trends fitted to 2019 and projected on",
        captions,
    )
    shown = segments.assign(
        Measure=segments.measure.map(MEASURE_SHORT),
        Years=[f"{int(a)}–{int(b)}" for a, b in zip(segments.start, segments.end)],
        Change=[_signed_pct(float(v), 1) for v in segments.annual_change],
        Interval=[
            f"{_signed_pct(float(lo), 1)} to {_signed_pct(float(hi), 1)}"
            for lo, hi in zip(segments.low, segments.high)
        ],
    )[["Measure", "Years", "Change", "Interval"]].rename(
        columns={"Change": "Annual change", "Interval": "95% interval"}
    )
    body += table(
        shown,
        "Segments of the 1993–2019 trend, turning points chosen by the data. Sources: DGT "
        "yearbook series (all deaths, and occupant deaths of motorcycles, cars, vans, trucks and "
        "buses), registered fleet and CORES road fuel",
    )
    body += (
        "<p>The three measures find the same history. The turning points are placed by the data "
        "(every combination of up to three is fitted and the simplest adequate model kept), and "
        f"they land within {gap} years of each other: a slow decline to "
        f"{_years(first_breaks)}, a fall of between {_fmt_pct(-max(middle))} and "
        f"{_fmt_pct(-min(middle))} a year for {_years(decade)} years, then a halt. In the last "
        f"segment the count changes {_signed_pct(float(last_segments['count'].annual_change), 1)} "
        "a year and occupant deaths per registered vehicle "
        f"{_signed_pct(float(last_segments['occupants_per_vehicle'].annual_change), 1)}, both "
        "with intervals that include no change; deaths per tonne of road fuel still fall, "
        f"{_signed_pct(float(fuel_flat.annual_change), 1)} a year. The per-vehicle measure counts "
        "only the occupants of motorcycles, cars, vans, trucks and buses, the people a "
        "registered vehicle can carry.</p>"
    )

    body += "<h2>2020 to 2024 against the pre-pandemic trends</h2>"
    body += figure(
        "l2_observed_over_trend",
        "Observed deaths divided by each measure's pre-pandemic trend, 2010–2024",
        captions,
    )
    rows = []
    for year in range(2020, last + 1):
        record = {"Year": year}
        for measure, label in MEASURE_SHORT.items():
            row = projected.loc[(measure, year)]
            flag = " (outside)" if bool(row.outside_interval) else ""
            record[label] = f"{float(row.ratio):.2f}{flag}"
        rows.append(record)
    body += table(
        pd.DataFrame(rows),
        "Observed deaths as a multiple of each projected trend; outside: beyond the 95% "
        "prediction interval",
        {"Year": "year"},
    )

    at_pace = efficiency[efficiency.hypothetical_extra_annual_gain == 0].set_index("year")

    def needed(year: int) -> float:
        return float(at_pace.loc[year, "ratio_low"]) ** (1 / (year - 2019)) - 1

    def excess(gain: float) -> str:
        rows = efficiency[
            (efficiency.hypothetical_extra_annual_gain == gain) & (efficiency.year >= last - 1)
        ].set_index("year")
        parts = []
        for year in (last - 1, last):
            row = rows.loc[year]
            where = "outside" if float(row.ratio_low) > 1 else "inside"
            parts.append(f"{_change(float(row.ratio), 0)} in {year} ({where} the interval)")
        return _join(parts)

    fuel_start = int(fuel_flat.start)
    body += (
        f"<p>As a count, 2020 was {_change(float(count_2020.ratio), 0)} against trend and "
        f"{last} {_change(float(count_last.ratio), 0)}. Occupant deaths per registered vehicle "
        f"were {_change(float(occupants[2020].ratio), 0)} in 2020 and "
        f"{_change(float(occupants[2021].ratio), 0)} in 2021, below the interval: the fleet, "
        "which counts vehicles whether used or not, grew in 2020 while deaths fell. From "
        f"{back_inside} the count and the per-vehicle measure are both inside their intervals. "
        "Per tonne of fuel, 2020 was "
        f"{_change(float(fuel[2020].ratio), 0)}, inside the interval, and {last} "
        f"{_change(float(fuel[last].ratio), 0)}, outside it.</p>"
        "<p>The per-fuel projection assumes that whatever moved kilometres per tonne over "
        f"{fuel_start}–2019 went on at the same pace after it. No series in the repository "
        "measures kilometres per tonne on all roads, so that assumption cannot be checked. As "
        "hypotheticals only: with kilometres per tonne growing an extra 1% a year from 2020 the "
        f"ratio would be {excess(0.01)}; with an extra 2% a year, {excess(0.02)}. The excess "
        f"would fall inside the interval with an extra {needed(last - 1) * 100:.1f} points a "
        f"year for {last - 1} and {needed(last) * 100:.1f} for {last}. These are conditions, "
        "not estimates, and the page draws no conclusion from them.</p>"
    )

    body += "<h2>Interurban roads: deaths per measured kilometre</h2>"
    cov_first, cov_last = int(coverage.index.min()), int(coverage.index.max())
    body += (
        "<p>The Ministerio de Transportes publishes the vehicle-kilometres travelled each year "
        "on the interurban roads of the State, the regions and the provincial councils, measured "
        "by their traffic counts. Divided into the yearbook's interurban deaths, that is the one "
        "series here whose numerator and denominator cover nearly the same roads. Nearly: the "
        "deaths also include interurban roads run by municipalities and other bodies, which the "
        "kilometres leave out. The DGT microdata, which reproduce the yearbook's interurban "
        f"count in every year from {cov_first} to {cov_last}, record who runs the road: between "
        f"{_fmt_pct(float(share.min()))} and {_fmt_pct(float(share.max()))} of interurban "
        "deaths each year were on roads outside the counted networks, "
        f"{_fmt_pct(float(share.loc[2019]))} in 2019 and {_fmt_pct(float(share.loc[km_last]))} "
        f"in {km_last}. The level of the rate is too high by about that share; the 2019 to "
        f"{km_last} comparison moves by under one point. Before {cov_first} the share cannot be "
        "measured.</p>"
        "<p>Fitting the same turning-point search to interurban deaths per measured kilometre, "
        f"{km_first}–2019, places the last turning point in {km_base} and finds a change of "
        f"{_signed_pct(float(km_row.last_segment_annual_change), 1)} a year after it. Projected "
        f"on with each year's kilometres, {km_last} sits {_change(float(km_row.ratio), 0)} on "
        "that trend, inside the interval, and 2020 at "
        f"{_times(float(km_check.loc[('per_km', 2020), 'ratio']))} the trend.</p>"
        "<p>The same interurban deaths divided by national road fuel give a different "
        f"projection: {km_last} at {_change(float(fuel_km_row.ratio), 0)} on that trend, "
        f"{_within(fuel_km_row)}. That is not a second rate: fuel sold for every road, towns "
        "included, is not the exposure of interurban deaths, and it is shown only as a "
        "diagnostic of the fuel proxy. The two exposures part after 2019: measured interurban "
        f"kilometres per tonne of national road fuel were {float(per_tonne.loc[2019]):,.0f} in "
        f"2019 and {float(per_tonne.loc[km_last]):,.0f} in {km_last}. That ratio mixes scopes, "
        "so it is not a measure of fuel economy, and nothing here uses it to correct the "
        "all-road per-fuel series.</p>"
    )
    body += figure(
        "l4_km_against_fuel",
        "Interurban deaths against the pre-pandemic trend, per measured kilometre, with "
        "national road fuel as a diagnostic",
        captions,
    )
    body += downloads(
        [
            ("longrun_series", "observed against trend, every year"),
            ("longrun_segments", "segments and annual changes"),
            ("longrun_model_choice", "the turning-point search"),
            ("longrun_efficiency", "the per-fuel ratio under hypothetical drifts"),
            ("longrun_km_panel", "interurban deaths, kilometres and fuel"),
            ("longrun_km_check", "the trend re-run on kilometres, with the fuel diagnostic"),
            ("longrun_km_coverage", "interurban deaths by who runs the road"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        f"Spanish road deaths fell most between about {_years(first_breaks)} and "
        f"{plateau_start}, and as a count they have not fallen since. In 2020 the count fell "
        "below its pre-pandemic trend while deaths per tonne of road fuel stayed inside the "
        f"interval of theirs. From {back_inside} the count and occupant deaths per registered "
        "vehicle are inside their intervals; deaths per tonne of road fuel are above theirs in "
        f"{last - 1} and {last}, but fuel is a proxy whose relation to kilometres is not "
        "measured on all roads. On interurban roads, the one network where kilometres are "
        f"measured, deaths per kilometre in {km_last} were inside the interval of their "
        f"pre-2020 trend. These series show no rise in deaths per kilometre on interurban roads "
        f"up to {km_last}; they cannot say what happened per kilometre on all roads."
    )
    body += limits(
        "The trends are statistical descriptions, not explanations, and a projection assumes "
        "the last segment would have continued. Road fuel is fuel sold, a proxy for traffic "
        "whose relation to kilometres is not measured on all roads. The measured kilometres "
        "cover the interurban roads of the State, the regions and the provincial councils, run "
        f"to {km_last} and change basis in 2008; between {_fmt_pct(float(share.min()))} and "
        f"{_fmt_pct(float(share.max()))} of interurban deaths in {cov_first}–{cov_last} were "
        "on other roads. The registered fleet counts vehicles whether used or not, and the "
        "per-vehicle measure counts only occupants of motorcycles, cars, vans, trucks and "
        "buses. The 30-day death series is taken as DGT publishes it for every year since "
        "1993; the repository does not document whether its definition changed over that "
        "period."
    )
    return render_page(
        "long-run",
        "1993 to 2024: structural change and the pandemic",
        "Which changes in thirty years of road deaths are structural, and which are the "
        "pandemic? Fit the trend before 2020, project it, and compare the count with occupant "
        "deaths per registered vehicle, deaths per tonne of road fuel and, on interurban roads, "
        "deaths per measured kilometre.",
        body,
    )
