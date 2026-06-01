from typing import Optional

from pydantic import BaseModel


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
    mode: str
    warning: Optional[str] = None
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


class AdminCreateKeyRequest(BaseModel):
    name: str


class AdminApiKeyRow(BaseModel):
    id: int
    name: str
    key_prefix: str
    is_active: int
    created_at: str
    last_used_at: Optional[str] = None
    use_count: int


class AdminCreateKeyResponse(AdminApiKeyRow):
    api_key: str
