"""The front page: what the study is, its main findings, where to read on and what data it uses.

Each finding is one number with a sentence or two saying what it measures, and a link to the page
that sets it out; the methods are left to the pages behind them. Every number is read from a
committed result table, and every qualitative sentence is checked against the tables before the
page is written.
"""

from __future__ import annotations

import math

from dgt_stats import edm2018
from dgt_stats.exposure_risk import national as national_rates
from dgt_stats.site.components import (
    ALL_PAGES,
    _fmt_int,
    _fmt_pct,
    esc,
    read_table,
    render_page,
    summary,
)
from dgt_stats.site.numbers import _long_run_numbers, _risk_numbers, _speed_numbers
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
    body = _introduction()
    body += "<h2>Main findings</h2>"
    body += '<ol class="findings">'
    body += _long_run()
    body += _drivers()
    body += _speed()
    body += _models()
    body += "</ol>"
    body += _explore()
    body += _data(first, last)
    lead = (
        f"An independent statistical study of road deaths and injuries in Spain from {first} to "
        f"{last}, built from official statistics and from police crash records for Catalonia and "
        "Barcelona."
    )
    return render_page("index", "Road safety in Spain", lead, body)


def _finding(value: str, text: str, links: list[tuple[str, str]]) -> str:
    """One main finding: its number, what the number measures, and the pages that set it out.

    Each link is ``(target, label)``, the target a page slug with an optional ``#section``.
    """

    def href(target: str) -> str:
        page, _, anchor = target.partition("#")
        return f"{page}.html" + (f"#{anchor}" if anchor else "")

    more = " · ".join(_link(href(target), label) for target, label in links)
    return (
        f'<li><p class="finding-value">{value}</p><div class="finding-body"><p>{text}</p>'
        f'<p class="finding-more">{more}</p></div></li>'
    )


def _introduction() -> str:
    return summary(
        "Most of this study is ordinary statistical analysis of published data: deaths and "
        "crashes counted over time and divided by residents, licence holders, vehicles, fuel "
        "sold or kilometres driven, and, where the data allow, split into how often crashes "
        "happen and how deadly a crash is once it has happened. A smaller part fits predictive "
        "models to individual crash records from Catalonia and Barcelona, and keeps a model only "
        "if it beats a simple table of the same records. Every comparison between an outcome "
        "and a circumstance is an association, not an estimate of a causal effect."
    )


def _data(first: int, last: int) -> str:
    """The quiet closing line: where the data come from."""
    records_first = int(read_table("missingness_by_year").year.min())
    cat_years = read_table("cat_frequency").year
    bcn_year = _year_label(read_table("bcn_person_severity_share"))
    return (
        '<div class="provenance"><p>'
        f"Data: the Dirección General de Tráfico (DGT) yearbook series {first}–{last}, its "
        f"tables of drivers and vehicles involved in crashes, its file of injury crashes since "
        f"{records_first} and its estimates of kilometres driven; INE population figures, "
        "road-fuel sales and traffic counts; Catalonia's crashes with a death or serious injury, "
        f"{int(cat_years.min())}–{int(cat_years.max())}; and Barcelona's police-attended "
        f"crashes, {bcn_year}; and two travel surveys for kilometres by driver age, the "
        "Barcelona area's working-day mobility survey (EMEF) and Madrid's household travel "
        f"survey of {edm2018.SURVEY_YEAR}. The sources share no record identifier and are analysed "
        f"separately. {_link('sources.html', 'Data sources and scope')}."
        "</p></div>"
    )


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
    per_fuel = float(split.loc[split_last, "deaths_per_fuel_index"]) / 100
    severity = float(split.loc[split_last, "severity_index"]) / 100
    frequency = float(split.loc[split_last, "frequency_index"]) / 100
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
            "no denominator shows a change in deaths beyond an ordinary year since the base year": all(
                float(row.ratio_low_yty) <= 1 <= float(row.ratio_high_yty)
                for _, row in deaths.iterrows()
            ),
            "deaths per crash fell much more than crashes per tonne of fuel": severity
            < frequency
            < 1
            and math.log(severity) < 2 * math.log(frequency),
        },
    )
    fall = 1 - float(headline.loc[int(steep.end)]) / float(headline.loc[first])
    trend = _finding(
        f"−{_fmt_pct(fall, 0)}",
        f"Road deaths in Spain fell from {_fmt_int(headline.loc[first])} in {first} to "
        f"{_fmt_int(headline.loc[int(steep.end)])} in {int(steep.end)}, most of the fall coming "
        f"between {int(steep.start)} and {int(steep.end)}. That steep decline then ended: the "
        f"trend since {int(flat.start)} shows no clear rise or fall, and the "
        f"{_fmt_int(deaths.loc['count', 'count'])} deaths of {last} were more than in "
        f"{int(steep.end)}. Since {base}, no measure of deaths, whether counted or divided by "
        "residents, licence holders, vehicles or fuel sold, has changed by more than ordinary "
        "year-to-year variation.",
        [("long-run", "Long-run trends"), ("trends", f"Trends since {base}")],
    )
    severity_finding = _finding(
        f"−{_fmt_pct(1 - severity, 0)}",
        f"Deaths per injury crash fell {_fmt_pct(1 - severity, 0)} between {split_first} and "
        f"{split_last}, while injury crashes per tonne of road fuel sold fell "
        f"{_fmt_pct(1 - frequency, 0)}. Deaths relative to traffic fell "
        f"{_fmt_pct(1 - per_fuel, 0)} over the period, mostly because crashes became less "
        "deadly rather than less frequent. How the fall divides between the two depends on how "
        "completely crashes with only slight injuries are recorded.",
        [
            (
                f"long-run#crash-frequency-and-severity-{split_first}-{split_last}",
                "Crash frequency and severity",
            )
        ],
    )
    return trend + severity_finding


