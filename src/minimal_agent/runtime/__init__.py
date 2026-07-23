from __future__ import annotations

from typing import Any

from minimal_agent.runtime.models import (
    AgentDecision,
    AgentRunResult,
    ChatMessage,
    FinalDecision,
    ToolCallDecision,
)
from minimal_agent.runtime.parser import (
    ResponseParseError,
    ResponseParser,
)

__all__ = [
    "AgentRuntime",
    "AgentRuntimeError",
    "LLMInvocationError",
    "MaxStepsExceededError",
    "AgentDecision",
    "AgentRunResult",
    "ChatMessage",
    "FinalDecision",
    "ToolCallDecision",
    "ResponseParseError",
    "ResponseParser",
]


def __getattr__(name: str) -> Any:
    """延迟导入 AgentRuntime，避免 runtime 与 llm 循环导入。"""

    if name in {
        "AgentRuntime",
        "AgentRuntimeError",
        "LLMInvocationError",
        "MaxStepsExceededError",
    }:
        from minimal_agent.runtime.agent import (
            AgentRuntime,
            AgentRuntimeError,
            LLMInvocationError,
            MaxStepsExceededError,
        )

        runtime_exports = {
            "AgentRuntime": AgentRuntime,
            "AgentRuntimeError": AgentRuntimeError,
            "LLMInvocationError": LLMInvocationError,
            "MaxStepsExceededError": MaxStepsExceededError,
        }

        return runtime_exports[name]

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )