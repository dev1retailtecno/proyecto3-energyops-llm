"""Build the editable report from its reviewed Markdown source using python-docx."""
import re
from pathlib import Path
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/entrega';OUT.mkdir(parents=True,exist_ok=True)
doc=Document();sec=doc.sections[0];sec.page_width=Inches(8.27);sec.page_height=Inches(11.69);sec.top_margin=Inches(.8);sec.bottom_margin=Inches(.75);sec.left_margin=sec.right_margin=Inches(.8)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3','TOC Heading','Caption']:
 st=doc.styles[name];st.font.name='Calibri';st.font.color.rgb=RGBColor(0,0,0)
normal=doc.styles['Normal'];normal.font.size=Pt(11);normal.paragraph_format.space_after=Pt(6);normal.paragraph_format.line_spacing=1.08
for name,size in [('Heading 1',16),('Heading 2',12),('Heading 3',11)]:
 st=doc.styles[name];st.font.size=Pt(size);st.font.bold=True;st.paragraph_format.keep_with_next=True;st.paragraph_format.space_before=Pt(15);st.paragraph_format.space_after=Pt(7)
doc.styles['Title'].font.size=Pt(32);doc.styles['Title'].font.bold=True;doc.styles['Subtitle'].font.size=Pt(16)
header=sec.header.paragraphs[0];header.text='UVG  |  CC3092  |  Proyecto 3';header.runs[0].font.size=Pt(8)
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT;footer.add_run('EnergyOps  ·  ')
for cmd in ['PAGE','NUMPAGES']:
 if cmd=='NUMPAGES':footer.add_run(' / ')
 f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),cmd);footer._p.append(f)
for run in footer.runs:run.font.size=Pt(8)
sec.different_first_page_header_footer=True

def p(t,style=None):
 par=doc.add_paragraph(t,style)
 if len(t)>65 and re.match(r'[a-z0-9]{64}',t):par.paragraph_format.keep_together=True
 return par

def table(lines):
 rows=[[c.strip() for c in line.strip().strip('|').split('|')] for line in lines];headers=rows[0];rows=[headers]+rows[2:];n=len(headers)
 widths={2:[2.0,4.6],3:[1.5,2.5,2.6],4:[2.1,1.25,1.9,1.35],5:[.65,2.05,1.6,2.3],7:[1.05,.5,.5,.5,1.25,1.2,1.6]}.get(n,[6.6/n]*n)
 if headers[0]=='Iteración':widths=[.65,2.0,1.65,2.3]
 if headers[0]=='Atributo':widths=[1.25,2.7,2.65]
 if headers[0]=='Métrica':widths=[2.7,1.95,1.95]
 if headers[0]=='Necesidad':widths=[1.55,2.05,3]
 if 'few shot' in headers[0]:widths=[5.15,1.45]
 t=doc.add_table(rows=0,cols=n);t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
 for i,w in enumerate(widths):t.columns[i].width=Inches(w)
 for ri,row in enumerate(rows):
  cells=t.add_row().cells;trpr=t.rows[-1]._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
  if ri==0:trpr.append(OxmlElement('w:tblHeader'))
  for ci,value in enumerate(row):
   cell=cells[ci];cell.text=value;cell.width=Inches(widths[ci]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER;props=cell._tc.get_or_add_tcPr();borders=OxmlElement('w:tcBorders')
   for edge in ['top','left','bottom','right','insideH','insideV']:
    el=OxmlElement('w:'+edge);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'5');el.set(qn('w:color'),'D9D9D9');borders.append(el)
   props.append(borders);shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'17384B' if ri==0 else ('F1F5F7' if ri%2 else 'FFFFFF'));props.append(shade);margins=OxmlElement('w:tcMar')
   for edge in ['top','left','bottom','right']:
    el=OxmlElement('w:'+edge);el.set(qn('w:w'),'85');el.set(qn('w:type'),'dxa');margins.append(el)
   props.append(margins)
   for par in cell.paragraphs:
    par.paragraph_format.space_before=Pt(3);par.paragraph_format.space_after=Pt(3);par.paragraph_format.line_spacing=1.03;par.paragraph_format.keep_with_next=ri<len(rows)-1
    if ri and len(value)<15 and ci:par.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for run in par.runs:run.font.size=Pt(9.5);run.font.bold=ri==0;run.font.color.rgb=RGBColor(255,255,255) if ri==0 else RGBColor(0,0,0)
 par=p('');par.paragraph_format.space_after=Pt(4);par.paragraph_format.line_spacing=1;par.paragraph_format.space_before=Pt(0)
 for run in par.runs:run.font.size=Pt(1)

