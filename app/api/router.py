from fastapi import APIRouter

from app.api.routes.admin_keys import router as admin_keys_router
from app.api.routes.collab import router as collab_router
from app.api.routes.public import router as public_router

api_router = APIRouter()
api_router.include_router(public_router)
api_router.include_router(collab_router)
api_router.include_router(admin_keys_router)