def _drivers() -> str:
    rates = read_table("risk_national_rates")
    rates = rates[rates.km_total == "less taxi and ride-hailing"]
    central = rates[rates.method.str.startswith("A:")].set_index("group")
    spread = rates.groupby("group").involved_ratio
    severity = read_table("risk_severity_and_licences").set_index("group")
    young, older = central.loc["16-29"], central.loc["65+"]
    oldest, reference = severity.loc["75+"], severity.loc["45-64"]
    ratio = float(oldest.killed_per_1000_involved) / float(reference.killed_per_1000_involved)
    _require(
        "drivers",
        {
            "drivers aged 75 and over die more once involved": float(
                oldest.killed_per_1000_involved_low
            )
            > float(reference.killed_per_1000_involved_high),
            "the youngest drivers are involved more per km on every method": float(
                spread.get_group("16-29").min()
            )
            > 1.5
            and float(young.involved_ratio_low) > 2,
            "drivers aged 65 and over are involved about as often per km as 45-64": 0.95
            < float(older.involved_ratio_low)
            and float(older.involved_ratio) < 1.3,
        },
    )
    deaths = _finding(
        f"{ratio:.1f}×",
        f"In {national_rates.YEAR}, car drivers aged 75 and over who were involved in an injury crash died "
        f"{ratio:.1f} times as often as drivers aged 45–64 "
        f"({float(oldest.killed_per_1000_involved):.1f} against "
        f"{float(reference.killed_per_1000_involved):.1f} per 1,000 involved), a result that "
        "needs no estimate of kilometres.",
        [("drivers#deaths-once-a-crash-has-happened", "Drivers: deaths once a crash has happened")],
    )
    per_km = _finding(
        f"{float(young.involved_ratio):.1f}×",
        "Per kilometre driven, car drivers aged 18–29 were involved in injury crashes "
        f"{float(young.involved_ratio):.1f} times as often as drivers aged 45–64 in "
        f"{national_rates.YEAR} (95% "
        f"interval {float(young.involved_ratio_low):.1f}–{float(young.involved_ratio_high):.1f}), "
        "and drivers aged 65 and over about as often as the middle-aged or modestly more "
        f"({float(older.involved_ratio):.2f}). The kilometres by driver age come from the "
        "Barcelona-area working-day mobility survey applied to Spain's population, so the "
        "ratios carry sensitivity ranges; the former figure, on kilometres by the age of a "
        "car's registered owner, put the young drivers' excess at nearly seven times.",
        [("drivers#involvement-in-crashes-per-kilometre-driven", "Drivers: crashes per kilometre")],
    )
    return deaths + per_km


def _speed() -> str:
    numbers = _speed_numbers()
    adjusted = numbers["pooled"].loc["adjusted"]
    all_roads = numbers["all_roads"]
    last = int(all_roads.index.max())
    _require(
        "speed",
        {
            "deaths per crash are about twice as high where speed is recorded": 1.8
            <= float(adjusted.rate_ratio)
            <= 2.2
            and float(adjusted.ratio_low) > 1,
        },
    )
    return _finding(
        f"{float(adjusted.rate_ratio):.1f}×",
        "In Spain outside Catalonia and the Basque Country, police recorded inappropriate speed "
        f"in {_fmt_pct(float(all_roads.loc[last, 'share_of_crashes']))} of injury crashes in "
        f"{last}. Those crashes had about twice the deaths per crash of other crashes on the "
        "same kind of road in the same year. This is an association in police records, not an "
        "estimate of how many crashes or deaths speeding caused.",
        [("speed", "Speed"), ("factors", "Recorded factors")],
    )


