"""The validation layer: rule baselines, the Barcelona diagnosis, the DGT audit, the outward path,
the model decisions and the source comparison."""

import numpy as np
import pandas as pd
import pytest

from dgt_stats import layers
from dgt_stats.microdata.ml import modelling, rules
from dgt_stats.paths import TABLES_DIR


def _table(name: str) -> pd.DataFrame:
    path = TABLES_DIR / f"{name}.csv"
    if not path.exists():
        pytest.skip(f"run `python scripts/microdata.py validate` first ({name}.csv missing)")
    return pd.read_csv(path)


# ----------------------------------------------------------------------------- no data needed
def test_rule_shares_are_smoothed_and_unseen_groups_get_the_prevalence() -> None:
    train = pd.DataFrame({"g": ["a"] * 10 + ["b"] * 10, "y": [1] * 10 + [0] * 10})
    shares, prevalence = rules.fit_rule(train, "y", ("g",))
    assert prevalence == 0.5
    # Smoothed toward the prevalence: never 0 or 1 for a group seen ten times.
    assert 0.5 < shares["a"] < 1 and 0 < shares["b"] < 0.5
    test = pd.DataFrame({"g": ["a", "c"]})
    scored = rules.apply_rule(test, shares, prevalence, ("g",))
    assert scored[1] == prevalence


def test_paired_difference_of_identical_scores_is_zero() -> None:
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 400)
    p = rng.random(400)
    d = modelling.paired_difference(y, p, p, n=50)
    assert d["roc_auc_difference"] == 0
    assert d["roc_auc_difference_low"] == 0 == d["roc_auc_difference_high"]


def test_grouped_resamples_keep_whole_crashes_together() -> None:
    groups = np.array(["a", "a", "b", "c", "c", "c"])
    for idx in modelling.resamples(len(groups), groups, 20, seed=1):
        drawn = pd.Series(groups[idx]).value_counts()
        sizes = pd.Series(groups).value_counts()
        assert all(drawn[g] % sizes[g] == 0 for g in drawn.index)


def test_population_comparisons_keep_every_conventional_road_in_one_group() -> None:
    from dgt_stats.microdata.validation import generalisability

    road = generalisability.ROAD_CLASS
    # Code 5 (conventional, dual carriageway) is the code DGT's Catalan records use for every
    # conventional road until 2020; code 6 replaces it from 2021.
    assert road[4] == road[5] == road[6] == "conventional"
    assert road[3] != "conventional" and road[1] == road[2] == "motorway"
    assert {road[code] for code in (7, 8, 10, 11, 12, 13, 14)} == {"other"}


def test_the_outward_path_does_not_count_a_model_of_another_population() -> None:
    from dgt_stats.microdata.validation import generalisability

    stage3 = generalisability.PATH["catalonia_crash_severity"][3][1]
    # The reverse test trains on Barcelona city alone: a model of the city, not of Catalonia.
    assert not any(test.startswith("Barcelona municipality ->") for test in stage3)
    assert any(test.startswith("rest of Catalonia to ") for test in stage3)
    calculator = generalisability.PATH["calculator"]
    assert calculator[4][0] == "none"
    assert calculator[3][0] == "transport" and len(calculator[3][1]) == 5


def test_barcelona_descriptive_tables_read_the_outcome_dependent_term_as_rear_end() -> None:
    from dgt_stats.microdata import barcelona, descriptive

    recorded = pd.Series([barcelona.ACCIDENT_TYPES["Encalç"], barcelona.ACCIDENT_TYPES["Abast"]])
    merged = descriptive._bcn_crash_type(recorded)
    assert merged.nunique() == 1 and merged.iloc[0] == barcelona.ACCIDENT_TYPES["Abast"]
    # The source models, fitted earlier, keep the field as recorded.
    assert barcelona.ACCIDENT_TYPES["Encalç"] != barcelona.ACCIDENT_TYPES["Abast"]


