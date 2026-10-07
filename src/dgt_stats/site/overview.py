"""The front page: what the study is, what data it uses, its main results and where to read on.

It quotes only the strongest results and leaves the methods to the pages behind them. Every
number is read from a committed result table, and every qualitative sentence is checked against
the tables before the page is written.
"""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import driver_risk, vehicles
from dgt_stats.microdata.validation import decisions as decision_rules
from dgt_stats.site.components import (
    _fmt_int,
    _fmt_pct,
    read_table,
    render_page,
    summary,
)
from dgt_stats.site.numbers import _age_numbers, _long_run_numbers, _risk_numbers, _speed_numbers
from dgt_stats.site.regional_common import _year_label

# The three models trained on the regional records, in the order the page names them.
REGIONAL_MODELS = (
    "catalonia_crash_severity",
    "barcelona_person_severity",
    "barcelona_crash_severity",
)


def _require(section: str, checks: dict[str, bool]) -> None:
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"overview ({section}): the tables no longer support: {failed}")


def _link(href: str, text: str) -> str:
    return f'<a href="{href}">{text}</a>'


def _share(frame: pd.DataFrame, dimension: str, level: str) -> pd.Series:
    return frame[(frame.dimension == dimension) & (frame.level == level)].iloc[0]


def page_index(captions: dict[str, str]) -> str:
    national_years = read_table("longrun_series").year
    cat_years = read_table("cat_frequency").year
    bcn_year = _year_label(read_table("bcn_person_severity_share"))
    body = _introduction()
    body += _data(int(national_years.min()), int(national_years.max()), cat_years, bcn_year)
    body += _results()
    body += _reading_on()
    lead = (
        "An independent statistical study of road deaths and injuries in Spain from "
        f"{int(national_years.min())} to {int(national_years.max())}, built from official "
        "statistics and from police crash records for Catalonia and Barcelona."
    )
    return render_page("index", "Road safety in Spain", lead, body)


def _introduction() -> str:
    return summary(
        "Most of this study is ordinary statistical analysis of published data: deaths and "
        "crashes counted over time and divided by measures of population and traffic, such as "
        "residents, licence holders, vehicles, fuel sold or kilometres driven. Where the data "
        "allow, a death rate is split into two parts: how often crashes happen, and how deadly a "
        "crash is once it has happened. A smaller part of the study fits predictive models to "
        "individual crash "
        "records from Catalonia and Barcelona, and keeps a model only if it beats a simple table "
        "of the same records."
    )


def _data(first: int, last: int, cat_years: pd.Series, bcn_year: str) -> str:
    records_first = int(read_table("missingness_by_year").year.min())
    return (
        "<h2>Data</h2>"
        "<p>The national analysis uses statistics from the Dirección General de Tráfico (DGT): "
        f"its yearbook series from {first} to {last}, its tables of the drivers and vehicles "
        f"involved in crashes, its file of every injury crash since {records_first} and its "
        "estimates of kilometres driven. INE's population figures, road-fuel sales and traffic "
        "counts supply the denominators. Two regional sources record "
        "individual crashes in more detail: Catalonia's file of every crash with a death or "
        f"serious injury from {int(cat_years.min())} to {int(cat_years.max())}, and Barcelona's "
        f"police records of every crash attended in {bcn_year}, with each person involved. The "
        "sources share no record identifier, so they are analysed separately and never merged "
        f"({_link('sources.html', 'data sources and scope')}).</p>"
    )


def _results() -> str:
    text = "<h2>Main results</h2>"
    text += _long_run()
    text += _drivers_and_vehicles()
    text += _speed()
    text += _regional()
    text += _models()
    return text


