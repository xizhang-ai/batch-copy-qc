$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $pythonExe = Join-Path $root ".venv/Scripts/python.exe"
    $pythonPrefix = @()
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) { & py -3.12 -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 12))" 2>$null }
        if ($py -and $LASTEXITCODE -eq 0) { $pythonExe = $py.Source; $pythonPrefix = @("-3.12") }
        else {
            $pythonExe = (Get-Command python -ErrorAction Stop).Source
            & $pythonExe -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 12))"
            if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required for real-stack E2E." }
        }
    }

    New-Item -ItemType Directory -Force -Path "output/e2e" | Out-Null
    $env:DATABASE_PATH = "output/e2e/backend-$PID.sqlite3"
    $env:UPLOAD_DIR = "output/e2e/uploads-$PID"
    $env:MODEL_ADAPTER = "fake"
    $env:FEISHU_ADAPTER = "fake"
    $env:APP_ENV = "test"
    & $pythonExe @pythonPrefix -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
