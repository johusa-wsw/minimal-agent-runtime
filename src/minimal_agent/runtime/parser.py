from __future__ import annotations

import json
import re
from typing import Any

from pydantic import TypeAdapter, ValidationError

from minimal_agent.runtime.models import (
    AgentDecision,
)


class ResponseParseError(ValueError):
    """LLM 输出无法被解析为 Agent 决策。"""

    def __init__(
        self,
        message: str,
        raw_output: str,
    ) -> None:
        super().__init__(message)
        self.raw_output = raw_output


class ResponseParser:
    """将 LLM 原始文本解析为结构化决策。"""

    def __init__(self) -> None:
        self._adapter = TypeAdapter(AgentDecision)

    def parse(
        self,
        raw_output: str,
    ) -> AgentDecision:
        if not isinstance(raw_output, str):
            raise ResponseParseError(
                "LLM output must be a string",
                raw_output=str(raw_output),
            )

        if not raw_output.strip():
            raise ResponseParseError(
                "LLM output is empty",
                raw_output=raw_output,
            )

        payload = self._extract_json_object(
            raw_output
        )

        try:
            return self._adapter.validate_python(
                payload
            )
        except ValidationError as exc:
            raise ResponseParseError(
                f"Invalid Agent decision: {exc}",
                raw_output=raw_output,
            ) from exc

    def _extract_json_object(
        self,
        raw_output: str,
    ) -> dict[str, Any]:
        candidates = self._build_candidates(
            raw_output
        )

        decoder = json.JSONDecoder()

        for candidate in candidates:
            candidate = candidate.strip()

            # 先尝试整个字符串就是 JSON。
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                value = None

            if isinstance(value, dict):
                return value

            # 再尝试从混合文本中寻找第一个合法 JSON 对象。
            for index, character in enumerate(
                candidate
            ):
                if character != "{":
                    continue

                try:
                    value, _ = decoder.raw_decode(
                        candidate[index:]
                    )
                except json.JSONDecodeError:
                    continue

                if isinstance(value, dict):
                    return value

        raise ResponseParseError(
            "No valid JSON object found in LLM output",
            raw_output=raw_output,
        )

    @staticmethod
    def _build_candidates(
        raw_output: str,
    ) -> list[str]:
        candidates = [raw_output]

        fenced_blocks = re.findall(
            r"```(?:json)?\s*(.*?)```",
            raw_output,
            flags=re.IGNORECASE | re.DOTALL,
        )

        candidates.extend(fenced_blocks)

        return candidates