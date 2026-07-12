# Meridian AI — RAG Backend

A FastAPI backend implementing a Retrieval-Augmented Generation (RAG) pipeline: upload a document, chunk and embed it, store it in a local vector database, then ask natural-language questions answered from that document's content using Groq-hosted LLMs.

## Demo


https://github.com/user-attachments/assets/e856061d-a610-4bb2-9c1c-73aeba2eff33





The video demonstrates the complete workflow:
- Browse and select a PDF, DOCX, or TXT file.
- Upload and process the document.
- Ask questions about the uploaded document.
- Receive context-aware answers generated using the RAG pipeline.

## Pipeline

```
Upload → Extract Text → Clean Text → Chunk → Generate Embeddings → Store in ChromaDB
                                                                          │
Query → Embed Question → Similarity Search → Build Context → Generate Answer (Groq)
```

| Stage | Responsibility | Module |
|---|---|---|
| Load & extract | Save the upload, extract text from PDF/DOCX/TXT | `app/services/document_loader.py` |
| Clean | Normalize whitespace/line endings | `app/services/text_processor.py` |
| Chunk | Split cleaned text into overlapping chunks | `app/services/chunker.py` |
| Embed | Generate dense vector embeddings (local sentence-transformers model) | `app/services/embedding_service.py` |
| Store | Persist chunks + embeddings in ChromaDB | `app/services/vector_store.py` |
| Retrieve | Embed a question, similarity-search the store | `app/services/retrieval_service.py` |
| Generate | Send retrieved context + question to Groq, return a grounded answer | `app/services/llm_service.py`, `app/services/groq_provider.py` |
| Orchestrate | Wire the above into the two end-to-end pipelines | `app/services/document_processing.py` (ingestion), `app/services/query_service.py` (query) |

All services are constructor-injected (no service instantiates its own dependencies), which is why they're independently unit-testable — see [Testing](#testing).

## Requirements

- Python 3.11+ (developed against 3.12/3.13)
- A [Groq API key](https://console.groq.com)
- ~2–3 GB free disk for the embedding model and its dependencies (PyTorch, sentence-transformers)

## Tech Stack

- FastAPI
- Python
- ChromaDB
- Sentence Transformers (BAAI/bge-small-en-v1.5)
- Groq API
- PyTorch
- Pytest

## Setup

```bash
# 1. Clone / enter the project
cd backend

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables (see below)
cp .env.example .env              # if you're starting fresh
# otherwise edit the existing .env directly

# 5. Run the server
uvicorn app.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`, with interactive docs at `http://127.0.0.1:8000/docs`.

## Environment Variables

Configuration is read from a `.env` file in the `backend/` directory (loaded via `python-dotenv` in `app/core/config.py`).

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | *(none — empty string)* | Your Groq API key. Required for `/query` to generate answers. |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Groq model used for answer generation. |

Example `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
```

> **Security note:** `.env` holds a live secret. Do not commit it. If a Groq key has ever been committed to source control or shared, rotate it in the [Groq console](https://console.groq.com/keys) before deploying.

All other settings (upload limits, chunk size, embedding model, ChromaDB path, default `top_k`, LLM temperature/max tokens) are code-level constants in `app/core/config.py` rather than environment variables, since they define the pipeline's behavior rather than per-deployment secrets. Adjust them there if needed.

## API Reference

### `POST /upload/`
Uploads a document, extracts and cleans its text. Does **not** chunk, embed, or store it.

- **Body:** `multipart/form-data`, field `file` — a `.pdf`, `.docx`, or `.txt` file (max 10 MB)
- **Response `200`:**
  ```json
  {
    "success": true,
    "document": { "document_id": "...", "filename": "...", "status": "processed", "...": "..." },
    "preview": "first 500 characters of cleaned text"
  }
  ```
- **Errors:** `415` unsupported file type, `413` file too large, `400` empty/unreadable document

### `POST /chunk/`
Runs the **full ingestion pipeline**: upload → extract → clean → chunk → embed → store in ChromaDB.

- **Body:** same as `/upload/`
- **Response `200`:**
  ```json
  {
    "document": { "document_id": "...", "chunk_count": 12, "...": "..." },
    "chunks": [ { "chunk_id": "...", "chunk_index": 0, "text": "...", "...": "..." } ]
  }
  ```
- **Errors:** same as `/upload/`

### `POST /query`
Answers a natural-language question using content previously ingested via `/chunk/`.

- **Body:**
  ```json
  { "question": "What programming languages does Rishabh know?", "top_k": 5 }
  ```
  `top_k` is optional (defaults to `5`).
- **Response `200`:**
  ```json
  {
    "answer": "C++, Python, HTML and CSS.",
    "context": "Chunk 1\n...\n--------------------------------\nChunk 2\n...",
    "retrieved_chunks": 2
  }
  ```
  If no relevant chunks are found, `answer` returns a fixed fallback message with `retrieved_chunks: 0` and an empty `context`, without calling the LLM.
- **Errors:** `400` retrieval failure, `500` LLM failure

### `GET /health`
Liveness check — returns `{"status": "healthy"}`.

### `GET /`
Returns project name, version, and status.

## Testing

The project uses `pytest`. Run the full suite from `backend/`:

```bash
pytest
```

Tests are organized as:

- **Pure unit tests** (`test_chunker.py`, `test_text_processor.py`, `test_llm_service.py`, `test_retrieval_service.py`, `test_query_service.py`) — no model load, no network, no disk beyond a temp directory. These always run.
- **Vector store tests** (`test_vector_store.py`) — exercise a real ChromaDB instance backed by a throwaway temp directory (via the `tmp_path` fixture). No embedding model involved.
- **API tests** (`test_api_upload.py`, `test_api_chunk.py`, `test_api_query.py`, `test_api_health.py`) — exercise the real FastAPI app end-to-end via `TestClient`. The embedding/vector-store/LLM dependencies are swapped for fast, deterministic test doubles (see `tests/fakes.py`) so no real model inference, ChromaDB writes, or Groq calls occur.
- **Embedding integration tests** (`test_embedding_service.py`) — load the real sentence-transformers model. Marked `@pytest.mark.integration` and will **skip automatically** (not fail) in any environment where the model can't be loaded, e.g. no network on first run and no local model cache.

To skip the slower integration tests:

```bash
pytest -m "not integration"
```

## Known Limitations

- **Duplicate chunks on repeated uploads:** each call to `/chunk/` generates a fresh `document_id` and fresh chunk UUIDs, so re-uploading the same file multiple times (e.g. during manual testing) inserts duplicate entries into ChromaDB rather than overwriting the previous ones. This doesn't break retrieval but can slightly dilute answer quality over many repeated test uploads. Not currently a blocker; a content-based document identity (e.g. hash the file) would be the fix if it becomes one.
- Chunk size, overlap, embedding model, and default `top_k` are fixed in `app/core/config.py` rather than configurable per-request.

## Project Structure

```
backend/
├── app/
│   ├── api/            # FastAPI route handlers (upload, chunk, query, health)
│   ├── core/           # Config, custom exceptions
│   ├── models/         # Pydantic request/response/domain models
│   ├── services/       # Pipeline logic (loader, chunker, embeddings, vector store, retrieval, LLM)
│   └── main.py         # FastAPI app entrypoint
├── tests/              # pytest suite (unit, integration, and API-level tests) + shared fakes
├── uploads/            # Saved uploaded files (created at runtime)
├── data/chroma/        # Persistent ChromaDB store (created at runtime)
├── requirements.txt
├── pytest.ini
└── .env                # Local secrets/config (not committed)
```
