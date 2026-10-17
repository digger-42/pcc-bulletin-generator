import io

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

from pcc_bulletin.docx_builder import build_docx

FULL_TEXT = """\
Dear Plainfield Christian Church Friends,

This Sunday Steve Higgs brings a powerful message from Romans 8.

Rapha Support Ministry meets Tuesday at 7pm.

See the bulletin for details: https://pccmi.org/bulletin
UPCOMING_TABLE
DATE_ROW: Fall Potluck | Sun, Oct 25 @ 12:00 pm
DATE_ROW: Men's Breakfast | Sat, Oct 31 @ 8:00 am
"""


def _load(docx_bytes: bytes) -> Document:
    return Document(io.BytesIO(docx_bytes))


def test_returns_bytes():
    result = build_docx(FULL_TEXT)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_table_created_with_header():
    doc = _load(build_docx(FULL_TEXT))
    assert len(doc.tables) == 1
    hdr = doc.tables[0].rows[0]
    assert hdr.cells[0].text == "Event"
    assert hdr.cells[1].text == "Date & Time"


def test_table_rows_populated():
    doc = _load(build_docx(FULL_TEXT))
    table = doc.tables[0]
    assert table.rows[1].cells[0].text == "Fall Potluck"
    assert table.rows[1].cells[1].text == "Sun, Oct 25 @ 12:00 pm"
    assert table.rows[2].cells[0].text == "Men's Breakfast"
    assert table.rows[2].cells[1].text == "Sat, Oct 31 @ 8:00 am"


def test_no_table_when_no_rows():
    text = "Dear friends,\n\nSome content.\nUPCOMING_TABLE\n"
    doc = _load(build_docx(text))
    assert len(doc.tables) == 0


def test_malformed_date_row_skipped():
    # DATE_ROW with no pipe delimiter should be silently dropped
    text = "Dear friends,\nUPCOMING_TABLE\nDATE_ROW: No pipe here\nDATE_ROW: Event | Date\n"
    doc = _load(build_docx(text))
    assert len(doc.tables) == 1
    assert doc.tables[0].rows[1].cells[0].text == "Event"


def test_looking_ahead_directly_above_table():
    text = "Looking ahead:\nSome item.\nUPCOMING_TABLE\nDATE_ROW: E | D\n"
    doc = _load(build_docx(text))
    body = doc.element.body
    table_el = doc.tables[0]._tbl
    prev = table_el.getprevious()
    assert "".join(t.text for t in prev.iter(qn("w:t"))) == "Looking ahead..."
    la = [p for p in doc.paragraphs if p.text.lower().startswith("looking ahead")]
    assert len(la) == 1  # model's standalone line replaced, not duplicated
    assert la[0].runs[0].bold
    assert la[0].paragraph_format.keep_with_next
    assert list(body).index(prev) + 1 == list(body).index(table_el)


def test_no_looking_ahead_without_table():
    doc = _load(build_docx("Dear friends,\nUPCOMING_TABLE\n"))
    assert not any("Looking ahead" in p.text for p in doc.paragraphs)


def test_looking_ahead_prose_kept():
    text = "Looking a little further ahead: the dinner is Nov 5.\n"
    doc = _load(build_docx(text))
    assert doc.paragraphs[0].text == text.strip()


def test_font_applied_everywhere():
    doc = _load(build_docx(FULL_TEXT))
    normal = doc.styles["Normal"]
    assert normal.font.name == "Avenir Next LT Pro"
    r_fonts = normal.element.rPr.rFonts
    assert r_fonts.get(qn("w:eastAsia")) == "Avenir Next LT Pro"
    runs = [r for p in doc.paragraphs for r in p.runs]
    runs += [r for row in doc.tables[0].rows for c in row.cells for r in c.paragraphs[0].runs]
    assert runs and all(r.font.name == "Avenir Next LT Pro" for r in runs)


def test_normal_paragraph_not_bold():
    text = "Dear friends,\nUPCOMING_TABLE\n"
    doc = _load(build_docx(text))
    para = [p for p in doc.paragraphs if p.text == "Dear friends,"]
    assert len(para) == 1
    assert not para[0].runs[0].bold


def test_alternating_row_colors():
    # Build a doc with 3 data rows to hit both colour branches (idx 0, 1, 2)
    text = (
        "UPCOMING_TABLE\n"
        "DATE_ROW: Event A | Mon, Oct 19 @ 9:00 am\n"
        "DATE_ROW: Event B | Tue, Oct 20 @ 10:00 am\n"
        "DATE_ROW: Event C | Wed, Oct 21 @ 11:00 am\n"
    )
    result = build_docx(text)
    # Verify it round-trips without error; colour values are in XML only
    doc = _load(result)
    assert len(doc.tables[0].rows) == 4  # 1 header + 3 data


