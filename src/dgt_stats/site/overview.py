"""The front page: the study's answer in two sentences, its main findings, and its pages.

Each finding leads with its answer in one sentence, then the numbers behind it and a link to the
page that sets it out; the methods are left to the pages behind them. The list of pages follows
the navigation's groups. Every number is read from a committed result table, and every
qualitative sentence is checked against the tables before the page is written.
"""

from __future__ import annotations

import math

from dgt_stats.exposure_risk import national as national_rates
from dgt_stats.site.components import (
    NAV_GROUPS,
    PAGE_QUESTIONS,
    _fmt_int,
    _fmt_pct,
    esc,
    read_table,
    render_page,
    summary,
)
from dgt_stats.site.numbers import (
    _driver_numbers,
    _long_run_numbers,
    _risk_numbers,
    _speed_numbers,
)

NUMBER_WORDS = {0: "none", 1: "one", 2: "two", 3: "all three"}

# The three models trained on the regional records, in the order the page names them.
REGIONAL_MODELS = (
    "catalonia_crash_severity",
    "barcelona_person_severity",
    "barcelona_crash_severity",
)


def _require(section: str, checks: dict[str, bool]) -> None:
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"overview ({section}): the tables no longer support: {failed}")


def _link(href: str, text: str) -> str:
    return f'<a href="{href}">{text}</a>'


def page_index(captions: dict[str, str]) -> str:
    national_years = read_table("longrun_series").year
    first, last = int(national_years.min()), int(national_years.max())
    headline = read_table("q1_annual_headline").set_index("year").deaths_30d
    segments = _long_run_numbers()["segments"]
    count = segments[segments.measure == "count"].sort_values("start")
    steep_end = int(count.loc[count.annual_change.idxmin()].end)
    fall = 1 - float(headline.loc[steep_end]) / float(headline.loc[first])
    _require(
        "opening",
        {
            "deaths fell by about three quarters to the end of the steep decline": 0.7 < fall < 0.8,
            "the latest count is above the end of the steep decline": float(headline.loc[last])
            > float(headline.loc[steep_end]),
        },
    )
    body = summary(
        f"Road deaths in Spain fell by about three quarters between {first} and {steep_end} and "
        f"have not fallen since: {_fmt_int(headline.loc[last])} people died in {last}. The "
        "findings below come from official statistics and police crash records. Every "
        "comparison between an outcome and a circumstance is an association in those records, "
        "not an estimate of what caused it."
    )
    body += "<h2>Main findings</h2>"
    body += '<ul class="findings">'
    body += _long_run()
    body += _drivers()
    body += _speed()
    body += _models()
    body += "</ul>"
    body += _explore()
    lead = (
        f"An independent statistical study of road deaths and injuries in Spain from {first} to "
        f"{last}, built from official statistics and from police crash records for Catalonia and "
        "Barcelona."
    )
    return render_page("index", "Road safety in Spain", lead, body)


def _finding(lead: str, text: str, links: list[tuple[str, str]]) -> str:
    """One main finding: its answer in one sentence, what supports it, and the pages that set
    it out. Each link is ``(target, label)``, the target a page slug with an optional
    ``#section``."""

    def href(target: str) -> str:
        page, _, anchor = target.partition("#")
        return f"{page}.html" + (f"#{anchor}" if anchor else "")

    more = " · ".join(_link(href(target), label) for target, label in links)
    return f'<li><p><strong>{lead}</strong> {text}</p><p class="finding-more">{more}</p></li>'


