# Minimal Agent Runtime Recording Report

## Recording result

- Status: blocked — no MP4 was generated in the current environment.
- Intended video path: `E:\minimal-agent\recordings\minimal-agent-demo.mp4`
- Recording tool: none available with reliable command-line start and graceful stop.
- Duration: not applicable.
- File size: not applicable.

## Environment and recorder audit

- Project Python: `E:\minimal-agent\.venv\Scripts\python.exe`
- Baseline tests: `74 passed`
- End-to-end demo validation: passed with real LLM calls
- Git worktree before preparation: clean
- OBS Studio: not installed in `PATH` or its standard installation locations.
- The ffmpeg bundled with Kingsoft software does not provide the Windows `gdigrab` input device.
- The ffmpeg bundled with Tencent/VALORANT recording components is application-specific and does not expose a usable `gdigrab` command-line capture path.
- Windows Xbox Game Bar and Clipchamp are installed, but neither provides a reliable command-line workflow for starting and gracefully stopping this terminal recording.
- The Windows automation capability available to this environment explicitly prohibits automating terminal applications.

Because no supported recorder could be controlled reliably, this report does not claim that a recording exists.

## Prepared demonstration

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo_recording.ps1
```

The script uses a dedicated SQLite database and Trace directory, removes only previous demo artifacts, uses the project virtual environment, and exits with a non-zero status on any failed command or verification.

It demonstrates:

1. Project and CLI information
2. Direct conversation and same-session memory
3. Calculator followed by Todo in one Agent run
4. Todo listing
5. Local mock Search
6. Same-session recovery across separate Python processes
7. Different-session isolation, verified with non-sensitive SQLite aggregate queries
8. A readable JSONL Trace projection
9. The full test suite and the expected `74 passed` summary

The fast validation run completed successfully. Its checks confirmed:

- The same session remembered the name “小明”.
- One Agent run called `calculator`, obtained `4046`, called `todo`, and returned a final answer.
- The saved Todo contained `238 * 17 = 4046`.
- A Trace contained a real `search` tool call.
- A separate Python process recovered the first session's name and Todo.
- SQLite aggregate queries found one Todo in `demo-window-1` and zero Todos in `demo-window-2`.
- The formatted multi-tool Trace included `run_started`, `context_loaded`, `llm_request`, `llm_response`, `tool_call`, `tool_result`, and `final_answer`.
- The final test run reported `74 passed`.

Default pauses are three seconds. For a fast non-recorded validation run, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo_recording.ps1 -PauseSeconds 0
```

## Video verification

Not performed because no MP4 was generated. The required checks for playable format, duration, size, visual readability, and absence of secrets remain pending until a recording tool is started manually.

The script never prints environment variables or API credentials. The operator must capture only the PowerShell demo window and must not open `.env` during recording.

## Code findings

No core Runtime defect was identified during preparation.

Two environment/script compatibility issues were handled:

- The repository's default `python` command currently resolves to `D:\miniconda\python.exe`, so the demo script explicitly invokes `E:\minimal-agent\.venv\Scripts\python.exe`.
- Windows PowerShell 5.1 misreads non-ASCII source text in a UTF-8 script without a byte-order mark. The demo's Chinese prompts are stored as UTF-8 Base64 constants and decoded only when invoked, preserving the intended terminal text without requiring a PowerShell policy or encoding change.

## Manual step required

Open any screen recorder, capture the PowerShell window at a resolution of at least 1280×720, then run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo_recording.ps1
```

Stop the recorder normally and save the result as:

```text
E:\minimal-agent\recordings\minimal-agent-demo.mp4
```
