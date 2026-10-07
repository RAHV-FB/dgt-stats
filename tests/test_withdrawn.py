"""The analyses withdrawn because their results came from external-study coefficients stay gone."""

import re
from pathlib import Path

from dgt_stats import summaries
from dgt_stats.paths import PROJECT_ROOT

SOURCE_DIRS = (PROJECT_ROOT / "src" / "dgt_stats", PROJECT_ROOT / "scripts")
# The hand-typed registers of external-study values. The files stay in data/raw, which is
# immutable, but no code reads them.
REGISTERS = re.compile(r"simulator_parameters|factor_parameters|SIMULATOR_EVIDENCE|FACTOR_EVIDENCE")
WITHDRAWN_MODULES = re.compile(
    r"\b(factor_models|factor_pages|io_activity|read_activity_register|sex_travel_bracket)\b"
    r"|dgt_stats\.simulator\b"
)


def _python_files() -> list[Path]:
    return [path for root in SOURCE_DIRS for path in sorted(root.rglob("*.py"))]


def test_no_code_reads_the_external_evidence_registers() -> None:
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        assert not REGISTERS.search(text), path.relative_to(PROJECT_ROOT)


def test_the_withdrawn_models_and_their_scripts_are_gone() -> None:
    package = PROJECT_ROOT / "src" / "dgt_stats"
    for name in ("simulator.py", "factor_models.py", "site/simulator.py", "site/factor_pages.py"):
        assert not (package / name).exists(), name
    assert not list(package.rglob("*.js"))
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        assert not WITHDRAWN_MODULES.search(text), path.relative_to(PROJECT_ROOT)


def test_no_summary_table_carries_a_withdrawn_result() -> None:
    names = set(summaries.SUMMARIES)
    assert not any(name.startswith("simulator_") for name in names)
    withdrawn = {
        "factor_casualties",
        "factor_recorded_shares",
        "factor_inputs",
        "factor_deaths",
        "factor_naturalistic",
        "factor_crashes",
        "factor_speed_curve",
        "factor_comparison",
        "drivers_sex_travel",
    }
    assert not names & withdrawn
    assert {"road_class_baseline", "road_class_risk"} <= names
