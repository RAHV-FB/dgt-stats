"""Seasonal variation in road deaths: deaths by month, as a count and per tonne of road fuel sold,
and the fall in deaths during the lockdown beside road fuel, petrol and toll-motorway traffic. How
months are compared and the traffic series in detail are technical notes on the methodology page
(``technical_notes``)."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from dgt_stats import seasonality
from dgt_stats.site.components import (
    ALL_PAGES,
    DOCS_URL,
    _fmt_int,
    _fmt_pct,
    _join,
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
TITLES = dict(ALL_PAGES)
# The section of the methodology page that holds this page's technical notes.
NOTES = "seasons-method"


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


def _times(value: float) -> str:
    return f"{float(value):.2f} times"


def _fall(value: float) -> str:
    return _fmt_pct(-value, 0)


def _facts() -> SimpleNamespace:
    """Every figure the page and its technical notes quote, read from the tables, with the checks
    that the sentences built on them still hold."""
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
    # The page and the notes state each of these; stop if the tables stop supporting them.
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
    return SimpleNamespace(**locals())


def page_seasons(captions: dict[str, str]) -> str:
    f = _facts()
    above, below, others_above, effect = f.above, f.below, f.others_above, f.effect
    profile, falls, lockdown_year = f.profile, f.traffic_falls, f.lockdown_year
    fuel_link = '<a href="trends.html#road-fuel">road fuel as a measure of traffic</a>'
    notes_link = f'<a href="data.html#{NOTES}">technical notes</a>'

    body = summary(
        "Road deaths in Spain peak in summer: July has "
        f"{_times(f.july.rate_ratio)} the deaths of the average month and August "
        f"{_times(f.august.rate_ratio)}. Per tonne of road fuel sold, the only monthly measure "
        f"of traffic on all roads, July and August stand at {_times(f.july_fuel.rate_ratio)} "
        f"and {_times(f.august_fuel.rate_ratio)} the average month, still above it, but other "
        "measures of traffic disagree about August. In April "
        f"{lockdown_year}, under the lockdown, deaths fell {_fall(f.deaths_fall)} and road fuel "
        f"sold {_fall(falls['road fuel sold'])}."
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
        "<p>Each month is compared with the average month of the same year, so the long-run "
        "trend does not enter the pattern. Per tonne of road fuel, the 95% intervals for July "
        f"({_interval(f.july_fuel)}) and August ({_interval(f.august_fuel)}) lie above 1. "
        f"{_month_run(below)} lie between "
        f"{_times(min(float(effect(FUEL, m).rate_ratio) for m in below))} and "
        f"{_times(max(float(effect(FUEL, m).rate_ratio) for m in below))} the average month, "
        "with intervals below 1"
        + (
            f"; {_month_run(others_above)}, at "
            + _join([_times(effect(FUEL, m).rate_ratio) for m in others_above])
            + (", has an interval" if len(others_above) == 1 else ", have intervals")
            + " above 1"
            if others_above
            else ""
        )
        + ". The intervals of the other months include the average month.</p>"
    )

    body += (
        "<h2>The measures of traffic disagree about August, so the excess per kilometre is "
        "unknown</h2>"
    )
    body += figure(
        "m1_season_profile",
        "Index of deaths, road fuel sold, petrol sold and toll-motorway traffic by month of the "
        "year, with the average month at 100. Deaths are highest in July and next in August. "
        "Road fuel sold peaks in July and falls in August, while petrol sold and toll-motorway "
        "traffic peak in August, the motorway traffic furthest above the average month.",
        captions,
    )
    body += (
        "<p>No series counts the kilometres driven on all Spanish roads month by month, so road "
        f"fuel sold stands in for them ({fuel_link}). It peaks in July and falls in August, "
        "while petrol sold, which leaves out diesel vehicles, and traffic on the state toll "
        "motorways, a small part of the network, peak in August.</p>"
        "<p>In the average August deaths "
        f"stand at {float(profile.loc[8, 'deaths_all']):.0f} on this index, road fuel sold at "
        f"{float(profile.loc[8, FUEL]):.0f}, petrol sold at "
        f"{float(profile.loc[8, 'petrol_tonnes']):.0f} and toll-motorway traffic at "
        f"{float(profile.loc[8, 'toll_intensity']):.0f}. Which comes closest to the kilometres "
        "driven on all roads is unknown, and so is how much of the summer excess would remain "
        "per kilometre.</p>"
    )

    body += (
        f"<h2>In the April {lockdown_year} lockdown, deaths fell more than road fuel sold and "
        "less than petrol or motorway traffic</h2>"
    )
    body += figure(
        "m3_lockdown",
        f"Change in deaths, road fuel sold, petrol sold and toll-motorway traffic in each month "
        f"of {lockdown_year}, against the same month of {f.baseline}. In April deaths fell "
        f"{_fall(f.deaths_fall)}, road fuel sold {_fall(falls['road fuel sold'])}, petrol "
        f"sold {_fall(falls['petrol sold'])} and toll-motorway traffic "
        f"{_fall(falls['toll-motorway traffic'])}.",
        captions,
    )
    body += (
        f"<p>April {lockdown_year} was the one full month under the strictest restrictions. "
        f"Against the average April of {f.baseline}, deaths fell {_fall(f.deaths_fall)}, road "
        f"fuel sold {_fall(falls['road fuel sold'])}, petrol sold "
        f"{_fall(falls['petrol sold'])} and toll-motorway traffic "
        f"{_fall(falls['toll-motorway traffic'])}, so deaths per tonne of road fuel fell "
        f"{_fall(float(f.april.deaths_per_road_fuel_tonnes_change))}. Petrol and toll traffic "
        f"were already above their {f.baseline} level before the lockdown, so measured from "
        "early in the year their falls would be larger still. The comparison in detail is in "
        f"the {notes_link}.</p>"
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
        method=(f"data.html#{NOTES}", "how months are compared, and the traffic series"),
    )
    return render_page(
        "seasons",
        "Seasonal variation in road deaths",
        f"Monthly road deaths in Spain from {f.first} to {f.last}, set beside sales of road fuel "
        f"and petrol and traffic on the toll motorways, with the {lockdown_year} lockdown "
        "treated separately.",
        body,
    )


def technical_notes(captions: dict[str, str]) -> str:
    """How months are compared, the three measures of traffic and the lockdown comparison in
    detail: one section for the methodology page."""
    del captions
    f = _facts()
    profile, lockdown_year, baseline = f.profile, f.lockdown_year, f.baseline
    seasons = f'<a href="seasons.html">{TITLES["seasons"]}</a>'
    document = f'<a href="{DOCS_URL}/methodology.md">methods document</a>'
    body = (
        f'<h2 id="{NOTES}">{TITLES["seasons"]}: the month model and the traffic series</h2>'
        f"<p>These notes support {seasons}; the {document} gives the full account, in its "
        "section on seasonality and mobility.</p>"
        '<h3 id="seasons-months">How months are compared</h3>'
        "<p>Each month is compared with the average month of the same year, so the long-run "
        "trend does not enter the seasonal pattern; the model compares each month with the "
        "geometric mean of the year's months. The intervals allow for monthly counts that vary "
        "more than chance alone would produce. Both versions, as a count and per tonne of road "
        f"fuel, pool {_count_word(int(f.pooled.n_years))} years from {f.first} to {f.last}, "
        f"leaving out {_join([str(year) for year in f.left_out])}.</p>"
        "<p>The index in the figure of deaths and traffic by month is a simple average of each "
        "year's ratio to its mean month, so it differs a little from the model: the average "
        f"August stands at {float(profile.loc[8, 'deaths_all']):.0f} on the index and at "
        f"{_times(f.august.rate_ratio)} the average month in the model.</p>"
        '<h3 id="seasons-traffic">The three measures of traffic</h3>'
        "<p>Road fuel sold (petrol plus diesel) is the one series used to divide deaths, "
        "standing in for kilometres as on the annual pages. Two narrower series are shown beside "
        "deaths only: petrol sold, which leaves out every diesel vehicle, and traffic on the "
        "state toll motorways, measured directly but on a small part of the network, as vehicles "
        "per kilometre of motorway. On the index road fuel sold falls from "
        f"{float(profile.loc[7, FUEL]):.0f} in July to {float(profile.loc[8, FUEL]):.0f} in "
        f"August, while petrol sold rises from {float(profile.loc[7, 'petrol_tonnes']):.0f} to "
        f"{float(profile.loc[8, 'petrol_tonnes']):.0f}.</p>"
        "<p>The summer excess reads differently against each. Against road fuel sold, deaths "
        "rise more than fuel sales in July and August; against toll-motorway traffic they rise "
        "less in both months; against petrol sales they rise more in July and less in "
        "August.</p>"
        f'<h3 id="seasons-lockdown">The {lockdown_year} lockdown against {baseline}</h3>'
        f"<p>Both narrower series were already above their {baseline} level before the "
        f"lockdown: in January and February {lockdown_year} petrol sold was "
        f"{_fmt_pct(f.petrol_before[0], 0)} and {_fmt_pct(f.petrol_before[1], 0)} higher and "
        f"toll-motorway traffic {_fmt_pct(f.toll_before[0], 0)} and "
        f"{_fmt_pct(f.toll_before[1], 0)} higher. The toll network had also shrunk, from "
        f"{_fmt_int(f.network_then)} km on average in the April of {baseline} to "
        f"{_fmt_int(f.network_now)} km, as concessions expired. Measured from their level early "
        "in the year, the April falls of petrol and toll traffic would be larger still, so "
        "deaths still fell less than both.</p>"
    )
    return body
