import json
from pathlib import Path

import pytest

from minimal_agent.llm.fake import (
    FakeLLMClient,
)
from minimal_agent.runtime.agent import (
    AgentRuntime,
    MaxStepsExceededError,
)
from minimal_agent.tools.factory import (
    build_default_registry,
)


@pytest.fixture
def registry(tmp_path: Path):
    return build_default_registry(
        database_path=tmp_path / "agent.db",
        search_data_path=(
            Path("data") / "mock_search.json"
        ),
    )


def test_agent_can_answer_directly(
    registry,
) -> None:
    llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "final",
                    "reason": "无需工具",
                    "answer": "你好，我是 Agent。",
                },
                ensure_ascii=False,
            )
        ]
    )

    agent = AgentRuntime(
        llm=llm,
        registry=registry,
    )

    result = agent.run(
        user_input="你好",
        user_id="user-a",
        session_id="window-1",
    )

    assert result.answer == (
        "你好，我是 Agent。"
    )
    assert result.steps == 1
    assert len(llm.calls) == 1


def test_agent_calls_calculator_then_answers(
    registry,
) -> None:
    llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "tool_call",
                    "reason": "需要计算",
                    "tool_name": "calculator",
                    "arguments": {
                        "expression": "6 * 7"
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "type": "final",
                    "reason": "已经得到计算结果",
                    "answer": "6 × 7 等于 42。",
                },
                ensure_ascii=False,
            ),
        ]
    )

    agent = AgentRuntime(
        llm=llm,
        registry=registry,
    )

    result = agent.run(
        user_input="6乘7等于多少？",
        user_id="user-a",
        session_id="window-1",
    )

    assert result.answer == (
        "6 × 7 等于 42。"
    )
    assert result.steps == 2
    assert len(llm.calls) == 2

    second_call_messages = (
        llm.calls[1]["messages"]
    )

    tool_messages = [
        message
        for message in second_call_messages
        if message.role == "tool"
    ]

    assert len(tool_messages) == 1
    assert '"value": 42' in (
        tool_messages[0].content
    )


def test_agent_can_call_multiple_tools(
    registry,
) -> None:
    llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "tool_call",
                    "reason": "先计算",
                    "tool_name": "calculator",
                    "arguments": {
                        "expression": "238 * 17"
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "type": "tool_call",
                    "reason": "将结果记入待办",
                    "tool_name": "todo",
                    "arguments": {
                        "action": "add",
                        "content": (
                            "记录计算结果：4046"
                        ),
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "type": "final",
                    "reason": "计算和待办均已完成",
                    "answer": (
                        "结果是 4046，"
                        "并已记录到待办。"
                    ),
                },
                ensure_ascii=False,
            ),
        ]
    )

    agent = AgentRuntime(
        llm=llm,
        registry=registry,
    )

    result = agent.run(
        user_input=(
            "计算238乘17，并记到待办"
        ),
        user_id="user-a",
        session_id="window-1",
    )

    assert result.steps == 3
    assert "4046" in result.answer

    listed = registry.execute(
        tool_name="todo",
        arguments={
            "action": "list",
        },
        context=None,
    )

    # 不传 Session 上下文必须失败。
    assert listed.success is False
    assert listed.error_type == (
        "tool_execution_error"
    )


def test_agent_can_recover_from_unknown_tool(
    registry,
) -> None:
    llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "tool_call",
                    "reason": "错误选择了工具",
                    "tool_name": "unknown_tool",
                    "arguments": {},
                }
            ),
            json.dumps(
                {
                    "type": "tool_call",
                    "reason": "改用计算器",
                    "tool_name": "calculator",
                    "arguments": {
                        "expression": "1 + 1"
                    },
                }
            ),
            json.dumps(
                {
                    "type": "final",
                    "reason": "计算完成",
                    "answer": "答案是 2。",
                },
                ensure_ascii=False,
            ),
        ]
    )

    agent = AgentRuntime(
        llm=llm,
        registry=registry,
    )

    result = agent.run(
        user_input="1加1是多少？",
        user_id="user-a",
        session_id="window-1",
    )

    assert result.answer == "答案是 2。"
    assert result.steps == 3

    second_call_messages = (
        llm.calls[1]["messages"]
    )

    assert any(
        message.role == "tool"
        and "unknown_tool" in message.content
        for message in second_call_messages
    )


def test_agent_can_recover_from_malformed_output(
    registry,
) -> None:
    llm = FakeLLMClient(
        responses=[
            "我认为答案是 42。",
            json.dumps(
                {
                    "type": "final",
                    "reason": "修正输出格式",
                    "answer": "答案是 42。",
                },
                ensure_ascii=False,
            ),
        ]
    )

    agent = AgentRuntime(
        llm=llm,
        registry=registry,
    )

    result = agent.run(
        user_input="答案是什么？",
        user_id="user-a",
        session_id="window-1",
    )

    assert result.answer == "答案是 42。"
    assert result.steps == 2

    second_call_messages = (
        llm.calls[1]["messages"]
    )

    assert any(
        message.role == "system"
        and "无法解析" in message.content
        for message in second_call_messages
    )


def test_agent_stops_at_max_steps(
    registry,
) -> None:
    tool_call = json.dumps(
        {
            "type": "tool_call",
            "reason": "继续计算",
            "tool_name": "calculator",
            "arguments": {
                "expression": "1 + 1"
            },
        }
    )

    llm = FakeLLMClient(
        responses=[
            tool_call,
            tool_call,
        ]
    )

    agent = AgentRuntime(
        llm=llm,
        registry=registry,
        max_steps=2,
    )

    with pytest.raises(
        MaxStepsExceededError,
        match="maximum steps",
    ):
        agent.run(
            user_input="不停计算",
            user_id="user-a",
            session_id="window-1",
        )


def test_agent_rejects_empty_input(
    registry,
) -> None:
    llm = FakeLLMClient(
        responses=[]
    )

    agent = AgentRuntime(
        llm=llm,
        registry=registry,
    )

    with pytest.raises(
        ValueError,
        match="user_input",
    ):
        agent.run(
            user_input="   ",
            user_id="user-a",
            session_id="window-1",
        )