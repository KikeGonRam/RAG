import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    AskRequest,
    AskResponse,
    ChatCreateRequest,
    ChatMessageResponse,
    ChatSessionResponse,
    IngestRequest,
    IngestResponse,
)
from app.core.state import chat_store, rag
from app.security import enforce_collab_rate_limit, get_collaborator_id, require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_key)], tags=["collaborator"])


@router.post("/ingest", response_model=IngestResponse, dependencies=[Depends(enforce_collab_rate_limit)])
async def ingest(req: IngestRequest):
    texts = []
    if req.text:
        texts.append(req.text)
    if req.documents:
        texts.extend(req.documents)

    if not texts:
        raise HTTPException(status_code=400, detail="Debes enviar 'text' o 'documents'.")

    try:
        chunks_stored = await rag.ingest(texts, collection=req.collection)
        return IngestResponse(status="ok", chunks_stored=chunks_stored, collection=req.collection)
    except Exception as e:
        logger.error(f"Error en /ingest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask", response_model=AskResponse, dependencies=[Depends(enforce_collab_rate_limit)])
async def ask(req: AskRequest, collaborator_id: str = Depends(get_collaborator_id)):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacia.")

    try:
        if req.stream:
            generator = rag.ask_stream(question=req.question, collection=req.collection, top_k=req.top_k)
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

        result = await rag.ask(question=req.question, collection=req.collection, top_k=req.top_k)
        result.setdefault("mode", "llm_only" if result.get("context_used", 0) == 0 else "rag")
        result.setdefault("warning", None)

        chat_store.add_message(
            collaborator_id=collaborator_id,
            session_id=session_id,
            role="assistant",
            content=result.get("answer", ""),
            meta={"context_used": result.get("context_used", 0), "sources": result.get("sources", [])},
        )

        return AskResponse(**result, session_id=session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en /ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chats", response_model=list[ChatSessionResponse])
async def list_chats(collaborator_id: str = Depends(get_collaborator_id)):
    return chat_store.list_sessions(collaborator_id)


@router.post("/chats", response_model=ChatSessionResponse)
async def create_chat(req: ChatCreateRequest, collaborator_id: str = Depends(get_collaborator_id)):
    title = (req.title or "Nuevo chat").strip() or "Nuevo chat"
    return chat_store.create_session(collaborator_id, title)


@router.get("/chats/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_chat_messages(session_id: int, collaborator_id: str = Depends(get_collaborator_id)):
    session = chat_store.get_session(collaborator_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    return chat_store.list_messages(collaborator_id, session_id)


@router.delete("/chats/{session_id}")
async def delete_chat(session_id: int, collaborator_id: str = Depends(get_collaborator_id)):
    session = chat_store.get_session(collaborator_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    chat_store.delete_session(collaborator_id, session_id)
    return {"status": "deleted", "session_id": session_id}


@router.get("/collections")
async def list_collections():
    try:
        cols = rag.vectorstore.list_collections()
        return {"collections": cols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collection/{name}")
async def delete_collection(name: str):
    try:
        rag.vectorstore.delete_collection(name)
        return {"status": "deleted", "collection": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
