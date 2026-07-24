[CmdletBinding()]
param(
    [ValidateRange(0, 10)]
    [int]$PauseSeconds = 3
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ($null -ne $Host.UI.RawUI) {
    $Host.UI.RawUI.WindowTitle = "Minimal Agent Runtime Demo"
}

[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$DemoDatabase = Join-Path $RepoRoot "data\demo_recording.db"
$DemoTraces = Join-Path $RepoRoot "traces\demo_recording"
$Recordings = Join-Path $RepoRoot "recordings"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project Python was not found: $Python"
}

$env:AGENT_DATABASE_PATH = "data/demo_recording.db"
$env:AGENT_TRACES_DIR = "traces/demo_recording"
$env:PYTHONIOENCODING = "utf-8"

function Write-Section {
    param(
        [Parameter(Mandatory)]
        [string]$Title
    )

    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host ("=" * 78) -ForegroundColor Cyan
}

function Wait-Demo {
    if ($PauseSeconds -gt 0) {
        Start-Sleep -Seconds $PauseSeconds
    }
}

function ConvertFrom-Utf8Base64 {
    param(
        [Parameter(Mandatory)]
        [string]$Value
    )

    return [System.Text.Encoding]::UTF8.GetString(
        [System.Convert]::FromBase64String($Value)
    )
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory)]
        [string]$DisplayCommand,

        [Parameter(Mandatory)]
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host ("PS> " + $DisplayCommand) -ForegroundColor Yellow
    & $Command

    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $DisplayCommand"
    }
}

