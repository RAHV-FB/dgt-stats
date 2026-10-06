import json
import re
from pathlib import Path

import pandas as pd
import pytest

from dgt_stats import site, summaries
from dgt_stats.paths import FIGURES_DIR, TABLES_DIR

# The analysis pages in navigation order: everything in the main row but the overview and data.
ANALYSIS_PAGES = tuple(slug for slug, _ in site.PAGES if slug not in ("index", "data"))

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
        _scripts_are_only_the_simulator(slug, text)
        assert 'lang="en"' in text
        assert f'href="{slug}.html" aria-current="page"' in text
    # Seven analyses, the simulator, the overview and the data in the main navigation; two
    # supporting analyses in their own group; and a pointer for each page that was renamed.
    assert len(site.PAGES) == 10 and len(site.SUPPORTING_PAGES) == 2
    expected = {slug for slug, _ in site.ALL_PAGES} | set(site.MOVED_PAGES)
    assert expected == {p.stem for p in built.glob("*.html")}


def _scripts_are_only_the_simulator(slug: str, text: str) -> None:
    """No page runs a script except the simulator, which loads its own file and a data block."""
    scripts = re.findall(r"<script[^>]*>", text)
    if slug != "simulator":
        assert not scripts, slug
        return
    assert scripts == [
        '<script type="application/json" id="simulator-parameters">',
        '<script src="simulator.js" defer>',
    ]


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
    assert site.mark_spanish(site.esc(captions["l1_trend_projection"])) in text


def test_table_formats_numbers() -> None:
    frame = pd.DataFrame({"Year": [2024], "Crashes": [101996], "Share": [0.1234]})
    out = site.table(frame, "Caption", {"Crashes": "int", "Share": "pct"})
    assert "<td>101,996</td>" in out
    assert "<td>12.3%</td>" in out
    assert "<caption>Caption</caption>" in out


def test_severity_page_leads_with_the_adverse_finding(built: Path) -> None:
    text = (built / "severity.html").read_text(encoding="utf-8")
    adverse = pd.read_csv(TABLES_DIR / "q3_adverse_conditions.csv")
    fatal = adverse[adverse.outcome == "fatal"].set_index(["variant", "level"])
    wet_alone = float(fatal.loc[("no_weather", "wet"), "odds_ratio"])
    # The headline number is computed from the table, not typed.
    assert f"{wet_alone:.2f}×" in text
    assert "Odds ratios for the adverse conditions under every model variant" in text
    assert 'src="figures/s2_adverse_conditions.svg"' in text
    assert 'src="figures/s1_forest_fatal.svg"' in text
    # The distinction the finding depends on is made explicitly.
    assert "given an injury crash" in text
    assert "It says nothing about how often crashes happen" in text
    # Mechanisms are labelled as proposals and cited to original research.
    assert "mechanisms the literature proposes, not results this analysis demonstrates" in text
    for _, url in site.LITERATURE.values():
        assert url in text
    assert "doi.org" in text
    # The full coefficient table is linked, not printed.
    assert 'href="tables/q3_model_coefficients.csv"' in text
    assert text.count("<table>") <= 3


