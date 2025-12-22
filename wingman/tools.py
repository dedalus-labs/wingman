"""File and shell tools for coding assistance."""

import asyncio
import re
import select
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .checkpoints import get_checkpoint_manager, get_current_session
from .config import get_working_dir

# App instance reference (set by app module, avoids circular import)
_app_instance: Any = None

# Edit approval state
_edit_approval_event: threading.Event | None = None
_edit_approval_result: bool = False
_pending_edit: dict | None = None

# Tool approval state - tracks which tools are "always allowed"
_always_allowed_tools: set[str] = set()


def set_app_instance(app: Any) -> None:
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
        if not self.process.stdout:
            return
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
        except (OSError, ValueError):
            # Process stdout closed or select interrupted
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
_command_widget_counter: int = 0

# Track segments (text + tool calls) in order for session persistence
_current_segments: list[dict] = []


def _notify_mount(command: str, widget_id: str) -> None:
    """Mount command status widget via app (thread-safe)."""
    if _app_instance is not None:
        _app_instance.call_from_thread(_app_instance._mount_command_status, command, widget_id)


def _notify_status(widget_id: str, status: str, output: str | None = None) -> None:
    """Update command status via app (thread-safe)."""
    if _app_instance is not None:
        _app_instance.call_from_thread(_app_instance._update_command_status, widget_id, status, output)


def get_segments() -> list[dict]:
    """Get segments (text + tool calls) in order."""
    return _current_segments.copy()


def clear_segments() -> None:
    """Clear tracked segments (call before each new response)."""
    _current_segments.clear()


def add_text_segment(text: str) -> None:
    """Add or append to text segment."""
    if _current_segments and _current_segments[-1].get("type") == "text":
        _current_segments[-1]["content"] += text
    else:
        _current_segments.append({"type": "text", "content": text})


def _track_tool_call(command: str, output: str, status: str) -> None:
    """Track a tool call for session persistence."""
    _current_segments.append({
        "type": "tool",
        "command": command,
        "output": output,
        "status": status,
    })


def request_background() -> None:
    """Called when user presses Ctrl+B to background current command."""
    global _background_requested
    _background_requested = True


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


async def _update_command_status(widget_id: str, status: str, output: str | None = None) -> None:
    if _app_instance is not None:
        _app_instance._update_command_status(widget_id, status, output)
        await asyncio.sleep(0)


def read_file(path: str) -> str:
    """Read the contents of a file."""
    global _command_widget_counter
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = get_working_dir() / file_path

    _command_widget_counter += 1
    widget_id = f"cmd-status-{_command_widget_counter}"
    display_path = path if len(path) <= 40 else "..." + path[-37:]
    command = f"read {display_path}"
    _notify_mount(command, widget_id)

    if not file_path.exists():
        output = f"Error: File not found: {path}"
        _notify_status(widget_id, "error")
        _track_tool_call(command, output, "error")
        return output
    if not file_path.is_file():
        output = f"Error: Not a file: {path}"
        _notify_status(widget_id, "error")
        _track_tool_call(command, output, "error")
        return output
    try:
        content = file_path.read_text()
        lines = content.split('\n')
        numbered = '\n'.join(f"{i+1:4}│ {line}" for i, line in enumerate(lines))
        output_preview = f"{len(lines)} lines"
        _notify_status(widget_id, "success", output_preview)
        _track_tool_call(command, output_preview, "success")
        return numbered
    except (OSError, UnicodeDecodeError) as e:
        output = f"Error reading file: {e}"
        _notify_status(widget_id, "error", str(e))
        _track_tool_call(command, output, "error")
        return output


