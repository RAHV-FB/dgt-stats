import pandas as pd
import pytest

from dgt_stats import agebands, driver_risk, io_exposure, io_tables

pytestmark = pytest.mark.skipif(
    not (
        io_exposure.interim_path("km_edad_propietario_2024").exists()
        and io_tables.interim_path("tables_driver_victims").exists()
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
    # The finding: involvement per km is flat across the older bands, fatality is not.
    assert rates.loc["75+", "involved_per_bn_km"] < 1.5 * rates.loc["35-54", "involved_per_bn_km"]
    assert (
        rates.loc["75+", "deaths_per_1000_involved"]
        > 3 * rates.loc["35-54", "deaths_per_1000_involved"]
    )


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
    # Giving them to working-age bands raises the older ratio, so the published one is the
    # conservative end of the bracket.
    assert working > published


def test_denominator_contrast_moves_the_answer_without_moving_the_numerator() -> None:
    contrast = driver_risk.denominator_contrast()
    assert set(contrast.band) == set(driver_risk.CONTRAST_BANDS)
    deaths = contrast.pivot(index="band", columns="denominator", values="driver_deaths")
    assert deaths.nunique(axis=1).eq(1).all()  # the same deaths in every panel
    ratios = contrast[contrast.band == "75+"].set_index("denominator").ratio
    assert ratios["residents"] < ratios["licence_holders"] < ratios["kilometres"]
    assert contrast[contrast.band == driver_risk.REFERENCE_BAND].ratio.eq(1.0).all()


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


def test_travel_bracket_divides_by_the_2006_trip_ratio() -> None:
    travel = driver_risk.sex_travel_bracket()
    assert list(travel.band) == ["15-29", "30-39", "40-49", "50-64", "65+"]
    assert (travel.trip_ratio_2006 > 1).all()  # men made more car-or-motorcycle trips
    per_trip = travel.involved_ratio_per_resident / travel.trip_ratio_2006
    assert per_trip.to_numpy() == pytest.approx(travel.involved_ratio_per_trip.to_numpy())