def _models() -> str:
    scores = read_table("sev_rolling_scores")
    span = str(scores.subset[scores.subset.str.fullmatch(r"\d{4}-\d{4}")].iloc[0])
    first_test, last_test = span.split("-")
    pooled = scores[scores.subset == span].set_index("estimator")
    calibration = read_table("sev_calibration")
    bands = calibration[calibration.estimator == "calculator"]
    calc, table_score = pooled.loc["calculator"], pooled.loc["road_x_crash_table"]
    selected = read_table("ml_selected")
    primary = selected[selected.primary].set_index("model")
    transport = read_table("ml_transport_validation")
    path = read_table("ml_outward_path")
    national = transport[
        transport.experiment.eq("Catalonia -> Spain outside Catalonia")
        & transport.model.eq("catalonia_common_dgt")
        & transport.estimator.eq(primary.loc["catalonia_common_dgt", "estimator"])
        & transport.status.eq("reported")
    ].iloc[0]
    _require(
        "models",
        {
            "the calculator's model ranks better than the table": float(calc.roc_auc)
            > float(table_score.roc_auc),
            "its predictions match the observed shares in every band": bool(
                (
                    (bands.mean_predicted >= bands.observed_low)
                    & (bands.mean_predicted <= bands.observed_high)
                ).all()
            ),
            "the Catalonia-trained model ranks Spanish crashes almost as well as one trained "
            "on them": abs(float(national.transfer_gap)) <= 0.01,
            "no model is called fit for national use": not path.verdict.eq(
                "potentially nationally transferable"
            ).any(),
        },
    )
    return _finding(
        _fmt_pct(float(calc.mean_predicted)),
        "A model of which crashes with a death or serious injury in Catalonia were fatal, tested "
        f"on each year from {first_test} to {last_test} with a model fitted only on earlier years, "
        f"predicted {_fmt_pct(float(calc.mean_predicted))} of them fatal against "
        f"{_fmt_pct(float(calc.prevalence))} observed, and its predicted shares matched the "
        "observed ones across the whole range. It picked out the fatal crashes better than a "
        "table of the same records, and a calculator applies it to any crash a reader "
        "describes. Of the project's other models, the Barcelona crash model did no better "
        "than a table and was removed. A version of the Catalan model ranked serious crashes in "
        "the rest of Spain almost as well as a model trained on them, which does not make it fit "
        "for national use. None of the models predicts whether a crash will happen.",
        [
            ("severity-models", "Severity model and calculator"),
            ("validation", "External validation"),
        ],
    )


# The front page's index of the study: each group of pages, what it covers, and its pages.
EXPLORE = (
    (
        "National trends and exposure",
        "Deaths and crashes over time, against residents, licence holders, vehicles, fuel and "
        "kilometres.",
        ("trends", "long-run", "seasons", "policy"),
    ),
    (
        "Drivers and vehicles",
        "Rates by driver age and sex, and by type of vehicle, per vehicle and per kilometre.",
        ("drivers", "vehicles"),
    ),
    (
        "Recorded crash factors",
        "What the police recorded about each crash, and how it relates to severity.",
        ("speed", "factors", "severity"),
    ),
    (
        "Catalonia and Barcelona",
        "Severity among recorded crashes in two detailed regional files.",
        ("catalonia", "barcelona"),
    ),
    (
        "Predictive severity models",
        "A model of which severe crashes were fatal, its calculator, and how every model held up "
        "on other records.",
        ("severity-models", "validation"),
    ),
    (
        "Sources and methodology",
        "Where the data come from, what they cover and how the results are produced.",
        ("sources", "data"),
    ),
)


def _explore() -> str:
    titles = dict(ALL_PAGES)
    if sorted(slug for *_, slugs in EXPLORE for slug in slugs) != sorted(
        slug for slug in titles if slug != "index"
    ):
        raise ValueError("overview: the study index must list every page once")
    groups = "".join(
        f'<section aria-labelledby="explore-{index}"><h3 id="explore-{index}">{esc(name)}</h3>'
        f"<p>{esc(text)}</p><ul>"
        + "".join(f"<li>{_link(f'{slug}.html', esc(titles[slug]))}</li>" for slug in slugs)
        + "</ul></section>"
        for index, (name, text, slugs) in enumerate(EXPLORE, 1)
    )
    return f'<h2>Explore the study</h2><div class="explore">{groups}</div>'
