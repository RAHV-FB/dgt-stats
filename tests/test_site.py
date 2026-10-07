import re
from pathlib import Path

import pandas as pd
import pytest

from dgt_stats import site, summaries
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR
from dgt_stats.site import components
from dgt_stats.site.script import JS_FLAG

# The national analysis pages in navigation order, and the monthly deaths forecast; then the
# regional, model, validation and sources pages.
ANALYSIS_PAGES = tuple(slug for slug, _ in components.SPAIN_PAGES) + ("forecast",)
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
    # The navigation follows the argument: Spain (seven pages and three supporting analyses),
    # the regional records, the models and their external validation, and the methods; a
    # pointer for each page that was renamed; and a notice for each withdrawn analysis.
    assert [group for group, _ in site.NAV_GROUPS] == [
        "Overview",
        "Spain",
        "Supporting analyses",
        "Regional data",
        "Models",
        "Methods",
    ]
    assert len(site.PAGES) == 14 and len(site.SUPPORTING_PAGES) == 3
    assert [slug for slug, _ in dict(site.NAV_GROUPS)["Models"]] == [
        "severity-models",
        "validation",
    ]
    expected = (
        {slug for slug, _ in site.ALL_PAGES} | set(site.MOVED_PAGES) | set(site.WITHDRAWN_PAGES)
    )
    assert expected == {p.stem for p in built.glob("*.html")}
    # The site's one script is its own reading aid; the withdrawn models' scripts and registers
    # are not shipped.
    assert [p.name for p in built.glob("*.js")] == ["site.js"]
    published = {p.name for p in (built / "tables").glob("*.csv")}
    assert not published & {"simulator_evidence.csv", "factor_evidence.csv"}


def _runs_no_script(slug: str, text: str) -> None:
    """No page runs a script of its own: the simulator and factor models that did were withdrawn.

    Every page loads only the site's reading aid (menus and contents), after a one-line flag that
    says scripting is on; both are the same on every page.
    """
    assert re.findall(r"<script[^>]*>", text) == ["<script>", '<script src="site.js" defer>'], slug
    assert JS_FLAG in text, slug


def test_moved_pages_point_to_their_successors(built: Path) -> None:
    for old, new in site.MOVED_PAGES.items():
        text = (built / f"{old}.html").read_text(encoding="utf-8")
        assert f'content="0; url={new}.html"' in text
        assert f'href="{new}.html">' in text
    # No live page links to a moved slug: the pointers are for old bookmarks, not navigation.
    for slug, _ in site.ALL_PAGES:
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        for moved in site.MOVED_PAGES:
            assert f'href="{moved}.html"' not in text, (slug, moved)


def test_withdrawn_pages_say_why_and_nothing_links_to_them(built: Path) -> None:
    assert set(site.WITHDRAWN_PAGES) == {"simulator", "distraction", "alcohol-drugs", "enforcement"}
    live = {slug for slug, _ in site.ALL_PAGES}
    for slug, reason in site.WITHDRAWN_PAGES.items():
        assert slug not in live and slug not in site.MOVED_PAGES, slug
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        body = text[text.find("<main>") : text.find("</main>")]
        # A short notice, not a redirect: it says why the analysis went and links to the data.
        assert "http-equiv" not in text and 'rel="canonical"' not in text, slug
        assert "withdrawn because its results came from coefficients published in external " in text
        assert "rather than from data in this repository" in text
        assert site.esc(reason) in body, slug
        assert 'href="data.html"' in body, slug
        assert '<div class="conclusion">' not in body and "<table>" not in body, slug
        assert len(body) < 4000, slug
    # The forecast that was on the simulator page is pointed to from its notice.
    assert 'href="forecast.html"' in (built / "simulator.html").read_text(encoding="utf-8")
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
    svgs = sorted(p.name for p in (built / "figures").glob("*.svg"))
    assert svgs == sorted(p.name for p in FIGURES_DIR.glob("*.svg"))
    captions = site.read_captions()
    for name in captions:
        assert (built / "figures" / f"{name}.svg").exists(), name
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
    assert text.count("<table>") <= 3


