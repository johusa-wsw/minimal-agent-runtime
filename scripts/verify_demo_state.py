from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify demo session isolation using only "
            "non-sensitive aggregate database queries."
        )
    )
    parser.add_argument(
        "database_path",
        type=Path,
    )
    return parser.parse_args()


def scalar(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[str, ...],
) -> int:
    row = connection.execute(
        query,
        parameters,
    ).fetchone()

    if row is None:
        raise AssertionError(
            "Aggregate query returned no row."
        )

    return int(row[0])


def main() -> int:
    args = parse_args()

    with sqlite3.connect(
        args.database_path
    ) as connection:
        message_query = """
            SELECT COUNT(*)
            FROM messages
            WHERE user_id = ?
              AND session_id = ?
        """
        todo_query = """
            SELECT COUNT(*)
            FROM todos
            WHERE user_id = ?
              AND session_id = ?
        """

        window_1_messages = scalar(
            connection,
            message_query,
            ("demo-user", "demo-window-1"),
        )
        window_2_messages = scalar(
            connection,
            message_query,
            ("demo-user", "demo-window-2"),
        )
        window_1_todos = scalar(
            connection,
            todo_query,
            ("demo-user", "demo-window-1"),
        )
        window_2_todos = scalar(
            connection,
            todo_query,
            ("demo-user", "demo-window-2"),
        )
        expected_todo = scalar(
            connection,
            """
                SELECT COUNT(*)
                FROM todos
                WHERE user_id = ?
                  AND session_id = ?
                  AND content LIKE ?
                  AND content LIKE ?
            """,
            (
                "demo-user",
                "demo-window-1",
                "%238%",
                "%4046%",
            ),
        )

    assert window_1_messages > 0
    assert window_2_messages > 0
    assert window_1_todos >= 1
    assert window_2_todos == 0
    assert expected_todo >= 1

    print("SQLite verification: PASS")
    print(
        "demo-window-1: "
        f"messages={window_1_messages}, "
        f"todos={window_1_todos}"
    )
    print(
        "demo-window-2: "
        f"messages={window_2_messages}, "
        f"todos={window_2_todos}"
    )
    print(
        "Only non-sensitive aggregate counts "
        "were displayed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
