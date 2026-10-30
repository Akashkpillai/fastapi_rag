from sqlalchemy.orm import Session

from app.db.repository import search_chunks
from app.schemas.chat import RetrievedChunk
from app.services.embeddings import embed_query


def retrieve(
    session: Session,
    question: str,
    top_k: int = 5,
    document_id: str | None = None,
) -> list[RetrievedChunk]:
    query_embedding = embed_query(question)
    matches = search_chunks(session, query_embedding, top_k, document_id)
    return [
        RetrievedChunk(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            page_number=chunk.page_number,
            page_label=chunk.page_label,
            text=chunk.text,
            score=round(score, 4),
        )
        for chunk, score in matches
    ]
