# Meridian AI RAG Backend — production container image
FROM python:3.12-slim

WORKDIR /app

# System build dependencies:
# - build-essential: some packages in requirements.txt (e.g. chroma-hnswlib) compile
#   native extensions and don't ship a prebuilt wheel for every platform.
# - curl: used by the HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so this layer is cached unless requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Application code only — tests, .env, uploads/, data/ are excluded via .dockerignore.
COPY app ./app

# Runtime directories used by the app (uploaded files, ChromaDB persistence).
# On most PaaS platforms these are ephemeral unless a persistent volume/disk is
# mounted at this path — see the deployment notes in README.md.
RUN mkdir -p uploads data/chroma

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Respect the platform-provided $PORT (Render/Railway) if set, otherwise default to 8000.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
