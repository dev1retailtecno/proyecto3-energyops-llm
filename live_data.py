"""Extended synthetic application data, separate from the original benchmark."""
import os
import sqlite3
import threading
from datetime import date, timedelta, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from energyops_mcp.energy import storage

ROOT = Path(__file__).resolve().parent
TODAY = date.fromisoformat(os.getenv('ENERGYOPS_TODAY', '2026-11-02'))
FIRST_DAY = date(2026, 1, 5)
DB_PATH = ROOT / 'dashboard.sqlite3'
_ready = False
_lock = threading.Lock()

def ensure_data():
    global _ready
    if _ready:
        return
    with _lock:
        if _ready:
            return
        conn = storage.connect(DB_PATH)
        try:
            row = conn.execute("SELECT value FROM dataset_meta WHERE key='dashboard_through'").fetchone()
            if not row or row['value'] != str(TODAY):
                storage.seed_demo_building(conn, through_date=TODAY)
                conn.execute("INSERT OR REPLACE INTO dataset_meta VALUES ('dashboard_through',?)", (str(TODAY),))
                conn.commit()
            _ready = True
        finally:
            conn.close()

def overview(selected=None, period='day'):
    ensure_data()
    day = date.fromisoformat(selected) if selected else TODAY
    if not FIRST_DAY <= day <= TODAY:
        raise ValueError(f'Elige una fecha entre {FIRST_DAY} y {TODAY}.')
    # UTC timestamps in the database are converted to Guatemala's fixed UTC-6.
    with sqlite3.connect(DB_PATH, timeout=15) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT date(r.timestamp_utc,'-6 hours') AS day,
              SUM(CASE WHEN m.kind='consumption' THEN energy_kwh ELSE 0 END) AS consumption_kwh,
              SUM(CASE WHEN m.kind='generation' THEN energy_kwh ELSE 0 END) AS generation_kwh,
              COUNT(*) AS readings
            FROM readings r JOIN meters m ON m.id=r.meter_id
            WHERE m.building_id='demo-building'
            GROUP BY day ORDER BY day
        """).fetchall()
    daily = [{**dict(r), 'consumption_kwh': round(r['consumption_kwh'], 3), 'generation_kwh': round(r['generation_kwh'], 3)} for r in rows]
    if period not in {'day','week','month'}:
        raise ValueError('Período no disponible.')
    first=day if period=='day' else max(FIRST_DAY,day-timedelta(days=6)) if period=='week' else day.replace(day=1)
    first=max(FIRST_DAY,first)
    selected_rows=[r for r in daily if str(first)<=r['day']<=str(day)]
    span=(day-first).days+1
    previous=[r for r in daily if str(first-timedelta(days=span))<=r['day']<str(first)]
    total=sum(r['consumption_kwh'] for r in selected_rows)
    previous_total=sum(r['consumption_kwh'] for r in previous)
    chosen = next(r for r in daily if r['day'] == str(day))
    prior = next((r for r in daily if r['day'] == str(day-timedelta(days=1))), None)
    return {
        'today': str(TODAY), 'first_day': str(FIRST_DAY), 'last_day': str(TODAY),
        'selected_date': str(day), 'period':period, 'source': 'Datos sintéticos reproducibles; días completos simulados, no medición en tiempo real.',
        'building': 'Edificio Demo UVG', 'readings': sum(r['readings'] for r in daily),
        'days': len(daily), 'meters': 6, 'selected': chosen,
        'change_pct': round(100*(total/previous_total-1), 2) if previous_total and len(previous)==len(selected_rows) else None,
        'selection': {'start':str(first),'end':str(day),'days':len(selected_rows),'consumption_kwh':round(total,3),'generation_kwh':round(sum(r['generation_kwh'] for r in selected_rows),3),'readings':sum(r['readings'] for r in selected_rows),'expected_readings':span*576},
        'daily': [r for r in daily if str(day-timedelta(days=29)) <= r['day'] <= str(day)],
        'month_consumption_kwh': round(sum(r['consumption_kwh'] for r in daily if r['day'][:7] == str(day)[:7] and r['day'] <= str(day)), 3),
    }

def data_bounds():
    return {'first_day': str(FIRST_DAY), 'last_day': str(TODAY), 'today': str(TODAY), 'source': 'synthetic'}
