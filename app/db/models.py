from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.session import Base


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(primary_key=True)
    filename: Mapped[str]
    page_count: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Tells SQLAlchemy to insert the document before its chunks
    chunks: Mapped[list["ChunkRecord"]] = relationship(cascade="all, delete-orphan")


class ChunkRecord(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        # HNSW index makes nearest-neighbour search fast; cosine matches our normalized embeddings
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    chunk_id: Mapped[str] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    page_id: Mapped[str]
    page_number: Mapped[int]
    page_label: Mapped[str | None]
    chunk_index: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dimensions))
