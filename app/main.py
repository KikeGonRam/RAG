from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(
    title="RAG Ollama API",
    description="Sistema RAG local con arquitectura modular y capacidades MCP-ready",
    version="1.1.0",
)

app.include_router(api_router)
