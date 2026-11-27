import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from pcc_bulletin import alerts
from pcc_bulletin.alerts import (
    AlertConfig,
    append_error_log,
    error_log_path,
    raise_alarm,
    send_alert,
    warn_if_unconfigured,
)


def _configured(**overrides) -> AlertConfig:
    kw = dict(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="bot@example.com",
        smtp_password="pw",
        alert_from="bot@example.com",
        alert_to=["me@example.com"],
    )
    kw.update(overrides)
    return AlertConfig(**kw)


# ── AlertConfig ──────────────────────────────────────────────────────────────


def test_config_defaults_to_user(monkeypatch):
    monkeypatch.setenv("PCC_SMTP_USER", "bot@example.com")
    monkeypatch.setenv("PCC_SMTP_PASSWORD", "pw")
    cfg = AlertConfig.from_env()
    assert cfg.smtp_host == "smtp.gmail.com"
    assert cfg.smtp_port == 587
    assert cfg.alert_from == "bot@example.com"
    assert cfg.alert_to == ["bot@example.com"]
    assert cfg.is_configured
    assert "pw" not in repr(cfg)


def test_config_all_vars(monkeypatch):
    monkeypatch.setenv("PCC_SMTP_USER", "bot@example.com")
    monkeypatch.setenv("PCC_SMTP_PASSWORD", "pw")
    monkeypatch.setenv("PCC_SMTP_HOST", "mail.example.com")
    monkeypatch.setenv("PCC_SMTP_PORT", "465")
    monkeypatch.setenv("PCC_ALERT_TO", "a@example.com, b@example.com,")
    monkeypatch.setenv("PCC_ALERT_FROM", "from@example.com")
    cfg = AlertConfig.from_env()
    assert cfg.smtp_host == "mail.example.com"
    assert cfg.smtp_port == 465
    assert cfg.alert_to == ["a@example.com", "b@example.com"]
    assert cfg.alert_from == "from@example.com"


def test_config_bad_port(monkeypatch, caplog):
    monkeypatch.setenv("PCC_SMTP_PORT", "abc")
    assert AlertConfig.from_env().smtp_port == 587
    assert "not a number" in caplog.text


def test_missing_lists_everything_when_empty():
    assert AlertConfig().missing() == ["PCC_SMTP_USER", "PCC_SMTP_PASSWORD", "PCC_ALERT_TO"]
    assert _configured().missing() == []


def test_warn_if_unconfigured(caplog):
    warn_if_unconfigured()
    assert "NOT configured" in caplog.text


def test_warn_if_configured_is_quiet(caplog):
    warn_if_unconfigured(_configured())
    assert caplog.text == ""


# ── send_alert ───────────────────────────────────────────────────────────────


def test_send_unconfigured_logs_critical(caplog):
    assert send_alert("Subj", "Body") is False
    assert "ALERT EMAIL NOT SENT" in caplog.text
    assert any(r.levelno == logging.CRITICAL for r in caplog.records)


@patch("pcc_bulletin.alerts.smtplib.SMTP")
def test_send_starttls(mock_smtp):
    smtp = mock_smtp.return_value.__enter__.return_value
    assert send_alert("Subj", "Body", _configured()) is True
    mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=30)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("bot@example.com", "pw")
    msg = smtp.send_message.call_args.args[0]
    assert msg["Subject"] == "[PCC Bulletin] Subj"
    assert msg["To"] == "me@example.com"
    assert "Body" in msg.get_content()


@patch("pcc_bulletin.alerts.smtplib.SMTP_SSL")
def test_send_implicit_tls(mock_ssl):
    smtp = mock_ssl.return_value.__enter__.return_value
    assert send_alert("Subj", "Body", _configured(smtp_port=465)) is True
    smtp.login.assert_called_once()
    smtp.send_message.assert_called_once()


@patch("pcc_bulletin.alerts.smtplib.SMTP", side_effect=OSError("connection refused"))
def test_send_failure_never_raises(mock_smtp, caplog):
    assert send_alert("Subj", "Body text", _configured()) is False
    assert "FAILED TO SEND ALERT EMAIL" in caplog.text
    assert "connection refused" in caplog.text
    assert "Body text" in caplog.text  # the original alert isn't lost


def test_send_reads_env_when_no_config(monkeypatch):
    monkeypatch.setenv("PCC_SMTP_USER", "bot@example.com")
    monkeypatch.setenv("PCC_SMTP_PASSWORD", "pw")
    with patch("pcc_bulletin.alerts.smtplib.SMTP") as mock_smtp:
        assert send_alert("Subj", "Body") is True
    mock_smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=30)


# ── error log ────────────────────────────────────────────────────────────────


def test_error_log_path_explicit(monkeypatch, tmp_path):
    monkeypatch.setenv("PCC_ERROR_LOG", str(tmp_path / "x.md"))
    assert error_log_path() == tmp_path / "x.md"


def test_error_log_path_follows_bulletin_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("PCC_ERROR_LOG")
    monkeypatch.setenv("PCC_BULLETIN_FOLDER", str(tmp_path))
    assert error_log_path() == tmp_path / "HEY-CLAUDE-API-ERRORS.md"


def test_error_log_path_default(monkeypatch):
    monkeypatch.delenv("PCC_ERROR_LOG")
    monkeypatch.delenv("PCC_BULLETIN_FOLDER", raising=False)
    assert error_log_path() == Path("/home/dan/Documents/PCC Bulletins/HEY-CLAUDE-API-ERRORS.md")


def test_append_creates_then_appends(tmp_path):
    path = tmp_path / "errors.md"
    assert append_error_log("First", "one", path) is True
    assert append_error_log("Second", "two", path) is True
    text = path.read_text()
    assert text.count("# Claude API errors") == 1
    assert text.index("First") < text.index("Second")
    assert "```\none\n```" in text


def test_append_failure_never_raises(tmp_path, caplog):
    assert append_error_log("S", "B", tmp_path / "missing-dir" / "e.md") is False
    assert "FAILED TO APPEND TO ERROR LOG" in caplog.text


# ── raise_alarm ──────────────────────────────────────────────────────────────


def test_raise_alarm_does_all_three(caplog):
    with patch.object(alerts, "send_alert") as mock_send:
        raise_alarm("Subj", "Body")
    assert "Subj" in caplog.text and alerts.BANNER in caplog.text
    assert "Subj" in error_log_path().read_text()
    mock_send.assert_called_once_with("Subj", "Body")


def test_raise_alarm_survives_everything(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("PCC_ERROR_LOG", str(tmp_path / "nope" / "e.md"))
    monkeypatch.setenv("PCC_SMTP_USER", "bot@example.com")
    monkeypatch.setenv("PCC_SMTP_PASSWORD", "pw")
    with patch("pcc_bulletin.alerts.smtplib.SMTP", side_effect=OSError("down")):
        raise_alarm("Subj", "Body")  # must not raise
    assert "FAILED TO APPEND" in caplog.text
    assert "FAILED TO SEND ALERT EMAIL" in caplog.text


def test_send_alert_config_error_never_raises(caplog):
    with patch.object(AlertConfig, "from_env", side_effect=RuntimeError("boom")):
        assert send_alert("S", "B") is False
    assert "boom" in caplog.text


@pytest.fixture(autouse=True)
def _capture(caplog):
    caplog.set_level(logging.INFO)
