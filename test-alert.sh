#!/usr/bin/env bash
# Simulate a Claude API failure to check that alerts work end to end.
#
# Runs the real pipeline on a throwaway one-page PDF with a deliberately
# invalid API key, so the Claude API answers 401. That should produce:
#   - a CRITICAL "CLAUDE API FAILURE" banner in this terminal,
#   - a new entry in HEY-CLAUDE-API-ERRORS.md (or $PCC_ERROR_LOG),
#   - an alert email, if the PCC_SMTP_* settings are in the env file.
#
# Your real bulletins, -email.docx files and failure state are not touched.
# Uses the same virtualenv and env file as pcc-bulletin.service.
# Usage: ./test-alert.sh
set -euo pipefail

VENV_PYTHON="${PCC_VENV_PYTHON:-$HOME/.local/share/pcc-bulletin/venv/bin/python}"
ENV_FILE="${PCC_ENV_FILE:-$HOME/.config/pcc-bulletin/env}"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "Virtualenv not found at $VENV_PYTHON. Run ./scripts/install.sh first." >&2
    exit 1
fi

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
PDF="$WORK_DIR/TEST-ALERT-simulated-failure.pdf"

"$VENV_PYTHON" - "$PDF" <<'PY'
import sys

import pymupdf

doc = pymupdf.open()
doc.new_page().insert_text((72, 72), "Test bulletin for ./test-alert.sh")
doc.save(sys.argv[1])
PY

echo "==> Simulating a Claude API failure (an invalid API key on purpose)..."
set +e
ANTHROPIC_API_KEY="sk-ant-invalid-key-for-alert-test" \
    PCC_STATE_DIR="$WORK_DIR/state" \
    "$VENV_PYTHON" -m pcc_bulletin.main "$PDF"
status=$?
set -e

echo ""
if [ "$status" -eq 0 ]; then
    echo "Unexpected: the run succeeded, so no failure was simulated." >&2
    exit 1
fi
echo "Done. The run failed as intended. Check above for 'Alert email sent to ...',"
echo "then check your inbox and HEY-CLAUDE-API-ERRORS.md."
