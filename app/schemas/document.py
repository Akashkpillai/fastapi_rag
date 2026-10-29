from pydantic import BaseModel

class PageContent(BaseModel):
    page_id: str
    page_number: int        # page number as the PDF viewer shows it (1, 2, 3...)
    page_label: str | None  # printed page label embedded in the PDF, if any
    text: str


class UploadSummary(BaseModel):
    document_id: str
    filename: str
    page_count: int
    pages_with_text: int
    empty_pages: list[int]  # viewer page numbers that had no extractable text
