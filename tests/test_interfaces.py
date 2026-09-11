from datetime import datetime, timedelta

import pytest

from energy_management.adapters import (
    SimulatedBatteryAdapter,
    SimulatedEvChargerAdapter,
    SimulatedSmartMeterAdapter,
    SimulatedSolarInverterAdapter,
)
from energy_management.interfaces import DeviceAdapter, EnergyReading
from energy_management.validators import validate_reading

ALL_ADAPTERS = [
    SimulatedSmartMeterAdapter,
    SimulatedSolarInverterAdapter,
    SimulatedBatteryAdapter,
    SimulatedEvChargerAdapter,
]


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_adapter_conforms_to_interface(adapter_cls):
    adapter = adapter_cls()
    assert isinstance(adapter, DeviceAdapter)
    assert adapter.device_id
    assert adapter.model
    assert adapter.device_type is not None


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_read_requires_connection(adapter_cls):
    adapter = adapter_cls()
    with pytest.raises(RuntimeError):
        adapter.read(at=datetime(2026, 1, 1))


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_full_day_of_readings_is_valid(adapter_cls):
    adapter = adapter_cls()
    adapter.connect()
    ts = datetime(2026, 6, 1, 0, 0)
    for _ in range(24 * 4):  # every 15 minutes for a day
        reading = adapter.read(ts)
        assert isinstance(reading, EnergyReading)
        validate_reading(reading, now=ts + timedelta(minutes=1))
        ts += timedelta(minutes=15)
    adapter.disconnect()


def test_cumulative_energy_is_monotonic_non_decreasing():
    adapter = SimulatedSolarInverterAdapter()
    adapter.connect()
    ts = datetime(2026, 6, 1, 8, 0)
    prev = -1.0
    for _ in range(20):
        reading = adapter.read(ts)
        assert reading.energy_wh_cumulative >= prev
        prev = reading.energy_wh_cumulative
        ts += timedelta(minutes=5)
