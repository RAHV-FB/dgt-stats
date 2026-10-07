"""Deaths, hospital admissions and injury crashes from the base year to the last, as counts and rates."""

from __future__ import annotations

import re

import pandas as pd

from dgt_stats import driver_risk, vehicles
from dgt_stats.site.components import (
    _change,
    _fmt_dec,
    _fmt_int,
    _fmt_pct,
    _join,
    downloads,
    figure,
    limitation,
    read_table,
    render_page,
    summary,
    table,
)
from dgt_stats.site.numbers import _risk_numbers

# The words that follow a change under each denominator.
PER = {
    "count": "as a count",
    "residents": "per resident",
    "licence_holders": "per licence holder",
    "vehicles": "per registered vehicle",
    "road_fuel": "per tonne of road fuel",
}


def _beyond(row: pd.Series) -> bool:
    """Whether a change lies outside the interval of an ordinary year."""
    return float(row.ratio_low_yty) > 1 or float(row.ratio_high_yty) < 1


def _beyond_poisson(row: pd.Series) -> bool:
    """Whether a change lies outside the pure Poisson interval."""
    return float(row.ratio_low) > 1 or float(row.ratio_high) < 1


def _size(ratio: float, decimals: int = 1) -> str:
    """How far a ratio lies from 1, as an unsigned percentage."""
    return _fmt_pct(abs(float(ratio) - 1), decimals)


def _rise_or_fall(ratio: float, decimals: int = 1) -> str:
    """A ratio to a base in words: a rise or a fall of so many per cent, or no change."""
    if round((float(ratio) - 1) * 100, decimals) == 0:
        return "no change"
    word = "rise" if float(ratio) > 1 else "fall"
    return f"a {word} of {_size(ratio, decimals)}"


def _check(ok: bool, claim: str) -> None:
    if not ok:
        raise ValueError(f"trends page: the tables no longer support: {claim}")


