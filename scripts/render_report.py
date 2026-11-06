"""Invoke the packaged DOCX renderer with native Word/PyMuPDF adapters on Windows."""
import importlib.util,subprocess,sys,json,shutil,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
available=sorted((Path.home()/'.codex/plugins/cache/openai-primary-runtime/documents').glob('*/skills/documents/render_docx.py'))
SKILL=available[-1] if available else None
SYSTEM_PYTHON=os.getenv('ENERGYOPS_RENDER_PYTHON') or shutil.which('python') or sys.executable
def native_word(input_path,profile,temp_dir,stem,verbose=False):
 target=Path(temp_dir)/(stem+'.pdf');result=subprocess.run([SYSTEM_PYTHON,str(ROOT/'scripts/export_word.py'),str(input_path),str(target)],capture_output=True,text=True)
 if result.returncode:raise RuntimeError(result.stderr)
 return str(target),'Native Microsoft Word 16 DOCX export; LibreOffice unavailable on Windows.'
def raster(pdf_path,dpi=150,output_folder=None,**kwargs):
 result=subprocess.run([SYSTEM_PYTHON,str(ROOT/'scripts/rasterize_pdf.py'),str(pdf_path),str(output_folder),str(dpi)],capture_output=True,text=True,check=True)
 return json.loads(result.stdout)
destination=ROOT/'tmp/report_render';destination.mkdir(parents=True,exist_ok=True)
if SKILL:
 spec=importlib.util.spec_from_file_location('packaged_render_docx',SKILL);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
 r.convert_to_pdf=native_word;r.convert_from_path=raster
 sys.argv=[str(SKILL),str(ROOT/'output/entrega/Informe_EnergyOps.docx'),'--output_dir',str(destination),'--emit_pdf']
 r.main()
else:
 pdf,_=native_word(ROOT/'output/entrega/Informe_EnergyOps.docx',None,destination,'Informe_EnergyOps')
 raster(pdf,output_folder=destination)
shutil.copy2(destination/'Informe_EnergyOps.pdf',ROOT/'output/entrega/Informe_EnergyOps.pdf')
print('PDF final copiado a output/entrega/Informe_EnergyOps.pdf')
