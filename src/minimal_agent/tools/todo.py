from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from minimal_agent.tools.base import (
    BaseTool,
    ToolArguments,
    ToolContext,
    ToolExecutionError,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TodoItem(BaseModel):
    id: int
    user_id: str
    session_id: str
    content: str
    completed: bool
    created_at: str
    updated_at: str


class TodoRepository:
    """负责 Todo 数据的 SQLite 持久化。"""

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

        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_todos_session
                ON todos (
                    user_id,
                    session_id,
                    id
                )
                """
            )

    def add(
        self,
        user_id: str,
        session_id: str,
        content: str,
    ) -> TodoItem:
        now = utc_now()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO todos (
                    user_id,
                    session_id,
                    content,
                    completed,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (
                    user_id,
                    session_id,
                    content,
                    now,
                    now,
                ),
            )

            todo_id = cursor.lastrowid

        if todo_id is None:
            raise ToolExecutionError(
                "Failed to create todo"
            )

        item = self.get(
            user_id=user_id,
            session_id=session_id,
            todo_id=todo_id,
        )

        if item is None:
            raise ToolExecutionError(
                "Created todo could not be loaded"
            )

        return item

    def list_items(
        self,
        user_id: str,
        session_id: str,
        include_completed: bool = False,
    ) -> list[TodoItem]:
        query = """
            SELECT
                id,
                user_id,
                session_id,
                content,
                completed,
                created_at,
                updated_at
            FROM todos
            WHERE user_id = ?
              AND session_id = ?
        """

        parameters: list[Any] = [
            user_id,
            session_id,
        ]

        if not include_completed:
            query += " AND completed = 0"

        query += " ORDER BY id ASC"

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [
            self._row_to_item(row)
            for row in rows
        ]

    def get(
        self,
        user_id: str,
        session_id: str,
        todo_id: int,
    ) -> TodoItem | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    session_id,
                    content,
                    completed,
                    created_at,
                    updated_at
                FROM todos
                WHERE id = ?
                  AND user_id = ?
                  AND session_id = ?
                """,
                (
                    todo_id,
                    user_id,
                    session_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_item(row)

    def complete(
        self,
        user_id: str,
        session_id: str,
        todo_id: int,
    ) -> TodoItem | None:
        now = utc_now()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE todos
                SET completed = 1,
                    updated_at = ?
                WHERE id = ?
                  AND user_id = ?
                  AND session_id = ?
                """,
                (
                    now,
                    todo_id,
                    user_id,
                    session_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

        return self.get(
            user_id=user_id,
            session_id=session_id,
            todo_id=todo_id,
        )

    def delete(
        self,
        user_id: str,
        session_id: str,
        todo_id: int,
    ) -> TodoItem | None:
        item = self.get(
            user_id=user_id,
            session_id=session_id,
            todo_id=todo_id,
        )

        if item is None:
            return None

        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM todos
                WHERE id = ?
                  AND user_id = ?
                  AND session_id = ?
                """,
                (
                    todo_id,
                    user_id,
                    session_id,
                ),
            )

        return item

    @staticmethod
    def _row_to_item(
        row: sqlite3.Row,
    ) -> TodoItem:
        return TodoItem(
            id=row["id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            content=row["content"],
            completed=bool(row["completed"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class TodoArguments(ToolArguments):
    action: Literal[
        "add",
        "list",
        "complete",
        "delete",
    ] = Field(
        description=(
            "待办操作：add、list、complete 或 delete"
        )
    )

    content: str | None = Field(
        default=None,
        max_length=500,
        description="新增待办时的待办内容",
    )

    todo_id: int | None = Field(
        default=None,
        ge=1,
        description="完成或删除待办时的待办 ID",
    )

    include_completed: bool = Field(
        default=False,
        description="list 时是否包含已完成待办",
    )

    @model_validator(mode="after")
    def validate_action_fields(
        self,
    ) -> "TodoArguments":
        if self.action == "add":
            if (
                self.content is None
                or not self.content.strip()
            ):
                raise ValueError(
                    "content is required for add"
                )

            if self.todo_id is not None:
                raise ValueError(
                    "todo_id is not allowed for add"
                )

            self.content = self.content.strip()

        elif self.action in {
            "complete",
            "delete",
        }:
            if self.todo_id is None:
                raise ValueError(
                    f"todo_id is required for "
                    f"{self.action}"
                )

            if self.content is not None:
                raise ValueError(
                    f"content is not allowed for "
                    f"{self.action}"
                )

        elif self.action == "list":
            if self.content is not None:
                raise ValueError(
                    "content is not allowed for list"
                )

            if self.todo_id is not None:
                raise ValueError(
                    "todo_id is not allowed for list"
                )

        return self


class TodoTool(BaseTool):
    name = "todo"

    description = (
        "管理当前聊天窗口的待办事项。"
        "支持新增、查看、完成和删除待办。"
        "不同用户和不同 session 的待办彼此隔离。"
    )

    args_model = TodoArguments

    def __init__(
        self,
        repository: TodoRepository,
    ) -> None:
        self._repository = repository

    def run(
        self,
        arguments: ToolArguments,
        context: ToolContext | None = None,
    ) -> dict[str, Any]:
        if not isinstance(arguments, TodoArguments):
            raise TypeError(
                "TodoTool received invalid argument type"
            )

        if context is None:
            raise ToolExecutionError(
                "Todo tool requires user and session context"
            )

        if arguments.action == "add":
            assert arguments.content is not None

            item = self._repository.add(
                user_id=context.user_id,
                session_id=context.session_id,
                content=arguments.content,
            )

            return {
                "action": "add",
                "item": item.model_dump(
                    mode="json"
                ),
            }

        if arguments.action == "list":
            items = self._repository.list_items(
                user_id=context.user_id,
                session_id=context.session_id,
                include_completed=(
                    arguments.include_completed
                ),
            )

            return {
                "action": "list",
                "count": len(items),
                "items": [
                    item.model_dump(mode="json")
                    for item in items
                ],
            }

        if arguments.action == "complete":
            assert arguments.todo_id is not None

            item = self._repository.complete(
                user_id=context.user_id,
                session_id=context.session_id,
                todo_id=arguments.todo_id,
            )

            if item is None:
                raise ToolExecutionError(
                    "Todo not found in current session"
                )

            return {
                "action": "complete",
                "item": item.model_dump(
                    mode="json"
                ),
            }

        if arguments.action == "delete":
            assert arguments.todo_id is not None

            item = self._repository.delete(
                user_id=context.user_id,
                session_id=context.session_id,
                todo_id=arguments.todo_id,
            )

            if item is None:
                raise ToolExecutionError(
                    "Todo not found in current session"
                )

            return {
                "action": "delete",
                "item": item.model_dump(
                    mode="json"
                ),
            }

        raise ToolExecutionError(
            f"Unsupported todo action: "
            f"{arguments.action}"
        )