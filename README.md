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

On each run, only the bulletin dated for the **upcoming Sunday** (today, if today is Sunday) is processed, and only if its `-email.docx` doesn't exist yet. Older or future bulletins in the folder are ignored. The filename must match exactly, including the capital `B`, except that any number of spaces before `.pdf` (which Thunderbird sometimes adds) is allowed. The same goes for an existing `-email.docx`.

---

## Environment Variables

Set in `~/.config/pcc-bulletin/env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required)* | Your Anthropic API key |
| `PCC_BULLETIN_FOLDER` | `~/Documents/PCC Bulletins` | Where bulletins are saved |
| `PCC_SERMON_NOTES_ROOT` | `/MaresLeg/Church/SermonNotes` | Root of sermon notes tree |
| `PCC_MODEL` | `claude-sonnet-4-6` | Claude model to use |
| `PCC_SMTP_USER` | *(none)* | SMTP login for failure alerts. For Gmail, your Gmail address |
| `PCC_SMTP_PASSWORD` | *(none)* | SMTP password. For Gmail, an [app password](https://myaccount.google.com/apppasswords), not your normal password |
| `PCC_SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `PCC_SMTP_PORT` | `587` | `587` uses STARTTLS, `465` uses implicit TLS |
| `PCC_ALERT_TO` | `PCC_SMTP_USER` | Who gets alert emails (comma-separated) |
| `PCC_ALERT_FROM` | `PCC_SMTP_USER` | Sender address on alert emails |
| `PCC_ERROR_LOG` | `<bulletin folder>/HEY-CLAUDE-API-ERRORS.md` | Markdown file that every failure is appended to |
| `PCC_STATE_DIR` | `~/.local/state/pcc-bulletin` | Remembers failed bulletins so the watcher doesn't retry in a loop |

---

## When the Claude API Fails

Any failure of the Claude API call is reported three ways, none of which use Claude:

1. A `CRITICAL` entry wrapped in `!!!!` banners in the journal (`journalctl --user -u pcc-bulletin.service`).
2. An entry appended to `HEY-CLAUDE-API-ERRORS.md` in the bulletin folder.
3. An alert email sent over SMTP, if the `PCC_SMTP_*` settings are filled in.

"Failure" covers SDK errors (bad key, rate limits, outages and timeouts after 3 retries,
connection errors) and unusable responses: empty text, a refusal, or output cut off at the
token limit. Each report says which step failed, which bulletin, the model, the HTTP status and
request id when there is one, and the command to rerun. A missing `ANTHROPIC_API_KEY` is reported
the same way, once, until it's fixed. If the email or the log append itself fails, that is also
logged at `CRITICAL` with the full original alert, so nothing fails silently.

Because the path watcher fires on any change in the folder (including the error log append), an
automatic run won't retry a bulletin whose last attempt failed until the PDF is downloaded again.
After fixing the problem, rerun by hand with `./force-run.sh` or `pcc-bulletin <path>`.

To check that alerts work, run `./test-alert.sh` from the repo root. It runs the real pipeline on a
throwaway PDF with a deliberately invalid API key, so you should get the banner, a new entry in
`HEY-CLAUDE-API-ERRORS.md`, and an alert email. Your real bulletins aren't touched.

---

## Manual Run

```bash
# Process the upcoming Sunday's bulletin, if present and not yet processed:
pcc-bulletin

# Process a specific file (any date, even if already processed):
pcc-bulletin /path/to/Bulletin-10-18-2026.pdf

# Reprocess the most recently downloaded bulletin, even if already processed:
pcc-bulletin --latest
```

If the path watcher misses a new bulletin, run `./force-run.sh` from the repo root. It runs
`pcc-bulletin --latest` with the same virtualenv and env file the service uses, so it picks the
newest `Bulletin-MM-DD-YYYY.pdf` in the folder and regenerates its `-email.docx` immediately.

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
