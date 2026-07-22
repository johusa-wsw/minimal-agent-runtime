import json
from pathlib import Path

from minimal_agent.tools.factory import (
    build_default_registry,
)


def test_build_default_registry(
    tmp_path: Path,
) -> None:
    search_path = tmp_path / "search.json"

    search_path.write_text(
        json.dumps(
            [
                {
                    "id": "test",
                    "title": "Test",
                    "content": "Test document",
                    "keywords": ["test"],
                }
            ]
        ),
        encoding="utf-8",
    )

    registry = build_default_registry(
        database_path=tmp_path / "agent.db",
        search_data_path=search_path,
    )

    assert registry.list_names() == [
        "calculator",
        "search",
        "todo",
    ]