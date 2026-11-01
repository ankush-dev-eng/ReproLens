#!/usr/bin/env bash
set -euo pipefail

echo "=== [1/6] Python Compileall Check ==="
python -m compileall -q reprolens ui main.py tests

echo "=== [2/6] Ruff Linter Check ==="
ruff check .

echo "=== [3/6] Ruff Formatter Check ==="
ruff format --check .

echo "=== [4/6] Unit & Integration Tests (excluding live Docker) ==="
pytest -m "not docker" --junitxml=junit.xml -v

echo "=== [5/6] Secret Scan ==="
if git grep -i -E "sk-ant-|sk-or-v1-[0-9a-f]{64}|ghp_[A-Za-z0-9]{36}" -- ":(exclude).env.example" ":(exclude)docs/MASTER_PROMPT.md" ":(exclude)scripts/check.ps1" ":(exclude)scripts/check.sh"; then
    echo "ERROR: Potential secrets found in tracked files!"
    exit 1
fi

echo "=== [6/6] Docker Smoke Tests Status ==="
if command -v docker &> /dev/null && docker version &> /dev/null; then
    echo "Docker available. Running Docker smoke tests..."
    pytest -m "docker" -v
else
    echo "DOCKER NOT AVAILABLE: Docker smoke tests NOT RUN (Docker unavailable)"
fi

echo "All Quality Gate Checks Passed Successfully!"

