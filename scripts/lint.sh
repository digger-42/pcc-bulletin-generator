#!/usr/bin/env bash
# Run all code-quality checks.
# Usage: ./scripts/lint.sh
set -euo pipefail

echo "==> black (format check)"
black --check .

echo "==> ruff (lint)"
ruff check .

echo "==> bandit (security)"
bandit -r pcc_bulletin/ -ll

echo "All checks passed."
