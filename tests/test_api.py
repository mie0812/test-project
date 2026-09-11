from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from energy_management.adapters import SimulatedSmartMeterAdapter, SimulatedSolarInverterAdapter
from energy_management.api import create_app
from energy_management.collector import DataCollector
from energy_management.storage import ReadingStore


@pytest.fixture
def client():
    store = ReadingStore()
    adapters = [SimulatedSmartMeterAdapter(), SimulatedSolarInverterAdapter()]
    collector = DataCollector(adapters, store)
    collector.connect_all()

    start = datetime(2026, 6, 1, 0, 0)
    for i in range(60):  # one hour at 1-minute resolution
        collector.poll_once(start + timedelta(minutes=i))

    return TestClient(create_app(store))


def test_list_devices(client):
    resp = client.get("/api/devices")
    assert resp.status_code == 200
    ids = {d["device_id"] for d in resp.json()}
    assert ids == {"meter-1", "solar-1"}


def test_summary_returns_latest_per_device(client):
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    for row in body:
        assert "power_w" in row and "timestamp" in row


def test_readings_filters_by_device(client):
    resp = client.get("/api/readings", params={"device_id": "meter-1"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 60
    assert all(r["device_id"] == "meter-1" for r in body)


def test_readings_unknown_device_is_404(client):
    resp = client.get("/api/readings", params={"device_id": "nope"})
    assert resp.status_code == 404


def test_readings_respects_time_window(client):
    resp = client.get(
        "/api/readings",
        params={"device_id": "meter-1", "start": "2026-06-01T00:30:00", "limit": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 5
    assert body[0]["timestamp"] >= "2026-06-01T00:30:00"
