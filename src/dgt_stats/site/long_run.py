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
    "vehicles": "Deaths per vehicle",
    "road_fuel": "Deaths per tonne of fuel",
}


def page_long_run(captions: dict[str, str]) -> str:
    numbers = _long_run_numbers()
    segments, projected = numbers["segments"], numbers["projected"]
    efficiency, last = numbers["efficiency"], numbers["last"]
    headline = read_table("q1_annual_headline").set_index("year")
    peak = int(headline.deaths_30d.idxmax())
    count_segments = segments[segments.measure == "count"].reset_index(drop=True)
    fuel_segments = segments[segments.measure == "road_fuel"].reset_index(drop=True)
    steep, flat = count_segments.iloc[1], count_segments.iloc[2]
    fuel_flat = fuel_segments.iloc[-1]
    count_2020 = projected.loc[("count", 2020)]
    fuel_2020 = projected.loc[("road_fuel", 2020)]
    fuel_last = projected.loc[("road_fuel", last)]
    fuel_prev = projected.loc[("road_fuel", last - 1)]
    count_last = projected.loc[("count", last)]
    plateau_start = int(flat.start)
    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_panel = read_table("longrun_km_panel").set_index("year")
    km_last = int(km_panel.index.max())
    km_last_row = km_check.loc[("per_km", km_last)]
    km_prev_row = km_check.loc[("per_km", km_last - 1)]
    fuel_km_last = km_check.loc[("per_fuel", km_last)]
    fuel_km_prev = km_check.loc[("per_fuel", km_last - 1)]
    # The answer below says which of these lie outside their intervals; stop if that changes.
    flags = [
        bool(row.outside_interval) for row in (fuel_km_last, fuel_km_prev, km_last_row, km_prev_row)
    ]
    if flags != [True, False, False, False]:
        raise ValueError(
            f"long-run page: the kilometre check no longer splits as described: {flags}"
        )
    km_base = int(km_last_row.last_segment_start)

    def per_tonne_pace(first: int, last_year: int) -> float:
        ratio = float(km_panel.loc[last_year, "km_per_tonne"] / km_panel.loc[first, "km_per_tonne"])
        return ratio ** (1 / (last_year - first)) - 1

    def per_tonne_growth(first: int, last_year: int) -> str:
        return _signed_pct(per_tonne_pace(first, last_year), 1)

    # The extra yearly growth in kilometres per tonne, beyond the pace the national per-fuel
    # trend's last segment already carries, that brings a year's per-fuel excess inside the
    # interval; and the extra growth the measured kilometres show.
    at_pace = efficiency[efficiency.extra_annual_efficiency_gain == 0].set_index("year")

    def needed(year: int) -> float:
        return float(at_pace.loc[year, "ratio_low"]) ** (1 / (year - 2019)) - 1

    fuel_start = int(fuel_flat.start)
    measured_extra = per_tonne_pace(2019, km_last) - per_tonne_pace(fuel_start, 2019)
    margin = measured_extra - needed(km_last)
    if margin < 0:
        enough = "not enough"
    elif margin < 0.005:
        enough = "just enough"
    else:
        enough = "more than enough"

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
                f"Per kilometre driven, {km_last}",
                _change(float(km_last_row.ratio), 0),
                f"interurban, against the {km_base}–2019 trend; "
                f"{_change(float(fuel_km_last.ratio), 0)} per tonne of fuel",
            ),
        ]
    )
    body += (
        '<p class="answer">Spain\'s road deaths fell slowly until '
        f"{int(steep.start)}, steeply for a decade, and have not fallen since "
        f"{plateau_start}. The pandemic looks like a dip in that plateau and a recovery. Measured "
        "against traffic it was neither: per tonne of road fuel, 2020 and 2021 were on the "
        "pre-pandemic trend, so the fall in deaths was the fall in driving. What changed after "
        f"is smaller than fuel suggests. By {last - 1} and {last}, deaths per tonne of fuel were "
        f"{_change(float(fuel_prev.ratio), 0)} and {_change(float(fuel_last.ratio), 0)} above "
        "where the pre-2020 decline was heading. On interurban roads, where the Ministerio de "
        "Transportes measures the kilometres driven, the same comparison can be made both ways: "
        f"in {km_last} deaths per tonne of fuel were {_change(float(fuel_km_last.ratio), 0)} "
        "above trend, outside the interval, but deaths per kilometre only "
        f"{_change(float(km_last_row.ratio), 0)}, inside it ({km_last - 1}: "
        f"{_change(float(fuel_km_prev.ratio), 0)} per tonne of fuel, just inside, and "
        f"{_change(float(km_prev_row.ratio), 0)} per kilometre). The counts cannot yet tell "
        "whether the pre-2020 decline carried "
        "on or stalled, but they rule out a jump in risk per kilometre. Fuel overstated the "
        "rise because each tonne carried more traffic after 2019 than before.</p>"
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
        "yearbook series, registered fleet and CORES road fuel",
    )
    body += (
        "<p>The three measures find the same history. The turning points are placed by the data "
        "(every combination of up to three is fitted and the simplest adequate model kept), and "
        "they land within two years of each other: a slow decline to about 2003, a fall of "
        "around a tenth a year for a decade, then a halt. Per vehicle and per tonne of fuel the "
        "last segment still slopes down "
        f"({_signed_pct(float(fuel_flat.annual_change), 1)} a year per tonne of fuel), because "
        "traffic kept growing while deaths held steady.</p>"
    )

    body += "<h2>2020 to 2024: distortion or trend?</h2>"
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

    def excess(gain: float) -> str:
        rows = efficiency[
            (efficiency.extra_annual_efficiency_gain == gain) & (efficiency.year >= last - 1)
        ].set_index("year")
        parts = []
        for year in (last - 1, last):
            row = rows.loc[year]
            where = "outside" if float(row.ratio_low) > 1 else "inside"
            parts.append(f"{_change(float(row.ratio), 0)} in {year} ({where} the interval)")
        return _join(parts)

    body += (
        f"<p>As a count, 2020 was {_change(float(count_2020.ratio), 0)} against trend and "
        f"{last} {_change(float(count_last.ratio), 0)}: a dip and a return. Per tonne of fuel, "
        f"2020 was {_change(float(fuel_2020.ratio), 0)}, inside the interval. The per-fuel trend "
        "already carries the growth in kilometres per tonne of its last segment, "
        f"{fuel_start}–2019, so projecting it assumes that growth went on at the same pace. If "
        f"kilometres per tonne grew an extra 1% a year from 2020, the excess is {excess(0.01)}; "
        f"at an extra 2% a year it is {excess(0.02)}. So the excess is clear if kilometres per "
        "tonne kept their pre-2020 pace, and inside the trend's uncertainty only if they grew "
        f"faster: about {needed(last - 1) * 100:.1f} points a year faster for {last - 1} and "
        f"{needed(last) * 100:.1f} for {last}.</p>"
    )
    body += "<h2>Kilometres, not fuel</h2>"
    body += (
        "<p>That condition can now be checked, roughly. The Ministerio de Transportes publishes "
        "the vehicle-kilometres travelled each year on the whole interurban network of the "
        "State, the regions and the provincial councils, measured by their traffic counts. "
        "Kilometres on that network per tonne of all road fuel grew "
        f"{per_tonne_growth(fuel_start, 2019)} a year from {fuel_start} to 2019 and "
        f"{per_tonne_growth(2019, km_last)} a year from 2019 to {km_last}: "
        f"{measured_extra * 100:.1f} points a year faster, {enough} to bring the per-fuel "
        f"excess of {km_last} inside the interval. The ratio is not fuel economy alone: it "
        "also moves when traffic shifts between towns and interurban roads, and with the mix "
        "of freight. Fitting the same turning-point search to "
        "interurban deaths with each exposure in turn, both place the last turning point in "
        f"{km_base} and both find a decline of {_signed_pct(float(km_last_row.last_segment_annual_change), 1)} "
        "a year after it. Projected on, the per-fuel trend leaves "
        f"{km_last} {_change(float(fuel_km_last.ratio), 0)} above it, outside the interval; the "
        f"per-kilometre trend leaves it {_change(float(km_last_row.ratio), 0)} above, inside. "
        f"And 2020 lies exactly on the per-kilometre trend ({_times(float(km_check.loc[('per_km', 2020), 'ratio']))}).</p>"
    )
    body += figure(
        "l4_km_against_fuel",
        "Interurban deaths against the pre-pandemic trend, per kilometre and per tonne of fuel",
        captions,
    )
    body += downloads(
        [
            ("longrun_series", "observed against trend, every year"),
            ("longrun_segments", "segments and annual changes"),
            ("longrun_model_choice", "the turning-point search"),
            ("longrun_efficiency", "fuel-economy sensitivity"),
            ("longrun_km_panel", "interurban deaths, kilometres and fuel"),
            ("longrun_km_check", "the trend re-run on kilometres"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "The large structural change in Spanish road deaths happened between about 2003 and "
        f"{plateau_start} and has not resumed. The pandemic did not interrupt it: 2020 and 2021 "
        "deaths fell in line with traffic, so they are a distortion of the count, not of the "
        "risk. After it, per tonne of fuel deaths appear to have risen well above the "
        "pre-pandemic decline; per kilometre measured on interurban roads they sit a few per "
        "cent above it, inside its interval, because each tonne of fuel now carries more "
        "traffic. The honest reading is that the counts cannot yet tell whether the slow "
        f"decline of {km_base}–2019 carried on or stalled, and that they rule out a jump in "
        "risk: the roads did not become measurably more dangerous."
    )
    body += limits(
        "The trends are statistical descriptions, not explanations, and a projection assumes "
        "the last segment would have continued. Road fuel is a proxy for traffic whose "
        "relation to kilometres drifts. The measured kilometres cover interurban roads only, "
        "leave out municipal interurban roads (up to a tenth of traffic, the Ministry "
        f"estimates), run to {km_last} and change basis in 2008. The registered fleet "
        "counts idle vehicles and grows as the fleet ages. The 30-day death series is taken as "
        "DGT publishes it for every year since 1993."
    )
    return render_page(
        "long-run",
        "1993 to 2024: structural change and the pandemic",
        "Which changes in thirty years of road deaths are structural, and which are the "
        "pandemic? Fit the trend before 2020, project it, and measure against traffic.",
        body,
    )