def _long_run() -> str:
    long_run = _long_run_numbers()
    segments = long_run["segments"]
    count = segments[segments.measure == "count"].sort_values("start")
    steep = count.loc[count.annual_change.idxmin()]
    flat = count.iloc[-1]
    headline = read_table("q1_annual_headline").set_index("year").deaths_30d
    first = int(headline.index.min())
    risk = _risk_numbers()
    latest, last, base = risk["latest"], risk["last"], risk["base"]
    deaths = latest.xs("deaths_30d", level="outcome")
    split = read_table("risk_frequency_severity").set_index("year")
    split_first, split_last = int(split.index.min()), int(split.index.max())
    end = split.loc[split_last]
    per_fuel = float(end.deaths_per_fuel_index) / 100
    severity = float(end.severity_index) / 100
    frequency = float(end.frequency_index) / 100
    admitted = float(end.hospitalised_per_fuel_index) / 100
    per_admission = float(end.deaths_per_hospitalised_index) / 100
    _require(
        "long run",
        {
            "the steepest segment of the count ends where the last starts": int(steep.end)
            == int(flat.start),
            "the count fell in the steep segment": float(steep.high) < 0,
            "the last segment shows no clear rise or fall": float(flat.low) < 0 < float(flat.high),
            "most of the fall to the end of the steep segment came within it": float(
                headline.loc[int(steep.start)] - headline.loc[int(steep.end)]
            )
            > 0.5 * float(headline.loc[first] - headline.loc[int(steep.end)]),
            "more people died in the latest year than at the end of the steep segment": float(
                deaths.loc["count", "count"]
            )
            > float(headline.loc[int(steep.end)]),
            "no denominator shows a change in deaths beyond an ordinary year in the last year": all(
                float(row.ratio_low_yty) <= 1 <= float(row.ratio_high_yty)
                for _, row in deaths.iterrows()
            ),
            "each split multiplies to deaths per tonne of fuel": math.isclose(
                frequency * severity, per_fuel, rel_tol=1e-6
            )
            and math.isclose(admitted * per_admission, per_fuel, rel_tol=1e-6),
            "the two splits disagree: by crashes mostly severity, by admissions all frequency": (
                severity < frequency < 1 and admitted < per_fuel < 1 < per_admission
            ),
            "deaths per tonne of fuel fell by about three quarters": 0.7 < 1 - per_fuel < 0.8,
        },
    )
    projections = read_table("longrun_projection_sensitivity")
    other_start = f"start_{int(flat.start)}"
    per_fuel_recent = projections[
        (projections.measure == "road_fuel")
        & projections.variant.isin(["main", other_start])
        & projections.year.isin([last - 1, last])
    ].ratio
    _require(
        "recent years",
        {
            "per tonne of fuel, the last two years are above the projected trend on both starts": bool(
                (per_fuel_recent > 1).all()
            ),
            "both trend starts are present": len(per_fuel_recent) == 4,
        },
    )
    trend = _finding(
        f"Deaths fell steeply until {int(steep.end)} and have levelled off since.",
        f"Road deaths fell from {_fmt_int(headline.loc[first])} in {first} to "
        f"{_fmt_int(headline.loc[int(steep.end)])} in {int(steep.end)}, most of the fall coming "
        f"between {int(steep.start)} and {int(steep.end)}; since {int(flat.start)} the trend "
        f"shows no clear rise or fall, and {_fmt_int(deaths.loc['count', 'count'])} people died "
        f"in {last}. Against {base}, the count of deaths and every death rate changed by no more "
        "than ordinary year-to-year variation. Against the falling trend of the 2010s, deaths "
        "per tonne of "
        f"road fuel in {last - 1} and {last} were higher than projected, by "
        f"{_fmt_pct(float(per_fuel_recent.min()) - 1, 0)} to "
        f"{_fmt_pct(float(per_fuel_recent.max()) - 1, 0)} depending on where that trend is "
        "taken to start.",
        [
            ("long-run", "Long-run trends"),
            ("long-run#recent-years", "Recent years against the trend"),
            ("trends", f"Since {base}"),
        ],
    )
    severity_finding = _finding(
        "Deaths relative to traffic fell by three quarters, but the records cannot say how "
        "much of that came from fewer crashes and how much from less deadly ones.",
        f"Deaths per tonne of road fuel sold, which stands in for traffic, fell "
        f"{_fmt_pct(1 - per_fuel, 0)} between {split_first} and {split_last}. Counted by injury "
        f"crashes, deaths per crash fell {_fmt_pct(1 - severity, 0)} and crashes per tonne "
        f"{_fmt_pct(1 - frequency, 0)}; counted by people admitted to hospital, deaths per "
        f"admission rose {_fmt_pct(per_admission - 1, 0)} and admissions per tonne fell "
        f"{_fmt_pct(1 - admitted, 0)}.",
        [("long-run#frequency-and-severity", "Crash frequency and severity")],
    )
    return trend + severity_finding


def _drivers() -> str:
    numbers = _driver_numbers()
    central, ranges = numbers["central"], numbers["ranges"]
    severity = numbers["severity"]
    young, older = central.loc["18-29"], central.loc["65+"]
    oldest, reference = severity.loc["75+"], severity.loc["45-64"]
    ratio = float(oldest.killed_per_1000_involved) / float(reference.killed_per_1000_involved)
    _require(
        "drivers",
        {
            "drivers aged 75 and over die more once involved": float(
                oldest.killed_per_1000_involved_low
            )
            > float(reference.killed_per_1000_involved_high),
            "the youngest drivers are involved more per km on every assumption": float(
                ranges.loc["18-29", "min"]
            )
            > 1.5
            and float(young.involved_ratio_low) > 2,
            "drivers aged 65 and over slightly more often per km than 45-64 centrally": 1
            < float(older.involved_ratio)
            < 1.35
            and float(older.involved_ratio_low) > 0.95,
        },
    )
    deaths = _finding(
        "Older drivers are far more likely to die once a crash has happened.",
        f"In {national_rates.YEAR}, car drivers aged 75 and over who were involved in an injury "
        f"crash died {ratio:.1f} times as often as drivers aged 45–64 "
        f"({float(oldest.killed_per_1000_involved):.1f} against "
        f"{float(reference.killed_per_1000_involved):.1f} per 1,000 involved), a result that "
        "needs no estimate of kilometres. Involvement counts every driver in the crash, so "
        "neither this nor the rate per kilometre says who caused it.",
        [("drivers#deaths-once-a-crash-has-happened", "Drivers: deaths once a crash has happened")],
    )
    per_km = _finding(
        "Young drivers are in more crashes for the distance they drive.",
        "Per kilometre driven, car drivers aged 18–29 were involved in injury crashes about "
        f"{float(young.involved_ratio):.1f} times as often as drivers aged 45–64 in "
        f"{national_rates.YEAR} (95% interval {float(young.involved_ratio_low):.1f}–"
        f"{float(young.involved_ratio_high):.1f}; {float(ranges.loc['18-29', 'min']):.1f}–"
        f"{float(ranges.loc['18-29', 'max']):.1f} under other assumptions about the kilometres), "
        f"and drivers aged 65 and over {float(older.involved_ratio):.2f} times as often (95% "
        f"interval {float(older.involved_ratio_low):.2f}–{float(older.involved_ratio_high):.2f}; "
        f"{float(ranges.loc['65+', 'min']):.2f}–{float(ranges.loc['65+', 'max']):.2f} under "
        "the other assumptions). The kilometres by driver age are estimated from the "
        "Barcelona-area working-day travel survey applied to Spain's population.",
        [("drivers#involvement-in-crashes-per-kilometre-driven", "Drivers: crashes per kilometre")],
    )
    return deaths + per_km


