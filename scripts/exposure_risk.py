"""Crash involvement per kilometre driven, by driver age.

Usage:
    python scripts/exposure_risk.py barcelona   # the working-day design matched to Barcelona city
    python scripts/exposure_risk.py madrid      # the Madrid household survey's age profile
    python scripts/exposure_risk.py national    # Spain: exposure methods A-D, rates, 65-74/75+
    python scripts/exposure_risk.py all

Needs the EMEF tables (``scripts/emef.py build``), the Barcelona crash layer
(``scripts/microdata.py``) and the DGT table layer (``scripts/ingest.py``). Writes
``reports/tables/risk_*.csv`` and ``reports/tables/edm_*.csv``; ``all`` takes about five minutes.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from dgt_stats import edm2018  # noqa: E402
from dgt_stats.exposure_risk import barcelona, national  # noqa: E402
from dgt_stats.paths import TABLES_DIR  # noqa: E402

log = logging.getLogger("exposure_risk")


# The youngest group pairs drivers aged 18-29 with the kilometres of residents aged 16-29, of whom
# those aged 16 and 17 drive no car; the published tables name it by its drivers.
DRIVER_LABELS = {"16-29": "18-29"}


def write(frame: pd.DataFrame, name: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frame = frame.copy()
    for column in frame.columns:
        if frame[column].dtype == object or pd.api.types.is_string_dtype(frame[column]):
            frame[column] = frame[column].replace(DRIVER_LABELS)
    frame.to_csv(TABLES_DIR / f"{name}.csv", index=False, float_format="%.10g")
    log.info("%s: %d rows", name, len(frame))


def run_barcelona() -> None:
    write(barcelona.rates(), "risk_barcelona_rates")
    write(barcelona.unknown_age_bounds(), "risk_barcelona_unknown_age_bounds")
    write(barcelona.older_ratios(), "risk_barcelona_older")
    write(barcelona.km_composition(), "risk_barcelona_km")
    write(barcelona.counts_by_day_type(), "risk_barcelona_day_type")


def run_madrid() -> None:
    profiles = [edm2018.profile("band")]
    profiles += [edm2018.profile("group", sex) for sex in (None, "male", "female")]
    write(pd.concat(profiles, ignore_index=True), "edm_profile")
    write(edm2018.older_split(), "edm_older_split")


def run_national() -> None:
    write(national.shares(), "risk_national_shares")
    write(
        pd.concat(
            [national.rates(variant) for variant in national.dgt_car_km()], ignore_index=True
        ),
        "risk_national_rates",
    )
    numerator = national.drivers_involved()
    numerator["unknown_share"] = numerator.attrs["unknown_share"]
    numerator["public_service_drivers_left_out"] = numerator.attrs[
        "public_service_drivers_left_out"
    ]
    write(numerator, "risk_national_numerator")
    km = pd.DataFrame([{"variant": k, "km": v} for k, v in national.dgt_car_km().items()])
    write(km, "risk_national_km_total")
    write(national.severity_and_licences(), "risk_severity_and_licences")
    write(national.older_split(), "risk_older_split")
    write(national.weekend_sensitivity(), "risk_weekend_sensitivity")
    write(national.sensitivity(), "risk_national_sensitivity")
    write(national.older_sensitivity(), "risk_older_sensitivity")
    write(national.unknown_age_bounds(), "risk_unknown_age_bounds")
    write(national.sex_per_km(), "risk_sex_per_km")
    write(
        pd.concat(
            [
                national.licence_prevalence(),
                national.licence_prevalence(national.BARCELONA_PROVINCE),
            ],
            ignore_index=True,
        ),
        "risk_licence_prevalence",
    )
    write(national.owner_age_comparison(), "risk_owner_age_comparison")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=("barcelona", "madrid", "national", "all"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    start = time.time()
    if args.step in ("barcelona", "all"):
        run_barcelona()
    if args.step in ("madrid", "all"):
        run_madrid()
    if args.step in ("national", "all"):
        run_national()
    log.info("done in %.1f s", time.time() - start)


if __name__ == "__main__":
    main()
