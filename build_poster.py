"""Scientific poster generated from the recorded evaluation and demo evidence."""
import json
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
import pymupdf

ROOT=Path(__file__).resolve().parent

def main():
    s=json.loads((ROOT/'evaluation/results.json').read_text(encoding='utf-8'))['summary']
    local=json.loads((ROOT/'evaluation/results_local.json').read_text(encoding='utf-8'))['summary']
    snapshot=json.loads((ROOT/'evaluation/poster_current_snapshot.json').read_text(encoding='utf-8'))
    coverage=snapshot['overview']
    outage=snapshot['outage']['data']
    out=ROOT/'output/pdf';out.mkdir(parents=True,exist_ok=True)
    for n,file in [('Regular','segoeui.ttf'),('Bold','segoeuib.ttf')]:
        pdfmetrics.registerFont(TTFont(n,str(Path('C:/Windows/Fonts')/file)))
    W,H=1440,1000
    c=canvas.Canvas(str(out/'Poster_EnergyOps.pdf'),pagesize=(W,H))
    c.setTitle('EnergyOps - Poster científico - Proyecto 3 Deep Learning')
    ink='#142e3b';muted='#526b78';teal='#087f70';light='#e9f5f1';navy='#0b2333'
    def rect(x,y,w,h,color,r=0):
        c.setFillColor(HexColor(color))
        if r:c.roundRect(x,H-y-h,w,h,r,fill=1,stroke=0)
        else:c.rect(x,H-y-h,w,h,fill=1,stroke=0)
    def txt(t,x,y,size=15,color=ink,bold=False,width=400):
        st=ParagraphStyle('p',fontName='Bold' if bold else 'Regular',fontSize=size,leading=size*1.35,textColor=HexColor(color))
        p=Paragraph(t,st);_,h=p.wrap(width,1000);p.drawOn(c,x,H-y-h);return h
    def line(x,y,x2,y2,color='#d3e0e3'):
        c.setStrokeColor(HexColor(color));c.setLineWidth(1);c.line(x,H-y,x2,H-y2)
    def section(n,title,x,y,width=400):
        txt(n,x,y,12,teal,True,30);txt(title,x+34,y-4,22,ink,True,width-34)
    rect(0,0,W,H,'#f8fbfa')
    rect(0,0,W,202,navy)
    rect(0,0,12,202,'#46dfb7')
    txt('UVG  /  CC3092 DEEP LEARNING Y SISTEMAS INTELIGENTES',48,23,11,'#73e5c5',True,1000)
    txt('EnergyOps',46,47,61,'#ffffff',True,950)
    txt('Análisis energético con lenguaje natural y herramientas verificables',50,132,22,'#d4e8ec',False,1040)
    txt('Ian Cumes  /  Feria científica  /  Actualizado al 2 de noviembre de 2026',50,173,12,'#91b7c2',False,1000)
    txt(f"{round(s['route_accuracy']*s['n'])}/{s['n']}",1136,42,48,'#73e5c5',True,270)
    txt('selecciones correctas de Claude<br/>en el benchmark original',1140,112,13,'#d4e8ec',False,250)
    # Upper row: the problem, comparative evidence and a concrete decisión.
    section('01','Problema y propuesta',48,237,375)
    txt('Un administrador necesita entender su consumo, investigar picos y evaluar el respaldo de un edificio.',48,280,17,ink,False,360)
    txt('EnergyOps convierte una pregunta en una operación trazable: el LLM interpreta y el motor calcula.',48,373,17,ink,True,360)
    txt('Cobertura ampliada de la aplicación',48,467,12,teal,True,360)
    txt(f"{coverage['readings']:,}",48,490,37,ink,True,360)
    txt(f"lecturas sintéticas / {coverage['days']} días / 6 medidores<br/>05 ene - 02 nov 2026 / intervalos de 15 min<br/>SQLite / semilla 1337 / hora de Guatemala<br/>Días completos simulados, sin sensores reales.",48,544,13,muted,False,370)
    line(438,240,438,599)
    section('02','Evaluación comparativa',472,237,470)
    txt('Benchmark original: 2 de marzo / 32,832 lecturas',472,275,11,muted,False,460)
    txt('Exactitud al seleccionar la herramienta (%)',472,296,13,muted,False,460)
    bars=[('Palabras clave',s['baseline_accuracy'],s['baseline_macro_f1'],'#9aaeb8'),('Qwen3 local',local['route_accuracy'],local['macro_f1'],'#44ad9f'),('Claude + MCP',s['route_accuracy'],s['macro_f1'],teal)]
    y=326
    for label,value,f1,color in bars:
        txt(label,472,y,15,ink,True,260)
        txt(f'{value:.1%}',826,y-2,18,color,True,110)
        rect(472,y+29,450,15,'#e1e9ea',4);rect(472,y+29,450*value,15,color,4)
        txt(f'F1 macro: {f1:.3f}',472,y+49,11,muted,False,450)
        y+=81
    txt('30 casos sintéticos, 5 por cada una de 6 intenciones.<br/>Claude: campos de argumentos 100%; MCP sin error 25/25.<br/>Qwen3 usa extracción por reglas; Claude, tool calling.<br/>Comparación de pipelines, no de modelos aislados.',472,569,11.5,muted,False,470)
    rect(978,236,414,367,light,14)
    txt('03   UNA DECISIÓN CONCRETA',1002,258,12,teal,True,365)
    txt('¿Qué mantengo encendido<br/>durante un apagón?',1002,294,23,ink,True,365)
    txt(f"{outage['full_building']['autonomy_minutes']} min",1002,374,34,ink,True,160)
    txt(f"{outage['critical_only']['autonomy_minutes']} min",1190,374,34,teal,True,190)
    txt('edificio completo',1002,423,13,muted,False,175)
    txt('solo cargas críticas',1190,423,13,muted,False,180)
    line(1002,458,1368,458,'#bddbd3')
    hours=outage['critical_only']['autonomy_minutes']/60
    txt(f'El edificio supera la potencia disponible desde el primer intervalo. Priorizar cargas críticas permite {hours:g} horas de respaldo continuo.',1002,478,15,ink,False,365)
    txt(f"Escenario simulado: {snapshot['scenario_date']}, 00:00, horizonte 24 h.",1002,566,10,muted,False,365)
    # Architecture diagram as a single horizontal reading path.
    section('04','Pipeline: de la pregunta al resultado',48,647,1200)
    steps=[('01','Entrada','Web y calendario.<br/>Preguntas o análisis directo.'),('02','Interpretación','Claude / Qwen3.<br/>Respaldo explícito por reglas.'),('03','Validación + MCP','JSON Schema.<br/>JSON-RPC 2.0 por stdio.'),('04','Datos + algoritmos','SQLite, mediana y MAD,<br/>horarios y batería.'),('05','Salida verificable','Plantillas y gráficas.<br/>Cifras y modo visibles.')]
    for i,(num,title,body) in enumerate(steps):
        x=48+i*273
        rect(x,691,250,109,'#ffffff',8)
        rect(x,691,250,3,teal)
        txt(num,x+14,707,11,teal,True,28);txt(title,x+43,704,17,ink,True,200)
        txt(body,x+14,742,13,muted,False,224)
        if i<4:
            line(x+255,744,x+268,744,teal);line(x+268,744,x+264,740,teal);line(x+268,744,x+264,748,teal)
    # Lower row: method, operational measures and limitations.
    section('05','Adaptación y continuidad',48,837,670)
    txt('Prompting y herramientas, sin fine-tuning ni RAG. Recuperación Claude / Qwen3 / reglas explícitas; consultas directas sin LLM. Reconexión MCP y resultados guardados identificados.',48,876,13,muted,False,650)
    txt(f"<b>{s['mean_e2e_latency_s']:.2f} s</b> y <b>US${s['estimated_cost_usd']/s['n']:.4f}</b> por consulta: benchmark original de Claude*",48,934,13,teal,False,660)
    section('06','Alcance de la evidencia',750,837,642)
    txt('Muestra sintética pequeña, sin validación humana independiente. Las métricas no evalúan todo el intervalo ampliado ni los modos de continuidad. No garantizan disponibilidad. Tarifas ficticias; posibles falsas alertas. Sin tasa general de alucinación medida.',750,876,13,muted,False,642)
    txt('*Excluye conexión inicial, descubrimiento y renderizado. Fuentes: modelcontextprotocol.io / platform.claude.com/docs / huggingface.co/Qwen/Qwen3-0.6B-GGUF. Motor reutilizado: energyops-mcp (MIT).',48,976,8,muted,False,1344)
    c.save()
    with pymupdf.open(out/'Poster_EnergyOps.pdf') as doc:
        doc[0].get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save(out/'Poster_EnergyOps.png')
    (ROOT/'poster.html').write_text("""<!doctype html><html lang="es"><meta charset="utf-8"><title>EnergyOps · Poster científico</title><style>body{margin:0;background:#0b2333;color:white;font:16px Segoe UI}header{padding:12px 25px}a{color:#73e5c5;margin-right:30px}iframe{width:100%;height:calc(100vh - 50px);border:0}</style><header><a href="/">Abrir demostración</a><a href="/poster.pdf">Descargar / imprimir poster PDF</a>Feria cientifica · UVG · Deep Learning</header><iframe title="Poster científico EnergyOps" src="/poster.pdf#view=FitH"></iframe></html>""",encoding='utf-8')
    print('Poster actualizado: PDF y PNG.')
if __name__=='__main__':main()
