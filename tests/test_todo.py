from pathlib import Path

import pytest
from pydantic import ValidationError

from minimal_agent.tools.base import (
    ToolContext,
    ToolExecutionError,
)
from minimal_agent.tools.todo import (
    TodoRepository,
    TodoTool,
)


@pytest.fixture
def todo_tool(
    tmp_path: Path,
) -> TodoTool:
    repository = TodoRepository(
        tmp_path / "test.db"
    )

    return TodoTool(repository)


@pytest.fixture
def context() -> ToolContext:
    return ToolContext(
        user_id="user-a",
        session_id="window-1",
    )


def test_add_and_list_todo(
    todo_tool: TodoTool,
    context: ToolContext,
) -> None:
    added = todo_tool.execute(
        {
            "action": "add",
            "content": "完成 Agent 作业",
        },
        context=context,
    )

    listed = todo_tool.execute(
        {
            "action": "list",
        },
        context=context,
    )

    assert added["item"]["content"] == (
        "完成 Agent 作业"
    )
    assert listed["count"] == 1
    assert listed["items"][0]["completed"] is False


def test_complete_todo(
    todo_tool: TodoTool,
    context: ToolContext,
) -> None:
    added = todo_tool.execute(
        {
            "action": "add",
            "content": "编写测试",
        },
        context=context,
    )

    todo_id = added["item"]["id"]

    completed = todo_tool.execute(
        {
            "action": "complete",
            "todo_id": todo_id,
        },
        context=context,
    )

    assert completed["item"]["completed"] is True

    active = todo_tool.execute(
        {
            "action": "list",
        },
        context=context,
    )

    assert active["count"] == 0

    all_items = todo_tool.execute(
        {
            "action": "list",
            "include_completed": True,
        },
        context=context,
    )

    assert all_items["count"] == 1


def test_delete_todo(
    todo_tool: TodoTool,
    context: ToolContext,
) -> None:
    added = todo_tool.execute(
        {
            "action": "add",
            "content": "临时待办",
        },
        context=context,
    )

    todo_id = added["item"]["id"]

    deleted = todo_tool.execute(
        {
            "action": "delete",
            "todo_id": todo_id,
        },
        context=context,
    )

    assert deleted["item"]["id"] == todo_id

    listed = todo_tool.execute(
        {
            "action": "list",
            "include_completed": True,
        },
        context=context,
    )

    assert listed["count"] == 0


def test_different_sessions_are_isolated(
    todo_tool: TodoTool,
) -> None:
    window_1 = ToolContext(
        user_id="user-a",
        session_id="window-1",
    )

    window_2 = ToolContext(
        user_id="user-a",
        session_id="window-2",
    )

    todo_tool.execute(
        {
            "action": "add",
            "content": "窗口一待办",
        },
        context=window_1,
    )

    list_1 = todo_tool.execute(
        {"action": "list"},
        context=window_1,
    )

    list_2 = todo_tool.execute(
        {"action": "list"},
        context=window_2,
    )

    assert list_1["count"] == 1
    assert list_2["count"] == 0


def test_different_users_are_isolated(
    todo_tool: TodoTool,
) -> None:
    user_a = ToolContext(
        user_id="user-a",
        session_id="window-1",
    )

    user_b = ToolContext(
        user_id="user-b",
        session_id="window-1",
    )

    todo_tool.execute(
        {
            "action": "add",
            "content": "用户 A 的待办",
        },
        context=user_a,
    )

    result = todo_tool.execute(
        {"action": "list"},
        context=user_b,
    )

    assert result["count"] == 0


def test_cannot_modify_another_session_todo(
    todo_tool: TodoTool,
) -> None:
    window_1 = ToolContext(
        user_id="user-a",
        session_id="window-1",
    )

    window_2 = ToolContext(
        user_id="user-a",
        session_id="window-2",
    )

    added = todo_tool.execute(
        {
            "action": "add",
            "content": "窗口一的私有待办",
        },
        context=window_1,
    )

    todo_id = added["item"]["id"]

    with pytest.raises(
        ToolExecutionError,
        match="not found",
    ):
        todo_tool.execute(
            {
                "action": "complete",
                "todo_id": todo_id,
            },
            context=window_2,
        )


def test_todo_requires_context(
    todo_tool: TodoTool,
) -> None:
    with pytest.raises(
        ToolExecutionError,
        match="requires user and session context",
    ):
        todo_tool.execute(
            {
                "action": "list",
            }
        )


def test_add_requires_content(
    todo_tool: TodoTool,
    context: ToolContext,
) -> None:
    with pytest.raises(
        ValidationError,
        match="content is required",
    ):
        todo_tool.execute(
            {
                "action": "add",
            },
            context=context,
        )


def test_complete_requires_todo_id(
    todo_tool: TodoTool,
    context: ToolContext,
) -> None:
    with pytest.raises(
        ValidationError,
        match="todo_id is required",
    ):
        todo_tool.execute(
            {
                "action": "complete",
            },
            context=context,
        )