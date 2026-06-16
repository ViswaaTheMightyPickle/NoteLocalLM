import logging
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, Filter, FieldCondition, MatchValue, FilterSelector,
)

from backend.core.config import get_app_config

logger = logging.getLogger(__name__)

# Default dimension for the bundled multilingual model; ensure_collection accepts
# an explicit size so other embedding models keep working.
DEFAULT_VECTOR_SIZE = 768


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    cfg = get_app_config()
    return QdrantClient(url=cfg.qdrant_url)


def collection_exists(client: QdrantClient, collection_name: str) -> bool:
    try:
        return client.collection_exists(collection_name)
    except AttributeError:
        # Older qdrant-client without collection_exists()
        existing = {c.name for c in client.get_collections().collections}
        return collection_name in existing


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int = DEFAULT_VECTOR_SIZE):
    if not collection_exists(client, collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info(f"[retriever] Created collection {collection_name} (dim={vector_size})")


def delete_document_points(client: QdrantClient, collection_name: str, subject_id: str, source_file: str):
    """Remove all vectors for a given source file so re-indexing leaves no stale data."""
    if not collection_exists(client, collection_name):
        return
    client.delete(
        collection_name=collection_name,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(key="subject_id", match=MatchValue(value=subject_id)),
                    FieldCondition(key="source_file", match=MatchValue(value=source_file)),
                ]
            )
        ),
    )
    logger.info(f"[retriever] Deleted old vectors for {source_file} in {collection_name}")


def retrieve(
    collection_name: str,
    query_vector: list[float],
    subject_id: str,
    top_k: int = 5,
) -> list[dict]:
    client = get_qdrant_client()
    # Guard: a subject that was never ingested has no collection yet.
    if not collection_exists(client, collection_name):
        logger.info(f"[retriever] Collection {collection_name} does not exist yet — no results")
        return []

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
