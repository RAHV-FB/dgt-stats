import pandas as pd
import pytest

from dgt_stats import agebands, driver_risk, io_exposure, io_tables

pytestmark = pytest.mark.skipif(
    not (
        io_exposure.staging_path("conductores_por_edad").exists()
        and io_tables.staging_path("tables_driver_victims").exists()
    ),
    reason="run `python scripts/ingest.py tables exposure` first",
)


def test_exposure_bands_nest_both_sources() -> None:
    for key, (low, high) in agebands.DGT_BANDS.items():
        band = agebands.band_for(low, high, agebands.EXPOSURE_BANDS)
        assert band in agebands.EXPOSURE_BANDS, key
    for label in ("18-20", "21-24", "70-74", "75+"):
        parsed = agebands.parse_age_label(driver_risk_label(label))
        assert agebands.band_for(*parsed, agebands.EXPOSURE_BANDS) in agebands.EXPOSURE_BANDS


def driver_risk_label(band: str) -> str:
    from dgt_stats.io_exposure import _owner_label

    return _owner_label(band)


def test_sex_rates_leave_out_unlicensed_modes_and_add_up() -> None:
    rates = driver_risk.sex_age_rates().set_index(["scope", "band", "sex"])
    for scope in driver_risk.VEHICLE_SCOPES:
        for sex in driver_risk.SEX_LABELS:
            bands = rates.loc[(scope, list(driver_risk.SEX_BANDS), sex)]
            adult = rates.loc[(scope, driver_risk.ADULT_BAND, sex)]
            for column in ("drivers_involved", "driver_deaths", "licence_holder_years"):
                assert bands[column].sum() == adult[column]
    # Cars are a subset of motor vehicles, and cyclists are in neither.
    assert (
        rates.xs("car", level="scope").drivers_involved
        <= rates.xs("motor", level="scope").drivers_involved
    ).all()
    assert not driver_risk._in_scope(pd.Series(["Bicicleta", "VMP", "BICICLETA"]), "motor").any()
    assert driver_risk._in_scope(pd.Series(["Motocicleta", "Turismo sin remolque"]), "motor").all()


def test_sex_ratios_separate_crashing_from_dying() -> None:
    ratios = driver_risk.sex_ratios().set_index(["scope", "band", "measure"])
    involved = ratios.loc[("car", "18+", "involved_per_1000_licences")]
    fatality = ratios.loc[("car", "18+", "deaths_per_1000_involved")]
    deaths = ratios.loc[("car", "18+", "deaths_per_million_licences")]
    # Deaths per licence holder are involvement per licence holder times fatality once involved.
    assert deaths.ratio == pytest.approx(involved.ratio * fatality.ratio, rel=1e-9)
    assert fatality.low > 1 and involved.low > 1


def test_b_permit_holders_are_a_subset_of_the_census() -> None:
    permits = io_exposure.b_permit_holders_by_age(driver_risk.KM_YEAR)
    wide = permits.pivot(index="band", columns="sex", values="n_b_permit_holders").fillna(0)
    assert (wide.male + wide.female == wide.total).all()
    assert wide.loc["15-17", "total"] == 0  # no B permit below 18
    census = io_exposure.read_exposure("conductores_por_edad")
    census = census[(census.year == driver_risk.KM_YEAR) & (census.sex == "total")]
    census = census.set_index("band").n_drivers
    holders = wide.total.reindex(census.index)
    assert (holders <= census).all()
    # Pinned to NUM_PERMISOS_B of the 2024 text file, summed over provinces and bands.
    older = permits[(permits.sex == "total") & (permits.band == "75+")]
    assert older.n_b_permit_holders.sum() == 1_569_029
    with pytest.raises(ValueError):
        io_exposure.b_permit_holders_by_age(2014)
