"""File and shell tools for coding assistance."""

import asyncio
import re
import select
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .checkpoints import get_checkpoint_manager, get_current_session
from .config import get_working_dir

# App instance reference (set by app module)
_app_instance = None

# Edit approval state
_edit_approval_event: threading.Event | None = None
_edit_approval_result: bool = False
_pending_edit: dict | None = None

# Tool approval state - tracks which tools are "always allowed"
_always_allowed_tools: set[str] = set()


def set_app_instance(app) -> None:
    """Set the app instance for UI interactions."""
    global _app_instance
    _app_instance = app


def get_pending_edit() -> dict | None:
    """Get pending edit for approval."""
    return _pending_edit


def set_edit_result(result: bool) -> None:
    """Set edit approval result."""
    global _edit_approval_result
    _edit_approval_result = result
    if _edit_approval_event:
        _edit_approval_event.set()


async def request_tool_approval(tool_name: str, command: str) -> bool:
    """Request approval for a tool. Returns True if approved."""
    if tool_name in _always_allowed_tools:
        return True
    if _app_instance is None:
        return True
    result = await _app_instance.request_tool_approval(tool_name, command)
    if result == "always":
        _always_allowed_tools.add(tool_name)
        return True
    return result == "yes"


@dataclass
class BackgroundProcess:
    """Tracks a backgrounded shell process."""
    pid: int
    command: str
    process: subprocess.Popen
    output_buffer: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def read_output(self) -> None:
        if self.process.stdout:
            try:
                while True:
                    ready, _, _ = select.select([self.process.stdout], [], [], 0)
                    if not ready:
                        break
                    line = self.process.stdout.readline()
                    if not line:
                        break
                    self.output_buffer.append(line)
                    if len(self.output_buffer) > 1000:
                        self.output_buffer = self.output_buffer[-500:]
            except Exception:
                pass

    def get_recent_output(self, lines: int = 50) -> str:
        self.read_output()
        recent = self.output_buffer[-lines:] if self.output_buffer else []
        return "".join(recent) or "(no output yet)"

    def is_running(self) -> bool:
        return self.process.poll() is None


_background_processes: dict[str, BackgroundProcess] = {}
_next_bg_id: int = 1
_background_requested: bool = False
_current_command: str | None = None
_command_widget_counter: int = 0


def request_background() -> None:
    """Called when user presses Ctrl+B to background current command."""
    global _background_requested
    _background_requested = True


def get_current_command() -> str | None:
    return _current_command


def get_background_processes() -> dict[str, BackgroundProcess]:
    return _background_processes


async def _show_command_widget(command: str) -> str:
    global _command_widget_counter
    _command_widget_counter += 1
    widget_id = f"cmd-status-{_command_widget_counter}"
    if _app_instance is not None:
        _app_instance._mount_command_status(command, widget_id)
        await asyncio.sleep(0)
    return widget_id


async def _update_command_status(widget_id: str, status: str) -> None:
    if _app_instance is not None:
        _app_instance._update_command_status(widget_id, status)
        await asyncio.sleep(0)


def read_file(path: str) -> str:
    """Read the contents of a file."""
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = get_working_dir() / file_path
    if not file_path.exists():
        return f"Error: File not found: {path}"
    if not file_path.is_file():
        return f"Error: Not a file: {path}"
    try:
        content = file_path.read_text()
        lines = content.split('\n')
        numbered = '\n'.join(f"{i+1:4}│ {line}" for i, line in enumerate(lines))
        return numbered
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Create a new file with the given content."""
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = get_working_dir() / file_path
    if file_path.exists():
        return f"Error: File already exists: {path}. Use edit_file to modify existing files."
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return f"Created: {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Edit a file by replacing old_string with new_string."""
    global _edit_approval_event, _edit_approval_result, _pending_edit

    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = get_working_dir() / file_path
    if not file_path.exists():
        return f"Error: File not found: {path}"
    try:
        content = file_path.read_text()
        if old_string not in content:
            return f"Error: old_string not found in {path}. Read the file first to see exact content."
        if content.count(old_string) > 1:
            return f"Error: old_string appears multiple times. Be more specific."

        if _app_instance is not None:
            _edit_approval_event = threading.Event()
            _pending_edit = {
                "path": str(file_path),
                "old_string": old_string,
                "new_string": new_string,
            }
            _app_instance.call_from_thread(_app_instance.show_diff_approval)
            _edit_approval_event.wait()

            if not _edit_approval_result:
                return f"Edit rejected by user: {path}"

        cp_manager = get_checkpoint_manager()
        cp = cp_manager.create([file_path], f"Before edit: {file_path.name}", session_id=get_current_session())

        new_content = content.replace(old_string, new_string, 1)
        file_path.write_text(new_content)

        cp_note = f" (checkpoint: {cp.id})" if cp else ""
        return f"Edited: {path}{cp_note}"
    except Exception as e:
        return f"Error editing file: {e}"


async def list_files(pattern: str = "**/*", path: str = ".") -> str:
    """List files matching a glob pattern."""
    if not await request_tool_approval("list_files", f"ls {pattern}"):
        return "Command rejected by user."
    widget_id = await _show_command_widget(f"ls {pattern}")
    base = Path(path)
    if not base.is_absolute():
        base = get_working_dir() / base
    try:
        matches = sorted(base.glob(pattern))
        ignore = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.idea'}
        filtered = [
            str(p.relative_to(get_working_dir())) for p in matches
            if p.is_file() and not any(part in ignore for part in p.parts)
        ]
        await _update_command_status(widget_id, "success")
        if not filtered:
            return f"No files matching: {pattern}"
        return '\n'.join(filtered[:100])
    except Exception as e:
        await _update_command_status(widget_id, "error")
        return f"Error listing files: {e}"