p('Universidad del Valle de Guatemala');p('CC3092 Deep Learning y Sistemas Inteligentes');p('Proyecto 3 Casos de uso de LLM');p('');p('EnergyOps','Title');p('Análisis energético con modelos de lenguaje y herramientas verificables','Subtitle');p('Informe técnico final');p('');p('Ian Cumes · Carné 23236');p('Javier Valladares · Carné 23045');p('');p('6 de noviembre de 2026');p('');p('Producto end-to-end, evaluación reproducible y resultados de iteraciones. Código y evidencia: https://github.com/dev1retailtecno/proyecto3-energyops-llm')
doc.add_page_break();lines=(ROOT/'docs/INFORME.md').read_text(encoding='utf-8').splitlines();i=0;table_no=0
while i<len(lines):
 line=lines[i].strip()
 if not line:i+=1;continue
 if line.startswith('# '):
  title=line[2:]
  if title.startswith('1 Definición'):
   doc.add_page_break();p('Contenido','TOC Heading');par=p('');field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'TOC '+chr(92)+'o \"1-2\" '+chr(92)+'h '+chr(92)+'z '+chr(92)+'u');par._p.append(field);doc.add_page_break()

  if title.startswith('Anexo B'):doc.add_page_break()
  doc.add_heading(title,1)
 elif line.startswith('## '):doc.add_heading(line[3:],2)
 elif line.startswith('|'):
  block=[]
  while i<len(lines) and lines[i].strip().startswith('|'):block.append(lines[i]);i+=1
  table_no+=1;titles=['Resumen de evidencia','Funciones del producto','Auditoría de datos','Modelos y parámetros','Comparación final','Detector de anomalías','Métricas operativas','Iteraciones','Riesgos y medidas','Ejemplos few shot','Cobertura de entregables'];cap=p(f'Tabla {table_no} '+titles[table_no-1],'Caption');cap.paragraph_format.keep_with_next=True;table(block);continue
 elif line.startswith('!['):
  match=re.match(r'!\[(.*?)\]\((.*?)\)',line)
  if match:
   title,file=match.groups();cap=p(title,'Caption');cap.paragraph_format.keep_with_next=True
   par=p('');par.alignment=WD_ALIGN_PARAGRAPH.CENTER;run=par.add_run();width=5.1 if 'matriz' in file else 6.55;run.add_picture(str(ROOT/'output/figures'/file),width=Inches(width));par.paragraph_format.space_after=Pt(10)
   props=run._r.xpath('.//wp:docPr')
   if props:props[0].set('descr',title)
 else:
  # Strip emphasis markers while retaining plain editable prose.
  p(line.replace('**',''))
 i+=1
for style in doc.styles:
 if style.type==1 and (style.name.startswith('Heading') or style.name.startswith('TOC')):style.font.color.rgb=RGBColor(0,0,0)
# Remove Word default title borders and theme-colored rules.
for root in [doc._element,doc.styles.element]:
 for border in list(root.iter(qn('w:pBdr'))):border.getparent().remove(border)
doc.core_properties.title='EnergyOps Informe técnico final';doc.core_properties.author='Ian Cumes y Javier Valladares';doc.core_properties.subject='Proyecto 3 Casos de uso de LLM';doc.core_properties.comments=''
path=OUT/'Informe_EnergyOps.docx';doc.save(path);print(path)
