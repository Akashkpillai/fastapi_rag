"""End-to-end tests against the real database and embedding model (no OpenAI calls).

Run only these with: pytest -m integration. They skip if the database isn't running.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.db.models import ChunkRecord
from app.db.session import SessionLocal, engine
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    try:
        engine.connect().close()
    except OperationalError:
        pytest.skip("Database not running: start it with docker compose up -d db")
    with TestClient(app) as client:  # runs startup, which creates the tables
        yield client


@pytest.fixture(scope="module")
def uploaded(client, sample_pdf_bytes):
    response = client.post(
        "/document/upload",
        files={"file": ("NIST.CSWP.29.ipd.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201
    summary = response.json()
    yield summary

    # Remove the test copy (this also tests the delete endpoint) so repeated runs don't pile up documents
    assert client.delete(f"/document/{summary['document_id']}").status_code == 204
    assert client.get(f"/document/{summary['document_id']}").status_code == 404
    with SessionLocal() as session:
        orphans = session.scalar(
            select(func.count()).select_from(ChunkRecord).where(ChunkRecord.document_id == summary["document_id"])
        )
    assert orphans == 0  # the chunks were deleted with the document


def search_pages(client, document_id: str, question: str, top_k: int = 3) -> list[int]:
    response = client.post("/search", json={"question": question, "document_id": document_id, "top_k": top_k})
    assert response.status_code == 200
    return [result["page_number"] for result in response.json()["results"]]


def test_upload_stores_every_chunk(client, uploaded):
    assert uploaded["page_count"] == 53
    assert uploaded["empty_pages"] == []

    info = client.get(f"/document/{uploaded['document_id']}").json()
    assert info["chunk_count"] == uploaded["chunk_count"]


def test_upload_appears_in_document_list(client, uploaded):
    ids = [document["document_id"] for document in client.get("/document/").json()]
    assert uploaded["document_id"] in ids


def test_search_finds_gv_sc_05_table(client, uploaded):
    assert 41 in search_pages(client, uploaded["document_id"], "What is GV.SC-05?")


def test_hybrid_search_finds_exact_id(client, uploaded):
    # Vector search alone ranked general "what changed" pages first; page 44 lists ID.SC-03
    assert search_pages(client, uploaded["document_id"], "What happened to ID.SC-03 in CSF 2.0?")[0] == 44


def test_search_finds_core_functions(client, uploaded):
    pages = search_pages(client, uploaded["document_id"], "What are the six core functions of the CSF?")
    assert {14, 15} & set(pages)


def test_search_results_are_best_first(client, uploaded):
    response = client.post("/search", json={"question": "supply chain risk", "document_id": uploaded["document_id"]})
    scores = [result["score"] for result in response.json()["results"]]
    assert scores == sorted(scores, reverse=True)
