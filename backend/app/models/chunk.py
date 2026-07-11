from pydantic import BaseModel


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str

    chunk_index: int

    text: str

    character_count: int
    word_count: int