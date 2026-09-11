"""Sanity checks applied to every reading before it is stored.

Devices lie: a flaky sensor can report a stuck value, a spike, or a
timestamp far from "now". These bounds are deliberately generous
(household/small-commercial scale) so real hardware noise passes while
garbage does not.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .interfaces import DeviceType, EnergyReading

MAX_POWER_W = 50_000.0
MAX_VOLTAGE_V = 400.0
MAX_CURRENT_A = 250.0
MAX_CLOCK_SKEW = timedelta(minutes=5)


class ReadingValidationError(ValueError):
    pass


def validate_reading(reading: EnergyReading, *, now: datetime | None = None) -> None:
    now = now or datetime.utcnow()

    if abs(reading.power_w) > MAX_POWER_W:
        raise ReadingValidationError(
            f"{reading.device_id}: power_w={reading.power_w} exceeds {MAX_POWER_W}W"
        )
    if not (0.0 <= reading.voltage_v <= MAX_VOLTAGE_V):
        raise ReadingValidationError(
            f"{reading.device_id}: voltage_v={reading.voltage_v} out of range"
        )
    if not (0.0 <= reading.current_a <= MAX_CURRENT_A):
        raise ReadingValidationError(
            f"{reading.device_id}: current_a={reading.current_a} out of range"
        )
    if reading.energy_wh_cumulative < 0:
        raise ReadingValidationError(
            f"{reading.device_id}: energy_wh_cumulative cannot be negative"
        )
    if reading.timestamp > now + MAX_CLOCK_SKEW:
        raise ReadingValidationError(
            f"{reading.device_id}: timestamp {reading.timestamp} is in the future"
        )

    if reading.device_type in (DeviceType.SOLAR_INVERTER, DeviceType.EV_CHARGER):
        if reading.power_w < 0:
            raise ReadingValidationError(
                f"{reading.device_id}: {reading.device_type} power_w cannot be negative"
            )

    soc = reading.extra.get("state_of_charge_pct")
    if soc is not None and not (0.0 <= soc <= 100.0):
        raise ReadingValidationError(
            f"{reading.device_id}: state_of_charge_pct={soc} out of range"
        )
