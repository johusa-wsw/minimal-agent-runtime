from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from minimal_agent.tools.base import (
    BaseTool,
    ToolContext,
    ToolExecutionError,
)

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """一次工具调用的标准化结果。"""

    success: bool
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    output: Any | None = None
    error: str | None = None
    error_type: str | None = None


class ToolRegistry:
    """负责工具注册、Schema 暴露和工具执行。"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> BaseTool:
        """注册一个工具。

        返回工具实例本身，方便后续扩展为装饰器式写法。
        """

        if not tool.name or not tool.name.strip():
            raise ValueError("Tool name cannot be empty")

        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' has already been registered"
            )

        self._tools[tool.name] = tool
        return tool

    def get(self, tool_name: str) -> BaseTool:
        """根据名称取得工具。

        不存在时抛出 KeyError，适合程序内部明确访问。
        """

        try:
            return self._tools[tool_name]
        except KeyError as exc:
            raise KeyError(
                f"Tool '{tool_name}' is not registered"
            ) from exc

    def has(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def list_names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        """返回所有工具 Schema，之后会放进 LLM Prompt。"""

        return [
            self._tools[name].schema()
            for name in sorted(self._tools)
        ]

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> ToolResult:
        """安全执行工具，并把所有结果统一包装为 ToolResult。"""

        tool = self._tools.get(tool_name)

        if tool is None:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                arguments=arguments,
                error=f"Unknown tool: {tool_name}",
                error_type="unknown_tool",
            )

        try:
            output = tool.execute(
                arguments=arguments,
                context=context,
            )

            return ToolResult(
                success=True,
                tool_name=tool_name,
                arguments=arguments,
                output=output,
            )

        except ValidationError as exc:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                arguments=arguments,
                error=str(exc),
                error_type="invalid_arguments",
            )

        except ToolExecutionError as exc:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                arguments=arguments,
                error=str(exc),
                error_type="tool_execution_error",
            )

        except Exception as exc:
            logger.exception(
                "Unexpected error while executing tool '%s'",
                tool_name,
            )

            return ToolResult(
                success=False,
                tool_name=tool_name,
                arguments=arguments,
                error=str(exc),
                error_type="unexpected_tool_error",
            )