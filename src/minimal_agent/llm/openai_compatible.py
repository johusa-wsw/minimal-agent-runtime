from __future__ import annotations

import json
from typing import Any

import httpx
import time

from minimal_agent.llm.base import BaseLLMClient
from minimal_agent.runtime.models import ChatMessage


class LLMClientError(RuntimeError):
    """真实 LLM 客户端基础异常。"""


class LLMHTTPError(LLMClientError):
    """LLM HTTP 请求失败。"""


class LLMResponseError(LLMClientError):
    """LLM 返回结构不符合预期。"""


class OpenAICompatibleLLMClient(BaseLLMClient):
    """通过 OpenAI-compatible Chat Completions 接口调用模型。

    Agent Loop、工具执行和输出解析仍由本项目自行实现。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        retry_base_seconds: float = 1.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        api_key = api_key.strip()
        base_url = base_url.strip().rstrip("/")
        model = model.strip()

        if not api_key:
            raise ValueError("api_key cannot be empty")

        if not base_url:
            raise ValueError("base_url cannot be empty")

        if not model:
            raise ValueError("model cannot be empty")

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be positive"
            )

        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._timeout_seconds = timeout_seconds

        self._owns_http_client = (
            http_client is None
        )

        if max_retries < 0:
            raise ValueError(
                "max_retries cannot be negative"
            )

        if retry_base_seconds <= 0:
            raise ValueError(
                "retry_base_seconds must be positive"
            )

        self._max_retries = max_retries
        self._retry_base_seconds = retry_base_seconds

        self._http_client = (
            http_client
            or httpx.Client(
                timeout=timeout_seconds
            )
        )

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
    ) -> str:
        provider_messages = (
            self._build_provider_messages(
                messages=messages,
                tools=tools,
            )
        )

        request_body = {
            "model": self._model,
            "messages": provider_messages,
        }

        endpoint = (
            f"{self._base_url}/chat/completions"
        )

        response: httpx.Response | None = None
        last_error: Exception | None = None

        for attempt in range(
            self._max_retries + 1
        ):
            try:
                response = self._http_client.post(
                    endpoint,
                    headers={
                        "Authorization": (
                            f"Bearer {self._api_key}"
                        ),
                        "Content-Type": (
                            "application/json"
                        ),
                    },
                    json=request_body,
                    timeout=self._timeout_seconds,
                )

                break

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
            ) as exc:
                last_error = exc

                if attempt >= self._max_retries:
                    break

                delay = (
                    self._retry_base_seconds
                    * (2 ** attempt)
                )

                time.sleep(delay)

            except httpx.HTTPError as exc:
                raise LLMHTTPError(
                    f"LLM request failed: {exc}"
                ) from exc

        if response is None:
            raise LLMHTTPError(
                "LLM request failed after "
                f"{self._max_retries + 1} attempts: "
                f"{last_error}"
            ) from last_error

        if not response.is_success:
            response_text = response.text

            if len(response_text) > 1000:
                response_text = (
                    response_text[:1000]
                    + "...[truncated]"
                )

            raise LLMHTTPError(
                f"LLM returned HTTP "
                f"{response.status_code}: "
                f"{response_text}"
            )

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                "LLM response is not valid JSON"
            ) from exc

        return self._extract_content(payload)

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def _build_provider_messages(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        tool_instruction = (
            "以下是当前可用工具的名称、描述和参数 "
            "Schema。只能调用这里列出的工具：\n"
            + json.dumps(
                tools,
                ensure_ascii=False,
                indent=2,
            )
        )

        provider_messages: list[
            dict[str, str]
        ] = []

        tool_schema_inserted = False

        for message in messages:
            if (
                message.role == "system"
                and not tool_schema_inserted
            ):
                provider_messages.append(
                    {
                        "role": "system",
                        "content": message.content,
                    }
                )

                provider_messages.append(
                    {
                        "role": "system",
                        "content": tool_instruction,
                    }
                )

                tool_schema_inserted = True
                continue

            if message.role == "tool":
                # 当前项目自行实现工具协议，
                # 不使用供应商原生 tool_call_id。
                # 因此将内部 tool 消息转换成普通消息。
                provider_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "[TOOL_RESULT]\n"
                            f"tool_name: "
                            f"{message.name or 'unknown'}\n"
                            f"result: {message.content}\n"
                            "这是工具执行结果，不是新的"
                            "用户请求。请根据结果继续决策。"
                        ),
                    }
                )

                continue

            provider_messages.append(
                {
                    "role": message.role,
                    "content": message.content,
                }
            )

        if not tool_schema_inserted:
            provider_messages.insert(
                0,
                {
                    "role": "system",
                    "content": tool_instruction,
                },
            )

        return provider_messages

    @staticmethod
    def _extract_content(
        payload: Any,
    ) -> str:
        if not isinstance(payload, dict):
            raise LLMResponseError(
                "LLM response root must be an object"
            )

        choices = payload.get("choices")

        if (
            not isinstance(choices, list)
            or not choices
        ):
            raise LLMResponseError(
                "LLM response has no choices"
            )

        first_choice = choices[0]

        if not isinstance(first_choice, dict):
            raise LLMResponseError(
                "LLM choice must be an object"
            )

        message = first_choice.get("message")

        if not isinstance(message, dict):
            raise LLMResponseError(
                "LLM choice has no message"
            )

        content = message.get("content")

        if isinstance(content, str):
            if not content.strip():
                raise LLMResponseError(
                    "LLM returned empty content"
                )

            return content

        # 兼容部分供应商返回内容块列表。
        if isinstance(content, list):
            text_parts: list[str] = []

            for item in content:
                if not isinstance(item, dict):
                    continue

                text = item.get("text")

                if isinstance(text, str):
                    text_parts.append(text)

            combined = "".join(text_parts)

            if combined.strip():
                return combined

        raise LLMResponseError(
            "LLM message content is missing "
            "or unsupported"
        )