from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.exceptions import LLMError

if TYPE_CHECKING:
    from app.services.groq_provider import LLMProvider

logger = logging.getLogger(__name__)


class LLMService:
    """
    Thin orchestration layer over an injected LLMProvider.

    Responsibility boundary: this class ONLY validates input, delegates to
    the provider, and returns the answer. It does not retrieve context,
    does not generate embeddings, and does not perform vector search — and
    it never talks to Groq (or any vendor SDK) directly, only through the
    LLMProvider interface. Swapping providers is a constructor argument
    change, not a change to this class.
    """

    def __init__(self, provider: "LLMProvider") -> None:
        self._provider = provider

    def answer(self, question: str, context: str) -> str:
        """
        Validates input and delegates to the provider to generate a
        grounded answer.

        Raises:
            LLMError: if `question` is empty/whitespace-only, or if the
                underlying provider fails to generate an answer.
        """
        if not question or not question.strip():
            raise LLMError("Question must not be empty.")

        logger.info(
            "Generating answer for question of length %d (context length %d).",
            len(question),
            len(context) if context else 0,
        )

        try:
            answer = self._provider.generate_answer(question=question, context=context or "")
        except LLMError:
            raise
        except Exception as exc:
            logger.exception("LLM provider failed to generate an answer.")
            raise LLMError(f"Failed to generate an answer: {exc}") from exc

        logger.info("Answer generated successfully (length=%d).", len(answer) if answer else 0)

        return answer