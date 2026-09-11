"""Shared plumbing for adapters backed by a synthetic power-curve function.

A subclass only supplies `_power_and_extra(at)`; this base handles the
DeviceAdapter contract (connect/disconnect/health) and turns instantaneous
power into a running energy-cumulative counter the same way a real meter's
register would (integrated over successive reads, not recomputed from
scratch), so a real-hardware adapter can be swapped in later without the
collector or storage layer changing.
"""
from __future__ import annotations

from datetime import datetime

from ..interfaces import DeviceAdapter, DeviceType, EnergyReading

NOMINAL_VOLTAGE_V = 230.0


class SimulatedDeviceAdapter(DeviceAdapter):
    def __init__(self, device_id: str, model: str):
        self._device_id = device_id
        self._model = model
        self._connected = False
        self._cum_wh = 0.0
        self._last_ts: datetime | None = None

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def model(self) -> str:
        return self._model

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def seed_cumulative(self, at: datetime, wh: float) -> None:
        """Resume a running energy counter (e.g. after a process restart) instead
        of starting back at zero, the way a real meter's register would."""
        self._cum_wh = wh
        self._last_ts = at

    def _power_and_extra(self, at: datetime) -> tuple[float, dict]:
        raise NotImplementedError

    def read(self, at: datetime) -> EnergyReading:
        if not self._connected:
            raise RuntimeError(f"{self._device_id}: not connected")

        power_w, extra = self._power_and_extra(at)

        if self._last_ts is not None and at > self._last_ts:
            dt_hours = (at - self._last_ts).total_seconds() / 3600
            self._cum_wh += abs(power_w) * dt_hours
        self._last_ts = at

        current_a = abs(power_w) / NOMINAL_VOLTAGE_V if NOMINAL_VOLTAGE_V else 0.0

        return EnergyReading(
            device_id=self._device_id,
            device_type=self.device_type,
            timestamp=at,
            power_w=power_w,
            energy_wh_cumulative=round(self._cum_wh, 2),
            voltage_v=NOMINAL_VOLTAGE_V,
            current_a=round(current_a, 2),
            extra=extra,
        )
