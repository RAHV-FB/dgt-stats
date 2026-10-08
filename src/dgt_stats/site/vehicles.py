"""Vehicle types compared per vehicle on the road and per kilometre driven."""

from __future__ import annotations

import pandas as pd

from dgt_stats.site.components import (
    NAV_GROUPS,
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


def _page_name(slug: str) -> str:
    """A page's name as the navigation gives it, so a link never types a year of its own."""
    return {s: name for _, pages in NAV_GROUPS for s, name in pages}[slug]


def _x(value: float) -> str:
    """A ratio to cars, to one decimal: the rates rest on one year of modelled kilometres.

    Every ratio on the page uses this one precision.
    """
    return f"{value:.1f} times"


# A non-breaking space keeps a weight class on one line ("3,500 kg") when a label wraps.
NBSP = "\u00a0"


def _label(text: object) -> str:
    """A vehicle type's label, with its weight class kept on one line."""
    return str(text).replace(" kg", NBSP + "kg")


def page_vehicles(captions: dict[str, str]) -> str:
    rates = read_table("q6_summary_2022").set_index("group")
    split = read_table("q6_van_light_truck_split").set_index("group")
    year = int(read_table("q6_rates_2022").year.iloc[0])
    car, truck, bike = rates.loc["car"], rates.loc["heavy_truck"], rates.loc["motorcycle"]
    # DGT's kilometre series, as its later release sets it out.
    km_years = sorted(int(year) for year in read_table("risk_km_crosscheck").year)
    # The rates with their 95% intervals, all roads.
    intervals = read_table("q6_rates_2022")
    intervals = intervals[intervals.zone == "all"].set_index(["measure", "group"])

    def bounds(measure: str, group: str) -> tuple[float, float]:
        row = intervals.loc[(measure, group)]
        return float(row.per_billion_km_low), float(row.per_billion_km_high)

    fatal_per_km = rates.fatal_involvement_per_bn_km.sort_values(ascending=False)
    leader, second, third = fatal_per_km.index[:3]

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
    truck_class = str(truck.label).removeprefix("Trucks ")
    order = rates.sort_values("fatal_involvement_per_bn_km", ascending=False)
    next_two = rates.loc[["moped", "bus"], "fatal_involvement"]

    # Each sentence below describes one of these directions; stop if the tables no longer show it.
    checks = {
        "the heavy-truck label names its weight class": truck_class != str(truck.label)
        and truck_class.startswith("over "),
        "heavy trucks exceed cars both ways, by less per kilometre": per_vehicle > per_km > 1,
        "a heavy truck is driven further than a car": truck_distance > 1,
        "a motorcycle is driven less than a car, and its ratio rises per kilometre": (
            float(bike.km_per_vehicle) < float(car.km_per_vehicle)
            and 1 < bike_per_vehicle < bike_per_km
        ),
        "buses and heavy trucks lead per vehicle": top_per_vehicle == {"bus", "heavy_truck"},
        "motorcycles lead per kilometre, clear of every other type's interval": leader
        == "motorcycle"
        and bounds("fatal_involvement", "motorcycle")[0]
        > max(bounds("fatal_involvement", g)[1] for g in fatal_per_km.index[1:]),
        "mopeds and buses come next per kilometre, with overlapping intervals": {second, third}
        == {"moped", "bus"}
        and bounds("fatal_involvement", second)[0] <= bounds("fatal_involvement", third)[1],
        "the next two per kilometre rest on few vehicles in fatal crashes": bool(
            (next_two < 100).all()
        ),
        "the motorcycle's excess is mostly frequency": bike_crashes > bike_fatal_share > 1,
        "the heavy truck's excess is severity, by a wide margin": truck_crashes < 1
        and truck_fatal_share > 2,
        "most deaths in heavy-truck fatal crashes are outside the truck": truck_occupants < 0.5,
        "heavy trucks' own occupants killed per km below cars', with overlapping intervals": float(
            truck.occupant_deaths_per_bn_km
        )
        < float(car.occupant_deaths_per_bn_km)
        and bounds("occupant_deaths", "heavy_truck")[1] >= bounds("occupant_deaths", "car")[0],
        "DGT's kilometre series starts in the year compared here and runs on": (
            len(km_years) > 1 and km_years[0] == year
        ),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"vehicles page: the tables no longer support: {failed}")
    later_km_years = km_years[1:]

    body = summary(
        f"In {year} a heavy truck ({_label(truck_class)}) was involved in a fatal crash "
        f"{_x(per_vehicle)} as often as a car per vehicle on the road, but {_x(per_km)} as "
        f"often per kilometre, because each heavy truck is driven {_x(truck_distance)} as far. "
        f"A motorcycle is driven {_fmt_int(bike.km_per_vehicle)} km a year against a car's "
        f"{_fmt_int(car.km_per_vehicle)} km, so its rate rises from {_x(bike_per_vehicle)} a "
        f"car's per vehicle to {_x(bike_per_km)} per kilometre, the highest of any type. The "
        "motorcycle's excess comes mostly from being in more crashes, the heavy truck's from "
        "more of its crashes being fatal."
    )

    body += '<h2 id="ranking">The ranking depends on the denominator</h2>'
    body += (
        "<p>Per vehicle on the road, buses and heavy trucks have the highest rates of "
        "involvement in fatal crashes. Per kilometre, motorcycles have by far the highest, and "
        "their 95% interval is clear of every other type's. Mopeds and buses come next, but "
        f"their rates rest on few vehicles in fatal crashes ({_fmt_int(next_two['moped'])} and "
        f"{_fmt_int(next_two['bus'])}) and their intervals overlap, so their order is not "
        "established. Figure 1 prints each rate beside its point; the vertical position shows "
        "only the rank.</p>"
    )
    body += figure(
        "v1_per_vehicle_vs_per_km",
        f"Slope chart of six vehicle types ranked by involvement in fatal crashes in {year}, "
        "per 100,000 vehicles on the left and per billion kilometres on the right. Buses and "
        "heavy trucks rank first and second per vehicle but fall per kilometre, where "
        "motorcycles rise to the top, followed by mopeds and buses.",
        captions,
    )
    fleet = pd.DataFrame(
        {
            "Vehicle type": [_label(label) for label in order.label],
            "Vehicles in circulation": order.n_vehicles,
            "Km per vehicle a year": order.km_per_vehicle,
        }
    )
    body += table(
        fleet,
        f"Vehicles in circulation and distance driven, by vehicle type, Spain, {year}. These are "
        "the denominators of the rates in Figure 1; the rates table gives the rates with their "
        "crash counts and 95% intervals.",
        {"Vehicles in circulation": "int", "Km per vehicle a year": "int"},
    )

    body += '<h2 id="frequency-severity">Frequency for motorcycles, severity for heavy trucks</h2>'
    body += (
        "<p>Involvement in fatal crashes per kilometre is the product of two parts: involvement "
        "in injury crashes per kilometre, and the share of those crashes that were fatal.</p>"
    )
    body += table(
        pd.DataFrame(
            {
                "Vehicle type": [_label(label) for label in order.label],
                "In injury crashes per billion km": order.injury_involvement_per_bn_km,
                "Share that were fatal": order.fatal_involvement / order.injury_involvement,
            }
        ),
        "Involvement in injury crashes per kilometre and the share of those crashes that were "
        f"fatal, by vehicle type, Spain, {year}.",
        {
            "In injury crashes per billion km": "int",
            "Share that were fatal": "pct",
        },
    )
    body += (
        f"<p>Motorcycles are involved in {_x(bike_crashes)} as many injury crashes per "
        "kilometre as cars, and the share of those crashes that are fatal is "
        f"{_x(bike_fatal_share)} a car's: their excess is mostly one of frequency. Heavy trucks "
        "are involved in fewer injury crashes per kilometre than cars "
        f"({_x(truck_crashes)} a car's rate), but the share of those crashes that are fatal is "
        f"{_x(truck_fatal_share)} a car's: their "
        "excess is one of severity. Both profiles describe each vehicle as it is used, together "
        "with the roads, drivers and journeys that go with it.</p>"
    )

    body += '<h2 id="who-dies">Most deaths in heavy-truck crashes were outside the truck</h2>'
    body += (
        "<p>Involvement counts the crash, whoever died in it. The table below counts only the "
        "deaths of each vehicle's own occupants. Own occupants killed per fatal crash average "
        f"{truck_occupants:.2f} for a heavy truck, {car_occupants:.2f} for a car and "
        f"{bike_occupants:.2f} for a motorcycle. Every fatal crash has at least one death, so a "
        f"figure of {truck_occupants:.2f} means that in at least "
        f"{_fmt_pct(1 - truck_occupants, 0)} of the fatal crashes involving a heavy truck, "
        "nobody in the truck died: everyone killed was in another vehicle or on foot.</p>"
    )
    body += table(
        pd.DataFrame(
            {
                "Vehicle type": [_label(label) for label in order.label],
                "Killed per billion km": order.occupant_deaths_per_bn_km,
                "Killed per fatal crash": order.occupant_deaths_per_fatal_involvement,
            }
        ),
        f"Deaths of each vehicle's own occupants, by vehicle type, Spain, {year}.",
        {
            "Killed per billion km": "dec",
            "Killed per fatal crash": "dec2",
        },
    )
    body += (
        "<p>Counted by the deaths of their own occupants, heavy trucks have about the same rate "
        f"per kilometre as cars ({float(truck.occupant_deaths_per_bn_km):.1f} against "
        f"{float(car.occupant_deaths_per_bn_km):.1f} per billion km; the 95% intervals "
        f"overlap). Counted by involvement in fatal crashes, their rate is {_x(per_km)} a "
        "car's. A measure built from occupant deaths alone would miss most of the deaths in "
        "crashes involving heavy trucks.</p>"
    )

    body += technical(
        "How the crash counts and the kilometres are matched",
        "<p>DGT models the kilometres from odometer readings taken at roadworthiness "
        f"inspections over several years, annualised and attached to the {year} fleet. "
        "Quadricycles count with mopeds and motorcycles in the "
        "kilometres but among other vehicles in the crash tables. Vans and light trucks form "
        "one group because the crash records and the vehicle register divide them "
        f"differently; taken apart, light trucks would have {_fmt_pct(van_gap, 0)} of a van's "
        "rate per kilometre, and the data cannot show how much of that gap is real and how "
        "much comes from the split.</p>",
    )
    body += limitation(
        f"The kilometres are DGT's estimates for {year}, which DGT describes as valid for "
        "aggregates rather than for individual vehicles. DGT's later release gives mean "
        f"kilometres by vehicle type for {_join([str(y) for y in later_km_years])} on the same "
        f'basis (see <a href="trends.html#road-fuel">{_page_name("trends")}</a>); this page '
        f"matches the crash tables and the kilometres for {year} only. The kilometres cover "
        "all roads, so rates per kilometre cannot be split between urban and interurban roads. "
        "The crash counts include foreign-registered vehicles driven in Spain, while the "
        "kilometres are those of Spanish-registered vehicles, including their travel abroad. "
        "The size of that mismatch cannot be measured from these sources, and its direction is "
        "unknown. It bears most on the rates of heavy trucks and buses, the types used for "
        "international haulage and coach travel. The intervals in the result tables reflect "
        "the crash counts only and treat the kilometres as exact."
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
