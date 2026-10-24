"""Step 1: read text from a PDF. Rejects files we cannot read (no OCR, PLAN.md scope)."""

import io
from dataclasses import dataclass

import pdfplumber


class UnreadableDocumentError(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class IngestResult:
    text: str
    page_count: int


def ingest(pdf_bytes: bytes, max_pages: int = 20) -> IngestResult:
    if not pdf_bytes:
        raise UnreadableDocumentError("empty", "the file is empty")
    if not pdf_bytes.startswith(b"%PDF"):
        raise UnreadableDocumentError("not_a_pdf", "the file is not a PDF")
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page_count = len(pdf.pages)
            if page_count > max_pages:
                raise UnreadableDocumentError(
                    "too_many_pages", f"{page_count} pages, the limit is {max_pages}"
                )
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except UnreadableDocumentError:
        raise
    except Exception as error:
        raise UnreadableDocumentError(
            "not_a_pdf", f"the PDF could not be parsed: {error}"
        ) from error
    if not text.strip():
        raise UnreadableDocumentError("no_text", "no text found, the PDF may be a scan")
    return IngestResult(text=text, page_count=page_count)
