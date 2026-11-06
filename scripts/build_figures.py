import json,sqlite3,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'output/figures';out.mkdir(exist_ok=True,parents=True)
r=json.loads((ROOT/'evaluation/final_results.json').read_text(encoding='utf-8'));d=json.loads((ROOT/'evaluation/detection_results.json').read_text());a=json.loads((ROOT/'evaluation/release_audit.json').read_text(encoding='utf-8'))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
colors=['#9aaeb8','#6688a1','#45aa9b','#087f70'];labels=['Palabras clave','Reglas','Qwen3 local','Claude Haiku 4.5'];values=[r['summary'][k]['route_accuracy']*100 for k in ['keyword_baseline','rules_baseline','local','claude']]
f,ax=plt.subplots(figsize=(9,3.5));bars=ax.barh(labels,values,color=colors,height=.58);ax.invert_yaxis();ax.set_xlim(0,110);ax.set_xlabel('Exactitud de selección de herramienta (%)');ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
for b,v in zip(bars,values):ax.text(v+1,b.get_y()+b.get_height()/2,f'{v:.1f}%',va='center',fontweight='bold')
f.tight_layout();f.savefig(out/'comparacion_modelos.png',dpi=240);plt.close(f)
labels2=['Aclarar','Anomalías','Consumo','Edificios','Horarios','Apagón'];keys=['clarify','detect_anomalies','get_energy_summary','list_buildings','optimize_schedule','simulate_outage'];matrix=[[0]*6 for _ in keys]
for c in r['cases']:
 if c['provider']=='claude' and c['predicted_tool'] in keys:matrix[keys.index(c['expected_tool'])][keys.index(c['predicted_tool'])]+=1
f,ax=plt.subplots(figsize=(6.8,4.5));im=ax.imshow(matrix,cmap='Greens',vmin=0,vmax=10);ax.set_xticks(range(6),labels2,rotation=30,ha='right');ax.set_yticks(range(6),labels2);ax.set_xlabel('Predicción');ax.set_ylabel('Referencia')
for i in range(6):
 for j in range(6):ax.text(j,i,matrix[i][j],ha='center',va='center',color='white' if matrix[i][j]>6 else '#183746')
f.tight_layout();f.savefig(out/'matriz_claude.png',dpi=240);plt.close(f)
f,ax=plt.subplots(figsize=(8,3));ax.plot([x['floor_kwh'] for x in d['calibration']],[x['f1'] for x in d['calibration']],marker='o',color='#087f70');ax.axvline(d['selected_floor_kwh'],color='#a77935',ls='--',label='Umbral seleccionado con desarrollo');ax.set_xlabel('Piso absoluto de desviación (kWh por intervalo)');ax.set_ylabel('F1 en desarrollo');ax.set_ylim(.55,1.06);ax.grid(alpha=.2);ax.legend(loc='lower right');f.tight_layout();f.savefig(out/'calibracion_anomalias.png',dpi=240);plt.close(f)
# Architecture with larger labels for print readability.
f,ax=plt.subplots(figsize=(7.8,5.5));ax.set_xlim(0,7.8);ax.set_ylim(0,5.5);ax.axis('off')
nodes=[(.1,3.85,'Interfaz web','Pregunta y calendario'),(2.75,3.85,'Normalización y LLM','Tokens y contexto\nClaude / Qwen3'),(5.4,3.85,'Validación','JSON Schema\nfechas y alcance'),(5.4,2.05,'Cliente MCP','JSON-RPC por stdio'),(2.75,2.05,'Servidor y SQLite','Lecturas y algoritmos'),(.1,2.05,'Posprocesamiento','Plantillas y trazabilidad'),(.1,.25,'Salida en la web','Cifras, JSON y CSV')]
for x,y,title,body in nodes:
 ax.add_patch(FancyBboxPatch((x,y),2.25,1.05,boxstyle='round,pad=.04',fc='#eef6f3',ec='#6aa99a'));ax.text(x+1.125,y+.76,title,ha='center',va='center',weight='bold',fontsize=10);ax.text(x+1.125,y+.32,body,ha='center',va='center',fontsize=9)
for p1,p2 in [((2.38,4.38),(2.7,4.38)),((5.03,4.38),(5.35,4.38)),((6.52,3.8),(6.52,3.15)),((5.35,2.58),(5.03,2.58)),((2.7,2.58),(2.38,2.58)),((1.22,2),(1.22,1.35))]:ax.add_patch(FancyArrowPatch(p1,p2,arrowstyle='-|>',mutation_scale=15,color='#087f70'))
ax.annotate('Análisis directo sin LLM',xy=(6.52,4.95),xytext=(1.2,5.2),arrowprops={'arrowstyle':'->','linestyle':'--','color':'#617c8b'},fontsize=9,color='#526d7e');ax.text(2.8,.65,'Continuidad: Claude → Qwen3 → reglas.\nLos resultados guardados se identifican.',fontsize=9,color='#526d7e')
f.tight_layout();f.savefig(out/'arquitectura.png',dpi=260,bbox_inches='tight');plt.close(f)
with sqlite3.connect(ROOT/'dashboard.sqlite3') as db:
 rows=db.execute("SELECT date(r.timestamp_utc,'-6 hours'),SUM(CASE WHEN m.kind='consumption' THEN energy_kwh ELSE 0 END),SUM(CASE WHEN m.kind='generation' THEN energy_kwh ELSE 0 END) FROM readings r JOIN meters m ON m.id=r.meter_id GROUP BY 1 ORDER BY 1").fetchall()
f,ax=plt.subplots(figsize=(9,3));ax.plot([x[0] for x in rows],[x[1] for x in rows],color='#087f70',lw=.8,label='Consumo');ax.plot([x[0] for x in rows],[x[2] for x in rows],color='#b28742',lw=.8,label='Solar');idx=list(range(0,len(rows),50));ax.set_xticks(idx,[rows[i][0] for i in idx],fontsize=8);ax.set_ylabel('Energía diaria (kWh)');ax.legend(ncol=2);ax.grid(alpha=.15);f.tight_layout();f.savefig(out/'serie_datos.png',dpi=240);plt.close(f)
print('5 figuras científicas generadas.')
