import pytest

from minimal_agent.runtime.models import (
    FinalDecision,
    ToolCallDecision,
)
from minimal_agent.runtime.parser import (
    ResponseParseError,
    ResponseParser,
)


@pytest.fixture
def parser() -> ResponseParser:
    return ResponseParser()


def test_parse_final_decision(
    parser: ResponseParser,
) -> None:
    decision = parser.parse(
        """
        {
          "type": "final",
          "reason": "可以直接回答",
          "answer": "你好"
        }
        """
    )

    assert isinstance(
        decision,
        FinalDecision,
    )
    assert decision.answer == "你好"


def test_parse_tool_call_decision(
    parser: ResponseParser,
) -> None:
    decision = parser.parse(
        """
        {
          "type": "tool_call",
          "reason": "需要计算",
          "tool_name": "calculator",
          "arguments": {
            "expression": "6 * 7"
          }
        }
        """
    )

    assert isinstance(
        decision,
        ToolCallDecision,
    )
    assert decision.tool_name == "calculator"
    assert decision.arguments == {
        "expression": "6 * 7"
    }


def test_parse_json_code_block(
    parser: ResponseParser,
) -> None:
    decision = parser.parse(
        """
        ```json
        {
          "type": "final",
          "reason": "完成",
          "answer": "结果是 42"
        }
        ```
        """
    )

    assert isinstance(
        decision,
        FinalDecision,
    )
    assert decision.answer == "结果是 42"


def test_parse_json_surrounded_by_text(
    parser: ResponseParser,
) -> None:
    decision = parser.parse(
        """
        我决定直接回答：
        {
          "type": "final",
          "reason": "无需工具",
          "answer": "这是答案"
        }
        谢谢。
        """
    )

    assert isinstance(
        decision,
        FinalDecision,
    )


def test_reject_empty_output(
    parser: ResponseParser,
) -> None:
    with pytest.raises(
        ResponseParseError,
        match="empty",
    ):
        parser.parse("   ")


def test_reject_output_without_json(
    parser: ResponseParser,
) -> None:
    with pytest.raises(
        ResponseParseError,
        match="No valid JSON",
    ):
        parser.parse(
            "I think the answer is 42."
        )


def test_reject_unknown_decision_type(
    parser: ResponseParser,
) -> None:
    with pytest.raises(
        ResponseParseError,
        match="Invalid Agent decision",
    ):
        parser.parse(
            """
            {
              "type": "unknown",
              "answer": "hello"
            }
            """
        )


def test_reject_extra_fields(
    parser: ResponseParser,
) -> None:
    with pytest.raises(
        ResponseParseError,
        match="Invalid Agent decision",
    ):
        parser.parse(
            """
            {
              "type": "final",
              "answer": "hello",
              "unexpected": true
            }
            """
        )