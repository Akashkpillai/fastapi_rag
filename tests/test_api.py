"""Endpoint tests that need neither the database nor OpenAI: those parts are replaced with fakes."""
import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app.api.routes import chat
from app.api.routes.documents import MAX_UPLOAD_BYTES
from app.db.session import get_session
from app.main import app
from app.schemas.chat import AnswerResponse, RetrievedChunk
from app.services.answer_generator import MissingAPIKeyError
from tests.conftest import make_pdf


@pytest.fixture
def client():
    # Not used as a context manager, so the startup step that connects to the database is skipped
    app.dependency_overrides[get_session] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client, data: bytes, content_type="application/pdf"):
    return client.post("/document/upload", files={"file": ("test.pdf", data, content_type)})


def chunk(page_number: int, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"c{page_number}", document_id="d", page_number=page_number,
        page_label=None, text="...", score=score,
    )


@pytest.fixture
def fake_pipeline(monkeypatch):
    # Every document "exists", retrieval returns the given chunks, and the LLM call is recorded
    sent = []

    def setup(chunks, answer=None, error=None):
        monkeypatch.setattr(chat, "get_document", lambda session, document_id: object())
        monkeypatch.setattr(chat, "retrieve", lambda *args: chunks)

        def generate(question, relevant):
            sent.append(relevant)
            if error:
                raise error
            return answer

        monkeypatch.setattr(chat, "generate_answer", generate)
        return sent

    return setup


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


# --- upload checks ---

def test_upload_rejects_non_pdf_content_type(client):
    assert upload(client, b"hello", content_type="text/plain").status_code == 415


def test_upload_rejects_file_over_20_mb(client):
    assert upload(client, b"%PDF-" + b"0" * MAX_UPLOAD_BYTES).status_code == 413


def test_upload_rejects_file_without_pdf_signature(client):
    response = upload(client, b"just text pretending to be a pdf")
    assert response.status_code == 400
    assert response.json()["detail"] == "File is not a valid PDF"


def test_upload_rejects_broken_pdf(client):
    response = upload(client, b"%PDF-1.7 broken")
    assert response.status_code == 400
    assert response.json()["detail"] == "The file could not be read as a PDF"


def test_upload_rejects_pdf_with_no_text(client):
    response = upload(client, make_pdf())
    assert response.status_code == 422
    assert "OCR" in response.json()["detail"]


# --- question / search ---

def test_question_validates_input(client):
    assert client.post("/question", json={"question": ""}).status_code == 422
    assert client.post("/question", json={"question": "q", "top_k": 50}).status_code == 422


def test_unknown_document_is_404(client, monkeypatch):
    monkeypatch.setattr(chat, "get_document", lambda session, document_id: None)
    for path in ("/question", "/search"):
        response = client.post(path, json={"question": "q", "document_id": "missing"})
        assert response.status_code == 404


def test_weak_matches_skip_the_llm(client, fake_pipeline):
    sent = fake_pipeline([chunk(1, 0.43), chunk(2, 0.40)])
    response = client.post("/question", json={"question": "best pizza recipe"})

    assert response.json() == {"answer": chat.NOT_FOUND_ANSWER, "cited_pages": []}
    assert sent == []  # OpenAI was never called


def test_only_strong_matches_reach_the_llm(client, fake_pipeline):
    answer = AnswerResponse(answer="GV.SC-05 is ...", cited_pages=[41])
    sent = fake_pipeline([chunk(41, 0.69), chunk(40, 0.66), chunk(53, 0.41)], answer=answer)
    response = client.post("/question", json={"question": "What is GV.SC-05?"})

    assert response.json() == answer.model_dump()
    assert [c.page_number for c in sent[0]] == [41, 40]


def test_missing_api_key_is_503(client, fake_pipeline):
    fake_pipeline([chunk(1, 0.9)], error=MissingAPIKeyError("empty"))
    response = client.post("/question", json={"question": "q"})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_openai_failure_is_502(client, fake_pipeline):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    fake_pipeline([chunk(1, 0.9)], error=openai.APIConnectionError(request=request))
    assert client.post("/question", json={"question": "q"}).status_code == 502
