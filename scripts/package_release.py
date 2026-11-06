"""Package committed source and reviewed artifacts without credentials or runtimes."""
from pathlib import Path,PurePosixPath
import hashlib,io,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/entrega'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def allowed(name):
    parts=PurePosixPath(name).parts
    return not any(x in {'.git','local_runtime','tmp','__pycache__'} for x in parts) and not name.endswith(('.sqlite3','.log','.zip')) and not any(x.startswith('.env') and x!='.env.example' for x in parts)
def main():
    if git('status','--porcelain').strip():raise SystemExit('Commit the final files before packaging; the source ZIP must match a clean Git revision.')
    OUT.mkdir(parents=True,exist_ok=True)
    source=OUT/'Codigo_EnergyOps.zip'
    with zipfile.ZipFile(io.BytesIO(git('archive','--format=zip','HEAD'))) as snapshot,zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as target:
        target.writestr('EnergyOps/SOURCE_REVISION.txt',git('rev-parse','HEAD').decode().strip()+'\n')
        for item in snapshot.infolist():
            name=item.filename
            if item.is_dir():continue
            if not allowed(name):raise SystemExit('Unexpected sensitive/generated path in Git: '+name)
            if name.startswith('output/') and not name.startswith('output/figures/'):continue
            target.writestr('EnergyOps/'+name,snapshot.read(item))
    names=['Informe_EnergyOps.docx','Informe_EnergyOps.pdf','Poster_EnergyOps.pdf','Demo_EnergyOps.mp4','GUIA_PARA_PRESENTAR.md','LEEME_ENTREGA.md','Codigo_EnergyOps.zip']
    for name in names:
        if not (OUT/name).is_file():raise SystemExit('Missing deliverable: '+name)
    manifest={'project':'EnergyOps','date':'2026-11-06','authors':[{'name':'Ian Cumes','id':'23236'},{'name':'Javier Valladares','id':'23045'}],'source_commit':git('rev-parse','HEAD').decode().strip(),'repository':'https://github.com/dev1retailtecno/proyecto3-energyops-llm','visibility':'public','files':[{ 'file':name,'bytes':(OUT/name).stat().st_size,'sha256':sha(OUT/name)} for name in names]}
    (OUT/'MANIFIESTO.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    delivery=OUT/'Entrega_EnergyOps.zip'
    with zipfile.ZipFile(delivery,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in names+['MANIFIESTO.json']:z.write(OUT/name,arcname='Entrega_EnergyOps/'+name)
    for path in [source,delivery]:
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None:raise AssertionError('Corrupted archive')
    print(json.dumps({'source_commit':manifest['source_commit'],'files':len(names)+1,'delivery_bytes':delivery.stat().st_size,'delivery_sha256':sha(delivery)},indent=2))
if __name__=='__main__':main()
