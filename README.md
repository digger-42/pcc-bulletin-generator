# pcc-bulletin-generator

Automatically generates a weekly email summary for Plainfield Christian Church from the bulletin PDF.

**Pipeline:** Email received → FiltaQuilla saves PDF attachment → systemd path watcher fires → Python script extracts text, fetches sermon notes, calls Claude API → `.docx` email draft saved alongside the bulletin.

---

## Requirements

- Python 3.11+
- [Thunderbird](https://www.thunderbird.net/) with the [FiltaQuilla](https://addons.thunderbird.net/en-US/thunderbird/addon/filtaquilla/) extension
- An [Anthropic API key](https://console.anthropic.com/)
- Sermon notes PDFs on a mounted path (default: `/MaresLeg/Church/SermonNotes/`)

---

## Installation

```bash
git clone git@github.com:digger-42/pcc-bulletin-generator.git
cd pcc-bulletin-generator
./scripts/install.sh
```

The script:
1. Creates a virtualenv at `~/.local/share/pcc-bulletin/venv`
2. Creates `~/.config/pcc-bulletin/env` (permissions `600`) for the API key
3. Installs and enables the systemd user units

**After running install, add your API key:**

```bash
# Edit with your preferred editor (sudo if needed):
nano ~/.config/pcc-bulletin/env
# Set: ANTHROPIC_API_KEY=sk-ant-...
```

---

## FiltaQuilla Setup

FiltaQuilla is a Thunderbird extension that lets message filters save attachments to disk.

1. Install **FiltaQuilla** from the Thunderbird Add-ons Manager.
2. In Thunderbird → **Tools → Message Filters**, create a new filter:
   - **Filter name:** Save PCC Bulletin
   - **Match:** Subject contains `bulletin` **AND** From contains `office@pccmi.org`
   - **Action:** Save Attachments To → `~/Documents/PCC Bulletins/`
3. Apply the filter to the Inbox.

FiltaQuilla saves *every* attachment on a matching email; it cannot filter by file type. That's fine: the script ignores anything that isn't the upcoming Sunday's `Bulletin-MM-DD-YYYY.pdf`, so other attachments just sit in the folder. Keep the match conditions tight to limit the clutter.

New emails matching the filter will have their attachments saved automatically. The systemd path watcher fires within seconds.

---

## Systemd Units

Two units are installed to `~/.config/systemd/user/`:

| Unit | Purpose |
|------|---------|
| `pcc-bulletin.path` | Watches `~/Documents/PCC Bulletins/` for changes |
| `pcc-bulletin.service` | Runs `pcc-bulletin` (oneshot) when the path unit fires |

```bash
# Check watcher status
systemctl --user status pcc-bulletin.path

# View logs from last run
journalctl --user -u pcc-bulletin.service -n 50

# Manually trigger a run
systemctl --user start pcc-bulletin.service
```

---

## File Naming

| File | Pattern |
|------|---------|
| Input bulletin | `Bulletin-MM-DD-YYYY.pdf` |
| Output email draft | `Bulletin-MM-DD-YYYY-email.docx` |
| Sermon notes | `/MaresLeg/Church/SermonNotes/YYYY/YYYY-MM-DD-sermon-notes*.pdf` |

Both files live in `~/Documents/PCC Bulletins/` (configurable via `PCC_BULLETIN_FOLDER`).

On each run, only the bulletin dated for the **upcoming Sunday** (today, if today is Sunday) is processed, and only if its `-email.docx` doesn't exist yet. Older or future bulletins in the folder are ignored. The filename match is case-insensitive.

---

## Environment Variables

Set in `~/.config/pcc-bulletin/env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required)* | Your Anthropic API key |
| `PCC_BULLETIN_FOLDER` | `~/Documents/PCC Bulletins` | Where bulletins are saved |
| `PCC_SERMON_NOTES_ROOT` | `/MaresLeg/Church/SermonNotes` | Root of sermon notes tree |
| `PCC_MODEL` | `claude-sonnet-4-6` | Claude model to use |

---

## Manual Run

```bash
# Process the upcoming Sunday's bulletin, if present and not yet processed:
pcc-bulletin

# Process a specific file (any date, even if already processed):
pcc-bulletin /path/to/Bulletin-10-18-2026.pdf
```

---

## Development

```bash
# Install with dev dependencies
pip install -e .
pip install -r requirements-dev.txt

# Format
black .

# Lint
./scripts/lint.sh

# Test (with coverage)
./scripts/test.sh

# Or run pytest directly
pytest
```

All CI checks (black, ruff, bandit, pytest with 100% coverage) must pass before a PR can merge.
