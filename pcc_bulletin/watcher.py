from pathlib import Path

from .processor import BULLETIN_PATTERN, is_processed


def find_unprocessed(folder: Path) -> list[Path]:
    """
    Return all bulletin PDFs in *folder* that have not yet been processed,
    sorted by filename (which sorts chronologically given MM-DD-YYYY naming).
    """
    return [
        p
        for p in sorted(folder.glob("Bulletin-*.pdf"))
        if BULLETIN_PATTERN.match(p.name) and not is_processed(p)
    ]
