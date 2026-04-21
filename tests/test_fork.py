"""Tests for conversation forking."""

from pathlib import Path

import pytest


@pytest.fixture
def isolated_sessions(tmp_path, monkeypatch):
    """Redirect session storage to a tmp dir so tests don't touch ~/.wingman."""
    from wingman import config, sessions

    fake_dir = tmp_path / "sessions"
    fake_dir.mkdir(parents=True)
    monkeypatch.setattr(config, "SESSIONS_DIR", fake_dir)
    monkeypatch.setattr(sessions, "SESSIONS_DIR", fake_dir)
    return fake_dir


def _seed_panel(panel, messages: list[dict], session_id: str) -> None:
    """Populate a panel's in-memory state as if a conversation had happened."""
    panel.session_id = session_id
    panel.messages = list(messages)
    panel.working_dir = Path.cwd()


def _loaded_message_widgets(panel) -> list:
    """Return the scrollback's rendered ChatMessage children (excl. welcome)."""
    from wingman.ui.widgets import ChatMessage

    chat = panel.get_chat_container()
    return [w for w in chat.children if isinstance(w, ChatMessage)]


# ---------------------------------------------------------------- sessions layer


def test_fork_session_copy_writes_parent_and_index(isolated_sessions):
    from wingman.sessions import fork_session_copy, get_session, get_session_parent

    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    ok = fork_session_copy("fork-1", messages, "parent", 2, working_dir="/tmp")
    assert ok
    assert get_session("fork-1") == messages
    assert get_session_parent("fork-1") == "parent"


def test_fork_session_copy_rejects_collision(isolated_sessions):
    from wingman.sessions import fork_session_copy, save_session

    save_session("existing", [{"role": "user", "content": "hi"}])
    ok = fork_session_copy("existing", [], None, 0)
    assert not ok


def test_save_session_preserves_parent_linkage(isolated_sessions):
    from wingman.sessions import fork_session_copy, get_session_parent, save_session

    fork_session_copy("fork", [{"role": "user", "content": "q"}], "parent", 1)
    # Re-save after conversation continues. Must not lose parent linkage.
    save_session("fork", [{"role": "user", "content": "q"}, {"role": "user", "content": "q2"}])
    assert get_session_parent("fork") == "parent"


def test_list_forks_filters_by_parent(isolated_sessions):
    from wingman.sessions import fork_session_copy, list_forks, save_session

    save_session("parent-a", [])
    save_session("parent-b", [])
    fork_session_copy("child-1", [], "parent-a", 0)
    fork_session_copy("child-2", [], "parent-a", 0)
    fork_session_copy("child-3", [], "parent-b", 0)
    assert sorted(list_forks("parent-a")) == ["child-1", "child-2"]
    assert list_forks("parent-b") == ["child-3"]
    assert list_forks("no-such-parent") == []


# ---------------------------------------------------------------- /fork command