def test_the_layers_never_share_a_source() -> None:
    sources = [s for layer in layers.LAYERS for s in layer.sources]
    assert len(sources) == len(set(sources))
    assert [layer.key for layer in layers.LAYERS] == [
        "national",
        "catalonia",
        "barcelona",
        "validation",
    ]


def test_absence_coded_dgt_field_counts_blanks_as_recorded() -> None:
    from dgt_stats.microdata.validation import dgt_audit

    frame = pd.DataFrame({c: [np.nan, "1"] for c in dgt_audit.CANDIDATES})
    status = dgt_audit.statuses(frame)
    assert status.loc[0, "CONDICION_VIENTO"] == "observed"
    assert status.loc[0, "CONDICION_NIEBLA"] == "observed"
    assert status.loc[0, "TIPO_VIA"] == "empty"
    # With no NUDO value, whether the junction fields apply is unknown: they stay unrecorded.
    assert status.loc[0, "NUDO_INFO"] == "empty"
    # The presence fields are read from DGT's dictionary: the condition fields with no
    # "not specified" code, which are fog and wind and nothing else.
    present = [c for c in dgt_audit.CANDIDATES if dgt_audit.presence_field(c)]
    assert present == ["CONDICION_NIEBLA", "CONDICION_VIENTO"]


def test_junction_fields_do_not_apply_away_from_a_junction() -> None:
    from dgt_stats.microdata.validation import dgt_audit

    junction = dgt_audit.junction_code()
    assert junction == 1  # "En intersección o nudo" in DGT's dictionary
    rows = [
        # NUDO, NUDO_INFO, PRIORI_NORMA
        (1, 999, 999),  # at a junction, nothing recorded: unrecorded
        (1, 4, 0),  # at a junction, recorded
        (2, np.nan, 999),  # away from a junction: neither applies
        (2, 4, 1),  # away from a junction but recorded: a recorded value stays recorded
    ]
    frame = pd.DataFrame({c: ["1"] * len(rows) for c in dgt_audit.CANDIDATES})
    frame["NUDO"], frame["NUDO_INFO"], frame["PRIORI_NORMA"] = zip(*rows)
    status = dgt_audit.statuses(frame)
    assert list(status.NUDO_INFO) == ["not_specified", "observed", "not_applicable", "observed"]
    assert list(status.PRIORI_NORMA) == ["not_specified", "observed", "not_applicable", "observed"]
    # A field outside the junction fields keeps its 999 away from a junction.
    frame["CONDICION_METEO"] = 999
    assert (dgt_audit.statuses(frame).CONDICION_METEO == "not_specified").all()


def test_recording_by_year_counts_what_applies_and_what_is_recorded() -> None:
    """The table the data page's missing-values chart draws: per year and field, the crashes
    the audit's rule says a field applies to and those with a value recorded."""
    from dgt_stats.microdata.validation import dgt_audit

    rows = [
        # ANYO, NUDO, NUDO_INFO, CONDICION_NIEBLA
        (2022, 1, 4, np.nan),  # at a junction, type recorded; no fog
        (2022, 1, 999, 1),  # at a junction, type not specified; light fog
        (2022, 2, np.nan, np.nan),  # away from a junction: the type does not apply
        (2023, 2, 4, np.nan),  # away, but a type recorded: recorded
    ]
    frame = pd.DataFrame({c: ["1"] * len(rows) for c in dgt_audit.CANDIDATES})
    frame["ANYO"], frame["NUDO"], frame["NUDO_INFO"], frame["CONDICION_NIEBLA"] = zip(*rows)
    out = dgt_audit.recording_by_year(frame).set_index(["column", "year"])
    assert set(out.index.get_level_values("column")) == set(dgt_audit.CANDIDATES)
    info = out.loc["NUDO_INFO"]
    assert list(info.applies) == [2, 1] and list(info.recorded) == [1, 1]
    assert info.loc[2022, "share_recorded_where_applies"] == pytest.approx(0.5)
    fog = out.loc["CONDICION_NIEBLA"]
    assert list(fog.applies) == [3, 1] and list(fog.recorded) == [3, 1]
    assert list(out.loc["DIA_SEMANA"].rows) == [3, 1]


