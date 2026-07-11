from datetime import datetime

from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    document_id: str
    filename: str
    stored_filename: str
    extension: str

    size_bytes: int

    character_count: int
    word_count: int

    chunk_count: int = 0

    uploaded_at: datetime

    status: str