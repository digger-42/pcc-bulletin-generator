"""
Email alerts for failures that need a human's attention.

Alerts go out over SMTP using settings from the environment (see the README):

    PCC_SMTP_USER       login for the SMTP server (required to send alerts)
    PCC_SMTP_PASSWORD   password; for Gmail, an app password (required)
    PCC_SMTP_HOST       default smtp.gmail.com
    PCC_SMTP_PORT       default 587 (STARTTLS); 465 uses implicit TLS
    PCC_ALERT_TO        recipient(s), comma-separated; default PCC_SMTP_USER
    PCC_ALERT_FROM      sender; default PCC_SMTP_USER

Every alert is also appended to a Markdown error log, by default
"HEY-CLAUDE-API-ERRORS.md" in the bulletin folder (override with PCC_ERROR_LOG).

Raising an alarm never raises. If the alert can't be sent, that is logged at
CRITICAL level along with the original problem, so it still shows up loudly in
the journal.
"""

import logging
import os
import smtplib
import socket
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

log = logging.getLogger(__name__)

BANNER = "!" * 72
ERROR_LOG_NAME = "HEY-CLAUDE-API-ERRORS.md"
DEFAULT_BULLETIN_FOLDER = "/home/dan/Documents/PCC Bulletins"


def error_log_path() -> Path:
    """Where error entries are appended: PCC_ERROR_LOG, else the bulletin folder."""
    explicit = os.environ.get("PCC_ERROR_LOG", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    folder = os.environ.get("PCC_BULLETIN_FOLDER", "").strip() or DEFAULT_BULLETIN_FOLDER
    return Path(folder).expanduser() / ERROR_LOG_NAME


def append_error_log(subject: str, body: str, path: Path | None = None) -> bool:
    """Append one entry to the Markdown error log. Returns True on success; never raises."""
    try:
        path = path or error_log_path()
        new_file = not path.exists()
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        with path.open("a", encoding="utf-8") as f:
            if new_file:
                f.write("# Claude API errors from pcc-bulletin\n\nNewest entries at the bottom.\n")
            f.write(f"\n## {stamp}: {subject}\n\n```\n{body}\n```\n")
        log.info("Error appended to %s", path)
        return True
    except Exception as exc:  # noqa: BLE001 — logging the error must never crash
        log.critical(
            "%s\nFAILED TO APPEND TO ERROR LOG %s: %s: %s\n%s",
            BANNER,
            path,
            type(exc).__name__,
            exc,
            BANNER,
        )
        return False


def raise_alarm(subject: str, body: str) -> None:
    """
    Report a failure every way we can: a CRITICAL log entry (journal), an entry
    in the Markdown error log, and an alert email. Never raises.
    """
    log.critical("%s\n%s\n%s\n%s", BANNER, subject, body, BANNER)
    append_error_log(subject, body)
    send_alert(subject, body)


@dataclass
class AlertConfig:
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = field(default="", repr=False)
    alert_from: str = ""
    alert_to: list[str] = field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_password and self.alert_to)

    def missing(self) -> list[str]:
        """Names of the env vars that still need to be set."""
        names = []
        if not self.smtp_user:
            names.append("PCC_SMTP_USER")
        if not self.smtp_password:
            names.append("PCC_SMTP_PASSWORD")
        if not self.alert_to:
            names.append("PCC_ALERT_TO")
        return names

    @classmethod
    def from_env(cls) -> "AlertConfig":
        user = os.environ.get("PCC_SMTP_USER", "").strip()
        port_raw = os.environ.get("PCC_SMTP_PORT", "").strip() or "587"
        try:
            port = int(port_raw)
        except ValueError:
            log.error("PCC_SMTP_PORT=%r is not a number; using 587.", port_raw)
            port = 587
        to_raw = os.environ.get("PCC_ALERT_TO", "").strip() or user
        return cls(
            smtp_host=os.environ.get("PCC_SMTP_HOST", "").strip() or "smtp.gmail.com",
            smtp_port=port,
            smtp_user=user,
            smtp_password=os.environ.get("PCC_SMTP_PASSWORD", ""),
            alert_from=os.environ.get("PCC_ALERT_FROM", "").strip() or user,
            alert_to=[a.strip() for a in to_raw.split(",") if a.strip()],
        )


def warn_if_unconfigured(config: AlertConfig | None = None) -> None:
    """Log a warning at startup if failure alerts can't be emailed."""
    config = config or AlertConfig.from_env()
    if not config.is_configured:
        log.warning(
            "Email alerts are NOT configured (missing %s in ~/.config/pcc-bulletin/env). "
            "Claude API failures will only be logged, not emailed.",
            ", ".join(config.missing()) or "settings",
        )


def send_alert(subject: str, body: str, config: AlertConfig | None = None) -> bool:
    """
    Email an alert. Returns True if it was sent, False otherwise.

    Never raises: every failure is logged at CRITICAL level instead.
    """
    try:
        config = config or AlertConfig.from_env()
        if not config.is_configured:
            log.critical(
                "%s\nALERT EMAIL NOT SENT: email alerts are not configured (missing %s).\n"
                "Subject: %s\n%s",
                BANNER,
                ", ".join(config.missing()) or "settings",
                subject,
                BANNER,
            )
            return False

        msg = EmailMessage()
        msg["Subject"] = f"[PCC Bulletin] {subject}"
        msg["From"] = config.alert_from
        msg["To"] = ", ".join(config.alert_to)
        msg["X-Priority"] = "1"
        msg["Importance"] = "high"
        msg.set_content(f"{body}\n\n-- \nSent by pcc-bulletin on {socket.gethostname()}\n")

        context = ssl.create_default_context()
        if config.smtp_port == 465:
            with smtplib.SMTP_SSL(
                config.smtp_host, config.smtp_port, context=context, timeout=30
            ) as smtp:
                smtp.login(config.smtp_user, config.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as smtp:
                smtp.starttls(context=context)
                smtp.login(config.smtp_user, config.smtp_password)
                smtp.send_message(msg)

        log.info("Alert email sent to %s", ", ".join(config.alert_to))
        return True
    except Exception as exc:  # noqa: BLE001 — an alert must never take the program down
        log.critical(
            "%s\nFAILED TO SEND ALERT EMAIL: %s: %s\nThe alert was:\nSubject: %s\n%s\n%s",
            BANNER,
            type(exc).__name__,
            exc,
            subject,
            body,
            BANNER,
        )
        return False
