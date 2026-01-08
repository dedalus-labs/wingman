"""Tests for bulletin system."""

from datetime import datetime, timezone

from wingman.bulletin import (
    Bulletin,
    BulletinManager,
    Conditions,
    _compare_versions,
    evaluate_conditions,
    load_from_yaml,
)


class TestYamlParsing:
    """Test YAML parsing."""

    def test_parse_banner(self, banner_yaml):
        """Parse a simple banner."""
        bulletins = load_from_yaml(banner_yaml)
        assert len(bulletins) == 1
        b = bulletins[0]
        assert b.id == "test-banner"
        assert b.type == "banner"
        assert "[bold]" in b.content
        assert b.priority == 10
        assert b.dismissible is True

    def test_parse_multiple_tips(self, tip_yaml):
        """Parse multiple tips."""
        bulletins = load_from_yaml(tip_yaml)
        assert len(bulletins) == 2
        assert bulletins[0].id == "tip-1"
        assert bulletins[1].id == "tip-2"

    def test_invalid_yaml(self):
        """Gracefully handle invalid YAML."""
        assert load_from_yaml("not: valid: yaml: {{") == []
        assert load_from_yaml("") == []
        assert load_from_yaml("messages: null") == []


class TestConditions:
    """Test condition evaluation."""

    def test_no_conditions(self):
        """No conditions = always show."""
        assert evaluate_conditions(None) is True

    def test_expired_until(self):
        """Message with past 'until' should not show."""
        cond = Conditions(until=datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert evaluate_conditions(cond) is False

    def test_future_from(self):
        """Message with future 'from' should not show."""
        cond = Conditions(from_time=datetime(2099, 1, 1, tzinfo=timezone.utc))
        assert evaluate_conditions(cond) is False

    def test_active_window(self):
        """Message within time window should show."""
        cond = Conditions(
            from_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
            until=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        assert evaluate_conditions(cond) is True

    def test_platform_match(self):
        """Platform condition matching."""
        import sys

        cond = Conditions(platforms=[sys.platform])
        assert evaluate_conditions(cond) is True

        cond = Conditions(platforms=["nonexistent-platform"])
        assert evaluate_conditions(cond) is False

    def test_conditional_yaml_filtering(self, conditional_yaml):
        """Integration: filter bulletins by conditions."""
        bulletins = load_from_yaml(conditional_yaml)
        active = [b for b in bulletins if evaluate_conditions(b.conditions)]
        assert len(active) == 1
        assert active[0].id == "active"


class TestVersionCompare:
    """Test semver comparison."""

    def test_equal(self):
        assert _compare_versions("1.0.0", "1.0.0") == 0
        assert _compare_versions("2.1", "2.1.0") == 0

    def test_less_than(self):
        assert _compare_versions("1.0.0", "2.0.0") == -1
        assert _compare_versions("1.0.0", "1.1.0") == -1
        assert _compare_versions("1.0.0", "1.0.1") == -1

    def test_greater_than(self):
        assert _compare_versions("2.0.0", "1.0.0") == 1
        assert _compare_versions("1.1.0", "1.0.0") == 1


class TestBulletinManager:
    """Test BulletinManager."""

    def test_dismiss_in_memory(self, banner_yaml):
        """Dismiss keeps bulletin out of active list."""
        mgr = BulletinManager()
        mgr._loaded["test"] = load_from_yaml(banner_yaml)

        assert len(mgr.get_active("test")) == 1
        mgr.dismiss("test-banner")
        assert len(mgr.get_active("test")) == 0

    def test_dismiss_include_dismissed(self, banner_yaml):
        """Can still get dismissed bulletins if requested."""
        mgr = BulletinManager()
        mgr._loaded["test"] = load_from_yaml(banner_yaml)

        mgr.dismiss("test-banner")
        assert len(mgr.get_active("test", include_dismissed=True)) == 1

    def test_priority_sorting(self):
        """Higher priority bulletins come first."""
        mgr = BulletinManager()
        mgr._loaded["test"] = [
            Bulletin(id="low", type="tip", content="low", priority=1),
            Bulletin(id="high", type="tip", content="high", priority=100),
            Bulletin(id="mid", type="tip", content="mid", priority=50),
        ]

        active = mgr.get_active("test")
        assert [b.id for b in active] == ["high", "mid", "low"]


class TestDevMode:
    """Test dev mode detection."""

    def test_env_var_override(self, monkeypatch, tmp_path):
        """WINGMAN_BULLETIN_PATH overrides default."""
        from wingman.bulletin import _get_bulletin_dir

        bulletin_dir = tmp_path / "bulletin"
        bulletin_dir.mkdir()

        monkeypatch.setenv("WINGMAN_BULLETIN_PATH", str(bulletin_dir))
        assert _get_bulletin_dir() == bulletin_dir

    def test_invalid_path_falls_through(self, monkeypatch):
        """Invalid path doesn't crash."""
        from wingman.bulletin import _get_bulletin_dir

        monkeypatch.setenv("WINGMAN_BULLETIN_PATH", "/nonexistent/path")
        # Should not raise, just return None or fallback
        _get_bulletin_dir()