def page_trends(captions: dict[str, str]) -> str:
    risk = _risk_numbers()
    index, latest, base, last = risk["index"], risk["latest"], risk["base"], risk["last"]
    efficiency = read_table("risk_fuel_efficiency")
    crosscheck = read_table("risk_km_crosscheck").set_index("measure")
    scatter = read_table("risk_dispersion").set_index("outcome")
    panel_first = int(read_table("risk_annual_panel").year.min())
    segments = read_table("longrun_segments")
    scatter_first = int(scatter.loc["deaths_30d", "first_year"])
    scatter_last = int(scatter.loc["deaths_30d", "last_year"])
    scatter_years = f"{scatter_first}–{scatter_last}"
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
    _check(
        all(float(hosp.loc[key, "ratio_low_yty"]) > 1 for key in hosp_beyond),
        "admissions rose beyond an ordinary year as a count and per tonne of fuel",
    )
    _check(
        all(float(hosp.loc[key, "ratio_to_base"]) > 1 for key in PER),
        "admissions rose under every denominator",
    )
    if any(_beyond(crashes.loc[key]) for key in crash_keys):
        raise ValueError("trends page: a change in injury crashes now lies beyond an ordinary year")
    _check(
        all(float(crashes.loc[key, "ratio_to_base"]) < 1 for key in crash_keys),
        "injury crashes fell under every denominator",
    )
    crash_poisson = [key for key in crash_keys if _beyond_poisson(crashes.loc[key])]
    if not float(hosp.loc["count", "ratio_to_base"]) > float(crashes.loc["count", "ratio_to_base"]):
        raise ValueError("trends page: admissions per crash no longer rose")

    # How far each denominator itself moved between the two years: the reason the rates part.
    exposure = index[index.outcome == "deaths_30d"].set_index(["denominator", "year"]).exposure
    moved = {
        key: float(exposure.loc[(key, last)]) / float(exposure.loc[(key, base)])
        for key in ("residents", "licence_holders", "vehicles", "road_fuel")
    }
    ratio = {key: float(deaths.loc[key, "ratio_to_base"]) for key in PER}
    _check(
        all(moved[key] > 1 for key in ("residents", "licence_holders", "vehicles"))
        and moved["road_fuel"] < 1,
        "population, licence holders and fleet grew while road fuel sold fell",
    )
    _check(
        ratio["count"] > 1 and ratio["residents"] < 1 and ratio["road_fuel"] > 1,
        "deaths rose as a count, fell per resident and rose per tonne of fuel",
    )
    dispersion = {o: float(scatter.loc[o, "dispersion"]) for o in scatter.index}
    _check(
        all(dispersion[o] > 1 for o in ("deaths_30d", "hospitalised_30d", "crashes")),
        "annual counts scatter more than Poisson chance",
    )
    _check(
        dispersion["crashes"] > max(dispersion["deaths_30d"], dispersion["hospitalised_30d"]),
        "the widening matters most for injury crashes",
    )
    count_segments = segments[segments.measure == "count"]
    _check(
        int(count_segments.start.iloc[-1]) == scatter_first
        and int(count_segments.end.iloc[-1]) == scatter_last,
        "the scatter window is the last segment of the long-run trend",
    )

    def change(frame: pd.DataFrame, key: str) -> str:
        return _change(float(frame.loc[key, "ratio_to_base"]))

    def interval(row: pd.Series) -> str:
        return f"{_change(float(row.ratio_low_yty))} to {_change(float(row.ratio_high_yty))}"

    def size(frame: pd.DataFrame, key: str) -> str:
        return _size(float(frame.loc[key, "ratio_to_base"]))

    body = summary(
        f"Spain recorded {_fmt_int(deaths.loc['count', 'count'])} road deaths in {last}, "
        f"{size(deaths, 'count')} more than in {base}. As a rate, the change depends on what the "
        f"deaths are divided by: per resident they fell {size(deaths, 'residents')}, and per "
        f"tonne of road fuel sold they rose {size(deaths, 'road_fuel')}. Under every "
        "denominator, including drivers per licence holder and vehicle occupants per registered "
        "vehicle, the change lies within the ordinary year-to-year variation of the annual "
        "count. The number of people admitted to hospital after a crash rose beyond it: "
        f"{size(hosp, 'count')} as a count and {size(hosp, 'road_fuel')} per tonne of road fuel."
    )
    body += figure(
        "r1_risk_change",
        f"Three panels: deaths, people admitted to hospital and injury crashes in {last} as a "
        f"ratio to {base}, under each denominator they can be paired with, with intervals for "
        "ordinary year-to-year variation. Only the ratios for hospital admissions as a count and "
        "per tonne of road fuel have intervals that exclude no change.",
        captions,
    )

    # Ordinary variation: explained before the table that uses it.
    crash_width = dispersion["crashes"] ** 0.5
    body += (
        "<h2>Ordinary year-to-year variation</h2>"
        "<p>If road casualties were independent events, each occurring by chance, a year's count "
        "would scatter around its trend with a variance equal to its mean, the pattern known as "
        "Poisson variation. Spain's annual counts scatter more than that. Over "
        f"{scatter_years}, the last segment of the long-run trend before the pandemic, the "
        f"variance around the trend was {_fmt_dec(dispersion['deaths_30d'])} times the Poisson "
        f"variance for deaths, {_fmt_dec(dispersion['hospitalised_30d'])} times for hospital "
        f"admissions and {_fmt_dec(dispersion['crashes'], 0)} times for injury crashes. Each "
        "interval in the table is widened by the square root of its own count's factor, so that "
        "it spans the variation of an ordinary year: a change outside it is larger than the "
        "count's ordinary movement from one year to the next.</p>"
    )
    rows = []
    for frame in (deaths, hosp):
        for key in PER:
            row = frame.loc[key]
            rows.append(
                {
                    "Counted": row.numerator_label,
                    "Denominator": row.denominator_label,
                    f"Change, {base} to {last}": _change(float(row.ratio_to_base)),
                    "95% interval for an ordinary year": interval(row),
                }
            )
    body += table(
        pd.DataFrame(rows),
        f"Deaths and hospital admissions in {last} against {base}, under each denominator. The "
        f"interval covers ordinary year-to-year variation around the {scatter_years} trend.",
    )

    falls = "fall" if len(crash_poisson) == 1 else "falls"
    body += (
        "<p>The widening matters most for injury crashes, whose intervals are about "
        f"{crash_width:.0f} times as wide as Poisson intervals (the square root of "
        f"{_fmt_dec(dispersion['crashes'], 0)}). Injury crashes fell "
        f"{_join([f'{size(crashes, k)} {PER[k]}' for k in crash_keys])}."
        + (
            f" A pure Poisson interval would treat the {falls} "
            f"{_join([PER[k] for k in crash_poisson])} as real changes; against ordinary "
            "variation none of them stands out."
            if crash_poisson
            else " None of these falls stands out against ordinary variation."
        )
        + " DGT's yearbook does not split injury crashes by vehicle type, so they have no rate "
        "per licence holder or registered vehicle.</p>"
        "<p>Per resident, and for drivers per licence holder and occupants per registered "
        "vehicle, the rise in hospital admissions stays within ordinary variation. Admissions "
        "rose while the number of injury crashes fell, so more people were admitted to "
        "hospital per crash. Two explanations fit these tables: crashes became more serious, or "
        "admissions were traced back to crashes more completely. A change in tracing would move "
        "the series without any change on the road, and the tables do not distinguish the "
        "two.</p>"
    )

    # Why the same deaths read differently under each denominator, argued from the table above.
    body += (
        "<h2>Denominators and what they measure</h2>"
        "<p>Each denominator measures a different opportunity for harm. Residents measure a "
        "population: deaths per resident describe the burden of road deaths on everyone living "
        "in Spain, whether or not they travel. Licence holders and registered vehicles measure "
        "who or what could be on the road, without saying how much each is used. Road fuel sold "
        "comes closest to measuring traffic itself. A denominator can be set only against the "
        "casualties it could contain: pedestrians and cyclists hold no licence for their journey "
        "and travel in no registered vehicle, so licence holders divide only the deaths of "
        "drivers, and the fleet only those of occupants, of motorcycles, cars, vans, trucks and "
        "buses. Mopeds, bicycles, personal mobility vehicles and the yearbook's category of "
        "other vehicles are left out of both, because they need no licence, may be missing from "
        "the fleet or were reclassified during the period.</p>"
        f"<p>Between {base} and {last} the denominators themselves moved apart: the population "
        f"grew {_fmt_pct(moved['residents'] - 1)}, licence holders "
        f"{_fmt_pct(moved['licence_holders'] - 1)} and the registered fleet "
        f"{_fmt_pct(moved['vehicles'] - 1)}, while road fuel sold fell "
        f"{_fmt_pct(1 - moved['road_fuel'])}. The same deaths therefore fall per resident and "
        "rise per tonne of fuel. Both rates are correct, and they describe different things: "
        "the burden on a population, and deaths in proportion to the traffic that fuel stands "
        "for. A change that appears under one denominator and reverses under another says more "
        "about the denominators than about the roads.</p>"
    )

    last_rows = efficiency[(efficiency.year == last) & (efficiency.outcome == "deaths_30d")]
    by_gain = last_rows.set_index("hypothetical_annual_gain")
    gains = sorted(float(g) for g in by_gain.index if float(g) > 0)
    if len(gains) != 2 or 0.0 not in by_gain.index:
        raise ValueError(f"trends page: the hypothetical drifts are no longer two: {gains}")
    km_years = sorted(
        int(match.group(1))
        for column in crosscheck.columns
        if (match := re.fullmatch(r"billion_km_(\d{4})", column))
    )
    if len(km_years) != 2:
        raise ValueError(f"trends page: DGT kilometre estimates are no longer two: {km_years}")
    km_early, km_late = km_years
    span = f"{km_late}_to_{km_early}"
    all_km = float(crosscheck.loc["All vehicle types", f"km_ratio_{span}"])
    car_km = float(crosscheck.loc["Cars", f"km_ratio_{span}"])
    km_fuel = float(crosscheck.loc["All vehicle types", f"fuel_ratio_{span}"])
    _check(
        all_km < 1 and car_km < 1 and km_fuel > 1,
        "between the two kilometre estimates kilometres fell while road fuel sold rose",
    )
    _check(
        vehicles.KM_YEAR == km_early and driver_risk.KM_YEAR == km_late,
        "vehicle types use the earlier kilometre estimates and driver age the later",
    )
    body += (
        '<h2 id="road-fuel">Road fuel as a measure of traffic</h2>'
        "<p>Risk on the road is best expressed per kilometre travelled, but no Spanish source "
        "counts vehicle-kilometres on all roads every year, and road fuel sold stands in for "
        "them. The kilometres a tonne represents can change with fuel economy, electric driving, "
        "the mix of freight and private travel, and fuel bought in Spain but burnt elsewhere, "
        "and no available series measures that drift on all roads. The change per tonne of fuel "
        "therefore cannot be converted into a change per kilometre. A hypothetical case shows "
        "how much depends on it: had kilometres per tonne grown "
        f"{_fmt_pct(gains[0], 0)} a year since {base}, deaths per tonne of fuel would show "
        f"{_rise_or_fall(float(by_gain.loc[gains[0], 'ratio_to_base']))} instead of "
        f"{_rise_or_fall(float(by_gain.loc[0.0, 'ratio_to_base']))}; at "
        f"{_fmt_pct(gains[1], 0)} a year, "
        f"{_rise_or_fall(float(by_gain.loc[gains[1], 'ratio_to_base']))}. These growth rates are "
        'illustrative assumptions. <a href="long-run.html">Long-run trends</a> sets the latest '
        "years against the pre-pandemic trend, per tonne of fuel and per measured interurban "
        "kilometre.</p>"
        f"<p>DGT has published estimates of vehicle-kilometres for two years, {km_early} and "
        f"{km_late}. They are built by different methods and cannot be joined into a series: "
        f"they give {_size(all_km)} fewer kilometres in {km_late} than in {km_early} "
        f"({_size(car_km)} fewer for cars), while road fuel sold rose {_size(km_fuel)}. Each is "
        f"used where a single year is enough: {km_early} for "
        f'<a href="vehicles.html">vehicle types</a> and {km_late} for '
        '<a href="drivers.html">drivers by age</a>.</p>'
    )
    body += limitation(
        "The denominators are national totals that weight every resident, licence, vehicle and "
        "tonne of fuel alike. The intervals allow for the year-to-year variation of the casualty "
        "counts but treat every denominator as exact."
    )
    body += downloads(
        [
            ("risk_index", "every outcome, denominator and year"),
            ("risk_annual_panel", f"annual outcomes and denominators since {panel_first}"),
            ("risk_dispersion", "the year-to-year scatter of each count"),
            ("risk_fuel_efficiency", "the per-fuel change under hypothetical drifts"),
            ("risk_km_crosscheck", "DGT kilometre estimates against road fuel"),
        ],
        method=("data.html#rates", "rates, denominators and intervals"),
    )
    return render_page(
        "trends",
        f"Road deaths and injuries, {base}–{last}",
        f"Deaths, hospital admissions and injury crashes in Spain in {last} compared with "
        f"{base}, as counts and as rates per resident, licence holder, registered vehicle and "
        "tonne of road fuel sold.",
        body,
    )
