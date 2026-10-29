import io
import logging
from pypdf import PdfReader

from app.schemas.document import PageContent

logger = logging.getLogger(__name__)



class InvalidPDFError(Exception):
    """Raised with a message that is safe to show to the client."""


def parse_pdf(data: bytes, document_id: str) -> list[PageContent]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise InvalidPDFError("Password-protected PDFs are not supported")
        page_count = len(reader.pages)
        has_labels = "/PageLabels" in reader.trailer["/Root"]
        labels = reader.page_labels if has_labels else None
    except InvalidPDFError:
        raise  # already has a safe message, so let it through unchanged
    except Exception:
        logger.exception("Could not open PDF for document %s", document_id)
        raise InvalidPDFError("The file could not be read as a PDF")

    if page_count == 0:
        raise InvalidPDFError("The PDF has no pages")

    pages = []
    for index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            # One broken page shouldn't fail the whole upload
            logger.warning("Text extraction failed on page %d of document %s",
                        index + 1, document_id, exc_info=True)
            text = ""

        page_number = index + 1
        pages.append(
            PageContent(
                page_id=f"{document_id}-p{page_number}",
                page_number=page_number,
                page_label=labels[index] if labels else None,
                text=text.strip(),
            )
        )
    return pages
