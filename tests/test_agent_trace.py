import json
from pathlib import Path

from minimal_agent.llm.fake import (
    FakeLLMClient,
)
from minimal_agent.runtime.agent import (
    AgentRuntime,
)
from minimal_agent.tools.factory import (
    build_default_registry,
)
from minimal_agent.tracing.trace import (
    JSONLTraceWriter,
)


def read_events(
    trace_path: str,
) -> list[dict]:
    path = Path(trace_path)

    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def test_agent_writes_direct_answer_trace(
    tmp_path: Path,
) -> None:
    llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "final",
                    "reason": "无需工具",
                    "answer": "你好。",
                },
                ensure_ascii=False,
            )
        ]
    )

    registry = build_default_registry(
        database_path=(
            tmp_path / "agent.db"
        ),
        search_data_path=(
            Path("data")
            / "mock_search.json"
        ),
    )

    agent = AgentRuntime(
        llm=llm,
        registry=registry,
        trace_writer=JSONLTraceWriter(
            traces_dir=tmp_path / "traces"
        ),
    )

    result = agent.run(
        user_input="你好",
        user_id="user-a",
        session_id="window-1",
    )

    assert result.run_id is not None
    assert result.trace_path is not None

    events = read_events(
        result.trace_path
    )

    event_names = [
        event["event"]
        for event in events
    ]

    assert event_names == [
        "run_started",
        "context_loaded",
        "llm_request",
        "llm_response",
        "final_answer",
    ]


def test_agent_writes_tool_trace(
    tmp_path: Path,
) -> None:
    llm = FakeLLMClient(
        responses=[
            json.dumps(
                {
                    "type": "tool_call",
                    "reason": "需要计算",
                    "tool_name": "calculator",
                    "arguments": {
                        "expression": "7 * 8"
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "type": "final",
                    "reason": "计算完成",
                    "answer": "答案是 56。",
                },
                ensure_ascii=False,
            ),
        ]
    )

    registry = build_default_registry(
        database_path=(
            tmp_path / "agent.db"
        ),
        search_data_path=(
            Path("data")
            / "mock_search.json"
        ),
    )

    agent = AgentRuntime(
        llm=llm,
        registry=registry,
        trace_writer=JSONLTraceWriter(
            traces_dir=tmp_path / "traces"
        ),
    )

    result = agent.run(
        user_input="7乘8是多少？",
        user_id="user-a",
        session_id="window-1",
    )

    assert result.trace_path is not None

    events = read_events(
        result.trace_path
    )

    event_names = [
        event["event"]
        for event in events
    ]

    assert "tool_call" in event_names
    assert "tool_result" in event_names
    assert "final_answer" in event_names

    tool_result = next(
        event
        for event in events
        if event["event"] == "tool_result"
    )

    assert (
        tool_result["payload"]
        ["output"]["value"]
        == 56
    )