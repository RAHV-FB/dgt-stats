from pathlib import Path

import pandas as pd
import pytest

from dgt_stats import plots


def _svg_ok(path: Path) -> None:
    assert path.exists() and path.suffix == ".svg"
    text = path.read_text(encoding="utf-8")
    assert "<svg" in text and len(text) > 1_000
    assert "dc:date" not in text  # no timestamp, rebuilds stay byte-stable


def test_line_series_single_and_multi(tmp_path: Path) -> None:
    frame = pd.DataFrame({"year": range(2016, 2025), "value": range(9)})
    _svg_ok(plots.line_series(frame, "year", "value", tmp_path / "one.svg", "One"))
    multi = pd.concat(
        [frame.assign(zone="Urban"), frame.assign(zone="Interurban", value=frame.value * 2)]
    )
    out = plots.line_series(
        multi, "year", "value", tmp_path / "two.svg", "Two", series="zone", percent=False
    )
    _svg_ok(out)
    assert "Interurban" in out.read_text(encoding="utf-8")


def test_line_series_refuses_more_series_than_colours(tmp_path: Path) -> None:
    frame = pd.DataFrame({"x": [1] * 9, "y": range(9), "s": [f"s{i}" for i in range(9)]})
    with pytest.raises(ValueError):
        plots.line_series(frame, "x", "y", tmp_path / "bad.svg", "Bad", series="s")


def test_bar_shares_and_heatmap(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {"year": [2023, 2023, 2024, 2024], "group": ["a", "b", "a", "b"], "v": [1, 3, 2, 2]}
    )
    _svg_ok(plots.bar_shares(frame, "year", "group", "v", tmp_path / "bars.svg", "Bars"))
    matrix = pd.DataFrame([[0.1, 0.2], [0.3, 0.4]], index=["r1", "r2"], columns=["c1", "c2"])
    _svg_ok(plots.heatmap(matrix, tmp_path / "heat.svg", "Heat", percent=True))


def test_small_multiples_and_missingness(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {"facet": ["a"] * 3 + ["b"] * 3, "x": [1, 2, 3] * 2, "y": [1, 2, 3, 3, 2, 1]}
    )
    _svg_ok(plots.small_multiples(frame, "facet", "x", "y", tmp_path / "sm.svg", "Small"))
    profile = pd.DataFrame(
        {
            "year": [2016, 2017, 2016, 2017],
            "column": ["A", "A", "B", "B"],
            "share_observed": [0.9, 0.8, 0.5, 0.4],
        }
    )
    _svg_ok(plots.missingness_heatmap(profile, tmp_path / "miss.svg", "Missing"))


def test_caption_format() -> None:
    text = plots.caption("DGT", "2016–2024", "30-day deaths", 875_013)
    assert text == "Source: DGT. Period: 2016–2024. Definition: 30-day deaths. n = 875,013."
