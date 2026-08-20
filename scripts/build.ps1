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
            if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required. Create .venv or install Python 3.12." }
        }
    }
    & $pythonExe @pythonPrefix -m pytest backend/tests -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $pythonExe @pythonPrefix -m ruff check backend
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & npm.cmd --prefix frontend test -- --run
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & npm.cmd --prefix frontend run typecheck
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $env:VITE_API_MODE = "real"
    & npm.cmd --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
