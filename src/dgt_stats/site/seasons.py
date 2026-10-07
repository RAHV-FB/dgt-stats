"""Seasonal variation in road deaths: deaths by month, as a count and per tonne of road fuel sold,
and the fall in deaths during the lockdown beside road fuel, petrol and toll-motorway traffic."""

from __future__ import annotations

import pandas as pd

from dgt_stats import seasonality
from dgt_stats.site.components import (
    _fmt_pct,
    _join,
    _times,
    conclusion,
    downloads,
    figure,
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
        "August deaths below petrol sold and toll-motorway traffic on the index": float(
            profile.loc[8, "deaths_all"]
        )
        < min(float(profile.loc[8, "petrol_tonnes"]), float(profile.loc[8, "toll_intensity"])),
        "the pooled years leave out the lockdown year": lockdown_year in left_out,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"seasons page: the tables no longer support: {failed}")

    def fall(value: float) -> str:
        return _fmt_pct(-value, 0)

    body = summary(
        "Road deaths in Spain peak in summer. Once each year's overall level is removed, July "
        f"has {_times(float(july.rate_ratio))} the deaths of an average month and August "
        f"{_times(float(august.rate_ratio))}. More road fuel is sold in those months, and part "
        "of the excess goes with it. Per tonne of road fuel sold, the one monthly series that "
        f"covers every road and every vehicle, July and August stand at "
        f"{_times(float(july_fuel.rate_ratio))} and {_times(float(august_fuel.rate_ratio))}: "
        "smaller, but with 95% intervals that lie wholly above the average month. On the same "
        f"basis {_month_run(below)} are below the average month"
        + (f" and {_month_run(others_above)} above it" if others_above else "")
        + f". In April {lockdown_year}, under the lockdown, deaths fell "
        f"{fall(deaths_fall)} and road fuel sold {fall(traffic_falls['road fuel sold'])} "
        f"against the average April of {baseline}."
    )

    body += "<h2>Deaths, fuel sales and motorway traffic by month</h2>"
    body += figure(
        "m1_season_profile",
        "Index of deaths, road fuel sold, petrol sold and toll-motorway traffic by month of the "
        "year, with the average month at 100",
        captions,
    )
    body += (
        "<p>No series counts the kilometres driven on all Spanish roads month by month. Road "
        "fuel sold (petrol plus diesel) is the one series used to divide deaths; as on the "
        "annual pages, a rate per tonne of fuel stands "
        'in for a rate per kilometre (<a href="trends.html">Trends since 2019</a>). Two '
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

    body += "<h2>Month effects</h2>"
    body += (
        "<p>The month effects come from a model of monthly deaths with a separate level for "
        "each year, so that the long-run trend does not enter the seasonal pattern. A second "
        "version adds road fuel sold as the denominator, which turns each month effect into "
        "deaths per tonne of fuel against the average month. The intervals allow for monthly "
        "counts that vary more than chance alone would produce. Both versions pool "
        f"{_count_word(int(pooled.n_years))} years from {first} to {last}, leaving out "
        f"{_join([str(year) for year in left_out])}.</p>"
    )
    body += figure(
        "m2_month_effects",
        "Deaths in each month against the average month, as a count and per tonne of road "
        "fuel sold, with 95% intervals",
        captions,
    )
    body += (
        f"<p>Per tonne of road fuel, the 95% intervals for July ({_interval(july_fuel)}) and "
        f"August ({_interval(august_fuel)}) lie above 1. {_month_run(below)} lie between "
        f"{_times(min(float(effect(FUEL, m).rate_ratio) for m in below))} and "
        f"{_times(max(float(effect(FUEL, m).rate_ratio) for m in below))}, with intervals "
        "below 1"
        + (
            f"; {_month_run(others_above)}, at "
            + _join([_times(float(effect(FUEL, m).rate_ratio)) for m in others_above])
            + (", has an interval" if len(others_above) == 1 else ", have intervals")
            + " above 1"
            if others_above
            else ""
        )
        + ". The intervals of the other months include the average month.</p>"
    )

    body += f"<h2>The {lockdown_year} lockdown</h2>"
    body += figure(
        "m3_lockdown",
        f"Change in deaths, road fuel sold, petrol sold and toll-motorway traffic in each month "
        f"of {lockdown_year}, against the same month of {baseline}",
        captions,
    )
    body += (
        f"<p>April {lockdown_year} was the one full month under the strictest restrictions. "
        f"Against the average April of {baseline}, deaths fell {fall(deaths_fall)}, road fuel "
        f"sold {fall(traffic_falls['road fuel sold'])}, petrol sold "
        f"{fall(traffic_falls['petrol sold'])} and toll-motorway traffic "
        f"{fall(traffic_falls['toll-motorway traffic'])}. Deaths therefore fell by more than "
        "road fuel and by less than the two narrower series, and per tonne of road fuel they "
        f"fell {fall(float(april.deaths_per_road_fuel_tonnes_change))}.</p>"
    )

    body += "<h2>What the summer excess means</h2>"
    body += conclusion(
        "Both results depend on the measure set against deaths. Measured against road fuel "
        "sold, deaths rise more than fuel sales in summer and fell more than fuel sales in "
        "the April lockdown. Against petrol sales or toll-motorway traffic, August deaths "
        "stand below both series on the monthly index, and in April deaths fell less than "
        "either. None of these series measures risk per "
        "kilometre driven, so whether each kilometre became more or less dangerous during the "
        "lockdown, and how much of the summer excess would remain per kilometre, is unknown. "
        "The firm result concerns fuel: in July and August more people die on Spanish roads "
        "than the fuel sold in those months would predict."
    )
    body += downloads(
        [
            ("season_profile", "monthly indices"),
            ("season_month_effects", "month effects, as a count and per tonne of road fuel"),
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
