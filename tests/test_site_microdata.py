"""The microdata pages: numbers come from the result tables, never from the page code."""

import re

import pandas as pd
import pytest

from dgt_stats.paths import FIGURES_DIR, PROJECT_ROOT, TABLES_DIR
from dgt_stats.site.components import _fmt_int, _fmt_pct

PAGES = ("catalonia", "barcelona", "severity-models", "transport", "sources")
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
    source = (PROJECT_ROOT / "src/dgt_stats/site/microdata_pages.py").read_text(encoding="utf-8")
    strings = re.findall(r'"[^"\n]*"', source)
    years = [s for s in strings if re.search(r"\b(19|20)\d\d\b", s)]
    assert not years, years
    # Percentages other than the 95% of an interval would be results typed into the page.
    shares = [s for s in strings if re.search(r"\b(?!95%)\d+(\.\d+)?%", s)]
    assert not shares, shares


def test_every_microdata_page_states_source_coverage_and_unit(pages: dict[str, str]) -> None:
    for slug in ("catalonia", "barcelona", "transport"):
        assert '<details class="about">' in pages[slug], slug
        assert "One row is" in pages[slug]
    for slug, text in pages.items():
        assert text.count('<div class="conclusion">') == 1, slug
        assert text.rindex('<div class="conclusion">') > text.rindex("</table>"), slug


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
    selected = _table("ml_selected")
    for row in selected[selected.primary].itertuples():
        assert f"{row.roc_auc:.2f}" in pages["severity-models"], row.model
        if not row.probabilities_shown_as_estimates:
            assert "not reliable as the share of similar cases" in pages["severity-models"]


def test_transfer_scores_and_the_small_barcelona_benchmark_come_from_the_tables(
    pages: dict[str, str],
) -> None:
    transport = _table("ml_transport_validation")
    fitted = transport[transport.estimator.ne("baseline_prior")]
    bcn = fitted[fitted.experiment.str.match(r"Catalonia -> Barcelona \d")].iloc[0]
    assert bcn.status != "reported"
    assert _fmt_int(bcn.test_positives) in pages["transport"]
    assert "too few" in pages["transport"]
    national = (
        fitted[
            fitted.experiment.eq("Catalonia -> Spain outside Catalonia")
            & fitted.status.eq("reported")
        ]
        .sort_values("roc_auc")
        .iloc[-1]
    )
    assert f"{national.roc_auc:.2f}" in pages["transport"]


def test_every_microdata_page_names_its_layer(pages: dict[str, str]) -> None:
    for slug, text in pages.items():
        assert re.search(r'<p class="level">Layers?: <a href="sources.html">', text), slug


def test_models_page_follows_the_decisions(pages: dict[str, str]) -> None:
    decisions = _table("ml_model_decisions")
    rules = _table("ml_rule_comparison")
    text = pages["severity-models"]
    for row in rules.itertuples():
        assert f"{row.rule_roc_auc:.2f}" in text, row.model
    replaced = decisions[
        decisions.decision.eq("REPLACE with descriptive table") & decisions.variant.eq("context")
    ]
    for model in replaced.model:
        assert "a table, not a model" in text, model
    assert "MODEL_DECISIONS.md" in text


def test_transport_page_keeps_representativeness_and_transportability_apart(
    pages: dict[str, str],
) -> None:
    text = pages["transport"]
    a = text.index("A. How the populations differ")
    b = text.index("B. Do the models keep their ranking?")
    c = text.index("C. The outward path toward Spain")
    assert a < b < c
    verdicts = _table("ml_barcelona_diagnosis_verdicts")
    full = verdicts[verdicts.features.str.startswith("full")]
    assert any(f"{v:.2f}" in text for v in full.intrinsic_difference)
    path = _table("ml_outward_path")
    if not path.verdict.eq("potentially nationally transferable").any():
        assert "none is called nationally transferable" in text


def test_sources_page_states_the_dgt_audit_decision(pages: dict[str, str]) -> None:
    checks = _table("dgt_audit_checks")
    assert checks.decision.iloc[0].replace("'", "&#x27;") in pages["sources"]


def test_the_models_group_holds_only_models_that_beat_their_comparator() -> None:
    from dgt_stats import site
    from dgt_stats.microdata.validation import decisions as rules

    decisions = _table("ml_model_decisions")
    forecast = decisions[decisions.model.eq("dgt_monthly_deaths_forecast")].decision.iloc[0]
    in_models = "forecast" in [slug for slug, _ in dict(site.NAV_GROUPS)["Models"]]
    assert in_models == (forecast in rules.FEATURED)
