"""Data and methods: sources, assumptions tested, definitions, checks, reuse and reproduction."""

from __future__ import annotations

import pandas as pd

from dgt_stats import forecast, io_exposure, risk_trends
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
    coverage = read_table("longrun_km_coverage")
    segments = read_table("longrun_segments")
    base_year = int(segments[segments.measure == "road_fuel"].start.max())
    bio = read_table("longrun_fuel_bio").set_index("year").bio_share
    owner = read_table("q7_owner_age_check").set_index("band")
    validation = (
        read_table("forecast_validation").set_index(["outcome", "set", "method"]).sort_index()
    )
    detect = read_table("forecast_detectability").set_index(["outcome", "horizon"])
    split = read_table("risk_frequency_severity").set_index("year")
    index = read_table("risk_index").set_index(["outcome", "denominator", "year"])
    first, last = int(split.index.min()), int(split.index.max())
    reference = risk_trends.BASE_YEAR

    def growth(a: int, b: int) -> str:
        ratio = float(km.loc[b, "km_per_tonne"] / km.loc[a, "km_per_tonne"])
        return _signed_pct(ratio ** (1 / (b - a)) - 1, 1)

    def rmse(kind: str, method: str) -> str:
        return _fmt_pct(float(validation.loc[("deaths_all", kind, method), "rmse"]))

    def span(years: tuple[int, ...]) -> str:
        return f"{min(years)}–{max(years)}"

    holdout_years = sorted(forecast.HOLDOUT_YEARS)
    holdout = (
        f"{holdout_years[0]}–{forecast.PANDEMIC_YEARS[0] - 1} and "
        f"{forecast.PANDEMIC_YEARS[-1] + 1}–{holdout_years[-1]}"
    )
    index_last = int(index.index.get_level_values("year").max())
    crash_person = index.loc[("crashes", "residents", index_last)]
    hosp = index.loc[("hospitalised_30d", "count", index_last)]
    per_km_last = km_check.loc[("per_km", km_last)]
    young, middle, old = owner.loc["18-34"], owner.loc["35-54"], owner.loc["75+"]
    checks = {
        "admissions and crashes scatter more than Poisson chance": float(
            scatter.loc["hospitalised_30d", "dispersion"]
        )
        > 1
        and float(scatter.loc["crashes", "dispersion"]) > 1,
        "crashes per resident are within an ordinary year": float(crash_person.ratio_low_yty)
        <= 1
        <= float(crash_person.ratio_high_yty),
        "admissions as a count are beyond an ordinary year": float(hosp.ratio_low_yty) > 1,
        "per measured interurban km the last year is inside its interval": not bool(
            per_km_last.outside_interval
        ),
        "interurban km per tonne of national fuel rise after the reference year": float(
            km.loc[km_last, "km_per_tonne"]
        )
        > float(km.loc[reference, "km_per_tonne"]),
        "the biofuel share rose, which lowers km per tonne": float(bio.loc[km_last])
        > float(bio.loc[reference]),
        "owner age does not stand for driver age at either end": float(young.cars_per_b_permit)
        < float(middle.cars_per_b_permit)
        < 1
        < float(old.cars_per_b_permit),
        "deaths per crash fell more than crashes per tonne": float(
            split.loc[last, "severity_index"]
        )
        < float(split.loc[last, "frequency_index"]),
        "waiting makes a change harder to see": bool(
            detect.loc["deaths_interurban"].mde.is_monotonic_increasing
        ),
    }
    failed = [claim for claim, holds in checks.items() if not holds]
    if failed:
        raise ValueError(f"data page: the tables no longer support: {failed}")

    rows = [
        (
            f"{reference}–{index_last}",
            "A year's count varies only by Poisson chance",
            f"Scatter of each annual count around its {span(risk_trends.SCATTER_YEARS)} trend",
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
            "The Ministry's measured interurban vehicle-km against national road fuel (the "
            "scopes differ, so this is a diagnostic of the proxy, not a rate)",
            f"Interurban km per tonne of national fuel {growth(base_year, reference)} a year "
            f"{base_year}–{reference}, {growth(reference, km_last)} a year "
            f"{reference}–{km_last}",
            "Cannot be tested on all roads: the measured km cover only State, regional and "
            "provincial interurban roads. Per measured km, interurban deaths in "
            f"{km_last} are {_change(float(per_km_last.ratio), 0)} on trend, inside the "
            f"interval; {_fmt_pct(float(coverage.outside_share.min()))} to "
            f"{_fmt_pct(float(coverage.outside_share.max()))} of interurban deaths are on roads "
            "the km leave out",
        ),
        (
            "Long run",
            "A tonne of road fuel means the same every year",
            "CORES subtotals against their products, biofuels included, and the published "
            "biofuel share",
            "Each subtotal equals its products in every month; biofuel was "
            f"{_fmt_pct(float(bio.loc[reference]))} of road fuel by mass in {reference} and "
            f"{_fmt_pct(float(bio.loc[km_last]))} in {km_last}",
            "Holds. More biofuel, which carries less energy per tonne, would lower kilometres "
            "per tonne slightly; it cannot explain the rise in interurban km per tonne",
        ),
        (
            "Age and sex",
            "The registered owner's age stands for the driver's",
            "Cars and kilometres per B-permit holder, by age band",
            f"18–34: {float(young.cars_per_b_permit):.2f} cars and "
            f"{float(young.km_per_b_permit):,.0f} km per B-permit holder; 35–54: "
            f"{float(middle.cars_per_b_permit):.2f} and {float(middle.km_per_b_permit):,.0f}; "
            f"75+: {float(old.cars_per_b_permit):.2f} cars",
            "Does not hold at either end. Moving "
            f"{float(young.transfer_bn_km):.1f} billion km from the 35–54 band to the 18–34 "
            "band "
            "takes the 18–34 involvement ratio per km from "
            f"{float(young.involved_per_bn_km_ratio):.2f} to "
            f"{float(young.involved_per_bn_km_ratio_transfer):.2f} and the 75-and-over one from "
            f"{float(old.involved_per_bn_km_ratio):.2f} to "
            f"{float(old.involved_per_bn_km_ratio_transfer):.2f}. Per-km ratios are published "
            "as ranges from that scenario (not an estimate) to the published ratio; deaths per "
            "driver involved need no kilometres",
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
            "Deaths forecast",
            "A forecast can show a change in the counts",
            "Rolling forecasts on years the model had not seen",
            f"Model {rmse('selection', forecast.CHOSEN)} on {span(forecast.SELECTION_YEARS)} and "
            f"{rmse('holdout', forecast.CHOSEN)} on {holdout}; last year's count "
            f"{rmse('selection', 'last_year')} and {rmse('holdout', 'last_year')}. In the "
            f"lockdown years {rmse('pandemic', forecast.CHOSEN)} against "
            f"{rmse('pandemic', 'last_year')}",
            "Only for large changes: one year after a change the comparison picks up a fall of "
            f"{_fmt_pct(float(detect.loc[('deaths_interurban', 1), 'mde']), 0)} of interurban "
            f"deaths with probability {_fmt_pct(forecast.POWER, 0)}, smaller ones less often, "
            "and the threshold grows with every year waited",
        ),
    ]
    frame = pd.DataFrame(rows, columns=["Page", "Assumption", "Test", "Result", "Verdict"])
    return (
        '<h2 id="assumptions-tested">Assumptions tested</h2>'
        "<p>Every headline rests on an assumption the data can be asked about. These are the "
        "ones that were tested, with what the test found.</p>"
        + table(frame, "The assumptions behind the headlines, and what testing them found")
    )


