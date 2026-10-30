from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import ChunkRecord, DocumentRecord
from app.schemas.document import Chunk


def save_document(
    session: Session,
    document_id: str,
    filename: str,
    page_count: int,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> None:
    document = DocumentRecord(
        id=document_id,
        filename=filename,
        page_count=page_count,
        chunks=[
            ChunkRecord(**chunk.model_dump(), embedding=embedding)
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ],
    )
    session.add(document)
    session.commit()  # the document and all its chunks are saved together, or not at all


def get_document(session: Session, document_id: str) -> DocumentRecord | None:
    return session.get(DocumentRecord, document_id)


def count_chunks(session: Session, document_id: str) -> int:
    query = select(func.count()).select_from(ChunkRecord).where(ChunkRecord.document_id == document_id)
    return session.scalar(query)


def search_chunks(
    session: Session,
    query_embedding: list[float],
    top_k: int,
    document_id: str | None = None,
) -> list[tuple[ChunkRecord, float]]:
    # <=> is pgvector's cosine distance (0 = identical); ordering by it uses the HNSW index
    distance = ChunkRecord.embedding.cosine_distance(query_embedding)
    query = select(ChunkRecord, distance).order_by(distance).limit(top_k)

    if document_id is not None:
        query = query.where(ChunkRecord.document_id == document_id)
        # The index finds neighbours first and filters after, so with many documents it could
        # return fewer than top_k matches. This makes it keep scanning until it has enough.
        session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))

    return [(chunk, 1 - distance) for chunk, distance in session.execute(query)]
