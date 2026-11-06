"""EnergyOps local MCP server: the seven analytical tools, over stdio.

Exposes list_buildings, import_readings, get_energy_summary,
detect_anomalies, optimize_schedule, simulate_outage and prepare_report on
top of energyops_mcp.energy.{storage,anomalies,schedule,battery}.

Every handler that hits bad input (unknown building, invalid date, no data
for the period) raises ValueError; energyops_mcp.protocol.server.McpServer catches
that and turns it into a normal CallToolResult(is_error=True) instead of a
JSON-RPC protocol error, per the project's separation between protocol
errors and tool execution failures. Only tools/call with an unknown tool
*name* is a protocol error (handled by the base class itself).

The database auto-seeds the reproducible demo building on first use, since
this server's entire purpose is the documented simulation -- there is no
"real" data to protect a clean/empty database for.
"""

from __future__ import annotations

import argparse
import math
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..protocol.server import McpServer
from ..protocol.types import CallToolResult
from . import storage
from .anomalies import detect_anomalies as run_detect_anomalies
from .battery import Battery
from .battery import simulate_outage as run_simulate_outage
from .datagen import CIRCUITS
from .schedule import FlexibleLoad
from .schedule import optimize_schedule as run_optimize_schedule
from .timeutil import INTERVALS_PER_DAY, UTC, from_utc_iso, local_datetime, to_local, to_utc_iso

DEFAULT_DB_PATH = Path("energyops.sqlite3")
DEFAULT_IMPORT_DIR = Path("data/imports").resolve()

server = McpServer(name="energyops-energy", version="0.1.0")
_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = storage.connect(DEFAULT_DB_PATH)
        storage.seed_demo_building(_conn)
    return _conn


def _require_building(conn: sqlite3.Connection, building_id: str) -> dict[str, Any]:
    buildings = {b["id"]: b for b in storage.list_buildings(conn)}
    if building_id not in buildings:
        raise ValueError(f"unknown building_id: {building_id!r}; call list_buildings first")
    return buildings[building_id]


def _parse_when(text: str) -> datetime:
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp {text!r}: {exc}") from None
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must include a timezone offset: {text!r}")
    return dt.astimezone(UTC)


def _parse_local_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid date {text!r}, expected YYYY-MM-DD: {exc}") from None


