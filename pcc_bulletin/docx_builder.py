import io

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


def build_docx(email_text: str) -> bytes:
    """Convert the Claude-generated email text into a formatted .docx file."""
    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(12)

    date_rows: list[tuple[str, str]] = []
    body_lines: list[str] = []

    for line in email_text.strip().split("\n"):
        if line.startswith("DATE_ROW:"):
            parts = line.replace("DATE_ROW:", "").strip().split("|")
            if len(parts) == 2:
                date_rows.append((parts[0].strip(), parts[1].strip()))
        else:
            body_lines.append(line)

    for line in body_lines:
        stripped = line.strip()
        if stripped == "UPCOMING_TABLE":
            _insert_table(doc, date_rows)
        elif stripped == "":
            doc.add_paragraph("")
        else:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(8)
            run = p.add_run(stripped)
            run.font.name = "Arial"
            run.font.size = Pt(12)
            if stripped == "Looking ahead:":
                run.bold = True

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def _set_cell_bg(cell, hex_color: str) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _insert_table(doc: Document, date_rows: list[tuple[str, str]]) -> None:
    if not date_rows:
        return

    table = doc.add_table(rows=1 + len(date_rows), cols=2)
    table.style = "Table Grid"

    hdr = table.rows[0]
    for i, text in enumerate(["Event", "Date & Time"]):
        cell = hdr.cells[i]
        _set_cell_bg(cell, "2E5D2E")
        cell.paragraphs[0].clear()
        run = cell.paragraphs[0].add_run(text)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        run.font.name = "Arial"
        run.font.size = Pt(12)

    for idx, (event, date_str) in enumerate(date_rows):
        row = table.rows[idx + 1]
        fill = "F2F2F2" if idx % 2 == 0 else "FFFFFF"
        for i, text in enumerate([event, date_str]):
            cell = row.cells[i]
            _set_cell_bg(cell, fill)
            cell.paragraphs[0].clear()
            run = cell.paragraphs[0].add_run(text)
            run.font.name = "Arial"
            run.font.size = Pt(12)