def test_drivers_page_separates_the_two_questions(built: Path) -> None:
    text = (built / "drivers.html").read_text(encoding="utf-8")
    body = text[text.find("<main>") : text.find("</main>")]
    ratios = pd.read_csv(TABLES_DIR / "q7_km_ratio.csv").set_index(["measure", "band"])
    rates = pd.read_csv(TABLES_DIR / "q7_km_rates.csv").set_index("band")
    fatality = ratios.loc[("deaths_per_1000_involved", "75+")]
    # Deaths per driver involved need no exposure, so they are quoted as a point with its interval,
    # and they lead the page: the opening summary carries the rates, and the key result of the
    # first section the ratio and its interval, before any per-km range.
    opening = re.search(r'<p class="summary">(.*?)</p>', body, re.S).group(1)
    assert f"{rates.loc['75+', 'deaths_per_1000_involved']:.1f}" in opening
    key = re.search(r'<div class="key-result">(.*?)</div>', body, re.S).group(1)
    assert f'<p class="key-value">{fatality.ratio:.2f}×</p>' in key
    assert f"95% interval {fatality.low:.2f}–{fatality.high:.2f}" in key
    assert body.find('<div class="key-result">') < body.find(
        '<h2 id="crashes-relative-to-kilometres'
    )
    assert f"{fatality.ratio:.2f}× ({fatality.low:.2f}–{fatality.high:.2f})" in text
    # The young drivers are split at 25 wherever the sources allow, with 35-54 the reference.
    owner = pd.read_csv(TABLES_DIR / "q7_owner_age_check.csv").set_index("band")
    assert list(owner.index) == ["18-24", "25-34", "35-54", "55-64", "65-74", "75+"]
    # Every per-km ratio is a range from the transfer scenario to the published ratio.
    for measure, band in (
        ("deaths_per_bn_km", "75+"),
        ("involved_per_bn_km", "18-24"),
        ("involved_per_bn_km", "25-34"),
    ):
        low = owner.loc[band, f"{measure}_range_low"]
        high = owner.loc[band, f"{measure}_range_high"]
        assert low < high
        assert f"{low:.2f}–{high:.2f}×" in text, (measure, band)
        if measure == "involved_per_bn_km":
            # The old point claim on the owner-age kilometres is gone.
            row = ratios.loc[(measure, band)]
            assert f"{row.ratio:.2f}× ({row.low:.2f}–{row.high:.2f})" not in text
    young = owner.loc["18-24"]
    young_range = (
        f"{young.involved_per_bn_km_range_low:.2f}–{young.involved_per_bn_km_range_high:.2f}×"
    )
    assert body.find(f"{fatality.ratio:.2f}") < body.find(young_range)
    assert "cars registered to owners of the same age" in text
    assert f"{-owner.loc['35-54', 'transfer_bn_km']:.1f} billion km" in text
    assert f"{owner.loc['75+', 'cars_per_b_permit']:.2f} cars per licence holder" in text
    for phrase in ("like with like", "frailty", "travel-weighted", "MOVILIA", "extra travel"):
        assert phrase not in text, phrase
    assert "doi.org" not in text  # no external study interprets these results
    contrast = pd.read_csv(TABLES_DIR / "q7_denominator_contrast.csv")
    assert set(contrast.denominator) == {
        "residents",
        "b_permit_holders",
        "drivers_involved",
        "kilometres",
    }
    # INE's five-year groups cannot be cut at 18, so the per-resident contrast starts at 25.
    assert "18-24" not in set(contrast.band)
    assert 'src="figures/a1_killed_per_involved.svg"' in text
    company = pd.read_csv(TABLES_DIR / "q7_company_km.csv").set_index(["allocation", "band"])
    working = float(company.loc[("to_working_age", "75+"), "ratio_to_reference"])
    assert f"{working:.2f}×" in text  # the company-car scenario is quoted, not hidden
    # Sex: the ratio per driver involved is quoted with its interval; no travel proxy is used.
    sex = pd.read_csv(TABLES_DIR / "drivers_sex_ratios.csv").set_index(["scope", "band", "measure"])
    fatality_men = sex.loc[("car", "18+", "deaths_per_1000_involved")]
    assert f"{fatality_men.ratio:.2f}" in text
    assert f"({fatality_men.low:.2f}–{fatality_men.high:.2f})" in text
    assert "kilometres driven by sex" in text
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
    assert f"{ordinal} of {int(true_forecast.n_fits)}" in text
    assert 'src="figures/p2_july_placebos.svg"' in text
    # The fall is not attributed to the licence, and the 2019 study is a collapsed note.
    opening = re.search(r'<p class="summary">(.*?)</p>', text, re.S).group(1)
    assert "cannot show that the licence caused" in opening
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
    # The summary says plainly that a recorded factor is an association, not a cause.
    assert (
        "Police-recorded inappropriate speed is associated with greater crash severity" in opening
    )
    assert "This is not an estimate of causation." in opening
    # The two biases are named, in both directions.
    assert "which would raise it" in text and "which would lower it" in text
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
    assert components._change(float(km_last.ratio), 0) in long_run
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
    seasons = (built / "seasons.html").read_text(encoding="utf-8")
    for name in ("m1_season_profile", "m2_month_effects", "m3_lockdown"):
        assert f'src="figures/{name}.svg"' in seasons
    # Deaths are divided only by road fuel; under it July and August stay above 1.
    effects = pd.read_csv(TABLES_DIR / "season_month_effects.csv")
    assert set(effects.exposure) == {"none", "road_fuel_tonnes"}
    fuel_effects = effects[effects.exposure == "road_fuel_tonnes"].set_index("month")
    for month in (7, 8):
        assert fuel_effects.loc[month, "low"] > 1
        assert components._times(float(fuel_effects.loc[month, "rate_ratio"])) in seasons
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
    # What the project is, its main findings, where to read on and its data: no numbered
    # questions, no boxed finding blocks, and the page opens on a summary paragraph.
    headings = re.findall(r"<h2[^>]*>([^<]+)</h2>", body)
    assert headings == ["Main findings", "Explore the study"]
    assert '<div class="finding">' not in body and "Finding 1" not in body
    assert body.find('<p class="summary">') < body.find("<h2")
    opening = re.search(r'<p class="summary">(.*?)</p>', body, re.S).group(1)
    assert "ordinary statistical analysis" in opening and "predictive models" in opening
    sections = dict(zip(headings, re.split(r"<h2[^>]*>[^<]+</h2>", body)[1:]))
    # A short list of findings, each a single number with the sentences saying what it measures.
    findings = re.search(r'<ol class="findings">(.*?)</ol>', body, re.S).group(1)
    items = re.findall(r"<li>(.*?)</li>", findings, re.S)
    assert 4 <= len(items) <= 7
    for item in items:
        assert item.count('<p class="finding-value">') == 1
    for slug in ("trends", "long-run", "drivers", "speed", "factors", "severity-models"):
        assert f'href="{slug}.html' in sections["Main findings"], slug
    assert 'href="validation.html' in sections["Main findings"]
    # The study index lists every page once, in the groups a reader would look for.
    explore = re.search(r'<div class="explore">(.*?)</div>', body, re.S).group(1)
    groups = re.findall(r"<h3[^>]*>([^<]+)</h3>", explore)
    assert groups == [
        "National trends and exposure",
        "Drivers and vehicles",
        "Recorded crash factors",
        "Catalonia and Barcelona",
        "Predictive severity models",
        "Sources and methodology",
    ]
    linked = re.findall(r'href="([a-z-]+)\.html"', explore)
    assert sorted(linked) == sorted(slug for slug, _ in site.ALL_PAGES if slug != "index")
    # The data line closes the page quietly and links the sources.
    provenance = re.search(r'<div class="provenance">(.*?)</div>', body, re.S).group(1)
    assert 'href="sources.html"' in provenance
    # The headline numbers are computed from the tables.
    risk = pd.read_csv(TABLES_DIR / "risk_index.csv")
    latest = risk[(risk.year == risk.year.max()) & (risk.outcome == "deaths_30d")]
    deaths = latest[latest.denominator == "count"].iloc[0]
    assert components._fmt_int(deaths["count"]) in sections["Main findings"]
    ratios = pd.read_csv(TABLES_DIR / "q7_km_ratio.csv").set_index(["measure", "band"])
    oldest = ratios.loc[("deaths_per_1000_involved", "75+")]
    assert f"{oldest.ratio:.1f} times as often" in sections["Main findings"]
    owner = pd.read_csv(TABLES_DIR / "q7_owner_age_check.csv").set_index("band")
    low, high = owner.loc[
        "18-24", ["involved_per_bn_km_range_low", "involved_per_bn_km_range_high"]
    ]
    # The published owner-age ratio and the reassignment scenario, both from the table.
    assert f"{high:.1f} times as many injury crashes per kilometre" in sections["Main findings"]
    assert f"the ratio falls to {low:.1f}" in sections["Main findings"]
    # A reader can follow the front page without the modelling vocabulary of the deeper pages.
    visible = re.sub(r"<[^>]+>", " ", body)
    for jargon in ("ROC-AUC", "calibration slope", "Jensen", "transportab", "odds ratio"):
        assert jargon not in visible, jargon
    assert "national use" in sections["Main findings"]
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


