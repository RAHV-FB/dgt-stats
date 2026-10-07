"""The overview: the findings, what connects them, and what the site does not claim.

Every number is read from a committed result table, and every qualitative sentence (which
comparisons stay within an ordinary year, where an excess sits) is guarded by a check that stops
the build when the tables stop supporting it.
"""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import driver_risk, forecast, risk_trends, vehicles
from dgt_stats.site.components import (
    _change,
    _fmt_int,
    _fmt_pct,
    _join,
    _signed_pct,
    _times,
    figure,
    finding,
    key_figures,
    read_table,
    render_page,
    table,
)
from dgt_stats.site.numbers import (
    _age_numbers,
    _factor_numbers,
    _long_run_numbers,
    _risk_numbers,
    _season_numbers,
    _sex_numbers,
    _speed_numbers,
    _window,
)


def _within(row: pd.Series) -> bool:
    """A 2019-to-latest ratio inside its ordinary-year interval."""
    return float(row.ratio_low_yty) <= 1 <= float(row.ratio_high_yty)


def _range(low: float, high: float) -> str:
    return f"{float(low):.2f}–{float(high):.2f}×"


def page_index(captions: dict[str, str]) -> str:
    risk = _risk_numbers()
    latest, last, base = risk["latest"], risk["last"], risk["base"]
    long_run = _long_run_numbers()
    projected = long_run["projected"]
    season = _season_numbers()
    effects = season["effects"]
    sex = _sex_numbers()
    age = _age_numbers()
    speed = _speed_numbers()
    factor = _factor_numbers()
    summary = read_table("q6_summary_2022").set_index("group")
    truck, car = summary.loc["heavy_truck"], summary.loc["car"]
    split = read_table("risk_frequency_severity").set_index("year")
    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_last = int(km_check.loc["per_km"].index.max())
    coverage = read_table("longrun_km_coverage")
    validation = read_table("forecast_validation").set_index(["outcome", "set", "method"])
    detect = read_table("forecast_detectability").set_index(["outcome", "horizon"])

    # 2019 to the latest year: deaths under every denominator, and admissions as a count.
    deaths = {key: latest.loc[("deaths_30d", key)] for key in latest.loc["deaths_30d"].index}
    hosp_count = latest.loc[("hospitalised_30d", "count")]
    # The long run: the count and deaths per tonne of road fuel against their projected trends.
    count_rows = projected.loc["count"]
    fuel_rows = projected.loc["road_fuel"]
    dip, fit_end = risk_trends.PANDEMIC_YEARS[0], risk_trends.BASE_YEAR
    count_2020, fuel_2020 = count_rows.loc[dip], fuel_rows.loc[dip]
    back_in = [
        int(y) for y in count_rows.index if y > dip and not count_rows.loc[y].outside_interval
    ]
    fuel_above = [int(y) for y in fuel_rows.index if y > dip and fuel_rows.loc[y].outside_interval]
    km_last_row = km_check.loc[("per_km", km_last)]
    km_low = float(km_last_row.observed) / float(km_last_row.high) - 1
    km_high = float(km_last_row.observed) / float(km_last_row.low) - 1
    km_segment = int(km_last_row.last_segment_start)
    # Seasons: per tonne of road fuel, the only monthly denominator for all-road deaths.
    july_raw, august_raw = effects.loc[("none", 7)], effects.loc[("none", 8)]
    july_fuel = effects.loc[("road_fuel_tonnes", 7)]
    august_fuel = effects.loc[("road_fuel_tonnes", 8)]
    season_first = int(effects.first_year.min())
    april = season["lockdown"].loc[4]
    # Age and sex.
    ratios_sex = sex["ratios"]
    men_involved = ratios_sex.loc[("car", "18+", "involved_per_1000_licences")]
    men_fatality = ratios_sex.loc[("car", "18+", "deaths_per_1000_involved")]
    men_killed = ratios_sex.loc[("car", "18+", "deaths_per_million_licences")]
    fatality_75 = age["ratios"].loc[("deaths_per_1000_involved", "75+")]
    owner = age["owner"]
    killed_75 = _range(
        owner.loc["75+", "deaths_per_bn_km_range_low"],
        owner.loc["75+", "deaths_per_bn_km_range_high"],
    )
    involved_young = _range(
        owner.loc["18-34", "involved_per_bn_km_range_low"],
        owner.loc["18-34", "involved_per_bn_km_range_high"],
    )
    # Vehicles, speed, factors.
    adjusted = speed["pooled"].loc["adjusted"]
    per_vehicle = float(
        truck.fatal_involvement_per_100k_vehicles / car.fatal_involvement_per_100k_vehicles
    )
    per_km = float(truck.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
    truck_occupants = float(truck.occupant_deaths_per_fatal_involvement)
    windows, changes = factor["windows"], factor["changes"]
    alcohol = _window(windows, "interurban", "Alcohol", 2014)
    speed_share = _window(windows, "all", "Inappropriate speed", 2014)
    urban_distraction = changes[
        (changes.zone == "urban") & (changes.factor == "Distraction or inattention") & changes.jump
    ].sort_values("to_year")
    # The forecast: its error on years it had not seen, and the change a year of counts shows.
    chosen = forecast.CHOSEN

    def rmse(kind: str, method: str) -> float:
        return float(validation.loc[("deaths_all", kind, method), "rmse"])

    one_year = detect.loc[("deaths_all", 1)]
    rise = forecast.minimum_detectable_rise(float(one_year.expected), float(one_year.tau))
    # The split of deaths per tonne of road fuel into crashes per tonne and deaths per crash.
    first, final = int(split.index.min()), int(split.index.max())
    severity = float(split.loc[final, "severity_index"]) / 100 - 1
    frequency = float(split.loc[final, "frequency_index"]) / 100 - 1
    per_fuel = float(split.loc[final, "deaths_per_fuel_index"]) / 100 - 1

    checks = {
        "the count and the rate per resident move in opposite directions": (
            float(deaths["count"].ratio_to_base) - 1
        )
        * (float(deaths["residents"].ratio_to_base) - 1)
        < 0,
        "no denominator shows a change in deaths beyond an ordinary year": all(
            _within(row) for row in deaths.values()
        ),
        "admissions rose beyond an ordinary year as a count": float(hosp_count.ratio_low_yty) > 1,
        "the 2020 count fell below its interval": bool(count_2020.outside_interval)
        and float(count_2020.ratio) < 1,
        "the count is back inside its interval every year from the first one after 2020": (
            bool(back_in) and back_in == [int(y) for y in count_rows.index if y >= back_in[0]]
        ),
        "deaths per tonne of road fuel stayed inside the interval in 2020": not bool(
            fuel_2020.outside_interval
        ),
        "deaths per tonne of road fuel are above the interval in the last years": bool(fuel_above)
        and all(float(fuel_rows.loc[y].ratio) > 1 for y in fuel_above),
        "per measured interurban km the last year is inside its interval": not bool(
            km_last_row.outside_interval
        ),
        "July and August stay above the average month per tonne of road fuel": all(
            float(row.low) > 1 for row in (july_fuel, august_fuel)
        ),
        "the summer excess is smaller per tonne of road fuel than as a count": (
            float(july_fuel.rate_ratio) < float(july_raw.rate_ratio)
            and float(august_fuel.rate_ratio) < float(august_raw.rate_ratio)
        ),
        "deaths fell more than road fuel in April 2020": float(april.deaths_change)
        < float(april.road_fuel_tonnes_change)
        < 0,
        "the per-km ranges are above 1 at both ends": all(
            float(owner.loc[band, f"{measure}_range_low"]) > 1
            for band, measure in (("75+", "deaths_per_bn_km"), ("18-34", "involved_per_bn_km"))
        ),
        "a heavy truck is further above a car per vehicle than per km": per_vehicle > per_km > 1,
        "urban distraction has a jump up and a later one down": len(urban_distraction) == 2
        and float(urban_distraction.share_ratio.iloc[0])
        > 1
        > float(urban_distraction.share_ratio.iloc[-1]),
        "the forecast beats last year's count in the lockdowns": rmse("pandemic", chosen)
        < rmse("pandemic", "last_year"),
        "deaths per crash fell more than crashes per tonne of fuel": severity < frequency,
        "the forecast's detection probability is four in five": forecast.POWER == 0.8,
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"overview: the tables no longer support: {failed}")

    body = key_figures(
        [
            (
                f"How deadly a crash is, {first}–{final}",
                _signed_pct(severity),
                "deaths per injury crash; injury crashes per tonne of road fuel: "
                f"{_signed_pct(frequency)}",
            ),
            (
                "Killed per driver involved, 75+",
                _times(float(fatality_75.ratio)),
                f"car drivers against 35–54, {driver_risk.KM_YEAR}; needs no kilometres",
            ),
            (
                "Deaths per crash with speed",
                _times(float(adjusted.rate_ratio)),
                "recorded speed against other crashes on the same kind of road",
            ),
            (
                f"Interurban deaths per measured km, {km_last}",
                _change(float(km_last_row.ratio), 0),
                f"against the {km_segment}–{fit_end} trend, inside its interval",
            ),
        ]
    )

    rows = _split_rows()
    by_place = {
        "deadliness": [row["short"] for row in rows if row["where"] == "deadliness"],
        "crashes": [row["short"] for row in rows if row["where"].startswith("crashes")],
    }
    body += (
        '<p class="answer">A count of crashes or deaths says how many. It does not say how '
        "dangerous the roads were, because it moves with how much people drove, who was driving "
        "and in what. This site divides the same DGT counts by residents, licence holders, "
        "vehicles, kilometres and road fuel, each paired with the casualties it can contain, and "
        "asks what changes. On several questions below the answer changes size, and on some it "
        "changes sign. Each answer can then be split in two, how often crashes happen and how "
        "deadly they are, and the split shows where the extra deaths are recorded: for "
        f"{_join(by_place['deadliness'])} it is how deadly the crash is; for "
        f"{_join(by_place['crashes'])} it is mostly how often crashes happen. The last page "
        "asks how large a change in deaths a year of counts can show at all.</p>"
    )

    findings = [
        (
            "trends.html",
            f"Since {base}, no denominator shows a change in deaths beyond an ordinary year; "
            "recorded hospital admissions rose",
            f"Deaths in {last} were {_change(float(deaths['count'].ratio_to_base))} on {base} as "
            f"a count, {_change(float(deaths['residents'].ratio_to_base))} per resident and "
            f"{_change(float(deaths['road_fuel'].ratio_to_base))} per tonne of road fuel; driver "
            f"deaths per licence holder moved "
            f"{_change(float(deaths['licence_holders'].ratio_to_base))} and occupant deaths per "
            f"registered vehicle {_change(float(deaths['vehicles'].ratio_to_base))}, all within "
            "an ordinary year's variation. People admitted to hospital rose "
            f"{_change(float(hosp_count.ratio_to_base))} as a count, beyond it.",
            "Annual DGT totals over INE residents and CORES road fuel, driver deaths over the "
            "driver census and occupant deaths over the registered fleet, indexed to "
            f"{base}, with intervals that allow for the yearly scatter of each count.",
        ),
        (
            "long-run.html",
            f"The {dip} dip was in the count, not per tonne of fuel; per measured interurban km "
            f"{km_last} was on trend",
            f"As a count, {dip} deaths were {_change(float(count_2020.ratio), 0)} against the "
            f"pre-pandemic trend, below its interval, and inside it from {back_in[0]}. Deaths "
            f"per tonne of road fuel stayed inside the trend's interval in {dip} "
            f"({_times(float(fuel_2020.ratio))}); in {_join([str(y) for y in fuel_above])} they "
            "are above it ("
            + _join([_change(float(fuel_rows.loc[y].ratio), 0) for y in fuel_above])
            + "), but fuel sold is not measured against kilometres on all roads. On interurban "
            f"roads, deaths per measured kilometre in {km_last} were "
            f"{_change(float(km_last_row.ratio), 0)} on trend, inside its interval "
            f"({_signed_pct(km_low)} to {_signed_pct(km_high)}); "
            f"{_fmt_pct(float(coverage.outside_share.min()))} to "
            f"{_fmt_pct(float(coverage.outside_share.max()))} of interurban deaths in "
            f"{int(coverage.year.min())}–{int(coverage.year.max())} are on municipal or other "
            "roads the kilometres leave out.",
            "Joinpoint quasi-Poisson trends fitted to "
            f"{int(long_run['series'].year.min())}–{fit_end} "
            "and projected, re-run on the Ministerio de Transportes' measured interurban "
            "vehicle-kilometres.",
        ),
        (
            "seasons.html",
            "Per tonne of road fuel the summer excess shrinks but does not disappear",
            f"Raw deaths in July are {_times(float(july_raw.rate_ratio))} and in August "
            f"{_times(float(august_raw.rate_ratio))} the average month. Per tonne of road fuel "
            f"sold they are {_times(float(july_fuel.rate_ratio))} and "
            f"{_times(float(august_fuel.rate_ratio))}, still above the average month. In the "
            f"April 2020 lockdown deaths fell {_fmt_pct(-float(april.deaths_change), 0)} and "
            f"road fuel sold {_fmt_pct(-float(april.road_fuel_tonnes_change), 0)}; these series "
            "cannot say whether each kilometre became more or less dangerous.",
            f"Monthly deaths since {season_first} against monthly road fuel, in quasi-Poisson "
            "models with year and month effects; petrol and toll-motorway traffic are shown "
            "beside deaths as traffic indices only.",
        ),
        (
            "drivers.html",
            "Older car drivers in a crash are killed more often; per owner-age km young drivers "
            "are in more crashes",
            "Car drivers aged 75 and over in an injury crash are killed "
            f"{_times(float(fatality_75.ratio))} as often as those aged 35 to 54, a ratio that "
            "needs no kilometres. Per km of cars registered to owners of each age they are "
            f"killed {killed_75} as often, and drivers aged 18 to 34 are involved in injury "
            f"crashes {involved_young} as often. Men, per licence holder: "
            f"{_times(float(men_killed.ratio))}, from {_times(float(men_involved.ratio))} the "
            f"crashes × {_times(float(men_fatality.ratio))} the deaths per crash.",
            f"DGT driver tables over the driver census, and DGT's {driver_risk.KM_YEAR} "
            "kilometres by the registered owner's age, as ranges (transfer scenario to "
            "published).",
        ),
        (
            "vehicles.html",
            f"A heavy truck is {per_vehicle:.1f} times a car per vehicle, {per_km:.1f} times "
            "per kilometre: the divisor decides",
            f"Per circulating vehicle a heavy truck is in a fatal crash {per_vehicle:.1f} times as "
            f"often as a car. Per kilometre driven it is {per_km:.1f} times. For every fatal crash "
            f"a truck is in, {truck_occupants:.2f} of its own occupants die, so in at least "
            f"{_fmt_pct(1 - truck_occupants, 0)} of those crashes nobody in the truck was killed.",
            f"DGT's {vehicles.KM_YEAR} kilometre estimates divided into the same year's "
            "involvement counts, "
            "with exact Poisson intervals.",
        ),
        (
            "speed.html",
            f"Where speed is recorded, a crash is {_times(float(adjusted.rate_ratio))} as likely "
            "to kill on the same kind of road",
            "Injury crashes in which the police recorded inappropriate speed kill "
            f"{_times(float(adjusted.crude_ratio))} as many people per crash as the rest, and "
            f"{_times(float(adjusted.rate_ratio))} once the comparison is made on the same kind "
            "of road in the same year. That is an association: the record is written after the "
            "fact, and is likelier to be written when someone has died.",
            "DGT's speed-factor report against totals from the microdata for the same provinces, "
            "which reproduce the report's own zone totals exactly.",
        ),
        (
            "factors.html",
            "Recorded alcohol is rising on interurban roads; distraction cannot be trended in "
            "towns",
            "Recorded alcohol went from "
            f"{_fmt_pct(float(alcohol.share_first))} to {_fmt_pct(float(alcohol.share_last))} of "
            f"interurban injury crashes between {int(alcohol.first_year)} and "
            f"{int(alcohol.last_year)}, and inappropriate speed from "
            f"{_fmt_pct(float(speed_share.share_first))} to "
            f"{_fmt_pct(float(speed_share.share_last))} of all of them, both on a consistent "
            "record. Urban distraction's share changes by "
            + _join(
                [
                    f"{_signed_pct(float(row.share_ratio) - 1)} in {int(row.to_year)}"
                    for row in urban_distraction.itertuples()
                ]
            )
            + ", single-year changes the break rule flags, and drugs are too few to compare.",
            "DGT's concurrent-factor tables, with a recording-break rule applied to every "
            "year-to-year change before any trend is read.",
        ),
        (
            "forecast.html",
            "One year of deaths shows a change reliably only from about "
            f"{_fmt_pct(float(one_year.mde), 0)} down or {_fmt_pct(rise, 0)} up",
            "A Poisson model of monthly deaths, fitted only to DGT's series and CORES road fuel, "
            "forecasts a year's deaths with an error of "
            f"{_fmt_pct(rmse('holdout', chosen))} in years it had not seen and "
            f"{_fmt_pct(rmse('pandemic', chosen))} in the lockdown years, when repeating last "
            f"year's count was off by {_fmt_pct(rmse('pandemic', 'last_year'))}. Against that "
            "forecast one year of deaths on all roads shows a fall of "
            f"{_fmt_pct(float(one_year.mde), 0)} ({_fmt_int(one_year.mde_deaths_per_year)} "
            f"deaths) or a rise of {_fmt_pct(rise, 0)} four times in five; summing five years "
            "does not help, because the trend drifts from any forecast.",
            f"Rolling forecasts, chosen on {min(forecast.SELECTION_YEARS)}–"
            f"{max(forecast.SELECTION_YEARS)} and tested on held-back years, against naive "
            "forecasts and gradient-boosted trees.",
        ),
    ]
    body += "".join(
        finding(index, href, heading, text, method)
        for index, (href, heading, text, method) in enumerate(findings, start=1)
    )

    body += "<h2>What connects them</h2>"
    body += (
        "<p>Every comparison on the site can be split the same way: deaths for a given exposure "
        "are crashes for that exposure times deaths per crash. Set side by side, the splits show "
        "that the extra deaths do not all come from the same place.</p>"
    )
    body += table(_split_table(rows), _SPLIT_CAPTION)
    body += (
        f"<p>For {_join(by_place['deadliness'])} the excess is in how deadly a crash is; for "
        f"{_join(by_place['crashes'])} it is mostly in how often crashes happen. Ages are "
        "compared per km of cars registered to owners of each age, so their crash cells are "
        "ranges, from a scenario that moves young drivers' kilometres out of the 35–54 band to "
        "the published ratio. The long run fell more through severity than through frequency: "
        f"between {first} and {final} deaths per tonne of road fuel fell "
        f"{_fmt_pct(-per_fuel, 0)}, injury crashes per tonne {_fmt_pct(-frequency, 0)} and "
        f"deaths per injury crash {_fmt_pct(-severity, 0)}, a split that depends on how "
        "completely slight injuries are recorded, though their product does not.</p>"
    )
    body += figure(
        "l3_frequency_severity",
        "Deaths per tonne of road fuel split into how often crashes happen and how deadly they are",
        captions,
    )

    body += "<h2>What this site does not claim</h2>"
    body += (
        "<p>It attributes no cause from Spanish data. DGT's national microdata have one row per "
        "crash and no driver, vehicle or person records, so every factor here is an "
        "association, and a policy or campaign effect is never read off a time series. Every "
        "result comes from the rows of files in the repository: no observation, coefficient or "
        "relative risk is taken from a study made elsewhere, and the forecasting model is "
        "fitted only to Spain's monthly deaths and road fuel. Two analyses built earlier in the "
        "project are kept as supporting material because they are careful but outside this "
        'question: a <a href="severity.html">model of crash severity</a> and a '
        '<a href="policy.html">test of the 2006 points licence</a> whose headline did not '
        "survive its own falsification tests. Road design and municipal hotspots are not "
        "analysed: DGT's national files carry no road geometry, traffic volume or "
        "coordinates.</p>"
    )
    body += "<h2>How to read the numbers</h2>"
    body += (
        "<p>Counts are DGT's consolidated figures. An injury crash is one with at least one "
        "person killed or injured, and deaths are counted within 30 days. Every rate names its "
        "denominator, because the denominator is usually where the answer comes from. Sources, "
        "definitions, the reconciliation checks and the assumptions tested are on the "
        '<a href="data.html">data page</a>.</p>'
    )
    return render_page(
        "index",
        "Road safety in Spain",
        "What changes when you stop counting crashes and start measuring road risk: seven "
        "questions answered from DGT data, each with the denominator that decides it, and a "
        "model of monthly deaths that says how large a change a year of counts can show.",
        body,
    )


_SPLIT_CAPTION = (
    "Where the extra deaths come from: each comparison split into how often crashes happen for "
    "the exposure and how deadly a crash is, which multiply to the deaths for the exposure; a "
    "range runs from the transfer scenario to the published ratio. Drivers: car drivers in "
    "injury crashes and killed (the driver only); vehicles: vehicles in injury and in fatal "
    "crashes; roads: interurban injury crashes and deaths on State, regional and provincial "
    "roads, the networks whose kilometres the Ministry measures (crashes on those roads "
    "recorded in the urban zone are in neither class); years: injury crashes and deaths"
)


def _where_both(crashes: tuple[float, float], deadly: float) -> str:
    """Where the excess sits, said only when both ends of a range agree."""
    places = {_where(value, deadly) for value in crashes}
    return places.pop() if len(places) == 1 else "depends on the kilometres"


def _split_rows() -> list[dict[str, object]]:
    """Every comparison the site makes, as crashes per exposure times deaths per crash."""
    age = _age_numbers()
    ratios, owner = age["ratios"], age["owner"]
    sex = _sex_numbers()["ratios"]
    summary = read_table("q6_summary_2022").set_index("group")
    risk = read_table("road_class_risk")
    risk_year = int(risk.year.max())
    risk = risk[risk.year == risk_year].set_index("road_class")
    split = read_table("risk_frequency_severity").set_index("year")
    first, final = int(split.index.min()), int(split.index.max())
    owner_km = "km of cars of owners that age"

    def vehicle(group: str) -> tuple[float, float]:
        row, car = summary.loc[group], summary.loc["car"]
        crashes = float(row.injury_involvement_per_bn_km / car.injury_involvement_per_bn_km)
        deaths = float(row.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
        return crashes, deaths / crashes

    def band(name: str) -> tuple[tuple[float, float], float]:
        low = float(owner.loc[name, "involved_per_bn_km_range_low"])
        high = float(owner.loc[name, "involved_per_bn_km_range_high"])
        return (low, high), float(ratios.loc[("deaths_per_1000_involved", name), "ratio"])

    conventional, motorway = risk.loc["conventional"], risk.loc["motorway"]
    road_crashes = float(conventional.injury_crashes_per_bn_km / motorway.injury_crashes_per_bn_km)
    road_deadly = float(
        (conventional.deaths_per_bn_km / conventional.injury_crashes_per_bn_km)
        / (motorway.deaths_per_bn_km / motorway.injury_crashes_per_bn_km)
    )
    rows: list[dict[str, object]] = []
    km_year, sex_years = driver_risk.KM_YEAR, driver_risk.SEX_POOL_YEARS
    for label, short, name in (
        (f"Car drivers 75+ against 35–54, {km_year}", "older drivers", "75+"),
        (f"Car drivers 18–34 against 35–54, {km_year}", "young drivers", "18-34"),
    ):
        crashes, deadly = band(name)
        rows.append(
            {
                "label": label,
                "short": short,
                "per": owner_km,
                "crashes": crashes,
                "deadly": deadly,
                "where": _where_both(crashes, deadly),
            }
        )
    point_rows = [
        (
            f"Male against female car drivers, {min(sex_years)}–{max(sex_years)}",
            "men",
            "licence holder",
            float(sex.loc[("car", "18+", "involved_per_1000_licences"), "ratio"]),
            float(sex.loc[("car", "18+", "deaths_per_1000_involved"), "ratio"]),
        ),
        (
            f"Heavy trucks against cars, {vehicles.KM_YEAR}",
            "heavy trucks",
            "km driven",
            *vehicle("heavy_truck"),
        ),
        (
            f"Motorcycles against cars, {vehicles.KM_YEAR}",
            "motorcycles",
            "km driven",
            *vehicle("motorcycle"),
        ),
        (
            f"Conventional roads against autopistas and autovías, {risk_year}",
            "conventional roads",
            "km measured",
            road_crashes,
            road_deadly,
        ),
    ]
    for label, short, per, crashes, deadly in point_rows:
        rows.append(
            {
                "label": label,
                "short": short,
                "per": per,
                "crashes": (crashes, crashes),
                "deadly": deadly,
                "where": _where(crashes, deadly),
            }
        )
    rows.append(
        {
            "label": f"All roads, {final} against {first}",
            "short": "",
            "per": "tonne of road fuel",
            "crashes": (float(split.loc[final, "frequency_index"]) / 100,) * 2,
            "deadly": float(split.loc[final, "severity_index"]) / 100,
            "where": _where(
                float(split.loc[final, "frequency_index"]) / 100,
                float(split.loc[final, "severity_index"]) / 100,
            ),
        }
    )
    return rows


def _split_table(rows: list[dict[str, object]] | None = None) -> pd.DataFrame:
    rows = rows if rows is not None else _split_rows()
    speed = _speed_numbers()["pooled"].loc["adjusted"]
    out = []
    for row in rows:
        low, high = row["crashes"]  # type: ignore[misc]
        deadly = float(row["deadly"])  # type: ignore[arg-type]

        def cell(a: float, b: float) -> str:
            return _times(a) if math.isclose(a, b) else _range(a, b)

        out.append(
            {
                "Comparison": row["label"],
                "Per": row["per"],
                "How often crashes happen": cell(low, high),
                "How deadly a crash is": _times(deadly),
                "Deaths": cell(low * deadly, high * deadly),
                "Where the excess sits": row["where"],
            }
        )
    out.append(
        {
            "Comparison": "Crashes with speed recorded against others, same road and year",
            "Per": "crash",
            "How often crashes happen": "",
            "How deadly a crash is": _times(float(speed.rate_ratio)),
            "Deaths": "",
            "Where the excess sits": "deadliness",
        }
    )
    return pd.DataFrame(out)


def _where(crashes: float, deadly: float) -> str:
    """Which factor carries a comparison: the one further from 1 on the log scale."""
    a, b = math.log(crashes), math.log(deadly)
    if a < 0 and b < 0:
        return "both fell, deadliness most" if b < a else "both fell, crashes most"
    if abs(b) > 2 * abs(a):
        return "deadliness"
    if abs(a) > 2 * abs(b):
        return "crashes"
    return "crashes more than deadliness" if abs(a) > abs(b) else "deadliness more than crashes"
