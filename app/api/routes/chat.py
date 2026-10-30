from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.repository import get_document
from app.db.session import get_session
from app.schemas.chat import AnswerResponse, QuestionRequest, SearchResponse
from app.services.retrieval import retrieve

router = APIRouter(tags=["chat"])


# Plain def (not async): embedding the question is CPU work, so FastAPI runs this in a thread
@router.post("/search", response_model=SearchResponse)
def search(request: QuestionRequest, session: Annotated[Session, Depends(get_session)]):
    if request.document_id is not None and get_document(session, request.document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")

    results = retrieve(session, request.question, request.top_k, request.document_id)
    return SearchResponse(question=request.question, results=results)


@router.post("/question", response_model=AnswerResponse)
async def question(request: QuestionRequest):
    # Placeholder until answer generation is implemented
    return AnswerResponse(answer=f"You asked: {request.question}", cited_pages=[])
