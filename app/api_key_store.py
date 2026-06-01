"""
api_key_store.py - Gestion de API keys para colaboradores.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
from pathlib import Path
from typing import Any

DB_PATH = Path("/app/data/chat_history.db")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ApiKeyStore:
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
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    key_prefix TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_used_at TEXT,
                    use_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_api_keys_active
                ON api_keys(is_active)
                """
            )

    def create_key(self, name: str, prefix: str = "colab_") -> dict[str, Any]:
        token = prefix + secrets.token_urlsafe(24)
        key_hash = sha256_text(token)
        key_prefix = token[:14]

        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO api_keys(name, key_hash, key_prefix, is_active)
                VALUES (?, ?, ?, 1)
                """,
                (name.strip() or "Sin nombre", key_hash, key_prefix),
            )
            key_id = cur.lastrowid
            row = conn.execute(
                """
                SELECT id, name, key_prefix, is_active, created_at, last_used_at, use_count
                FROM api_keys
                WHERE id = ?
                """,
                (key_id,),
            ).fetchone()

        data = dict(row)
        data["api_key"] = token
        return data

    def list_keys(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, key_prefix, is_active, created_at, last_used_at, use_count
                FROM api_keys
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def deactivate_key(self, key_id: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE api_keys
                SET is_active = 0
                WHERE id = ?
                """,
                (key_id,),
            )
            return cur.rowcount > 0

    def validate_key(self, candidate: str) -> dict[str, Any] | None:
        candidate_hash = sha256_text(candidate)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, key_prefix, is_active, created_at, last_used_at, use_count
                FROM api_keys
                WHERE key_hash = ? AND is_active = 1
                """,
                (candidate_hash,),
            ).fetchone()
            return dict(row) if row else None

    def register_use(self, key_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE api_keys
                SET use_count = use_count + 1,
                    last_used_at = datetime('now')
                WHERE id = ?
                """,
                (key_id,),
            )
