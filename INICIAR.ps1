$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -c "import httpx,jsonschema,zoneinfo; zoneinfo.ZoneInfo('America/Guatemala')"
if ($LASTEXITCODE -ne 0) { python -m pip install -r requirements.txt }
try { $taskAppHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2; $taskAppReady=$taskAppHealth.status -eq 'ok' } catch { $taskAppReady=$false }
if (-not $taskAppReady) { Start-Process -FilePath 'python' -ArgumentList 'app.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput 'app-out.log' -RedirectStandardError 'app-error.log' }
$taskLocalFiles = (Test-Path -LiteralPath '.\local_runtime\llama-server.exe') -and (Test-Path -LiteralPath '.\local_runtime\Qwen3-0.6B-Q8_0.gguf')
$taskModelReady = $false
try { $taskHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/health' -TimeoutSec 2; $taskModelReady = $taskHealth.status -eq 'ok' } catch {}
if ((-not $taskModelReady) -and $taskLocalFiles) {
    Start-Process -FilePath '.\local_runtime\llama-server.exe' -ArgumentList '-m Qwen3-0.6B-Q8_0.gguf --host 127.0.0.1 --port 8766 -c 2048 -t 8 --parallel 1 --jinja --no-webui' -WorkingDirectory '.\local_runtime' -WindowStyle Hidden -RedirectStandardOutput 'llama-out.log' -RedirectStandardError 'llama-error.log'
    for ($taskTry=0; $taskTry -lt 15; $taskTry++) {
        try { $taskHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/health' -TimeoutSec 2; if ($taskHealth.status -eq 'ok') { $taskModelReady=$true; break } } catch {}
        Start-Sleep -Seconds 1
    }
    if (-not $taskModelReady) { Write-Host 'Qwen3 no está disponible. Puedes seguir con Claude o los análisis directos.' }
}
if (-not $taskLocalFiles) { Write-Host 'Modo local opcional no instalado. La aplicación y el análisis directo siguen disponibles. Para instalarlo: python setup_local.py' }
for ($taskTry=0; $taskTry -lt 15; $taskTry++) {
    try { $taskAppHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2; if ($taskAppHealth.status -eq 'ok') { $taskAppReady=$true; break } } catch {}
    Start-Sleep -Seconds 1
}
if (-not $taskAppReady) { throw 'La aplicación no pudo iniciar. Revisa app-error.log y ejecuta otra vez INICIAR.cmd.' }
Start-Process 'http://127.0.0.1:8765'
Write-Host 'EnergyOps listo. Poster: http://127.0.0.1:8765/poster'
