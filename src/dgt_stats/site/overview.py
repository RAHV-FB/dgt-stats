"""The overview: the study's principal results, read as one argument.

Every number is read from a committed result table, and every qualitative sentence (which changes
stay within ordinary year-to-year variation, where a group's excess of deaths arises, which models
beat their descriptive tables, how far the Catalonia severity model holds elsewhere) is guarded by
a check that stops the build when the tables stop supporting it.
"""

from __future__ import annotations

import math
import re

import pandas as pd

from dgt_stats import driver_risk, forecast, risk_trends, vehicles
from dgt_stats.microdata.ml import modelling
from dgt_stats.microdata.validation import decisions as decision_rules
from dgt_stats.site.components import (
    _change,
    _fmt_dec,
    _fmt_int,
    _fmt_pct,
    _join,
    _ordinal,
    _signed_pct,
    _times,
    read_table,
    render_page,
    summary,
    table,
)
from dgt_stats.site.numbers import (
    _age_numbers,
    _factor_numbers,
    _long_run_numbers,
    _policy_numbers,
    _risk_numbers,
    _season_numbers,
    _sex_numbers,
    _speed_numbers,
    _window,
)
from dgt_stats.site.regional_common import MODEL_NAMES, _check, _year_label

# The three models trained on the regional records, in the order the page discusses them.
REGIONAL_MODELS = (
    "catalonia_crash_severity",
    "barcelona_person_severity",
    "barcelona_crash_severity",
)
# The groupings of the descriptive tables each model was compared with, in words.
RULE_LABELS = {
    "D_SUBTIPUS_ACCIDENT x D_SUBZONA": "crash subtype and by urban or interurban zone",
    "person_role x associated_vehicle_group": "road-user role and vehicle group",
    "accident_type": "accident type",
}
_WORDS = {2: "two", 3: "three", 4: "four", 5: "five"}


def _require(section: str, checks: dict[str, bool]) -> None:
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"overview ({section}): the tables no longer support: {failed}")


def _within(row: pd.Series) -> bool:
    """A ratio of the latest year to the base year inside its ordinary-year interval."""
    return float(row.ratio_low_yty) <= 1 <= float(row.ratio_high_yty)


def _range(low: float, high: float) -> str:
    return f"{float(low):.2f}–{float(high):.2f}×"


def _interval(low: float, high: float) -> str:
    return f"{float(low):.2f}–{float(high):.2f}"


def _link(href: str, text: str) -> str:
    return f'<a href="{href}">{text}</a>'


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


# ----------------------------------------------------------------------------- the page
def page_index(captions: dict[str, str]) -> str:
    body = _introduction()
    body += _national()
    body += _frequency_and_severity()
    body += _regional_records()
    body += _validation()
    body += _further()
    national_years = read_table("longrun_series").year
    cat_years = read_table("cat_frequency").year
    bcn_year = _year_label(read_table("bcn_person_severity_share"))
    lead = (
        f"A statistical study of road deaths and injuries in Spain from "
        f"{int(national_years.min())} to {int(national_years.max())}, based on national DGT and "
        "INE statistics, the Servei Català de Trànsit's file of crashes with a death or serious "
        f"injury ({int(cat_years.min())}–{int(cat_years.max())}) and Barcelona's crash and "
        f"casualty records for {bcn_year}."
    )
    return render_page("index", "Road safety in Spain", lead, body)


