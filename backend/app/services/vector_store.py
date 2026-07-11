from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from app.core.config import CHROMA_COLLECTION_NAME, CHROMA_DB_PATH
from app.core.exceptions import VectorInsertionError, VectorSearchError, VectorStoreError

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection

    from app.models.chunk import DocumentChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Thin wrapper around a persistent local ChromaDB collection.

    Responsibility boundary: this class ONLY stores and retrieves vectors
    (and their associated text/metadata). It does not generate embeddings,
    does not load models, does not call an LLM, and does not touch document
    loading or text cleaning — those stay the responsibility of
    EmbeddingService and DocumentProcessingService respectively.
    """

    def __init__(
        self,
        collection_name: str = CHROMA_COLLECTION_NAME,
        persist_directory: str = CHROMA_DB_PATH,
    ) -> None:
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self._client = self._init_client()
        self._collection: "Collection" = self._get_or_create_collection()

    def _init_client(self) -> Any:
        try:
            import chromadb

            return chromadb.PersistentClient(path=self.persist_directory)
        except Exception as exc:
            logger.exception(
                "Failed to initialize ChromaDB persistent client at '%s'.",
                self.persist_directory,
            )
            raise VectorStoreError(
                f"Could not initialize ChromaDB client at '{self.persist_directory}': {exc}"
            ) from exc

    def _get_or_create_collection(self) -> "Collection":
        try:
            collection = self._client.get_or_create_collection(name=self.collection_name)
        except Exception as exc:
            logger.exception(
                "Failed to get or create collection '%s'.",
                self.collection_name,
            )
            raise VectorStoreError(
                f"Could not get or create collection '{self.collection_name}': {exc}"
            ) from exc

        logger.info(
            "Vector store ready: collection '%s' at '%s'.",
            self.collection_name,
            self.persist_directory,
        )
        return collection

    def add_chunks(
        self,
        chunks: list["DocumentChunk"],
        embeddings: list[list[float]],
    ) -> None:
        """
        Upserts a batch of chunks and their pre-computed embeddings into the
        collection. `chunks` and `embeddings` must be the same length and in
        the same order — the caller (DocumentProcessingService) is
        responsible for generating embeddings via EmbeddingService before
        calling this.

        Raises:
            VectorInsertionError: if the counts don't match, or if the
                underlying ChromaDB upsert fails.
        """
        if len(chunks) != len(embeddings):
            raise VectorInsertionError(
                f"Chunk count ({len(chunks)}) does not match embedding count "
                f"({len(embeddings)}); refusing to insert misaligned data."
            )

        if not chunks:
            logger.info("add_chunks called with an empty chunk list; nothing to insert.")
            return

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "character_count": chunk.character_count,
                "word_count": chunk.word_count,
            }
            for chunk in chunks
        ]

        try:
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        except Exception as exc:
            logger.exception(
                "Failed to upsert %d chunk(s) into collection '%s'.",
                len(chunks),
                self.collection_name,
            )
            raise VectorInsertionError(
                f"Failed to insert {len(chunks)} chunk(s) into collection "
                f"'{self.collection_name}': {exc}"
            ) from exc

        logger.info(
            "Inserted %d chunk(s) into collection '%s'.",
            len(chunks),
            self.collection_name,
        )

    def similarity_search(
        self,
        embedding: list[float],
        top_k: int = 5,
    ) -> dict[str, Any]:
        """
        Runs a similarity search against the collection and returns the raw
        ChromaDB query result (ids, documents, metadatas, distances). No
        formatting, no prompt construction — that's the caller's job
        (e.g. a future RetrievalService/LLMService).

        Raises:
            VectorSearchError: if the underlying ChromaDB query fails.
        """
        try:
            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
            )
        except Exception as exc:
            logger.exception(
                "Similarity search failed against collection '%s' (top_k=%d).",
                self.collection_name,
                top_k,
            )
            raise VectorSearchError(
                f"Similarity search failed against collection "
                f"'{self.collection_name}': {exc}"
            ) from exc

        logger.info(
            "Similarity search on collection '%s' returned %d result(s) (top_k=%d).",
            self.collection_name,
            len(results.get("ids", [[]])[0]) if results.get("ids") else 0,
            top_k,
        )

        return results