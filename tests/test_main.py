"""Tests for pcc_bulletin.main — the CLI entry point."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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


@patch("pcc_bulletin.main.raise_alarm")
@patch("pcc_bulletin.main.Config.from_env", side_effect=RuntimeError("no key"))
def test_bad_config_alarms_once(mock_cfg, mock_alarm, caplog):
    assert main() == 1
    assert main() == 1  # re-triggered by the watcher: no second alert
    mock_alarm.assert_called_once()
    assert "no key" in mock_alarm.call_args.args[1]
    assert "already alerted" in caplog.text


@patch("pcc_bulletin.main.find_unprocessed", return_value=[])
@patch("pcc_bulletin.main.raise_alarm")
@patch("pcc_bulletin.main.Config.from_env")
def test_config_alarm_rearms_after_fix(mock_cfg, mock_alarm, mock_find, monkeypatch):
    monkeypatch.setattr("sys.argv", ["pcc-bulletin"])
    mock_cfg.side_effect = RuntimeError("no key")
    main()
    mock_cfg.side_effect = None
    mock_cfg.return_value = _good_config()
    main()  # fixed
    mock_cfg.side_effect = RuntimeError("no key")
    main()  # broken again: alert again
    assert mock_alarm.call_count == 2


# ── no retry loop after a Claude failure ──────────────────────────────────────


@patch("pcc_bulletin.main.process_bulletin")
@patch("pcc_bulletin.main.find_unprocessed")
@patch("pcc_bulletin.main.Config.from_env")
def test_watcher_run_skips_previously_failed(
    mock_cfg, mock_find, mock_proc, tmp_path, monkeypatch, caplog
):
    from pcc_bulletin.failure_state import failed_before, record_failure

    monkeypatch.setattr("sys.argv", ["pcc-bulletin"])
    mock_cfg.return_value = _good_config()
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()
    mock_find.return_value = [pdf]
    record_failure(pdf)

    assert main() == 0
    mock_proc.assert_not_called()
    assert "Skipping Bulletin-10-18-2026.pdf" in caplog.text

    # a manual run retries, and success clears the failure
    monkeypatch.setattr("sys.argv", ["pcc-bulletin", str(pdf)])
    mock_proc.return_value = tmp_path / "Bulletin-10-18-2026-email.docx"
    assert main() == 0
    mock_proc.assert_called_once()
    assert not failed_before(pdf)


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


# ── --latest (force) mode ─────────────────────────────────────────────────────


@patch("pcc_bulletin.main.process_bulletin")
@patch("pcc_bulletin.main.find_unprocessed")
@patch("pcc_bulletin.main.find_latest")
@patch("pcc_bulletin.main.Config.from_env")
def test_latest_flag_reprocesses_newest(
    mock_cfg, mock_latest, mock_find, mock_proc, tmp_path, monkeypatch
):
    monkeypatch.setattr("sys.argv", ["pcc-bulletin", "--latest"])
    cfg = _good_config()
    mock_cfg.return_value = cfg
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    mock_latest.return_value = [pdf]
    mock_proc.return_value = tmp_path / "Bulletin-10-18-2026-email.docx"

    assert main() == 0
    mock_latest.assert_called_once_with(cfg.bulletin_folder)
    mock_find.assert_not_called()
    mock_proc.assert_called_once_with(pdf, cfg)


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

    with (
        patch("pcc_bulletin.main.find_unprocessed", return_value=[]),
        pytest.raises(SystemExit) as exc,
    ):
        runpy.run_module("pcc_bulletin.main", run_name="__main__", alter_sys=True)

    assert exc.value.code == 0
