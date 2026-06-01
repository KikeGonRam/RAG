from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings


def _validate_security_configuration(origins: list[str]) -> None:
    if not settings.is_production():
        return

    allow_all_origins = len(origins) == 1 and origins[0] == "*"

    if not settings.API_KEY_ENABLED:
        raise RuntimeError("En APP_ENV=production debes activar API_KEY_ENABLED=true.")

    if not settings.ADMIN_PANEL_PASSWORD.strip():
        raise RuntimeError("En APP_ENV=production debes configurar ADMIN_PANEL_PASSWORD.")

    if allow_all_origins:
        raise RuntimeError(
            "En APP_ENV=production no se permite CORS wildcard. Define CORS_ALLOWED_ORIGINS.",
        )

app = FastAPI(
    title="RAG Ollama API",
    description="Sistema RAG local con arquitectura modular y capacidades MCP-ready",
    version="1.1.0",
)

origins = settings.cors_origins()
_validate_security_configuration(origins)
allow_all_origins = len(origins) == 1 and origins[0] == "*"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=settings.cors_headers() or ["*"],
)
app.include_router(api_router)
