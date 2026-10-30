import re

from sqlalchemy.orm import Session

from app.db.models import ChunkRecord
from app.db.repository import search_chunks, search_chunks_containing
from app.schemas.chat import RetrievedChunk
from app.services.embeddings import embed_query

# Codes mixing letters and digits joined by "." or "-", like GV.SC-05, ID.SC-03 or PR.DS-11.
# Embeddings blur these together, so they're matched as exact text instead.
IDENTIFIER = re.compile(r"\b(?=[\w.-]*[A-Za-z])(?=[\w.-]*\d)[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)+\b")
MAX_EXACT_MATCHES = 3  # leave the other slots for semantic matches


def find_identifiers(question: str) -> list[str]:
    return list(dict.fromkeys(IDENTIFIER.findall(question)))  # unique, in order


def to_result(chunk: ChunkRecord, score: float, exact_match: bool) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        page_number=chunk.page_number,
        page_label=chunk.page_label,
        text=chunk.text,
        score=round(score, 4),
        exact_match=exact_match,
    )


def retrieve(
    session: Session,
    question: str,
    top_k: int = 5,
    document_id: str | None = None,
) -> list[RetrievedChunk]:
    query_embedding = embed_query(question)

    # Hybrid search: chunks containing an ID named in the question come first...
    identifiers = find_identifiers(question)
    exact = []
    if identifiers:
        limit = min(top_k, MAX_EXACT_MATCHES)
        exact = search_chunks_containing(session, query_embedding, identifiers, limit, document_id)

    # ...then the closest chunks by meaning fill the remaining slots
    semantic = search_chunks(session, query_embedding, top_k, document_id)

    results = [to_result(chunk, score, exact_match=True) for chunk, score in exact]
    seen = {result.chunk_id for result in results}
    for chunk, score in semantic:
        if len(results) == top_k:
            break
        if chunk.chunk_id not in seen:
            results.append(to_result(chunk, score, exact_match=False))
    return results
