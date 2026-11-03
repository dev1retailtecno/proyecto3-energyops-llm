from datetime import date, timedelta

from energyops_mcp.energy.anomalies import detect_anomalies
from energyops_mcp.energy.datagen import DEFAULT_TARGET_DAY, INJECTED_ANOMALY, generate_dataset
from energyops_mcp.energy.timeutil import from_utc_iso, to_local


def _weekly_timestamps(start: date, count: int, hour: int = 18) -> list[str]:
    """UTC timestamps spaced exactly one week apart at a fixed hour, so every
    entry lands in the same (weekday-type, minute-of-day) bucket by construction."""
    return [f"{(start + timedelta(weeks=i)).isoformat()}T{hour:02d}:00:00+00:00" for i in range(count)]


def _split_by_local_day(readings, target_day):
    history, target = [], []
    for r in readings:
        local_date = to_local(from_utc_iso(r.timestamp_utc)).date()
        row = (r.meter_id, r.timestamp_utc, r.energy_kwh)
        (target if local_date == target_day else history).append(row)
    return history, target


def test_injected_anomaly_is_detected_on_the_correct_meter_and_window():
    readings = generate_dataset()
    history_rows, target_rows = _split_by_local_day(readings, DEFAULT_TARGET_DAY)

    incidents, _diagnostics = detect_anomalies(history_rows, target_rows)

    matches = [inc for inc in incidents if inc.meter_id == INJECTED_ANOMALY["meter"]]
    assert matches, f"expected an incident on meter {INJECTED_ANOMALY['meter']!r}, got {incidents!r}"

    inc = matches[0]
    start_local = to_local(from_utc_iso(inc.start_utc))
    start_minute = start_local.hour * 60 + start_local.minute
    end_local = to_local(from_utc_iso(inc.end_utc))
    end_minute = end_local.hour * 60 + end_local.minute
    assert start_minute <= INJECTED_ANOMALY["start_minute_of_day"]
    assert end_minute >= INJECTED_ANOMALY["end_minute_of_day"]
    assert inc.excess_kwh > 0


def test_insufficient_history_is_reported_not_flagged():
    base = date(2025, 12, 4)
    history_rows = [("m1", ts, 1.0) for ts in _weekly_timestamps(base, 3)]  # only 3, need >= 7
    target_rows = [("m1", _weekly_timestamps(base, 5)[4], 50.0)]  # same slot, huge value

    incidents, diagnostics = detect_anomalies(history_rows, target_rows)

    assert incidents == []
    assert diagnostics["target_intervals_with_insufficient_history"] == 1


def test_zero_variance_baseline_does_not_false_positive_on_tiny_noise():
    base = date(2025, 10, 1)
    history_rows = [("m1", ts, 2.0) for ts in _weekly_timestamps(base, 8)]  # MAD == 0
    target_rows = [("m1", _weekly_timestamps(base, 9)[8], 2.05)]  # +0.05 kWh, below the 0.1 kWh floor

    incidents, diagnostics = detect_anomalies(history_rows, target_rows)

    assert incidents == []
    assert diagnostics["target_intervals_with_insufficient_history"] == 0


def test_zero_variance_baseline_still_flags_a_real_excess():
    base = date(2025, 10, 1)
    history_rows = [("m1", ts, 2.0) for ts in _weekly_timestamps(base, 8)]
    target_rows = [("m1", _weekly_timestamps(base, 9)[8], 5.0)]  # +3.0 kWh, well past the floor

    incidents, _diagnostics = detect_anomalies(history_rows, target_rows)

    assert len(incidents) == 1
    assert incidents[0].excess_kwh > 0
