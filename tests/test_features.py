"""The model frame's junction correction: DGT's inverted junction flag read the other way round."""

import numpy as np
import pandas as pd
import pytest

from dgt_stats import codes, features
from dgt_stats.paths import DGT_PROCESSED_CRASHES, TABLES_DIR


def _crashes() -> pd.DataFrame:
    """Two province-years: province 8 in 2023 with the flag the wrong way round (its crashes
    flagged away from a junction carry a junction type and right-of-way flags, those flagged at
    one carry neither), and province 28 in 2023 coded as DGT does everywhere else."""
    rows = [
        # province, NUDO, NUDO_INFO, PRIORI_NORMA
        (8, 1, 999, 999),  # flagged at a junction, nothing recorded: away from one
        (8, 1, 999, 999),
        (8, 2, 4, 1),  # flagged away, junction type and right of way: at a junction
        (8, 2, 2, 0),
        (8, 2, np.nan, 1),  # flagged away, no type but right of way: at a junction
        (28, 1, 4, 1),
        (28, 1, 999, 0),  # at a junction with no type
        (28, 2, np.nan, 999),
        (28, 2, 4, 999),  # away from a junction with a type: rare, not an inversion
        (28, 2, np.nan, 999),
    ]
    frame = pd.DataFrame(rows, columns=["COD_PROVINCIA", "NUDO", "NUDO_INFO", "PRIORI_NORMA"])
    frame["ANYO"] = 2023
    for column in codes.PRIORI_COLUMNS[1:]:
        frame[column] = frame.PRIORI_NORMA
    return frame.astype({"NUDO": "Int16", "NUDO_INFO": "Int16", "COD_PROVINCIA": "Int16"})


def test_the_inverted_province_years_are_found_from_the_junction_type() -> None:
    crashes = _crashes()
    inverted = features.inverted_junction_rows(crashes)
    assert list(inverted) == [True] * 5 + [False] * 5


def test_each_treatment_reads_the_inverted_flag_as_documented() -> None:
    crashes = _crashes()

    def read(treatment: str) -> list:
        return [None if pd.isna(v) else int(v) for v in features.junction_codes(crashes, treatment)]

    published = [1, 1, 2, 2, 2, 1, 1, 2, 2, 2]
    assert read("as published") == published
    # The flag the other way round in province 8 only.
    assert read("flip") == [2, 2, 1, 1, 1] + published[5:]
    # The junction type alone loses the junction crash that has no type.
    assert read("junction type") == [2, 2, 1, 1, 2] + published[5:]
    assert read("unrecorded") == [None] * 5 + published[5:]
    # Outside the inverted province-years only Catalan crashes are moved by the near-junction
    # treatment: province 28's typed crash away from a junction stays where DGT put it.
    assert read("flip and near junctions") == read("flip")
    with pytest.raises(ValueError):
        features.junction_codes(crashes, "something else")


def test_the_near_junction_treatment_moves_catalan_crashes_with_junction_fields() -> None:
    crashes = _crashes()
    crashes["ANYO"] = [2021] * 5 + [2023] * 5  # province 8's year is no longer inverted
    crashes["NUDO"] = pd.array([1, 1, 2, 2, 2, 1, 1, 2, 2, 2], dtype="Int16")
    crashes.loc[[2, 3], "NUDO_INFO"] = pd.NA  # most crashes away carry no type: not inverted
    assert not features.inverted_junction_rows(crashes).any()
    moved = features.junction_codes(crashes, "flip and near junctions")
    # Province 8's crashes flagged away with a right-of-way flag are placed at a junction.
    assert list(moved[:5]) == [1, 1, 1, 1, 1]
    assert list(moved[5:]) == [1, 1, 2, 2, 2]


def test_the_model_frame_reads_the_corrected_flag_and_the_groupings_say_so() -> None:
    crashes = _crashes()
    for column in ("ZONA", "TIPO_VIA", "TIPO_ACCIDENTE", "CONDICION_ILUMINACION"):
        crashes[column] = 1
    crashes["CONDICION_METEO"], crashes["CONDICION_FIRME"] = 1, 1
    crashes["TRAZADO_PLANTA"], crashes["TOTAL_VEHICULOS"] = 1, 2
    crashes["hour_band"], crashes["weekend"] = "10-13", False
    crashes["fatal"], crashes["serious"] = False, False
    frame = features.model_frame(crashes)
    assert list(frame.junction[:5]) == ["not at a junction"] * 2 + ["at a junction"] * 3
    assert list(frame.junction[5:]) == ["at a junction"] * 2 + ["not at a junction"] * 3
    assert frame.attrs["junction_inverted"] == [(8, 2023)]
    published = features.model_frame(crashes, junction="as published")
    assert list(published.junction[:2]) == ["at a junction"] * 2
    groupings = features.grouping_table(frame).set_index(["predictor", "code"])
    flipped = groupings.loc[("Junction", "1" + features.INVERTED_KEY)]
    assert flipped.level.startswith("not at a junction (flag read the other way round: Barcelona")
    assert bool(flipped.reference)
    assert groupings.loc[("Junction", "2" + features.INVERTED_KEY)].level.startswith(
        "at a junction"
    )


