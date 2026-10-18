from datetime import date

import pytest

from pcc_bulletin.sermon_notes import find_sermon_notes


@pytest.fixture()
def notes_root(tmp_path):
    return tmp_path


def test_found(notes_root):
    sunday = date(2026, 10, 18)
    year_dir = notes_root / "2026"
    year_dir.mkdir()
    expected = year_dir / "2026-10-18-sermon-notes.pdf"
    expected.touch()

    result = find_sermon_notes(sunday, notes_root)
    assert result == expected


def test_found_with_suffix(notes_root):
    sunday = date(2026, 10, 18)
    year_dir = notes_root / "2026"
    year_dir.mkdir()
    expected = year_dir / "2026-10-18-sermon-notes-draft.pdf"
    expected.touch()

    result = find_sermon_notes(sunday, notes_root)
    assert result == expected


def test_no_year_dir(notes_root):
    sunday = date(2026, 10, 18)
    result = find_sermon_notes(sunday, notes_root)
    assert result is None


def test_no_matching_file(notes_root):
    sunday = date(2026, 10, 18)
    year_dir = notes_root / "2026"
    year_dir.mkdir()
    (year_dir / "2026-10-25-sermon-notes.pdf").touch()  # wrong date

    result = find_sermon_notes(sunday, notes_root)
    assert result is None


def test_multiple_matches_returns_first_sorted(notes_root):
    sunday = date(2026, 10, 18)
    year_dir = notes_root / "2026"
    year_dir.mkdir()
    f_a = year_dir / "2026-10-18-sermon-notes-a.pdf"
    f_b = year_dir / "2026-10-18-sermon-notes-b.pdf"
    f_b.touch()
    f_a.touch()

    result = find_sermon_notes(sunday, notes_root)
    assert result == f_a  # alphabetically first


def test_different_year(notes_root):
    sunday = date(2027, 1, 2)
    year_dir = notes_root / "2027"
    year_dir.mkdir()
    expected = year_dir / "2027-01-02-sermon-notes.pdf"
    expected.touch()

    result = find_sermon_notes(sunday, notes_root)
    assert result == expected
