from pathlib import Path

APP_NAME = "Meridian AI"
VERSION = "1.0.0"

# Upload Configuration
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# Chunking Configuration
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Embedding Configuration
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DEVICE = "cpu"
EMBEDDING_BATCH_SIZE = 32
EMBEDDING_NORMALIZE = True

# ChromaDB Configuration
CHROMA_DB_PATH = "data/chroma"
CHROMA_COLLECTION_NAME = "documents"

# Retrieval Configuration
DEFAULT_TOP_K = 5

# Groq 

import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

TEMPERATURE = 0.2
MAX_OUTPUT_TOKENS = 1024