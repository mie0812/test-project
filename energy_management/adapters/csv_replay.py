"""Integrates a device model that exports its own CSV format rather than
exposing a live API — a common shape for third-party meters/loggers.

Different vendors name their columns differently, so the column mapping is
configurable rather than hardcoded; only the DeviceAdapter contract
(read() -> EnergyReading) is fixed. This is the pattern a real Modbus/MQTT/
vendor-SDK adapter would follow too: adapt on the way in, normalize out.
"""
from __future__ import annotations

import bisect
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..interfaces import DeviceAdapter, DeviceType, EnergyReading

DEFAULT_COLUMNS = {
    "timestamp": "timestamp",
    "power_w": "power_w",
    "voltage_v": "voltage_v",
    "current_a": "current_a",
    "energy_wh_cumulative": "energy_wh_cumulative",
}


@dataclass(frozen=True)
class _Row:
    timestamp: datetime
    power_w: float
    voltage_v: float
    current_a: float
    energy_wh_cumulative: float


class CsvReplayAdapter(DeviceAdapter):
    def __init__(
        self,
        device_id: str,
        device_type: DeviceType,
        csv_path: str | Path,
        model: str = "thirdparty:csv-export-v1",
        column_map: dict[str, str] | None = None,
    ):
        self._device_id = device_id
        self._device_type = device_type
        self._csv_path = Path(csv_path)
        self._model = model
        self._columns = {**DEFAULT_COLUMNS, **(column_map or {})}
        self._rows: list[_Row] = []
        self._timestamps: list[datetime] = []

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def device_type(self) -> DeviceType:
        return self._device_type

    @property
    def model(self) -> str:
        return self._model

    def connect(self) -> None:
        rows = []
        with self._csv_path.open(newline="") as f:
            for raw in csv.DictReader(f):
                rows.append(
                    _Row(
                        timestamp=datetime.fromisoformat(raw[self._columns["timestamp"]]),
                        power_w=float(raw[self._columns["power_w"]]),
                        voltage_v=float(raw[self._columns["voltage_v"]]),
                        current_a=float(raw[self._columns["current_a"]]),
                        energy_wh_cumulative=float(raw[self._columns["energy_wh_cumulative"]]),
                    )
                )
        rows.sort(key=lambda r: r.timestamp)
        if not rows:
            raise ValueError(f"{self._csv_path}: no rows found")
        self._rows = rows
        self._timestamps = [r.timestamp for r in rows]

    def disconnect(self) -> None:
        self._rows = []
        self._timestamps = []

    def read(self, at: datetime) -> EnergyReading:
        if not self._rows:
            raise RuntimeError(f"{self._device_id}: not connected")

        idx = bisect.bisect_right(self._timestamps, at) - 1
        idx = max(0, min(idx, len(self._rows) - 1))
        row = self._rows[idx]

        return EnergyReading(
            device_id=self._device_id,
            device_type=self._device_type,
            timestamp=at,
            power_w=row.power_w,
            energy_wh_cumulative=row.energy_wh_cumulative,
            voltage_v=row.voltage_v,
            current_a=row.current_a,
            extra={"source_row_timestamp": row.timestamp.isoformat()},
        )
