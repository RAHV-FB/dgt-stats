import pytest

from dgt_stats import model_cards
from dgt_stats.paths import TABLES_DIR

tables = pytest.mark.skipif(
    not all((TABLES_DIR / f"{name}.csv").exists() for name in model_cards.FORECAST_TABLES),
    reason="run `python scripts/analyse.py all` first",
)


@tables
def test_the_committed_forecast_card_is_the_one_the_tables_give() -> None:
    # The card is generated from the committed tables; a stale card means a number was typed or
    # the tables moved without `python -m dgt_stats.model_cards` being run.
    assert model_cards.FORECAST_CARD_PATH.read_text(encoding="utf-8") == model_cards.forecast_card()


@tables
def test_the_forecast_card_states_its_design_and_its_limits() -> None:
    card = model_cards.forecast_card()
    for heading in (
        "## Task",
        "## Training, selection and test",
        "## Metrics",
        "## Comparators",
        "## Valid interpretation",
        "## Invalid interpretation",
        "## Limitations",
    ):
        assert heading in card, heading
    assert "one calendar month" in card
    assert "Disclosed, not a candidate" in card
    assert "\u2014" not in card
    # Nothing in the card comes from the withdrawn models.
    for word in ("simulator", "Power Model", "speed law"):
        assert word not in card, word


severity_tables = pytest.mark.skipif(
    not all((TABLES_DIR / f"{name}.csv").exists() for name in model_cards.SEVERITY_TABLES),
    reason="run `python scripts/model.py` first",
)


@severity_tables
def test_the_committed_severity_card_is_the_one_the_tables_give() -> None:
    assert model_cards.SEVERITY_CARD_PATH.read_text(encoding="utf-8") == (
        model_cards.severity_card()
    )


@severity_tables
def test_the_severity_card_states_its_design_and_its_nuisance_levels() -> None:
    card = model_cards.severity_card()
    for heading in (
        "## Task",
        "## Features",
        "## Holdout design and metrics",
        "## Nuisance levels",
        "## Sensitivity: without Cataluña",
        "## Valid interpretation",
        "## Invalid interpretation",
        "## Limitations",
    ):
        assert heading in card, heading
    assert "one DGT injury crash" in card and "Brier skill" in card
    assert "(nuisance)" in card and "is_nuisance" in card
    assert "—" not in card
    # No external study explains or supports anything in the card.
    for word in ("et al", "doi.org", "literature", "Elvik"):
        assert word not in card, word
