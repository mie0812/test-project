from datetime import datetime

from energy_management.adapters import SimulatedSmartMeterAdapter, SimulatedSolarInverterAdapter
from energy_management.collector import DataCollector
from energy_management.interfaces import DeviceAdapter, DeviceType, EnergyReading
from energy_management.storage import ReadingStore


class BrokenAdapter(DeviceAdapter):
    """Always fails, to prove one bad device can't take down the collector."""

    device_id_value = "broken-1"

    @property
    def device_id(self):
        return self.device_id_value

    @property
    def device_type(self):
        return DeviceType.SMART_METER

    @property
    def model(self):
        return "broken:v1"

    def connect(self):
        pass

    def disconnect(self):
        pass

    def read(self, at):
        raise ConnectionError("simulated hardware fault")


def test_poll_once_stores_valid_readings():
    store = ReadingStore()
    adapters = [SimulatedSmartMeterAdapter(), SimulatedSolarInverterAdapter()]
    collector = DataCollector(adapters, store)
    collector.connect_all()

    collected = collector.poll_once(datetime(2026, 6, 1, 12, 0))

    assert len(collected) == 2
    assert len(store.query()) == 2


def test_broken_adapter_does_not_block_others():
    store = ReadingStore()
    adapters = [SimulatedSmartMeterAdapter(), BrokenAdapter()]
    collector = DataCollector(adapters, store)
    collector.connect_all()

    collected = collector.poll_once(datetime(2026, 6, 1, 12, 0))

    assert len(collected) == 1
    assert collected[0].device_id == "meter-1"

    health = collector.health()
    assert health["broken-1"].healthy is False
    assert health["broken-1"].consecutive_failures == 1
    assert health["meter-1"].healthy is True


def test_health_recovers_after_success():
    store = ReadingStore()
    meter = SimulatedSmartMeterAdapter()
    collector = DataCollector([meter], store)
    collector.connect_all()

    collector.poll_once(datetime(2026, 6, 1, 12, 0))
    assert collector.health()["meter-1"].healthy is True
