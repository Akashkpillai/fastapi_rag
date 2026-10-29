from fastapi import APIRouter
from app.schemas.chat import AnswerResponse, QuestionRequest

router = APIRouter(tags=["chat"])

@router.post("/question", response_model=AnswerResponse)
async def question(request: QuestionRequest):
    # Placeholder until retrieval and answer generation are implemented
    return AnswerResponse(answer=f"You asked: {request.question}", cited_pages=[])
