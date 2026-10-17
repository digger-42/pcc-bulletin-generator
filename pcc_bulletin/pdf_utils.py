from pathlib import Path

import pymupdf as fitz


def extract_text(source: Path | bytes) -> str:
    """Extract plain text from a PDF given as a file path or raw bytes."""
    if isinstance(source, (str, Path)):
        doc = fitz.open(str(source))
    else:
        doc = fitz.open(stream=source, filetype="pdf")
    return "".join(page.get_text() for page in doc)
