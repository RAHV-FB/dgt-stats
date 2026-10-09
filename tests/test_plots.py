import contextlib
import json
import re
from pathlib import Path

import matplotlib.dates
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from dgt_stats import figures, plots, summaries
from dgt_stats.microdata import charts as microdata_charts
from dgt_stats.paths import TABLES_DIR

# build_all writes these from the summary tables plus missingness_by_year.csv; the Q3 ones need
# the model tables.
EXPECTED_FIGURES = {
    "r1_risk_change",
    "l1_trend_projection",
    "l2_observed_over_trend",
    "l3_frequency_severity",
    "l4_km_against_fuel",
    "m1_season_profile",
    "m2_month_effects",
    "m3_lockdown",
    "a3_sex_ratios",
    "f1_speed_severity",
    "f2_factor_shares",
    "c3_speed_status",
    "v1_per_vehicle_vs_per_km",
    "p1_points_series",
    "p2_july_placebos",
    "d1_missingness",
}
EXPECTED_MODEL_FIGURES = {
    "s1_forest_fatal",
    "s2_adverse_conditions",
}
# The driver-age figures, drawn from the committed risk tables (scripts/exposure_risk.py).
EXPECTED_DRIVER_FIGURES = (
    {"dr1_involved_per_km", "dr2_killed_per_involved"}
    if (TABLES_DIR / "risk_national_rates.csv").exists()
    else set()
)
# The calculator's predicted-against-observed figure, drawn when its table is committed.
EXPECTED_CALCULATOR_FIGURES = (
    {"sev1_predicted_observed"} if (TABLES_DIR / "sev_calibration.csv").exists() else set()
)
_TABLES_PRESENT = all(
    (TABLES_DIR / f"{name}.csv").exists() for name in (*summaries.SUMMARIES, "missingness_by_year")
)


def _svg_ok(path: Path) -> None:
    assert path.exists() and path.suffix == ".svg"
    text = path.read_text(encoding="utf-8")
    assert "<svg" in text and len(text) > 1_000
    assert "dc:date" not in text  # no date stamp, so an unchanged figure does not churn on rebuild


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


def test_missingness_heatmap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    drawn = _capture_axes(monkeypatch)
    matrix = pd.DataFrame(
        [[1.0, 0.97], [0.9, 0.8], [0.5, None]], index=["A", "B", "C"], columns=[2016, 2017]
    )
    _svg_ok(plots.missingness_heatmap(matrix, tmp_path / "miss.svg", "Missing"))
    heat, bar = drawn[0]
    # The rows keep the matrix's order, the first at the top.
    assert [label.get_text() for label in heat.get_yticklabels()] == ["A", "B", "C"]
    # A binned scale with every band's edges labelled, 0% included.
    labels = [label.get_text() for label in bar.get_yticklabels()]
    assert labels == ["0%", "20%", "50%", "80%", "95%", "100%"]
    image = heat.get_images()[0]
    colours = {tuple(image.cmap(image.norm(v))) for v in (0.96, 1.0)}
    assert len(colours) == 1  # 96% and 100% fall in the same band
    assert image.cmap(image.norm(0.94)) != image.cmap(image.norm(0.96))


def _profile(rows: list[tuple[str, dict[str, float]]]) -> pd.DataFrame:
    """A missing-values table (``missingness_by_year``) for one year from per-field shares."""
    records = []
    for column, shares in rows:
        record = {"year": 2020, "column": column, "rows": 1000}
        for state in ("empty", "not_specified", "not_applicable", "unknown"):
            record[f"share_{state}"] = shares.get(state, 0.0)
        record["share_observed"] = 1 - sum(shares.values())
        records.append(record)
    return pd.DataFrame(records)


def _applicability(rows: list[tuple[str, int, int]]) -> pd.DataFrame:
    """The audited fields' table (``missingness_where_applicable``) for one year of 1000 crashes:
    each field with the crashes it applies to and those with a value recorded."""
    return pd.DataFrame(
        [
            {"year": 2020, "column": column, "rows": 1000, "applies": applies, "recorded": recorded}
            for column, applies, recorded in rows
        ]
    )


