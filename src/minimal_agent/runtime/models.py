from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """发送给 LLM 的标准消息。"""

    model_config = ConfigDict(extra="forbid")

    role: Literal[
        "system",
        "user",
        "assistant",
        "tool",
    ]

    content: str
    name: str | None = None


class ToolCallDecision(BaseModel):
    """LLM 决定调用工具。"""

    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_call"]

    reason: str = Field(
        default="",
        max_length=500,
        description="简短说明为什么需要调用工具",
    )

    tool_name: str = Field(
        min_length=1,
        max_length=100,
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict
    )


class FinalDecision(BaseModel):
    """LLM 决定返回最终答案。"""

    model_config = ConfigDict(extra="forbid")

    type: Literal["final"]

    reason: str = Field(
        default="",
        max_length=500,
        description="简短说明为什么可以结束循环",
    )

    answer: str = Field(
        min_length=1,
    )


AgentDecision = Annotated[
    ToolCallDecision | FinalDecision,
    Field(discriminator="type"),
]


class AgentRunResult(BaseModel):
    """一次 Agent 执行的最终结果。"""

    answer: str
    steps: int
    messages: list[ChatMessage]