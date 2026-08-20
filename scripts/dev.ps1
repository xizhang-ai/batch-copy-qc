$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "output/dev"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$frontendOut = Join-Path $logDir "frontend.stdout.log"
$frontendErr = Join-Path $logDir "frontend.stderr.log"

$pythonExe = Join-Path $root ".venv/Scripts/python.exe"
$pythonArgs = @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1")
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { & py -3.12 -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 12))" 2>$null }
    if ($py -and $LASTEXITCODE -eq 0) { $pythonExe = $py.Source; $pythonArgs = @("-3.12") + $pythonArgs }
    else {
        $pythonExe = (Get-Command python -ErrorAction Stop).Source
        & $pythonExe -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 12))"
        if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required. Create .venv or install Python 3.12." }
    }
}

$env:VITE_API_MODE = "real"

$frontend = Start-Process -FilePath "npm.cmd" -ArgumentList @("--prefix", "frontend", "run", "dev", "--", "--host", "127.0.0.1") -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr

Write-Host "Backend: http://127.0.0.1:8000"
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Logs: $logDir"
try {
    Start-Sleep -Seconds 1
    $frontend.Refresh()
    if ($frontend.HasExited) { throw "Frontend exited. See $frontendErr" }
    & $pythonExe @pythonArgs
    if ($LASTEXITCODE -ne 0) { throw "Backend exited with code $LASTEXITCODE" }
} finally {
    if ($frontend -and -not $frontend.HasExited) {
        & taskkill.exe /PID $frontend.Id /T /F *> $null
    }
}