def test_the_missing_values_chart_leaves_not_applicable_out() -> None:
    from dgt_stats import codes

    profile = _profile(
        [
            ("DIA_SEMANA", {}),
            # The dictionary defines the island's empty cell as "No aplica".
            ("ISLA", {"empty": 0.9, "not_specified": 0.02}),
            # Fields the audit examines: their shares in this table are not read.
            ("ACERA", {"not_applicable": 0.8, "not_specified": 0.05}),
            ("CONDICION_NIEBLA", {"empty": 0.9}),
            ("NUDO_INFO", {"empty": 0.6}),
            ("CARRETERA_CRUCE", {"empty": 0.97}),
            *[(column, {"not_specified": 0.6}) for column in codes.PRIORI_COLUMNS],
        ]
    )
    applicability = _applicability(
        [
            ("DIA_SEMANA", 1000, 1000),
            # 998: left out of the denominator.
            ("ACERA", 200, 150),
            # A presence field: every crash is recorded, a blank being the recorded "no".
            ("CONDICION_NIEBLA", 1000, 1000),
            # Not applicable away from a junction.
            ("NUDO_INFO", 400, 380),
            # The crossing road, like the junction fields, applies only at a junction.
            ("CARRETERA_CRUCE", 400, 30),
            *[(column, 450, 360 + i // 10) for i, column in enumerate(codes.PRIORI_COLUMNS)],
        ]
    )
    shown = figures.recorded_where_applicable(profile, applicability)[2020]
    names = figures.MISSINGNESS_FIELDS
    assert shown[names["ACERA"]] == pytest.approx(0.75)
    assert shown[names["ISLA"]] == pytest.approx(0.08 / 0.1)
    assert shown[names["CONDICION_NIEBLA"]] == pytest.approx(1.0)
    assert shown[names["NUDO_INFO"]] == pytest.approx(0.95)
    assert shown[names["CARRETERA_CRUCE"]] == pytest.approx(0.075)
    # The right-of-way flags share one row, and no raw field name is left.
    row = figures.priority_row(len(codes.PRIORI_COLUMNS))
    assert shown[row] == pytest.approx(0.8, abs=0.01)
    assert not any("_" in label for label in shown.index)
    # Most completely recorded first.
    assert list(shown) == sorted(shown, reverse=True)
    # Flags that are no longer recorded together stop the build.
    apart = applicability.copy()
    apart.loc[apart.column == "PRIORI_OTRA", "recorded"] = 450
    with pytest.raises(ValueError):
        figures.recorded_where_applicable(profile, apart)
    # So does a field without an English name, or tables of different years.
    with pytest.raises(ValueError):
        figures.recorded_where_applicable(
            _profile([("NEW_FIELD", {})]), _applicability([("DIA_SEMANA", 1000, 1000)])
        )
    with pytest.raises(ValueError):
        figures.recorded_where_applicable(profile, applicability.assign(year=2021))


def test_the_missing_values_chart_reads_the_audit_rule() -> None:
    """On the committed tables, the chart's audited rows are the audit's: the fog and strong-wind
    fields are always recorded, and, with the inverted Catalan junction flag read the other way
    round, the junction fields are not recorded less often in the inverted years."""
    profile_path = TABLES_DIR / "missingness_by_year.csv"
    audited_path = TABLES_DIR / "missingness_where_applicable.csv"
    junctions_path = TABLES_DIR / "dgt_audit_junction_coding.csv"
    if not (profile_path.exists() and audited_path.exists() and junctions_path.exists()):
        pytest.skip("the missing-values tables are not built")
    applicability = pd.read_csv(audited_path)
    shown = figures.recorded_where_applicable(pd.read_csv(profile_path), applicability)
    names = figures.MISSINGNESS_FIELDS
    assert (shown.loc[[names["CONDICION_NIEBLA"], names["CONDICION_VIENTO"]]] == 1).all().all()
    junctions = pd.read_csv(junctions_path)
    years = figures.inverted_junction_years(shown, junctions)
    assert years == [2023, 2024]
    for column in ("NUDO_INFO", "CARRETERA_CRUCE"):
        rows = applicability[applicability.column == column]
        assert (rows.applies < rows.rows).all()
    # Read as published, the inverted years' junction type would fall far below every other
    # year's; read the other way round, it does not.
    junction_type = shown.loc[figures.MISSINGNESS_FIELDS["NUDO_INFO"]]
    others = [year for year in shown.columns if year not in years]
    assert junction_type[years].min() >= junction_type[others].min()
    # A table that shows the drop is refused.
    dropped = shown.copy()
    dropped.loc[figures.MISSINGNESS_FIELDS["NUDO_INFO"], years] = 0.7
    with pytest.raises(ValueError):
        figures.inverted_junction_years(dropped, junctions)


def test_caption_format() -> None:
    text = plots.caption("DGT", "2016–2024", "30-day deaths", 875_013)
    assert text == "Source: DGT. Period: 2016–2024. Definition: 30-day deaths. n = 875,013."
    text = plots.caption("DGT", "2016–2024", "30-day deaths", "15,441 deaths")
    assert text.endswith("n = 15,441 deaths.")


def test_percent_ticks_keep_the_decimals_they_need() -> None:
    assert [plots._percent_text(v) for v in (0, 0.025, 0.05, 0.075, 0.2)] == [
        "0%",
        "2.5%",
        "5%",
        "7.5%",
        "20%",
    ]
    assert plots._percent_text(0.05, decimals=1) == "5.0%"
    # Negative ticks carry a true minus sign, as the site's text does.
    assert [plots._percent_text(v, signed=True) for v in (-0.05, 0.0, 0.1)] == [
        "\u22125%",
        "0%",
        "+10%",
    ]
    assert plots._tick(-1500) == "\u22121,500" and plots._tick(-0.25) == "\u22120.25"


def test_series_styles_differ_beyond_colour() -> None:
    styles = [plots._series_style(i) for i in range(len(plots.CATEGORICAL))]
    assert len({(s["linestyle"], s.get("marker")) for s in styles}) == len(styles)


def test_line_series_with_band(tmp_path: Path) -> None:
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
    text = out.read_text(encoding="utf-8")
    assert "65-74" in text and "75+" in text  # both series are labelled


def test_dot_interval(tmp_path: Path) -> None:
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


def test_dot_interval_can_keep_its_ticks_on_whole_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Deaths per 1,000 involved run from about 3 to 20: whole-number ticks, no needless decimals.
    drawn = _capture_axes(monkeypatch)
    frame = pd.DataFrame(
        {"name": list("abc"), "v": [4.1, 8.5, 15.9], "lo": [3.3, 6.5, 12.6], "hi": [5.1, 10.8, 20]}
    )
    plots.dot_interval(
        frame, "name", "v", "lo", "hi", tmp_path / "w.svg", "W", keep_order=True, integer_ticks=True
    )
    axis = drawn[0][0]
    axis.figure.canvas.draw()
    labels = [label.get_text() for label in axis.get_xticklabels() if label.get_text()]
    assert labels and all("." not in label for label in labels), labels


def test_ratio_charts_can_use_a_log_axis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Ratios on a log axis, so a halving and a doubling look the same size; the axes are
    # captured as each chart is saved.
    drawn = []
    save = plots.save

    def keep(fig, path):
        drawn.append([axis for axis in fig.axes])
        return save(fig, path)

    monkeypatch.setattr(plots, "save", keep)
    ratios = pd.DataFrame(
        {
            "name": ["a", "b", "c"],
            "v": [1.2, 1.9, 5.9],
            "lo": [1.0, 1.3, 5.1],
            "hi": [1.5, 2.8, 6.9],
        }
    )
    out = plots.dot_interval(
        ratios, "name", "v", "lo", "hi", tmp_path / "log.svg", "Log", reference=1.0, log=True
    )
    _svg_ok(out)
    axis = drawn[-1][0]
    assert axis.get_xscale() == "log"
    assert list(axis.get_xticks()) == [1.0, 2.0, 4.0]
    left, right = axis.get_xlim()
    assert left < 1.0 and right > 6.9
    odds = ratios.assign(
        panel=["p", "p", "q"], v=[0.6, 0.8, 0.7], lo=[0.5, 0.7, 0.6], hi=[0.7, 0.9, 1.1]
    )
    out = plots.dot_interval_panels(
        odds,
        "panel",
        "name",
        "v",
        "lo",
        "hi",
        tmp_path / "logpanels.svg",
        "Log panels",
        reference=1.0,
        from_zero=False,
        shared=True,
        log=True,
    )
    _svg_ok(out)
    for axis in drawn[-1]:
        if axis.get_xticks().size:
            assert axis.get_xscale() == "log"
            # Fewer than three doublings in range, so the ticks add 0.75 between them.
            assert list(axis.get_xticks()) == [0.5, 0.75, 1.0]


def test_charts_embed_the_glyphs_of_their_serif(tmp_path: Path) -> None:
    import base64
    import io

    from fontTools.ttLib import TTFont

    frame = pd.DataFrame(
        {
            "label": ["Línea à", "B (n=2)", "C"],
            "group": ["Heading one", "Heading one", "Heading two"],
            "v": [0.2, 0.4, 0.3],
            "lo": [0.1, 0.3, 0.2],
            "hi": [0.3, 0.5, 0.4],
        }
    )
    paths = [tmp_path / "first.svg", tmp_path / "second.svg"]
    for path in paths:
        plots.dot_interval(frame, "label", "v", "lo", "hi", path, "Dots", group="group")
    text = paths[0].read_text(encoding="utf-8")
    # The same chart twice is the same bytes: the embedded subsets carry no timestamp.
    assert text == paths[1].read_text(encoding="utf-8")
    # Text is set in the serif with a fallback, and both weights in use are embedded.
    assert "font-family: 'STIX Two Text', 'Times New Roman', serif" in text
    faces = dict(re.findall(r"font-weight:(\d+);src:url\(data:font/woff;base64,([^)]+)\)", text))
    assert set(faces) == {"400", "600"}
    # Each subset holds the characters the chart writes in that weight, accents included.
    regular = TTFont(io.BytesIO(base64.b64decode(faces["400"])))
    assert {ord(c) for c in "Línea à(n=2)"} <= set(regular.getBestCmap())
    heading = TTFont(io.BytesIO(base64.b64decode(faces["600"])))
    assert {ord(c) for c in "Heading one"} <= set(heading.getBestCmap())


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
    # A level with no odds ratio (no crash of the outcome) is left out, not drawn as an empty row.
    separated = pd.concat(
        [
            frame,
            pd.DataFrame(
                [
                    {
                        "predictor": "Lighting",
                        "level": "not specified",
                        "odds_ratio": float("nan"),
                        "or_low": float("nan"),
                        "or_high": float("nan"),
                        "is_reference": False,
                    }
                ]
            ),
        ]
    )
    out = plots.forest(
        separated,
        "predictor",
        "level",
        "odds_ratio",
        "or_low",
        "or_high",
        tmp_path / "forest_separated.svg",
        "Forest",
        reference_flag="is_reference",
    )
    _svg_ok(out)
    assert "not specified" not in out.read_text(encoding="utf-8")
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


def test_intervention_and_placebo_dots(tmp_path: Path) -> None:
    periods = pd.date_range("2005-01-01", "2007-12-01", freq="MS")
    frame = pd.DataFrame(
        {
            "period": list(periods) * 2,
            "group": ["a"] * len(periods) + ["b"] * len(periods),
            "deaths": list(range(36)) * 2,
            "fitted": list(range(36)) * 2,
            "counterfactual": [v + 3 for v in range(36)] * 2,
        }
    )
    out = plots.intervention(
        frame,
        "period",
        "deaths",
        "fitted",
        "counterfactual",
        tmp_path / "its.svg",
        "ITS",
        pd.Timestamp("2006-07-01"),
        "July 2006",
        facet="group",
        shaded=[(pd.Timestamp("2007-06-01"), pd.Timestamp("2007-12-01"), "later")],
    )
    _svg_ok(out)
    out = plots.intervention(
        frame[frame.group == "a"],
        "period",
        "deaths",
        "fitted",
        "counterfactual",
        tmp_path / "its_single.svg",
        "ITS",
        pd.Timestamp("2006-07-01"),
        "July 2006",
    )
    _svg_ok(out)
    placebo = pd.DataFrame(
        {
            "label": ["Jan", "Feb", "Mar"],
            "v": [-0.1, 0.02, 0.05],
            "lo": [-0.2, -0.05, -0.01],
            "hi": [0.0, 0.09, 0.11],
            "is_true": [True, False, False],
        }
    )
    out = plots.dot_interval(
        placebo,
        "label",
        "v",
        "lo",
        "hi",
        tmp_path / "placebo.svg",
        "Placebo",
        percent=True,
        reference=0,
        highlight="is_true",
        keep_order=True,
    )
    _svg_ok(out)


def test_intervention_enlarges_the_months_after_the_break(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawn = _capture_axes(monkeypatch)
    periods = pd.date_range("2000-01-01", "2007-11-01", freq="MS")
    frame = pd.DataFrame(
        {
            "period": periods,
            "deaths": [400 + (i % 12) * 10 for i in range(len(periods))],
            "fitted": [400.0] * len(periods),
            "cf": [410.0] * len(periods),
            "alt": [420.0] * len(periods),
        }
    )
    names = {"observed": "Observed deaths", "fitted": "Fitted model", "counterfactual": "Main"}
    for narrow in (False, True):
        with plots.narrow() if narrow else contextlib.nullcontext():
            _svg_ok(
                plots.intervention(
                    frame,
                    "period",
                    "deaths",
                    "fitted",
                    "cf",
                    tmp_path / f"zoom_{narrow}.svg",
                    "Zoom",
                    pd.Timestamp("2006-07-01"),
                    "1 July 2006",
                    alternative=("alt", "Straight"),
                    names=names,
                    zero_based=False,
                    zoom_from=pd.Timestamp("2005-01-01"),
                )
            )
    for axes in drawn:
        overview, zoom = axes[:2]
        # The value axes start near the data, not at zero.
        assert overview.get_ylim()[0] > 300 and zoom.get_ylim()[0] > 300
        # The second panel holds the enlarged months only.
        left, right = zoom.get_xlim()
        assert matplotlib.dates.num2date(left).year == 2004
        assert matplotlib.dates.num2date(right) < matplotlib.dates.num2date(overview.get_xlim()[1])
        # One name for each line, as given.
        legend = axes[0].figure.legends or [axes[1].get_legend()]
        texts = [text.get_text().replace("\n", " ") for text in legend[0].get_texts()]
        assert texts == ["Observed deaths", "Fitted model", "Main", "Straight"]
    with pytest.raises(ValueError):
        plots.intervention(
            frame.assign(group="a"),
            "period",
            "deaths",
            "fitted",
            "cf",
            tmp_path / "bad.svg",
            "Bad",
            pd.Timestamp("2006-07-01"),
            "July",
            facet="group",
            zoom_from=pd.Timestamp("2005-01-01"),
        )


def test_hidden_bar_series_count_in_the_total_but_are_not_drawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawn = _capture_axes(monkeypatch)
    frame = pd.DataFrame({"year": [2023] * 3, "status": ["a", "b", "rare"], "drivers": [50, 49, 1]})
    plots.bar_shares(
        frame,
        "year",
        "status",
        "drivers",
        tmp_path / "bars.svg",
        "Bars",
        order=["a", "b"],
        hidden=("rare",),
    )
    axis = drawn[0][0]
    assert [text.get_text() for text in axis.get_legend().get_texts()] == ["a", "b"]
    tops = [patch.get_y() + patch.get_height() for patch in axis.patches]
    assert max(tops) == pytest.approx(0.99)


def test_dot_rows_without_a_value_are_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawn = _capture_axes(monkeypatch)
    frame = pd.DataFrame(
        {
            "label": ["2004", "2005: left out", "2006"],
            "v": [0.01, None, -0.1],
            "lo": [-0.02, None, -0.15],
            "hi": [0.04, None, -0.05],
            "is_true": [False, False, True],
        }
    )
    plots.dot_interval(
        frame,
        "label",
        "v",
        "lo",
        "hi",
        tmp_path / "notes.svg",
        "Notes",
        percent=True,
        reference=0.0,
        highlight="is_true",
        keep_order=True,
    )
    axis = drawn[0][0]
    assert [label.get_text() for label in axis.get_yticklabels()] == [
        "2004",
        "2005: left out",
        "2006",
    ]
    # Two markers, none at the note's row.
    points = [
        (x, y)
        for line in axis.get_lines()
        if line.get_marker() not in (None, "None", "")
        for x, y in zip(line.get_xdata(), line.get_ydata())
    ]
    assert len(points) == 2 and all(y != 1 for _, y in points)


def test_breaks_are_marked_and_a_series_that_always_breaks_is_unjoined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawn = _capture_axes(monkeypatch)
    years = list(range(2014, 2020))
    frame = pd.DataFrame(
        {
            "factor": ["A"] * 12,
            "zone": ["x"] * 6 + ["y"] * 6,
            "year": years * 2,
            "share": [0.1] * 12,
            # x breaks once, after 2016; y breaks at every year.
            "segment": [0, 0, 0, 1, 1, 1] + list(range(6)),
        }
    )
    plots.segmented_small_multiples(
        frame, "factor", "year", "share", "zone", "segment", tmp_path / "f.svg", "F"
    )
    marks = [line for line in drawn[0][0].get_lines() if line.get_marker() == "|"]
    assert len(marks) == 1 and marks[0].get_xdata()[0] == pytest.approx(2016.5)


@pytest.mark.skipif(not _TABLES_PRESENT, reason="run `python scripts/analyse.py tables` first")
def test_build_all_writes_every_registered_figure(tmp_path: Path) -> None:
    frames = {name: pd.read_csv(TABLES_DIR / f"{name}.csv") for name in summaries.SUMMARIES}
    captions = figures.build_all(tmp_path, frames=frames)
    # The regional figures are whatever the microdata chart module draws from its tables.
    regional: dict[str, str] = {}
    (tmp_path / "regional").mkdir()
    microdata_charts.build(tmp_path / "regional", regional)
    expected = (
        EXPECTED_FIGURES
        | (EXPECTED_MODEL_FIGURES if summaries.model_tables_present() else set())
        | EXPECTED_CALCULATOR_FIGURES
        | EXPECTED_DRIVER_FIGURES
        | set(regional)
    )
    assert set(captions) == expected
    assert {p.stem for p in tmp_path.glob("*.svg")} == expected
    for name in expected:
        _svg_ok(tmp_path / f"{name}.svg")
    # Every figure is also drawn for a phone's column, no wider than the column allows, with
    # every piece of text at the size of the tick labels or larger.
    narrow = tmp_path / "narrow"
    assert {p.stem for p in narrow.glob("*.svg")} == expected
    for name in expected:
        _svg_ok(narrow / f"{name}.svg")
        width, smallest = _svg_width_and_smallest_text(narrow / f"{name}.svg")
        assert width <= plots.NARROW_MAX_POINTS, name
        assert smallest >= plots.TICK_SIZE, name
        # Shown 334 px wide (a 390 px phone, inside the dark theme's chart box), the smallest
        # text is 11 px or more.
        assert smallest * 334 / width >= 11, name
        assert width < figures.svg_width(tmp_path / f"{name}.svg"), name
    saved = json.loads((tmp_path / "captions.json").read_text(encoding="utf-8"))
    assert saved == captions
    # n is counted from the frame each figure draws and says what it counts.
    n_speed = int(frames["speed_severity_pooled"].speed_crashes.sum())
    assert captions["f1_speed_severity"].endswith(
        f"n = {n_speed:,} crashes with inappropriate speed recorded."
    )
    n_drivers = int(frames["q9_infraction_shares"].query("zone == 'all'").total.sum())
    assert captions["c3_speed_status"].endswith(f"n = {n_drivers:,} drivers.")
    if EXPECTED_DRIVER_FIGURES:
        severity = pd.read_csv(TABLES_DIR / "risk_severity_and_licences.csv")
        n_involved = int(severity[severity.group != "65+"].involved.sum())
        assert captions["dr2_killed_per_involved"].endswith(f"n = {n_involved:,} drivers involved.")
        # The per-km chart shows each estimate and its sampling interval, no sensitivity bands.
        assert "95% sampling intervals" in captions["dr1_involved_per_km"]
        assert "sensitivity" not in captions["dr1_involved_per_km"].lower()


@pytest.mark.skipif(not _TABLES_PRESENT, reason="run `python scripts/analyse.py tables` first")
def test_build_all_removes_a_figure_that_is_no_longer_registered(tmp_path: Path) -> None:
    stale = tmp_path / "q9_report_day_hour.svg"
    stale.write_text("<svg></svg>", encoding="utf-8")
    (tmp_path / "narrow").mkdir()
    stale_narrow = tmp_path / "narrow" / "ml9_withdrawn.svg"
    stale_narrow.write_text("<svg></svg>", encoding="utf-8")
    frames = {name: pd.read_csv(TABLES_DIR / f"{name}.csv") for name in summaries.SUMMARIES}
    figures.build_all(tmp_path, frames=frames)
    assert not stale.exists() and not stale_narrow.exists()


def _svg_width_and_smallest_text(path: Path) -> tuple[float, float]:
    """A chart's width in points and the size of its smallest text, in the same units."""

    text = path.read_text(encoding="utf-8")
    sizes = [float(size) for size in re.findall(r"font-size: ([\d.]+)px", text)]
    return figures.svg_width(path), min(sizes)


def _capture_axes(monkeypatch: pytest.MonkeyPatch) -> list[list]:
    """The axes of every chart drawn from now on, captured as it is saved."""
    drawn: list[list] = []
    save = plots.save

    def keep(fig, path):
        drawn.append(list(fig.axes))
        return save(fig, path)

    monkeypatch.setattr(plots, "save", keep)
    return drawn


def test_narrow_sets_and_restores_the_drawing_width() -> None:
    wide = (plots.FIGURE_WIDTH, plots.NOTE_SIZE, plots.NARROW)
    with plots.narrow():
        assert plots.FIGURE_WIDTH == plots.NARROW_WIDTH and plots.NARROW
        # Notes are set at the tick size, the smallest text a phone shows.
        assert plots.NOTE_SIZE == plots.TICK_SIZE
    assert (plots.FIGURE_WIDTH, plots.NOTE_SIZE, plots.NARROW) == wide
    with pytest.raises(RuntimeError), plots.narrow():
        raise RuntimeError("a chart failed")
    assert (plots.FIGURE_WIDTH, plots.NOTE_SIZE, plots.NARROW) == wide


def test_narrow_labels_wrap_and_wide_ones_do_not() -> None:
    label = "generic limit for the road (value not recorded)  (n=17,969)"
    assert plots._fit(label) == label
    with plots.narrow():
        lines = plots._fit(label).split("\n")
        assert lines[-1] == "(n=17,969)" and lines[-2] == "not recorded)"
        assert all(len(line) <= plots.NARROW_LABEL_CHARS for line in lines)
        # Never broken at a hyphen; a short label is left alone.
        assert plots._fit("75 and over (model-dependent)") == "75 and over\n(model-dependent)"
        assert plots._fit("Per resident") == "Per resident"
        # The lines are as even as the words allow: no word is left alone on the last line.
        assert plots._fit("2007–2011: left out") == "2007–2011:\nleft out"
        assert plots._axis_text("Ratio of deaths per 100 crashes, log scale") == (
            "Ratio of deaths per\n100 crashes, log scale"
        )


def test_narrow_charts_fit_a_phone_column(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    drawn = _capture_axes(monkeypatch)
    rows = pd.DataFrame(
        {
            "name": [
                "personal mobility vehicle rider  (n=528)",
                "van or light truck passenger  (n=40)",
                "car driver  (n=4,671)",
            ],
            "v": [0.02, 0.01, 0.001],
            "lo": [0.01, 0.0, 0.0005],
            "hi": [0.03, 0.09, 0.002],
        }
    )
    panels = pd.concat([rows.assign(panel=p) for p in ("First", "Second", "Third")])
    wide_out = plots.dot_interval_panels(
        panels, "panel", "name", "v", "lo", "hi", tmp_path / "wide.svg", "Wide", xlabel="Share"
    )
    with plots.narrow():
        dots = plots.dot_interval(
            rows,
            "name",
            "v",
            "lo",
            "hi",
            tmp_path / "dots.svg",
            "Dots",
            xlabel="Share of people in recorded crashes with a long axis label",
            reference=0.016,
            reference_label="all",
            percent=True,
        )
        stacked = plots.dot_interval_panels(
            panels, "panel", "name", "v", "lo", "hi", tmp_path / "panels.svg", "P", xlabel="Share"
        )
    for out in (dots, stacked):
        _svg_ok(out)
        width, smallest = _svg_width_and_smallest_text(out)
        assert width <= plots.NARROW_MAX_POINTS and smallest >= plots.TICK_SIZE, out.name
    assert figures.svg_width(wide_out) > 2 * plots.NARROW_MAX_POINTS
    # The long labels wrap, their counts on a line of their own.
    labels = [tick.get_text() for tick in drawn[1][0].get_yticklabels()]
    assert "personal mobility\nvehicle rider\n(n=528)" in labels
    # Side by side when wide, stacked when narrow, each stacked panel with its own numbers.
    wide_axes, narrow_axes = drawn[0], drawn[2]
    assert len({round(axis.get_position().y0, 3) for axis in wide_axes}) == 1
    assert len({round(axis.get_position().x0, 3) for axis in narrow_axes}) == 1
    assert len({round(axis.get_position().y0, 3) for axis in narrow_axes}) == 3
    assert all(axis.xaxis.get_tick_params()["labelbottom"] for axis in narrow_axes)


def test_narrow_bars_thin_crowded_year_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawn = _capture_axes(monkeypatch)
    years = pd.DataFrame(
        {
            "year": [y for y in range(2010, 2025) for _ in range(2)],
            "group": ["a", "b"] * 15,
            "v": [1, 2] * 15,
        }
    )
    plots.bar_shares(years, "year", "group", "v", tmp_path / "wide.svg", "Bars")
    with plots.narrow():
        out = plots.bar_shares(years, "year", "group", "v", tmp_path / "narrow.svg", "Bars")
    assert figures.svg_width(out) <= plots.NARROW_MAX_POINTS
    wide = [label.get_text() for label in drawn[0][0].get_xticklabels()]
    narrow = [label.get_text() for label in drawn[1][0].get_xticklabels()]
    assert all(wide) and len(narrow) == len(wide)
    # Every second year is named, so the names do not run into each other; every bar stays.
    assert narrow[::2] == wide[::2] and not any(narrow[1::2])


def test_narrow_charts_name_the_months_they_thin_and_add_ticks_to_a_sparse_axis() -> None:
    plots.apply_style()
    with plots.narrow():
        fig, (months, change) = plt.subplots(2, 1, figsize=(1.6, 2.4))
        months.set_xticks(range(1, 13), plots.MONTH_TICKS)
        months.set_xlim(0.6, 12.4)
        change.plot([-0.15, 0.34], [0, 1])
        change.set_xlim(-0.15, 0.34)
        fig.draw_without_rendering()
        assert sum(-0.15 <= at <= 0.34 for at in change.get_xticks()) < 3
        plots._add_sparse_ticks(fig)
        plots._thin_crowded_ticks(fig)
    # A letter alone does not say which month it is: every other month is named instead.
    assert [label.get_text() for label in months.get_xticklabels()] == [
        "Jan",
        "",
        "Mar",
        "",
        "May",
        "",
        "Jul",
        "",
        "Sep",
        "",
        "Nov",
        "",
    ]
    # A change from -15% to +34% is labelled on both sides of 0, not at 0 and +20% only.
    shown = [at for at in change.get_xticks() if -0.15 <= at <= 0.34]
    assert len(shown) >= 3 and min(shown) < 0
    plt.close(fig)


def test_ratio_panels_and_line_panels(tmp_path: Path) -> None:
    years = list(range(2015, 2025))
    frame = pd.DataFrame(
        {
            "measure": ["Count"] * 10 + ["Per tonne"] * 10,
            "year": years * 2,
            "ratio": [1.0] * 5
            + [0.75, 0.85, 0.95, 1.0, 1.0]
            + [1.0] * 5
            + [1.0, 1.0, 1.1, 1.2, 1.1],
        }
    )
    frame["range_low"] = 0.9
    frame["range_high"] = 1.1
    out = plots.ratio_panels(
        frame,
        "measure",
        "year",
        "ratio",
        "range_low",
        "range_high",
        tmp_path / "ratio.svg",
        "Ratio",
        last_fitted=2019,
    )
    _svg_ok(out)
    text = out.read_text(encoding="utf-8")
    assert "Count" in text and "Per tonne" in text
    lines = pd.DataFrame(
        {
            "panel": ["A"] * 20 + ["B"] * 20,
            "series": (["Total"] * 10 + ["Part"] * 10) * 2,
            "year": years * 4,
            "index": list(range(100, 90, -1)) * 4,
        }
    )
    _svg_ok(
        plots.line_panels(
            lines,
            "panel",
            "year",
            "index",
            "series",
            tmp_path / "lines.svg",
            "Lines",
            focal="Total",
        )
    )


# Colour-vision deficiency simulation (Machado, Oliveira and Fernandes 2009, full severity) in
# linear sRGB; distances in OKLab, times 100.
_CVD = {
    "normal": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "protan": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deutan": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritan": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}
_LMS = (
    (0.4122214708, 0.5363325363, 0.0514459929),
    (0.2119034982, 0.6806995451, 0.1073969566),
    (0.0883024619, 0.2817188376, 0.6299787005),
)
_LAB = (
    (0.2104542553, 0.7936177850, -0.0040720468),
    (1.9779984951, -2.4285922050, 0.4505937099),
    (0.0259040371, 0.7827717662, -0.8086757660),
)


def _oklab(colour: str, vision: str):
    import numpy as np
    from matplotlib.colors import to_rgb

    srgb = np.array(to_rgb(colour))
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    linear = np.clip(np.array(_CVD[vision]) @ linear, 0, 1)
    return np.array(_LAB) @ np.cbrt(np.array(_LMS) @ linear)


def test_the_season_series_differ_in_colour_and_marker() -> None:
    import itertools

    import numpy as np

    looks = [{"color": plots.ACCENT, "marker": "o"}, *figures.SEASON_STYLES.values()]
    assert len({look["marker"] for look in looks}) == len(looks)
    assert len({look["linestyle"] for look in figures.SEASON_STYLES.values()}) == 3
    # Every pair, deaths included, at least 15 apart with full colour vision and at least 10
    # under each colour-vision deficiency; the three greys these replace were 11 apart.
    for vision, floor in (("normal", 15), ("protan", 10), ("deutan", 10), ("tritan", 10)):
        for a, b in itertools.combinations([look["color"] for look in looks], 2):
            distance = 100 * np.linalg.norm(_oklab(a, vision) - _oklab(b, vision))
            assert distance >= floor, (vision, a, b, distance)


@pytest.mark.skipif(not _TABLES_PRESENT, reason="run `python scripts/analyse.py tables` first")
def test_season_long_run_and_sex_ratio_charts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawn = _capture_axes(monkeypatch)
    frames = {name: pd.read_csv(TABLES_DIR / f"{name}.csv") for name in summaries.SUMMARIES}

    def summary(name: str) -> pd.DataFrame:
        return frames[name].copy()

    captions: dict[str, str] = {}
    figures._season_figures(tmp_path, captions, summary)
    figures._sex_figures(tmp_path, captions, summary)
    figures._long_run_figures(tmp_path, captions, summary)
    season_profile, _, lockdown, sex_ratios, trend = drawn[:5]
    # The road-use series in both season charts take their own colour and marker.
    for axes in (season_profile, lockdown):
        lines = {line.get_label(): line for line in axes[0].get_lines()}
        for name, look in figures.SEASON_STYLES.items():
            assert lines[name].get_color() == look["color"], name
            assert lines[name].get_marker() == look["marker"], name
    # Ratios of men's to women's rates on a log axis, the same in every panel, and labelled so.
    assert all(axis.get_xscale() == "log" for axis in sex_ratios)
    assert "log scale" in sex_ratios[0].figure.get_supxlabel()
    # Each long-run panel names what it counts and the measure its trend was fitted to.
    titles = [axis.get_title(loc="left").replace("\n", " ") for axis in trend]
    assert titles == list(figures.LONG_RUN_PANELS.values())
    assert all("deaths a year" in title for title in titles)
    assert "per registered vehicle" in titles[1] and "per tonne of road fuel" in titles[2]


@pytest.mark.skipif(not summaries.model_tables_present(), reason="run `python scripts/model.py`")
def test_the_forest_plot_names_road_types_in_english(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drawn = _capture_axes(monkeypatch)
    figures._severity_figures(tmp_path, {})
    labels = [label.get_text().strip() for label in drawn[0][0].get_yticklabels()]
    # The page and its tables call DGT's autovía a dual carriageway; so does the chart.
    assert "dual carriageway" in labels
    assert not any("autov" in label.lower() for label in labels)
