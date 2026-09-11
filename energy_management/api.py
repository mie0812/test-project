"""REST API serving stored readings to the dashboard (and any other client)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .storage import ReadingStore

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app(store: ReadingStore) -> FastAPI:
    app = FastAPI(title="Energy Management API")

    @app.get("/api/devices")
    def list_devices():
        return store.devices()

    @app.get("/api/summary")
    def summary():
        latest = store.latest_per_device()
        out = []
        for r in latest:
            out.append(
                {
                    "device_id": r.device_id,
                    "device_type": r.device_type.value,
                    "timestamp": r.timestamp.isoformat(),
                    "power_w": r.power_w,
                    "energy_wh_cumulative": r.energy_wh_cumulative,
                    "extra": r.extra,
                }
            )
        return out

    @app.get("/api/readings")
    def readings(
        device_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = Query(default=2000, le=20000),
    ):
        rows = store.query(device_id=device_id, start=start, end=end, limit=limit)
        if device_id and not rows:
            raise HTTPException(status_code=404, detail=f"no data for device '{device_id}'")
        return [
            {
                "device_id": r.device_id,
                "device_type": r.device_type.value,
                "timestamp": r.timestamp.isoformat(),
                "power_w": r.power_w,
                "energy_wh_cumulative": r.energy_wh_cumulative,
                "voltage_v": r.voltage_v,
                "current_a": r.current_a,
                "extra": r.extra,
            }
            for r in rows
        ]

    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

    return app
