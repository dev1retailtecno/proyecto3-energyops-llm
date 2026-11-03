"""Synthetic, reproducible demo data generator for EnergyOps.

All figures are fabricated for demonstration -- not measurements from a real
building. Five independent consumption circuits plus one solar generation
meter, at 15-minute resolution, so energy is never double counted: building
totals are the sum of the five consumption meters, and generation is always
reported separately.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from .timeutil import INTERVAL_MINUTES, INTERVALS_PER_DAY, is_weekend, local_datetime, to_utc_iso

DEFAULT_SEED = 1337
# Fixed anchor date (not "today") so the dataset is byte-for-byte reproducible
# no matter when it is generated.
DEFAULT_TARGET_DAY = date(2026, 3, 2)
DEFAULT_HISTORY_WEEKS = 8

CIRCUITS = ("lighting", "hvac", "critical", "pump", "equipment")
SOLAR_METER = "solar"

# A deliberately injected, known anomaly used to validate detect_anomalies:
# an unexplained load spike on the equipment circuit at 02:00-02:30 local on
# the target day, when equipment load should be close to zero.
INJECTED_ANOMALY = {
    "meter": "equipment",
    "start_minute_of_day": 120,  # 02:00 local
    "end_minute_of_day": 150,  # 02:30 local (exclusive)
    "extra_kw": 3.2,
}


@dataclass(frozen=True)
class Reading:
    meter_id: str  # circuit name; caller namespaces it per building
    timestamp_utc: str
    energy_kwh: float


def _lighting_kw(minute: int, weekend: bool, rng: random.Random) -> float:
    hour = minute / 60
    base = 0.8 if (7 <= hour < 19) else 0.15
    if weekend:
        base *= 0.5
    return max(0.0, base + rng.gauss(0, 0.05))


def _hvac_kw(minute: int, weekend: bool, rng: random.Random) -> float:
    hour = minute / 60
    peak = 3.0 if weekend else 6.0
    shape = max(0.0, 1 - ((hour - 14) / 7) ** 2)  # bell-shaped, peaks ~14:00
    base = 0.6 + peak * shape
    return max(0.0, base + rng.gauss(0, 0.2))


def _critical_kw(minute: int, weekend: bool, rng: random.Random) -> float:
    return max(0.0, 2.5 + rng.gauss(0, 0.1))  # near-constant baseload


def _pump_kw(minute: int, weekend: bool, rng: random.Random) -> float:
    cycle_minute = minute % 180  # runs 15 min out of every 3 hours
    return 4.0 + rng.gauss(0, 0.1) if cycle_minute < 15 else 0.0


def _equipment_kw(minute: int, weekend: bool, rng: random.Random) -> float:
    hour = minute / 60
    if weekend:
        return max(0.0, 0.2 + rng.gauss(0, 0.05))
    base = 3.5 if (8 <= hour < 18) else 0.3
    return max(0.0, base + rng.gauss(0, 0.15))


def _solar_kw(minute: int, weekend: bool, rng: random.Random, capacity_kw: float = 10.0) -> float:
    hour = minute / 60
    if hour < 6 or hour > 18:
        return 0.0
    shape = max(0.0, 1 - ((hour - 12) / 6) ** 2)
    cloud_factor = max(0.0, min(1.0, rng.gauss(0.9, 0.15)))
    return capacity_kw * shape * cloud_factor


_PROFILES = {
    "lighting": _lighting_kw,
    "hvac": _hvac_kw,
    "critical": _critical_kw,
    "pump": _pump_kw,
    "equipment": _equipment_kw,
}


def generate_dataset(
    seed: int = DEFAULT_SEED,
    target_day: date = DEFAULT_TARGET_DAY,
    history_weeks: int = DEFAULT_HISTORY_WEEKS,
) -> list[Reading]:
    """Generate `history_weeks` of history plus `target_day`, at 15-min resolution.

    Deterministic for a given (seed, target_day, history_weeks): uses a local
    `random.Random` instance, never the global `random` module state.
    """
    rng = random.Random(seed)
    first_day = target_day - timedelta(weeks=history_weeks)
    total_days = history_weeks * 7 + 1
    readings: list[Reading] = []

    for day_offset in range(total_days):
        day = first_day + timedelta(days=day_offset)
        weekend = is_weekend(day)
        is_target = day == target_day
        for slot in range(INTERVALS_PER_DAY):
            minute = slot * INTERVAL_MINUTES
            ts = to_utc_iso(local_datetime(day, minute))
            for circuit, profile in _PROFILES.items():
                kw = profile(minute, weekend, rng)
                if (
                    is_target
                    and circuit == INJECTED_ANOMALY["meter"]
                    and INJECTED_ANOMALY["start_minute_of_day"] <= minute < INJECTED_ANOMALY["end_minute_of_day"]
                ):
                    kw += INJECTED_ANOMALY["extra_kw"]
                readings.append(Reading(circuit, ts, round(kw * (INTERVAL_MINUTES / 60), 4)))
            solar_kw = _solar_kw(minute, weekend, rng)
            readings.append(Reading(SOLAR_METER, ts, round(solar_kw * (INTERVAL_MINUTES / 60), 4)))

    return readings
