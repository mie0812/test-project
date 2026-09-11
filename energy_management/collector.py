"""Polls every registered adapter once per tick, validates, and persists.

One misbehaving device must not stop data collection for the others: a
failed read or a failed validation is recorded against that device's
health and skipped, not raised out of poll_once().
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from .interfaces import DeviceAdapter, EnergyReading
from .storage import ReadingStore
from .validators import validate_reading

logger = logging.getLogger(__name__)


@dataclass
class DeviceHealth:
    healthy: bool = True
    consecutive_failures: int = 0
    last_error: str | None = None
    last_success_ts: datetime | None = None


class DataCollector:
    def __init__(self, adapters: list[DeviceAdapter], store: ReadingStore):
        self._adapters = {a.device_id: a for a in adapters}
        self._store = store
        self._health: dict[str, DeviceHealth] = {
            a.device_id: DeviceHealth() for a in adapters
        }

    def connect_all(self) -> None:
        for adapter in self._adapters.values():
            adapter.connect()

    def disconnect_all(self) -> None:
        for adapter in self._adapters.values():
            adapter.disconnect()

    def health(self) -> dict[str, DeviceHealth]:
        return dict(self._health)

    def poll_once(self, at: datetime) -> list[EnergyReading]:
        collected: list[EnergyReading] = []
        for device_id, adapter in self._adapters.items():
            health = self._health[device_id]
            try:
                reading = adapter.read(at)
                validate_reading(reading, now=at)
            except Exception as exc:  # noqa: BLE001
                health.healthy = False
                health.consecutive_failures += 1
                health.last_error = str(exc)
                logger.warning("skipping reading from %s: %s", device_id, exc)
                continue

            health.healthy = True
            health.consecutive_failures = 0
            health.last_error = None
            health.last_success_ts = at
            collected.append(reading)

        if collected:
            self._store.add_many(collected)
        return collected
