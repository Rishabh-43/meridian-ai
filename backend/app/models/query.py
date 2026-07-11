from __future__ import annotations

from pydantic import BaseModel

from app.core.config import DEFAULT_TOP_K


class QueryRequest(BaseModel):
    question: str
    top_k: int = DEFAULT_TOP_K


class QueryResponse(BaseModel):
    answer: str
    context: str
    retrieved_chunks: int