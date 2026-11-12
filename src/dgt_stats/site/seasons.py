"""Seasonal variation in road deaths: deaths by month, per day and per tonne of road fuel sold, and
the fall in deaths during the lockdown beside road fuel. How months are compared is a technical
note on the methodology page (``technical_notes``)."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from dgt_stats import seasonality
from dgt_stats.site.components import (
    ALL_PAGES,
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
    fuel_fall = float(april.road_fuel_tonnes_change)

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
        "April lockdown deaths fell more than road fuel sold": fuel_fall > deaths_fall,
        "deaths per tonne of road fuel fell in the April lockdown": float(
            april.deaths_per_road_fuel_tonnes_change
        )
        < 0,
        "deaths above road fuel sold in July and August on the index": all(
            index["deaths_all"] > index[FUEL] for index in (july_index, august_index)
        ),
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
    profile, lockdown_year = f.profile, f.lockdown_year
    fuel_link = '<a href="long-run.html#road-fuel">road fuel as a measure of traffic</a>'

    body = summary(
        "Road deaths in Spain peak in summer: July has "
        f"{_times(f.july.rate_ratio)} the deaths of the average month and August "
        f"{_times(f.august.rate_ratio)}. Per tonne of road fuel sold, the only monthly measure "
        f"of traffic on all roads, July and August stand at {_times(f.july_fuel.rate_ratio)} "
        f"and {_times(f.august_fuel.rate_ratio)} the average month, still above it, but other "
        "measures of traffic disagree about August. In April "
        f"{lockdown_year}, under the lockdown, deaths fell {_fall(f.deaths_fall)} and road fuel "
        f"sold {_fall(f.fuel_fall)}."
    )

    body += (
        f"<h2>Per tonne of fuel, {_month_run(above)} are above the average month and "
        f"{_month_run(below)} below it</h2>"
    )
    body += figure(
        "m2_month_effects",
        "Deaths in each month against the average month, per day and per tonne of road "
        "fuel sold, with 95% intervals. Per day, July and August lie furthest above the "
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

    body += f"<h2>In the April {lockdown_year} lockdown, deaths fell more than road fuel sold</h2>"
    body += figure(
        "m3_lockdown",
        f"Change in deaths and in road fuel sold in each month of {lockdown_year}, against the "
        f"same month of {f.baseline}. In April deaths fell {_fall(f.deaths_fall)} and road fuel "
        f"sold {_fall(f.fuel_fall)}.",
        captions,
    )
    body += (
        f"<p>April {lockdown_year} was the one full month under the strictest restrictions. "
        f"Against the average April of {f.baseline}, deaths fell {_fall(f.deaths_fall)} and road "
        f"fuel sold {_fall(f.fuel_fall)}, so deaths per tonne of road fuel fell "
        f"{_fall(float(f.april.deaths_per_road_fuel_tonnes_change))}.</p>"
    )

    body += downloads(
        [
            ("season_profile", "monthly indices"),
            (
                "season_month_effects",
                "each month against the average month, per day and per tonne of road fuel",
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
    """How months are compared and the traffic series: one section for the methodology page."""
    del captions
    f = _facts()
    seasons = f'<a href="seasons.html">{TITLES["seasons"]}</a>'
    return (
        f'<h2 id="{NOTES}">{TITLES["seasons"]}: the month model and the traffic series</h2>'
        f"<p>These notes support {seasons}.</p>"
        "<p>Each month is compared with the average month of the same year, by a quasi-Poisson "
        "regression of monthly deaths on year and month, with the days in the month, or road "
        f"fuel sold, as the offset. It pools {_count_word(int(f.pooled.n_years))} years from "
        f"{f.first} to {f.last}, leaving out {_join([str(year) for year in f.left_out])}. "
        "The index in the figure of deaths and traffic by month averages each year's ratio to "
        "its mean month, so it differs a little from the model.</p>"
        "<p>Road fuel sold is the one series that divides deaths. Petrol sold, which leaves out "
        "diesel vehicles, and traffic on the state toll motorways, a small part of the network, "
        "are shown beside deaths only.</p>"
    )
