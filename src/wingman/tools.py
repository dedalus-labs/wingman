"""File and shell tools for coding assistance."""

import asyncio
import json
import select
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .checkpoints import get_checkpoint_manager, get_current_session

# Filesystem traversal limits
IGNORED_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".idea",
        ".cache",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        ".tox",
        ".eggs",
        ".mypy_cache",
        ".pytest_cache",
    }
)
MAX_FILES_TO_SCAN = 5000
MAX_FILE_SIZE = 1_000_000
MAX_LIST_RESULTS = 100
MAX_SEARCH_RESULTS = 50
CONTENT_TRUNCATE_LIMIT = 8000
DEFAULT_READ_LINES = 2000
MAX_LINE_LENGTH = 2000

# App instance reference (set by app module, avoids circular import)
_app_instance: Any = None

# Edit approval state
_edit_approval_event: threading.Event | None = None
_edit_approval_result: bool = False
_pending_edit: dict | None = None

# Tool approval state - tracks which tools are "always allowed" per panel
_panel_allowed_tools: dict[str, set[str]] = {}


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


async def request_tool_approval(tool_name: str, command: str, panel_id: str | None = None) -> tuple[bool, str]:
    """Request approval for a tool. Returns (approved, feedback)."""
    allowed = _panel_allowed_tools.get(panel_id, set()) if panel_id else set()
    if tool_name in allowed:
        return (True, "")
    if _app_instance is None:
        return (True, "")
    result, feedback = await _app_instance.request_tool_approval(tool_name, command, panel_id)
    if result == "cancelled":
        return (False, "Operation cancelled")
    if result == "always":
        if panel_id:
            if panel_id not in _panel_allowed_tools:
                _panel_allowed_tools[panel_id] = set()
            _panel_allowed_tools[panel_id].add(tool_name)
        return (True, "")
    if result == "no":
        return (False, feedback)
    return (True, "")


@dataclass
class BackgroundProcess:
    """Tracks a backgrounded shell process."""

    pid: int
    command: str
    process: subprocess.Popen
    output_buffer: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    notified: bool = False  # Whether completion notification was shown

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


# Background processes per panel
_panel_background_processes: dict[str, dict[str, BackgroundProcess]] = {}
_next_bg_id: int = 1
_background_requested: dict[str, bool] = {}  # Per-panel background request flags
_command_widget_counter: int = 0

# Track segments (text + tool calls) per panel for session persistence
_panel_segments: dict[str, list[dict]] = {}


def _notify_mount(command: str, widget_id: str, panel_id: str | None = None) -> None:
    """Mount command status widget via app (thread-safe)."""
    if _app_instance is not None:
        if threading.current_thread() == threading.main_thread():
            _app_instance._mount_command_status(command, widget_id, panel_id)
        else:
            _app_instance.call_from_thread(_app_instance._mount_command_status, command, widget_id, panel_id)


def _notify_status(widget_id: str, status: str, output: str | None = None, panel_id: str | None = None) -> None:
    """Update command status via app (thread-safe)."""
    if _app_instance is not None:
        if threading.current_thread() == threading.main_thread():
            _app_instance._update_command_status(widget_id, status, output, panel_id)
        else:
            _app_instance.call_from_thread(_app_instance._update_command_status, widget_id, status, output, panel_id)


def _update_thinking(status: str | None, panel_id: str | None = None) -> None:
    """Update the Thinking spinner status (thread-safe)."""
    if _app_instance is not None:
        if threading.current_thread() == threading.main_thread():
            _app_instance._update_thinking_status(status, panel_id)
        else:
            _app_instance.call_from_thread(_app_instance._update_thinking_status, status, panel_id)


def get_segments(panel_id: str | None = None) -> list[dict]:
    """Get segments (text + tool calls) for a panel."""
    if not panel_id:
        return []
    return _panel_segments.get(panel_id, []).copy()


def clear_segments(panel_id: str | None = None) -> None:
    """Clear tracked segments for a panel."""
    if panel_id:
        _panel_segments[panel_id] = []


def add_text_segment(text: str, panel_id: str | None = None) -> None:
    """Add or append to text segment for a panel."""
    if not panel_id:
        return
    if panel_id not in _panel_segments:
        _panel_segments[panel_id] = []
    segments = _panel_segments[panel_id]
    if segments and segments[-1].get("type") == "text":
        segments[-1]["content"] += text
    else:
        segments.append({"type": "text", "content": text})


def _track_tool_call(command: str, output: str, status: str, panel_id: str | None = None) -> None:
    """Track a tool call for session persistence."""
    if not panel_id:
        return
    if panel_id not in _panel_segments:
        _panel_segments[panel_id] = []
    _panel_segments[panel_id].append(
        {
            "type": "tool",
            "command": command,
            "output": output,
            "status": status,
        }
    )


def request_background(panel_id: str | None = None) -> None:
    """Called when user presses Ctrl+B to background current command."""
    if panel_id:
        _background_requested[panel_id] = True


def get_background_processes(panel_id: str | None = None) -> dict[str, BackgroundProcess]:
    """Get background processes for a panel."""
    if not panel_id:
        return {}
    return _panel_background_processes.get(panel_id, {})


def check_completed_processes() -> list[tuple[str, str, int, str]]:
    """Check for completed background processes that haven't been notified.

    Returns list of (panel_id, bg_id, exit_code, command) for newly completed processes.
    """
    completed = []
    for panel_id, processes in _panel_background_processes.items():
        for bg_id, proc in processes.items():
            if not proc.is_running() and not proc.notified:
                proc.notified = True
                proc.read_output()  # Capture final output
                exit_code = proc.process.returncode or 0
                completed.append((panel_id, bg_id, exit_code, proc.command))
    return completed


