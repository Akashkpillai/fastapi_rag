import io
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.services.pdf_parser import parse_pdf

SAMPLE_PDF = Path(__file__).parent.parent / "data" / "sample_pdfs" / "NIST.CSWP.29.ipd.pdf"


def make_pdf(encrypt: bool = False) -> bytes:
    # A one-page PDF with no text, like a scanned page
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if encrypt:
        writer.encrypt("secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture(scope="session")
def sample_pdf_bytes() -> bytes:
    return SAMPLE_PDF.read_bytes()


@pytest.fixture(scope="session")
def nist_pages(sample_pdf_bytes):
    return parse_pdf(sample_pdf_bytes, "test-doc")
