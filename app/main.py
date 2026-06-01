from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import logging
from pathlib import Path

from app.chat_store import ChatStore
from app.rag import RAGPipeline
from app.security import get_collaborator_id, require_api_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Ollama API",
    description="Sistema RAG local con Ollama + ChromaDB",
    version="1.0.0"
)

rag = RAGPipeline()
chat_store = ChatStore()
UI_PATH = Path(__file__).parent / "static" / "index.html"


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
    session_id: Optional[int] = None

class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    context_used: int
    session_id: int


class ChatCreateRequest(BaseModel):
    title: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: int
    collaborator_id: str
    title: str
    created_at: str
    updated_at: str


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    meta: dict
    created_at: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "RAG Ollama API corriendo 🚀", "docs": "/docs"}


@app.get("/ui", include_in_schema=False)
async def ui():
    """Interfaz visual basica para usuarios finales."""
    if not UI_PATH.exists():
        raise HTTPException(status_code=404, detail="UI no encontrada")
    return FileResponse(UI_PATH)


@app.get("/health")
async def health():
    """Verifica que Ollama y ChromaDB estén disponibles."""
    status = await rag.health_check()
    if not status["ollama"] or not status["chromadb"]:
        raise HTTPException(status_code=503, detail=status)
    return status


@app.post("/ingest", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
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


@app.post("/ask", dependencies=[Depends(require_api_key)])
async def ask(req: AskRequest, collaborator_id: str = Depends(get_collaborator_id)):
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

        if req.session_id:
            session = chat_store.get_session(collaborator_id, req.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Sesion no encontrada")
            session_id = req.session_id
        else:
            title = req.question.strip()[:60] or "Nuevo chat"
            created = chat_store.create_session(collaborator_id, title)
            session_id = int(created["id"])

        chat_store.add_message(
            collaborator_id=collaborator_id,
            session_id=session_id,
            role="user",
            content=req.question,
            meta={"collection": req.collection, "top_k": req.top_k},
        )

        result = await rag.ask(
            question=req.question,
            collection=req.collection,
            top_k=req.top_k
        )

        chat_store.add_message(
            collaborator_id=collaborator_id,
            session_id=session_id,
            role="assistant",
            content=result.get("answer", ""),
            meta={
                "context_used": result.get("context_used", 0),
                "sources": result.get("sources", []),
            },
        )

        return AskResponse(**result, session_id=session_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en /ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chats", response_model=list[ChatSessionResponse], dependencies=[Depends(require_api_key)])
async def list_chats(collaborator_id: str = Depends(get_collaborator_id)):
    """Lista sesiones del colaborador autenticado."""
    return chat_store.list_sessions(collaborator_id)


@app.post("/chats", response_model=ChatSessionResponse, dependencies=[Depends(require_api_key)])
async def create_chat(req: ChatCreateRequest, collaborator_id: str = Depends(get_collaborator_id)):
    """Crea una sesion nueva de chat para el colaborador."""
    title = (req.title or "Nuevo chat").strip() or "Nuevo chat"
    return chat_store.create_session(collaborator_id, title)


@app.get(
    "/chats/{session_id}/messages",
    response_model=list[ChatMessageResponse],
    dependencies=[Depends(require_api_key)],
)
async def get_chat_messages(session_id: int, collaborator_id: str = Depends(get_collaborator_id)):
    """Obtiene el historial de mensajes de una sesion del colaborador."""
    session = chat_store.get_session(collaborator_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    return chat_store.list_messages(collaborator_id, session_id)


@app.delete("/chats/{session_id}", dependencies=[Depends(require_api_key)])
async def delete_chat(session_id: int, collaborator_id: str = Depends(get_collaborator_id)):
    """Elimina una sesion de chat (y sus mensajes)."""
    session = chat_store.get_session(collaborator_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    chat_store.delete_session(collaborator_id, session_id)
    return {"status": "deleted", "session_id": session_id}


@app.delete("/collection/{name}", dependencies=[Depends(require_api_key)])
async def delete_collection(name: str):
    """Elimina una colección de ChromaDB."""
    try:
        rag.vectorstore.delete_collection(name)
        return {"status": "deleted", "collection": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collections", dependencies=[Depends(require_api_key)])
async def list_collections():
    """Lista todas las colecciones existentes."""
    try:
        cols = rag.vectorstore.list_collections()
        return {"collections": cols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
