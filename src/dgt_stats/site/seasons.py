"""Seasonal variation in road deaths: deaths by month, as a count and per tonne of road fuel sold,
and the fall in deaths during the lockdown beside road fuel, petrol and toll-motorway traffic."""

from __future__ import annotations

import pandas as pd

from dgt_stats import seasonality
from dgt_stats.site.components import (
    _fmt_int,
    _fmt_pct,
    _join,
    downloads,
    figure,
    limitation,
    read_table,
    render_page,
    summary,
)
from dgt_stats.site.numbers import _season_numbers

FUEL = "road_fuel_tonnes"
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _month_run(months: list[int]) -> str:
    """'February to May' for consecutive months, otherwise 'March, May and June'."""
    if len(months) > 2 and months == list(range(months[0], months[-1] + 1)):
        return f"{MONTHS[months[0] - 1]} to {MONTHS[months[-1] - 1]}"
    return _join([MONTHS[m - 1] for m in months])


def _count_word(value: int) -> str:
    """A small count in words."""
    words = ("two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven")
    return words[value - 2] if 2 <= value <= 11 else str(value)


def _years(years: tuple[int, ...]) -> str:
    """Consecutive years as a range with an en dash, otherwise as a list in words."""
    years = tuple(sorted(years))
    if len(years) > 1 and years == tuple(range(years[0], years[-1] + 1)):
        return f"{years[0]}–{years[-1]}"
    return _join([str(year) for year in years])


def _interval(row: pd.Series) -> str:
    """A month effect's 95% interval, both ends unsigned: '1.06–1.18'."""
    return f"{float(row.low):.2f}–{float(row.high):.2f}"


