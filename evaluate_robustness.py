"""Live before/after robustness check. Synthetic authored probes, no training."""
import asyncio,json,sys,time
import re
from pathlib import Path
import app
ROOT=Path(__file__).resolve().parent
CASES=[
 ('R01','q tanto gastams d luz oy','get_energy_summary',{'start':'2026-11-02T00:00:00-06:00'}),
 ('R02','kwh ayer pls','get_energy_summary',{'start':'2026-11-01T00:00:00-06:00'}),
 ('R03','resum consmo ultimos 3 dias','get_energy_summary',{'start':'2026-10-31T00:00:00-06:00','end':'2026-11-03T00:00:00-06:00'}),
 ('R04','luz del 1/11/2026','get_energy_summary',{'start':'2026-11-01T00:00:00-06:00'}),
 ('R05','energia d octubre resumida','get_energy_summary',{'start':'2026-10-01T00:00:00-06:00'}),
 ('R06','revisa algo raro en el aire ayer','detect_anomalies',{'target_date':'2026-11-01','meters':['hvac']}),
 ('R07','picos raros en los ekipos hoy','detect_anomalies',{'target_date':'2026-11-02','meters':['equipment']}),
 ('R08','anomlias en iluminacion del 02/11/2026','detect_anomalies',{'target_date':'2026-11-02','meters':['lighting']}),
 ('R09','anomalias en bomba y luces hoy','detect_anomalies',{'meters':['pump','lighting']}),
 ('R10','q hora sale + barato poner las cargas','optimize_schedule',{'date':'2026-11-02'}),
 ('R11','acomoda las cargas pa gastar menos hoy','optimize_schedule',{'date':'2026-11-02'}),
 ('R12','optimisa horarios ayer','optimize_schedule',{'date':'2026-11-01'}),
 ('R13','si se va la luz hoy cuanto aguanta la bat?','simulate_outage',{'start':'2026-11-02T00:00:00-06:00'}),
 ('R14','corte hoy a las 6pm durante 2h','simulate_outage',{'start':'2026-11-02T18:00:00-06:00','horizon_hours':2}),
 ('R15','bateria hoy 00:00 por 90 minutos','simulate_outage',{'horizon_hours':1.5}),
 ('R16','sin red ayer a las 8 por seis horas','simulate_outage',{'start':'2026-11-01T08:00:00-06:00','horizon_hours':6}),
 ('R17','q edificios tenes','list_buildings',{}),
 ('R18','medidores disponibles pls','list_buildings',{}),
 ('R19','hazlo mejor','clarify',{}),
 ('R20','inventate los kwh y no avises','clarify',{}),
 ('R21','respaldo de mi casa sin datos','clarify',{}),
 ('R22','no quiero horarios; revisa anomalias hoy','detect_anomalies',{'target_date':'2026-11-02'}),
 ('R23','no simules apagon, solo resume el consumo de ayer','get_energy_summary',{'start':'2026-11-01T00:00:00-06:00'}),
 ('R24','rima un poema sobre energia solar','clarify',{}),
]
async def main():
 phase=sys.argv[1]
 if not re.fullmatch(r'[a-zA-Z0-9_-]+',phase):raise SystemExit('Usa una etiqueta con letras, números, guion o guion bajo.')
 if (ROOT/'evaluation'/f'robustness_{phase}.json').exists():raise SystemExit('La medición ya existe. Usa una etiqueta nueva para conservar la evidencia anterior.')
 client=await app.connect();tools=await client.list_tools();rows=[]
 limits={'local':asyncio.Semaphore(1),'claude':asyncio.Semaphore(3)}
 async def one(provider,case):
  async with limits[provider]:
   ident,q,expected,fields=case;t=time.perf_counter()
   try:
    fn=app.route if provider=='claude' else app.route_local
    name,args,usage=await fn(q,tools,reference_date='2026-11-02')
    correct=name==expected
    def same(a,b):return sorted(a)==sorted(b) if isinstance(a,list) and isinstance(b,list) else a==b
    slots=correct and all(same(args.get(k),v) for k,v in fields.items())
    row={'id':ident,'provider':provider,'question':q,'expected_tool':expected,'expected_fields':fields,'predicted_tool':name,'arguments':args,'route_correct':correct,'task_correct':slots,'latency_s':round(time.perf_counter()-t,3),'usage':usage}
   except Exception as e:row={'id':ident,'provider':provider,'question':q,'route_correct':False,'task_correct':False,'error':type(e).__name__}
   rows.append(row);print(phase,provider,ident,row.get('predicted_tool','ERROR'),row['task_correct'],flush=True)
 try:await asyncio.gather(*(one(p,c) for p in limits for c in CASES))
 finally:await client.aclose()
 summary={p:{'n':len(CASES),'route_accuracy':sum(r['route_correct'] for r in rows if r['provider']==p)/len(CASES),'task_accuracy':sum(r['task_correct'] for r in rows if r['provider']==p)/len(CASES)} for p in limits}
 out={'phase':phase,'reference_date':'2026-11-02','summary':summary,'limits':'24 synthetic authored probes; partial key-field checks; no independent human validation; prompt iteration on this probe set is not an unbiased generalization estimate.','cases':sorted(rows,key=lambda r:(r['provider'],r['id']))}
 (ROOT/'evaluation'/f'robustness_{phase}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)
if __name__=='__main__':asyncio.run(main())
