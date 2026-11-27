import re
from datetime import date
from pathlib import Path

from .alerts import raise_alarm
from .claude_client import ClaudeAPIError, generate_email
from .config import Config
from .docx_builder import build_docx
from .failure_state import record_failure
from .pdf_utils import extract_text
from .sermon_notes import find_sermon_notes

# Matches "Bulletin-MM-DD-YYYY.pdf" (case-sensitive). Thunderbird sometimes saves
# attachments with spaces before the extension, so any number of them is allowed.
BULLETIN_PATTERN = re.compile(r"^Bulletin-(\d{2})-(\d{2})-(\d{4}) *\.pdf$")


def parse_sunday_from_filename(pdf_path: Path) -> date | None:
    """Extract the Sunday date encoded in a bulletin filename, or None if it doesn't match."""
    m = BULLETIN_PATTERN.match(pdf_path.name)
    if not m:
        return None
    month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return date(year, month, day)


def output_path_for(pdf_path: Path) -> Path:
    """
    Return the .docx output path for a given bulletin PDF. Spaces before the
    PDF's extension are dropped, so the output name is always clean.
    """
    return pdf_path.parent / f"{pdf_path.stem.rstrip(' ')}-email.docx"


def is_processed(pdf_path: Path) -> bool:
    """
    True if an output .docx already exists for this bulletin, allowing any
    number of spaces before its extension.
    """
    base = re.escape(output_path_for(pdf_path).stem)
    pattern = re.compile(rf"^{base} *\.docx$")
    folder = pdf_path.parent
    return folder.is_dir() and any(pattern.match(p.name) for p in folder.iterdir())


def process_bulletin(pdf_path: Path, config: Config) -> Path:
    """
    Process one bulletin PDF end-to-end.

    1. Extract text from the PDF.
    2. Look for matching sermon notes (derived from the date in the filename).
    3. Call Claude to generate the email summary.
    4. Build a .docx and write it next to the source file.

    Returns the path of the generated .docx.
    """
    sunday = parse_sunday_from_filename(pdf_path)
    bulletin_text = extract_text(pdf_path)

    sermon_notes_text = ""
    if sunday is not None:
        notes_path = find_sermon_notes(sunday, config.sermon_notes_root)
        if notes_path is not None:
            sermon_notes_text = extract_text(notes_path)

    try:
        email_text = generate_email(bulletin_text, config.api_key, sermon_notes_text, config.model)
    except ClaudeAPIError as exc:
        # Record first: the error-log append below re-triggers the path watcher.
        record_failure(pdf_path)
        report_claude_failure(pdf_path, config, exc, has_sermon_notes=bool(sermon_notes_text))
        raise
    docx_bytes = build_docx(email_text)

    out_path = output_path_for(pdf_path)
    out_path.write_bytes(docx_bytes)
    return out_path


def report_claude_failure(
    pdf_path: Path, config: Config, exc: Exception, has_sermon_notes: bool
) -> None:
    """Log, record and email a Claude API failure. Never raises."""
    details = (
        f"Step: generating the email text with the Claude API\n"
        f"Bulletin: {pdf_path}\n"
        f"Model: {config.model}\n"
        f"Sermon notes included: {'yes' if has_sermon_notes else 'no'}\n"
        f"\nError:\n{exc}\n"
        f"\nNo -email.docx was written for this bulletin. Once the problem is fixed, rerun with:\n"
        f"  pcc-bulletin '{pdf_path}'\n"
        f"or ./force-run.sh from the repo if this is the newest bulletin."
    )
    raise_alarm(f"CLAUDE API FAILURE for {pdf_path.name}", details)