def test_supporting_pages_say_they_are_supporting(built: Path) -> None:
    # The section line above the title says so; the prose does not restate the site's structure.
    for slug in ("severity", "forecast", "policy"):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        body = text[text.find("<main>") : text.find("</main>")]
        assert body.startswith(
            '<main>\n<header class="page-header" id="content">\n'
            '<p class="eyebrow">Spain · supporting analysis</p>'
        ), slug
        assert "Supporting analysis." not in body, slug


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


def test_forecast_page_reports_the_model_on_years_it_had_not_seen(built: Path) -> None:
    from dgt_stats import forecast

    text = (built / "forecast.html").read_text(encoding="utf-8")
    body = text[text.find("<main>") : text.find("</main>")]
    validation = pd.read_csv(TABLES_DIR / "forecast_validation.csv").set_index(
        ["outcome", "set", "method"]
    )
    detect = pd.read_csv(TABLES_DIR / "forecast_detectability.csv").set_index(
        ["outcome", "horizon"]
    )
    # The headline numbers are computed from the tables, not typed.
    holdout = float(validation.loc[("deaths_all", "holdout", forecast.CHOSEN), "rmse"])
    naive = float(validation.loc[("deaths_all", "holdout", "last_year"), "rmse"])
    assert f"{holdout * 100:.1f}%" in body and f"{naive * 100:.1f}%" in body
    one = detect.loc[("deaths_all", 1)]
    rise = forecast.minimum_detectable_rise(float(one.expected), float(one.tau))
    assert f"{one.mde * 100:.0f}%" in body and f"{rise * 100:.0f}%" in body
    assert f"{detect.loc[('deaths_all', 5), 'mde'] * 100:.0f}%" in body
    # Both figures, the comparison with machine learning and the naive forecasts, and the tables.
    for name in ("k1_forecast_check", "k2_detectability"):
        assert f'src="figures/{name}.svg"' in body
    assert "Gradient-boosted trees" in body and site.esc("Last year's monthly counts") in body
    for name in ("forecast_validation", "forecast_detectability", "forecast_coefficients"):
        assert f'href="tables/{name}.csv"' in body
    # The tree setting found by looking at the held-back years stays disclosed, with a link to
    # the model card that reports it.
    assert "found by looking at the held-out years" in body
    assert "not an independent test" in body
    assert "models/dgt_monthly_deaths_forecast.md" in body
    # Detectability is generic: nothing ties it to a speed law or any withdrawn model's effect.
    for word in ("simulator", "speed law", "km/h", "Power Model", "law shows"):
        assert word not in body, word
    eyebrow = '<p class="eyebrow">Spain · supporting analysis</p>'
    assert eyebrow in body
    # The eyebrow carries the supporting status; the prose states what the model is used for.
    assert "supporting analysis" not in body.replace(eyebrow, "")
    # The page leads with the model losing to last year's counts in ordinary years.
    opening = re.search(r'<p class="summary">(.*?)</p>', body, re.S).group(1)
    assert opening.find(f"{naive * 100:.1f}%") < opening.find(f"{holdout * 100:.1f}%")
    assert "not used as the forecast for ordinary years" in opening
    # The pointer to the comparison made after the test sits in a collapsed technical block.
    after = body.find("found by looking at the held-out years")
    assert body.rfind('<details class="technical">', 0, after) > body.rfind("</details>", 0, after)


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
    assert '<p class="eyebrow">Spain</p>' in text
    assert 'href="vehicles.html" rel="prev"' in text and 'href="factors.html" rel="next"' in text
    # The last national page leads on to the supporting analyses, and the last of those to the
    # regional crash records.
    for slug, before, after in (
        ("factors", "speed", "severity"),
        ("policy", "forecast", "catalonia"),
        ("validation", "severity-models", "sources"),
    ):
        page = (built / f"{slug}.html").read_text(encoding="utf-8")
        pager = re.search(r'<nav class="pager"[^>]*>(.*?)</nav>', page, re.S).group(1)
        assert f'href="{before}.html" rel="prev"' in pager, slug
        assert f'href="{after}.html" rel="next"' in pager, slug


