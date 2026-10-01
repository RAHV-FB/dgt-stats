"""The overview: the seven findings, what connects them, and what the site does not claim."""

from __future__ import annotations

from dgt_stats.site.components import (
    _chance,
    _change,
    _fmt_int,
    _fmt_pct,
    _signed_pct,
    _times,
    figure,
    finding,
    key_figures,
    read_table,
    render_page,
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
    class_risk = read_table("simulator_class_risk")
    risk_year = int(class_risk.year.max())
    latest_risk = class_risk[class_risk.year == risk_year].set_index("road_class")
    risk_ratio = float(
        latest_risk.loc["conventional", "deaths_per_bn_km"]
        / latest_risk.loc["motorway", "deaths_per_bn_km"]
    )
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
                "Killed once in a crash",
                _times(float(fatality_75.ratio)),
                "car drivers 75 and over against 35 to 54; they crash about as often per km",
            ),
            (
                "Deaths per crash with speed",
                _times(float(adjusted.rate_ratio)),
                "against other crashes on the same kind of road",
            ),
            (
                "If every speeder kept to the limit",
                _fmt_int(comply.deaths_change),
                "deaths a year on motorways and conventional roads",
            ),
        ]
    )
    body += (
        '<p class="answer">A count of crashes or deaths says how many. It does not say how '
        "dangerous the roads were, because it moves with how much people drove, who was driving "
        "and in what. This site divides the same DGT counts by residents, licence holders, "
        "vehicles, kilometres and road fuel, and asks what changes. On every question below the "
        "answer changes size, and on several it changes sign. Put together, the answers point "
        "the same way: what decides how many people die is less how often crashes happen than "
        "how hard they are, and the one lever on that which a law reaches is speed.</p>"
    )

    findings = [
        (
            "trends.html",
            "Since 2019, death risk has not measurably changed; serious injury has risen",
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
            "Older and male drivers crash little more for their driving; they die more when they do",
            f"Per kilometre, car drivers aged 75 and over are involved in injury crashes "
            f"{_times(float(involved_75.ratio))} as often as those aged 35 to 54, but are killed "
            f"{_times(float(fatality_75.ratio))} as often once involved. Male car drivers are "
            f"involved {_times(float(men_involved.ratio))} as often as women per licence holder, "
            "about what the only Spanish travel survey by sex implies, and killed "
            f"{_times(float(men_fatality.ratio))} as often once involved.",
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
            "Keeping to today's limits would save more lives than any one new limit",
            "If every driver now above the limit on motorways and conventional roads kept to "
            "it, the Power Model and the speeds measured in Spain put the saving at about "
            f"{_fmt_int(-comply.deaths_change)} lives a year, more than any one new limit with "
            "the typical response; 80 km/h on conventional roads would save about "
            f"{_fmt_int(-conventional.deaths_change)}. A validated forecast says the first year's "
            f"count would show the first {_chance(comply.power_in_one_year)}, the second "
            f"{_chance(conventional.power_in_one_year)}.",
            "Spanish baselines and speeds, published dose-response evidence and DGT's values of "
            "a life, all sourced.",
        ),
    ]
    body += "".join(
        finding(index, href, heading, text, method)
        for index, (href, heading, text, method) in enumerate(findings, start=1)
    )

    body += "<h2>What connects them</h2>"
    body += (
        "<p>Wherever the data let risk be split into how often people crash and how badly they "
        "are hurt when they do, the difference lies in the second. Drivers of 75 and over, and "
        "men, crash about as often as their driving predicts and die far more often once in a "
        "crash. A crash with speed recorded kills twice as often as another on the same kind "
        f"of road. Conventional roads kill {_times(risk_ratio)} as many people per kilometre "
        f"as motorways in {risk_year}, though their traffic is slower. The national series says "
        f"the same about the past: between {first} and {final} deaths per tonne of road fuel "
        f"fell {_fmt_pct(-per_fuel, 0)}, injury crashes per tonne only "
        f"{_fmt_pct(-frequency, 0)}, and deaths per injury crash "
        f"{_fmt_pct(-severity, 0)}.</p>"
    )
    body += figure(
        "l3_frequency_severity",
        "Deaths per unit of traffic split into how often crashes happen and how deadly they are",
        captions,
    )
    body += (
        "<p>How hard a crash is depends on the energy in it and on the body that absorbs it. "
        "Age is the body; speed is the energy, the one a law reaches, the one the evidence "
        "measures best and the one on which Spanish drivers stray furthest from the rule: in "
        "2022 only "
        f"{_fmt_pct(float(speeds.loc['conventional', 'share_within_limit']), 0)} of cars "
        "measured on conventional roads kept to 90 km/h. That is why the last page is a "
        "simulator of speed laws, and why it says how likely the counts are to show it.</p>"
    )

    body += "<h2>What this site does not claim</h2>"
    body += (
        "<p>It attributes no cause from Spanish data. The public microdata have one row per "
        "crash and no driver, vehicle or person records, so every factor here is an "
        "association, and a policy or campaign effect is never read off a time series. The "
        "simulator applies dose-response evidence measured elsewhere to Spanish baselines. Two "
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
        "questions answered from DGT data, each with the denominator that decides it, and a "
        "simulator of speed laws built on what they show.",
        body,
    )
