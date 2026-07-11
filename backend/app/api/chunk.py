import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.exceptions import (
    DocumentError,
    EmptyDocument,
    FileTooLarge,
    UnsupportedFileType,
)
from app.services.chunker import DocumentChunker
from app.services.document_loader import DocumentLoader
from app.services.document_processing import DocumentProcessingService
from app.services.embedding_service import EmbeddingService
from app.services.text_processor import TextProcessor
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chunk",
    tags=["Chunking"],
)

# Dependencies
loader = DocumentLoader()
processor = TextProcessor()
chunker = DocumentChunker()
embedding_service = EmbeddingService()
vector_store = VectorStore()

document_service = DocumentProcessingService(
    loader=loader,
    processor=processor,
    chunker=chunker,
    embedding_service=embedding_service,
    vector_store=vector_store,
)


@router.post("/")
async def chunk_document(
    file: UploadFile = File(...),
):
    try:
        metadata, chunks = await document_service.chunk_document(file)

        return {
            "document": metadata.model_dump(mode="json"),
            "chunks": [
                chunk.model_dump(mode="json")
                for chunk in chunks
            ],
        }

    except UnsupportedFileType as exc:
        raise HTTPException(
            status_code=415,
            detail=str(exc),
        )

    except FileTooLarge as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        )

    except EmptyDocument as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except DocumentError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:
        logger.exception(
            "Unexpected error while chunking document."
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error.",
        )