def test_drivers_page_separates_the_two_questions(built: Path) -> None:
    text = (built / "drivers.html").read_text(encoding="utf-8")
    ratios = pd.read_csv(TABLES_DIR / "q7_km_ratio.csv").set_index(["measure", "band"])
    involved = ratios.loc[("involved_per_bn_km", "75+")]
    fatality = ratios.loc[("deaths_per_1000_involved", "75+")]
    assert f"{involved.ratio:.2f}× ({involved.low:.2f}–{involved.high:.2f})" in text
    assert f"{fatality.ratio:.2f}× ({fatality.low:.2f}–{fatality.high:.2f})" in text
    # The exposure is kilometres and the page says whose age it is.
    assert "kilometres" in text and "owner" in text.lower()
    assert "travel-weighted" not in text  # the synthetic denominator is gone
    contrast = pd.read_csv(TABLES_DIR / "q7_denominator_contrast.csv")
    assert set(contrast.denominator) == {
        "residents",
        "licence_holders",
        "drivers_involved",
        "kilometres",
    }
    assert 'src="figures/a1_km_risk_by_age.svg"' in text
    company = pd.read_csv(TABLES_DIR / "q7_company_km.csv").set_index(["allocation", "band"])
    working = float(company.loc[("to_working_age", "75+"), "ratio_to_reference"])
    assert f"{working:.2f}" in text  # the company-car sensitivity is quoted, not hidden
    # Sex: the fatality ratio once involved is quoted with its interval, and the travel proxy is
    # named as what it is.
    ratios = pd.read_csv(TABLES_DIR / "drivers_sex_ratios.csv").set_index(
        ["scope", "band", "measure"]
    )
    fatality_men = ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    assert f"{fatality_men.ratio:.2f}× ({fatality_men.low:.2f}–{fatality_men.high:.2f})" in text
    assert "MOVILIA" in text and "passengers" in text
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
    assert f"{int(true['rank'])} of {int(true.n_fits)}" in text
    forecast = pd.read_csv(TABLES_DIR / "q8_points_forecast.csv")
    true_forecast = forecast[forecast.is_true].iloc[0]
    assert f"{int(true_forecast['rank'])} of {int(true_forecast.n_fits)}" in text
    assert 'src="figures/p2_july_placebos.svg"' in text
    # The two claims are kept apart, and the 2019 study is a paragraph, not a section.
    assert "That the points licence caused it" in text
    assert "2019" in text and 'src="figures/q8_speed_series.svg"' not in text
    # The exposure series are named and their effect reported.
    assert "CORES" in text and "toll" in text


def test_speed_page_carries_severity_and_the_recording_discontinuity(built: Path) -> None:
    text = (built / "speed.html").read_text(encoding="utf-8")
    pooled = pd.read_csv(TABLES_DIR / "speed_severity_pooled.csv").set_index("road_type")
    adjusted = pooled.loc["adjusted"]
    assert (
        f"{adjusted.rate_ratio:.2f}× ({adjusted.ratio_low:.2f}–{adjusted.ratio_high:.2f})" in text
    )
    assert f"{adjusted.crude_ratio:.2f}×" in text  # the unadjusted ratio is shown beside it
    # The two biases are named, and no causal count is claimed.
    assert "inflates the ratio" in text and "deflates it" in text
    assert "not an estimate of how many deaths speed caused" in text
    shares = pd.read_csv(TABLES_DIR / "q9_infraction_shares.csv")
    all_roads = shares[shares.zone == "all"].set_index("year")
    for year in (2014, 2016, int(all_roads.index.max())):
        assert f"{all_roads.loc[year, 'share_unknown'] * 100:.0f}%" in text
    assert 'src="figures/c3_speed_status.svg"' in text
    assert "point in opposite directions" in text
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
    assert "recording break" in text and "Drugs" in text


def test_trend_pages_show_every_denominator_and_the_projection(built: Path) -> None:
    trends = (built / "trends.html").read_text(encoding="utf-8")
    index = pd.read_csv(TABLES_DIR / "risk_index.csv")
    for label in index.denominator_label.unique():
        assert site.esc(label) in trends, label
    assert 'src="figures/r1_risk_change.svg"' in trends
    long_run = (built / "long-run.html").read_text(encoding="utf-8")
    assert 'src="figures/l2_observed_over_trend.svg"' in long_run
    series = pd.read_csv(TABLES_DIR / "longrun_series.csv")
    fuel = series[(series.measure == "road_fuel") & (series.period == "projected")]
    last = fuel[fuel.year == fuel.year.max()].iloc[0]
    assert site._signed_pct(float(last.ratio) - 1, 0) in long_run
    seasons = (built / "seasons.html").read_text(encoding="utf-8")
    for name in ("m1_season_profile", "m2_month_effects", "m3_lockdown"):
        assert f'src="figures/{name}.svg"' in seasons


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
            assert "<title>Road safety in Spain · measuring risk, not counting crashes" in text
        else:
            assert re.search(r"<title>[^<]+ · Road safety in Spain</title>", text), page.name
        for image in re.findall(r"<img[^>]*>", text):
            alt = re.search(r'alt="([^"]*)"', image)
            assert alt and alt.group(1).strip(), (page.name, image[:80])
        _scripts_are_only_the_simulator(page.stem, text)