def test_the_coding_table_counts_the_record_crash_by_crash() -> None:
    table = features.junction_coding_table(_crashes()).set_index("region")
    catalonia, rest = table.loc["Catalonia"], table.loc["rest of Spain"]
    assert catalonia.inverted_province_years == 1 and rest.inverted_province_years == 0
    assert catalonia.flagged_at == 2 and catalonia.flagged_at_with_junction_fields == 0
    assert catalonia.flagged_away_with_junction_type == 2
    assert catalonia.flagged_away_with_junction_fields == 3
    assert catalonia.at_junction == 3 and catalonia.at_junction_with_junction_fields == 3
    assert catalonia.away_with_junction_fields == 0 and catalonia.recoded == 5
    assert rest.recoded == 0 and rest.at_junction == rest.flagged_at == 2


# ----------------------------------------------------------------------------- on the data
def _processed(columns: list[str]) -> pd.DataFrame:
    if not DGT_PROCESSED_CRASHES.exists():
        pytest.skip("run `python scripts/build_tables.py` first (processed crashes missing)")
    return pd.read_parquet(DGT_PROCESSED_CRASHES, columns=columns)


def test_the_features_find_the_province_years_the_audit_flags() -> None:
    path = TABLES_DIR / "dgt_audit_junction_coding.csv"
    if not path.exists():
        pytest.skip("run `python scripts/microdata.py validate` first")
    audit = pd.read_csv(path)
    flagged = audit[audit.junction_flag_inverted.astype(bool)]
    crashes = _processed(["ANYO", "COD_PROVINCIA", "NUDO", "NUDO_INFO"])
    inverted = features.inverted_junction_rows(crashes)
    found = crashes.loc[inverted, ["COD_PROVINCIA", "ANYO"]].drop_duplicates()
    assert set(zip(found.COD_PROVINCIA.astype(int), found.ANYO.astype(int))) == set(
        zip(flagged.province, flagged.year)
    )
    assert int(inverted.sum()) == int(flagged.crashes.sum())


def test_corrected_catalan_junction_shares_are_in_line_with_earlier_years_and_spain() -> None:
    crashes = _processed(features.JUNCTION_COLUMNS)
    table = features.junction_coding_table(crashes).set_index(["region", "year"])
    catalonia, rest = table.loc["Catalonia"], table.loc["rest of Spain"]
    inverted = catalonia[catalonia.inverted_province_years > 0].index
    before = catalonia[catalonia.index < inverted.min()]
    assert list(inverted) == [2023, 2024]
    # As published the Catalan share at a junction jumps; corrected it lies among the earlier
    # years' shares and close to the rest of Spain's in the same years.
    assert (catalonia.loc[inverted].share_flagged_at > before.share_flagged_at.max() + 0.15).all()
    low, high = before.share_at_junction.min(), before.share_at_junction.max()
    assert catalonia.loc[inverted].share_at_junction.between(low, high).all()
    assert (
        catalonia.loc[inverted].share_at_junction - rest.loc[inverted].share_at_junction
    ).abs().max() < 0.02
    # Crash by crash, the corrected flag agrees with the rest of the record as in earlier years:
    # crashes it places at a junction carry a junction type or right-of-way flag, those away do not.
    corrected = catalonia.loc[inverted]
    assert (corrected.at_junction_with_junction_fields / corrected.at_junction > 0.99).all()
    assert (corrected.away_with_junction_fields / corrected.away_from_junction < 0.001).all()
    assert (corrected.flagged_at_with_junction_fields / corrected.flagged_at < 0.001).all()
    # Only the inverted province-years are recoded.
    assert int(table.recoded.sum()) == int(corrected.crashes.sum())


def test_corrected_catalan_severe_crashes_at_a_junction_match_the_catalan_file() -> None:
    """The Servei Català de Trànsit's file holds the same crashes with a death or serious injury
    within 24 hours. Corrected, DGT's count of those at a junction in 2023 matches the Catalan
    file's crashes within or near a junction, as in 2016-2020 and 2022, within 1% of the year's
    crashes (the audit's tolerance)."""
    from dgt_stats.microdata.validation import dgt_audit

    path = TABLES_DIR / "dgt_audit_junction_coding.csv"
    if not path.exists():
        pytest.skip("run `python scripts/microdata.py validate` first")
    audit = pd.read_csv(path)
    crashes = _processed([*features.MODEL_COLUMNS, "TOTAL_MU24H", "TOTAL_HG24H"])
    corrected = features.junction_codes(crashes)
    severe = (crashes.TOTAL_MU24H.fillna(0) + crashes.TOTAL_HG24H.fillna(0)) > 0
    catalan = crashes.COD_PROVINCIA.astype(str).isin(features.CATALAN_PROVINCES)
    years = sorted(set(audit[audit.junction_flag_inverted.astype(bool)].year))
    compared = dgt_audit.catalan_junction_years(audit).set_index("year")
    checked = 0
    for year in years:
        if year not in compared.index or pd.isna(compared.loc[year, "cat_file_severe_crashes"]):
            continue
        rows = catalan & severe & crashes.ANYO.eq(year)
        at = int(corrected[rows].eq(1).sum())
        row = compared.loc[year]
        within_or_near = row.cat_file_within_junction + row.cat_file_near_junction
        assert abs(at - within_or_near) <= dgt_audit.MATCH_TOLERANCE * row.severe_crashes
        checked += 1
    assert checked >= 1
