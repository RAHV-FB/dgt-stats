"""Vehicle types per vehicle and per kilometre driven."""

from __future__ import annotations

import pandas as pd

from dgt_stats.site.components import (
    _fmt_pct,
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


def page_vehicles(captions: dict[str, str]) -> str:
    summary = read_table("q6_summary_2022").set_index("group")
    split = read_table("q6_van_light_truck_split").set_index("group")
    car, truck, bike = summary.loc["car"], summary.loc["heavy_truck"], summary.loc["motorcycle"]
    per_vehicle = float(
        truck.fatal_involvement_per_100k_vehicles / car.fatal_involvement_per_100k_vehicles
    )
    per_km = float(truck.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
    bike_per_km = float(bike.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)

    body = key_figures(
        [
            ("Heavy truck vs car, per vehicle", f"{per_vehicle:.1f}×", "in a fatal crash, 2022"),
            (
                "Heavy truck vs car, per kilometre",
                f"{per_km:.1f}×",
                "the same crashes, distance as the divisor",
            ),
            ("Motorcycle vs car, per kilometre", f"{bike_per_km:.0f}×", "in a fatal crash"),
            (
                "Truck occupants killed",
                f"{float(truck.occupant_deaths_per_fatal_involvement):.2f}",
                "per fatal crash a heavy truck is in; 0.93 for a motorcycle",
            ),
        ]
    )
    body += (
        f'<p class="answer">A heavy truck is in a fatal crash {per_vehicle:.1f} times as often as '
        f"a car per vehicle on the road, and {per_km:.1f} times as often per kilometre driven. "
        "The gap between those two numbers is the difference between blaming the vehicle and "
        "describing how much it is used. Motorcycles move the other way. "
        f"They are driven little, so a modest rate per vehicle becomes {bike_per_km:.0f} times a "
        "car's rate once distance is the divisor.</p>"
    )
    body += figure(
        "v1_per_vehicle_vs_per_km",
        "Ranking of vehicle types in fatal crashes per vehicle and per kilometre",
        captions,
    )

    shown = summary.reset_index()[
        [
            "label",
            "n_vehicles",
            "km_per_vehicle",
            "vehicle_km_bn",
            "fatal_involvement_per_100k_vehicles",
            "fatal_involvement_per_bn_km",
            "occupant_deaths_per_bn_km",
            "occupant_deaths_per_fatal_involvement",
        ]
    ].rename(
        columns={
            "label": "Vehicle type",
            "n_vehicles": "Circulating",
            "km_per_vehicle": "Km per vehicle",
            "vehicle_km_bn": "Billion km",
            "fatal_involvement_per_100k_vehicles": "In fatal crashes per 100,000 vehicles",
            "fatal_involvement_per_bn_km": "In fatal crashes per bn km",
            "occupant_deaths_per_bn_km": "Own occupants killed per bn km",
            "occupant_deaths_per_fatal_involvement": "Own occupants killed per fatal crash",
        }
    )
    shown = shown.sort_values("In fatal crashes per bn km", ascending=False)
    body += table(
        shown,
        "Fleet, kilometres and fatal-crash rates by vehicle type, 2022. Sources: DGT statistical "
        "tables 2022; DGT, Kilómetros recorridos estimados a partir de la ITV 2022",
        {
            "Circulating": "int",
            "Km per vehicle": "int",
            "Billion km": "dec",
            "In fatal crashes per 100,000 vehicles": "dec",
            "In fatal crashes per bn km": "dec",
            "Own occupants killed per bn km": "dec",
            "Own occupants killed per fatal crash": "dec2",
        },
    )
    body += downloads(
        [
            ("q6_summary_2022", "rates by type"),
            ("q6_rates_2022", "rates with intervals, by zone and measure"),
            ("q6_vehicle_km_2022", "fleet and kilometres"),
            ("q6_vehicle_groups", "how the source categories map to these groups"),
            ("q6_van_light_truck_split", "vans and light trucks taken separately"),
        ]
    )

    body += "<h2>How often they crash, and how often a crash is fatal</h2>"
    split_rows = []
    for group, row in summary.sort_values(
        "fatal_involvement_per_bn_km", ascending=False
    ).iterrows():
        crashes = float(row.injury_involvement_per_bn_km / car.injury_involvement_per_bn_km)
        deaths = float(row.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
        split_rows.append(
            {
                "Vehicle type": row.label,
                "In injury crashes per bn km": f"{row.injury_involvement_per_bn_km:,.0f}",
                "Share of those crashes that are fatal": _fmt_pct(
                    float(row.fatal_involvement / row.injury_involvement)
                ),
                "In fatal crashes per bn km": f"{row.fatal_involvement_per_bn_km:.1f}",
                "Crashes per km, against cars": "1 (reference)"
                if group == "car"
                else _times(crashes),
                "Fatal share, against cars": "1 (reference)"
                if group == "car"
                else _times(deaths / crashes),
                "Fatal crashes per km, against cars": "1 (reference)"
                if group == "car"
                else _times(deaths),
            }
        )
    body += table(
        pd.DataFrame(split_rows),
        "Vehicles in injury crashes per kilometre, the share of those crashes that were fatal, "
        "and their product, vehicles in fatal crashes per kilometre, 2022",
    )
    bike_crashes = float(bike.injury_involvement_per_bn_km / car.injury_involvement_per_bn_km)
    truck_crashes = float(truck.injury_involvement_per_bn_km / car.injury_involvement_per_bn_km)
    body += (
        "<p>Per kilometre, the motorcycle's excess is in how often it crashes: "
        f"{_times(bike_crashes)} a car's injury crashes, of which a share only "
        f"{_times(bike_per_km / bike_crashes)} a car's is fatal. The heavy truck is the opposite: it is in "
        f"{_times(truck_crashes)} a car's injury crashes per kilometre, but "
        f"{_times(per_km / truck_crashes)} as many of them are fatal.</p>"
    )

    body += "<h2>Who dies in the crash</h2>"
    body += (
        "<p>The last column of the first table is the second half of the finding. When a motorcycle is "
        f"in a fatal crash, {float(bike.occupant_deaths_per_fatal_involvement):.2f} of its own riders "
        f"are killed on average; for a car {float(car.occupant_deaths_per_fatal_involvement):.2f}; for "
        f"a heavy truck {float(truck.occupant_deaths_per_fatal_involvement):.2f}. A fatal crash "
        "kills at least one person, so a figure of 0.18 means that in most fatal crashes involving "
        "a heavy truck the people killed were in the other vehicle or on foot. A truck's risk per "
        "kilometre is mostly a risk to other people, which is exactly what a measure built from "
        "its own occupants' deaths would miss.</p>"
    )
    van_gap = float(
        split.loc["light_truck", "fatal_involvement_per_bn_km"]
        / split.loc["van", "fatal_involvement_per_bn_km"]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Per vehicle on the road a heavy truck is in a fatal crash "
        f"{per_vehicle:.1f}× as often as a car; per kilometre, {per_km:.1f}×, because each truck "
        f"is driven {float(truck.km_per_vehicle / car.km_per_vehicle):.1f}× as far. Per kilometre "
        f"the motorcycle leads, at {bike_per_km:.0f}×, almost all of it from crashing "
        f"{_times(bike_crashes)} as often; the truck's {per_km:.1f}× is all deadliness, and its "
        f"own occupants are {float(truck.occupant_deaths_per_fatal_involvement):.2f} of the "
        "deaths in each fatal crash it is in, so most of the people it kills are in other "
        "vehicles or on foot: a measure built from a vehicle's own occupants would miss most of "
        "the truck's toll."
    )

    body += limits(
        "Kilometres exist for 2022 only, so this is a cross-section, not a trend. They are "
        "modelled from inspection odometer readings, and DGT's own note says they are valid for "
        "aggregates rather than for individual vehicles. They are annualised over readings taken "
        "across 2014 to 2023, so they describe a normal year imputed to the 2022 fleet rather "
        "than 2022 travel. The two sides of the division do not cover quite the same vehicles: the "
        "crash counts include foreign-registered vehicles, and the kilometres include the "
        "distance Spanish vehicles drive abroad. Vans and light trucks are one group because the "
        f"crash record and the register split them differently; taken apart, light trucks would "
        f"show {van_gap:.0%} of a van's rate per kilometre, a gap with no plausible cause but the "
        "coding. The intervals come from the crash counts and treat the kilometres as known."
    )
    return render_page(
        "vehicles",
        "Vehicle risk per kilometre",
        "How different vehicle types look when the divisor is distance driven rather than the "
        "number of vehicles on the road.",
        body,
    )
