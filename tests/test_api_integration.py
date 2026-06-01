from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import security
from app.config import settings


class _StubVectorStore:
    def list_collections(self) -> list[str]:
        return ["default"]

    def delete_collection(self, name: str) -> None:
        _ = name


class _StubRag:
    def __init__(self) -> None:
        self.vectorstore = _StubVectorStore()

    async def health_check(self) -> dict:
        return {"ollama": True, "chromadb": True, "status": "ok"}

    async def ingest(self, texts: list[str], collection: str = "default") -> int:
        _ = collection
        return len(texts)

    async def ask(self, question: str, collection: str = "default", top_k: int = 4) -> dict:
        _ = collection
        _ = top_k
        return {
            "answer": f"Echo: {question}",
            "sources": [],
            "context_used": 0,
        }

    async def ask_stream(self, question: str, collection: str = "default", top_k: int = 4):
        _ = question
        _ = collection
        _ = top_k
        yield "data: stream\n\n"
        yield "data: [DONE]\n\n"


class _StubChatStore:
    def __init__(self) -> None:
        self._sessions: dict[int, dict] = {}
        self._messages: dict[int, list[dict]] = {}
        self._next_session_id = 1
        self._next_message_id = 1

    def create_session(self, collaborator_id: str, title: str) -> dict:
        session_id = self._next_session_id
        self._next_session_id += 1
        row = {
            "id": session_id,
            "collaborator_id": collaborator_id,
            "title": title,
            "created_at": "2026-01-01 00:00:00",
            "updated_at": "2026-01-01 00:00:00",
        }
        self._sessions[session_id] = row
        self._messages[session_id] = []
        return row

    def get_session(self, collaborator_id: str, session_id: int) -> dict | None:
        row = self._sessions.get(session_id)
        if not row:
            return None
        if row["collaborator_id"] != collaborator_id:
            return None
        return row

    def list_sessions(self, collaborator_id: str) -> list[dict]:
        return [s for s in self._sessions.values() if s["collaborator_id"] == collaborator_id]

    def delete_session(self, collaborator_id: str, session_id: int) -> None:
        row = self.get_session(collaborator_id, session_id)
        if not row:
            return
        self._sessions.pop(session_id, None)
        self._messages.pop(session_id, None)

    def add_message(
        self,
        collaborator_id: str,
        session_id: int,
        role: str,
        content: str,
        meta: dict | None = None,
    ) -> None:
        if not self.get_session(collaborator_id, session_id):
            raise ValueError("Sesion no encontrada")

        row = {
            "id": self._next_message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "meta": meta or {},
            "created_at": "2026-01-01 00:00:00",
        }
        self._next_message_id += 1
        self._messages[session_id].append(row)

    def list_messages(self, collaborator_id: str, session_id: int) -> list[dict]:
        if not self.get_session(collaborator_id, session_id):
            return []
        return self._messages.get(session_id, [])


@pytest.fixture(autouse=True)
def _reset_security_state() -> Generator[None, None, None]:
    security._rate_limit_hits.clear()
    security._allowed_keys.cache_clear()
    yield
    security._rate_limit_hits.clear()
    security._allowed_keys.cache_clear()


@pytest.fixture(autouse=True)
def _settings_guard() -> Generator[None, None, None]:
    fields = [
        "APP_ENV",
        "API_KEY_ENABLED",
        "API_KEYS",
        "ADMIN_PANEL_PASSWORD",
        "RATE_LIMIT_ENABLED",
        "RATE_LIMIT_REQUESTS_PER_MINUTE",
        "RATE_LIMIT_WINDOW_SECONDS",
    ]
    snapshot = {field: getattr(settings, field) for field in fields}
    yield
    for field, value in snapshot.items():
        setattr(settings, field, value)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import app.api.routes.collab as collab_routes
    import app.api.routes.public as public_routes
    from app.main import app

    rag = _StubRag()
    chat_store = _StubChatStore()

    monkeypatch.setattr(collab_routes, "rag", rag)
    monkeypatch.setattr(collab_routes, "chat_store", chat_store)
    monkeypatch.setattr(public_routes, "rag", rag)

    return TestClient(app)


def test_chats_requires_api_key_when_enabled(client: TestClient) -> None:
    settings.API_KEY_ENABLED = True
    settings.API_KEYS = "demo-key"
    security._allowed_keys.cache_clear()

    res = client.get("/chats")
    assert res.status_code == 401
    assert "API key" in res.json()["detail"]


def test_admin_requires_password_when_not_configured(client: TestClient) -> None:
    settings.ADMIN_PANEL_PASSWORD = ""
    res = client.get("/admin/keys")
    assert res.status_code == 503


def test_admin_rejects_invalid_password(client: TestClient) -> None:
    settings.ADMIN_PANEL_PASSWORD = "top-secret"
    res = client.get("/admin/keys", headers={"X-Admin-Password": "bad"})
    assert res.status_code == 401


def test_ask_creates_session_and_messages(client: TestClient) -> None:
    settings.API_KEY_ENABLED = True
    settings.API_KEYS = "demo-key"
    security._allowed_keys.cache_clear()

    payload = {
        "question": "Hola",
        "collection": "default",
        "top_k": 1,
        "stream": False,
    }
    headers = {"X-API-Key": "demo-key"}

    ask_res = client.post("/ask", json=payload, headers=headers)
    assert ask_res.status_code == 200
    ask_data = ask_res.json()
    assert ask_data["answer"].startswith("Echo:")
    assert ask_data["session_id"] == 1

    chats_res = client.get("/chats", headers=headers)
    assert chats_res.status_code == 200
    assert len(chats_res.json()) == 1

    msgs_res = client.get("/chats/1/messages", headers=headers)
    assert msgs_res.status_code == 200
    msgs = msgs_res.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_ingest_rate_limit_returns_429_after_threshold(client: TestClient) -> None:
    settings.API_KEY_ENABLED = False
    settings.RATE_LIMIT_ENABLED = True
    settings.RATE_LIMIT_REQUESTS_PER_MINUTE = 2
    settings.RATE_LIMIT_WINDOW_SECONDS = 60
    security._rate_limit_hits.clear()

    payload = {"text": "hola", "collection": "default"}

    r1 = client.post("/ingest", json=payload)
    r2 = client.post("/ingest", json=payload)
    r3 = client.post("/ingest", json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429