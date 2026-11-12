"""The DGT coding tables (unrecorded shares, junction flag, fog and wind), the road-type coding,
the severity model's tests and the source comparison."""

import numpy as np
import pandas as pd
import pytest

from dgt_stats.paths import TABLES_DIR


def _table(name: str) -> pd.DataFrame:
    path = TABLES_DIR / f"{name}.csv"
    if not path.exists():
        pytest.skip(f"run `python scripts/microdata.py analyse` first ({name}.csv missing)")
    return pd.read_csv(path)


def test_barcelona_descriptive_tables_read_the_outcome_dependent_term_as_rear_end() -> None:
    from dgt_stats.microdata import barcelona, descriptive

    recorded = pd.Series([barcelona.ACCIDENT_TYPES["Encalç"], barcelona.ACCIDENT_TYPES["Abast"]])
    merged = descriptive._bcn_crash_type(recorded)
    assert merged.nunique() == 1 and merged.iloc[0] == barcelona.ACCIDENT_TYPES["Abast"]
    # The crash table keeps the field as recorded.
    assert barcelona.ACCIDENT_TYPES["Encalç"] != barcelona.ACCIDENT_TYPES["Abast"]


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


def test_the_crossing_road_follows_the_junction_rule_where_it_is_read() -> None:
    """The crossing road is not a candidate, so the audit's own tables never read it; read for the
    missing-values chart, it does not apply away from a junction, like the junction fields."""
    from dgt_stats.microdata.validation import dgt_audit

    assert dgt_audit.CROSSING_ROAD not in dgt_audit.CANDIDATES
    assert not dgt_audit.presence_field(dgt_audit.CROSSING_ROAD)
    rows = [
        # ANYO, NUDO, CARRETERA_CRUCE
        (2022, 1, "N-340"),  # at a junction, recorded
        (2022, 1, np.nan),  # at a junction, empty: unrecorded
        (2022, 2, np.nan),  # away from a junction: does not apply
    ]
    columns = (*dgt_audit.CANDIDATES, dgt_audit.CROSSING_ROAD)
    frame = pd.DataFrame({c: ["1"] * len(rows) for c in columns})
    frame["ANYO"], frame["NUDO"], frame[dgt_audit.CROSSING_ROAD] = zip(*rows)
    status = dgt_audit.statuses(frame, columns)
    assert list(status[dgt_audit.CROSSING_ROAD]) == ["observed", "empty", "not_applicable"]
    assert dgt_audit.CROSSING_ROAD not in dgt_audit.statuses(frame).columns
    out = dgt_audit.recording_by_year(frame, columns=columns).set_index("column")
    assert out.loc[dgt_audit.CROSSING_ROAD, "applies"] == 2
    assert out.loc[dgt_audit.CROSSING_ROAD, "recorded"] == 1


def test_presence_coding_flags_a_province_that_codes_fog_its_own_way(monkeypatch, tmp_path) -> None:
    """A presence field given to more than a tenth of a province-year's crashes is coded another
    way; the wind field's "." (no strong wind) does not count as the condition."""
    from dgt_stats.microdata.validation import dgt_audit

    cat = pd.DataFrame(
        {"year": [2020] * 4, "province_code": [8] * 4, "D_BOIRA": ["Si", "Si", "No n'hi ha", "Si"]}
    )
    path = tmp_path / "catalonia.parquet"
    cat.to_parquet(path)
    monkeypatch.setattr(dgt_audit.catalonia, "PROCESSED", path)
    n = 20
    frame = pd.DataFrame(
        {
            "ANYO": [2020] * (2 * n),
            "COD_PROVINCIA": [8] * n + [28] * n,
            # Barcelona: light fog in 3 of 20 crashes; Madrid: in 1 of 20.
            "CONDICION_NIEBLA": [1, 1, 2] + [np.nan] * (n - 3) + [1] + [np.nan] * (n - 1),
            # Wind's "." is the recorded "no", never the condition.
            "CONDICION_VIENTO": ["."] * n + ["1"] + [np.nan] * (n - 1),
            "TOTAL_MU24H": [1, 1, 0, 1] + [0] * (n - 4) + [0] * n,
            "TOTAL_HG24H": [0] * (2 * n),
        }
    )
    out = dgt_audit.presence_coding(frame).set_index("province")
    assert out.loc[8, "CONDICION_NIEBLA_recorded"] == 3
    assert out.loc[8, "CONDICION_VIENTO_recorded"] == 0
    assert out.loc[28, "CONDICION_VIENTO_recorded"] == 1
    assert bool(out.loc[8, "CONDICION_NIEBLA_coding_break"])
    assert not bool(out.loc[28, "CONDICION_NIEBLA_coding_break"])
    # Fog among the severe crashes, beside the Catalan file's count for the same province-year.
    assert out.loc[8, "severe_CONDICION_NIEBLA_recorded"] == 2
    assert out.loc[8, "cat_file_fog"] == 3 and pd.isna(out.loc[28, "cat_file_fog"])
    breaks = dgt_audit.presence_breaks(out.reset_index())
    assert list(zip(breaks.field, breaks.province)) == [("CONDICION_NIEBLA", 8)]
    assert breaks.iloc[0].years == [2020]


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


def test_the_dgt_audit_tables_follow_its_definition_of_unrecorded() -> None:
    from dgt_stats.microdata.validation import dgt_audit

    regional = _table("dgt_audit_regional").set_index("field")
    # Blank fog and wind fields are the recorded "no"; the junction fields apply to some crashes.
    assert (regional.loc[["CONDICION_NIEBLA", "CONDICION_VIENTO"]].unrecorded_share == 0).all()
    assert (regional.loc[list(dgt_audit.JUNCTION_FIELDS)].applies_share < 1).all()
    junction = regional.loc[list(dgt_audit.JUNCTION_FIELDS)]
    assert junction.province_spread_without_inverted_junction_years.notna().all()


def test_only_catalan_records_have_the_junction_flag_inverted() -> None:
    from dgt_stats.microdata.validation import dgt_audit

    coding = _table("dgt_audit_junction_coding")
    inverted = coding[coding.junction_flag_inverted]
    assert inverted.catalan.all()
    matched = dgt_audit.catalan_junction_years(coding)
    flipped = matched.junction_flag_inverted
    assert (matched[flipped].dgt_at_junction_matches == "between junctions").all()
    assert (matched[~flipped].dgt_at_junction_matches != "between junctions").all()


def test_every_source_answers_every_question() -> None:
    from dgt_stats import source_profile

    frame = _table("source_comparison")
    assert set(frame.question) == set(source_profile.QUESTIONS)
    assert (frame.groupby("source").question.nunique() == len(source_profile.QUESTIONS)).all()
    assert set(frame.basis) <= {"measured", "reconciled", "file", "documentation"}


def test_the_severity_tests_sit_beside_a_reference_and_the_table() -> None:
    tests = _table("sev_tests")
    # The last year, each province left out, and Barcelona city, each with its own in-domain
    # reference and the table fitted on the same training crashes.
    assert len(tests) == 6
    assert tests.in_domain_cv_roc_auc.notna().all() and tests.table_roc_auc.notna().all()
    gap = tests.roc_auc - tests.in_domain_cv_roc_auc
    assert np.allclose(gap, tests.transfer_gap, rtol=0, atol=1e-9)
    assert (tests.roc_auc_low <= tests.roc_auc).all() and (
        tests.roc_auc <= tests.roc_auc_high
    ).all()
