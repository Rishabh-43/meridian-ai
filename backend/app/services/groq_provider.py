from __future__ import annotations

import abc
import logging

from app.core.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    MAX_OUTPUT_TOKENS,
    TEMPERATURE,
)
from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are Meridian AI.\n"
    "Answer ONLY using the provided context.\n"
    "If the answer cannot be found in the context, say "
    '"I don\'t have enough information from the provided documents."\n'
    "Do not hallucinate."
)


class LLMProvider(abc.ABC):
    """
    Abstract interface every LLM backend must implement. The rest of the
    project depends only on this interface (via LLMService) and never on a
    specific vendor SDK, so swapping providers later does not touch any
    other module.
    """

    @abc.abstractmethod
    def generate_answer(self, question: str, context: str) -> str:
        ...


class GroqProvider(LLMProvider):
    """
    Communicates with the Groq API to generate a grounded answer.

    Responsibility boundary: this class ONLY builds the Groq request, sends
    it, and returns the generated answer text. It does not validate input
    (that's LLMService's job), does not retrieve context, and does not
    generate embeddings.
    """

    def __init__(
        self,
        api_key: str = GROQ_API_KEY,
        model: str = GROQ_MODEL,
        temperature: float = TEMPERATURE,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._client = self._init_client(api_key)

    def _init_client(self, api_key: str):
        try:
            from groq import Groq

            return Groq(api_key=api_key)
        except Exception as exc:
            logger.exception("Failed to initialize Groq client.")
            raise ProviderError(f"Could not initialize Groq client: {exc}") from exc

    def generate_answer(self, question: str, context: str) -> str:
        """
        Sends a grounded chat completion request to Groq and returns the
        generated answer text.

        Raises:
            ProviderError: if the Groq API call fails.
        """
        user_message = f"Context\n{context}\n\nQuestion\n{question}"

        logger.info(
            "Sending request to Groq (model=%s, temperature=%s, max_output_tokens=%d).",
            self.model,
            self.temperature,
            self.max_output_tokens,
        )

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=self.temperature,
                max_completion_tokens=self.max_output_tokens,
            )
        except Exception as exc:
            logger.exception("Groq request failed (model=%s).", self.model)
            raise ProviderError(f"Groq request failed: {exc}") from exc

        answer = response.choices[0].message.content

        logger.info(
            "Response received from Groq (model=%s, answer_length=%d).",
            self.model,
            len(answer) if answer else 0,
        )

        return answer