def test_front_page_leads_with_the_central_question(built: Path) -> None:
    index = (built / "index.html").read_text(encoding="utf-8")
    body = index[index.find("<main>") : index.find("</main>")]
    # One finding per analysis page, in navigation order, and four key figures.
    assert body.count('<div class="finding">') == len(ANALYSIS_PAGES)
    assert body.count('<div class="keyfig">') == 4
    positions = [body.find(f'href="{slug}.html"') for slug in ANALYSIS_PAGES]
    assert all(p > 0 for p in positions) and positions == sorted(positions)
    # The supporting analyses are linked from a paragraph that says why they are not central.
    assert "does not claim" in body
    for slug in ("severity", "policy"):
        assert f'href="{slug}.html"' in body
    assert site.PROFILE_URL in index and "Russell Howard" in index
    # Concise: the findings, one table that splits each of them, and the framing around them.
    assert len(body) < 14_000


def test_every_analysis_page_ends_on_a_stated_conclusion(built: Path) -> None:
    for slug in ANALYSIS_PAGES + ("severity", "policy"):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        assert text.count('<div class="conclusion">') == 1, slug
        body = text[text.find("<main>") : text.find("</main>")]
        # The conclusion is the last thing in the argument, not a box in the middle of it.
        assert body.rfind('<div class="conclusion">') > body.rfind("<table>"), slug


def test_supporting_pages_say_they_are_supporting(built: Path) -> None:
    for slug in ("severity", "policy"):
        text = (built / f"{slug}.html").read_text(encoding="utf-8")
        body = text[text.find("<main>") : text.find("</main>")]
        assert body.find("Supporting analysis.") < body.find("<h2>"), slug


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


def test_simulator_page_carries_its_evidence_and_works_without_the_script(built: Path) -> None:
    text = (built / "simulator.html").read_text(encoding="utf-8")
    assert (built / "simulator.js").exists()
    presets = pd.read_csv(TABLES_DIR / "simulator_presets.csv").set_index("scenario")
    comply = presets.loc["all_comply"]
    # The headline is computed from the table, and the presets are printed for readers without
    # the script, the interactive panel staying hidden until the script reveals it.
    assert f"{-comply.deaths_change:,.0f}" in text
    assert '<div id="simulator-panel" hidden>' in text
    assert "The starting points:" in text
    # Every publication the simulator draws on is linked, and the register is downloadable.
    evidence = pd.read_csv(simulator_evidence_path())
    for url in evidence.url.unique():
        assert f'href="{site.esc(url)}"' in text, url
    assert 'href="tables/simulator_evidence.csv"' in text
    # The model behind the detectability is reported against the naive forecasts.
    for name in ("k1_forecast_check", "k2_detectability"):
        assert f'src="figures/{name}.svg"' in text
    assert "held-back years" in text
    # The parameters block parses and names every interurban road and urban street.
    block = re.search(
        r'<script type="application/json" id="simulator-parameters">(.*?)</script>', text, re.S
    )
    parameters = json.loads(block.group(1).replace("<\\/", "</"))
    assert set(parameters["sites"]) == {
        "autopista",
        "autovia",
        "conventional",
        "urban_50",
        "urban_30",
    }
    assert set(parameters["levers"]) == {"motorway", "conventional", "urban"}
    assert set(parameters["groups"]) == {"motorway", "conventional", "urban"}
    assert {p["key"] for p in parameters["presets"]} == set(presets.index)
    # Every preset's chance of showing in a year's count is printed, never a bare yes or no.
    for key, row in presets.drop(index="current").iterrows():
        if pd.isna(row.power_in_one_year):
            continue
        power = float(row.power_in_one_year)
        printed = "over 99%" if power > 0.995 else f"{power:.0%}"
        assert f"<td>{printed}</td>" in text, key
    assert "Visible in a year" not in text and "invisible" not in text


def simulator_evidence_path() -> Path:
    from dgt_stats.paths import SIMULATOR_EVIDENCE_PATH

    return SIMULATOR_EVIDENCE_PATH


