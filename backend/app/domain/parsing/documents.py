"""Turn uploaded bytes (PDF, DOCX, XLSX or pasted text) into plain text blocks.

`ParsedDocument.role_blocks` has one entry per role. PDF, DOCX and text give one block.
An XLSX sheet that is a table with a role/position column gives one block per row, and
each block also carries the workbook's general (non-table) text as context.
"""

import io
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

FileType = Literal["pdf", "docx", "xlsx", "text"]

MAX_XLSX_ROWS = 1000
MAX_PDF_PAGES = 50
ROLE_HEADERS = ("role", "position", "designation", "profile", "job title", "title")


class UnsupportedFileError(ValueError):
    """The file is not a PDF, DOCX or XLSX, or its content does not match its extension."""


class EmptyDocumentError(ValueError):
    """The document was parsed but contains no text (for example, a scanned PDF)."""


@dataclass(frozen=True)
class ParsedDocument:
    file_type: FileType
    text: str
    role_blocks: list[str] = field(default_factory=list)


def detect_file_type(filename: str, content: bytes) -> FileType:
    """Trust the magic bytes, not only the extension."""
    name = filename.lower()
    if content.startswith(b"%PDF"):
        if not name.endswith(".pdf"):
            raise UnsupportedFileError("File content is PDF but the extension is not .pdf")
        return "pdf"
    if content.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile as exc:
            raise UnsupportedFileError("Corrupt Office file") from exc
        if name.endswith(".docx") and "word/document.xml" in names:
            return "docx"
        if name.endswith(".xlsx") and "xl/workbook.xml" in names:
            return "xlsx"
    raise UnsupportedFileError("Only PDF, DOCX and XLSX files are supported")


def parse_text(text: str) -> ParsedDocument:
    cleaned = _clean(text)
    if not cleaned:
        raise EmptyDocumentError("The pasted text is empty")
    return ParsedDocument("text", cleaned, [cleaned])


def parse_bytes(filename: str, content: bytes) -> ParsedDocument:
    kind = detect_file_type(filename, content)
    if kind == "pdf":
        text = _pdf_text(content)
        doc = ParsedDocument("pdf", text, [text])
    elif kind == "docx":
        text = _docx_text(content)
        doc = ParsedDocument("docx", text, [text])
    else:
        doc = _xlsx(content)
    if not doc.text.strip():
        raise EmptyDocumentError(
            "No text found in the file. Scanned PDFs (images) are not supported yet."
        )
    return doc


def _clean(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def _pdf_text(content: bytes) -> str:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages[:MAX_PDF_PAGES]:
            pages.append(page.extract_text() or "")
    return _clean("\n".join(pages))


def _docx_text(content: bytes) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(io.BytesIO(content))
    lines: list[str] = []
    # Walk the body in order so tables stay where they appear in the notice.
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            lines.append(Paragraph(child, document).text)
        elif tag == "tbl":
            for row in Table(child, document).rows:
                cells = _dedupe_cells([c.text.strip() for c in row.cells])
                if len(cells) == 2 and cells[0]:
                    lines.append(f"{cells[0]}: {cells[1]}")
                elif any(cells):
                    lines.append(" | ".join(c for c in cells if c))
    return _clean("\n".join(lines))


def _dedupe_cells(cells: list[str]) -> list[str]:
    """Merged cells repeat their text in python-docx; keep each run once."""
    out: list[str] = []
    for c in cells:
        if not out or out[-1] != c:
            out.append(c)
    return out


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return (
            value.strftime("%d %B %Y %I:%M %p")
            if value.time() != datetime.min.time()
            else value.strftime("%d %B %Y")
        )
    if isinstance(value, date):
        return value.strftime("%d %B %Y")
    if isinstance(value, float):
        return f"{value:g}"
    return " ".join(str(value).split())


def _xlsx(content: bytes) -> ParsedDocument:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    general: list[str] = []
    roles: list[str] = []
    all_text: list[str] = []
    try:
        for ws in wb.worksheets:
            rows = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= MAX_XLSX_ROWS:
                    break
                cells = [_cell_text(v) for v in row]
                if any(cells):
                    rows.append(cells)
            if not rows:
                continue
            all_text.append(f"[Sheet: {ws.title}]")
            all_text.extend(" | ".join(c for c in r if c) for r in rows)
            header_idx = _find_role_header(rows)
            if header_idx is None:
                for r in rows:
                    filled = [c for c in r if c]
                    general.append(
                        f"{filled[0]}: {' '.join(filled[1:])}" if len(filled) >= 2 else filled[0]
                    )
                continue
            header = rows[header_idx]
            for r in rows[header_idx + 1 :]:
                pairs = [(h, v) for h, v in zip(header, r, strict=False) if h and v]
                if pairs:
                    roles.append("\n".join(f"{h}: {v}" for h, v in pairs))
    finally:
        wb.close()

    context = "\n".join(general)
    blocks = [_clean(f"{context}\n{role}") for role in roles] if roles else [_clean(context)]
    return ParsedDocument("xlsx", _clean("\n".join(all_text)), blocks)


def _find_role_header(rows: list[list[str]]) -> int | None:
    """Index of a header row that has a role-like column and at least 2 filled cells."""
    for i, r in enumerate(rows[:10]):
        lowered = [c.lower() for c in r if c]
        if len(lowered) >= 2 and any(c in ROLE_HEADERS for c in lowered) and i + 1 < len(rows):
            return i
    return None
