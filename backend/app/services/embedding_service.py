from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from app.core.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DEVICE,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_NORMALIZE,
)
from app.core.exceptions import (
    EmbeddingError,
    EmbeddingModelLoadError,
    EmptyEmbeddingInput,
)

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Generates dense vector embeddings for document chunks and queries using
    a locally-run sentence-transformers model.

    Model caching: the underlying SentenceTransformer model is loaded at
    most once per (model_name, device) combination for the lifetime of the
    process, regardless of how many EmbeddingService instances are created.
    This matters because the model is large (hundreds of MB) and loading it
    is slow; every EmbeddingService() call in request-handling code should
    be cheap, not trigger a fresh load.
    """

    _model_cache: dict[tuple[str, str], "SentenceTransformer"] = {}
    _cache_lock = threading.Lock()

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        device: str = EMBEDDING_DEVICE,
        batch_size: int = EMBEDDING_BATCH_SIZE,
        normalize_embeddings: bool = EMBEDDING_NORMALIZE,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self._model: "SentenceTransformer" = self._get_or_load_model()
        self._is_ready = True

    def _get_or_load_model(self) -> "SentenceTransformer":
        cache_key = (self.model_name, self.device)

        with self._cache_lock:
            cached = self._model_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Reusing cached embedding model '%s' on device '%s'.",
                    self.model_name,
                    self.device,
                )
                return cached

            model = self._load_model()
            self._model_cache[cache_key] = model
            return model

    def _load_model(self) -> "SentenceTransformer":
        """
        Loads the sentence-transformers model from disk/hub. Only ever
        called while holding `_cache_lock`, and only on a cache miss.
        Raises EmbeddingModelLoadError on any failure so callers get a
        domain-specific exception rather than a raw ImportError/OSError.
        """
        logger.info(
            "Loading embedding model '%s' on device '%s' (cache miss).",
            self.model_name,
            self.device,
        )

        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model_name, device=self.device)

        except Exception as exc:
            logger.exception(
                "Failed to load embedding model '%s'.",
                self.model_name,
            )
            raise EmbeddingModelLoadError(
                f"Could not load embedding model '{self.model_name}': {exc}"
            ) from exc

        logger.info(
            "Embedding model '%s' loaded successfully.",
            self.model_name,
        )

        return model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Generates embeddings for a batch of document chunk texts.

        The returned list is always exactly the same length as `texts`,
        in the same order — no input is silently dropped.

        Raises:
            EmptyEmbeddingInput: if `texts` is empty, or if ANY element is
                empty/whitespace-only (since dropping it would break the
                one-to-one alignment between chunks and their embeddings).
            EmbeddingError: if the underlying model fails during encoding.
        """
        self._validate(texts)

        logger.info(
            "Generating embeddings for %d text(s) using model '%s'.",
            len(texts),
            self.model_name,
        )

        try:
            vectors = self._model.encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=False,
            )
        except Exception as exc:
            logger.exception(
                "Embedding generation failed for %d text(s) using model '%s'.",
                len(texts),
                self.model_name,
            )
            raise EmbeddingError(
                f"Failed to generate embeddings using model '{self.model_name}': {exc}"
            ) from exc

        result = vectors.tolist()

        logger.info(
            "Generated %d embedding(s) of dimension %d.",
            len(result),
            len(result[0]) if result else 0,
        )

        return result

    def embed_query(self, text: str) -> list[float]:
        """
        Generates a single embedding for a query string.

        Raises:
            EmptyEmbeddingInput: if `text` is empty or whitespace-only.
            EmbeddingError: if the underlying model fails during encoding.
        """
        if not text or not text.strip():
            raise EmptyEmbeddingInput("Query text must not be empty.")

        return self.embed([text])[0]

    @staticmethod
    def _validate(texts: list[str]) -> None:
        if not texts:
            raise EmptyEmbeddingInput("No texts provided for embedding.")

        if any(not t or not t.strip() for t in texts):
            raise EmptyEmbeddingInput(
                "One or more input texts are empty or whitespace-only. "
                "All inputs must be non-empty to preserve one-to-one "
                "alignment between chunks and their embeddings."
            )

    @property
    def dimension(self) -> int:
        """Embedding vector dimensionality for the loaded model."""
        return self._model.get_sentence_embedding_dimension()

    @property
    def is_ready(self) -> bool:
        """True once the embedding model has successfully loaded."""
        return self._is_ready