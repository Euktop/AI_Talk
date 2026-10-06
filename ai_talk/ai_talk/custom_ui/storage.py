"""SQLite-хранилище запросов и клиентов."""
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ai_talk.custom_ui.models import Client, Request


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    """Потокобезопасное хранилище на SQLite.

    Каждый вызов открывает новое соединение — избегаем проблем
    с shared connection между потоками Flask.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY,
                    system_prompt TEXT NOT NULL DEFAULT '',
                    user_prompt TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    answer TEXT,
                    answered_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY,
                    registered_at TEXT NOT NULL
                )
                """
            )

    # -------- requests --------

    def create_request(self, system_prompt: str, user_prompt: str) -> Request:
        rid = str(uuid.uuid4())
        now = _utcnow_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO requests (id, system_prompt, user_prompt, created_at)"
                " VALUES (?, ?, ?, ?)",
                (rid, system_prompt, user_prompt, now),
            )
        result = self.get_request(rid)
        assert result is not None
        return result

    def get_request(self, request_id: str) -> Optional[Request]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM requests WHERE id = ?", (request_id,)
            ).fetchone()
        return self._row_to_request(row) if row else None

    def list_requests(self) -> List[Request]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM requests ORDER BY created_at ASC"
            ).fetchall()
        return [self._row_to_request(r) for r in rows]

    def answer_request(self, request_id: str, answer: str) -> bool:
        """Сохраняет ответ. Пустой ответ отвергается. Повторный — отвергается."""
        if not answer or not answer.strip():
            return False
        now = _utcnow_iso()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE requests SET answer = ?, answered_at = ?"
                " WHERE id = ? AND answer IS NULL",
                (answer, now, request_id),
            )
        return cur.rowcount > 0

    def delete_request(self, request_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM requests WHERE id = ?", (request_id,))
        return cur.rowcount > 0

    def count_requests(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM requests").fetchone()
        return int(row["n"])

    # -------- clients --------

    def register_client(self, client_id: str) -> None:
        now = _utcnow_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO clients (id, registered_at) VALUES (?, ?)",
                (client_id, now),
            )

    def unregister_client(self, client_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))

    def list_clients(self) -> List[Client]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM clients ORDER BY registered_at ASC"
            ).fetchall()
        return [
            Client(
                id=r["id"],
                registered_at=datetime.fromisoformat(r["registered_at"]),
            )
            for r in rows
        ]

    def count_clients(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM clients").fetchone()
        return int(row["n"])

    # -------- internals --------

    def _row_to_request(self, row: sqlite3.Row) -> Request:
        return Request(
            id=row["id"],
            system_prompt=row["system_prompt"],
            user_prompt=row["user_prompt"],
            created_at=datetime.fromisoformat(row["created_at"]),
            answer=row["answer"],
            answered_at=(
                datetime.fromisoformat(row["answered_at"])
                if row["answered_at"]
                else None
            ),
        )
