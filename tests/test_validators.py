from datetime import datetime, timedelta

import pytest

from energy_management.interfaces import DeviceType, EnergyReading
from energy_management.validators import ReadingValidationError, validate_reading

BASE_KWARGS = dict(
    device_id="dev-1",
    device_type=DeviceType.SMART_METER,
    timestamp=datetime(2026, 1, 1, 12, 0),
    power_w=100.0,
    energy_wh_cumulative=10.0,
    voltage_v=230.0,
    current_a=0.43,
    extra={},
)


def make_reading(**overrides):
    return EnergyReading(**{**BASE_KWARGS, **overrides})


def test_valid_reading_passes():
    validate_reading(make_reading())


def test_rejects_excessive_power():
    with pytest.raises(ReadingValidationError):
        validate_reading(make_reading(power_w=999_999))


def test_rejects_out_of_range_voltage():
    with pytest.raises(ReadingValidationError):
        validate_reading(make_reading(voltage_v=-5))


def test_rejects_negative_cumulative_energy():
    with pytest.raises(ReadingValidationError):
        validate_reading(make_reading(energy_wh_cumulative=-1))


def test_rejects_future_timestamp():
    now = datetime(2026, 1, 1, 12, 0)
    future = now + timedelta(hours=1)
    with pytest.raises(ReadingValidationError):
        validate_reading(make_reading(timestamp=future), now=now)


def test_solar_power_cannot_be_negative():
    with pytest.raises(ReadingValidationError):
        validate_reading(make_reading(device_type=DeviceType.SOLAR_INVERTER, power_w=-50))


def test_rejects_out_of_range_state_of_charge():
    with pytest.raises(ReadingValidationError):
        validate_reading(make_reading(extra={"state_of_charge_pct": 150}))
