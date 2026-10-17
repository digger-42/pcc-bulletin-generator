from datetime import date, timedelta
from pathlib import Path

from .processor import is_processed, parse_sunday_from_filename


def upcoming_sunday(today: date) -> date:
    """Return *today* if it is a Sunday, otherwise the next Sunday."""
    return today + timedelta(days=(6 - today.weekday()) % 7)


def find_unprocessed(folder: Path, today: date | None = None) -> list[Path]:
    """
    Return the bulletin PDF in *folder* dated for the upcoming Sunday, if it has
    not yet been processed. Bulletins for any other date are ignored.
    """
    if not folder.is_dir():
        return []
    sunday = upcoming_sunday(today or date.today())
    return [
        p
        for p in sorted(folder.iterdir())
        if p.is_file() and parse_sunday_from_filename(p) == sunday and not is_processed(p)
    ]
