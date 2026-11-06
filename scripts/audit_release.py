"""Reproducible data-quality and numerical evidence for the release."""
import asyncio,json,sqlite3,sys,hashlib,platform,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import app
from live_data import DB_PATH,overview,TODAY
async def main():
 view=overview();c=await app.connect(extended=True);outputs={}
 try:
  for name,q in [('get_energy_summary',f'Resume consumo del {TODAY}'),('detect_anomalies','Detecta anomalias del 2026-03-02'),('optimize_schedule',f'Optimiza horarios del {TODAY}'),('simulate_outage',f'Simula apagon del {TODAY} a las 00:00 por 24 horas')]:
   r=await c.call_tool(name,app.extract_arguments(q,name,str(TODAY)));assert not r.is_error;outputs[name]={'data':app.compact(r.structured_content),'answer':app.display_result(name,r)}
 finally:await c.aclose()
 with sqlite3.connect(DB_PATH) as db:
  rows=db.execute('SELECT COUNT(*),MIN(energy_kwh),MAX(energy_kwh),SUM(energy_kwh<0),COUNT(DISTINCT meter_id) FROM readings').fetchone()
  dup=db.execute('SELECT COUNT(*) FROM (SELECT meter_id,timestamp_utc,COUNT(*) n FROM readings GROUP BY 1,2 HAVING n>1)').fetchone()[0]
  days=db.execute("SELECT date(timestamp_utc,'-6 hours'),COUNT(*) FROM readings GROUP BY 1").fetchall()
  dayrows=db.execute("SELECT m.circuit,SUM(r.energy_kwh) FROM readings r JOIN meters m ON m.id=r.meter_id WHERE date(timestamp_utc,'-6 hours')=? GROUP BY 1",(str(TODAY),)).fetchall()
 data={'as_of':str(TODAY),'overview':view,'quality':{'rows':rows[0],'minimum_kwh':rows[1],'maximum_kwh':rows[2],'negative_values':rows[3],'meters':rows[4],'duplicate_keys':dup,'complete_days':sum(n==576 for _,n in days),'total_days':len(days),'missing_intervals':sum(max(0,576-n) for _,n in days)},'today_per_circuit':dict(dayrows),'outputs':outputs,'environment':{'python':platform.python_version(),'platform':platform.platform(),'processor':platform.processor()},'source_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['app.py','query_understanding.py','live_data.py','energyops_mcp/energy/anomalies.py']}}
 (ROOT/'evaluation/release_audit.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data['quality'],indent=2))
if __name__=='__main__':asyncio.run(main())
