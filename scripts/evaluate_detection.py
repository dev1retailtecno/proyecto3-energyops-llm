"""Threshold calibration on development seeds; evaluation on separate untouched seeds."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from energyops_mcp.energy import anomalies as a
from energyops_mcp.energy.datagen import generate_dataset,DEFAULT_TARGET_DAY
from energyops_mcp.energy.timeutil import from_utc_iso,to_local
from datetime import timedelta

def split(seed):
 readings=generate_dataset(seed=seed);history=[];target=[]
 for r in readings:
  if r.meter_id=='solar':continue
  row=(r.meter_id,r.timestamp_utc,r.energy_kwh)
  (target if to_local(from_utc_iso(r.timestamp_utc)).date()==DEFAULT_TARGET_DAY else history).append(row)
 return history,target

def measure(data,floor):
 a.MIN_EXCESS_KWH=floor;tp=fp=fn=tn=0
 for history,target in data:
  incidents,_=a.detect_anomalies(history,target);pred=set()
  for inc in incidents:
   t=from_utc_iso(inc.start_utc);end=from_utc_iso(inc.end_utc)
   while t<end:pred.add((inc.meter_id,t.isoformat()));t+=timedelta(minutes=15)
  truth={(m,t) for m,t,v in target if m=='equipment' and to_local(from_utc_iso(t)).hour==2 and to_local(from_utc_iso(t)).minute in [0,15]}
  universe={(m,t) for m,t,v in target};tp+=len(pred&truth);fp+=len(pred-truth);fn+=len(truth-pred);tn+=len(universe-pred-truth)
 p=tp/(tp+fp) if tp+fp else 0;r=tp/(tp+fn) if tp+fn else 0
 return {'floor_kwh':floor,'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':p,'recall':r,'f1':2*p*r/(p+r) if p+r else 0,'false_positive_rate':fp/(fp+tn) if fp+tn else 0}

def main():
 devseeds=list(range(100,110));testseeds=list(range(1000,1020));dev=[split(s) for s in devseeds];table=[measure(dev,v) for v in [.1,.15,.2,.25,.3]]
 selected=max(table,key=lambda r:(r['f1'],-r['floor_kwh']))['floor_kwh'];print('Selected from dev',selected,flush=True)
 holdout=[split(s) for s in testseeds]
 result={'development_seeds':devseeds,'test_seeds':testseeds,'unit':'meter interval, 15 minutes','truth':'Only the injected equipment spike on the target day is labelled positive. Normal stochastic excursions are negatives. Synthetic detection scenario only.','calibration':table,'selected_floor_kwh':selected,'holdout_original':measure(holdout,.1),'holdout_selected':measure(holdout,selected)}
 (ROOT/'evaluation/detection_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
