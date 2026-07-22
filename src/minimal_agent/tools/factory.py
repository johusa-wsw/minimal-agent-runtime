from __future__ import annotations

from pathlib import Path

from minimal_agent.tools.calculator import (
    CalculatorTool,
)
from minimal_agent.tools.registry import (
    ToolRegistry,
)
from minimal_agent.tools.search import SearchTool
from minimal_agent.tools.todo import (
    TodoRepository,
    TodoTool,
)


def build_default_registry(
    database_path: str | Path = (
        "data/minimal_agent.db"
    ),
    search_data_path: str | Path = (
        "data/mock_search.json"
    ),
) -> ToolRegistry:
    repository = TodoRepository(
        database_path=database_path
    )

    registry = ToolRegistry()

    registry.register(CalculatorTool())
    registry.register(
        SearchTool(
            data_path=search_data_path
        )
    )
    registry.register(
        TodoTool(
            repository=repository
        )
    )

    return registry