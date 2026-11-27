import os

from pcc_bulletin import failure_state as fs


def test_record_and_clear(tmp_path):
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()
    assert not fs.failed_before(pdf)
    fs.record_failure(pdf)
    assert fs.failed_before(pdf)
    fs.clear_failure(pdf)
    assert not fs.failed_before(pdf)
    fs.clear_failure(pdf)  # clearing twice is harmless


def test_new_download_is_retried(tmp_path):
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()
    fs.record_failure(pdf)
    st = pdf.stat()
    os.utime(pdf, (st.st_atime, st.st_mtime + 60))
    assert not fs.failed_before(pdf)


def test_missing_pdf(tmp_path):
    pdf = tmp_path / "gone.pdf"
    fs.record_failure(pdf)
    assert fs.failed_before(pdf)


def test_corrupt_state_is_ignored(tmp_path, caplog):
    path = fs.state_file()
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2]")
    assert not fs.failed_before(tmp_path / "x.pdf")
    assert "unreadable" in caplog.text


def test_unwritable_state_is_logged(monkeypatch, tmp_path, caplog):
    blocker = tmp_path / "file"
    blocker.touch()
    monkeypatch.setenv("PCC_STATE_DIR", str(blocker / "sub"))
    fs.record_failure(tmp_path / "x.pdf")  # must not raise
    assert "Could not write" in caplog.text


def test_default_state_dir(monkeypatch):
    monkeypatch.delenv("PCC_STATE_DIR")
    assert str(fs.state_file()).endswith(".local/state/pcc-bulletin/claude-failures.json")


def test_config_error_alerts_once():
    assert fs.is_new_config_error("no key")
    assert not fs.is_new_config_error("no key")
    assert fs.is_new_config_error("different")
    fs.clear_config_error()
    assert fs.is_new_config_error("different")
    fs.clear_config_error()
    fs.clear_config_error()
