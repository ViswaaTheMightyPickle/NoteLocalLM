import logging
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, MatchValue

from backend.core.config import get_app_config

logger = logging.getLogger(__name__)

_VECTOR_SIZE = 768


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    cfg = get_app_config()
    return QdrantClient(url=cfg.qdrant_url)


def ensure_collection(client: QdrantClient, collection_name: str):
    existing = {c.name for c in client.get_collections().collections}
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info(f"[retriever] Created collection: {collection_name}")


def retrieve(
    collection_name: str,
    query_vector: list[float],
    subject_id: str,
    top_k: int = 5,
) -> list[dict]:
    client = get_qdrant_client()
    results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=Filter(
            must=[FieldCondition(key="subject_id", match=MatchValue(value=subject_id))]
        ),
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "chunk_id": hit.payload.get("chunk_id", str(hit.id)),
            "text": hit.payload.get("text", ""),
            "score": hit.score,
            "metadata": {k: v for k, v in hit.payload.items() if k not in ("text", "chunk_id")},
        }
        for hit in results
    ]
