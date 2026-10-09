"""The microdata pages: numbers come from the result tables, never from the page code."""

import re

import pandas as pd
import pytest

from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, TABLES_DIR
from dgt_stats.site.components import _fmt_int, _fmt_pct

PAGES = ("catalonia", "barcelona", "severity-models", "validation", "sources", "calculator")
# The modules that write the pages, and the helpers they share. Two are left out: components,
# whose navigation labels and publication titles carry years, and data, which cites a law by its
# number.
MODULES = tuple(
    path.stem
    for path in sorted((PROJECT_ROOT / "src/dgt_stats/site").glob("*.py"))
    if path.stem not in {"components", "data", "script", "style"}
)
NEEDED = (
    "cat_fatal_share",
    "bcn_person_severity_share",
    "ml_selected",
    "ml_transport_validation",
    "gen_outcomes",
    "ml_outward_path",
    "ml_model_decisions",
    "source_comparison",
)

pytestmark = pytest.mark.skipif(
    not all((TABLES_DIR / f"{name}.csv").exists() for name in NEEDED)
    or not (FIGURES_DIR / "captions.json").exists(),
    reason="run `python scripts/microdata.py all` and `python scripts/analyse.py all` first",
)


@pytest.fixture(scope="module")
def pages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    from dgt_stats import site

    target = tmp_path_factory.mktemp("site")
    site.build(target)
    # The methodology page too, which holds the regional pages' technical notes.
    return {
        slug: (target / f"{slug}.html").read_text(encoding="utf-8") for slug in (*PAGES, "data")
    }


def _table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


def _notes(data: str, anchor: str) -> str:
    """One page's technical notes on the methodology page: its section, up to the next one."""
    start = data.index(f'<h2 id="{anchor}">')
    return data[start : data.index("<h2", start + 1)]


def test_page_code_types_no_year_and_no_result() -> None:
    source = "\n".join(
        (PROJECT_ROOT / f"src/dgt_stats/site/{name}.py").read_text(encoding="utf-8")
        for name in MODULES
    )
    strings = re.findall(r'"[^"\n]*"', source)
    years = [s for s in strings if re.search(r"\b(19|20)\d\d\b", s)]
    assert not years, years
    # Percentages other than the 95% of an interval would be results typed into the page.
    shares = [s for s in strings if re.search(r"\b(?!95%)\d+(\.\d+)?%", s)]
    assert not shares, shares


def test_microdata_pages_open_with_a_summary_and_link_their_tables(pages: dict[str, str]) -> None:
    for slug, text in pages.items():
        if slug in ("calculator", "data"):
            continue
        # The old furniture is gone: no source block, no layer line. (A model's description
        # may say in prose what one row is; the old per-page "unit" block is what is banned.)
        assert '<details class="about">' not in text, slug
        assert '<p class="level">' not in text and "Layer:" not in text, slug
        assert text.count('<p class="summary">') == 1, slug
        assert 'href="tables/' in text, slug
    # Each regional page links its technical notes on the methodology page, and the notes link
    # the methodology's account of how police crash records are read.
    for slug in ("catalonia", "barcelona"):
        assert f'href="data.html#{slug}-method"' in pages[slug], slug
        assert 'href="#records"' in _notes(pages["data"], f"{slug}-method"), slug


def test_catalonia_headline_numbers_come_from_the_tables(pages: dict[str, str]) -> None:
    shares = _table("cat_fatal_share")
    overall = shares[(shares.dimension == "unit type involved") & (shares.level == "all")].iloc[0]
    text = pages["catalonia"]
    assert _fmt_int(overall.n) in text
    assert _fmt_pct(overall.share) in text
    comparison = _table("cat_vs_dgt_province_year")
    assert bool((comparison.ratio_fatal_24h == 1).all())
    assert f"in all {len(comparison)} province-years" in text


def _summary(text: str) -> str:
    return re.search(r'<p class="summary">(.*?)</p>', text, re.S).group(1)


def _headings(text: str) -> list[str]:
    main = text[text.find("<main>") : text.find("</main>")]
    return re.findall(r"<h2[^>]*>(.*?)</h2>", main, re.S)


