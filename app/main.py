import logging
import time
import uuid

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.observability import observe_http_request

logger = logging.getLogger(__name__)


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

    if settings.RAG_MODE_REQUIRED and not settings.EMBEDDING_MODEL:
        raise RuntimeError(
            "En APP_ENV=production con RAG_MODE_REQUIRED=true debes configurar EMBEDDING_MODEL.",
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


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id_header = settings.REQUEST_ID_HEADER_NAME
    request_id = request.headers.get(request_id_header) or str(uuid.uuid4())
    request.state.request_id = request_id

    status_code = 500
    started = time.perf_counter()
    route_path = request.url.path

    try:
        response = await call_next(request)
        status_code = response.status_code
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        response.headers[request_id_header] = request_id
        return response
    finally:
        elapsed = time.perf_counter() - started
        observe_http_request(request.method, route_path, status_code, elapsed)
        if settings.ACCESS_LOG_ENABLED:
            logger.info(
                "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
                request_id,
                request.method,
                route_path,
                status_code,
                elapsed * 1000,
            )

app.include_router(api_router)
