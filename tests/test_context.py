from pathlib import Path

from minimal_agent.context.manager import (
    ContextManager,
    TokenEstimator,
)
from minimal_agent.runtime.models import (
    ChatMessage,
)
from minimal_agent.session.store import (
    SessionStore,
)


def test_token_estimator_handles_text() -> None:
    estimator = TokenEstimator()

    english_tokens = estimator.estimate_text(
        "This is a simple English sentence."
    )

    chinese_tokens = estimator.estimate_text(
        "这是一个中文句子。"
    )

    assert english_tokens > 0
    assert chinese_tokens > 0


def test_context_under_budget_is_not_compressed(
    tmp_path: Path,
) -> None:
    store = SessionStore(
        tmp_path / "agent.db"
    )

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

    manager = ContextManager(
        session_store=store,
        max_context_tokens=500,
    )

    result = manager.build_context(
        user_id="user-a",
        session_id="window-1",
    )

    assert result.compressed is False
    assert result.removed_messages == 0
    assert len(result.messages) == 2

    assert store.count_messages(
        user_id="user-a",
        session_id="window-1",
    ) == 2


def test_context_compresses_old_messages(
    tmp_path: Path,
) -> None:
    store = SessionStore(
        tmp_path / "agent.db"
    )

    for index in range(12):
        store.append_message(
            user_id="user-a",
            session_id="window-1",
            message=ChatMessage(
                role=(
                    "user"
                    if index % 2 == 0
                    else "assistant"
                ),
                content=(
                    f"第 {index} 条消息："
                    + "这是一段用于触发上下文压缩的内容。"
                    * 5
                ),
            ),
        )

    manager = ContextManager(
        session_store=store,
        max_context_tokens=180,
        recent_token_ratio=0.5,
        max_recent_messages=4,
        min_recent_messages=2,
        max_message_chars=300,
    )

    result = manager.build_context(
        user_id="user-a",
        session_id="window-1",
    )

    assert result.compressed is True
    assert result.removed_messages > 0
    assert result.retained_messages <= 4

    summary = store.get_summary(
        user_id="user-a",
        session_id="window-1",
    )

    assert summary
    assert "用户" in summary or "Agent" in summary

    remaining = store.load_messages(
        user_id="user-a",
        session_id="window-1",
    )

    assert len(remaining) <= 4

    # Context 第一条消息应当是历史摘要。
    assert result.messages[0].role == "system"
    assert "压缩摘要" in (
        result.messages[0].content
    )


def test_recent_messages_are_preserved(
    tmp_path: Path,
) -> None:
    store = SessionStore(
        tmp_path / "agent.db"
    )

    for index in range(10):
        store.append_message(
            user_id="user-a",
            session_id="window-1",
            message=ChatMessage(
                role="user",
                content=(
                    f"历史消息 {index} "
                    + "内容" * 30
                ),
            ),
        )

    manager = ContextManager(
        session_store=store,
        max_context_tokens=120,
        recent_token_ratio=0.6,
        max_recent_messages=3,
        min_recent_messages=2,
    )

    result = manager.build_context(
        user_id="user-a",
        session_id="window-1",
    )

    contents = [
        message.content
        for message in result.messages
    ]

    assert any(
        "历史消息 9" in content
        for content in contents
    )

    assert any(
        "历史消息 8" in content
        for content in contents
    )


def test_existing_summary_is_injected(
    tmp_path: Path,
) -> None:
    store = SessionStore(
        tmp_path / "agent.db"
    )

    store.update_summary(
        user_id="user-a",
        session_id="window-1",
        summary=(
            "用户正在开发一个最小 Agent。"
        ),
    )

    store.append_message(
        user_id="user-a",
        session_id="window-1",
        message=ChatMessage(
            role="user",
            content="接下来实现什么？",
        ),
    )

    manager = ContextManager(
        session_store=store,
        max_context_tokens=500,
    )

    result = manager.build_context(
        user_id="user-a",
        session_id="window-1",
    )

    assert result.messages[0].role == "system"

    assert (
        "用户正在开发一个最小 Agent"
        in result.messages[0].content
    )