def test_regional_pages_state_their_population_and_link_the_other_two(
    pages: dict[str, str],
) -> None:
    # Spain's, Catalonia's and Barcelona's pages answer related questions for different crashes
    # and definitions: each says so in its first paragraph and links the other two once.
    others = {"catalonia": ("severity", "barcelona"), "barcelona": ("severity", "catalonia")}
    for slug, linked in others.items():
        opening = _summary(pages[slug])
        for other in linked:
            assert opening.count(f'href="{other}.html"') == 1, (slug, other)
        assert "within 30 days" in opening and "within 24 hours" in opening, slug
        assert '<p class="scope">' not in pages[slug], slug


def test_catalonia_leads_with_its_results_and_links_the_calculator(
    pages: dict[str, str],
) -> None:
    text = pages["catalonia"]
    headings = _headings(text)
    # The checks on the file are technical notes on the methodology page, not sections of the
    # page. The page keeps the agreement with DGT's 24-hour counts, under the anchor the sources
    # and validation pages cite; the comparison in full is in the notes.
    assert "Agreement with DGT's national records" not in headings
    assert "Fields recorded unevenly" not in headings
    assert '<details class="technical"' not in text
    main = text[text.find("<main>") : text.find("</main>")]
    assert headings[-1] == "Data and method"
    agreement = re.search(r'<p id="dgt-agreement">(.*?)</p>', main, re.S).group(1)
    comparison = _table("cat_vs_dgt_province_year")
    assert f"in all {len(comparison)} province-years" in agreement
    assert "a death within 24 hours" in agreement
    notes = _notes(pages["data"], "catalonia-method")
    ratio30 = comparison.ratio_fatal_30d
    assert (
        f"{_fmt_pct(ratio30.min(), 0).removesuffix('%')}–{_fmt_pct(ratio30.max(), 0)} of DGT's "
        "count of crashes with a death within 30 days" in notes
    )
    # Where it shows fatal shares by circumstance, the page sends the reader to the calculator
    # before its first chart.
    first = main.find("<h2")
    calculator = main.find('href="calculator.html"')
    assert first < calculator < main.find("cat1_fatal_by_road")


def test_barcelona_tables_name_each_breakdown_once(pages: dict[str, str]) -> None:
    # The tables of people by road user, age and sex are the Barcelona page's technical notes.
    text = _notes(pages["data"], "barcelona-method")
    for prefix in ("Road user: ", "Age: ", "Sex: "):
        assert f">{prefix}" not in text, prefix
    for column in ("Road user", "Age", "Sex"):
        assert re.search(rf'<th scope="col"[^>]*>{column}</th>', text), column
    # The road users are listed as in their figure, from the highest share.
    people = _table("bcn_person_severity_share")
    road_users = people[(people.dimension == "road user") & (people.n >= 30)]
    top = road_users.sort_values("share", ascending=False).iloc[0]
    block = text[re.search(r'<th scope="col"[^>]*>Road user</th>', text).end() :]
    first = re.search(r'<th scope="row"[^>]*>([^<]+)</th>', block).group(1)
    assert first.lower() == top.label


def test_barcelona_headline_numbers_come_from_the_tables(pages: dict[str, str]) -> None:
    people = _table("bcn_person_severity_share")
    pedestrian = people[(people.dimension == "road user") & (people.level == "pedestrian")]
    assert _fmt_pct(float(pedestrian.share.iloc[0])) in pages["barcelona"]
    structure = _table("mq_bcn_structure").set_index("table")
    assert _fmt_int(structure.loc["bcn_accidents", "rows"]) in pages["barcelona"]


def test_model_scores_come_from_the_tables(pages: dict[str, str]) -> None:
    # The scores are on the Model method and tests page; the model page gives the shares.
    text, notes = pages["severity-models"], pages["validation"]
    scores = _table("sev_rolling_scores")
    pooled = scores[scores.subset.str.fullmatch(r"\d{4}-\d{4}")].set_index("estimator")
    calc, table = pooled.loc["calculator"], pooled.loc["road_x_crash_table"]
    trees = pooled.loc["boosted_trees"]
    # Ranking is given as ROC-AUC to two decimals, the scale the validation page uses.
    assert f"The model's ROC-AUC is {calc.roc_auc:.2f} and the table's {table.roc_auc:.2f}" in notes
    assert f"({trees.roc_auc:.2f}) but gives no interval" in notes
    gap = _table("sev_comparison").set_index(["estimator", "metric"])
    lead = gap.loc[("road_x_crash_table", "roc_auc_minus_calculator")]
    assert f"lead is {-lead.high:.2f}–{-lead.low:.2f} (95% interval)" in notes
    assert _fmt_pct(calc.mean_predicted) in text and _fmt_pct(calc.prevalence) in text
    # Predicted against observed leads the page, before the calculator, and no score box.
    body = text[text.find("<main>") : text.find("</main>")]
    assert body.find("sev1_predicted_observed") < body.find('id="calculator"')
    assert 'class="key-result"' not in body
    calibration = _table("sev_calibration")
    model = calibration[calibration.estimator == "calculator"].sort_values("group")
    top = model.tail(2).positives.sum() / model.tail(2).n.sum()
    assert f"rated most likely to have been fatal, {_fmt_pct(top, 0)} were" in text


