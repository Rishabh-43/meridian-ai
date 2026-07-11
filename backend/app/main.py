from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.upload import router as upload_router
from app.api.chunk import router as chunk_router
from app.api.query import router as query_router

from app.core.config import APP_NAME, VERSION

app = FastAPI(
    title=APP_NAME,
    version=VERSION,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(upload_router)
app.include_router(chunk_router)
app.include_router(query_router)


@app.get("/")
def root():
    return {
        "project": APP_NAME,
        "version": VERSION,
        "status": "running",
    }