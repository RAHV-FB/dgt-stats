"""Deaths, hospital admissions and injury crashes in the last year against the base year, as counts
and rates, with the per-fuel death rate also read against the long-run page's pre-pandemic trend."""

from __future__ import annotations

import pandas as pd

from dgt_stats import driver_risk, vehicles
from dgt_stats.risk_trends import NORMAL_QUANTILE
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
    technical,
)
from dgt_stats.site.numbers import _long_run_numbers, _risk_numbers

# The words that follow a change under each denominator.
PER = {
    "count": "as a count",
    "residents": "per resident",
    "licence_holders": "per licence holder",
    "vehicles": "per registered vehicle",
    "road_fuel": "per tonne of road fuel",
}
# A lower bound this close to no change is described as at the edge of an ordinary year.
EDGE_LOW = 0.98
WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


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
    crosscheck = read_table("risk_km_crosscheck").set_index("year")
    scatter = read_table("risk_dispersion").set_index("outcome")
    panel = read_table("risk_annual_panel").set_index("year")
    panel_first = int(panel.index.min())
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
    if hosp_beyond != ["road_fuel"]:
        raise ValueError(f"trends page: hospital admissions beyond an ordinary year: {hosp_beyond}")
    _check(
        float(hosp.loc["road_fuel", "ratio_low_yty"]) > 1,
        "admissions per tonne of fuel rose beyond an ordinary year",
    )
    _check(
        EDGE_LOW < float(hosp.loc["count", "ratio_low_yty"]) <= 1,
        "the count of admissions lies at the edge of an ordinary year",
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

    # How far each denominator itself moved between the two years: the reason the rates diverge.
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
    df_resid = {int(v) for v in scatter.df_resid}
    quantiles = {round(float(v), 6) for v in scatter.t_quantile}
    _check(
        len(df_resid) == 1 and len(quantiles) == 1,
        "every scatter factor rests on the same years and degrees of freedom",
    )
    df_resid, quantile = df_resid.pop(), float(scatter.t_quantile.iloc[0])
    widening = quantile / NORMAL_QUANTILE - 1
    deaths_scatter = scatter.loc["deaths_30d"]
    _check(
        float(deaths_scatter.dispersion_low)
        < 1
        < float(deaths_scatter.dispersion)
        < float(deaths_scatter.dispersion_high),
        "the deaths factor is uncertain enough to include pure chance",
    )
    # The step in recorded urban injury crashes inside the scatter window.
    step_end = scatter_first + 3
    urban_step = (
        float(panel.loc[step_end, "crashes_urban"] / panel.loc[scatter_first, "crashes_urban"]) - 1
    )
    interurban_step = (
        float(
            panel.loc[step_end, "crashes_interurban"]
            / panel.loc[scatter_first, "crashes_interurban"]
        )
        - 1
    )
    _check(
        urban_step > 0.2 and interurban_step < 0,
        "urban injury crashes stepped up early in the scatter window while interurban ones did not",
    )

    # The same rate against the pre-pandemic trend, as the long-run page reads it: the main
    # projection, and the one whose last segment starts with the count's.
    long_run = _long_run_numbers()
    fuel_projected = long_run["projected"].loc["road_fuel"]
    fit_end = int(long_run["series"].query("period == 'fitted'").year.max())
    fuel_trend = long_run["series"].query("measure == 'road_fuel' and period == 'projected'")
    trend_start = int(fuel_trend.projection_start.iloc[0])
    trend_slope = float(fuel_trend.projection_annual_change.iloc[0])
    count_trend = long_run["segments"].query("measure == 'count'").start.max()
    later = read_table("longrun_projection_sensitivity").set_index(["measure", "variant", "year"])
    recent = (last - 1, last)
    above = [fuel_projected.loc[year] for year in recent]
    later_rows = [later.loc[("road_fuel", f"start_{int(count_trend)}", year)] for year in recent]
    _check(
        long_run["last"] == last and fit_end == base,
        "the long-run projection ends in this page's last year and starts after its base year",
    )
    _check(
        all(bool(row.outside_interval) and float(row.ratio) > 1 for row in above),
        "per tonne of fuel, the last two years lie above the pre-pandemic trend's range",
    )
    _check(
        trend_slope < 0 and int(count_trend) > trend_start,
        "the per-fuel trend was falling, and a later start is the count's last turning point",
    )
    _check(
        all(float(row.ratio) > 1 for row in later_rows)
        and all(float(b.ratio) < float(a.ratio) for a, b in zip(above, later_rows)),
        "a trend started later leaves smaller excesses, both still above the trend",
    )
    count_projection = long_run["series"].query("measure == 'count' and period == 'projected'")
    _check(
        abs(float(count_projection.projection_dispersion.iloc[0]) - dispersion["deaths_30d"]) < 1e-9
        and int(count_projection.projection_start.iloc[0]) == scatter_first,
        "the long-run projection of the count uses the same years and scatter for deaths",
    )

    def interval(row: pd.Series) -> str:
        return f"{_change(float(row.ratio_low_yty))} to {_change(float(row.ratio_high_yty))}"

    def size(frame: pd.DataFrame, key: str) -> str:
        return _size(float(frame.loc[key, "ratio_to_base"]))

    # The only rise beyond ordinary variation is in admissions per tonne of fuel: the extra
    # yearly growth in kilometres per tonne that would bring its lower bound to no change.
    hosp_drift = float(hosp.loc["road_fuel", "ratio_low_yty"]) ** (1 / (last - base)) - 1
    hosp_other = [key for key in PER if key not in ("count", "road_fuel")]
    _check(
        float(hosp.loc["road_fuel", "ratio_low_yty"]) > 1
        and all(float(hosp.loc[key, "ratio_low_yty"]) <= 1 for key in hosp_other)
        and 0 < hosp_drift < 0.01,
        "admissions rise beyond ordinary variation only per tonne of fuel, and a small drift in "
        "kilometres per tonne would bring that within it",
    )
    _check(
        all(not bool(row.outside_interval) for row in later_rows),
        "for a trend started with the count's last turning point, neither year is outside the "
        "range",
    )

    recent_link = '<a href="long-run.html#recent-years">Long-run trends</a>'
    body = summary(
        f"Spain recorded {_fmt_int(deaths.loc['count', 'count'])} road deaths in {last}, "
        f"{size(deaths, 'count')} more than in {base}. Per resident they fell "
        f"{size(deaths, 'residents')}, and per tonne of road fuel sold they rose "
        f"{size(deaths, 'road_fuel')}. Under every denominator, the change from {base} lies "
        "within the ordinary year-to-year variation of the annual count. Set against the trend "
        f"of {trend_start}–{fit_end} instead, when deaths per tonne of fuel were falling about "
        f"{_fmt_pct(-trend_slope, 0)} a year, the rate in {last - 1} and {last} was "
        f"{_size(above[0].ratio, 0)} and {_size(above[1].ratio, 0)} above the projected trend, "
        f"outside its range, or {_size(later_rows[0].ratio, 0)} and "
        f"{_size(later_rows[1].ratio, 0)} for a trend started in {int(count_trend)}, within "
        f"its range ({recent_link}). The number of people admitted to hospital after a crash "
        f"rose {size(hosp, 'count')} as a count, at the edge of ordinary variation, and "
        f"{size(hosp, 'road_fuel')} per tonne of road fuel, beyond it; that excess would "
        f"disappear if kilometres per tonne of fuel had grown {_fmt_pct(hosp_drift)} a year "
        "faster than before."
    )
    body += figure(
        "r1_risk_change",
        f"Three panels: deaths, people admitted to hospital and injury crashes in {last} as a "
        f"ratio to {base}, under each denominator they can be paired with, with intervals for "
        "ordinary year-to-year variation. Only the ratio for hospital admissions per tonne of "
        "road fuel has an interval that excludes no change; the interval for admissions as a "
        "count only just includes it.",
        captions,
    )

    crash_width = (dispersion["crashes"] ** 0.5) * quantile / NORMAL_QUANTILE
    body += (
        "<h2>Deaths moved within ordinary variation; hospital admissions rose beyond it only per "
        "tonne of fuel</h2>"
        "<p>An ordinary year's variation is how far each annual count moved around its trend "
        f"over {scatter_years}, the last segment of the long-run trend before the pandemic. A "
        "change outside the interval in the table is larger than the count usually moves from "
        "one year to the next.</p>"
    )
    rows = []
    for frame, keys in ((deaths, list(PER)), (hosp, list(PER)), (crashes, crash_keys)):
        for key in keys:
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
        f"Deaths, hospital admissions and injury crashes in {last} against {base}, under each "
        "denominator. The interval covers ordinary year-to-year variation around the "
        f"{scatter_years} trend.",
    )
    falls = "fall" if len(crash_poisson) == 1 else "falls"
    body += (
        "<p>Injury crashes fell "
        f"{_join([f'{size(crashes, k)} {PER[k]}' for k in crash_keys])}."
        + (
            f" Judged against pure chance alone, the {falls} "
            f"{_join([PER[k] for k in crash_poisson])} would be real changes; against the "
            f"{scatter_years} scatter none of them stands out."
            if crash_poisson
            else f" None of these falls stands out against the {scatter_years} scatter."
        )
        + " That scatter does not describe an ordinary year for crashes. Between "
        f"{scatter_first} and {step_end} recorded urban injury crashes rose "
        f"{_fmt_pct(urban_step, 0)} while interurban ones fell {_fmt_pct(-interurban_step, 0)}, "
        "a step that a straight trend cannot follow, so the crash intervals are about "
        f"{crash_width:.0f} times as wide as pure-chance intervals and too wide to say whether "
        "the falls are larger than an ordinary year. DGT's yearbook does not split injury "
        "crashes by vehicle type, so they have no rate per licence holder or registered "
        "vehicle.</p>"
        "<p>Per resident, and for drivers per licence holder and occupants per registered "
        "vehicle, the rise in hospital admissions stays within ordinary variation. Admissions "
        "rose while the number of injury crashes fell, so more people were admitted to "
        "hospital per crash. That can reflect more serious crashes, more complete tracing of "
        "admissions back to crashes, or both. A change in tracing would move the series without "
        "any change on the road, and the tables cannot separate the two.</p>"
    )
    body += technical(
        "How ordinary variation was measured",
        "<p>Annual counts move around their trend more than pure chance would make them. Over "
        f"{scatter_years} the variance around the trend was "
        f"{_fmt_dec(dispersion['deaths_30d'])} times the pure-chance (Poisson) variance for "
        f"deaths, {_fmt_dec(dispersion['hospitalised_30d'])} times for hospital admissions and "
        f"{_fmt_dec(dispersion['crashes'], 0)} times for injury crashes. Each interval in the "
        "table is widened by the square root of its own count's factor. Each factor rests on "
        f"{WORDS[scatter_last - scatter_first + 1]} years and is itself uncertain: the 95% "
        f"interval of the factor for deaths runs from {_fmt_dec(deaths_scatter.dispersion_low)} "
        f"to {_fmt_dec(deaths_scatter.dispersion_high)}. The intervals therefore use Student's "
        f"t distribution with the trend fit's {WORDS[df_resid]} residual degrees of freedom "
        f"instead of the normal distribution, which widens them by {_fmt_pct(widening, 0)}. The "
        f'factor for deaths is the one <a href="long-run.html">Long-run trends</a> uses to '
        f"project the count from {fit_end + 1}.</p>",
    )

    body += (
        "<h2>The rates diverge because the population grew while fuel sales fell</h2>"
        f"<p>Between {base} and {last} the population grew {_fmt_pct(moved['residents'] - 1)}, "
        f"licence holders {_fmt_pct(moved['licence_holders'] - 1)} and the registered fleet "
        f"{_fmt_pct(moved['vehicles'] - 1)}, while road fuel sold fell "
        f"{_fmt_pct(1 - moved['road_fuel'])}. The same deaths therefore fall per resident, a "
        "measure of the burden on everyone living in Spain whether or not they travel, and rise "
        "per tonne of fuel, a measure against the traffic that fuel stands for. Licence holders "
        "and registered vehicles measure who or what could be on the road, without saying how "
        "much each is used, and each divides only the casualties it could contain: pedestrians "
        "and cyclists hold no licence for their journey and travel in no registered vehicle.</p>"
    )
    body += technical(
        "Which casualties each denominator divides",
        "<p>Licence holders divide only the deaths and admissions of drivers, and the fleet "
        "only those of occupants, of motorcycles, cars, vans, trucks and buses. Bicycles and "
        "personal mobility vehicles are left out of both because they need neither a licence "
        "nor a registration. Mopeds are left out because it is not established whether the "
        "fleet counts them, and the two numerators are kept to the same vehicles. The "
        "yearbook's category of other vehicles is left out because it held personal mobility "
        "vehicles until they were given their own category.</p>",
    )

    last_rows = efficiency[(efficiency.year == last) & (efficiency.outcome == "deaths_30d")]
    by_gain = last_rows.set_index("hypothetical_annual_gain")
    gains = sorted(float(g) for g in by_gain.index if float(g) > 0)
    if len(gains) != 2 or 0.0 not in by_gain.index:
        raise ValueError(f"trends page: the hypothetical drifts are no longer two: {gains}")
    km_first, km_last = int(crosscheck.index.min()), int(crosscheck.index.max())
    km_years = list(crosscheck.index)
    km_end = crosscheck.loc[km_last]
    totals = crosscheck.billion_km.dropna()
    _check(
        km_years == list(range(km_first, km_last + 1)) and len(km_years) > 2,
        "DGT's kilometre series runs over consecutive years",
    )
    _check(
        list(totals.index) == [km_first, km_last],
        "the repository holds the fleet, and so total kilometres, for the first and last years",
    )
    _check(
        float(km_end.car_mean_km_ratio) < 1
        and float(km_end.billion_km_ratio) < 1
        and float(km_end.road_fuel_tonnes_ratio) > 1,
        "over DGT's kilometre series, kilometres fell while road fuel sold rose",
    )
    per_km = float(km_end.deaths_per_bn_km / crosscheck.loc[km_first, "deaths_per_bn_km"])
    per_tonne = float(km_end.deaths_per_mt_fuel / crosscheck.loc[km_first, "deaths_per_mt_fuel"])
    _check(per_km > per_tonne > 1, "deaths per kilometre rose more than deaths per tonne")
    _check(
        km_first > base,
        "DGT's kilometre series starts after the base year",
    )
    _check(
        vehicles.KM_YEAR == km_first and driver_risk.KM_YEAR == km_last,
        "vehicle types use the first year of the kilometre series and driver age the last",
    )
    body += (
        '<h2 id="road-fuel">Road fuel stands in for kilometres driven, which no source counts '
        "on all roads</h2>"
        "<p>No Spanish source counts vehicle-kilometres on all roads every year, and road fuel "
        "sold stands in for them. The kilometres a tonne represents can change with fuel "
        "economy, electric driving, the mix of freight and private travel, and fuel bought in "
        "Spain but burnt elsewhere, and no available series measures that drift on all roads "
        f"since {base}. The change per tonne of fuel therefore cannot be converted into a "
        "change per kilometre. A hypothetical case shows how much depends on it: had kilometres "
        f"per tonne grown {_fmt_pct(gains[0], 0)} a year since {base}, deaths per kilometre "
        f"would show {_rise_or_fall(float(by_gain.loc[gains[0], 'ratio_to_base']))} where deaths "
        f"per tonne of fuel show {_rise_or_fall(float(by_gain.loc[0.0, 'ratio_to_base']))}; at "
        f"{_fmt_pct(gains[1], 0)} a year, "
        f"{_rise_or_fall(float(by_gain.loc[gains[1], 'ratio_to_base']))}. These growth rates are "
        "illustrative assumptions. The same drift bears on how far deaths per tonne of fuel lie "
        f"above the pre-pandemic trend ({recent_link}). On interurban roads the Ministerio de "
        'Transportes measures the kilometres, and <a href="long-run.html#interurban">Long-run '
        "trends</a> sets deaths per measured kilometre against their trend.</p>"
        f"<p>DGT's kilometre release of {km_last} gives the mean distance driven per vehicle "
        f"for {_join([str(y) for y in km_years])} as one series, estimated from roadworthiness "
        f"inspections, and its {km_first} values are those of DGT's {km_first} release. By "
        f"those estimates a car was driven {_fmt_int(crosscheck.loc[km_first, 'car_mean_km'])} "
        f"km on average in {km_first} and {_fmt_int(km_end.car_mean_km)} km in {km_last}, and "
        f"all vehicles together drove {_size(float(km_end.billion_km_ratio))} fewer kilometres "
        f"in {km_last} than in {km_first}, while road "
        f"fuel sold rose {_size(float(km_end.road_fuel_tonnes_ratio))}. Over those years "
        f"deaths per kilometre by DGT's estimate rose {_size(per_km)} and deaths per tonne of "
        f"fuel {_size(per_tonne)}. The series starts in {km_first}, so it cannot be set against "
        f"{base} or the long run, and fuel remains the denominator on this page. The "
        f'rates per kilometre on the <a href="vehicles.html">vehicles page</a> use its '
        f'{km_first} estimates, and those on the <a href="drivers.html">drivers page</a> its '
        f"{km_last} estimates.</p>"
    )
    body += limitation(
        "The denominators are national totals that weight every resident, licence, vehicle and "
        "tonne of fuel alike. The casualties include visitors, foreign and unlicensed drivers "
        "and the occupants of foreign-registered vehicles, whom no denominator counts. The "
        "intervals allow for the year-to-year variation of the casualty "
        "counts, and for the uncertainty of that variation, but treat every denominator as "
        "exact."
    )
    body += downloads(
        [
            ("risk_index", "every outcome, denominator and year"),
            ("risk_annual_panel", f"annual outcomes and denominators since {panel_first}"),
            ("risk_dispersion", "the year-to-year scatter of each count"),
            ("risk_fuel_efficiency", "the per-fuel change under hypothetical drifts"),
            ("risk_km_crosscheck", "DGT kilometre estimates beside road fuel"),
        ],
        method=("data.html#rates", "rates, denominators and intervals"),
    )
    return render_page(
        "trends",
        f"Road deaths and injuries in {last} against {base}",
        f"Deaths, hospital admissions and injury crashes in Spain in {last} compared with "
        f"{base}, as counts and as rates per resident, licence holder, registered vehicle and "
        "tonne of road fuel sold.",
        body,
    )
