"""Frozen-set evaluation, raw vs reviewed pipeline, deterministic baselines and real MCP."""
import asyncio,json,hashlib,math,statistics,time,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import app
from evaluate import baseline


def correct(name,args,case):
 if name!=case['expected_tool']:return False
 for k,value in case['expected_fields'].items():
  got=args.get(k)
  if isinstance(value,list):
   if not isinstance(got,list) or sorted(value)!=sorted(got):return False
  elif got!=value:return False
 return True


def metrics(rows,key,slot=None):
 labels=sorted({r['expected_tool'] for r in rows});details=[]
 for label in labels:
  tp=sum(r[key]==label and r['expected_tool']==label for r in rows);fp=sum(r[key]==label and r['expected_tool']!=label for r in rows);fn=sum(r[key]!=label and r['expected_tool']==label for r in rows)
  p=tp/(tp+fp) if tp+fp else 0;rec=tp/(tp+fn) if tp+fn else 0
  details.append({'class':label,'precision':p,'recall':rec,'f1':2*p*rec/(p+rec) if p+rec else 0,'support':sum(r['expected_tool']==label for r in rows)})
 n=len(rows);acc=sum(r[key]==r['expected_tool'] for r in rows)/n;z=1.96;den=1+z*z/n;center=(acc+z*z/(2*n))/den;half=z*math.sqrt(acc*(1-acc)/n+z*z/(4*n*n))/den
 return {'n':n,'route_accuracy':acc,'route_95ci':[center-half,center+half],'task_accuracy':sum(r.get(slot,False) for r in rows)/n if slot else None,'macro_precision':statistics.mean(x['precision'] for x in details),'macro_recall':statistics.mean(x['recall'] for x in details),'macro_f1':statistics.mean(x['f1'] for x in details),'per_class':details}


async def main():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--output',default='evaluation/final_results.json');options=parser.parse_args()
 output=ROOT/options.output;output.parent.mkdir(parents=True,exist_ok=True)
 if output.exists():raise SystemExit('Final results already exist; preserve the frozen measurement.')
 path=ROOT/'evaluation/final_cases.json';dataset=json.loads(path.read_text(encoding='utf-8'));cases=dataset['cases'];client=await app.connect(extended=True);tools=await client.list_tools();rows=[]
 api_limits={'claude':asyncio.Semaphore(3),'local':asyncio.Semaphore(1)}
 async def one(provider,case):
  async with api_limits[provider]:
   t=time.perf_counter();base=baseline(case['question']);rule,ruleargs=app.rule_route(case['question'],dataset['reference_date'])
   row={**case,'provider':provider,'baseline_tool':base,'rules_tool':rule,'rules_correct':correct(rule,ruleargs,case)}
   try:
    fn=app.route if provider=='claude' else app.route_local
    name,args,usage=await fn(case['question'],tools,reference_date=dataset['reference_date']);raw=usage.get('raw_prediction',{'tool':name,'arguments':args})
    row.update(predicted_tool=name,arguments=args,raw_tool=raw['tool'],raw_arguments=raw['arguments'],usage=usage,task_correct=correct(name,args,case),raw_correct=correct(raw['tool'],raw['arguments'],case),llm_latency_s=round(time.perf_counter()-t,4))
   except Exception as e:row.update(predicted_tool='ERROR',raw_tool='ERROR',task_correct=False,raw_correct=False,error_type=type(e).__name__,llm_latency_s=round(time.perf_counter()-t,4),usage={})
   print(provider,case['id'],row['predicted_tool'],row['task_correct'],flush=True);return row
 try:
  rows=await asyncio.gather(*(one(p,c) for p in api_limits for c in cases))
  for row in rows:
   if row['predicted_tool'] not in app.ALLOWED:continue
   t=time.perf_counter()
   try:
    app.check_window(row['predicted_tool'],row['arguments']);result=await client.call_tool(row['predicted_tool'],row['arguments']);row['mcp_success']=not result.is_error;row['output']=app.compact(result.structured_content or {});row['answer']=app.display_result(row['predicted_tool'],result)
   except Exception as e:row['mcp_success']=False;row['mcp_error_type']=type(e).__name__
   row['mcp_latency_s']=round(time.perf_counter()-t,4)
 finally:await client.aclose()
 summary={}
 for p in api_limits:
  subset=[r for r in rows if r['provider']==p];usage_in=sum(r['usage'].get('input_tokens',0) for r in subset);usage_out=sum(r['usage'].get('output_tokens',0) for r in subset);latencies=[r['llm_latency_s']+r.get('mcp_latency_s',0) for r in subset]
  summary[p]={**metrics(subset,'predicted_tool','task_correct'),'raw':metrics(subset,'raw_tool','raw_correct'),'mean_llm_latency_s':statistics.mean(r['llm_latency_s'] for r in subset),'mean_llm_mcp_s':statistics.mean(latencies),'p95_llm_mcp_s':sorted(latencies)[math.ceil(.95*len(latencies))-1],'input_tokens':usage_in,'output_tokens':usage_out,'estimated_cost_usd':(usage_in+5*usage_out)/1e6 if p=='claude' else 0,'mcp_attempts':sum('mcp_success' in r for r in subset),'mcp_successes':sum(r.get('mcp_success',False) for r in subset),'end_to_end_task_accuracy':sum(r['task_correct'] and (r['predicted_tool']=='clarify' or r.get('mcp_success')) for r in subset)/len(subset)}
 summary['keyword_baseline']=metrics([r for r in rows if r['provider']=='claude'],'baseline_tool')
 summary['rules_baseline']=metrics([r for r in rows if r['provider']=='claude'],'rules_tool','rules_correct')
 result={'reference_date':dataset['reference_date'],'dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'scope':'Frozen authored synthetic holdout; no independent human label validation. Raw and reviewed use the same model call. Latency excludes startup, discovery and browser. Claude concurrent=3, local sequential=1; throughput conditions differ. Wilson intervals descriptive only.','summary':summary,'cases':rows}
 output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':asyncio.run(main())
