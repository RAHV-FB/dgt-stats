import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from dgt_stats import factor_models
from dgt_stats.paths import PROCESSED_DATA_DIR, TABLES_DIR

JS = Path(factor_models.__file__).parent / "assets" / "factors.js"


def _numbers(quote: str) -> set[float]:
    """Every number a quote prints, read both ways: '1.373' is 1373 or 1.373, '13,1' is 13.1."""
    out: set[float] = set()
    for token in re.findall(r"\d+(?:[.,]\d+)*", quote):
        candidates = {
            token.replace(",", ""),
            token.replace(".", "").replace(",", "."),
            token.replace(",", "."),
            token.replace(".", "").replace(",", ""),
        }
        for candidate in candidates:
            try:
                out.add(float(candidate))
            except ValueError:
                continue
    return out


def _printed(quote: str, value: float, unit: str) -> bool:
    if unit == "share":
        targets = [value * 100, value]
    elif unit == "relative_change":
        # Studies print a change as a percentage, with or without its sign: -0.47 is "-47".
        targets = [abs(value) * 100]
    else:
        targets = [value]
    numbers = _numbers(quote)
    return any(math.isclose(t, n, rel_tol=1e-9, abs_tol=1e-9) for t in targets for n in numbers)


def test_every_published_value_carries_its_source_and_quote() -> None:
    rows = factor_models.evidence()
    for column in ("source", "location", "url", "quote"):
        assert rows[column].notna().all(), column
    assert rows.url.str.startswith("http").all()
    for row in rows.itertuples():
        if row.unit != "ratio_range":
            assert _printed(row.quote, float(row.value), row.unit), (row.parameter, row.applies_to)
        # Interval ends feed the ranges the pages print, so they are checked too.
        for bound in (row.low, row.high):
            if not pd.isna(bound):
                assert _printed(row.quote, float(bound), row.unit), (row.parameter, bound)
    # The check catches a mistyped value, and a flipped sign wherever the unit carries one in the
    # quote; the sign of a relative change is checked row by row below.
    for factor in (0.61, 1.37, 1.9, -1):
        caught = [
            not _printed(row.quote, float(row.value) * factor, row.unit)
            for row in rows.itertuples()
            if row.unit != "ratio_range" and not (factor == -1 and row.unit == "relative_change")
        ]
        assert all(caught), factor


def test_every_enforcement_study_is_described_and_bracketed() -> None:
    from dgt_stats.site.factor_pages import ENFORCEMENT_STUDIES

    rows = factor_models.evidence()
    rows = rows[rows.parameter == "enforcement_effect"]
    assert set(rows.applies_to) == set(ENFORCEMENT_STUDIES)
    assert set(rows.unit) <= {"relative_change", "rate_ratio"}
    for row in rows.itertuples():
        if not pd.isna(row.low):
            assert row.low <= row.value <= row.high, row.applies_to
    # Every effect points the way its quote does: only texting bans went with more crashes. A
    # change is below 0 for a fall, a rate ratio below 1.
    effects = rows.set_index("applies_to")
    for name, row in effects.iterrows():
        change = row.value - 1 if row.unit == "rate_ratio" else row.value
        assert (change > 0) == (name == "texting_ban_crashes"), name


def test_the_risk_bounds_bracket_the_central_estimate() -> None:
    for factor in factor_models.FACTORS:
        low, value, high = (
            factor_models.attributable_fraction(factor, bound) for bound in ("low", "value", "high")
        )
        assert 0 < low <= value <= high < 1, factor
    # Almost every death in a crash with a driver far over the limit is caused by the alcohol.
    assert factor_models.attributable_fraction("alcohol") > 0.9
    # A distracted driver crashes twice as often: half of those crashes are caused by it. The low
    # end is the low end of that odds ratio's interval, 1.8; the high end a handheld phone, 3.6.
    assert factor_models.attributable_fraction("distraction") == pytest.approx(0.5)
    assert factor_models.attributable_fraction("distraction", "low") == pytest.approx(1 - 1 / 1.8)
    assert factor_models.attributable_fraction("distraction", "high") == pytest.approx(1 - 1 / 3.6)
    weights = factor_models.alcohol_rr_bands()
    assert sum(w for w, _ in weights.values()) == pytest.approx(1)
    assert sum(w for w, _ in factor_models.drug_rr_mix().values()) == pytest.approx(1)


def test_the_urban_share_is_what_all_roads_leave_after_interurban_roads() -> None:
    shares = factor_models.recorded_shares()
    for (factor, year), group in shares[shares.year.isin(["2022", "2024", "pooled"])].groupby(
        ["factor", "year"]
    ):
        by_zone = group.set_index("zone")
        for column in ("crashes_with_factor", "fatal_crashes"):
            assert by_zone.loc["interurban", column] + by_zone.loc[
                "urban", column
            ] == pytest.approx(by_zone.loc["all", column]), (factor, year, column)
        assert 0 < by_zone.loc["urban", "share"] < 1
    pooled = shares[(shares.year == "pooled") & (shares.zone == "all")].set_index("factor")
    assert pooled.loc["distraction", "crashes_with_factor"] == 404 + 406


def test_the_drug_share_leaves_out_drivers_who_also_had_alcohol() -> None:
    # 2023: drug positives less those with alcohol, of the drivers analysed. 2024: the drug share
    # less the alcohol-and-drug combinations, which INTCF gives as shares of the 452 positives.
    share_2023 = (196 - 94) / 862
    share_2024 = 0.164 - (0.131 + 0.031) * 452 / 937
    assert share_2024 == pytest.approx(0.086, abs=0.001)
    assert factor_models.drug_share() == pytest.approx((share_2023 + share_2024) / 2)


