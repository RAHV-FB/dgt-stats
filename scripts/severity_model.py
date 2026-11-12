"""Fit the Catalan severity model, evaluate it and run its tests on held-out crashes.

Usage:
    python scripts/severity_model.py

Reads the Catalan feature table written by ``scripts/microdata.py features`` and writes
``reports/tables/sev_*.csv``. The nested choices refit the model a few hundred times: expect
about twenty minutes on one core.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from dgt_stats import metrics, severity_model, severity_tests  # noqa: E402
from dgt_stats.paths import TABLES_DIR  # noqa: E402

log = logging.getLogger("severity_model")


def write(frame: pd.DataFrame, name: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.10g")
    log.info("%s: %d rows", name, len(frame))


def _subsets(rolling: pd.DataFrame) -> dict[str, pd.Series]:
    """The pooled years, each year, each zone, Barcelona city, each province, and each zone of
    each province."""
    urban = rolling.zone == "urban"
    first, last = severity_model.ROLLING_TEST_YEARS[0], severity_model.ROLLING_TEST_YEARS[-1]
    subsets = {f"{first}-{last}": rolling.year > 0}
    subsets |= {str(year): rolling.year == year for year in severity_model.ROLLING_TEST_YEARS}
    subsets |= {f"zone: {zone}": rolling.zone == zone for zone in severity_model.ZONES}
    subsets["Barcelona city, urban streets"] = urban & rolling.barcelona_city
    subsets["urban streets outside Barcelona city"] = urban & ~rolling.barcelona_city
    subsets |= {
        f"province: {province}": rolling.province == province
        for province in severity_model.PROVINCES
    }
    subsets |= {
        f"province and zone: {province}|{zone}": (rolling.province == province)
        & (rolling.zone == zone)
        for province in severity_model.PROVINCES
        for zone in severity_model.ZONES
    }
    return subsets


def _scores(rolling: pd.DataFrame, estimators: list[str]) -> pd.DataFrame:
    rows = []
    for subset, mask in _subsets(rolling).items():
        part = rolling[mask]
        y = part.fatal.to_numpy()
        low, high = metrics.wilson(y.sum(), len(y))
        for name in estimators:
            rows.append(
                {"subset": subset, "estimator": name}
                | metrics.scores(y, part[name].to_numpy())
                | {"observed_low": low, "observed_high": high}
            )
    return pd.DataFrame(rows)


def _population(rec: severity_model.Records) -> pd.DataFrame:
    """The crashes the model describes against all the file's crashes: the excluded roads are
    those whose owner network is not named, and they change the fatal share."""
    everything = severity_model.load_all()
    roads = severity_model.road_of(everything)
    fatal = everything.fatal.to_numpy().astype(int)
    zone = roads.map({key: zone for key, (_, zone) in severity_model.ROADS.items()})
    zone = zone.fillna("interurban").to_numpy()
    groups = {
        "fitted (named owner network or not a conventional road)": ~roads.isin(
            severity_model.EXCLUDED_ROADS
        ).to_numpy(),
        "excluded: owner recorded as other": (roads == "conventional_owner_other").to_numpy(),
        "excluded: owner blank": (roads == "conventional_owner_blank").to_numpy(),
        "excluded: both": roads.isin(severity_model.EXCLUDED_ROADS).to_numpy(),
        "all crashes in the file": np.ones(len(roads), dtype=bool),
    }
    rows = []
    for label, mask in groups.items():
        for scope, scoped in (
            ("all zones", mask),
            ("interurban roads", mask & (zone == "interurban")),
        ):
            n, k = int(scoped.sum()), int(fatal[scoped].sum())
            low, high = metrics.wilson(k, n)
            rows.append(
                {
                    "population": label,
                    "zone": scope,
                    "crashes": n,
                    "fatal": k,
                    "fatal_share": k / n if n else np.nan,
                    "fatal_share_low": low,
                    "fatal_share_high": high,
                }
            )
    out = pd.DataFrame(rows)
    fitted = out[out.population.str.startswith("fitted")]
    assert int(fitted[fitted.zone == "all zones"].crashes.iloc[0]) == len(rec.y)
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = time.time()
    rec = severity_model.records()
    nested = severity_model.nested_rolling(rec)
    final, final_grid = severity_model.final_choice(rec)
    choices = pd.concat(
        [
            nested.choices,
            pd.DataFrame([severity_model.choice_row(final, final_grid, "published model")]),
        ],
        ignore_index=True,
    )
    write(choices, "sev_choices")

    rolling = nested.predictions
    estimators = ["model", "boosted_trees", "road_x_crash_table"]
    write(_scores(rolling, estimators), "sev_rolling_scores")
    y = rolling.fatal.to_numpy()
    comparison = metrics.bootstrap_intervals(
        y, {name: rolling[name].to_numpy() for name in estimators}, reference="model"
    )
    write(comparison, "sev_comparison")
    calibration = []
    for name in estimators:
        table = metrics.calibration_groups(y, rolling[name].to_numpy())
        table.insert(0, "estimator", name)
        calibration.append(table)
    write(pd.concat(calibration, ignore_index=True), "sev_calibration")
    write(severity_model.geography(rec), "sev_geography")
    write(_population(rec), "sev_population")
    write(severity_tests.held_out_tests(rec, nested), "sev_tests")

    fitted, x = severity_model.final_fit(final, rec)
    draws = severity_model.bootstrap_draws(x, rec.y, final.c, fitted.columns)
    covariance = np.cov(draws, rowvar=False)
    contrasts = pd.concat(
        [
            severity_model.scenario_contrasts(fitted, covariance, base).assign(base=label)
            for label, base in (
                ("interurban", severity_model.REFERENCE_SCENARIO),
                ("urban", severity_model.URBAN_REFERENCE),
            )
        ],
        ignore_index=True,
    )
    write(contrasts, "sev_contrasts")
    write(severity_model.stability(final, rec), "sev_stability")
    coefficients = pd.DataFrame(
        {
            "column": fitted.columns,
            "group": [severity_model.column_group(col) for col in fitted.columns],
            "coefficient": fitted.coef,
            "bootstrap_se": np.sqrt(np.diag(covariance)),
        }
    )
    write(coefficients, "sev_coefficients")
    log.info("done in %.1f s", time.time() - start)


if __name__ == "__main__":
    main()
