import sys,json
from pathlib import Path
import pymupdf
source=Path(sys.argv[1]);out=Path(sys.argv[2]);dpi=int(sys.argv[3]);out.mkdir(parents=True,exist_ok=True);paths=[]
with pymupdf.open(source) as doc:
 for i,page in enumerate(doc):
  target=out/f'raw-{i+1:02}.png';page.get_pixmap(matrix=pymupdf.Matrix(dpi/72,dpi/72)).save(target);paths.append(str(target.resolve()))
print(json.dumps(paths))
