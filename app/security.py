"""
security.py - Validacion de API keys para endpoints protegidos.
"""

import hmac
import hashlib
from functools import lru_cache

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER_NAME, auto_error=False)


@lru_cache(maxsize=1)
def _allowed_keys() -> list[str]:
    return [k.strip() for k in settings.API_KEYS.split(",") if k.strip()]


def _is_valid_key(candidate: str, keys: list[str]) -> bool:
    for key in keys:
        if hmac.compare_digest(candidate, key):
            return True
    return False


def _validated_key_or_none(api_key: str | None) -> str | None:
    if not settings.API_KEY_ENABLED:
        return None

    allowed = _allowed_keys()
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEY_ENABLED=true pero API_KEYS esta vacio.",
        )

    if not api_key or not _is_valid_key(api_key, allowed):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key invalida o ausente.",
        )

    return api_key


async def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    """Valida API key cuando la proteccion esta habilitada."""
    _validated_key_or_none(api_key)


async def get_collaborator_id(api_key: str | None = Security(api_key_header)) -> str:
    """Retorna un identificador anonimo y estable por colaborador."""
    key = _validated_key_or_none(api_key)
    if not key:
        return "public"

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"key_{digest}"
