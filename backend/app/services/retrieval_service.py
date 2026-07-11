from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from app.core.config import DEFAULT_TOP_K
from app.core.exceptions import RetrievalError

if TYPE_CHECKING:
    from app.services.embedding_service import EmbeddingService
    from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RetrievalService:
    """
    Retrieves semantically relevant chunks for a natural-language question
    and prepares them as plain-text context.

    Responsibility boundary: this class ONLY embeds the query and retrieves
    matching chunks. It does not call an LLM, does not build prompts, does
    not load or chunk documents, and does not insert vectors — those stay
    the responsibility of EmbeddingService, VectorStore,
    DocumentProcessingService, and a future LLMService respectively.

    Dependencies are injected via the constructor, not instantiated
    internally, so this service can be unit-tested with fake
    EmbeddingService/VectorStore implementations.
    """

    def __init__(
        self,
        embedding_service: "EmbeddingService",
        vector_store: "VectorStore",
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    def retrieve(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> dict[str, Any]:
        """
        Embeds `question` and returns the raw similarity-search results from
        the vector store. No formatting, no prompt construction.

        Raises:
            RetrievalError: if query embedding generation or the vector
                store search fails.
        """
        logger.info("Retrieval started for question of length %d (top_k=%d).", len(question), top_k)

        try:
            query_embedding = self._embedding_service.embed_query(question)
        except Exception as exc:
            logger.exception("Failed to generate query embedding during retrieval.")
            raise RetrievalError(f"Failed to generate query embedding: {exc}") from exc

        logger.info("Query embedding generated (dimension=%d).", len(query_embedding))

        try:
            results = self._vector_store.similarity_search(
                embedding=query_embedding,
                top_k=top_k,
            )
        except Exception as exc:
            logger.exception("Vector store similarity search failed during retrieval.")
            raise RetrievalError(f"Vector store search failed: {exc}") from exc

        num_results = len(results.get("documents", [[]])[0]) if results.get("documents") else 0
        logger.info("Retrieval completed: %d chunk(s) returned.", num_results)

        return results

    def build_context(self, results: dict[str, Any]) -> str:
        """
        Formats raw Chroma similarity-search results into a single
        plain-text context string, using only document texts (no metadata).

        Returns an empty string if no documents were found.
        """
        documents = results.get("documents")

        if not documents or not documents[0]:
            logger.info("build_context called with no documents; returning empty context.")
            return ""

        texts = documents[0]

        sections = []
        for index, text in enumerate(texts, start=1):
            sections.append(f"Chunk {index}\n{text}")

        context = "\n--------------------------------\n".join(sections)

        logger.info("Context built from %d chunk(s), length=%d characters.", len(texts), len(context))

        return context