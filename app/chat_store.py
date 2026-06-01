"""
chat_store.py - Persistencia simple de sesiones y mensajes de chat por colaborador.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

DB_PATH = Path("/app/data/chat_history.db")


class ChatStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collaborator_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    meta_json TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_collaborator
                ON chat_sessions(collaborator_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON chat_messages(session_id)
                """
            )

    def create_session(self, collaborator_id: str, title: str) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO chat_sessions(collaborator_id, title)
                VALUES(?, ?)
                """,
                (collaborator_id, title.strip() or "Nuevo chat"),
            )
            session_id = cur.lastrowid
            row = conn.execute(
                """
                SELECT id, collaborator_id, title, created_at, updated_at
                FROM chat_sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
            return dict(row)

    def list_sessions(self, collaborator_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, collaborator_id, title, created_at, updated_at
                FROM chat_sessions
                WHERE collaborator_id = ?
                ORDER BY updated_at DESC, id DESC
                """,
                (collaborator_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_session(self, collaborator_id: str, session_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, collaborator_id, title, created_at, updated_at
                FROM chat_sessions
                WHERE collaborator_id = ? AND id = ?
                """,
                (collaborator_id, session_id),
            ).fetchone()
            return dict(row) if row else None

    def rename_session(self, collaborator_id: str, session_id: int, title: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE chat_sessions
                SET title = ?, updated_at = datetime('now')
                WHERE collaborator_id = ? AND id = ?
                """,
                (title.strip() or "Nuevo chat", collaborator_id, session_id),
            )

    def delete_session(self, collaborator_id: str, session_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                DELETE FROM chat_sessions
                WHERE collaborator_id = ? AND id = ?
                """,
                (collaborator_id, session_id),
            )

    def add_message(
        self,
        collaborator_id: str,
        session_id: int,
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM chat_sessions
                WHERE collaborator_id = ? AND id = ?
                """,
                (collaborator_id, session_id),
            ).fetchone()
            if not row:
                raise ValueError("Sesion no encontrada para el colaborador.")

            meta_json = json.dumps(meta or {}, ensure_ascii=True)
            conn.execute(
                """
                INSERT INTO chat_messages(session_id, role, content, meta_json)
                VALUES(?, ?, ?, ?)
                """,
                (session_id, role, content, meta_json),
            )
            conn.execute(
                """
                UPDATE chat_sessions
                SET updated_at = datetime('now')
                WHERE id = ?
                """,
                (session_id,),
            )

    def list_messages(self, collaborator_id: str, session_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            owner = conn.execute(
                """
                SELECT id FROM chat_sessions
                WHERE collaborator_id = ? AND id = ?
                """,
                (collaborator_id, session_id),
            ).fetchone()
            if not owner:
                return []

            rows = conn.execute(
                """
                SELECT id, session_id, role, content, meta_json, created_at
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()

            out: list[dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                try:
                    item["meta"] = json.loads(item.pop("meta_json") or "{}")
                except json.JSONDecodeError:
                    item["meta"] = {}
                    item.pop("meta_json", None)
                out.append(item)
            return out
