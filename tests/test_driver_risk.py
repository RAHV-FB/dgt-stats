import pandas as pd
import pytest

from dgt_stats import agebands, driver_risk, io_exposure, io_tables

pytestmark = pytest.mark.skipif(
    not (
        io_exposure.staging_path("km_edad_propietario_2024").exists()
        and io_tables.staging_path("tables_driver_victims").exists()
    ),
    reason="run `python scripts/ingest.py tables exposure` first",
)


def test_car_kilometres_cover_the_fleet_and_keep_company_cars_apart() -> None:
    km = driver_risk.car_kilometres().set_index("band")
    assert driver_risk.COMPANY_BAND in km.index
    bands = [band for band in km.index if band != driver_risk.COMPANY_BAND]
    assert bands == [band for band in agebands.EXPOSURE_BANDS if band in km.index]
    assert "15-17" not in bands  # nobody under 18 owns a car in DGT's table
    assert km.share_of_km.sum() == pytest.approx(1.0)
    # Company cars are a material share, which is why the page has a sensitivity for them.
    assert 0.05 < float(km.loc[driver_risk.COMPANY_BAND, "share_of_km"]) < 0.25
    published = io_exposure.read_exposure("km_medios_tipo_2024").set_index("vehicle_group")
    assert km.total_km.sum() == pytest.approx(float(published.loc["car", "total_km"]), rel=0.005)
    assert km.n_vehicles.sum() == pytest.approx(
        float(published.loc["car", "n_vehicles"]), rel=0.005
    )
    # Distance per car falls with the owner's age, which is the whole reason the denominator
    # matters; it is asserted rather than assumed.
    per_car = km.loc[bands].total_km / km.loc[bands].n_vehicles
    assert per_car["35-54"] > per_car["55-64"] > per_car["65-74"] > per_car["75+"]


def test_car_driver_counts_keep_unknown_age_visible() -> None:
    counts = driver_risk.car_driver_counts().set_index("band")
    assert agebands.UNKNOWN in counts.index
    compared = counts.loc[list(driver_risk.COMPARED_BANDS)]
    assert counts.drivers_involved.sum() > compared.drivers_involved.sum()
    # The car rows of table 4.1.1 reproduce the yearbook's car-driver deaths for the year.
    series = io_tables.read_table("series_road_users")
    published = series[
        (series.year == driver_risk.KM_YEAR)
        & (series.population == "drivers")
        & (series.severity == "deaths_30d")
        & (series.zone == "all")
        & (series.vehicle_type == "Turismos")
    ].value.iloc[0]
    assert counts.driver_deaths.sum() == published


def test_km_rates_multiply_out_and_carry_intervals() -> None:
    rates = driver_risk.km_rates().set_index("band")
    assert list(rates.index) == list(driver_risk.COMPARED_BANDS)
    assert (rates.involved_per_bn_km > 0).all() and (rates.deaths_per_bn_km > 0).all()
    # deaths per km is involvement per km times fatality given involvement, by construction.
    product = rates.involved_per_bn_km * rates.deaths_per_1000_involved / 1000
    assert product.values == pytest.approx(rates.deaths_per_bn_km.values, rel=1e-9)
    for name in ("involved_per_bn_km", "deaths_per_bn_km", "deaths_per_1000_involved"):
        assert (rates[f"{name}_low"] <= rates[name]).all()
        assert (rates[name] <= rates[f"{name}_high"]).all()
    # Pinned to the published inputs: 2024 car rows of tables 4.2 and 4.1.1 and owner-age km.
    assert rates.loc["75+", "drivers_involved"] == 4_456
    assert rates.loc["75+", "driver_deaths"] == 71
    assert rates.loc["35-54", "billion_km"] == pytest.approx(120.302993, rel=1e-6)
    # Every per-km label says whose kilometres they are.
    for measure in driver_risk.KM_MEASURES:
        assert "registered to owners of this age" in driver_risk.RATE_LABELS[measure]


def test_ratios_are_one_at_the_baseline_and_ordered_by_age() -> None:
    ratios = driver_risk.km_rate_ratios()
    assert set(ratios.measure) == set(driver_risk.RATE_DEFINITIONS)
    reference = ratios[ratios.is_reference]
    assert len(reference) == len(driver_risk.RATE_DEFINITIONS)
    assert reference.ratio.eq(1.0).all()
    fatality = ratios[ratios.measure == "deaths_per_1000_involved"].set_index("band")
    assert (
        fatality.loc["35-54", "ratio"]
        < fatality.loc["55-64", "ratio"]
        < fatality.loc["65-74", "ratio"]
        < fatality.loc["75+", "ratio"]
    )
    assert (fatality.low <= fatality.ratio).all() and (fatality.ratio <= fatality.high).all()