def test_unrecorded_shares_are_taken_over_the_crashes_a_field_applies_to(monkeypatch) -> None:
    from dgt_stats.microdata.validation import dgt_audit

    monkeypatch.setattr(dgt_audit, "MIN_PROVINCE_CRASHES", 1)
    # Province 28: four junction crashes, one with the junction type unrecorded, and four crashes
    # away from a junction. Province 41: two junction crashes, both recorded.
    nudo = [1, 1, 1, 1, 2, 2, 2, 2, 1, 1]
    info = [999, 4, 4, 4, np.nan, np.nan, np.nan, np.nan, 2, 2]
    frame = pd.DataFrame({c: ["1"] * len(nudo) for c in dgt_audit.CANDIDATES})
    frame["NUDO"], frame["NUDO_INFO"] = nudo, info
    frame["COD_PROVINCIA"] = [28] * 8 + [41] * 2
    frame["ANYO"] = 2020
    status = dgt_audit.statuses(frame)
    coding = pd.DataFrame(
        {"province": [28, 41], "year": [2020, 2020], "junction_flag_inverted": [False, False]}
    )
    regional = dgt_audit.regional_recording(frame, status, coding).set_index("field")
    row = regional.loc["NUDO_INFO"]
    assert row.applies_share == pytest.approx(6 / 10)
    assert row.unrecorded_share == pytest.approx(1 / 6)
    assert row.province_max == pytest.approx(1 / 4) and row.province_min == 0


def test_catalan_junction_years_name_the_place_dgt_counts_match() -> None:
    from dgt_stats.microdata.validation import dgt_audit

    coding = pd.DataFrame(
        {
            "province": [8, 8, 28],
            "year": [2022, 2023, 2023],
            "catalan": [True, True, False],
            "severe_crashes": [100, 100, 50],
            "severe_at_junction": [30, 70, 20],
            "cat_file_severe_crashes": [100, 100, np.nan],
            "cat_file_within_junction": [25, 25, np.nan],
            "cat_file_near_junction": [5, 5, np.nan],
            "cat_file_between_junctions": [70, 70, np.nan],
            "junction_flag_inverted": [False, True, False],
        }
    )
    years = dgt_audit.catalan_junction_years(coding).set_index("year")
    assert years.loc[2022, "dgt_at_junction_matches"] == "within or near a junction"
    assert years.loc[2023, "dgt_at_junction_matches"] == "between junctions"
    assert bool(years.loc[2023, "junction_flag_inverted"])
    assert years.loc[2023, "cat_share_between_junctions"] == pytest.approx(0.7)


def test_the_artefact_share_interval_holds_its_estimate() -> None:
    from dgt_stats.microdata.validation import dgt_audit

    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 2000)
    values = y + rng.normal(0, 1, len(y))
    flags = y + rng.normal(0, 3, len(y))
    share = dgt_audit._share_of_lift(y, flags, values)
    low, high = dgt_audit.share_interval(y, flags, values)
    assert 0 < low < share < high < 1


# ----------------------------------------------------------------------------- results
def test_every_source_model_is_compared_with_a_lookup_table() -> None:
    comparison = _table("ml_rule_comparison")
    assert set(comparison.model) == set(rules.RULES)
    adds = comparison.roc_auc_gain.ge(rules.MIN_GAIN) & comparison.roc_auc_gain_low.gt(0)
    assert (adds == comparison.model_adds_signal_over_table).all()


def test_diagnosis_components_telescope_to_the_total_drop() -> None:
    components = _table("ml_barcelona_diagnosis_components")
    parts = ("training-size cost", "intrinsic difference", "transport cost")
    for (_, _), group in components[~components.features.str.startswith("full against")].groupby(
        ["features", "estimator"]
    ):
        g = group.set_index("component").value
        # The table is written to six significant digits, so allow the rounding of four values.
        assert sum(g[p] for p in parts) == pytest.approx(g["total drop"], abs=1e-5)


