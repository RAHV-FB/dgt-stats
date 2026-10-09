"""The front page: what the study measures, the way into the tools, its main findings, its pages.

A short opening says what the study measures and how to read its comparisons; a link to the
interactive tools follows. Each main finding is one sentence: its answer, then the number behind
it and, where the number rests on assumptions or a model, what kind of result it is, with links to
the page that sets it out. The detail behind each finding and the analyses' own checks are on
those pages; the list of pages follows the navigation's groups. Every number is read from a
committed result table, and every qualitative sentence is checked against the tables before the
page is written.
"""

from __future__ import annotations

from dgt_stats.exposure_risk import national as national_rates
from dgt_stats.site.components import (
    ALL_PAGES,
    NAV_GROUPS,
    OVERVIEW,
    PAGE_QUESTIONS,
    _fmt_int,
    definition_link,
    esc,
    read_table,
    render_page,
    summary,
)
from dgt_stats.site.numbers import (
    _driver_numbers,
    _long_run_numbers,
    _speed_numbers,
    rate_interval,
)
from dgt_stats.site.regional_common import _year_label

TITLES = dict(ALL_PAGES)


def _require(section: str, checks: dict[str, bool]) -> None:
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"overview ({section}): the tables no longer support: {failed}")


def page_index(captions: dict[str, str]) -> str:
    del captions
    years = read_table("longrun_series").year
    first, last = int(years.min()), int(years.max())
    body = summary(
        "The study measures how road deaths have changed relative to population and traffic, "
        "which drivers are involved in more crashes for the distance they drive, and which "
        "recorded circumstances go with deadlier crashes. Each comparison between an outcome and "
        "a circumstance is an association in the records, not an estimate of what caused it."
    )
    body += (
        '<p class="home-tools"><a href="explore.html">Interactive tools</a> See how often severe '
        "crashes like one you describe were fatal in Catalonia, compare drivers by age or sex, "
        "and explore crashes, deaths and rates by year, region and road.</p>"
    )
    body += "<h2>Main findings</h2>"
    body += '<ul class="findings">'
    body += _deaths()
    body += _drivers()
    body += _speed()
    body += _heavy_vehicles()
    body += "</ul>"
    body += _pages()
    barcelona_year = _year_label(read_table("bcn_person_severity_share"))
    lead = (
        f"An independent statistical study of road deaths and injuries in Spain from {first} to "
        f"{last}, built from official statistics and from police crash records for Catalonia and "
        f"for Barcelona ({barcelona_year})."
    )
    return render_page("index", "Road safety in Spain", lead, body)


def _finding(answer: str, evidence: str, links: list[tuple[str, str]]) -> str:
    """One main finding in one sentence: its answer, then the numbers that support it, and the
    pages that set it out. Each link is ``(target, label)``, the target a page slug with an
    optional ``#section``; an empty label is the page's title."""

    def link(target: str, label: str) -> str:
        page, _, anchor = target.partition("#")
        href = f"{page}.html" + (f"#{anchor}" if anchor else "")
        return f'<a href="{href}">{esc(label or TITLES[page])}</a>'

    more = " · ".join(link(target, label) for target, label in links)
    return (
        f'<li><p><strong>{answer}</strong>: {evidence}</p><p class="finding-more">{more}</p></li>'
    )


def _deaths() -> str:
    headline = read_table("q1_annual_headline").set_index("year").deaths_30d
    first, last = int(headline.index.min()), int(headline.index.max())
    segments = _long_run_numbers()["segments"]
    count = segments[segments.measure == "count"].sort_values("start")
    steep, flat = count.loc[count.annual_change.idxmin()], count.iloc[-1]
    end = int(steep.end)
    fall = 1 - float(headline.loc[end]) / float(headline.loc[first])
    _require(
        "deaths",
        {
            "deaths fell by about three quarters to the steep fall's end": 0.7 < fall < 0.8,
            "the steepest segment of the count ends where the last starts": end == int(flat.start),
            "the count fell in the steepest segment": float(steep.high) < 0,
            "the last segment shows no clear rise or fall": float(flat.low) < 0 < float(flat.high),
        },
    )
    return _finding(
        f"Road deaths fell by about three quarters between {first} and {end} and have shown no "
        "clear rise or fall since",
        f"{_fmt_int(headline.loc[first])} people died in {first}, "
        f"{_fmt_int(headline.loc[end])} in {end} and {_fmt_int(headline.loc[last])} in {last}.",
        [("long-run", ""), ("trends", "")],
    )


