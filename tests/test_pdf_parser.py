import re

import pytest

from app.services.pdf_parser import InvalidPDFError, parse_pdf
from tests.conftest import make_pdf

# The printed page number sits right after the running header on every page
PRINTED_NUMBER = re.compile(r"Framework 2\.0\s+(\d+)\s")


def test_reads_every_page_in_order(nist_pages):
    assert len(nist_pages) == 53
    assert [page.page_number for page in nist_pages] == list(range(1, 54))
    assert nist_pages[0].page_id == "test-doc-p1"


def test_every_page_has_text(nist_pages):
    assert all(page.text for page in nist_pages)


@pytest.mark.parametrize("viewer_page, printed_page", [(18, "9"), (41, "32")])
def test_printed_page_numbers(nist_pages, viewer_page, printed_page):
    page = nist_pages[viewer_page - 1]
    # This PDF has no embedded page labels, so the printed number only exists in the text
    assert page.page_label is None
    assert PRINTED_NUMBER.search(page.text).group(1) == printed_page


def test_dot_leaders_removed(nist_pages):
    assert not any("....." in page.text for page in nist_pages)


def test_rejects_bytes_that_are_not_a_pdf():
    with pytest.raises(InvalidPDFError, match="could not be read"):
        parse_pdf(b"%PDF-1.7 this is not really a pdf", "bad")


def test_rejects_password_protected_pdf():
    with pytest.raises(InvalidPDFError, match="Password-protected"):
        parse_pdf(make_pdf(encrypt=True), "locked")


def test_page_without_text_comes_back_empty():
    pages = parse_pdf(make_pdf(), "blank")
    assert len(pages) == 1
    assert pages[0].text == ""
