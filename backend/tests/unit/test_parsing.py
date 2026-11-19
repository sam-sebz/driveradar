import io
from pathlib import Path

import pytest
from docx import Document
from fpdf import FPDF
from openpyxl import Workbook

from app.domain.parsing.documents import (
    EmptyDocumentError,
    UnsupportedFileError,
    detect_file_type,
    parse_bytes,
    parse_text,
)

SAMPLES = Path(__file__).resolve().parents[3] / "samples" / "synthetic"


def _pdf(lines: list[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in lines:
        pdf.multi_cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def _docx(build) -> bytes:  # type: ignore[no-untyped-def]
    doc = Document()
    build(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _xlsx(sheets: dict[str, list[list[object]]]) -> bytes:
    wb = Workbook()
    first = True
    for title, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet(title)
        assert ws is not None
        ws.title = title
        first = False
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_pdf_text_extraction() -> None:
    doc = parse_bytes("n.pdf", _pdf(["Company: Foo Ltd", "CTC: 5 LPA"]))
    assert doc.file_type == "pdf"
    assert "Company: Foo Ltd" in doc.text
    assert doc.role_blocks == [doc.text]


def test_docx_paragraphs_and_tables_in_order() -> None:
    def build(d):  # type: ignore[no-untyped-def]
        d.add_paragraph("Company: Foo Ltd")
        t = d.add_table(rows=1, cols=2)
        t.rows[0].cells[0].text = "CGPA"
        t.rows[0].cells[1].text = "7.0"
        t3 = d.add_table(rows=1, cols=3)
        for i, v in enumerate(["Round", "Online test", "Interview"]):
            t3.rows[0].cells[i].text = v
        d.add_paragraph("Footer line")

    doc = parse_bytes("n.docx", _docx(build))
    assert doc.text.split("\n") == [
        "Company: Foo Ltd",
        "CGPA: 7.0",
        "Round | Online test | Interview",
        "Footer line",
    ]


def test_xlsx_every_row_of_role_table_is_a_role_with_shared_context() -> None:
    content = _xlsx(
        {
            "Info": [["Company", "Foo Ltd"], ["Deadline", "1 Dec 2026"]],
            "Roles": [["Role", "CTC"], ["SDE", "8 LPA"], ["Analyst", "6 LPA"], [None, None]],
        }
    )
    doc = parse_bytes("n.xlsx", content)
    assert doc.file_type == "xlsx"
    assert len(doc.role_blocks) == 2
    assert doc.role_blocks[0].startswith("Company: Foo Ltd\nDeadline: 1 Dec 2026")
    assert "Role: SDE\nCTC: 8 LPA" in doc.role_blocks[0]
    assert "Role: Analyst" in doc.role_blocks[1]
    assert "[Sheet: Roles]" in doc.text


def test_xlsx_roles_spread_across_two_sheets() -> None:
    content = _xlsx(
        {
            "A": [["Position", "CTC"], ["SDE", "8 LPA"]],
            "B": [["Designation", "CTC"], ["QA", "5 LPA"]],
        }
    )
    assert len(parse_bytes("n.xlsx", content).role_blocks) == 2


def test_xlsx_without_role_table_is_one_block() -> None:
    content = _xlsx({"Info": [["Company", "Foo"], ["CTC", 6.5]]})
    doc = parse_bytes("n.xlsx", content)
    assert doc.role_blocks == ["Company: Foo\nCTC: 6.5"]


def test_synthetic_samples_parse() -> None:
    counts = {
        p.name: len(parse_bytes(p.name, p.read_bytes()).role_blocks) for p in SAMPLES.iterdir()
    }
    assert counts == {
        "kaveri_analytics_notice.pdf": 1,
        "nilgiri_cloudworks_notice.docx": 1,
        "thamirabarani_systems_3roles.xlsx": 3,
    }


def test_extension_must_match_content() -> None:
    with pytest.raises(UnsupportedFileError):
        detect_file_type("notice.docx", _pdf(["x"]))
    with pytest.raises(UnsupportedFileError):
        detect_file_type("notice.pdf", b"MZ\x90\x00 not a pdf")
    with pytest.raises(UnsupportedFileError):
        detect_file_type("notice.xlsx", _docx(lambda d: d.add_paragraph("x")))


def test_corrupt_zip_is_rejected() -> None:
    with pytest.raises(UnsupportedFileError):
        detect_file_type("n.docx", b"PK\x03\x04garbage")


def test_empty_pdf_raises() -> None:
    with pytest.raises(EmptyDocumentError):
        parse_bytes("blank.pdf", _pdf([""]))


def test_pasted_text_is_cleaned() -> None:
    doc = parse_text("  Company:   Foo  \r\n\r\n\r\n CTC: 5 LPA ")
    assert doc.text == "Company: Foo\n\nCTC: 5 LPA"
    with pytest.raises(EmptyDocumentError):
        parse_text("   \n ")