def test_drivers_page_chains_crashes_and_deaths_per_crash(built: Path) -> None:
    text = (built / "drivers.html").read_text(encoding="utf-8")
    ratios = pd.read_csv(TABLES_DIR / "q7_km_ratio.csv").set_index(["measure", "band"])
    for band in ("18-24", "25-34", "55-64", "65-74", "75+"):
        crashes = ratios.loc[("involved_per_bn_km", band), "ratio"]
        deadly = ratios.loc[("deaths_per_1000_involved", band), "ratio"]
        deaths = ratios.loc[("deaths_per_bn_km", band), "ratio"]
        assert crashes * deadly == pytest.approx(deaths)  # the chain holds in the table
    older = pd.read_csv(TABLES_DIR / "q7_km_ratio_65_74.csv").set_index(["measure", "band"])
    peers = older.loc[("involved_per_bn_km", "75+")]
    assert f"{peers.ratio:.2f} times" in text and f"({peers.low:.2f}–{peers.high:.2f})" in text
    assert "= killed per billion km" in text


def test_vehicles_page_quotes_per_km_rates_for_all_roads_only(built: Path) -> None:
    text = (built / "vehicles.html").read_text(encoding="utf-8")
    summary = pd.read_csv(TABLES_DIR / "q6_summary_2022.csv").set_index("group")
    truck, car, bike = summary.loc["heavy_truck"], summary.loc["car"], summary.loc["motorcycle"]
    per_vehicle = (
        truck.fatal_involvement_per_100k_vehicles / car.fatal_involvement_per_100k_vehicles
    )
    per_km = truck.fatal_involvement_per_bn_km / car.fatal_involvement_per_bn_km
    assert f"{per_vehicle:.1f}×" in text and f"{per_km:.1f}×" in text
    # The occupant shares are computed, not typed.
    assert f"{bike.occupant_deaths_per_fatal_involvement:.2f} for a motorcycle" in text
    assert f"a figure of {truck.occupant_deaths_per_fatal_involvement:.2f}" in text
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
