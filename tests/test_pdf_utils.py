from pathlib import Path
from unittest.mock import MagicMock, patch

from pcc_bulletin.pdf_utils import extract_text


def _make_mock_doc(page_texts: list[str]) -> list[MagicMock]:
    pages = []
    for text in page_texts:
        page = MagicMock()
        page.get_text.return_value = text
        pages.append(page)
    return pages


def test_extract_from_path():
    mock_doc = _make_mock_doc(["Hello world"])
    with patch("pcc_bulletin.pdf_utils.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        result = extract_text(Path("/fake/bulletin.pdf"))

    mock_fitz.open.assert_called_once_with("/fake/bulletin.pdf")
    assert result == "Hello world"


def test_extract_from_bytes():
    fake_bytes = b"%PDF-1.4 fake content"
    mock_doc = _make_mock_doc(["Page one ", "Page two"])
    with patch("pcc_bulletin.pdf_utils.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        result = extract_text(fake_bytes)

    mock_fitz.open.assert_called_once_with(stream=fake_bytes, filetype="pdf")
    assert result == "Page one Page two"


def test_extract_multipage():
    mock_doc = _make_mock_doc(["A", "B", "C"])
    with patch("pcc_bulletin.pdf_utils.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        result = extract_text(b"bytes")

    assert result == "ABC"


def test_extract_empty_doc():
    mock_doc = _make_mock_doc([])
    with patch("pcc_bulletin.pdf_utils.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        result = extract_text(b"bytes")

    assert result == ""
