"""Anomaly detection: compare each target-day interval against the historical
median for the same time-of-day slot and day type (weekday/weekend), using a
median-absolute-deviation (MAD) robust threshold.

Rule: an interval is anomalous when its (time-of-day, day-type) slot has at
least MIN_REFERENCE_OBSERVATIONS historical points AND
abs(observed - median) > max(3 * 1.4826 * MAD, MIN_EXCESS_KWH). The 1.4826
factor scales MAD to be comparable to a standard deviation under normality;
the absolute floor keeps near-zero-variance baselines (e.g. an idle circuit)
from flagging on floating-point noise. Consecutive flagged intervals for the
same meter are grouped into one incident.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .timeutil import INTERVAL_MINUTES, from_utc_iso, is_weekend, to_local

MIN_REFERENCE_OBSERVATIONS = 7
MIN_EXCESS_KWH = 0.2  # Selected on development seeds 100..109; see evaluation/detection_results.json.
ROBUST_SCALE = 1.4826
THRESHOLD_DEVIATIONS = 3.0

RULE_DESCRIPTION = (
    f"|observado-mediana| > max({THRESHOLD_DEVIATIONS}*1.4826*MAD, {MIN_EXCESS_KWH} kWh), "
    f"con al menos {MIN_REFERENCE_OBSERVATIONS} observaciones de referencia para el mismo "
    f"horario y tipo de dia (laborable/fin de semana)"
)

ReadingRow = tuple[str, str, float]  # (meter_id, timestamp_utc, energy_kwh)


@dataclass
class Incident:
    meter_id: str
    start_utc: str
    end_utc: str
    duration_minutes: int
    expected_kwh: float
    observed_kwh: float
    excess_kwh: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "meter_id": self.meter_id,
            "start_utc": self.start_utc,
            "end_utc": self.end_utc,
            "duration_minutes": self.duration_minutes,
            "expected_kwh": round(self.expected_kwh, 4),
            "observed_kwh": round(self.observed_kwh, 4),
            "excess_kwh": round(self.excess_kwh, 4),
            "rule": RULE_DESCRIPTION,
        }


def _slot_key(ts_iso: str) -> tuple[bool, int]:
    local = to_local(from_utc_iso(ts_iso))
    return (is_weekend(local.date()), local.hour * 60 + local.minute)


def _is_next_interval(prev_ts: str, ts: str) -> bool:
    return (from_utc_iso(ts) - from_utc_iso(prev_ts)).total_seconds() == INTERVAL_MINUTES * 60


def _incident_from_run(meter_id: str, run: list[tuple[str, float, float]]) -> Incident:
    start = run[0][0]
    end = (from_utc_iso(run[-1][0]) + timedelta(minutes=INTERVAL_MINUTES)).isoformat()
    observed = sum(p[1] for p in run)
    expected = sum(p[2] for p in run)
    return Incident(
        meter_id=meter_id,
        start_utc=start,
        end_utc=end,
        duration_minutes=len(run) * INTERVAL_MINUTES,
        expected_kwh=expected,
        observed_kwh=observed,
        excess_kwh=observed - expected,
    )


def detect_anomalies(
    history_rows: list[ReadingRow], target_rows: list[ReadingRow]
) -> tuple[list[Incident], dict[str, Any]]:
    """history_rows is the reference window (must exclude the target day itself);
    target_rows is the day being analyzed. Returns (incidents, diagnostics)."""

    reference: dict[tuple[str, bool, int], list[float]] = {}
    for meter_id, ts, kwh in history_rows:
        weekend, minute = _slot_key(ts)
        reference.setdefault((meter_id, weekend, minute), []).append(kwh)

    flags: dict[str, list[tuple[str, float, float]]] = {}
    insufficient_history = 0

    for meter_id, ts, kwh in target_rows:
        weekend, minute = _slot_key(ts)
        samples = reference.get((meter_id, weekend, minute), [])
        if len(samples) < MIN_REFERENCE_OBSERVATIONS:
            insufficient_history += 1
            continue
        median = statistics.median(samples)
        mad = statistics.median([abs(s - median) for s in samples])
        threshold = max(THRESHOLD_DEVIATIONS * ROBUST_SCALE * mad, MIN_EXCESS_KWH)
        if abs(kwh - median) > threshold:
            flags.setdefault(meter_id, []).append((ts, kwh, median))

    incidents: list[Incident] = []
    for meter_id, points in flags.items():
        points.sort(key=lambda p: p[0])
        run: list[tuple[str, float, float]] = []
        for point in points:
            if run and _is_next_interval(run[-1][0], point[0]):
                run.append(point)
                continue
            if run:
                incidents.append(_incident_from_run(meter_id, run))
            run = [point]
        if run:
            incidents.append(_incident_from_run(meter_id, run))

    incidents.sort(key=lambda inc: (inc.meter_id, inc.start_utc))
    diagnostics = {
        "target_intervals_evaluated": len(target_rows),
        "target_intervals_with_insufficient_history": insufficient_history,
        "min_reference_observations": MIN_REFERENCE_OBSERVATIONS,
        "rule": RULE_DESCRIPTION,
    }
    return incidents, diagnostics