def test_company_kilometres_bracket_the_comparison_in_a_known_direction() -> None:
    company = driver_risk.company_km_sensitivity().set_index(["allocation", "band"])
    assert set(company.index.get_level_values("allocation")) == {
        "excluded",
        "to_working_age",
        "to_all_bands",
    }
    published = float(company.loc[("excluded", "75+"), "ratio_to_reference"])
    working = float(company.loc[("to_working_age", "75+"), "ratio_to_reference"])
    spread = float(company.loc[("to_all_bands", "75+"), "ratio_to_reference"])
    # Spreading company kilometres over every band cannot change a ratio between two bands.
    assert spread == pytest.approx(published)
    # The working-age scenario adds kilometres to the 35-54 reference and none to 75+, so the
    # 75+ ratio rises by arithmetic; it says nothing about who drives company cars.
    assert working > published
    labels = company.allocation_label.groupby(level="allocation").first()
    assert labels["to_working_age"].startswith("Scenario")
    assert labels["to_all_bands"].startswith("Scenario")


def test_denominator_contrast_moves_the_answer_without_moving_the_numerator() -> None:
    contrast = driver_risk.denominator_contrast()
    assert set(contrast.band) == set(driver_risk.CONTRAST_BANDS)
    deaths = contrast.pivot(index="band", columns="denominator", values="driver_deaths")
    assert deaths.nunique(axis=1).eq(1).all()  # the same deaths in every panel
    assert set(contrast.denominator) == set(driver_risk.CONTRAST_LABELS)
    assert contrast[contrast.band == driver_risk.REFERENCE_BAND].ratio.eq(1.0).all()
    # The permit panel divides by B-permit holders, the car licence, not by every licence holder.
    permits = contrast[contrast.denominator == "b_permit_holders"].set_index("band").exposure
    assert permits.equals(driver_risk.b_permit_holders().reindex(permits.index))
    assert (permits < driver_risk.licence_holders().reindex(permits.index)).all()


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


def test_rates_are_written_to_the_result_tables() -> None:
    from dgt_stats.paths import TABLES_DIR

    path = TABLES_DIR / "q7_km_rates.csv"
    if not path.exists():
        pytest.skip("run `python scripts/analyse.py tables` first")
    published = pd.read_csv(path)
    assert list(published.band) == list(driver_risk.COMPARED_BANDS)


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
    assert driver_risk.b_permit_holders().loc["75+"] == 1_569_029
    with pytest.raises(ValueError):
        io_exposure.b_permit_holders_by_age(2014)


def test_owner_age_check_gives_every_band_and_measure_both_readings() -> None:
    check = driver_risk.owner_age_check().set_index("band")
    assert list(check.index) == list(driver_risk.COMPARED_BANDS)
    young, base = check.loc[driver_risk.TRANSFER_BAND], check.loc[driver_risk.REFERENCE_BAND]
    # The transfer equalises kilometres per B-permit holder in the two bands and moves no other.
    per_holder = check.billion_km_transfer / check.b_permit_holders
    assert per_holder[driver_risk.TRANSFER_BAND] == pytest.approx(
        per_holder[driver_risk.REFERENCE_BAND]
    )
    assert young.transfer_bn_km == pytest.approx(-base.transfer_bn_km)
    assert check.transfer_bn_km.sum() == pytest.approx(0.0, abs=1e-9)
    assert (
        check.drop([driver_risk.TRANSFER_BAND, driver_risk.REFERENCE_BAND]).transfer_bn_km == 0
    ).all()
    published = driver_risk.km_rate_ratios().set_index(["measure", "band"])
    for measure in driver_risk.RATE_DEFINITIONS:
        for band in check.index:
            row = published.loc[(measure, band)]
            assert check.loc[band, f"{measure}_ratio"] == pytest.approx(row.ratio)
            assert check.loc[band, f"{measure}_low"] == pytest.approx(row.low)
        assert check[f"{measure}_ratio"][driver_risk.REFERENCE_BAND] == 1.0
    for measure in driver_risk.KM_MEASURES:
        low, high = check[f"{measure}_range_low"], check[f"{measure}_range_high"]
        assert (low <= high).all()
        assert (low == check[[f"{measure}_ratio", f"{measure}_ratio_transfer"]].min(axis=1)).all()
        # Adding kilometres to 18-34 and taking them from the reference lowers every other
        # band's ratio to the reference.
        assert (check[f"{measure}_ratio_transfer"] <= check[f"{measure}_ratio"] + 1e-12).all()
    # Deaths per driver involved need no kilometres and have no transfer reading.
    assert "deaths_per_1000_involved_ratio_transfer" not in check.columns
    # 75+ against 65-74 is the same under both readings: neither band's kilometres move.
    for measure in driver_risk.KM_MEASURES:
        published_ratio = (
            check.loc["75+", f"{measure}_ratio"] / check.loc["65-74", f"{measure}_ratio"]
        )
        transfer_ratio = (
            check.loc["75+", f"{measure}_ratio_transfer"]
            / check.loc["65-74", f"{measure}_ratio_transfer"]
        )
        assert transfer_ratio == pytest.approx(published_ratio)
