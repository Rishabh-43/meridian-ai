from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.llm_service import LLMService
    from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

_NO_CONTEXT_ANSWER = "I couldn't find any relevant information in the uploaded documents."


class QueryService:
    """
    Orchestrates the full RAG query pipeline: retrieve -> build context ->
    generate answer (or short-circuit with a fallback if no context was
    found).

    This is the query-side counterpart to DocumentProcessingService: the
    API layer (app/api/query.py) should know nothing about retrieval,
    context, or LLM calls — it only calls `QueryService.answer()` and
    translates whatever domain exception comes back into an HTTP response.

    Dependencies are injected via the constructor, not instantiated
    internally, consistent with the rest of the project.
    """

    def __init__(
        self,
        retrieval_service: "RetrievalService",
        llm_service: "LLMService",
    ) -> None:
        self._retrieval_service = retrieval_service
        self._llm_service = llm_service

    def answer(self, question: str, top_k: int) -> dict[str, Any]:
        """
        Runs the full pipeline for one question and returns a plain dict
        with `answer`, `context`, and `retrieved_chunks` — shaped to match
        QueryResponse, but without importing/depending on the API's
        Pydantic model, keeping this service HTTP-agnostic.

        Domain exceptions (RetrievalError, LLMError) are intentionally NOT
        caught here — they propagate to the API layer, which is
        responsible for translating them into HTTP responses.
        """
        results = self._retrieval_service.retrieve(question=question, top_k=top_k)
        context = self._retrieval_service.build_context(results)

        documents = results.get("documents")
        retrieved_chunks = len(documents[0]) if documents and documents[0] else 0

        logger.info("Retrieval completed: %d chunk(s) found.", retrieved_chunks)

        if not context:
            logger.info("No context available; skipping LLM call.")
            return {
                "answer": _NO_CONTEXT_ANSWER,
                "context": "",
                "retrieved_chunks": 0,
            }

        answer = self._llm_service.answer(question=question, context=context)

        logger.info("Answer generated (retrieved_chunks=%d).", retrieved_chunks)

        return {
            "answer": answer,
            "context": context,
            "retrieved_chunks": retrieved_chunks,
        }