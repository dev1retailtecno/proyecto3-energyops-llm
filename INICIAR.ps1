$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -c "import httpx,jsonschema,zoneinfo; zoneinfo.ZoneInfo('America/Guatemala')"
if ($LASTEXITCODE -ne 0) { python -m pip install -r requirements.txt }
if ((-not (Test-Path -LiteralPath '.\local_runtime\llama-server.exe')) -or (-not (Test-Path -LiteralPath '.\local_runtime\Qwen3-0.6B-Q8_0.gguf'))) { python setup_local.py }
$taskModelReady = $false
try { $taskHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/health' -TimeoutSec 2; $taskModelReady = $taskHealth.status -eq 'ok' } catch {}
if (-not $taskModelReady) {
    Start-Process -FilePath '.\local_runtime\llama-server.exe' -ArgumentList '-m Qwen3-0.6B-Q8_0.gguf --host 127.0.0.1 --port 8766 -c 2048 -t 8 --parallel 1 --jinja --no-webui' -WorkingDirectory '.\local_runtime' -WindowStyle Hidden -RedirectStandardOutput 'llama-out.log' -RedirectStandardError 'llama-error.log'
    for ($taskTry=0; $taskTry -lt 45; $taskTry++) {
        try { $taskHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/health' -TimeoutSec 2; if ($taskHealth.status -eq 'ok') { $taskModelReady=$true; break } } catch {}
        Start-Sleep -Seconds 1
    }
    if (-not $taskModelReady) { throw 'No inició Qwen3. Revisa llama-error.log.' }
}
try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8765/' -TimeoutSec 2 | Out-Null; $taskAppReady=$true } catch { $taskAppReady=$false }
if (-not $taskAppReady) { Start-Process -FilePath 'python' -ArgumentList 'app.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput 'app-out.log' -RedirectStandardError 'app-error.log' }
Start-Process 'http://127.0.0.1:8765'
Write-Host 'EnergyOps listo. Poster: http://127.0.0.1:8765/poster'
