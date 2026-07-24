import json
from pathlib import Path

from minimal_agent.context.manager import (
    ContextManager,
)
from minimal_agent.llm.fake import (
    FakeLLMClient,
)
from minimal_agent.runtime.agent import (
    AgentRuntime,
)
from minimal_agent.runtime.models import (
    ChatMessage,
)
from minimal_agent.session.store import (
    SessionStore,
)
from minimal_agent.tools.factory import (
    build_default_registry,
)


def test_agent_receives_compressed_summary(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "agent.db"

    store = SessionStore(database_path)

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
                    f"历史对话 {index}："
                    + "Agent Runtime 项目进展。"
                    * 8
                ),
            ),
        )

    context_manager = ContextManager(
        session_store=store,
        max_context_tokens=180,
        recent_token_ratio=0.5,
        max_recent_messages=4,
        min_recent_messages=2,
    )

    llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "final",
                    "reason": "已参考历史摘要",
                    "answer": "我们继续实现项目。",
                },
                ensure_ascii=False,
            )
        ]
    )

    registry = build_default_registry(
        database_path=database_path,
        search_data_path=(
            Path("data")
            / "mock_search.json"
        ),
    )

    agent = AgentRuntime(
        llm=llm,
        registry=registry,
        session_store=store,
        context_manager=context_manager,
    )

    result = agent.run(
        user_input="继续刚才的项目",
        user_id="user-a",
        session_id="window-1",
    )

    assert result.answer == (
        "我们继续实现项目。"
    )

    sent_messages = llm.calls[0][
        "messages"
    ]

    summary_messages = [
        message
        for message in sent_messages
        if (
            message.role == "system"
            and "压缩摘要"
            in message.content
        )
    ]

    assert len(summary_messages) == 1

    assert any(
        message.role == "user"
        and message.content
        == "继续刚才的项目"
        for message in sent_messages
    )