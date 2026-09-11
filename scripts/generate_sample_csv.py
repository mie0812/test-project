"""Produces data/sample_secondary_meter.csv: a stand-in for a real device's
own CSV export, using different column names than our internal schema, to
exercise CsvReplayAdapter's column_map. Run once; the output is committed.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from energy_management.simulation import household_load_w

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_secondary_meter.csv"


def main() -> None:
    start = datetime(2026, 1, 1, 0, 0, 0)
    rows = []
    cum_wh = 0.0
    prev_ts = None
    for i in range(96):  # 96 * 15min = 24h
        ts = start + timedelta(minutes=15 * i)
        power_w = household_load_w(ts, seed=99) * 0.35  # e.g. a sub-panel/garage circuit
        if prev_ts is not None:
            cum_wh += power_w * (ts - prev_ts).total_seconds() / 3600
        prev_ts = ts
        rows.append(
            {
                "iso_time": ts.isoformat(),
                "W": round(power_w, 1),
                "V": 230.0,
                "A": round(power_w / 230.0, 2),
                "Wh_total": round(cum_wh, 2),
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["iso_time", "W", "V", "A", "Wh_total"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
