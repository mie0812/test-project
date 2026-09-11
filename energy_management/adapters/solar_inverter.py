from __future__ import annotations

from datetime import datetime

from ..interfaces import DeviceType
from ..simulation import solar_generation_w
from .base import SimulatedDeviceAdapter


class SimulatedSolarInverterAdapter(SimulatedDeviceAdapter):
    """Represents a rooftop PV inverter model, e.g. 'sim:solar-v2'."""

    def __init__(self, device_id: str = "solar-1", capacity_w: float = 4000.0, seed: int = 0):
        super().__init__(device_id, model="sim:solar-v2")
        self._capacity_w = capacity_w
        self._seed = seed

    @property
    def device_type(self) -> DeviceType:
        return DeviceType.SOLAR_INVERTER

    def _power_and_extra(self, at: datetime) -> tuple[float, dict]:
        power = solar_generation_w(at, capacity_w=self._capacity_w, seed=self._seed)
        return power, {"capacity_w": self._capacity_w}
