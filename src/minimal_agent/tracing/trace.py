from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceWriteError(RuntimeError):
    """Trace 文件写入失败。"""


class RunTrace:
    """记录一次 Agent Run 的全部事件。"""

    def __init__(
        self,
        file_path: Path,
        run_id: str,
        user_id: str,
        session_id: str,
        max_text_chars: int,
    ) -> None:
        self.file_path = file_path
        self.run_id = run_id
        self.user_id = user_id
        self.session_id = session_id
        self._max_text_chars = max_text_chars
        self._lock = threading.Lock()

    def write(
        self,
        event: str,
        step: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = event.strip()

        if not event:
            raise ValueError("event cannot be empty")

        record = {
            "timestamp": utc_now(),
            "run_id": self.run_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "event": event,
            "step": step,
            "payload": self._normalize(
                payload or {}
            ),
        }

        line = json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        try:
            with self._lock:
                with self.file_path.open(
                    "a",
                    encoding="utf-8",
                ) as file:
                    file.write(line + "\n")
        except OSError as exc:
            raise TraceWriteError(
                f"Failed to write trace: {exc}"
            ) from exc

    def _normalize(
        self,
        value: Any,
    ) -> Any:
        if isinstance(value, BaseModel):
            return self._normalize(
                value.model_dump(mode="json")
            )

        if isinstance(value, dict):
            return {
                str(key): self._normalize(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple)):
            return [
                self._normalize(item)
                for item in value
            ]

        if isinstance(value, Path):
            return str(value)

        if isinstance(value, str):
            if len(value) <= self._max_text_chars:
                return value

            return (
                value[: self._max_text_chars]
                + "...[trace truncated]"
            )

        if value is None or isinstance(
            value,
            (bool, int, float),
        ):
            return value

        return str(value)


class JSONLTraceWriter:
    """为每次 Agent Run 创建独立 JSONL 文件。"""

    def __init__(
        self,
        traces_dir: str | Path = "traces",
        max_text_chars: int = 4000,
    ) -> None:
        if max_text_chars < 100:
            raise ValueError(
                "max_text_chars must be at least 100"
            )

        self.traces_dir = Path(traces_dir)
        self.traces_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._max_text_chars = max_text_chars

    def start_run(
        self,
        user_id: str,
        session_id: str,
    ) -> RunTrace:
        run_id = uuid.uuid4().hex

        timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%dT%H%M%S")

        safe_user = self._safe_filename(
            user_id
        )

        safe_session = self._safe_filename(
            session_id
        )

        file_path = self.traces_dir / (
            f"{timestamp}_{safe_user}_"
            f"{safe_session}_{run_id[:8]}.jsonl"
        )

        return RunTrace(
            file_path=file_path,
            run_id=run_id,
            user_id=user_id,
            session_id=session_id,
            max_text_chars=self._max_text_chars,
        )

    @staticmethod
    def _safe_filename(value: str) -> str:
        normalized = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            value.strip(),
        ).strip("_")

        return normalized or "unknown"