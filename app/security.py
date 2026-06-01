"""
security.py - Validacion de API keys para endpoints protegidos.
"""

import hmac
import hashlib
import time
from functools import lru_cache

from fastapi import Header, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from app.api_key_store import ApiKeyStore
from app.config import settings

api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER_NAME, auto_error=False)
api_key_store = ApiKeyStore()
_rate_limit_hits: dict[str, list[float]] = {}


@lru_cache(maxsize=1)
def _allowed_keys() -> list[str]:
    return [k.strip() for k in settings.API_KEYS.split(",") if k.strip()]


def _is_valid_key(candidate: str, keys: list[str]) -> bool:
    for key in keys:
        if hmac.compare_digest(candidate, key):
            return True
    return False


def _validate_static_key(candidate: str | None) -> bool:
    if not candidate:
        return False
    static_keys = _allowed_keys()
    if not static_keys:
        return False
    return _is_valid_key(candidate, static_keys)


def _validate_dynamic_key(candidate: str | None) -> dict | None:
    if not candidate:
        return None
    return api_key_store.validate_key(candidate)


def _validated_key_or_none(api_key: str | None) -> str | None:
    if not settings.API_KEY_ENABLED:
        return None

    if _validate_static_key(api_key):
        return api_key

    if _validate_dynamic_key(api_key):
        return api_key

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key ausente.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API key invalida.",
    )


async def require_admin_password(
    admin_password: str | None = Header(default=None, alias=settings.ADMIN_PASSWORD_HEADER_NAME),
) -> None:
    """Valida password para operaciones de administracion de API keys."""
    expected = settings.ADMIN_PANEL_PASSWORD.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Panel de administracion deshabilitado: configura ADMIN_PANEL_PASSWORD.",
        )

    if not admin_password or not hmac.compare_digest(admin_password, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de administrador invalidas.",
        )

    return None


async def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    """Valida API key cuando la proteccion esta habilitada."""
    _validated_key_or_none(api_key)
    row = _validate_dynamic_key(api_key)
    if row:
        api_key_store.register_use(int(row["id"]))


async def get_collaborator_id(api_key: str | None = Security(api_key_header)) -> str:
    """Retorna un identificador anonimo y estable por colaborador."""
    key = _validated_key_or_none(api_key)
    if not key:
        return "public"

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"key_{digest}"


def _request_identity(request: Request, api_key: str | None) -> str:
    if api_key:
        return f"k:{hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:16]}"

    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        if ip:
            return f"ip:{ip}"

    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


async def enforce_collab_rate_limit(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return

    identity = _request_identity(request, api_key if settings.API_KEY_ENABLED else None)
    route_path = request.url.path
    bucket = f"{identity}:{route_path}"
    now = time.time()
    window_seconds = max(1, settings.RATE_LIMIT_WINDOW_SECONDS)
    max_requests = max(1, settings.RATE_LIMIT_REQUESTS_PER_MINUTE)
    window_start = now - window_seconds

    hits = _rate_limit_hits.get(bucket, [])
    hits = [ts for ts in hits if ts >= window_start]

    if len(hits) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit excedido. Intenta de nuevo en unos segundos.",
        )

    hits.append(now)
    _rate_limit_hits[bucket] = hits
