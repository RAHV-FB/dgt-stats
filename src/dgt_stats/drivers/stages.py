"""The drivers section's pipeline stages, run by ``scripts/run.py drivers``.

In order: ``tables`` writes the driver tables that need only DGT's driver tables and census;
``emef`` reads and checks the EMEF microdata and estimates car-driving exposure by age;
``exposure`` puts kilometres on driver ages (EMEF, EDM2018, MOVILIA) and divides DGT's car
drivers involved in crashes by them, for Spain and for Barcelona city's working days. ``emef``
and ``exposure`` run on one BLAS thread (``scripts/run.py`` sets it): their distance model's
optimiser stops where the order of floating-point sums leads it, and one thread makes the
committed tables reproducible on any machine.
"""

from __future__ import annotations

import logging

import pandas as pd

from dgt_stats.drivers import driver_risk, edm2018
from dgt_stats.drivers.emef import distance, exposure, ingest, older_routing
from dgt_stats.drivers.exposure_risk import barcelona, coverage, national
from dgt_stats.national.stages import write_registry
from dgt_stats.paths import table_path

log = logging.getLogger(__name__)


def tables() -> None:
    """Driver rates by sex and by the car owner's age, from DGT's tables and census."""
    write_registry(driver_risk.TABLES)


def _write_emef(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(table_path(name), index=False, float_format="%.10g")
    log.info("%s: %d rows", name, len(frame))


def emef() -> None:
    """The EMEF: read and check the files, reproduce the published figures, and estimate
    car-driving exposure by age, sex, area and year."""
    _write_emef(ingest.validate(), "emef_checks")
    people, trips = ingest.build()
    log.info("persons %d, trips %d", len(people), len(trips))
    _write_emef(ingest.inventory(), "emef_inventory")
    _write_emef(ingest.reproduce_2024(), "emef_reproduction")
    _write_emef(distance.validate_against_report(), "emef_distance_validation")
    _write_emef(exposure.imputation_check(), "emef_imputation_check")
    _write_emef(exposure.contemporary(), "emef_exposure_contemporary")
    _write_emef(exposure.by_area(), "emef_exposure_area")
    _write_emef(exposure.series(), "emef_exposure_series")
    _write_emef(exposure.periods(), "emef_exposure_periods")
    _write_emef(exposure.km_by_band(), "emef_km_by_band")
    _write_emef(exposure.sensitivity(), "emef_sensitivity")
    _write_emef(exposure.usual_frequency(), "emef_driving_frequency")
    _write_emef(exposure.weekend_away_2023(), "emef_weekend_2023")
    _write_emef(exposure.employment_benchmark(), "emef_employment_benchmark")


# The youngest group pairs drivers aged 18-29 with the kilometres of residents aged 16-29, of whom
# those aged 16 and 17 drive no car; tables of drivers and rates name it by its drivers. Tables of
# residents keep 16-29, and licence prevalence divides by residents aged 15-29.
DRIVER_LABELS = {"16-29": "18-29"}
RESIDENT_TABLES = {"edm_profile", "risk_barcelona_km", "emef_routing_older"}
GROUP_LABELS = {"risk_licence_prevalence": {"16-29": "15-29"}}


def _write_exposure(frame: pd.DataFrame, name: str) -> None:
    frame = frame.copy()
    labels = GROUP_LABELS.get(name, {} if name in RESIDENT_TABLES else DRIVER_LABELS)
    for column in frame.columns:
        if frame[column].dtype == object or pd.api.types.is_string_dtype(frame[column]):
            frame[column] = frame[column].replace(labels)
    frame.to_csv(table_path(name), index=False, float_format="%.10g")
    log.info("%s: %d rows", name, len(frame))


def exposure_barcelona() -> None:
    """The working-day check in Barcelona city: Guàrdia Urbana crashes of 2025 against EMEF
    driving inside the city."""
    _write_exposure(barcelona.rates(), "risk_barcelona_rates")
    _write_exposure(barcelona.unknown_age_bounds(), "risk_barcelona_unknown_age_bounds")
    _write_exposure(barcelona.older_ratios(), "risk_barcelona_older")
    _write_exposure(barcelona.km_composition(), "risk_barcelona_km")
    _write_exposure(barcelona.counts_by_day_type(), "risk_barcelona_day_type")


def exposure_madrid() -> None:
    """The Madrid household survey's car driving by exact age."""
    profiles = [edm2018.profile("band")]
    profiles += [edm2018.profile("group", sex) for sex in (None, "male", "female")]
    _write_exposure(pd.concat(profiles, ignore_index=True), "edm_profile")
    _write_exposure(edm2018.older_split(), "edm_older_split")


def exposure_national() -> None:
    """Spain: car-driving kilometres by driver age (methods A-D), the rates per kilometre, the
    65-74/75+ split, the coverage of DGT's kilometres and its scenarios."""
    _write_exposure(national.shares(), "risk_national_shares")
    _write_exposure(
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
    _write_exposure(numerator, "risk_national_numerator")
    km = pd.DataFrame([{"variant": k, "km": v} for k, v in national.dgt_car_km().items()])
    _write_exposure(km, "risk_national_km_total")
    _write_exposure(national.severity_and_licences(), "risk_severity_and_licences")
    older_split = national.older_split()
    _write_exposure(older_split, "risk_older_split")
    _write_exposure(national.weekend_sensitivity(), "risk_weekend_sensitivity")
    _write_exposure(national.sensitivity(), "risk_national_sensitivity")
    older = national.older_sensitivity()
    _write_exposure(older, "risk_older_sensitivity")
    _write_exposure(national.older_extremes(older), "risk_older_extremes")
    _write_exposure(national.older_decomposition(older, older_split), "risk_older_decomposition")
    _write_exposure(national.older_attribution(older), "risk_older_attribution")
    _write_exposure(national.reference_checks(), "risk_older_reference_checks")
    _write_exposure(older_routing.routing_share(), "emef_routing_older")
    _write_exposure(national.unknown_age_bounds(), "risk_unknown_age_bounds")
    _write_exposure(national.sex_per_km(), "risk_sex_per_km")
    _write_exposure(
        pd.concat(
            [
                national.licence_prevalence(),
                national.licence_prevalence(national.BARCELONA_PROVINCE),
            ],
            ignore_index=True,
        ),
        "risk_licence_prevalence",
    )
    _write_exposure(national.owner_age_comparison(), "risk_owner_age_comparison")
    _write_exposure(coverage.components(), "risk_coverage")
    _write_exposure(coverage.evidence(), "risk_coverage_evidence")
    _write_exposure(coverage.mixes(), "risk_coverage_mixes")
    _write_exposure(coverage.scenarios(), "risk_coverage_scenarios")


def exposure_all() -> None:
    """Every per-kilometre table: Barcelona city, the Madrid profile, then Spain."""
    exposure_barcelona()
    exposure_madrid()
    exposure_national()
