"""Core contract every device integration must implement.

Any device model (a real meter, inverter, or a simulator) is integrated by
writing a DeviceAdapter and exchanging data as EnergyReading. Nothing else
in the system (collector, storage, API, dashboard) knows about vendor
protocols — they only ever see this normalized shape.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DeviceType(str, Enum):
    SMART_METER = "smart_meter"
    SOLAR_INVERTER = "solar_inverter"
    BATTERY = "battery"
    EV_CHARGER = "ev_charger"


@dataclass(frozen=True)
class EnergyReading:
    """One normalized sample from a device, regardless of make/model.

    Sign convention for power_w (device_type determines what "positive"
    physically means, since a meter drawing power and a battery
    discharging power are both "positive" from the grid's point of view):
      - SMART_METER:     +import from grid,  -export to grid
      - SOLAR_INVERTER:  +generation (always >= 0)
      - BATTERY:         +discharging (supplying power), -charging
      - EV_CHARGER:      +power draw (always >= 0)
    """

    device_id: str
    device_type: DeviceType
    timestamp: datetime
    power_w: float
    energy_wh_cumulative: float
    voltage_v: float
    current_a: float
    extra: dict = field(default_factory=dict)


class DeviceAdapter(abc.ABC):
    """Common integration point for a single physical (or simulated) device."""

    @property
    @abc.abstractmethod
    def device_id(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def device_type(self) -> DeviceType:
        ...

    @property
    @abc.abstractmethod
    def model(self) -> str:
        """Vendor/model string, e.g. 'Acme SM-100' or 'sim:solar-v1'."""

    @abc.abstractmethod
    def connect(self) -> None:
        """Establish whatever link the device needs (network, serial, file)."""

    @abc.abstractmethod
    def disconnect(self) -> None:
        ...

    @abc.abstractmethod
    def read(self, at: datetime) -> EnergyReading:
        """Return the current (or, for replay/simulation, the reading as-of `at`)."""

    def health_check(self) -> bool:
        """Cheap liveness probe. Default: a read that doesn't raise counts as healthy."""
        try:
            self.read(at=datetime.utcnow())
            return True
        except Exception:
            return False
