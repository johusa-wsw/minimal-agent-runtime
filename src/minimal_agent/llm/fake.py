from __future__ import annotations

from collections import deque
from typing import Any, Iterable

from minimal_agent.llm.base import BaseLLMClient
from minimal_agent.runtime.models import ChatMessage


class FakeLLMExhaustedError(RuntimeError):
    """FakeLLM 已没有预设响应。"""


class FakeLLMClient(BaseLLMClient):
    """按照预设顺序返回响应的测试模型。"""

    def __init__(
        self,
        responses: Iterable[str],
    ) -> None:
        self._responses = deque(responses)

        # 记录 Runtime 每次传给模型的内容，
        # 测试时可验证工具结果是否重新进入上下文。
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
    ) -> str:
        self.calls.append(
            {
                "messages": [
                    message.model_copy(deep=True)
                    for message in messages
                ],
                "tools": tools,
            }
        )

        if not self._responses:
            raise FakeLLMExhaustedError(
                "FakeLLM has no responses left"
            )

        return self._responses.popleft()