def test_navigation_groups_its_pages_under_labels(built: Path) -> None:
    text = (built / "speed.html").read_text(encoding="utf-8")
    nav = re.search(r'<nav aria-label="Sections">(.*?)</nav>', text, re.S).group(1)
    labels = re.findall(r'<span class="navlabel" id="(nav-\d+)">([^<]+)</span>', nav)
    assert [label for _, label in labels] == [group for group, _ in site.NAV_GROUPS]
    # Every link sits in a list labelled by its group, and no label is itself a list item, so a
    # group's name can never be mistaken for a page.
    for anchor, _ in labels:
        assert f'<ul aria-labelledby="{anchor}">' in nav
    assert "<li>Supporting analyses</li>" not in nav
    links = re.findall(r'href="([a-z-]+)\.html"', nav)
    assert links == [slug for _, pages in site.NAV_GROUPS for slug, _ in pages]
    # A finding says where it sits and links to its neighbours.
    assert '<p class="eyebrow">Finding 6 of 7</p>' in text
    assert 'href="vehicles.html" rel="prev"' in text and 'href="factors.html" rel="next"' in text


def test_simulator_controls_start_at_today_and_mark_a_new_limit(built: Path) -> None:
    text = (built / "simulator.html").read_text(encoding="utf-8")
    form = text[text.find('<form id="simulator"') : text.find("</form>")]
    for group, limit in (("motorway", 120), ("conventional", 90), ("urban", 50)):
        box = form[form.find(f'data-group="{group}"') :]
        box = box[: box.find("</fieldset>")]
        # Today's limit is stated as the current one, and the first, checked choice keeps it.
        assert f"<strong>{limit} km/h</strong>" in box, group
        first = re.search(rf'<input type="radio" name="limit-{group}" value="(\d+)" checked>', box)
        assert first and int(first.group(1)) == limit, group
        assert "No change" in box and f"No new limit: {limit} km/h stays." in box
        # How drivers respond to a new limit is hidden until a new limit is chosen.
        assert f'data-response="{group}" hidden' in box, group
        assert f'id="compliance-{group}"' in box
    assert 'data-state="unchanged"' in form and 'data-state="changed"' not in form


def test_simulator_page_explains_a_higher_limit_everyone_keeps_to(built: Path) -> None:
    text = (built / "simulator.html").read_text(encoding="utf-8")
    presets = pd.read_csv(TABLES_DIR / "simulator_presets.csv").set_index("scenario")
    kept = presets.loc["motorway_140_comply"]
    assert kept.deaths_change > 0  # the page's claim that a higher limit kept costs lives
    assert "A higher limit that everyone keeps to" in text
    assert site._signed_int(kept.deaths_change) in text
    even = pd.read_csv(TABLES_DIR / "simulator_break_even.csv")
    assert f"{even.break_even_limit.iloc[0]:.0f} km/h" in text
    for heading in ("What the model is", "What the model concludes", "The forecasting model"):
        assert heading in text, heading
    assert "Gradient-boosted trees" in text and "doi.org/10.1016/j.aap.2005.07.004" in text


def test_drivers_page_chains_crashes_and_deaths_per_crash(built: Path) -> None:
    text = (built / "drivers.html").read_text(encoding="utf-8")
    ratios = pd.read_csv(TABLES_DIR / "q7_km_ratio.csv").set_index(["measure", "band"])
    for band in ("18-34", "55-64", "65-74", "75+"):
        crashes = ratios.loc[("involved_per_bn_km", band), "ratio"]
        deadly = ratios.loc[("deaths_per_1000_involved", band), "ratio"]
        deaths = ratios.loc[("deaths_per_bn_km", band), "ratio"]
        assert crashes * deadly == pytest.approx(deaths)  # the chain holds in the table
    older = pd.read_csv(TABLES_DIR / "q7_km_ratio_65_74.csv").set_index(["measure", "band"])
    peers = older.loc[("involved_per_bn_km", "75+")]
    assert f"{peers.ratio:.2f}× ({peers.low:.2f}–{peers.high:.2f})" in text
    assert "= drivers killed per billion km" in text
    for doi in ("10.1016/j.aap.2005.12.002", "10.1016/S0001-4575(01)00107-5"):
        assert doi in text


def test_overview_splits_every_comparison_into_crashes_and_deadliness(built: Path) -> None:
    text = (built / "index.html").read_text(encoding="utf-8")
    assert "Where the excess sits" in text
    # The split shows both directions, not one story told everywhere.
    body = text[text.find("Where the excess sits") :]
    body = body[: body.find("</table>")]
    assert "<td>crashes</td>" in body and "<td>deadliness</td>" in body