def _speed() -> str:
    numbers = _speed_numbers()
    pooled = numbers["pooled"]
    adjusted = pooled.loc["adjusted"]
    types = pooled.drop(index="adjusted")
    lowest, highest = types.loc[types.rate_ratio.idxmin()], types.loc[types.rate_ratio.idxmax()]
    all_roads = numbers["all_roads"]
    last = int(all_roads.index.max())
    # The pooled rows carry their period as "first-last".
    first_year, last_year = (int(year) for year in str(adjusted.year).split("-"))
    _require(
        "speed",
        {
            "deaths per crash are about twice as high where speed is recorded": 1.8
            <= float(adjusted.rate_ratio)
            <= 2.2
            and float(adjusted.ratio_low) > 1,
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
        "urban streets.",
        "In Spain outside Catalonia and the Basque Country, police recorded inappropriate speed "
        f"in {_fmt_pct(float(all_roads.loc[last, 'share_of_crashes']))} of injury crashes in "
        f"{last}. Over {first_year}–{last_year}, those crashes had more deaths per crash than "
        "other crashes on the same kind of road, from "
        f"{float(lowest.rate_ratio):.1f} times on dual carriageways to "
        f"{float(highest.rate_ratio):.1f} times on urban streets, and about twice as many "
        f"({float(adjusted.rate_ratio):.1f} times) with the road types taken together.",
        [("speed", "Speed"), ("factors", "Recorded factors")],
    )


def _models() -> str:
    contrasts = read_table("sev_contrasts")
    interurban = contrasts[contrasts.base == "interurban"].set_index(["input", "level"])
    heavy = interurban.loc[("users", "heavy_vehicle")]
    urban = interurban.loc[("road", "urban_street")]
    scores = read_table("sev_rolling_scores")
    span = str(scores.subset[scores.subset.str.fullmatch(r"\d{4}-\d{4}")].iloc[0])
    pooled = scores[scores.subset == span].set_index("estimator")
    calc, table_score = pooled.loc["calculator"], pooled.loc["road_x_crash_table"]
    training = read_table("sev_coefficients")
    _require(
        "models",
        {
            "a heavy vehicle about doubles the fatal share, clearly": 1.7 < float(heavy.ratio) < 2.3
            and float(heavy.ratio_low) > 1.5,
            "an urban street about halves it, clearly": 0.4 < float(urban.ratio) < 0.65
            and float(urban.ratio_high) < 0.7,
            "the model ranks better than the road and crash-type table": float(calc.roc_auc)
            > float(table_score.roc_auc),
            "its estimates match the observed share overall": abs(
                float(calc.mean_predicted) - float(calc.prevalence)
            )
            < 0.005,
            "the coefficients are published": not training.empty,
        },
    )
    return _finding(
        "In Catalonia, severe crashes with a heavy vehicle involved were fatal about twice as "
        "often.",
        "Among crashes in Catalonia in which someone was killed or seriously injured, the same "
        "crash on a regional road was fatal "
        f"{float(heavy.ratio):.1f} times as often with a lorry or bus involved (95% interval "
        f"{float(heavy.ratio_low):.1f}–{float(heavy.ratio_high):.1f}), and about half as often "
        f"({float(urban.ratio):.2f} times) on an urban street, other recorded circumstances "
        "held equal. A calculator gives the model's estimate for a crash a reader "
        "describes; it has been tested only within Catalonia, on years it had not seen.",
        [
            ("severity-models", "Severity model and calculator"),
            ("validation", "External validation"),
        ],
    )


def _explore() -> str:
    """The pages, in the navigation's groups and order, each with the question it answers."""
    groups = []
    for index, (group, pages) in enumerate(NAV_GROUPS):
        if group == "Overview":
            continue
        items = "".join(
            f"<li>{_link(f'{slug}.html', esc(title))}: "
            f"{esc(PAGE_QUESTIONS[slug][:1].lower() + PAGE_QUESTIONS[slug][1:])}</li>"
            for slug, title in pages
        )
        groups.append(f'<h3 id="pages-{index}">{esc(group)}</h3><ul class="page-list">{items}</ul>')
    return "<h2>The pages</h2>" + "".join(groups)