def _long_run() -> str:
    long_run = _long_run_numbers()
    segments = long_run["segments"]
    count = segments[segments.measure == "count"].sort_values("start")
    steep = count.loc[count.annual_change.idxmin()]
    flat = count.iloc[-1]
    headline = read_table("q1_annual_headline").set_index("year").deaths_30d
    first = int(headline.index.min())
    risk = _risk_numbers()
    latest, last, base = risk["latest"], risk["last"], risk["base"]
    deaths = latest.xs("deaths_30d", level="outcome")
    split = read_table("risk_frequency_severity").set_index("year")
    split_first, split_last = int(split.index.min()), int(split.index.max())
    per_fuel = float(split.loc[split_last, "deaths_per_fuel_index"]) / 100
    severity = float(split.loc[split_last, "severity_index"]) / 100
    frequency = float(split.loc[split_last, "frequency_index"]) / 100
    _require(
        "long run",
        {
            "the steepest segment of the count ends where the last starts": int(steep.end)
            == int(flat.start),
            "the count fell in the steep segment": float(steep.high) < 0,
            "the last segment shows no clear rise or fall": float(flat.low) < 0 < float(flat.high),
            "most of the fall to the end of the steep segment came within it": float(
                headline.loc[int(steep.start)] - headline.loc[int(steep.end)]
            )
            > 0.5 * float(headline.loc[first] - headline.loc[int(steep.end)]),
            "more people died in the latest year than at the end of the steep segment": float(
                deaths.loc["count", "count"]
            )
            > float(headline.loc[int(steep.end)]),
            "no denominator shows a change in deaths beyond an ordinary year since the base year": all(
                float(row.ratio_low_yty) <= 1 <= float(row.ratio_high_yty)
                for _, row in deaths.iterrows()
            ),
            "deaths per crash fell much more than crashes per tonne of fuel": severity
            < frequency
            < 1
            and math.log(severity) < 2 * math.log(frequency),
        },
    )
    fall = 1 - float(headline.loc[int(steep.end)]) / float(headline.loc[first])
    return (
        f"<p>Road deaths in Spain fell from {_fmt_int(headline.loc[first])} in {first} to "
        f"{_fmt_int(headline.loc[int(steep.end)])} in {int(steep.end)}, a fall of "
        f"{_fmt_pct(fall, 0)}, most of it between {int(steep.start)} and {int(steep.end)}, when "
        f"they fell {_fmt_pct(-float(steep.annual_change))} a year. That steep decline ended "
        f"around {int(steep.end)}: the trend fitted from {int(flat.start)} to {int(flat.end)} "
        f"shows no clear rise or fall, and the {_fmt_int(deaths.loc['count', 'count'])} deaths "
        f"of {last} were more than the {_fmt_int(headline.loc[int(steep.end)])} of "
        f"{int(steep.end)}. The change since {base} is within ordinary year-to-year variation "
        "whether deaths are counted or divided by residents, licence holders, vehicles or fuel "
        "sold "
        f"({_link('long-run.html', 'long-run trends')}, "
        f"{_link('trends.html', f'trends since {base}')}).</p>"
        f"<p>Between {split_first} and {split_last}, deaths per tonne of road fuel sold, the "
        "only measure of traffic that covers every road in every year, fell "
        f"{_fmt_pct(1 - per_fuel, 0)}. Most of that fall came from crashes becoming less deadly: "
        f"deaths per injury crash fell {_fmt_pct(1 - severity, 0)}, while injury crashes per "
        f"tonne of fuel fell {_fmt_pct(1 - frequency, 0)}. How the fall divides between the two "
        "depends on how completely crashes with only slight injuries are recorded; the fall "
        "itself does not.</p>"
    )