def test_strategies_score_the_same_rows_for_every_strategy() -> None:
    strategies = _table("ml_domain_strategies")
    for _, group in strategies.groupby(["target_domain", "estimator"]):
        assert group.n.nunique() == 1 and group.positives.nunique() == 1
        assert group.strategy.str.startswith("domain-specific").sum() == 1


def test_every_transfer_test_with_a_reference_reports_its_gap() -> None:
    transport = _table("ml_transport_validation")
    fitted = transport[transport.estimator.ne("baseline_prior")]
    with_reference = fitted[fitted.in_domain_cv_roc_auc.notna() & fitted.roc_auc.notna()]
    assert not with_reference.empty
    # Transferred minus native: negative is ranking lost in the move.
    gap = with_reference.roc_auc - with_reference.in_domain_cv_roc_auc
    # Six significant digits in the table: allow the rounding of three values.
    assert np.allclose(gap, with_reference.transfer_gap, rtol=0, atol=5e-6)
    temporal = transport[
        transport.experiment.str.startswith("temporal holdout")
        & transport.estimator.ne("baseline_prior")
    ]
    assert temporal.in_domain_cv_roc_auc.notna().all()


def test_the_calculator_tests_sit_beside_a_reference_and_the_table() -> None:
    tests = _table("gen_calculator_transfer")
    assert set(tests.model) == {"calculator"}
    held_out = tests[~tests.experiment.str.startswith(("random", "rolling"))]
    # Each province, the city and the last year, each with its own in-domain reference.
    assert len(held_out) == 6
    assert held_out.in_domain_cv_roc_auc.notna().all() and held_out.table_roc_auc.notna().all()
    gap = held_out.roc_auc - held_out.in_domain_cv_roc_auc
    assert np.allclose(gap, held_out.transfer_gap, rtol=0, atol=5e-6)
    rolling = tests[tests.experiment.str.startswith("rolling")].iloc[0]
    assert np.isnan(rolling.in_domain_cv_roc_auc) and rolling.roc_auc > rolling.table_roc_auc
    # The rolling test reproduces the calculator's own evaluation on the same crashes.
    scores = _table("sev_rolling_scores")
    own = scores[scores.subset.str.fullmatch(r"\d{4}-\d{4}") & scores.estimator.eq("calculator")]
    assert int(own.n.iloc[0]) == int(rolling.test_n)
    assert abs(float(own.roc_auc.iloc[0]) - rolling.roc_auc) < 1e-6


def test_road_type_coding_switches_only_in_the_catalan_records() -> None:
    coding = _table("gen_coding_by_region").set_index(["region", "year"])
    catalonia = coding.loc["Catalonia"]
    rest = coding.loc["Spain outside Catalonia"]
    before, after = catalonia.loc[:2020], catalonia.loc[2021:]
    assert (
        before.road_type_6_single_carriageway < 0.01 * before.road_type_5_dual_carriageway
    ).all()
    assert (after.road_type_5_dual_carriageway == 0).all()
    assert rest.road_type_5_dual_carriageway.max() < 1.5 * rest.road_type_5_dual_carriageway.min()


def test_national_transferability_is_claimed_only_after_all_five_stages() -> None:
    path = _table("ml_outward_path")
    for model, group in path.groupby("model"):
        status = group.set_index("stage").status
        claimed = group.verdict.iloc[0] == "potentially nationally transferable"
        assert claimed == (status == "passed").all(), model
        highest = int(group.highest_consecutive_stage.iloc[0])
        assert all(status[s] == "passed" for s in range(1, highest + 1))
        assert highest == 5 or status[highest + 1] != "passed"


def test_the_dgt_audit_decision_follows_its_checks() -> None:
    checks = _table("dgt_audit_checks")
    file_checks = checks[checks.check.str.match(r"\d")]
    assert len(file_checks) == 7
    decision = checks.decision.iloc[0]
    assert decision.startswith("DGT microdata may train") == bool(file_checks.passed.all())


