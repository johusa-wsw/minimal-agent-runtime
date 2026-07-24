from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from minimal_agent.context.manager import (
    ContextManager,
)
from minimal_agent.llm.openai_compatible import (
    OpenAICompatibleLLMClient,
)
from minimal_agent.runtime.agent import (
    AgentRuntime,
    AgentRuntimeError,
)
from minimal_agent.session.store import (
    SessionStore,
)
from minimal_agent.tools.factory import (
    build_default_registry,
)
from minimal_agent.tracing.trace import (
    JSONLTraceWriter,
)


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise ValueError(
            f"Missing required environment "
            f"variable: {name}"
        )

    return value


def env_int(
    name: str,
    default: int,
) -> int:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be an integer"
        ) from exc


def env_float(
    name: str,
    default: float,
) -> float:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a number"
        ) from exc


def build_runtime() -> tuple[
    AgentRuntime,
    SessionStore,
    OpenAICompatibleLLMClient,
]:
    load_dotenv()

    api_key = require_env("LLM_API_KEY")
    base_url = require_env("LLM_BASE_URL")
    model = require_env("LLM_MODEL")

    timeout_seconds = env_float(
        "LLM_TIMEOUT_SECONDS",
        60.0,
    )

    max_steps = env_int(
        "AGENT_MAX_STEPS",
        8,
    )

    database_path = Path(
        os.getenv(
            "AGENT_DATABASE_PATH",
            "data/minimal_agent.db",
        )
    )

    search_data_path = Path(
        os.getenv(
            "AGENT_SEARCH_DATA_PATH",
            "data/mock_search.json",
        )
    )

    traces_dir = Path(
        os.getenv(
            "AGENT_TRACES_DIR",
            "traces",
        )
    )

    llm = OpenAICompatibleLLMClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
    )

    session_store = SessionStore(
        database_path=database_path
    )

    registry = build_default_registry(
        database_path=database_path,
        search_data_path=search_data_path,
    )

    context_manager = ContextManager(
        session_store=session_store
    )

    trace_writer = JSONLTraceWriter(
        traces_dir=traces_dir
    )

    runtime = AgentRuntime(
        llm=llm,
        registry=registry,
        session_store=session_store,
        context_manager=context_manager,
        trace_writer=trace_writer,
        max_steps=max_steps,
    )

    return runtime, session_store, llm


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minimal-agent",
        description=(
            "A minimal Agent Runtime built "
            "from scratch"
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    chat_parser = subparsers.add_parser(
        "chat",
        help="Start an interactive chat session",
    )

    chat_parser.add_argument(
        "--user",
        required=True,
        help="User identifier",
    )

    chat_parser.add_argument(
        "--session",
        required=True,
        help="Session/window identifier",
    )

    chat_parser.add_argument(
        "--show-trace",
        action="store_true",
        help="Print trace path after each run",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run one user request",
    )

    run_parser.add_argument(
        "message",
        nargs="+",
        help="User request",
    )

    run_parser.add_argument(
        "--user",
        required=True,
    )

    run_parser.add_argument(
        "--session",
        required=True,
    )

    run_parser.add_argument(
        "--show-trace",
        action="store_true",
    )

    return parser


def run_once(
    runtime: AgentRuntime,
    message: str,
    user_id: str,
    session_id: str,
    show_trace: bool,
) -> int:
    try:
        result = runtime.run(
            user_input=message,
            user_id=user_id,
            session_id=session_id,
        )

    except AgentRuntimeError as exc:
        print(
            f"Agent runtime error: {exc}",
            file=sys.stderr,
        )

        return 1

    except Exception as exc:
        print(
            f"Unexpected error: {exc}",
            file=sys.stderr,
        )

        return 1

    print(f"Agent: {result.answer}")

    if show_trace and result.trace_path:
        print(f"Trace: {result.trace_path}")

    return 0


def interactive_chat(
    runtime: AgentRuntime,
    session_store: SessionStore,
    user_id: str,
    session_id: str,
    show_trace: bool,
) -> int:
    print(
        "Minimal Agent interactive chat"
    )

    print(
        f"user={user_id}, session={session_id}"
    )

    print(
        "Commands: /exit, /history, /clear"
    )

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            return 0

        if not user_input:
            continue

        if user_input in {
            "/exit",
            "/quit",
        }:
            print("Session ended.")
            return 0

        if user_input == "/clear":
            removed = (
                session_store.clear_session(
                    user_id=user_id,
                    session_id=session_id,
                )
            )

            if removed:
                print(
                    "Current session history "
                    "has been cleared."
                )
            else:
                print(
                    "Current session was "
                    "already empty."
                )

            continue

        if user_input == "/history":
            messages = (
                session_store.load_messages(
                    user_id=user_id,
                    session_id=session_id,
                )
            )

            if not messages:
                print("No session history.")
                continue

            for message in messages:
                name = (
                    f"[{message.name}]"
                    if message.name
                    else ""
                )

                print(
                    f"{message.role}{name}: "
                    f"{message.content}"
                )

            continue

        run_once(
            runtime=runtime,
            message=user_input,
            user_id=user_id,
            session_id=session_id,
            show_trace=show_trace,
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        runtime, store, llm = (
            build_runtime()
        )
    except Exception as exc:
        print(
            f"Configuration error: {exc}",
            file=sys.stderr,
        )

        return 2

    try:
        if args.command == "run":
            return run_once(
                runtime=runtime,
                message=" ".join(args.message),
                user_id=args.user,
                session_id=args.session,
                show_trace=args.show_trace,
            )

        if args.command == "chat":
            return interactive_chat(
                runtime=runtime,
                session_store=store,
                user_id=args.user,
                session_id=args.session,
                show_trace=args.show_trace,
            )

        parser.error(
            f"Unknown command: {args.command}"
        )

        return 2

    finally:
        llm.close()


if __name__ == "__main__":
    raise SystemExit(main())