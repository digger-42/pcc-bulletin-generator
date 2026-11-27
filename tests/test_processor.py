from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from pcc_bulletin.config import Config
from pcc_bulletin.processor import (
    is_processed,
    output_path_for,
    parse_sunday_from_filename,
    process_bulletin,
)


def _cfg(tmp_path: Path) -> Config:
    return Config(
        api_key="sk-test",
        bulletin_folder=tmp_path,
        sermon_notes_root=tmp_path / "notes",
        model="claude-test",
    )


# ── parse_sunday_from_filename ──────────────────────────────────────────────


def test_parse_valid(tmp_path):
    assert parse_sunday_from_filename(tmp_path / "Bulletin-10-18-2026.pdf") == date(2026, 10, 18)


def test_parse_allows_spaces_before_extension(tmp_path):
    p = tmp_path / "Bulletin-10-18-2026   .pdf"
    assert parse_sunday_from_filename(p) == date(2026, 10, 18)


def test_parse_is_case_sensitive(tmp_path):
    assert parse_sunday_from_filename(tmp_path / "bulletin-10-18-2026.pdf") is None


def test_parse_invalid_returns_none(tmp_path):
    assert parse_sunday_from_filename(tmp_path / "random-file.pdf") is None


def test_parse_non_pdf_returns_none(tmp_path):
    assert parse_sunday_from_filename(tmp_path / "Bulletin-10-18-2026.docx") is None


# ── output_path_for ─────────────────────────────────────────────────────────


def test_output_path(tmp_path):
    p = tmp_path / "Bulletin-10-18-2026.pdf"
    assert output_path_for(p) == tmp_path / "Bulletin-10-18-2026-email.docx"


def test_output_path_drops_spaces_before_extension(tmp_path):
    p = tmp_path / "Bulletin-10-18-2026  .pdf"
    assert output_path_for(p) == tmp_path / "Bulletin-10-18-2026-email.docx"


# ── is_processed ────────────────────────────────────────────────────────────


def test_is_processed_false(tmp_path):
    p = tmp_path / "Bulletin-10-18-2026.pdf"
    p.touch()
    assert not is_processed(p)


def test_is_processed_true(tmp_path):
    p = tmp_path / "Bulletin-10-18-2026.pdf"
    p.touch()
    (tmp_path / "Bulletin-10-18-2026-email.docx").touch()
    assert is_processed(p)


def test_is_processed_docx_with_spaces(tmp_path):
    p = tmp_path / "Bulletin-10-18-2026 .pdf"
    p.touch()
    (tmp_path / "Bulletin-10-18-2026-email   .docx").touch()
    assert is_processed(p)


def test_is_processed_ignores_other_docx(tmp_path):
    p = tmp_path / "Bulletin-10-18-2026.pdf"
    p.touch()
    (tmp_path / "Bulletin-10-25-2026-email.docx").touch()
    (tmp_path / "Bulletin-10-18-2026-email-old.docx").touch()
    assert not is_processed(p)


def test_is_processed_missing_folder(tmp_path):
    assert not is_processed(tmp_path / "nope" / "Bulletin-10-18-2026.pdf")


# ── process_bulletin ─────────────────────────────────────────────────────────


@patch("pcc_bulletin.processor.build_docx", return_value=b"docx")
@patch("pcc_bulletin.processor.generate_email", return_value="email text")
@patch("pcc_bulletin.processor.find_sermon_notes")
@patch("pcc_bulletin.processor.extract_text")
def test_process_with_notes(mock_extract, mock_notes, mock_gen, mock_docx, tmp_path):
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()
    notes_path = MagicMock(spec=Path)
    mock_notes.return_value = notes_path
    mock_extract.side_effect = ["bulletin text", "notes text"]

    out = process_bulletin(pdf, _cfg(tmp_path))

    assert out == tmp_path / "Bulletin-10-18-2026-email.docx"
    assert out.read_bytes() == b"docx"
    mock_gen.assert_called_once_with("bulletin text", "sk-test", "notes text", "claude-test")
    # extract_text called twice: bulletin then notes
    assert mock_extract.call_count == 2


@patch("pcc_bulletin.processor.build_docx", return_value=b"docx")
@patch("pcc_bulletin.processor.generate_email", return_value="email text")
@patch("pcc_bulletin.processor.find_sermon_notes", return_value=None)
@patch("pcc_bulletin.processor.extract_text", return_value="bulletin text")
def test_process_without_notes(mock_extract, mock_notes, mock_gen, mock_docx, tmp_path):
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()

    process_bulletin(pdf, _cfg(tmp_path))

    mock_gen.assert_called_once_with("bulletin text", "sk-test", "", "claude-test")
    mock_extract.assert_called_once()  # only bulletin, not notes


@patch("pcc_bulletin.processor.build_docx", return_value=b"docx")
@patch("pcc_bulletin.processor.generate_email", return_value="email text")
@patch("pcc_bulletin.processor.find_sermon_notes")
@patch("pcc_bulletin.processor.extract_text", return_value="bulletin text")
def test_process_unrecognised_filename_skips_notes(
    mock_extract, mock_notes, mock_gen, mock_docx, tmp_path
):
    pdf = tmp_path / "random-name.pdf"
    pdf.touch()

    process_bulletin(pdf, _cfg(tmp_path))

    mock_notes.assert_not_called()
    mock_gen.assert_called_once_with("bulletin text", "sk-test", "", "claude-test")


# ── Claude API failure ───────────────────────────────────────────────────────


@patch("pcc_bulletin.alerts.send_alert")
@patch("pcc_bulletin.processor.generate_email")
@patch("pcc_bulletin.processor.find_sermon_notes", return_value=None)
@patch("pcc_bulletin.processor.extract_text", return_value="bulletin text")
def test_claude_failure_alerts_logs_and_reraises(
    mock_extract, mock_notes, mock_gen, mock_send, tmp_path, caplog
):
    import pytest

    from pcc_bulletin.alerts import error_log_path
    from pcc_bulletin.claude_client import ClaudeAPIError
    from pcc_bulletin.failure_state import failed_before

    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()
    mock_gen.side_effect = ClaudeAPIError("HTTP status: 529")

    with pytest.raises(ClaudeAPIError):
        process_bulletin(pdf, _cfg(tmp_path))

    # nothing written, failure remembered
    assert not (tmp_path / "Bulletin-10-18-2026-email.docx").exists()
    assert failed_before(pdf)
    # loud log
    assert "CLAUDE API FAILURE for Bulletin-10-18-2026.pdf" in caplog.text
    # error log file
    log_text = error_log_path().read_text()
    assert "Bulletin-10-18-2026.pdf" in log_text and "HTTP status: 529" in log_text
    # email with context
    subject, body = mock_send.call_args.args
    assert "Bulletin-10-18-2026.pdf" in subject
    assert "Step: generating the email text" in body
    assert "Model: claude-test" in body
    assert "Sermon notes included: no" in body
    assert "HTTP status: 529" in body