def _drivers() -> str:
    """Involvement per kilometre by age, an estimate, and deaths once involved, a count. The
    caveat on the figure for 75 and over is the drivers page's, said once there."""
    numbers = _driver_numbers()
    young, ranges = numbers["central"].loc["18-29"], numbers["ranges"]
    severity = numbers["severity"]
    oldest, reference = severity.loc["75+"], severity.loc["45-64"]
    ratio = float(oldest.killed_per_1000_involved) / float(reference.killed_per_1000_involved)
    _require(
        "drivers",
        {
            "the youngest drivers are involved more per km on every assumption": float(
                ranges.loc["18-29", "min"]
            )
            > 1.2
            and float(young.involved_ratio_low) > 2,
            "drivers aged 75 and over die far more often once involved, clearly": ratio > 2
            and float(oldest.killed_per_1000_involved_low)
            > float(reference.killed_per_1000_involved_high),
        },
    )
    per_km = _finding(
        "Young drivers are in more crashes for the distance they drive",
        "per kilometre, car drivers aged 18–29 were involved in injury crashes, whoever caused "
        f"them, an estimated {float(young.involved_ratio):.2f} times as often as drivers aged "
        f"45–64 in {national_rates.YEAR} (95% {definition_link('Sampling interval')} "
        f"{rate_interval(young, 'involved_ratio')}).",
        [("drivers#involvement-in-crashes-per-kilometre-driven", "Drivers: crashes per kilometre")],
    )
    deaths = _finding(
        "Older drivers are far more likely to die once a crash has happened",
        f"car drivers aged 75 and over involved in an injury crash died {ratio:.1f} times as "
        f"often as those aged 45–64 in {national_rates.YEAR}.",
        [("drivers#deaths-once-a-crash-has-happened", "Drivers: deaths once in a crash")],
    )
    return per_km + deaths


def _speed() -> str:
    pooled = _speed_numbers()["pooled"]
    adjusted = pooled.loc["adjusted"]
    types = pooled.drop(index="adjusted")
    lowest, highest = types.loc[types.rate_ratio.idxmin()], types.loc[types.rate_ratio.idxmax()]
    # The pooled rows carry their period as "first-last".
    first_year, last_year = (int(year) for year in str(adjusted.year).split("-"))
    _require(
        "speed",
        {
            "more deaths per crash where speed is recorded, clearly": float(adjusted.ratio_low) > 1,
            "the pooled ratios and the adjusted one cover the same years": set(
                pooled.year.astype(str)
            )
            == {str(adjusted.year)},
            "every road type has more deaths per crash where speed is recorded": bool(
                (types.ratio_low > 1).all()
            ),
            "the lowest ratio is on dual carriageways and the highest on urban streets": (
                lowest.name == "dual_carriageway" and highest.name == "urban"
            ),
            "the adjusted ratio lies between the road-type ratios": float(lowest.rate_ratio)
            < float(adjusted.rate_ratio)
            < float(highest.rate_ratio),
        },
    )
    return _finding(
        "Crashes in which the police recorded inappropriate speed are deadlier, most of all on "
        "urban streets",
        f"in Spain outside Catalonia and the Basque Country over {first_year}–{last_year}, those "
        f"crashes had {float(adjusted.rate_ratio):.1f} times as many deaths per crash as other "
        "crashes on the same kind of road, from "
        f"{float(lowest.rate_ratio):.1f} times on dual carriageways to "
        f"{float(highest.rate_ratio):.1f} times on urban streets.",
        [("speed", "")],
    )


def _heavy_vehicles() -> str:
    contrasts = read_table("sev_contrasts")
    heavy = contrasts[contrasts.base == "interurban"].set_index(["input", "level"])
    heavy = heavy.loc[("users", "heavy_vehicle")]
    _require(
        "heavy vehicles",
        {
            "a heavy vehicle about doubles the fatal share, clearly": 1.7 < float(heavy.ratio) < 2.3
            and float(heavy.ratio_low) > 1.5,
        },
    )
    return _finding(
        "In Catalonia, severe crashes involving a heavy vehicle were fatal about twice as often",
        "among crashes that killed or seriously injured someone, the Catalan severity model puts "
        f"the fatal share {float(heavy.ratio):.1f} times as high with a lorry or bus involved "
        f"(95% interval {float(heavy.ratio_low):.1f}–{float(heavy.ratio_high):.1f}), other "
        "recorded circumstances held equal; the model has been tested only within Catalonia.",
        [("severity-models", ""), ("validation", "")],
    )


def _pages() -> str:
    """The pages, in the navigation's groups and order, each with what it answers."""
    groups = []
    for index, (group, pages) in enumerate(NAV_GROUPS):
        if group == OVERVIEW:
            continue
        rows = "".join(
            f'<div><dt><a href="{slug}.html">{esc(title)}</a></dt>'
            f"<dd>{esc(PAGE_QUESTIONS[slug])}</dd></div>"
            for slug, title in pages
        )
        groups.append(f'<h3 id="pages-{index}">{esc(group)}</h3><dl class="page-list">{rows}</dl>')
    return "<h2>The pages</h2>" + "".join(groups)