def _drivers_and_vehicles() -> str:
    age = _age_numbers()
    ratios, rates, owner = age["ratios"], age["rates"], age["owner"]
    oldest = ratios.loc[("deaths_per_1000_involved", "75+")]
    young = driver_risk.TRANSFER_BANDS[0]
    young_low = float(owner.loc[young, "involved_per_bn_km_range_low"])
    young_high = float(owner.loc[young, "involved_per_bn_km_range_high"])
    young_fatality = ratios.loc[("deaths_per_1000_involved", young)]
    summary_rows = read_table("q6_summary_2022").set_index("group")
    truck, car, bike = (summary_rows.loc[g] for g in ("heavy_truck", "car", "motorcycle"))

    def ratio(row: pd.Series, column: str) -> float:
        return float(row[column] / car[column])

    truck_vehicle = ratio(truck, "fatal_involvement_per_100k_vehicles")
    truck_km = ratio(truck, "fatal_involvement_per_bn_km")
    bike_vehicle = ratio(bike, "fatal_involvement_per_100k_vehicles")
    bike_km = ratio(bike, "fatal_involvement_per_bn_km")
    _require(
        "drivers and vehicles",
        {
            "drivers aged 75 and over die more once involved": float(oldest.low) > 1,
            "the youngest drivers do not die more once involved": float(young_fatality.low)
            <= 1
            <= float(young_fatality.high),
            "the youngest drivers are involved more per km at both ends of the range": young_low
            > 1,
            "a heavy truck is further above a car per vehicle than per km": truck_vehicle
            > truck_km
            > 1,
            "a motorcycle is further above a car per km than per vehicle": bike_km
            > bike_vehicle
            > 1,
        },
    )
    km_year = driver_risk.KM_YEAR
    return (
        f"<p>In {km_year}, car drivers aged 75 and over who were involved in an injury crash died "
        f"{float(oldest.ratio):.1f} times as often as drivers aged 35–54 "
        f"({float(rates.loc['75+', 'deaths_per_1000_involved']):.1f} against "
        f"{float(rates.loc[driver_risk.REFERENCE_BAND, 'deaths_per_1000_involved']):.1f} per "
        "1,000), a result that needs no estimate of kilometres. Once involved, drivers aged "
        "18–24 died about as often as drivers aged 35–54. On DGT's kilometre estimates, which "
        "are published by the age of a car's registered owner and not its driver, they were "
        f"involved in {young_high:.1f} times as many injury crashes per kilometre as drivers "
        "aged 35–54. Under a deliberately extreme reassignment of kilometres to young owners, "
        f"the ratio falls to {young_low:.1f}, still above 1 "
        f"({_link('drivers.html', 'drivers')}).</p>"
        "<p>Comparisons between vehicle types depend on what they are measured against. In "
        f"{vehicles.KM_YEAR}, a heavy truck was in a fatal crash {truck_vehicle:.1f} times as "
        "often as a car per vehicle, but "
        f"{truck_km:.1f} times as often per kilometre, because each truck is driven much "
        f"further; a motorcycle, {bike_vehicle:.1f} times as often per vehicle and "
        f"{bike_km:.1f} times per kilometre ({_link('vehicles.html', 'vehicles')}).</p>"
    )


def _speed() -> str:
    numbers = _speed_numbers()
    adjusted = numbers["pooled"].loc["adjusted"]
    all_roads = numbers["all_roads"]
    last = int(all_roads.index.max())
    _require(
        "speed",
        {
            "deaths per crash are about twice as high where speed is recorded": 1.8
            <= float(adjusted.rate_ratio)
            <= 2.2
            and float(adjusted.ratio_low) > 1,
        },
    )
    return (
        "<p>In Spain outside Catalonia and the Basque Country, police recorded inappropriate "
        f"speed in {_fmt_pct(float(all_roads.loc[last, 'share_of_crashes']))} of injury crashes "
        f"in {last}. Those crashes had about twice the deaths per crash of other crashes on the "
        "same kind of road in the same year. That is an association in police records; it does "
        "not estimate how many crashes or deaths speeding caused "
        f"({_link('speed.html', 'speed')}, {_link('factors.html', 'recorded factors')}).</p>"
    )


def _regional() -> str:
    shares = read_table("cat_fatal_share")
    people = read_table("bcn_person_severity_share")
    overall = _share(shares, "unit type involved", "all")
    interurban = _share(shares, "zone", "Carretera")
    urban = _share(shares, "zone", "Zona urbana")
    pedestrian = _share(people, "road user", "pedestrian")
    motorcycle = _share(people, "road user", "motorcycle driver")
    car = _share(people, "road user", "car driver")
    _require(
        "regional records",
        {
            "interurban serious crashes are more often fatal than urban ones": float(
                interurban.ci_low
            )
            > float(urban.ci_high),
            "pedestrians, then motorcyclists, are more often seriously hurt than car drivers": float(
                pedestrian.share
            )
            > float(motorcycle.share)
            > 10 * float(car.share),
        },
    )
    return (
        "<p>The regional records describe severity among crashes that were recorded. In "
        f"Catalonia, {_fmt_pct(overall.share)} of crashes with a death or serious injury were "
        f"fatal: {_fmt_pct(interurban.share)} on interurban roads and {_fmt_pct(urban.share)} on "
        f"urban streets ({_link('catalonia.html', 'Catalonia')}). In Barcelona, "
        f"{_fmt_pct(pedestrian.share)} of pedestrians and {_fmt_pct(motorcycle.share)} of "
        "motorcyclists in recorded crashes were seriously or fatally injured, against "
        f"{_fmt_pct(car.share, 2)} of car drivers ({_link('barcelona.html', 'Barcelona')}). "
        "Neither source measures how much people travel, so these are not rates per journey or "
        "per kilometre.</p>"
    )


