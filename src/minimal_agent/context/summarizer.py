from __future__ import annotations

import json
from abc import ABC, abstractmethod

from minimal_agent.runtime.models import ChatMessage


class BaseSummarizer(ABC):
    """历史消息摘要器接口。"""

    @abstractmethod
    def summarize(
        self,
        existing_summary: str,
        messages: list[ChatMessage],
    ) -> str:
        raise NotImplementedError


class RuleBasedSummarizer(BaseSummarizer):
    """不依赖额外 LLM 调用的基础摘要器。

    当前版本通过提取不同角色的关键信息完成简单压缩。
    后续可以替换为真实 LLM 摘要器，而无需修改 ContextManager。
    """

    def __init__(
        self,
        max_summary_chars: int = 1200,
        max_line_chars: int = 240,
    ) -> None:
        if max_summary_chars < 100:
            raise ValueError(
                "max_summary_chars must be at least 100"
            )

        if max_line_chars < 40:
            raise ValueError(
                "max_line_chars must be at least 40"
            )

        self._max_summary_chars = max_summary_chars
        self._max_line_chars = max_line_chars

    def summarize(
        self,
        existing_summary: str,
        messages: list[ChatMessage],
    ) -> str:
        lines: list[str] = []

        if existing_summary.strip():
            lines.append(
                "此前摘要："
                + self._truncate(
                    existing_summary.strip(),
                    self._max_line_chars * 2,
                )
            )

        for message in messages:
            rendered = self._render_message(
                message
            )

            if rendered:
                lines.append(rendered)

        if not lines:
            return existing_summary.strip()

        summary = "\n".join(lines)

        if len(summary) > self._max_summary_chars:
            summary = (
                summary[: self._max_summary_chars]
                .rstrip()
                + "..."
            )

        return summary

    def _render_message(
        self,
        message: ChatMessage,
    ) -> str:
        content = message.content.strip()

        if not content:
            return ""

        if message.role == "user":
            prefix = "用户："

        elif message.role == "assistant":
            prefix = "Agent："
            content = self._render_assistant_content(
                content
            )

        elif message.role == "tool":
            tool_name = message.name or "unknown"
            prefix = f"工具 {tool_name}："
            content = self._render_tool_content(
                content
            )

        elif message.role == "system":
            prefix = "系统状态："

        else:
            prefix = f"{message.role}："

        return prefix + self._truncate(
            content,
            self._max_line_chars,
        )

    def _render_assistant_content(
        self,
        content: str,
    ) -> str:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return content

        if not isinstance(payload, dict):
            return content

        if payload.get("type") == "tool_call":
            tool_name = payload.get(
                "tool_name",
                "unknown",
            )

            arguments = payload.get(
                "arguments",
                {},
            )

            return (
                f"决定调用 {tool_name}，"
                f"参数为 {arguments}"
            )

        return content

    def _render_tool_content(
        self,
        content: str,
    ) -> str:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return content

        if not isinstance(payload, dict):
            return content

        success = payload.get("success")

        if success is True:
            output = payload.get("output")

            return f"执行成功，结果为 {output}"

        error = payload.get(
            "error",
            "unknown error",
        )

        return f"执行失败，错误为 {error}"

    @staticmethod
    def _truncate(
        text: str,
        max_chars: int,
    ) -> str:
        compact = " ".join(text.split())

        if len(compact) <= max_chars:
            return compact

        return (
            compact[:max_chars].rstrip()
            + "..."
        )