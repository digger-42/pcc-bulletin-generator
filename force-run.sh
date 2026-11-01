#!/usr/bin/env bash
# Force the bulletin service to run now on the most recently downloaded
# bulletin PDF, even if its -email.docx already exists (it is regenerated).
# Use this when the systemd path watcher missed a new bulletin.
#
# Uses the same virtualenv and env file as pcc-bulletin.service.
# Usage: ./force-run.sh
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

exec "$VENV_PYTHON" -m pcc_bulletin.main --latest