def test_combining_factors_removes_the_overlap() -> None:
    shares = [0.26, 0.34, 0.17]
    together = factor_models.combined(shares)
    assert max(shares) < together < sum(shares)
    assert factor_models.combined([0.0, 0.0]) == 0
    assert factor_models.combined([1.0, 0.3]) == 1


processed = pytest.mark.skipif(
    not (PROCESSED_DATA_DIR / "accidentes.parquet").exists(),
    reason="run `python scripts/build_tables.py` first",
)


def test_deaths_avoided_scale_with_the_share_removed() -> None:
    full = factor_models.deaths_avoided("alcohol", 1.0)
    half = factor_models.deaths_avoided("alcohol", 0.5)
    none = factor_models.deaths_avoided("alcohol", 0.0)
    assert half.avoided.sum() == pytest.approx(full.avoided.sum() / 2)
    assert none.avoided.sum() == 0
    # Never more deaths avoided than there are.
    assert (full.avoided < full.deaths).all()
    base = factor_models.casualties()
    assert base.deaths.sum() == pytest.approx(1779, abs=1)


@processed
def test_the_speed_curve_ends_where_the_simulator_does() -> None:
    curve = factor_models.speed_curve()
    from dgt_stats import simulator

    comply = simulator.presets().set_index("scenario").loc["all_comply"]
    assert curve.interurban_avoided.iloc[-1] == pytest.approx(-comply.deaths_change)
    assert curve.interurban_avoided.iloc[0] == pytest.approx(0, abs=1e-9)
    assert curve.interurban_avoided.is_monotonic_increasing
    assert (curve.urban_30_fall >= curve.urban_50_fall).all()


tables = pytest.mark.skipif(
    not (TABLES_DIR / "factor_speed_curve.csv").exists(),
    reason="run `python scripts/analyse.py tables` first",
)


def _browser_parameters() -> dict:
    names = ("factor_casualties", "factor_inputs", "factor_crashes", "factor_speed_curve")
    return factor_models.browser_parameters(
        {name: pd.read_csv(TABLES_DIR / f"{name}.csv") for name in names}
    )


@tables
@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_browser_computes_exactly_what_the_python_computes(tmp_path: Path) -> None:
    parameters = _browser_parameters()
    curve = pd.read_csv(TABLES_DIR / "factor_speed_curve.csv")
    grid = [
        {"speed": s, "alcohol_drugs": a, "distraction": d}
        for s in (0.0, 0.05, 0.333, 0.5, 0.995, 1.0)
        for a in (0.0, 0.25, 1.0)
        for d in (0.0, 0.6, 1.0)
    ]
    cases = [(settings, bound) for settings in grid for bound in factor_models.BOUNDS]
    (tmp_path / "p.json").write_text(json.dumps(parameters))
    (tmp_path / "c.json").write_text(json.dumps(cases))
    script = (
        f"const F = require({json.dumps(str(JS))});"
        f"const P = require({json.dumps(str(tmp_path / 'p.json'))});"
        f"const cases = require({json.dumps(str(tmp_path / 'c.json'))});"
        "console.log(JSON.stringify(cases.map(([s, b]) => ({"
        "  compare: F.compare(P, s, b),"
        "  alcohol: F.zoneTotals(F.avoided(P, 'alcohol', s.alcohol_drugs, b)),"
        "  distraction: F.zoneTotals(F.avoided(P, 'distraction', s.distraction, b)),"
        "}))));"
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    browser = json.loads(result.stdout)
    for (settings, bound), computed in zip(cases, browser):
        python = factor_models.lever_deaths(curve, settings, bound)
        for lever, zones in python.items():
            for zone, value in zones.items():
                assert computed["compare"][lever][zone] == pytest.approx(
                    value, rel=1e-9, abs=1e-9
                ), (settings, bound, lever, zone)
        for factor, share in (
            ("alcohol", settings["alcohol_drugs"]),
            ("distraction", settings["distraction"]),
        ):
            frame = factor_models.deaths_avoided(factor, share, bound)
            for zone in factor_models.ZONES:
                assert computed[factor][zone] == pytest.approx(
                    float(frame[frame.zone == zone].avoided.sum()), rel=1e-9, abs=1e-9
                ), (factor, zone, bound)


@tables
def test_the_share_needed_saves_exactly_the_lives_asked() -> None:
    curve = pd.read_csv(TABLES_DIR / "factor_speed_curve.csv")
    idle = dict.fromkeys(factor_models.LEVERS, 0.0)
    for lever in factor_models.LEVERS:
        for bound in factor_models.BOUNDS:
            share = factor_models.share_needed(curve, lever, 100, bound)
            assert 0 < share < 1, (lever, bound)
            saved = factor_models.lever_deaths(curve, {**idle, lever: share}, bound)[lever]
            assert sum(saved.values()) == pytest.approx(100, rel=1e-6), (lever, bound)
        assert math.isnan(factor_models.share_needed(curve, lever, 1779))
    # Fewer lives need a smaller share.
    assert factor_models.share_needed(curve, "speed", 50) < factor_models.share_needed(
        curve, "speed", 100
    )


@tables
def test_the_published_comparison_ranks_the_levers_as_the_page_says() -> None:
    comparison = pd.read_csv(TABLES_DIR / "factor_comparison.csv")
    everywhere = comparison[comparison.zone == "all"].set_index("lever")
    assert (
        everywhere.loc["alcohol_drugs", "avoided"]
        > everywhere.loc["speed", "avoided"]
        > everywhere.loc["distraction", "avoided"]
    )
    together = everywhere.loc["combined", "avoided"]
    levers = everywhere.drop(index="combined").avoided
    assert levers.max() < together < levers.sum()
