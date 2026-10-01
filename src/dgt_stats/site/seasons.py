"""Seasons and mobility: how much of a month's deaths is a month's traffic."""

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


def page_seasons(captions: dict[str, str]) -> str:
    numbers = _season_numbers()
    effects, lockdown = numbers["effects"], numbers["lockdown"]
    profile = read_table("season_profile").set_index("month")
    night = read_table("q2_night_share")
    night_year = int(night.year.max())
    night_inter = night[(night.year == night_year) & (night.zone == "interurban")].iloc[0]

    def effect(exposure: str, month: int) -> pd.Series:
        return effects.loc[(exposure, month)]

    july, august = effect("none", 7), effect("none", 8)
    july_petrol, august_petrol = effect("petrol_tonnes", 7), effect("petrol_tonnes", 8)
    july_fuel, august_fuel = effect("road_fuel_tonnes", 7), effect("road_fuel_tonnes", 8)
    august_toll = effect("toll_intensity", 8)
    april = lockdown.loc[4]
    exposures = ("road_fuel_tonnes", "petrol_tonnes", "toll_intensity")
    spring = [float(effect(e, m).rate_ratio) for e in exposures for m in (4, 5)]
    dark = [
        month
        for month in (1, 9, 10, 11, 12)
        if sum(float(effect(e, month).low) > 1 for e in exposures) >= 2
    ]
    month_names = {1: "January", 9: "September", 10: "October", 11: "November", 12: "December"}

    body = key_figures(
        [
            ("July deaths", _times(float(july.rate_ratio)), "the average month, as a count"),
            (
                "July, per unit of petrol",
                _times(float(july_petrol.rate_ratio)),
                "the average month",
            ),
            (
                "August, per unit of petrol",
                _times(float(august_petrol.rate_ratio)),
                f"{_times(float(august.rate_ratio))} as a count",
            ),
            (
                "Deaths, April 2020",
                _fmt_pct(float(april.deaths_change), 0),
                f"petrol {_fmt_pct(float(april.petrol_tonnes_change), 0)}",
            ),
        ]
    )
    body += (
        '<p class="answer">The summer rise in road deaths is mostly more driving. Deaths in July '
        f"and August run {_times(float(july.rate_ratio))} and {_times(float(august.rate_ratio))} "
        "the average month. Per unit of petrol, which in Spain is burnt mostly by private cars "
        f"and motorcycles, they are {_times(float(july_petrol.rate_ratio))} and "
        f"{_times(float(august_petrol.rate_ratio))}: August's excess disappears and July's "
        "shrinks to a few per cent. What survives the allowance for traffic is elsewhere in the "
        "year: spring has fewer deaths per unit of traffic under every measure, and "
        + _join([month_names[m] for m in dark])
        + " more under at least two of the three.</p>"
    )
    body += figure(
        "m1_season_profile",
        "Deaths and three traffic series by month, average month = 100",
        captions,
    )
    body += (
        "<p>No series counts kilometres on all Spanish roads month by month, so three stand in "
        "for it, each wrong in a known direction. Road fuel includes freight diesel, which slows "
        f"in the August industrial holiday, so it rises only to {float(profile.loc[8, 'road_fuel_tonnes']):.0f} "
        "in August. Traffic on the state toll motorways, mostly long-distance holiday routes, "
        f"rises to {float(profile.loc[8, 'toll_intensity']):.0f}. Petrol sits between them at "
        f"{float(profile.loc[8, 'petrol_tonnes']):.0f}. The truth for the whole network lies "
        "somewhere in that range, which is why the answer is given under all three.</p>"
    )
    body += figure(
        "m2_month_effects",
        "Month effects on deaths with no exposure and per unit of each traffic series",
        captions,
    )
    body += (
        "<p>With year effects taking out the trend, July's deaths are "
        f"{_times(float(july.rate_ratio))} the average month as a count, "
        f"{_times(float(july_fuel.rate_ratio))} per unit of road fuel and "
        f"{_times(float(july_petrol.rate_ratio))} per unit of petrol; August's are "
        f"{_times(float(august.rate_ratio))}, {_times(float(august_fuel.rate_ratio))} and "
        f"{_times(float(august_petrol.rate_ratio))}, and per unit of toll-motorway traffic "
        f"{_times(float(august_toll.rate_ratio))}. April and May run between "
        f"{min(spring):.2f} and {max(spring):.2f} under every proxy. "
        + _join([month_names[m] for m in dark])
        + " carry more deaths per unit of traffic under at least two of the three, and the "
        "winter months under some. That is consistent with longer hours of darkness: in the "
        f"microdata for {night_year}, darkness holds "
        f"{_fmt_pct(float(night_inter.night_crash_share), 0)} of interurban injury crashes but "
        f"{_fmt_pct(float(night_inter.night_death_share), 0)} of interurban deaths. These series "
        "do not show darkness to be the cause.</p>"
    )

    body += "<h2>The lockdown as a natural experiment</h2>"
    body += figure(
        "m3_lockdown", "2020 against 2017–2019, month by month: deaths and traffic", captions
    )
    body += (
        f"<p>In April 2020, the one full month of the strictest lockdown, deaths fell "
        f"{_fmt_pct(-float(april.deaths_change), 0)} on the 2017–2019 average. Road fuel fell "
        f"{_fmt_pct(-float(april.road_fuel_tonnes_change), 0)}, petrol "
        f"{_fmt_pct(-float(april.petrol_tonnes_change), 0)} and toll-motorway traffic "
        f"{_fmt_pct(-float(april.toll_intensity_change), 0)}. The fall in deaths was the size of "
        "the fall in traffic. Whether each remaining kilometre became more or less dangerous "
        "depends on which proxy is believed: per unit of road fuel deaths fell "
        f"{_fmt_pct(-float(april.risk_change_road_fuel_tonnes), 0)}, per unit of petrol they "
        f"rose {_fmt_pct(float(april.risk_change_petrol_tonnes), 0)}. The data cannot settle "
        "it, and this page does not claim either.</p>"
    )
    body += downloads(
        [
            ("season_profile", "monthly indices"),
            ("season_month_effects", "month effects under each exposure"),
            ("season_lockdown", "2020 month by month"),
        ]
    )
    body += "<h2>Conclusion</h2>"
    body += conclusion(
        "Most of the summer peak in road deaths is a peak in driving: per unit of private-car "
        "fuel, August is an ordinary month and July only slightly worse. The seasonal pattern "
        "that is not explained by volume runs the other way from the headlines: spring is "
        "safer per unit of traffic and autumn riskier. The 2020 collapse in "
        "deaths was a collapse in traffic, and is not evidence that the roads became safer."
    )
    body += limits(
        "The traffic series are proxies: fuel sales by month, not fuel burnt, and toll traffic "
        "on a network that shrank as concessions expired, which is why intensity per kilometre "
        "is used rather than vehicle-kilometres. Monthly deaths are small counts, about 100 to "
        "200, so single months carry wide intervals; the month effects pool nine years."
    )
    return render_page(
        "seasons",
        "Seasonality and mobility",
        "Is the summer peak in road deaths a peak in danger, or in driving? Divide each month by "
        "three measures of traffic and see what is left.",
        body,
    )