@pytest.mark.asyncio
async def test_fork_new_panel_shows_parent_messages(isolated_sessions):
    """Regression: the forked panel must render the parent's messages, not welcome."""
    from wingman.app import WingmanApp

    app = WingmanApp()
    async with app.run_test() as pilot:
        parent = app.active_panel
        _seed_panel(
            parent,
            [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
            session_id="parent-sess",
        )

        app._cmd_fork("")
        await pilot.pause()
        await pilot.pause()  # let on_mount + refresh queue drain

        assert len(app.panels) == 2
        fork_panel = app.panels[1]

        # The fork's session_id is set and its parent is the original.
        from wingman.sessions import get_session_parent

        assert fork_panel.session_id is not None
        assert get_session_parent(fork_panel.session_id) == "parent-sess"

        # The scrollback shows the parent's turns, not the welcome splash.
        widgets = _loaded_message_widgets(fork_panel)
        assert len(widgets) == 2, (
            f"Expected 2 ChatMessage widgets in forked panel, got {len(widgets)}. "
            f"Children: {[type(c).__name__ for c in fork_panel.get_chat_container().children]}"
        )
        # And the panel's messages list matches.
        assert len(fork_panel.messages) == 2
        assert fork_panel.messages[0]["content"] == "hi"


@pytest.mark.asyncio
async def test_fork_rewind_drops_last_user_turn(isolated_sessions):
    from wingman.app import WingmanApp

    app = WingmanApp()
    async with app.run_test() as pilot:
        panel = app.active_panel
        _seed_panel(
            panel,
            [
                {"role": "user", "content": "q1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "q2"},
                {"role": "assistant", "content": "a2"},
            ],
            session_id="p",
        )

        app._cmd_fork("1")  # rewind 1 user turn
        await pilot.pause()
        await pilot.pause()

        fork = app.panels[1]
        # Cut at the last user message (index 2) — so only q1/a1 remain.
        assert [m["content"] for m in fork.messages] == ["q1", "a1"]


@pytest.mark.asyncio
async def test_fork_rewind_skips_tool_messages(isolated_sessions):
    """/fork N counts USER turns, ignoring tool/assistant messages between them."""
    from wingman.app import WingmanApp

    app = WingmanApp()
    async with app.run_test() as pilot:
        panel = app.active_panel
        _seed_panel(
            panel,
            [
                {"role": "user", "content": "q1"},
                {"role": "assistant", "content": "a1"},
                {"role": "tool", "content": "tool-out"},
                {"role": "assistant", "content": "a1-cont"},
                {"role": "user", "content": "q2"},
                {"role": "assistant", "content": "a2"},
            ],
            session_id="p",
        )

        app._cmd_fork("1")
        await pilot.pause()
        await pilot.pause()

        fork = app.panels[1]
        # Cut at last user message (index 4): keep q1/a1/tool/a1-cont.
        assert [m["content"] for m in fork.messages] == ["q1", "a1", "tool-out", "a1-cont"]


@pytest.mark.asyncio
async def test_fork_rewind_too_many_is_rejected(isolated_sessions):
    from wingman.app import WingmanApp

    app = WingmanApp()
    async with app.run_test() as pilot:
        panel = app.active_panel
        _seed_panel(panel, [{"role": "user", "content": "q1"}], session_id="p")

        app._cmd_fork("5")
        await pilot.pause()
        # No new panel should have been created.
        assert len(app.panels) == 1


@pytest.mark.asyncio
async def test_fork_with_no_messages_is_rejected(isolated_sessions):
    from wingman.app import WingmanApp

    app = WingmanApp()
    async with app.run_test() as pilot:
        app._cmd_fork("")
        await pilot.pause()
        assert len(app.panels) == 1


@pytest.mark.asyncio
async def test_fork_rejects_nonnumeric_arg(isolated_sessions):
    from wingman.app import WingmanApp

    app = WingmanApp()
    async with app.run_test() as pilot:
        panel = app.active_panel
        _seed_panel(panel, [{"role": "user", "content": "q"}], session_id="p")
        app._cmd_fork("banana")
        await pilot.pause()
        assert len(app.panels) == 1


@pytest.mark.asyncio
async def test_fork_respects_panel_cap(isolated_sessions):
    """When 4 panels are already open, fork creates the session but not the panel."""
    from wingman.app import WingmanApp
    from wingman.sessions import list_forks

    app = WingmanApp()
    async with app.run_test() as pilot:
        # Open 3 more panels (total 4).
        for _ in range(3):
            app.action_split_panel()
            await pilot.pause()
        assert len(app.panels) == 4

        # Seed the active panel.
        _seed_panel(
            app.active_panel,
            [{"role": "user", "content": "q1"}],
            session_id="capped",
        )
        app._cmd_fork("")
        await pilot.pause()

        # No 5th panel.
        assert len(app.panels) == 4
        # But a fork session was created on disk.
        assert len(list_forks("capped")) == 1
