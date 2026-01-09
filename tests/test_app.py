"""Tests for WingmanApp UI interactions"""

import pytest


class TestPanelManagement:
    """Test panel split, close, and focus."""

    @pytest.mark.asyncio
    async def test_initial_single_panel(self):
        """App starts with one panel."""
        from wingman.app import WingmanApp

        app = WingmanApp()
        async with app.run_test() as _pilot:
            assert len(app.panels) == 1
            assert app.active_panel_idx == 0

    @pytest.mark.asyncio
    async def test_split_creates_panel(self):
        """Splitting creates a second panel."""
        from wingman.app import WingmanApp

        app = WingmanApp()
        async with app.run_test() as pilot:
            assert len(app.panels) == 1
            app.action_split_panel()
            await pilot.pause()
            assert len(app.panels) == 2

    @pytest.mark.asyncio
    async def test_close_panel_requires_multiple(self):
        """Cannot close the last panel. Use Ctrl+C to quit."""
        from wingman.app import WingmanApp

        app = WingmanApp()
        async with app.run_test() as pilot:
            assert len(app.panels) == 1
            app.action_close_panel()
            await pilot.pause()
            # Still has one panel
            assert len(app.panels) == 1

    @pytest.mark.asyncio
    async def test_close_panel_with_multiple(self):
        """Can close panel when multiple exist."""
        from wingman.app import WingmanApp

        app = WingmanApp()
        async with app.run_test() as pilot:
            app.action_split_panel()
            await pilot.pause()
            assert len(app.panels) == 2

            app.action_close_panel()
            await pilot.pause()
            assert len(app.panels) == 1


class TestPanelNavigation:
    """Test panel focus and navigation."""

    @pytest.mark.asyncio
    async def test_next_prev_panel(self):
        """Navigate between panels with actions."""
        from wingman.app import WingmanApp

        app = WingmanApp()
        async with app.run_test() as pilot:
            app.action_split_panel()
            await pilot.pause()

            # Still on panel 0 after split
            assert app.active_panel_idx == 0

            app.action_next_panel()
            await pilot.pause()
            assert app.active_panel_idx == 1

            app.action_prev_panel()
            await pilot.pause()
            assert app.active_panel_idx == 0

    @pytest.mark.asyncio
    async def test_goto_panel(self):
        """Jump to specific panel by number."""
        from wingman.app import WingmanApp

        app = WingmanApp()
        async with app.run_test() as pilot:
            app.action_split_panel()
            app.action_split_panel()
            await pilot.pause()
            assert len(app.panels) == 3

            app.action_goto_panel_1()
            await pilot.pause()
            assert app.active_panel_idx == 0


class TestCtrlCBehavior:
    """Test Ctrl+C quit behavior."""

    @pytest.mark.asyncio
    async def test_ctrl_c_clears_input(self):
        """Ctrl+C clears input if text present."""
        from wingman.app import WingmanApp

        app = WingmanApp()
        async with app.run_test() as pilot:
            # Type something
            await pilot.press("h", "e", "l", "l", "o")
            await pilot.pause()

            panel = app.active_panel
            input_widget = panel.get_input()
            assert input_widget.value == "hello"

            # Ctrl+C should clear
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert input_widget.value == ""

    @pytest.mark.asyncio
    async def test_ctrl_c_double_tap_exits(self):
        """Double Ctrl+C exits app."""
        from wingman.app import WingmanApp

        app = WingmanApp()
        async with app.run_test() as pilot:
            # First Ctrl+C
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert app.last_ctrl_c is not None

            # Second Ctrl+C within timeout should exit
            # (Best effort: can't easily test exit, but we can verify state)
