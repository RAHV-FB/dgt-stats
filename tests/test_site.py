import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dgt_stats import site, summaries
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR
from dgt_stats.site import components
from dgt_stats.site.script import JS_FLAG

# The national analysis pages in navigation order; then the regional, model, validation and
# sources pages.
ANALYSIS_PAGES = tuple(slug for slug, _ in components.SPAIN_PAGES)
REGIONAL_PAGES = ("catalonia", "barcelona", "severity-models", "validation", "sources")

pytestmark = pytest.mark.skipif(
    not (FIGURES_DIR / "captions.json").exists()
    or not (TABLES_DIR / "q1_annual_headline.csv").exists()
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
    # The navigation follows the questions a reader brings: deaths over time; drivers, vehicles
    # and recorded factors; how deadly a crash is once it has happened; and the data and methods.
    # A pointer for each page that was renamed, and a notice for each withdrawn analysis.
    assert [group for group, _ in site.NAV_GROUPS] == [
        "Overview",
        "Over time",
        "Drivers, vehicles and factors",
        "Crash severity",
        "Data and methods",
    ]
    assert len(site.PAGES) == 14 and len(site.SUPPORTING_PAGES) == 2
    assert [slug for slug, _ in dict(site.NAV_GROUPS)["Crash severity"]] == [
        "severity",
        "catalonia",
        "barcelona",
        "severity-models",
        "validation",
    ]
    expected = (
        {slug for slug, _ in site.ALL_PAGES} | set(site.MOVED_PAGES) | set(site.WITHDRAWN_PAGES)
    )
    assert expected == {p.stem for p in built.glob("*.html")}
    # The site's one site-wide script is its own reading aid; the withdrawn models' scripts and
    # registers are not shipped. The calculator's engine, page script and exported model live
    # apart in models/, and only its page loads them.
    assert [p.name for p in built.glob("*.js")] == ["site.js"]
    assert sorted(p.name for p in (built / "models").iterdir()) == [
        "severity-calculator.js",
        "severity-engine.js",
        "severity_model.json",
    ]
    published = {p.name for p in (built / "tables").glob("*.csv")}
    assert not published & {"simulator_evidence.csv", "factor_evidence.csv"}


CALCULATOR_SCRIPTS = [
    '<script src="models/severity-engine.js" defer>',
    '<script src="models/severity-calculator.js" defer>',
]


def _runs_no_script(slug: str, text: str) -> None:
    """No page runs a script of its own, except the calculator: the simulator and factor models
    that did were withdrawn.

    Every page loads the site's reading aid (menus and contents), after a one-line flag that says
    scripting is on; the severity model's page also loads the calculator's engine and page
    script, which compute only from the exported model.
    """
    expected = ["<script>", '<script src="site.js" defer>']
    if slug == "severity-models":
        expected += CALCULATOR_SCRIPTS
    assert re.findall(r"<script[^>]*>", text) == expected, slug
    assert JS_FLAG in text, slug


def test_moved_pages_point_to_their_successors(built: Path) -> None:
    for old, new in site.MOVED_PAGES.items():
        text = (built / f"{old}.html").read_text(encoding="utf-8")
        assert f'content="0; url={new}.html"' in text
        assert f'href="{new}.html">' in text
        # Kept out of search indexes, with no canonical link to contradict that.
        assert '<meta name="robots" content="noindex">' in text, old
        assert 'rel="canonical"' not in text, old
    # No live page links to a moved slug: the pointers are for old bookmarks, not navigation.
    for slug, _ in site.ALL_PAGES:
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        for moved in site.MOVED_PAGES:
            assert f'href="{moved}.html"' not in text, (slug, moved)


def test_withdrawn_pages_say_why_and_nothing_links_to_them(built: Path) -> None:
    external = {"simulator", "distraction", "alcohol-drugs", "enforcement"}
    assert set(site.WITHDRAWN_PAGES) == external | {"forecast"}
    live = {slug for slug, _ in site.ALL_PAGES}
    for slug, reason in site.WITHDRAWN_PAGES.items():
        assert slug not in live and slug not in site.MOVED_PAGES, slug
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        body = text[text.find("<main>") : text.find("</main>")]
        # A short notice, not a redirect: it says why the analysis went and links to the data.
        assert 'http-equiv="refresh"' not in text and 'rel="canonical"' not in text, slug
        if slug in external:
            assert "withdrawn because its results came from coefficients published in " in text
            assert "rather than from data in this repository" in text
        else:
            assert site.esc("less accurately than last year's count") in text
        assert site.esc(reason) in body, slug
        # The reason is stated once, in the lead; the body says what the page published.
        assert body.count("withdrawn because") == 1, slug
        assert "holds no" not in body and "so it was withdrawn" not in body, slug
        if slug == "forecast":
            assert body.count("less accurately") == 1
        assert 'href="data.html"' in body, slug
        assert '<div class="conclusion">' not in body and "<table>" not in body, slug
        assert len(body) < 4000, slug
    # The simulator's notice points to the speed page, and the forecast's to the trend pages.
    assert 'href="speed.html"' in (built / "simulator.html").read_text(encoding="utf-8")
    forecast = (built / "forecast.html").read_text(encoding="utf-8")
    assert 'href="long-run.html"' in forecast and 'href="trends.html"' in forecast
    # No live or moved page links to a withdrawn slug.
    for slug in live | set(site.MOVED_PAGES):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        for withdrawn in site.WITHDRAWN_PAGES:
            assert f'href="{withdrawn}.html"' not in text, (slug, withdrawn)


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
    assert {f"{name}.csv" for name in summaries.SUMMARIES} <= published
    assert {f"{name}.csv" for name in summaries.MODEL_TABLES} <= published
    assert "validation.csv" in published
    # Every page that shows a headline number also links the table it came from.
    for slug in ANALYSIS_PAGES + ("severity", "policy"):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        assert 'href="tables/' in text, slug


def test_figures_are_copied_and_captioned(built: Path) -> None:
    # Exactly the figures the pages show are published, each with its drawing for a phone.
    shown = {
        name
        for page in built.glob("*.html")
        for name in re.findall(r'<img src="figures/([^"/]+)\.svg"', page.read_text("utf-8"))
    }
    published = {p.stem for p in (built / "figures").glob("*.svg")}
    assert published == shown and len(shown) > 25
    assert {p.stem for p in (built / "figures" / "narrow").glob("*.svg")} == shown
    for path in (built / "figures").rglob("*.svg"):
        source = FIGURES_DIR / path.relative_to(built / "figures")
        assert path.read_bytes() == source.read_bytes(), path.name
    # A figure that is drawn but shown on no page, such as the models' test ROC-AUC chart, is
    # not published.
    captions = site.read_captions()
    for name in set(captions) - shown:
        assert not (built / "figures" / f"{name}.svg").exists(), name
    assert "ml1_test_auc" in captions and "ml1_test_auc" not in published
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
    adverse = pd.read_csv(TABLES_DIR / "q3_adverse_conditions.csv")
    fatal = adverse[adverse.outcome == "fatal"].set_index(["variant", "level"])
    wet_alone = float(fatal.loc[("no_weather", "wet"), "odds_ratio"])
    # The headline number is computed from the table, not typed.
    assert f"{wet_alone:.2f} times the odds" in text
    assert "Odds ratios for the adverse conditions under every model variant" in text
    assert 'src="figures/s2_adverse_conditions.svg"' in text
    assert 'src="figures/s1_forest_fatal.svg"' in text
    # The page says what kind of analysis it is, and the distinction the finding depends on.
    assert "an analysis of associations, not a predictive model" in text
    assert "nothing about how often crashes happen" in text
    # No outside study explains the associations, and the subtitle claims no explanation.
    for phrase in ("doi.org", "literature", "et al", "point the wrong way", "Naturalistic"):
        assert phrase not in text, phrase
    # The missing-value levels are nuisance terms: flagged, quantified by province and refitted
    # without the provinces that record most of them; the numbers come from the tables.
    coefficients = pd.read_csv(TABLES_DIR / "q3_model_coefficients.csv")
    nuisance = coefficients[coefficients.is_nuisance.astype(bool)]
    assert set(nuisance.level) <= {"unknown", "not specified", "not applicable"}
    regime = pd.read_csv(TABLES_DIR / "q3_recording_regime.csv").set_index(["predictor", "level"])
    alignment = regime.loc[("alignment", "unknown")]
    assert components._fmt_pct(float(alignment.catalan_share_of_level)) in text
    assert components._fmt_pct(float(alignment.share_of_catalan_crashes)) in text
    assert 'href="tables/q3_regime_sensitivity.csv"' in text
    sensitivity = pd.read_csv(TABLES_DIR / "q3_regime_sensitivity.csv")
    wet = sensitivity[(sensitivity.outcome == "fatal") & (sensitivity.level == "wet")].iloc[0]
    assert f"{wet.odds_ratio_without:.2f}" in text
    # The holdout is reported with its Brier skill against the training years' base rate.
    holdout = pd.read_csv(TABLES_DIR / "q3_holdout_summary.csv").set_index("outcome")
    assert components._fmt_pct(float(holdout.loc["fatal", "brier_skill"])) in text
    # The full coefficient table is linked, not printed.
    assert 'href="tables/q3_model_coefficients.csv"' in text
    assert text.count("<table>") <= 4
    # The summary names location beside crash type, from the joint zone and road-type contrast,
    # and gives the junction association by coding period, not pooled across the change.
    opening = re.search(r'<p class="summary">(.*?)</p>', text, re.S).group(1)
    locations = pd.read_csv(TABLES_DIR / "q3_location_contrasts.csv")
    conventional = locations[
        (locations.outcome == "fatal")
        & (locations.zone == "interurban road")
        & (locations.road == "conventional")
    ].iloc[0]
    assert f"{conventional.odds_ratio:.2f} times the odds" in opening
    assert "side or front-side collision" in opening
    periods = pd.read_csv(TABLES_DIR / "q3_period_refits.csv")
    junction = periods[
        (periods.outcome == "fatal")
        & (periods.level == "at a junction")
        & (periods.scope == "all provinces")
    ].set_index("period")
    for period in ("before", "from"):
        assert f"({junction.loc[period, 'odds_ratio']:.2f}" in opening
    assert "in every model variant, and so does that of the junction" not in text
    # The ranking is quoted with what the missing-value levels contribute to it, as ROC-AUC to
    # two decimals, the scale of the severity model and validation pages.
    recorded_only = holdout.loc["fatal", "auc_recorded_only"]
    missing_only = holdout.loc["fatal", "auc_missing_only"]
    assert f"death scores {recorded_only:.2f}, and those levels on their own" in text
    assert f"on their own {missing_only:.2f}" in text
    assert "the two regressions keep their ordering" in text
    assert "times in 100" not in text
    # The page leads with what the records show: the results come first, then what the records
    # cannot show, and only then the description of the records and the regressions.
    main = text[text.find("<main>") : text.find("</main>")]
    headings = re.findall(r"<h2[^>]*>(.*?)</h2>", main, re.S)
    assert headings[0] == "Crash type and location go most strongly with a death"
    assert headings[1].startswith("Lower odds of a death on wet roads")
    assert headings.index("The records and the regressions") > 2
    assert main.find("s1_forest_fatal") < main.find("s2_adverse_conditions")
    # The opening paragraph names the other two pages on severity, once each, with their
    # populations and definitions.
    assert opening.count('href="catalonia.html"') == opening.count('href="barcelona.html"') == 1
    assert "within 30 days" in opening and "within 24 hours" in opening
    # The weekend is defined, and the file's per-crash counts are not called absent.
    assert "from 20:00 on Friday" in text
    assert "no fields for drivers" not in text


def test_drivers_page_separates_the_two_questions(built: Path) -> None:
    text = (built / "drivers.html").read_text(encoding="utf-8")
    body = text[text.find("<main>") : text.find("</main>")]
    rates = pd.read_csv(TABLES_DIR / "risk_national_rates.csv")
    rates = rates[rates.km_total == "less taxi and ride-hailing"]
    central = rates[rates.method.str.startswith("A:")].set_index("group")
    severity = pd.read_csv(TABLES_DIR / "risk_severity_and_licences.csv").set_index("group")
    young, older = central.loc["18-29"], central.loc["65+"]
    # The page leads with involvement per km by driver age, quoted with its interval; the numbers
    # come from the tables, and no big-number callout repeats the summary.
    opening = re.search(r'<p class="summary">(.*?)</p>', body, re.S).group(1)
    assert f"{young.involved_ratio_low:.2f}–{young.involved_ratio_high:.2f}" in opening
    assert f"{older.involved_ratio:.2f}" in opening
    assert f"{severity.loc['75+', 'killed_per_1000_involved']:.1f}" in opening
    assert 'class="key-result"' not in body
    assert 'src="figures/dr1_involved_per_km.svg"' in body
    assert body.find("dr1_involved_per_km") < body.find("<table")
    # Intervals and sensitivity ranges are told apart, and the transfer is flagged as an estimate;
    # the range spans every alternative of the sensitivity table. For 65 and over, both ranges
    # are labelled wherever they are quoted together.
    spread = pd.read_csv(TABLES_DIR / "risk_national_sensitivity.csv").groupby("group")
    assert "sensitivity range" in body and "not measurements" in body
    assert f"{spread.involved_ratio.max()['65+']:.2f}" in body
    assert f"{spread.involved_ratio.min()['18-29']:.2f}" in body
    assert (
        f"(95% interval {older.involved_ratio_low:.2f}–{older.involved_ratio_high:.2f}; "
        f"sensitivity range {spread.involved_ratio.min()['65+']:.2f}–"
        f"{spread.involved_ratio.max()['65+']:.2f})"
    ) in opening
    # The opening says what involvement does not show: who caused the crash, or harm to others.
    assert "whoever caused it" in opening and "more dangerous to others" in opening
    # Table 1 names the rows of the published CSV it reproduces, and has no jargon column.
    assert f"method “{young.method}” and kilometre total “{young.km_total}”" in body
    assert "bootstrap replicates are not published" in body
    assert "licence-calibrated transfer</th>" not in body
    # No project process notes in the results.
    assert "request for the split" not in body
    # Barcelona's working-day check, the model-dependent oldest group, and deaths once involved.
    city = pd.read_csv(TABLES_DIR / "risk_barcelona_rates.csv")
    city = city[city.numerator == city.numerator.iloc[0]]
    assert "matched in place and time" not in body
    for value in city[city.age4 == "65+"].ratio_to_45_64:
        assert f"{value:.2f}" in body
    older_split = pd.read_csv(TABLES_DIR / "risk_older_split.csv")
    assert "model-dependent" in body and "no single figure is given" in body
    for value in older_split[older_split.group == "75+"].ratio_to_45_64:
        assert f"{value:.2f}" in body
    assert 'src="figures/dr2_killed_per_involved.svg"' in body
    assert "Powered by CRTM" in body and 'href="https://www.crtm.es"' in body
    # The former owner-age figures are explained, not hidden, and are no longer the result: a
    # short note closes the per-km section, with no section or table of its own.
    owner = pd.read_csv(TABLES_DIR / "risk_owner_age_comparison.csv")
    old = owner[owner.denominator.str.endswith("(former figure)")].set_index("group")
    same = owner[owner.denominator.str.endswith("same age groups")].set_index("group")
    # Compared like with like: the owner kilometres on today's age groups and reference.
    assert f"{same.loc['18-29', 'ratio_to_reference']:.2f} times the 45–64 rate" in body
    assert f"{old.loc['18-24', 'ratio_to_reference']:.2f}, compared drivers aged 18–24" in body
    assert "A car's owner is often not its driver" in body
    assert "Why the former figure differed" not in body and "Ratio to 35–54" not in body
    sections = re.split(r"<h2[^>]*>", body)
    per_km = next(s for s in sections if s.startswith("Crashes per kilometre"))
    assert "A car's owner is often not its driver" in per_km
    # The firm result, deaths once a crash has happened, follows the per-km section directly.
    headings = re.findall(r'<h2 id="([^"]+)"', body)
    assert headings[:2] == [
        "involvement-in-crashes-per-kilometre-driven",
        "deaths-once-a-crash-has-happened",
    ]
    for phrase in ("frailty", "travel-weighted", "extra travel", "nearly seven"):
        assert phrase not in text, phrase
    assert "doi.org" not in text  # no external study interprets these results
    # Sex: the ratio per driver involved is quoted with its interval and the ages are stated.
    sex = pd.read_csv(TABLES_DIR / "drivers_sex_ratios.csv").set_index(["scope", "band", "measure"])
    fatality_men = sex.loc[("car", "18+", "deaths_per_1000_involved")]
    killed_men = sex.loc[("car", "18+", "deaths_per_million_licences")]
    assert f"{fatality_men.ratio:.2f}" in text
    assert f"({fatality_men.low:.2f}–{fatality_men.high:.2f})" in text
    assert f"died at the wheel {killed_men.ratio:.2f}" in text
    # Per kilometre, from the survey's kilometres by sex carried to Spain as for age.
    per_km = pd.read_csv(TABLES_DIR / "risk_sex_per_km.csv").set_index("measure")
    assert f"{per_km.loc['involved per km', 'ratio_men_to_women']:.2f} times" in text
    assert "no source records kilometres" not in text
    assert "drivers_sex_travel" not in text
    assert 'src="figures/a3_sex_ratios.svg"' in text


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
    # The fall is not attributed to the licence, and the 2019 study is a collapsed note.
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
    assert "2019" in text and 'src="figures/q8_speed_series.svg"' not in text
    # The exposure series are named and their effect reported; the toll series is its
    # intensity, which does not step with the network's length, and no offset is used.
    assert "CORES" in text and "toll" in text and "intensity" in text
    assert "fleet_offset" not in set(sensitivity.index)
    toll = float(sensitivity.loc["toll", "level_change"])
    assert signed(toll) in text


def test_speed_page_carries_severity_and_the_recording_discontinuity(built: Path) -> None:
    text = (built / "speed.html").read_text(encoding="utf-8")
    pooled = pd.read_csv(TABLES_DIR / "speed_severity_pooled.csv").set_index("road_type")
    adjusted = pooled.loc["adjusted"]
    opening = re.search(r'<p class="summary">(.*?)</p>', text, re.S).group(1)
    assert f"{adjusted.rate_ratio:.2f} times" in opening
    assert f"{adjusted.ratio_low:.2f}–{adjusted.ratio_high:.2f}" in opening
    assert f"{adjusted.crude_ratio:.2f}" in opening  # the unadjusted ratio is shown beside it
    # The road-type ratios differ, so the summary gives their range and calls the adjusted ratio
    # a weighted summary; the home page says the same, with the pooled years.
    assert f"{pooled.loc['dual_carriageway', 'rate_ratio']:.2f} times on dual" in opening
    assert f"{pooled.loc['urban', 'rate_ratio']:.2f} times on urban streets" in opening
    assert "weighted summary" in opening
    home = (built / "index.html").read_text(encoding="utf-8")
    assert f"{pooled.loc['urban', 'rate_ratio']:.1f} times on urban streets" in home
    assert "Over 2016–2023, those crashes" in home
    # The summary says plainly that a recorded factor is an association, not a cause.
    assert "These are associations in police records, not estimates of what speed causes" in (
        opening
    )
    # The two biases are named, in both directions, and what a recorded factor is is explained
    # once, on the factors page, which this page links to.
    assert "which would raise it" in text and "which would lower it" in text
    assert 'href="factors.html#recorded-factors"' in text
    shares = pd.read_csv(TABLES_DIR / "q9_infraction_shares.csv")
    all_roads = shares[shares.zone == "all"].set_index("year")
    for year in (2014, 2016, int(all_roads.index.max())):
        assert f"{all_roads.loc[year, 'share_unknown'] * 100:.0f}%" in text
    assert 'src="figures/c3_speed_status.svg"' in text
    # Both readings of the broken driver tables are shown, so neither is read as a trend.
    for column in ("share_speed_infraction", "share_among_known"):
        for year in (2014, int(all_roads.index.max())):
            assert components._fmt_pct(float(all_roads.loc[year, column])) in text
    # Nothing on the page sizes speed's effect from outside the data, and the road-type mapping
    # is said to be checked only through the zone totals.
    for phrase in ("simulator", "Power Model", "physics"):
        assert phrase not in text, phrase
    assert "not road type by road type" in text
    # The transcribed speed report is not republished on the site: no table of the report's
    # breakdowns by limit, vehicle, licence class or hour survives anywhere.
    for page in built.glob("*.html"):
        page_text = page.read_text(encoding="utf-8")
        assert "by the road's speed limit" not in page_text, page.name
        assert "licence class" not in page_text, page.name


def test_factors_page_reads_trends_only_within_comparable_runs(built: Path) -> None:
    text = (built / "factors.html").read_text(encoding="utf-8")
    windows = pd.read_csv(TABLES_DIR / "factor_windows.csv")
    alcohol = windows[(windows.zone == "interurban") & (windows.factor == "Alcohol")]
    assert len(alcohol) == 1  # no recording break in the interurban alcohol series
    assert f"{alcohol.share_first.iloc[0] * 100:.1f}%" in text
    assert f"{alcohol.share_last.iloc[0] * 100:.1f}%" in text
    assert 'src="figures/f2_factor_shares.svg"' in text
    assert "break in comparability" in text and "Drugs" in text
    # A break is a threshold, never an explanation of what changed.
    assert "cannot say whether a break" in text and "from recording or from both" in text
    # The summary gives the fall in recorded speed within each kind of road, not only the
    # all-roads fall that the shift towards urban crashes enlarges, and makes no claim that the
    # recording is consistent.
    opening = re.search(r'<p class="summary">(.*?)</p>', text, re.S).group(1)
    speed = windows[windows.factor == "Inappropriate speed"].set_index("zone")
    for zone in ("interurban", "urban", "all"):
        assert f"{speed.loc[zone, 'share_last'] * 100:.1f}%" in opening
    assert "recording is consistent" not in opening and "point to changes in recording" not in text
    # The driver tables' break is set out once, on the speed page, which this page links to.
    assert 'href="speed.html#driver-tables"' in text


def test_trend_pages_show_every_denominator_and_the_projection(built: Path) -> None:
    trends = (built / "trends.html").read_text(encoding="utf-8")
    index = pd.read_csv(TABLES_DIR / "risk_index.csv")
    for label in index.denominator_label.unique():
        assert site.esc(label) in trends, label
    # Licence holders and the fleet divide only drivers and occupants, and the page says so.
    for label in index.numerator_label.unique():
        assert site.esc(label) in trends, label
    latest = index[index.year == index.year.max()].set_index(["outcome", "denominator"])
    for key in ("count", "residents", "licence_holders", "vehicles", "road_fuel"):
        change = components._change(float(latest.loc[("deaths_30d", key), "ratio_to_base"]))
        assert change in trends, key
    assert 'src="figures/r1_risk_change.svg"' in trends
    # The fuel-drift grid is a labelled hypothetical, not a per-kilometre finding.
    assert "roughly flat" not in trends and "per unit of traffic" not in trends
    assert "hypothetical" in trends
    long_run = (built / "long-run.html").read_text(encoding="utf-8")
    assert 'src="figures/l2_observed_over_trend.svg"' in long_run
    series = pd.read_csv(TABLES_DIR / "longrun_series.csv")
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
    # The long-run fall split into crashes per tonne of fuel and deaths per crash, and the
    # road-type comparison per measured kilometre, live on this page.
    assert 'src="figures/l3_frequency_severity.svg"' in long_run
    assert 'href="tables/road_class_risk.csv"' in long_run
    # The split is shown both ways and not attributed to severity; the per-fuel excess is shown
    # under another start of the trend; DGT's kilometre series is not called unjoinable.
    for page in (long_run, (built / "index.html").read_text(encoding="utf-8")):
        assert "mostly because crashes became less deadly" not in page
        assert "admitted to hospital" in page
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
    # The two pages answer 'has it got worse?' side by side: each states the other's comparison
    # and links to it, and the long-run page gives each year's count since the count's last
    # turning point.
    base = latest.loc[("deaths_30d", "road_fuel")]
    assert f"{components._fmt_pct(float(base.ratio_to_base) - 1)} higher" in long_run
    assert 'href="trends.html"' in long_run and 'href="long-run.html#recent-years"' in trends
    excess = [
        components._fmt_pct(float(ratio) - 1, 0)
        for ratio in fuel[fuel.year >= fuel.year.max() - 1].sort_values("year").ratio
    ]
    assert f"{excess[0]} and {excess[1]} above the projected trend" in trends
    counts = pd.read_csv(TABLES_DIR / "q1_annual_headline.csv").set_index("year").deaths_30d
    plateau = int(
        pd.read_csv(TABLES_DIR / "longrun_segments.csv").query("measure == 'count'").start.max()
    )
    for year in range(plateau, int(fuel.year.max()) + 1):
        assert f'<td class="num">{components._fmt_int(counts.loc[year])}</td>' in long_run, year
    for page in (trends, (built / "vehicles.html").read_text(encoding="utf-8")):
        assert "cannot be joined" not in page and "different method" not in page
    assert "deaths per tonne of fuel would show" not in trends
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
            if href.startswith(("http://", "https://", "mailto:")):
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
    # The answer first, then the main findings and the pages: no numbered questions, no number
    # tiles or boxed blocks, and the page opens on a summary paragraph.
    headings = re.findall(r"<h2[^>]*>([^<]+)</h2>", body)
    assert headings == ["Main findings", "The pages"]
    assert '<div class="finding">' not in body and "Finding 1" not in body
    assert "finding-value" not in body and "explore" not in body and "provenance" not in body
    assert body.find('<p class="summary">') < body.find("<h2")
    opening = re.search(r'<p class="summary">(.*?)</p>', body, re.S).group(1)
    assert "association" in opening and "fell by about three quarters" in opening
    sections = dict(zip(headings, re.split(r"<h2[^>]*>[^<]+</h2>", body)[1:]))
    # A short list of findings, each led by its answer in one sentence.
    findings = re.search(r'<ul class="findings">(.*?)</ul>', body, re.S).group(1)
    items = re.findall(r"<li>(.*?)</li>", findings, re.S)
    assert 4 <= len(items) <= 7
    for item in items:
        assert item.count("<strong>") == 1 and item.startswith("<p><strong>")
    for slug in ("trends", "long-run", "drivers", "speed", "factors", "severity-models"):
        assert f'href="{slug}.html' in sections["Main findings"], slug
    assert 'href="validation.html' in sections["Main findings"]
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
    severity = pd.read_csv(TABLES_DIR / "risk_severity_and_licences.csv").set_index("group")
    oldest = float(severity.loc["75+", "killed_per_1000_involved"]) / float(
        severity.loc["45-64", "killed_per_1000_involved"]
    )
    assert f"{oldest:.1f} times as often" in sections["Main findings"]
    rates = pd.read_csv(TABLES_DIR / "risk_national_rates.csv")
    young = rates[
        rates.method.str.startswith("A:")
        & (rates.km_total == "less taxi and ride-hailing")
        & (rates.group == "18-29")
    ].iloc[0]
    # Involvement per km by the driver's age, from the table, with its interval and the span of
    # the other assumptions.
    assert (
        f"{young.involved_ratio:.1f} times as often as drivers aged 45–64"
        in (sections["Main findings"])
    )
    spread = pd.read_csv(TABLES_DIR / "risk_national_sensitivity.csv").groupby("group")
    span = f"{spread.involved_ratio.min()['18-29']:.1f}–{spread.involved_ratio.max()['18-29']:.1f}"
    assert f"; {span} under other assumptions" in sections["Main findings"]
    assert "nearly seven" not in sections["Main findings"]
    # A reader can follow the front page without the modelling vocabulary of the deeper pages.
    visible = re.sub(r"<[^>]+>", " ", body)
    for jargon in ("ROC-AUC", "calibration slope", "Jensen", "transportab", "odds ratio"):
        assert jargon not in visible, jargon
    assert "tested only within Catalonia" in sections["Main findings"]
    assert site.PROFILE_URL in index and "Russell Howard" in index
    # Short, and nothing from the withdrawn external-study models.
    assert len(body) < 9_000
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

    # The transfer of one region's age profile is a sensitivity range, not a test.
    transfer = row("One region's age profile")
    assert "cannot be tested" in transfer and "sensitivity range" in transfer
    assert "was tested" not in transfer and "were tested" not in transfer
    # The rows added by the national corrections carry numbers from their tables.
    split = pd.read_csv(TABLES_DIR / "risk_frequency_severity.csv").set_index("year").iloc[-1]
    fall = components._fmt_pct(1 - float(split.deaths_per_fuel_index) / 100, 0)
    assert f"Deaths per tonne fell {fall}" in row("The fall in deaths per tonne")
    panel = pd.read_csv(TABLES_DIR / "risk_annual_panel.csv").set_index("year")
    ratio = panel.deaths_30d / panel.deaths_24h
    for year in (2010, 2011):
        assert f"{ratio.loc[year]:.3f} in {year}" in row("The 30-day death series")
    projection = pd.read_csv(TABLES_DIR / "longrun_projection_sensitivity.csv")
    later = projection[
        (projection.measure == "road_fuel")
        & (projection.variant.isin(["main"]) | projection.variant.str.startswith("start_"))
        & (projection.year >= projection.year.max() - 1)
    ]
    for value in later.ratio:
        assert components._fmt_pct(float(value) - 1, 0) in row("The excess of deaths per tonne")
    # The dispersion factors are given on the trends page, not repeated here.
    scatter = pd.read_csv(TABLES_DIR / "risk_dispersion.csv").set_index("outcome").dispersion
    assert f"{components._fmt_dec(scatter['crashes'], 0)} times" not in main


def test_forecast_page_is_withdrawn_and_says_why(built: Path) -> None:
    text = (built / "forecast.html").read_text(encoding="utf-8")
    body = text[text.find("<main>") : text.find("</main>")]
    assert '<meta name="robots" content="noindex">' in text
    assert "<img" not in body and "<table" not in body
    assert site.esc("last year's count") in body
    # Nothing on a live page links to it, and no figure of it survives.
    assert not (built / "figures" / "k1_forecast_check.svg").exists()
    assert not (built / "figures" / "k2_detectability.svg").exists()


def test_navigation_groups_its_pages_under_labels(built: Path) -> None:
    text = (built / "speed.html").read_text(encoding="utf-8")
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
    assert 'href="vehicles.html" rel="prev"' in text and 'href="factors.html" rel="next"' in text
    # Each group leads on to the next in reading order.
    for slug, before, after in (
        ("policy", "seasons", "drivers"),
        ("factors", "speed", "severity"),
        ("validation", "severity-models", "sources"),
    ):
        page = (built / f"{slug}.html").read_text(encoding="utf-8")
        pager = re.search(r'<nav class="pager"[^>]*>(.*?)</nav>', page, re.S).group(1)
        assert f'href="{before}.html" rel="prev"' in pager, slug
        assert f'href="{after}.html" rel="next"' in pager, slug


def test_drivers_page_chains_crashes_and_deaths_per_crash(built: Path) -> None:
    text = (built / "drivers.html").read_text(encoding="utf-8")
    rates = pd.read_csv(TABLES_DIR / "risk_national_rates.csv")
    for _, row in rates.iterrows():
        # Involved per km x killed per involved = killed per km, in every method and variant.
        per_involved = row.killed / row.involved
        assert row.involved_per_bn_km * per_involved == pytest.approx(row.killed_per_bn_km)
    central = rates[
        rates.method.str.startswith("A:") & (rates.km_total == "less taxi and ride-hailing")
    ].set_index("group")
    older = central.loc["65+"]
    assert f"{older.killed_ratio:.2f} times as often per kilometre" in text
    assert f"(95% interval {older.killed_ratio_low:.2f}–{older.killed_ratio_high:.2f}; " in text


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
    # Zone counts are not divided by all-road kilometres, and the download says so.
    rates = pd.read_csv(TABLES_DIR / "q6_rates_2022.csv")
    assert rates[rates.zone != "all"].per_billion_km.isna().all()
    assert rates[rates.zone == "all"].per_billion_km.notna().all()
    assert "urban and interurban roads only as counts and rates per vehicle" in text
    assert "rates per kilometre cannot be split between urban and interurban roads" in text
    # At most one closing synthesis, and only after the evidence; no generic heading.
    conclusions = text.count('<div class="conclusion">')
    assert conclusions <= 1
    if conclusions:
        assert text.rfind("</table>") < text.find('<div class="conclusion">')
    assert "Interpretation" not in text
