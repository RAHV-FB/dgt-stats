"""Seasons and mobility: deaths by month, raw and per tonne of road fuel sold."""

from __future__ import annotations

import pandas as pd

from dgt_stats.site.components import (
    _fmt_pct,
    _join,
    _times,
    conclusion,
    downloads,
    figure,
    key_figures,
    limits,
    read_table,
    render_page,
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
    left_out = sorted(
        set(range(int(pooled.first_year), int(pooled.last_year) + 1))
        - {int(year) for year in str(pooled.years).split()}
    )
    april = lockdown.loc[4]
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
        "months below the average month per tonne of fuel": bool(below),
        "road fuel sold falls from July to August while petrol rises": float(profile.loc[8, FUEL])
        < float(profile.loc[7, FUEL])
        and float(profile.loc[8, "petrol_tonnes"]) > float(profile.loc[7, "petrol_tonnes"]),
        "April 2020 deaths fell more than road fuel, less than petrol and toll traffic": (
            traffic_falls["road fuel sold"]
            > float(april.deaths_change)
            > max(traffic_falls["petrol sold"], traffic_falls["toll-motorway traffic"])
        ),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ValueError(f"seasons page: the tables no longer support: {failed}")

    body = key_figures(
        [
            ("July deaths", _times(float(july.rate_ratio)), "the average month, as a count"),
            (
                "July, per tonne of road fuel",
                _times(float(july_fuel.rate_ratio)),
                "the average month",
            ),
            (
                "August, per tonne of road fuel",
                _times(float(august_fuel.rate_ratio)),
                f"{_times(float(august.rate_ratio))} as a count",
            ),
            (
                "Deaths, April 2020",
                _fmt_pct(float(april.deaths_change), 0),
                f"road fuel sold {_fmt_pct(float(april.road_fuel_tonnes_change), 0)}",
            ),
        ]
    )
    body += (
        '<p class="answer">Road deaths in July and August run '
        f"{_times(float(july.rate_ratio))} and {_times(float(august.rate_ratio))} the average "
        "month. Divided by road fuel sold, the only monthly traffic series that covers every "
        f"road and every vehicle, they are {_times(float(july_fuel.rate_ratio))} and "
        f"{_times(float(august_fuel.rate_ratio))}: smaller, but both still above the average "
        "month, outside their intervals. Per tonne of road fuel, "
        f"{_month_run(below)} are below the average month"
        + (f", and {_month_run(others_above)} above it" if others_above else "")
        + ". Road fuel is fuel sold, not kilometres driven, so these are month effects per "
        "tonne of fuel, not per kilometre.</p>"
    )
    body += figure(
        "m1_season_profile",
        "Deaths and three traffic series by month, average month = 100",
        captions,
    )
    body += (
        "<p>No series counts kilometres on all Spanish roads month by month. Road fuel sold "
        "(petrol plus diesel) covers every road and every vehicle and is the one series used "
        "here as a denominator. Two narrower series are shown beside deaths as traffic indices "
        "only: petrol sold, which leaves out every diesel vehicle, and average daily traffic per "
        "kilometre on the state toll motorways, a small part of the network. They do not move "
        "together. In August the deaths index stands at "
        f"{float(profile.loc[8, 'deaths_all']):.0f}, road fuel sold at "
        f"{float(profile.loc[8, FUEL]):.0f} (down from {float(profile.loc[7, FUEL]):.0f} in "
        f"July), petrol sold at {float(profile.loc[8, 'petrol_tonnes']):.0f} (up from "
        f"{float(profile.loc[7, 'petrol_tonnes']):.0f}) and toll-motorway traffic at "
        f"{float(profile.loc[8, 'toll_intensity']):.0f}. Which of them is closest to "
        "kilometres driven on all roads is not something these data can establish, so neither "
        "narrow series is used to divide all-road deaths.</p>"
    )
    body += figure(
        "m2_month_effects",
        "Month effects on deaths with no exposure and per tonne of road fuel",
        captions,
    )
    body += (
        "<p>With year effects taking out the trend, July's deaths are "
        f"{_times(float(july.rate_ratio))} the average month as a count and "
        f"{_times(float(july_fuel.rate_ratio))} per tonne of road fuel (interval "
        f"{float(july_fuel.low):.2f} to {float(july_fuel.high):.2f}); August's are "
        f"{_times(float(august.rate_ratio))} and {_times(float(august_fuel.rate_ratio))} "
        f"({float(august_fuel.low):.2f} to {float(august_fuel.high):.2f}). Per tonne of road "
        f"fuel, {_month_run(below)} run between "
        f"{min(float(effect(FUEL, m).rate_ratio) for m in below):.2f} and "
        f"{max(float(effect(FUEL, m).rate_ratio) for m in below):.2f}"
        + (
            f", and {_month_run(others_above)} "
            + _join([f"{float(effect(FUEL, m).rate_ratio):.2f}" for m in others_above])
            if others_above
            else ""
        )
        + "; the other months are not distinguishable from the average month.</p>"
    )

    body += "<h2>The 2020 lockdown</h2>"
    body += figure(
        "m3_lockdown", "2020 against 2017–2019, month by month: deaths and traffic", captions
    )
    body += (
        f"<p>In April 2020, the one full month of the strictest lockdown, deaths fell "
        f"{_fmt_pct(-float(april.deaths_change), 0)} on the 2017–2019 average. Road fuel sold "
        f"fell {_fmt_pct(-traffic_falls['road fuel sold'], 0)}, petrol sold "
        f"{_fmt_pct(-traffic_falls['petrol sold'], 0)} and toll-motorway traffic "
        f"{_fmt_pct(-traffic_falls['toll-motorway traffic'], 0)}: deaths fell by more than road "
        "fuel and by less than the two narrower series. Per tonne of road fuel, deaths fell "
        f"{_fmt_pct(-float(april.deaths_per_road_fuel_tonnes_change), 0)}. Without a monthly "
        "count of kilometres on all roads these series cannot say whether each kilometre driven "
        "that month became more or less dangerous, and this page does not claim either.</p>"
    )
    body += downloads(
        [
            ("season_profile", "monthly indices"),
            ("season_month_effects", "month effects, raw and per tonne of road fuel"),
            ("season_lockdown", "2020 month by month"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Per tonne of road fuel sold, the only monthly traffic series that covers every road and "
        f"vehicle, July and August stay above the average month "
        f"({_times(float(july_fuel.rate_ratio))} and {_times(float(august_fuel.rate_ratio))}, "
        f"against {_times(float(july.rate_ratio))} and {_times(float(august.rate_ratio))} as "
        "a count): the summer excess is smaller per tonne of fuel than as a count, but it does "
        f"not disappear. {_month_run(below)} are below the average month per tonne of fuel"
        + (f", and {_month_run(others_above)} above it" if others_above else "")
        + ". These are rates per tonne of fuel sold, not per kilometre driven. In April 2020 "
        f"deaths fell {_fmt_pct(-float(april.deaths_change), 0)}, by more than road fuel sold "
        "and less than petrol sold or toll-motorway traffic; the series cannot tell whether "
        "the roads became more or less dangerous per kilometre that month."
    )
    body += limits(
        "Road fuel is fuel sold by month, not fuel burnt, and it mixes freight with private "
        "travel, so a month effect per tonne is not a month effect per kilometre. Petrol sold "
        "and toll-motorway traffic are shown only as traffic indices: petrol leaves out diesel "
        "vehicles, and the toll network is a small part of the roads that shrank as concessions "
        "expired, which is why its intensity per kilometre is read rather than "
        "vehicle-kilometres. Monthly deaths are small counts, so single months carry wide "
        f"intervals; the month effects pool {int(pooled.n_years)} years from "
        f"{int(pooled.first_year)} to {int(pooled.last_year)}, with "
        f"{_join([str(year) for year in left_out])} left out."
    )
    return render_page(
        "seasons",
        "Seasonality and mobility",
        "Is the summer peak in road deaths only a peak in driving? Divide each month by road "
        "fuel sold, the one monthly traffic series that covers every road, and see what is left.",
        body,
    )
