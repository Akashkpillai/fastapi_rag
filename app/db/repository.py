from sqlalchemy import func, select
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
