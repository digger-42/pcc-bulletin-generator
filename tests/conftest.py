import pytest

_ALERT_VARS = (
    "PCC_SMTP_USER",
    "PCC_SMTP_PASSWORD",
    "PCC_SMTP_HOST",
    "PCC_SMTP_PORT",
    "PCC_ALERT_TO",
    "PCC_ALERT_FROM",
)


@pytest.fixture(autouse=True)
def _isolate_alerts(monkeypatch, tmp_path_factory):
    """Keep tests from emailing anyone or writing to the real error log / state dir."""
    for var in _ALERT_VARS:
        monkeypatch.delenv(var, raising=False)
    sandbox = tmp_path_factory.mktemp("alerts")
    monkeypatch.setenv("PCC_ERROR_LOG", str(sandbox / "HEY-CLAUDE-API-ERRORS.md"))
    monkeypatch.setenv("PCC_STATE_DIR", str(sandbox / "state"))