def page_data(captions: dict[str, str]) -> str:
    validation = pd.read_csv(TABLES_DIR / "validation.csv")
    passed = int(validation.passed.astype(bool).sum())
    total = int(len(validation))
    coefficients = read_table("q3_model_coefficients")
    n_crashes = int(coefficients.n.iloc[0])
    micro_years = coefficients[coefficients.predictor == "year"].level.astype(int)
    micro_span = f"{micro_years.min()}–{micro_years.max()}"
    headline = read_table("q1_annual_headline")
    series_span = f"{int(headline.year.min())}–{int(headline.year.max())}"
    fuel = read_table("risk_frequency_severity")
    fuel_span = f"{int(fuel.year.min())}–{int(fuel.year.max())}"
    other = read_table("q2_other_road_by_period").set_index("period")

    body = key_figures(
        [
            ("Injury crashes", f"{n_crashes:,}", f"{micro_span} microdata, one row per crash"),
            ("Reconciliation checks", f"{passed} / {total}", "run before any analysis"),
            ("Series", series_span, "the yearbook annual series"),
            ("Road fuel", fuel_span, "CORES national road fuel, the traffic denominator"),
        ]
    )
    body += (
        '<p class="answer">Every number on this site is generated from files published by DGT, '
        "INE, the Ministerio de Transportes and CORES, reconciled against the publishers' own "
        f"totals by {total} checks before anything is computed. This page is the short version; "
        f'the <a href="{DOCS_URL}/data_sources.md">source register</a>, the '
        f'<a href="{DOCS_URL}/data_inventory.md">data audit</a> and the '
        f'<a href="{DOCS_URL}/methodology.md">methodology</a> in the repository are the long '
        "one.</p>"
    )

    body += "<h2>Sources</h2>"
    sources = pd.DataFrame(
        [
            (
                f"Crash microdata {micro_span}",
                "DGT",
                f"{n_crashes:,} injury crashes, one row each: place, time, road, conditions and "
                "victim counts. No driver, vehicle or person records.",
            ),
            (
                f"Yearbook series {series_span}",
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
                "Licence holders by province, sex and age band; B-permit (car) holders by age "
                "and sex in the text files from 2023.",
            ),
            (
                "Resident population 2002–2025",
                "INE",
                "Province by five-year age group and sex (CC BY 4.0).",
            ),
            (
                "Monthly traffic and fuel",
                "Ministerio de Transportes; CORES",
                "National road-fuel consumption, the denominator of the 2019–2024, long-run and "
                "seasons pages and a predictor of the deaths forecast; traffic on state toll "
                "motorways, shown on the seasons page as a traffic index beside deaths and used "
                "as a covariate in the 2006 case study, never as a denominator.",
            ),
            (
                "Interurban vehicle-kilometres 2004–2023",
                "Ministerio de Transportes",
                "Vehicle-kilometres measured on the State, regional and provincial road networks "
                "by type of road (yearbook table 1.2.14): interurban deaths per measured "
                "kilometre on the long-run page, and the split by road class on the overview, "
                "each with deaths on the roads of the networks the kilometres cover.",
            ),
            (
                "Speed-factor report 2014–2023",
                "DGT",
                "Injury crashes with each recorded concurrent factor, and deaths in those with "
                "speed, for Spain without Cataluña and País Vasco; used on the speed and factors "
                "pages, never added to national totals.",
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
        f"<p>{total} checks tie the crash microdata, the yearbook tables and the driver census to "
        "DGT's published totals: crashes and victims per year, deaths by province and by month, "
        "driver deaths by zone, vehicles involved by type, the census against its published "
        "tables, every code against the dictionary, and the speed report's own zone totals "
        "against the microdata restricted to its provinces. "
        + (
            "All of them pass, and the microdata match the yearbook exactly, year by year. "
            if passed == total
            else f"{total - passed} of them do not pass; the CSV says which. "
        )
        + "The kilometre table by owner age reconciles with the same release's published fleet "
        f"to within {_fmt_pct(io_exposure.KM_OWNER_TOLERANCE)}, the margin left by owners DGT "
        f'could not classify. The <a href="tables/validation.csv">full list is a CSV</a>.</p>'
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
        "page reports its year-by-year refits and puts both kinds of conventional road in one "
        "level, and why no page draws a road-type trend.</p>"
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
        f'checksums. The sequence is in the <a href="{REPO_URL}#reproduce">README</a>. On every '
        "pull request and every push to main, GitHub Actions reruns the first three commands and "
        "the tests from the raw files (not the analyses; a push to main that touches the site "
        "or its inputs also rebuilds this site from the committed tables and publishes it), and "
        "the result "
        "tables and figures are committed, so "
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
