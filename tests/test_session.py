from pathlib import Path

from minimal_agent.runtime.models import (
    ChatMessage,
)
from minimal_agent.session.store import (
    SessionStore,
)


def test_session_store_persists_messages(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "agent.db"

    store = SessionStore(database_path)

    store.append_messages(
        user_id="user-a",
        session_id="window-1",
        messages=[
            ChatMessage(
                role="user",
                content="你好",
            ),
            ChatMessage(
                role="assistant",
                content="你好，有什么可以帮助你？",
            ),
        ],
    )

    # 使用新的 Store 实例模拟程序重启。
    reopened_store = SessionStore(
        database_path
    )

    messages = reopened_store.load_messages(
        user_id="user-a",
        session_id="window-1",
    )

    assert len(messages) == 2
    assert messages[0].content == "你好"
    assert (
        messages[1].content
        == "你好，有什么可以帮助你？"
    )


def test_sessions_are_isolated(
    tmp_path: Path,
) -> None:
    store = SessionStore(
        tmp_path / "agent.db"
    )

    store.append_message(
        user_id="user-a",
        session_id="window-1",
        message=ChatMessage(
            role="user",
            content="窗口一消息",
        ),
    )

    store.append_message(
        user_id="user-a",
        session_id="window-2",
        message=ChatMessage(
            role="user",
            content="窗口二消息",
        ),
    )

    window_1 = store.load_messages(
        user_id="user-a",
        session_id="window-1",
    )

    window_2 = store.load_messages(
        user_id="user-a",
        session_id="window-2",
    )

    assert [
        message.content
        for message in window_1
    ] == ["窗口一消息"]

    assert [
        message.content
        for message in window_2
    ] == ["窗口二消息"]


def test_users_are_isolated(
    tmp_path: Path,
) -> None:
    store = SessionStore(
        tmp_path / "agent.db"
    )

    store.append_message(
        user_id="user-a",
        session_id="window-1",
        message=ChatMessage(
            role="user",
            content="用户 A 消息",
        ),
    )

    messages = store.load_messages(
        user_id="user-b",
        session_id="window-1",
    )

    assert messages == []


def test_load_messages_respects_limit(
    tmp_path: Path,
) -> None:
    store = SessionStore(
        tmp_path / "agent.db"
    )

    for index in range(5):
        store.append_message(
            user_id="user-a",
            session_id="window-1",
            message=ChatMessage(
                role="user",
                content=f"消息 {index}",
            ),
        )

    messages = store.load_messages(
        user_id="user-a",
        session_id="window-1",
        limit=2,
    )

    assert [
        message.content
        for message in messages
    ] == [
        "消息 3",
        "消息 4",
    ]


def test_clear_session_removes_messages(
    tmp_path: Path,
) -> None:
    store = SessionStore(
        tmp_path / "agent.db"
    )

    store.append_message(
        user_id="user-a",
        session_id="window-1",
        message=ChatMessage(
            role="user",
            content="需要删除的消息",
        ),
    )

    removed = store.clear_session(
        user_id="user-a",
        session_id="window-1",
    )

    assert removed is True

    assert store.load_messages(
        user_id="user-a",
        session_id="window-1",
    ) == []


def test_summary_can_be_saved(
    tmp_path: Path,
) -> None:
    store = SessionStore(
        tmp_path / "agent.db"
    )

    store.update_summary(
        user_id="user-a",
        session_id="window-1",
        summary="用户正在开发 Agent Runtime。",
    )

    summary = store.get_summary(
        user_id="user-a",
        session_id="window-1",
    )

    assert summary == (
        "用户正在开发 Agent Runtime。"
    )