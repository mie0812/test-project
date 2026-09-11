import csv
from datetime import datetime

from energy_management.adapters.csv_replay import CsvReplayAdapter
from energy_management.interfaces import DeviceType


def write_vendor_csv(path):
    rows = [
        {"iso_time": "2026-01-01T00:00:00", "W": 100.0, "V": 230.0, "A": 0.43, "Wh_total": 0.0},
        {"iso_time": "2026-01-01T00:15:00", "W": 120.0, "V": 230.0, "A": 0.52, "Wh_total": 27.5},
        {"iso_time": "2026-01-01T00:30:00", "W": 90.0, "V": 231.0, "A": 0.39, "Wh_total": 57.0},
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["iso_time", "W", "V", "A", "Wh_total"])
        writer.writeheader()
        writer.writerows(rows)


def test_csv_replay_maps_vendor_columns(tmp_path):
    csv_path = tmp_path / "vendor.csv"
    write_vendor_csv(csv_path)

    adapter = CsvReplayAdapter(
        device_id="vendor-meter",
        device_type=DeviceType.SMART_METER,
        csv_path=csv_path,
        column_map={
            "timestamp": "iso_time",
            "power_w": "W",
            "voltage_v": "V",
            "current_a": "A",
            "energy_wh_cumulative": "Wh_total",
        },
    )
    adapter.connect()

    reading = adapter.read(datetime(2026, 1, 1, 0, 15))
    assert reading.power_w == 120.0
    assert reading.energy_wh_cumulative == 27.5
    assert reading.device_id == "vendor-meter"
    assert reading.device_type == DeviceType.SMART_METER


def test_csv_replay_clamps_to_nearest_earlier_row(tmp_path):
    csv_path = tmp_path / "vendor.csv"
    write_vendor_csv(csv_path)

    adapter = CsvReplayAdapter(
        device_id="vendor-meter",
        device_type=DeviceType.SMART_METER,
        csv_path=csv_path,
        column_map={
            "timestamp": "iso_time",
            "power_w": "W",
            "voltage_v": "V",
            "current_a": "A",
            "energy_wh_cumulative": "Wh_total",
        },
    )
    adapter.connect()

    # far beyond the last row: clamp to the last known row rather than raising
    reading = adapter.read(datetime(2026, 1, 2, 0, 0))
    assert reading.power_w == 90.0
