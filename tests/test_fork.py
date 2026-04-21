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
async def test_fork_full_clone_renders_parent_messages(isolated_sessions):
    """Regression: forked panel must render the parent's messages, not welcome splash."""
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

        app._cmd_fork("0")  # rewind 0 turns = full clone, no picker
        await pilot.pause()
        await pilot.pause()  # let on_mount + refresh queue drain

        assert len(app.panels) == 2
        fork_panel = app.panels[1]

        from wingman.sessions import get_session_parent

        assert fork_panel.session_id is not None
        assert get_session_parent(fork_panel.session_id) == "parent-sess"

        widgets = _loaded_message_widgets(fork_panel)
        assert len(widgets) == 2, (
            f"Expected 2 ChatMessage widgets in forked panel, got {len(widgets)}. "
            f"Children: {[type(c).__name__ for c in fork_panel.get_chat_container().children]}"
        )
        assert len(fork_panel.messages) == 2
        assert fork_panel.messages[0]["content"] == "hi"


@pytest.mark.asyncio
async def test_bare_fork_opens_picker_modal(isolated_sessions):
    """`/fork` with no args pushes the picker — does not create a panel directly."""
    from wingman.app import WingmanApp
    from wingman.ui.modals import ForkPickerModal

    app = WingmanApp()
    async with app.run_test() as pilot:
        _seed_panel(
            app.active_panel,
            [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
            session_id="p",
        )
        app._cmd_fork("")
        await pilot.pause()

        # Modal is on the screen stack. No new panel yet.
        assert isinstance(app.screen, ForkPickerModal)
        assert len(app.panels) == 1


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
    from wingman.ui.modals import ForkPickerModal

    app = WingmanApp()
    async with app.run_test() as pilot:
        app._cmd_fork("")
        await pilot.pause()
        # No messages: picker is not opened either.
        assert not isinstance(app.screen, ForkPickerModal)
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
        for _ in range(3):
            app.action_split_panel()
            await pilot.pause()
        assert len(app.panels) == 4

        _seed_panel(
            app.active_panel,
            [{"role": "user", "content": "q1"}],
            session_id="capped",
        )
        app._cmd_fork("0")  # full clone via shortcut, bypassing picker
        await pilot.pause()

        assert len(app.panels) == 4
        assert len(list_forks("capped")) == 1


# ---------------------------------------------------------------- picker modal


@pytest.mark.asyncio
async def test_picker_cancel_does_nothing(isolated_sessions):
    from wingman.app import WingmanApp
    from wingman.sessions import list_forks

    app = WingmanApp()
    async with app.run_test() as pilot:
        _seed_panel(
            app.active_panel,
            [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
            session_id="p",
        )
        app._cmd_fork("")
        await pilot.pause()
        # Dismiss as the user would with Esc.
        app.screen.action_cancel()
        await pilot.pause()
        assert len(app.panels) == 1
        assert list_forks("p") == []


@pytest.mark.asyncio
async def test_picker_assistant_row_branches_after(isolated_sessions):
    """Selecting an assistant row forks AFTER it: fork keeps [..., selected]."""
    from wingman.app import WingmanApp

    app = WingmanApp()
    async with app.run_test() as pilot:
        _seed_panel(
            app.active_panel,
            [
                {"role": "user", "content": "q1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "q2"},
                {"role": "assistant", "content": "a2"},
            ],
            session_id="p",
        )
        app._cmd_fork("")
        await pilot.pause()

        # Assistant 'a1' is at index 1. Fork-after = (2, None).
        app.screen.dismiss((2, None))
        await pilot.pause()
        await pilot.pause()

        assert len(app.panels) == 2
        fork = app.panels[1]
        assert [m["content"] for m in fork.messages] == ["q1", "a1"]
        # No prefill for assistant rows: input is empty.
        assert fork.get_input().value == ""


@pytest.mark.asyncio
async def test_picker_user_row_forks_before_and_prefills(isolated_sessions):
    """Selecting a user row drops that message and prefills the input for rewriting."""
    from wingman.app import WingmanApp

    app = WingmanApp()
    async with app.run_test() as pilot:
        _seed_panel(
            app.active_panel,
            [
                {"role": "user", "content": "q1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "q2 original"},
                {"role": "assistant", "content": "a2"},
            ],
            session_id="p",
        )
        app._cmd_fork("")
        await pilot.pause()

        # User 'q2 original' is at index 2. Picker dispatches (2, "q2 original").
        app.screen.dismiss((2, "q2 original"))
        await pilot.pause()
        await pilot.pause()

        fork = app.panels[1]
        # Fork ends in assistant — clean state, no dangling user turn.
        assert [m["content"] for m in fork.messages] == ["q1", "a1"]
        # Input is pre-populated with the original user message text.
        assert fork.get_input().value == "q2 original"


@pytest.mark.asyncio
async def test_picker_head_option_clones_all(isolated_sessions):
    from wingman.app import WingmanApp

    app = WingmanApp()
    async with app.run_test() as pilot:
        msgs = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        _seed_panel(app.active_panel, msgs, session_id="p")
        app._cmd_fork("")
        await pilot.pause()

        # HEAD row dismisses with (len(messages), None).
        app.screen.dismiss((len(msgs), None))
        await pilot.pause()
        await pilot.pause()

        fork = app.panels[1]
        assert [m["content"] for m in fork.messages] == ["q1", "a1"]
        assert fork.get_input().value == ""


@pytest.mark.asyncio
async def test_fork_rewind_shortcut_prefills_last_user_turn(isolated_sessions):
    """/fork 1 should also pre-fill the input with the rewound user message."""
    from wingman.app import WingmanApp

    app = WingmanApp()
    async with app.run_test() as pilot:
        _seed_panel(
            app.active_panel,
            [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "reply1"},
                {"role": "user", "content": "second"},
                {"role": "assistant", "content": "reply2"},
            ],
            session_id="p",
        )
        app._cmd_fork("1")
        await pilot.pause()
        await pilot.pause()

        fork = app.panels[1]
        assert [m["content"] for m in fork.messages] == ["first", "reply1"]
        assert fork.get_input().value == "second"


def test_picker_format_row_handles_segments_and_lists():
    """Preview string is generated defensively for all message shapes."""
    from wingman.ui.modals import ForkPickerModal

    modal = ForkPickerModal(messages=[])

    # Plain string content.
    row = modal._format_row(0, {"role": "user", "content": "hello world"})
    assert "user" in row
    assert "hello world" in row

    # List content (multimodal).
    row = modal._format_row(1, {"role": "user", "content": [{"type": "text", "text": "hi"}]})
    assert "hi" in row

    # Segment-based assistant message with a tool call.
    row = modal._format_row(
        2,
        {
            "role": "assistant",
            "segments": [{"type": "text", "content": "ran"}, {"type": "tool", "command": "ls"}],
        },
    )
    assert "ran" in row
    assert "ls" in row

    # Long content is truncated.
    long = "x" * 200
    row = modal._format_row(3, {"role": "user", "content": long})
    assert "..." in row
    assert "x" * 200 not in row
