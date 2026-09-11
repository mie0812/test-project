from datetime import datetime

from energy_management.simulation import (
    battery_state_w,
    ev_charger_w,
    household_load_w,
    solar_generation_w,
)


def test_solar_is_zero_at_night():
    assert solar_generation_w(datetime(2026, 6, 1, 2, 0)) == 0.0
    assert solar_generation_w(datetime(2026, 6, 1, 23, 0)) == 0.0


def test_solar_is_positive_at_midday():
    assert solar_generation_w(datetime(2026, 6, 1, 12, 30)) > 0.0


def test_solar_never_exceeds_capacity():
    capacity = 5000.0
    for hour in range(24):
        power = solar_generation_w(datetime(2026, 6, 1, hour, 0), capacity_w=capacity)
        assert 0.0 <= power <= capacity


def test_household_load_is_always_positive():
    for hour in range(24):
        assert household_load_w(datetime(2026, 6, 1, hour, 0)) > 0.0


def test_battery_soc_stays_within_bounds():
    for hour in range(24):
        for minute in (0, 15, 30, 45):
            _, soc = battery_state_w(datetime(2026, 6, 1, hour, minute))
            assert 0.0 <= soc <= 100.0


def test_ev_charger_is_off_outside_session():
    power, plugged_in = ev_charger_w(datetime(2026, 6, 1, 10, 0))
    assert power == 0.0
    assert plugged_in is False


def test_ev_charger_draws_power_during_session():
    power, plugged_in = ev_charger_w(datetime(2026, 6, 1, 19, 0))
    assert plugged_in is True
    assert power > 0.0


def test_simulation_is_deterministic_for_same_timestamp():
    ts = datetime(2026, 6, 1, 12, 0)
    assert solar_generation_w(ts) == solar_generation_w(ts)
    assert household_load_w(ts) == household_load_w(ts)
    assert battery_state_w(ts) == battery_state_w(ts)
    assert ev_charger_w(ts) == ev_charger_w(ts)
