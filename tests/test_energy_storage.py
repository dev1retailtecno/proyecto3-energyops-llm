import pytest

from energyops_mcp.energy.storage import (
    ValidationError,
    connect,
    export_csv,
    import_csv,
    list_buildings,
    seed_demo_building,
)


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "test.sqlite3")
    yield connection
    connection.close()


def test_seed_demo_building_is_idempotent(conn):
    result1 = seed_demo_building(conn, seed=42)
    result2 = seed_demo_building(conn, seed=42)

    assert result1["readings_inserted"] > 0
    assert result2["readings_inserted"] == 0  # second call inserts nothing new

    buildings = list_buildings(conn)
    assert len(buildings) == 1
    assert len(buildings[0]["meters"]) == 6  # 5 consumption circuits + 1 solar meter


def test_csv_export_then_import_round_trip_is_idempotent(conn, tmp_path):
    seed_demo_building(conn, seed=1)
    csv_path = tmp_path / "export.csv"
    exported = export_csv(conn, csv_path, "demo-building")
    assert exported > 0

    result = import_csv(conn, csv_path)

    assert result["inserted"] == 0  # every row was already present
    assert result["duplicates_skipped"] == exported
    assert result["unknown_meters"] == []
    assert result["invalid_row_count"] == 0


def test_import_csv_rejects_unknown_meter_and_bad_rows(conn, tmp_path):
    seed_demo_building(conn, seed=1)
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text(
        "timestamp,meter_id,energy_kwh\n"
        "2026-01-01T00:00:00+00:00,does-not-exist,1.0\n"
        "not-a-date,demo-building:lighting,1.0\n"
        "2026-01-01T00:15:00+00:00,demo-building:lighting,not-a-number\n",
        encoding="utf-8",
    )

    result = import_csv(conn, csv_path)

    assert result["inserted"] == 0
    assert result["unknown_meters"] == ["does-not-exist"]
    assert result["invalid_row_count"] == 3


def test_import_csv_wrong_header_raises_validation_error(conn, tmp_path):
    csv_path = tmp_path / "wrong.csv"
    csv_path.write_text("time,meter,kwh\n2026-01-01T00:00:00+00:00,x,1.0\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        import_csv(conn, csv_path)


def test_import_csv_missing_file_raises_validation_error(conn, tmp_path):
    with pytest.raises(ValidationError):
        import_csv(conn, tmp_path / "does-not-exist.csv")
