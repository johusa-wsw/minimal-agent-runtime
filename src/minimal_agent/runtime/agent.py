from __future__ import annotations

import json
from typing import Any

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
from minimal_agent.context.manager import (
    ContextManager,
)
from minimal_agent.session.store import SessionStore
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
    """带 Session 持久化能力的最小 Agent Runtime。"""

    def __init__(
        self,
        llm: BaseLLMClient,
        registry: ToolRegistry,
        parser: ResponseParser | None = None,
        session_store: SessionStore | None = None,
	context_manager: ContextManager | None = None,
        max_steps: int = 8,
        history_message_limit: int = 100,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        if max_steps < 1:
            raise ValueError(
                "max_steps must be at least 1"
            )

        if history_message_limit < 1:
            raise ValueError(
                "history_message_limit must be at least 1"
            )

        self._llm = llm
        self._registry = registry
        self._parser = parser or ResponseParser()
        self._session_store = session_store
        self._context_manager = context_manager

        if (
            self._context_manager is None
            and self._session_store is not None
        ):
            self._context_manager = ContextManager(
                session_store=self._session_store
            )

        self._max_steps = max_steps
        self._history_message_limit = history_message_limit
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

        history = self._load_history(
            user_id=user_id,
            session_id=session_id,
        )

        user_message = ChatMessage(
            role="user",
            content=user_input,
        )

        messages = [
            ChatMessage(
                role="system",
                content=self._system_prompt,
            ),
            *history,
            user_message,
        ]

        self._persist_message(
            user_id=user_id,
            session_id=session_id,
            message=user_message,
        )

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
                # 错误输出只保留在当前 Runtime 上下文，
                # 不写入长期 Session 历史。
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=raw_output,
                    )
                )

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
                assistant_message = ChatMessage(
                    role="assistant",
                    content=decision.answer,
                )

                messages.append(
                    assistant_message
                )

                self._persist_message(
                    user_id=user_id,
                    session_id=session_id,
                    message=assistant_message,
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
                assistant_tool_call = ChatMessage(
                    role="assistant",
                    content=decision.model_dump_json(),
                )

                messages.append(
                    assistant_tool_call
                )

                tool_result = self._registry.execute(
                    tool_name=decision.tool_name,
                    arguments=decision.arguments,
                    context=tool_context,
                )

                tool_message = ChatMessage(
                    role="tool",
                    name=decision.tool_name,
                    content=json.dumps(
                        tool_result.model_dump(
                            mode="json"
                        ),
                        ensure_ascii=False,
                    ),
                )

                messages.append(tool_message)

                self._persist_messages(
                    user_id=user_id,
                    session_id=session_id,
                    messages=[
                        assistant_tool_call,
                        tool_message,
                    ],
                )

                continue

            raise AgentRuntimeError(
                "Unsupported Agent decision type"
            )

        raise MaxStepsExceededError(
            max_steps=self._max_steps,
            messages=messages,
        )

    def _load_history(
        self,
        user_id: str,
        session_id: str,
    ) -> list[ChatMessage]:
        if self._context_manager is not None:
            context_window = (
                self._context_manager
                .build_context(
                    user_id=user_id,
                    session_id=session_id,
                )
            )

            return context_window.messages

        if self._session_store is None:
            return []

        return self._session_store.load_messages(
            user_id=user_id,
            session_id=session_id,
            limit=self._history_message_limit,
        )

    def _persist_message(
        self,
        user_id: str,
        session_id: str,
        message: ChatMessage,
    ) -> None:
        if self._session_store is None:
            return

        self._session_store.append_message(
            user_id=user_id,
            session_id=session_id,
            message=message,
        )

    def _persist_messages(
        self,
        user_id: str,
        session_id: str,
        messages: list[ChatMessage],
    ) -> None:
        if self._session_store is None:
            return

        self._session_store.append_messages(
            user_id=user_id,
            session_id=session_id,
            messages=messages,
        )

    def _call_llm(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
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