async def search_files(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """Search for a regex pattern in files."""
    if not await request_tool_approval("search_files", f"grep \"{pattern}\""):
        return "Command rejected by user."
    widget_id = await _show_command_widget(f"grep \"{pattern}\"")
    base = Path(path)
    if not base.is_absolute():
        base = get_working_dir() / base
    try:
        regex = re.compile(pattern, re.IGNORECASE)
        results = []
        ignore = {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}

        for file_path in base.rglob(file_pattern):
            if not file_path.is_file():
                continue
            if any(part in ignore for part in file_path.parts):
                continue
            try:
                content = file_path.read_text()
                for i, line in enumerate(content.split('\n'), 1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(get_working_dir())
                        results.append(f"{rel_path}:{i}: {line.strip()}")
            except (UnicodeDecodeError, PermissionError):
                continue

            if len(results) >= 50:
                results.append("... (truncated)")
                break

        await _update_command_status(widget_id, "success")
        if not results:
            return f"No matches for: {pattern}"
        return '\n'.join(results)
    except re.error as e:
        await _update_command_status(widget_id, "error")
        return f"Invalid regex: {e}"
    except Exception as e:
        await _update_command_status(widget_id, "error")
        return f"Error searching: {e}"


async def run_command(command: str) -> str:
    """Run a shell command and return the output."""
    global _background_requested, _next_bg_id, _current_command

    if not await request_tool_approval("run_command", f"$ {command}"):
        return "Command rejected by user."

    _background_requested = False
    _current_command = command

    widget_id = await _show_command_widget(command)

    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=get_working_dir(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        output_lines = []
        start_time = time.time()
        timeout = 120

        while True:
            await asyncio.sleep(0.05)

            if _background_requested:
                _background_requested = False
                bg_id = f"bg_{_next_bg_id}"
                _next_bg_id += 1

                bg_proc = BackgroundProcess(
                    pid=proc.pid,
                    command=command,
                    process=proc,
                    output_buffer=output_lines.copy(),
                )
                _background_processes[bg_id] = bg_proc

                await _update_command_status(widget_id, "backgrounded")
                return f"[Backgrounded: {bg_id}] {command}\nUse get_process_output('{bg_id}') to check status."

            if proc.poll() is not None:
                remaining = proc.stdout.read() if proc.stdout else ""
                if remaining:
                    output_lines.append(remaining)
                break

            if proc.stdout:
                ready, _, _ = select.select([proc.stdout], [], [], 0)
                if ready:
                    line = proc.stdout.readline()
                    if line:
                        output_lines.append(line)

            if time.time() - start_time > timeout:
                proc.terminate()
                await _update_command_status(widget_id, "error")
                return f"Error: Command timed out after {timeout}s\n" + "".join(output_lines[-50:])

        output = "".join(output_lines)
        if len(output) > 10000:
            output = output[:10000] + "\n... (truncated)"

        status = "success" if proc.returncode == 0 else "error"
        await _update_command_status(widget_id, status)
        return output or "(no output)"

    except Exception as e:
        await _update_command_status(widget_id, "error")
        return f"Error running command: {e}"

    finally:
        _current_command = None


def get_process_output(process_id: str, lines: int = 50) -> str:
    """Get recent output from a background process."""
    if process_id not in _background_processes:
        return f"Error: No process with ID {process_id}. Use list_processes() to see running processes."

    proc = _background_processes[process_id]
    status = "running" if proc.is_running() else "stopped"
    output = proc.get_recent_output(lines)

    return f"[{process_id}] {proc.command} ({status})\n\n{output}"


def stop_process(process_id: str) -> str:
    """Stop a background process."""
    if process_id not in _background_processes:
        return f"Error: No process with ID {process_id}"

    proc = _background_processes[process_id]
    if proc.is_running():
        proc.process.terminate()
        try:
            proc.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.process.kill()

    del _background_processes[process_id]
    return f"Stopped: {proc.command}"


def list_processes() -> str:
    """List all background processes."""
    if not _background_processes:
        return "No background processes running"

    lines = []
    for pid, proc in _background_processes.items():
        status = "running" if proc.is_running() else "stopped"
        elapsed = int(time.time() - proc.started_at)
        lines.append(f"[{pid}] {proc.command} ({status}, {elapsed}s)")

    return "\n".join(lines)


FILE_TOOLS = [
    read_file, write_file, edit_file, list_files, search_files,
    run_command, get_process_output, stop_process, list_processes
]

CODING_SYSTEM_PROMPT = """You are Wingman, an AI coding assistant. You help users with their codebase.

## Tools Available
- read_file: Read file contents (ALWAYS do this before editing)
- edit_file: Modify existing files (old_string must match exactly)
- write_file: Create new files only
- list_files: Find files with glob patterns
- search_files: Search file contents with regex
- run_command: Execute shell commands (user can press Ctrl+B to background)
- get_process_output: Check output from backgrounded processes
- stop_process: Stop a background process
- list_processes: See all background processes

## Rules
1. ALWAYS read a file before editing it
2. Use list_files or search_files to discover code structure
3. Make minimal, focused edits
4. Explain what you're doing
5. If you're unsure, ask the user
6. For long-running commands, the user may background them with Ctrl+B

## Background Processes
When a command is backgrounded, you'll see "[Backgrounded: bg_X]". Use get_process_output('bg_X') to check its output later.

## Working Directory
{cwd}
"""
