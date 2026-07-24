from __future__ import annotations

import math
import re
from dataclasses import dataclass

from minimal_agent.context.summarizer import (
    BaseSummarizer,
    RuleBasedSummarizer,
)
from minimal_agent.runtime.models import (
    ChatMessage,
)
from minimal_agent.session.store import (
    SessionStore,
)


@dataclass(frozen=True)
class ContextWindow:
    """一次 Context 构建结果。"""

    messages: list[ChatMessage]
    compressed: bool
    estimated_tokens: int
    removed_messages: int
    retained_messages: int


class TokenEstimator:
    """不依赖特定 tokenizer 的近似 Token 估算器。

    中文字符大致按照 1.5 个字符一个 token，
    其他文本大致按照 4 个字符一个 token。
    """

    _cjk_pattern = re.compile(
        r"[\u3400-\u4dbf\u4e00-\u9fff]"
    )

    def estimate_text(
        self,
        text: str,
    ) -> int:
        if not text:
            return 0

        cjk_count = len(
            self._cjk_pattern.findall(text)
        )

        other_count = max(
            len(text) - cjk_count,
            0,
        )

        estimated = (
            cjk_count / 1.5
            + other_count / 4
        )

        return max(
            1,
            math.ceil(estimated),
        )

    def estimate_message(
        self,
        message: ChatMessage,
    ) -> int:
        # 给 role、name 和消息结构保留少量开销。
        return (
            self.estimate_text(
                message.content
            )
            + 6
        )

    def estimate_messages(
        self,
        messages: list[ChatMessage],
    ) -> int:
        return sum(
            self.estimate_message(message)
            for message in messages
        )


class ContextManager:
    """负责历史读取、Token 预算和基础压缩。"""

    SUMMARY_PREFIX = (
        "以下是当前 Session 更早对话的压缩摘要。"
        "它用于保持连续性，若与最近原始消息冲突，"
        "优先以最近原始消息为准：\n"
    )

    def __init__(
        self,
        session_store: SessionStore,
        summarizer: BaseSummarizer | None = None,
        token_estimator: TokenEstimator | None = None,
        max_context_tokens: int = 2000,
        recent_token_ratio: float = 0.65,
        max_recent_messages: int = 16,
        min_recent_messages: int = 4,
        max_message_chars: int = 1600,
    ) -> None:
        if max_context_tokens < 100:
            raise ValueError(
                "max_context_tokens must be at least 100"
            )

        if not 0.2 <= recent_token_ratio <= 0.9:
            raise ValueError(
                "recent_token_ratio must be between "
                "0.2 and 0.9"
            )

        if max_recent_messages < 1:
            raise ValueError(
                "max_recent_messages must be at least 1"
            )

        if min_recent_messages < 1:
            raise ValueError(
                "min_recent_messages must be at least 1"
            )

        if (
            min_recent_messages
            > max_recent_messages
        ):
            raise ValueError(
                "min_recent_messages cannot exceed "
                "max_recent_messages"
            )

        self._session_store = session_store

        self._summarizer = (
            summarizer
            or RuleBasedSummarizer()
        )

        self._token_estimator = (
            token_estimator
            or TokenEstimator()
        )

        self._max_context_tokens = (
            max_context_tokens
        )

        self._recent_token_budget = int(
            max_context_tokens
            * recent_token_ratio
        )

        self._max_recent_messages = (
            max_recent_messages
        )

        self._min_recent_messages = (
            min_recent_messages
        )

        self._max_message_chars = (
            max_message_chars
        )

    def build_context(
        self,
        user_id: str,
        session_id: str,
    ) -> ContextWindow:
        history = (
            self._session_store.load_messages(
                user_id=user_id,
                session_id=session_id,
            )
        )

        existing_summary = (
            self._session_store.get_summary(
                user_id=user_id,
                session_id=session_id,
            )
        )

        normalized_history = [
            self._normalize_message(message)
            for message in history
        ]

        complete_context = (
            self._with_summary(
                summary=existing_summary,
                messages=normalized_history,
            )
        )

        estimated_tokens = (
            self._token_estimator
            .estimate_messages(
                complete_context
            )
        )

        if (
            estimated_tokens
            <= self._max_context_tokens
        ):
            return ContextWindow(
                messages=complete_context,
                compressed=False,
                estimated_tokens=estimated_tokens,
                removed_messages=0,
                retained_messages=len(history),
            )

        recent_messages, keep_count = (
            self._select_recent_messages(
                history
            )
        )

        old_messages = (
            history[:-keep_count]
            if keep_count > 0
            else history
        )

        # 如果没有更早消息可压缩，
        # 只对超长的近期消息进行截断。
        if not old_messages:
            final_context = self._with_summary(
                summary=existing_summary,
                messages=recent_messages,
            )

            return ContextWindow(
                messages=final_context,
                compressed=False,
                estimated_tokens=(
                    self._token_estimator
                    .estimate_messages(
                        final_context
                    )
                ),
                removed_messages=0,
                retained_messages=keep_count,
            )

        new_summary = (
            self._summarizer.summarize(
                existing_summary=(
                    existing_summary
                ),
                messages=old_messages,
            )
        )

        removed_messages = (
            self._session_store
            .compact_session(
                user_id=user_id,
                session_id=session_id,
                summary=new_summary,
                keep_last=keep_count,
            )
        )

        final_context = self._with_summary(
            summary=new_summary,
            messages=recent_messages,
        )

        return ContextWindow(
            messages=final_context,
            compressed=True,
            estimated_tokens=(
                self._token_estimator
                .estimate_messages(
                    final_context
                )
            ),
            removed_messages=removed_messages,
            retained_messages=keep_count,
        )

    def _select_recent_messages(
        self,
        history: list[ChatMessage],
    ) -> tuple[list[ChatMessage], int]:
        selected: list[ChatMessage] = []
        used_tokens = 0

        for message in reversed(history):
            if (
                len(selected)
                >= self._max_recent_messages
            ):
                break

            normalized = (
                self._normalize_message(
                    message
                )
            )

            message_tokens = (
                self._token_estimator
                .estimate_message(
                    normalized
                )
            )

            enough_recent_messages = (
                len(selected)
                >= self._min_recent_messages
            )

            budget_would_overflow = (
                used_tokens + message_tokens
                > self._recent_token_budget
            )

            if (
                enough_recent_messages
                and budget_would_overflow
            ):
                break

            selected.append(normalized)
            used_tokens += message_tokens

        selected.reverse()

        return selected, len(selected)

    def _with_summary(
        self,
        summary: str,
        messages: list[ChatMessage],
    ) -> list[ChatMessage]:
        if not summary.strip():
            return list(messages)

        summary_message = ChatMessage(
            role="system",
            content=(
                self.SUMMARY_PREFIX
                + summary.strip()
            ),
        )

        return [
            summary_message,
            *messages,
        ]

    def _normalize_message(
        self,
        message: ChatMessage,
    ) -> ChatMessage:
        content = message.content

        if (
            len(content)
            > self._max_message_chars
        ):
            content = (
                content[
                    : self._max_message_chars
                ].rstrip()
                + "...[内容已截断]"
            )

        return ChatMessage(
            role=message.role,
            content=content,
            name=message.name,
        )