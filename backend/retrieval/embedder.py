import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "paraphrase-multilingual-mpnet-base-v2"


class Embedder:
    def __init__(self, model_name: str):
        logger.info(f"[embedder] Loading model: {model_name}")
        self._model = SentenceTransformer(model_name)
        logger.info("[embedder] Model ready")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def dim(self) -> int:
        size = self._model.get_sentence_embedding_dimension()
        return int(size) if size else len(self.embed_one("dimension probe"))


@lru_cache(maxsize=4)
def get_embedder(model_name: str = _DEFAULT_MODEL) -> Embedder:
    return Embedder(model_name)
