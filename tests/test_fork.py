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


# ---------------------------------------------------------------- branch markers


def _marker_widgets(panel) -> list:
    from wingman.ui.widgets import BranchMarker

    chat = panel.get_chat_container()
    return [w for w in chat.children if isinstance(w, BranchMarker)]


@pytest.mark.asyncio
async def test_parent_renders_branch_markers_for_its_forks(isolated_sessions):
    """Loading a parent session shows BranchMarkers at each fork's divergence point."""
    from wingman.app import WingmanApp
    from wingman.sessions import fork_session_copy, save_session

    parent_messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
    ]
    save_session("parent", parent_messages, working_dir="/tmp")
    fork_session_copy("f-at-2", parent_messages[:2], "parent", 2, working_dir="/tmp")
    fork_session_copy("f-at-4", parent_messages[:4], "parent", 4, working_dir="/tmp")

    app = WingmanApp()
    async with app.run_test() as pilot:
        await pilot.pause()  # let initial welcome render first; load wipes it after
        app.active_panel.load_session("parent")
        await pilot.pause()

        markers = _marker_widgets(app.active_panel)
        assert len(markers) == 2
        fork_ids = sorted(m.fork_session_id for m in markers)
        assert fork_ids == ["f-at-2", "f-at-4"]


@pytest.mark.asyncio
async def test_session_with_no_forks_renders_no_markers(isolated_sessions):
    from wingman.app import WingmanApp
    from wingman.sessions import save_session

    save_session("lonely", [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}])
    app = WingmanApp()
    async with app.run_test() as pilot:
        await pilot.pause()  # let initial welcome render first; load wipes it after
        app.active_panel.load_session("lonely")
        await pilot.pause()
        assert _marker_widgets(app.active_panel) == []


@pytest.mark.asyncio
async def test_marker_click_opens_fork_in_new_panel(isolated_sessions):
    """Posting OpenFork on the marker opens the child session in a new panel."""
    from wingman.app import WingmanApp
    from wingman.sessions import fork_session_copy, save_session
    from wingman.ui.widgets import BranchMarker

    save_session("p", [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}])
    fork_session_copy("child", [{"role": "user", "content": "q"}], "p", 1)

    app = WingmanApp()
    async with app.run_test() as pilot:
        await pilot.pause()  # let initial welcome render first; load wipes it after
        app.active_panel.load_session("p")
        await pilot.pause()

        markers = _marker_widgets(app.active_panel)
        assert len(markers) == 1
        markers[0].post_message(BranchMarker.OpenFork("child"))
        await pilot.pause()
        await pilot.pause()

        assert len(app.panels) == 2
        assert app.panels[1].session_id == "child"


@pytest.mark.asyncio
async def test_marker_click_focuses_fork_if_already_open(isolated_sessions):
    """Clicking a marker when the fork is already in a panel focuses it, no duplicate."""
    from wingman.app import WingmanApp
    from wingman.sessions import fork_session_copy, save_session
    from wingman.ui.widgets import BranchMarker

    save_session("p", [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}])
    fork_session_copy("child", [{"role": "user", "content": "q"}], "p", 1)

    app = WingmanApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.active_panel.load_session("p")
        await pilot.pause()

        markers = _marker_widgets(app.active_panel)
        # First click: opens the fork in panel 1.
        markers[0].post_message(BranchMarker.OpenFork("child"))
        await pilot.pause()
        await pilot.pause()
        assert len(app.panels) == 2
        assert app.panels[1].session_id == "child"

        # Switch focus back to the parent panel and click again.
        app._set_active_panel(0)
        await pilot.pause()
        markers[0].post_message(BranchMarker.OpenFork("child"))
        await pilot.pause()
        await pilot.pause()

        # No duplicate panel: same count, focus moved to the existing fork panel.
        assert len(app.panels) == 2, "marker re-click must not duplicate the panel"
        assert app.active_panel_idx == 1
        assert app.active_panel.session_id == "child"


@pytest.mark.asyncio
async def test_fork_live_injects_marker_into_parent(isolated_sessions):
    """After /fork, the parent panel shows a new BranchMarker without manual reload."""
    from wingman.app import WingmanApp
    from wingman.sessions import save_session

    save_session(
        "p",
        [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}],
    )

    app = WingmanApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.active_panel.load_session("p")
        await pilot.pause()
        await pilot.pause()
        assert _marker_widgets(app.active_panel) == []

        app._cmd_fork("0")  # full clone via shortcut, no modal
        await pilot.pause()
        await pilot.pause()

        assert len(app.panels) == 2
        parent_panel = app.panels[0]
        markers = _marker_widgets(parent_panel)
        assert len(markers) == 1, f"Parent should have 1 marker after fork; got {len(markers)}"


@pytest.mark.asyncio
async def test_head_fork_marker_renders_at_end(isolated_sessions):
    """A fork with forked_at_index == len(messages) lands AFTER the last message."""
    from wingman.app import WingmanApp
    from wingman.sessions import fork_session_copy, save_session
    from wingman.ui.widgets import BranchMarker, ChatMessage

    msgs = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
    save_session("p", msgs)
    fork_session_copy("head-fork", msgs, "p", len(msgs))

    app = WingmanApp()
    async with app.run_test() as pilot:
        await pilot.pause()  # let initial welcome render first; load wipes it after
        app.active_panel.load_session("p")
        await pilot.pause()

        chat = app.active_panel.get_chat_container()
        children = list(chat.children)
        # Find the last ChatMessage and the BranchMarker: the marker must come after.
        last_chat_idx = max(i for i, w in enumerate(children) if isinstance(w, ChatMessage))
        marker_idx = next(i for i, w in enumerate(children) if isinstance(w, BranchMarker))
        assert marker_idx > last_chat_idx


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
