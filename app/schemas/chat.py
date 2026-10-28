from pydantic import BaseModel


class QuestionRequest(BaseModel):
    question: str
    document_id: int | None = None


class AnswerResponse(BaseModel):
    answer: str
    cited_pages: list[int]
