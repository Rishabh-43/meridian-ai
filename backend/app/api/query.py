from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from app.core.exceptions import LLMError, RetrievalError
from app.models.query import QueryRequest, QueryResponse
from app.services.embedding_service import EmbeddingService
from app.services.groq_provider import GroqProvider
from app.services.llm_service import LLMService
from app.services.query_service import QueryService
from app.services.retrieval_service import RetrievalService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Query"])


# Lazily-created, cached singletons. Nothing here runs at import time —
# each factory only runs the first time FastAPI resolves it as a
# dependency (i.e. the first request to /query), and lru_cache ensures
# every subsequent request reuses the same instances rather than
# recreating them.
@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore()


@lru_cache
def get_retrieval_service() -> RetrievalService:
    return RetrievalService(
        embedding_service=get_embedding_service(),
        vector_store=get_vector_store(),
    )


@lru_cache
def get_groq_provider() -> GroqProvider:
    return GroqProvider()


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService(provider=get_groq_provider())


@lru_cache
def get_query_service() -> QueryService:
    return QueryService(
        retrieval_service=get_retrieval_service(),
        llm_service=get_llm_service(),
    )


@router.post("/query", response_model=QueryResponse)
def query_documents(
    request: QueryRequest,
    query_service: QueryService = Depends(get_query_service),
) -> QueryResponse:
    logger.info(
        "Incoming query (question_length=%d, top_k=%d).",
        len(request.question),
        request.top_k,
    )

    try:
        result = query_service.answer(question=request.question, top_k=request.top_k)
    except RetrievalError as exc:
        logger.exception("Retrieval failed for incoming query.")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        logger.exception("LLM failed to generate an answer.")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error while handling query.")
        raise HTTPException(status_code=500, detail="Internal server error.") from exc

    return QueryResponse(**result)