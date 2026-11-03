"""SQLite persistence + canonical CSV import/export for EnergyOps.

Canonical CSV columns: timestamp,meter_id,energy_kwh (UTC ISO-8601 timestamps).
Re-importing the same file is idempotent: readings are keyed by
(meter_id, timestamp_utc), so INSERT OR IGNORE never creates duplicates.
"""

from __future__ import annotations

import csv
import math
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .datagen import CIRCUITS, DEFAULT_SEED, INJECTED_ANOMALY, SOLAR_METER, generate_dataset
from .timeutil import UTC

SCHEMA = """
CREATE TABLE IF NOT EXISTS buildings (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'America/Guatemala',
    max_demand_kw REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS meters (
    id TEXT PRIMARY KEY,
    building_id TEXT NOT NULL REFERENCES buildings(id),
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('consumption','generation')),
    circuit TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readings (
    meter_id TEXT NOT NULL REFERENCES meters(id),
    timestamp_utc TEXT NOT NULL,
    energy_kwh REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'simulated',
    PRIMARY KEY (meter_id, timestamp_utc)
);

CREATE TABLE IF NOT EXISTS flexible_loads (
    id TEXT PRIMARY KEY,
    building_id TEXT NOT NULL REFERENCES buildings(id),
    name TEXT NOT NULL,
    power_kw REAL NOT NULL,
    duration_minutes INTEGER NOT NULL,
    window_start_minute INTEGER NOT NULL,
    window_end_minute INTEGER NOT NULL,
    original_start_minute INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS batteries (
    id TEXT PRIMARY KEY,
    building_id TEXT NOT NULL REFERENCES buildings(id),
    capacity_kwh REAL NOT NULL,
    initial_soc_fraction REAL NOT NULL,
    reserve_fraction REAL NOT NULL,
    charge_efficiency REAL NOT NULL,
    discharge_efficiency REAL NOT NULL,
    max_charge_kw REAL NOT NULL,
    max_discharge_kw REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

CIRCUIT_LABELS = {
    "lighting": "Iluminacion",
    "hvac": "Climatizacion",
    "critical": "Servicios criticos",
    "pump": "Bomba",
    "equipment": "Carga de equipos",
    "solar": "Generacion solar",
}


class ValidationError(ValueError):
    """A CSV import or query failed validation (bad input, not a bug)."""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def meter_id(building_id: str, circuit: str) -> str:
    return f"{building_id}:{circuit}"


def seed_demo_building(
    conn: sqlite3.Connection,
    building_id: str = "demo-building",
    name: str = "Edificio Demo UVG",
    max_demand_kw: float = 45.0,
    seed: int | None = None,
    through_date: date | None = None,
) -> dict[str, Any]:
    """Create the demo building/meters/loads/battery and load the synthetic dataset.

    Safe to call more than once: dimension rows use INSERT OR IGNORE and
    readings are idempotent on their (meter_id, timestamp_utc) primary key.
    """
    actual_seed = seed if seed is not None else DEFAULT_SEED

    conn.execute(
        "INSERT OR IGNORE INTO buildings (id, name, timezone, max_demand_kw) VALUES (?,?,?,?)",
        (building_id, name, "America/Guatemala", max_demand_kw),
    )
    for circuit in CIRCUITS:
        conn.execute(
            "INSERT OR IGNORE INTO meters (id, building_id, name, kind, circuit) VALUES (?,?,?,?,?)",
            (meter_id(building_id, circuit), building_id, CIRCUIT_LABELS[circuit], "consumption", circuit),
        )
    conn.execute(
        "INSERT OR IGNORE INTO meters (id, building_id, name, kind, circuit) VALUES (?,?,?,?,?)",
        (meter_id(building_id, SOLAR_METER), building_id, CIRCUIT_LABELS[SOLAR_METER], "generation", SOLAR_METER),
    )

    # Two demo flexible loads: a laundry-style task and a secondary pumping task.
    # original_start_minute is only their conventional/default slot for the
    # before/after comparison in optimize_schedule -- see energy.schedule for
    # why the two loads are modeled independently of the five measured circuits.
    conn.execute(
        "INSERT OR IGNORE INTO flexible_loads VALUES (?,?,?,?,?,?,?,?)",
        (f"{building_id}:load-1", building_id, "Carga flexible 1 (lavado)", 4.0, 90, 8 * 60, 18 * 60, 8 * 60),
    )
    conn.execute(
        "INSERT OR IGNORE INTO flexible_loads VALUES (?,?,?,?,?,?,?,?)",
        (f"{building_id}:load-2", building_id, "Carga flexible 2 (bombeo secundario)", 3.0, 60, 0, 24 * 60, 13 * 60),
    )
    conn.execute(
        "INSERT OR IGNORE INTO batteries VALUES (?,?,?,?,?,?,?,?,?)",
        (f"{building_id}:battery-1", building_id, 10.0, 1.0, 0.2, 0.95, 0.95, 5.0, 5.0),
    )

    readings = generate_dataset(seed=actual_seed, end_day=through_date)
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO readings (meter_id, timestamp_utc, energy_kwh, source) VALUES (?,?,?,?)",
        ((meter_id(building_id, r.meter_id), r.timestamp_utc, r.energy_kwh, "simulated") for r in readings),
    )
    inserted = conn.total_changes - before
    conn.execute("INSERT OR REPLACE INTO dataset_meta (key, value) VALUES ('seed', ?)", (str(actual_seed),))
    conn.commit()

    return {
        "building_id": building_id,
        "readings_generated": len(readings),
        "readings_inserted": inserted,
        "seed": actual_seed,
        "injected_anomaly": {**INJECTED_ANOMALY, "meter_id": meter_id(building_id, INJECTED_ANOMALY["meter"])},
    }


REQUIRED_CSV_COLUMNS = ("timestamp", "meter_id", "energy_kwh")


def import_csv(conn: sqlite3.Connection, csv_path: Path) -> dict[str, Any]:
    """Validate and import a canonical CSV file. Idempotent on repeated identical imports."""
    if not csv_path.exists():
        raise ValidationError(f"CSV file not found: {csv_path}")

    known_meters = {row["id"] for row in conn.execute("SELECT id FROM meters")}

    rows_read = 0
    inserted = 0
    duplicates = 0
    unknown_meters: set[str] = set()
    invalid_rows: list[dict[str, Any]] = []

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or list(reader.fieldnames) != list(REQUIRED_CSV_COLUMNS):
            raise ValidationError(f"CSV header must be exactly {REQUIRED_CSV_COLUMNS!r}, got {reader.fieldnames!r}")
        for line_no, row in enumerate(reader, start=2):
            rows_read += 1
            mid = row["meter_id"]
            if mid not in known_meters:
                unknown_meters.add(mid)
                invalid_rows.append({"line": line_no, "reason": "unknown meter_id", "row": row})
                continue
            try:
                ts = datetime.fromisoformat(row["timestamp"])
                if ts.tzinfo is None or ts.minute % 15 or ts.second or ts.microsecond:
                    raise ValueError("timezone and fifteen-minute alignment required")
            except (TypeError, ValueError):
                invalid_rows.append({"line": line_no, "reason": "invalid timestamp", "row": row})
                continue
            try:
                energy = float(row["energy_kwh"])
            except ValueError:
                invalid_rows.append({"line": line_no, "reason": "energy_kwh not numeric", "row": row})
                continue
            if not math.isfinite(energy) or energy < 0:
                invalid_rows.append({"line": line_no, "reason": "energy_kwh not finite", "row": row})
                continue

            cur = conn.execute(
                "INSERT OR IGNORE INTO readings (meter_id, timestamp_utc, energy_kwh, source) VALUES (?,?,?,?)",
                (mid, ts.astimezone(UTC).isoformat(), energy, f"import:{csv_path.name}"),
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                duplicates += 1

    conn.commit()
    return {
        "rows_read": rows_read,
        "inserted": inserted,
        "duplicates_skipped": duplicates,
        "unknown_meters": sorted(unknown_meters),
        "invalid_rows": invalid_rows[:20],
        "invalid_row_count": len(invalid_rows),
    }


def export_csv(conn: sqlite3.Connection, csv_path: Path, building_id: str) -> int:
    rows = conn.execute(
        "SELECT r.meter_id, r.timestamp_utc, r.energy_kwh FROM readings r "
        "JOIN meters m ON m.id = r.meter_id WHERE m.building_id = ? "
        "ORDER BY r.timestamp_utc, r.meter_id",
        (building_id,),
    ).fetchall()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(REQUIRED_CSV_COLUMNS)
        for row in rows:
            writer.writerow([row["timestamp_utc"], row["meter_id"], row["energy_kwh"]])
    return len(rows)


def list_buildings(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    buildings = []
    for b in conn.execute("SELECT * FROM buildings"):
        meters = conn.execute("SELECT * FROM meters WHERE building_id = ?", (b["id"],)).fetchall()
        buildings.append(
            {
                "id": b["id"],
                "name": b["name"],
                "timezone": b["timezone"],
                "max_demand_kw": b["max_demand_kw"],
                "meters": [dict(m) for m in meters],
            }
        )
    return buildings


def get_flexible_loads(conn: sqlite3.Connection, building_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM flexible_loads WHERE building_id = ?", (building_id,)).fetchall()


def get_battery(conn: sqlite3.Connection, building_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM batteries WHERE building_id = ? LIMIT 1", (building_id,)).fetchone()


def readings_in_range(
    conn: sqlite3.Connection, meter_ids: list[str], start_utc: str, end_utc: str
) -> list[sqlite3.Row]:
    placeholders = ",".join("?" for _ in meter_ids)
    return conn.execute(
        f"SELECT meter_id, timestamp_utc, energy_kwh FROM readings "
        f"WHERE meter_id IN ({placeholders}) AND timestamp_utc >= ? AND timestamp_utc < ? "
        f"ORDER BY timestamp_utc, meter_id",
        (*meter_ids, start_utc, end_utc),
    ).fetchall()