async def _show_command_widget(command: str, panel_id: str | None = None) -> str:
    global _command_widget_counter
    _command_widget_counter += 1
    widget_id = f"cmd-status-{_command_widget_counter}"
    if _app_instance is not None:
        _app_instance._mount_command_status(command, widget_id, panel_id)
        await asyncio.sleep(0)
    return widget_id


async def _update_command_status(
    widget_id: str, status: str, output: str | None = None, panel_id: str | None = None
) -> None:
    if _app_instance is not None:
        _app_instance._update_command_status(widget_id, status, output, panel_id)
        await asyncio.sleep(0)


def _read_file_impl(
    path: str, working_dir: Path, panel_id: str | None = None, offset: int | None = None, limit: int | None = None
) -> str:
    """Read file contents with optional line range."""
    global _command_widget_counter
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = working_dir / file_path
    file_path = file_path.resolve()

    _command_widget_counter += 1
    widget_id = f"cmd-status-{_command_widget_counter}"
    display_path = path if len(path) <= 40 else "..." + path[-37:]
    command = f"read {display_path}"
    _notify_mount(command, widget_id, panel_id)

    if not file_path.exists():
        output = f"Error: File not found: {file_path}"
        _notify_status(widget_id, "error", panel_id=panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output
    if not file_path.is_file():
        output = f"Error: Not a file: {file_path}"
        _notify_status(widget_id, "error", panel_id=panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output
    try:
        content = file_path.read_text()
        all_lines = content.split("\n")
        total_lines = len(all_lines)

        # Apply offset and limit (1-indexed like line numbers)
        start = (offset - 1) if offset and offset > 0 else 0
        end = (start + limit) if limit else (start + DEFAULT_READ_LINES)
        lines = all_lines[start:end]

        # Truncate long lines and format with line numbers
        formatted = []
        for i, line in enumerate(lines, start=start + 1):
            if len(line) > MAX_LINE_LENGTH:
                line = line[:MAX_LINE_LENGTH] + "..."
            formatted.append(f"{i:4}│ {line}")
        numbered = "\n".join(formatted)

        # Add truncation notice if applicable
        lines_shown = len(lines)
        was_truncated = end < total_lines
        if was_truncated:
            numbered += f"\n\n[Showing lines {start + 1}-{start + lines_shown} of {total_lines}. Use offset/limit to read more.]"

        output_preview = f"{lines_shown}/{total_lines} lines" if was_truncated else f"{total_lines} lines"
        _notify_status(widget_id, "success", output_preview, panel_id)
        tracked = (
            numbered
            if len(numbered) < CONTENT_TRUNCATE_LIMIT
            else numbered[:CONTENT_TRUNCATE_LIMIT] + "\n...[truncated]"
        )
        _track_tool_call(command, tracked, "success", panel_id)
        return numbered
    except (OSError, UnicodeDecodeError) as e:
        output = f"Error reading file: {e}"
        _notify_status(widget_id, "error", str(e), panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output


def _write_file_impl(path: str, content: str, working_dir: Path, panel_id: str | None = None, overwrite: bool = False) -> str:
    """Create or overwrite a file with the given content."""
    global _command_widget_counter
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = working_dir / file_path
    file_path = file_path.resolve()

    _command_widget_counter += 1
    widget_id = f"cmd-status-{_command_widget_counter}"
    display_path = path if len(path) <= 40 else "..." + path[-37:]
    command = f"write {display_path}"
    _notify_mount(command, widget_id, panel_id)

    exists = file_path.exists()
    if exists and not overwrite:
        output = f"Error: File already exists: {path}. Use overwrite=True or edit_file to modify."
        _notify_status(widget_id, "error", panel_id=panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        lines = len(content.split("\n"))
        action = "Overwritten" if exists else "Created"
        output_preview = f"{action} ({lines} lines)"
        _notify_status(widget_id, "success", output_preview, panel_id)
        _track_tool_call(command, output_preview, "success", panel_id)
        return f"{action}: {path}"
    except OSError as e:
        output = f"Error writing file: {e}"
        _notify_status(widget_id, "error", str(e), panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output


def _edit_file_impl(
    path: str,
    old_string: str,
    new_string: str,
    working_dir: Path,
    panel_id: str | None = None,
    session_id: str | None = None,
    replace_all: bool = False,
) -> str:
    """Edit a file by replacing old_string with new_string."""
    global _edit_approval_event, _edit_approval_result, _pending_edit, _command_widget_counter

    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = working_dir / file_path
    file_path = file_path.resolve()

    _command_widget_counter += 1
    widget_id = f"cmd-status-{_command_widget_counter}"
    display_path = path if len(path) <= 40 else "..." + path[-37:]
    command = f"edit {display_path}"
    _notify_mount(command, widget_id, panel_id)

    if not file_path.exists():
        output = f"Error: File not found: {file_path}"
        _notify_status(widget_id, "error", panel_id=panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output

    try:
        content = file_path.read_text()
        if old_string not in content:
            _notify_status(widget_id, "error", "failed", panel_id)
            _track_tool_call(command, "failed", "error", panel_id)
            return "Edit failed - text not found. Re-read the file and try again."

        # Request user approval via diff modal
        if _app_instance is not None:
            _edit_approval_event = threading.Event()
            _pending_edit = {
                "path": str(file_path),
                "old_string": old_string,
                "new_string": new_string,
                "replace_all": replace_all,
            }
            _app_instance.call_from_thread(_app_instance.show_diff_approval)
            _edit_approval_event.wait()

            if not _edit_approval_result:
                output = "Edit rejected by user. STOP and ask what they want instead."
                _notify_status(widget_id, "error", "rejected", panel_id)
                _track_tool_call(command, output, "error", panel_id)
                return output

        cp_manager = get_checkpoint_manager()
        cp = cp_manager.create([file_path], f"Before edit: {file_path.name}", session_id=session_id)

        if replace_all:
            new_content = content.replace(old_string, new_string)
            count = content.count(old_string)
        else:
            new_content = content.replace(old_string, new_string, 1)
            count = 1
        file_path.write_text(new_content)

        cp_note = f" (checkpoint: {cp.id})" if cp else ""
        count_note = f" ({count} replacements)" if replace_all and count > 1 else ""
        result = f"Edited: {path}{count_note}{cp_note}"
        _notify_status(widget_id, "success", "edited", panel_id)
        _track_tool_call(command, "edited", "success", panel_id)
        return result
    except OSError as e:
        output = f"Error editing file: {e}"
        _notify_status(widget_id, "error", str(e), panel_id)
        _track_tool_call(command, str(e), "error", panel_id)
        return output


def _read_notebook_impl(path: str, working_dir: Path, panel_id: str | None = None) -> str:
    """Read a Jupyter notebook and render cells with outputs."""
    global _command_widget_counter
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = working_dir / file_path
    file_path = file_path.resolve()

    _command_widget_counter += 1
    widget_id = f"cmd-status-{_command_widget_counter}"
    display_path = path if len(path) <= 40 else "..." + path[-37:]
    command = f"read notebook {display_path}"
    _notify_mount(command, widget_id, panel_id)

    if not file_path.exists():
        output = f"Error: Notebook not found: {file_path}"
        _notify_status(widget_id, "error", panel_id=panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output

    if not file_path.suffix == ".ipynb":
        output = f"Error: Not a notebook file: {file_path}"
        _notify_status(widget_id, "error", panel_id=panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output

    try:
        content = file_path.read_text()
        notebook = json.loads(content)
        cells = notebook.get("cells", [])

        formatted = []
        for i, cell in enumerate(cells):
            cell_type = cell.get("cell_type", "unknown")
            source = cell.get("source", [])
            if isinstance(source, list):
                source = "".join(source)

            # Cell header
            formatted.append(f"{'─' * 40}")
            formatted.append(f"Cell {i} [{cell_type}]")
            formatted.append(f"{'─' * 40}")

            # Source with line numbers
            for j, line in enumerate(source.split("\n"), start=1):
                if len(line) > MAX_LINE_LENGTH:
                    line = line[:MAX_LINE_LENGTH] + "..."
                formatted.append(f"{j:4}│ {line}")

            # Outputs (for code cells)
            if cell_type == "code":
                outputs = cell.get("outputs", [])
                if outputs:
                    formatted.append("")
                    formatted.append("Output:")
                    for out in outputs:
                        out_type = out.get("output_type", "")
                        if out_type == "stream":
                            text = out.get("text", [])
                            if isinstance(text, list):
                                text = "".join(text)
                            formatted.append(text.rstrip())
                        elif out_type == "execute_result":
                            data = out.get("data", {})
                            if "text/plain" in data:
                                text = data["text/plain"]
                                if isinstance(text, list):
                                    text = "".join(text)
                                formatted.append(text.rstrip())
                        elif out_type == "error":
                            ename = out.get("ename", "Error")
                            evalue = out.get("evalue", "")
                            formatted.append(f"{ename}: {evalue}")
                        elif out_type == "display_data":
                            data = out.get("data", {})
                            if "text/plain" in data:
                                text = data["text/plain"]
                                if isinstance(text, list):
                                    text = "".join(text)
                                formatted.append(text.rstrip())
                            elif "image/png" in data:
                                formatted.append("[Image output]")

            formatted.append("")

        result = "\n".join(formatted)
        output_preview = f"{len(cells)} cells"
        _notify_status(widget_id, "success", output_preview, panel_id)
        tracked = result if len(result) < CONTENT_TRUNCATE_LIMIT else result[:CONTENT_TRUNCATE_LIMIT] + "\n...[truncated]"
        _track_tool_call(command, tracked, "success", panel_id)
        return result

    except json.JSONDecodeError as e:
        output = f"Error parsing notebook JSON: {e}"
        _notify_status(widget_id, "error", str(e), panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output
    except (OSError, KeyError) as e:
        output = f"Error reading notebook: {e}"
        _notify_status(widget_id, "error", str(e), panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output


def _notebook_edit_impl(
    path: str,
    cell_number: int,
    new_source: str,
    working_dir: Path,
    panel_id: str | None = None,
    session_id: str | None = None,
    edit_mode: str = "replace",
    cell_type: str | None = None,
) -> str:
    """Edit a Jupyter notebook cell."""
    global _command_widget_counter

    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = working_dir / file_path
    file_path = file_path.resolve()

    _command_widget_counter += 1
    widget_id = f"cmd-status-{_command_widget_counter}"
    display_path = path if len(path) <= 40 else "..." + path[-37:]
    command = f"notebook {edit_mode} {display_path}[{cell_number}]"
    _notify_mount(command, widget_id, panel_id)

    if not file_path.exists():
        output = f"Error: Notebook not found: {file_path}"
        _notify_status(widget_id, "error", panel_id=panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output

    if not file_path.suffix == ".ipynb":
        output = f"Error: Not a notebook file: {file_path}"
        _notify_status(widget_id, "error", panel_id=panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output

    try:
        content = file_path.read_text()
        notebook = json.loads(content)
        cells = notebook.get("cells", [])

        if edit_mode == "delete":
            if cell_number < 0 or cell_number >= len(cells):
                output = f"Error: Cell {cell_number} out of range (0-{len(cells) - 1})"
                _notify_status(widget_id, "error", panel_id=panel_id)
                _track_tool_call(command, output, "error", panel_id)
                return output

            # Create checkpoint before edit
            cp_manager = get_checkpoint_manager()
            cp = cp_manager.create([file_path], f"Before notebook edit: {file_path.name}", session_id=session_id)

            del cells[cell_number]
            notebook["cells"] = cells
            file_path.write_text(json.dumps(notebook, indent=1))

            cp_note = f" (checkpoint: {cp.id})" if cp else ""
            result = f"Deleted cell {cell_number}{cp_note}"
            _notify_status(widget_id, "success", "deleted", panel_id)
            _track_tool_call(command, result, "success", panel_id)
            return result

        elif edit_mode == "insert":
            if cell_number < 0 or cell_number > len(cells):
                output = f"Error: Insert position {cell_number} out of range (0-{len(cells)})"
                _notify_status(widget_id, "error", panel_id=panel_id)
                _track_tool_call(command, output, "error", panel_id)
                return output

            if not cell_type:
                output = "Error: cell_type required for insert mode"
                _notify_status(widget_id, "error", panel_id=panel_id)
                _track_tool_call(command, output, "error", panel_id)
                return output

            # Create checkpoint before edit
            cp_manager = get_checkpoint_manager()
            cp = cp_manager.create([file_path], f"Before notebook edit: {file_path.name}", session_id=session_id)

            new_cell = {
                "cell_type": cell_type,
                "metadata": {},
                "source": new_source.split("\n"),
            }
            if cell_type == "code":
                new_cell["outputs"] = []
                new_cell["execution_count"] = None

            cells.insert(cell_number, new_cell)
            notebook["cells"] = cells
            file_path.write_text(json.dumps(notebook, indent=1))

            cp_note = f" (checkpoint: {cp.id})" if cp else ""
            result = f"Inserted {cell_type} cell at position {cell_number}{cp_note}"
            _notify_status(widget_id, "success", "inserted", panel_id)
            _track_tool_call(command, result, "success", panel_id)
            return result

        else:  # replace
            if cell_number < 0 or cell_number >= len(cells):
                output = f"Error: Cell {cell_number} out of range (0-{len(cells) - 1})"
                _notify_status(widget_id, "error", panel_id=panel_id)
                _track_tool_call(command, output, "error", panel_id)
                return output

            # Create checkpoint before edit
            cp_manager = get_checkpoint_manager()
            cp = cp_manager.create([file_path], f"Before notebook edit: {file_path.name}", session_id=session_id)

            cells[cell_number]["source"] = new_source.split("\n")
            if cell_type:
                cells[cell_number]["cell_type"] = cell_type
            # Clear outputs when replacing code
            if cells[cell_number].get("cell_type") == "code":
                cells[cell_number]["outputs"] = []
                cells[cell_number]["execution_count"] = None

            notebook["cells"] = cells
            file_path.write_text(json.dumps(notebook, indent=1))

            cp_note = f" (checkpoint: {cp.id})" if cp else ""
            result = f"Replaced cell {cell_number}{cp_note}"
            _notify_status(widget_id, "success", "replaced", panel_id)
            _track_tool_call(command, result, "success", panel_id)
            return result

    except json.JSONDecodeError as e:
        output = f"Error parsing notebook JSON: {e}"
        _notify_status(widget_id, "error", str(e), panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output
    except (OSError, KeyError) as e:
        output = f"Error editing notebook: {e}"
        _notify_status(widget_id, "error", str(e), panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return output


_tool_cache: dict[str, bool] = {}


def _has_fd() -> bool:
    """Check if fd is available (cached)."""
    if "fd" not in _tool_cache:
        try:
            subprocess.run(["fd", "--version"], capture_output=True, timeout=2)
            _tool_cache["fd"] = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _tool_cache["fd"] = False
    return _tool_cache["fd"]


def _has_ripgrep() -> bool:
    """Check if ripgrep is available (cached)."""
    if "rg" not in _tool_cache:
        try:
            subprocess.run(["rg", "--version"], capture_output=True, timeout=2)
            _tool_cache["rg"] = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _tool_cache["rg"] = False
    return _tool_cache["rg"]


def _list_files_sync(pattern: str, base: Path, working_dir: Path) -> list[str]:
    """List files using fd (preferred) or find (fallback)."""
    fd_result = _try_fd(pattern, base, working_dir)
    if fd_result is not None:
        return fd_result
    return _list_with_find(pattern, base, working_dir)


def _try_fd(pattern: str, base: Path, working_dir: Path) -> list[str] | None:
    """List files with fd. Returns None if fd not installed."""
    cmd = ["fd", "--type", "f", "--max-results", str(MAX_LIST_RESULTS)]
    if pattern == "**/*":
        pass
    elif pattern.startswith("**/*."):
        ext = pattern.split(".")[-1]
        cmd.extend(["-e", ext])
    elif "*" in pattern:
        cmd.extend(["-g", pattern.replace("**/", "")])
    else:
        cmd.extend(["-g", pattern])
    cmd.append(str(base))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, cwd=working_dir)
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            return sorted(lines[:MAX_LIST_RESULTS])
        return None
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None


def _list_with_find(pattern: str, base: Path, working_dir: Path) -> list[str]:
    """List files with find (available on all Unix systems)."""
    cmd = ["find", str(base), "-type", "f"]
    if pattern == "**/*":
        pass
    elif pattern.startswith("**/"):
        name_pattern = pattern.replace("**/", "")
        cmd.extend(["-name", name_pattern])
    elif "*" in pattern:
        cmd.extend(["-name", pattern])
    else:
        cmd.extend(["-name", pattern])
    for ignored in IGNORED_DIRS:
        cmd.extend(["-not", "-path", f"*/{ignored}/*"])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, cwd=working_dir)
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            rel_paths = []
            for line in lines:
                try:
                    rel_paths.append(str(Path(line).relative_to(working_dir)))
                except ValueError:
                    rel_paths.append(line)
            return sorted(rel_paths[:MAX_LIST_RESULTS])
        return []
    except subprocess.TimeoutExpired:
        return []


async def _list_files_impl(pattern: str, path: str, working_dir: Path, panel_id: str | None = None) -> str:
    """List files matching a glob pattern."""
    tool = "fd" if _has_fd() else "find"
    command = f"{tool} {pattern}"
    widget_id = await _show_command_widget(command, panel_id)
    base = Path(path)
    if not base.is_absolute():
        base = working_dir / base
    try:
        filtered = await asyncio.wait_for(asyncio.to_thread(_list_files_sync, pattern, base, working_dir), timeout=15.0)
        result = "\n".join(filtered) if filtered else f"No files matching: {pattern}"
        await _update_command_status(widget_id, "success", result, panel_id)
        _track_tool_call(command, result, "success", panel_id)
        return result
    except asyncio.TimeoutError:
        output = "Timed out after 15s"
        await _update_command_status(widget_id, "error", output, panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return f"Listing timed out after 15s. Try a more specific pattern."
    except Exception as e:
        output = str(e)
        await _update_command_status(widget_id, "error", output, panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return f"Error listing files: {e}"


def _search_files_sync(
    pattern: str,
    base: Path,
    file_pattern: str,
    working_dir: Path,
    context: int = 0,
    context_before: int | None = None,
    context_after: int | None = None,
    output_mode: str = "content",
    multiline: bool = False,
    file_type: str | None = None,
    head_limit: int = 0,
    offset: int = 0,
) -> list[str]:
    """Search files using ripgrep (preferred) or grep (fallback)."""
    rg_result = _try_ripgrep(
        pattern, base, file_pattern, context, context_before, context_after,
        output_mode, multiline, file_type, head_limit, offset
    )
    if rg_result is not None:
        return rg_result
    return _search_with_grep(pattern, base, file_pattern, context, context_before, context_after, output_mode, head_limit, offset)


def _try_ripgrep(
    pattern: str,
    base: Path,
    file_pattern: str,
    context: int,
    context_before: int | None,
    context_after: int | None,
    output_mode: str,
    multiline: bool,
    file_type: str | None,
    head_limit: int,
    offset: int,
) -> list[str] | None:
    """Search with ripgrep. Returns None if rg not installed."""
    cmd = ["rg", "--color=never", "-i"]

    # Output mode determines format
    if output_mode == "files_with_matches":
        cmd.append("--files-with-matches")
    elif output_mode == "count":
        cmd.append("--count")
    else:
        # content mode - show line numbers
        cmd.extend(["--line-number", "--no-heading"])

    # Multiline mode
    if multiline:
        cmd.extend(["-U", "--multiline-dotall"])

    # Context lines (only for content mode)
    if output_mode == "content":
        if context_before is not None:
            cmd.extend(["-B", str(context_before)])
        if context_after is not None:
            cmd.extend(["-A", str(context_after)])
        if context > 0 and context_before is None and context_after is None:
            cmd.extend(["-C", str(context)])

    # File filtering
    if file_type:
        cmd.extend(["--type", file_type])
    if file_pattern != "*":
        cmd.extend(["--glob", file_pattern])

    cmd.extend([pattern, str(base)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if result.returncode in (0, 1):  # 0=matches, 1=no matches
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            # Apply offset and head_limit
            if offset > 0:
                lines = lines[offset:]
            if head_limit > 0:
                lines = lines[:head_limit]
            elif len(lines) > MAX_SEARCH_RESULTS:
                lines = lines[:MAX_SEARCH_RESULTS] + ["... (truncated)"]
            return lines
        return None
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return ["... (search timed out)"]


def _search_with_grep(
    pattern: str,
    base: Path,
    file_pattern: str,
    context: int,
    context_before: int | None,
    context_after: int | None,
    output_mode: str,
    head_limit: int,
    offset: int,
) -> list[str]:
    """Search with grep (available on all Unix systems)."""
    cmd = ["grep", "-rn"]

    # Output mode
    if output_mode == "files_with_matches":
        cmd = ["grep", "-rl"]
    elif output_mode == "count":
        cmd = ["grep", "-rc"]
    else:
        cmd.append("-i")

    # Context (only for content mode)
    if output_mode == "content":
        if context_before is not None:
            cmd.append(f"-B{context_before}")
        if context_after is not None:
            cmd.append(f"-A{context_after}")
        if context > 0 and context_before is None and context_after is None:
            cmd.append(f"-C{context}")

    cmd.extend([pattern, str(base)])
    if file_pattern != "*":
        cmd.extend(["--include", file_pattern])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            # Apply offset and head_limit
            if offset > 0:
                lines = lines[offset:]
            if head_limit > 0:
                lines = lines[:head_limit]
            elif len(lines) > MAX_SEARCH_RESULTS:
                lines = lines[:MAX_SEARCH_RESULTS] + ["... (truncated)"]
            return lines
        return []
    except subprocess.TimeoutExpired:
        return ["... (search timed out)"]


async def _search_files_impl(
    pattern: str,
    path: str,
    file_pattern: str,
    working_dir: Path,
    panel_id: str | None = None,
    context: int = 0,
    context_before: int | None = None,
    context_after: int | None = None,
    output_mode: str = "content",
    multiline: bool = False,
    file_type: str | None = None,
    head_limit: int = 0,
    offset: int = 0,
) -> str:
    """Search for a regex pattern in files."""
    tool = "rg" if _has_ripgrep() else "grep"
    command = f'{tool} "{pattern}"'
    widget_id = await _show_command_widget(command, panel_id)
    base = Path(path)
    if not base.is_absolute():
        base = working_dir / base
    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(
                _search_files_sync, pattern, base, file_pattern, working_dir,
                context, context_before, context_after, output_mode, multiline,
                file_type, head_limit, offset
            ),
            timeout=30.0
        )
        result = "\n".join(results) if results else f"No matches for: {pattern}"
        await _update_command_status(widget_id, "success", result, panel_id)
        _track_tool_call(command, result, "success", panel_id)
        return result
    except asyncio.TimeoutError:
        output = "Timed out after 30s"
        await _update_command_status(widget_id, "error", output, panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return f"Search timed out after 30s. Try a more specific path or pattern."
    except Exception as e:
        output = str(e)
        await _update_command_status(widget_id, "error", output, panel_id)
        _track_tool_call(command, output, "error", panel_id)
        return f"Error searching: {e}"


async def _run_command_impl(command: str, working_dir: Path, panel_id: str | None = None) -> str:
    """Run a shell command and return the output."""
    global _next_bg_id

    approved, feedback = await request_tool_approval("run_command", f"$ {command}", panel_id)
    if not approved:
        # Don't track cancelled operations for consistency
        if feedback == "Operation cancelled":
            return "Command cancelled"
        msg = f"Command rejected by user. Feedback: {feedback}" if feedback else "Command rejected by user."
        _track_tool_call(f"$ {command}", msg, "error", panel_id)
        return msg

    # Clear any pending background request for this panel
    if panel_id:
        _background_requested[panel_id] = False
    widget_id = await _show_command_widget(command, panel_id)

    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=working_dir,
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

            if panel_id and _background_requested.get(panel_id, False):
                _background_requested[panel_id] = False
                bg_id = f"bg_{_next_bg_id}"
                _next_bg_id += 1

                bg_proc = BackgroundProcess(
                    pid=proc.pid,
                    command=command,
                    process=proc,
                    output_buffer=output_lines.copy(),
                )
                # Store in per-panel dict
                if panel_id not in _panel_background_processes:
                    _panel_background_processes[panel_id] = {}
                _panel_background_processes[panel_id][bg_id] = bg_proc

                await _update_command_status(widget_id, "backgrounded", panel_id=panel_id)
                _track_tool_call(f"$ {command}", "backgrounded", "success", panel_id)
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
                await _update_command_status(widget_id, "error", f"Timed out after {timeout}s", panel_id)
                _track_tool_call(f"$ {command}", f"Timed out after {timeout}s", "error", panel_id)
                return f"Error: Command timed out after {timeout}s\n" + output

        output = "".join(output_lines)
        if len(output) > 10000:
            output = output[:10000] + "\n... (truncated)"

        status = "success" if proc.returncode == 0 else "error"
        output_display = output or "(no output)"
        await _update_command_status(widget_id, status, output_display, panel_id)
        _track_tool_call(f"$ {command}", output_display, status, panel_id)
        return output_display

    except Exception as e:
        await _update_command_status(widget_id, "error", str(e), panel_id)
        _track_tool_call(f"$ {command}", str(e), "error", panel_id)
        return f"Error running command: {e}"


def _get_process_impl(process_id: str, panel_id: str | None) -> BackgroundProcess | None:
    """Get a background process by ID for a panel."""
    if not panel_id:
        return None
    return _panel_background_processes.get(panel_id, {}).get(process_id)


def get_process_output(process_id: str, lines: int = 50, panel_id: str | None = None) -> str:
    """Get recent output from a background process."""
    proc = _get_process_impl(process_id, panel_id)
    if not proc:
        return f"Error: No process with ID {process_id}. Use list_processes() to see running processes."

    status = "running" if proc.is_running() else "stopped"
    output = proc.get_recent_output(lines)

    return f"[{process_id}] {proc.command} ({status})\n\n{output}"


def stop_process(process_id: str, panel_id: str | None = None) -> str:
    """Stop a background process."""
    proc = _get_process_impl(process_id, panel_id)
    if not proc:
        return f"Error: No process with ID {process_id}"

    if proc.is_running():
        proc.process.terminate()
        try:
            proc.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.process.kill()

    if panel_id and panel_id in _panel_background_processes:
        _panel_background_processes[panel_id].pop(process_id, None)
    return f"Stopped: {proc.command}"


def list_processes(panel_id: str | None = None) -> str:
    """List background processes for a panel."""
    processes = _panel_background_processes.get(panel_id, {}) if panel_id else {}
    if not processes:
        return "No background processes running"

    lines = []
    for pid, proc in processes.items():
        status = "running" if proc.is_running() else "stopped"
        elapsed = int(time.time() - proc.started_at)
        lines.append(f"[{pid}] {proc.command} ({status}, {elapsed}s)")

    return "\n".join(lines)


def create_tools(working_dir: Path, panel_id: str | None = None, session_id: str | None = None) -> list:
    """Create tool functions bound to a specific working directory, panel, and session."""

    def read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
        """Read file contents. Default: first 2000 lines. Use offset/limit for specific sections."""
        # Pass through to impl - 0 offset means start from beginning, limit always honored
        return _read_file_impl(path, working_dir, panel_id, offset if offset > 0 else None, limit)

    def write_file(path: str, content: str, overwrite: bool = False) -> str:
        """Write content to a file.

        Args:
            path: File path to write.
            content: Content to write.
            overwrite: If True, overwrite existing files. Default prevents overwriting.
        """
        return _write_file_impl(path, content, working_dir, panel_id, overwrite)

    def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        """Edit a file by replacing old_string with new_string.

        Args:
            path: File path to edit.
            old_string: Text to find and replace.
            new_string: Replacement text.
            replace_all: If True, replace all occurrences. Default replaces only first.
        """
        return _edit_file_impl(path, old_string, new_string, working_dir, panel_id, session_id, replace_all)

    async def list_files(pattern: str = "**/*", path: str = ".") -> str:
        """List files matching a glob pattern."""
        try:
            return await _list_files_impl(pattern, path, working_dir, panel_id)
        except Exception as e:
            return f"Error listing files: {e}"

    async def search_files(
        pattern: str,
        path: str = ".",
        file_pattern: str = "*",
        context: int = 0,
        context_before: int | None = None,
        context_after: int | None = None,
        output_mode: str = "content",
        multiline: bool = False,
        file_type: str | None = None,
        head_limit: int = 0,
        offset: int = 0,
    ) -> str:
        """Search for a regex pattern in files.

        Args:
            pattern: Regex pattern to search for.
            path: Directory to search in (default ".").
            file_pattern: Glob pattern to filter files (e.g., "*.py").
            context: Lines of context before and after matches (-C).
            context_before: Lines before each match (-B), overrides context.
            context_after: Lines after each match (-A), overrides context.
            output_mode: "content" (default), "files_with_matches", or "count".
            multiline: Enable multiline matching (patterns can span lines).
            file_type: File type filter (e.g., "py", "js", "rust").
            head_limit: Limit output to first N results (0 = default limit).
            offset: Skip first N results before applying head_limit.
        """
        try:
            return await _search_files_impl(
                pattern, path, file_pattern, working_dir, panel_id, context,
                context_before, context_after, output_mode, multiline,
                file_type, head_limit, offset
            )
        except Exception as e:
            return f"Error searching files: {e}"

    async def run_command(command: str) -> str:
        """Run a shell command and return the output."""
        try:
            return await _run_command_impl(command, working_dir, panel_id)
        except Exception as e:
            return f"Error running command: {e}"

    def bound_get_process_output(process_id: str, lines: int = 50) -> str:
        """Get recent output from a background process."""
        return get_process_output(process_id, lines, panel_id)

    def bound_stop_process(process_id: str) -> str:
        """Stop a background process."""
        return stop_process(process_id, panel_id)

    def bound_list_processes() -> str:
        """List background processes for this panel."""
        return list_processes(panel_id)

    def read_notebook(path: str) -> str:
        """Read a Jupyter notebook (.ipynb) and display all cells with outputs."""
        return _read_notebook_impl(path, working_dir, panel_id)

    def notebook_edit(
        path: str,
        cell_number: int,
        new_source: str,
        edit_mode: str = "replace",
        cell_type: str | None = None,
    ) -> str:
        """Edit a Jupyter notebook cell.

        Args:
            path: Path to the .ipynb file.
            cell_number: 0-indexed cell number to edit.
            new_source: New content for the cell.
            edit_mode: "replace" (default), "insert", or "delete".
            cell_type: Cell type ("code" or "markdown"). Required for insert.
        """
        return _notebook_edit_impl(path, cell_number, new_source, working_dir, panel_id, session_id, edit_mode, cell_type)

    return [
        read_file,
        write_file,
        edit_file,
        list_files,
        search_files,
        run_command,
        bound_get_process_output,
        bound_stop_process,
        bound_list_processes,
        read_notebook,
        notebook_edit,
    ]


CODING_SYSTEM_PROMPT = """You are Wingman, an expert AI coding assistant.

## Tools Available
- read_file(path, offset?, limit?): Read file contents with line numbers (e.g. "   1│ code"). Default: first 2000 lines.
- edit_file(path, old_string, new_string, replace_all?): Replace old_string with new_string. Use replace_all=True to replace all occurrences. CRITICAL: old_string must match the actual file content - do NOT include line numbers from read output. Only use content after the "│" character.
- write_file(path, content, overwrite?): Write content to a file. Use overwrite=True to replace existing files.
- list_files: Find files with glob patterns
- search_files: Search file contents with regex. Options:
  - pattern: Regex pattern to search
  - path: Directory to search (default ".")
  - file_pattern: Glob filter (e.g., "*.py")
  - context: Lines before/after matches (-C)
  - context_before/context_after: Asymmetric context (-B/-A)
  - output_mode: "content" (default), "files_with_matches", or "count"
  - multiline: True to match across lines
  - file_type: Filter by type (e.g., "py", "js")
  - head_limit: Limit results, offset: Skip first N results
- run_command: Execute shell commands (user can press Ctrl+B to background)
- get_process_output: Check output from backgrounded processes
- stop_process: Stop a background process
- list_processes: See all background processes
- read_notebook(path): Read a Jupyter notebook (.ipynb), showing all cells with outputs
- notebook_edit(path, cell_number, new_source, edit_mode?, cell_type?): Edit notebook cells
  - cell_number: 0-indexed cell position
  - edit_mode: "replace" (default), "insert", or "delete"
  - cell_type: "code" or "markdown" (required for insert)

## Rules
1. ALWAYS read a file before editing it
2. Use list_files or search_files to discover code structure
3. Make minimal, focused edits
4. If you're unsure, ask the user
5. For long-running commands, the user may background them with Ctrl+B
6. If user rejects an edit, STOP and ask what they want - do NOT retry or use shell commands to bypass

## Efficient File Reading
For large files, search first then read targeted sections:
1. search_files("function_name", file_pattern="*.py", context=10) → find matches with 10 lines of context
2. read_file("file.py", offset=line-10, limit=50) → read more if needed

## Communication
Briefly state what you're doing before each action so the user can follow along. Keep it short.

## Background Processes
When a command is backgrounded, you'll see "[Backgrounded: bg_X]". Use get_process_output('bg_X') to check its output later.

## Working Directory
{cwd}
"""


# --- Headless mode implementations (no TUI, auto-approve) ---


def _edit_file_impl_headless(path: str, old_string: str, new_string: str, working_dir: Path, replace_all: bool = False) -> str:
    """Edit a file - headless mode (auto-approve, no checkpoints)."""
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = working_dir / file_path
    file_path = file_path.resolve()

    if not file_path.exists():
        return f"Error: File not found: {file_path}"

    try:
        content = file_path.read_text()
        if old_string not in content:
            return "Edit failed - text not found. Re-read the file and try again."

        if replace_all:
            new_content = content.replace(old_string, new_string)
            count = content.count(old_string)
        else:
            new_content = content.replace(old_string, new_string, 1)
            count = 1
        file_path.write_text(new_content)
        count_note = f" ({count} replacements)" if replace_all and count > 1 else ""
        return f"Edited: {path}{count_note}"
    except OSError as e:
        return f"Error editing file: {e}"


def _notebook_edit_impl_headless(
    path: str,
    cell_number: int,
    new_source: str,
    working_dir: Path,
    edit_mode: str = "replace",
    cell_type: str | None = None,
) -> str:
    """Edit a Jupyter notebook cell - headless mode (no checkpoints)."""
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = working_dir / file_path
    file_path = file_path.resolve()

    if not file_path.exists():
        return f"Error: Notebook not found: {file_path}"

    if not file_path.suffix == ".ipynb":
        return f"Error: Not a notebook file: {file_path}"

    try:
        content = file_path.read_text()
        notebook = json.loads(content)
        cells = notebook.get("cells", [])

        if edit_mode == "delete":
            if cell_number < 0 or cell_number >= len(cells):
                return f"Error: Cell {cell_number} out of range (0-{len(cells) - 1})"
            del cells[cell_number]
            notebook["cells"] = cells
            file_path.write_text(json.dumps(notebook, indent=1))
            return f"Deleted cell {cell_number}"

        elif edit_mode == "insert":
            if cell_number < 0 or cell_number > len(cells):
                return f"Error: Insert position {cell_number} out of range (0-{len(cells)})"
            if not cell_type:
                return "Error: cell_type required for insert mode"
            new_cell = {
                "cell_type": cell_type,
                "metadata": {},
                "source": new_source.split("\n"),
            }
            if cell_type == "code":
                new_cell["outputs"] = []
                new_cell["execution_count"] = None
            cells.insert(cell_number, new_cell)
            notebook["cells"] = cells
            file_path.write_text(json.dumps(notebook, indent=1))
            return f"Inserted {cell_type} cell at position {cell_number}"

        else:  # replace
            if cell_number < 0 or cell_number >= len(cells):
                return f"Error: Cell {cell_number} out of range (0-{len(cells) - 1})"
            cells[cell_number]["source"] = new_source.split("\n")
            if cell_type:
                cells[cell_number]["cell_type"] = cell_type
            if cells[cell_number].get("cell_type") == "code":
                cells[cell_number]["outputs"] = []
                cells[cell_number]["execution_count"] = None
            notebook["cells"] = cells
            file_path.write_text(json.dumps(notebook, indent=1))
            return f"Replaced cell {cell_number}"

    except json.JSONDecodeError as e:
        return f"Error parsing notebook JSON: {e}"
    except (OSError, KeyError) as e:
        return f"Error editing notebook: {e}"


async def _run_command_impl_headless(command: str, working_dir: Path, timeout: int = 120) -> str:
    """Run a shell command - headless mode (auto-approve)."""
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        output_lines = []
        start_time = time.time()

        while True:
            await asyncio.sleep(0.05)

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
                return f"Error: Command timed out after {timeout}s\n" + output

        output = "".join(output_lines)
        if len(output) > 10000:
            output = output[:10000] + "\n... (truncated)"

        return output or "(no output)"

    except Exception as e:
        return f"Error running command: {e}"


def create_tools_headless(working_dir: Path) -> list:
    """Create tools for headless mode with auto-approval."""

    def read_file(path: str, offset: int | None = None, limit: int | None = None) -> str:
        """Read file contents. Default: first 2000 lines."""
        return _read_file_impl(path, working_dir, None, offset, limit)

    def write_file(path: str, content: str, overwrite: bool = False) -> str:
        """Write content to a file."""
        return _write_file_impl(path, content, working_dir, None, overwrite)

    def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        """Edit a file by replacing old_string with new_string."""
        return _edit_file_impl_headless(path, old_string, new_string, working_dir, replace_all)

    async def list_files(pattern: str = "**/*", path: str = ".") -> str:
        """List files matching a glob pattern."""
        return await _list_files_impl(pattern, path, working_dir, None)

    async def search_files(
        pattern: str,
        path: str = ".",
        file_pattern: str = "*",
        context: int = 0,
        context_before: int | None = None,
        context_after: int | None = None,
        output_mode: str = "content",
        multiline: bool = False,
        file_type: str | None = None,
        head_limit: int = 0,
        offset: int = 0,
    ) -> str:
        """Search for a regex pattern in files."""
        return await _search_files_impl(
            pattern, path, file_pattern, working_dir, None, context,
            context_before, context_after, output_mode, multiline,
            file_type, head_limit, offset
        )

    async def run_command(command: str) -> str:
        """Run a shell command and return the output."""
        return await _run_command_impl_headless(command, working_dir)

    def read_notebook(path: str) -> str:
        """Read a Jupyter notebook (.ipynb) and display all cells with outputs."""
        return _read_notebook_impl(path, working_dir, None)

    def notebook_edit(
        path: str,
        cell_number: int,
        new_source: str,
        edit_mode: str = "replace",
        cell_type: str | None = None,
    ) -> str:
        """Edit a Jupyter notebook cell."""
        return _notebook_edit_impl_headless(path, cell_number, new_source, working_dir, edit_mode, cell_type)

    return [read_file, write_file, edit_file, list_files, search_files, run_command, read_notebook, notebook_edit]
