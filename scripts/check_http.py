"""Exercise the running application through HTTP; no paid model calls."""
import csv,io,json
from datetime import datetime
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def verify(name,condition):
    if not condition:raise AssertionError(name)
    checks.append({'check':name,'passed':True})
with httpx.Client(base_url='http://127.0.0.1:8765',timeout=45) as c:
    r=c.get('/health');verify('health',r.status_code==200 and r.json()['status']=='ok')
    r=c.get('/overview',params={'date':'2026-11-06','period':'day'});r.raise_for_status();v=r.json()
    verify('full November 6 day',v['selection']['readings']==576 and v['selection']['days']==1)
    r=c.get('/export.csv',params={'date':'2026-11-06','period':'day'});verify('CSV download',r.status_code==200 and 'attachment' in r.headers['content-disposition'])
    rows=list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig'))))
    verify('CSV exact rows and schema',len(rows)==576 and set(rows[0])=={'timestamp','meter_id','energy_kwh'})
    r=c.post('/analyze',json={'question':'Resume el consumo del 2026-11-06','date':'2026-11-06','task':'get_energy_summary','provider':'direct'});r.raise_for_status();summary=r.json()
    verify('direct real MCP summary',not summary['is_error'] and summary['tool']=='get_energy_summary' and 'sin LLM' in summary['mode'])
    verify('dashboard agrees with MCP',abs(v['selection']['consumption_kwh']-summary['data']['consumption_kwh'])<.01)
    verify('CSV balances with dashboard',abs(sum(float(x['energy_kwh']) for x in rows)-v['selection']['consumption_kwh']-v['selection']['generation_kwh'])<.01)
    verify('invalid CSV period helpful',c.get('/export.csv',params={'period':'bad'}).status_code==400)
    verify('foreign Origin blocked',c.post('/analyze',headers={'Origin':'https://example.invalid'},json={'question':'consumo hoy'}).status_code==403)
    verify('malformed JSON handled',c.post('/analyze',content='{').status_code==400)
    for name,q in [('multiple tasks','Optimiza horarios y además simula un apagón hoy'),('outside coverage','Resume el consumo del 2030-01-01')]:
        r=c.post('/analyze',json={'question':q,'date':'2026-11-06'});verify(name,r.status_code==200 and r.json()['tool']=='clarify' and bool(r.json().get('suggestions')))
    r=c.post('/analyze',json={'question':'Simula un apagón el 2026-11-06','date':'2026-11-06','task':'simulate_outage','provider':'direct'});verify('direct real MCP battery',r.status_code==200 and not r.json()['is_error'] and r.json()['tool']=='simulate_outage')
    for path in ['/poster.pdf','/report.pdf']:
        r=c.get(path);verify(path,r.status_code==200 and r.content.startswith(b'%PDF'))
result={'timestamp':datetime.now().astimezone().isoformat(),'scope':'Live HTTP checks, direct MCP only; no inference or production uptime claim.','passed':len(checks),'checks':checks}
(ROOT/'evaluation/http_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False))
