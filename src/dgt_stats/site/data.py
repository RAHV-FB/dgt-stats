"""Data and methods: sources, assumptions tested, definitions, checks, reuse and reproduction."""

from __future__ import annotations

import pandas as pd

from dgt_stats import forecast
from dgt_stats.paths import TABLES_DIR
from dgt_stats.site.components import (
    DOCS_URL,
    REPO_URL,
    _change,
    _fmt_pct,
    _signed_pct,
    figure,
    key_figures,
    read_table,
    render_page,
    table,
)


def _assumptions_section() -> str:
    """Every headline rests on an assumption; this is the list, each with its test and verdict."""
    scatter = read_table("risk_dispersion").set_index("outcome")
    km = read_table("longrun_km_panel").set_index("year")
    km_check = read_table("longrun_km_check").set_index(["measure", "year"])
    km_last = int(km.index.max())
    base_year = int(km_check.loc["per_km"].last_segment_start.iloc[0])
    owner = read_table("q7_owner_age_check").set_index("band")
    validation = (
        read_table("forecast_validation").set_index(["outcome", "set", "method"]).sort_index()
    )
    detect = read_table("forecast_detectability").set_index(["outcome", "horizon"])
    speeds = read_table("simulator_speed_sites")
    split = read_table("risk_frequency_severity").set_index("year")
    index = read_table("risk_index").set_index(["outcome", "denominator", "year"])
    last = int(split.index.max())
    first = int(split.index.min())

    def growth(a: int, b: int) -> str:
        ratio = float(km.loc[b, "km_per_tonne"] / km.loc[a, "km_per_tonne"])
        return _signed_pct(ratio ** (1 / (b - a)) - 1, 1)

    def rmse(kind: str, method: str) -> str:
        return _fmt_pct(float(validation.loc[("deaths_all", kind, method), "rmse"]))

    crash_person = index.loc[("crashes", "residents", last)]
    hosp = index.loc[("hospitalised_30d", "count", last)]
    young, middle = owner.loc["18-34"], owner.loc["35-54"]
    rows = [
        (
            "2019–2024",
            "A year's count varies only by Poisson chance",
            "Scatter of each annual count around its 2013–2019 trend",
            f"Deaths {float(scatter.loc['deaths_30d', 'dispersion']):.1f}, admissions "
            f"{float(scatter.loc['hospitalised_30d', 'dispersion']):.1f} and injury crashes "
            f"{float(scatter.loc['crashes', 'dispersion']):.0f} times the Poisson variance",
            "Fails for crashes and admissions. Intervals now allow for an ordinary year: the "
            f"fall in crashes per resident ({_change(float(crash_person.ratio_to_base))}) is "
            "within it; the rise in admissions as a count "
            f"({_change(float(hosp.ratio_to_base))}) is not",
        ),
        (
            "Long run",
            "Road fuel tracks the kilometres driven",
            "The Ministry's measured interurban vehicle-km against fuel",
            f"Kilometres per tonne {growth(base_year, 2019)} a year {base_year}–2019, "
            f"{growth(2019, km_last)} a year 2019–{km_last}",
            "Holds to 2019 and drifts after. Per kilometre, interurban deaths in "
            f"{km_last} are {_change(float(km_check.loc[('per_km', km_last), 'ratio']), 0)} on "
            "trend, inside the interval; the per-fuel excess is mostly the proxy. Finding "
            "corrected",
        ),
        (
            "Age and sex",
            "The registered owner's age stands for the driver's",
            "Cars and kilometres per licence holder, by age band",
            f"18–34: {float(young.cars_per_licence):.2f} cars and "
            f"{float(young.km_per_licence):,.0f} km per licence holder; 35–54: "
            f"{float(middle.cars_per_licence):.2f} and {float(middle.km_per_licence):,.0f}",
            "Partly: young drivers' kilometres sit with older owners. Moving all of the gap out "
            "of the 35–54 baseline takes the 75-and-over involvement ratio from "
            f"{float(owner.ratio_75_published.iloc[0]):.2f} to "
            f"{float(owner.ratio_75_if_young_drive_like_baseline.iloc[0]):.2f}; the fatality "
            "ratio needs no kilometres. The conclusion holds",
        ),
        (
            "Overview",
            "The fall in deaths was in how deadly crashes are",
            "Deaths per tonne of fuel split into crashes per tonne and deaths per crash",
            f"{first}–{last}: deaths per tonne "
            f"{_signed_pct(float(split.loc[last, 'deaths_per_fuel_index']) / 100 - 1)}, crashes "
            f"per tonne {_signed_pct(float(split.loc[last, 'frequency_index']) / 100 - 1)}, "
            "deaths per crash "
            f"{_signed_pct(float(split.loc[last, 'severity_index']) / 100 - 1)}",
            "Holds. The split depends on how completely slight injuries are recorded; the "
            "product, deaths per tonne, does not",
        ),
        (
            "Simulator",
            "A forecast can show a law's effect in the counts",
            "Rolling forecasts on years the model had not seen",
            f"Model {rmse('selection', forecast.CHOSEN)} on 2006–2015 and "
            f"{rmse('holdout', forecast.CHOSEN)} on 2016–2024; last year's count "
            f"{rmse('selection', 'last_year')} and {rmse('holdout', 'last_year')}",
            "Only for large effects: one year after a law the smallest visible change is "
            f"{_fmt_pct(float(detect.loc[('deaths_interurban', 1), 'mde']), 0)} of interurban "
            "deaths, and it grows with every year waited",
        ),
        (
            "Simulator",
            "Two numbers describe how fast cars drive",
            "A log-normal through the measured share within the limit and the 85th percentile, "
            "checked on the measured mean",
            "Its mean lands within "
            f"{float((speeds.implied_mean - speeds.mean_speed).abs().max()):.1f} km/h of the "
            "measured mean on every kind of road",
            "Holds",
        ),
    ]
    frame = pd.DataFrame(rows, columns=["Page", "Assumption", "Test", "Result", "Verdict"])
    return (
        '<h2 id="assumptions-tested">Assumptions tested</h2>'
        "<p>Every headline rests on an assumption the data can be asked about. These are the "
        "ones that could be tested, with what the test found; two of them changed a finding.</p>"
        + table(frame, "The assumptions behind the headlines, and what testing them found")
    )


