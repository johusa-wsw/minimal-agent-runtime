from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


class ToolArguments(BaseModel):
    """所有工具参数模型的基类。

    extra='forbid' 可以防止 LLM 传入 Schema 中不存在的参数。
    """

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolContext:
    """工具运行时上下文。

    后续 todo 工具会使用 user_id 和 session_id 实现数据隔离。
    """

    user_id: str
    session_id: str


class ToolExecutionError(Exception):
    """工具能够预期并安全返回给 Agent 的执行错误。"""


class BaseTool(ABC):
    """所有工具必须实现的统一接口。"""

    name: ClassVar[str]
    description: ClassVar[str]
    args_model: ClassVar[type[ToolArguments]]

    def schema(self) -> dict[str, Any]:
        """返回供 LLM 阅读的工具 Schema。"""

        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_model.model_json_schema(),
        }

    def validate_arguments(
        self,
        arguments: dict[str, Any],
    ) -> ToolArguments:
        """根据 Pydantic 参数模型校验工具参数。"""

        return self.args_model.model_validate(arguments)

    def execute(
        self,
        arguments: dict[str, Any],
        context: ToolContext | None = None,
    ) -> Any:
        """校验参数后执行工具。"""

        validated_arguments = self.validate_arguments(arguments)
        return self.run(validated_arguments, context)

    @abstractmethod
    def run(
        self,
        arguments: ToolArguments,
        context: ToolContext | None = None,
    ) -> Any:
        """子类实现具体工具逻辑。"""

        raise NotImplementedError