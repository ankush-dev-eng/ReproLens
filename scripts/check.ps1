# ReproLens Quality Gate Check Script (PowerShell / Windows)
$ErrorActionPreference = "Stop"

$python = if (Test-Path "$PSScriptRoot\..\.venv\Scripts\python.exe") { "$PSScriptRoot\..\.venv\Scripts\python.exe" } else { "python" }
$ruff = if (Test-Path "$PSScriptRoot\..\.venv\Scripts\ruff.exe") { "$PSScriptRoot\..\.venv\Scripts\ruff.exe" } else { "ruff" }
$pytest = if (Test-Path "$PSScriptRoot\..\.venv\Scripts\pytest.exe") { "$PSScriptRoot\..\.venv\Scripts\pytest.exe" } else { "pytest" }

Write-Host "=== [1/6] Python Compileall Check ===" -ForegroundColor Cyan
& $python -m compileall -q reprolens ui main.py tests
if ($LASTEXITCODE -ne 0) { Write-Error "Compileall failed"; exit 1 }

Write-Host "=== [2/6] Ruff Linter Check ===" -ForegroundColor Cyan
& $ruff check .
if ($LASTEXITCODE -ne 0) { Write-Error "Ruff check failed"; exit 1 }

Write-Host "=== [3/6] Ruff Formatter Check ===" -ForegroundColor Cyan
& $ruff format --check .
if ($LASTEXITCODE -ne 0) { Write-Error "Ruff format check failed"; exit 1 }

Write-Host "=== [4/6] Unit & Integration Tests (excluding live Docker) ===" -ForegroundColor Cyan
& $pytest -m "not docker" --junitxml=junit.xml -v
if ($LASTEXITCODE -ne 0) { Write-Error "Pytest failed"; exit 1 }

Write-Host "=== [5/6] Secret Scan ===" -ForegroundColor Cyan
$matches = git grep -i -E "sk-ant-|sk-or-v1-[0-9a-f]{64}|ghp_[A-Za-z0-9]{36}" -- ":(exclude).env.example" ":(exclude)docs/MASTER_PROMPT.md" ":(exclude)scripts/check.ps1" ":(exclude)scripts/check.sh"
if ($matches) {
    Write-Error "Potential secrets found in tracked files!"
    exit 1
}

Write-Host "=== [6/6] Docker Smoke Tests Status ===" -ForegroundColor Cyan
try {
    docker version | Out-Null
    Write-Host "Docker available. Running Docker smoke tests..." -ForegroundColor Green
    & $pytest -m "docker" -v
} catch {
    Write-Host "DOCKER NOT AVAILABLE: Docker smoke tests NOT RUN (Docker unavailable)" -ForegroundColor Yellow
}

Write-Host "`nAll Quality Gate Checks Passed Successfully!" -ForegroundColor Green

