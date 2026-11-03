"""Scientific poster PDF and screen HTML from measured results."""
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
    out=ROOT/'output/pdf';out.mkdir(parents=True,exist_ok=True)
    for n,file in [('Regular','segoeui.ttf'),('Bold','segoeuib.ttf')]:pdfmetrics.registerFont(TTFont(n,str(Path('C:/Windows/Fonts')/file)))
    W,H=1440,960
    c=canvas.Canvas(str(out/'Poster_EnergyOps.pdf'),pagesize=(W,H))
    c.setTitle('EnergyOps - Póster científico - Proyecto 3 Deep Learning')
    c.setFillColor(HexColor('#0b1422'));c.rect(0,0,W,H,fill=1,stroke=0)
    def txt(text,x,y,size=15,color='#dce8f3',bold=False,width=410):
        style=ParagraphStyle('p',fontName='Bold' if bold else 'Regular',fontSize=size,leading=size*1.4,textColor=HexColor(color))
        p=Paragraph(text,style);_,h=p.wrap(width,800);p.drawOn(c,x,H-y-h);return h
    txt('UVG / CC3092 DEEP LEARNING Y SISTEMAS INTELIGENTES',48,28,12,'#6ce4c2',True,1200)
    txt('EnergyOps',48,62,58,'#ffffff',True,1200)
    txt('Lenguaje natural para analizar consumo, ahorro y respaldo energético',50,145,25,'#c7d9eb',False,1300)
    txt('Ian Cumes · Feria científica · 2 de noviembre de 2026',50,188,14,'#8daac3',False,1300)
    c.setStrokeColor(HexColor('#355065'));c.line(48,H-228,W-48,H-228)
    xs=[50,515,980];cw=410
    def heading(t,col,y):return txt(t,xs[col],y,21,'#6ce4c2',True,cw)
    heading('01  Problema y usuario',0,253)
    txt('Un administrador de edificios necesita identificar gastos inusuales y evaluar decisiones operativas. Leer series de medidores y ejecutar cálculos manuales exige tiempo y conocimientos técnicos.',xs[0],296,width=cw)
    txt('<b>Propuesta:</b> preguntar en español y recibir un resultado trazable. El LLM selecciona una herramienta. El motor energético calcula las cifras.',xs[0],423,width=cw)
    heading('02  Datos y método',0,535)
    txt('<b>32,832 lecturas sintéticas</b> reproducibles, semilla 1337. Ocho semanas de historia y un día objetivo. Cinco circuitos de consumo y un medidor solar, cada 15 minutos. SQLite conserva fechas UTC y análisis en hora de Guatemala.',xs[0],580,width=cw)
    txt('<b>Anomalías:</b> mediana histórica y MAD por horario y tipo de día.<br/><b>Horarios:</b> búsqueda de combinaciones en intervalos de 15 min, con límites de carga.<br/><b>Apagón:</b> balance batería + solar, reserva y eficiencias.',xs[0],724,width=cw)
    heading('03  Pipeline completo',1,253)
    steps=[('1  Pregunta del usuario','Web local en español. Una tarea por consulta.'),('2  Claude Haiku 4.5','Tokenización del proveedor. Prompt + esquemas. Selecciona herramienta y argumentos JSON.'),('3  Validación y MCP','JSON Schema valida parámetros. JSON-RPC 2.0 / stdio invoca el servidor local.'),('4  Datos y cálculo','SQLite entrega lecturas. Algoritmos calculan consumo, incidentes, horarios o autonomía.'),('5  Resultado auditable','Texto determinista y JSON visibles. No hay una segunda generación de cifras por el LLM.')]
    y=301
    for title,body in steps:
        txt(title,xs[1],y,17,'#ffffff',True,cw);txt(body,xs[1],y+29,14,width=cw)
        if title != steps[-1][0]:
            c.setStrokeColor(HexColor('#6ce4c2')); c.setLineWidth(1.8)
            ax=xs[1]+200; ay=H-y-86
            c.line(ax,ay,ax,ay-12);c.line(ax,ay-12,ax-4,ay-7);c.line(ax,ay-12,ax+4,ay-7)
        y+=104
    txt('<b>Adaptación:</b> prompting + herramientas, sin fine-tuning ni RAG. Qwen3 0.6B Q8_0 funciona como respaldo local de clasificación, con extracción de argumentos por reglas.',xs[1],830,13,'#a9c0d3',False,cw)
    heading('04  Resultados medidos',2,253)
    rows=[('Sistema','Exactitud','F1 macro'),('Palabras clave',f"{s['baseline_accuracy']:.1%}",f"{s['baseline_macro_f1']:.3f}"),('Qwen3 local',f"{local['route_accuracy']:.1%}",f"{local['macro_f1']:.3f}"),('Claude + MCP',f"{s['route_accuracy']:.1%}",f"{s['macro_f1']:.3f}")]
    y=302
    for i,row in enumerate(rows):
        for xx,value in zip([xs[2],xs[2]+208,xs[2]+325],row):txt(value,xx,y,14,'#6ce4c2' if i==3 else '#dce8f3',i in [0,3],200)
        y+=40
    txt(f"<b>{s['n']} casos</b>, 5 por cada una de 6 intenciones. Referencias definidas antes de la prueba. Exactitud de argumentos: <b>{s['argument_accuracy']:.1%}</b>.<br/>Ejecuciones MCP sin error: <b>{s['mcp_successes']}/{s['mcp_attempts']}</b>.",xs[2],480,15,width=cw)
    txt(f"Latencia media observada: <b>{s['mean_e2e_latency_s']:.2f} s</b>.<br/>Tokens Claude en evaluación: <b>{s['input_tokens']+s['output_tokens']:,}</b>.<br/>Costo API estimado por consulta: <b>US${s['estimated_cost_usd']/s['n']:.4f}</b>.",xs[2],603,15,width=cw)
    heading('05  Alcance y limitaciones',2,720)
    txt('Muestra pequeña y sintética, sin validación humana independiente. Exactitud de herramienta no equivale a calidad total. No se midió una tasa general de alucinación. Las tarifas son ficticias y los resultados no certifican una instalación real.',xs[2],765,14,width=cw)
    txt('Código reutilizado: energyops-mcp (MIT). Modelos: Claude Haiku 4.5 / Qwen3-0.6B (Apache 2.0). Fuentes: modelcontextprotocol.io · platform.claude.com/docs · huggingface.co/Qwen/Qwen3-0.6B-GGUF',50,924,10,'#89a4bb',False,1340)
    c.save()
    d=pymupdf.open(out/'Poster_EnergyOps.pdf');p=d[0];pix=p.get_pixmap(matrix=pymupdf.Matrix(1.2,1.2));pix.save(out/'Poster_EnergyOps.png')
    # Screen poster uses the same verified PDF, with browser-native zoom and printing.
    (ROOT/'poster.html').write_text('''<!doctype html><html lang="es"><meta charset="utf-8"><title>EnergyOps · Póster científico</title><style>body{margin:0;background:#0b1422;color:white;font:16px Segoe UI}header{padding:12px 25px}a{color:#6ce4c2;margin-right:30px}iframe{width:100%;height:calc(100vh - 50px);border:0}</style><header><a href="/">Abrir demostración</a><a href="/poster.pdf">Descargar / imprimir póster PDF</a>Feria científica · UVG · Deep Learning</header><iframe title="Póster científico EnergyOps" src="/poster.pdf#view=FitH"></iframe></html>''',encoding='utf-8')
    print('Poster PDF y PNG listos.')
if __name__=='__main__':main()
