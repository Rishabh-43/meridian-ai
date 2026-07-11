from __future__ import annotations

import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
)
from app.models.chunk import DocumentChunk


class DocumentChunker:
    """
    Converts cleaned document text into embedding-ready chunks.
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",
                "\n",
                ". ",
                "? ",
                "! ",
                " ",
                "",
            ],
        )

    def split(
        self,
        *,
        text: str,
        document_id: str,
    ) -> list[DocumentChunk]:
        """
        Split a document into ordered chunks.
        """

        pieces = self.splitter.split_text(text)

        chunks: list[DocumentChunk] = []

        for index, piece in enumerate(pieces):

            piece = piece.strip()

            if not piece:
                continue

            chunks.append(
                DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=document_id,
                    chunk_index=index,
                    text=piece,
                    character_count=len(piece),
                    word_count=len(piece.split()),
                )
            )

        return chunks