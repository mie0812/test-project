from __future__ import annotations

from datetime import datetime

from ..interfaces import DeviceType
from ..simulation import ev_charger_w
from .base import SimulatedDeviceAdapter


class SimulatedEvChargerAdapter(SimulatedDeviceAdapter):
    """Represents an EV charge point model, e.g. 'sim:evse-v1'."""

    def __init__(self, device_id: str = "ev-charger-1", seed: int = 3):
        super().__init__(device_id, model="sim:evse-v1")
        self._seed = seed

    @property
    def device_type(self) -> DeviceType:
        return DeviceType.EV_CHARGER

    def _power_and_extra(self, at: datetime) -> tuple[float, dict]:
        power, plugged_in = ev_charger_w(at, seed=self._seed)
        return power, {"plugged_in": plugged_in}
