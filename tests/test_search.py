import json
from pathlib import Path

import pytest

from minimal_agent.tools.base import (
    ToolExecutionError,
)
from minimal_agent.tools.search import SearchTool


@pytest.fixture
def search_data_path(
    tmp_path: Path,
) -> Path:
    data = [
        {
            "id": "runtime",
            "title": "Agent Runtime",
            "content": (
                "Agent Runtime 负责模型调用和工具执行。"
            ),
            "keywords": [
                "agent",
                "runtime",
                "工具",
            ],
        },
        {
            "id": "session",
            "title": "Session",
            "content": (
                "Session 用于隔离不同聊天窗口。"
            ),
            "keywords": [
                "session",
                "会话",
                "隔离",
            ],
        },
        {
            "id": "context",
            "title": "Context",
            "content": (
                "Context 过长时可以压缩成摘要。"
            ),
            "keywords": [
                "context",
                "摘要",
                "压缩",
            ],
        },
    ]

    path = tmp_path / "search.json"

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path


def test_search_finds_relevant_document(
    search_data_path: Path,
) -> None:
    tool = SearchTool(search_data_path)

    result = tool.execute(
        {
            "query": "Agent Runtime",
            "top_k": 3,
        }
    )

    assert result["count"] >= 1
    assert (
        result["results"][0]["id"]
        == "runtime"
    )


def test_search_supports_chinese_query(
    search_data_path: Path,
) -> None:
    tool = SearchTool(search_data_path)

    result = tool.execute(
        {
            "query": "如何隔离会话窗口",
        }
    )

    ids = [
        item["id"]
        for item in result["results"]
    ]

    assert "session" in ids


def test_search_respects_top_k(
    search_data_path: Path,
) -> None:
    tool = SearchTool(search_data_path)

    result = tool.execute(
        {
            "query": "Agent session context",
            "top_k": 1,
        }
    )

    assert len(result["results"]) <= 1


def test_search_returns_empty_results(
    search_data_path: Path,
) -> None:
    tool = SearchTool(search_data_path)

    result = tool.execute(
        {
            "query": "completely-unknown-topic",
        }
    )

    assert result["count"] == 0
    assert result["results"] == []


def test_search_rejects_missing_data_file(
    tmp_path: Path,
) -> None:
    tool = SearchTool(
        tmp_path / "missing.json"
    )

    with pytest.raises(
        ToolExecutionError,
        match="does not exist",
    ):
        tool.execute(
            {"query": "agent"}
        )