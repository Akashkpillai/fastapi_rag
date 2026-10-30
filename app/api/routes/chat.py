import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from openai import APIError, AuthenticationError
from sqlalchemy.orm import Session

from app.db.repository import get_document
from app.db.session import get_session
from app.schemas.chat import AnswerResponse, QuestionRequest, SearchResponse
from app.services.answer_generator import AnswerGenerationError, MissingAPIKeyError, generate_answer
from app.services.retrieval import retrieve

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# On the NIST PDF, on-topic questions scored 0.65-0.78 and an off-topic one about 0.43
MIN_SCORE = 0.5
NOT_FOUND_ANSWER = "I couldn't find anything about that in the document."


def check_document_exists(session: Session, document_id: str | None) -> None:
    if document_id is not None and get_document(session, document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found")


# Plain def (not async): embedding the question is CPU work, so FastAPI runs this in a thread
@router.post("/search", response_model=SearchResponse)
def search(request: QuestionRequest, session: Annotated[Session, Depends(get_session)]):
    check_document_exists(session, request.document_id)
    results = retrieve(session, request.question, request.top_k, request.document_id)
    return SearchResponse(question=request.question, results=results)


@router.post("/question", response_model=AnswerResponse)
def question(request: QuestionRequest, session: Annotated[Session, Depends(get_session)]):
    check_document_exists(session, request.document_id)
    chunks = retrieve(session, request.question, request.top_k, request.document_id)

    # Weak matches would only tempt the model to answer from unrelated text, so skip the call
    relevant = [chunk for chunk in chunks if chunk.score >= MIN_SCORE]
    if not relevant:
        return AnswerResponse(answer=NOT_FOUND_ANSWER, cited_pages=[])

    try:
        return generate_answer(request.question, relevant)
    except (MissingAPIKeyError, AuthenticationError):
        raise HTTPException(status_code=503, detail="OpenAI API key is missing or invalid: check OPENAI_API_KEY in .env")
    except (APIError, AnswerGenerationError):
        logger.exception("Answer generation failed")
        raise HTTPException(status_code=502, detail="Could not generate an answer, please try again")