function Invoke-Agent {
    param(
        [Parameter(Mandatory)]
        [string]$Message,

        [Parameter(Mandatory)]
        [string]$Session
    )

    $display = 'python -m minimal_agent.cli run "{0}" --user demo-user --session {1} --show-trace' -f $Message, $Session
    Invoke-NativeChecked -DisplayCommand $display -Command {
        & $Python -m minimal_agent.cli run $Message `
            --user demo-user `
            --session $Session `
            --show-trace
    }
    Wait-Demo
}

function Get-TraceRecords {
    param(
        [Parameter(Mandatory)]
        [System.IO.FileInfo]$TraceFile
    )

    foreach ($line in Get-Content -LiteralPath $TraceFile.FullName -Encoding utf8) {
        if (-not [string]::IsNullOrWhiteSpace($line)) {
            $line | ConvertFrom-Json
        }
    }
}

function Find-MultiToolTrace {
    $traceFiles = Get-ChildItem -LiteralPath $DemoTraces -Filter "*.jsonl" -File |
        Sort-Object LastWriteTime -Descending

    foreach ($traceFile in $traceFiles) {
        $records = @(Get-TraceRecords -TraceFile $traceFile)
        $toolNames = @(
            $records |
                Where-Object { $_.event -eq "tool_call" } |
                ForEach-Object { $_.payload.tool_name }
        )

        if (
            $toolNames -contains "calculator" -and
            $toolNames -contains "todo"
        ) {
            return $traceFile
        }
    }

    throw "No trace containing both calculator and todo tool calls was found."
}

function Assert-DemoTraces {
    param(
        [Parameter(Mandatory)]
        [System.IO.FileInfo]$MultiToolTrace
    )

    $records = @(Get-TraceRecords -TraceFile $MultiToolTrace)
    $events = @($records | ForEach-Object { $_.event })
    $requiredEvents = @(
        "run_started",
        "context_loaded",
        "llm_request",
        "llm_response",
        "tool_call",
        "tool_result",
        "final_answer"
    )

    foreach ($eventName in $requiredEvents) {
        if ($events -notcontains $eventName) {
            throw "Required trace event is missing: $eventName"
        }
    }

    $failedToolResult = $records |
        Where-Object {
            $_.event -eq "tool_result" -and
            $_.payload.success -ne $true
        } |
        Select-Object -First 1

    if ($null -ne $failedToolResult) {
        throw "The multi-tool trace contains a failed tool result."
    }

    $searchTraceFound = $false
    foreach ($traceFile in Get-ChildItem -LiteralPath $DemoTraces -Filter "*.jsonl" -File) {
        $hasSearch = Get-TraceRecords -TraceFile $traceFile |
            Where-Object {
                $_.event -eq "tool_call" -and
                $_.payload.tool_name -eq "search"
            } |
            Select-Object -First 1

        if ($null -ne $hasSearch) {
            $searchTraceFound = $true
            break
        }
    }

    if (-not $searchTraceFound) {
        throw "No trace containing a real local search tool call was found."
    }
}

function Show-FormattedTrace {
    param(
        [Parameter(Mandatory)]
        [System.IO.FileInfo]$TraceFile
    )

    Write-Host ""
    Write-Host ("Formatted trace: " + $TraceFile.Name) -ForegroundColor Green
    Write-Host "Fields: timestamp | event | step | tool_name | success | answer"

    Get-TraceRecords -TraceFile $TraceFile |
        ForEach-Object {
            $toolName = if ($null -ne $_.payload.tool_name) {
                [string]$_.payload.tool_name
            } else {
                ""
            }

            $success = if ($null -ne $_.payload.success) {
                [string]$_.payload.success
            } else {
                ""
            }

            $answer = if ($null -ne $_.payload.answer) {
                [string]$_.payload.answer
            } else {
                ""
            }

            if ($answer.Length -gt 100) {
                $answer = $answer.Substring(0, 100) + "..."
            }

            [PSCustomObject]@{
                timestamp = $_.timestamp
                event = $_.event
                step = $_.step
                tool_name = $toolName
                success = $success
                answer = $answer
            }
        } |
        Format-Table -AutoSize -Wrap
}

try {
    New-Item -ItemType Directory -Path (Split-Path $DemoDatabase -Parent) -Force | Out-Null
    New-Item -ItemType Directory -Path $Recordings -Force | Out-Null

    if (Test-Path -LiteralPath $DemoDatabase) {
        Remove-Item -LiteralPath $DemoDatabase -Force
    }

    if (Test-Path -LiteralPath $DemoTraces) {
        Remove-Item -LiteralPath $DemoTraces -Recurse -Force
    }

    New-Item -ItemType Directory -Path $DemoTraces -Force | Out-Null

    Write-Section "1. Project information"
    Write-Host "Minimal Agent Runtime Demo" -ForegroundColor Green
    Write-Host "Repository: https://github.com/johusa-wsw/minimal-agent-runtime"
    Write-Host ("Python: " + $Python)
    Invoke-NativeChecked -DisplayCommand "python -m minimal_agent.cli --help" -Command {
        & $Python -m minimal_agent.cli --help
    }
    Wait-Demo

    Write-Section "2. Direct conversation and session memory"
    Write-Host "user = demo-user"
    Write-Host "session = demo-window-1"
    $rememberName = ConvertFrom-Utf8Base64 "5oiR5Y+r5bCP5piO77yM6K+36K6w5L2P44CC"
    $askName = ConvertFrom-Utf8Base64 "5oiR5Y+r5LuA5LmI77yf"
    Invoke-Agent -Message $rememberName -Session "demo-window-1"
    Invoke-Agent -Message $askName -Session "demo-window-1"

    Write-Section "3. Calculator to Todo: consecutive tool calls"
    $calculateAndSave = ConvertFrom-Utf8Base64 "6K+36K6h566XMjM45LmYMTfvvIzlubbmiornu5Pmnpzku6XigJwyMzggKiAxNyA9IDQwNDbigJ3liqDlhaXlvoXlip7jgII="
    $listTodos = ConvertFrom-Utf8Base64 "5p+l55yL5oiR55qE5b6F5Yqe44CC"
    Invoke-Agent -Message $calculateAndSave -Session "demo-window-1"
    Invoke-Agent -Message $listTodos -Session "demo-window-1"

    Write-Section "4. Local mock Search tool"
    $searchAgentRuntime = ConvertFrom-Utf8Base64 "5biu5oiR5pCc57SiIEFnZW50IFJ1bnRpbWUg5piv5LuA5LmI44CC"
    Invoke-Agent -Message $searchAgentRuntime -Session "demo-window-1"

    Write-Section "5. Session recovery in a new process"
    Write-Host "Starting a new process with the same user_id and session_id..." -ForegroundColor Green
    $recallSession = ConvertFrom-Utf8Base64 "5oiR5Y+r5LuA5LmI77yf6K+35ZCM5pe25ZGK6K+J5oiR5LmL5YmN6K6w5b2V5LqG5LuA5LmI5b6F5Yqe44CC"
    Invoke-Agent -Message $recallSession -Session "demo-window-1"

    Write-Section "6. Isolation between two windows"
    Write-Host "Using a new session: demo-window-2"
    Invoke-Agent -Message $askName -Session "demo-window-2"
    Invoke-Agent -Message $listTodos -Session "demo-window-2"

    $verificationScript = Join-Path $RepoRoot "scripts\verify_demo_state.py"
    Invoke-NativeChecked -DisplayCommand "python scripts\verify_demo_state.py data\demo_recording.db" -Command {
        & $Python $verificationScript $DemoDatabase
    }
    Write-Host "window-1 and window-2 are isolated." -ForegroundColor Green
    Wait-Demo

    Write-Section "7. JSONL Trace"
    Write-Host "Three newest trace files:"
    Get-ChildItem -LiteralPath $DemoTraces -Filter "*.jsonl" -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 3 Name, LastWriteTime, Length |
        Format-Table -AutoSize

    $multiToolTrace = Find-MultiToolTrace
    Assert-DemoTraces -MultiToolTrace $multiToolTrace
    Show-FormattedTrace -TraceFile $multiToolTrace
    Write-Host "Trace verification: PASS" -ForegroundColor Green
    Wait-Demo

    Write-Section "8. Full test suite"
    Write-Host ""
    Write-Host "PS> python -m pytest -q" -ForegroundColor Yellow
    $testOutput = @(& $Python -m pytest -q 2>&1)

    foreach ($line in $testOutput) {
        Write-Host $line
    }

    if ($LASTEXITCODE -ne 0) {
        throw "The full test suite failed with exit code $LASTEXITCODE."
    }

    $testText = $testOutput -join [Environment]::NewLine
    if ($testText -notmatch "74 passed") {
        throw "The test suite passed, but the expected '74 passed' summary was not found."
    }

    Write-Host ""
    Write-Host "All demo checks completed successfully." -ForegroundColor Green
    Write-Host "74 passed" -ForegroundColor Green
    Wait-Demo
}
catch {
    Write-Host ""
    Write-Host ("DEMO FAILED: " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}

exit 0
