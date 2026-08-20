$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    if (-not (Test-Path -LiteralPath ".env")) {
        throw "Missing .env. Copy .env.example to .env and configure the adapters."
    }
    if (-not (Test-Path -LiteralPath "frontend/dist/index.html")) {
        throw "Missing frontend/dist. Run scripts/build.ps1 first."
    }
    New-Item -ItemType Directory -Force -Path "data", "data/uploads" | Out-Null

    $pythonExe = Join-Path $root ".venv/Scripts/python.exe"
    $pythonPrefix = @()
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) { & py -3.12 -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 12))" 2>$null }
        if ($py -and $LASTEXITCODE -eq 0) { $pythonExe = $py.Source; $pythonPrefix = @("-3.12") }
        else {
            $pythonExe = (Get-Command python -ErrorAction Stop).Source
            & $pythonExe -c "import sys; raise SystemExit(sys.version_info[:2] != (3, 12))"
            if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required. Create .venv or install Python 3.12." }
        }
    }
    & $pythonExe @pythonPrefix -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
