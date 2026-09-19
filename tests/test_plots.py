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


def test_forest_and_calibration(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "predictor": ["Zone", "Zone", "Zone", "Lighting", "Lighting"],
            "level": ["street", "interurban", "crossing", "daylight", "dark"],
            "odds_ratio": [1.0, 2.5, 1.3, 1.0, 1.8],
            "or_low": [1.0, 2.2, 1.0, 1.0, 1.6],
            "or_high": [1.0, 2.9, 1.7, 1.0, 2.0],
            "is_reference": [True, False, False, True, False],
        }
    )
    out = plots.forest(
        frame,
        "predictor",
        "level",
        "odds_ratio",
        "or_low",
        "or_high",
        tmp_path / "forest.svg",
        "Forest",
        reference_flag="is_reference",
    )
    _svg_ok(out)
    text = out.read_text(encoding="utf-8")
    assert "interurban" in text and "Lighting" in text
    cal = pd.DataFrame(
        {
            "outcome": ["fatal"] * 3 + ["serious"] * 3,
            "predicted": [0.005, 0.02, 0.08, 0.03, 0.1, 0.3],
            "observed": [0.006, 0.019, 0.085, 0.028, 0.11, 0.29],
        }
    )
    _svg_ok(plots.calibration(cal, "predicted", "observed", tmp_path / "cal.svg", "Cal", "outcome"))


def test_dot_interval_panels_and_slope(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "panel": ["p", "p", "p", "q", "q", "q"],
            "name": ["a", "b", "c"] * 2,
            "v": [1, 3, 2, 10, 30, 20],
            "lo": [0.5, 2, 1, 5, 20, 10],
            "hi": [2, 4, 3, 15, 40, 30],
        }
    )
    out = plots.dot_interval_panels(
        frame,
        "panel",
        "name",
        "v",
        "lo",
        "hi",
        tmp_path / "panels.svg",
        "Panels",
        order=["b", "c", "a"],
        xlabel="per unit",
    )
    _svg_ok(out)
    ranks = pd.DataFrame({"name": list("abc"), "left": [1.0, 2.0, 3.0], "right": [3.0, 1.0, 2.0]})
    out = plots.slope(
        ranks, "name", "left", "right", tmp_path / "slope.svg", "Slope", "Left", "Right"
    )
    _svg_ok(out)
