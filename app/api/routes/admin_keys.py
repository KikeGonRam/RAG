from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import AdminApiKeyRow, AdminCreateKeyRequest, AdminCreateKeyResponse
from app.core.state import api_key_store
from app.security import require_admin_password

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_password)])


@router.get("/keys", response_model=list[AdminApiKeyRow])
async def admin_list_keys():
    return api_key_store.list_keys()


@router.post("/keys", response_model=AdminCreateKeyResponse)
async def admin_create_key(req: AdminCreateKeyRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre de la key es obligatorio")
    return api_key_store.create_key(name=name)


@router.delete("/keys/{key_id}")
async def admin_deactivate_key(key_id: int):
    ok = api_key_store.deactivate_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Key no encontrada")
    return {"status": "deactivated", "key_id": key_id}