def _models() -> str:
    rules = read_table("ml_rule_comparison").set_index("model")
    decisions = read_table("ml_model_decisions")
    context = decisions[decisions.variant.eq("context")].set_index("model").decision
    selected = read_table("ml_selected")
    primary = selected[selected.primary].set_index("model")
    transport = read_table("ml_transport_validation")
    path = read_table("ml_outward_path")
    national = transport[
        transport.experiment.eq("Catalonia -> Spain outside Catalonia")
        & transport.model.eq("catalonia_common_dgt")
        & transport.estimator.eq(primary.loc["catalonia_common_dgt", "estimator"])
        & transport.status.eq("reported")
    ].iloc[0]
    beat = [m for m in REGIONAL_MODELS if bool(rules.loc[m, "model_adds_signal_over_table"])]
    _require(
        "models",
        {
            "the Catalonia and Barcelona person models beat their tables, the crash model does "
            "not": beat == list(REGIONAL_MODELS[:2]),
            "the decision record keeps the first two and replaces the third with its table": all(
                context[m] in decision_rules.FEATURED for m in REGIONAL_MODELS[:2]
            )
            and context[REGIONAL_MODELS[2]] == decision_rules.REPLACE,
            "the Catalonia model's probabilities can be read as estimates": bool(
                primary.loc[REGIONAL_MODELS[0], "probabilities_shown_as_estimates"]
            ),
            "the Barcelona person model's probabilities cannot": not bool(
                primary.loc[REGIONAL_MODELS[1], "probabilities_shown_as_estimates"]
            ),
            "the Catalonia-trained model ranks Spanish crashes almost as well as one trained "
            "on them": abs(float(national.transfer_gap)) <= 0.01,
            "no model is called fit for national use": not path.verdict.eq(
                "potentially nationally transferable"
            ).any(),
        },
    )
    return (
        "<p>The modelling has a narrower aim: to rank crashes, or the people in them, by how "
        "severe the outcome was, using only what was recorded, better than a simple table of "
        "severity by type of crash or road user does. Each model was judged on later records it "
        "had not seen. The model for Catalonia, which ranks serious crashes by how likely they were "
        "to be fatal, did clearly better than its table, and in its test year its probabilities "
        "matched the observed fatal shares well overall. The model of people in Barcelona "
        "crashes also beat its table, but its scores were too extreme to read as probabilities, "
        "so it is used only to rank. "
        "A model of Barcelona crashes did no better than a table of the share of crashes with "
        "a serious or fatal injury by accident type, and the table is reported instead. A "
        "version of the Catalan model "
        "tested on DGT's records of serious crashes in the rest of Spain ranked them almost as "
        "well as a model trained on those records, which does not make it fit for national "
        "use. None of the models predicts whether a crash will happen "
        f"({_link('severity-models.html', 'predictive models')}, "
        f"{_link('validation.html', 'external validation')}).</p>"
    )


def _reading_on() -> str:
    base = _risk_numbers()["base"]
    return (
        "<h2>Reading on</h2>"
        f"<p>The pages under Spain cover the national data: {_link('trends.html', 'trends since')} "
        f"{base}, the {_link('long-run.html', 'long run')}, {_link('seasons.html', 'seasons')}, "
        f"{_link('drivers.html', 'drivers')}, {_link('vehicles.html', 'vehicles')}, "
        f"{_link('speed.html', 'speed')} and {_link('factors.html', 'recorded factors')}, with "
        "three supporting analyses: an association analysis of "
        f"{_link('severity.html', 'crash circumstances')}, a "
        f"{_link('forecast.html', 'forecast of monthly deaths')} and a study of the "
        f"{_link('policy.html', 'points-based licence')}. The Regional data pages describe the "
        "Catalan and Barcelona records, and the Models pages the predictive models and how they "
        f"were tested. {_link('data.html', 'Methodology')} defines the terms and explains how "
        "rates, police records and models are read. Every comparison on the site between an "
        "outcome and a circumstance is an association, not an estimate of a causal effect.</p>"
    )