def test_blank_lines_dropped():
    text = "Line one.\n\n\nLine two.\nUPCOMING_TABLE\n"
    doc = _load(build_docx(text))
    assert [p.text for p in doc.paragraphs] == ["Line one.", "Line two."]


def test_table_indented_one_tab():
    doc = _load(build_docx(FULL_TEXT))
    ind = doc.tables[0]._tbl.tblPr.find(qn("w:tblInd"))
    assert ind.get(qn("w:w")) == "720"
    assert ind.get(qn("w:type")) == "dxa"


# ── inline Markdown / links ──────────────────────────────────────────────────


def _hyperlinks(doc):
    """Return (text, url) for every hyperlink in the document body and tables."""
    rels = doc.part.rels
    out = []
    for h in doc.element.body.iter(qn("w:hyperlink")):
        text = "".join(t.text for t in h.iter(qn("w:t")))
        out.append((text, rels[h.get(qn("r:id"))].target_ref))
    return out


def test_bare_url_becomes_hyperlink():
    doc = _load(build_docx(FULL_TEXT))
    assert ("https://pccmi.org/bulletin", "https://pccmi.org/bulletin") in _hyperlinks(doc)
    para = [p for p in doc.paragraphs if "See the bulletin" in p.text][0]
    assert para.text == "See the bulletin for details: https://pccmi.org/bulletin"


def test_trailing_punctuation_not_in_url():
    doc = _load(build_docx("Visit https://pccmi.org/events.\n"))
    assert _hyperlinks(doc) == [("https://pccmi.org/events", "https://pccmi.org/events")]
    assert doc.paragraphs[0].text == "Visit https://pccmi.org/events."


def test_markdown_link_rendered():
    doc = _load(build_docx("Sign up [here](https://pccmi.org/signup) today.\n"))
    assert _hyperlinks(doc) == [("here", "https://pccmi.org/signup")]
    assert doc.paragraphs[0].text == "Sign up here today."


def test_bold_and_italic_rendered():
    doc = _load(build_docx("A **big** day and an *early* start and _more_.\n"))
    p = doc.paragraphs[0]
    assert p.text == "A big day and an early start and more."
    runs = {r.text: r for r in p.runs}
    assert runs["big"].bold
    assert runs["early"].italic
    assert runs["more"].italic
    assert not runs["A "].bold


def test_link_inside_bold():
    doc = _load(build_docx("**Register at https://pccmi.org/vbs**\n"))
    assert _hyperlinks(doc) == [("https://pccmi.org/vbs", "https://pccmi.org/vbs")]
    assert all(r.bold for r in doc.paragraphs[0].runs)


def test_asterisks_in_plain_text_left_alone():
    doc = _load(build_docx("2 * 3 = 6 and snake_case_name\n"))
    assert doc.paragraphs[0].text == "2 * 3 = 6 and snake_case_name"


def test_heading_bullets_numbers_and_rule():
    text = "## Coming Up\n- First *thing*\n1. Step one\n---\nDone\n"
    doc = _load(build_docx(text))
    texts = [p.text for p in doc.paragraphs]
    assert texts == ["Coming Up", "First thing", "Step one", "Done"]
    heading = doc.paragraphs[0]
    assert heading.runs[0].bold and heading.runs[0].font.size == Pt(14)
    assert doc.paragraphs[1].style.name == "List Bullet"
    assert doc.paragraphs[2].style.name == "List Number"


def test_no_raw_markdown_left():
    text = "## Hi\n**Bold** [link](https://a.org) *it*\n- item\n"
    doc = _load(build_docx(text))
    body = "\n".join(p.text for p in doc.paragraphs)
    for marker in ("**", "](", "## ", "- "):
        assert marker not in body


def test_table_cell_markdown_rendered():
    text = "UPCOMING_TABLE\nDATE_ROW: **Potluck** at https://pccmi.org/p | Sun, Oct 25\n"
    doc = _load(build_docx(text))
    cell = doc.tables[0].rows[1].cells[0]
    assert cell.text == "Potluck at https://pccmi.org/p"
    assert cell.paragraphs[0].runs[0].bold
    assert ("https://pccmi.org/p", "https://pccmi.org/p") in _hyperlinks(doc)