def test_transfer_scores_and_the_small_barcelona_benchmark_come_from_the_tables(
    pages: dict[str, str],
) -> None:
    transport = _table("ml_transport_validation")
    fitted = transport[transport.estimator.ne("baseline_prior")]
    bcn = fitted[fitted.experiment.str.match(r"Catalonia -> Barcelona \d")].iloc[0]
    assert bcn.status != "reported"
    assert _fmt_int(bcn.test_positives) in pages["validation"]
    assert "too few" in pages["validation"]
    national = (
        fitted[
            fitted.experiment.eq("Catalonia -> Spain outside Catalonia")
            & fitted.status.eq("reported")
        ]
        .sort_values("roc_auc")
        .iloc[-1]
    )
    # Ranking skill to two decimals, with the interval; no side-by-side pair without one.
    assert (
        f"ROC-AUC of {national.roc_auc:.2f} (95% interval {national.roc_auc_low:.2f}–"
        f"{national.roc_auc_high:.2f})" in pages["validation"]
    )
    if f"{national.roc_auc:.2f}" == f"{national.in_domain_cv_roc_auc:.2f}":
        assert "the same to two decimals as a model of the same kind" in pages["validation"]
    else:
        assert f"against {national.in_domain_cv_roc_auc:.2f} for a model" in pages["validation"]
    assert 'class="compare"' not in pages["validation"]
    # The published model's own tests come first, with its rolling score and interval.
    calculator = _table("gen_calculator_transfer").set_index("experiment")
    rolling = calculator.loc[calculator.index[calculator.index.str.startswith("rolling")][0]]
    assert (
        f"ROC-AUC of {rolling.roc_auc:.2f} (95% interval {rolling.roc_auc_low:.2f}–"
        f"{rolling.roc_auc_high:.2f})" in pages["validation"]
    )


def test_models_page_follows_the_decisions(pages: dict[str, str]) -> None:
    text = pages["severity-models"]
    # The other models are named as not used, with the reason, and the review is linked; no
    # other model's probabilities are shown.
    assert "are not used as predictors" in text
    assert "can only rank" in text
    assert "ML_MODEL_REVIEW.md" in text and "SEVERITY_CALCULATOR.md" in text


def _options(form: str, control: str) -> list[str]:
    """The option values of the calculator's select ``calc-<control>``."""
    select = re.search(rf'<select id="calc-{re.escape(control)}"[^>]*>(.*?)</select>', form)
    assert select, control
    return re.findall(r'<option value="([^"]*)"', select.group(1))