def page_seasons(captions: dict[str, str]) -> str:
    numbers = _season_numbers()
    effects, lockdown = numbers["effects"], numbers["lockdown"]
    profile = read_table("season_profile").set_index("month")

    def effect(exposure: str, month: int) -> pd.Series:
        return effects.loc[(exposure, month)]

    exposures = sorted(set(effects.index.get_level_values("exposure")))
    if exposures != ["none", FUEL]:
        raise ValueError(f"seasons page: month effects under other exposures: {exposures}")
    july, august = effect("none", 7), effect("none", 8)
    july_fuel, august_fuel = effect(FUEL, 7), effect(FUEL, 8)
    above = [m for m in range(1, 13) if float(effect(FUEL, m).low) > 1]
    below = [m for m in range(1, 13) if float(effect(FUEL, m).high) < 1]
    others_above = [m for m in above if m not in (7, 8)]
    pooled = effect(FUEL, 1)
    first, last = int(pooled.first_year), int(pooled.last_year)
    left_out = sorted(
        set(range(first, last + 1)) - {int(year) for year in str(pooled.years).split()}
    )
    lockdown_year = seasonality.LOCKDOWN_YEAR
    baseline = _years(seasonality.LOCKDOWN_BASELINE)
    april = lockdown.loc[4]
    deaths_fall = float(april.deaths_change)
    traffic_falls = {
        "road fuel sold": float(april.road_fuel_tonnes_change),
        "petrol sold": float(april.petrol_tonnes_change),
        "toll-motorway traffic": float(april.toll_intensity_change),
    }
    # The two months before the state of alarm, against the same months of the baseline.
    before = lockdown.loc[[1, 2]]
    petrol_before = [float(v) for v in before.petrol_tonnes_change]
    toll_before = [float(v) for v in before.toll_intensity_change]
    network_then = float(april.toll_network_km_baseline)
    network_now = float(april.toll_network_km)

    def summer(month: int) -> dict[str, float]:
        return {c: float(profile.loc[month, c]) for c in profile.select_dtypes("number").columns}

    july_index, august_index = summer(7), summer(8)
    # The prose below states each of these; stop if the tables stop supporting them.
    checks = {
        "July and August above the average month per tonne of fuel": 7 in above and 8 in above,
        "the summer excess smaller per tonne than as a count": float(july_fuel.rate_ratio)
        < float(july.rate_ratio)
        and float(august_fuel.rate_ratio) < float(august.rate_ratio),
        "more road fuel is sold in July and August than in the average month": float(
            profile.loc[7, FUEL]
        )
        > 100
        and float(profile.loc[8, FUEL]) > 100,
        "months below the average month per tonne of fuel": bool(below),
        "road fuel sold falls from July to August while petrol rises": float(profile.loc[8, FUEL])
        < float(profile.loc[7, FUEL])
        and float(profile.loc[8, "petrol_tonnes"]) > float(profile.loc[7, "petrol_tonnes"]),
        "April lockdown deaths fell more than road fuel, less than petrol and toll traffic": (
            traffic_falls["road fuel sold"]
            > deaths_fall
            > max(traffic_falls["petrol sold"], traffic_falls["toll-motorway traffic"])
        ),
        "deaths per tonne of road fuel fell in the April lockdown": float(
            april.deaths_per_road_fuel_tonnes_change
        )
        < 0,
        "August deaths below petrol sold and toll-motorway traffic on the index": august_index[
            "deaths_all"
        ]
        < min(august_index["petrol_tonnes"], august_index["toll_intensity"]),
        "July deaths above petrol sold but below toll-motorway traffic on the index": july_index[
            "petrol_tonnes"
        ]
        < july_index["deaths_all"]
        < july_index["toll_intensity"],
        "deaths above road fuel sold in July and August on the index": all(
            index["deaths_all"] > index[FUEL] for index in (july_index, august_index)
        ),
        "petrol and toll traffic above their baseline before the lockdown": min(
            petrol_before + toll_before
        )
        > 0,
        "the toll network was shorter in the lockdown year": network_now < network_then,
        "the pooled years leave out the lockdown year": lockdown_year in left_out,
        "deaths are highest in July and next in August, as a count and on the index": sorted(
            range(1, 13), key=lambda m: -float(effect("none", m).rate_ratio)
        )[:2]
        == [7, 8]
        and list(profile.deaths_all.sort_values(ascending=False).index[:2]) == [7, 8],
        "road fuel sold peaks in July, petrol and toll traffic in August, toll traffic highest": (
            int(profile[FUEL].idxmax()) == 7
            and int(profile.petrol_tonnes.idxmax()) == 8
            and int(profile.toll_intensity.idxmax()) == 8
            and float(profile.loc[8, "toll_intensity"])
            > max(float(profile.loc[8, c]) for c in ("deaths_all", FUEL, "petrol_tonnes"))
        ),
        "deaths above toll traffic in neither summer month": all(
            float(profile.loc[m, "deaths_all"]) < float(profile.loc[m, "toll_intensity"])
            for m in (7, 8)
        ),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"seasons page: the tables no longer support: {failed}")

    def fall(value: float) -> str:
        return _fmt_pct(-value, 0)

    def times(value: float) -> str:
        return f"{float(value):.2f} times"

    others = f" and {_month_run(others_above)} above it" if others_above else ""
    body = summary(
        "Road deaths in Spain peak in summer: compared with an average month of the same year, "
        f"July has {times(july.rate_ratio)} the deaths and August {times(august.rate_ratio)}. "
        "More road fuel is sold in those months, and per tonne of road fuel, the one monthly "
        f"stand-in for traffic that covers all roads, July and August stand lower, at "
        f"{times(july_fuel.rate_ratio)} and {times(august_fuel.rate_ratio)} the average month, "
        "with 95% intervals wholly above it. On the same basis "
        f"{_month_run(below)} are below the average month{others}. In April {lockdown_year}, "
        f"under the lockdown, deaths fell {fall(deaths_fall)} and road fuel sold "
        f"{fall(traffic_falls['road fuel sold'])} against the average April of {baseline}."
    )

    body += "<h2>Deaths peak in July, and the measures of traffic disagree about August</h2>"
    body += figure(
        "m1_season_profile",
        "Index of deaths, road fuel sold, petrol sold and toll-motorway traffic by month of the "
        "year, with the average month at 100. Deaths are highest in July and next in August. "
        "Road fuel sold peaks in July and falls in August, while petrol sold and toll-motorway "
        "traffic peak in August, the motorway traffic furthest above the average month.",
        captions,
    )
    body += (
        "<p>No series counts the kilometres driven on all Spanish roads month by month. Road "
        "fuel sold (petrol plus diesel) is the one series used to divide deaths, standing in "
        "for kilometres as on the annual pages "
        '(<a href="trends.html#road-fuel">road fuel as a measure of traffic</a>). Two '
        "narrower series are shown beside deaths only: petrol sold, which leaves out every "
        "diesel vehicle, and traffic on the state toll motorways, measured directly but on a "
        "small part of the network, as vehicles per kilometre of motorway. The three series "
        "diverge in summer. In the average August, deaths stand at "
        f"{float(profile.loc[8, 'deaths_all']):.0f} on this index, road fuel sold at "
        f"{float(profile.loc[8, FUEL]):.0f} (down from {float(profile.loc[7, FUEL]):.0f} in "
        f"July), petrol sold at {float(profile.loc[8, 'petrol_tonnes']):.0f} (up from "
        f"{float(profile.loc[7, 'petrol_tonnes']):.0f}) and toll-motorway traffic at "
        f"{float(profile.loc[8, 'toll_intensity']):.0f}. Which of them comes closest to the "
        "kilometres driven on all roads is unknown.</p>"
    )

    body += (
        f"<h2>Per tonne of fuel, {_month_run(above)} are above the average month and "
        f"{_month_run(below)} below it</h2>"
    )
    body += figure(
        "m2_month_effects",
        "Deaths in each month against the average month, as a count and per tonne of road "
        "fuel sold, with 95% intervals. As a count, July and August lie furthest above the "
        f"average month; per tonne of fuel, {_month_run(above)} lie above it and "
        f"{_month_run(below)} below it.",
        captions,
    )
    body += (
        f"<p>Per tonne of road fuel, the 95% intervals for July ({_interval(july_fuel)}) and "
        f"August ({_interval(august_fuel)}) lie above 1. {_month_run(below)} lie between "
        f"{times(min(float(effect(FUEL, m).rate_ratio) for m in below))} and "
        f"{times(max(float(effect(FUEL, m).rate_ratio) for m in below))} the average month, "
        "with intervals below 1"
        + (
            f"; {_month_run(others_above)}, at "
            + _join([times(effect(FUEL, m).rate_ratio) for m in others_above])
            + (", has an interval" if len(others_above) == 1 else ", have intervals")
            + " above 1"
            if others_above
            else ""
        )
        + ". The intervals of the other months include the average month.</p>"
        "<p>Each month is compared with the average month of the same year, so the long-run "
        "trend does not enter the seasonal pattern. The intervals allow for monthly counts "
        "that vary more than chance alone would produce. Both versions pool "
        f"{_count_word(int(pooled.n_years))} years from {first} to {last}, leaving out "
        f"{_join([str(year) for year in left_out])}.</p>"
    )

    body += (
        f"<h2>In the April {lockdown_year} lockdown, deaths fell more than road fuel sold and "
        "less than petrol or motorway traffic</h2>"
    )
    body += figure(
        "m3_lockdown",
        f"Change in deaths, road fuel sold, petrol sold and toll-motorway traffic in each month "
        f"of {lockdown_year}, against the same month of {baseline}. In April deaths fell "
        f"{fall(deaths_fall)}, road fuel sold {fall(traffic_falls['road fuel sold'])}, petrol "
        f"sold {fall(traffic_falls['petrol sold'])} and toll-motorway traffic "
        f"{fall(traffic_falls['toll-motorway traffic'])}.",
        captions,
    )
    body += (
        f"<p>April {lockdown_year} was the one full month under the strictest restrictions. "
        f"Against the average April of {baseline}, deaths fell {fall(deaths_fall)}, road fuel "
        f"sold {fall(traffic_falls['road fuel sold'])}, petrol sold "
        f"{fall(traffic_falls['petrol sold'])} and toll-motorway traffic "
        f"{fall(traffic_falls['toll-motorway traffic'])}, so deaths per tonne of road fuel "
        f"fell {fall(float(april.deaths_per_road_fuel_tonnes_change))}. Both narrower series "
        f"were already above their {baseline} level before the lockdown: in January and "
        f"February {lockdown_year} petrol sold was {_fmt_pct(petrol_before[0], 0)} and "
        f"{_fmt_pct(petrol_before[1], 0)} higher and toll-motorway traffic "
        f"{_fmt_pct(toll_before[0], 0)} and {_fmt_pct(toll_before[1], 0)} higher. The toll "
        f"network had also shrunk, from {_fmt_int(network_then)} km on average in the April of "
        f"{baseline} to {_fmt_int(network_now)} km, as concessions expired. Measured from their "
        "level early in the year, the April falls of petrol and toll traffic would be larger "
        "still, so deaths still fell less than both.</p>"
    )

    body += limitation(
        "None of the three series measures kilometres driven on all roads, and the summer "
        "excess reads differently against each. Against road fuel sold, deaths rise more than "
        "fuel sales in July and August; against toll-motorway traffic they rise less in both "
        "months; against petrol sales they rise more in July and less in August. How much of "
        "the summer excess would remain per kilometre is unknown."
    )
    body += downloads(
        [
            ("season_profile", "monthly indices"),
            (
                "season_month_effects",
                "each month against the average month, as a count and per tonne of road fuel",
            ),
            ("season_lockdown", f"{lockdown_year} month by month"),
        ],
        method=("data.html#rates", "rates and denominators"),
    )
    return render_page(
        "seasons",
        "Seasonal variation in road deaths",
        f"Monthly road deaths in Spain from {first} to {last}, set beside sales of road fuel "
        f"and petrol and traffic on the toll motorways, with the {lockdown_year} lockdown "
        "treated separately.",
        body,
    )
