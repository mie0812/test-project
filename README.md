# Energy Management System

An interface for integrating heterogeneous energy devices (meters, solar
inverters, batteries, EV chargers) into one data pipeline, verified against
simulated device data, with a live visualization dashboard.

## Architecture

```
Device Adapter (per model)  --read()-->  EnergyReading (normalized)
        |                                        |
        v                                        v
  DeviceAdapter contract              DataCollector.poll_once()
  (interfaces.py)                       - validates each reading
                                         - isolates failures per device
                                         - persists survivors
                                                 |
                                                 v
                                         ReadingStore (SQLite)
                                                 |
                                                 v
                                   FastAPI (/api/*)  -->  web/ dashboard
```

Every device model — real or simulated — is integrated by writing a
`DeviceAdapter` (`energy_management/interfaces.py`) that produces
`EnergyReading` objects. Nothing downstream (validation, storage, the API,
the dashboard) knows about vendor protocols; they only see this normalized
shape. That's what makes it possible to test the whole pipeline against
simulated data before any real hardware is connected, and to add a new
device model later without touching the collector, storage, or dashboard.

### Integrating a device model

Two integration patterns are included, covering the two shapes real
integrations usually take:

- **Live/simulated adapters** (`energy_management/adapters/{smart_meter,
  solar_inverter, battery, ev_charger}.py`) — a device you poll for a
  current value. Each is a thin subclass of `SimulatedDeviceAdapter`
  (`adapters/base.py`), which handles the `DeviceAdapter` contract and
  turns instantaneous power into a running energy-cumulative counter, the
  way a real meter's register would. A real version of one of these
  (Modbus, MQTT, a vendor SDK) plugs in at exactly the same seam — only
  `_power_and_extra(at)` changes.
- **File/export adapter** (`energy_management/adapters/csv_replay.py`) — a
  device that hands you its own CSV export with its own column names
  (`CsvReplayAdapter`'s `column_map`). Demonstrates adapting a foreign
  schema into `EnergyReading` without touching anything else.

### Verification before real hardware

- `energy_management/simulation.py` generates realistic synthetic curves
  (solar bell curve with daily cloudiness, a household load profile with
  morning/evening peaks, a battery charge/discharge cycle, an EV charging
  session) as pure functions of time, so a full day of data can be produced
  instantly and deterministically — no sleeping in real time, no flaky
  tests.
- `energy_management/validators.py` sanity-checks every reading (power/
  voltage/current bounds, non-decreasing cumulative energy, sign
  conventions per device type, clock skew) before it's stored.
- `energy_management/collector.py`'s `DataCollector` polls every adapter
  each tick; a device that fails to read or fails validation is marked
  unhealthy and skipped — it never blocks data collection from the others.
- `tests/` (pytest, 38 tests) exercises all of the above: adapter contract
  conformance, simulation invariants (solar is zero at night, battery SoC
  stays in [0,100], etc.), validator rejections, collector fault isolation,
  the CSV column-mapping adapter, and the API against seeded data.

### Visualization

`web/` is a small dependency-free dashboard (hand-drawn SVG charts, no
chart library) served as static files by the FastAPI app:

- Stat tiles: solar generation, total home load, grid import/export, battery
  state of charge.
- A multi-series power-over-time line chart (6h/24h range toggle) with a
  crosshair + tooltip on hover.
- An energy-by-device comparison for the selected range.
- A table view of the latest reading per device (accessible fallback to the
  chart).

It polls `/api/summary` and `/api/readings` every 15s, and supports light/
dark mode.

## Running it

```bash
pip install -r requirements.txt

# 1. Backfill history so the dashboard has something to show immediately
python3 -m scripts.generate_sample_csv   # one-time: creates the sample third-party CSV
python3 -m scripts.seed_history --hours 24

# 2. Serve the API + dashboard, appending live simulated readings every 15s
python3 -m scripts.serve --port 8000
```

Then open http://localhost:8000.

## Tests

```bash
python3 -m pytest
```

## Project layout

```
energy_management/
  interfaces.py       DeviceAdapter contract + EnergyReading
  simulation.py        Deterministic synthetic device curves
  validators.py         Reading sanity checks
  collector.py            Polls adapters, validates, persists
  storage.py                SQLite-backed reading store
  api.py                      FastAPI endpoints + static dashboard
  adapters/
    base.py            Shared plumbing for simulated adapters
    smart_meter.py, solar_inverter.py, battery.py, ev_charger.py
    csv_replay.py      Adapter for a third-party CSV export format
web/                    Dashboard (HTML/CSS/vanilla JS, hand-drawn SVG charts)
scripts/
  generate_sample_csv.py   Produces the demo third-party CSV
  seed_history.py            Backfills a SQLite DB with simulated history
  serve.py                     Runs the API + dashboard + live polling loop
tests/                  pytest suite (38 tests)
```
