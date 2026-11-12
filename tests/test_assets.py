"""The site's JavaScript carries no result: no hard-coded decimals or years."""

import re

from dgt_stats.paths import PROJECT_ROOT

ASSETS = PROJECT_ROOT / "src" / "dgt_stats" / "site" / "assets"


def test_scripts_hold_no_result_numbers_or_years() -> None:
    scripts = sorted(ASSETS.glob("*.js"))
    assert scripts
    for path in scripts:
        text = path.read_text(encoding="utf-8")
        # The SVG namespace's URL is the one four-digit number a script may hold.
        text = text.replace("http://www.w3.org/2000/svg", "")
        decimals = set(re.findall(r"\b\d+\.\d+\b", text))
        if path.name != "tools.js":
            assert not decimals, path.name
        assert not re.findall(r"\b(19|20)\d\d\b", text), path.name