def _expand_tariff_bands(bands: list[dict[str, Any]]) -> list[float]:
    if not bands:
        raise ValueError("tariff_bands must not be empty")
    prices: list[float | None] = [None] * INTERVALS_PER_DAY
    for band in bands:
        start, end, price = band["start_minute"], band["end_minute"], band["price_per_kwh"]
        if start % 15 or end % 15 or not math.isfinite(price) or price < 0:
            raise ValueError("tariff bands require quarter-hour boundaries and finite nonnegative prices")
        if not (0 <= start < end <= 24 * 60):
            raise ValueError(f"invalid tariff band {band!r}")
        for slot in range(start // 15, end // 15):
            if prices[slot] is not None:
                raise ValueError("overlapping tariff bands")
            prices[slot] = price
    missing = [i for i, p in enumerate(prices) if p is None]
    if missing:
        raise ValueError(f"tariff_bands do not cover the full day; gap starts at minute {missing[0] * 15}")
    return prices  # type: ignore[return-value]


def _interval_index_for_day(timestamp_utc: str, local_day: date) -> int | None:
    local_dt = to_local(from_utc_iso(timestamp_utc))
    if local_dt.date() != local_day:
        return None
    return (local_dt.hour * 60 + local_dt.minute) // 15


def _slot_offset(start_utc: datetime, timestamp_utc: str) -> int | None:
    total_minutes = (from_utc_iso(timestamp_utc) - start_utc).total_seconds() / 60
    if total_minutes < 0 or total_minutes % 15 != 0:
        return None
    return int(total_minutes // 15)


def _require_complete(rows, meter_ids, start_utc, intervals):
    """Continuity-sensitive analyses must never substitute zero for missing data."""
    if start_utc.minute % 15 or start_utc.second or start_utc.microsecond:
        raise ValueError("start must align with a fifteen-minute interval")
    present = {(r["meter_id"], r["timestamp_utc"]) for r in rows}
    missing = 0
    for meter in meter_ids:
        for i in range(intervals):
            stamp = to_utc_iso(start_utc + timedelta(minutes=15 * i))
            missing += (meter, stamp) not in present
    if missing:
        raise ValueError(f"incomplete readings: {missing} missing meter intervals; calculation stopped")


@server.tool("list_buildings", "List available buildings and their meters.", {"type": "object", "properties": {}})
def _list_buildings(_args: dict[str, Any]) -> CallToolResult:
    buildings = storage.list_buildings(_db())
    lines = [f"- {b['id']} ({b['name']}): {len(b['meters'])} meters, capacidad {b['max_demand_kw']} kW" for b in buildings]
    return CallToolResult.ok("\n".join(lines) or "No buildings configured.", structured={"buildings": buildings})


@server.tool(
    "import_readings",
    "Validate and import a canonical CSV (timestamp,meter_id,energy_kwh) from the authorized import directory.",
    {
        "type": "object",
        "properties": {
            "csv_path": {
                "type": "string",
                "description": "Path to the CSV file; must resolve inside the authorized import directory",
            }
        },
        "required": ["csv_path"],
    },
)
def _import_readings(args: dict[str, Any]) -> CallToolResult:
    resolved = Path(args["csv_path"]).resolve()
    DEFAULT_IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    if resolved != DEFAULT_IMPORT_DIR and DEFAULT_IMPORT_DIR not in resolved.parents:
        raise ValueError(f"csv_path must be inside the authorized import directory ({DEFAULT_IMPORT_DIR}); got {resolved}")

    result = storage.import_csv(_db(), resolved)  # storage.ValidationError is a ValueError subclass
    text = (
        f"Read {result['rows_read']} rows: {result['inserted']} inserted, "
        f"{result['duplicates_skipped']} duplicates skipped, {result['invalid_row_count']} invalid, "
        f"unknown meters: {result['unknown_meters'] or 'none'}"
    )
    return CallToolResult.ok(text, structured=result)


@server.tool(
    "get_energy_summary",
    "Consumption, generation, peak/average demand and data quality for a building over a period.",
    {
        "type": "object",
        "properties": {
            "building_id": {"type": "string"},
            "start": {"type": "string", "description": "ISO-8601 start, inclusive, with timezone offset"},
            "end": {"type": "string", "description": "ISO-8601 end, exclusive, with timezone offset"},
        },
        "required": ["building_id", "start", "end"],
    },
)
def _get_energy_summary(args: dict[str, Any]) -> CallToolResult:
    conn = _db()
    building = _require_building(conn, args["building_id"])
    start_utc, end_utc = _parse_when(args["start"]), _parse_when(args["end"])
    if end_utc <= start_utc:
        raise ValueError("end must be after start")
    if any(dt.minute % 15 or dt.second or dt.microsecond for dt in (start_utc,end_utc)):
        raise ValueError('summary boundaries must align with fifteen-minute intervals')

    meters = building["meters"]
    rows = storage.readings_in_range(conn, [m["id"] for m in meters], to_utc_iso(start_utc), to_utc_iso(end_utc))
    if not rows:
        raise ValueError('no readings found for the requested period')
    intervals=int((end_utc-start_utc).total_seconds()//900)
    is_partial=len(rows)!=intervals*len(meters)
    meter_by_id = {m["id"]: m for m in meters}

    by_meter: dict[str, list[float]] = {m["id"]: [] for m in meters}
    interval_totals: dict[str, float] = {}
    for row in rows:
        by_meter[row["meter_id"]].append(row["energy_kwh"])
        if meter_by_id[row["meter_id"]]["kind"] == "consumption":
            interval_totals[row["timestamp_utc"]] = interval_totals.get(row["timestamp_utc"], 0.0) + row["energy_kwh"]

    expected_intervals = max(0, int((end_utc - start_utc).total_seconds() // (15 * 60)))
    hours = expected_intervals * 0.25
    consumption_kwh = generation_kwh = 0.0
    per_circuit: dict[str, float] = {}
    quality: dict[str, dict[str, Any]] = {}

    for m in meters:
        values = by_meter[m["id"]]
        total = sum(values)
        per_circuit[m["circuit"]] = round(total, 4)
        quality[m["circuit"]] = {
            "intervals_present": len(values),
            "intervals_expected": expected_intervals,
            "completeness_pct": round(100 * len(values) / expected_intervals, 2) if expected_intervals else None,
        }
        if m["kind"] == "consumption":
            consumption_kwh += total
        else:
            generation_kwh += total

    peak_demand_kw = max((v / 0.25 for v in interval_totals.values()), default=0.0)
    average_demand_kw = (consumption_kwh / hours) if hours else 0.0

    text = (
        f"Periodo {args['start']} a {args['end']}: consumo {consumption_kwh:.2f} kWh, "
        f"generacion solar {generation_kwh:.2f} kWh, demanda maxima {peak_demand_kw:.2f} kW, "
        f"demanda promedio {average_demand_kw:.2f} kW."
    )
    return CallToolResult.ok(
        text,
        structured={
            "building_id": building["id"],
            "consumption_kwh": round(consumption_kwh, 4),
            "generation_kwh": round(generation_kwh, 4),
            "peak_demand_kw": round(peak_demand_kw, 4),
            "average_demand_kw": round(average_demand_kw, 4),
            "per_circuit_kwh": per_circuit,
            "data_quality": quality,
            "is_partial": is_partial,
            "interpretation": 'Observed readings only; totals and demand may be underestimated.' if is_partial else 'Complete meter intervals for the requested period.',
        },
    )


@server.tool(
    "detect_anomalies",
    "Detect anomalous intervals on a local target date vs. the historical same-slot median (MAD-based).",
    {
        "type": "object",
        "properties": {
            "building_id": {"type": "string"},
            "target_date": {"type": "string", "description": "Local date YYYY-MM-DD (America/Guatemala)"},
            "meters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Circuit names to check; defaults to all consumption circuits",
            },
        },
        "required": ["building_id", "target_date"],
    },
)
def _detect_anomalies(args: dict[str, Any]) -> CallToolResult:
    conn = _db()
    building = _require_building(conn, args["building_id"])
    target_day = _parse_local_date(args["target_date"])
    circuits = args.get("meters") or list(CIRCUITS)
    unknown = [c for c in circuits if c not in CIRCUITS]
    if unknown:
        raise ValueError(f"unknown circuit(s) {unknown}; known circuits: {list(CIRCUITS)}")

    meter_ids = [storage.meter_id(building["id"], c) for c in circuits]
    target_start = local_datetime(target_day, 0)
    target_end = local_datetime(target_day + timedelta(days=1), 0)
    history_start = local_datetime(target_day - timedelta(weeks=8), 0)

    target_rows = storage.readings_in_range(conn, meter_ids, to_utc_iso(target_start), to_utc_iso(target_end))
    if not target_rows:
        raise ValueError(f"no readings found for {args['target_date']}; import or seed data first")
    history_rows = storage.readings_in_range(conn, meter_ids, to_utc_iso(history_start), to_utc_iso(target_start))

    incidents, diagnostics = run_detect_anomalies(
        [(r["meter_id"], r["timestamp_utc"], r["energy_kwh"]) for r in history_rows],
        [(r["meter_id"], r["timestamp_utc"], r["energy_kwh"]) for r in target_rows],
    )

    if incidents:
        lines = [f"{len(incidents)} incidente(s) detectado(s) en {args['target_date']}:"]
        lines += [f"  - {inc.meter_id}: {inc.start_utc}..{inc.end_utc}, exceso {inc.excess_kwh:.3f} kWh" for inc in incidents]
    else:
        lines = [f"Sin anomalias en {args['target_date']} ({diagnostics['target_intervals_evaluated']} intervalos evaluados)."]
    return CallToolResult.ok(
        "\n".join(lines), structured={"incidents": [inc.to_dict() for inc in incidents], "diagnostics": diagnostics}
    )


@server.tool(
    "optimize_schedule",
    "Find the lowest-cost 15-minute start times for the building's flexible loads on a given local day.",
    {
        "type": "object",
        "properties": {
            "building_id": {"type": "string"},
            "date": {"type": "string", "description": "Local date YYYY-MM-DD"},
            "tariff_bands": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "start_minute": {"type": "integer"},
                        "end_minute": {"type": "integer"},
                        "price_per_kwh": {"type": "number"},
                    },
                    "required": ["start_minute", "end_minute", "price_per_kwh"],
                },
                "description": "Bands must cover the full day (0..1440 minutes) with no gaps",
            },
        },
        "required": ["building_id", "date", "tariff_bands"],
    },
)
def _optimize_schedule(args: dict[str, Any]) -> CallToolResult:
    conn = _db()
    building = _require_building(conn, args["building_id"])
    day = _parse_local_date(args["date"])
    tariff = _expand_tariff_bands(args["tariff_bands"])

    consumption_meters = [m["id"] for m in building["meters"] if m["kind"] == "consumption"]
    solar_meter_id = next(m["id"] for m in building["meters"] if m["kind"] == "generation")
    day_start, day_end = local_datetime(day, 0), local_datetime(day + timedelta(days=1), 0)
    rows = storage.readings_in_range(conn, [*consumption_meters, solar_meter_id], to_utc_iso(day_start), to_utc_iso(day_end))
    if not rows:
        raise ValueError(f"no readings found for {args['date']}; import or seed data first")
    _require_complete(rows, [*consumption_meters, solar_meter_id], day_start, INTERVALS_PER_DAY)

    base_profile = [0.0] * INTERVALS_PER_DAY
    solar_profile = [0.0] * INTERVALS_PER_DAY
    for row in rows:
        idx = _interval_index_for_day(row["timestamp_utc"], day)
        if idx is None:
            continue
        (solar_profile if row["meter_id"] == solar_meter_id else base_profile)[idx] += row["energy_kwh"]

    loads = [
        FlexibleLoad(
            id=r["id"],
            name=r["name"],
            power_kw=r["power_kw"],
            duration_minutes=r["duration_minutes"],
            window_start_minute=r["window_start_minute"],
            window_end_minute=r["window_end_minute"],
            original_start_minute=r["original_start_minute"],
        )
        for r in storage.get_flexible_loads(conn, building["id"])
    ]
    if not loads:
        raise ValueError(f"building {building['id']!r} has no flexible loads configured")

    result = run_optimize_schedule(base_profile, solar_profile, tariff, building["max_demand_kw"], loads)
    if result.feasible:
        text = (
            f"Propuesto: inicios {result.proposed.starts_minute} (minutos), costo {result.proposed.cost:.4f}, "
            f"ahorro {result.savings_variable_cost:.4f} vs. horario original."
        )
    else:
        text = f"Sin programacion factible: {result.reason_if_infeasible}"
    return CallToolResult.ok(text, structured=result.to_dict())


@server.tool(
    "simulate_outage",
    "Simulate battery+solar autonomy for an outage, comparing the full building vs. critical loads only.",
    {
        "type": "object",
        "properties": {
            "building_id": {"type": "string"},
            "start": {"type": "string", "description": "ISO-8601 outage start, with timezone offset"},
            "horizon_hours": {"type": "number", "default": 24, "description": "How many hours to simulate"},
        },
        "required": ["building_id", "start"],
    },
)
def _simulate_outage(args: dict[str, Any]) -> CallToolResult:
    conn = _db()
    building = _require_building(conn, args["building_id"])
    start_utc = _parse_when(args["start"])
    horizon_hours = float(args.get("horizon_hours", 24))
    if not math.isfinite(horizon_hours) or not 0 < horizon_hours <= 168 or horizon_hours * 4 % 1:
        raise ValueError("horizon_hours must be a quarter-hour multiple between 0.25 and 168")
    horizon_intervals = int(horizon_hours * 4)

    battery_row = storage.get_battery(conn, building["id"])
    if battery_row is None:
        raise ValueError(f"building {building['id']!r} has no battery configured")
    battery = Battery(
        id=battery_row["id"],
        capacity_kwh=battery_row["capacity_kwh"],
        initial_soc_fraction=battery_row["initial_soc_fraction"],
        reserve_fraction=battery_row["reserve_fraction"],
        charge_efficiency=battery_row["charge_efficiency"],
        discharge_efficiency=battery_row["discharge_efficiency"],
        max_charge_kw=battery_row["max_charge_kw"],
        max_discharge_kw=battery_row["max_discharge_kw"],
    )

    end_utc = start_utc + timedelta(minutes=15 * horizon_intervals)
    consumption_meters = {m["circuit"]: m["id"] for m in building["meters"] if m["kind"] == "consumption"}
    solar_meter_id = next(m["id"] for m in building["meters"] if m["kind"] == "generation")
    rows = storage.readings_in_range(conn, [*consumption_meters.values(), solar_meter_id], to_utc_iso(start_utc), to_utc_iso(end_utc))
    if not rows:
        raise ValueError("no readings found for the requested outage window; import or seed data first")
    _require_complete(rows, [*consumption_meters.values(), solar_meter_id], start_utc, horizon_intervals)

    full_demand = [0.0] * horizon_intervals
    critical_demand = [0.0] * horizon_intervals
    solar = [0.0] * horizon_intervals
    critical_meter_id = consumption_meters.get("critical")

    for row in rows:
        idx = _slot_offset(start_utc, row["timestamp_utc"])
        if idx is None or not (0 <= idx < horizon_intervals):
            continue
        if row["meter_id"] == solar_meter_id:
            solar[idx] += row["energy_kwh"]
        else:
            full_demand[idx] += row["energy_kwh"]
            if row["meter_id"] == critical_meter_id:
                critical_demand[idx] += row["energy_kwh"]

    full_result = run_simulate_outage(full_demand, solar, battery)
    critical_result = run_simulate_outage(critical_demand, solar, battery)

    def _describe(label: str, r) -> str:
        bound = " (limite inferior)" if r.autonomy_is_lower_bound else ""
        return f"{label}: autonomia {r.autonomy_minutes} min{bound}"

    text = f"{_describe('Edificio completo', full_result)}. {_describe('Solo cargas criticas', critical_result)}."
    return CallToolResult.ok(
        text,
        structured={
            "battery_id": battery.id,
            "full_building": full_result.to_dict(include_timeline=True),
            "critical_only": critical_result.to_dict(include_timeline=True),
        },
    )


@server.tool(
    "prepare_report",
    "Assemble selected analysis results into a Markdown report with figures and dataset provenance.",
    {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "building_id": {"type": "string"},
            "sections": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {"heading": {"type": "string"}, "body_markdown": {"type": "string"}},
                    "required": ["heading", "body_markdown"],
                },
            },
        },
        "required": ["title", "sections"],
    },
)
def _prepare_report(args: dict[str, Any]) -> CallToolResult:
    conn = _db()
    lines = [f"# {args['title']}", "", f"_Generado: {datetime.now(UTC).isoformat()}_"]
    if args.get("building_id"):
        building = _require_building(conn, args["building_id"])
        lines.append(f"_Edificio: {building['name']} ({building['id']})_")
    seed_row = conn.execute("SELECT value FROM dataset_meta WHERE key='seed'").fetchone()
    if seed_row:
        lines.append(f"_Dataset simulado, semilla reproducible: {seed_row['value']}_")
    lines.append("")
    for section in args["sections"]:
        lines += [f"## {section['heading']}", "", section["body_markdown"], ""]
    markdown = "\n".join(lines)
    return CallToolResult.ok(markdown, structured={"markdown": markdown})


def main() -> None:
    global DEFAULT_DB_PATH, DEFAULT_IMPORT_DIR

    parser = argparse.ArgumentParser(description="EnergyOps local MCP server (stdio)")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--import-dir", default=str(DEFAULT_IMPORT_DIR))
    parsed = parser.parse_args()

    DEFAULT_DB_PATH = Path(parsed.db_path)
    DEFAULT_IMPORT_DIR = Path(parsed.import_dir).resolve()
    server.run_stdio()


if __name__ == "__main__":
    main()
