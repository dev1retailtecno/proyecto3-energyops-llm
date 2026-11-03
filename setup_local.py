"""Download official Qwen weights and llama.cpp CPU runtime. No API credential."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import zipfile
import httpx
ROOT=Path(__file__).resolve().parent
def download(url,path):
    if path.exists():return
    tmp=path.with_suffix('.part')
    with httpx.stream('GET',url,follow_redirects=True,timeout=120) as r:
        r.raise_for_status()
        with tmp.open('wb') as f:
            for chunk in r.iter_bytes(1024*1024):f.write(chunk)
    tmp.rename(path)
    print(path.name,'listo',flush=True)
if __name__=='__main__':
    runtime=ROOT/'local_runtime';runtime.mkdir(exist_ok=True)
    urls=[('https://github.com/ggml-org/llama.cpp/releases/download/b12061/llama-b12061-bin-win-cpu-x64.zip',runtime/'llama.zip'),('https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q8_0.gguf',runtime/'Qwen3-0.6B-Q8_0.gguf')]
    with ThreadPoolExecutor(2) as pool:list(pool.map(lambda pair:download(*pair),urls))
    with zipfile.ZipFile(runtime/'llama.zip') as z:z.extractall(runtime)
    print('Runtime y modelo descargados.',flush=True)
