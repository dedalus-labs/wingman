"""Tests for async subprocess execution and backgrounding."""

import asyncio

import pytest

from wingman.tools import (
    BackgroundProcess,
    _panel_background_processes,
    _run_command_impl_headless,
    check_completed_processes,
    get_process_output,
    list_processes,
    stop_process,
)


@pytest.fixture(autouse=True)
def _clean_background_state():
    """Reset global background process state between tests."""
    _panel_background_processes.clear()
    yield
    # Kill any leftover processes
    for panel_procs in _panel_background_processes.values():
        for proc in panel_procs.values():
            if proc.is_running():
                proc.process.terminate()
    _panel_background_processes.clear()


class TestHeadlessCommand:
    @pytest.mark.asyncio
    async def test_simple_echo(self):
        result = await _run_command_impl_headless("echo hello", working_dir=".")
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_exit_code_nonzero(self):
        result = await _run_command_impl_headless("exit 1", working_dir=".")
        assert result == "(no output)"

    @pytest.mark.asyncio
    async def test_stderr_merged_into_stdout(self):
        result = await _run_command_impl_headless("echo err >&2", working_dir=".")
        assert "err" in result

    @pytest.mark.asyncio
    async def test_timeout(self):
        result = await _run_command_impl_headless("sleep 10", working_dir=".", timeout=1)
        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_large_output_truncated(self):
        result = await _run_command_impl_headless(
            "python3 -c \"print('x' * 20000)\"", working_dir="."
        )
        assert "truncated" in result

    @pytest.mark.asyncio
    async def test_multiline_output(self):
        result = await _run_command_impl_headless(
            "printf 'line1\\nline2\\nline3\\n'", working_dir="."
        )
        assert "line1" in result
        assert "line3" in result


class TestBackgroundProcess:
    @pytest.mark.asyncio
    async def test_drain_captures_output(self):
        proc = await asyncio.create_subprocess_shell(
            "printf 'a\\nb\\nc\\n'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        bg = BackgroundProcess(pid=proc.pid, command="printf", process=proc)
        bg.start_drain()
        await proc.wait()
        await asyncio.sleep(0.1)
        output = bg.get_recent_output()
        assert "a" in output
        assert "c" in output

    @pytest.mark.asyncio
    async def test_is_running(self):
        proc = await asyncio.create_subprocess_shell(
            "sleep 10",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        bg = BackgroundProcess(pid=proc.pid, command="sleep 10", process=proc)
        assert bg.is_running()
        proc.terminate()
        await proc.wait()
        assert not bg.is_running()

    @pytest.mark.asyncio
    async def test_drain_ring_buffer(self):
        proc = await asyncio.create_subprocess_shell(
            "python3 -c \"[print(i) for i in range(1500)]\"",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        bg = BackgroundProcess(pid=proc.pid, command="seq", process=proc)
        bg.start_drain()
        await proc.wait()
        await asyncio.sleep(0.2)
        assert len(bg.output_buffer) <= 1000


class TestProcessManagement:
    @pytest.mark.asyncio
    async def test_stop_process(self):
        proc = await asyncio.create_subprocess_shell(
            "sleep 60",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        bg = BackgroundProcess(pid=proc.pid, command="sleep 60", process=proc)
        bg.start_drain()
        _panel_background_processes["test-panel"] = {"bg_1": bg}

        result = stop_process("bg_1", panel_id="test-panel")
        assert "Stopped" in result
        assert "bg_1" not in _panel_background_processes.get("test-panel", {})

    @pytest.mark.asyncio
    async def test_list_processes(self):
        proc = await asyncio.create_subprocess_shell(
            "sleep 60",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        bg = BackgroundProcess(pid=proc.pid, command="sleep 60", process=proc)
        _panel_background_processes["test-panel"] = {"bg_1": bg}

        result = list_processes(panel_id="test-panel")
        assert "bg_1" in result
        assert "sleep 60" in result
        assert "running" in result

        proc.terminate()
        await proc.wait()

    @pytest.mark.asyncio
    async def test_get_process_output_missing(self):
        result = get_process_output("bg_999", panel_id="test-panel")
        assert "No process" in result

    @pytest.mark.asyncio
    async def test_check_completed_processes(self):
        proc = await asyncio.create_subprocess_shell(
            "echo done",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        bg = BackgroundProcess(pid=proc.pid, command="echo done", process=proc)
        bg.start_drain()
        _panel_background_processes["test-panel"] = {"bg_1": bg}

        await proc.wait()
        await asyncio.sleep(0.1)

        completed = check_completed_processes()
        assert len(completed) == 1
        panel_id, bg_id, exit_code, cmd = completed[0]
        assert panel_id == "test-panel"
        assert bg_id == "bg_1"
        assert exit_code == 0
        assert cmd == "echo done"

        # Second call should return empty (already notified)
        assert check_completed_processes() == []
