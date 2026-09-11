"""Runs the API + dashboard, continuously appending fresh simulated readings
so the charts visibly move like a live system.
"""
from __future__ import annotations

import argparse
import threading
import time
from datetime import datetime
from pathlib import Path

import uvicorn

from energy_management.adapters.base import SimulatedDeviceAdapter
from energy_management.api import create_app
from energy_management.collector import DataCollector
from energy_management.storage import ReadingStore
from scripts.seed_history import DB_PATH, build_adapters


def resume_cumulative_counters(adapters, store: ReadingStore) -> None:
    latest_by_device = {r.device_id: r for r in store.latest_per_device()}
    for adapter in adapters:
        latest = latest_by_device.get(adapter.device_id)
        if latest and isinstance(adapter, SimulatedDeviceAdapter):
            adapter.seed_cumulative(latest.timestamp, latest.energy_wh_cumulative)


def poll_loop(collector: DataCollector, interval_s: int, stop: threading.Event):
    while not stop.is_set():
        collector.poll_once(datetime.utcnow())
        stop.wait(interval_s)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--poll-interval", type=int, default=15)
    args = parser.parse_args()

    if not Path(args.db).exists():
        raise SystemExit(f"{args.db} not found — run scripts/seed_history.py first")

    store = ReadingStore(args.db)
    adapters = build_adapters()
    resume_cumulative_counters(adapters, store)
    collector = DataCollector(adapters, store)
    collector.connect_all()

    stop = threading.Event()
    thread = threading.Thread(target=poll_loop, args=(collector, args.poll_interval, stop), daemon=True)
    thread.start()

    app = create_app(store)
    try:
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    finally:
        stop.set()
        collector.disconnect_all()


if __name__ == "__main__":
    main()
