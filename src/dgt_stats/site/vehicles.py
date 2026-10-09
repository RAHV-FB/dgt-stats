"""Vehicle types compared per vehicle on the road and per kilometre driven.

The page gives the three results: the ranking of vehicle types depends on the denominator; the
motorcycle's excess per kilometre is one of frequency and the heavy truck's one of severity; and
most of the people killed in heavy-truck crashes were outside the truck. ``technical_notes``
gives the methodology page the fleet and kilometres behind the rates and how the crash counts and
the kilometres are matched. Every sentence is checked against the tables (``_facts``) before
either is written.
"""

from __future__ import annotations

from types import SimpleNamespace

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
)

# The section of the methodology page that holds this page's technical notes.
NOTES_ANCHOR = "vehicle-kilometres"


def _page_name(slug: str) -> str:
    """A page's name as the navigation gives it, so a link never types a year of its own."""
    return {s: name for _, pages in NAV_GROUPS for s, name in pages}[slug]


def _x(value: float) -> str:
    """A ratio to cars, to one decimal: the rates rest on one year of modelled kilometres.

    Every ratio on the page uses this one precision.
    """
    return f"{value:.1f} times"


# A non-breaking space keeps a weight class on one line ("3,500 kg") when a label wraps.
NBSP = " "


def _label(text: object) -> str:
    """A vehicle type's label, with its weight class kept on one line."""
    return str(text).replace(" kg", NBSP + "kg")


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the tables, with the checks
    that the sentences built on them still hold."""
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

    # Each sentence of the page and its notes describes one of these directions; stop if the
    # tables no longer show it.
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
    return SimpleNamespace(**locals())


def page_vehicles(captions: dict[str, str]) -> str:
    f = _facts()
    year, truck, car = f.year, f.truck, f.car

    body = summary(
        f"In {year} a heavy truck ({_label(f.truck_class)}) was involved in a fatal crash "
        f"{_x(f.per_vehicle)} as often as a car per vehicle on the road, but {_x(f.per_km)} per "
        f"kilometre, as it is driven {_x(f.truck_distance)} as far. Per kilometre, motorcycles "
        f"had the highest rate, {_x(f.bike_per_km)} a car's, mostly because they are in more "
        "crashes; heavy trucks are in fewer, but more of them are fatal, and most of those killed "
        "were outside the truck."
    )

    body += '<h2 id="ranking">The ranking depends on the denominator</h2>'
    body += (
        "<p>Per vehicle on the road, buses and heavy trucks have the highest rates of "
        "involvement in fatal crashes. Per kilometre, motorcycles do: a motorcycle is driven "
        f"{_fmt_int(f.bike.km_per_vehicle)} km a year against a car's "
        f"{_fmt_int(car.km_per_vehicle)}, so its rate rises from {_x(f.bike_per_vehicle)} a "
        f"car's per vehicle to {_x(f.bike_per_km)} per kilometre, and its 95% interval is clear "
        "of every other type's. Mopeds and buses come next, but "
        f"their rates rest on few vehicles in fatal crashes ({_fmt_int(f.next_two['moped'])} and "
        f"{_fmt_int(f.next_two['bus'])}) and their intervals overlap, so their order is not "
        "established.</p>"
    )
    body += figure(
        "v1_per_vehicle_vs_per_km",
        f"Slope chart of six vehicle types ranked by involvement in fatal crashes in {year}, "
        "per 100,000 vehicles on the left and per billion kilometres on the right. Buses and "
        "heavy trucks rank first and second per vehicle but fall per kilometre, where "
        "motorcycles rise to the top, followed by mopeds and buses.",
        captions,
    )

    order = f.order
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
        f"<p>Motorcycles are involved in {_x(f.bike_crashes)} as many injury crashes per "
        "kilometre as cars, and the share of those crashes that are fatal is "
        f"{_x(f.bike_fatal_share)} a car's: their excess is mostly one of frequency. Heavy trucks "
        f"are in fewer injury crashes per kilometre than cars ({_x(f.truck_crashes)} a car's "
        f"rate), but the share that are fatal is {_x(f.truck_fatal_share)} a car's: their excess "
        "is one of severity. Both profiles describe each vehicle as it is used, with the roads, "
        "drivers and journeys that go with it.</p>"
    )

    body += '<h2 id="who-dies">Most deaths in heavy-truck crashes were outside the truck</h2>'
    body += (
        "<p>Involvement counts the crash, whoever died in it. Counting only each vehicle's own "
        "occupants, the deaths per vehicle in a fatal crash average "
        f"{f.truck_occupants:.2f} for a heavy truck, {f.car_occupants:.2f} for a car and "
        f"{f.bike_occupants:.2f} for a motorcycle. A figure of {f.truck_occupants:.2f} means "
        f"that for at least {_fmt_pct(1 - f.truck_occupants, 0)} of the heavy trucks in fatal "
        "crashes, nobody in the truck died: everyone killed was in another vehicle or on "
        "foot.</p>"
    )
    body += table(
        pd.DataFrame(
            {
                "Vehicle type": [_label(label) for label in order.label],
                "Killed per billion km": order.occupant_deaths_per_bn_km,
                "Killed per vehicle in a fatal crash": order.occupant_deaths_per_fatal_involvement,
            }
        ),
        f"Deaths of each vehicle's own occupants, by vehicle type, Spain, {year}.",
        {
            "Killed per billion km": "dec",
            "Killed per vehicle in a fatal crash": "dec2",
        },
    )
    body += (
        "<p>Counted by the deaths of their own occupants, heavy trucks have about the same rate "
        f"per kilometre as cars ({float(truck.occupant_deaths_per_bn_km):.1f} against "
        f"{float(car.occupant_deaths_per_bn_km):.1f} per billion km; the 95% intervals "
        f"overlap). Counted by involvement in fatal crashes, their rate is {_x(f.per_km)} a "
        "car's. A measure built from occupant deaths alone would miss most of the deaths in "
        "crashes involving heavy trucks.</p>"
        "<p>Explore the deaths of each road-user group, from motorcyclists to the occupants of "
        "heavy vehicles, by year, region, road type and crash type in the "
        '<a href="crash-explorer.html">crash statistics explorer</a>.</p>'
    )
    body += limitation(
        f"The kilometres are DGT's modelled estimates for {year}, valid for aggregates rather "
        "than for individual vehicles, and cover all roads, so rates per kilometre cannot be "
        "split between urban and interurban roads. The crash counts include foreign-registered "
        "vehicles and the kilometres do not, which bears most on heavy trucks and buses "
        f'(<a href="data.html#{NOTES_ANCHOR}">how counts and kilometres are matched</a>).'
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


def technical_notes(captions: dict[str, str]) -> str:
    """The fleet and kilometres behind the vehicles page's rates, and how the crash counts and
    the kilometres are matched: one section of the methodology page."""
    del captions
    f = _facts()
    year, order = f.year, f.order
    fleet = pd.DataFrame(
        {
            "Vehicle type": [_label(label) for label in order.label],
            "Vehicles in circulation": order.n_vehicles,
            "Km per vehicle a year": order.km_per_vehicle,
        }
    )
    return (
        f'<h2 id="{NOTES_ANCHOR}">Vehicle types: fleet, kilometres and crash counts</h2>'
        '<p>The rates on the <a href="vehicles.html">vehicles page</a> divide DGT\'s counts of '
        f"vehicles involved in injury and fatal crashes in {year} by the vehicles in circulation "
        "and by the kilometres they were driven. DGT models the kilometres from odometer readings "
        "taken at roadworthiness inspections over several years, annualised and attached to the "
        f"{year} fleet, and describes them as valid for aggregates rather than for individual "
        "vehicles.</p>"
        + table(
            fleet,
            f"Vehicles in circulation and distance driven, by vehicle type, Spain, {year}: the "
            "denominators of the rates on the vehicles page, whose result tables give the rates "
            "with their crash counts and 95% intervals.",
            {"Vehicles in circulation": "int", "Km per vehicle a year": "int"},
        )
        + "<p>Quadricycles count with mopeds and motorcycles in the kilometres but among other "
        "vehicles in the crash tables. Vans and light trucks form one group because the crash "
        "records and the vehicle register divide them differently; taken apart, light trucks "
        f"would have {_fmt_pct(f.van_gap, 0)} of a van's rate per kilometre, and the data cannot "
        "show how much of that gap is real and how much comes from the split.</p>"
        "<p>DGT's later release gives mean kilometres by vehicle type for "
        f"{_join([str(y) for y in f.later_km_years])} on the same basis (see "
        f'<a href="trends.html#road-fuel">{_page_name("trends")}</a>); the vehicles page matches '
        f"the crash tables and the kilometres for {year} only. The kilometres cover all roads, so "
        "rates per kilometre cannot be split between urban and interurban roads.</p>"
        "<p>The crash counts include foreign-registered vehicles driven in Spain, while the "
        "kilometres are those of Spanish-registered vehicles, including their travel abroad. The "
        "size of that mismatch cannot be measured from these sources, and its direction is "
        "unknown. It bears most on the rates of heavy trucks and buses, the types used for "
        "international haulage and coach travel. The intervals in the result tables reflect "
        "the crash counts only and treat the kilometres as exact.</p>"
    )
