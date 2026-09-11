"""Synthetic data generators used to test the pipeline before real hardware exists.

Every function here is a pure function of a timestamp (plus a seed), not a
stateful process. That makes simulated adapters trivially testable: calling
read(at=t) twice with the same t always returns the same reading, and a full
day of data can be generated instantly without sleeping in real time.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone


def _hour_of_day(ts: datetime) -> float:
    return ts.hour + ts.minute / 60 + ts.second / 3600


def _daily_rng(seed: int, ts: datetime) -> random.Random:
    """RNG that stays constant across one calendar day, varies across days/devices."""
    return random.Random(hash((seed, ts.year, ts.month, ts.day)))


def _minute_rng(seed: int, ts: datetime) -> random.Random:
    """RNG that varies every minute, for high-frequency sensor noise."""
    return random.Random(hash((seed, ts.year, ts.month, ts.day, ts.hour, ts.minute)))


def solar_generation_w(ts: datetime, *, capacity_w: float = 4000.0, seed: int = 0) -> float:
    """Bell-shaped daylight curve, scaled by a per-day 'cloudiness' factor."""
    hod = _hour_of_day(ts)
    sunrise, sunset = 6.0, 19.5
    if not (sunrise < hod < sunset):
        return 0.0

    shape = math.sin(math.pi * (hod - sunrise) / (sunset - sunrise))
    cloudiness = _daily_rng(seed, ts).uniform(0.55, 1.0)
    noise = _minute_rng(seed, ts).uniform(-0.03, 0.03)
    power = capacity_w * shape * cloudiness * (1 + noise)
    return max(0.0, round(power, 1))


def household_load_w(ts: datetime, *, seed: int = 1) -> float:
    """Baseline load plus morning and evening peaks, like a typical home."""
    hod = _hour_of_day(ts)

    def bump(center: float, width: float, height: float) -> float:
        return height * math.exp(-((hod - center) ** 2) / (2 * width**2))

    base = 250.0
    morning = bump(7.5, 1.2, 900.0)
    evening = bump(19.0, 1.8, 1500.0)
    noise = _minute_rng(seed, ts).uniform(-40, 40)
    return max(0.0, round(base + morning + evening + noise, 1))


def _soc_curve(hod: float) -> float:
    """Target battery state-of-charge percent across the day (piecewise-linear)."""
    points = [
        (0.0, 35.0), (6.0, 35.0), (10.0, 40.0), (16.0, 90.0),
        (17.0, 90.0), (22.0, 45.0), (24.0, 35.0),
    ]
    for (h0, s0), (h1, s1) in zip(points, points[1:]):
        if h0 <= hod <= h1:
            frac = 0 if h1 == h0 else (hod - h0) / (h1 - h0)
            return s0 + frac * (s1 - s0)
    return 35.0


def battery_state_w(ts: datetime, *, capacity_wh: float = 10_000.0, seed: int = 2) -> tuple[float, float]:
    """Returns (power_w, state_of_charge_pct). Positive power = discharging."""
    hod = _hour_of_day(ts)
    soc = _soc_curve(hod)
    soc_next = _soc_curve(min(hod + 1 / 60, 24.0))
    delta_pct_per_min = soc_next - soc

    power_w = -(delta_pct_per_min / 100) * capacity_wh * 60
    noise = _minute_rng(seed, ts).uniform(-15, 15)
    return round(power_w + noise, 1), round(soc, 1)


def ev_charger_w(ts: datetime, *, seed: int = 3) -> tuple[float, bool]:
    """Returns (power_w, plugged_in). Session is ~18:00-23:00 with a random daily offset."""
    hod = _hour_of_day(ts)
    day_rng = _daily_rng(seed, ts)
    start = 18.0 + day_rng.uniform(-0.5, 0.5)
    end = start + day_rng.uniform(3.5, 5.0)

    if not (start <= hod <= end):
        return 0.0, False

    remaining_frac = (end - hod) / (end - start)
    power = 7200.0 if remaining_frac > 0.15 else 7200.0 * (remaining_frac / 0.15)
    noise = _minute_rng(seed, ts).uniform(-30, 30)
    return max(0.0, round(power + noise, 1)), True


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
