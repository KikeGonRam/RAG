"""
security.py - Validacion de API keys para endpoints protegidos.
"""

import hmac
import hashlib
from functools import lru_cache

from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.api_key_store import ApiKeyStore
from app.config import settings

api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER_NAME, auto_error=False)
api_key_store = ApiKeyStore()


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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_PANEL_PASSWORD no configurado.",
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
