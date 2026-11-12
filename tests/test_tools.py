"""The interactive tools' data: each value published for the browser is the result table's value,
recomputed here independently from the committed tables."""

import math

import pandas as pd
import pytest

from dgt_stats.exposure_risk import national
from dgt_stats.paths import TABLES_DIR
from dgt_stats.site import tool_driver_risk


def _table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


# --------------------------------------------------------------------------- driver risk


@pytest.fixture(scope="module")
def drivers() -> dict:
    return tool_driver_risk.driver_data()


def test_per_km_estimates_are_the_central_rates(drivers: dict) -> None:
    # One estimate per age group, the average of the Barcelona and Madrid profiles, with its 95%
    # sampling interval; the tool offers no choice of assumptions and quotes no range.
    rates = _table("risk_national_rates")
    assert "km_total" not in rates.columns
    rates = rates[rates.method == national.CENTRAL_METHOD].set_index("group")
    for measure_id, column in (
        ("involved_per_km", "involved_ratio"),
        ("killed_per_km", "killed_ratio"),
    ):
        measure = next(m for m in drivers["age"] if m["id"] == measure_id)
        for group in ("18-29", "30-44", "65+"):
            shown = measure["groups"][group]
            assert shown["value"] == pytest.approx(rates.loc[group, column])
            assert (shown["low"], shown["high"]) == pytest.approx(
                (rates.loc[group, f"{column}_low"], rates.loc[group, f"{column}_high"])
            )
            assert set(shown) == {"label", "value", "low", "high", "interval"}
        assert measure["groups"]["45-64"]["low"] is None
    young = next(m for m in drivers["age"] if m["id"] == "involved_per_km")["groups"]["18-29"]
    assert f"{young['value']:.2f}" == "2.68" and young["interval"] == "2.5–2.9"
    assert not {"profiles", "splits", "condition", "older_conclusion"} & set(drivers)


def test_the_older_estimates_follow_the_madrid_split(drivers: dict) -> None:
    split = _table("risk_older_split")
    split = split[
        (split.profile == national.CENTRAL_METHOD) & (split.assumption == national.REFERENCE_SPLIT)
    ].set_index("group")
    measure = next(m for m in drivers["age"] if m["id"] == "involved_per_km")
    for group in ("65-74", "75+"):
        shown = measure["groups"][group]
        assert shown["value"] == pytest.approx(split.loc[group, "ratio_to_45_64"])
        assert (shown["low"], shown["high"]) == pytest.approx(
            (split.loc[group, "ratio_low"], split.loc[group, "ratio_high"])
        )
    oldest = measure["groups"]["75+"]
    assert f"{oldest['value']:.2f}" == "2.43" and oldest["interval"] == "2.0–3.0"


def test_observed_driver_rates_and_their_ratios(drivers: dict) -> None:
    severity = _table("risk_severity_and_licences").set_index("group")
    measures = {m["id"]: m for m in drivers["age"]}
    killed = measures["killed_per_involved"]
    for group, row in severity.iterrows():
        assert killed["groups"][group]["value"] == pytest.approx(row.killed_per_1000_involved)
        rate = measures["involved_per_licence"]["groups"][group]
        assert rate["value"] == pytest.approx(row.involved / row.b_licence_holders * 1000)
        low, high = rate["ci"]
        assert low < rate["value"] < high
    # The ratio of 75 and over to 45-64 deaths once involved, with Katz's interval for a ratio
    # of two proportions, computed here from the counts.
    a, b = severity.loc["75+"], severity.loc["45-64"]
    se = math.sqrt(1 / a.killed - 1 / a.involved + 1 / b.killed - 1 / b.involved)
    value = a.killed_per_1000_involved / b.killed_per_1000_involved
    shown = killed["pairs"]["75+|45-64"]
    assert shown == pytest.approx(
        [value, value * math.exp(-1.959964 * se), value * math.exp(1.959964 * se)], rel=1e-6
    )
    assert f"{killed['groups']['75+']['value']:.1f}" == "15.9"
    assert f"{killed['groups']['45-64']['value']:.1f}" == "4.6"


def test_men_and_women_come_from_the_sex_tables(drivers: dict) -> None:
    ratios = _table("drivers_sex_ratios")
    ratios = ratios[ratios.scope == "car"].set_index(["band", "measure"])
    observed = drivers["sex"]["observed"]["killed_per_involved"]
    for band, shown in observed.items():
        row = ratios.loc[(band, "deaths_per_1000_involved")]
        assert shown["ratio"] == pytest.approx([row.ratio, row.low, row.high])
    per_km = _table("risk_sex_per_km").set_index("measure")
    shown = drivers["sex"]["per_km"]["involved_per_km"]
    assert shown["ratio"] == pytest.approx(per_km.loc["involved per km", "ratio_men_to_women"])
    assert "range" not in shown
