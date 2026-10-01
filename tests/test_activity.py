from dgt_stats import io_activity


def test_the_survey_register_parses() -> None:
    # No page reads the register any more; it is kept, and checked, as the record of what was
    # searched before DGT's kilometres by owner age replaced the survey-based denominator.
    register = io_activity.read_activity_register()
    assert {"source", "wave", "share", "n"} <= set(register.columns)
    assert {2018, 2023} <= set(register.wave)


def test_movilia_trips_by_mode_sex_and_age() -> None:
    trips = io_activity.read_movilia_trips()
    assert set(trips.day_type.unique()) == {"weekday", "weekend"}
    assert set(trips.sex.unique()) == {"total", "male", "female"}
    assert set(trips.transport_mode.unique()) == set(io_activity.MOVILIA_MODES)
    weekday = trips[(trips.day_type == "weekday") & (trips.sex == "total")]
    total = weekday[(weekday.band == "all") & (weekday.transport_mode == "all_modes")]
    assert abs(total.trips_thousands.iloc[0] - 123_364.79) < 0.01
    older = weekday[(weekday.band == "65+") & (weekday.transport_mode == "car_or_motorcycle")]
    assert abs(older.trips_thousands.iloc[0] - 2_422.13) < 0.01
