from fastapi import FastAPI
from app.schemas.chat import AnswerResponse, QuestionRequest

app = FastAPI()

@app.get("/health")
def health():
    return { "status" : "ok" }

@app.get("/document/{document_id}")
def one_document(document_id:int):
    return document_id

@app.get("/document/")
def document(limit: int = 5):
    return limit

@app.post("/question", response_model=AnswerResponse)
async def question(request: QuestionRequest):
    # Placeholder until retrieval and answer generation are implemented
    return AnswerResponse(answer=f"You asked: {request.question}", cited_pages=[])
