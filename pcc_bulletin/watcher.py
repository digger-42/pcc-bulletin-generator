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


def find_latest(folder: Path) -> list[Path]:
    """
    Return the most recently downloaded bulletin PDF in *folder* (newest
    modification time), regardless of its date or whether it was already
    processed. Files not named like a bulletin are ignored.
    """
    if not folder.is_dir():
        return []
    bulletins = [
        p for p in folder.iterdir() if p.is_file() and parse_sunday_from_filename(p) is not None
    ]
    if not bulletins:
        return []
    return [max(bulletins, key=lambda p: p.stat().st_mtime)]
