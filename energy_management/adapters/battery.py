from __future__ import annotations

from datetime import datetime

from ..interfaces import DeviceType
from ..simulation import battery_state_w
from .base import SimulatedDeviceAdapter


class SimulatedBatteryAdapter(SimulatedDeviceAdapter):
    """Represents a home battery storage model, e.g. 'sim:battery-v1'."""

    def __init__(self, device_id: str = "battery-1", capacity_wh: float = 10_000.0, seed: int = 2):
        super().__init__(device_id, model="sim:battery-v1")
        self._capacity_wh = capacity_wh
        self._seed = seed

    @property
    def device_type(self) -> DeviceType:
        return DeviceType.BATTERY

    def _power_and_extra(self, at: datetime) -> tuple[float, dict]:
        power, soc = battery_state_w(at, capacity_wh=self._capacity_wh, seed=self._seed)
        return power, {"state_of_charge_pct": soc, "capacity_wh": self._capacity_wh}
