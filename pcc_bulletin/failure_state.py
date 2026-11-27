"""
Remembers which bulletins already failed at the Claude API step.

The systemd path unit fires on *any* change in the bulletin folder, including
the append to HEY-CLAUDE-API-ERRORS.md that a failure makes. Without this, a
failure would trigger another run, which would call Claude again, fail again,
append again, and loop, sending an alert email each time.

So automatic runs skip a bulletin whose last attempt failed, until the PDF
itself changes (a new download). Manual runs (an explicit path, --latest,
./force-run.sh) always try again. A startup configuration error (such as a
missing API key) is alerted once, until it changes or is fixed. State lives
outside the watched folder, in $PCC_STATE_DIR (default ~/.local/state/pcc-bulletin).
"""

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

STATE_FILE_NAME = "claude-failures.json"


def state_file() -> Path:
    root = os.environ.get("PCC_STATE_DIR", "").strip() or "~/.local/state/pcc-bulletin"
    return Path(root).expanduser() / STATE_FILE_NAME


CONFIG_ERROR_KEY = "config-error"


def _load() -> dict:
    path = state_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
        return data
    except FileNotFoundError:
        return {}
    except Exception as exc:  # noqa: BLE001 — a corrupt state file must not block runs
        log.error("Ignoring unreadable failure state %s: %s", path, exc)
        return {}


def _save(data: dict) -> None:
    path = state_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log.error("Could not write failure state %s: %s", path, exc)


def _mtime(pdf_path: Path) -> float | None:
    try:
        return pdf_path.stat().st_mtime
    except OSError:
        return None


def record_failure(pdf_path: Path) -> None:
    data = _load()
    data[str(pdf_path)] = _mtime(pdf_path) or 0.0
    _save(data)


def clear_failure(pdf_path: Path) -> None:
    data = _load()
    if data.pop(str(pdf_path), None) is not None:
        _save(data)


def failed_before(pdf_path: Path) -> bool:
    """True if this exact PDF (same path and mtime) already failed at the Claude step."""
    recorded = _load().get(str(pdf_path))
    return recorded is not None and recorded == (_mtime(pdf_path) or 0.0)


def is_new_config_error(message: str) -> bool:
    """Record a startup config error. True if it differs from the one recorded last run."""
    data = _load()
    if data.get(CONFIG_ERROR_KEY) == message:
        return False
    data[CONFIG_ERROR_KEY] = message
    _save(data)
    return True


def clear_config_error() -> None:
    data = _load()
    if data.pop(CONFIG_ERROR_KEY, None) is not None:
        _save(data)
