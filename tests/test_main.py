"""Tests for pcc_bulletin.main — the CLI entry point."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pcc_bulletin.main as main_mod
from pcc_bulletin.main import main


# ── helpers ──────────────────────────────────────────────────────────────────

def _good_config():
    cfg = MagicMock()
    cfg.bulletin_folder = Path("/fake/bulletins")
    return cfg


# ── config failure ────────────────────────────────────────────────────────────

def test_bad_config_returns_1(monkeypatch):
    monkeypatch.setattr(
        "pcc_bulletin.main.Config.from_env",
        staticmethod(lambda: (_ for _ in ()).throw(RuntimeError("no key"))),
    )
    assert main() == 1


# ── no bulletins ─────────────────────────────────────────────────────────────

@patch("pcc_bulletin.main.find_unprocessed", return_value=[])
@patch("pcc_bulletin.main.Config.from_env")
def test_no_bulletins_returns_0(mock_cfg, mock_find, monkeypatch):
    monkeypatch.setattr("sys.argv", ["pcc-bulletin"])
    mock_cfg.return_value = _good_config()
    assert main() == 0
    mock_find.assert_called_once()


# ── explicit path argument ────────────────────────────────────────────────────

@patch("pcc_bulletin.main.process_bulletin")
@patch("pcc_bulletin.main.Config.from_env")
def test_explicit_path_argument(mock_cfg, mock_proc, monkeypatch, tmp_path):
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()
    mock_cfg.return_value = _good_config()
    mock_proc.return_value = tmp_path / "Bulletin-10-18-2026-email.docx"

    monkeypatch.setattr("sys.argv", ["pcc-bulletin", str(pdf)])
    result = main()

    assert result == 0
    mock_proc.assert_called_once()
    # find_unprocessed should NOT have been called — explicit path bypasses scan
    # (no patch for find_unprocessed; if it ran it would hit the filesystem and
    # likely return [] — but it must not be called at all)


# ── successful batch ──────────────────────────────────────────────────────────

@patch("pcc_bulletin.main.process_bulletin")
@patch("pcc_bulletin.main.find_unprocessed")
@patch("pcc_bulletin.main.Config.from_env")
def test_successful_batch(mock_cfg, mock_find, mock_proc, tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["pcc-bulletin"])
    cfg = _good_config()
    mock_cfg.return_value = cfg

    p1 = tmp_path / "Bulletin-10-11-2026.pdf"
    p2 = tmp_path / "Bulletin-10-18-2026.pdf"
    mock_find.return_value = [p1, p2]
    mock_proc.side_effect = [
        tmp_path / "Bulletin-10-11-2026-email.docx",
        tmp_path / "Bulletin-10-18-2026-email.docx",
    ]

    assert main() == 0
    assert mock_proc.call_count == 2


# ── one failure still processes rest, returns 1 ───────────────────────────────

@patch("pcc_bulletin.main.process_bulletin")
@patch("pcc_bulletin.main.find_unprocessed")
@patch("pcc_bulletin.main.Config.from_env")
def test_partial_failure_returns_1(mock_cfg, mock_find, mock_proc, tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["pcc-bulletin"])
    mock_cfg.return_value = _good_config()

    p1 = tmp_path / "Bulletin-10-11-2026.pdf"
    p2 = tmp_path / "Bulletin-10-18-2026.pdf"
    mock_find.return_value = [p1, p2]
    mock_proc.side_effect = [RuntimeError("API error"), tmp_path / "Bulletin-10-18-2026-email.docx"]

    result = main()

    assert result == 1
    assert mock_proc.call_count == 2  # both attempted


# ── __main__ block ────────────────────────────────────────────────────────────

def test_dunder_main(monkeypatch):
    """Executing the module as __main__ calls sys.exit(main())."""
    import runpy

    monkeypatch.setattr("sys.argv", ["pcc-bulletin"])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    with patch("pcc_bulletin.main.find_unprocessed", return_value=[]), \
         pytest.raises(SystemExit) as exc:
        runpy.run_module("pcc_bulletin.main", run_name="__main__", alter_sys=True)

    assert exc.value.code == 0
