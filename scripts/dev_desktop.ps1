param([switch]$WebOnly)

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontend = Join-Path $projectRoot 'frontend'
$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'

if (-not (Test-Path -LiteralPath $python)) { throw 'Project virtual environment is missing.' }
if (-not (Test-Path -LiteralPath (Join-Path $frontend 'package-lock.json'))) { throw 'Frontend dependencies are not installed.' }
if (Test-Path -LiteralPath $cargoBin) { $env:PATH = "$cargoBin;$env:PATH" }

$backend = Start-Process -FilePath $python -ArgumentList '-m','backend.main' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 1 | Out-Null; $ready = $true; break } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'Backend did not become healthy on 127.0.0.1:8000.' }
    Push-Location $frontend
    try { if ($WebOnly) { npm run dev } else { npm run tauri:dev } } finally { Pop-Location }
} finally {
    if (-not $backend.HasExited) { Stop-Process -Id $backend.Id }
}
