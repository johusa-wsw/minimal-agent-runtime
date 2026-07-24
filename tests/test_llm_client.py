import json

import httpx
import pytest

from minimal_agent.llm.openai_compatible import (
    LLMHTTPError,
    LLMResponseError,
    OpenAICompatibleLLMClient,
)
from minimal_agent.runtime.models import (
    ChatMessage,
)


def test_client_sends_messages_and_tools() -> None:
    captured_request: dict = {}

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        captured_request["url"] = str(
            request.url
        )

        captured_request["authorization"] = (
            request.headers.get(
                "Authorization"
            )
        )

        captured_request["body"] = (
            json.loads(request.content)
        )

        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"type":"final",'
                                '"reason":"完成",'
                                '"answer":"你好"}'
                            ),
                        }
                    }
                ]
            },
        )

    http_client = httpx.Client(
        transport=httpx.MockTransport(
            handler
        )
    )

    client = OpenAICompatibleLLMClient(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
        http_client=http_client,
    )

    result = client.complete(
        messages=[
            ChatMessage(
                role="system",
                content="系统提示",
            ),
            ChatMessage(
                role="user",
                content="你好",
            ),
        ],
        tools=[
            {
                "name": "calculator",
                "description": "计算表达式",
                "parameters": {
                    "type": "object",
                },
            }
        ],
    )

    assert '"type":"final"' in result

    assert captured_request["url"] == (
        "https://example.com/v1/"
        "chat/completions"
    )

    assert (
        captured_request["authorization"]
        == "Bearer test-key"
    )

    body = captured_request["body"]

    assert body["model"] == "test-model"

    assert any(
        message["role"] == "system"
        and "calculator" in message["content"]
        for message in body["messages"]
    )


def test_internal_tool_message_is_converted() -> None:
    captured_body: dict = {}

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        captured_body.update(
            json.loads(request.content)
        )

        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"type":"final",'
                                '"answer":"42"}'
                            )
                        }
                    }
                ]
            },
        )

    client = OpenAICompatibleLLMClient(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                handler
            )
        ),
    )

    client.complete(
        messages=[
            ChatMessage(
                role="system",
                content="系统提示",
            ),
            ChatMessage(
                role="tool",
                name="calculator",
                content=(
                    '{"success":true,'
                    '"output":{"value":42}}'
                ),
            ),
        ],
        tools=[],
    )

    provider_messages = (
        captured_body["messages"]
    )

    assert not any(
        message["role"] == "tool"
        for message in provider_messages
    )

    assert any(
        message["role"] == "user"
        and "[TOOL_RESULT]"
        in message["content"]
        and "calculator"
        in message["content"]
        for message in provider_messages
    )


def test_client_raises_for_http_error() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=401,
            json={
                "error": {
                    "message": "invalid key"
                }
            },
        )

    client = OpenAICompatibleLLMClient(
        api_key="bad-key",
        base_url="https://example.com/v1",
        model="test-model",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                handler
            )
        ),
    )

    with pytest.raises(
        LLMHTTPError,
        match="401",
    ):
        client.complete(
            messages=[
                ChatMessage(
                    role="user",
                    content="你好",
                )
            ],
            tools=[],
        )


def test_client_rejects_malformed_response() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "unexpected": "payload"
            },
        )

    client = OpenAICompatibleLLMClient(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                handler
            )
        ),
    )

    with pytest.raises(
        LLMResponseError,
        match="no choices",
    ):
        client.complete(
            messages=[
                ChatMessage(
                    role="user",
                    content="你好",
                )
            ],
            tools=[],
        )