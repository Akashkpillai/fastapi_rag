from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1)
    document_id: str | None = None  # search one document, or all of them when left out
    top_k: int = Field(default=5, ge=1, le=20)  # how many chunks to retrieve


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    page_number: int        # viewer page number, used for citations
    page_label: str | None  # printed label, if the PDF has one
    text: str
    score: float            # cosine similarity: 1 = same meaning, near 0 = unrelated
    exact_match: bool = False  # found because it contains an ID named in the question


class SearchResponse(BaseModel):
    question: str
    results: list[RetrievedChunk]  # best match first


class AnswerResponse(BaseModel):
    answer: str             # Markdown: a direct answer first, then bullets or steps when useful
    cited_pages: list[int]
    sources: list[RetrievedChunk] = []  # the excerpts from the cited pages, for showing evidence
