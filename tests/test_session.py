"""Tests for SessionManager and SessionConfig.

Coverage:
  - SessionManager creation (directory, naming, base creation, uniqueness)
  - SessionConfig injection (format, separator, defaults)
  - Path helpers (file, subdir, truediv)
  - Alternative constructor: in_temp()
  - Static helper: latest()
  - Repr
"""

import re
from pathlib import Path

import pytest

from session_manager import SessionConfig, SessionManager


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def base(tmp_path: Path) -> Path:
    return tmp_path / "results"


# ── SessionManager creation ────────────────────────────────────────────────────

class TestSessionManagerCreation:
    def test_creates_session_dir(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.session_dir.exists()
        assert sm.session_dir.is_dir()

    def test_session_dir_under_base(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.session_dir.parent == base.resolve()

    def test_folder_name_contains_name_and_timestamp(self, base: Path) -> None:
        sm = SessionManager(base, name="analysis")
        pattern = r"^analysis_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"
        assert re.match(pattern, sm.session_dir.name)

    def test_no_name_uses_timestamp_only(self, base: Path) -> None:
        sm = SessionManager(base, name="")
        pattern = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"
        assert re.match(pattern, sm.session_dir.name)

    def test_creates_base_dir_if_missing(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c"
        assert not deep.exists()
        SessionManager(deep, name="run")
        assert deep.exists()

    def test_two_instances_get_different_dirs(self, base: Path) -> None:
        import time
        sm1 = SessionManager(base, name="run")
        time.sleep(1.1)
        sm2 = SessionManager(base, name="run")
        assert sm1.session_dir != sm2.session_dir


# ── SessionConfig injection ────────────────────────────────────────────────────

class TestSessionConfig:
    def test_custom_timestamp_format(self, base: Path) -> None:
        cfg = SessionConfig(timestamp_format="%Y%m%d")
        sm = SessionManager(base, name="run", config=cfg)
        pattern = r"^run_\d{8}$"
        assert re.match(pattern, sm.session_dir.name)

    def test_custom_separator(self, base: Path) -> None:
        cfg = SessionConfig(separator="--")
        sm = SessionManager(base, name="run", config=cfg)
        assert sm.session_dir.name.startswith("run--")

    def test_default_config_used_when_none(self, base: Path) -> None:
        sm = SessionManager(base, name="run", config=None)
        pattern = r"^run_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"
        assert re.match(pattern, sm.session_dir.name)


# ── Path helpers ───────────────────────────────────────────────────────────────

class TestPathHelpers:
    def test_file_returns_path_inside_session(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        p = sm.file("output.csv")
        assert p.parent == sm.session_dir
        assert p.name == "output.csv"

    def test_file_accepts_multiple_parts(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        p = sm.file("plots", "volcano.png")
        assert p == sm.session_dir / "plots" / "volcano.png"

    def test_subdir_creates_directory(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        d = sm.subdir("plots")
        assert d.exists()
        assert d.is_dir()

    def test_subdir_returns_correct_path(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        d = sm.subdir("nested", "deep")
        assert d == sm.session_dir / "nested" / "deep"
        assert d.exists()

    def test_truediv_shorthand(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm / "file.txt" == sm.session_dir / "file.txt"


# ── in_temp ───────────────────────────────────────────────────────────────────

class TestInTemp:
    def test_creates_dir_in_system_temp(self) -> None:
        import tempfile
        sm = SessionManager.in_temp(name="tmp_run")
        assert sm.session_dir.exists()
        assert str(sm.session_dir).startswith(str(Path(tempfile.gettempdir()).resolve()))

    def test_classmethod_returns_correct_type(self) -> None:
        sm = SessionManager.in_temp(name="tmp_run")
        assert isinstance(sm, SessionManager)

    def test_subclass_in_temp_returns_subclass(self) -> None:
        class MySession(SessionManager):
            pass

        sm = MySession.in_temp(name="sub")
        assert type(sm) is MySession

    def test_accepts_config(self) -> None:
        cfg = SessionConfig(timestamp_format="%Y%m%d")
        sm = SessionManager.in_temp(name="run", config=cfg)
        import re
        assert re.match(r"^run_\d{8}$", sm.session_dir.name)


# ── latest ─────────────────────────────────────────────────────────────────────

class TestLatest:
    def test_returns_most_recent_session(self, base: Path) -> None:
        import time
        sm1 = SessionManager(base, name="run")
        time.sleep(1.1)
        sm2 = SessionManager(base, name="run")
        assert SessionManager.latest(base) == sm2.session_dir

    def test_filters_by_name(self, base: Path) -> None:
        import time
        sm_a = SessionManager(base, name="preprocess")
        time.sleep(1.1)
        sm_b = SessionManager(base, name="train")
        latest_pre = SessionManager.latest(base, name="preprocess")
        assert latest_pre == sm_a.session_dir

    def test_raises_if_dir_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            SessionManager.latest(tmp_path / "nonexistent")

    def test_raises_if_no_sessions(self, base: Path) -> None:
        base.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError):
            SessionManager.latest(base)

    def test_raises_if_no_matching_name(self, base: Path) -> None:
        SessionManager(base, name="run")
        with pytest.raises(ValueError):
            SessionManager.latest(base, name="other")

    def test_accepts_string_path(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        result = SessionManager.latest(str(base))
        assert result == sm.session_dir

    def test_config_separator_avoids_prefix_ambiguity(self, base: Path) -> None:
        """'run' must not match 'run_extra' when config pins the separator."""
        import time
        cfg = SessionConfig(separator="_")
        sm_run = SessionManager(base, name="run", config=cfg)
        time.sleep(1.1)
        sm_extra = SessionManager(base, name="run_extra", config=cfg)
        # without config both would match startswith("run")
        # with config only "run_" prefix is accepted
        result = SessionManager.latest(base, name="run", config=cfg)
        assert result == sm_run.session_dir

    def test_custom_separator_exact_match(self, base: Path) -> None:
        """latest() with config finds sessions created with the same separator."""
        cfg = SessionConfig(separator="--")
        sm = SessionManager(base, name="preprocess", config=cfg)
        result = SessionManager.latest(base, name="preprocess", config=cfg)
        assert result == sm.session_dir

    def test_no_config_falls_back_to_startswith(self, base: Path) -> None:
        """Without config, any separator is accepted (loose match)."""
        cfg = SessionConfig(separator="--")
        sm = SessionManager(base, name="preprocess", config=cfg)
        result = SessionManager.latest(base, name="preprocess")
        assert result == sm.session_dir


# ── Repr ───────────────────────────────────────────────────────────────────────

class TestRepr:
    def test_repr_contains_class_name(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert "SessionManager" in repr(sm)

    def test_repr_contains_path(self, base: Path) -> None:
        sm = SessionManager(base, name="run")
        assert sm.session_dir.name in repr(sm)
