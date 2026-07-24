import json
from pathlib import Path

from minimal_agent.tracing.trace import (
    JSONLTraceWriter,
)


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def test_trace_writer_creates_jsonl_file(
    tmp_path: Path,
) -> None:
    writer = JSONLTraceWriter(
        traces_dir=tmp_path,
    )

    trace = writer.start_run(
        user_id="user-a",
        session_id="window-1",
    )

    trace.write(
        event="run_started",
        payload={
            "user_input": "你好",
        },
    )

    trace.write(
        event="final_answer",
        step=1,
        payload={
            "answer": "你好！",
        },
    )

    assert trace.file_path.exists()

    events = read_jsonl(
        trace.file_path
    )

    assert len(events) == 2
    assert events[0]["event"] == (
        "run_started"
    )
    assert events[1]["event"] == (
        "final_answer"
    )

    assert events[0]["run_id"] == (
        trace.run_id
    )

    assert events[1]["step"] == 1


def test_trace_writer_truncates_long_text(
    tmp_path: Path,
) -> None:
    writer = JSONLTraceWriter(
        traces_dir=tmp_path,
        max_text_chars=100,
    )

    trace = writer.start_run(
        user_id="user-a",
        session_id="window-1",
    )

    trace.write(
        event="llm_response",
        payload={
            "raw_output": "x" * 500,
        },
    )

    events = read_jsonl(
        trace.file_path
    )

    raw_output = events[0][
        "payload"
    ]["raw_output"]

    assert len(raw_output) < 500
    assert "trace truncated" in raw_output


def test_separate_runs_use_separate_files(
    tmp_path: Path,
) -> None:
    writer = JSONLTraceWriter(
        traces_dir=tmp_path,
    )

    first = writer.start_run(
        user_id="user-a",
        session_id="window-1",
    )

    second = writer.start_run(
        user_id="user-a",
        session_id="window-1",
    )

    assert first.run_id != second.run_id
    assert first.file_path != second.file_path