def test_the_dgt_audit_tables_follow_its_definition_of_unrecorded() -> None:
    from dgt_stats.microdata.validation import dgt_audit

    regional = _table("dgt_audit_regional").set_index("field")
    # Blank fog and wind fields are the recorded "no"; the junction fields apply to some crashes.
    assert (regional.loc[["CONDICION_NIEBLA", "CONDICION_VIENTO"]].unrecorded_share == 0).all()
    assert (regional.loc[list(dgt_audit.JUNCTION_FIELDS)].applies_share < 1).all()
    junction = regional.loc[list(dgt_audit.JUNCTION_FIELDS)]
    assert junction.province_spread_without_inverted_junction_years.notna().all()
    artefacts = _table("dgt_audit_artefacts")
    assert (artefacts.artefact_share_low <= artefacts.artefact_share_of_lift).all()
    assert (artefacts.artefact_share_of_lift <= artefacts.artefact_share_high).all()
    assert (
        artefacts.artefacts_dominate
        == (artefacts.artefact_share_of_lift >= dgt_audit.MAX_ARTEFACT_SHARE)
    ).all()


def test_only_catalan_records_have_the_junction_flag_inverted() -> None:
    from dgt_stats.microdata.validation import dgt_audit

    coding = _table("dgt_audit_junction_coding")
    inverted = coding[coding.junction_flag_inverted]
    assert inverted.catalan.all()
    matched = dgt_audit.catalan_junction_years(coding)
    flipped = matched.junction_flag_inverted
    assert (matched[flipped].dgt_at_junction_matches == "between junctions").all()
    assert (matched[~flipped].dgt_at_junction_matches != "between junctions").all()


def test_the_national_test_holds_no_catalan_record() -> None:
    transfer = _table("dgt_audit_transfer").set_index("check")
    assert bool(transfer.loc["no Catalan records in the national test", "passed"])
    assert bool(transfer.loc["target equivalence", "passed"])


def test_model_decisions_follow_the_declared_rules() -> None:
    from dgt_stats.microdata.validation import decisions as rules_module

    decisions = _table("ml_model_decisions")
    comparison = _table("ml_rule_comparison").set_index("model")
    selected = _table("ml_selected")
    assert set(decisions.decision) <= set(rules_module.OUTCOMES)
    for model in selected.loc[selected.primary, "model"]:
        assert model in set(decisions.model), model
    for row in decisions.itertuples():
        if row.decision == rules_module.DROP:
            continue
        if row.variant in ("retrospective", "retrospective_administrative"):
            assert row.decision == rules_module.KEEP_RESEARCH
        if row.model.startswith("catalonia_common"):
            assert row.decision == rules_module.KEEP_RESEARCH
        if row.model in comparison.index and row.variant in ("context",):
            adds = bool(comparison.loc[row.model, "model_adds_signal_over_table"])
            if not adds:
                assert row.decision == rules_module.REPLACE, row.model
            else:
                assert row.decision in rules_module.FEATURED, row.model


def test_the_decision_rules_apply_in_the_declared_order() -> None:
    from dgt_stats.microdata.validation import decisions as d

    base = dict(beats_chance=True, holds_later=True, research=False, calibrated=True)
    assert d.decide(**{**base, "beats_chance": False}, beats_table=True) == d.DROP
    assert d.decide(**{**base, "holds_later": False}, beats_table=True) == d.DROP
    assert d.decide(**{**base, "research": True}, beats_table=False) == d.KEEP_RESEARCH
    assert d.decide(**base, beats_table=False) == d.REPLACE
    assert d.decide(**base, beats_table=True) == d.KEEP_PREDICTIVE
    assert d.decide(**{**base, "calibrated": False}, beats_table=True) == d.KEEP_RANKING


def test_every_source_answers_every_question() -> None:
    from dgt_stats import source_profile

    frame = _table("source_comparison")
    assert set(frame.question) == set(source_profile.QUESTIONS)
    assert (frame.groupby("source").question.nunique() == len(source_profile.QUESTIONS)).all()
    assert set(frame.basis) <= {"measured", "reconciled", "file", "documentation"}
