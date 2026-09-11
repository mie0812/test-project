"""Backfills the last N hours of simulated + replayed device data into a
SQLite file, so the dashboard has a history to draw on the moment it opens.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from energy_management.adapters import (
    CsvReplayAdapter,
    SimulatedBatteryAdapter,
    SimulatedEvChargerAdapter,
    SimulatedSmartMeterAdapter,
    SimulatedSolarInverterAdapter,
)
from energy_management.collector import DataCollector
from energy_management.interfaces import DeviceType
from energy_management.storage import ReadingStore

DB_PATH = Path(__file__).resolve().parent.parent / "energy_data.db"
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_secondary_meter.csv"


def build_adapters():
    adapters = [
        SimulatedSmartMeterAdapter(device_id="meter-main"),
        SimulatedSolarInverterAdapter(device_id="solar-roof"),
        SimulatedBatteryAdapter(device_id="battery-garage"),
        SimulatedEvChargerAdapter(device_id="ev-charger-driveway"),
    ]
    if CSV_PATH.exists():
        adapters.append(
            CsvReplayAdapter(
                device_id="meter-subpanel",
                device_type=DeviceType.SMART_METER,
                csv_path=CSV_PATH,
                model="thirdparty:vendorx-csv",
                column_map={
                    "timestamp": "iso_time",
                    "power_w": "W",
                    "voltage_v": "V",
                    "current_a": "A",
                    "energy_wh_cumulative": "Wh_total",
                },
            )
        )
    return adapters


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--resolution-min", type=int, default=1)
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    store = ReadingStore(args.db)
    collector = DataCollector(build_adapters(), store)
    collector.connect_all()

    now = datetime.utcnow()
    start = now - timedelta(hours=args.hours)
    step = timedelta(minutes=args.resolution_min)

    ts, count = start, 0
    while ts <= now:
        collector.poll_once(ts)
        ts += step
        count += 1

    collector.disconnect_all()
    print(f"seeded {count} ticks from {start} to {now} into {args.db}")
    for device_id, health in collector.health().items():
        status = "ok" if health.healthy else f"UNHEALTHY ({health.last_error})"
        print(f"  {device_id}: {status}")


if __name__ == "__main__":
    main()
