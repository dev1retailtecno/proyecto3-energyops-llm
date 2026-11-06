"""Native Microsoft Word conversion, separate application instance, no user documents."""
import sys
from pathlib import Path
import win32com.client
word=None;doc=None
try:
 word=win32com.client.DispatchEx('Word.Application');word.Visible=False;word.DisplayAlerts=0
 source=str(Path(sys.argv[1]).resolve());target=str(Path(sys.argv[2]).resolve());Path(target).parent.mkdir(parents=True,exist_ok=True)
 doc=word.Documents.Open(source,ReadOnly=False,AddToRecentFiles=False)
 doc.Fields.Update()
 for toc in doc.TablesOfContents:toc.Update()
 doc.Repaginate();doc.Fields.Update();doc.Save()
 doc.ExportAsFixedFormat(OutputFileName=target,ExportFormat=17,CreateBookmarks=1)
 print(target)
finally:
 if doc is not None:doc.Close(SaveChanges=False)
 if word is not None:word.Quit()
