from datetime import date

import pytest

from pcc_bulletin.watcher import find_unprocessed, upcoming_sunday

# Thursday before Sunday 2026-10-18
THURSDAY = date(2026, 10, 15)


@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 10, 12), date(2026, 10, 18)),  # Monday
        (date(2026, 10, 15), date(2026, 10, 18)),  # Thursday
        (date(2026, 10, 17), date(2026, 10, 18)),  # Saturday
        (date(2026, 10, 18), date(2026, 10, 18)),  # Sunday itself
    ],
)
def test_upcoming_sunday(today, expected):
    assert upcoming_sunday(today) == expected


def test_empty_folder(tmp_path):
    assert find_unprocessed(tmp_path, THURSDAY) == []


def test_missing_folder(tmp_path):
    assert find_unprocessed(tmp_path / "nope", THURSDAY) == []


def test_upcoming_bulletin_found(tmp_path):
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()
    assert find_unprocessed(tmp_path, THURSDAY) == [pdf]


def test_defaults_to_today(tmp_path, monkeypatch):
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()

    class FakeDate(date):
        @classmethod
        def today(cls):
            return THURSDAY

    monkeypatch.setattr("pcc_bulletin.watcher.date", FakeDate)
    assert find_unprocessed(tmp_path) == [pdf]


def test_lowercase_name_matched(tmp_path):
    pdf = tmp_path / "bulletin-10-18-2026.pdf"
    pdf.touch()
    assert find_unprocessed(tmp_path, THURSDAY) == [pdf]


def test_already_processed_excluded(tmp_path):
    (tmp_path / "Bulletin-10-18-2026.pdf").touch()
    (tmp_path / "Bulletin-10-18-2026-email.docx").touch()
    assert find_unprocessed(tmp_path, THURSDAY) == []


def test_older_and_future_bulletins_ignored(tmp_path):
    (tmp_path / "Bulletin-10-11-2026.pdf").touch()  # last week, unprocessed
    (tmp_path / "Bulletin-10-25-2026.pdf").touch()  # next week
    assert find_unprocessed(tmp_path, THURSDAY) == []


def test_non_bulletin_files_ignored(tmp_path):
    (tmp_path / "random.pdf").touch()
    (tmp_path / "logo.png").touch()
    (tmp_path / "Bulletin-10-18-2026.pdf").mkdir()  # directory, not a file
    assert find_unprocessed(tmp_path, THURSDAY) == []


def test_mixed_contents(tmp_path):
    (tmp_path / "Bulletin-10-04-2026.pdf").touch()
    (tmp_path / "Bulletin-10-11-2026.pdf").touch()
    (tmp_path / "Bulletin-10-11-2026-email.docx").touch()
    upcoming = tmp_path / "Bulletin-10-18-2026.pdf"
    upcoming.touch()
    (tmp_path / "random.pdf").touch()
    assert find_unprocessed(tmp_path, THURSDAY) == [upcoming]
