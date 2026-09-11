"""SQLite-backed persistence for normalized readings.

Kept deliberately thin: one table, a handful of query shapes the API and
dashboard actually need. Anything fancier (retention, downsampling) can be
layered on later without touching the collector or adapters.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .interfaces import DeviceType, EnergyReading

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    device_type TEXT NOT NULL,
    ts TEXT NOT NULL,
    power_w REAL NOT NULL,
    energy_wh_cumulative REAL NOT NULL,
    voltage_v REAL NOT NULL,
    current_a REAL NOT NULL,
    extra_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_device_ts ON readings(device_id, ts);
"""


def _row_to_reading(row: sqlite3.Row) -> EnergyReading:
    return EnergyReading(
        device_id=row["device_id"],
        device_type=DeviceType(row["device_type"]),
        timestamp=datetime.fromisoformat(row["ts"]),
        power_w=row["power_w"],
        energy_wh_cumulative=row["energy_wh_cumulative"],
        voltage_v=row["voltage_v"],
        current_a=row["current_a"],
        extra=json.loads(row["extra_json"]),
    )


class ReadingStore:
    def __init__(self, path: str | Path = ":memory:"):
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def add(self, reading: EnergyReading) -> None:
        self._conn.execute(
            """INSERT INTO readings
               (device_id, device_type, ts, power_w, energy_wh_cumulative,
                voltage_v, current_a, extra_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                reading.device_id,
                reading.device_type.value,
                reading.timestamp.isoformat(),
                reading.power_w,
                reading.energy_wh_cumulative,
                reading.voltage_v,
                reading.current_a,
                json.dumps(reading.extra),
            ),
        )
        self._conn.commit()

    def add_many(self, readings: list[EnergyReading]) -> None:
        for r in readings:
            self._conn.execute(
                """INSERT INTO readings
                   (device_id, device_type, ts, power_w, energy_wh_cumulative,
                    voltage_v, current_a, extra_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r.device_id,
                    r.device_type.value,
                    r.timestamp.isoformat(),
                    r.power_w,
                    r.energy_wh_cumulative,
                    r.voltage_v,
                    r.current_a,
                    json.dumps(r.extra),
                ),
            )
        self._conn.commit()

    def devices(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT DISTINCT device_id, device_type FROM readings ORDER BY device_id"
        ).fetchall()
        return [{"device_id": r["device_id"], "device_type": r["device_type"]} for r in rows]

    def query(
        self,
        device_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 5000,
    ) -> list[EnergyReading]:
        clauses, params = [], []
        if device_id:
            clauses.append("device_id = ?")
            params.append(device_id)
        if start:
            clauses.append("ts >= ?")
            params.append(start.isoformat())
        if end:
            clauses.append("ts <= ?")
            params.append(end.isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM readings {where} ORDER BY ts ASC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [_row_to_reading(r) for r in rows]

    def latest_per_device(self) -> list[EnergyReading]:
        rows = self._conn.execute(
            """SELECT r.* FROM readings r
               INNER JOIN (
                   SELECT device_id, MAX(ts) AS max_ts FROM readings GROUP BY device_id
               ) latest
               ON r.device_id = latest.device_id AND r.ts = latest.max_ts"""
        ).fetchall()
        return [_row_to_reading(r) for r in rows]