def _introduction() -> str:
    """The guiding idea: a count against a rate, and a rate split into frequency and severity."""
    vehicle_rows = read_table("q6_summary_2022").set_index("group")
    truck, car = vehicle_rows.loc["heavy_truck"], vehicle_rows.loc["car"]
    per_vehicle = float(
        truck.fatal_involvement_per_100k_vehicles / car.fatal_involvement_per_100k_vehicles
    )
    per_km = float(truck.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
    split = read_table("risk_frequency_severity").set_index("year")
    first, final = int(split.index.min()), int(split.index.max())
    frequency = float(split.loc[final, "frequency_index"]) / 100
    severity = float(split.loc[final, "severity_index"]) / 100
    per_fuel = float(split.loc[final, "deaths_per_fuel_index"]) / 100
    _require(
        "introduction",
        {
            "a heavy truck is further above a car per vehicle than per km": per_vehicle
            > per_km
            > 1,
            "deaths per crash fell, and fell more than twice as far as crashes per tonne of fuel "
            "on the log scale": severity < frequency < 1
            and math.log(severity) < 2 * math.log(frequency),
        },
    )
    text = summary(
        "A count of road deaths says how many people died. Whether the roads have become safer "
        "depends on what the count is divided by. Deaths per resident measure the burden on a "
        "population. Licence holders, registered vehicles and kilometres driven measure "
        "exposure: who could be on the road and how much they drive, with road fuel sold "
        "standing in for kilometres where these are missing. Deaths per unit of exposure are in "
        "turn the product of two factors, how often crashes happen and how deadly a crash is "
        "once it has happened, and the two often point in different directions."
    )
    text += (
        "<p>Two results show the difference. Per vehicle on the road, a "
        f"heavy truck is in a fatal crash {per_vehicle:.1f}× as often as a car; per kilometre "
        f"driven, {per_km:.1f}× as often, because each truck is driven "
        f"{per_vehicle / per_km:.1f} times as far. Between {first} and {final}, deaths per "
        f"tonne of road fuel fell {_fmt_pct(1 - per_fuel, 0)}, mostly through fewer deaths per "
        f"injury crash (down {_fmt_pct(1 - severity, 0)}) and much less through fewer injury "
        f"crashes per tonne (down {_fmt_pct(1 - frequency, 0)}), although the split depends on "
        "how completely slight injuries are recorded "
        f"({_link('long-run.html', 'Long-run trends')}).</p>"
    )
    return text


# ----------------------------------------------------------------------------- national trends
def _national() -> str:
    risk = _risk_numbers()
    latest, last, base = risk["latest"], risk["last"], risk["base"]
    long_run = _long_run_numbers()
    projected = long_run["projected"]
    segments = long_run["segments"]
    effects = _season_numbers()["effects"]
    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_last = int(km_check.loc["per_km"].index.max())

    # The long run: where the count fell steeply, and where it stopped falling.
    count_segments = segments[segments.measure == "count"].sort_values("start")
    steep = count_segments.loc[count_segments.annual_change.idxmin()]
    flat = count_segments.iloc[-1]
    # Base year to the latest year: deaths under every denominator, and admissions as a count.
    deaths = {key: latest.loc[("deaths_30d", key)] for key in latest.loc["deaths_30d"].index}
    hosp_count = latest.loc[("hospitalised_30d", "count")]
    # The pandemic years: the count and deaths per tonne of road fuel against their trends.
    count_rows = projected.loc["count"]
    fuel_rows = projected.loc["road_fuel"]
    dip = risk_trends.PANDEMIC_YEARS[0]
    count_dip, fuel_dip = count_rows.loc[dip], fuel_rows.loc[dip]
    fuel_above = [int(y) for y in fuel_rows.index if y > dip and fuel_rows.loc[y].outside_interval]
    km_row = km_check.loc[("per_km", km_last)]
    km_ratio = float(km_row.ratio)
    km_low = float(km_row.observed) / float(km_row.high) - 1
    km_high = float(km_row.observed) / float(km_row.low) - 1
    # Seasons: per tonne of road fuel, the only monthly denominator for all-road deaths.
    july_raw, august_raw = effects.loc[("none", 7)], effects.loc[("none", 8)]
    july_fuel = effects.loc[("road_fuel_tonnes", 7)]
    august_fuel = effects.loc[("road_fuel_tonnes", 8)]

    _require(
        "national trends",
        {
            "the steepest segment of the count ends where the last one starts": int(steep.end)
            == int(flat.start)
            and int(steep.start) < int(flat.start),
            "the count fell in the steep segment": float(steep.high) < 0,
            "the last segment of the count shows no fall": float(flat.low) < 0 < float(flat.high),
            "the five denominators quoted are the ones in the table": set(deaths)
            == {"count", "residents", "licence_holders", "vehicles", "road_fuel"},
            "no denominator shows a change in deaths beyond ordinary year-to-year variation": all(
                _within(row) for row in deaths.values()
            ),
            "admissions rose beyond ordinary year-to-year variation as a count": float(
                hosp_count.ratio_low_yty
            )
            > 1,
            "the pandemic-year count fell below its interval": bool(count_dip.outside_interval)
            and float(count_dip.ratio) < 1,
            "deaths per tonne of road fuel stayed inside the interval in the pandemic year": not bool(
                fuel_dip.outside_interval
            ),
            "deaths per tonne of road fuel are above the interval in the last years": bool(
                fuel_above
            )
            and all(float(fuel_rows.loc[y].ratio) > 1 for y in fuel_above),
            "per measured interurban km the last year is inside its interval": not bool(
                km_row.outside_interval
            )
            and km_low < 0 < km_high,
            "July and August stay above the average month per tonne of road fuel": all(
                float(row.low) > 1 for row in (july_fuel, august_fuel)
            ),
            "the summer excess is smaller per tonne of road fuel than as a count": (
                float(july_fuel.rate_ratio) < float(july_raw.rate_ratio)
                and float(august_fuel.rate_ratio) < float(august_raw.rate_ratio)
            ),
        },
    )

    text = "<h2>National trends</h2>"
    text += (
        f"<p>Over the {_link('long-run.html', 'long run')}, road deaths in Spain fell most "
        f"steeply between {int(steep.start)} and {int(steep.end)}, by "
        f"{_fmt_pct(-float(steep.annual_change))} a year, and from {int(flat.start)} to "
        f"{int(flat.end)} they no longer fell. {_link('trends.html', f'Since {base}')} the "
        "change in deaths has stayed within ordinary year-to-year variation under every "
        "denominator: "
        f"by {last} it was "
        f"{_change(float(deaths['count'].ratio_to_base))} as a count, "
        f"{_change(float(deaths['residents'].ratio_to_base))} per resident, "
        f"{_change(float(deaths['road_fuel'].ratio_to_base))} per tonne of road fuel, "
        f"{_change(float(deaths['licence_holders'].ratio_to_base))} for driver deaths per "
        f"licence holder and {_change(float(deaths['vehicles'].ratio_to_base))} for occupant "
        "deaths per registered vehicle. Hospital admissions after a crash rose "
        f"{_fmt_pct(float(hosp_count.ratio_to_base) - 1)}, beyond that variation; the published "
        "tables cannot tell whether crashes became more serious or admissions were recorded "
        "more completely.</p>"
    )
    text += (
        f"<p>In {dip} the count of deaths fell {_fmt_pct(1 - float(count_dip.ratio), 0)} below "
        "its pre-pandemic trend, outside the trend's 95% prediction range, while deaths per "
        "tonne of road fuel stayed within theirs: over the year as a whole, deaths fell roughly "
        f"in line with fuel sales. In {_join([str(y) for y in fuel_above])} deaths per tonne of "
        "fuel were "
        + _join([_fmt_pct(float(fuel_rows.loc[y].ratio) - 1, 0) for y in fuel_above])
        + " above their trend, beyond its range, but fuel sold only "
        + _link("trends.html#road-fuel", "stands in for distance driven")
        + ". "
        "On interurban roads, where vehicle-kilometres are measured, "
        f"deaths per kilometre in {km_last} were {_fmt_pct(abs(km_ratio - 1), 0)} "
        f"{'above' if km_ratio > 1 else 'below'} their pre-pandemic trend, within its range "
        f"({_signed_pct(km_low)} to {_signed_pct(km_high)}).</p>"
    )
    text += (
        f"<p>Part of the {_link('seasons.html', 'summer peak')} follows fuel sales: July has "
        f"{_times(float(july_raw.rate_ratio))} the deaths of an average month, and "
        f"{_times(float(july_fuel.rate_ratio))} per tonne of road fuel.</p>"
    )
    return text


# ----------------------------------------------------------------------------- frequency, severity
def _frequency_and_severity() -> str:
    rows = _split_rows()
    by_key = {str(row["key"]): row for row in rows}
    age = _age_numbers()
    fatality_75 = age["ratios"].loc[("deaths_per_1000_involved", "75+")]
    owner = age["owner"]
    vehicle_rows = read_table("q6_summary_2022").set_index("group")
    truck_occupants = float(
        vehicle_rows.loc["heavy_truck", "occupant_deaths_per_fatal_involvement"]
    )
    adjusted = _speed_numbers()["pooled"].loc["adjusted"]
    factor = _factor_numbers()
    windows = factor["windows"]
    report_first, report_last = int(windows.first_year.min()), int(windows.last_year.max())
    alcohol = _window(windows, "interurban", "Alcohol", report_first)
    speed_share = _window(windows, "all", "Inappropriate speed", report_first)
    urban_distraction = windows[
        (windows.zone == "urban") & (windows.factor == "Distraction or inattention")
    ]
    drugs = windows[windows.factor == "Drugs"]
    named = [row for row in rows if row["short"]]
    pure_deadly = [str(row["short"]) for row in named if row["where"] == "deadliness"]
    pure_crashes = [str(row["short"]) for row in named if row["where"] == "crashes"]
    both = [row for row in named if str(row["where"]).endswith("more than crashes")] + [
        row for row in named if str(row["where"]).endswith("more than deadliness")
    ]

    def crashes(key: str) -> float:
        return float(by_key[key]["crashes"][0])  # type: ignore[index]

    _require(
        "frequency and severity",
        {
            "the per-km ranges are above 1 at both ends": all(
                float(owner.loc[band, f"{measure}_range_low"]) > 1
                for band, measure in (("75+", "deaths_per_bn_km"), ("18-34", "involved_per_bn_km"))
            ),
            "every named comparison shows an excess of deaths": all(
                low * float(row["deadly"]) > 1  # type: ignore[arg-type]
                for row in named
                for low in row["crashes"]  # type: ignore[attr-defined]
            ),
            "groups sit on each side of the split": bool(pure_deadly) and bool(pure_crashes),
            "most people killed in a heavy truck's fatal crashes are outside it": truck_occupants
            < 0.5,
            "conventional roads have more crashes per km and, less so, deadlier ones": crashes(
                "conventional"
            )
            > float(by_key["conventional"]["deadly"])  # type: ignore[arg-type]
            > 1,
            "deaths per crash are higher where speed is recorded, on the same kind of road": float(
                adjusted.ratio_low
            )
            > 1,
            "recorded alcohol rose on interurban roads": float(alcohol.share_last)
            > float(alcohol.share_first),
            "recorded inappropriate speed fell": float(speed_share.share_last)
            < float(speed_share.share_first),
            "both series run without a break over the whole report": all(
                int(w.first_year) == report_first and int(w.last_year) == report_last
                for w in (alcohol, speed_share)
            ),
            "no comparable run of urban distraction covers the whole report": not (
                (urban_distraction.first_year == report_first)
                & (urban_distraction.last_year == report_last)
            ).any(),
            "no two years of drug-related crashes can be compared": int(drugs.n_years.max()) == 1,
        },
    )

    text = "<h2>Frequency and severity across drivers, vehicles and roads</h2>"
    text += (
        "<p>The split into crashes per unit of exposure and deaths per crash shows whether a "
        "group's excess of deaths comes from crashing more often or from deadlier crashes. "
        f"For {_join(pure_deadly)} the excess lies in how deadly a crash is; for "
        f"{_join(pure_crashes)} it lies in how often crashes happen."
    )
    if both:
        text += (
            f" {_capital(_join([str(row['short']) for row in both]))} differ on both counts, "
            + _join(
                [
                    f"{row['short']} mainly in "
                    + (
                        "how deadly a crash is"
                        if str(row["where"]).startswith("deadliness")
                        else "how often crashes happen"
                    )
                    for row in both
                ]
            )
            + "."
        )
    text += "</p>"
    text += table(_split_table(rows), _SPLIT_CAPTION)
    text += (
        "<p>Car drivers aged 75 and over who are in an injury crash are killed "
        f"{_times(float(fatality_75.ratio))} ({_interval(fatality_75.low, fatality_75.high)}) "
        "as often as those aged 35 to 54. Kilometres by age exist only for cars registered to "
        "owners of each age, so the per-kilometre ratios for "
        f"{_link('drivers.html', 'drivers')} are given as ranges; men and women are compared per "
        "licence holder, since no source gives kilometres by sex.</p>"
    )
    text += (
        f"<p>The rows for {_link('vehicles.html', 'vehicle types')} count vehicles in fatal "
        "crashes, whoever died. In the fatal crashes a heavy truck is in, its own occupants "
        f"account for {truck_occupants:.2f} deaths per crash, so in at least "
        f"{_fmt_pct(1 - truck_occupants, 0)} of them everyone killed was outside the truck. "
        "Conventional roads have more deaths per measured kilometre "
        "than motorways and dual carriageways, mostly through more crashes per kilometre "
        f"({_link('long-run.html', 'Long-run trends')}).</p>"
    )
    text += (
        "<p>In Spain outside Catalonia and the Basque Country, an injury crash in which the "
        "police recorded "
        f"{_link('speed.html', 'inappropriate speed')} has "
        f"{_times(float(adjusted.rate_ratio))} ({_interval(adjusted.ratio_low, adjusted.ratio_high)}) "
        "the deaths of other crashes on the same kind of road in the same year, an association "
        "in a record written after the crash. Among the "
        f"{_link('factors.html', 'recorded factors')}, alcohol rose from "
        f"{_fmt_pct(float(alcohol.share_first))} to {_fmt_pct(float(alcohol.share_last))} of "
        f"interurban injury crashes between {int(alcohol.first_year)} and "
        f"{int(alcohol.last_year)}, and inappropriate speed fell from "
        f"{_fmt_pct(float(speed_share.share_first))} to "
        f"{_fmt_pct(float(speed_share.share_last))} of all injury crashes, both recorded "
        "consistently throughout; distraction on urban streets and drug-related crashes cannot "
        "be followed across the period.</p>"
    )
    return text


_SPLIT_CAPTION = (
    "Each group as a ratio to the group it is compared with. Driver rows count the driver's own "
    "death per driver involved, vehicle rows count vehicles in injury and in fatal crashes, and "
    "road rows cover the interurban State, regional and provincial roads whose kilometres are "
    "measured. For the age rows each range runs from a scenario that moves kilometres between "
    "age bands to the published ratio."
)
# How each comparison divides, in words: the codes ``_where`` returns.
_WHERE_LABELS = {
    "deadliness": "how deadly crashes are",
    "crashes": "how often crashes happen",
    "crashes more than deadliness": "both, mostly how often crashes happen",
    "deadliness more than crashes": "both, mostly how deadly crashes are",
    "both fell, deadliness most": "both fell, mostly how deadly crashes are",
    "both fell, crashes most": "both fell, mostly how often crashes happen",
    "depends on the kilometres": "depends on the kilometres assumed",
}
# Of two factors that both raise a comparison, the smaller is named when it carries at least this
# share of the excess on the log scale.
_SECOND_FACTOR_SHARE = 0.2


def _where_both(crashes: tuple[float, float], deadly: float) -> str:
    """Where the excess sits, said only when both ends of a range agree."""
    places = {_where(value, deadly) for value in crashes}
    return places.pop() if len(places) == 1 else "depends on the kilometres"


def _split_rows() -> list[dict[str, object]]:
    """Every comparison the study makes, as crashes per exposure times deaths per crash."""
    age = _age_numbers()
    ratios, owner = age["ratios"], age["owner"]
    sex = _sex_numbers()["ratios"]
    summary_rows = read_table("q6_summary_2022").set_index("group")
    risk = read_table("road_class_risk")
    risk_year = int(risk.year.max())
    risk = risk[risk.year == risk_year].set_index("road_class")
    split = read_table("risk_frequency_severity").set_index("year")
    first, final = int(split.index.min()), int(split.index.max())
    owner_km = "km driven by cars of owners that age"

    def vehicle(group: str) -> tuple[float, float]:
        row, car = summary_rows.loc[group], summary_rows.loc["car"]
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
    for key, label, short, name in (
        ("older", f"Car drivers aged 75 and over against 35–54, {km_year}", "older drivers", "75+"),
        ("young", f"Car drivers aged 18–34 against 35–54, {km_year}", "young drivers", "18-34"),
    ):
        crashes, deadly = band(name)
        rows.append(
            {
                "key": key,
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
            "men",
            f"Male against female car drivers, {min(sex_years)}–{max(sex_years)}",
            "men",
            "licence holders",
            float(sex.loc[("car", "18+", "involved_per_1000_licences"), "ratio"]),
            float(sex.loc[("car", "18+", "deaths_per_1000_involved"), "ratio"]),
        ),
        (
            "trucks",
            f"Heavy trucks against cars, {vehicles.KM_YEAR}",
            "heavy trucks",
            "vehicle-km",
            *vehicle("heavy_truck"),
        ),
        (
            "motorcycles",
            f"Motorcycles against cars, {vehicles.KM_YEAR}",
            "motorcycles",
            "vehicle-km",
            *vehicle("motorcycle"),
        ),
        (
            "conventional",
            f"Conventional roads against motorways and dual carriageways, {risk_year}",
            "conventional roads",
            "measured vehicle-km",
            road_crashes,
            road_deadly,
        ),
        (
            "years",
            f"All roads, {final} against {first}",
            "",
            "tonnes of road fuel sold",
            float(split.loc[final, "frequency_index"]) / 100,
            float(split.loc[final, "severity_index"]) / 100,
        ),
    ]
    for key, label, short, per, crashes, deadly in point_rows:
        rows.append(
            {
                "key": key,
                "label": label,
                "short": short,
                "per": per,
                "crashes": (crashes, crashes),
                "deadly": deadly,
                "where": _where(crashes, deadly),
            }
        )
    return rows


def _split_table(rows: list[dict[str, object]] | None = None) -> pd.DataFrame:
    rows = rows if rows is not None else _split_rows()
    out = []
    for row in rows:
        low, high = row["crashes"]  # type: ignore[misc]
        deadly = float(row["deadly"])  # type: ignore[arg-type]

        def cell(a: float, b: float) -> str:
            return _times(a) if math.isclose(a, b) else _range(a, b)

        out.append(
            {
                "Comparison": row["label"],
                "Exposure measure": row["per"],
                "Crashes per unit of exposure": cell(low, high),
                "How deadly a crash is": _times(deadly),
                "Deaths per unit of exposure": cell(low * deadly, high * deadly),
                "Mainly from": _WHERE_LABELS[str(row["where"])],
            }
        )
    return pd.DataFrame(out)


def _where(crashes: float, deadly: float) -> str:
    """Which factor carries a comparison, read on the log scale.

    When both factors fall, the larger fall is named. Otherwise only a factor above 1 adds to the
    excess; when both are above 1, the smaller is named as well if it carries at least
    ``_SECOND_FACTOR_SHARE`` of the excess.
    """
    a, b = math.log(crashes), math.log(deadly)
    if a < 0 and b < 0:
        return "both fell, deadliness most" if b < a else "both fell, crashes most"
    if a <= 0 or b <= 0 or min(a, b) / (a + b) < _SECOND_FACTOR_SHARE:
        return "deadliness" if b > a else "crashes"
    return "deadliness more than crashes" if b > a else "crashes more than deadliness"


# ----------------------------------------------------------------------------- regional records
def _share(frame: pd.DataFrame, dimension: str, level: str) -> pd.Series:
    return frame[(frame.dimension == dimension) & (frame.level == level)].iloc[0]


def _regional_records() -> str:
    """The Catalan and Barcelona records, and the two models that beat their tables."""
    shares = read_table("cat_fatal_share")
    people = read_table("bcn_person_severity_share")
    cat_years = read_table("cat_frequency").year
    bcn_year = _year_label(people)
    overall = _share(shares, "unit type involved", "all")
    interurban = _share(shares, "zone", "Carretera")
    urban = _share(shares, "zone", "Zona urbana")
    pedestrian = _share(people, "road user", "pedestrian")
    motorcycle = _share(people, "road user", "motorcycle driver")
    car = _share(people, "road user", "car driver")
    _check(interurban.ci_low > urban.ci_high, "overview", "interurban crashes more often fatal")
    _check(pedestrian.share > motorcycle.share > car.share, "overview", "road-user ordering")

    rules = read_table("ml_rule_comparison").set_index("model")
    selected = read_table("ml_selected")
    primary = selected[selected.primary].set_index("model")
    decisions = read_table("ml_model_decisions")
    context = decisions[decisions.variant.eq("context")].set_index("model").decision
    cat_last = int(cat_years.max())
    catalonia, person, crash = (rules.loc[model] for model in REGIONAL_MODELS)
    featured = [m for m in REGIONAL_MODELS if bool(rules.loc[m, "model_adds_signal_over_table"])]
    person_fit = primary.loc["barcelona_person_severity"]
    slope_low, slope_high = modelling.CALIBRATION_SLOPE_RANGE

    def held_out_later(design: str) -> bool:
        """Training precedes the test period, and settings were chosen without the test data."""
        years = re.fullmatch(r"train (\d+)-(\d+), choose on (\d+)-(\d+), test (\d+)", design)
        if years:
            train_end, choose_start, choose_end, test = (int(y) for y in years.groups()[1:])
            return train_end < choose_start <= choose_end < test
        months = re.fullmatch(
            r"train months 1-(\d+) with \d+-fold cross-validation grouped by crash; "
            r"test months (\d+)-12",
            design,
        )
        return bool(months) and int(months.group(1)) < int(months.group(2))

    _require(
        "regional records",
        {
            "the three regional models are the ones compared with a table": sorted(rules.index)
            == sorted(REGIONAL_MODELS),
            "every comparison table has a label": all(rule in RULE_LABELS for rule in rules.rule),
            "the Catalonia and Barcelona person models beat their tables, the crash model does "
            "not": featured == list(REGIONAL_MODELS[:2]),
            "the decision record features the same two models": sorted(
                m for m, d in context.items() if d in decision_rules.FEATURED
            )
            == sorted(REGIONAL_MODELS[:2])
            and context["barcelona_crash_severity"] == decision_rules.REPLACE,
            "each model is tested on later records not used to fit it or choose its settings": all(
                held_out_later(str(primary.loc[m, "design"])) for m in REGIONAL_MODELS
            ),
            "the Catalonia model is tested on the final year of the file": str(
                primary.loc["catalonia_crash_severity", "design"]
            ).endswith(f"test {cat_last}"),
            "the Barcelona models are tested on the year's final months": all(
                bool(re.search(r"test months \d+-12$", str(primary.loc[m, "design"])))
                for m in REGIONAL_MODELS[1:]
            ),
            "the Catalonia model's probabilities are usable as estimates": bool(
                primary.loc["catalonia_crash_severity", "probabilities_shown_as_estimates"]
            ),
            "the Barcelona person model's probabilities are not": not bool(
                person_fit.probabilities_shown_as_estimates
            ),
            "the Barcelona person model is right on average": abs(
                float(person_fit.mean_predicted) - float(person_fit.prevalence)
            )
            <= modelling.CALIBRATION_LARGE_TOLERANCE * float(person_fit.prevalence),
            "the Barcelona person model's calibration slope is outside the accepted range and its "
            "interval excludes 1": not slope_low
            <= float(person_fit.calibration_slope)
            <= slope_high
            and float(person_fit.calibration_slope_high) < 1,
        },
    )

    def scores(row: pd.Series) -> str:
        return f"{float(row.model_roc_auc):.2f} against {float(row.rule_roc_auc):.2f}"

    return (
        "<h2>Crash records and severity models in Catalonia and Barcelona</h2>"
        f"<p>The {_link('catalonia.html', 'Catalan file')} holds every crash with a death or serious "
        f"injury: {_fmt_int(overall.n)} between {int(cat_years.min())} and {cat_last}, of which "
        f"{_fmt_pct(overall.share)} were fatal ({_fmt_pct(interurban.share)} on interurban "
        f"roads and {_fmt_pct(urban.share)} on urban streets). "
        + _link("barcelona.html", "Barcelona's records")
        + f" list the people in each crash: in {bcn_year}, {_fmt_pct(pedestrian.share)} of "
        f"pedestrians and {_fmt_pct(motorcycle.share)} of motorcyclists in recorded crashes "
        f"were seriously or fatally injured, against {_fmt_int(car.events)} of "
        f"{_fmt_int(car.n)} car drivers ({_fmt_pct(car.share, 2)}). Neither source measures "
        "exposure, so these shares describe "
        + _link("data.html#records", "how severe the outcome was once a crash had been recorded")
        + ".</p>"
        f"<p>From these records the study built {_WORDS[len(REGIONAL_MODELS)]} "
        f"{_link('severity-models.html', 'models that rank recorded cases by severity')}. Each "
        "was tested once on later records not used to fit it or choose its settings, and "
        "compared with a simple table of the share of severe outcomes in each group. Ranking is measured by the "
        "ROC-AUC, the probability that a model scores a randomly chosen severe case above a "
        "less severe one: 0.5 is chance and 1 a perfect ranking. "
        f"{_capital(_WORDS[len(featured)])} of the {_WORDS[len(REGIONAL_MODELS)]} rank better "
        "than their tables.</p>"
        f"<p>The <strong>{MODEL_NAMES['catalonia_crash_severity']}</strong> estimates which "
        "crashes with a death or serious injury were fatal. On the crashes of "
        f"{cat_last}, the file's last year, it reaches a ROC-AUC of {scores(catalonia)} "
        f"for a table of fatal shares by {RULE_LABELS[catalonia.rule]}, and its predicted "
        "probabilities agree with the observed fatal shares.</p>"
        f"<p>The <strong>{MODEL_NAMES['barcelona_person_severity']}</strong> estimates which "
        "people in Barcelona crashes were seriously or fatally injured. On the final months of "
        f"{bcn_year} it reaches {scores(person)} for a table of shares by "
        f"{RULE_LABELS[person.rule]}. Its probabilities are right on average but do not match "
        "the observed shares across groups of people (calibration slope "
        f"{float(person_fit.calibration_slope):.2f}, where 1 is perfect agreement), so it is "
        "used only to rank people. The third, the Barcelona crash model, ranked "
        "crashes no better than a table of the share with a serious or fatal injury by "
        f"{RULE_LABELS[crash.rule]} ({scores(crash)}), so the study reports that table in its "
        "place.</p>"
    )


# ----------------------------------------------------------------------------- external validation
def _validation() -> str:
    transport = read_table("ml_transport_validation")
    path = read_table("ml_outward_path")
    outcomes = read_table("gen_outcomes")
    verdicts = read_table("ml_barcelona_diagnosis_verdicts")
    components = read_table("ml_barcelona_diagnosis_components")
    selected = read_table("ml_selected")
    chosen = selected[selected.primary].set_index("model").estimator

    def external(prefix: str, model: str) -> pd.Series:
        part = transport[
            transport.experiment.str.startswith(prefix)
            & transport.model.eq(model)
            & transport.estimator.eq(chosen[model])
            & transport.status.eq("reported")
        ]
        return part.iloc[0]

    national = external("Catalonia -> Spain outside Catalonia", "catalonia_common_dgt")
    to_bcn = external("rest of Catalonia -> Barcelona municipality", "catalonia_crash_severity")
    main = (
        verdicts[verdicts.features.str.startswith("full")]
        .set_index("estimator")
        .loc[chosen["catalonia_crash_severity"]]
    )
    harder = components[
        components.features.str.startswith("full")
        & components.estimator.eq(chosen["catalonia_crash_severity"])
        & components.component.eq("intrinsic difference")
    ].iloc[0]
    fatal = outcomes[
        outcomes.comparison.eq("Catalonia vs Spain outside Catalonia")
        & outcomes.outcome.str.startswith("fatal (24 h) among")
    ].iloc[0]
    national_stage = path[(path.model == "catalonia_common_dgt") & (path.stage == path.stage.max())]

    _require(
        "validation",
        {
            "the Catalonia-trained model ranks almost as well as one trained in the test "
            "population": abs(float(national.transfer_gap)) <= 0.01,
            "the national ranking is clearly better than chance": float(national.roc_auc_low) > 0.5,
            "Catalonia's fatal share of serious crashes differs from the rest of Spain's": float(
                fatal.high_a
            )
            < float(fatal.low_b),
            "the national-resemblance stage fails for the harmonised model": bool(
                national_stage.status.eq("failed").all()
            )
            and len(national_stage) == 1,
            "no model is called nationally transferable": not path.verdict.eq(
                "potentially nationally transferable"
            ).any(),
            "the gap quoted for Barcelona is the model's own transfer cost": math.isclose(
                -float(to_bcn.transfer_gap), float(main.transport_cost), abs_tol=1e-6
            ),
            "moving the model to Barcelona costs no measurable ranking": not bool(
                main.transport_cost_excludes_zero
            ),
            "Barcelona's crashes are harder to rank at equal training size": float(harder.low) > 0,
        },
    )

    return (
        "<h2>External validation</h2>"
        "<p>A model can rank cases well in the population it was trained on and fail elsewhere. "
        f"In the {_link('validation.html', 'external validation')}, the "
        f"{MODEL_NAMES['catalonia_crash_severity']}, restricted to the variables both sources "
        "record in the same way, was trained on the Catalan file and applied to "
        f"{_fmt_int(national.test_n)} crashes with a death or serious "
        f"injury recorded by DGT outside Catalonia, {_fmt_int(national.test_positives)} of them "
        "fatal within 24 hours. It ranks those crashes almost as well as a model trained on the "
        "DGT records themselves: a ROC-AUC of "
        f"{float(national.roc_auc):.3f} against {float(national.in_domain_cv_roc_auc):.3f}.</p>"
        "<p>Catalonia's serious and fatal crashes differ from the rest of Spain's, however: in "
        "DGT's own records, "
        f"{_fmt_pct(fatal.share_a)} of them were fatal within 24 hours in Catalonia, against "
        f"{_fmt_pct(fatal.share_b)} elsewhere. Use of the model across Spain is therefore not "
        f"established. Within Catalonia, the {MODEL_NAMES['catalonia_crash_severity']} trained "
        f"on the rest of the region scores {float(to_bcn.roc_auc):.3f} on Barcelona city's "
        f"crashes, against {float(to_bcn.in_domain_cv_roc_auc):.3f} for a model trained on the "
        f"city's own crashes (difference {_fmt_dec(float(to_bcn.transfer_gap), 3)}): the change "
        "of population itself costs no measurable ranking, and Barcelona's crashes are harder "
        "to rank than the rest of Catalonia's even for a model trained there.</p>"
    )


# ----------------------------------------------------------------------------- further analyses
def _further() -> str:
    """The supporting analyses, the data sources and the methodology, in one closing section."""
    validation = read_table("forecast_validation").set_index(["outcome", "set", "method"])
    detect = read_table("forecast_detectability").set_index(["outcome", "horizon"])
    chosen = forecast.CHOSEN

    def rmse(kind: str, method: str) -> float:
        return float(validation.loc[("deaths_all", kind, method), "rmse"])

    one_year = detect.loc[("deaths_all", 1)]
    rise = forecast.minimum_detectable_rise(float(one_year.expected), float(one_year.tau))
    policy = _policy_numbers()
    step, calendar = policy["main"], policy["calendar"]
    true_calendar, true_forecast = policy["true_calendar"], policy["true_forecast"]
    runner_up = calendar[calendar["rank"] == 2].iloc[0]
    licence_year = int(true_forecast.year)

    _require(
        "further analyses",
        {
            "last year's count beats the forecast in ordinary held-out years, but only slightly": (
                rmse("holdout", "last_year")
                < rmse("holdout", chosen)
                < 1.25 * rmse("holdout", "last_year")
            ),
            "the forecast does much better than last year's count in the lockdowns": 2
            * rmse("pandemic", chosen)
            < rmse("pandemic", "last_year"),
            "the forecast's detection probability is four in five": forecast.POWER == 0.8,
            "deaths fell at the points licence under the preferred trend": float(step.level_change)
            < 0,
            "the licence year is the same in both July tests": int(true_calendar.year)
            == licence_year,
            "the licence July has the largest step of the July placebos": int(true_calendar["rank"])
            == 1,
            "but not exceptionally: its interval overlaps the next July's, and a rank of 1 is "
            "short of conventional significance": float(runner_up.low) <= float(true_calendar.high)
            and 1 / float(true_calendar.n_fits) > 0.05,
            "other Julys fall further below their forecast": int(true_forecast["rank"]) > 1,
        },
    )

    return (
        "<h2>Further analyses, data and methods</h2>"
        "<p>An "
        f"{_link('severity.html', 'association analysis of DGT crash records')} describes which "
        "recorded circumstances go with a fatal outcome once an injury crash has happened. A "
        f"{_link('forecast.html', 'monthly deaths forecast')} is slightly less accurate than "
        "repeating the previous year's count in ordinary years "
        f"({_fmt_pct(rmse('holdout', chosen))} error against "
        f"{_fmt_pct(rmse('holdout', 'last_year'))}) and far more accurate in the lockdown years "
        f"({_fmt_pct(rmse('pandemic', chosen))} against "
        f"{_fmt_pct(rmse('pandemic', 'last_year'))}); a comparison with its forecast detects "
        f"a fall of {_fmt_pct(float(one_year.mde), 0)} or a rise of {_fmt_pct(rise, 0)} in one "
        "year's deaths four times in five. The study of the "
        f"{_link('policy.html', f'{licence_year} points-based licence')} estimates a fall in "
        f"monthly deaths of about {_fmt_pct(-float(step.level_change), 0)} when it came into "
        f"force. A simpler step model fitted at {int(true_calendar.n_fits)} Julys gives "
        f"{licence_year} the largest fall, but only narrowly, and against forecasts made before "
        f"each July it ranks {_ordinal(int(true_forecast['rank']))} of "
        f"{int(true_forecast.n_fits)}, so the series cannot attribute the fall to the licence."
        "</p>"
        f"<p>{_link('sources.html', 'Data sources and scope')} describes each source and sets "
        f"out {_link('sources.html#scope', 'the limits of the data')}; the sources share no "
        "record identifier, so no record is linked across them. The "
        f"{_link('data.html', 'methodology')} defines the terms and explains how rates, police "
        "records and models are built and read. Every comparison in the study between an "
        "outcome and a circumstance is an association, and none estimates a causal effect.</p>"
    )
