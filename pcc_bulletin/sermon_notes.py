from datetime import date
from pathlib import Path


def find_sermon_notes(sunday: date, notes_root: Path) -> Path | None:
    """
    Return the sermon notes PDF for *sunday*, or None if not found.

    Expected path:
        <notes_root>/<YYYY>/<YYYY-MM-DD>-sermon-notes*.pdf
    """
    year_dir = notes_root / str(sunday.year)
    if not year_dir.is_dir():
        return None
    prefix = sunday.strftime("%Y-%m-%d")
    matches = sorted(year_dir.glob(f"{prefix}-sermon-notes*.pdf"))
    return matches[0] if matches else None
