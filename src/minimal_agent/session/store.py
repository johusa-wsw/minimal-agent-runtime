from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from minimal_agent.runtime.models import ChatMessage


def utc_now() -> str:
    """返回 UTC ISO 8601 时间。"""

    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    """使用 SQLite 保存 Session 和聊天消息。"""

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path
        )

        connection.row_factory = sqlite3.Row
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (
                        user_id,
                        session_id
                    )
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    name TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (
                        user_id,
                        session_id
                    )
                    REFERENCES sessions (
                        user_id,
                        session_id
                    )
                    ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_messages_session
                ON messages (
                    user_id,
                    session_id,
                    id
                )
                """
            )

    def ensure_session(
        self,
        user_id: str,
        session_id: str,
    ) -> None:
        """确保 Session 已存在。"""

        self._validate_identity(
            user_id=user_id,
            session_id=session_id,
        )

        now = utc_now()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sessions (
                    user_id,
                    session_id,
                    summary,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, '', ?, ?)
                """,
                (
                    user_id,
                    session_id,
                    now,
                    now,
                ),
            )

    def append_message(
        self,
        user_id: str,
        session_id: str,
        message: ChatMessage,
    ) -> None:
        """向指定 Session 添加一条消息。"""

        self.append_messages(
            user_id=user_id,
            session_id=session_id,
            messages=[message],
        )

    def append_messages(
        self,
        user_id: str,
        session_id: str,
        messages: Iterable[ChatMessage],
    ) -> None:
        """一次写入多条消息。"""

        self._validate_identity(
            user_id=user_id,
            session_id=session_id,
        )

        message_list = list(messages)

        if not message_list:
            return

        now = utc_now()

        with self._connect() as connection:
            self._ensure_session_on_connection(
                connection=connection,
                user_id=user_id,
                session_id=session_id,
                now=now,
            )

            connection.executemany(
                """
                INSERT INTO messages (
                    user_id,
                    session_id,
                    role,
                    content,
                    name,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        user_id,
                        session_id,
                        message.role,
                        message.content,
                        message.name,
                        now,
                    )
                    for message in message_list
                ],
            )

            connection.execute(
                """
                UPDATE sessions
                SET updated_at = ?
                WHERE user_id = ?
                  AND session_id = ?
                """,
                (
                    now,
                    user_id,
                    session_id,
                ),
            )

    def load_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int | None = None,
    ) -> list[ChatMessage]:
        """读取 Session 消息，并保持原始时间顺序。"""

        self._validate_identity(
            user_id=user_id,
            session_id=session_id,
        )

        if limit is not None and limit < 1:
            raise ValueError(
                "limit must be at least 1"
            )

        with self._connect() as connection:
            if limit is None:
                rows = connection.execute(
                    """
                    SELECT
                        role,
                        content,
                        name
                    FROM messages
                    WHERE user_id = ?
                      AND session_id = ?
                    ORDER BY id ASC
                    """,
                    (
                        user_id,
                        session_id,
                    ),
                ).fetchall()

            else:
                # 先取最后 N 条，再恢复为正序。
                rows = connection.execute(
                    """
                    SELECT
                        role,
                        content,
                        name
                    FROM messages
                    WHERE user_id = ?
                      AND session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (
                        user_id,
                        session_id,
                        limit,
                    ),
                ).fetchall()

                rows = list(reversed(rows))

        return [
            ChatMessage(
                role=row["role"],
                content=row["content"],
                name=row["name"],
            )
            for row in rows
        ]

    def count_messages(
        self,
        user_id: str,
        session_id: str,
    ) -> int:
        self._validate_identity(
            user_id=user_id,
            session_id=session_id,
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS message_count
                FROM messages
                WHERE user_id = ?
                  AND session_id = ?
                """,
                (
                    user_id,
                    session_id,
                ),
            ).fetchone()

        if row is None:
            return 0

        return int(row["message_count"])

    def clear_session(
        self,
        user_id: str,
        session_id: str,
    ) -> bool:
        """删除指定 Session 及其消息。"""

        self._validate_identity(
            user_id=user_id,
            session_id=session_id,
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM sessions
                WHERE user_id = ?
                  AND session_id = ?
                """,
                (
                    user_id,
                    session_id,
                ),
            )

        return cursor.rowcount > 0

    def get_summary(
        self,
        user_id: str,
        session_id: str,
    ) -> str:
        self._validate_identity(
            user_id=user_id,
            session_id=session_id,
        )

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT summary
                FROM sessions
                WHERE user_id = ?
                  AND session_id = ?
                """,
                (
                    user_id,
                    session_id,
                ),
            ).fetchone()

        if row is None:
            return ""

        return str(row["summary"])

    def update_summary(
        self,
        user_id: str,
        session_id: str,
        summary: str,
    ) -> None:
        """保存 Session 摘要，后续 Context 压缩会使用。"""

        self._validate_identity(
            user_id=user_id,
            session_id=session_id,
        )

        now = utc_now()

        with self._connect() as connection:
            self._ensure_session_on_connection(
                connection=connection,
                user_id=user_id,
                session_id=session_id,
                now=now,
            )

            connection.execute(
                """
                UPDATE sessions
                SET summary = ?,
                    updated_at = ?
                WHERE user_id = ?
                  AND session_id = ?
                """,
                (
                    summary.strip(),
                    now,
                    user_id,
                    session_id,
                ),
            )

    @staticmethod
    def _ensure_session_on_connection(
        connection: sqlite3.Connection,
        user_id: str,
        session_id: str,
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO sessions (
                user_id,
                session_id,
                summary,
                created_at,
                updated_at
            )
            VALUES (?, ?, '', ?, ?)
            """,
            (
                user_id,
                session_id,
                now,
                now,
            ),
        )

    @staticmethod
    def _validate_identity(
        user_id: str,
        session_id: str,
    ) -> None:
        if not user_id.strip():
            raise ValueError(
                "user_id cannot be empty"
            )

        if not session_id.strip():
            raise ValueError(
                "session_id cannot be empty"
            )