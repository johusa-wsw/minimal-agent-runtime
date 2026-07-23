from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from minimal_agent.runtime.models import ChatMessage


class BaseLLMClient(ABC):
    """Agent Runtime 使用的统一 LLM 接口。"""

    @abstractmethod
    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
    ) -> str:
        """返回模型生成的原始文本。"""

        raise NotImplementedError