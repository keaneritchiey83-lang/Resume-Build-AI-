from __future__ import annotations

import threading

from anyio import to_thread
from sentence_transformers import SentenceTransformer

from app.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self._model: SentenceTransformer | None = None
        self._lock = threading.Lock()

    def _get_model(self) -> SentenceTransformer:
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is None:
                self._model = SentenceTransformer(settings.embedding_model)

        return self._model

    def _encode(self, values: list[str]) -> list[list[float]]:
        vectors = self._get_model().encode(
            values,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        result = [vector.astype(float).tolist() for vector in vectors]

        for vector in result:
            if len(vector) != settings.embedding_dimensions:
                raise RuntimeError(
                    "Embedding model dimension differs from EMBEDDING_DIMENSIONS."
                )

        return result

    async def encode_many(self, values: list[str]) -> list[list[float]]:
        return await to_thread.run_sync(self._encode, values)

    async def encode(self, value: str) -> list[float]:
        return (await self.encode_many([value]))[0]


embedding_service = EmbeddingService()
