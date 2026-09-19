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


def test_line_series_with_band_and_small_multiples_with_series(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "year": list(range(2014, 2025)) * 2,
            "band": ["65-74"] * 11 + ["75+"] * 11,
            "value": list(range(11)) + list(range(5, 16)),
        }
    )
    frame["low"] = frame.value - 1
    frame["high"] = frame.value + 1
    out = plots.line_series(
        frame, "year", "value", tmp_path / "band.svg", "Band", series="band", band=("low", "high")
    )
    _svg_ok(out)
    frame["kind"] = "a"
    other = frame.assign(kind="b", value=frame.value * 2, low=frame.low * 2, high=frame.high * 2)
    both = pd.concat([frame, other])
    out = plots.small_multiples(
        both, "band", "year", "value", tmp_path / "sm2.svg", "Panels", ncols=2, series="kind"
    )
    _svg_ok(out)
    text = out.read_text(encoding="utf-8")
    assert ">a<" in text and ">b<" in text  # series names appear in the shared legend


def test_dot_interval_and_grouped_bars(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {"name": list("abcdef"), "v": [1, 3, 2, 5, 4, 6], "lo": [0.5] * 6, "hi": [7] * 6}
    )
    out = plots.dot_interval(
        frame,
        "name",
        "v",
        "lo",
        "hi",
        tmp_path / "dots.svg",
        "Dots",
        reference=3.5,
        reference_label="Spain",
    )
    _svg_ok(out)
    bars = pd.DataFrame(
        {"band": ["a", "a", "b", "b"], "kind": ["x", "y", "x", "y"], "share": [0.2, 0.1, 0.5, 0.4]}
    )
    out = plots.grouped_bars(
        bars, "band", "kind", "share", tmp_path / "bars2.svg", "Bars", percent=True
    )
    _svg_ok(out)
