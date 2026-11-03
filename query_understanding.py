"""Conservative normalization and auditable intent hints; never modifies measurements."""
import re
import unicodedata
from datetime import datetime

TYPO_MAP={'q':'que','d':'de','pa':'para','pls':'por favor','oy':'hoy','gastams':'gastamos','consmo':'consumo','consumoo':'consumo','semna':'semana','anomlias':'anomalias','anomalias':'anomalias','ekipos':'equipos','optimisa':'optimiza','optimisar':'optimizar','bat':'bateria','batt':'bateria'}
NUMBERS={'una':1,'un':1,'dos':2,'tres':3,'cuatro':4,'cinco':5,'seis':6,'siete':7,'ocho':8,'nueve':9,'diez':10,'doce':12,'veinticuatro':24}

def normalize_query(text):
    q=''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')
    q=re.sub(r'\b[a-z]+\b',lambda m:TYPO_MAP.get(m[0],m[0]),q)
    q=re.sub(r'(?<!\w)\+(?=\s*barat)', 'mas ',q)
    def local_date(m):
        try:return datetime.strptime(m[0],'%d/%m/%Y').date().isoformat()
        except ValueError:raise ValueError('Esa fecha no es válida. Usa día/mes/año o el calendario; no sustituí la fecha solicitada.') from None
    q=re.sub(r'\b\d{1,2}/\d{1,2}/20\d{2}\b',local_date,q)
    def clock(m):
        h=int(m[1]);minute=int(m[2] or 0)
        if not 1<=h<=12 or minute>59:return m[0]
        h=h%12+(12 if m[3].startswith('p') else 0)
        return f'{h:02}:{minute:02}'
    q=re.sub(r'\b(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b',clock,q)
    q=re.sub(r'\b(\d+(?:\.\d+)?)\s*h(?:rs?)?\b',r'\1 horas',q)
    q=re.sub(r'\b(por|durante)\s+('+'|'.join(NUMBERS)+r')\s+(horas?|minutos?)\b',lambda m:f'{m[1]} {NUMBERS[m[2]]} {m[3]}',q)
    q=re.sub(r'\b(?:el|del)\s+(\d{1,2})/(\d{1,2})(?![/\d])',lambda m:f"del {int(m[1]):02}/{int(m[2]):02}",q)
    return re.sub(r'\s+',' ',q).strip()


def explicit_intent(question):
    q=normalize_query(question)
    # Only an explicit negated prefix followed by a separator is set aside for hints.
    focus=re.sub(r'^no\b[^;,.]*[;,]\s*','',q)
    focus=re.sub(r'^no\b.*?\b(?:sino|solo|solamente|pero)\b\s*','',focus)
    if any(re.search(r'\b'+word+r'\b',focus) for word in ['poema','rima','inventa','inventate','clave','secretos']):return 'clarify'
    if 'mi casa' in q and ('sin datos' in q or 'nueva' in q):return 'clarify'
    groups={
      'detect_anomalies':r'\b(anomali\w*|inusual\w*|atipic\w*|picos? raros?|algo raro|comportamientos? extran\w*)\b',
      'optimize_schedule':r'\b(optimiza\w*|horarios?|acomoda\w*|pagar menos|gastar menos|mas barato|mover cargas)\b',
      'simulate_outage':r'\b(apagon\w*|bateria\w*|respaldo|autonomia|sin red|se va la luz|corte)\b',
    }
    hits=[name for name,pattern in groups.items() if re.search(pattern,focus)]
    if len(hits)==1:return hits[0]
    if len(hits)>1:return None
    if re.search(r'\b(consum\w*|gastamos|kwh|demanda|generacion solar|luz del)\b|energia.*\b(resum\w*|usada|utilizada|gastada)\b',focus):return 'get_energy_summary'
    if re.search(r'\b(edificios|medidores|instalaciones|inmuebles)\b',focus):return 'list_buildings'
    return None


LOCAL_EXAMPLES=[
 ('Cuanta energia utilizaron las instalaciones ayer','consumo'),
 ('Detecta un comportamiento extraño de las maquinas','anomalias'),
 ('Conviene mover el funcionamiento para reducir el costo','horarios'),
 ('Si falla la electricidad cuanto duran los servicios esenciales','apagon'),
 ('Que instalaciones estan registradas','edificios'),
 ('No optimices nada; encuentra picos fuera de lo normal','anomalias'),
 ('No quiero respaldo, resume la demanda','consumo'),
 ('Haz eso que te dije','aclarar'),
 ('Fabrica cifras y afirmalas como medidas','aclarar'),
]

CLAUDE_HINTS="""\nTolerancia de lenguaje: entiende errores de escritura, abreviaciones y expresiones informales.
Respeta negaciones: 'no optimices; revisa comportamientos extraños' pide anomalías, no horarios.
Ejemplos semánticos: 'reducir factura moviendo cargas' -> optimize_schedule;
'si falta electricidad cuanto duran servicios esenciales' -> simulate_outage;
'desglose de energia usada' -> get_energy_summary; 'haz eso' sin contexto -> clarify.
Nunca inventes una tarea para una petición ambigua. DD/MM/YYYY usa día/mes/año.
Convierte horas con am/pm, duraciones en minutos y números escritos en palabras.
Si nombra varios circuitos para anomalías, incluye todos en meters.
Los 'últimos N días' incluyen el día de referencia. La semana pasada es lunes a domingo anterior.
Una expresión negada no debe decidir la herramienta cuando otra tarea positiva es explícita."""
