import io

import pytest
from reportlab.pdfgen import canvas

from triage.golden import GOLDEN_DIR, load_golden_cases
from triage.nodes.ingest import UnreadableDocumentError, ingest


def blank_pdf(pages: int = 1) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, invariant=1)
    for _ in range(pages):
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def text_pdf(lines: list[str], pages: int = 1) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, invariant=1)
    for _ in range(pages):
        for i, line in enumerate(lines):
            pdf.drawString(72, 750 - 16 * i, line)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def test_ingest_reads_text_from_a_golden_pdf():
    case = load_golden_cases(split="dev")[0]
    result = ingest((GOLDEN_DIR / "dev" / case.pdf_file).read_bytes())
    assert case.expected.fields.claim_number in result.text
    assert result.page_count >= 1


def test_ingest_reads_every_page():
    result = ingest(text_pdf(["Claim CLM-2026-12345"], pages=3))
    assert result.page_count == 3
    assert result.text.count("CLM-2026-12345") == 3


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"", "empty"),
        (b"this is not a pdf", "not_a_pdf"),
        (blank_pdf(), "no_text"),
    ],
)
def test_ingest_rejects_unreadable_files(data, reason):
    with pytest.raises(UnreadableDocumentError) as error:
        ingest(data)
    assert error.value.reason == reason


def test_ingest_rejects_too_many_pages():
    with pytest.raises(UnreadableDocumentError) as error:
        ingest(text_pdf(["x"], pages=3), max_pages=2)
    assert error.value.reason == "too_many_pages"
