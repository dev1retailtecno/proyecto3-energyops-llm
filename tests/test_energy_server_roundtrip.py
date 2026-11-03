"""End-to-end test: spawn the real EnergyOps local MCP server as a subprocess
and exercise all seven tools through the same MCP client the host will use.

Each test gets its own --db-path (and, where relevant, --import-dir) under
tmp_path, so the auto-seeded demo dataset and any imports never leak
between tests or depend on shared state.
"""

from __future__ import annotations

import sys

import pytest

from energyops_mcp.protocol.client import McpClient
from energyops_mcp.protocol.stdio_transport import StdioTransport

pytestmark = pytest.mark.asyncio

EXPECTED_TOOLS = {
    "list_buildings",
    "import_readings",
    "get_energy_summary",
    "detect_anomalies",
    "optimize_schedule",
    "simulate_outage",
    "prepare_report",
}


async def _connected_client(db_path, import_dir=None) -> McpClient:
    args = ["-m", "energyops_mcp.energy.server", "--db-path", str(db_path)]
    if import_dir is not None:
        args += ["--import-dir", str(import_dir)]
    transport = StdioTransport(sys.executable, args)
    client = McpClient(transport, server_name="energyops-energy", request_timeout=30)
    await client.start()
    await client.initialize()
    return client


async def test_all_seven_tools_are_registered(tmp_path):
    client = await _connected_client(tmp_path / "t1.sqlite3")
    try:
        names = {t.name for t in await client.list_tools()}
        assert names == EXPECTED_TOOLS
    finally:
        await client.aclose()


async def test_list_buildings_auto_seeds_demo_data(tmp_path):
    client = await _connected_client(tmp_path / "t2.sqlite3")
    try:
        result = await client.call_tool("list_buildings", {})
        assert result.is_error is False
        buildings = result.structured_content["buildings"]
        assert buildings[0]["id"] == "demo-building"
        assert len(buildings[0]["meters"]) == 6
    finally:
        await client.aclose()


async def test_unknown_building_is_a_tool_failure_not_a_protocol_error(tmp_path):
    client = await _connected_client(tmp_path / "t3.sqlite3")
    try:
        result = await client.call_tool("get_energy_summary", {"building_id": "nope", "start": "2026-01-01T00:00:00+00:00", "end": "2026-01-02T00:00:00+00:00"})
        assert result.is_error is True
        assert "unknown building_id" in result.text()
    finally:
        await client.aclose()


async def test_get_energy_summary_matches_hand_checkable_arithmetic(tmp_path):
    import_dir = tmp_path / "imports"
    import_dir.mkdir()
    csv_path = import_dir / "known.csv"
    csv_path.write_text(
        "timestamp,meter_id,energy_kwh\n"
        "2026-06-01T12:00:00+00:00,demo-building:critical,0.5\n"
        "2026-06-01T12:15:00+00:00,demo-building:critical,0.5\n"
        "2026-06-01T12:30:00+00:00,demo-building:critical,0.5\n"
        "2026-06-01T12:45:00+00:00,demo-building:critical,0.5\n",
        encoding="utf-8",
    )
    # 2026-06-01 falls outside the auto-seeded 8-week-history + target-day window
    # (anchored on 2026-03-02), so these four rows are the only readings that date.
    client = await _connected_client(tmp_path / "t4.sqlite3", import_dir)
    try:
        imported = await client.call_tool("import_readings", {"csv_path": str(csv_path)})
        assert imported.is_error is False
        assert imported.structured_content["inserted"] == 4

        summary = await client.call_tool(
            "get_energy_summary",
            {"building_id": "demo-building", "start": "2026-06-01T12:00:00+00:00", "end": "2026-06-01T13:00:00+00:00"},
        )
        assert summary.is_error is False
        sc = summary.structured_content
        assert sc["per_circuit_kwh"]["critical"] == pytest.approx(2.0)
        assert sc["peak_demand_kw"] == pytest.approx(2.0)
        assert sc["average_demand_kw"] == pytest.approx(2.0)
    finally:
        await client.aclose()


async def test_detect_anomalies_finds_the_injected_spike_via_the_server(tmp_path):
    client = await _connected_client(tmp_path / "t5.sqlite3")
    try:
        result = await client.call_tool("detect_anomalies", {"building_id": "demo-building", "target_date": "2026-03-02"})
        assert result.is_error is False
        incidents = result.structured_content["incidents"]
        assert any(inc["meter_id"] == "demo-building:equipment" for inc in incidents)
    finally:
        await client.aclose()


async def test_optimize_schedule_returns_feasible_result_with_full_day_tariff(tmp_path):
    client = await _connected_client(tmp_path / "t6.sqlite3")
    try:
        tariff_bands = [{"start_minute": 0, "end_minute": 24 * 60, "price_per_kwh": 0.2}]
        result = await client.call_tool(
            "optimize_schedule", {"building_id": "demo-building", "date": "2026-03-02", "tariff_bands": tariff_bands}
        )
        assert result.is_error is False
        sc = result.structured_content
        assert sc["feasible"] is True
        assert set(sc["proposed"]["starts_minute"].keys()) == {"demo-building:load-1", "demo-building:load-2"}
    finally:
        await client.aclose()


async def test_simulate_outage_compares_full_building_and_critical_only(tmp_path):
    client = await _connected_client(tmp_path / "t7.sqlite3")
    try:
        result = await client.call_tool(
            "simulate_outage",
            {"building_id": "demo-building", "start": "2026-03-02T06:00:00-06:00", "horizon_hours": 6},
        )
        assert result.is_error is False
        sc = result.structured_content
        assert sc["critical_only"]["autonomy_minutes"] >= sc["full_building"]["autonomy_minutes"]
    finally:
        await client.aclose()


async def test_prepare_report_assembles_markdown_with_provenance(tmp_path):
    client = await _connected_client(tmp_path / "t8.sqlite3")
    try:
        result = await client.call_tool(
            "prepare_report",
            {
                "title": "Reporte de prueba",
                "building_id": "demo-building",
                "sections": [{"heading": "Resumen", "body_markdown": "Consumo total: 10 kWh."}],
            },
        )
        assert result.is_error is False
        markdown = result.structured_content["markdown"]
        assert "# Reporte de prueba" in markdown
        assert "semilla reproducible" in markdown
        assert "Consumo total: 10 kWh." in markdown
    finally:
        await client.aclose()
