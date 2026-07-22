import pytest
from pydantic import Field

from minimal_agent.tools.base import (
    BaseTool,
    ToolArguments,
    ToolContext,
    ToolExecutionError,
)
from minimal_agent.tools.calculator import CalculatorTool
from minimal_agent.tools.registry import ToolRegistry


class EchoArguments(ToolArguments):
    text: str = Field(min_length=1)


class EchoTool(BaseTool):
    name = "echo"
    description = "原样返回输入文本"
    args_model = EchoArguments

    def run(
        self,
        arguments: ToolArguments,
        context: ToolContext | None = None,
    ) -> dict[str, str]:
        assert isinstance(arguments, EchoArguments)

        return {
            "text": arguments.text,
        }


class BrokenArguments(ToolArguments):
    message: str


class BrokenTool(BaseTool):
    name = "broken"
    description = "用于测试工具执行异常"
    args_model = BrokenArguments

    def run(
        self,
        arguments: ToolArguments,
        context: ToolContext | None = None,
    ) -> None:
        raise ToolExecutionError(
            "Expected tool failure"
        )


@pytest.fixture
def registry() -> ToolRegistry:
    tool_registry = ToolRegistry()
    tool_registry.register(CalculatorTool())
    tool_registry.register(EchoTool())

    return tool_registry


def test_register_and_get_tool(
    registry: ToolRegistry,
) -> None:
    tool = registry.get("calculator")

    assert tool.name == "calculator"
    assert registry.has("calculator") is True


def test_registry_lists_tool_names(
    registry: ToolRegistry,
) -> None:
    assert registry.list_names() == [
        "calculator",
        "echo",
    ]


def test_registry_rejects_duplicate_tool_name(
    registry: ToolRegistry,
) -> None:
    with pytest.raises(
        ValueError,
        match="already been registered",
    ):
        registry.register(CalculatorTool())


def test_registry_exposes_tool_schemas(
    registry: ToolRegistry,
) -> None:
    schemas = registry.schemas()

    calculator_schema = next(
        schema
        for schema in schemas
        if schema["name"] == "calculator"
    )

    assert calculator_schema["description"]
    assert (
        "expression"
        in calculator_schema["parameters"]["properties"]
    )
    assert (
        "expression"
        in calculator_schema["parameters"]["required"]
    )


def test_registry_executes_tool_successfully(
    registry: ToolRegistry,
) -> None:
    result = registry.execute(
        tool_name="calculator",
        arguments={"expression": "6 * 7"},
    )

    assert result.success is True
    assert result.error is None
    assert result.output["value"] == 42


def test_registry_returns_unknown_tool_error(
    registry: ToolRegistry,
) -> None:
    result = registry.execute(
        tool_name="weather",
        arguments={"city": "Beijing"},
    )

    assert result.success is False
    assert result.error_type == "unknown_tool"
    assert result.output is None


def test_registry_returns_argument_validation_error(
    registry: ToolRegistry,
) -> None:
    result = registry.execute(
        tool_name="calculator",
        arguments={"wrong_field": "1 + 1"},
    )

    assert result.success is False
    assert result.error_type == "invalid_arguments"


def test_registry_returns_tool_execution_error() -> None:
    registry = ToolRegistry()
    registry.register(BrokenTool())

    result = registry.execute(
        tool_name="broken",
        arguments={"message": "test"},
    )

    assert result.success is False
    assert result.error_type == "tool_execution_error"
    assert result.error == "Expected tool failure"


def test_tool_context_can_be_passed(
    registry: ToolRegistry,
) -> None:
    context = ToolContext(
        user_id="user-a",
        session_id="window-1",
    )

    result = registry.execute(
        tool_name="echo",
        arguments={"text": "hello"},
        context=context,
    )

    assert result.success is True
    assert result.output == {"text": "hello"}