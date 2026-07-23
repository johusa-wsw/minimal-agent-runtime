import json
from pathlib import Path

from minimal_agent.llm.fake import (
    FakeLLMClient,
)
from minimal_agent.runtime.agent import (
    AgentRuntime,
)
from minimal_agent.session.store import (
    SessionStore,
)
from minimal_agent.tools.factory import (
    build_default_registry,
)


def build_agent(
    tmp_path: Path,
    llm: FakeLLMClient,
    store: SessionStore,
) -> AgentRuntime:
    registry = build_default_registry(
        database_path=tmp_path / "agent.db",
        search_data_path=(
            Path("data") / "mock_search.json"
        ),
    )

    return AgentRuntime(
        llm=llm,
        registry=registry,
        session_store=store,
    )


def test_follow_up_receives_previous_history(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "agent.db"

    store = SessionStore(database_path)

    first_llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "final",
                    "reason": "已经记住名字",
                    "answer": "好的，我记住你叫小明。",
                },
                ensure_ascii=False,
            )
        ]
    )

    first_agent = build_agent(
        tmp_path=tmp_path,
        llm=first_llm,
        store=store,
    )

    first_agent.run(
        user_input="我叫小明，请记住。",
        user_id="user-a",
        session_id="window-1",
    )

    second_llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "final",
                    "reason": "历史中包含用户名",
                    "answer": "你叫小明。",
                },
                ensure_ascii=False,
            )
        ]
    )

    # 创建新的 Agent，模拟程序重启后继续聊天。
    second_agent = build_agent(
        tmp_path=tmp_path,
        llm=second_llm,
        store=SessionStore(database_path),
    )

    result = second_agent.run(
        user_input="我叫什么？",
        user_id="user-a",
        session_id="window-1",
    )

    assert result.answer == "你叫小明。"

    messages = second_llm.calls[0][
        "messages"
    ]

    contents = [
        message.content
        for message in messages
    ]

    assert "我叫小明，请记住。" in contents
    assert "好的，我记住你叫小明。" in contents
    assert "我叫什么？" in contents


def test_other_session_does_not_receive_history(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "agent.db"
    store = SessionStore(database_path)

    first_llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "final",
                    "reason": "完成",
                    "answer": "窗口一回答",
                },
                ensure_ascii=False,
            )
        ]
    )

    first_agent = build_agent(
        tmp_path=tmp_path,
        llm=first_llm,
        store=store,
    )

    first_agent.run(
        user_input="这是窗口一的秘密",
        user_id="user-a",
        session_id="window-1",
    )

    second_llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "final",
                    "reason": "没有相关历史",
                    "answer": "我不知道。",
                },
                ensure_ascii=False,
            )
        ]
    )

    second_agent = build_agent(
        tmp_path=tmp_path,
        llm=second_llm,
        store=store,
    )

    second_agent.run(
        user_input="窗口一说了什么？",
        user_id="user-a",
        session_id="window-2",
    )

    messages = second_llm.calls[0][
        "messages"
    ]

    assert not any(
        "窗口一的秘密" in message.content
        for message in messages
    )


def test_tool_result_is_saved_in_session(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "agent.db"
    store = SessionStore(database_path)

    llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "tool_call",
                    "reason": "需要计算",
                    "tool_name": "calculator",
                    "arguments": {
                        "expression": "8 * 8"
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "type": "final",
                    "reason": "已经得到结果",
                    "answer": "8 × 8 等于 64。",
                },
                ensure_ascii=False,
            ),
        ]
    )

    agent = build_agent(
        tmp_path=tmp_path,
        llm=llm,
        store=store,
    )

    agent.run(
        user_input="8乘8是多少？",
        user_id="user-a",
        session_id="window-1",
    )

    messages = store.load_messages(
        user_id="user-a",
        session_id="window-1",
    )

    roles = [
        message.role
        for message in messages
    ]

    assert roles == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]

    assert any(
        message.role == "tool"
        and '"value": 64' in message.content
        for message in messages
    )