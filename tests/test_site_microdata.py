"""The microdata pages: numbers come from the result tables, never from the page code."""

import re

import pandas as pd
import pytest

from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, TABLES_DIR
from dgt_stats.site.components import _fmt_int, _fmt_pct

PAGES = ("catalonia", "barcelona", "severity-models", "validation", "sources")
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
    return {slug: (target / f"{slug}.html").read_text(encoding="utf-8") for slug in PAGES}


def _table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


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
        # The old furniture is gone: no source block, no layer line. (A model's description
        # may say in prose what one row is; the old per-page "unit" block is what is banned.)
        assert '<details class="about">' not in text, slug
        assert '<p class="level">' not in text and "Layer:" not in text, slug
        assert text.count('<p class="summary">') == 1, slug
        assert 'href="tables/' in text, slug
    for slug in ("catalonia", "barcelona"):
        assert 'href="data.html#records"' in pages[slug], slug


def test_catalonia_headline_numbers_come_from_the_tables(pages: dict[str, str]) -> None:
    shares = _table("cat_fatal_share")
    overall = shares[(shares.dimension == "unit type involved") & (shares.level == "all")].iloc[0]
    text = pages["catalonia"]
    assert _fmt_int(overall.n) in text
    assert _fmt_pct(overall.share) in text
    comparison = _table("cat_vs_dgt_province_year")
    assert f"{int((comparison.ratio_fatal_24h == 1).sum())} of {len(comparison)}" in text


def test_barcelona_headline_numbers_come_from_the_tables(pages: dict[str, str]) -> None:
    people = _table("bcn_person_severity_share")
    pedestrian = people[(people.dimension == "road user") & (people.level == "pedestrian")]
    assert _fmt_pct(float(pedestrian.share.iloc[0])) in pages["barcelona"]
    structure = _table("mq_bcn_structure").set_index("table")
    assert _fmt_int(structure.loc["bcn_accidents", "rows"]) in pages["barcelona"]


def test_model_scores_come_from_the_tables(pages: dict[str, str]) -> None:
    text = pages["severity-models"]
    scores = _table("sev_rolling_scores")
    pooled = scores[scores.subset.str.fullmatch(r"\d{4}-\d{4}")].set_index("estimator")
    calc, table = pooled.loc["calculator"], pooled.loc["road_x_crash_table"]
    trees = pooled.loc["boosted_trees"]
    # Ranking is put in plain words: how often a fatal crash gets the higher estimate.
    assert f"higher estimate {round(100 * calc.roc_auc)} times in 100" in text
    assert f"the table {round(100 * table.roc_auc)} times" in text
    assert f"({round(100 * trees.roc_auc)} times in 100) but gives no interval" in text
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
    assert f"{national.roc_auc:.3f}" in pages["validation"]
    assert f"{national.in_domain_cv_roc_auc:.3f}" in pages["validation"]


def test_models_page_follows_the_decisions(pages: dict[str, str]) -> None:
    text = pages["severity-models"]
    # The other models are named as not used, with the reason, and the review is linked; no
    # other model's probabilities are shown.
    assert "are not used as predictors" in text
    assert "can only rank" in text
    assert "ML_MODEL_REVIEW.md" in text and "SEVERITY_CALCULATOR.md" in text
    # The calculator's form offers exactly the exported model's inputs.
    import json

    from dgt_stats.paths import REPORTS_DIR

    model = json.loads((REPORTS_DIR / "models" / "severity_model.json").read_text())
    for name, spec in model["inputs"].items():
        if spec["type"] == "flags":
            for level in spec["levels"]:
                assert f'name="users" value="{level["value"]}"' in text, level
        else:
            assert f'name="{name}"' in text, name
            assert text.count(f'id="calc-{name}"') == 1, name


def test_validation_page_keeps_population_differences_and_validation_apart(
    pages: dict[str, str],
) -> None:
    text = pages["validation"]
    # The main external test leads; how the populations differ follows the tests it qualifies.
    headings = [
        "<h2>Tested on DGT records outside Catalonia</h2>",
        "<h2>Tested on a later year and on provinces left out</h2>",
        "<h2>Tested on Barcelona city</h2>",
        "<h2>How the crash populations differ</h2>",
        "<h2>What the tests support</h2>",
    ]
    positions = [
        re.search(heading.replace("<h2>", "<h2[^>]*>"), text).start() for heading in headings
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
        assert f"{value:.3f}" in text, value
    assert 'href="tables/ml_barcelona_diagnosis_components.csv"' in text
    path = _table("ml_outward_path")
    if not path.verdict.eq("potentially nationally transferable").any():
        assert "national use of the models is not established" in text


def test_sources_page_states_the_dgt_audit_decision(pages: dict[str, str]) -> None:
    checks = _table("dgt_audit_checks")
    text = pages["sources"]
    if checks.decision.iloc[0].startswith("DGT microdata stay"):
        assert "They are not used to train a predictive severity model" in text
    artefacts = _table("dgt_audit_artefacts")
    died = artefacts[artefacts.target.str.contains("30 days")].iloc[0]
    assert f"{died.roc_auc_unrecorded_flags_only:.2f}" in text
    assert f"{died.roc_auc_recorded_values:.2f}" in text
    assert "DGT_MICRODATA_AUDIT.md" in text and 'id="scope"' in text


def test_the_models_group_holds_only_models_that_beat_their_comparator() -> None:
    from dgt_stats import site
    from dgt_stats.microdata.validation import decisions as rules

    decisions = _table("ml_model_decisions")
    forecast = decisions[decisions.model.eq("dgt_monthly_deaths_forecast")].decision.iloc[0]
    in_models = "forecast" in [slug for slug, _ in dict(site.NAV_GROUPS)["Models"]]
    assert in_models == (forecast in rules.FEATURED)
