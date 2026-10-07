"""Vehicle types compared per vehicle on the road and per kilometre driven."""

from __future__ import annotations

import re

import pandas as pd

from dgt_stats.site.components import (
    NAV_GROUPS,
    _fmt_int,
    _fmt_pct,
    downloads,
    figure,
    limitation,
    read_table,
    render_page,
    summary,
    table,
    technical,
)


def _page_name(slug: str) -> str:
    """A page's name as the navigation gives it, so a link never types a year of its own."""
    return {s: name for _, pages in NAV_GROUPS for s, name in pages}[slug]


def _x(value: float) -> str:
    """A ratio to cars, to one decimal: the rates rest on one year of modelled kilometres.

    Every ratio on the page, in the prose and in the tables, uses this one precision.
    """
    return f"{value:.1f}×"


def page_vehicles(captions: dict[str, str]) -> str:
    rates = read_table("q6_summary_2022").set_index("group")
    split = read_table("q6_van_light_truck_split").set_index("group")
    year = int(read_table("q6_rates_2022").year.iloc[0])
    car, truck, bike = rates.loc["car"], rates.loc["heavy_truck"], rates.loc["motorcycle"]
    # DGT's two kilometre releases, read from the table that sets them side by side.
    km_years = sorted(
        int(match.group(1))
        for column in read_table("risk_km_crosscheck").columns
        if (match := re.fullmatch(r"billion_km_(\d{4})", column))
    )

    per_vehicle = float(
        truck.fatal_involvement_per_100k_vehicles / car.fatal_involvement_per_100k_vehicles
    )
    per_km = float(truck.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
    bike_per_vehicle = float(
        bike.fatal_involvement_per_100k_vehicles / car.fatal_involvement_per_100k_vehicles
    )
    bike_per_km = float(bike.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
    truck_distance = float(truck.km_per_vehicle / car.km_per_vehicle)
    bike_crashes = float(bike.injury_involvement_per_bn_km / car.injury_involvement_per_bn_km)
    truck_crashes = float(truck.injury_involvement_per_bn_km / car.injury_involvement_per_bn_km)
    bike_fatal_share = bike_per_km / bike_crashes
    truck_fatal_share = per_km / truck_crashes
    truck_occupants = float(truck.occupant_deaths_per_fatal_involvement)
    bike_occupants = float(bike.occupant_deaths_per_fatal_involvement)
    car_occupants = float(car.occupant_deaths_per_fatal_involvement)
    van_gap = float(
        split.loc["light_truck", "fatal_involvement_per_bn_km"]
        / split.loc["van", "fatal_involvement_per_bn_km"]
    )
    top_per_vehicle = set(rates.fatal_involvement_per_100k_vehicles.nlargest(2).index)
    top_per_km = set(rates.fatal_involvement_per_bn_km.nlargest(2).index)

    # Each sentence below describes one of these directions; stop if the tables no longer show it.
    checks = {
        "heavy trucks exceed cars both ways, by less per kilometre": per_vehicle > per_km > 1,
        "a heavy truck is driven further than a car": truck_distance > 1,
        "a motorcycle is driven less than a car, and its ratio rises per kilometre": (
            float(bike.km_per_vehicle) < float(car.km_per_vehicle)
            and 1 < bike_per_vehicle < bike_per_km
        ),
        "buses and heavy trucks lead per vehicle": top_per_vehicle == {"bus", "heavy_truck"},
        "motorcycles and mopeds lead per kilometre": top_per_km == {"motorcycle", "moped"},
        "the motorcycle's excess is mostly frequency": bike_crashes > bike_fatal_share > 1,
        "the heavy truck's excess is severity, by a wide margin": truck_crashes < 1
        and truck_fatal_share > 2,
        "most deaths in heavy-truck fatal crashes are outside the truck": truck_occupants < 0.5,
        "heavy trucks kill fewer of their own occupants per kilometre than cars": float(
            truck.occupant_deaths_per_bn_km
        )
        < float(car.occupant_deaths_per_bn_km),
        "DGT has two kilometre releases, and the comparison uses the earlier": (
            len(km_years) == 2 and km_years[0] == year
        ),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"vehicles page: the tables no longer support: {failed}")
    later_km_year = km_years[1]

    body = summary(
        f"In {year} a heavy truck (over 3,500 kg) was involved in a fatal crash "
        f"{_x(per_vehicle)} as often as a car per vehicle on the road, and {_x(per_km)} as "
        "often per kilometre driven. The two figures differ because each heavy truck is driven "
        f"{_x(truck_distance)} as far as a car. Motorcycles show the opposite pattern. Each is driven "
        f"{_fmt_int(bike.km_per_vehicle)} km a year against {_fmt_int(car.km_per_vehicle)} km "
        f"for a car, so a rate {_x(bike_per_vehicle)} a car's per vehicle becomes "
        f"{_x(bike_per_km)} a car's per kilometre."
    )
    body += (
        "<p>The ranking of vehicle types therefore depends on the denominator. Per vehicle on "
        "the road, buses and heavy trucks have the highest rates of involvement in fatal "
        "crashes; per kilometre, motorcycles and mopeds do.</p>"
    )
    body += figure(
        "v1_per_vehicle_vs_per_km",
        f"Slope chart of six vehicle types ranked by involvement in fatal crashes in {year}, "
        "per 100,000 vehicles on the left and per billion kilometres on the right. Buses and "
        "heavy trucks fall in the ranking and motorcycles and mopeds rise to the top.",
        captions,
    )

    shown = rates.reset_index()[
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
            "n_vehicles": "Vehicles in circulation",
            "km_per_vehicle": "Km per vehicle a year",
            "vehicle_km_bn": "Total distance (billion km)",
            "fatal_involvement_per_100k_vehicles": "In fatal crashes per 100,000 vehicles",
            "fatal_involvement_per_bn_km": "In fatal crashes per billion km",
            "occupant_deaths_per_bn_km": "Own occupants killed per billion km",
            "occupant_deaths_per_fatal_involvement": "Own occupants killed per fatal crash",
        }
    )
    shown = shown.sort_values("In fatal crashes per billion km", ascending=False)
    body += table(
        shown,
        f"Fleet, distance driven, involvement in fatal crashes and occupant deaths by vehicle "
        f"type, Spain, {year}.",
        {
            "Vehicles in circulation": "int",
            "Km per vehicle a year": "int",
            "Total distance (billion km)": "dec",
            "In fatal crashes per 100,000 vehicles": "dec",
            "In fatal crashes per billion km": "dec",
            "Own occupants killed per billion km": "dec",
            "Own occupants killed per fatal crash": "dec2",
        },
    )

    body += "<h2>Frequency for motorcycles, severity for heavy trucks</h2>"
    body += (
        "<p>A rate of fatal crashes per kilometre is the product of involvement in injury "
        "crashes per kilometre and the share of those crashes that were fatal.</p>"
    )
    split_rows = []
    for group, row in rates.sort_values("fatal_involvement_per_bn_km", ascending=False).iterrows():
        crashes = float(row.injury_involvement_per_bn_km / car.injury_involvement_per_bn_km)
        deaths = float(row.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km)
        reference = group == "car"
        split_rows.append(
            {
                "Vehicle type": row.label,
                "In injury crashes per billion km": f"{row.injury_involvement_per_bn_km:,.0f}",
                "Share of those crashes that were fatal": _fmt_pct(
                    float(row.fatal_involvement / row.injury_involvement)
                ),
                "In fatal crashes per billion km": f"{row.fatal_involvement_per_bn_km:.1f}",
                "Injury crashes per km, relative to cars": "1 (reference)"
                if reference
                else _x(crashes),
                "Share fatal, relative to cars": "1 (reference)"
                if reference
                else _x(deaths / crashes),
                "Fatal crashes per km, relative to cars": "1 (reference)"
                if reference
                else _x(deaths),
            }
        )
    body += table(
        pd.DataFrame(split_rows),
        "Involvement in injury crashes per kilometre and the share of those crashes that were "
        f"fatal, by vehicle type, Spain, {year}.",
    )
    body += (
        f"<p>Motorcycles are involved in {_x(bike_crashes)} as many injury crashes per "
        "kilometre as cars, and the share of those crashes that are fatal is only "
        f"{_x(bike_fatal_share)} a car's: their excess is mostly one of frequency. Heavy "
        f"trucks are involved in fewer injury crashes per kilometre than cars "
        f"({_x(truck_crashes)}), but the share of those crashes that are fatal is "
        f"{_x(truck_fatal_share)} a car's: their excess is one of severity. Both profiles "
        "describe each vehicle as it is used, together with the roads, drivers and journeys "
        "that go with it.</p>"
    )

    body += "<h2>Who dies in crashes involving heavy trucks</h2>"
    body += (
        "<p>Involvement counts the crash, whoever died in it. The occupant columns of the first "
        "table count only the deaths of each vehicle's own occupants. Own occupants killed per "
        f"fatal crash average {truck_occupants:.2f} for a heavy truck, {car_occupants:.2f} for "
        f"a car and {bike_occupants:.2f} for a motorcycle. Every fatal crash has at least one "
        f"death, so a figure of {truck_occupants:.2f} means that in at least "
        f"{_fmt_pct(1 - truck_occupants, 0)} of the fatal crashes involving a heavy truck, "
        "nobody in the truck died: everyone killed was in another vehicle or on foot.</p>"
    )
    body += (
        "<p>The choice of measure reverses the comparison with cars. Counted by the deaths of "
        "their own occupants, heavy trucks have a lower rate per kilometre than cars "
        f"({float(truck.occupant_deaths_per_bn_km):.1f} against "
        f"{float(car.occupant_deaths_per_bn_km):.1f} per billion km). Counted by involvement in "
        f"fatal crashes, their rate is {_x(per_km)} a car's. A measure built from occupant deaths "
        "alone would miss most of the deaths in crashes involving heavy trucks.</p>"
    )

    body += limitation(
        f"The kilometres are DGT's estimates for {year}, which DGT describes as valid for "
        "aggregates rather than for individual vehicles. The estimates it published for "
        f"{later_km_year} are built by a different method and cannot be joined to them (see "
        f'<a href="trends.html">{_page_name("trends")}</a>), so the comparison covers a single '
        "year. The kilometres cover all roads, so rates per kilometre cannot be split between "
        "urban and interurban roads. The crash counts and the kilometres cover slightly "
        "different sets of vehicles. The intervals in the result tables reflect the crash "
        "counts only and treat the kilometres as exact."
    )
    body += technical(
        "How the crash counts and the kilometres are matched",
        "<p>DGT models the kilometres from odometer readings taken at roadworthiness "
        f"inspections over several years, annualised and attached to the {year} fleet. The "
        "crash counts include foreign-registered vehicles, and the kilometres include Spanish "
        "vehicles' travel abroad. Quadricycles count with mopeds and motorcycles in the "
        "kilometres but among other vehicles in the crash tables. Vans and light trucks form "
        "one group because the crash records and the vehicle register divide them "
        f"differently; taken apart, light trucks would have {_fmt_pct(van_gap, 0)} of a van's "
        "rate per kilometre, and the data cannot show how much of that gap is real and how "
        "much comes from the split.</p>",
    )
    body += downloads(
        [
            ("q6_summary_2022", "rates by vehicle type"),
            (
                "q6_rates_2022",
                "rates with 95% intervals (urban and interurban roads only as counts and "
                "rates per vehicle)",
            ),
            ("q6_vehicle_km_2022", "fleet and kilometres"),
            ("q6_vehicle_groups", "how the source categories map to these groups"),
            ("q6_van_light_truck_split", "vans and light trucks separately"),
        ],
        method=("data.html#rates", "rates and denominators"),
    )
    return render_page(
        "vehicles",
        "Vehicle type, distance driven and crash severity",
        f"Six vehicle types compared by their involvement in fatal crashes in Spain in {year}, "
        "per vehicle on the road and per kilometre driven, and by who dies in those crashes.",
        body,
    )
