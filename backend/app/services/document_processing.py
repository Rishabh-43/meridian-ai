from __future__ import annotations

import logging

from fastapi import UploadFile

from app.models.chunk import DocumentChunk
from app.models.document import DocumentMetadata
from app.services.chunker import DocumentChunker
from app.services.document_loader import DocumentLoader
from app.services.embedding_service import EmbeddingService
from app.services.text_processor import TextProcessor
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """
    Orchestrates the document ingestion pipeline.

    Pipeline:
        Upload
            ↓
        Save
            ↓
        Extract Text
            ↓
        Clean Text
            ↓
        Chunk
            ↓
        EmbeddingService
            ↓
        VectorStore
    """

    def __init__(
        self,
        loader: DocumentLoader,
        processor: TextProcessor,
        chunker: DocumentChunker,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self.loader = loader
        self.processor = processor
        self.chunker = chunker
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    async def upload_document(
        self,
        file: UploadFile,
    ) -> tuple[DocumentMetadata, str]:
        """
        Upload endpoint pipeline.

        Returns:
            metadata,
            cleaned preview text
        """

        metadata, saved_path = await self.loader.save(file)

        text = self.loader.extract_text(saved_path)

        cleaned_text = self.processor.clean(text)

        metadata.character_count = len(cleaned_text)
        metadata.word_count = len(cleaned_text.split())
        metadata.status = "processed"

        logger.info(
            "Upload pipeline completed for document %s",
            metadata.document_id,
        )

        return metadata, cleaned_text

    async def chunk_document(
        self,
        file: UploadFile,
    ) -> tuple[DocumentMetadata, list[DocumentChunk]]:
        """
        Chunk endpoint pipeline.

        Returns:
            metadata,
            generated chunks
        """

        metadata, saved_path = await self.loader.save(file)

        text = self.loader.extract_text(saved_path)

        cleaned_text = self.processor.clean(text)

        metadata.character_count = len(cleaned_text)
        metadata.word_count = len(cleaned_text.split())

        chunks = self.chunker.split(
            text=cleaned_text,
            document_id=metadata.document_id,
        )

        metadata.chunk_count = len(chunks)

        logger.info(
            "Generated %d chunks for document %s",
            len(chunks),
            metadata.document_id,
        )

        if chunks:
            try:
                embeddings = self.embedding_service.embed([chunk.text for chunk in chunks])

                logger.info(
                    "Generated %d embedding(s) for document %s",
                    len(embeddings),
                    metadata.document_id,
                )

                self.vector_store.add_chunks(chunks, embeddings)

                logger.info(
                    "Inserted %d chunk(s) into vector store for document %s",
                    len(chunks),
                    metadata.document_id,
                )
            except Exception:
                logger.exception(
                    "Failed ingesting document %s during embedding/storage",
                    metadata.document_id,
                )
                raise

        # Only marked "processed" once chunking (and, if applicable,
        # embedding + storage) has fully succeeded — a document must never
        # be reported as processed while ingestion may have failed partway.
        metadata.status = "processed"

        return metadata, chunks