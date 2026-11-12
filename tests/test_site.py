import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dgt_stats import site, summaries
from dgt_stats.exposure_risk import national
from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, TABLES_DIR
from dgt_stats.site import components
from dgt_stats.site import numbers as site_numbers
from dgt_stats.site.script import JS_FLAG

# The national analysis pages in navigation order; then the regional, model and sources pages.
ANALYSIS_PAGES = tuple(slug for slug, _ in components.SPAIN_PAGES)
REGIONAL_PAGES = ("catalonia", "barcelona", "severity-models", "sources")

pytestmark = pytest.mark.skipif(
    not (FIGURES_DIR / "captions.json").exists()
    or not (TABLES_DIR / "risk_annual_panel.csv").exists()
    or not summaries.model_tables_present(),
    reason="run `python scripts/model.py` and `python scripts/analyse.py all` first",
)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("site")
    site.build(target)
    return target


def test_every_page_is_written_with_one_heading(built: Path) -> None:
    for slug, _ in site.ALL_PAGES:
        page = built / f"{slug}.html"
        assert page.exists(), slug
        text = page.read_text(encoding="utf-8")
        assert text.count("<h1>") == 1, slug
        _runs_no_script(slug, text)
        assert 'lang="en"' in text
        assert f'href="{slug}.html" aria-current="page"' in text
    # The navigation follows the questions a reader brings: the interactive tools; deaths over
    # time; drivers, vehicles and recorded factors; how deadly a crash is once it has happened; and
    # the data and methods. Old pages that no builder writes are gone.
    assert [group for group, _ in site.NAV_GROUPS] == [
        "Overview",
        "Explore",
        "Over time",
        "Drivers, vehicles and factors",
        "Crash severity",
        "Data and methods",
    ]
    assert [slug for slug, _ in dict(site.NAV_GROUPS)["Explore"]] == [
        "explore",
        "driver-risk",
        "crash-explorer",
    ]
    assert [slug for slug, _ in dict(site.NAV_GROUPS)["Crash severity"]] == [
        "severity",
        "catalonia",
        "barcelona",
        "severity-models",
    ]
    assert {slug for slug, _ in site.ALL_PAGES} == {p.stem for p in built.glob("*.html")}
    # The site's one site-wide script is its own reading aid. The tools' scripts and data live
    # apart in tools/, and only the tool pages load them.
    assert [p.name for p in built.glob("*.js")] == ["site.js"]
    assert not (built / "models").exists()
    tools = {p.name for p in (built / "tools").iterdir()}
    assert {"tools.js", "driver-risk.js", "crash-explorer.js"} <= tools
    assert "trends-explorer.js" not in tools
    assert {p.suffix for p in (built / "tools").iterdir()} <= {".js", ".json"}
    published = {p.name for p in (built / "tables").glob("*.csv")}
    assert not published & {"simulator_evidence.csv", "factor_evidence.csv"}


def _runs_no_script(slug: str, text: str) -> None:
    """No page runs a script of its own, except the tools.

    Every page loads the site's reading aid (menus and contents), after a one-line flag that says
    scripting is on; each tool page also loads the tools' shared helpers and its own script.
    """
    expected = ["<script>", '<script src="site.js" defer>']
    if slug in site.components.TOOL_SLUGS:
        expected.append('<script src="tools/tools.js" defer>')
        expected.append(f'<script src="tools/{slug}.js" defer>')
    assert re.findall(r"<script[^>]*>", text) == expected, slug
    assert JS_FLAG in text, slug


# Pages that were renamed or removed. They are not kept as pointers.
DEFUNCT_PAGES = (
    "older-drivers",
    "context",
    "transport",
    "forecast",
    "simulator",
    "distraction",
    "alcohol-drugs",
    "enforcement",
    "trends",
    "trends-explorer",
    "calculator",
    "validation",
)


def test_defunct_pages_are_gone_and_nothing_links_to_them(built: Path) -> None:
    for slug in DEFUNCT_PAGES:
        assert not (built / f"{slug}.html").exists(), slug
    for slug, _ in site.ALL_PAGES:
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        for defunct in DEFUNCT_PAGES:
            assert f'href="{defunct}.html"' not in text, (slug, defunct)
    for name in (
        "k1_forecast_check",
        "k2_detectability",
        "r1_risk_change",
        "l2_observed_over_trend",
    ):
        assert not (built / "figures" / f"{name}.svg").exists(), name


def test_reuse_names_each_provider_its_terms_and_its_dates(built: Path) -> None:
    text = (built / "data.html").read_text(encoding="utf-8")
    reuse = text[text.find('id="reuse"') : text.find('id="data-and-method"')]
    for terms in (
        "https://datos.gob.es/avisolegal",
        "https://creativecommons.org/licenses/by/4.0/",
        "https://www.ine.es/aviso_legal/",
        "https://www.transportes.gob.es/ministerio/aviso-legal",
        "https://www.omc.cat/ca/avis-legal",
        "https://www.idescat.cat/institut/web/?lang=en",
    ):
        assert f'href="{terms}"' in reuse, terms
    assert "CORES" in reuse and "Idescat" in reuse
    # The dates of last update are the source register's; where none is published, the text
    # gives the download dates and says so.
    manifest = pd.read_csv(PROJECT_ROOT / "data/raw/manifest.csv")
    described = " ".join(manifest.description.astype(str))
    for pattern, dayfirst in (
        (r"last updated (\d{4}-\d{2}-\d{2})", False),
        (r"Actualizado el (\d{2}-\d{2}-\d{4})", True),
        (r"por última vez el (\d{2}-\d{2}-\d{4})", True),
    ):
        for found in re.findall(pattern, described):
            stamp = pd.to_datetime(found, dayfirst=dayfirst)
            assert f"{stamp.day} {stamp:%B %Y}" in reuse, found
    assert reuse.count("carry no date of last update") == 2
    # Every provider is named in the footer of every page.
    for page in built.glob("*.html"):
        footer = page.read_text(encoding="utf-8").split('<footer class="site-footer">')[1]
        assert "Idescat" in footer and "CORES" in footer, page.name


def test_sources_date_the_mobility_survey_by_its_microdata(built: Path) -> None:
    # Documents archived beside the microdata (the 2003-2018 methodology report) must not
    # stretch the years the study holds.
    years = sorted(
        int(path.name.split("_")[1])
        for path in (PROJECT_ROOT / "data/raw/emef").glob("*/emef_*_persons.csv")
    )
    assert years == list(range(years[0], years[-1] + 1))
    text = (built / "sources.html").read_text(encoding="utf-8")
    assert f"Barcelona area, working days, {years[0]}–{years[-1]}" in text


def test_referenced_assets_exist(built: Path) -> None:
    for page in built.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        for src in re.findall(r'src="([^"]+)"', text):
            assert (built / src).exists(), (page.name, src)
        for href in re.findall(r'href="([^"]+\.(?:css|csv))"', text):
            assert (built / href).exists(), (page.name, href)
        for href in re.findall(r'href="([a-z-]+\.html)"', text):
            assert (built / href).exists(), (page.name, href)


def test_full_result_tables_are_published_as_csv(built: Path) -> None:
    published = {p.name for p in (built / "tables").glob("*.csv")}
    # Exactly the tables some page links are published; the others stay in the repository.
    linked = {
        name
        for page in built.glob("*.html")
        for name in re.findall(r'href="tables/([^"/]+\.csv)"', page.read_text("utf-8"))
    }
    assert published == linked
    # The severity page links the model tables its text rests on; the rest stay unpublished.
    assert {f"{name}.csv" for name in summaries.MODEL_TABLES} >= {
        "q3_model_coefficients.csv",
        "q3_location_contrasts.csv",
        "q3_adverse_conditions.csv",
        "q3_junction_sensitivity.csv",
        "q3_regime_sensitivity.csv",
        "q3_holdout_summary.csv",
    }
    assert {
        "q3_model_coefficients.csv",
        "q3_location_contrasts.csv",
        "q3_adverse_conditions.csv",
        "q3_junction_sensitivity.csv",
        "q3_regime_sensitivity.csv",
        "q3_holdout_summary.csv",
    } <= published
    assert "validation.csv" in published
    # Removed analyses leave no download behind.
    removed = {"q7_breakeven_km", "risk_fuel_efficiency", "q1_annual_headline", "q2_night_share"}
    removed |= {"q8_speed_placebo", "q8_speed_sensitivity", "q8_points_placebo"}
    assert not published & {f"{name}.csv" for name in removed}
    # Every page that shows a headline number also links the table it came from.
    for slug in ANALYSIS_PAGES + ("severity", "policy"):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        assert 'href="tables/' in text, slug


