from pcc_bulletin.watcher import find_unprocessed


def test_empty_folder(tmp_path):
    assert find_unprocessed(tmp_path) == []


def test_single_unprocessed(tmp_path):
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()
    assert find_unprocessed(tmp_path) == [pdf]


def test_already_processed_excluded(tmp_path):
    pdf = tmp_path / "Bulletin-10-18-2026.pdf"
    pdf.touch()
    (tmp_path / "Bulletin-10-18-2026-email.docx").touch()
    assert find_unprocessed(tmp_path) == []


def test_non_matching_pdf_ignored(tmp_path):
    (tmp_path / "random.pdf").touch()
    assert find_unprocessed(tmp_path) == []


def test_mixed_contents(tmp_path):
    processed = tmp_path / "Bulletin-10-11-2026.pdf"
    processed.touch()
    (tmp_path / "Bulletin-10-11-2026-email.docx").touch()

    unprocessed = tmp_path / "Bulletin-10-18-2026.pdf"
    unprocessed.touch()

    (tmp_path / "random.pdf").touch()

    assert find_unprocessed(tmp_path) == [unprocessed]


def test_sorted_order(tmp_path):
    b1 = tmp_path / "Bulletin-10-18-2026.pdf"
    b2 = tmp_path / "Bulletin-10-25-2026.pdf"
    b2.touch()
    b1.touch()
    assert find_unprocessed(tmp_path) == [b1, b2]
