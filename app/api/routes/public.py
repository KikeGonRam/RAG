from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.state import ADMIN_UI_PATH, UI_PATH, rag
from app.mcp.capabilities import get_mcp_capabilities

router = APIRouter(tags=["public"])


@router.get("/")
async def root():
    return {"message": "RAG Ollama API corriendo", "docs": "/docs"}


@router.get("/ui", include_in_schema=False)
async def ui():
    if not UI_PATH.exists():
        raise HTTPException(status_code=404, detail="UI no encontrada")
    return FileResponse(UI_PATH)


@router.get("/admin", include_in_schema=False)
async def admin_ui():
    if not ADMIN_UI_PATH.exists():
        raise HTTPException(status_code=404, detail="Panel admin no encontrado")
    return FileResponse(ADMIN_UI_PATH)


@router.get("/health")
async def health():
    status = await rag.health_check()
    if not status["ollama"] or not status["chromadb"]:
        raise HTTPException(status_code=503, detail=status)
    return status


@router.get("/mcp/capabilities", tags=["mcp"])
async def mcp_capabilities():
    return get_mcp_capabilities()
