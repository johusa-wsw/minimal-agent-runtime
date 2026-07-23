from __future__ import annotations

import json

from minimal_agent.llm.base import BaseLLMClient
from minimal_agent.prompts.system_prompt import (
    SYSTEM_PROMPT,
)
from minimal_agent.runtime.models import (
    AgentRunResult,
    ChatMessage,
    FinalDecision,
    ToolCallDecision,
)
from minimal_agent.runtime.parser import (
    ResponseParseError,
    ResponseParser,
)
from minimal_agent.tools.base import ToolContext
from minimal_agent.tools.registry import ToolRegistry


class AgentRuntimeError(RuntimeError):
    """Agent Runtime 基础异常。"""


class LLMInvocationError(AgentRuntimeError):
    """调用 LLM 时发生异常。"""


class MaxStepsExceededError(AgentRuntimeError):
    """Agent 超过最大循环次数。"""

    def __init__(
        self,
        max_steps: int,
        messages: list[ChatMessage],
    ) -> None:
        super().__init__(
            f"Agent exceeded maximum steps: "
            f"{max_steps}"
        )

        self.max_steps = max_steps
        self.messages = messages


class AgentRuntime:
    """最小可用 Agent 核心循环。"""

    def __init__(
        self,
        llm: BaseLLMClient,
        registry: ToolRegistry,
        parser: ResponseParser | None = None,
        max_steps: int = 8,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        if max_steps < 1:
            raise ValueError(
                "max_steps must be at least 1"
            )

        self._llm = llm
        self._registry = registry
        self._parser = parser or ResponseParser()
        self._max_steps = max_steps
        self._system_prompt = system_prompt

    def run(
        self,
        user_input: str,
        user_id: str,
        session_id: str,
    ) -> AgentRunResult:
        user_input = user_input.strip()
        user_id = user_id.strip()
        session_id = session_id.strip()

        if not user_input:
            raise ValueError(
                "user_input cannot be empty"
            )

        if not user_id:
            raise ValueError(
                "user_id cannot be empty"
            )

        if not session_id:
            raise ValueError(
                "session_id cannot be empty"
            )

        messages = [
            ChatMessage(
                role="system",
                content=self._system_prompt,
            ),
            ChatMessage(
                role="user",
                content=user_input,
            ),
        ]

        tool_context = ToolContext(
            user_id=user_id,
            session_id=session_id,
        )

        tool_schemas = self._registry.schemas()

        for step in range(
            1,
            self._max_steps + 1,
        ):
            raw_output = self._call_llm(
                messages=messages,
                tools=tool_schemas,
            )

            try:
                decision = self._parser.parse(
                    raw_output
                )
            except ResponseParseError as exc:
                # 保留模型原始错误输出。
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=raw_output,
                    )
                )

                # 将格式错误反馈给模型，
                # 让模型在下一轮自我修正。
                messages.append(
                    ChatMessage(
                        role="system",
                        content=(
                            "上一轮输出无法解析。"
                            f"错误：{exc}。"
                            "请严格按照约定，只返回一个合法 "
                            "JSON 对象。"
                        ),
                    )
                )

                continue

            if isinstance(
                decision,
                FinalDecision,
            ):
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=decision.answer,
                    )
                )

                return AgentRunResult(
                    answer=decision.answer,
                    steps=step,
                    messages=messages,
                )

            if isinstance(
                decision,
                ToolCallDecision,
            ):
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=decision.model_dump_json(),
                    )
                )

                tool_result = self._registry.execute(
                    tool_name=decision.tool_name,
                    arguments=decision.arguments,
                    context=tool_context,
                )

                messages.append(
                    ChatMessage(
                        role="tool",
                        name=decision.tool_name,
                        content=json.dumps(
                            tool_result.model_dump(
                                mode="json"
                            ),
                            ensure_ascii=False,
                        ),
                    )
                )

                continue

            raise AgentRuntimeError(
                "Unsupported Agent decision type"
            )

        raise MaxStepsExceededError(
            max_steps=self._max_steps,
            messages=messages,
        )

    def _call_llm(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
    ) -> str:
        try:
            return self._llm.complete(
                messages=messages,
                tools=tools,
            )
        except Exception as exc:
            raise LLMInvocationError(
                f"LLM invocation failed: {exc}"
            ) from exc