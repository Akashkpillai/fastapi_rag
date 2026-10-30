from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import settings


@lru_cache
def get_model() -> SentenceTransformer:
    # Loading takes seconds, so do it once and reuse the model
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    # Normalized vectors let retrieval compare them with a simple dot product
    vectors = get_model().encode(texts, batch_size=32, normalize_embeddings=True)
    return vectors.tolist()