def write_file(path: str, content: str) -> str:
    """Create a new file with the given content."""
    global _command_widget_counter
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = get_working_dir() / file_path

    _command_widget_counter += 1
    widget_id = f"cmd-status-{_command_widget_counter}"
    display_path = path if len(path) <= 40 else "..." + path[-37:]
    command = f"write {display_path}"
    _notify_mount(command, widget_id)

    if file_path.exists():
        output = f"Error: File already exists: {path}. Use edit_file to modify existing files."
        _notify_status(widget_id, "error")
        _track_tool_call(command, output, "error")
        return output
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        lines = len(content.split('\n'))
        output_preview = f"Created ({lines} lines)"
        _notify_status(widget_id, "success", output_preview)
        _track_tool_call(command, output_preview, "success")
        return f"Created: {path}"
    except OSError as e:
        output = f"Error writing file: {e}"
        _notify_status(widget_id, "error", str(e))
        _track_tool_call(command, output, "error")
        return output


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Edit a file by replacing old_string with new_string."""
    global _edit_approval_event, _edit_approval_result, _pending_edit, _command_widget_counter

    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = get_working_dir() / file_path

    _command_widget_counter += 1
    widget_id = f"cmd-status-{_command_widget_counter}"
    display_path = path if len(path) <= 40 else "..." + path[-37:]
    command = f"edit {display_path}"
    _notify_mount(command, widget_id)

    if not file_path.exists():
        output = f"Error: File not found: {path}"
        _notify_status(widget_id, "error")
        _track_tool_call(command, output, "error")
        return output

    try:
        content = file_path.read_text()
        if old_string not in content:
            output = f"Error: old_string not found in {path}. Read the file first to see exact content."
            _notify_status(widget_id, "error")
            _track_tool_call(command, output, "error")
            return output
        if content.count(old_string) > 1:
            output = f"Error: old_string appears multiple times. Be more specific."
            _notify_status(widget_id, "error")
            _track_tool_call(command, output, "error")
            return output

        # Request user approval via diff modal
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
                output = f"Edit rejected by user: {path}"
                _notify_status(widget_id, "error")
                _track_tool_call(command, output, "error")
                return output

        cp_manager = get_checkpoint_manager()
        cp = cp_manager.create([file_path], f"Before edit: {file_path.name}", session_id=get_current_session())

        new_content = content.replace(old_string, new_string, 1)
        file_path.write_text(new_content)

        cp_note = f" (checkpoint: {cp.id})" if cp else ""
        result = f"Edited: {path}{cp_note}"
        _notify_status(widget_id, "success", "edited")
        _track_tool_call(command, "edited", "success")
        return result
    except OSError as e:
        output = f"Error editing file: {e}"
        _notify_status(widget_id, "error", str(e))
        _track_tool_call(command, str(e), "error")
        return output


def _list_files_sync(pattern: str, base: Path, working_dir: Path) -> list[str]:
    """Synchronous file listing - runs in thread pool."""
    ignore = {
        '.git', 'node_modules', '__pycache__', '.venv', 'venv', '.idea',
        '.cache', 'dist', 'build', '.next', '.nuxt', 'coverage',
    }
    results = []
    max_files = 5000
    checked = 0
    for p in base.glob(pattern):
        checked += 1
        if checked > max_files:
            break
        if p.is_file() and not any(part in ignore for part in p.parts):
            results.append(str(p.relative_to(working_dir)))
            if len(results) >= 100:
                break
    return sorted(results)


async def list_files(pattern: str = "**/*", path: str = ".") -> str:
    """List files matching a glob pattern."""
    command = f"ls {pattern}"
    widget_id = await _show_command_widget(command)
    base = Path(path)
    if not base.is_absolute():
        base = get_working_dir() / base
    try:
        filtered = await asyncio.wait_for(
            asyncio.to_thread(_list_files_sync, pattern, base, get_working_dir()),
            timeout=15.0
        )
        result = '\n'.join(filtered) if filtered else f"No files matching: {pattern}"
        await _update_command_status(widget_id, "success", result)
        _track_tool_call(command, result, "success")
        return result
    except asyncio.TimeoutError:
        output = "Timed out after 15s"
        await _update_command_status(widget_id, "error", output)
        _track_tool_call(command, output, "error")
        return f"Listing timed out after 15s. Try a more specific pattern."
    except Exception as e:
        output = str(e)
        await _update_command_status(widget_id, "error", output)
        _track_tool_call(command, output, "error")
        return f"Error listing files: {e}"


def _search_files_sync(pattern: str, base: Path, file_pattern: str, working_dir: Path) -> list[str]:
    """Synchronous file search - runs in thread pool."""
    regex = re.compile(pattern, re.IGNORECASE)
    results = []
    ignore = {
        '.git', 'node_modules', '__pycache__', '.venv', 'venv',
        '.cache', 'dist', 'build', '.next', '.nuxt', 'coverage',
        '.tox', '.eggs', '*.egg-info', '.mypy_cache', '.pytest_cache',
    }
    max_file_size = 1_000_000  # 1MB limit
    files_checked = 0
    max_files = 5000

    for file_path in base.rglob(file_pattern):
        files_checked += 1
        if files_checked > max_files:
            results.append(f"... (stopped after {max_files} files)")
            break
        if not file_path.is_file():
            continue
        if any(part in ignore for part in file_path.parts):
            continue
        try:
            if file_path.stat().st_size > max_file_size:
                continue
            content = file_path.read_text()
            for i, line in enumerate(content.split('\n'), 1):
                if regex.search(line):
                    rel_path = file_path.relative_to(working_dir)
                    results.append(f"{rel_path}:{i}: {line.strip()}")
                    if len(results) >= 50:
                        results.append("... (truncated)")
                        return results
        except (UnicodeDecodeError, PermissionError, OSError):
            continue
    return results


async def search_files(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """Search for a regex pattern in files."""
    command = f"grep \"{pattern}\""
    widget_id = await _show_command_widget(command)
    base = Path(path)
    if not base.is_absolute():
        base = get_working_dir() / base
    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_search_files_sync, pattern, base, file_pattern, get_working_dir()),
            timeout=30.0
        )
        result = '\n'.join(results) if results else f"No matches for: {pattern}"
        await _update_command_status(widget_id, "success", result)
        _track_tool_call(command, result, "success")
        return result
    except asyncio.TimeoutError:
        output = "Timed out after 30s"
        await _update_command_status(widget_id, "error", output)
        _track_tool_call(command, output, "error")
        return f"Search timed out after 30s. Try a more specific path or pattern."
    except re.error as e:
        output = f"Invalid regex: {e}"
        await _update_command_status(widget_id, "error", output)
        _track_tool_call(command, output, "error")
        return output
    except Exception as e:
        output = str(e)
        await _update_command_status(widget_id, "error", output)
        _track_tool_call(command, output, "error")
        return f"Error searching: {e}"


async def run_command(command: str) -> str:
    """Run a shell command and return the output."""
    global _background_requested, _next_bg_id

    if not await request_tool_approval("run_command", f"$ {command}"):
        _track_tool_call(f"$ {command}", "rejected by user", "error")
        return "Command rejected by user."

    _background_requested = False
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
                _track_tool_call(f"$ {command}", "backgrounded", "success")
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
                output = "".join(output_lines[-50:])
                await _update_command_status(widget_id, "error", f"Timed out after {timeout}s")
                _track_tool_call(f"$ {command}", f"Timed out after {timeout}s", "error")
                return f"Error: Command timed out after {timeout}s\n" + output

        output = "".join(output_lines)
        if len(output) > 10000:
            output = output[:10000] + "\n... (truncated)"

        status = "success" if proc.returncode == 0 else "error"
        output_display = output or "(no output)"
        await _update_command_status(widget_id, status, output_display)
        _track_tool_call(f"$ {command}", output_display, status)
        return output_display

    except Exception as e:
        await _update_command_status(widget_id, "error", str(e))
        _track_tool_call(f"$ {command}", str(e), "error")
        return f"Error running command: {e}"


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
4. If you're unsure, ask the user
5. For long-running commands, the user may background them with Ctrl+B

## IMPORTANT: Think Out Loud
BEFORE calling any tool, briefly explain what you're about to do and why. For example:
- "I'll search for files containing 'server'..."
- "Let me read the config file to understand the structure..."
- "I'll run the tests to check if the fix works..."

This helps the user follow along with your reasoning. Don't just silently call tools.

## Background Processes
When a command is backgrounded, you'll see "[Backgrounded: bg_X]". Use get_process_output('bg_X') to check its output later.

## Working Directory
{cwd}
"""
