"""The overview: the findings, what connects them, and what the site does not claim."""

from __future__ import annotations

import math

import pandas as pd

from dgt_stats import factor_models, simulator
from dgt_stats.site import factor_pages
from dgt_stats.site.components import (
    _chance,
    _change,
    _fmt_int,
    _fmt_pct,
    _signed_int,
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


def page_index(captions: dict[str, str]) -> str:
    risk = _risk_numbers()
    latest, last = risk["latest"], risk["last"]
    long_run = _long_run_numbers()
    projected = long_run["projected"]
    season = _season_numbers()
    effects = season["effects"]
    sex = _sex_numbers()
    age = _age_numbers()
    speed = _speed_numbers()
    factor = _factor_numbers()
    vehicles = read_table("q6_summary_2022").set_index("group")
    truck, car = vehicles.loc["heavy_truck"], vehicles.loc["car"]
    split = read_table("risk_frequency_severity").set_index("year")
    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_last = int(km_check.index.get_level_values("year").max())
    presets = read_table("simulator_presets").set_index("scenario")
    speeds = read_table("simulator_speed_sites").set_index("site")

    deaths_count = latest.loc[("deaths_30d", "count")]
    deaths_fuel = latest.loc[("deaths_30d", "road_fuel")]
    deaths_vehicle = latest.loc[("deaths_30d", "vehicles")]
    deaths_resident = latest.loc[("deaths_30d", "residents")]
    hosp_count = latest.loc[("hospitalised_30d", "count")]
    count_2020 = projected.loc[("count", 2020)]
    fuel_2020 = projected.loc[("road_fuel", 2020)]
    km_last_row = km_check.loc[("per_km", km_last)]
    fuel_km_last_row = km_check.loc[("per_fuel", km_last)]
    if bool(km_last_row.outside_interval) or not bool(fuel_km_last_row.outside_interval):
        raise ValueError("overview: the per-km and per-fuel checks no longer split as described")
    july_raw = effects.loc[("none", 7)]
    july_petrol = effects.loc[("petrol_tonnes", 7)]
    august_raw = effects.loc[("none", 8)]
    august_petrol = effects.loc[("petrol_tonnes", 8)]
    april = season["lockdown"].loc[4]
    ratios_sex = sex["ratios"]
    men_involved = ratios_sex.loc[("car", "18+", "involved_per_1000_licences")]
    men_fatality = ratios_sex.loc[("car", "18+", "deaths_per_1000_involved")]
    involved_75 = age["ratios"].loc[("involved_per_bn_km", "75+")]
    fatality_75 = age["ratios"].loc[("deaths_per_1000_involved", "75+")]
    killed_75 = age["ratios"].loc[("deaths_per_bn_km", "75+")]
    involved_young = age["ratios"].loc[("involved_per_bn_km", "18-34")]
    fatality_young = age["ratios"].loc[("deaths_per_1000_involved", "18-34")]
    killed_young = age["ratios"].loc[("deaths_per_bn_km", "18-34")]
    older_peers = read_table("q7_km_ratio_65_74").set_index(["measure", "band"])
    men_killed = ratios_sex.loc[("car", "18+", "deaths_per_million_licences")]
    adjusted = speed["pooled"].loc["adjusted"]
    per_vehicle = float(
        truck.fatal_involvement_per_100k_vehicles / car.fatal_involvement_per_100k_vehicles
    )
    per_km = float(truck.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
    windows = factor["windows"]
    alcohol = _window(windows, "interurban", "Alcohol", 2014)
    speed_share = _window(windows, "all", "Inappropriate speed", 2014)
    comply = presets.loc["all_comply"]
    conventional = presets.loc["conventional_80"]
    conventional_comply = presets.loc["conventional_comply"]
    kept_140 = presets.loc["motorway_140_comply"]
    levers = read_table("factor_comparison").set_index(["lever", "zone"])
    by_factor = read_table("factor_deaths").set_index(["factor", "zone", "role"])
    upper = read_table("factor_naturalistic").set_index("zone").loc["all"]
    lever = {name: levers.loc[(name, "all")] for name in (*factor_models.LEVERS, "combined")}
    if not upper.avoided > by_factor.loc[("alcohol", "all", "all")].avoided_high:
        raise ValueError("overview: the distraction ceiling no longer exceeds alcohol")

    first, final = int(split.index.min()), int(split.index.max())
    severity = float(split.loc[final, "severity_index"]) / 100 - 1
    frequency = float(split.loc[final, "frequency_index"]) / 100 - 1
    per_fuel = float(split.loc[final, "deaths_per_fuel_index"]) / 100 - 1

    body = key_figures(
        [
            (
                f"How deadly a crash is, {first}–{final}",
                _signed_pct(severity),
                f"deaths per injury crash; how often crashes happen per unit of traffic: "
                f"{_signed_pct(frequency)}",
            ),
            (
                "Killed per km, drivers 75+",
                _times(float(killed_75.ratio)),
                f"against 35–54: {_times(float(involved_75.ratio))} the crashes × "
                f"{_times(float(fatality_75.ratio))} the deaths per crash",
            ),
            (
                "Deaths per crash with speed",
                _times(float(adjusted.rate_ratio)),
                "against other crashes on the same kind of road",
            ),
            (
                "If everyone kept to today's limits",
                _signed_int(comply.deaths_change),
                "deaths a year on autopistas, autovías and conventional roads",
            ),
        ]
    )
    body += (
        '<p class="answer">A count of crashes or deaths says how many. It does not say how '
        "dangerous the roads were, because it moves with how much people drove, who was driving "
        "and in what. This site divides the same DGT counts by residents, licence holders, "
        "vehicles, kilometres and road fuel, and asks what changes. On every question below the "
        "answer changes size, and on several it changes sign. Each answer can then be split in "
        "two, how often crashes happen and how deadly they are, and the split shows where the "
        "extra deaths come from: for older drivers, men and heavy trucks it is how deadly the "
        "crash is; for young drivers, motorcycles and conventional roads it is mostly how often "
        "crashes happen. Speed acts on both, and the last page asks what a speed law would "
        "do.</p>"
    )

    findings = [
        (
            "trends.html",
            "Since 2019, death risk has not measurably changed; recorded hospital admissions have "
            "risen",
            f"Deaths in {last} were {_change(float(deaths_count.ratio_to_base))} on 2019 as a "
            f"count, {_change(float(deaths_resident.ratio_to_base))} per resident, "
            f"{_change(float(deaths_vehicle.ratio_to_base))} per registered vehicle and "
            f"{_change(float(deaths_fuel.ratio_to_base))} per tonne of road fuel, all within an "
            "ordinary year's variation. People admitted to hospital rose "
            f"{_change(float(hosp_count.ratio_to_base))}, beyond it.",
            "Annual DGT totals over INE residents, the driver census, the registered fleet and "
            "CORES road fuel, indexed to 2019, with intervals that allow for the yearly "
            "scatter of each count.",
        ),
        (
            "long-run.html",
            "The pandemic dip was less driving; since then risk per kilometre has not jumped",
            f"As a count, 2020 deaths were {_change(float(count_2020.ratio), 0)} against the "
            "pre-pandemic trend and back on it by 2022. Per tonne of road fuel 2020 was on trend "
            f"({_times(float(fuel_2020.ratio))}): the fall was the traffic. On interurban roads "
            f"in {km_last}, deaths per tonne of fuel were "
            f"{_change(float(fuel_km_last_row.ratio), 0)} on trend, outside its interval, but "
            f"per kilometre measured {_change(float(km_last_row.ratio), 0)}, inside it. The "
            "counts cannot yet tell whether the pre-2020 decline went on or stalled; they rule "
            "out a jump.",
            "Joinpoint quasi-Poisson trends fitted to 1993–2019 and projected, re-run on the "
            "Ministerio de Transportes' measured interurban vehicle-kilometres.",
        ),
        (
            "seasons.html",
            "The summer peak is mostly traffic; the autumn excess is not",
            f"Raw deaths in July are {_times(float(july_raw.rate_ratio))} and in August "
            f"{_times(float(august_raw.rate_ratio))} the average month. Per unit of petrol, "
            "which cars and motorcycles burn, they are "
            f"{_times(float(july_petrol.rate_ratio))} and "
            f"{_times(float(august_petrol.rate_ratio))}. In the April 2020 lockdown deaths fell "
            f"{_fmt_pct(-float(april.deaths_change), 0)} and petrol sales "
            f"{_fmt_pct(-float(april.petrol_tonnes_change), 0)}: fewer deaths, not safer roads.",
            "Monthly deaths since 2014 against monthly road fuel, petrol and toll-motorway "
            "traffic, in quasi-Poisson models with year and month effects.",
        ),
        (
            "drivers.html",
            "Young drivers die more per km because they crash more; older drivers because a "
            "crash kills them more often",
            f"Per kilometre, car drivers aged 75 and over are killed "
            f"{_times(float(killed_75.ratio))} as often as those aged 35 to 54: "
            f"{_times(float(involved_75.ratio))} the crashes per km (but "
            f"{_times(float(older_peers.loc[('involved_per_bn_km', '75+'), 'ratio']))} those of "
            f"drivers aged 65 to 74) × {_times(float(fatality_75.ratio))} the deaths per crash. "
            f"Drivers aged 18 to 34: {_times(float(killed_young.ratio))}, from "
            f"{_times(float(involved_young.ratio))} the crashes × "
            f"{_times(float(fatality_young.ratio))} the deaths per crash. Men, per licence holder: "
            f"{_times(float(men_killed.ratio))}, from {_times(float(men_involved.ratio))} the "
            f"crashes, about their extra travel, × {_times(float(men_fatality.ratio))} the deaths "
            "per crash.",
            "DGT driver tables over the driver census and DGT's 2024 kilometres by owner age; "
            "MOVILIA trips by sex as a bounded travel proxy.",
        ),
        (
            "vehicles.html",
            "A heavy truck is ten times a car, or two and a half times, depending on the divisor",
            f"Per circulating vehicle a heavy truck is in a fatal crash {per_vehicle:.1f} times as "
            f"often as a car. Per kilometre driven it is {per_km:.1f} times. For every fatal crash "
            f"a truck is in, {float(truck.occupant_deaths_per_fatal_involvement):.2f} of its own "
            "occupants die, so most of the danger a truck carries is to other people.",
            "DGT's 2022 kilometre estimates divided into the same year's involvement counts, "
            "with exact Poisson intervals.",
        ),
        (
            "speed.html",
            "Where speed is recorded, a crash is twice as likely to kill",
            "Injury crashes in which the police recorded inappropriate speed kill "
            f"{_times(float(adjusted.crude_ratio))} as many people per crash as the rest, and "
            f"{_times(float(adjusted.rate_ratio))} once the comparison is made on the same kind "
            "of road in the same year. That is an association: the record is written after the "
            "fact, and is likelier to be written when someone has died.",
            "DGT's speed-factor report against totals from the microdata for the same provinces, "
            "which reproduce the report's own totals exactly.",
        ),
        (
            "factors.html",
            "Alcohol is rising on interurban roads; distraction cannot be trended in towns",
            "Recorded alcohol went from "
            f"{_fmt_pct(float(alcohol.share_first))} to {_fmt_pct(float(alcohol.share_last))} of "
            f"interurban injury crashes between {int(alcohol.first_year)} and "
            f"{int(alcohol.last_year)}, and inappropriate speed from "
            f"{_fmt_pct(float(speed_share.share_first))} to "
            f"{_fmt_pct(float(speed_share.share_last))} of all of them, both on a consistent "
            "record. Urban distraction jumps and falls by half in single years, and drugs are too "
            "few to compare.",
            "DGT's concurrent-factor tables, with a recording-break rule applied to every "
            "year-to-year change before any trend is read.",
        ),
        (
            "simulator.html",
            "Keeping to today's limits saves more than any single new limit; a higher limit kept "
            "still costs lives",
            "On the published evidence and the speeds measured in Spain, if every driver now "
            "above the limit on autopistas, autovías and conventional roads kept to it, about "
            f"{_fmt_int(-comply.deaths_change)} fewer people a year would die there, "
            f"{_fmt_int(-conventional_comply.deaths_change)} of them on conventional roads; 80 km/h "
            f"on conventional roads would save about {_fmt_int(-conventional.deaths_change)}. "
            "Motorways at 140 km/h with every driver keeping to it would cost "
            f"{_fmt_int(kept_140.deaths_change)}. A validated forecast says the first year's count "
            f"would show full compliance {_chance(comply.power_in_one_year)} and 80 km/h "
            f"{_chance(conventional.power_in_one_year)}.",
            "Spanish baselines and radar speeds, published dose-response evidence and DGT's values "
            "of a life, all sourced; a Poisson forecast tested against machine learning.",
        ),
        (
            "distraction.html",
            "Distraction is in the most fatal crashes; its toll is the least certain",
            "On the police record and the risk measured in cars, removing distraction would save "
            f"about {_fmt_int(lever['distraction'].avoided)} lives a year "
            f"({_fmt_int(lever['distraction'].avoided_low)} to "
            f"{_fmt_int(lever['distraction'].avoided_high)}), "
            f"{_fmt_pct(float(lever['distraction'].share), 0)} of "
            f"{_fmt_int(lever['distraction'].deaths)}: the police record it in "
            f"{_fmt_pct(factor_models.presence('distraction', 'interurban'), 0)} of interurban "
            "fatal crashes, more than any other factor, but a distracted driver is only about "
            "twice as likely to crash. That is the low end: read as a judgement of cause the "
            f"record gives {_fmt_int(upper.record_as_cause)}, and cameras in cars "
            f"{_fmt_int(upper.avoided)}, more than alcohol.",
            "DGT's record of the factors in fatal crashes, with the crash risk measured by "
            "cameras in drivers' own cars (Dingus et al., 2016).",
        ),
        (
            "alcohol-drugs.html",
            "Drink- and drug-driving is the largest avoidable share of deaths on the central "
            "estimates",
            "Without drink- or drug-driving about "
            f"{_fmt_int(lever['alcohol_drugs'].avoided)} fewer people a year would die "
            f"({_fmt_int(lever['alcohol_drugs'].avoided_low)} to "
            f"{_fmt_int(lever['alcohol_drugs'].avoided_high)}), "
            f"{_fmt_pct(float(lever['alcohol_drugs'].share), 0)} of deaths: "
            f"{_fmt_int(by_factor.loc[('alcohol', 'all', 'all')].avoided)} from alcohol and "
            f"{_fmt_int(by_factor.loc[('drugs', 'all', 'all')].avoided)} from drugs. A driver "
            "over the limit is in "
            f"{_fmt_pct(factor_models.presence('alcohol', 'interurban'), 0)} of interurban fatal "
            "crashes where every driver was tested, and most of them are far over it, so almost "
            "all of those deaths are caused by the alcohol.",
            "DGT's record of fatal crashes, the forensic toxicology of killed drivers (INTCF) "
            "and the risks the EU's DRUID project measured.",
        ),
        (
            "enforcement.html",
            "More enforcement against drink- and drug-driving has the strongest case",
            "Removing each factor would save about "
            f"{_fmt_int(lever['alcohol_drugs'].avoided)} lives a year for alcohol and drugs, "
            f"{_fmt_int(lever['speed'].avoided)} for speeding "
            f"({_fmt_int(levers.loc[('speed', 'interurban')].avoided)} on interurban roads) and "
            f"{_fmt_int(lever['distraction'].avoided)} for distraction on the police record. "
            "Breath-test checkpoints, the most studied measure, cut alcohol-related crashes by "
            f"{factor_pages._point('checkpoints_alcohol_crashes')} where they run, and more "
            "often is better. Speed cameras show larger effects, "
            f"{factor_pages._point('section_control')} to {factor_pages._point('fixed_cameras')} "
            "fewer fatal or serious crashes in international reviews, but only near them. Phone "
            "bans have not measurably changed total deaths. Most of every gain is on interurban "
            "roads.",
            "The three models side by side, with the published evaluations of each kind of "
            "enforcement.",
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
    body += table(_split_table(), _SPLIT_CAPTION)
    body += (
        "<p>For older drivers, men and heavy trucks the excess is in how deadly a crash is: the "
        "body that absorbs it, or the mass that strikes the other party. For young drivers, "
        "motorcycles and conventional roads it is mostly in how often crashes happen. The long "
        f"run fell through severity: between {first} and {final} deaths per tonne of road fuel "
        f"fell {_fmt_pct(-per_fuel, 0)}, injury crashes per tonne {_fmt_pct(-frequency, 0)} and "
        f"deaths per injury crash {_fmt_pct(-severity, 0)}, a split that depends on how "
        "completely slight injuries are recorded, though their product does not.</p>"
    )
    body += figure(
        "l3_frequency_severity",
        "Deaths per unit of traffic split into how often crashes happen and how deadly they are",
        captions,
    )
    rural_deaths = simulator.exponent("deaths", "rural")
    rural_crashes = simulator.exponent("injury_crashes", "rural")
    body += (
        "<p>Speed acts on both factors, and more on the second: in the Power Model a 1% rise in "
        f"the average speed on interurban roads brings about {_fmt_pct(1.01**rural_crashes - 1)} "
        f"more injury crashes and {_fmt_pct(1.01**rural_deaths - 1)} more deaths. It is also the "
        "factor on which Spanish drivers stray furthest from the rule: in 2022 "
        f"{_fmt_pct(1 - float(speeds.loc['conventional', 'share_within_limit']), 0)} of cars "
        "measured on conventional roads were above 90 km/h. That is why the site ends with a "
        "simulator of speed laws, set beside models of distraction and of alcohol and drugs, "
        "and says how likely the counts are to show a change.</p>"
    )

    body += "<h2>What this site does not claim</h2>"
    body += (
        "<p>It attributes no cause from Spanish data. The public microdata have one row per "
        "crash and no driver, vehicle or person records, so every factor here is an "
        "association, and a policy or campaign effect is never read off a time series. The "
        "models apply dose-response evidence and crash risks measured elsewhere to Spanish "
        "baselines and to the police record of fatal crashes. Two "
        "analyses built earlier in the project are kept "
        "as supporting material because they are careful but outside this question: a "
        '<a href="severity.html">model of crash severity</a> and a '
        '<a href="policy.html">test of the 2006 points licence</a> whose headline did not '
        "survive its own falsification tests. Road design and municipal hotspots are not "
        "analysed: the files carry no road geometry, traffic volume or coordinates.</p>"
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
        "questions answered from DGT data, each with the denominator that decides it, and "
        "models of speed, distraction and alcohol that ask which enforcement would save most.",
        body,
    )


_SPLIT_CAPTION = (
    "Where the extra deaths come from: each comparison split into how often crashes happen for "
    "the exposure and how deadly a crash is, which multiply to the deaths for the exposure. "
    "Drivers: car drivers in injury crashes and killed (the driver only); vehicles: vehicles in "
    "injury and in fatal crashes; roads and years: injury crashes and deaths"
)


def _split_table() -> pd.DataFrame:
    """Every comparison the site makes, as crashes per exposure times deaths per crash."""
    age = _age_numbers()["ratios"]
    sex = _sex_numbers()["ratios"]
    vehicles = read_table("q6_summary_2022").set_index("group")
    risk = read_table("simulator_class_risk")
    risk_year = int(risk.year.max())
    risk = risk[risk.year == risk_year].set_index("road_class")
    split = read_table("risk_frequency_severity").set_index("year")
    first, final = int(split.index.min()), int(split.index.max())
    speed = _speed_numbers()["pooled"].loc["adjusted"]

    def vehicle(group: str) -> tuple[float, float]:
        row, car = vehicles.loc[group], vehicles.loc["car"]
        crashes = float(row.injury_involvement_per_bn_km / car.injury_involvement_per_bn_km)
        deaths = float(row.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
        return crashes, deaths / crashes

    conventional, motorway = risk.loc["conventional"], risk.loc["motorway"]
    road_crashes = float(conventional.injury_crashes_per_bn_km / motorway.injury_crashes_per_bn_km)
    road_deadly = float(
        (conventional.deaths_per_bn_km / conventional.injury_crashes_per_bn_km)
        / (motorway.deaths_per_bn_km / motorway.injury_crashes_per_bn_km)
    )
    rows = [
        (
            "Car drivers 75+ against 35–54, 2024",
            "km driven",
            float(age.loc[("involved_per_bn_km", "75+"), "ratio"]),
            float(age.loc[("deaths_per_1000_involved", "75+"), "ratio"]),
        ),
        (
            "Car drivers 18–34 against 35–54, 2024",
            "km driven",
            float(age.loc[("involved_per_bn_km", "18-34"), "ratio"]),
            float(age.loc[("deaths_per_1000_involved", "18-34"), "ratio"]),
        ),
        (
            "Male against female car drivers, 2022–2024",
            "licence holder",
            float(sex.loc[("car", "18+", "involved_per_1000_licences"), "ratio"]),
            float(sex.loc[("car", "18+", "deaths_per_1000_involved"), "ratio"]),
        ),
        ("Heavy trucks against cars, 2022", "km driven", *vehicle("heavy_truck")),
        ("Motorcycles against cars, 2022", "km driven", *vehicle("motorcycle")),
        (
            f"Conventional roads against motorways, {risk_year}",
            "km driven",
            road_crashes,
            road_deadly,
        ),
        (
            f"All roads, {final} against {first}",
            "tonne of road fuel",
            float(split.loc[final, "frequency_index"]) / 100,
            float(split.loc[final, "severity_index"]) / 100,
        ),
    ]
    out = []
    for label, per, crashes, deadly in rows:
        out.append(
            {
                "Comparison": label,
                "Per": per,
                "How often crashes happen": _times(crashes),
                "How deadly a crash is": _times(deadly),
                "Deaths": _times(crashes * deadly),
                "Where the excess sits": _where(crashes, deadly),
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