def test_a_page_that_links_a_missing_table_fails_the_build(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text('<a href="tables/no_such_table.csv">x</a>', encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="no_such_table.csv"):
        site.publish_tables(tmp_path / "site", [page])


def test_figures_are_copied_and_captioned(built: Path) -> None:
    # Exactly the figures the pages show are published, each with its drawing for a phone.
    shown = {
        name
        for page in built.glob("*.html")
        for name in re.findall(
            r'<img class="figure-wide" src="figures/([^"/]+)\.svg"', page.read_text("utf-8")
        )
    }
    published = {p.stem for p in (built / "figures").glob("*.svg")}
    assert published == shown and len(shown) > 25
    assert {p.stem for p in (built / "figures" / "narrow").glob("*.svg")} == shown
    for path in (built / "figures").rglob("*.svg"):
        source = FIGURES_DIR / path.relative_to(built / "figures")
        assert path.read_bytes() == source.read_bytes(), path.name
    # A figure that is drawn but shown on no page is not published.
    captions = site.read_captions()
    for name in set(captions) - shown:
        assert not (built / "figures" / f"{name}.svg").exists(), name
    text = (built / "long-run.html").read_text(encoding="utf-8")
    # The caption is set in two parts: what is shown, then its source on a line of its own.
    shown, source = components._split_source(captions["l1_trend_projection"])
    assert source.startswith("Source: ")
    assert f"<figcaption><p>{site.mark_spanish(site.esc(shown))}</p>" in text
    assert f'<p class="figure-source">{site.mark_spanish(site.esc(source))}</p>' in text


def test_table_formats_numbers() -> None:
    frame = pd.DataFrame({"Year": [2024], "Crashes": [101996], "Share": [0.1234]})
    out = site.table(frame, "Caption", {"Crashes": "int", "Share": "pct"})
    # Numbers are right-aligned and the row label is a header cell.
    assert '<th scope="row">2024</th>' in out
    assert '<td class="num">101,996</td>' in out
    assert '<td class="num">12.3%</td>' in out
    # The title is set above the scrolling box, and the caption carries it for screen readers.
    assert out.index('<p class="table-title" aria-hidden="true">Caption</p>') < out.index(
        '<div class="table-wrap"'
    )
    assert '<caption class="visually-hidden">Caption</caption>' in out
    # A table of numbers keeps its columns; a table of prose alone is stacked on a small screen.
    assert "<table>" in out
    prose = pd.DataFrame({"Source": ["DGT"], "Publisher": ["DGT"], "Use": ["deaths"]})
    stacked = site.table(prose, "Sources. Each source used.")
    assert '<table class="stack">' in stacked and 'data-label="Use"' in stacked
    assert '<p class="table-note" aria-hidden="true">Each source used.</p>' in stacked


def test_severity_page_leads_with_the_adverse_finding(built: Path) -> None:
    text = (built / "severity.html").read_text(encoding="utf-8")
    # How the regressions are specified and checked, the junction flag's evidence, the model
    # variants and the missing-value levels are the page's technical notes on the methodology
    # page, which it links to.
    data = (built / "data.html").read_text(encoding="utf-8")
    notes = data[data.index('id="severity-method"') :]
    notes = notes[: notes.index("<h2", 1)]
    assert 'href="data.html#severity-method"' in text
    adverse = pd.read_csv(TABLES_DIR / "q3_adverse_conditions.csv")
    fatal = adverse[adverse.outcome == "fatal"].set_index(["variant", "level"])
    # The reduced set of variants: the full model, each of weather and surface left out, and the
    # two kinds of road; no hail-and-snow row, no composition or exclusion tables.
    assert set(adverse.variant) == {"full", "no_surface", "no_weather", "interurban", "street"}
    assert "hail or snow" not in set(adverse.level)
    for name in ("q3_marginal_effects", "q3_year_stability", "q3_adverse_composition"):
        assert not (TABLES_DIR / f"{name}.csv").exists(), name
    assert "s2_adverse_conditions" not in text
    # The wet-surface odds ratio is the full model's, with its interval, not the no-weather one.
    wet = fatal.loc[("full", "wet")]
    assert f"{wet.odds_ratio:.2f}, {wet.or_low:.2f}–{wet.or_high:.2f}" in text
    opening = re.search(r'<p class="summary">(.*?)</p>', text, re.S).group(1)
    assert f"({wet.odds_ratio:.2f}, {wet.or_low:.2f}–{wet.or_high:.2f})" in opening
    assert "Odds ratios for a wet surface, rain and a junction under each model variant" in notes
    assert 'src="figures/s1_forest_fatal.svg"' in text
    # The page says what kind of analysis it is, and the distinction the finding depends on.
    assert "an analysis of associations, not a predictive model" in text
    assert "nothing about how often crashes happen" in text
    # No outside study explains the associations, and the subtitle claims no explanation.
    for phrase in ("doi.org", "literature", "et al", "point the wrong way", "Naturalistic"):
        assert phrase not in text + notes, phrase
    # The missing-value levels are nuisance terms: flagged, quantified by province and refitted
    # without the provinces that record most of them; the numbers come from the tables.
    coefficients = pd.read_csv(TABLES_DIR / "q3_model_coefficients.csv")
    nuisance = coefficients[coefficients.is_nuisance.astype(bool)]
    assert set(nuisance.level) <= {"unknown", "not specified", "not applicable"}
    regime = pd.read_csv(TABLES_DIR / "q3_recording_regime.csv").set_index(["predictor", "level"])
    alignment = regime.loc[("alignment", "unknown")]
    assert components._fmt_pct(float(alignment.catalan_share_of_level)) in notes
    assert components._fmt_pct(float(alignment.share_of_catalan_crashes)) in notes
    assert 'href="tables/q3_regime_sensitivity.csv"' in text
    sensitivity = pd.read_csv(TABLES_DIR / "q3_regime_sensitivity.csv")
    sensitivity = sensitivity[sensitivity.outcome == "fatal"]
    wet_row = sensitivity[sensitivity.level == "wet"].iloc[0]
    assert f"moves from {wet_row.odds_ratio:.2f} to {wet_row.odds_ratio_without:.2f}" in notes
    # The robustness statement compares in both directions: how many full-model estimates lie
    # inside the without-Catalonia interval, and the largest moves by name.
    kept = sensitivity[~sensitivity.is_nuisance.astype(bool)]
    inside = int(
        ((kept.odds_ratio >= kept.or_low_without) & (kept.odds_ratio <= kept.or_high_without)).sum()
    )
    assert (
        f"The full model's odds ratio lies inside the interval of the refit for {inside} "
        f"of the {len(kept)} terms" in notes
    )
    moves = kept.loc[(kept.ratio_without_to_full - 1).abs().sort_values(ascending=False).index]
    biggest = moves.iloc[0]
    assert f"({biggest.odds_ratio:.2f} to {biggest.odds_ratio_without:.2f})" in notes
    assert "stay inside the full model's interval" not in notes
    # The later-years check gives the AUC and the calibration beside the Brier skill, and says
    # the regressions are not used for prediction as a matter of purpose.
    holdout = pd.read_csv(TABLES_DIR / "q3_holdout_summary.csv").set_index("outcome")
    assert components._fmt_pct(float(holdout.loc["fatal", "brier_skill"])) in notes
    assert f"in {holdout.loc['fatal', 'auc']:.2f} of pairs" in notes
    assert "calibrated" in notes and "not used for prediction, as a matter of purpose" in notes
    assert "improve little" not in text + notes
    # The full coefficient table is linked, not printed, and the download list stays short.
    assert 'href="tables/q3_model_coefficients.csv"' in text
    assert text.count("<table>") <= 4
    downloads = re.search(r'<ul class="downloads">(.*?)</ul>', text, re.S)
    if downloads:
        assert downloads.group(1).count("<li>") <= 7
    # The summary names location beside crash type, from the joint zone and road-type contrast,
    # and gives the junction association with the inverted Catalan flag read the other way round.
    locations = pd.read_csv(TABLES_DIR / "q3_location_contrasts.csv")
    conventional = locations[
        (locations.outcome == "fatal")
        & (locations.zone == "interurban road")
        & (locations.road == "conventional")
    ].iloc[0]
    assert f"{conventional.odds_ratio:.2f} times the odds" in opening
    assert "side or front-side collision" in opening
    junction = coefficients[
        (coefficients.outcome == "fatal") & (coefficients.level == "at a junction")
    ].iloc[0]
    assert f"({junction.odds_ratio:.2f}, {junction.or_low:.2f}–{junction.or_high:.2f})" in opening
    assert "read the other way round" in opening
    # The page states the junction coding problem, how it was corrected, the period refits and
    # the flag as published; the notes add the evidence and the one alternative reading, every
    # number from the tables.
    junction_sensitivity = pd.read_csv(TABLES_DIR / "q3_junction_sensitivity.csv")
    assert set(junction_sensitivity.treatment) == {"flip", "as published"}
    assert set(junction_sensitivity.fit) == {"full", "from break"}
    full = junction_sensitivity[
        (junction_sensitivity.outcome == "fatal") & (junction_sensitivity.fit == "full")
    ].set_index("treatment")
    published = full.loc["as published"]
    assert f"{published.odds_ratio:.2f} ({published.or_low:.2f}–{published.or_high:.2f})" in text
    recoded = int(pd.read_csv(TABLES_DIR / "q3_junction_coding.csv").recoded.sum())
    assert f"{recoded:,} crashes" in text and f"{recoded:,} crashes" in notes
    periods = pd.read_csv(TABLES_DIR / "q3_period_refits.csv")
    assert set(periods.level) == {"at a junction"}
    later = periods[
        (periods.outcome == "fatal")
        & (periods.scope == "all provinces")
        & (periods.period == "from")
    ].iloc[0]
    assert f"{later.odds_ratio:.2f} ({later.or_low:.2f}–{later.or_high:.2f})" in text
    assert 'href="tables/q3_junction_sensitivity.csv"' in text
    for phrase in ("until the coding changed", "only the junction term", "Cochran"):
        assert phrase not in text + notes, phrase
    # The ranking is quoted with what the missing-value levels contribute to it, as ROC-AUC to
    # two decimals, the scale of the severity model page.
    recorded_only = holdout.loc["fatal", "auc_recorded_only"]
    missing_only = holdout.loc["fatal", "auc_missing_only"]
    assert (
        f"death scores {recorded_only:.2f}, and those levels on their own {missing_only:.2f}"
        in (notes)
    )
    assert "times in 100" not in text + notes
    # The page leads with what the records show: the results come first, then what the records
    # cannot show; the description of the records and the regressions opens the notes.
    main = text[text.find("<main>") : text.find("</main>")]
    headings = re.findall(r"<h2[^>]*>(.*?)</h2>", main, re.S)
    assert headings[0] == "Crash type and location go most strongly with a death"
    assert headings[1].startswith("Lower odds of a death on wet roads")
    assert headings[2].startswith("The records show which crashes were deadlier")
    assert "The records and the regressions" not in headings
    assert '<h3 id="severity-regressions">The records and the regressions</h3>' in notes
    # The opening paragraph names the other two pages on severity, once each, with their
    # populations and definitions.
    assert opening.count('href="catalonia.html"') == opening.count('href="barcelona.html"') == 1
    assert "within 30 days" in opening and "within 24 hours" in opening
    # The weekend is defined, and the file's per-crash counts are not called absent.
    assert "from 20:00 on Friday" in notes
    assert "no fields for drivers" not in text + notes


def test_intervals_are_printed_at_the_precision_their_monte_carlo_error_supports() -> None:
    # A unit of the last digit at least twice the larger error of the two ends.
    assert site_numbers.mc_digits(0.004, 0.002) == 2
    assert site_numbers.mc_digits(0.006, 0.002) == 1
    assert site_numbers.mc_digits(0.06) == 0
    assert site_numbers.mc_digits(3.8, coarsest=-2) == -1
    assert site_numbers.mc_digits(0.49, coarsest=-2) == 0
    assert site_numbers.mc_interval(2.2426, 2.8230, 0.0174, 0.0159) == "2.2–2.8"
    assert site_numbers.mc_interval(585.06, 704.95, 3.81, 3.43, coarsest=-2) == "590–700"
    assert site_numbers.mc_interval(1.6311, 2.6429, 0.019, 0.033, sep=" to ") == "1.6 to 2.6"
    # An interval wholly on one side of 1 is not printed as reaching it: an end three errors
    # clear of 1 gets the decimal it needs (men against women per km), an end closer to 1 does
    # not (65 and over).
    assert site_numbers.mc_interval(0.8559, 0.9802, 0.0061, 0.0036) == "0.86–0.98"
    assert site_numbers.mc_interval(1.0242, 1.362, 0.0103, 0.0148) == "1.0–1.4"
    assert site_numbers.mc_interval(0.9988, 1.82, 0.012, 0.03) == "1.0–1.8"
    # An interval that includes 1 keeps the supported precision.
    assert site_numbers.mc_interval(0.9501, 1.2626, 0.0088, 0.012) == "1.0–1.3"
    row = pd.Series(
        {"ratio_low": 1.0242, "ratio_high": 1.362, "mc_se_low": 0.0103, "mc_se_high": 0.0148}
    )
    assert site_numbers.joint_interval(row) == "1.0–1.4"
    rate = pd.Series(
        {
            "involved_ratio_low": 1.0242,
            "involved_ratio_high": 1.362,
            "involved_ratio_mc_se_low": 0.0103,
            "involved_ratio_mc_se_high": 0.0148,
        }
    )
    assert site_numbers.rate_interval(rate, "involved_ratio") == "1.0–1.4"


def _sections(body: str) -> dict[str, str]:
    """A page's sections by the id of their heading, each up to the next heading."""
    anchors = re.findall(r'<h2 id="([^"]+)"', body)
    return dict(zip(anchors, re.split(r"<h2[^>]*>", body)[1:], strict=True))


def _driver_notes(built: Path) -> tuple[str, str, str]:
    """The drivers page's technical notes on the methodology page: all of them, the section on
    kilometres and crashes per kilometre, and the part on drivers aged 75 and over."""
    data = (built / "data.html").read_text(encoding="utf-8")
    main = data[data.find("<main>") : data.find("</main>")]
    per_km = _sections(main)["drivers-per-km"]
    older = per_km[per_km.index('id="drivers-75-and-over"') :]
    return per_km, per_km, older


def test_drivers_page_separates_the_two_questions(built: Path) -> None:
    text = (built / "drivers.html").read_text(encoding="utf-8")
    body = text[text.find("<main>") : text.find("</main>")]
    ranges = pd.read_csv(TABLES_DIR / "risk_national_ranges.csv")
    involved = ranges[ranges.measure == "involved per km"].set_index("group")
    severity = pd.read_csv(TABLES_DIR / "risk_severity_and_licences.csv").set_index("group")
    # The opening states the results in the order of how firmly they are known: deaths once
    # involved at 75 and over, a count, with its interval; then involvement per km, an estimate,
    # each ratio to one decimal with its sampling interval and the range beside it.
    opening = re.search(r'<p class="summary">(.*?)</p>', body, re.S).group(1)
    old = severity.loc["75+"]
    assert f"die {old.killed_ratio_to_45_64:.1f} times as often as drivers aged 45–64" in opening
    assert f"(95% interval {old.killed_ratio_low:.1f}–{old.killed_ratio_high:.1f})" in opening
    for group in ("18-29", "30-44", "65-74", "75+"):
        row = involved.loc[group]
        assert f"{row.ratio:.1f} times" in opening, group
        assert f"{row.ratio_low:.1f}–{row.ratio_high:.1f}" in opening, group
        assert f"{row.range_min:.1f}–{row.range_max:.1f}" in opening, group
    assert "cannot be told apart" in opening and "is not established" in opening
    assert 'class="key-result"' not in body
    # Three sections whose headings state the findings.
    sections = _sections(body)
    assert list(sections)[:3] == [
        "involvement-in-crashes-per-kilometre-driven",
        "deaths-once-a-crash-has-happened",
        "men-and-women",
    ]
    per_km = sections["involvement-in-crashes-per-kilometre-driven"]
    deaths, sexes = sections["deaths-once-a-crash-has-happened"], sections["men-and-women"]
    # Per km: one table with a row for every age group, each with its sampling interval and the
    # range under other assumptions; the method linked once; the caveat on 75 and over said in
    # plain words with the Madrid survey credited.
    assert "average of two travel surveys" in per_km
    assert 'href="data.html#drivers-per-km"' in per_km
    assert 'href="data.html#drivers-75-and-over"' in per_km
    assert "Powered by CRTM" in per_km and 'href="https://www.crtm.es"' in per_km
    assert per_km.count("<table") == 1
    for group in ("18-29", "30-44", "65+", "65-74", "75+"):
        row = involved.loc[group]
        assert f"{row.ratio_low:.1f}–{row.ratio_high:.1f}" in per_km, group
        assert f"{row.range_min:.1f}–{row.range_max:.1f}" in per_km, group
    assert 'src="figures/dr1_involved_per_km.svg"' in per_km
    alt = re.search(r'src="figures/dr1_involved_per_km.svg" alt="([^"]*)"', body).group(1)
    for group in ("18-29", "30-44", "65-74", "75+"):
        row = involved.loc[group]
        assert f"{row.range_min:.1f}–{row.range_max:.1f}" in alt, group
    assert 'href="driver-risk.html"' in body
    # Deaths once involved: counted, with the ratio and what the rate cannot show.
    assert f"{severity.loc['75+', 'killed_per_1000_involved']:.1f}" in deaths
    assert f"{old.killed_ratio_to_45_64:.1f} times the 45–64 rate" in deaths
    assert "more dangerous to others" in deaths and "who caused a crash" in deaths
    assert 'src="figures/dr2_killed_per_involved.svg"' in deaths
    assert body.count("<figure") == 3
    # Figure 2's text names every age group's rate.
    alt = re.search(
        r'<img class="figure-wide" src="figures/dr2_killed_per_involved.svg" alt="([^"]*)"', body
    ).group(1)
    for group, label in (("18-29", "18–29"), ("30-44", "30–44"), ("45-64", "45–64")):
        assert f"{severity.loc[group, 'killed_per_1000_involved']:.1f} at {label}" in alt
    # Figure references are computed.
    numbers = re.findall(r'<span class="figure-label">Figure (\d+)\.</span>', body)
    names = re.findall(r'id="figure-([a-z0-9_]+)"', body)
    order = dict(zip(names, numbers))
    assert f"(Figure {order['a3_sex_ratios']})" in sexes
    assert "[[figure:" not in body
    assert 'class="figure-narrow" src="figures/narrow/dr1_involved_per_km.svg"' in body
    for phrase in ("frailty", "travel-weighted", "extra travel", "nearly seven"):
        assert phrase not in text, phrase
    assert "doi.org" not in text  # no external study interprets these results
    # Sex: the ratio per driver involved with its interval, and the per-km ratios with ranges.
    sex = pd.read_csv(TABLES_DIR / "drivers_sex_ratios.csv").set_index(["scope", "band", "measure"])
    fatality_men = sex.loc[("car", "18+", "deaths_per_1000_involved")]
    assert f"{fatality_men.ratio:.2f}" in sexes
    assert f"({fatality_men.low:.2f}–{fatality_men.high:.2f})" in sexes
    per_km_sex = pd.read_csv(TABLES_DIR / "risk_sex_per_km.csv").set_index("measure")
    row = per_km_sex.loc["involved per km"]
    assert f"{row.ratio_men_to_women:.2f} times" in sexes
    assert f"range {row.range_low:.2f}–{row.range_high:.2f}" in sexes
    assert 'src="figures/a3_sex_ratios.svg"' in sexes
    # About ten tables are offered for download, none of the retired ones.
    links = set(re.findall(r'href="tables/([a-z0-9_]+)\.csv"', body))
    assert 8 <= len(links) <= 12 and "risk_national_ranges" in links
    assert not {n for n in links if n.startswith(("q7_", "risk_older_sens", "risk_coverage_"))}


def test_drivers_technical_notes_hold_the_method_and_the_checks(built: Path) -> None:
    notes, per_km, section = _driver_notes(built)
    ranges = pd.read_csv(TABLES_DIR / "risk_national_ranges.csv")
    involved = ranges[ranges.measure == "involved per km"].set_index("group")
    # The method: the average of the two surveys' age profiles, with each one's shares.
    shares = pd.read_csv(TABLES_DIR / "risk_national_shares.csv")
    for method in (national.BARCELONA_METHOD, national.MADRID_METHOD, national.CENTRAL_METHOD):
        share = shares[(shares.method == method) & (shares.group == "65+")].share_of_km.iloc[0]
        assert components._fmt_pct(share) in per_km, method
    assert "average of the two shares" in per_km
    # The notes stay short: about ten kilobytes of text beside their three tables.
    assert len(re.sub(r"<[^>]+>", "", per_km)) < 12_000
    # The coverage of DGT's kilometres: the working days' share and the table of its parts.
    parts = pd.read_csv(TABLES_DIR / "risk_coverage.csv").set_index("component")
    assert components._fmt_pct(parts.loc["working days", "share_least_explained"], 0) in per_km
    assert "What DGT&#x27;s kilometres are made of" in per_km or "What DGT's kilometres" in per_km
    # The ranges: what they span, and what produces the ends at 18-29.
    assert "not a confidence interval and not a bound" in per_km
    assert involved.loc["18-29", "range_min_from"] in per_km
    assert involved.loc["18-29", "range_max_from"] in per_km
    # The employed share of the survey's older respondents is mentioned once.
    assert per_km.count("were in work more often") == 1
    # Deaths per km: the 65-and-over ratio with its range.
    killed = ranges[ranges.measure == "killed per km"].set_index("group").loc["65+"]
    assert f"{killed.ratio:.1f} times as often per kilometre" in per_km
    assert f"{killed.range_min:.1f}–{killed.range_max:.1f}" in per_km
    # Barcelona's working-day check, with the ratios for 65 and over from its table.
    city = pd.read_csv(TABLES_DIR / "risk_barcelona_rates.csv")
    city = city[city.numerator == city.numerator.iloc[0]]
    for value in city[city.age4 == "65+"].ratio_to_45_64:
        assert f"{value:.1f}" in per_km
    # Nothing of the retired owner-age figure, the RACC split or the retired scenario tables.
    for phrase in ("former figure", "owner-age", "RACC", "Fundació", "composition bound"):
        assert phrase not in notes, phrase
    # Men and women, combined.
    assert "3.49 to 3.57" in per_km or "licence holders of any class" in per_km
    # Ages 75 and over: the conditional estimate, its two other splits and the range that
    # includes 1.
    row = involved.loc["75+"]
    assert f"({row.range_min:.1f}–{row.range_max:.1f}) includes 1" in section
    assert "conditional estimate" in section
    assert "equal kilometres per licence holder" in section
    assert 'href="drivers.html#deaths-once-a-crash-has-happened"' in section
    for phrase in ("frailty", "travel-weighted", "extra travel", "nearly seven", "doi.org"):
        assert phrase not in notes, phrase


def test_policy_page_reports_the_falsification_not_the_headline(built: Path) -> None:
    text = (built / "policy.html").read_text(encoding="utf-8")
    sensitivity = pd.read_csv(TABLES_DIR / "q8_points_sensitivity.csv").set_index("variant")
    main = float(sensitivity.loc["main", "level_change"])
    linear = float(sensitivity.loc["linear_trend", "level_change"])
    # Signed percentages are typeset with a real minus sign, not a hyphen.
    signed = lambda v: f"{v * 100:+.0f}%".replace("-", "\u2212")  # noqa: E731
    assert signed(main) in text and signed(linear) in text
    assert "-7%" not in text and "-12%" not in text
    assert main > linear  # the preferred specification gives the smaller drop
    calendar = pd.read_csv(TABLES_DIR / "q8_points_calendar_placebo.csv")
    true = calendar[calendar.is_true].iloc[0]
    assert int(true["rank"]) == 1 and f"largest of {int(true.n_fits)}" in text
    forecast = pd.read_csv(TABLES_DIR / "q8_points_forecast.csv")
    true_forecast = forecast[forecast.is_true].iloc[0]
    ordinal = components._ordinal(int(true_forecast["rank"]))
    assert f"{ordinal} largest of {int(true_forecast.n_fits)}" in text
    # The forecast shortfall is printed as the proportional change the rank orders.
    assert f"{abs(np.expm1(true_forecast.log_ratio)) * 100:.1f}% below their forecast" in text
    assert 'src="figures/p2_july_placebos.svg"' in text
    # The fall is not attributed to the licence.
    opening = re.search(r'<p class="summary">(.*?)</p>', text, re.S).group(1)
    assert "cannot show that the licence caused" in opening
    # The step is never quoted without what the slope change does to it: the summary gives the
    # average over the post-period with its interval, and says the intervals are too narrow.
    main_row = sensitivity.loc["main"]
    assert f"{abs(main_row.mean_change) * 100:.1f}% below the projection" in opening
    assert components._signed_pct(float(main_row.mean_high), 1) in opening
    calibration = pd.read_csv(TABLES_DIR / "q8_points_calibration.csv").iloc[0]
    assert f"at {int(calibration.n_excluding_zero)} of the {int(calibration.n_placebos)}" in opening
    assert "too narrow" in opening
    assert components._signed_pct(float(calibration.calibrated_low)) in text
    assert "strong evidence" not in text and "QAIC" in text
    # The model's notes are on the methodology page, without a speed-limit design.
    data = (built / "data.html").read_text(encoding="utf-8")
    notes = data[data.index('id="policy-method"') :]
    notes = notes[: notes.index("<h2", 1)]
    assert "speed limit" not in notes and "q8_speed" not in text + data
    assert 'href="data.html#policy-method"' in text
    assert not {"fuel", "toll", "24h", "interurban", "urban"} & set(sensitivity.index)


def test_factors_page_carries_speed_severity_and_reads_trends_within_comparable_runs(
    built: Path,
) -> None:
    text = (built / "factors.html").read_text(encoding="utf-8")
    assert not (built / "speed.html").exists()
    pooled = pd.read_csv(TABLES_DIR / "speed_severity_pooled.csv").set_index("road_type")
    adjusted = pooled.loc["adjusted"]
    opening = re.search(r'<p class="summary">(.*?)</p>', text, re.S).group(1)
    assert f"{adjusted.rate_ratio:.2f} times" in opening
    assert f"{adjusted.ratio_low:.2f}–{adjusted.ratio_high:.2f}" in opening
    assert f"{adjusted.crude_ratio:.2f}" in opening  # the unadjusted ratio is shown beside it
    assert f"{pooled.loc['dual_carriageway', 'rate_ratio']:.2f} times on dual" in opening
    assert f"{pooled.loc['urban', 'rate_ratio']:.2f} times on urban streets" in opening
    assert "weighted summary" in opening
    home = (built / "index.html").read_text(encoding="utf-8")
    assert f"{pooled.loc['urban', 'rate_ratio']:.1f} times on urban streets" in home
    assert f"{adjusted.rate_ratio:.1f} times as many deaths per crash" in home
    assert 'href="factors.html#road-types"' in home
    assert "These are associations in police records, not estimates of what speed causes" in (
        opening
    )
    # Recorded speed is not called a steady decline, and a change in recording is not excluded.
    assert (
        "not in steady decline" in opening and "change in recording cannot be excluded" in opening
    )
    assert "which would raise it" in text and "which would lower it" in text
    # The driver tables' break is stated once, and the dropped series and figure are gone.
    shares = pd.read_csv(TABLES_DIR / "q9_infraction_shares.csv")
    all_roads = shares[shares.zone == "all"].set_index("year")
    assert "no trend in speeding" in text
    for year in (2015, 2016):
        assert f"{all_roads.loc[year, 'share_unknown'] * 100:.0f}%" in text
    assert "c3_speed_status" not in text and "Drugs" not in text
    for column in shares.columns:
        assert "known" not in column.replace("unknown", "")
    # Interurban alcohol and the speed series come from the published shares.
    factor_shares = pd.read_csv(TABLES_DIR / "factor_shares.csv")
    assert "Drugs" not in set(factor_shares.factor)
    alcohol = factor_shares[
        (factor_shares.zone == "interurban") & (factor_shares.factor == "Alcohol")
    ]
    assert f"{alcohol.share.iloc[0] * 100:.1f}%" in text
    assert f"{alcohol.share.iloc[-1] * 100:.1f}%" in text
    assert 'src="figures/f2_factor_shares.svg"' in text
    assert 'src="figures/f1_speed_severity.svg"' in text
    assert "break in comparability" in text
    assert "cannot say whether a break" in text and "from recording or from both" in text
    data = (built / "data.html").read_text(encoding="utf-8")
    notes = data[data.index('id="factors-method"') :]
    notes = notes[: notes.index("<h2", 1)]
    assert 'href="data.html#factors-method"' in text
    assert "only through the interurban total" in notes
    for phrase in ("simulator", "Power Model", "physics"):
        assert phrase not in text and phrase not in notes, phrase
    for page in built.glob("*.html"):
        page_text = page.read_text(encoding="utf-8")
        assert "by the road's speed limit" not in page_text, page.name
        assert "licence class" not in page_text, page.name


def test_long_run_page_shows_the_trends_the_projection_and_the_last_year(built: Path) -> None:
    long_run = (built / "long-run.html").read_text(encoding="utf-8")
    index = pd.read_csv(TABLES_DIR / "risk_index.csv")
    # The last year against 2019: deaths as a count, per resident and per tonne of fuel, and
    # admissions per tonne, each with its change and its interval for an ordinary year.
    since = long_run[long_run.index('id="since-2019"') :]
    since = since[: since.index("<h2", 1)]
    latest = index[index.year == index.year.max()].set_index(["outcome", "denominator"])
    for outcome, key in (
        ("deaths_30d", "count"),
        ("deaths_30d", "residents"),
        ("deaths_30d", "road_fuel"),
        ("hospitalised_30d", "road_fuel"),
    ):
        row = latest.loc[(outcome, key)]
        assert components._change(float(row.ratio_to_base)) in since, (outcome, key)
        assert components._change(float(row.ratio_low_yty)) in since, (outcome, key)
        assert components._change(float(row.ratio_high_yty)) in since, (outcome, key)
    assert "licence holder" not in since and "registered vehicle" not in since
    dispersion = pd.read_csv(TABLES_DIR / "risk_dispersion.csv").set_index("outcome")
    assert components._fmt_dec(dispersion.loc["deaths_30d", "dispersion"]) in since
    # The projection under other choices is a technical note on the methodology page; the
    # measured-kilometre check, with its figure in the notes, is stated on the page itself.
    data = (built / "data.html").read_text(encoding="utf-8")
    notes = data[data.index('id="long-run-method"') :]
    notes = notes[: notes.index("<h2", 1)]
    assert 'src="figures/l4_km_against_fuel.svg"' in notes and "l4_km" not in long_run
    assert "l2_observed_over_trend" not in long_run + notes
    assert 'href="tables/longrun_segments.csv"' in notes
    assert 'href="data.html#long-run-method"' in long_run
    assert "occupant" not in long_run.lower() and "per registered vehicle" not in long_run
    sensitivity = pd.read_csv(TABLES_DIR / "longrun_projection_sensitivity.csv")
    assert not {"normal_quantile", "joinpoint"} & set(sensitivity.variant)
    series = pd.read_csv(TABLES_DIR / "longrun_series.csv")
    assert set(series.measure) == {"count", "road_fuel"}
    fuel = series[(series.measure == "road_fuel") & (series.period == "projected")]
    last = fuel[fuel.year == fuel.year.max()].iloc[0]
    assert site._signed_pct(float(last.ratio) - 1, 0) in long_run
    # The per-km headline and the municipal-road gap beside it come from the tables.
    km_check = pd.read_csv(TABLES_DIR / "longrun_km_check.csv")
    per_km = km_check[km_check.measure == "per_km"]
    km_last = per_km[per_km.year == per_km.year.max()].iloc[0]
    # The per-km year is read against the trend's own range around it, not against the interval
    # of the ratio, which contains the ratio by construction.
    assert f"{components._fmt_pct(abs(float(km_last.ratio) - 1), 0)} above the trend" in long_run
    assert f"range of ±{components._fmt_pct(float(km_last.range_high) - 1, 0)}" in long_run
    coverage = pd.read_csv(TABLES_DIR / "longrun_km_coverage.csv")
    assert components._fmt_pct(float(coverage.outside_share.min())) in long_run
    assert components._fmt_pct(float(coverage.outside_share.max())) in long_run
    assert "carries more traffic" not in long_run and "carried more traffic" not in long_run
    assert "diagnostic" not in long_run
    assert "check on road fuel as a measure of traffic" in long_run
    # The long-run fall split into crashes per tonne of fuel and deaths per crash is one
    # paragraph and a table; the road-type comparison per measured kilometre lives on this page.
    assert "l3_frequency_severity" not in long_run
    assert 'href="tables/risk_frequency_severity.csv"' in long_run
    assert 'href="tables/road_class_risk.csv"' in long_run
    # The split is shown both ways and not attributed to severity (the home page leaves it to this
    # page); the per-fuel excess is shown under another start of the trend.
    assert "admitted to hospital" in long_run
    for page in (long_run, (built / "index.html").read_text(encoding="utf-8")):
        assert "mostly because crashes became less deadly" not in page
    assert 'href="tables/longrun_projection_sensitivity.csv"' in long_run
    # The per-fuel excess is qualified by the extra growth in kilometres per tonne that would
    # bring each of the last two years inside the trend's range, read from the drift table.
    fit_end = int(series[series.period == "fitted"].year.max())
    drifts = pd.read_csv(TABLES_DIR / "longrun_efficiency.csv")
    at_pace = drifts[drifts.hypothetical_extra_annual_gain == 0].set_index("year")
    for year in (int(fuel.year.max()) - 1, int(fuel.year.max())):
        needed = float(at_pace.loc[year, "ratio_low"]) ** (1 / (year - fit_end)) - 1
        assert f"{needed * 100:.1f}" in long_run, year
    assert "deaths per tonne of fuel would be" not in long_run
    assert "dual carriageways" not in long_run
    # The page gives each year's count since the count's last turning point.
    base = latest.loc[("deaths_30d", "road_fuel")]
    assert f"{components._fmt_pct(float(base.ratio_to_base) - 1)} above 2019" in notes
    counts = pd.read_csv(TABLES_DIR / "risk_annual_panel.csv").set_index("year").deaths_30d
    plateau = int(
        pd.read_csv(TABLES_DIR / "longrun_segments.csv").query("measure == 'count'").start.max()
    )
    for year in range(plateau, int(fuel.year.max()) + 1):
        assert f'<td class="num">{components._fmt_int(counts.loc[year])}</td>' in long_run, year
    assert "cannot be joined" not in long_run and "different method" not in long_run
    seasons = (built / "seasons.html").read_text(encoding="utf-8")
    for name in ("m1_season_profile", "m2_month_effects", "m3_lockdown"):
        assert f'src="figures/{name}.svg"' in seasons
    # Deaths are divided only by road fuel; under it July and August stay above 1.
    effects = pd.read_csv(TABLES_DIR / "season_month_effects.csv")
    assert set(effects.exposure) == {"none", "road_fuel_tonnes"}
    fuel_effects = effects[effects.exposure == "road_fuel_tonnes"].set_index("month")
    for month in (7, 8):
        assert fuel_effects.loc[month, "low"] > 1
        assert f"{float(fuel_effects.loc[month, 'rate_ratio']):.2f} times" in seasons
    assert "per unit of petrol" not in seasons.lower()


def test_every_internal_link_and_anchor_resolves(built: Path) -> None:
    pages = {p.name for p in built.glob("*.html")}
    ids = {
        p.name: set(re.findall(r'\sid="([^"]+)"', p.read_text(encoding="utf-8")))
        for p in built.glob("*.html")
    }
    for page in sorted(built.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("http://", "https://", "mailto:", "data:")):
                continue
            target, _, anchor = href.partition("#")
            if target:
                assert target in pages or (built / target).exists(), (page.name, href)
            if anchor:
                host = target or page.name
                assert host in ids, (page.name, href)
                assert anchor in ids[host], (page.name, href)


def test_every_page_has_a_description_and_every_image_an_alt(built: Path) -> None:
    for page in sorted(built.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        description = re.search(r'<meta name="description" content="([^"]*)"', text)
        assert description and len(description.group(1)) > 40, page.name
        if page.name == "index.html":
            assert "<title>Road safety in Spain</title>" in text
        else:
            assert re.search(r"<title>[^<]+ · Road safety in Spain</title>", text), page.name
        for image in re.findall(r"<img[^>]*>", text):
            alt = re.search(r'alt="([^"]*)"', image)
            assert alt and alt.group(1).strip(), (page.name, image[:80])
        _runs_no_script(page.stem, text)


def test_front_page_is_an_overview_of_the_study(built: Path) -> None:
    index = (built / "index.html").read_text(encoding="utf-8")
    body = index[index.find("<main>") : index.find("</main>")]
    # What the study measures, the way into the tools, then the main findings and the pages: no
    # numbered questions, no number tiles, boxed blocks or figures, and the page opens on a
    # summary paragraph.
    headings = re.findall(r"<h2[^>]*>([^<]+)</h2>", body)
    assert headings == ["Main findings", "The pages"]
    assert '<div class="finding">' not in body and "Finding 1" not in body
    assert "finding-value" not in body and "provenance" not in body
    assert "<figure" not in body
    assert body.find('<p class="summary">') < body.find("<h2")
    opening = re.search(r'<p class="summary">(.*?)</p>', body, re.S).group(1)
    assert "association" in opening
    # The interactive tools are linked straight after the opening, before the findings.
    assert body.find(opening) < body.find('href="explore.html"') < body.find("<h2")
    sections = dict(zip(headings, re.split(r"<h2[^>]*>[^<]+</h2>", body)[1:]))
    # Three to five findings, each one sentence led by its answer and linked to its page.
    findings = re.search(r'<ul class="findings">(.*?)</ul>', body, re.S).group(1)
    items = re.findall(r"<li>(.*?)</li>", findings, re.S)
    assert 3 <= len(items) <= 5
    for item in items:
        assert item.count("<strong>") == 1 and item.startswith("<p><strong>")
        sentence = components.html.unescape(re.sub(r"<[^>]+>", "", item.split("</p>")[0]))
        assert sentence.endswith(".") and not re.search(r"\.\s+[A-Z]", sentence), sentence
        assert re.search(r'<p class="finding-more"><a href="[a-z-]+\.html', item), item
    for slug in ("long-run", "drivers", "factors", "severity-models"):
        assert f'href="{slug}.html' in sections["Main findings"], slug
    # The list of pages follows the navigation's groups and lists every page once.
    groups = re.findall(r"<h3[^>]*>([^<]+)</h3>", sections["The pages"])
    assert groups == [group for group, _ in site.NAV_GROUPS][1:]
    linked = re.findall(r'href="([a-z-]+)\.html"', sections["The pages"])
    assert sorted(linked) == sorted(slug for slug, _ in site.ALL_PAGES if slug != "index")
    # The headline numbers are computed from the tables.
    risk = pd.read_csv(TABLES_DIR / "risk_index.csv")
    latest = risk[(risk.year == risk.year.max()) & (risk.outcome == "deaths_30d")]
    deaths = latest[latest.denominator == "count"].iloc[0]
    assert components._fmt_int(deaths["count"]) in sections["Main findings"]
    counts = pd.read_csv(TABLES_DIR / "risk_annual_panel.csv").set_index("year").deaths_30d
    steep_end = int(
        pd.read_csv(TABLES_DIR / "longrun_segments.csv").query("measure == 'count'").start.max()
    )
    first = int(counts.index.min())
    assert "fell by about three quarters" in sections["Main findings"]
    assert (
        f"{components._fmt_int(counts.loc[first])} people died in {first}, "
        f"{components._fmt_int(counts.loc[steep_end])} in {steep_end}"
    ) in sections["Main findings"]
    heavy = (
        pd.read_csv(TABLES_DIR / "sev_contrasts.csv")
        .query("base == 'interurban'")
        .set_index(["input", "level"])
        .loc[("users", "heavy_vehicle")]
    )
    assert (
        f"{heavy.ratio:.1f} times as high with a lorry or bus involved (95% interval "
        f"{heavy.ratio_low:.1f}–{heavy.ratio_high:.1f})"
    ) in sections["Main findings"]
    severity = pd.read_csv(TABLES_DIR / "risk_severity_and_licences.csv").set_index("group")
    old = severity.loc["75+"]
    finding = sections["Main findings"]
    assert f"{old.killed_ratio_to_45_64:.1f} times as often" in finding
    assert f"(95% interval {old.killed_ratio_low:.1f}–{old.killed_ratio_high:.1f})" in finding
    ranges = pd.read_csv(TABLES_DIR / "risk_national_ranges.csv")
    young = ranges[(ranges.measure == "involved per km") & (ranges.group == "18-29")].iloc[0]
    # Involvement per km by the driver's age, the central estimate from the table to one decimal,
    # with its sampling interval and the range under other assumptions beside it; the caveat on
    # the older groups is said once, on the drivers page, not here.
    assert f"{young.ratio:.1f} times as often as drivers aged 45–64" in finding
    assert f"{young.ratio_low:.1f}–{young.ratio_high:.1f}" in finding
    assert f"{young.range_min:.1f}–{young.range_max:.1f}" in finding
    assert "Madrid" not in finding
    # The sampling interval and the range are linked to their definitions at first use.
    methodology = (built / "data.html").read_text(encoding="utf-8")
    for term in ("Sampling interval", "Sensitivity range"):
        anchor = components.DEFINITION_IDS[term]
        assert f'href="data.html#{anchor}"' in finding, anchor
    for anchor in components.DEFINITION_IDS.values():
        assert f'<dt id="{anchor}">' in methodology, anchor
    # Drivers aged 75 and over: the deaths once involved, a count that needs no kilometres, and
    # a link to where the drivers page sets it out; no per-km figure for them here.
    assert 'href="drivers.html#deaths-once-a-crash-has-happened"' in finding
    assert "nearly seven" not in finding
    # A reader can follow the front page without the modelling vocabulary of the deeper pages.
    visible = re.sub(r"<[^>]+>", " ", body)
    for jargon in ("ROC-AUC", "calibration slope", "Jensen", "transportab", "odds ratio"):
        assert jargon not in visible, jargon
    assert "tested only within Catalonia" in sections["Main findings"]
    assert site.PROFILE_URL in index and "Russell Howard" in index
    # Short, and nothing from the withdrawn external-study models.
    assert len(body) < 7_500
    data = (built / "data.html").read_text(encoding="utf-8")
    for text in (body, data):
        for phrase in ("simulator", "Power Model", "DRUID", "Dingus", "per unit of traffic"):
            assert phrase not in text, phrase


def test_any_closing_synthesis_follows_the_evidence(built: Path) -> None:
    # A page keeps a closing synthesis only where it adds to the summary; where it has one, the
    # synthesis is the last thing in the argument, not a box in the middle of it.
    for slug in ANALYSIS_PAGES + ("severity", "policy") + REGIONAL_PAGES:
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        body = text[text.find("<main>") : text.find("</main>")]
        assert body.count('<div class="conclusion">') <= 1, slug
        if '<div class="conclusion">' in body:
            assert body.rfind('<div class="conclusion">') > body.rfind("<table>"), slug


def test_supporting_pages_name_their_group(built: Path) -> None:
    # The section line above the title names the page's group; the prose does not restate the
    # site's structure.
    for slug, group in (("severity", "Crash severity"), ("policy", "Over time")):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        body = text[text.find("<main>") : text.find("</main>")]
        assert body.startswith(
            f'<main>\n<header class="page-header" id="content">\n<p class="eyebrow">{group}</p>'
        ), slug
        assert "Supporting analysis." not in body and "supporting analysis" not in body, slug


def test_no_page_uses_an_em_dash(built: Path) -> None:
    # House style: colons, commas, brackets and full stops instead. Checked on the rendered
    # pages because the prose is assembled from many fragments.
    for page in sorted(built.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        assert "\u2014" not in text, page.name
        assert "&mdash;" not in text, page.name


def test_the_development_note_is_professional_and_present(built: Path) -> None:
    data = (built / "data.html").read_text(encoding="utf-8")
    assert "reproducible, source-driven workflow" in data
    assert "AI coding assistants were used during implementation" in data
    assert "are the author's" in data
    for page in built.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        if page.name != "data.html":
            assert "Claude Code" not in text


def test_methodology_lists_every_assumption_the_methods_document_tests(built: Path) -> None:
    data = (built / "data.html").read_text(encoding="utf-8")
    main = data[data.find("<main>") : data.find("</main>")]
    # The glossary and the denominators are definition lists, not bulleted lists with bold leads.
    assert '<dl class="facts" aria-label="Definitions">' in main
    assert '<dl class="facts" aria-label="Denominators">' in main
    assert "<li><strong>" not in main
    # One row on the page for each row of the methods document's table of assumptions tested.
    doc = (TABLES_DIR.parents[1] / "docs" / "methodology.md").read_text(encoding="utf-8")
    section = doc[doc.index("## 12. Assumptions tested") :]
    section = section[: section.index("\n## ", 1)]
    documented = [line for line in section.splitlines() if line.startswith("| ")][1:]
    block = main[main.index('id="assumptions-tested"') :]
    body = block[block.index("<tbody>") : block.index("</tbody>")]
    rows = re.findall(r"<tr>(.*?)</tr>", body, re.S)
    rows = [re.sub(r"<[^>]+>", " ", components.html.unescape(row)) for row in rows]
    assert len(rows) == len(documented) >= 10
    text = {row.split("  ")[0].strip(): " ".join(row.split()) for row in rows}

    def row(start: str) -> str:
        return next(value for key, value in text.items() if key.startswith(start))

    # The transfer of the averaged regional age profiles cannot be tested; the ranges are the
    # recomputations under the alternatives.
    transfer = row("The average of the Barcelona-area and Madrid age profiles")
    assert "cannot be tested" in transfer and "are recomputed" in transfer
    ranges = pd.read_csv(TABLES_DIR / "risk_national_ranges.csv")
    ranges = ranges[ranges.measure == "involved per km"].set_index("group")
    young = ranges.loc["18-29"]
    assert f"{young.range_min:.1f}–{young.range_max:.1f} at 18–29" in transfer
    # The split at 75 is a conditional estimate beside its range, which includes 1.
    oldest = row("People aged 75 and over drive as much less")
    split = pd.read_csv(TABLES_DIR / "risk_older_split.csv")
    split = split[split.profile == national.CENTRAL_METHOD]
    madrid = split[(split.assumption == national.REFERENCE_SPLIT) & (split.group == "75+")].iloc[0]
    assert "Conditional." in oldest and "not established" in oldest
    assert f"{madrid.ratio_to_45_64:.1f} times the 45–64 rate" in oldest
    assert f"{ranges.loc['75+', 'range_min']:.1f}–{ranges.loc['75+', 'range_max']:.1f}" in oldest
    assert not any(key.startswith("The owner's age stands") for key in text)
    # The rows added by the national corrections carry numbers from their tables.
    split = pd.read_csv(TABLES_DIR / "risk_frequency_severity.csv").set_index("year").iloc[-1]
    fall = components._fmt_pct(1 - float(split.deaths_per_fuel_index) / 100, 0)
    assert f"Deaths per tonne fell {fall}" in row("The fall in deaths per tonne")
    panel = pd.read_csv(TABLES_DIR / "risk_annual_panel.csv").set_index("year")
    ratio = panel.deaths_30d / panel.deaths_24h
    for year in (2010, 2011):
        assert f"{ratio.loc[year]:.3f} in {year}" in row("The 30-day death series")
    # The 2011 fall in the ratio is a dip that recovers, not a lasting step.
    assert "temporary dip" in row("The 30-day death series")
    assert "a step in the ratio" not in row("The 30-day death series")
    # Poisson variation is rejected for admissions and crashes only; for deaths the interval
    # of the dispersion includes 1.
    scatter_rows = pd.read_csv(TABLES_DIR / "risk_dispersion.csv").set_index("outcome")
    chance = row("A year's count varies")
    assert scatter_rows.loc["deaths_30d", "dispersion_low"] < 1
    assert "Not established for deaths" in chance
    assert "any of the three counts" not in chance
    projection = pd.read_csv(TABLES_DIR / "longrun_projection_sensitivity.csv")
    later = projection[
        (projection.measure == "road_fuel")
        & (projection.variant.isin(["main"]) | projection.variant.str.startswith("start_"))
        & (projection.year >= projection.year.max() - 1)
    ]
    for value in later.ratio:
        assert components._fmt_pct(float(value) - 1, 0) in row("The excess of deaths per tonne")
    # The dispersion factors are given on the long-run page, not repeated here: the factor as a
    # number of its own, not the last digits of another ratio in the text.
    scatter = pd.read_csv(TABLES_DIR / "risk_dispersion.csv").set_index("outcome").dispersion
    factor = components._fmt_dec(scatter["crashes"], 0)
    assert not re.search(rf"(?<![\d.,]){re.escape(factor)} times", main)


def test_coding_breaks_describe_the_inverted_catalan_junction_flag(built: Path) -> None:
    from dgt_stats.microdata.validation import dgt_audit

    data = (built / "data.html").read_text(encoding="utf-8")
    # The four changes and how the series are read, up to the fog and strong-wind fields.
    block = data[data.index('id="coding-breaks"') :]
    block = components.html.unescape(block[: block.index("<p>The fog and strong-wind fields")])
    assert "the junction flag the wrong way round" in block
    assert "changes how it marks a missing value" not in block
    matched = dgt_audit.catalan_junction_years(
        pd.read_csv(TABLES_DIR / "dgt_audit_junction_coding.csv")
    )
    first = matched[matched.junction_flag_inverted].iloc[0]
    assert components._fmt_pct(first.dgt_share_at_junction) in block
    assert components._fmt_pct(first.cat_share_between_junctions) in block
    # The "other" road group and code 14 are named apart.
    assert "“other” road group" in block and "code 14" in block
    # How the association analysis treats the inverted years, from the table it reads.
    assert "reads the flag the other way round in those province-years" in block
    assert "read from the years before it" not in block
    read = pd.read_csv(TABLES_DIR / "q3_junction_coding.csv")
    read = read[(read.region == "Catalonia") & (read.recoded > 0)]
    for row in read.itertuples():
        assert f"{components._fmt_pct(row.share_at_junction, 0)} in {row.year}" in block
    # The year whose records count only crashes within a junction is named, and left out of the
    # range given for the earlier years.
    narrow = matched[matched.dgt_at_junction_matches == "within a junction"]
    assert len(narrow) == 1
    year = int(narrow.year.iloc[0])
    assert f"In {year} the records use a narrower definition of a junction" in block
    assert "under the narrower definition below" in block


def test_coding_breaks_name_the_fog_and_wind_fields_coded_another_way(built: Path) -> None:
    from dgt_stats.microdata.validation import dgt_audit

    data = (built / "data.html").read_text(encoding="utf-8")
    start = data.index('id="coding-breaks"')
    block = components.html.unescape(data[start : data.index('id="models"', start)])
    presence = pd.read_csv(TABLES_DIR / "dgt_audit_presence_coding.csv")
    breaks = dgt_audit.presence_breaks(presence)
    fog = breaks[breaks.field == "CONDICION_NIEBLA"].iloc[0]
    assert fog.province_name == "Barcelona"
    assert f"From {min(fog.years)} the records for the province of Barcelona code fog" in block
    assert (
        f"{components._fmt_pct(fog.share_low, 0)} to {components._fmt_pct(fog.share_high, 0)}"
        in block
    )
    assert "neither a value nor a blank says whether there was fog or strong wind" in block
    records = data[data.index('id="records"') : start]
    assert "apart from a few province-years that code them another way" in components.html.unescape(
        records
    )


def test_the_missing_values_figure_leaves_not_applicable_out(built: Path) -> None:
    """The records section's figure and its text judge each field where it applies, read a blank
    fog or wind field as the recorded "no", and leave the junction-only fields out."""
    data = (built / "data.html").read_text(encoding="utf-8")
    block = data[data.index('id="records"') : data.index('id="coding-breaks"')]
    block = components.html.unescape(block)
    assert "figure leaves “not applicable” out of each field's share" in block
    assert "In the figure an empty fog or strong-wind field counts as recorded" in block
    assert "so they are not drawn" in block
    captions = json.loads((FIGURES_DIR / "captions.json").read_text(encoding="utf-8"))
    caption = captions["d1_missingness"]
    assert "fog or strong wind field counts as recorded" in caption
    assert "and are not drawn" in caption
    assert "kilometre post field" in caption
    assert "the flag is read the other way round" not in caption
    assert "recorded less often" not in caption


def test_navigation_groups_its_pages_under_labels(built: Path) -> None:
    text = (built / "factors.html").read_text(encoding="utf-8")
    nav = re.search(r'<nav aria-label="Sections">(.*?)</nav>', text, re.S).group(1)
    labels = re.findall(r'<span class="nav-label" id="(label-[a-z-]+)">([^<]+)</span>', nav)
    # Every section but the overview link is labelled, in navigation order.
    assert [label for _, label in labels] == [group for group, _ in site.NAV_GROUPS][1:]
    # Every link sits in a list labelled by its group, opened by a button that names the group;
    # no label is itself a link, so a group's name can never be mistaken for a page. The section
    # holding the current page says so.
    for anchor, label in labels:
        menu = anchor.replace("label-", "menu-")
        assert f'<ul class="nav-menu" id="{menu}" aria-labelledby="{anchor}">' in nav
        assert re.search(rf'aria-expanded="false" aria-controls="{menu}">{label}[<]', nav)
    assert nav.count("(current section)") == 1
    assert "<li>Supporting analyses</li>" not in nav
    links = re.findall(r'href="([a-z-]+)\.html"', nav)
    assert links == [slug for _, pages in site.NAV_GROUPS for slug, _ in pages]
    # A page names its section and links to its neighbours in reading order.
    assert '<p class="eyebrow">Drivers, vehicles and factors</p>' in text
    assert 'href="vehicles.html" rel="prev"' in text and 'href="severity.html" rel="next"' in text
    # Each group leads on to the next in reading order.
    for slug, before, after in (
        ("policy", "seasons", "drivers"),
        ("factors", "vehicles", "severity"),
        ("severity-models", "barcelona", "sources"),
    ):
        page = (built / f"{slug}.html").read_text(encoding="utf-8")
        pager = re.search(r'<nav class="pager"[^>]*>(.*?)</nav>', page, re.S).group(1)
        assert f'href="{before}.html" rel="prev"' in pager, slug
        assert f'href="{after}.html" rel="next"' in pager, slug


def test_drivers_page_chains_crashes_and_deaths_per_crash(built: Path) -> None:
    # Deaths per km, the two measures combined, are set out in the drivers page's technical notes.
    text, _, _ = _driver_notes(built)
    rates = pd.read_csv(TABLES_DIR / "risk_national_rates.csv")
    for _, row in rates.iterrows():
        # Involved per km x killed per involved = killed per km, in every profile.
        per_involved = row.killed / row.involved
        assert row.involved_per_bn_km * per_involved == pytest.approx(row.killed_per_bn_km)
    assert "km_total" not in rates.columns
    central = rates[rates.method == national.CENTRAL_METHOD].set_index("group")
    older = central.loc["65+"]
    assert f"{older.killed_ratio:.1f} times as often per kilometre" in text
    assert f"{older.killed_ratio_low:.1f}–{older.killed_ratio_high:.1f}" in text


def test_vehicles_page_quotes_per_km_rates_for_all_roads_only(built: Path) -> None:
    text = (built / "vehicles.html").read_text(encoding="utf-8")
    summary = pd.read_csv(TABLES_DIR / "q6_summary_2022.csv").set_index("group")
    truck, car, bike = summary.loc["heavy_truck"], summary.loc["car"], summary.loc["motorcycle"]
    per_vehicle = (
        truck.fatal_involvement_per_100k_vehicles / car.fatal_involvement_per_100k_vehicles
    )
    per_km = truck.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km
    assert f"{per_vehicle:.1f} times" in text and f"{per_km:.1f} times" in text
    # The weight class of a vehicle label never breaks across lines.
    assert "3,500\u00a0kg" in text and "3,500 kg" not in text
    # The occupant shares are computed, not typed.
    assert f"{bike.occupant_deaths_per_fatal_involvement:.2f} for a motorcycle" in text
    assert f"A figure of {truck.occupant_deaths_per_fatal_involvement:.2f}" in text
    # The table has all-roads rows only, and the intervals are said to cover the counts only.
    rates = pd.read_csv(TABLES_DIR / "q6_rates_2022.csv")
    assert "zone" not in rates.columns and rates.per_billion_km.notna().all()
    assert "not the uncertainty of the modelled kilometres" in text
    # At most one closing synthesis, and only after the evidence; no generic heading.
    conclusions = text.count('<div class="conclusion">')
    assert conclusions <= 1
    if conclusions:
        assert text.rfind("</table>") < text.find('<div class="conclusion">')
    assert "Interpretation" not in text
