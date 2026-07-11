class DocumentError(Exception):
    """Base document exception."""


class UnsupportedFileType(DocumentError):
    """Unsupported file type."""


class FileTooLarge(DocumentError):
    """File too large."""


class EmptyDocument(DocumentError):
    """Document contains no readable text."""


# ==========================
# Embedding Exceptions
# ==========================

class EmbeddingError(Exception):
    """Base embedding exception."""


class EmbeddingModelLoadError(EmbeddingError):
    """Embedding model failed to load."""


class EmptyEmbeddingInput(EmbeddingError):
    """Embedding input was empty or contained no usable text."""


# ==========================
# Vector Store Exceptions
# ==========================

class VectorStoreError(Exception):
    """Base vector store exception."""


class VectorInsertionError(VectorStoreError):
    """Failed to insert vectors into the store."""


class VectorSearchError(VectorStoreError):
    """Failed to search the vector store."""


# ==========================
# Retrieval Exceptions
# ==========================

class RetrievalError(Exception):
    """Failed to retrieve or prepare context from the vector store."""


# ==========================
# LLM Exceptions
# ==========================

class LLMError(Exception):
    """Base LLM exception."""


class ProviderError(LLMError):
    """An LLM provider failed to generate a response."""