#!/usr/bin/env bash
# Run the test suite with coverage.
# Usage: ./scripts/test.sh [extra pytest args]
set -euo pipefail

python -m pytest \
  --cov=pcc_bulletin \
  --cov-report=term-missing \
  "$@"
