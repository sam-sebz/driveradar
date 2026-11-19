# Windows equivalent of the Makefile:  .\scripts\dev.ps1 <target>
# Targets: setup, up, down, logs, test, lint, seed, eval, smoke, samples
param([Parameter(Position = 0)][string]$Target = "help")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"
$Py = if (Test-Path $VenvPy) { $VenvPy } else { "python" }

function Invoke-Step([string]$Dir, [scriptblock]$Block) {
    Push-Location $Dir
    # Native tools write progress to stderr; judge success by exit code, not by stderr.
    $ErrorActionPreference = "Continue"
    try {
        & $Block
        if ($LASTEXITCODE -ne 0) { throw "command failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
}

switch ($Target) {
    "setup" {
        Invoke-Step $Backend { & $Py -m pip install -r requirements-dev.txt }
        Invoke-Step $Frontend { npm ci }
    }
    "up" {
        $envFile = Join-Path $Root ".env"
        if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $Root ".env.example") $envFile }
        Invoke-Step $Root { docker compose up --build -d --wait }
        Write-Host "API: http://localhost:8000/docs   App: http://localhost:5173"
    }
    "down" { Invoke-Step $Root { docker compose down } }
    "logs" { Invoke-Step $Root { docker compose logs -f backend } }
    "test" {
        Invoke-Step $Backend { & $Py -m pytest --cov=app --cov-report=term-missing --cov-fail-under=70 }
        Invoke-Step $Backend { & $Py -m coverage report --include="app/domain/*" --fail-under=70 }
        Invoke-Step $Frontend { npm run test:coverage }
    }
    "lint" {
        Invoke-Step $Backend { & $Py -m ruff check . }
        Invoke-Step $Backend { & $Py -m ruff format --check . }
        Invoke-Step $Backend { & $Py -m mypy app tests }
        Invoke-Step $Frontend { npm run lint }
        Invoke-Step $Frontend { npm run typecheck }
    }
    "seed" { Invoke-Step $Root { docker compose exec backend python -m app.seed } }
    "eval" { Invoke-Step $Backend { & $Py ..\eval\run_eval.py } }
    "smoke" { Invoke-Step $Root { & $Py scripts\smoke.py } }
    "samples" {
        Invoke-Step $Backend { & $Py scripts\make_samples.py }
        Invoke-Step $Backend { & $Py ..\eval\make_heldout.py }
    }
    default {
        Write-Host "Usage: .\scripts\dev.ps1 <setup|up|down|logs|test|lint|seed|eval|smoke|samples>"
    }
}
