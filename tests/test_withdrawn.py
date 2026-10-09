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
    # The scripts in the package are the interactive tools'. The severity calculator's engine
    # computes from the exported model and holds no coefficient of its own (its only decimal
    # constant is the 97.5% normal quantile). The tools' shared helpers hold only the geometry of
    # their charts. Every tool's own script, the calculator's form included, only moves values
    # between its controls and the data it loads, and holds no decimal constant and no year.
    scripts = sorted(path.relative_to(package).as_posix() for path in package.rglob("*.js"))
    assert scripts == [
        "site/assets/crash-explorer.js",
        "site/assets/driver-risk.js",
        "site/assets/severity-calculator.js",
        "site/assets/severity-engine.js",
        "site/assets/tools.js",
        "site/assets/trends-explorer.js",
    ]
    engine = (package / "site/assets/severity-engine.js").read_text(encoding="utf-8")
    assert set(re.findall(r"\b\d+\.\d+\b", engine)) == {"1.959964"}
    shared = (package / "site/assets/tools.js").read_text(encoding="utf-8")
    # (The SVG namespace's URL is the one four-digit number it may hold.)
    shared = shared.replace("http://www.w3.org/2000/svg", "")
    assert not re.findall(r"\b(19|20)\d\d\b", shared)
    for name in scripts:
        if name.endswith(("severity-engine.js", "tools.js")):
            continue
        page = (package / name).read_text(encoding="utf-8")
        assert not re.findall(r"\b\d+\.\d+\b", page), name
        assert not re.findall(r"\b(19|20)\d\d\b", page), name
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


WITHDRAWN_TABLES = re.compile(
    r"^(simulator_|factor_(deaths|comparison|casualties|inputs|naturalistic|crashes"
    r"|recorded_shares|speed_curve)|drivers_sex_travel)"
)
EXTERNAL_RESULTS = (
    "Power Model",
    "DRUID",
    "Dingus",
    "INTCF",
    "lives a year",
    "attributable",
    "simulator.js",
    "factors.js",
)


def test_no_committed_result_table_is_a_withdrawn_one() -> None:
    tables = PROJECT_ROOT / "reports" / "tables"
    assert not [path.name for path in tables.glob("*.csv") if WITHDRAWN_TABLES.match(path.name)]


def test_the_committed_site_carries_no_withdrawn_result() -> None:
    site_dir = PROJECT_ROOT / "site"
    # The one script is the site's own reading aid (menus and contents); none of the withdrawn
    # models' scripts is shipped.
    assert [path.name for path in site_dir.glob("*.js")] == ["site.js"]
    script = (site_dir / "site.js").read_text(encoding="utf-8")
    for word in ("simulat", "fetch(", "XMLHttpRequest", "evidence"):
        assert word not in script, word
    # The withdrawn analyses' pages are gone.
    for name in ("simulator", "distraction", "alcohol-drugs", "enforcement", "forecast"):
        assert not (site_dir / f"{name}.html").exists(), name
    for path in sorted(site_dir.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        for phrase in EXTERNAL_RESULTS:
            assert phrase not in text, (path.name, phrase)
