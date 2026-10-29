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
    chunk_count : int

class Chunk(BaseModel):
    chunk_id: str           # unique: "<page_id>-c0", "<page_id>-c1", ...
    document_id: str
    page_id: str            # the same for every chunk from one page
    page_number: int        # viewer page number, used for citations
    page_label: str | None  # printed label, if the PDF has one
    chunk_index: int        # order of this chunk within its page (0, 1, 2...)
    text: str