def test_every_level_of_the_model_stays_reachable(pages: dict[str, str]) -> None:
    """The calculator asks directly for every level of the place and the conditions, and its
    crash description, run through the page's own mapping, reaches every crash type, every kind
    of road user and every number involved."""
    import json
    import shutil
    import subprocess

    from dgt_stats.paths import REPORTS_DIR
    from dgt_stats.site import tool_calculator

    form = pages["calculator"]
    model = json.loads((REPORTS_DIR / "models" / "severity_model.json").read_text())
    direct = (*tool_calculator.PLACE_INPUTS, *tool_calculator.CONDITION_INPUTS)
    assert {*direct, "crash_type", "units", "users"} == set(model["inputs"])
    for name in direct:
        assert form.count(f'id="calc-{name}"') == 1 and f'name="{name}"' in form, name
        levels = [level["value"] for level in model["inputs"][name]["levels"]]
        # The lighting's empty option is the "Choose the lighting" prompt.
        assert [value for value in _options(form, name) if value] == levels, name
    for what, fields in tool_calculator.GROUPS.items():
        assert form.count(f'data-group="{what}"') == 1, what
        for _, control, _, options in fields:
            assert _options(form, control) == [value for value, _ in options], control
    assert _options(form, "what") == [value for value, _ in tool_calculator.WHAT]
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is not installed")
    script = PROJECT_ROOT / "src/dgt_stats/site/assets/severity-calculator.js"
    described = json.loads(
        subprocess.run(
            [
                node,
                "-e",
                f"const b = require({json.dumps(str(script))});"
                "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
                "process.stdout.write(JSON.stringify(input.map(c => b.crash(c))));",
            ],
            input=json.dumps(tool_calculator.builder_choices()),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    for name, reached in (
        ("crash_type", {crash["crash_type"] for crash in described}),
        ("units", {crash["units"] for crash in described}),
        ("users", {user for crash in described for user in crash["users"]}),
    ):
        assert reached == {level["value"] for level in model["inputs"][name]["levels"]}, name


def test_validation_page_keeps_population_differences_and_validation_apart(
    pages: dict[str, str],
) -> None:
    text = pages["validation"]
    # The published model's tests lead; then the external test on another source, of a version
    # of the retired original model, and how the populations differ, which qualifies it; then
    # the original model's own tests, labelled as such.
    headings = [
        "<h2>The Catalan severity model: ranking holds, estimates of the fatal share miss in "
        "several provinces</h2>",
        "<h2>Spain outside Catalonia: a version of the original model holds its ranking</h2>",
        "<h2>Catalonia's serious crashes differ from Spain's in type and in recording</h2>",
        "<h2>The original Catalan model (retired), tested within Catalonia</h2>",
        "<h2>Barcelona city: the original model's ranking carries over, its estimates do not</h2>",
        "<h2>No model has passed every kind of test</h2>",
    ]
    positions = [
        re.search(re.escape(heading).replace("<h2>", "<h2[^>]*>"), text).start()
        for heading in headings
    ]
    assert positions == sorted(positions)
    # The Barcelona comparison comes from the tables, and the parts of the fall in Barcelona are
    # published as a table rather than worked through on the page.
    chosen = _table("ml_selected").query("primary").set_index("model").estimator
    transport = _table("ml_transport_validation")
    to_bcn = transport[
        transport.experiment.str.startswith("rest of Catalonia -> Barcelona municipality")
        & transport.model.eq("catalonia_crash_severity")
        & transport.estimator.eq(chosen["catalonia_crash_severity"])
        & transport.status.eq("reported")
    ].iloc[0]
    verdicts = _table("ml_barcelona_diagnosis_verdicts")
    full = verdicts[verdicts.features.str.startswith("full")]
    row = full.set_index("estimator").loc[chosen["catalonia_crash_severity"]]
    for value in (to_bcn.roc_auc, to_bcn.in_domain_cv_roc_auc, to_bcn.roc_auc + row.total_drop):
        assert f"{value:.2f}" in text, value
    assert f"calibration slope there is {to_bcn.calibration_slope:.2f}" in text
    assert 'href="tables/ml_barcelona_diagnosis_components.csv"' in text
    path = _table("ml_outward_path")
    if not path.verdict.eq("potentially nationally transferable").any():
        assert "national use of the models is not established" in text


def test_sources_page_states_the_dgt_audit_decision(pages: dict[str, str]) -> None:
    checks = _table("dgt_audit_checks")
    text = pages["sources"]
    if checks.decision.iloc[0].startswith("DGT microdata stay"):
        assert "but no published predictive model" in text
    artefacts = _table("dgt_audit_artefacts")
    died = artefacts[artefacts.target.str.contains("30 days")].iloc[0]
    assert f"{died.roc_auc_unrecorded_flags_only:.2f}" in text
    assert f"{died.roc_auc_recorded_values:.2f}" in text
    assert "DGT_MICRODATA_AUDIT.md" in text and 'id="scope"' in text
    # Fields that do not apply are not unrecorded, and a narrow pass of a limit is called narrow.
    assert "in a crash it applies to" in text
    if died.artefacts_dominate and died.artefact_share_of_lift - 0.5 < 0.1:
        assert "but only by" in text
    # The junction flag is described as inverted, not as a new way of marking missing types.
    assert "the junction flag the wrong way round" in text
    assert "instead of leaving it blank" not in text


def test_the_models_group_holds_only_models_that_beat_their_comparator() -> None:
    from dgt_stats import site
    from dgt_stats.microdata.validation import decisions as rules

    decisions = _table("ml_model_decisions")
    forecast = decisions[decisions.model.eq("dgt_monthly_deaths_forecast")].decision.iloc[0]
    in_models = "forecast" in [slug for slug, _ in dict(site.NAV_GROUPS)["Crash severity"]]
    assert in_models == (forecast in rules.FEATURED)
