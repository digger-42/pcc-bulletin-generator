#!/usr/bin/env bash
# Install pcc-bulletin-generator: virtualenv, systemd user units, env skeleton.
# Run once after cloning the repo.  Re-running is idempotent.
# Usage: ./scripts/install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$HOME/.local/share/pcc-bulletin/venv"
ENV_FILE="$HOME/.config/pcc-bulletin/env"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# ── 1. Virtual environment ────────────────────────────────────────────────────
echo "==> Creating virtualenv at $VENV_DIR"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet "$REPO_DIR"
VENV_PYTHON="$VENV_DIR/bin/python"

# ── 2. Environment file ───────────────────────────────────────────────────────
echo "==> Setting up env file at $ENV_FILE"
mkdir -p "$(dirname "$ENV_FILE")"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" <<'EOF'
# PCC Bulletin Generator — environment configuration
# Edit this file to add your Anthropic API key, then reload the systemd unit.
ANTHROPIC_API_KEY=your-api-key-here

# Optional overrides (defaults shown):
# PCC_BULLETIN_FOLDER=/home/dan/Documents/PCC Bulletins
# PCC_SERMON_NOTES_ROOT=/MaresLeg/Church/SermonNotes
# PCC_MODEL=claude-sonnet-4-6
EOF
    echo "    Created skeleton env file — add your ANTHROPIC_API_KEY."
else
    echo "    Env file already exists, leaving it untouched."
fi
chmod 600 "$ENV_FILE"
chown "$USER" "$ENV_FILE"

# ── 3. systemd user units ─────────────────────────────────────────────────────
echo "==> Installing systemd user units"
mkdir -p "$SYSTEMD_DIR"

sed "s|__VENV_PYTHON__|$VENV_PYTHON|g" \
    "$REPO_DIR/systemd/pcc-bulletin.service" \
    > "$SYSTEMD_DIR/pcc-bulletin.service"

cp "$REPO_DIR/systemd/pcc-bulletin.path" "$SYSTEMD_DIR/pcc-bulletin.path"

systemctl --user daemon-reload
systemctl --user enable --now pcc-bulletin.path

echo ""
echo "Installation complete."
echo ""
echo "Next steps:"
echo "  1. Edit $ENV_FILE and set ANTHROPIC_API_KEY."
echo "  2. Check status:  systemctl --user status pcc-bulletin.path"
echo "  3. View logs:     journalctl --user -u pcc-bulletin.service -f"
