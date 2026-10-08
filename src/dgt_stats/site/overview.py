"""The front page: the study's answer in two sentences, its main findings, and its pages.

Each finding leads with its answer in one sentence, then the numbers behind it and a link to the
page that sets it out; the methods are left to the pages behind them. The list of pages follows
the navigation's groups. Every number is read from a committed result table, and every
qualitative sentence is checked against the tables before the page is written.
"""

from __future__ import annotations

import math

from dgt_stats import edm2018
from dgt_stats.exposure_risk import national as national_rates
from dgt_stats.site.components import (
    NAV_GROUPS,
    PAGE_QUESTIONS,
    _fmt_int,
    _fmt_pct,
    definition_link,
    esc,
    read_table,
    render_page,
    summary,
)
from dgt_stats.site.numbers import (
    FAIL,
    INTERMEDIATE,
    OLDER_CONCLUSION,
    PASS,
    _driver_numbers,
    _long_run_numbers,
    _older_numbers,
    _risk_numbers,
    _speed_numbers,
    joint_interval,
    rate_interval,
)
from dgt_stats.site.regional_common import _year_label

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
    barcelona_year = _year_label(read_table("bcn_person_severity_share"))
    lead = (
        f"An independent statistical study of road deaths and injuries in Spain from {first} to "
        f"{last}, built from official statistics and from police crash records for Catalonia and "
        f"for Barcelona ({barcelona_year})."
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
            "with the later start, neither year is outside the trend's range": not bool(
                projections[
                    (projections.measure == "road_fuel")
                    & (projections.variant == other_start)
                    & projections.year.isin([last - 1, last])
                ].outside_interval.any()
            ),
            "deaths per measured interurban kilometre stayed within their range": not bool(
                read_table("longrun_km_check").query("measure == 'per_km'").outside_interval.any()
            ),
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
        f"taken to start; with the trend started in {int(flat.start)}, neither year lies "
        "outside the trend's range, and on interurban roads deaths per measured kilometre "
        "stayed within theirs.",
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
    covered = read_table("risk_coverage").set_index("component")
    oldest_numbers = _older_numbers()
    tier = oldest_numbers["tier"]
    estimate = oldest_numbers["conditional"].loc["75+"]
    full, clear = oldest_numbers["range"]["75+"], oldest_numbers["clear"]["75+"]
    lowest_clear = oldest_numbers["lowest_clear"]
    oldest_rows = oldest_numbers["older"]
    _require(
        "drivers",
        {
            "the conditional 75+ estimate's sampling interval is above the 45-64 rate": float(
                estimate.ratio_low
            )
            > 1,
            "the lowest combination tested for 75+ is marked as at odds with men's driving": bool(
                oldest_rows.loc[oldest_rows.ratio_75_plus.idxmin(), "at_odds_with_mens_driving"]
            ),
            "the lowest unmarked 75+ combination is above the 45-64 rate": clear[0] > 1,
            "the wording printed for 75+ matches the tables": (
                tier == INTERMEDIATE and float(lowest_clear.ratio_low) <= 1 < clear[0]
            )
            or (tier == PASS and float(lowest_clear.ratio_low) > 1)
            or (tier == FAIL and clear[0] <= 1),
            "the 75+ sensitivity range reaches the 45-64 rate": full[0] <= 1 < full[1],
            "the survey's working days cover about half of DGT's car km": 0.45
            < float(covered.loc["working days", "share_least_explained"])
            < 0.55,
            "drivers aged 75 and over die more once involved": float(
                oldest.killed_per_1000_involved_low
            )
            > float(reference.killed_per_1000_involved_high),
            "the youngest drivers are involved more per km on every assumption": float(
                ranges.loc["18-29", "min"]
            )
            > 1.2
            and float(young.involved_ratio_low) > 2,
            "drivers aged 65 and over above 45-64 per km centrally, on either side of it under "
            "the other assumptions": 1 < float(older.involved_ratio) < 1.35
            and float(ranges.loc["65+", "min"]) < 1 < float(ranges.loc["65+", "max"]),
        },
    )
    deaths = _finding(
        "Older drivers are far more likely to die once a crash has happened.",
        f"In {national_rates.YEAR}, car drivers aged 75 and over who were involved in an injury "
        f"crash died {ratio:.1f} times as often as drivers aged 45–64 "
        f"({float(oldest.killed_per_1000_involved):.1f} against "
        f"{float(reference.killed_per_1000_involved):.1f} per 1,000 involved), a count that "
        "needs no estimate of kilometres. It measures how often a crash kills the driver, not "
        "how often older drivers are in crashes or who caused them.",
        [("drivers#deaths-once-a-crash-has-happened", "Drivers: deaths once a crash has happened")],
    )
    direction = OLDER_CONCLUSION[tier]
    per_km = _finding(
        "Young drivers are in more crashes for the distance they drive.",
        "Per kilometre driven, car drivers aged 18–29 were involved in injury crashes "
        f"{float(young.involved_ratio):.2f} times as often as drivers aged 45–64 in "
        f"{national_rates.YEAR} (95% {definition_link('Sampling interval')} "
        f"{rate_interval(young, 'involved_ratio')}; {definition_link('Sensitivity range')} "
        f"{float(ranges.loc['18-29', 'min']):.2f}–{float(ranges.loc['18-29', 'max']):.2f}). "
        f"For drivers aged 65 and over the central estimate is {float(older.involved_ratio):.2f} "
        f"times (95% sampling interval {rate_interval(older, 'involved_ratio')}), but the "
        "sensitivity range is "
        f"{float(ranges.loc['65+', 'min']):.2f}–{float(ranges.loc['65+', 'max']):.2f}, so "
        "whether they are involved more or less often per kilometre is not established. For "
        "drivers aged 75 and over no source measures their kilometres apart from those at "
        "65–74; depending on how the 65-and-over kilometres are divided and carried to Spain, "
        f"the sensitivity range is {full[0]:.2f} to {full[1]:.2f} times the 45–64 rate"
        f"{direction}. If people aged 75 and over drive as much less than those aged 65–74 as "
        f"in Madrid in {edm2018.SURVEY_YEAR}, they were involved about "
        f"{float(estimate.ratio_to_45_64):.1f} times as often (95% sampling interval "
        f"{joint_interval(estimate, 1)}), a {definition_link('Conditional estimate')} that holds "
        "only on that assumption. The "
        "kilometres by driver age come from a Barcelona-area survey of working days. Carried to "
        "Spain's population, the survey's working-day driving adds up to about half of DGT's car "
        "kilometres; the central estimate gives the rest the same age mix, and the sensitivity "
        "range tests other mixes. Involvement counts every driver in a crash, whoever caused it.",
        [
            (
                "drivers#involvement-in-crashes-per-kilometre-driven",
                "Drivers: crashes per kilometre",
            ),
            ("drivers#ages-75-and-over", "Drivers: ages 75 and over"),
        ],
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
            "an urban street clearly lowers it": float(urban.ratio_high) < 0.7,
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
        f"{float(heavy.ratio_low):.1f}–{float(heavy.ratio_high):.1f}), and on an urban street "
        f"rather than a regional road {float(urban.ratio):.2f} times as often (95% interval "
        f"{float(urban.ratio_low):.2f}–{float(urban.ratio_high):.2f}), other recorded "
        "circumstances held equal. A calculator gives the model's estimate for a crash "
        "a reader describes. The way the model is fitted and tuned has been tested only within "
        "Catalonia, by predicting each year from the years before it; the published model, "
        "fitted on every year, has no later year left to test.",
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
