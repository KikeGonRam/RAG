from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import logging

from app.rag import RAGPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Ollama API",
    description="Sistema RAG local con Ollama + ChromaDB",
    version="1.0.0"
)

rag = RAGPipeline()


# ── Schemas ──────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    text: Optional[str] = None
    documents: Optional[list[str]] = None
    collection: str = "default"

class IngestResponse(BaseModel):
    status: str
    chunks_stored: int
    collection: str

class AskRequest(BaseModel):
    question: str
    collection: str = "default"
    top_k: int = 4
    stream: bool = False

class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    context_used: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "RAG Ollama API corriendo 🚀", "docs": "/docs"}


@app.get("/health")
async def health():
    """Verifica que Ollama y ChromaDB estén disponibles."""
    status = await rag.health_check()
    if not status["ollama"] or not status["chromadb"]:
        raise HTTPException(status_code=503, detail=status)
    return status


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    """
    Ingesta documentos al vector store.
    Acepta un campo `text` (string) o `documents` (lista de strings).
    """
    texts = []

    if req.text:
        texts.append(req.text)
    if req.documents:
        texts.extend(req.documents)

    if not texts:
        raise HTTPException(status_code=400, detail="Debes enviar 'text' o 'documents'.")

    try:
        chunks_stored = await rag.ingest(texts, collection=req.collection)
        return IngestResponse(
            status="ok",
            chunks_stored=chunks_stored,
            collection=req.collection
        )
    except Exception as e:
        logger.error(f"Error en /ingest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask")
async def ask(req: AskRequest):
    """
    Recibe una pregunta, busca contexto en ChromaDB y consulta Ollama.
    Soporta streaming opcional con `stream: true`.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")

    try:
        if req.stream:
            generator = rag.ask_stream(
                question=req.question,
                collection=req.collection,
                top_k=req.top_k
            )
            return StreamingResponse(generator, media_type="text/event-stream")

        result = await rag.ask(
            question=req.question,
            collection=req.collection,
            top_k=req.top_k
        )
        return AskResponse(**result)

    except Exception as e:
        logger.error(f"Error en /ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/collection/{name}")
async def delete_collection(name: str):
    """Elimina una colección de ChromaDB."""
    try:
        rag.vectorstore.delete_collection(name)
        return {"status": "deleted", "collection": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collections")
async def list_collections():
    """Lista todas las colecciones existentes."""
    try:
        cols = rag.vectorstore.list_collections()
        return {"collections": cols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
