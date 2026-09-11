from __future__ import annotations

from datetime import datetime

from ..interfaces import DeviceType
from ..simulation import household_load_w
from .base import SimulatedDeviceAdapter


class SimulatedSmartMeterAdapter(SimulatedDeviceAdapter):
    """Represents a household grid meter model, e.g. 'sim:meter-v1'."""

    def __init__(self, device_id: str = "meter-1", seed: int = 1):
        super().__init__(device_id, model="sim:meter-v1")
        self._seed = seed

    @property
    def device_type(self) -> DeviceType:
        return DeviceType.SMART_METER

    def _power_and_extra(self, at: datetime) -> tuple[float, dict]:
        return household_load_w(at, seed=self._seed), {}