def page_data(captions: dict[str, str]) -> str:
    validation = pd.read_csv(TABLES_DIR / "validation.csv")
    passed = int(validation.passed.astype(bool).sum())
    total = int(len(validation))
    coefficients = read_table("q3_model_coefficients")
    n_crashes = int(coefficients.n.iloc[0])
    other = read_table("q2_other_road_by_period").set_index("period")

    body = key_figures(
        [
            ("Injury crashes", f"{n_crashes:,}", "2016–2024 microdata, one row per crash"),
            ("Reconciliation checks", f"{passed} / {total}", "run before any analysis"),
            ("Series", "1993–2024", "the yearbook monthly and annual series"),
            ("Traffic series", "1990–2025", "monthly road fuel and toll-motorway traffic"),
        ]
    )
    body += (
        '<p class="answer">Every number on this site is generated from files published by DGT, '
        "INE, the Ministerio de Transportes and CORES, reconciled against the publishers' own "
        f"totals by {passed} checks before anything is computed. This page is the short version; "
        f'the <a href="{DOCS_URL}/data_sources.md">source register</a>, the '
        f'<a href="{DOCS_URL}/data_inventory.md">data audit</a> and the '
        f'<a href="{DOCS_URL}/methodology.md">methodology</a> in the repository are the long '
        "one.</p>"
    )

    body += "<h2>Sources</h2>"
    sources = pd.DataFrame(
        [
            (
                "Crash microdata 2016–2024",
                "DGT",
                f"{n_crashes:,} injury crashes, one row each: place, time, road, conditions and "
                "victim counts. No driver, vehicle or person records.",
            ),
            (
                "Yearbook series 1993–2024",
                "DGT",
                "Annual, monthly and provincial totals; the reference the microdata are checked "
                "against, and the series the long-run and seasons pages fit.",
            ),
            (
                "Statistical tables 2014–2024",
                "DGT",
                "Drivers involved and killed by age, sex and vehicle; vehicles involved by type; "
                "drivers by recorded infraction.",
            ),
            (
                "Kilometre estimates 2022 and 2024",
                "DGT",
                "Circulating fleet and mean annual kilometres from roadworthiness-inspection "
                "odometer readings; the 2024 release adds a breakdown by the owner's age band.",
            ),
            (
                "Driver census 2014–2025",
                "DGT",
                "Licence holders by province, sex and age band.",
            ),
            (
                "Resident population 2002–2025",
                "INE",
                "Province by five-year age group and sex (CC BY 4.0).",
            ),
            (
                "Monthly traffic and fuel",
                "Ministerio de Transportes; CORES",
                "Traffic on state toll motorways from 1990 and national road-fuel consumption "
                "from 1996: the traffic denominators of the 2019–2024, long-run and seasons pages.",
            ),
            (
                "Interurban vehicle-kilometres 2004–2023",
                "Ministerio de Transportes",
                "Vehicle-kilometres measured on the State, regional and provincial road networks "
                "by type of road (yearbook table 1.2.14): the check on road fuel, and the "
                "per-kilometre risk of each kind of road.",
            ),
            (
                "Speed-factor report 2014–2023",
                "DGT",
                "Injury crashes with each recorded concurrent factor, and deaths in those with "
                "speed, for Spain without Cataluña and País Vasco; used on the speed and factors "
                "pages, never added to national totals.",
            ),
            (
                "Evidence for the simulator",
                "TØI; European Commission; DGT; BOE",
                "The Power Model exponents, the response of speeds to a new limit, car speeds "
                "measured in Spain in 2022, the legal limits and DGT's values of a casualty: one "
                "register, each value with its source, table and a verbatim quote.",
            ),
        ],
        columns=["Source", "Published by", "What it carries"],
    )
    body += table(sources, "The sources behind this site")
    body += _assumptions_section()

    body += "<h2>Definitions</h2>"
    body += (
        "<p><strong>Injury crash</strong>: at least one person killed or injured. "
        "<strong>Death</strong>: within 30 days of the crash, DGT's consolidated definition. "
        "<strong>Serious</strong>: a death or a person admitted to hospital for more than 24 "
        "hours. <strong>Zone</strong>: interurban roads against urban streets and crossings, as "
        "DGT groups them. Missing states are kept apart everywhere: “not specified”, “not "
        "applicable” and a field's own unknown code are three different things, and none of them "
        "means no.</p>"
    )

    body += "<h2>Checks, and what they found</h2>"
    body += (
        f"<p>{passed} checks tie the crash microdata, the yearbook tables and the driver census to "
        "DGT's published totals: crashes and victims per year, deaths by province and by month, "
        "driver deaths by zone, vehicles involved by type, the census against its published "
        "tables, every code against the dictionary, and the speed report's own totals against "
        "the microdata restricted to its provinces. All of them pass, and the microdata match "
        "the yearbook exactly, year by year. The kilometre table by owner age reconciles with the "
        "same release's published fleet to within 0.5%, the margin left by owners DGT could not "
        f'classify. The <a href="tables/validation.csv">full list is a CSV</a>.</p>'
    )
    body += figure(
        "d1_missingness", "Share of crashes with a value recorded, by field and year", captions
    )
    body += "<h3>Three coding breaks worth knowing about</h3>"
    later = other.loc["2024"] if "2024" in other.index else other.iloc[-1]
    earlier = other.loc["2016-2023"] if "2016-2023" in other.index else other.iloc[0]
    body += (
        "<p>In 2024 Barcelona begins coding most of its streets as road type “other”: "
        f"{float(later.street_share):.0%} of that year's “other” crashes are urban streets, "
        f"against {float(earlier.street_share):.0%} before, so road-type series must be read year "
        "by year and alongside zone. In 2021 most crashes on double-carriageway conventional "
        "roads are recoded as single-carriageway conventional. From 2023 the junction field "
        "records more crashes at a junction, mostly in Barcelona. All three are why the severity "
        "page reports its year-by-year refits, and why no page draws a road-type trend.</p>"
    )

    body += "<h2>Reuse</h2>"
    body += (
        f'<p>The code is under the <a href="{REPO_URL}/blob/main/LICENSE">MIT licence</a>. The '
        "data are not: each file keeps the terms of the body that publishes it, and DGT's "
        "statistics are reused here as public-sector information under Ley 37/2007 with the "
        "datos.gob.es conditions applied: the source is named, the meaning is not distorted, the "
        "dates are kept and no endorsement is implied. INE population is CC BY 4.0. Every figure "
        "published here is an aggregate and nothing identifies a person. The file-by-file terms, "
        f'with URLs and checksums, are in the <a href="{DOCS_URL}/data_sources.md">source '
        "register</a>.</p>"
    )

    body += "<h2>Reproduce</h2>"
    body += (
        "<p>Five commands from the raw files, which are tracked in the repository with their "
        f'checksums. The sequence is in the <a href="{REPO_URL}#reproduce">README</a>, it runs on '
        "every push through GitHub Actions, and the result tables and figures are committed, so "
        "any number on this site can be traced to the table it came from and the table to the "
        "file it came from.</p>"
    )
    body += (
        "<p>The project was developed through a reproducible, source-driven workflow. The "
        "research questions, the choice of sources, the statistical design, the interpretation "
        "and the decision to publish each result are the author's, and so is responsibility for "
        "them. AI coding assistants were used during implementation, debugging, data-processing "
        "work and review. All published results are generated from the recorded source data and "
        "can be independently reproduced and checked through the repository.</p>"
    )
    return render_page(
        "data",
        "Data and methods",
        "Where the numbers come from, how they are defined, what the checks found and how to "
        "reproduce all of it.",
        body,
    )
